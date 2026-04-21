"""Prompt enhancer service — injects RAG-retrieved context into agent prompts.

Provides automatic retrieval of relevant context based on agent type and task,
with support for different context injection strategies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.observability.logger import get_logger
from src.services.retrieval_context import (
    RetrievalQuery,
    retrieve_context,
    expand_query,
    QUERY_TYPE_CORPUS_MAP,
    get_retrieval_metrics,
    get_retrieval_cache,
)

logger = get_logger("prompt_enhancer")


@dataclass
class EnhancementContext:
    """Context for prompt enhancement describing the task and agent."""

    agent_type: str = ""
    task_id: str = ""
    task_description: str = ""
    current_phase: str | None = None
    touched_paths: list[str] = field(default_factory=list)
    extra_hints: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnhancementResult:
    """Result of prompt enhancement with retrieval metrics."""

    enhanced_prompt: str
    sources_used: int = 0
    sources: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    cache_hit: bool = False
    query_expanded: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for logging/serialization."""
        return {
            "enhanced_prompt_length": len(self.enhanced_prompt),
            "sources_used": self.sources_used,
            "latency_ms": self.latency_ms,
            "cache_hit": self.cache_hit,
            "query_expanded": self.query_expanded,
        }


# Agent-specific query builders
AGENT_QUERY_PATTERNS: dict[str, Callable[[EnhancementContext], str]] = {
    "ideator": lambda ctx: f"similar tasks patterns {ctx.task_description}",
    "architect": lambda ctx: f"ADR architecture decision records {ctx.task_description}",
    "builder": lambda ctx: f"code patterns implementation {ctx.current_phase or ''} {ctx.task_description}",
    "critic": lambda ctx: f"review guidelines quality criteria {ctx.task_description}",
    "governor": lambda ctx: f"governance policies compliance {ctx.task_description}",
    "pulse": lambda ctx: f"health checks monitoring {ctx.task_description}",
    "finops": lambda ctx: f"cost optimization budget {ctx.task_description}",
    "orchestrator": lambda ctx: f"workflow patterns coordination {ctx.task_description}",
}

# Agent-specific corpus preferences
AGENT_CORPUS_MAP: dict[str, list[str]] = {
    "ideator": ["history", "plans"],
    "architect": ["specs", "plans", "history"],
    "builder": ["specs", "history"],
    "critic": ["specs", "history"],
    "governor": ["specs"],
    "pulse": ["history"],
    "finops": ["history", "plans"],
    "orchestrator": ["plans", "history"],
}

# Domain hints for common technical areas
TECH_DOMAIN_HINTS = [
    "python", "api", "test", "database", "validation",
    "async", "error", "config", "schema"
]


def _build_agent_query(context: EnhancementContext) -> str:
    """Build a retrieval query based on agent type and task context."""
    agent_type = context.agent_type.lower()

    # Use agent-specific pattern if available
    if agent_type in AGENT_QUERY_PATTERNS:
        base_query = AGENT_QUERY_PATTERNS[agent_type](context)
    else:
        # Default query pattern
        base_query = f"{context.task_description} documentation patterns"

    # Add extra context from hints
    if context.current_phase:
        base_query += f" {context.current_phase}"

    if context.touched_paths:
        # Extract file extensions/patterns for better matching
        extensions = set()
        for path in context.touched_paths:
            if "." in path:
                extensions.add(path.split(".")[-1])
        if extensions:
            base_query += f" {' '.join(extensions)}"

    return base_query.strip()


def _get_agent_corpus(agent_type: str) -> list[str]:
    """Get preferred corpus for an agent type."""
    return AGENT_CORPUS_MAP.get(agent_type.lower(), ["specs", "plans", "history"])


def _detect_domain_hints(text: str) -> list[str] | None:
    """Detect technical domain hints from text for query expansion."""
    text_lower = text.lower()
    hints = []
    for domain in TECH_DOMAIN_HINTS:
        if domain in text_lower:
            hints.append(domain)
    return hints if hints else None


def _format_retrieved_context(
    sources: list[dict[str, Any]],
    max_sources: int = 3,
    max_snippet_length: int = 400,
) -> str:
    """Format retrieved sources into a readable context block."""
    if not sources:
        return ""

    lines = ["\n--- Retrieved Context ---\n"]

    for i, source in enumerate(sources[:max_sources], 1):
        path = source.get("path", "unknown")
        corpus = source.get("corpus", "unknown")
        snippet = source.get("snippet", "")
        relevance = source.get("relevance", 0.0)

        # Truncate snippet if needed
        if len(snippet) > max_snippet_length:
            snippet = snippet[:max_snippet_length - 3] + "..."

        lines.append(f"[{i}] {path} (corpus: {corpus}, relevance: {relevance:.2f})")
        lines.append(f"    {snippet}")
        lines.append("")

    lines.append("--- End Retrieved Context ---\n")

    return "\n".join(lines)


def enhance_prompt(
    prompt: str,
    agent_type: str,
    task_context: EnhancementContext | dict[str, Any],
    *,
    injection_strategy: str = "prepend",
    top_k: int = 3,
    expand_query_terms: bool = True,
    use_cache: bool = True,
    repo_root: Path | None = None,
) -> EnhancementResult:
    """Enhance a prompt with RAG-retrieved context.

    Args:
        prompt: The original prompt to enhance
        agent_type: Type of agent (ideator, architect, builder, critic, etc.)
        task_context: Context describing the task (EnhancementContext or dict)
        injection_strategy: How to inject context ("prepend", "interleave", "append")
        top_k: Number of sources to retrieve
        expand_query_terms: Whether to expand query with related terms
        use_cache: Whether to use retrieval cache
        repo_root: Optional repository root for retrieval

    Returns:
        EnhancementResult containing enhanced prompt and metadata
    """
    start_time = time.time()

    # Normalize task_context to EnhancementContext
    if isinstance(task_context, dict):
        task_context = EnhancementContext(
            agent_type=agent_type,
            **{k: v for k, v in task_context.items() if k in EnhancementContext.__dataclass_fields__}
        )
    else:
        task_context.agent_type = agent_type

    # Build retrieval query
    retrieval_query = _build_agent_query(task_context)

    # Detect domain hints for expansion
    domain_hints = None
    if expand_query_terms:
        combined_text = f"{retrieval_query} {task_context.task_description}"
        domain_hints = _detect_domain_hints(combined_text)

    # Get corpus for agent type
    corpus = _get_agent_corpus(agent_type)

    # Create retrieval request
    request = RetrievalQuery(
        query=retrieval_query,
        corpus=corpus,
        top_k=top_k,
    )

    # Perform retrieval
    try:
        result = retrieve_context(
            request,
            repo_root=repo_root,
            use_cache=use_cache,
            expand_query_terms=expand_query_terms,
            domain_hints=domain_hints,
        )
        sources = result.get("sources", [])
        cache_hit = result.get("metrics", {}).get("backend") == "cache"  # Approximation

    except Exception as exc:
        logger.warning("enhancement.retrieval_failed error=%s", exc)
        sources = []
        cache_hit = False

    # Format retrieved context
    context_block = _format_retrieved_context(sources, max_sources=top_k)

    # Apply injection strategy
    if sources:
        if injection_strategy == "prepend":
            enhanced_prompt = f"{context_block}\n{prompt}"
        elif injection_strategy == "interleave":
            # Insert before the main task but after any instructions
            lines = prompt.split("\n")
            # Find a good insertion point (after first paragraph or instruction block)
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.strip() == "" and i > 0:
                    insert_idx = i + 1
                    break
            lines.insert(insert_idx, context_block)
            enhanced_prompt = "\n".join(lines)
        else:  # append
            enhanced_prompt = f"{prompt}\n{context_block}"
    else:
        enhanced_prompt = prompt

    latency_ms = (time.time() - start_time) * 1000

    return EnhancementResult(
        enhanced_prompt=enhanced_prompt,
        sources_used=len(sources),
        sources=sources,
        latency_ms=latency_ms,
        cache_hit=cache_hit,
        query_expanded=expand_query_terms and bool(domain_hints),
    )


def get_enhancement_metrics() -> dict[str, Any]:
    """Get metrics for prompt enhancement operations."""
    return {
        "retrieval": get_retrieval_metrics(),
        "cache": get_retrieval_cache().get_metrics(),
    }


def clear_enhancement_cache() -> None:
    """Clear the enhancement cache."""
    get_retrieval_cache().clear()
    logger.info("enhancement.cache_cleared")


# Convenience functions for specific agents

def enhance_ideator_prompt(
    prompt: str,
    task_description: str,
    **kwargs,
) -> EnhancementResult:
    """Enhance an Ideator agent prompt with task patterns."""
    context = EnhancementContext(
        agent_type="ideator",
        task_description=task_description,
    )
    return enhance_prompt(
        prompt,
        "ideator",
        context,
        injection_strategy="prepend",
        **kwargs,
    )


def enhance_architect_prompt(
    prompt: str,
    task_description: str,
    touched_paths: list[str] | None = None,
    **kwargs,
) -> EnhancementResult:
    """Enhance an Architect agent prompt with ADRs and specs."""
    context = EnhancementContext(
        agent_type="architect",
        task_description=task_description,
        touched_paths=touched_paths or [],
    )
    return enhance_prompt(
        prompt,
        "architect",
        context,
        injection_strategy="prepend",
        **kwargs,
    )


def enhance_builder_prompt(
    prompt: str,
    task_description: str,
    current_phase: str | None = None,
    touched_paths: list[str] | None = None,
    **kwargs,
) -> EnhancementResult:
    """Enhance a Builder agent prompt with code patterns."""
    context = EnhancementContext(
        agent_type="builder",
        task_description=task_description,
        current_phase=current_phase,
        touched_paths=touched_paths or [],
    )
    return enhance_prompt(
        prompt,
        "builder",
        context,
        injection_strategy="interleave",
        **kwargs,
    )


def enhance_critic_prompt(
    prompt: str,
    task_description: str,
    **kwargs,
) -> EnhancementResult:
    """Enhance a Critic agent prompt with review guidelines."""
    context = EnhancementContext(
        agent_type="critic",
        task_description=task_description,
    )
    return enhance_prompt(
        prompt,
        "critic",
        context,
        injection_strategy="prepend",
        **kwargs,
    )


__all__ = [
    "AGENT_CORPUS_MAP",
    "EnhancementContext",
    "EnhancementResult",
    "clear_enhancement_cache",
    "enhance_architect_prompt",
    "enhance_builder_prompt",
    "enhance_critic_prompt",
    "enhance_ideator_prompt",
    "enhance_prompt",
    "get_enhancement_metrics",
]

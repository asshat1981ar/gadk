from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

APPROVED_CORPORA = ("specs", "plans", "history")
DEFAULT_CORPUS = list(APPROVED_CORPORA)
PLANNING_RETRIEVAL_CAPABILITY = "planning.retrieve_context"


class RetrievalQuery(BaseModel):
    """Validated retrieval request limited to the approved planning corpus."""

    query: str = Field(min_length=1)
    corpus: list[str] = Field(default_factory=lambda: list(DEFAULT_CORPUS))
    top_k: int = Field(default=3, ge=1, le=10)

    @field_validator("corpus")
    @classmethod
    def validate_corpus(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            corpus_name = item.strip().lower()
            if corpus_name not in APPROVED_CORPORA:
                msg = f"Unsupported retrieval corpus: {item}"
                raise ValueError(msg)
            if corpus_name not in normalized:
                normalized.append(corpus_name)
        return normalized


def _repo_root(repo_root: Path | None = None) -> Path:
    return (repo_root or Path.cwd()).resolve()


def _collect_corpus_files(repo_root: Path, corpus: list[str]) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for corpus_name in corpus:
        if corpus_name == "specs":
            files.extend(
                (corpus_name, path)
                for path in sorted((repo_root / "docs/superpowers/specs").glob("**/*.md"))
                if path.is_file()
            )
        elif corpus_name == "plans":
            files.extend(
                (corpus_name, path)
                for path in sorted((repo_root / "docs/superpowers/plans").glob("**/*.md"))
                if path.is_file()
            )
        elif corpus_name == "history":
            history_path = repo_root / ".swarm_history"
            if history_path.is_file():
                files.append((corpus_name, history_path))
    return files


def _load_documents(repo_root: Path, corpus: list[str]) -> list[Any]:
    try:
        from llama_index.core import Document
    except ImportError as exc:  # pragma: no cover - guarded by environment setup
        msg = "llama-index is required for retrieval context support"
        raise RuntimeError(msg) from exc

    documents: list[Any] = []
    for corpus_name, path in _collect_corpus_files(repo_root, corpus):
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        documents.append(
            Document(
                text=content,
                metadata={
                    "path": str(path.relative_to(repo_root)),
                    "corpus": corpus_name,
                },
            )
        )
    return documents


def _build_snippet(text: str, query: str, limit: int = 240) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= limit:
        return collapsed

    for token in [part for part in re.split(r"\W+", query.lower()) if part]:
        location = collapsed.lower().find(token)
        if location >= 0:
            start = max(location - limit // 3, 0)
            end = min(start + limit, len(collapsed))
            snippet = collapsed[start:end]
            return snippet if start == 0 else f"...{snippet}"

    return f"{collapsed[:limit].rstrip()}..."


def retrieve_context(
    request: RetrievalQuery,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Retrieve opt-in planning context from the approved corpus only."""

    resolved_root = _repo_root(repo_root)
    documents = _load_documents(resolved_root, request.corpus)
    if not documents:
        return {
            "query": request.query,
            "corpus": request.corpus,
            "sources": [],
        }

    from llama_index.core import KeywordTableIndex
    from llama_index.core.llms.mock import MockLLM

    index = KeywordTableIndex.from_documents(documents, llm=MockLLM())
    retriever = index.as_retriever()
    retrieved_nodes = retriever.retrieve(request.query)[: request.top_k]

    sources: list[dict[str, Any]] = []
    for retrieved in retrieved_nodes:
        node = getattr(retrieved, "node", retrieved)
        metadata = getattr(node, "metadata", {})
        text = node.get_content()
        sources.append(
            {
                "path": metadata.get("path"),
                "corpus": metadata.get("corpus"),
                "score": getattr(retrieved, "score", None),
                "snippet": _build_snippet(text, request.query),
            }
        )

    return {
        "query": request.query,
        "corpus": request.corpus,
        "sources": sources,
    }


async def retrieve_planning_context(
    query: str,
    corpus: list[str] | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """Execute planning retrieval through the shared capability layer."""

    from src.tools.dispatcher import execute_capability

    return await execute_capability(
        PLANNING_RETRIEVAL_CAPABILITY,
        query=query,
        corpus=corpus or list(DEFAULT_CORPUS),
        top_k=top_k,
    )


__all__ = [
    "APPROVED_CORPORA",
    "DEFAULT_CORPUS",
    "PLANNING_RETRIEVAL_CAPABILITY",
    "RetrievalQuery",
    "retrieve_context",
    "retrieve_planning_context",
]

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field, field_validator

from src.config import Config
from src.observability.logger import get_logger
from src.services.vector_index import (
    SearchHit,
    VectorBackendUnavailable,
    VectorIndex,
    resolve_vector_backend,
)

logger = get_logger("retrieval_context")

APPROVED_CORPORA = ("specs", "plans", "history")
DEFAULT_CORPUS = list(APPROVED_CORPORA)
PLANNING_RETRIEVAL_CAPABILITY = "planning.retrieve_context"

# Query type mappings for different agent use cases
QUERY_TYPE_CORPUS_MAP: dict[str, list[str]] = {
    "specs": ["specs"],
    "plans": ["plans"],
    "history": ["history"],
    "adr": ["specs", "plans"],
    "patterns": ["specs", "history"],
    "guidelines": ["specs"],
    "all": list(DEFAULT_CORPUS),
}

# Cache TTL in seconds (5 minutes)
RETRIEVAL_CACHE_TTL = 300


@dataclass
class RetrievalMetrics:
    """Metrics for tracking retrieval operations."""

    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_latency_ms: float = 0.0
    errors: int = 0
    relevance_scores: list[float] = field(default_factory=list)

    def record_query(self, latency_ms: float, cache_hit: bool = False) -> None:
        self.total_queries += 1
        self.total_latency_ms += latency_ms
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def record_error(self) -> None:
        self.errors += 1

    def record_relevance(self, score: float) -> None:
        self.relevance_scores.append(score)

    @property
    def average_latency_ms(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.total_latency_ms / self.total_queries

    @property
    def average_relevance(self) -> float:
        if not self.relevance_scores:
            return 0.0
        return sum(self.relevance_scores) / len(self.relevance_scores)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_queries": self.total_queries,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hits / self.total_queries if self.total_queries > 0 else 0.0,
            "average_latency_ms": self.average_latency_ms,
            "average_relevance": self.average_relevance,
            "errors": self.errors,
        }


# Global metrics tracker
_retrieval_metrics = RetrievalMetrics()


class RetrievalCache:
    """Simple TTL cache for retrieval results."""

    def __init__(self, ttl: int = RETRIEVAL_CACHE_TTL) -> None:
        self._cache: dict[str, tuple[dict[str, Any], float]] = {}
        self._ttl = ttl

    def _make_key(self, query: str, corpus: tuple[str, ...], top_k: int) -> str:
        """Create cache key from query parameters."""
        return f"{query}:{':'.join(sorted(corpus))}:{top_k}"

    def get(self, query: str, corpus: list[str], top_k: int) -> dict[str, Any] | None:
        """Get cached result if not expired."""
        key = self._make_key(query, tuple(corpus), top_k)
        if key in self._cache:
            result, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                logger.debug("retrieval_cache.hit key=%s", key[:32])
                return result
            else:
                del self._cache[key]
        return None

    def set(self, query: str, corpus: list[str], top_k: int, result: dict[str, Any]) -> None:
        """Cache result with current timestamp."""
        key = self._make_key(query, tuple(corpus), top_k)
        self._cache[key] = (result, time.time())
        logger.debug("retrieval_cache.set key=%s", key[:32])

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def get_metrics(self) -> dict[str, Any]:
        """Return cache statistics."""
        total = len(self._cache)
        expired = sum(1 for _, ts in self._cache.values() if time.time() - ts >= self._ttl)
        return {
            "size": total,
            "expired": expired,
            "active": total - expired,
        }


# Global cache instance
_retrieval_cache = RetrievalCache()


def get_retrieval_metrics() -> dict[str, Any]:
    """Get current retrieval metrics."""
    return _retrieval_metrics.as_dict()


def reset_retrieval_metrics() -> None:
    """Reset retrieval metrics (useful for testing)."""
    global _retrieval_metrics
    _retrieval_metrics = RetrievalMetrics()


def get_retrieval_cache() -> RetrievalCache:
    """Get the global retrieval cache instance."""
    return _retrieval_cache


class RetrievalQuery(BaseModel):
    """Validated retrieval request limited to the approved planning corpus."""

    query: str = Field(min_length=1)
    corpus: list[str] = Field(default_factory=lambda: list(DEFAULT_CORPUS))
    top_k: int = Field(default=3, ge=1, le=10)
    query_type: str | None = Field(default=None, description="Type of query for corpus routing")

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

    @field_validator("query_type")
    @classmethod
    def resolve_corpus_from_type(cls, v: str | None, values) -> str | None:
        """Resolve corpus from query_type if provided."""
        if v and v in QUERY_TYPE_CORPUS_MAP:
            # Update corpus based on query type
            values.data["corpus"] = QUERY_TYPE_CORPUS_MAP[v]
        return v


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


# Expansion keywords for common technical domains
QUERY_EXPANSIONS: dict[str, list[str]] = {
    "python": ["python", "py", "pythonic"],
    "api": ["api", "rest", "endpoint", "routes"],
    "test": ["test", "testing", "pytest", "unittest"],
    "database": ["database", "db", "sql", "storage"],
    "validation": ["validation", "validate", "validator"],
    "async": ["async", "await", "asyncio", "coroutine"],
    "error": ["error", "exception", "raise", "error handling"],
    "config": ["config", "configuration", "settings", "env"],
    "schema": ["schema", "model", "pydantic", "structure"],
}


def expand_query(query: str, domain_hints: list[str] | None = None) -> str:
    """Expand a query with related terms for better matching.

    Args:
        query: The original search query
        domain_hints: Optional list of technical domains to expand

    Returns:
        Expanded query string with related terms
    """
    query_lower = query.lower()
    expanded_terms = [query]

    # Check each expansion category
    for category, terms in QUERY_EXPANSIONS.items():
        if domain_hints and category in domain_hints:
            # Include all terms from hinted category
            expanded_terms.extend(terms)
        elif any(term in query_lower for term in terms):
            # Auto-expand if query matches any term
            expanded_terms.extend(terms)

    # Remove duplicates while preserving order
    seen = set()
    unique_terms = []
    for term in expanded_terms:
        if term not in seen:
            seen.add(term)
            unique_terms.append(term)

    return " ".join(unique_terms)


def compute_relevance_score(hit: dict[str, Any]) -> float:
    """Compute a normalized relevance score for a search hit.

    Returns a score between 0.0 and 1.0 based on available metadata.
    """
    raw_score = hit.get("score")
    if raw_score is None:
        return 0.5  # Default score when no score available

    # Normalize score - different backends may have different scales
    if isinstance(raw_score, (int, float)):
        # Assume scores are between -1 and 1 or 0 and 1
        if raw_score < 0:
            return (raw_score + 1) / 2
        return min(raw_score, 1.0)

    return 0.5


def _keyword_retrieve(
    request: RetrievalQuery,
    resolved_root: Path,
) -> list[dict[str, Any]]:
    """Existing LlamaIndex keyword path — extracted so the vector branch
    can reuse it as a fallback without duplicating the loader + snippet
    logic."""
    documents = _load_documents(resolved_root, request.corpus)
    if not documents:
        return []

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
    return sources


#: Override hook for tests and callers that want to inject a custom
#: embedder (e.g., deterministic fakes). ``None`` means "use the
#: default embedder from :func:`src.services.embedder.build_default_embedder`".
_embedder_override: Any = None


def set_embedder(embedder: Any) -> None:
    """Install a custom :data:`Embedder` for the next vector-retrieve calls.

    Primarily used by tests; production code should rely on the
    Config-driven default from ``build_default_embedder``.
    """
    global _embedder_override
    _embedder_override = embedder


def _resolve_embedder():
    if _embedder_override is not None:
        return _embedder_override
    # Late import to break a potential cycle during module bootstrap.
    from src.services.embedder import build_default_embedder

    return build_default_embedder()


#: Content-hash cache keyed by ``doc_id`` so we only re-embed files whose
#: content has actually changed between calls. Process-local — safe for the
#: swarm's single-writer model; Phase 3d may move it into the backend's
#: meta table so it survives restarts.
_doc_hashes: dict[str, str] = {}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sync_corpus_to_backend(
    backend: VectorIndex,
    resolved_root: Path,
    corpus: list[str],
) -> int:
    """Bring the backend in line with the on-disk corpus.

    - Upserts only docs whose SHA-256 content hash changed.
    - Removes docs that were previously indexed but are no longer on disk.
    - Returns the number of documents currently present after sync.

    The hash cache is only written for backends that actually persist
    writes. Without that guard, a degraded run backed by ``NullVectorIndex``
    would mark every file as "current" and cause later retrievals against
    a real backend to skip them forever, leaving the index empty.
    """
    # Skip hash caching when the backend is the no-op placeholder — its
    # upsert() doesn't persist anything, so subsequent runs must still see
    # the files as "changed" and re-embed them into a real backend.
    backend_persists = getattr(backend, "name", "") != "null"

    seen_ids: set[str] = set()
    for corpus_name, path in _collect_corpus_files(resolved_root, corpus):
        try:
            text = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as exc:
            logger.debug("vector.upsert: skipping %s (%s)", path, exc)
            continue
        if not text:
            continue
        doc_id = str(path.relative_to(resolved_root))
        seen_ids.add(doc_id)
        sha = _sha(text)
        if backend_persists and _doc_hashes.get(doc_id) == sha:
            # Unchanged since last call — skip the (costly) embed.
            continue
        backend.upsert(
            doc_id=doc_id,
            text=text,
            metadata={"corpus": corpus_name, "path": doc_id},
        )
        if backend_persists:
            _doc_hashes[doc_id] = sha

    # Drop backend rows + cache entries whose source file disappeared so
    # stale embeddings don't get served in future queries. Only supported
    # on backends that expose `known_doc_ids` / `delete` (SqliteVecBackend);
    # the NullVectorIndex no-ops both. IMPORTANT: scope the cleanup to the
    # corpora we actually synced this call — without that restriction,
    # retrieving only `specs` would wipe all `plans` / `history` docs from
    # the shared index.
    if hasattr(backend, "known_doc_ids") and hasattr(backend, "delete"):
        try:
            in_scope = backend.known_doc_ids(corpora=corpus)
        except TypeError:
            # Older backend without the corpus filter — fall back to
            # full scan (matches pre-fix behavior). This path is
            # intentionally conservative.
            in_scope = backend.known_doc_ids()
        for stale_id in in_scope - seen_ids:
            backend.delete(stale_id)
            _doc_hashes.pop(stale_id, None)

    return len(seen_ids)


def _vector_retrieve(
    request: RetrievalQuery,
    resolved_root: Path,
) -> list[dict[str, Any]]:
    """Vector-backed retrieval path.

    When no embedder is available (test mode, missing API key, or no
    override installed) ``resolve_vector_backend`` returns a
    :class:`NullVectorIndex` and the caller falls back to keyword
    retrieval with a ``retrieval.degraded`` log line.
    """
    embedder = _resolve_embedder()
    backend = resolve_vector_backend(embedder=embedder)

    # Ensure backend connections (e.g., SqliteVecBackend) are released
    # even if upsert/query raises. The NullVectorIndex has no close().
    try:
        any_docs = _sync_corpus_to_backend(backend, resolved_root, request.corpus) > 0
        if not any_docs:
            # Match the keyword path: empty corpus returns no sources rather
            # than provoking a backend.query() that would raise on some
            # implementations.
            return []

        hits: list[SearchHit] = backend.query(request.query, top_k=request.top_k)
        return [
            {
                "path": h.metadata.get("path", h.doc_id),
                "corpus": h.metadata.get("corpus"),
                "score": h.score,
                "snippet": _build_snippet(h.text, request.query),
            }
            for h in hits
        ]
    finally:
        if hasattr(backend, "close"):
            backend.close()


def retrieve_context(
    request: RetrievalQuery,
    *,
    repo_root: Path | None = None,
    use_cache: bool = True,
    expand_query_terms: bool = False,
    domain_hints: list[str] | None = None,
) -> dict[str, Any]:
    """Retrieve opt-in planning context from the approved corpus only.

    Routes through the configured retrieval backend (``Config.RETRIEVAL_BACKEND``).
    When the vector backend is requested but unavailable, emits a structured
    ``retrieval.degraded`` log line and falls back to keyword retrieval so
    callers always get a best-effort result.

    Args:
        request: The retrieval query containing query string, corpus, and top_k
        repo_root: Optional repository root path (defaults to current working directory)
        use_cache: Whether to check cache for results (default: True)
        expand_query_terms: Whether to expand query with related terms (default: False)
        domain_hints: Optional technical domain hints for query expansion
    """
    global _retrieval_metrics, _retrieval_cache

    resolved_root = _repo_root(repo_root)
    backend_name = (Config.RETRIEVAL_BACKEND or "keyword").strip().lower()

    # Expand query if requested
    if expand_query_terms:
        request.query = expand_query(request.query, domain_hints)

    # Check cache first
    if use_cache:
        cached = _retrieval_cache.get(request.query, request.corpus, request.top_k)
        if cached:
            start_time = time.time()
            _retrieval_metrics.record_query(0.0, cache_hit=True)
            logger.debug("retrieval.cache.hit query=%s", request.query[:50])
            return cached

    # Track latency
    start_time = time.time()
    sources: list[dict[str, Any]] = []

    try:
        if backend_name in {"vector", "sqlite-vec", "sqlitevec"}:
            try:
                sources = _vector_retrieve(request, resolved_root)
            except VectorBackendUnavailable as exc:
                logger.warning(
                    "retrieval.degraded backend=%s reason=%s falling_back=keyword",
                    backend_name,
                    exc,
                )
                sources = _keyword_retrieve(request, resolved_root)
            except Exception as exc:  # noqa: BLE001
                # Broader safety net: sqlite-vec extension misconfigured,
                # schema migration failures, OpenRouter transport errors, etc.
                # The documented contract is best-effort fallback to keyword;
                # surface the actual exception on the same `retrieval.degraded`
                # channel so it's still visible in logs.
                logger.warning(
                    "retrieval.degraded backend=%s unexpected_error=%s:%s falling_back=keyword",
                    backend_name,
                    type(exc).__name__,
                    exc,
                )
                sources = _keyword_retrieve(request, resolved_root)
        else:
            sources = _keyword_retrieve(request, resolved_root)

        # Compute relevance scores
        for source in sources:
            relevance = compute_relevance_score(source)
            source["relevance"] = relevance
            _retrieval_metrics.record_relevance(relevance)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        _retrieval_metrics.record_query(latency_ms, cache_hit=False)

    except Exception as exc:
        _retrieval_metrics.record_error()
        logger.error("retrieval.error error=%s query=%s", exc, request.query[:50])
        raise

    result = {
        "query": request.query,
        "corpus": request.corpus,
        "sources": sources,
        "metrics": {
            "latency_ms": latency_ms if 'latency_ms' in locals() else None,
            "backend": backend_name,
            "sources_count": len(sources),
        },
    }

    # Cache the result
    if use_cache:
        _retrieval_cache.set(request.query, request.corpus, request.top_k, result)

    return result


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
    "QUERY_TYPE_CORPUS_MAP",
    "RetrievalCache",
    "RetrievalMetrics",
    "RetrievalQuery",
    "compute_relevance_score",
    "expand_query",
    "get_retrieval_cache",
    "get_retrieval_metrics",
    "reset_retrieval_metrics",
    "retrieve_context",
    "retrieve_planning_context",
]

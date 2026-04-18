"""Tests for SqliteVecBackend._open_db error paths (issue #35).

These tests inject a broken sqlite_vec stub so they run even when the
real sqlite-vec extension is not installed in the test environment.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence
from pathlib import Path

import pytest

from src.services.vector_index import (
    SqliteVecBackend,
    VectorBackendUnavailable,
)


def _make_fake_embedder(dim: int = 32) -> object:
    def _embed(texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            bucket = [0.0] * dim
            normalized = text.lower().strip()
            if not normalized:
                out.append([0.0] * dim)
                continue
            for word in normalized.replace("-", " ").split():
                h = hashlib.md5(word.encode()).digest()
                idx = int.from_bytes(h[:4], "big") % dim
                bucket[idx] += 1.0
            norm = math.sqrt(sum(v * v for v in bucket)) or 1.0
            out.append([v / norm for v in bucket])
        return out

    return _embed


# ---------------------------------------------------------------------------
# Issue #35: SqliteVecBackend._open_db logs and chains load failure
# ---------------------------------------------------------------------------


def test_open_db_chains_load_failure_as_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When sqlite_vec.load raises, VectorBackendUnavailable.__cause__ is the original error."""
    import src.services.vector_index as vi_mod

    class _BrokenSqliteVec:
        @staticmethod
        def load(conn):
            raise RuntimeError("extension load failed: wrong architecture")

    monkeypatch.setattr(vi_mod, "_sqlite_vec", _BrokenSqliteVec)
    monkeypatch.setattr(vi_mod, "_SQLITE_VEC_AVAILABLE", True)

    with pytest.raises(VectorBackendUnavailable) as exc_info:
        SqliteVecBackend(
            embedder=_make_fake_embedder(dim=32),
            db_path=tmp_path / "fail.db",
            dim=32,
        )

    assert exc_info.value.__cause__ is not None
    assert "extension load failed" in str(exc_info.value.__cause__)


def test_open_db_load_failure_logs_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When sqlite_vec.load raises, a WARNING is emitted with the original error details."""
    import src.services.vector_index as vi_mod

    class _BrokenSqliteVec:
        @staticmethod
        def load(conn):
            raise OSError("missing symbol _vec_init")

    monkeypatch.setattr(vi_mod, "_sqlite_vec", _BrokenSqliteVec)
    monkeypatch.setattr(vi_mod, "_SQLITE_VEC_AVAILABLE", True)

    with caplog.at_level(logging.WARNING, logger="vector_index"):
        with pytest.raises(VectorBackendUnavailable):
            SqliteVecBackend(
                embedder=_make_fake_embedder(dim=32),
                db_path=tmp_path / "fail2.db",
                dim=32,
            )

    assert any("sqlite_vec.load failed" in r.message for r in caplog.records)

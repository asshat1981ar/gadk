"""Test deprecation of src/services/self_prompt.py gap-collection functions.

These functions are superseded by ReflectionNode (src/orchestration/reflection_node.py).
Once all callers are migrated, this module should be removed.
"""
from __future__ import annotations

import warnings
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestSelfPromptDeprecation:
    """Deprecation warnings for collect_* functions."""

    def test_collect_coverage_signals_emits_deprecation(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Import the module (trigger lazy warning if any at import time)
            import src.services.self_prompt as self_prompt

            # Call the function
            result = self_prompt.collect_coverage_signals(Path("nonexistent.xml"))

            # Should return empty list for missing file
            assert result == []
            # A deprecation warning should have been raised about this function
            deprecations = [x for x in w if "collect_coverage_signals" in str(x.message)]
            assert len(deprecations) >= 1, (
                f"Expected deprecation warning for collect_coverage_signals, got: {[str(x.message) for x in w]}"
            )
            assert "ReflectionNode" in str(deprecations[0].message)

    def test_collect_event_log_signals_emits_deprecation(self, tmp_path):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import src.services.self_prompt as self_prompt

            # Create minimal state for StateManager (uses cwd)
            from src.state import StateManager

            sm = StateManager()
            result = self_prompt.collect_event_log_signals(sm, limit=10)

            # Should return empty list for fresh state
            assert result == []
            deprecations = [x for x in w if "collect_event_log_signals" in str(x.message)]
            assert len(deprecations) >= 1, (
                f"Expected deprecation warning for collect_event_log_signals, got: {[str(x.message) for x in w]}"
            )
            assert "ReflectionNode" in str(deprecations[0].message)

    def test_collect_backlog_signals_emits_deprecation(self, tmp_path):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import src.services.self_prompt as self_prompt

            queue_path = tmp_path / "prompt_queue.jsonl"
            result = self_prompt.collect_backlog_signals(queue_path, max_age_hours=12.0)

            # Should return empty list for missing queue
            assert result == []
            deprecations = [x for x in w if "collect_backlog_signals" in str(x.message)]
            assert len(deprecations) >= 1, (
                f"Expected deprecation warning for collect_backlog_signals, got: {[str(x.message) for x in w]}"
            )
            assert "ReflectionNode" in str(deprecations[0].message)

    def test_run_once_emits_deprecation(self, tmp_path):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import src.services.self_prompt as self_prompt

            from src.state import StateManager

            sm = StateManager()
            result = self_prompt.run_once(sm=sm, queue_path=tmp_path / "queue.jsonl")

            # Should return empty list
            assert result == []
            deprecations = [x for x in w if "run_once" in str(x.message)]
            assert len(deprecations) >= 1, (
                f"Expected deprecation warning for run_once, got: {[str(x.message) for x in w]}"
            )
            assert "ReflectionNode" in str(deprecations[0].message)

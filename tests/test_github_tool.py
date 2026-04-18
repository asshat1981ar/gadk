"""Tests for src.tools.github_tool — MockGithub gating and error paths."""

from __future__ import annotations

import importlib
import sys

import pytest

import src.tools.github_tool as github_tool


def test_mock_module_exports_expected_surface() -> None:
    """The extracted mock module exposes the names the tool imports."""
    mocks = importlib.import_module("src.testing.github_mocks")
    assert hasattr(mocks, "Github")
    gh = mocks.Github(token="fake")
    repo = gh.get_repo("mock/repo")
    assert hasattr(repo, "create_issue")
    assert hasattr(repo, "get_pulls")


def test_github_api_errors_tuple_contains_expected_types() -> None:
    assert ConnectionError in github_tool._GITHUB_API_ERRORS
    assert TimeoutError in github_tool._GITHUB_API_ERRORS


def test_github_retryable_error_is_runtimeerror() -> None:
    assert issubclass(github_tool.GitHubRetryableError, RuntimeError)


def test_sanitize_review_section_leaves_bodies_without_marker_unchanged() -> None:
    body = "No markers here. Just plain text."
    assert github_tool._sanitize_review_section(body) == body


class _StubRepo:
    """Minimal stub to exercise error paths without PyGithub."""

    def __init__(self, *, raise_on: str | None = None) -> None:
        self._raise_on = raise_on

    def create_issue(self, title: str, body: str):
        if self._raise_on == "create":
            raise ConnectionError("network down")

        class _Issue:
            html_url = "https://example/issues/1"

        return _Issue()

    def get_issues(self, state: str = "open"):
        return []


@pytest.mark.asyncio
async def test_create_issue_returns_error_string_on_api_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = github_tool.GitHubTool.__new__(github_tool.GitHubTool)
    tool.repo = _StubRepo(raise_on="create")  # type: ignore[attr-defined]
    tool.gh = None  # type: ignore[attr-defined]
    out = await tool.create_issue("t", "b")
    assert out.startswith("Error creating issue:")


@pytest.mark.asyncio
async def test_create_issue_returns_not_configured_when_repo_missing() -> None:
    tool = github_tool.GitHubTool.__new__(github_tool.GitHubTool)
    tool.repo = None  # type: ignore[attr-defined]
    tool.gh = None  # type: ignore[attr-defined]
    out = await tool.create_issue("t", "b")
    assert "Repository not configured" in out


def test_pygithub_missing_raises_when_mock_not_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prod default: import-time failure if PyGithub is missing and mock is off."""
    # Force a fresh config read with both flags off.
    monkeypatch.delenv("GITHUB_MOCK_ALLOWED", raising=False)
    monkeypatch.setenv("GITHUB_MOCK_ALLOWED", "false")
    monkeypatch.setenv("TEST_MODE", "false")

    # Rebuild Config so the new env is visible.
    import src.config as config_mod

    config_mod.get_settings.cache_clear()
    monkeypatch.setattr(config_mod.Config, "GITHUB_MOCK_ALLOWED", False)
    monkeypatch.setattr(config_mod.Config, "TEST_MODE", False)

    saved_github = sys.modules.get("github")
    sys.modules["github"] = None  # type: ignore[assignment]
    sys.modules.pop("src.tools.github_tool", None)
    try:
        with pytest.raises(RuntimeError, match="PyGithub is not installed"):
            importlib.import_module("src.tools.github_tool")
    finally:
        if saved_github is not None:
            sys.modules["github"] = saved_github
        else:
            sys.modules.pop("github", None)
        sys.modules.pop("src.tools.github_tool", None)
        # Re-enable the mock path so subsequent test collection succeeds
        # even though monkeypatch teardown has not yet run.
        import os as _os

        _os.environ["GITHUB_MOCK_ALLOWED"] = "true"
        _os.environ["TEST_MODE"] = "true"
        config_mod.get_settings.cache_clear()
        config_mod.Config.GITHUB_MOCK_ALLOWED = True
        config_mod.Config.TEST_MODE = True
        importlib.import_module("src.tools.github_tool")

"""Tests for src.tools.github_tool — MockGithub gating and error paths."""

from __future__ import annotations

import importlib

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

    def get_branch(self, name: str):
        if self._raise_on == "get_branch":
            raise ConnectionError("branch not found")

        class _Branch:
            class commit:
                sha = "abc123"

        return _Branch()

    def create_git_ref(self, ref: str, sha: str):
        if self._raise_on == "create_git_ref":
            raise TimeoutError("network timeout creating ref")

    def create_pull(self, title: str, body: str, head: str, base: str):
        class _PR:
            html_url = "https://example/pull/1"

        return _PR()


# ---------------------------------------------------------------------------
# Issue #35: create_pull_request error chaining
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pull_request_chains_inner_error_as_cause() -> None:
    """When get_branch raises then create_git_ref fails, __cause__ carries the original error."""

    class _TwoStageRepo:
        """get_branch(head) raises; get_branch(base) succeeds; create_git_ref raises."""

        def get_branch(self, name: str):
            if name != "main":
                raise ConnectionError("branch not found")

            class _Branch:
                class commit:
                    sha = "abc123"

            return _Branch()

        def create_git_ref(self, ref: str, sha: str):
            raise TimeoutError("network timeout creating ref")

        def create_pull(self, title, body, head, base):
            raise AssertionError("should not reach create_pull")  # pragma: no cover

    tool = github_tool.GitHubTool.__new__(github_tool.GitHubTool)
    tool.repo = _TwoStageRepo()  # type: ignore[attr-defined]
    tool.gh = None  # type: ignore[attr-defined]

    result = await tool.create_pull_request(
        title="Test PR",
        body="some body text that is long enough to pass the low-value guard check",
        head="my-branch",
    )
    # Should return an error string (not raise), but the inner cause should be chained.
    assert result.startswith("Error creating PR:")


@pytest.mark.asyncio
async def test_create_pull_request_error_cause_is_original_branch_error() -> None:
    """__cause__ on create_git_ref failure is the branch-lookup exception."""
    captured_exc: list[BaseException] = []

    class _ChainCheckRepo:
        def get_branch(self, name: str):
            if name != "main":
                raise ConnectionError("original branch error")

            class _Branch:
                class commit:
                    sha = "abc123"

            return _Branch()

        def create_git_ref(self, ref: str, sha: str):
            raise TimeoutError("create ref failed")

        def create_pull(self, title, body, head, base):
            raise AssertionError("should not reach create_pull")  # pragma: no cover

    tool = github_tool.GitHubTool.__new__(github_tool.GitHubTool)
    tool.repo = _ChainCheckRepo()  # type: ignore[attr-defined]
    tool.gh = None  # type: ignore[attr-defined]

    # Patch the logger.error to capture the exc_info
    import logging

    class _CapHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.exc_info and record.exc_info[1]:
                captured_exc.append(record.exc_info[1])

    handler = _CapHandler()
    import src.tools.github_tool as _gh_mod

    _gh_mod.logger.addHandler(handler)  # type: ignore[attr-defined]
    try:
        result = await tool.create_pull_request(
            title="Test PR",
            body="some body text that is long enough to pass the low-value guard check",
            head="my-branch",
        )
        assert result.startswith("Error creating PR:")
        assert captured_exc, "expected logger.error to emit with exc_info"
        # The chained __cause__ must be the original branch error
        outer_exc = captured_exc[0]
        assert isinstance(outer_exc.__cause__, ConnectionError)
        assert "original branch error" in str(outer_exc.__cause__)
    finally:
        _gh_mod.logger.removeHandler(handler)  # type: ignore[attr-defined]


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
    """Prod default: constructor-time failure if PyGithub is missing and mock is off.

    After the validator refactor, the PyGithub availability check was deferred
    from module import to ``GitHubTool.__init__`` so a late
    ``os.environ["GITHUB_MOCK_ALLOWED"]="true"`` is honoured. The regression
    guard therefore has to instantiate the tool, not just import the module.
    """
    import src.config as config_mod
    import src.tools.github_tool as gh_mod

    monkeypatch.setattr(config_mod.Config, "GITHUB_MOCK_ALLOWED", False)
    monkeypatch.setattr(config_mod.Config, "TEST_MODE", False)
    # Force ``_PYGITHUB_AVAILABLE=False`` so __init__ hits the missing-PyGithub
    # branch even in envs where the package is installed.
    monkeypatch.setattr(gh_mod, "_PYGITHUB_AVAILABLE", False)
    # Reset the cached settings so the constructor re-reads the overridden flags.
    config_mod.get_settings.cache_clear()
    # github_tool imports ``get_settings`` at module scope, so patch the
    # reference bound in ``gh_mod`` (not just ``config_mod``).
    fake_settings = config_mod.Settings(github_mock_allowed=False, test_mode=False)
    monkeypatch.setattr(gh_mod, "get_settings", lambda: fake_settings)

    with pytest.raises(RuntimeError, match="PyGithub is not installed"):
        gh_mod.GitHubTool()

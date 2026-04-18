import asyncio

from tenacity import wait_none

import src.tools.github_tool as github_tool
from src.tools.github_tool import GitHubTool


def test_github_tool_has_pr_methods():
    gh = GitHubTool()
    assert hasattr(gh, "create_pull_request")
    assert hasattr(gh, "list_pull_requests")
    assert hasattr(gh, "review_pull_request")


def test_list_pull_requests_returns_list():
    gh = GitHubTool()
    # May return empty list if repo not configured, but shouldn't crash
    result = asyncio.run(gh.list_pull_requests())
    assert isinstance(result, list)


def test_read_repo_file_retries_transient_content_errors(monkeypatch):
    monkeypatch.setattr(github_tool, "_GITHUB_RETRY_WAIT", wait_none())

    class FakeContent:
        decoded_content = b"retry success"

    class FakeRepo:
        def __init__(self):
            self.calls = 0

        def get_contents(self, path, ref=None):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary github error")
            return FakeContent()

    gh = GitHubTool()
    gh.repo = FakeRepo()

    result = asyncio.run(gh.read_repo_file("README.md"))

    assert result == "retry success"
    assert gh.repo.calls == 2

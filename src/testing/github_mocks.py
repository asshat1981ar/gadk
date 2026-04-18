"""In-process PyGithub-shaped mocks for tests and explicit offline mode.

Only imported by ``src.tools.github_tool`` when PyGithub is unavailable AND
``Config.GITHUB_MOCK_ALLOWED`` is True. In production the missing-dependency
path raises ``RuntimeError`` at import time instead of silently degrading.
"""

from __future__ import annotations

import base64


class MockContent:
    def __init__(self, path: str, type_: str, content: bytes | None = None) -> None:
        self.path = path
        self.name = path.rsplit("/", 1)[-1]
        self.type = type_
        self._content = content

    @property
    def content(self) -> str:
        return base64.b64encode(self._content).decode() if self._content else ""

    @property
    def decoded_content(self) -> bytes:
        return self._content or b""


class MockIssue:
    html_url = "https://github.com/mock/repo/issues/1"
    number = 1
    title = "Mock Title"
    state = "open"

    class _Head:
        ref = "mock-branch"

    head = _Head()


class _MockBranch:
    class _Commit:
        sha = "mocksha"

    commit = _Commit()


class _MockPR:
    def create_review(self, body: str, event: str) -> None:
        return None


class MockRepo:
    def create_issue(self, title: str, body: str) -> MockIssue:
        return MockIssue()

    def get_issues(self, state: str = "open") -> list[MockIssue]:
        return []

    def get_branch(self, name: str) -> _MockBranch:
        return _MockBranch()

    def create_git_ref(self, ref: str, sha: str) -> None:
        return None

    def create_pull(self, title: str, body: str, head: str, base: str) -> MockIssue:
        return MockIssue()

    def get_pulls(self, state: str) -> list[MockIssue]:
        return []

    def get_pull(self, number: int) -> _MockPR:
        return _MockPR()

    def get_contents(self, path: str, ref: str | None = None) -> MockContent | list[MockContent]:
        if not path:
            return [MockContent("README.md", "file"), MockContent("src", "dir")]
        return MockContent(path, "file", content=b"mock content")


class Github:
    def __init__(self, token: str | None) -> None:
        self._token = token

    def get_repo(self, name: str) -> MockRepo:
        return MockRepo()


__all__ = ["Github", "MockContent", "MockIssue", "MockRepo"]

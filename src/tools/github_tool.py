import asyncio

try:
    from github import Github
except ImportError:
    # Mock for environment where PyGithub is not installed
    class Github:
        def __init__(self, token): pass
        def get_repo(self, name): return MockRepo()
    class MockRepo:
        def create_issue(self, title, body): return MockIssue()
        def get_branch(self, name):
            class MockBranch:
                class MockCommit:
                    sha = "mocksha"
                commit = MockCommit()
            return MockBranch()
        def create_git_ref(self, ref, sha): pass
        def create_pull(self, title, body, head, base): return MockIssue()
        def get_pulls(self, state): return []
        def get_pull(self, number):
            class MockPR:
                def create_review(self, body, event): pass
            return MockPR()
        def get_contents(self, path, ref=None):
            if not path:
                return [MockContent("README.md", "file"), MockContent("src", "dir")]
            return MockContent(path, "file", content=b"mock content")
    class MockContent:
        def __init__(self, path, type, content=None):
            self.path = path
            self.type = type
            self._content = content
        @property
        def content(self):
            import base64
            return base64.b64encode(self._content).decode() if self._content else ""
        @property
        def decoded_content(self):
            return self._content or b""
    class MockIssue:
        html_url = "https://github.com/mock/repo/issues/1"
        number = 1
        title = "Mock Title"
        state = "open"
        class MockHead:
            ref = "mock-branch"
        head = MockHead()

try:
    from google.adk import Tool
except ImportError:
    class Tool:
        pass

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import Config
from src.observability.metrics import tool_timer

_GITHUB_RETRY_WAIT = wait_exponential(multiplier=0.01, min=0, max=0.05)


class GitHubRetryableError(RuntimeError):
    """Raised for transient GitHub content reads that should be retried."""


class GitHubTool(Tool):
    def __init__(self):
        self.gh = Github(Config.GITHUB_TOKEN)
        # Handle case where repo name might not be set
        repo_name = Config.REPO_NAME or "unknown/repo"
        try:
            self.repo = self.gh.get_repo(repo_name)
        except Exception:
            self.repo = None

    @retry(
        stop=stop_after_attempt(3),
        wait=_GITHUB_RETRY_WAIT,
        retry=retry_if_exception_type(GitHubRetryableError),
        reraise=True,
    )
    def _get_contents_with_retry(self, path: str, ref: str | None = None):
        """Retry narrow repository content reads without broad refactors."""
        try:
            return self.repo.get_contents(path, ref=ref)
        except Exception as exc:
            raise GitHubRetryableError(str(exc)) from exc

    @tool_timer("GitHubTool")
    async def create_issue(self, title, body):
        if not self.repo:
            return "Error: Repository not configured or not found"
        try:
            issue = self.repo.create_issue(title=title, body=body)
            return issue.html_url
        except Exception as e:
            return f"Error creating issue: {str(e)}"

    async def create_pull_request(self, title: str, body: str, head: str, base: str = "main") -> str:
        if not self.repo:
            return "Error: Repository not configured or not found"
        try:
            # Ensure branch exists; if not, create it from base
            try:
                self.repo.get_branch(head)
            except Exception:
                default_branch = self.repo.get_branch(base)
                self.repo.create_git_ref(ref=f"refs/heads/{head}", sha=default_branch.commit.sha)
            pr = self.repo.create_pull(title=title, body=body, head=head, base=base)
            return pr.html_url
        except Exception as e:
            return f"Error creating PR: {str(e)}"

    async def list_pull_requests(self, state: str = "open") -> list:
        if not self.repo:
            return []
        try:
            prs = self.repo.get_pulls(state=state)
            return [
                {
                    "number": p.number,
                    "title": p.title,
                    "state": p.state,
                    "url": p.html_url,
                    "head": p.head.ref,
                }
                for p in prs
            ]
        except Exception as e:
            return []

    async def review_pull_request(self, pr_number: int, body: str, event: str = "COMMENT") -> str:
        if not self.repo:
            return "Error: Repository not configured or not found"
        try:
            pr = self.repo.get_pull(pr_number)
            pr.create_review(body=body, event=event)
            return f"Reviewed PR #{pr_number}"
        except Exception as e:
            return f"Error reviewing PR: {str(e)}"

    async def merge_pull_request(self, pr_number: int, commit_message: str = None) -> str:
        if not self.repo:
            return "Error: Repository not configured or not found"
        try:
            pr = self.repo.get_pull(pr_number)
            merge_result = pr.merge(commit_message=commit_message or f"Merge PR #{pr_number}")
            return f"Merged PR #{pr_number}: {merge_result.sha}"
        except Exception as e:
            return f"Error merging PR: {str(e)}"

    @tool_timer("GitHubTool")
    async def create_or_update_file(self, path: str, content: str, message: str, branch: str, base: str = "main") -> str:
        """Create or update a file in a specific branch via GitHub API."""
        if not self.repo:
            return "Error: Repository not configured or not found"
        try:
            # Ensure branch exists
            try:
                self.repo.get_branch(branch)
            except Exception:
                default_branch = self.repo.get_branch(base)
                self.repo.create_git_ref(ref=f"refs/heads/{branch}", sha=default_branch.commit.sha)
            # Try to get existing file for sha
            try:
                existing = self.repo.get_contents(path, ref=branch)
                if isinstance(existing, list):
                    existing = existing[0]
                self.repo.update_file(path, message, content, existing.sha, branch=branch)
                return f"Updated {path} in {branch}"
            except Exception:
                self.repo.create_file(path, message, content, branch=branch)
                return f"Created {path} in {branch}"
        except Exception as e:
            return f"Error creating/updating file: {str(e)}"

    @tool_timer("GitHubTool")
    async def commit_files_to_branch(self, files: dict, message: str, branch: str, base: str = "main") -> str:
        """Commit multiple files to a branch. files = {path: content}."""
        if not self.repo:
            return "Error: Repository not configured or not found"
        results = []
        for path, content in files.items():
            result = await self.create_or_update_file(path, content, f"{message} - {path}", branch, base)
            results.append(result)
        return "\n".join(results)

    @tool_timer("GitHubTool")
    async def read_repo_file(self, path: str) -> str:
        """
        Read a file from the configured GitHub repository.

        Args:
            path: Repository-relative file path (e.g., 'README.md', 'src/main.py').

        Returns:
            File contents as a string.
        """
        if not self.repo:
            return "Error: Repository not configured or not found"
        try:
            content_file = await asyncio.to_thread(self._get_contents_with_retry, path)
            if isinstance(content_file, list):
                return f"Error: {path} is a directory, not a file"
            return content_file.decoded_content.decode("utf-8")
        except Exception as e:
            return f"Error reading file: {str(e)}"

    @tool_timer("GitHubTool")
    async def list_repo_contents(self, path: str = "") -> list:
        """
        List files and directories in the configured GitHub repository.

        Args:
            path: Repository-relative directory path. Defaults to repository root.

        Returns:
            List of dicts with 'name', 'path', and 'type' ('file' or 'dir').
        """
        if not self.repo:
            return []
        try:
            contents = await asyncio.to_thread(self._get_contents_with_retry, path)
            if not isinstance(contents, list):
                contents = [contents]
            return [
                {"name": c.name, "path": c.path, "type": c.type}
                for c in contents
            ]
        except Exception as e:
            return []


# Standalone wrappers for agent tool registration (lazy instantiation)
_gh_tool_instance = None

def _get_gh_tool() -> GitHubTool:
    global _gh_tool_instance
    if _gh_tool_instance is None:
        _gh_tool_instance = GitHubTool()
    return _gh_tool_instance


async def read_repo_file(path: str) -> str:
    """Read a file from the configured GitHub repository."""
    return await _get_gh_tool().read_repo_file(path)


async def list_repo_contents(path: str = "") -> list:
    """List files and directories in the configured GitHub repository."""
    return await _get_gh_tool().list_repo_contents(path)

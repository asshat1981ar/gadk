import asyncio
import logging

from src.config import Config, get_settings

_PYGITHUB_AVAILABLE = True
try:
    from github import Github
except ImportError:  # pragma: no cover — branch depends on environment
    _PYGITHUB_AVAILABLE = False

try:
    from google.adk import Tool
except ImportError:

    class Tool:  # type: ignore[no-redef]
        pass


from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    from github import GithubException  # type: ignore[import]
except ImportError:  # pragma: no cover

    class GithubException(Exception):  # type: ignore[no-redef]
        """PyGithub-compatible fallback exception for offline/test mode."""


from src.observability.metrics import tool_timer
from src.tools.content_guards import (
    LEAKED_REVIEW_PLACEHOLDER,
    is_low_value_content,
    sanitize_review,
)

logger = logging.getLogger(__name__)

#: Narrow exception tuple for GitHub API boundaries. Broader than
#: ``GithubException`` because network and auth errors surface as other
#: exception types, but narrower than bare ``Exception``.
_GITHUB_API_ERRORS: tuple[type[BaseException], ...] = (
    GithubException,
    ConnectionError,
    TimeoutError,
    ValueError,
    KeyError,
)

_GITHUB_RETRY_WAIT = wait_exponential(multiplier=0.01, min=0, max=0.05)

#: Default cap for the open-issue scan used by create_issue dedup. The
#: runtime value comes from ``Config.GITHUB_DEDUP_ISSUE_SCAN_LIMIT`` so
#: operators can tune it without patching code; the module-level constant
#: stays as a fallback for callers that construct ``GitHubTool`` before
#: Config is initialized (import-time paths).
_DEDUP_OPEN_ISSUE_SCAN_LIMIT = 100

#: Token used in issue bodies to mark the critic review section. Keep in sync
#: with the body template in autonomous_sdlc.py / android_rpg_sdlc.py.
_CRITIC_REVIEW_MARKER = "**Critic Review:**"
_REVIEW_MARKER = "**Review:**"


class GitHubRetryableError(RuntimeError):
    """Raised for transient GitHub content reads that should be retried."""


def _sanitize_review_section(body: str) -> str:
    """Run sanitize_review over the content after a Critic Review / Review marker.

    The SDLC pipelines build issue and PR bodies like::

        **Critic Review:**
        <raw agent output, possibly JSON leakage>

    We walk the body, find the marker, sanitize everything after it up to the
    next ``---`` separator (or end of body), and splice the clean version
    back in. If no marker is found, the body is returned unchanged.
    """
    for marker in (_CRITIC_REVIEW_MARKER, _REVIEW_MARKER):
        idx = body.find(marker)
        if idx == -1:
            continue
        head = body[: idx + len(marker)]
        tail = body[idx + len(marker) :]
        # Review runs until a trailing separator (Feature Discovery footer etc.)
        # or the end of the body.
        sep_idx = tail.find("\n---")
        if sep_idx == -1:
            review_part, footer = tail, ""
        else:
            review_part, footer = tail[:sep_idx], tail[sep_idx:]
        cleaned = sanitize_review(review_part)
        return f"{head}\n{cleaned}{footer}"
    return body


class GitHubTool(Tool):
    def __init__(self):
        # Resolve the Github class at constructor time so that a late
        # os.environ["GITHUB_MOCK_ALLOWED"]="true" (or TEST_MODE) is
        # honoured even when PyGithub was unavailable at module-import time.
        if _PYGITHUB_AVAILABLE:
            _gh_cls = Github
        else:  # pragma: no cover — branch depends on environment
            settings = get_settings()
            if settings.github_mock_allowed or settings.test_mode:
                from src.testing.github_mocks import Github as _gh_cls  # type: ignore[assignment]
            else:
                raise RuntimeError(
                    "PyGithub is not installed but GITHUB_MOCK_ALLOWED is False. "
                    "Install PyGithub (`pip install pygithub`) or set GITHUB_MOCK_ALLOWED=true "
                    "for offline/test use only."
                ) from None
        self.gh = _gh_cls(Config.GITHUB_TOKEN)
        # Handle case where repo name might not be set
        repo_name = Config.REPO_NAME or "unknown/repo"
        try:
            self.repo = self.gh.get_repo(repo_name)
        except _GITHUB_API_ERRORS as exc:
            logger.warning("GitHubTool: failed to resolve repo '%s': %s", repo_name, exc)
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
        except _GITHUB_API_ERRORS as exc:
            raise GitHubRetryableError(str(exc)) from exc

    def _find_duplicate_open_issue(self, title: str):
        """Return an existing open issue whose title matches ``title`` (case-insensitive,
        whitespace-normalized), or None. Swallows errors — dedup is best-effort."""
        from src.tools.content_guards import _normalize_title  # local to keep public API small

        target = _normalize_title(title)
        try:
            # PyGithub's get_issues is paginated and lazy; slice to bound the scan.
            for idx, issue in enumerate(self.repo.get_issues(state="open")):
                if idx >= getattr(
                    Config, "GITHUB_DEDUP_ISSUE_SCAN_LIMIT", _DEDUP_OPEN_ISSUE_SCAN_LIMIT
                ):
                    break
                # Skip pull requests — they show up in issues/ but we dedup those separately.
                if getattr(issue, "pull_request", None):
                    continue
                if _normalize_title(issue.title) == target:
                    return issue
        except _GITHUB_API_ERRORS as exc:  # pragma: no cover — observability only
            logger.warning("dedup scan failed, filing anyway: %s", exc)
        return None

    @tool_timer("GitHubTool")
    async def create_issue(self, title, body):
        """Create an issue, with dedup against open issues + review-section sanitization.

        If an open issue with the same title (normalized) already exists,
        returns that issue's URL instead of filing a duplicate. The body is
        scanned for a ``**Critic Review:**`` section and any tool-call-JSON
        leakage in that section is replaced with a placeholder marker before
        the issue is filed.
        """
        if not self.repo:
            return "Error: Repository not configured or not found"

        # Dedup: don't file a new issue if an equivalent open one exists.
        existing = await asyncio.to_thread(self._find_duplicate_open_issue, title)
        if existing is not None:
            logger.info(
                "create_issue: skipping duplicate of open issue #%s (%s)",
                existing.number,
                existing.html_url,
            )
            return existing.html_url

        clean_body = _sanitize_review_section(body or "")
        try:
            issue = self.repo.create_issue(title=title, body=clean_body)
            return issue.html_url
        except _GITHUB_API_ERRORS as exc:
            logger.error("create_issue failed: %s", exc, exc_info=True)
            return f"Error creating issue: {exc}"

    async def create_pull_request(
        self, title: str, body: str, head: str, base: str = "main"
    ) -> str:
        """Open a PR, with review-section sanitization and an empty-body guard.

        Refuses to file the PR if the body (after sanitization) contains nothing
        but the leaked-review placeholder — that's the signal that the Critic
        produced no usable review and the pipeline should not have reached this
        call. Pipelines are expected to check ``is_low_value_content`` on the
        generated code before calling this, but we defend in depth here anyway.
        """
        if not self.repo:
            return "Error: Repository not configured or not found"

        clean_body = _sanitize_review_section(body or "")

        # Defense in depth: if the only thing the body has to say is "the
        # review was leakage", refuse to ship. Real PRs have task description
        # text around the review section.
        if is_low_value_content(clean_body.replace(LEAKED_REVIEW_PLACEHOLDER, ""), min_bytes=40):
            msg = "Error creating PR: body is empty or contains only leaked review"
            logger.warning("create_pull_request refused: %s (head=%s)", msg, head)
            return msg

        try:
            # Ensure branch exists; if not, create it from base
            try:
                self.repo.get_branch(head)
            except _GITHUB_API_ERRORS as exc:
                default_branch = self.repo.get_branch(base)
                try:
                    self.repo.create_git_ref(
                        ref=f"refs/heads/{head}", sha=default_branch.commit.sha
                    )
                except _GITHUB_API_ERRORS as create_exc:
                    raise create_exc from exc
            pr = self.repo.create_pull(title=title, body=clean_body, head=head, base=base)
            return pr.html_url
        except _GITHUB_API_ERRORS as exc:
            logger.error("create_pull_request failed: %s", exc, exc_info=True)
            return f"Error creating PR: {exc}"

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
        except _GITHUB_API_ERRORS as exc:
            logger.warning("list_pull_requests failed: %s", exc)
            return []

    async def review_pull_request(self, pr_number: int, body: str, event: str = "COMMENT") -> str:
        if not self.repo:
            return "Error: Repository not configured or not found"
        try:
            pr = self.repo.get_pull(pr_number)
            pr.create_review(body=body, event=event)
            return f"Reviewed PR #{pr_number}"
        except _GITHUB_API_ERRORS as exc:
            logger.error("review_pull_request(%s) failed: %s", pr_number, exc)
            return f"Error reviewing PR: {exc}"

    async def merge_pull_request(self, pr_number: int, commit_message: str = None) -> str:
        if not self.repo:
            return "Error: Repository not configured or not found"
        try:
            pr = self.repo.get_pull(pr_number)
            merge_result = pr.merge(commit_message=commit_message or f"Merge PR #{pr_number}")
            return f"Merged PR #{pr_number}: {merge_result.sha}"
        except _GITHUB_API_ERRORS as exc:
            logger.error("merge_pull_request(%s) failed: %s", pr_number, exc)
            return f"Error merging PR: {exc}"

    @tool_timer("GitHubTool")
    async def create_or_update_file(
        self, path: str, content: str, message: str, branch: str, base: str = "main"
    ) -> str:
        """Create or update a file in a specific branch via GitHub API."""
        if not self.repo:
            return "Error: Repository not configured or not found"
        try:
            # Ensure branch exists
            try:
                self.repo.get_branch(branch)
            except _GITHUB_API_ERRORS:
                default_branch = self.repo.get_branch(base)
                self.repo.create_git_ref(ref=f"refs/heads/{branch}", sha=default_branch.commit.sha)
            # Try to get existing file for sha
            try:
                existing = self.repo.get_contents(path, ref=branch)
                if isinstance(existing, list):
                    existing = existing[0]
                self.repo.update_file(path, message, content, existing.sha, branch=branch)
                return f"Updated {path} in {branch}"
            except _GITHUB_API_ERRORS:
                self.repo.create_file(path, message, content, branch=branch)
                return f"Created {path} in {branch}"
        except _GITHUB_API_ERRORS as exc:
            logger.error("create_or_update_file failed (%s): %s", path, exc, exc_info=True)
            return f"Error creating/updating file: {exc}"

    @tool_timer("GitHubTool")
    async def commit_files_to_branch(
        self, files: dict, message: str, branch: str, base: str = "main"
    ) -> str:
        """Commit multiple files to a branch. files = {path: content}."""
        if not self.repo:
            return "Error: Repository not configured or not found"
        results = []
        for path, content in files.items():
            result = await self.create_or_update_file(
                path, content, f"{message} - {path}", branch, base
            )
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
        except (GitHubRetryableError, *_GITHUB_API_ERRORS, UnicodeDecodeError) as exc:
            logger.warning("read_repo_file(%s) failed: %s", path, exc)
            return f"Error reading file: {exc}"

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
            return [{"name": c.name, "path": c.path, "type": c.type} for c in contents]
        except (GitHubRetryableError, *_GITHUB_API_ERRORS) as exc:
            logger.warning("list_repo_contents(%s) failed: %s", path, exc)
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

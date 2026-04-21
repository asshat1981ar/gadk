"""Tests for the Builder agent's pure tool functions."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import ArchitectureNote directly from architect module
from src.agents.architect import ArchitectureNote
from src.agents.builder import (
    apply_code_changes,
    create_branch,
    create_builder_pr,
    generate_pr_body,
    generate_pr_title,
    run_tests_locally,
)


@pytest.fixture
def sample_architecture_note() -> ArchitectureNote:
    """Create a sample ArchitectureNote for testing."""
    return ArchitectureNote(
        task_id="test-task-001",
        title="Add user authentication module",
        context="Users need to authenticate before accessing protected resources.",
        decision="Implement JWT-based authentication with middleware.",
        consequences=["Increased security", "Requires token refresh logic"],
        alternatives_considered=["Session-based auth", "OAuth only"],
        touched_paths=["src/auth/jwt.py", "src/auth/middleware.py"],
    )


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create project structure
        Path(tmpdir, "src").mkdir()
        Path(tmpdir, "tests").mkdir()
        Path(tmpdir, "requirements.txt").write_text("pytest\n")
        yield tmpdir


class TestCreateBranch:
    """Tests for create_branch function."""

    @pytest.mark.asyncio
    async def test_create_branch_success(self):
        """Test successful branch creation."""
        with patch("src.agents.builder.GitHubTool") as MockGH:
            mock_gh = MagicMock()
            mock_gh.create_branch = AsyncMock(return_value="refs/heads/feature/test-task-001")
            MockGH.return_value = mock_gh

            result = await create_branch(
                task_id="test-task-001",
                base="main",
            )

            assert isinstance(result, dict)
            assert "branch_name" in result
            assert "feature/test-task-001" in result["branch_name"]
            assert result["base"] == "main"

    @pytest.mark.asyncio
    async def test_create_branch_errorHandling(self):
        """Test branch creation error handling."""
        with patch("src.agents.builder.GitHubTool") as MockGH:
            mock_gh = MagicMock()
            mock_gh.create_branch = AsyncMock(side_effect=Exception("API error"))
            MockGH.return_value = mock_gh

            # Should handle errors gracefully
            result = await create_branch(
                task_id="test-task-001",
                base="main",
            )
            # Returns dict with error info on failure path
            assert isinstance(result, dict)


class TestApplyCodeChanges:
    """Tests for apply_code_changes function."""

    @pytest.mark.asyncio
    async def test_apply_single_file_change(self, temp_project_dir):
        """Test applying a single file change."""
        with patch("src.agents.builder._PROJECT_ROOT", Path(temp_project_dir)):
            changes = {
                "src/new_file.py": "print('hello')",
            }

            result = await apply_code_changes(
                changes=changes,
                branch_name="feature/test",
            )

            assert isinstance(result, dict)
            assert result["files_written"] == 1
            assert len(result["results"]) == 1
            assert "src/new_file.py" in result["results"][0]

    @pytest.mark.asyncio
    async def test_apply_multiple_files(self, temp_project_dir):
        """Test applying multiple file changes."""
        with patch("src.agents.builder._PROJECT_ROOT", Path(temp_project_dir)):
            changes = {
                "src/auth/jwt.py": "def decode_token(token): pass",
                "src/auth/middleware.py": "class AuthMiddleware: pass",
            }

            result = await apply_code_changes(
                changes=changes,
                branch_name="feature/test",
            )

            assert isinstance(result, dict)
            assert result["files_written"] == 2

    @pytest.mark.asyncio
    async def test_apply_empty_changes(self):
        """Test applying empty changes raises error."""
        result = await apply_code_changes(
            changes={},
            branch_name="feature/test",
        )

        assert isinstance(result, dict)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_apply_invalid_path(self, temp_project_dir):
        """Test applying changes with invalid path fails safely."""
        with patch("src.agents.builder._PROJECT_ROOT", Path(temp_project_dir)):
            changes = {
                "/etc/passwd": "malicious",
            }

            result = await apply_code_changes(
                changes=changes,
                branch_name="feature/test",
            )

            assert isinstance(result, dict)
            # Should report 0 successful writes and an error
            assert result["files_written"] == 0


class TestRunTestsLocally:
    """Tests for run_tests_locally function."""

    @pytest.mark.asyncio
    async def test_run_tests_success(self):
        """Test successful test execution."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "3 passed"
        mock_result.stderr = ""

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = AsyncMock(
                communicate=AsyncMock(return_value=(b"3 passed", b"")),
                returncode=0,
            )

            result = await run_tests_locally(
                test_paths=["tests/"],
                timeout=30,
            )

            assert isinstance(result, dict)
            assert result["success"] is True
            assert "3 passed" in result["stdout"]

    @pytest.mark.asyncio
    async def test_run_tests_failure(self):
        """Test test failure handling."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = AsyncMock(
                communicate=AsyncMock(return_value=(b"", b"1 failed")),
                returncode=1,
            )

            result = await run_tests_locally(
                test_paths=["tests/"],
                timeout=30,
            )

            assert isinstance(result, dict)
            assert result["success"] is False
            assert "failed" in result["stdout"].lower() or "1 failed" in result["stderr"]

    @pytest.mark.asyncio
    async def test_run_tests_timeout(self):
        """Test test execution timeout."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Simulate timeout by having communicate raise asyncio.TimeoutError
            proc = AsyncMock()
            proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            proc.kill = MagicMock()
            mock_exec.return_value = proc

            result = await run_tests_locally(
                test_paths=["tests/"],
                timeout=1,
            )

            assert isinstance(result, dict)
            assert result["success"] is False
            # Check that timeout message is in stderr
            assert "timed out" in result.get("stderr", "").lower() or "Timeout" in result.get(
                "stderr", ""
            )


class TestGeneratePRTitle:
    """Tests for generate_pr_title function."""

    def test_generate_pr_title(self, sample_architecture_note):
        """Test PR title generation."""
        title = generate_pr_title(sample_architecture_note)

        assert isinstance(title, str)
        assert len(title) > 0
        assert "Add user authentication module" in title

    def test_generate_pr_title_truncation(self):
        """Test PR title truncation for long titles."""
        note = ArchitectureNote(
            task_id="t1",
            title="A very long title that exceeds the GitHub PR title limit of 256 characters "
            * 10,
            context="test",
            decision="test",
        )

        title = generate_pr_title(note)

        assert isinstance(title, str)
        assert len(title) <= 256


class TestGeneratePRBody:
    """Tests for generate_pr_body function."""

    def test_generate_pr_body_contains_sections(self, sample_architecture_note):
        """Test PR body contains expected sections."""
        body = generate_pr_body(sample_architecture_note)

        assert isinstance(body, str)
        assert "## Description" in body
        assert "## Context" in body
        assert "## Decision" in body
        assert "## Changes" in body
        assert "## Testing" in body
        assert "src/auth/jwt.py" in body
        assert "src/auth/middleware.py" in body

    def test_generate_pr_body_with_all_fields(self):
        """Test PR body with all architecture note fields."""
        note = ArchitectureNote(
            task_id="task-123",
            title="Feature X",
            context="We need feature X",
            decision="Implement X using Y",
            consequences=["Pro: faster", "Con: more complex"],
            alternatives_considered=["Option A", "Option B"],
            touched_paths=["src/x.py", "tests/x_test.py"],
        )

        body = generate_pr_body(note)

        assert "We need feature X" in body
        assert "Implement X using Y" in body
        assert "faster" in body
        assert "more complex" in body
        assert "Option A" in body
        assert "Option B" in body


class TestCreateBuilderPR:
    """Tests for create_builder_pr function."""

    @pytest.mark.asyncio
    async def test_create_pr_success(self, sample_architecture_note):
        """Test successful PR creation."""
        with patch("src.agents.builder.GitHubTool") as MockGH:
            mock_gh = MagicMock()
            mock_gh.create_pull_request = AsyncMock(
                return_value="https://github.com/owner/repo/pull/123"
            )
            MockGH.return_value = mock_gh

            result = await create_builder_pr(
                note=sample_architecture_note,
                branch_name="feature/test-task-001",
            )

            assert isinstance(result, dict)
            assert result["success"] is True
            assert result["pr_url"] == "https://github.com/owner/repo/pull/123"
            assert "branch_name" in result

    @pytest.mark.asyncio
    async def test_create_pr_errorHandling(self, sample_architecture_note):
        """Test PR creation error handling."""
        with patch("src.agents.builder.GitHubTool") as MockGH:
            mock_gh = MagicMock()
            mock_gh.create_pull_request = AsyncMock(side_effect=Exception("GitHub API error"))
            MockGH.return_value = mock_gh

            result = await create_builder_pr(
                note=sample_architecture_note,
                branch_name="feature/test-task-001",
            )

            assert isinstance(result, dict)
            assert result["success"] is False
            assert "error" in result


class TestBuilderWorkflow:
    """Integration-style tests for the builder workflow."""

    @pytest.mark.asyncio
    async def test_full_implementation_workflow(self, sample_architecture_note, temp_project_dir):
        """Test the complete implementation workflow."""
        with patch("src.agents.builder._PROJECT_ROOT", Path(temp_project_dir)):
            with patch("src.agents.builder.GitHubTool") as MockGH:
                mock_gh = MagicMock()
                mock_gh.create_pull_request = AsyncMock(
                    return_value="https://github.com/owner/repo/pull/456"
                )
                MockGH.return_value = mock_gh

                # Apply code changes
                changes = {
                    "src/auth/jwt.py": "def decode_token(t): return {}",
                    "src/auth/middleware.py": "class Middleware: pass",
                }
                apply_result = await apply_code_changes(changes, "feature/auth")
                assert apply_result["files_written"] == 2

                # Create PR
                pr_result = await create_builder_pr(
                    note=sample_architecture_note,
                    branch_name="feature/auth",
                )
                assert pr_result["success"] is True
                assert pr_result["pr_url"] is not None

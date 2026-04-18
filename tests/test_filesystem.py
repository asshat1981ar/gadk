"""Tests for filesystem tools with guardrails."""


import pytest

from src.tools import filesystem as fs


@pytest.fixture
def temp_project(tmp_path):
    """Temporarily override the project root for isolated tests."""
    original_root = fs._PROJECT_ROOT
    fs._PROJECT_ROOT = tmp_path
    yield tmp_path
    fs._PROJECT_ROOT = original_root


class TestReadFile:
    def test_reads_existing_file(self, temp_project):
        test_file = temp_project / "src" / "hello.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("print('hello')", encoding="utf-8")

        result = fs.read_file("src/hello.py")
        assert result == "print('hello')"

    def test_file_not_found(self, temp_project):
        with pytest.raises(fs.FilesystemGuardrailError, match="File not found"):
            fs.read_file("nonexistent.py")

    def test_path_is_directory(self, temp_project):
        (temp_project / "src").mkdir()
        with pytest.raises(fs.FilesystemGuardrailError, match="not a file"):
            fs.read_file("src")

    def test_traversal_blocked(self, temp_project):
        with pytest.raises(fs.FilesystemGuardrailError, match="traversal"):
            fs.read_file("../outside.txt")

    def test_absolute_outside_blocked(self, temp_project):
        with pytest.raises(fs.FilesystemGuardrailError, match="Absolute paths"):
            fs.read_file("/etc/passwd")

    def test_denylist_blocks_sensitive(self, temp_project):
        secret = temp_project / ".env"
        secret.write_text("SECRET=1", encoding="utf-8")
        with pytest.raises(fs.FilesystemGuardrailError, match="blocked by security policy"):
            fs.read_file(".env")

    def test_size_limit_enforced(self, temp_project):
        big = temp_project / "big.txt"
        big.write_text("x" * (fs._READ_MAX_BYTES + 1), encoding="utf-8")
        with pytest.raises(fs.FilesystemGuardrailError, match="exceeds read limit"):
            fs.read_file("big.txt")

    def test_empty_path_rejected(self, temp_project):
        with pytest.raises(fs.FilesystemGuardrailError, match="cannot be empty"):
            fs.read_file("")


class TestWriteFile:
    def test_writes_to_allowed_dir(self, temp_project):
        result = fs.write_file("src/staged_agents/new_tool.py", "# new tool")
        assert "Successfully wrote" in result
        assert (temp_project / "src" / "staged_agents" / "new_tool.py").read_text() == "# new tool"

    def test_creates_parent_dirs(self, temp_project):
        fs.write_file("src/deep/nested/file.py", "deep")
        assert (temp_project / "src" / "deep" / "nested" / "file.py").read_text() == "deep"

    def test_write_to_docs_allowed(self, temp_project):
        fs.write_file("docs/guide.md", "# Guide")
        assert (temp_project / "docs" / "guide.md").exists()

    def test_write_to_tests_allowed(self, temp_project):
        fs.write_file("tests/test_new.py", "def test(): pass")
        assert (temp_project / "tests" / "test_new.py").exists()

    def test_write_to_root_blocked(self, temp_project):
        with pytest.raises(fs.FilesystemGuardrailError, match="only permitted under"):
            fs.write_file("requirements.txt", "new-package")

    def test_write_to_config_blocked(self, temp_project):
        with pytest.raises(fs.FilesystemGuardrailError, match="only permitted under"):
            fs.write_file("requirements.txt", "new-package==1.0")

    def test_denylist_blocks_write(self, temp_project):
        with pytest.raises(fs.FilesystemGuardrailError, match="blocked by security policy"):
            fs.write_file("src/.env", "SECRET=1")

    def test_traversal_blocked(self, temp_project):
        with pytest.raises(fs.FilesystemGuardrailError, match="traversal"):
            fs.write_file("../outside.txt", "bad")

    def test_size_limit_enforced(self, temp_project):
        big = "x" * (fs._WRITE_MAX_BYTES + 1)
        with pytest.raises(fs.FilesystemGuardrailError, match="exceeds write limit"):
            fs.write_file("src/big.py", big)


class TestListDirectory:
    def test_lists_files_and_dirs(self, temp_project):
        (temp_project / "src").mkdir()
        (temp_project / "README.md").write_text("hi", encoding="utf-8")

        entries = fs.list_directory(".")
        names = {e["name"] for e in entries}
        assert "src" in names
        assert "README.md" in names

        readme = next(e for e in entries if e["name"] == "README.md")
        assert readme["type"] == "file"
        assert readme["size"] == 2

        src = next(e for e in entries if e["name"] == "src")
        assert src["type"] == "directory"
        assert "size" not in src

    def test_lists_subdirectory(self, temp_project):
        (temp_project / "src" / "agents").mkdir(parents=True)
        (temp_project / "src" / "main.py").write_text("x", encoding="utf-8")

        entries = fs.list_directory("src")
        names = {e["name"] for e in entries}
        assert "agents" in names
        assert "main.py" in names

    def test_directory_not_found(self, temp_project):
        with pytest.raises(fs.FilesystemGuardrailError, match="Directory not found"):
            fs.list_directory("nonexistent")

    def test_path_is_file(self, temp_project):
        (temp_project / "file.txt").write_text("x", encoding="utf-8")
        with pytest.raises(fs.FilesystemGuardrailError, match="not a directory"):
            fs.list_directory("file.txt")

    def test_traversal_blocked(self, temp_project):
        with pytest.raises(fs.FilesystemGuardrailError, match="traversal"):
            fs.list_directory("../etc")


class TestAbsolutePathInsideProject:
    def test_absolute_path_inside_allowed(self, temp_project):
        (temp_project / "src").mkdir(parents=True)
        (temp_project / "src" / "main.py").write_text("hello", encoding="utf-8")
        result = fs.read_file(str(temp_project / "src" / "main.py"))
        assert result == "hello"

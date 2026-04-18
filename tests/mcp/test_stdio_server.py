import json
from pathlib import Path

import pytest

from src.mcp.server import build_mcp_server
from src.tools import filesystem as fs


def _parse_tool_result(result: object) -> dict:
    if isinstance(result, tuple):
        content_blocks, structured_result = result
        assert len(content_blocks) == 1
        assert json.loads(content_blocks[0].text) == structured_result
        return structured_result

    assert isinstance(result, list)
    assert len(result) == 1
    return json.loads(result[0].text)


class TestStdioMcpServer:
    @pytest.mark.asyncio
    async def test_build_mcp_server_registers_expected_tools(self):
        server = build_mcp_server()

        tool_names = {tool.name for tool in await server.list_tools()}

        assert tool_names == {
            "swarm_status",
            "repo_read_file",
            "repo_list_directory",
        }

    @pytest.mark.asyncio
    async def test_swarm_status_returns_standard_result_envelope(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        Path("state.json").write_text(
            json.dumps(
                {
                    "task-1": {"status": "PLANNED"},
                    "task-2": {"status": "COMPLETED"},
                    "task-3": {"status": "STALLED"},
                }
            ),
            encoding="utf-8",
        )
        Path("prompt_queue.jsonl").write_text(
            json.dumps({"timestamp": "2026-04-18T00:00:00Z", "user_id": "cli", "prompt": "hi"})
            + "\n",
            encoding="utf-8",
        )
        Path("swarm.pid").write_text("1234", encoding="utf-8")

        server = build_mcp_server()

        result = _parse_tool_result(await server.call_tool("swarm_status", {}))

        assert result == {
            "status": "success",
            "payload": {
                "pid": 1234,
                "shutdown_requested": False,
                "queue_depth": 1,
                "total_tasks": 3,
                "planned_tasks": 1,
                "completed_tasks": 1,
                "stalled_tasks": 1,
                "health": "DEGRADED",
            },
            "error": None,
            "source_backend": "local",
            "retryable": False,
        }

    @pytest.mark.asyncio
    async def test_repo_tools_return_envelopes_and_preserve_guardrails(
        self,
        monkeypatch,
        tmp_path,
    ):
        original_root = fs._PROJECT_ROOT
        monkeypatch.setattr(fs, "_PROJECT_ROOT", tmp_path)
        try:
            (tmp_path / "src").mkdir()
            (tmp_path / "src" / "hello.py").write_text("print('hello')", encoding="utf-8")
            (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")

            server = build_mcp_server()

            read_result = _parse_tool_result(
                await server.call_tool("repo_read_file", {"path": "src/hello.py"})
            )
            list_result = _parse_tool_result(
                await server.call_tool("repo_list_directory", {"path": "src"})
            )
            blocked_result = _parse_tool_result(
                await server.call_tool("repo_read_file", {"path": ".env"})
            )
        finally:
            monkeypatch.setattr(fs, "_PROJECT_ROOT", original_root)

        assert read_result == {
            "status": "success",
            "payload": {
                "path": "src/hello.py",
                "content": "print('hello')",
            },
            "error": None,
            "source_backend": "local",
            "retryable": False,
        }
        assert list_result["status"] == "success"
        assert list_result["payload"]["path"] == "src"
        assert list_result["payload"]["entries"] == [
            {"name": "hello.py", "type": "file", "size": 14}
        ]
        assert list_result["error"] is None
        assert list_result["source_backend"] == "local"
        assert list_result["retryable"] is False
        assert blocked_result == {
            "status": "error",
            "payload": None,
            "error": "Access to '.env' is blocked by security policy.",
            "source_backend": "local",
            "retryable": False,
        }

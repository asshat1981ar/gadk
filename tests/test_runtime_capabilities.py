from pathlib import Path
from unittest.mock import patch

import pytest

from src.tools.dispatcher import batch_execute, execute_capability


class TestRuntimeCapabilities:
    @pytest.mark.asyncio
    async def test_execute_capability_returns_standard_status_envelope(self):
        with (
            patch("src.tools.dispatcher.get_swarm_pid", return_value=1234),
            patch("src.tools.dispatcher.is_shutdown_requested", return_value=False),
            patch("src.tools.dispatcher.peek_prompts", return_value=[{"prompt": "review queue"}]),
            patch("src.tools.dispatcher.StateManager") as mock_state_manager,
        ):
            state_manager = mock_state_manager.return_value
            state_manager.get_all_tasks.return_value = {
                "task-1": {"status": "PLANNED"},
                "task-2": {"status": "STALLED"},
                "task-3": {"status": "COMPLETED"},
            }

            result = await execute_capability("swarm.status")

        assert result == {
            "status": "success",
            "payload": {
                "pid": 1234,
                "shutdown_requested": False,
                "queue_depth": 1,
                "total_tasks": 3,
                "planned": 1,
                "completed": 1,
                "stalled": 1,
                "health": "DEGRADED",
            },
            "error": None,
            "source_backend": "local",
            "retryable": False,
        }

    @pytest.mark.asyncio
    async def test_batch_execute_supports_capability_requests(self):
        with patch("src.tools.dispatcher.read_file", return_value="runtime capability content"):
            results = await batch_execute(
                [
                    {
                        "tool_name": "execute_capability",
                        "args": {
                            "name": "repo.read_file",
                            "path": "src/main.py",
                        },
                    }
                ]
            )

        assert results == [
            {
                "status": "success",
                "output": {
                    "status": "success",
                    "payload": {"content": "runtime capability content"},
                    "error": None,
                    "source_backend": "local",
                    "retryable": False,
                },
            }
        ]

    def test_orchestrator_instruction_prefers_capabilities(self):
        orchestrator_source = Path("src/agents/orchestrator.py").read_text(encoding="utf-8")
        assert "execute_capability" in orchestrator_source

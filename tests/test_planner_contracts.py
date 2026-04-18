from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from tenacity import wait_none

import src.planner as planner


def _mock_response(content: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=None,
                )
            )
        ]
    )


def test_repair_and_validate_tool_json_recovers_nearly_valid_json():
    raw = '{"action":"tool_call","tool_name":"read_file","args":{"path":"src/main.py",}}'

    parsed = planner.repair_and_validate_tool_json(raw)

    assert isinstance(parsed, planner.PlannerToolCall)
    assert parsed.tool_name == "read_file"
    assert parsed.args["path"] == "src/main.py"


def test_repair_and_validate_tool_json_rejects_unknown_tool_name():
    raw = '{"action":"tool_call","tool_name":"unknown","args":{"path":"src/main.py"}}'

    parsed = planner.repair_and_validate_tool_json(raw)

    assert parsed is None


def test_parse_tool_calls_repairs_canonical_json_blocks():
    raw = '```json\n{"action":"tool_call","tool_name":"read_file","args":{"path":"src/main.py",}}\n```'

    calls = planner._parse_tool_calls(raw)

    assert calls == [{"tool_name": "read_file", "args": {"path": "src/main.py"}}]


@pytest.mark.asyncio
async def test_llm_turn_retries_empty_response(monkeypatch):
    monkeypatch.setattr(planner, "_PLANNER_RETRY_WAIT", wait_none())
    mocked_completion = AsyncMock(
        side_effect=[
            _mock_response(""),
            _mock_response("final response"),
        ]
    )
    monkeypatch.setattr(planner, "acompletion", mocked_completion)

    content = await planner._llm_turn(
        messages=[{"role": "user", "content": "hello"}],
        model="test-model",
        retries=1,
    )

    assert content == "final response"
    assert mocked_completion.await_count == 2


@pytest.mark.asyncio
async def test_run_planner_finalizes_after_terminal_tool_call(monkeypatch):
    mocked_turn = AsyncMock(
        side_effect=[
            '```json\n{"action": "read_file", "arguments": {"path": "README.md"}}\n```',
            "Final summary after reading the file.",
        ]
    )
    mocked_execute = AsyncMock(
        return_value={
            "status": "success",
            "tool_name": "read_file",
            "output": "README contents",
        }
    )

    monkeypatch.setattr(planner, "_llm_turn", mocked_turn)
    monkeypatch.setattr(planner, "_execute_tool_call", mocked_execute)

    result = await planner.run_planner(
        user_prompt="Inspect the README and summarize it.",
        system_prompt="You are a helpful assistant.",
        max_iterations=1,
    )

    assert result == "Final summary after reading the file."
    assert mocked_execute.await_count == 1
    assert mocked_turn.await_count == 2


@pytest.mark.asyncio
async def test_run_planner_with_zero_iterations_returns_empty_string():
    result = await planner.run_planner(
        user_prompt="Do nothing.",
        system_prompt="You are a helpful assistant.",
        max_iterations=0,
    )

    assert result == ""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from tenacity import wait_none

import src.planner as planner
from src.config import Config


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


# ---------------------------------------------------------------------------
# Parametrized matrix: all 4 parser paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_calls",
    [
        # 1. Parser #1 – canonical JSON, single call (repair_and_validate_tool_json)
        (
            '```json\n{"action":"tool_call","tool_name":"read_file","args":{"path":"src/main.py"}}\n```',
            [{"tool_name": "read_file", "args": {"path": "src/main.py"}}],
        ),
        # 2. Parser #2 – canonical JSON, multiple calls (_load_repaired_json + _extract)
        (
            "```json\n"
            '[{"action":"tool_call","tool_name":"read_file","args":{"path":"a"}},'
            '{"action":"tool_call","tool_name":"list_directory","args":{"path":"src"}}]\n```',
            [
                {"tool_name": "read_file", "args": {"path": "a"}},
                {"tool_name": "list_directory", "args": {"path": "src"}},
            ],
        ),
        # 3. Parser #2 – repaired JSON with trailing comma
        (
            '```json\n{"action":"tool_call","tool_name":"write_file",'
            '"args":{"path":"out.txt","content":"data",}}\n```',
            [{"tool_name": "write_file", "args": {"path": "out.txt", "content": "data"}}],
        ),
        # 4. Parser #2 – repaired JSON with unquoted keys (_load_repaired_json)
        (
            '```json\n{action: "write_file", path: "out.txt", content: "data"}\n```',
            [{"tool_name": "write_file", "args": {"path": "out.txt", "content": "data"}}],
        ),
        # 5. Fallback 1 – inline {"tool_name": ..., "args": {...}} dict pattern
        (
            'Call {"tool_name": "read_file", "args": {"path": "x.py"}} to read.',
            [{"tool_name": "read_file", "args": {"path": "x.py"}}],
        ),
        # 6. Fallback 2 / Parser #3 – simple function-call syntax  read_file("path")
        (
            'read_file("src/main.py")',
            [{"tool_name": "read_file", "args": {"path": "src/main.py"}}],
        ),
        # 7. Fallback 3 / Parser #4 – write_file block, well-formed for the walker
        #    Even without explicit "action"/"tool_name" keys, the fallback should
        #    recover the intended path + content payload without trailing JSON junk.
        (
            '```json\n{"write_file": 1, "path": "notes.txt", "content": "hello world"}\n```',
            [
                {
                    "tool_name": "write_file",
                    "args": {"path": "notes.txt", "content": "hello world"},
                }
            ],
        ),
        # 8. Fallback 3 / Parser #4 – write_file block embedded in surrounding prose
        #    Content should still be extracted cleanly from the JSON block.
        (
            "Here is the file:\n"
            '```json\n{"write_file": 1, "path": "code.py", "content": "x = 1"}\n```\n'
            "Done.",
            [{"tool_name": "write_file", "args": {"path": "code.py", "content": "x = 1"}}],
        ),
        # 9. Malformed-everything – returns [], no crash
        (
            "```json\n{this is NOT valid json at all!!! @#$}\n```",
            [],
        ),
        # 10. Plain text, no tool calls – returns []
        (
            "I have finished the task. No further tools are needed.",
            [],
        ),
    ],
    ids=[
        "canonical-single",
        "canonical-multi",
        "repaired-trailing-comma",
        "repaired-unquoted-key",
        "fallback1-inline-json-dict",
        "fallback2-function-syntax",
        "fallback3-writefile-wellformed",
        "fallback3-writefile-prose",
        "malformed-everything",
        "plain-text-no-tools",
    ],
)
def test_parse_tool_calls_parametrized(text, expected_calls):
    calls = planner._parse_tool_calls(text)
    assert calls == expected_calls


def test_parse_tool_calls_caps_pathological_content_size():
    """Oversized content must not produce a huge ``write_file`` tool call,
    and parsing must stay fast (~O(1) relative to content size).

    Exercises the two-layer size cap in ``_parse_tool_calls``:
      * The top-level guard skips fenced-block scans when total text exceeds
        ``PLANNER_MAX_CONTENT_BYTES`` (primary DoS defence).
      * The per-block walker cap in Fallback 3 rejects individual
        write_file blocks whose content slice exceeds the same limit.

    The ~10 MB payload below blew past 1s of parsing before the guards
    landed; with them it should complete in well under 100 ms.
    """
    import time as _time

    big_content = "X" * 10_000_001  # ~10 million bytes
    text = '```json\n{"write_file": 1, "path": "big.txt", "content": "' + big_content + '"}\n```'

    start = _time.monotonic()
    calls = planner._parse_tool_calls(text)
    elapsed_sec = _time.monotonic() - start

    # The oversized block must not produce a write_file call with the huge content.
    assert not any(
        c.get("tool_name") == "write_file"
        and len(c.get("args", {}).get("content", "")) > Config.PLANNER_MAX_CONTENT_BYTES
        for c in calls
    )
    # Timing guardrail — loose enough to avoid CI flake but tight enough to
    # catch regressions where the guards stop working (pre-fix: ~1s, post-fix: ~1ms).
    assert (
        elapsed_sec < 0.5
    ), f"parser took {elapsed_sec:.3f}s on a 10 MB payload; DoS guard may be broken"


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

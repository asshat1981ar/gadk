import json

import pytest

pytest.importorskip("google.adk")

import src.main as main_module
from src.agents.ideator import ideator_agent
from src.agents.orchestrator import orchestrator_agent
from src.main import _build_autonomous_prompt
from src.services.runtime_strategy import should_use_planner_for_autonomous_run


def test_autonomous_runtime_uses_planner_for_elephant_ollama():
    assert should_use_planner_for_autonomous_run("ollama/minimax-m2.7:cloud") is True


def test_orchestrator_instruction_mentions_remote_repo_tools():
    instruction = orchestrator_agent.instruction
    assert "read_repo_file" in instruction
    assert "list_repo_contents" in instruction


def test_instruction_surface_uses_remote_repo_tools_not_fake_capabilities():
    orchestrator_text = orchestrator_agent.instruction
    ideator_text = ideator_agent.instruction

    assert "read_repo_file and list_repo_contents directly" in orchestrator_text
    assert "not for browsing the remote GitHub repository" in orchestrator_text
    assert "only for local specs, plans, and history" in orchestrator_text

    assert "start with 'list_repo_contents'" in ideator_text
    assert "inspect files with 'read_repo_file'" in ideator_text
    assert "Use 'list_directory' and 'read_file' only for local workspace files." in ideator_text
    assert (
        "Do not use retrieve_planning_context or execute_capability to explore the remote repository"
        in ideator_text
    )


def test_autonomous_prompt_uses_registered_remote_repo_tools():
    prompt = _build_autonomous_prompt("project-chimera")
    assert "list_repo_contents" in prompt
    assert "read_repo_file" in prompt


@pytest.mark.asyncio
async def test_process_prompt_uses_planner_for_autonomous_runs(monkeypatch):
    calls = []

    async def fake_run_planner(*, user_prompt: str, system_prompt: str, max_iterations: int):
        calls.append((user_prompt, system_prompt, max_iterations))
        return "DONE"

    monkeypatch.setattr(main_module, "run_planner", fake_run_planner)

    result = await main_module._run_autonomous_prompt_with_tools("prompt text")

    assert result == "DONE"
    assert calls == [("prompt text", main_module.AUTONOMOUS_SYSTEM_PROMPT, 8)]


@pytest.mark.asyncio
async def test_run_swarm_loop_routes_initial_prompt_through_planner(monkeypatch):
    prompts = []

    async def fake_run_autonomous_prompt_with_tools(user_prompt: str) -> str:
        prompts.append(user_prompt)
        return "planner response"

    monkeypatch.setattr(
        main_module, "_run_autonomous_prompt_with_tools", fake_run_autonomous_prompt_with_tools
    )
    monkeypatch.setattr(
        main_module, "should_use_planner_for_autonomous_run", lambda model_name: True
    )
    monkeypatch.setattr(main_module, "is_shutdown_requested", lambda: True)
    monkeypatch.setattr(main_module, "dequeue_prompts", lambda: [])

    await main_module.run_swarm_loop(
        session_service=None,
        session=type("Session", (), {"id": "session-1"})(),
        runner=object(),
    )

    assert prompts == [main_module._build_autonomous_prompt("project-chimera")]


@pytest.mark.asyncio
async def test_process_prompt_falls_back_on_tool_call_json_decode_error(monkeypatch, capsys):
    class BrokenRunner:
        def run_async(self, **kwargs):
            async def _events():
                raise json.JSONDecodeError("bad tool call", "{", 1)
                yield

            return _events()

    fallback_calls = []

    async def fake_run_autonomous_prompt_with_tools(user_prompt: str) -> str:
        fallback_calls.append(user_prompt)
        return "recovered"

    monkeypatch.setattr(
        main_module,
        "_run_autonomous_prompt_with_tools",
        fake_run_autonomous_prompt_with_tools,
    )

    await main_module.process_prompt(BrokenRunner(), type("S", (), {"id": "s1"})(), "prompt text")

    captured = capsys.readouterr()
    assert fallback_calls == ["prompt text"]
    assert "Swarm: recovered" in captured.out


@pytest.mark.asyncio
async def test_process_prompt_falls_back_on_wrapped_tool_call_json_error(monkeypatch, capsys):
    class BrokenRunner:
        def run_async(self, **kwargs):
            async def _events():
                raise RuntimeError(
                    "Malformed tool-call JSON returned by ADK"
                ) from json.JSONDecodeError(
                    "bad tool call",
                    "{",
                    1,
                )
                yield

            return _events()

    fallback_calls = []

    async def fake_run_autonomous_prompt_with_tools(user_prompt: str) -> str:
        fallback_calls.append(user_prompt)
        return "wrapped recovery"

    monkeypatch.setattr(
        main_module,
        "_run_autonomous_prompt_with_tools",
        fake_run_autonomous_prompt_with_tools,
    )

    await main_module.process_prompt(BrokenRunner(), type("S", (), {"id": "s2"})(), "prompt text")

    captured = capsys.readouterr()
    assert fallback_calls == ["prompt text"]
    assert "Swarm: wrapped recovery" in captured.out


@pytest.mark.asyncio
async def test_process_prompt_does_not_fallback_on_unrelated_exception(monkeypatch):
    class BrokenRunner:
        def run_async(self, **kwargs):
            async def _events():
                raise RuntimeError("upstream timeout")
                yield

            return _events()

    fallback_calls = []

    async def fake_run_autonomous_prompt_with_tools(user_prompt: str) -> str:
        fallback_calls.append(user_prompt)
        return "should not run"

    monkeypatch.setattr(
        main_module,
        "_run_autonomous_prompt_with_tools",
        fake_run_autonomous_prompt_with_tools,
    )

    await main_module.process_prompt(BrokenRunner(), type("S", (), {"id": "s3"})(), "prompt text")

    assert fallback_calls == []


@pytest.mark.asyncio
async def test_process_prompt_reports_empty_planner_fallback(monkeypatch, capsys):
    class BrokenRunner:
        def run_async(self, **kwargs):
            async def _events():
                raise json.JSONDecodeError("bad tool call", "{", 1)
                yield

            return _events()

    async def fake_run_autonomous_prompt_with_tools(user_prompt: str) -> str:
        return ""

    monkeypatch.setattr(
        main_module,
        "_run_autonomous_prompt_with_tools",
        fake_run_autonomous_prompt_with_tools,
    )

    await main_module.process_prompt(BrokenRunner(), type("S", (), {"id": "s4"})(), "prompt text")

    captured = capsys.readouterr()
    assert "Error during planner fallback: no response produced" in captured.out


@pytest.mark.asyncio
async def test_process_prompt_reports_planner_fallback_failure(monkeypatch, capsys):
    class BrokenRunner:
        def run_async(self, **kwargs):
            async def _events():
                raise json.JSONDecodeError("bad tool call", "{", 1)
                yield

            return _events()

    async def fake_run_autonomous_prompt_with_tools(user_prompt: str) -> str:
        raise RuntimeError("planner crashed")

    monkeypatch.setattr(
        main_module,
        "_run_autonomous_prompt_with_tools",
        fake_run_autonomous_prompt_with_tools,
    )

    await main_module.process_prompt(BrokenRunner(), type("S", (), {"id": "s5"})(), "prompt text")

    captured = capsys.readouterr()
    assert "Error during planner fallback: planner crashed" in captured.out

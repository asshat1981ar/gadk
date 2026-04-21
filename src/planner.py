"""Lightweight planner that parses elephant-alpha text output into tool calls.

ADK's native function calling doesn't work reliably with elephant-alpha on OpenRouter.
This planner prompts the model to emit JSON tool-call blocks inside its text response,
then parses and executes them explicitly.
"""

import asyncio
import json
import re
from typing import Any, TypeVar

from json_repair import repair_json
from litellm import acompletion
from litellm.exceptions import RateLimitError
from pydantic import BaseModel, Field, ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import Config
from src.observability.logger import get_logger
from src.observability.metrics import registry
from src.services.structured_output import request_structured_output
from src.tools.dispatcher import _TOOL_REGISTRY

logger = get_logger("planner")
StructuredModelT = TypeVar("StructuredModelT", bound=BaseModel)


# Prompt suffix injected into every request to elephant-alpha agents.
TOOL_PROMPT_SUFFIX = """

---
TOOL INSTRUCTIONS:
You have access to the following tools. When you need to use a tool,
output a JSON code block with the tool call details. You may emit multiple
tool calls in a single response by including a JSON array.

CRITICAL: You MUST always respond with text. Never return an empty response.
If you have nothing to say, explain your reasoning.

Available tools:
- read_file(path): Read a text file within the project.
- write_file(path, content): Write text content to a file (allowed dirs: src/, tests/, docs/, staged_agents/).
- list_directory(path="."): List files and directories.
- read_repo_file(path): Read a file from the configured GitHub repository.
- list_repo_contents(path=""): List files/directories in the GitHub repo.
- search_web(query, max_results=3): Search the web.
- execute_python_code(code): Execute Python in a sandbox.

TOOL CALL FORMAT (use exactly this markdown block):
```json
{"action": "tool_call", "tool_name": "read_file", "args": {"path": "src/main.py"}}
```

Or for multiple calls:
```json
[
  {"action": "tool_call", "tool_name": "read_file", "args": {"path": "src/main.py"}},
  {"action": "tool_call", "tool_name": "list_directory", "args": {"path": "src"}}
]
```

After each tool execution, you will receive the results and can continue.
If you don't need any tools, just respond normally without JSON blocks.
"""


# Recognized tool names for permissive parsing
_KNOWN_TOOLS = {
    "read_file",
    "write_file",
    "list_directory",
    "read_repo_file",
    "list_repo_contents",
    "search_web",
    "execute_python_code",
}

_PLANNER_RETRY_WAIT = wait_exponential(multiplier=1, min=1, max=8)


class PlannerToolCall(BaseModel):
    """Validated planner tool-call payload for the canonical JSON block shape."""

    action: str = Field(pattern="^tool_call$")
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)

    def to_dispatch_call(self) -> dict[str, Any]:
        """Return the dispatcher-compatible envelope."""
        return {
            "tool_name": self.tool_name,
            "args": dict(self.args),
        }


class EmptyPlannerResponseError(RuntimeError):
    """Raised when the planner LLM returns no usable content."""


_PLANNER_RETRYABLE_EXCEPTIONS = (
    EmptyPlannerResponseError,
    TimeoutError,
    ConnectionError,
    OSError,
    RateLimitError,
)


def repair_and_validate_tool_json(raw: str) -> PlannerToolCall | None:
    """Repair and validate the canonical planner tool-call JSON block."""
    try:
        repaired = repair_json(raw)
        candidate = PlannerToolCall.model_validate_json(repaired)
    except (ValidationError, TypeError, ValueError):
        return None

    if candidate.tool_name not in _KNOWN_TOOLS:
        return None
    return candidate


def _load_repaired_json(raw: str) -> Any | None:
    """Repair malformed JSON text enough to re-enter the permissive parser."""
    try:
        return json.loads(repair_json(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _extract_tool_calls_from_obj(data: Any) -> list[dict[str, Any]]:
    """Extract tool calls from a parsed JSON object. Very permissive."""
    calls = []
    if isinstance(data, list):
        for item in data:
            calls.extend(_extract_tool_calls_from_obj(item))
    elif isinstance(data, dict):
        # Format 1: {"action": "tool_call", "tool_name": "...", "args": {...}}
        # Also handles: {"action": "tool_call", "arguments": {"tool_name": "...", "args": {...}}}
        if data.get("action") == "tool_call":
            calls.append(_normalize_call(data))
            return calls
        # Format 2/3b: {"action": "write_file", "args": {...}} or {"action": "list_directory", "arguments": {...}}
        action = data.get("action", "")
        if action in _KNOWN_TOOLS:
            args = (
                data.get("args")
                or data.get("arguments")
                or {k: v for k, v in data.items() if k not in ["action", "args", "arguments"]}
            )
            calls.append({"tool_name": action, "args": args})
            return calls
        # Format 3: {"action": "read_file", "tools": [{...}]}
        if "tools" in data and isinstance(data["tools"], list):
            for tool in data["tools"]:
                if isinstance(tool, dict):
                    name = tool.get("name") or tool.get("tool_name")
                    args = tool.get("arguments") or tool.get("args", {})
                    if name in _KNOWN_TOOLS:
                        calls.append({"tool_name": name, "args": args})
            return calls
        # Format 4: {"tool_name": "...", "args": {...}} at root level
        if "tool_name" in data:
            calls.append(_normalize_call(data))
    return calls


def _parse_tool_calls(text: str) -> list[dict[str, Any]]:
    """Extract tool-call JSON blocks from LLM text output.
    Handles multiple formats the model might emit.
    """
    calls = []
    # Find all ```json ... ``` and ```python ... ``` blocks
    for match in re.finditer(r"```(?:json|python)\s*(.*?)\s*```", text, re.DOTALL):
        raw = match.group(1).strip()
        validated_call = repair_and_validate_tool_json(raw)
        if validated_call is not None:
            calls.append(validated_call.to_dispatch_call())
            continue

        data = _load_repaired_json(raw)
        if data is not None:
            calls.extend(_extract_tool_calls_from_obj(data))
        else:
            logger.warning(f"Failed to parse JSON block: {raw[:100]}")

    # Fallback 1: look for inline {"tool_name": "...", "args": {...}} patterns
    if not calls:
        for match in re.finditer(
            r'\{\s*"tool_name"\s*:\s*"([^"]+)"\s*,\s*"args"\s*:\s*(\{[^}]*\})\s*\}', text
        ):
            try:
                args = json.loads(match.group(2))
                calls.append({"tool_name": match.group(1), "args": args})
            except json.JSONDecodeError:
                pass

    # Fallback 2: look for simple tool calls like read_file("path")
    if not calls:
        simple_pattern = r'(read_file|list_directory|read_repo_file|list_repo_contents|search_web|execute_python_code)\s*\(\s*"([^"]+)"\s*\)'
        for match in re.finditer(simple_pattern, text):
            tool_name = match.group(1)
            arg = match.group(2)
            calls.append({"tool_name": tool_name, "args": {"path": arg}})

    # Fallback 3: robust write_file extraction from malformed JSON blocks
    # The model often emits JSON with unescaped quotes in content — we extract
    # path and content by scanning the raw block character-by-character.
    if not calls:
        for match in re.finditer(r"```(?:json|python)\s*(.*?)\s*```", text, re.DOTALL):
            raw = match.group(1).strip()
            if '"write_file"' not in raw and '"action"' not in raw:
                continue
            # Extract path
            pm = re.search(r'"path"\s*:\s*"([^"]+)"', raw)
            if not pm:
                continue
            path = pm.group(1)
            # Extract content: find "content" key, then grab everything until the last }}}
            cm = re.search(r'"content"\s*:\s*"', raw)
            if not cm:
                continue
            start = cm.end()
            # Walk backward from the end to find the closing brace of args
            end = len(raw)
            brace_depth = 0
            in_string = False
            for i in range(end - 1, start - 1, -1):
                ch = raw[i]
                if ch == '"' and (i == 0 or raw[i - 1] != "\\"):
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "}":
                    brace_depth += 1
                elif ch == "{":
                    brace_depth -= 1
                if brace_depth == 0 and ch == "}":
                    end = i
                    break
            content = raw[start:end]
            calls.append({"tool_name": "write_file", "args": {"path": path, "content": content}})

    return calls


def _normalize_call(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize different call formats into {tool_name, args}."""
    # Handle nested arguments: {"action": "tool_call", "arguments": {"tool_name": "x", "args": {}}}
    if "arguments" in item and isinstance(item["arguments"], dict):
        inner = item["arguments"]
        tool_name = inner.get("tool_name") or item.get("tool_name")
        args = inner.get("args") or {
            k: v for k, v in inner.items() if k not in ["tool_name", "args"]
        }

        # Heuristic: if tool_name is missing but we have path/content, it's write_file
        if not tool_name:
            if "path" in args and "content" in args:
                tool_name = "write_file"
            elif "path" in args:
                tool_name = "read_file"

        return {
            "tool_name": tool_name or "",
            "args": args,
        }
    # Handle flat format: {"action": "tool_call", "tool_name": "x", "args": {}}
    return {
        "tool_name": item.get("tool_name", ""),
        "args": item.get("args", {}),
    }


async def _execute_tool_call(call: dict[str, Any]) -> dict[str, Any]:
    """Execute a single parsed tool call."""
    name = call.get("tool_name")
    args = call.get("args", {})
    if name not in _TOOL_REGISTRY:
        return {"status": "error", "message": f"Tool '{name}' not found."}
    func = _TOOL_REGISTRY[name]
    try:
        if asyncio.iscoroutinefunction(func):
            result = await func(**args)
        else:
            result = func(**args)
        registry.record_tool_call(name, 0.0)
        return {"status": "success", "tool_name": name, "output": result}
    except Exception as e:
        registry.record_tool_call(name, 0.0, error=e)
        return {"status": "error", "tool_name": name, "message": str(e)}


def _extract_response_content(response: Any) -> str:
    """Normalize LiteLLM responses into planner text content."""
    content = response.choices[0].message.content
    if content is None:
        content = getattr(response.choices[0].message, "tool_calls", None)
        if content:
            content = str(content)
        else:
            content = ""
    return content


async def _llm_turn(messages: list[dict[str, str]], model: str = None, retries: int = 1) -> str:
    """Single LLM completion call via LiteLLM, with retry for empty responses."""
    model = model or Config.OPENROUTER_MODEL
    attempts = max(1, retries + 1)
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=_PLANNER_RETRY_WAIT,
            retry=retry_if_exception_type(_PLANNER_RETRYABLE_EXCEPTIONS),
            reraise=True,
        ):
            with attempt:
                response = await acompletion(
                    model=model,
                    api_key=Config.OPENROUTER_API_KEY,
                    api_base=Config.OPENROUTER_API_BASE,
                    messages=messages,
                    timeout=Config.LLM_TIMEOUT,
                )
                content = _extract_response_content(response)
                if content.strip():
                    return content

                logger.warning(
                    f"LLM returned empty response (attempt {attempt.retry_state.attempt_number}/{attempts})"
                )
                raise EmptyPlannerResponseError("LLM returned empty response")
    except EmptyPlannerResponseError:
        return ""

    return ""


async def _llm_turn_structured(
    messages: list[dict[str, str]],
    response_model: type[StructuredModelT],
    model: str = None,
    retries: int = 1,
) -> StructuredModelT:
    """Single structured LLM completion call via the Instructor bridge."""
    model = model or Config.OPENROUTER_MODEL
    attempts = max(1, retries + 1)
    return await request_structured_output(
        messages=messages,
        response_model=response_model,
        model=model,
        api_key=Config.OPENROUTER_API_KEY,
        api_base=Config.OPENROUTER_API_BASE,
        timeout=Config.LLM_TIMEOUT,
        max_retries=attempts,
        completion=acompletion,
    )


def _build_tool_suffix(allowed: set | None = None) -> str:
    """Build tool prompt suffix, optionally filtering to allowed tools only."""
    if allowed is None:
        return TOOL_PROMPT_SUFFIX
    lines = []
    for line in TOOL_PROMPT_SUFFIX.splitlines():
        # Keep header lines and format examples
        if line.strip().startswith("- "):
            tool_name = line[2:].split("(")[0].strip()
            if tool_name in allowed:
                lines.append(line)
        else:
            lines.append(line)
    return "\n".join(lines)


async def run_planner(
    user_prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    max_iterations: int = 10,
    model: str = None,
    allowed_tools: set | None = None,
) -> str:
    """
    Run the lightweight planner loop:
      1. Send prompt to LLM
      2. Parse tool calls from response
      3. Execute tools
      4. Feed results back
      5. Repeat until no more tool calls or max_iterations reached

    Args:
        user_prompt: The user's request.
        system_prompt: System instructions for the LLM.
        max_iterations: Safety limit on tool-call loops.
        model: LiteLLM model string. Defaults to Config.OPENROUTER_MODEL.
        allowed_tools: Optional set of tool names to restrict to.

    Returns:
        Final text response from the LLM after all tools are resolved.
    """
    if max_iterations <= 0:
        return ""

    suffix = _build_tool_suffix(allowed_tools)
    messages = [
        {"role": "system", "content": system_prompt + suffix},
        {"role": "user", "content": user_prompt},
    ]
    text = ""
    last_result_text = ""

    for iteration in range(max_iterations):
        logger.info(f"Planner iteration {iteration + 1}/{max_iterations}")
        text = await _llm_turn(messages, model=model, retries=Config.LLM_RETRIES)
        logger.info(f"LLM response length: {len(text)} chars")
        logger.info(f"LLM raw response: {text[:500]}...")

        calls = _parse_tool_calls(text)
        # If allowed_tools is set, filter out unauthorized calls
        if allowed_tools is not None:
            calls = [c for c in calls if c.get("tool_name") in allowed_tools]

        if not calls:
            logger.info("No tool calls detected. Returning final response.")
            return text

        logger.info(f"Detected {len(calls)} tool call(s): {[c['tool_name'] for c in calls]}")

        # Append the assistant's reasoning (including tool blocks) to history
        messages.append({"role": "assistant", "content": text})

        # Execute all tool calls concurrently
        results = await asyncio.gather(*(_execute_tool_call(c) for c in calls))

        # Build result message
        result_text = "\n".join(
            f"Tool '{r.get('tool_name')}': {r.get('status')} → {r.get('output', r.get('message', ''))}"
            for r in results
        )
        last_result_text = result_text
        messages.append({"role": "user", "content": f"Tool results:\n{result_text}"})

    logger.warning("Max iterations reached. Requesting final response without more tool calls.")
    final_messages = messages + [
        {
            "role": "user",
            "content": (
                "You have received the latest tool results. "
                "Respond with a final plain-text answer now. "
                "Do not call any more tools or return JSON."
            ),
        }
    ]
    final_text = await _llm_turn(final_messages, model=model, retries=Config.LLM_RETRIES)
    if final_text and not _parse_tool_calls(final_text):
        return final_text

    logger.warning(
        "Planner finalization still returned tool calls. Returning latest tool results instead."
    )
    return last_result_text or text


async def run_planner_structured(
    user_prompt: str,
    response_model: type[StructuredModelT],
    system_prompt: str = "You are a helpful assistant.",
    model: str = None,
) -> StructuredModelT:
    """Run a single non-tool planner turn through the structured-output bridge."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return await _llm_turn_structured(
        messages=messages,
        response_model=response_model,
        model=model,
        retries=Config.LLM_RETRIES,
    )

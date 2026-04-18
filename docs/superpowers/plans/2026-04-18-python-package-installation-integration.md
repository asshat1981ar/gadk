# Python Package Installation and Integration Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install and integrate 10 targeted Python packages into the Cognitive Foundry runtime in phased layers, prioritizing planner/runtime correctness and typed configuration first, then observability, caching/testing depth, and finally persistence/performance.

**Architecture:** The rollout is capability-layered instead of package-by-package. Phase 1 strengthens typed settings and planner/runtime behavior, Phase 2 adds explicit schema validation, caching, and property-based tests, and Phase 3 introduces new async persistence and selective JSON-performance upgrades without destabilizing the existing ADK/LiteLLM flows.

**Tech Stack:** Python 3, `pytest`, `pytest-asyncio`, `google-adk`, `litellm`, `pydantic`, `pydantic-settings`, `tenacity`, `json-repair`, `opentelemetry-sdk`, `jsonschema`, `diskcache`, `hypothesis`, `aiosqlite`, `orjson`

---

## Planning handoff

- **Approved spec path:** `docs/superpowers/specs/2026-04-18-python-package-installation-integration-design.md`
- **In scope:** `requirements.txt`, `src/config.py`, `src/planner.py`, `src/main.py`, `src/planned_main.py`, `src/autonomous_sdlc.py`, `src/tools/`, `src/observability/`, `src/services/`, and `tests/`
- **Out of scope:** replacing ADK or LiteLLM, unrelated broad refactors, packages outside the approved 10-package set
- **Explicit constraints:** prioritize top 3-5 packages first; every package lands with a narrow seam integration and tests; defer `jsonschema`, `aiosqlite`, and `orjson` until the higher-leverage runtime work is in place
- **Known files/directories:** `requirements.txt`, `src/config.py`, `src/planner.py`, `src/main.py`, `src/planned_main.py`, `src/autonomous_sdlc.py`, `src/tools/`, `src/observability/`, `src/services/`, `tests/`

## File structure

- Modify: `requirements.txt`
- Modify: `src/config.py:1-39`
- Modify: `src/planner.py:1-325`
- Modify: `src/main.py:1-168`
- Modify: `src/observability/adk_callbacks.py:1-60`
- Modify: `src/observability/logger.py:1-85`
- Create: `src/observability/telemetry.py`
- Create: `src/services/cache_store.py`
- Create: `src/services/optimization_history.py`
- Create: `tests/test_config_settings.py`
- Create: `tests/test_planner_contracts.py`
- Create: `tests/observability/test_telemetry.py`
- Create: `tests/test_planner_cache.py`
- Create: `tests/test_planner_property.py`
- Create: `tests/services/test_optimization_history.py`

## Fleet execution handoff

> **Fleet mode preamble:** Execute this plan as five dependency-aware work packages. Current repo state is still pre-integration: `requirements.txt` does not include the planned package set beyond current runtime dependencies, `src/config.py` still uses raw environment parsing, `src/planner.py` still uses the current handwritten parsing and retry behavior, and the telemetry/cache/history modules listed below do not exist yet. Keep every task additive, narrow, and reversible. Do not fold later-phase work into earlier tasks. `requirements.txt` is a shared merge hotspot, so even parallel work must land in dependency order.

### Preflight baseline

Run these checks before dispatching workers so the fleet starts from the same baseline:

1. `python3 -m pytest tests/test_dispatcher.py::test_batch_execute_success -q`
2. `python3 -m src.cli.swarm_cli status`
3. `python3 -m pytest tests/cli/test_swarm_cli.py::TestSwarmCli::test_status_no_swarm -q`
4. `python3 -m pytest tests/test_persistent_sessions.py -q`

Use the results as a baseline only; do not broaden the starting sweep beyond these focused checks.

### Execution graph

```text
Task 1 (typed settings foundation)
  ↓
Task 2 (planner hardening)
  ├─→ Task 3 (observability uplift)*
  └─→ Task 4 (schema/cache/property tests)
              ↓
Task 5 (async history + selective JSON perf)
              ↓
Final integration gate

* Parallel-safe only if Task 3 stays within `src/main.py`, `src/observability/`, and telemetry tests.
  If Task 3 needs `src/planner.py` changes for planner-iteration or retry spans, serialize instead:
  Task 1 → Task 2 → Task 4 → Task 3 → Task 5
```

### Phase ordering and landing rules

1. **Serialize:** Task 1 lands first. It establishes the typed config surface downstream tasks should consume.
2. **Serialize:** Task 2 lands second. Task 4 extends planner contracts introduced here.
3. **Parallel-safe with caveat:** Task 3 and Task 4 may run in parallel only if Task 3 avoids `src/planner.py`.
4. **Serialize:** Task 5 lands last. It is intentionally deferred until planner/runtime and Phase 2 work are in place.
5. **Always serialize merges to `requirements.txt`:** workers may develop in parallel, but the final landing order must follow this graph.

### Fleet task prompts

#### Fleet Task 1 — Typed settings foundation
- **Depends on:** none
- **Parallel with:** none
- **Fleet prompt:** Implement only Task 1 from this plan. Add `pydantic` and `pydantic-settings`, refactor `src/config.py` to expose a typed `Settings`/`get_settings` path while preserving compatibility for existing `Config` consumers, and add focused config-loading tests. Do not change planner, observability, caching, or persistence code in this task.
- **Landing note:** This task defines the config contract other tasks should reuse.

#### Fleet Task 2 — Planner hardening
- **Depends on:** Task 1 landed
- **Parallel with:** none
- **Fleet prompt:** Implement only Task 2 from this plan. Add `tenacity` and `json-repair`, harden `src/planner.py` with repair → validation → retry behavior, preserve current tool dispatch behavior, and add the focused planner contract/regression tests listed in the task. Do not add caching, telemetry, or persistence work here.
- **Landing note:** This is the critical-path seam; later planner-adjacent work assumes these interfaces exist.

#### Fleet Task 3 — Observability uplift
- **Depends on:** Task 2 landed
- **Parallel with:** Task 4 only if this task does **not** modify `src/planner.py`
- **Fleet prompt:** Implement only Task 3 from this plan. Add `opentelemetry-sdk`, create the additive telemetry module, wire spans through `src/main.py` and `src/observability/`, and keep existing JSON logging/metrics intact. Run only the listed observability regressions. If planner span wiring would require touching `src/planner.py`, stop at the observability surface and queue the planner-specific span hookup after Task 4 lands.
- **Landing note:** Prefer isolation over “full” instrumentation if full coverage would create cross-task merge conflicts.

#### Fleet Task 4 — Schema validation, caching, and property tests
- **Depends on:** Task 2 landed
- **Parallel with:** Task 3 under the isolation rule above
- **Fleet prompt:** Implement only Task 4 from this plan. Add `jsonschema`, `diskcache`, and `hypothesis`, extend the planner validation path introduced in Task 2, add the persistent planner cache, and add the property/cache tests listed here. Do not introduce `aiosqlite` or `orjson` in this task.
- **Landing note:** This task owns the next planner mutation after Task 2.

#### Fleet Task 5 — Async history and selective JSON performance
- **Depends on:** Task 4 landed
- **Parallel with:** none recommended
- **Fleet prompt:** Implement only Task 5 from this plan. Add `aiosqlite` and `orjson`, create the new async optimization history store, and apply JSON-performance changes only to the targeted metrics/history path named in the plan. Do not broaden this into a general persistence migration.
- **Landing note:** Keep this phase narrow and benchmark-driven; no unrelated storage refactors.

### Fleet execution checks

- Before starting a task, verify all listed dependencies are landed on the working branch.
- Before merging a parallel task, rebase and resolve `requirements.txt` explicitly.
- If a task needs files owned by a downstream task, stop and re-sequence instead of widening scope.
- Each task must finish with the focused tests already listed in its task body; do not substitute a broader unplanned test sweep for dependency gates.

### Task 1: Install typed settings packages and refactor configuration

**Files:**
- Modify: `requirements.txt`
- Modify: `src/config.py:1-39`
- Test: `tests/test_config_settings.py`

> **Fleet note:** Preserve compatibility for current `Config` consumers. If the typed settings refactor would require breaking edits in `src/main.py`, `src/agents/orchestrator.py`, or `src/autonomous_sdlc.py`, stop and keep the `Config` compatibility path intact instead of widening Task 1.

- [ ] **Step 1: Write the failing test**

```python
from src.config import Settings


def test_settings_reads_defaults_without_env(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)

    settings = Settings()

    assert settings.openrouter_model == "openrouter/elephant-alpha"
    assert settings.llm_timeout == 30


def test_settings_parses_boolean_flags(monkeypatch):
    monkeypatch.setenv("AUTONOMOUS_MODE", "true")
    monkeypatch.setenv("TEST_MODE", "false")

    settings = Settings()

    assert settings.autonomous_mode is True
    assert settings.test_mode is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config_settings.py -v`
Expected: FAIL with `ImportError: cannot import name 'Settings' from 'src.config'`

- [ ] **Step 3: Write minimal implementation**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    github_token: str | None = None
    repo_name: str | None = None
    state_table_type: str = "json"
    autonomous_mode: bool = False
    test_mode: bool = False
    token_quota_per_task: int = 50000
    openrouter_api_key: str | None = None
    openrouter_api_base: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/elephant-alpha"
    openrouter_tool_model: str = "openrouter/elephant-alpha"
    llm_timeout: int = 30
    llm_retries: int = 3


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


class Config:
    _settings = get_settings()
    GITHUB_TOKEN = _settings.github_token
    REPO_NAME = _settings.repo_name
    STATE_TABLE_TYPE = _settings.state_table_type
    AUTONOMOUS_MODE = _settings.autonomous_mode
    TEST_MODE = _settings.test_mode
    TOKEN_QUOTA_PER_TASK = _settings.token_quota_per_task
    OPENROUTER_API_KEY = _settings.openrouter_api_key
    OPENROUTER_API_BASE = _settings.openrouter_api_base
    OPENROUTER_MODEL = _settings.openrouter_model
    OPENROUTER_TOOL_MODEL = _settings.openrouter_tool_model
    FALLBACK_MODELS = [
        _settings.openrouter_tool_model,
        "google/gemini-2.5-flash",
        "google/gemini-2.0-flash-001",
        "anthropic/claude-sonnet-4",
        "openrouter/elephant-alpha",
    ]
    LLM_TIMEOUT = _settings.llm_timeout
    LLM_RETRIES = _settings.llm_retries
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_config_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/config.py tests/test_config_settings.py
git commit -m "feat: add typed settings configuration"
```

### Task 2: Harden planner parsing with Pydantic models, retries, and JSON repair

**Files:**
- Modify: `requirements.txt`
- Modify: `src/planner.py:1-325`
- Modify: `src/tools/github_tool.py`
- Modify: `src/tools/smithery_bridge.py`
- Modify: `src/tools/web_search.py`
- Test: `tests/test_planner_contracts.py`
- Test: `tests/test_smithery_bridge.py`
- Test: `tests/test_web_search.py`

- [ ] **Step 1: Write the failing test**

```python
from src.planner import PlannerToolCall, repair_and_validate_tool_json


def test_repair_and_validate_tool_json_recovers_nearly_valid_json():
    raw = '{"action":"tool_call","tool_name":"read_file","args":{"path":"src/main.py",}}'

    parsed = repair_and_validate_tool_json(raw)

    assert parsed.tool_name == "read_file"
    assert parsed.args["path"] == "src/main.py"


def test_repair_and_validate_tool_json_rejects_unknown_tool_name():
    raw = '{"action":"tool_call","tool_name":"unknown","args":{"path":"src/main.py"}}'

    parsed = repair_and_validate_tool_json(raw)

    assert parsed is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_planner_contracts.py -v`
Expected: FAIL with `ImportError` for `PlannerToolCall` or `repair_and_validate_tool_json`

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, Field, ValidationError
from json_repair import repair_json
from tenacity import retry, stop_after_attempt, wait_exponential


class PlannerToolCall(BaseModel):
    action: str = Field(pattern="^tool_call$")
    tool_name: str
    args: dict[str, object] = Field(default_factory=dict)


def repair_and_validate_tool_json(raw: str) -> PlannerToolCall | None:
    try:
        repaired = repair_json(raw)
        candidate = PlannerToolCall.model_validate_json(repaired)
    except (ValidationError, ValueError):
        return None

    if candidate.tool_name not in _KNOWN_TOOLS:
        return None
    return candidate


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
async def _llm_turn(messages: list[dict[str, str]], model: str = None, retries: int = 1) -> str:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_planner_contracts.py -v`
Expected: PASS

- [ ] **Step 5: Run the focused planner regression subset**

Run: `python3 -m pytest tests/test_dispatcher.py tests/test_fallbacks.py tests/test_planner_contracts.py -v`
Expected: PASS

- [ ] **Step 6: Add narrow retry wrappers to retry-sensitive tool seams**

```python
# src/tools/smithery_bridge.py / src/tools/web_search.py / src/tools/github_tool.py
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
async def call_smithery_tool(server_id: str, tool_name: str, args: dict) -> str:
    ...


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def search_web(query: str, max_results: int = 5) -> str:
    ...
```

- [ ] **Step 7: Run the focused retry-sensitive tool subset**

Run: `python3 -m pytest tests/test_smithery_bridge.py tests/test_web_search.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add requirements.txt src/planner.py src/tools/github_tool.py src/tools/smithery_bridge.py src/tools/web_search.py tests/test_planner_contracts.py tests/test_smithery_bridge.py tests/test_web_search.py
git commit -m "feat: harden planner parsing and retries"
```

### Task 3: Add OpenTelemetry as an additive observability layer

**Files:**
- Modify: `requirements.txt`
- Create: `src/observability/telemetry.py`
- Modify: `src/observability/adk_callbacks.py:1-60`
- Modify: `src/main.py:118-168`
- Test: `tests/observability/test_telemetry.py`

> **Fleet note:** Keep this task out of `src/planner.py` if Task 4 is running in parallel. If planner span instrumentation is deferred for parallel safety, Task 4 must add only the narrow planner-iteration or retry span hooks needed to complete the approved telemetry coverage while it is already modifying `src/planner.py`.

- [ ] **Step 1: Write the failing test**

```python
from src.observability.telemetry import get_tracer, start_span


def test_start_span_returns_context_manager():
    tracer = get_tracer("test-suite")

    with start_span(tracer, "planner-iteration") as span:
        assert span is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/observability/test_telemetry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.observability.telemetry'`

- [ ] **Step 3: Write minimal implementation**

```python
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter


_provider = TracerProvider(resource=Resource.create({"service.name": "cognitive-foundry"}))
_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(_provider)


def get_tracer(name: str):
    return trace.get_tracer(name)


@contextmanager
def start_span(tracer, name: str):
    with tracer.start_as_current_span(name) as span:
        yield span
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/observability/test_telemetry.py -v`
Expected: PASS

- [ ] **Step 5: Run the focused observability regression subset**

Run: `python3 -m pytest tests/observability/test_metrics.py tests/observability/test_adk_callbacks.py tests/test_e2e_observability.py tests/observability/test_telemetry.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add requirements.txt src/observability/telemetry.py src/observability/adk_callbacks.py src/main.py tests/observability/test_telemetry.py
git commit -m "feat: add tracing to observability layer"
```

### Task 4: Add Phase 2 schema validation, caching, and property-based tests

**Files:**
- Modify: `requirements.txt`
- Create: `src/services/cache_store.py`
- Modify: `src/planner.py:103-325`
- Test: `tests/test_planner_cache.py`
- Test: `tests/test_planner_property.py`

> **Fleet note:** This task owns the next `src/planner.py` mutation after Task 2. If Task 3 deferred planner span hooks for parallel safety, land those narrow planner telemetry hooks here while touching the same planner flow, without broadening the task beyond validation, caching, and property-test work.

- [ ] **Step 1: Write the failing test**

```python
from src.services.cache_store import PlannerCache


def test_planner_cache_round_trips_values(tmp_path):
    cache = PlannerCache(tmp_path / "planner-cache")
    cache.set("prompt-a", {"result": "cached"})

    assert cache.get("prompt-a") == {"result": "cached"}
```

```python
from hypothesis import given, strategies as st

from src.planner import repair_and_validate_tool_json


@given(st.sampled_from(["read_file", "write_file", "list_directory"]))
def test_repair_and_validate_tool_json_accepts_known_tools(tool_name):
    raw = f'{{"action":"tool_call","tool_name":"{tool_name}","args":{{"path":"src/main.py"}}}}'
    parsed = repair_and_validate_tool_json(raw)
    assert parsed is not None
```

```python
from src.services.cache_store import PlannerCache
from src.planner import parse_tool_response


def test_parse_tool_response_uses_planner_cache(monkeypatch, tmp_path):
    cache = PlannerCache(tmp_path / "planner-cache")
    raw = '{"action":"tool_call","tool_name":"read_file","args":{"path":"src/main.py"}}'
    cache.set(raw, {"tool_name": "read_file", "args": {"path": "src/main.py"}})

    monkeypatch.setattr("src.planner._PLANNER_CACHE", cache)
    monkeypatch.setattr(
        "src.planner.repair_and_validate_tool_json",
        lambda _: (_ for _ in ()).throw(AssertionError("cache miss")),
    )

    parsed = parse_tool_response(raw)

    assert parsed["tool_name"] == "read_file"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_planner_cache.py tests/test_planner_property.py -v`
Expected: FAIL with missing cache module or missing Hypothesis dependency

- [ ] **Step 3: Write minimal implementation**

```python
# src/services/cache_store.py
from diskcache import Cache


class PlannerCache:
    def __init__(self, path):
        self._cache = Cache(str(path))

    def get(self, key: str):
        return self._cache.get(key)

    def set(self, key: str, value):
        self._cache.set(key, value)
```

```python
# planner validation extension
from jsonschema import validate
from src.services.cache_store import PlannerCache


_TOOL_CALL_SCHEMA = {
    "type": "object",
    "required": ["action", "tool_name", "args"],
    "properties": {
        "action": {"const": "tool_call"},
        "tool_name": {"type": "string"},
        "args": {"type": "object"},
    },
}

_PLANNER_CACHE = PlannerCache(".planner-cache")


def repair_and_validate_tool_json(raw: str) -> PlannerToolCall | None:
    ...
    payload = candidate.model_dump()
    validate(instance=payload, schema=_TOOL_CALL_SCHEMA)
    return candidate


def parse_tool_response(raw: str) -> dict[str, object] | None:
    cached = _PLANNER_CACHE.get(raw)
    if cached is not None:
        return cached

    candidate = repair_and_validate_tool_json(raw)
    if candidate is None:
        return None

    payload = candidate.model_dump()
    _PLANNER_CACHE.set(raw, payload)
    return payload
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_planner_cache.py tests/test_planner_property.py -v`
Expected: PASS

- [ ] **Step 5: Run the focused planner regression subset again**

Run: `python3 -m pytest tests/test_dispatcher.py tests/test_fallbacks.py tests/test_planner_contracts.py tests/test_planner_cache.py tests/test_planner_property.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add requirements.txt src/services/cache_store.py src/planner.py tests/test_planner_cache.py tests/test_planner_property.py
git commit -m "feat: add planner cache and schema tests"
```

### Task 5: Add async history storage and selective JSON performance upgrades

**Files:**
- Modify: `requirements.txt`
- Create: `src/services/optimization_history.py`
- Modify: `src/observability/metrics.py:29-118`
- Test: `tests/services/test_optimization_history.py`

> **Fleet note:** `orjson` is benchmark-gated in this phase. If no targeted metrics/history path shows a clear benefit during implementation, wire `aiosqlite` history storage now and defer `orjson` integration to a follow-up instead of broadening the task.

> **Fleet note:** The targeted JSON seam for this phase is `src/observability/metrics.py` event or snapshot serialization only. Use `orjson` there only if a small benchmark against the current serializer shows a measurable improvement on repeated metrics writes; otherwise leave metrics on the current serializer and document the defer.

- [ ] **Step 1: Write the failing test**

```python
import asyncio

from src.services.optimization_history import OptimizationHistoryStore


def test_optimization_history_store_round_trips_rows(tmp_path):
    async def scenario():
        store = OptimizationHistoryStore(tmp_path / "optimization-history.db")
        await store.initialize()
        await store.record_run("planner.tool_prompt_suffix", 0.50, 0.82, True)
        rows = await store.list_runs("planner.tool_prompt_suffix")
        assert rows[0]["promoted"] is True

    asyncio.run(scenario())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/services/test_optimization_history.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.optimization_history'`

- [ ] **Step 3: Write minimal implementation**

```python
import aiosqlite


class OptimizationHistoryStore:
    def __init__(self, db_path):
        self.db_path = db_path

    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS optimization_runs (
                    target_id TEXT,
                    baseline_score REAL,
                    candidate_score REAL,
                    promoted INTEGER
                )
                """
            )
            await db.commit()

    async def record_run(self, target_id: str, baseline_score: float, candidate_score: float, promoted: bool):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO optimization_runs VALUES (?, ?, ?, ?)",
                (target_id, baseline_score, candidate_score, int(promoted)),
            )
            await db.commit()

    async def list_runs(self, target_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT target_id, baseline_score, candidate_score, promoted FROM optimization_runs WHERE target_id = ?",
                (target_id,),
            )
            rows = await cursor.fetchall()
        return [
            {
                "target_id": row[0],
                "baseline_score": row[1],
                "candidate_score": row[2],
                "promoted": bool(row[3]),
            }
            for row in rows
        ]
```

```python
# src/observability/metrics.py
import json

import orjson


def _serialize_metrics_payload(payload: dict, use_orjson: bool = False) -> str:
    if use_orjson:
        return orjson.dumps(payload).decode("utf-8")
    return json.dumps(payload)
```

- [ ] **Step 4: Run the implementation-time benchmark decision**

Run: `python3 -m timeit -s "import json, orjson; payload={'agent':'planner','calls':100,'errors':0,'durations':[0.1,0.2,0.3]*50}" "json.dumps(payload)" "orjson.dumps(payload)"`
Expected: Record whether `orjson` is measurably faster for the targeted `src/observability/metrics.py` serialization path. If it is not clearly faster, keep `use_orjson=False` and document the defer in the commit message or task notes.

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/services/test_optimization_history.py -v`
Expected: PASS

- [ ] **Step 6: Run the focused persistence regression subset**

Run: `python3 -m pytest tests/test_persistent_sessions.py tests/services/test_optimization_history.py tests/observability/test_metrics.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add requirements.txt src/services/optimization_history.py tests/services/test_optimization_history.py src/observability/metrics.py
git commit -m "feat: add async optimization history storage"
```

## Self-review

1. **Spec coverage:** The plan covers all 10 packages and preserves the approved phasing: Phase 1 (`pydantic`, `pydantic-settings`, `tenacity`, `json-repair`, `opentelemetry-sdk`), Phase 2 (`jsonschema`, `diskcache`, `hypothesis`), and Phase 3 (`aiosqlite`, `orjson`). No spec requirement is missing.
2. **Placeholder scan:** No `TBD`, `TODO`, or “implement later” steps remain. Each task includes files, code, commands, and expected outcomes.
3. **Type consistency:** `Settings`, `PlannerToolCall`, `PromptOptimizer`-adjacent history naming, `PlannerCache`, and `OptimizationHistoryStore` are used consistently across tasks.
4. **Handoff fidelity:** The plan stays within the approved surfaces (`requirements.txt`, runtime/planner/observability/services/tests), preserves the top-3-5-first constraint, and avoids unrelated refactors or framework replacement.

## Final integration gate

After Task 5 lands, run this focused cross-phase regression gate before declaring the fleet execution complete:

1. `python3 -m pytest tests/test_config_settings.py tests/test_planner_contracts.py tests/observability/test_telemetry.py tests/test_planner_cache.py tests/test_planner_property.py tests/services/test_optimization_history.py -v`
2. `python3 -m pytest tests/test_dispatcher.py tests/test_persistent_sessions.py tests/cli/test_swarm_cli.py tests/observability/test_metrics.py -v`

Expected result: all package-roadmap tests pass together without requiring unrelated broad-suite fixes.

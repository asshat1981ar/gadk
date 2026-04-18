# Prompt Optimization System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a v1 prompt optimization system that discovers whitelisted prompt targets in `src/planner.py`, `src/planned_main.py`, and `src/autonomous_sdlc.py`, evaluates prompt variants against deterministic scenarios, and rewrites source only when a candidate beats the baseline and passes post-rewrite verification.

**Architecture:** The implementation adds a small service layer under `src/services/` for prompt target discovery, evaluation/history, and promotion/rollback. A dedicated entrypoint runs the optimizer outside normal swarm execution so prompt mutation stays measurable and reversible.

**Tech Stack:** Python 3, `pytest`, `dataclasses`, `pathlib`, `ast`, `re`, existing `src/services/`, existing planner/workflow modules

---

## Planning handoff

- **Approved spec path:** `docs/superpowers/specs/2026-04-17-prompt-optimization-system-design.md`
- **In scope:** `src/planner.py`, `src/planned_main.py`, `src/autonomous_sdlc.py`, new modules under `src/services/`, and new tests under `tests/`
- **Out of scope:** `src/agents/*.py` promotion support in v1, non-Python assets, runtime self-editing during live swarm tasks
- **Explicit constraints:** auto-rewrite prompt text in source only after evaluation passes; use deterministic harnesses first; keep prompt targets whitelist-based; rollback on failed post-rewrite verification
- **Known files/directories:** `src/planner.py`, `src/planned_main.py`, `src/autonomous_sdlc.py`, `src/services/`, `tests/`

## File structure

- Create: `src/services/prompt_targets.py` — prompt target definitions, whitelist, discovery, and source replacement helpers
- Create: `src/services/prompt_history.py` — prompt version history and promotion log persistence
- Create: `src/services/prompt_evaluator.py` — deterministic baseline/candidate evaluation and scoring
- Create: `src/services/prompt_optimizer.py` — end-to-end optimization orchestration, promotion gate, and rollback
- Create: `src/prompt_optimization.py` — runnable entrypoint for batch or single-target optimization
- Create: `tests/services/test_prompt_targets.py` — discovery and replacement tests
- Create: `tests/services/test_prompt_evaluator.py` — scoring and verification tests
- Create: `tests/services/test_prompt_optimizer.py` — promotion, rejection, and rollback tests
- Create: `tests/test_prompt_optimization_e2e.py` — end-to-end optimizer flow with mocked generation/evaluation

### Task 1: Add prompt target discovery and source replacement

**Files:**
- Create: `src/services/prompt_targets.py`
- Test: `tests/services/test_prompt_targets.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from src.services.prompt_targets import (
    PromptTarget,
    discover_v1_prompt_targets,
    replace_prompt_text,
)


def test_discover_v1_prompt_targets_returns_expected_ids():
    targets = discover_v1_prompt_targets(Path.cwd())
    ids = {target.target_id for target in targets}

    assert "planner.tool_prompt_suffix" in ids
    assert "planned_main.builder_system" in ids
    assert "planned_main.builder_prompt" in ids
    assert "autonomous_sdlc.discover_prompt" in ids
    assert "autonomous_sdlc.builder_prompt" in ids


def test_replace_prompt_text_updates_only_selected_span():
    source = "alpha = \"before\"\\nbeta = \"keep\"\\n"
    target = PromptTarget(
        target_id="demo.alpha",
        file_path=Path("demo.py"),
        symbol="alpha",
        category="workflow",
        placeholders=(),
        rewrite_allowed=True,
        evaluator_id="demo",
        start_token='alpha = "before"',
        end_token='alpha = "before"',
    )

    updated = replace_prompt_text(source, target, '"after"')

    assert 'alpha = "after"' in updated
    assert 'beta = "keep"' in updated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/services/test_prompt_targets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.prompt_targets'`

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class PromptTarget:
    target_id: str
    file_path: Path
    symbol: str
    category: str
    placeholders: tuple[str, ...]
    rewrite_allowed: bool
    evaluator_id: str
    start_token: str
    end_token: str


def discover_v1_prompt_targets(repo_root: Path) -> list[PromptTarget]:
    return [
        PromptTarget(
            target_id="planner.tool_prompt_suffix",
            file_path=repo_root / "src" / "planner.py",
            symbol="TOOL_PROMPT_SUFFIX",
            category="planner",
            placeholders=(),
            rewrite_allowed=True,
            evaluator_id="planner_json",
            start_token='TOOL_PROMPT_SUFFIX = """',
            end_token='"""',
        ),
        PromptTarget(
            target_id="planned_main.builder_system",
            file_path=repo_root / "src" / "planned_main.py",
            symbol="builder_system",
            category="code_generation",
            placeholders=(),
            rewrite_allowed=True,
            evaluator_id="builder_prompt",
            start_token='    builder_system = (',
            end_token='    )',
        ),
        PromptTarget(
            target_id="planned_main.builder_prompt",
            file_path=repo_root / "src" / "planned_main.py",
            symbol="builder_prompt",
            category="code_generation",
            placeholders=("task_spec", "context"),
            rewrite_allowed=True,
            evaluator_id="builder_prompt",
            start_token='    builder_prompt = (',
            end_token='    )',
        ),
        PromptTarget(
            target_id="autonomous_sdlc.discover_prompt",
            file_path=repo_root / "src" / "autonomous_sdlc.py",
            symbol="prompt",
            category="workflow",
            placeholders=("REPO",),
            rewrite_allowed=True,
            evaluator_id="task_format",
            start_token='        prompt = (',
            end_token='        )',
        ),
        PromptTarget(
            target_id="autonomous_sdlc.builder_prompt",
            file_path=repo_root / "src" / "autonomous_sdlc.py",
            symbol="builder_prompt",
            category="code_generation",
            placeholders=("task", "context"),
            rewrite_allowed=True,
            evaluator_id="builder_prompt",
            start_token='        builder_prompt = (',
            end_token='        )',
        ),
    ]


def replace_prompt_text(source: str, target: PromptTarget, replacement_literal: str) -> str:
    if target.start_token == target.end_token:
        return source.replace(target.start_token, f'{target.symbol} = {replacement_literal}', 1)

    start = source.index(target.start_token)
    end = source.index(target.end_token, start + len(target.start_token))
    new_block = f"{target.start_token}\\n{replacement_literal}\\n{target.end_token}"
    return source[:start] + new_block + source[end + len(target.end_token):]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/services/test_prompt_targets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/services/test_prompt_targets.py src/services/prompt_targets.py
git commit -m "feat: add prompt target discovery"
```

### Task 2: Add deterministic prompt evaluation and history tracking

**Files:**
- Create: `src/services/prompt_history.py`
- Create: `src/services/prompt_evaluator.py`
- Test: `tests/services/test_prompt_evaluator.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from src.services.prompt_evaluator import (
    EvaluationScenario,
    EvaluationResult,
    evaluate_candidate,
    verify_candidate_placeholders,
)
from src.services.prompt_history import PromptHistoryStore


def test_verify_candidate_placeholders_rejects_missing_variables():
    assert verify_candidate_placeholders(
        candidate="Task spec:\\n{task_spec}\\nContext:\\n{context}",
        required_placeholders=("task_spec", "context"),
    ) is True

    assert verify_candidate_placeholders(
        candidate="Task spec:\\n{task_spec}",
        required_placeholders=("task_spec", "context"),
    ) is False


def test_evaluate_candidate_scores_pass_and_fail():
    scenarios = [
        EvaluationScenario(
            scenario_id="builder-1",
            prompt_input={"task_spec": "Build x", "context": "Context y"},
            required_substrings=("write_file", "DONE"),
        )
    ]

    baseline = evaluate_candidate(
        candidate_text="Use write_file and say DONE",
        scenarios=scenarios,
    )
    failing = evaluate_candidate(
        candidate_text="Just think silently",
        scenarios=scenarios,
    )

    assert baseline.passed is True
    assert failing.passed is False
    assert baseline.score > failing.score


def test_prompt_history_store_records_versions(tmp_path: Path):
    store = PromptHistoryStore(tmp_path / "prompt_history.json")
    store.record_result(
        target_id="planned_main.builder_prompt",
        baseline_score=0.4,
        candidate_score=0.9,
        promoted=True,
    )

    payload = store.read_all()
    assert payload["planned_main.builder_prompt"][0]["promoted"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/services/test_prompt_evaluator.py -v`
Expected: FAIL with `ModuleNotFoundError` for the new services

- [ ] **Step 3: Write minimal implementation**

```python
# src/services/prompt_evaluator.py
from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationScenario:
    scenario_id: str
    prompt_input: dict[str, str]
    required_substrings: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    score: float
    failures: tuple[str, ...]


def verify_candidate_placeholders(candidate: str, required_placeholders: tuple[str, ...]) -> bool:
    return all(f"{{{name}}}" in candidate for name in required_placeholders)


def evaluate_candidate(candidate_text: str, scenarios: list[EvaluationScenario]) -> EvaluationResult:
    failures: list[str] = []
    total_checks = 0
    passed_checks = 0

    for scenario in scenarios:
        for needle in scenario.required_substrings:
            total_checks += 1
            if needle in candidate_text:
                passed_checks += 1
            else:
                failures.append(f"{scenario.scenario_id}: missing {needle}")

    score = passed_checks / total_checks if total_checks else 0.0
    return EvaluationResult(
        passed=not failures,
        score=score,
        failures=tuple(failures),
    )
```

```python
# src/services/prompt_history.py
import json
from pathlib import Path


class PromptHistoryStore:
    def __init__(self, history_path: Path):
        self.history_path = history_path

    def read_all(self) -> dict[str, list[dict]]:
        if not self.history_path.exists():
            return {}
        return json.loads(self.history_path.read_text(encoding="utf-8"))

    def record_result(
        self,
        target_id: str,
        baseline_score: float,
        candidate_score: float,
        promoted: bool,
    ) -> None:
        payload = self.read_all()
        payload.setdefault(target_id, []).append(
            {
                "baseline_score": baseline_score,
                "candidate_score": candidate_score,
                "promoted": promoted,
            }
        )
        self.history_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/services/test_prompt_evaluator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/services/test_prompt_evaluator.py src/services/prompt_evaluator.py src/services/prompt_history.py
git commit -m "feat: add prompt evaluation primitives"
```

### Task 3: Add optimizer orchestration, promotion gate, and rollback

**Files:**
- Create: `src/services/prompt_optimizer.py`
- Test: `tests/services/test_prompt_optimizer.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from src.services.prompt_optimizer import PromptOptimizer
from src.services.prompt_targets import PromptTarget


def test_optimizer_promotes_higher_scoring_candidate(tmp_path: Path):
    source_file = tmp_path / "planner.py"
    source_file.write_text('TOOL_PROMPT_SUFFIX = """before"""\\n', encoding="utf-8")

    target = PromptTarget(
        target_id="planner.tool_prompt_suffix",
        file_path=source_file,
        symbol="TOOL_PROMPT_SUFFIX",
        category="planner",
        placeholders=(),
        rewrite_allowed=True,
        evaluator_id="planner_json",
        start_token='TOOL_PROMPT_SUFFIX = """',
        end_token='"""',
    )

    optimizer = PromptOptimizer(
        history_path=tmp_path / "history.json",
        promotion_threshold=0.1,
    )

    promoted = optimizer.optimize_target(
        target=target,
        baseline_text="before",
        candidate_text='Use JSON blocks and always say what tool you are calling.',
    )

    assert promoted.promoted is True
    assert "Use JSON blocks" in source_file.read_text(encoding="utf-8")


def test_optimizer_rolls_back_when_post_verify_fails(tmp_path: Path):
    source_file = tmp_path / "planner.py"
    source_file.write_text('TOOL_PROMPT_SUFFIX = """before"""\\n', encoding="utf-8")

    target = PromptTarget(
        target_id="planner.tool_prompt_suffix",
        file_path=source_file,
        symbol="TOOL_PROMPT_SUFFIX",
        category="planner",
        placeholders=(),
        rewrite_allowed=True,
        evaluator_id="planner_json",
        start_token='TOOL_PROMPT_SUFFIX = """',
        end_token='"""',
    )

    optimizer = PromptOptimizer(
        history_path=tmp_path / "history.json",
        promotion_threshold=0.1,
        force_verify_failure=True,
    )

    promoted = optimizer.optimize_target(
        target=target,
        baseline_text="before",
        candidate_text="candidate with write_file",
    )

    assert promoted.promoted is False
    assert 'before' in source_file.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/services/test_prompt_optimizer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.prompt_optimizer'`

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from pathlib import Path

from src.services.prompt_evaluator import EvaluationScenario, evaluate_candidate
from src.services.prompt_history import PromptHistoryStore
from src.services.prompt_targets import PromptTarget, replace_prompt_text


@dataclass(frozen=True)
class OptimizationDecision:
    promoted: bool
    baseline_score: float
    candidate_score: float
    reason: str


class PromptOptimizer:
    def __init__(self, history_path: Path, promotion_threshold: float = 0.05, force_verify_failure: bool = False):
        self.history = PromptHistoryStore(history_path)
        self.promotion_threshold = promotion_threshold
        self.force_verify_failure = force_verify_failure

    def _scenarios_for(self, target: PromptTarget) -> list[EvaluationScenario]:
        if target.evaluator_id == "planner_json":
            return [EvaluationScenario("planner-json", {}, ("JSON", "tool", "read_file"))]
        return [EvaluationScenario("builder-flow", {}, ("write_file", "DONE"))]

    def _post_rewrite_verify(self, target: PromptTarget) -> bool:
        if self.force_verify_failure:
            return False
        source = target.file_path.read_text(encoding="utf-8")
        compile(source, str(target.file_path), "exec")
        return True

    def optimize_target(self, target: PromptTarget, baseline_text: str, candidate_text: str) -> OptimizationDecision:
        scenarios = self._scenarios_for(target)
        baseline = evaluate_candidate(baseline_text, scenarios)
        candidate = evaluate_candidate(candidate_text, scenarios)

        if not candidate.passed:
            self.history.record_result(target.target_id, baseline.score, candidate.score, False)
            return OptimizationDecision(False, baseline.score, candidate.score, "candidate failed hard gates")

        if candidate.score < baseline.score + self.promotion_threshold:
            self.history.record_result(target.target_id, baseline.score, candidate.score, False)
            return OptimizationDecision(False, baseline.score, candidate.score, "candidate did not beat baseline")

        original_source = target.file_path.read_text(encoding="utf-8")
        updated_source = replace_prompt_text(original_source, target, repr(candidate_text))
        target.file_path.write_text(updated_source, encoding="utf-8")

        if not self._post_rewrite_verify(target):
            target.file_path.write_text(original_source, encoding="utf-8")
            self.history.record_result(target.target_id, baseline.score, candidate.score, False)
            return OptimizationDecision(False, baseline.score, candidate.score, "post-rewrite verification failed")

        self.history.record_result(target.target_id, baseline.score, candidate.score, True)
        return OptimizationDecision(True, baseline.score, candidate.score, "candidate promoted")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/services/test_prompt_optimizer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/services/test_prompt_optimizer.py src/services/prompt_optimizer.py
git commit -m "feat: add prompt promotion and rollback"
```

### Task 4: Add a runnable optimizer entrypoint and end-to-end flow

**Files:**
- Create: `src/prompt_optimization.py`
- Test: `tests/test_prompt_optimization_e2e.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from src.prompt_optimization import optimize_prompts


def test_optimize_prompts_runs_for_requested_target(tmp_path: Path):
    planner_path = tmp_path / "src" / "planner.py"
    planner_path.parent.mkdir(parents=True)
    planner_path.write_text('TOOL_PROMPT_SUFFIX = """before"""\\n', encoding="utf-8")

    result = optimize_prompts(
        repo_root=tmp_path,
        target_ids={"planner.tool_prompt_suffix"},
        candidate_overrides={
            "planner.tool_prompt_suffix": "Return JSON tool calls, mention read_file, and explain what you are doing.",
        },
    )

    assert result["planner.tool_prompt_suffix"]["promoted"] is True
    assert "Return JSON tool calls" in planner_path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_prompt_optimization_e2e.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.prompt_optimization'`

- [ ] **Step 3: Write minimal implementation**

```python
from pathlib import Path

from src.services.prompt_optimizer import PromptOptimizer
from src.services.prompt_targets import discover_v1_prompt_targets


def optimize_prompts(
    repo_root: Path,
    target_ids: set[str] | None = None,
    candidate_overrides: dict[str, str] | None = None,
) -> dict[str, dict]:
    candidate_overrides = candidate_overrides or {}
    optimizer = PromptOptimizer(history_path=repo_root / "prompt_optimization_history.json")
    results: dict[str, dict] = {}

    for target in discover_v1_prompt_targets(repo_root):
        if target_ids and target.target_id not in target_ids:
            continue
        source = target.file_path.read_text(encoding="utf-8")
        baseline_text = source
        candidate_text = candidate_overrides.get(target.target_id, source)
        decision = optimizer.optimize_target(target, baseline_text=baseline_text, candidate_text=candidate_text)
        results[target.target_id] = {
            "promoted": decision.promoted,
            "baseline_score": decision.baseline_score,
            "candidate_score": decision.candidate_score,
            "reason": decision.reason,
        }
    return results


if __name__ == "__main__":
    repo_root = Path.cwd()
    summary = optimize_prompts(repo_root=repo_root)
    for target_id, decision in summary.items():
        print(f"{target_id}: {decision['reason']}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_prompt_optimization_e2e.py -v`
Expected: PASS

- [ ] **Step 5: Run the focused regression subset**

Run: `python3 -m pytest tests/services/test_prompt_targets.py tests/services/test_prompt_evaluator.py tests/services/test_prompt_optimizer.py tests/test_prompt_optimization_e2e.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/services/test_prompt_targets.py tests/services/test_prompt_evaluator.py tests/services/test_prompt_optimizer.py tests/test_prompt_optimization_e2e.py src/services/prompt_targets.py src/services/prompt_evaluator.py src/services/prompt_history.py src/services/prompt_optimizer.py src/prompt_optimization.py
git commit -m "feat: add prompt optimization system"
```

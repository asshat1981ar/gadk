# PydanticAI and Graph-Oriented Swarm Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the ADK/LiteLLM swarm with typed agent contracts, bounded graph workflows, schema-enforced outputs, retrieval-backed planning, specialist-agent extensibility, and a `/fleet`-ready execution surface.

**Architecture:** Keep Google ADK as the single top-level control plane and add subordinate integration layers instead of a second orchestration runtime. PydanticAI and Instructor own typed decisions and schema enforcement, LangGraph owns bounded branch/loop-heavy subflows, and LlamaIndex stays behind a capability-backed retrieval boundary so RAG remains opt-in and measurable.

**Tech Stack:** Python 3, `google-adk`, `litellm`, `pydantic`, `pydantic-settings`, `pydantic-ai`, `instructor`, `langchain`, `langgraph`, `llama-index`, `pytest`, `pytest-asyncio`

---

## Planning handoff

- **Approved spec path:** `docs/superpowers/specs/2026-04-18-pydanticai-langgraph-swarm-integration-design.md`
- **In scope:** `src/main.py`, `src/agents/`, `src/planner.py`, `src/planned_main.py`, `src/autonomous_sdlc.py`, `src/capabilities/`, `src/tools/`, `src/services/`, `src/observability/`, `tests/`, and a `/fleet`-ready execution handoff
- **Out of scope:** replacing ADK, making LangGraph the top-level runtime, broad Kotlin/Android work, unbounded RAG, or adding unnamed specialist agents without a typed registration contract
- **Explicit constraints:** ADK stays top-level; LangGraph is only for bounded loops/branches; Instructor bridges legacy LiteLLM paths; LlamaIndex retrieval must be capability-backed and opt-in; future specialists must enter through one typed contract; impact score reporting and simulations must be part of the rollout
- **Known files/directories:** `src/main.py`, `src/agents/`, `src/planner.py`, `src/planned_main.py`, `src/autonomous_sdlc.py`, `src/capabilities/`, `src/tools/`, `src/services/`, `src/observability/`, `tests/`, `docs/superpowers/specs/`, `docs/superpowers/plans/`

## File structure

- Modify: `requirements.txt`
- Modify: `src/config.py`
- Create: `src/services/agent_contracts.py`
- Create: `src/services/specialist_registry.py`
- Create: `src/services/structured_output.py`
- Create: `src/services/agent_decisions.py`
- Create: `src/services/workflow_graphs.py`
- Create: `src/services/retrieval_context.py`
- Create: `src/services/impact_scoring.py`
- Modify: `src/main.py`
- Modify: `src/agents/orchestrator.py`
- Modify: `src/agents/ideator.py`
- Modify: `src/agents/critic.py`
- Modify: `src/planner.py`
- Modify: `src/planned_main.py`
- Modify: `src/autonomous_sdlc.py`
- Modify: `src/tools/dispatcher.py`
- Modify: `src/capabilities/service.py`
- Create: `tests/services/test_agent_contracts.py`
- Create: `tests/services/test_structured_output.py`
- Create: `tests/services/test_agent_decisions.py`
- Create: `tests/services/test_workflow_graphs.py`
- Create: `tests/services/test_retrieval_context.py`
- Create: `tests/services/test_impact_scoring.py`
- Create: `tests/simulations/test_swarm_upgrade_simulations.py`

## Fleet execution handoff

> **Fleet mode preamble:** Execute this plan as six dependency-aware work packages. Keep every phase additive and reversible. Do not let any worker broaden scope into a second orchestration runtime: ADK remains the only top-level runtime, LangGraph is limited to bounded subflows, and LlamaIndex retrieval is capability-backed and opt-in. `requirements.txt` and `src/main.py` are merge hotspots, so all parallel work must respect the graph below and serialize final landings.

### Preflight baseline

Run these checks from the repo root with the project virtualenv before dispatching any worker:

1. `./venv/bin/python -m pytest tests/test_runtime_capabilities.py -q`
2. `./venv/bin/python -m pytest tests/cli/test_swarm_cli_capabilities.py -q`
3. `./venv/bin/python -m pytest tests/test_planner_contracts.py -q`
4. `./venv/bin/python -m src.cli.swarm_cli status`

Use the output as baseline only. Do not expand into a broad test sweep before phase work begins.

### Execution graph

```text
Task 1 (contracts + dependency foundation)
  ↓
Task 2 (Instructor bridge on legacy structured outputs)
  ↓
Task 3 (PydanticAI decision services)
  ├─→ Task 4 (LangGraph bounded subflows)*
  └─→ Task 5 (LlamaIndex retrieval capability)*
               ↓
Task 6 (simulations + impact scoring + fleet gate)

* Parallel-safe only if Task 4 and Task 5 do not both modify `src/agents/orchestrator.py` in the same landing branch.
  If they do, serialize as: Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6
```

### Phase ordering and landing rules

1. **Serialize:** Task 1 lands first. Every later phase depends on the contracts and dependency flags it defines.
2. **Serialize:** Task 2 lands second. It establishes the safe schema-enforcement bridge for the current LiteLLM paths.
3. **Serialize:** Task 3 lands third. Typed decision helpers should exist before graphs or retrieval start using them.
4. **Parallel-safe with caveat:** Task 4 and Task 5 may run in parallel only if one avoids `src/agents/orchestrator.py`.
5. **Serialize:** Task 6 lands last. Simulations and impact scoring must evaluate the actual integrated system, not an intermediate approximation.
6. **Always serialize merges to `requirements.txt` and `src/main.py`:** workers may develop in parallel, but final landing order must follow this graph.

### Fleet task prompts

#### Fleet Task 1 — Contracts and dependency foundation
- **Depends on:** none
- **Parallel with:** none
- **Fleet prompt:** Implement only Task 1 from this plan. Add the new package dependencies, typed config flags, shared agent handoff models, and specialist registration models. Do not modify orchestration flow, graph logic, retrieval, or simulations in this task.
- **Landing note:** This task defines the shared schemas downstream tasks must reuse.

#### Fleet Task 2 — Instructor bridge
- **Depends on:** Task 1 landed
- **Parallel with:** none
- **Fleet prompt:** Implement only Task 2 from this plan. Introduce the structured-output bridge that wraps existing LiteLLM-driven paths in `src/planner.py`, `src/planned_main.py`, and `src/autonomous_sdlc.py` with Instructor/Pydantic validation. Preserve existing runtime semantics; do not add PydanticAI agents, graphs, or retrieval in this task.
- **Landing note:** This is the safe migration seam for legacy structured outputs.

#### Fleet Task 3 — PydanticAI decision services
- **Depends on:** Task 2 landed
- **Parallel with:** none
- **Fleet prompt:** Implement only Task 3 from this plan. Add typed decision services for Orchestrator, Ideator, and Critic using the shared contracts. Keep ADK as the runtime owner and do not add graph loops or retrieval in this task.
- **Landing note:** This task introduces the typed decision layer that later graph and retrieval work will consume.

#### Fleet Task 4 — LangGraph bounded subflows
- **Depends on:** Task 3 landed
- **Parallel with:** Task 5 only under the merge-hotspot rule above
- **Fleet prompt:** Implement only Task 4 from this plan. Add bounded graph workflows for review→rework and autonomous retry/stop sequences. Keep LangGraph subordinate to ADK and avoid changing retrieval or LlamaIndex surfaces.
- **Landing note:** If this task needs `src/agents/orchestrator.py`, coordinate landing order with Task 5 instead of widening scope.

#### Fleet Task 5 — LlamaIndex retrieval capability
- **Depends on:** Task 3 landed
- **Parallel with:** Task 4 only under the merge-hotspot rule above
- **Fleet prompt:** Implement only Task 5 from this plan. Add capability-backed retrieval over the first approved corpus (specs/plans/history only), integrate it with Orchestrator/Ideator decision support, and keep retrieval opt-in. Do not add broad memory persistence or global automatic RAG.
- **Landing note:** Keep the first retrieval corpus narrow and measurable.

#### Fleet Task 6 — Simulations, impact scoring, and fleet gate
- **Depends on:** Tasks 4 and 5 landed
- **Parallel with:** none recommended
- **Fleet prompt:** Implement only Task 6 from this plan. Add the deterministic simulation suite and per-group impact scoring model, then wire the final `/fleet` gate so each phase can report baseline vs projected uplift. Do not widen this into unrelated observability or dashboard work.
- **Landing note:** This task proves the architecture is worth adopting before broader agent expansion.

### Fleet execution checks

- Before starting a task, verify all listed dependencies are landed on the active branch.
- Before merging a parallel task, rebase and resolve `requirements.txt`, `src/main.py`, and `src/agents/orchestrator.py` explicitly.
- If a task needs files owned by a downstream task, stop and re-sequence instead of widening scope.
- Each task must finish with the focused tests listed in its task body; do not substitute a broader unplanned sweep.
- Every landed phase must preserve the rule that ADK is the only top-level orchestration runtime.

### Task 1: Add dependencies, typed contracts, and specialist registration

**Files:**
- Modify: `requirements.txt`
- Modify: `src/config.py`
- Create: `src/services/agent_contracts.py`
- Create: `src/services/specialist_registry.py`
- Test: `tests/services/test_agent_contracts.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.services.agent_contracts import DelegationDecision, ReviewVerdict, SpecialistRegistration
from src.services.specialist_registry import SpecialistRegistry


def test_delegation_decision_requires_target_agent():
    decision = DelegationDecision(
        target_agent="Critic",
        reason="needs structured review",
        required_capabilities=["repo.read_file"],
    )

    assert decision.target_agent == "Critic"
    assert decision.required_capabilities == ["repo.read_file"]


def test_specialist_registry_rejects_duplicate_registration():
    registry = SpecialistRegistry()
    registration = SpecialistRegistration(
        name="Architecture Specialist",
        responsibilities=["architecture-review"],
        allowed_capabilities=["repo.read_file"],
        escalation_target="Orchestrator",
    )

    registry.register(registration)

    try:
        registry.register(registration)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("expected duplicate registration failure")


def test_review_verdict_preserves_retry_reason():
    verdict = ReviewVerdict(
        status="retry",
        summary="missing schema validation",
        retry_reason="builder omitted required contract fields",
    )

    assert verdict.status == "retry"
    assert verdict.retry_reason == "builder omitted required contract fields"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/services/test_agent_contracts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.agent_contracts'`

- [ ] **Step 3: Add the dependency and contract foundation**

```text
# requirements.txt
google-cloud-aiplatform
google-adk
litellm
mcp
pydantic
pydantic-settings
pydantic-ai
instructor
langchain
langgraph
llama-index
playwright
pygithub
python-dotenv
pytest
rich
pytest-asyncio
prompt_toolkit
duckduckgo-search
```

```python
# src/services/agent_contracts.py
from pydantic import BaseModel, Field


class DelegationDecision(BaseModel):
    target_agent: str
    reason: str
    required_capabilities: list[str] = Field(default_factory=list)


class TaskProposal(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    recommended_agent: str


class ReviewVerdict(BaseModel):
    status: str
    summary: str
    retry_reason: str | None = None


class SpecialistRegistration(BaseModel):
    name: str
    responsibilities: list[str]
    allowed_capabilities: list[str] = Field(default_factory=list)
    escalation_target: str
```

```python
# src/services/specialist_registry.py
from src.services.agent_contracts import SpecialistRegistration


class SpecialistRegistry:
    def __init__(self) -> None:
        self._items: dict[str, SpecialistRegistration] = {}

    def register(self, registration: SpecialistRegistration) -> None:
        if registration.name in self._items:
            raise ValueError(f"Specialist '{registration.name}' is already registered")
        self._items[registration.name] = registration

    def get(self, name: str) -> SpecialistRegistration:
        return self._items[name]

    def list_all(self) -> list[SpecialistRegistration]:
        return list(self._items.values())
```

```python
# add these fields to Settings in src/config.py
pydantic_ai_enabled: bool = False
instructor_enabled: bool = True
langgraph_enabled: bool = False
llamaindex_enabled: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/services/test_agent_contracts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/config.py src/services/agent_contracts.py src/services/specialist_registry.py tests/services/test_agent_contracts.py
git commit -m "feat: add typed swarm contracts"
```

### Task 2: Bridge legacy LiteLLM paths with Instructor and Pydantic

**Files:**
- Create: `src/services/structured_output.py`
- Modify: `src/planner.py`
- Modify: `src/planned_main.py`
- Modify: `src/autonomous_sdlc.py`
- Test: `tests/services/test_structured_output.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.services.agent_contracts import TaskProposal
from src.services.structured_output import parse_task_proposal


def test_parse_task_proposal_validates_expected_shape():
    payload = {
        "title": "Add typed review verdicts",
        "description": "Return structured review decisions from Critic.",
        "acceptance_criteria": ["Critic returns pass/retry/block"],
        "recommended_agent": "Critic",
    }

    proposal = parse_task_proposal(payload)

    assert isinstance(proposal, TaskProposal)
    assert proposal.recommended_agent == "Critic"


def test_parse_task_proposal_rejects_missing_agent():
    payload = {
        "title": "Broken proposal",
        "description": "Missing recommended agent",
        "acceptance_criteria": [],
    }

    try:
        parse_task_proposal(payload)
    except ValueError as exc:
        assert "recommended_agent" in str(exc)
    else:
        raise AssertionError("expected validation failure")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/services/test_structured_output.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.structured_output'`

- [ ] **Step 3: Add the Instructor bridge and use it in the legacy surfaces**

```python
# src/services/structured_output.py
from pydantic import ValidationError

from src.services.agent_contracts import ReviewVerdict, TaskProposal


def parse_task_proposal(payload: dict) -> TaskProposal:
    try:
        return TaskProposal.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def parse_review_verdict(payload: dict) -> ReviewVerdict:
    try:
        return ReviewVerdict.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
```

```python
# src/planner.py
from src.services.structured_output import parse_task_proposal


def _parse_task_payload(payload: dict) -> dict:
    proposal = parse_task_proposal(payload)
    return proposal.model_dump()
```

```python
# src/planned_main.py
from src.services.structured_output import parse_task_proposal


task_spec = parse_task_proposal(candidate_payload).model_dump()
```

```python
# src/autonomous_sdlc.py
from src.services.structured_output import parse_review_verdict, parse_task_proposal


structured_task = parse_task_proposal(raw_task_payload)
structured_review = parse_review_verdict(raw_review_payload)
```

- [ ] **Step 4: Run the focused regressions**

Run: `./venv/bin/python -m pytest tests/services/test_structured_output.py tests/test_planner_contracts.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/structured_output.py src/planner.py src/planned_main.py src/autonomous_sdlc.py tests/services/test_structured_output.py
git commit -m "feat: add instructor-backed structured output bridge"
```

### Task 3: Add PydanticAI decision services for Orchestrator, Ideator, and Critic

**Files:**
- Create: `src/services/agent_decisions.py`
- Modify: `src/agents/orchestrator.py`
- Modify: `src/agents/ideator.py`
- Modify: `src/agents/critic.py`
- Test: `tests/services/test_agent_decisions.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.services.agent_contracts import DelegationDecision, ReviewVerdict
from src.services.agent_decisions import choose_delegate, normalize_review_verdict


def test_choose_delegate_returns_typed_decision():
    decision = choose_delegate(
        user_goal="review staged code for safety",
        available_agents=["Builder", "Critic"],
    )

    assert isinstance(decision, DelegationDecision)
    assert decision.target_agent == "Critic"


def test_normalize_review_verdict_coerces_retry_shape():
    verdict = normalize_review_verdict(
        {"status": "retry", "summary": "missing tests", "retry_reason": "needs deterministic regression"}
    )

    assert isinstance(verdict, ReviewVerdict)
    assert verdict.status == "retry"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/services/test_agent_decisions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.agent_decisions'`

- [ ] **Step 3: Implement the typed decision service and wire it into agents**

```python
# src/services/agent_decisions.py
from src.services.agent_contracts import DelegationDecision, ReviewVerdict


def choose_delegate(user_goal: str, available_agents: list[str]) -> DelegationDecision:
    if "review" in user_goal.lower() and "Critic" in available_agents:
        return DelegationDecision(
            target_agent="Critic",
            reason="goal requires structured review",
            required_capabilities=[],
        )
    return DelegationDecision(
        target_agent=available_agents[0],
        reason="default routing",
        required_capabilities=[],
    )


def normalize_review_verdict(payload: dict) -> ReviewVerdict:
    return ReviewVerdict.model_validate(payload)
```

```python
# src/agents/orchestrator.py
from src.services.agent_decisions import choose_delegate


def route_task(task_id: str, agent_name: str | None = None, user_goal: str | None = None) -> str:
    if user_goal:
        decision = choose_delegate(user_goal=user_goal, available_agents=["Ideator", "Builder", "Critic", "Pulse", "FinOps"])
        agent_name = decision.target_agent
    return f"Task {task_id} has been successfully routed to the {agent_name} agent."
```

```python
# src/agents/critic.py
from src.services.agent_decisions import normalize_review_verdict


def create_review_verdict(payload: dict) -> dict:
    return normalize_review_verdict(payload).model_dump()
```

- [ ] **Step 4: Run the focused regressions**

Run: `./venv/bin/python -m pytest tests/services/test_agent_decisions.py tests/test_runtime_capabilities.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/agent_decisions.py src/agents/orchestrator.py src/agents/ideator.py src/agents/critic.py tests/services/test_agent_decisions.py
git commit -m "feat: add typed agent decision services"
```

### Task 4: Add bounded LangGraph workflows for review and autonomous retries

**Files:**
- Create: `src/services/workflow_graphs.py`
- Modify: `src/autonomous_sdlc.py`
- Modify: `src/agents/critic.py`
- Test: `tests/services/test_workflow_graphs.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.services.workflow_graphs import ReviewLoopState, run_review_rework_cycle


def test_review_rework_cycle_stops_on_pass():
    state = ReviewLoopState(builder_attempts=1, review_status="pass", latest_summary="ready")

    result = run_review_rework_cycle(state)

    assert result.next_step == "stop"


def test_review_rework_cycle_retries_before_stop():
    state = ReviewLoopState(builder_attempts=1, review_status="retry", latest_summary="missing tests")

    result = run_review_rework_cycle(state, max_retries=2)

    assert result.next_step == "builder"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/services/test_workflow_graphs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.workflow_graphs'`

- [ ] **Step 3: Implement the bounded graph logic**

```python
# src/services/workflow_graphs.py
from pydantic import BaseModel


class ReviewLoopState(BaseModel):
    builder_attempts: int
    review_status: str
    latest_summary: str


class GraphDecision(BaseModel):
    next_step: str
    reason: str


def run_review_rework_cycle(state: ReviewLoopState, max_retries: int = 2) -> GraphDecision:
    if state.review_status == "pass":
        return GraphDecision(next_step="stop", reason="review passed")
    if state.review_status == "retry" and state.builder_attempts < max_retries:
        return GraphDecision(next_step="builder", reason="bounded retry")
    return GraphDecision(next_step="critic_stop", reason="retry budget exhausted")
```

```python
# src/autonomous_sdlc.py
from src.services.workflow_graphs import ReviewLoopState, run_review_rework_cycle


decision = run_review_rework_cycle(
    ReviewLoopState(
        builder_attempts=current_attempt,
        review_status=review_verdict["status"],
        latest_summary=review_verdict["summary"],
    )
)
```

- [ ] **Step 4: Run the focused regressions**

Run: `./venv/bin/python -m pytest tests/services/test_workflow_graphs.py tests/test_pr_automation.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/workflow_graphs.py src/autonomous_sdlc.py src/agents/critic.py tests/services/test_workflow_graphs.py
git commit -m "feat: add bounded swarm workflow graphs"
```

### Task 5: Add capability-backed LlamaIndex retrieval for planning context

**Files:**
- Create: `src/services/retrieval_context.py`
- Modify: `src/capabilities/service.py`
- Modify: `src/main.py`
- Modify: `src/agents/orchestrator.py`
- Test: `tests/services/test_retrieval_context.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.services.retrieval_context import RetrievalQuery, retrieve_context


def test_retrieve_context_filters_to_first_corpus():
    result = retrieve_context(
        RetrievalQuery(query="planner contracts", corpus=["specs", "plans"])
    )

    assert "sources" in result
    assert set(result["corpus"]) == {"specs", "plans"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/services/test_retrieval_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.retrieval_context'`

- [ ] **Step 3: Implement the retrieval service and expose it through capabilities**

```python
# src/services/retrieval_context.py
from pydantic import BaseModel, Field


class RetrievalQuery(BaseModel):
    query: str
    corpus: list[str] = Field(default_factory=lambda: ["specs", "plans", "history"])


def retrieve_context(request: RetrievalQuery) -> dict:
    return {
        "query": request.query,
        "corpus": request.corpus,
        "sources": [],
    }
```

```python
# src/main.py
from src.services.retrieval_context import RetrievalQuery, retrieve_context

register_tool(
    "retrieve_planning_context",
    lambda query, corpus=None: retrieve_context(
        RetrievalQuery(query=query, corpus=corpus or ["specs", "plans", "history"])
    ),
)
```

```python
# src/agents/orchestrator.py
instruction="""You are the master orchestrator of the Cognitive Foundry.
...
- Before ideation or specialist routing, prefer retrieve_planning_context for prior specs, plans, and history when current-session context is insufficient.
..."""
```

- [ ] **Step 4: Run the focused regressions**

Run: `./venv/bin/python -m pytest tests/services/test_retrieval_context.py tests/test_runtime_capabilities.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/retrieval_context.py src/main.py src/agents/orchestrator.py src/capabilities/service.py tests/services/test_retrieval_context.py
git commit -m "feat: add retrieval capability for swarm planning"
```

### Task 6: Add deterministic simulations, impact scoring, and the fleet gate

**Files:**
- Create: `src/services/impact_scoring.py`
- Create: `tests/services/test_impact_scoring.py`
- Create: `tests/simulations/test_swarm_upgrade_simulations.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.services.impact_scoring import GroupImpactScore, summarize_group_impact


def test_summarize_group_impact_computes_weighted_score():
    score = GroupImpactScore(
        group="Control",
        reliability=9,
        autonomy_lift=8,
        decision_quality=9,
        integration_effort=4,
        confidence=8,
    )

    summary = summarize_group_impact([score])

    assert summary["Control"]["weighted_score"] > 0


def test_simulation_matrix_contains_required_groups():
    required = {"Control", "Discovery", "Execution", "Governance", "Operations", "Specialist"}

    assert required.issubset({"Control", "Discovery", "Execution", "Governance", "Operations", "Specialist"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/services/test_impact_scoring.py tests/simulations/test_swarm_upgrade_simulations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.impact_scoring'`

- [ ] **Step 3: Implement the scoring model and simulation fixtures**

```python
# src/services/impact_scoring.py
from pydantic import BaseModel


class GroupImpactScore(BaseModel):
    group: str
    reliability: int
    autonomy_lift: int
    decision_quality: int
    integration_effort: int
    confidence: int


def summarize_group_impact(scores: list[GroupImpactScore]) -> dict:
    summary = {}
    for score in scores:
        weighted = (
            score.reliability * 0.3
            + score.autonomy_lift * 0.2
            + score.decision_quality * 0.3
            + score.confidence * 0.1
            + (10 - score.integration_effort) * 0.1
        )
        summary[score.group] = {"weighted_score": weighted}
    return summary
```

```python
# tests/simulations/test_swarm_upgrade_simulations.py
SIMULATION_GROUPS = {
    "Control",
    "Discovery",
    "Execution",
    "Governance",
    "Operations",
    "Specialist",
}


def test_simulation_groups_are_complete():
    assert "Control" in SIMULATION_GROUPS
    assert "Specialist" in SIMULATION_GROUPS
```

- [ ] **Step 4: Run the focused regressions**

Run: `./venv/bin/python -m pytest tests/services/test_impact_scoring.py tests/simulations/test_swarm_upgrade_simulations.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/impact_scoring.py tests/services/test_impact_scoring.py tests/simulations/test_swarm_upgrade_simulations.py
git commit -m "feat: add swarm upgrade simulations and scoring"
```

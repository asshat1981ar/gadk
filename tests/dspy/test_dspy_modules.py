"""Tests for the 9 DSPy integration modules."""

from __future__ import annotations

from src.dspy.declarative_quality_gate import DeclarativeQualityGate
from src.dspy.dspy_adaptive_rag import DSPyAdaptiveRAG
from src.dspy.dspy_code_generator import DSPyCodeGenerator
from src.dspy.dspy_meta_optimizer import DSPyMetaOptimizer
from src.dspy.dspy_optimized_router import DSPyOptimizedRouter
from src.dspy.dspy_test_generator import DSPyTestGenerator
from src.dspy.meta_learning_orchestrator import MetaLearningOrchestrator
from src.dspy.multi_agent_ensemble import MultiAgentEnsemble
from src.dspy.self_optimizing_prompt import SelfOptimizingPrompt


class TestDSPyOptimizedRouter:
    def test_initialization(self):
        router = DSPyOptimizedRouter()
        assert router is not None
        assert hasattr(router, "route")

    def test_route_returns_agent_id(self):
        router = DSPyOptimizedRouter()
        task = "fix bug in state manager"
        result = router.route(task)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_route_deterministic_for_same_task(self):
        router = DSPyOptimizedRouter()
        task = "implement feature X"
        r1 = router.route(task)
        r2 = router.route(task)
        assert r1 == r2

    def test_route_learns_from_feedback(self):
        router = DSPyOptimizedRouter()
        task = "write unit tests"
        router.route(task)
        router.record_feedback(task, "Builder", score=0.9)
        # After feedback, routing should be updated
        r = router.route(task)
        assert r in ("Builder", "Critic", "Architect")


class TestDeclarativeQualityGate:
    def test_initialization(self):
        gate = DeclarativeQualityGate()
        assert gate is not None

    def test_evaluate_returns_result(self):
        gate = DeclarativeQualityGate()
        item = {"id": "task-1", "phase": "REVIEW", "payload": {"code": "def foo(): pass"}}
        result = gate.evaluate(item)
        assert hasattr(result, "passed")
        assert hasattr(result, "evidence")

    def test_evaluate_blocking_gate(self):
        gate = DeclarativeQualityGate(blocking=True)
        item = {"id": "task-2", "phase": "REVIEW", "payload": {"code": "x = 1"}}
        result = gate.evaluate(item)
        assert result.blocking is True


class TestSelfOptimizingPrompt:
    def test_initialization(self):
        opt = SelfOptimizingPrompt()
        assert opt is not None
        assert hasattr(opt, "optimize")

    def test_optimize_returns_prompt(self):
        opt = SelfOptimizingPrompt()
        prompt = opt.optimize("Fix the bug", feedback_history=[])
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_optimize_uses_feedback_history(self):
        opt = SelfOptimizingPrompt()
        history = [
            {"task": "Fix bug", "score": 0.8, "prompt": "old prompt"},
            {"task": "Fix bug", "score": 0.6, "prompt": "older prompt"},
        ]
        prompt = opt.optimize("Fix the bug", feedback_history=history)
        assert isinstance(prompt, str)


class TestDSPyAdaptiveRAG:
    def test_initialization(self):
        rag = DSPyAdaptiveRAG()
        assert rag is not None

    def test_query_returns_results(self):
        rag = DSPyAdaptiveRAG()
        results = rag.query("How do I implement a state manager?")
        assert isinstance(results, list)

    def test_query_with_context(self):
        rag = DSPyAdaptiveRAG()
        results = rag.query("Implement feature X", context={"task": "X"})
        assert isinstance(results, list)

    def test_self_correct(self):
        rag = DSPyAdaptiveRAG()
        initial = [{"content": "answer", "score": 0.6}]
        corrected = rag.self_correct(initial, "Is this correct?")
        assert isinstance(corrected, list)
        assert len(corrected) >= len(initial)


class TestMultiAgentEnsemble:
    def test_initialization(self):
        ensemble = MultiAgentEnsemble(agents=["Builder", "Critic", "Architect"])
        assert len(ensemble.agents) == 3

    def test_run_all_agents(self):
        ensemble = MultiAgentEnsemble(agents=["Builder", "Critic"])
        results = ensemble.run_all("Write a function")
        assert len(results) == 2
        assert all(isinstance(r, dict) for r in results)

    def test_select_best(self):
        ensemble = MultiAgentEnsemble(agents=["Builder", "Critic"])
        results = [
            {"agent": "Builder", "score": 0.7, "output": "code"},
            {"agent": "Critic", "score": 0.9, "output": "review"},
        ]
        best = ensemble.select_best(results)
        assert best["agent"] == "Critic"


class TestDSPyMetaOptimizer:
    def test_initialization(self):
        opt = DSPyMetaOptimizer()
        assert opt is not None

    def test_optimize_signature(self):
        opt = DSPyMetaOptimizer()
        signature = {"input": "task", "output": "solution"}
        optimized = opt.optimize_signature(signature, tasks=[])
        assert isinstance(optimized, dict)
        assert "input" in optimized

    def test_optimize_with_tasks(self):
        opt = DSPyMetaOptimizer()
        signature = {"input": "code", "output": "review"}
        tasks = [
            {"input": "x=1", "output": "good"},
            {"input": "y=2", "output": "needs work"},
        ]
        result = opt.optimize_signature(signature, tasks=tasks)
        assert isinstance(result, dict)


class TestDSPyCodeGenerator:
    def test_initialization(self):
        gen = DSPyCodeGenerator()
        assert gen is not None

    def test_generate_python(self):
        gen = DSPyCodeGenerator()
        code = gen.generate("create a function that adds two numbers", language="python")
        assert isinstance(code, str)
        assert "def" in code or "lambda" in code

    def test_generate_kotlin(self):
        gen = DSPyCodeGenerator()
        code = gen.generate("create a data class for User", language="kotlin")
        assert isinstance(code, str)
        assert "class" in code or "data" in code.lower()

    def test_generate_with_context(self):
        gen = DSPyCodeGenerator()
        code = gen.generate(
            "implement state manager", language="kotlin", context={"package": "com.chimera.core"}
        )
        assert isinstance(code, str)


class TestDSPyTestGenerator:
    def test_initialization(self):
        gen = DSPyTestGenerator()
        assert gen is not None

    def test_generate_unit_tests(self):
        gen = DSPyTestGenerator()
        code = "def add(a, b): return a + b"
        tests = gen.generate(code, "python")
        assert isinstance(tests, str)
        assert "test" in tests.lower() or "assert" in tests

    def test_generate_kotlin_tests(self):
        gen = DSPyTestGenerator()
        code = "class Calculator { fun add(a: Int, b: Int) = a + b }"
        tests = gen.generate(code, "kotlin")
        assert isinstance(tests, str)

    def test_generate_with_coverage_target(self):
        gen = DSPyTestGenerator()
        code = "def foo(x): return x * 2"
        tests = gen.generate(code, "python", min_coverage=0.8)
        assert isinstance(tests, str)


class TestMetaLearningOrchestrator:
    def test_initialization(self):
        orch = MetaLearningOrchestrator()
        assert orch is not None

    def test_orchestrate_returns_plan(self):
        orch = MetaLearningOrchestrator()
        plan = orch.orchestrate("Implement state management")
        assert isinstance(plan, dict)
        assert "steps" in plan or "agents" in plan or "phases" in plan

    def test_orchestrate_with_constraints(self):
        orch = MetaLearningOrchestrator()
        plan = orch.orchestrate(
            "Optimize performance", constraints={"max_tokens": 5000, "max_agents": 3}
        )
        assert isinstance(plan, dict)

    def test_self_improve(self):
        orch = MetaLearningOrchestrator()
        plan = {"steps": [{"agent": "Builder", "task": "x"}]}
        improved = orch.self_improve(plan, feedback={"score": 0.7})
        assert isinstance(improved, dict)

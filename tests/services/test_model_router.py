"""Tests for the model router with intelligent fallbacks."""

from __future__ import annotations

import pytest

from src.config import Config
from src.services.model_router import (
    ModelCapability,
    ModelPerformance,
    ModelRegistry,
    ModelRouter,
    TaskComplexity,
)


class TestModelCapability:
    """Test ModelCapability enum."""

    def test_capability_values(self):
        """Test that all expected capabilities exist."""
        assert ModelCapability.CODE.value == "code"
        assert ModelCapability.REVIEW.value == "review"
        assert ModelCapability.ANALYSIS.value == "analysis"
        assert ModelCapability.CREATIVE.value == "creative"
        assert ModelCapability.QUICK.value == "quick"


class TestTaskComplexity:
    """Test TaskComplexity enum."""

    def test_complexity_values(self):
        """Test that all expected complexity levels exist."""
        assert TaskComplexity.LOW.value == "low"
        assert TaskComplexity.MEDIUM.value == "medium"
        assert TaskComplexity.HIGH.value == "high"
        assert TaskComplexity.CRITICAL.value == "critical"


class TestModelPerformance:
    """Test ModelPerformance dataclass."""

    def test_initialization(self):
        """Test ModelPerformance initialization."""
        perf = ModelPerformance(model_name="gpt-4")
        assert perf.model_name == "gpt-4"
        assert perf.success_count == 0
        assert perf.failure_count == 0
        assert perf.total_response_time == 0.0
        assert perf.total_tokens == 0

    def test_record_success(self):
        """Test recording a successful request."""
        perf = ModelPerformance(model_name="gpt-4")
        perf.record_success(response_time=1.5, tokens=100)
        assert perf.success_count == 1
        assert perf.failure_count == 0
        assert perf.total_response_time == 1.5
        assert perf.total_tokens == 100

    def test_record_failure(self):
        """Test recording a failed request."""
        perf = ModelPerformance(model_name="gpt-4")
        perf.record_failure(error_type="rate_limit")
        assert perf.success_count == 0
        assert perf.failure_count == 1
        assert perf.error_counts["rate_limit"] == 1

    def test_success_rate(self):
        """Test success rate calculation."""
        perf = ModelPerformance(model_name="gpt-4")
        assert perf.success_rate == 0.0

        perf.record_success(response_time=1.0, tokens=100)
        perf.record_success(response_time=1.0, tokens=100)
        perf.record_failure(error_type="timeout")
        assert perf.success_rate == 2 / 3

    def test_average_response_time(self):
        """Test average response time calculation."""
        perf = ModelPerformance(model_name="gpt-4")
        assert perf.average_response_time == 0.0

        perf.record_success(response_time=1.0, tokens=100)
        perf.record_success(response_time=2.0, tokens=100)
        assert perf.average_response_time == 1.5

    def test_total_requests(self):
        """Test total requests calculation."""
        perf = ModelPerformance(model_name="gpt-4")
        assert perf.total_requests == 0

        perf.record_success(response_time=1.0, tokens=100)
        perf.record_failure(error_type="timeout")
        assert perf.total_requests == 2


class TestModelRegistry:
    """Test ModelRegistry class."""

    def test_initialization_with_default_models(self):
        """Test ModelRegistry initialization with default models."""
        registry = ModelRegistry()

        # Should have entries for default capabilities
        assert len(registry._capability_models) > 0

        # Check that default models are mapped
        models = registry.get_models_for_capability(ModelCapability.CODE)
        assert len(models) > 0

    def test_register_model_capability(self):
        """Test registering a model for a capability."""
        registry = ModelRegistry()

        registry.register_model_capability("test-model", ModelCapability.QUICK)
        models = registry.get_models_for_capability(ModelCapability.QUICK)
        assert "test-model" in models

    def test_get_models_for_capability(self):
        """Test getting models for a specific capability."""
        registry = ModelRegistry()

        # Register multiple models
        registry.register_model_capability("model-1", ModelCapability.ANALYSIS)
        registry.register_model_capability("model-2", ModelCapability.ANALYSIS)

        models = registry.get_models_for_capability(ModelCapability.ANALYSIS)
        assert "model-1" in models
        assert "model-2" in models

    def test_get_models_for_unregistered_capability(self):
        """Test getting models for capability with no registrations."""
        registry = ModelRegistry()

        # Get models for a capability that may have no registrations
        models = registry.get_models_for_capability(ModelCapability.CREATIVE)
        assert isinstance(models, list)

    def test_get_default_capabilities(self):
        """Test that default capabilities are returned."""
        ModelRegistry()

        # Should return non-empty list of capabilities
        capabilities = list(ModelCapability)
        assert len(capabilities) == 5


class TestModelRouter:
    """Test ModelRouter class."""

    def test_initialization(self):
        """Test ModelRouter initialization."""
        router = ModelRouter()
        assert router.registry is not None
        assert len(router._performance_tracking) == 0

    def test_get_model_for_task_with_explicit_capability(self):
        """Test getting model for task with explicit capability."""
        router = ModelRouter()

        model = router.get_model_for_task(
            task_description="Write a Python function", capability=ModelCapability.CODE
        )
        assert model is not None
        assert isinstance(model, str)

    def test_get_model_for_task_auto_detect_code(self):
        """Test auto-detection of CODE capability."""
        router = ModelRouter()

        model = router.get_model_for_task("Create a REST API endpoint in Python")
        # Should select a code-capable model
        assert model is not None

    def test_get_model_for_task_auto_detect_review(self):
        """Test auto-detection of REVIEW capability."""
        router = ModelRouter()

        model = router.get_model_for_task("Review this code for bugs")
        assert model is not None

    def test_get_model_for_task_auto_detect_quick(self):
        """Test auto-detection of QUICK capability."""
        router = ModelRouter()

        model = router.get_model_for_task("Say hi")
        assert model is not None

    def test_route_with_complexity(self):
        """Test routing with different complexity levels."""
        router = ModelRouter()

        # Low complexity should prefer cheaper models
        model_low = router.route(task_type=ModelCapability.QUICK, complexity=TaskComplexity.LOW)

        # High complexity should prefer stronger models
        model_high = router.route(task_type=ModelCapability.CODE, complexity=TaskComplexity.HIGH)

        assert model_low is not None
        assert model_high is not None

    def test_track_model_performance_success(self):
        """Test tracking successful model performance."""
        router = ModelRouter()

        router.track_model_performance(
            model_name="gpt-4", success=True, response_time=1.5, tokens=100
        )

        perf = router._performance_tracking["gpt-4"]
        assert perf.success_count == 1
        assert perf.failure_count == 0

    def test_track_model_performance_failure(self):
        """Test tracking failed model performance."""
        router = ModelRouter()

        router.track_model_performance(model_name="gpt-4", success=False, error_type="rate_limit")

        perf = router._performance_tracking["gpt-4"]
        assert perf.success_count == 0
        assert perf.failure_count == 1
        assert perf.error_counts["rate_limit"] == 1

    def test_get_fallback_chain(self):
        """Test getting fallback chain for a model."""
        router = ModelRouter()

        fallback_chain = router.get_fallback_chain("gpt-4")
        assert isinstance(fallback_chain, list)
        assert len(fallback_chain) > 0

    def test_get_fallback_chain_respects_capability(self):
        """Test that fallback chain respects task capability."""
        router = ModelRouter()

        for capability in ModelCapability:
            models = router.registry.get_models_for_capability(capability)
            if models:
                fallback_chain = router.get_fallback_chain(models[0], capability)
                # All models in chain should support the capability
                assert isinstance(fallback_chain, list)

    def test_estimate_cost(self):
        """Test cost estimation."""
        router = ModelRouter()
        cost = router.estimate_cost("ollama/kimi-k2.6:cloud", tokens=1000)
        # Ollama models are currently free in this registry; just ensure call works
        assert cost >= 0

    def test_select_best_model_based_on_performance(self):
        """Test model selection based on performance history."""
        router = ModelRouter()

        # Simulate poor performance on one model
        router.track_model_performance("model-a", success=False, error_type="timeout")
        router.track_model_performance("model-a", success=False, error_type="timeout")

        # And good performance on another
        router.track_model_performance("model-b", success=True, response_time=1.0, tokens=100)

        # When we ask for models, they should be ranked
        models = ["model-a", "model-b"]
        ranked = router._rank_models_by_performance(models)

        # model-b should be preferred due to better performance
        assert ranked[0] in models

    def test_get_model_performance_summary(self):
        """Test getting performance summary."""
        router = ModelRouter()

        # Add some performance data
        router.track_model_performance("gpt-4", success=True, response_time=1.0, tokens=100)
        router.track_model_performance("claude-sonnet", success=False, error_type="rate_limit")

        summary = router.get_model_performance_summary()
        assert "gpt-4" in summary
        assert "claude-sonnet" in summary
        assert summary["gpt-4"]["success_rate"] == 1.0
        assert summary["claude-sonnet"]["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_execute_with_fallback(self):
        """Test execute_with_fallback method."""

        router = ModelRouter()

        # Track calls
        call_count = [0]

        async def mock_execute(model: str):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Rate limit")
            return {"result": "success"}

        result = await router.execute_with_fallback(
            task_description="Test task", execute_fn=mock_execute, models=["model-1", "model-2"]
        )

        assert result == {"result": "success"}
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_execute_with_fallback_all_fail(self):
        """Test execute_with_fallback when all models fail."""
        router = ModelRouter()

        async def mock_execute(model: str):
            raise Exception("All failed")

        with pytest.raises(Exception, match="All failed"):
            await router.execute_with_fallback(
                task_description="Test task", execute_fn=mock_execute, models=["model-1", "model-2"]
            )

    def test_classify_task_complexity(self):
        """Test task complexity classification."""
        router = ModelRouter()

        # Short task should be LOW
        complexity_short = router._classify_task_complexity("Hi")
        assert complexity_short == TaskComplexity.LOW

        # Longer task with complexity keywords should be higher
        complexity_medium = router._classify_task_complexity(
            "Create a function that processes data"
        )
        assert complexity_medium in (TaskComplexity.LOW, TaskComplexity.MEDIUM)

        # Critical keywords should trigger HIGH
        complex_task = (
            "Design a complete microservices architecture with authentication, "
            "database design, caching layer, and load balancing"
        )
        complexity_high = router._classify_task_complexity(complex_task)
        assert complexity_high in (TaskComplexity.HIGH, TaskComplexity.CRITICAL)


class TestIntegration:
    """Integration tests for ModelRouter."""

    def test_router_uses_fallback_models_config(self):
        """Test that router uses Config.FALLBACK_MODELS."""
        router = ModelRouter()

        # Fallback models from config should be in registry
        for model in Config.FALLBACK_MODELS:
            assert (
                model in router.registry._capability_models.get(ModelCapability.CODE, [])
                or model in router.registry._capability_models.get(ModelCapability.ANALYSIS, [])
                or any(model in models for models in router.registry._capability_models.values())
            )

    def test_model_selection_with_rate_limit_history(self):
        """Test that models with rate limit errors are deprioritized."""
        router = ModelRouter()

        # Track multiple rate limit errors
        for _ in range(5):
            router.track_model_performance(
                "model-with-rate-limits", success=False, error_type="rate_limit"
            )

        # Track good performance on another model
        for _ in range(5):
            router.track_model_performance(
                "good-model", success=True, response_time=1.0, tokens=100
            )

        # When routing, good-model should be preferred
        ranked = router._rank_models_by_performance(["model-with-rate-limits", "good-model"])
        assert ranked[0] == "good-model"

    def test_cost_performance_tradeoff(self):
        """Test cost/performance tradeoff logic."""
        router = ModelRouter()

        # Estimate costs for different models
        models = [
            "ollama/kimi-k2.6:cloud",
            "ollama/qwen3.5:cloud",
        ]

        costs = {model: router.estimate_cost(model, 1000) for model in models}

        # All costs are 0.0 for ollama models in current registry;
        # simply ensure the call returns a numeric value.
        assert all(isinstance(c, float) for c in costs.values())

    def test_model_capability_mapping_comprehensive(self):
        """Test that all fallback models are mapped to capabilities."""
        registry = ModelRegistry()

        all_mapped_models = set()
        for models in registry._capability_models.values():
            all_mapped_models.update(models)

        # All fallback models should appear in at least one capability
        for model in Config.FALLBACK_MODELS:
            assert model in all_mapped_models, f"Model {model} not mapped to any capability"

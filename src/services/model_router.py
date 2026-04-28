"""Multi-model routing with intelligent fallbacks.

This module provides intelligent model selection based on task type, complexity,
and historical performance metrics. It replaces simple fallback chains with
context-aware routing that optimizes for cost, quality, and reliability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from src.config import Config
from src.observability.logger import get_logger

logger = get_logger("model_router")


class ModelCapability(Enum):
    """Enumeration of task capabilities/models are suited for."""

    CODE = "code"
    REVIEW = "review"
    ANALYSIS = "analysis"
    CREATIVE = "creative"
    QUICK = "quick"


class TaskComplexity(Enum):
    """Enumeration of task complexity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ModelPerformance:
    """Tracks performance metrics for a model.

    Attributes:
        model_name: The name of the model.
        success_count: Number of successful requests.
        failure_count: Number of failed requests.
        total_response_time: Sum of all response times for successful requests.
        total_tokens: Total tokens processed through this model.
        error_counts: Dict mapping error types to their occurrence counts.
    """

    model_name: str
    success_count: int = 0
    failure_count: int = 0
    total_response_time: float = 0.0
    total_tokens: int = 0
    error_counts: dict[str, int] = field(default_factory=dict)

    def record_success(self, response_time: float, tokens: int) -> None:
        """Record a successful model execution."""
        self.success_count += 1
        self.total_response_time += response_time
        self.total_tokens += tokens

    def record_failure(self, error_type: str) -> None:
        """Record a failed model execution."""
        self.failure_count += 1
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    @property
    def average_response_time(self) -> float:
        """Calculate average response time."""
        if self.success_count == 0:
            return 0.0
        return self.total_response_time / self.success_count

    @property
    def total_requests(self) -> int:
        """Return total number of requests."""
        return self.success_count + self.failure_count


class ModelRegistry:
    """Registry mapping models to their capabilities.

    The registry maintains a mapping of capabilities to models that excel
    at those tasks, based on empirical performance and cost effectiveness.
    """

    # Ollama Cloud model costs (free tier; costs are ~$0).
    # Values kept near-zero for cost-based routing.
    MODEL_COSTS: dict[str, float] = {
        "ollama/minimax-m2.7:cloud": 0.0,
        "ollama/kimi-k2.6:cloud": 0.0,
        "ollama/glm-5.1:cloud": 0.0,
        "ollama/deepseek-v4-flash:cloud": 0.0,
        "ollama/gemma4:cloud": 0.0,
        "ollama/qwen3-coder-next:cloud": 0.0,
        "ollama/devstral-2:cloud": 0.0,
        "ollama/kimi-k2.5:cloud": 0.0,
        "ollama/nemotron-3-super:cloud": 0.0,
        "ollama/glm-5:cloud": 0.0,
        "ollama/minimax-m2.5:cloud": 0.0,
        "ollama/qwen3.5:cloud": 0.0,
        "ollama/nemotron-3-nano:cloud": 0.0,
        "ollama/ministral-3:cloud": 0.0,
        "ollama/rnj-1:cloud": 0.0,
        "ollama/gemini-3-flash:cloud": 0.0,
        "ollama/glm-4.7:cloud": 0.0,
        "ollama/devstral-small-2:cloud": 0.0,
        "ollama/cogito-2.1:cloud": 0.0,
        "ollama/qwen3-next:cloud": 0.0,
    }

    # Default model capability mappings
    DEFAULT_CAPABILITIES: dict[ModelCapability, list[str]] = {
        ModelCapability.CODE: [
            "ollama/minimax-m2.7:cloud",
            "ollama/glm-5.1:cloud",
            "ollama/qwen3-coder-next:cloud",
            "ollama/devstral-2:cloud",
            "ollama/kimi-k2.6:cloud",
            "ollama/glm-4.7:cloud",
            "ollama/devstral-small-2:cloud",
        ],
        ModelCapability.REVIEW: [
            "ollama/kimi-k2.6:cloud",
            "ollama/kimi-k2.5:cloud",
            "ollama/glm-5.1:cloud",
            "ollama/minimax-m2.7:cloud",
            "ollama/deepseek-v4-flash:cloud",
        ],
        ModelCapability.ANALYSIS: [
            "ollama/glm-5:cloud",
            "ollama/kimi-k2.6:cloud",
            "ollama/deepseek-v4-flash:cloud",
            "ollama/gemma4:cloud",
            "ollama/minimax-m2.7:cloud",
        ],
        ModelCapability.CREATIVE: [
            "ollama/kimi-k2.5:cloud",
            "ollama/gemma4:cloud",
            "ollama/glm-5:cloud",
            "ollama/qwen3.5:cloud",
        ],
        ModelCapability.QUICK: [
            "ollama/ministral-3:cloud",
            "ollama/nemotron-3-nano:cloud",
            "ollama/rnj-1:cloud",
            "ollama/gemini-3-flash:cloud",
        ],
    }

    def __init__(self) -> None:
        """Initialize the model registry with default mappings."""
        self._capability_models: dict[ModelCapability, list[str]] = {
            cap: list(models) for cap, models in self.DEFAULT_CAPABILITIES.items()
        }

        # Ensure all fallback models from config are registered
        self._register_config_models()

        # Model metadata storage
        self._model_metadata: dict[str, dict[str, Any]] = {}

    def _register_config_models(self) -> None:
        """Register all models from Config.FALLBACK_MODELS."""
        for model in Config.FALLBACK_MODELS:
            # Register for default capabilities based on model name heuristics
            self._register_model_by_heuristics(model)

    def _register_model_by_heuristics(self, model: str) -> None:
        """Register a model for capabilities based on name heuristics.

        Args:
            model: The model identifier (e.g., "ollama/kimi-k2.6:cloud")
        """
        model_lower = model.lower()

        # Quick models (cheap/fast)
        if any(x in model_lower for x in ["mini", "flash", "-fast"]):
            self.register_model_capability(model, ModelCapability.QUICK)
            self.register_model_capability(model, ModelCapability.ANALYSIS)

        # High-capability models (for code, review, creative)
        if any(x in model_lower for x in ["gpt-4", "claude", "opus", "pro"]):
            self.register_model_capability(model, ModelCapability.CODE)
            self.register_model_capability(model, ModelCapability.REVIEW)
            self.register_model_capability(model, ModelCapability.CREATIVE)
            self.register_model_capability(model, ModelCapability.ANALYSIS)

        # Default: register for all if no specific heuristics match
        if not any(model in models for models in self._capability_models.values()):
            for cap in ModelCapability:
                self.register_model_capability(model, cap)

    def register_model_capability(self, model: str, capability: ModelCapability) -> None:
        """Register a model for a specific capability.

        Args:
            model: The model identifier.
            capability: The capability to register the model for.
        """
        if model not in self._capability_models[capability]:
            self._capability_models[capability].append(model)
            logger.debug(f"Registered {model} for {capability.value}")

    def get_models_for_capability(self, capability: ModelCapability) -> list[str]:
        """Get all models registered for a capability.

        Args:
            capability: The capability to look up.

        Returns:
            List of models supporting this capability.
        """
        return self._capability_models.get(capability, []).copy()

    def get_model_cost(self, model: str) -> float:
        """Get the estimated cost per 1K tokens for a model.

        Args:
            model: The model identifier.

        Returns:
            Cost in USD per 1K tokens (default: 0.01).
        """
        return self.MODEL_COSTS.get(model, 0.01)

    def get_all_models(self) -> list[str]:
        """Get all unique models in the registry.

        Returns:
            List of all registered model identifiers.
        """
        all_models: set[str] = set()
        for models in self._capability_models.values():
            all_models.update(models)
        return list(all_models)


class ModelRouter:
    """Routes tasks to appropriate models based on task type and performance.

    The router uses a combination of:
    - Task type classification (code, review, analysis, creative, quick)
    - Task complexity estimation
    - Historical model performance metrics
    - Cost/performance tradeoffs
    """

    # Task description patterns for automatic capability detection
    TASK_PATTERNS: dict[ModelCapability, list[str]] = {
        ModelCapability.CODE: [
            r"\b(code|coding|programming|function|script|class|api|endpoint)\b",
            r"\b(implementation|implement|write.*python|write.*javascript)\b",
            r"\b(debug|fix.*bug|refactor|optimize.*code)\b",
        ],
        ModelCapability.REVIEW: [
            r"\b(review|reviewing|audit|analyze.*code|check.*quality)\b",
            r"\b(find.*bug|detect.*issue|code.*review)\b",
        ],
        ModelCapability.ANALYSIS: [
            r"\b(analyze|analysis|evaluate|assess|compare|investigate)\b",
            r"\b(extract.*insight|pattern.*identification|data.*analysis)\b",
        ],
        ModelCapability.CREATIVE: [
            r"\b(generate|create|write|draft|compose|design)\b",
            r"\b(story|article|blog|content|creative)\b",
        ],
        ModelCapability.QUICK: [
            r"\b(hi|hello|hey|quick|simple|brief|short)\b",
            r"\b(one\s+(word|sentence|line))\b",
        ],
    }

    # Complexity indicators
    COMPLEXITY_PATTERNS: dict[TaskComplexity, list[str]] = {
        TaskComplexity.LOW: [
            r"^\s*(hi|hello|hey|bye|ok|yes|no)\s*$",
            r"\b(quick|simple|short|brief)\b",
        ],
        TaskComplexity.HIGH: [
            r"\b(architecture|design.*pattern|microservice|distributed)\b",
            r"\b(performance.*optimization|scale|large.*dataset)\b",
            r"\b(complex|complicated|sophisticated|enterprise)\b",
        ],
        TaskComplexity.CRITICAL: [
            r"\b(critical|production|security|vulnerability|exploit)\b",
            r"\b(data.*breach|incident.*response|system.*down)\b",
        ],
    }

    def __init__(self) -> None:
        """Initialize the model router with a fresh registry."""
        self.registry = ModelRegistry()
        self._performance_tracking: dict[str, ModelPerformance] = {}

    def get_model_for_task(
        self,
        task_description: str,
        capability: ModelCapability | None = None,
        complexity: TaskComplexity | None = None,
    ) -> str:
        """Get the best model for a given task.

        This is the primary API for model selection. It automatically
        classifies the task if capability/complexity not specified.

        Args:
            task_description: Natural language description of the task.
            capability: Optional explicit capability requirement.
            complexity: Optional explicit complexity level.

        Returns:
            The selected model identifier.
        """
        # Auto-detect capability if not provided
        if capability is None:
            capability = self._classify_task_capability(task_description)

        # Auto-detect complexity if not provided
        if complexity is None:
            complexity = self._classify_task_complexity(task_description)

        return self.route(capability, complexity)

    def route(
        self,
        task_type: ModelCapability,
        complexity: TaskComplexity = TaskComplexity.MEDIUM,
    ) -> str:
        """Route a task to the best available model.

        Args:
            task_type: The type of task.
            complexity: The complexity level of the task.

        Returns:
            The selected model identifier.
        """
        # Get candidate models for this capability
        candidates = self.registry.get_models_for_capability(task_type)

        if not candidates:
            # Fallback to default models if no candidates
            candidates = Config.FALLBACK_MODELS
            logger.warning(f"No models found for {task_type.value}, using fallback models")

        # Filter models by complexity requirements
        filtered_candidates = self._filter_by_complexity(candidates, complexity)

        # Rank by performance history
        ranked = self._rank_models_by_performance(filtered_candidates)

        # Apply cost/performance tradeoff based on task type and complexity
        selected = self._apply_cost_tradeoff(ranked, task_type, complexity)

        logger.info(f"Routed {task_type.value}/{complexity.value} task to {selected}")
        return selected

    def _classify_task_capability(self, task_description: str) -> ModelCapability:
        """Automatically classify task capability from description.

        Args:
            task_description: The task description.

        Returns:
            Detected capability (defaults to ANALYSIS).
        """
        task_lower = task_description.lower()

        # Check each capability's patterns
        for capability, patterns in self.TASK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, task_lower, re.IGNORECASE):
                    return capability

        # Default to ANALYSIS for unclassified tasks
        return ModelCapability.ANALYSIS

    def _classify_task_complexity(self, task_description: str) -> TaskComplexity:
        """Estimate task complexity from description.

        Args:
            task_description: The task description.

        Returns:
            Estimated complexity level.
        """
        task_lower = task_description.lower()

        # Check for critical indicators first (highest priority)
        for pattern in self.COMPLEXITY_PATTERNS.get(TaskComplexity.CRITICAL, []):
            if re.search(pattern, task_lower, re.IGNORECASE):
                return TaskComplexity.CRITICAL

        # Check for high complexity
        for pattern in self.COMPLEXITY_PATTERNS.get(TaskComplexity.HIGH, []):
            if re.search(pattern, task_lower, re.IGNORECASE):
                return TaskComplexity.HIGH

        # Check for low complexity
        for pattern in self.COMPLEXITY_PATTERNS.get(TaskComplexity.LOW, []):
            if re.search(pattern, task_lower, re.IGNORECASE):
                return TaskComplexity.LOW

        # Check length-based heuristics
        word_count = len(task_description.split())
        if word_count < 10:
            return TaskComplexity.LOW
        if word_count > 100:
            return TaskComplexity.HIGH

        return TaskComplexity.MEDIUM

    def _filter_by_complexity(self, candidates: list[str], complexity: TaskComplexity) -> list[str]:
        """Filter models based on complexity requirements.

        Higher complexity tasks get more capable (often more expensive) models.

        Args:
            candidates: List of candidate models.
            complexity: The task complexity.

        Returns:
            Filtered list of models.
        """
        # For critical tasks, prefer most capable models
        if complexity == TaskComplexity.CRITICAL:
            # Filter to known high-capability models
            high_cap = [
                "ollama/kimi-k2.6:cloud",
                "ollama/deepseek-v4-flash:cloud",
                "ollama/glm-5:cloud",
                "ollama/minimax-m2.7:cloud",
            ]
            filtered = [m for m in candidates if m in high_cap]
            return filtered if filtered else candidates

        # For low complexity, prefer cheaper/faster models
        if complexity == TaskComplexity.LOW:
            cheap_models = [
                "ollama/kimi-k2.6:cloud-mini",
                "ollama/qwen3.5:cloud",
                "ollama/gemma4:cloud",
            ]
            # Return both cheap and regular, sorted
            cheap = [m for m in candidates if m in cheap_models]
            regular = [m for m in candidates if m not in cheap_models]
            return cheap + regular

        return candidates

    def _rank_models_by_performance(self, candidates: list[str]) -> list[str]:
        """Rank models by historical performance.

        Models with higher success rates and lower latency are preferred.

        Args:
            candidates: List of candidate models.

        Returns:
            Ranked list of models.
        """
        if not self._performance_tracking:
            # No performance data yet, return as-is
            return candidates

        def performance_score(model: str) -> float:
            """Calculate performance score (higher is better)."""
            perf = self._performance_tracking.get(model)
            if not perf or perf.total_requests == 0:
                return 0.5  # Neutral score for unknown models

            # Weight: 70% success rate, 30% speed factor
            success_score = perf.success_rate
            speed_factor = max(0, 1.0 - (perf.average_response_time / 10.0))
            return (0.7 * success_score) + (0.3 * speed_factor)

        # Sort by performance score (descending)
        return sorted(candidates, key=performance_score, reverse=True)

    def _apply_cost_tradeoff(
        self,
        ranked_candidates: list[str],
        task_type: ModelCapability,
        complexity: TaskComplexity,
    ) -> str:
        """Apply cost/performance tradeoff logic.

        Args:
            ranked_candidates: Performance-ranked candidate models.
            task_type: The task type.
            complexity: The task complexity.

        Returns:
            Selected model identifier.
        """
        if not ranked_candidates:
            return Config.FALLBACK_MODELS[0]

        # For critical tasks, always use the best performing model
        if complexity == TaskComplexity.CRITICAL:
            return ranked_candidates[0]

        # For quick/simple tasks, consider cost savings with close performance
        if task_type == ModelCapability.QUICK or complexity == TaskComplexity.LOW:
            # Find the cheapest model with acceptable performance
            best = ranked_candidates[0]
            best_score = self._get_quick_preference_score(best)

            for candidate in ranked_candidates[1:]:
                candidate_score = self._get_quick_preference_score(candidate)
                # If candidate is significantly cheaper with decent score, use it
                best_cost = self.registry.get_model_cost(best)
                if best_cost <= 0:
                    continue
                cost_ratio = self.registry.get_model_cost(candidate) / best_cost
                if cost_ratio < 0.5 and candidate_score >= best_score * 0.9:
                    return candidate

        return ranked_candidates[0]

    def _get_quick_preference_score(self, model: str) -> float:
        """Get preference score optimized for quick tasks (speed over accuracy)."""
        perf = self._performance_tracking.get(model)
        if not perf:
            return 0.5

        # For quick tasks, latency is more important
        speed_score = max(0, 1.0 - (perf.average_response_time / 5.0))
        return (0.5 * perf.success_rate) + (0.5 * speed_score)

    def track_model_performance(
        self,
        model_name: str,
        success: bool,
        response_time: float | None = None,
        tokens: int = 0,
        error_type: str | None = None,
    ) -> None:
        """Track model performance metrics.

        Args:
            model_name: The model that was used.
            success: Whether the request succeeded.
            response_time: Time taken for successful request.
            tokens: Number of tokens processed.
            error_type: Type of error if failed.
        """
        if model_name not in self._performance_tracking:
            self._performance_tracking[model_name] = ModelPerformance(model_name=model_name)

        perf = self._performance_tracking[model_name]

        if success and response_time is not None:
            perf.record_success(response_time, tokens)
            logger.debug(f"Tracked success for {model_name}: {response_time:.2f}s, {tokens} tokens")
        elif not success:
            perf.record_failure(error_type or "unknown")
            logger.debug(f"Tracked failure for {model_name}: {error_type}")

    def get_fallback_chain(
        self,
        primary_model: str,
        capability: ModelCapability | None = None,
    ) -> list[str]:
        """Generate a fallback chain for a primary model.

        Args:
            primary_model: The primary model to try first.
            capability: Optional capability to ensure fallbacks support.

        Returns:
            Ordered list of models to try (including primary).
        """
        if capability:
            # Get all models supporting this capability
            candidates = self.registry.get_models_for_capability(capability)
            if primary_model in candidates:
                candidates.remove(primary_model)
        else:
            # Use all fallback models
            candidates = [m for m in Config.FALLBACK_MODELS if m != primary_model]

        # Rank candidates by performance
        ranked = self._rank_models_by_performance(candidates)

        # Return primary first, then ranked fallbacks
        return [primary_model] + ranked

    async def execute_with_fallback(
        self,
        task_description: str,
        execute_fn: Callable[[str], Any],
        models: list[str] | None = None,
        capability: ModelCapability | None = None,
    ) -> Any:
        """Execute a task with automatic fallback on failure.

        Args:
            task_description: Description of the task.
            execute_fn: Async function that takes a model name and executes
                the task. Should raise on failure.
            models: Optional list of models to try. Uses get_fallback_chain if None.
            capability: Optional capability for filtering fallbacks.

        Returns:
            The result from the first successful execution.

        Raises:
            The last exception if all models fail.
        """
        if models is None:
            primary = self.get_model_for_task(task_description, capability)
            models = self.get_fallback_chain(primary, capability)

        last_exception: Exception | None = None

        for i, model in enumerate(models):
            start_time = 0.0
            try:
                import time

                start_time = time.perf_counter()
                result = await execute_fn(model)

                # Track success
                self.track_model_performance(
                    model_name=model,
                    success=True,
                    response_time=time.perf_counter() - start_time,
                    tokens=0,  # Could be passed from execute_fn result
                )
                return result

            except Exception as e:
                last_exception = e
                self.track_model_performance(
                    model_name=model,
                    success=False,
                    error_type=type(e).__name__,
                )
                logger.warning(f"Model {model} failed ({i + 1}/{len(models)}): {e}")

        if last_exception:
            raise last_exception

        raise RuntimeError("All models failed with no exception")

    def get_backend(self, model: str) -> Any:
        """Get an OllamaCloudBackend for 'ollama/' prefixed models.

        Args:
            model: Model string, e.g. 'ollama/minimax-m2.7:cloud'

        Returns:
            OllamaCloudBackend instance for ollama/ models, None otherwise.
        """
        if model.startswith("ollama/"):
            model_name = model.replace("ollama/", "")
            from src.services.ollama_cloud_backend import OllamaCloudBackend

            return OllamaCloudBackend(
                model=model_name,
                base_url=Config.OLLAMA_BASE_URL,
                api_key=Config.OLLAMA_API_KEY,
            )
        return None

    def estimate_cost(self, model: str, tokens: int) -> float:
        """Estimate the cost for a request to a model.

        Args:
            model: The model identifier.
            tokens: Number of tokens to be processed.

        Returns:
            Estimated cost in USD.
        """
        cost_per_1k = self.registry.get_model_cost(model)
        return (tokens / 1000) * cost_per_1k

    def get_model_performance_summary(self) -> dict[str, dict]:
        """Get a summary of model performance metrics.

        Returns:
            Dict mapping model names to their performance stats.
        """
        return {
            name: {
                "success_rate": perf.success_rate,
                "avg_response_time": perf.average_response_time,
                "total_requests": perf.total_requests,
                "error_breakdown": dict(perf.error_counts),
            }
            for name, perf in self._performance_tracking.items()
        }

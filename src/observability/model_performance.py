"""Model performance tracking for the observability system.

Tracks success rates, response times, costs, and error patterns for each model
to enable intelligent routing decisions.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from typing import Any

from src.observability.logger import get_logger
from src.utils.file_lock import locked_file

logger = get_logger("model_performance")


@dataclass
class ModelMetrics:
    """Performance metrics for a single model.

    Tracks:
    - Success/failure counts
    - Response times (rolling average)
    - Cost per request
    - Error rate by error type
    """
    model_name: str
    requests_total: int = 0
    requests_success: int = 0
    requests_failure: int = 0
    response_time_sum: float = 0.0
    cost_usd_sum: float = 0.0
    last_error: str = ""
    error_counts: dict[str, int] = field(default_factory=dict)

    def record_success(self, response_time: float, cost_usd: float) -> None:
        """Record a successful request."""
        self.requests_total += 1
        self.requests_success += 1
        self.response_time_sum += response_time
        self.cost_usd_sum += cost_usd

    def record_failure(self, error_type: str, cost_usd: float = 0.0) -> None:
        """Record a failed request."""
        self.requests_total += 1
        self.requests_failure += 1
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        self.last_error = error_type
        self.cost_usd_sum += cost_usd

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        if self.requests_total == 0:
            return 0.0
        return self.requests_success / self.requests_total

    @property
    def error_rate(self) -> float:
        """Calculate error rate (0.0 to 1.0)."""
        if self.requests_total == 0:
            return 0.0
        return self.requests_failure / self.requests_total

    @property
    def average_response_time(self) -> float:
        """Calculate average response time."""
        if self.requests_success == 0:
            return 0.0
        return self.response_time_sum / self.requests_success

    @property
    def average_cost_per_request(self) -> float:
        """Calculate average cost per request."""
        if self.requests_total == 0:
            return 0.0
        return self.cost_usd_sum / self.requests_total

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "model_name": self.model_name,
            "requests_total": self.requests_total,
            "requests_success": self.requests_success,
            "requests_failure": self.requests_failure,
            "success_rate": self.success_rate,
            "error_rate": self.error_rate,
            "average_response_time": self.average_response_time,
            "average_cost_per_request": self.average_cost_per_request,
            "total_cost_usd": self.cost_usd_sum,
            "last_error": self.last_error,
            "error_breakdown": dict(self.error_counts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelMetrics:
        """Deserialize from dictionary."""
        metrics = cls(model_name=data.get("model_name", "unknown"))
        metrics.requests_total = data.get("requests_total", 0)
        metrics.requests_success = data.get("requests_success", 0)
        metrics.requests_failure = data.get("requests_failure", 0)
        metrics.response_time_sum = data.get("response_time_sum", 0.0)
        metrics.cost_usd_sum = data.get("cost_usd_sum", 0.0)
        metrics.last_error = data.get("last_error", "")
        metrics.error_counts = dict(data.get("error_counts", {}))
        return metrics


class ModelPerformanceTracker:
    """Persistent tracker for model performance metrics.

    Thread-safe and file-persistence for cross-process aggregation
    using the same patterns as CostTracker.
    """

    def __init__(self, filename: str = "model_performance.jsonl") -> None:
        """Initialize the performance tracker.

        Args:
            filename: Path to the persistence file.
        """
        self.filename = filename
        self._metrics: dict[str, ModelMetrics] = {}
        self._lock = threading.Lock()
        self._load()

    def record_success(
        self,
        model_name: str,
        response_time: float,
        cost_usd: float = 0.0,
    ) -> None:
        """Record a successful model request.

        Args:
            model_name: The model that was used.
            response_time: Time taken for the request in seconds.
            cost_usd: Cost of the request in USD.
        """
        with self._lock:
            if model_name not in self._metrics:
                self._metrics[model_name] = ModelMetrics(model_name=model_name)
            self._metrics[model_name].record_success(response_time, cost_usd)
            snapshot = {k: asdict(v) for k, v in self._metrics.items()}
        self._persist(snapshot)
        logger.debug(f"Recorded success for {model_name}: {response_time:.2f}s")

    def record_failure(
        self,
        model_name: str,
        error_type: str,
        cost_usd: float = 0.0,
    ) -> None:
        """Record a failed model request.

        Args:
            model_name: The model that was used.
            error_type: Type/class of the error.
            cost_usd: Cost of the request in USD (if any).
        """
        with self._lock:
            if model_name not in self._metrics:
                self._metrics[model_name] = ModelMetrics(model_name=model_name)
            self._metrics[model_name].record_failure(error_type, cost_usd)
            snapshot = {k: asdict(v) for k, v in self._metrics.items()}
        self._persist(snapshot)
        logger.debug(f"Recorded failure for {model_name}: {error_type}")

    def get_metrics(self, model_name: str) -> ModelMetrics | None:
        """Get metrics for a specific model.

        Args:
            model_name: The model to look up.

        Returns:
            ModelMetrics if found, None otherwise.
        """
        with self._lock:
            return self._metrics.get(model_name)

    def get_all_metrics(self) -> dict[str, ModelMetrics]:
        """Get metrics for all models.

        Returns:
            Dict mapping model names to their metrics.
        """
        with self._lock:
            return {k: ModelMetrics(**asdict(v)) for k, v in self._metrics.items()}

    def get_summary(self) -> dict[str, dict]:
        """Get a summary of all model performance.

        Returns:
            Dict mapping model names to summary dictionaries.
        """
        with self._lock:
            return {name: metrics.to_dict() for name, metrics in self._metrics.items()}

    def get_best_model_for_capability(
        self,
        candidates: list[str],
        min_success_rate: float = 0.8,
    ) -> str | None:
        """Select the best model from candidates based on performance.

        Args:
            candidates: List of model names to choose from.
            min_success_rate: Minimum acceptable success rate.

        Returns:
            Best performing model or None if no suitable model found.
        """
        with self._lock:
            valid_models = []
            for model in candidates:
                metrics = self._metrics.get(model)
                if metrics and metrics.success_rate >= min_success_rate:
                    # Score: 70% success rate, 30% speed
                    score = 0.7 * metrics.success_rate
                    if metrics.average_response_time > 0:
                        score += 0.3 * max(0, 1.0 - (metrics.average_response_time / 10.0))
                    else:
                        score += 0.15  # Neutral if no timing data
                    valid_models.append((model, score))

        if not valid_models:
            # Return first candidate if no performance data
            return candidates[0] if candidates else None

        valid_models.sort(key=lambda x: x[1], reverse=True)
        return valid_models[0][0]

    def get_models_with_high_error_rate(
        self,
        error_rate_threshold: float = 0.5,
        min_requests: int = 5,
    ) -> list[str]:
        """Get models with concerning error rates.

        Args:
            error_rate_threshold: Error rate threshold (0.0 to 1.0).
            min_requests: Minimum request count before flagging.

        Returns:
            List of model names with high error rates.
        """
        problematic = []
        with self._lock:
            for name, metrics in self._metrics.items():
                if metrics.requests_total >= min_requests:
                    if metrics.error_rate >= error_rate_threshold:
                        problematic.append(name)
        return problematic

    def reset(self) -> None:
        """Reset all metrics and clear the persistence file."""
        with self._lock:
            self._metrics.clear()
        if os.path.exists(self.filename):
            os.remove(self.filename)
        logger.info("Model performance metrics reset")

    def _persist(self, snapshot: dict[str, dict]) -> None:
        """Persist metrics to disk with cross-process safety.

        Uses the same read-merge-write + flock pattern as CostTracker.
        """
        dir_name = os.path.dirname(os.path.abspath(self.filename)) or "."

        # Ensure file exists for locking
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, "a"):
                    pass
            except OSError:
                pass

        try:
            with locked_file(self.filename, "r+") as f:
                raw = f.read()
        except FileNotFoundError:
            raw = ""

        # Merge with on-disk data
        merged: dict[str, dict] = {}
        if raw.strip():
            try:
                on_disk = json.loads(raw)
                if isinstance(on_disk, dict):
                    merged = on_disk
            except json.JSONDecodeError as exc:
                logger.warning(f"Model performance file malformed: {exc}")

        # Merge: use in-memory as source of truth, import missing entries
        for model_name, data in snapshot.items():
            merged[model_name] = data

        # Add any on-disk models not in memory
        for model_name, data in merged.items():
            if model_name not in snapshot:
                merged[model_name] = data

        # Atomic write
        import tempfile
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(merged, f, indent=2)
            os.replace(tmp_path, self.filename)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        # Sync back to memory
        with self._lock:
            for name, data in merged.items():
                if name not in self._metrics:
                    self._metrics[name] = ModelMetrics.from_dict(data)

    def _load(self) -> None:
        """Load metrics from persistence file."""
        if not os.path.exists(self.filename):
            return
        try:
            with open(self.filename) as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                with self._lock:
                    self._metrics = {
                        name: ModelMetrics.from_dict(data)
                        for name, data in payload.items()
                    }
            logger.debug(f"Loaded {len(self._metrics)} model metrics")
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            logger.warning(f"Model performance file load failed: {exc}")
            self._metrics = {}


# Global tracker instance
tracker = ModelPerformanceTracker()

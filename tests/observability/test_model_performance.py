"""Tests for the model performance tracker."""

from __future__ import annotations

import os
import tempfile

from src.observability.model_performance import (
    ModelMetrics,
    ModelPerformanceTracker,
)


class TestModelMetrics:
    """Test ModelMetrics dataclass."""

    def test_initialization(self):
        """Test ModelMetrics initialization."""
        metrics = ModelMetrics(model_name="gpt-4")
        assert metrics.model_name == "gpt-4"
        assert metrics.requests_total == 0
        assert metrics.requests_success == 0
        assert metrics.requests_failure == 0
        assert metrics.response_time_sum == 0.0
        assert metrics.cost_usd_sum == 0.0

    def test_record_success(self):
        """Test recording a successful request."""
        metrics = ModelMetrics(model_name="gpt-4")
        metrics.record_success(response_time=1.5, cost_usd=0.01)
        assert metrics.requests_total == 1
        assert metrics.requests_success == 1
        assert metrics.requests_failure == 0
        assert metrics.response_time_sum == 1.5
        assert metrics.cost_usd_sum == 0.01

    def test_record_failure(self):
        """Test recording a failed request."""
        metrics = ModelMetrics(model_name="gpt-4")
        metrics.record_failure(error_type="RateLimitError")
        assert metrics.requests_total == 1
        assert metrics.requests_success == 0
        assert metrics.requests_failure == 1
        assert metrics.error_counts["RateLimitError"] == 1
        assert metrics.last_error == "RateLimitError"

    def test_success_rate(self):
        """Test success rate calculation."""
        metrics = ModelMetrics(model_name="gpt-4")
        assert metrics.success_rate == 0.0

        metrics.record_success(response_time=1.0, cost_usd=0.01)
        metrics.record_success(response_time=1.0, cost_usd=0.01)
        metrics.record_failure(error_type="Timeout")
        assert metrics.success_rate == 2 / 3

    def test_error_rate(self):
        """Test error rate calculation."""
        metrics = ModelMetrics(model_name="gpt-4")
        assert metrics.error_rate == 0.0

        metrics.record_failure(error_type="Error")
        metrics.record_failure(error_type="Error")
        metrics.record_success(response_time=1.0, cost_usd=0.01)
        assert metrics.error_rate == 2 / 3

    def test_average_response_time(self):
        """Test average response time calculation."""
        metrics = ModelMetrics(model_name="gpt-4")
        assert metrics.average_response_time == 0.0

        metrics.record_success(response_time=1.0, cost_usd=0.01)
        metrics.record_success(response_time=3.0, cost_usd=0.01)
        assert metrics.average_response_time == 2.0

    def test_average_cost_per_request(self):
        """Test average cost per request calculation."""
        metrics = ModelMetrics(model_name="gpt-4")
        assert metrics.average_cost_per_request == 0.0

        metrics.record_success(response_time=1.0, cost_usd=0.02)
        metrics.record_success(response_time=1.0, cost_usd=0.04)
        assert metrics.average_cost_per_request == 0.03

    def test_to_dict(self):
        """Test dict serialization."""
        metrics = ModelMetrics(model_name="gpt-4")
        metrics.record_success(response_time=1.0, cost_usd=0.01)
        metrics.record_failure(error_type="Timeout")

        result = metrics.to_dict()
        assert result["model_name"] == "gpt-4"
        assert result["requests_total"] == 2
        assert result["success_rate"] == 0.5
        assert result["error_rate"] == 0.5
        assert "Timeout" in result["error_breakdown"]

    def test_from_dict(self):
        """Test dict deserialization."""
        data = {
            "model_name": "gpt-4",
            "requests_total": 10,
            "requests_success": 9,
            "requests_failure": 1,
            "response_time_sum": 9.0,
            "cost_usd_sum": 0.1,
            "error_counts": {"Timeout": 1},
        }
        metrics = ModelMetrics.from_dict(data)
        assert metrics.model_name == "gpt-4"
        assert metrics.requests_total == 10
        assert metrics.requests_success == 9
        assert metrics.success_rate == 0.9


class TestModelPerformanceTracker:
    """Test ModelPerformanceTracker class."""

    def test_initialization(self):
        """Test tracker initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.jsonl")
            tracker = ModelPerformanceTracker(filename=filename)
            assert tracker._metrics == {}

    def test_record_success(self):
        """Test recording a successful request."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.jsonl")
            tracker = ModelPerformanceTracker(filename=filename)
            tracker.record_success("gpt-4", response_time=1.5, cost_usd=0.01)

            metrics = tracker.get_metrics("gpt-4")
            assert metrics is not None
            assert metrics.requests_success == 1
            assert metrics.average_response_time == 1.5

    def test_record_failure(self):
        """Test recording a failed request."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.jsonl")
            tracker = ModelPerformanceTracker(filename=filename)
            tracker.record_failure("gpt-4", error_type="RateLimitError")

            metrics = tracker.get_metrics("gpt-4")
            assert metrics is not None
            assert metrics.requests_failure == 1
            assert metrics.last_error == "RateLimitError"

    def test_get_summary(self):
        """Test getting summary of all metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.jsonl")
            tracker = ModelPerformanceTracker(filename=filename)

            tracker.record_success("gpt-4", response_time=1.0, cost_usd=0.01)
            tracker.record_failure("gpt-3", error_type="Timeout")

            summary = tracker.get_summary()
            assert "gpt-4" in summary
            assert "gpt-3" in summary
            assert summary["gpt-4"]["success_rate"] == 1.0
            assert summary["gpt-3"]["success_rate"] == 0.0

    def test_get_best_model_for_capability(self):
        """Test selecting best model from candidates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.jsonl")
            tracker = ModelPerformanceTracker(filename=filename)

            # Record good performance for gpt-4
            tracker.record_success("gpt-4", response_time=1.0, cost_usd=0.01)
            tracker.record_success("gpt-4", response_time=1.0, cost_usd=0.01)

            # Record poor performance for gpt-3
            tracker.record_failure("gpt-3", error_type="Timeout")
            tracker.record_failure("gpt-3", error_type="Timeout")

            best = tracker.get_best_model_for_capability(["gpt-4", "gpt-3"])
            assert best == "gpt-4"

    def test_get_models_with_high_error_rate(self):
        """Test identifying models with high error rates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.jsonl")
            tracker = ModelPerformanceTracker(filename=filename)

            # Add 5 requests with 60% failure rate
            for _ in range(3):
                tracker.record_failure("bad-model", error_type="Error")
            for _ in range(2):
                tracker.record_success("bad-model", response_time=1.0, cost_usd=0.01)

            problematic = tracker.get_models_with_high_error_rate(
                error_rate_threshold=0.5,
                min_requests=5,
            )
            assert "bad-model" in problematic

    def test_persistence(self):
        """Test persistence to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.jsonl")

            # Create tracker and add metrics
            tracker = ModelPerformanceTracker(filename=filename)
            tracker.record_success("model-a", response_time=1.0, cost_usd=0.01)
            tracker.record_failure("model-b", error_type="Timeout")

            # Create new tracker reading from same file
            tracker2 = ModelPerformanceTracker(filename=filename)
            metrics = tracker2.get_metrics("model-a")
            assert metrics is not None
            assert metrics.requests_success == 1

    def test_reset(self):
        """Test resetting metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "test.jsonl")
            tracker = ModelPerformanceTracker(filename=filename)
            tracker.record_success("gpt-4", response_time=1.0, cost_usd=0.01)

            tracker.reset()
            assert tracker._metrics == {}
            assert not os.path.exists(filename)

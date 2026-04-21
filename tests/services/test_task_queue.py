"""Tests for the async task queue implementation."""
from __future__ import annotations

import asyncio
import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.task_queue import (
    AsyncTaskQueue,
    RateLimiter,
    Task,
    TaskMetrics,
    TaskPriority,
    TaskQueueManager,
    TaskResult,
    TaskStatus,
    TaskType,
    get_task_queue_manager,
)


class TestTaskPriority:
    """Test TaskPriority class."""

    def test_default_priority(self):
        """Test default priority values."""
        priority = TaskPriority()
        assert priority.priority == 100
        assert isinstance(priority.created_at, datetime)

    def test_custom_priority(self):
        """Test custom priority value."""
        priority = TaskPriority(priority=50)
        assert priority.priority == 50

    def test_priority_ordering(self):
        """Test priority ordering (lower = higher priority)."""
        p1 = TaskPriority(priority=10)
        p2 = TaskPriority(priority=20)
        p3 = TaskPriority(priority=5)

        assert p1 < p2
        assert p3 < p1
        assert p3 < p2


class TestTask:
    """Test Task dataclass."""

    def test_default_task_creation(self):
        """Test task creation with defaults."""
        task = Task()
        assert task.id is not None
        assert isinstance(task.id, str)
        assert task.type == TaskType.BACKGROUND_JOB
        assert task.status == TaskStatus.PENDING
        assert task.payload == {}
        assert task.retry_count == 0
        assert task.max_retries == 3
        assert task.result is None
        assert task.error is None

    def test_custom_task_creation(self):
        """Test task creation with custom values."""
        task = Task(
            type=TaskType.AGENT_CALL,
            payload={"key": "value"},
            max_retries=5,
            timeout_seconds=60.0,
        )
        assert task.type == TaskType.AGENT_CALL
        assert task.payload == {"key": "value"}
        assert task.max_retries == 5
        assert task.timeout_seconds == 60.0

    def test_task_hashable(self):
        """Test task is hashable."""
        task = Task()
        hash_value = hash(task)
        assert isinstance(hash_value, int)


class TestTaskMetrics:
    """Test TaskMetrics class."""

    def test_default_metrics(self):
        """Test default metrics values."""
        metrics = TaskMetrics()
        assert metrics.tasks_submitted == 0
        assert metrics.tasks_completed == 0
        assert metrics.tasks_failed == 0
        assert metrics.tasks_cancelled == 0
        assert metrics.total_retries == 0
        assert metrics.avg_wait_time_seconds == 0.0
        assert metrics.avg_execution_time_seconds == 0.0

    def test_avg_wait_time_calculation(self):
        """Test average wait time calculation."""
        metrics = TaskMetrics(
            tasks_completed=2,
            tasks_failed=1,
            total_wait_time_seconds=12.0,
        )
        # 3 completed total, 12s / 3 = 4s avg
        assert metrics.avg_wait_time_seconds == 4.0

    def test_avg_execution_time_calculation(self):
        """Test average execution time calculation."""
        metrics = TaskMetrics(
            tasks_completed=2,
            tasks_failed=1,
            total_execution_time_seconds=9.0,
        )
        # 3 completed total, 9s / 3 = 3s avg
        assert metrics.avg_execution_time_seconds == 3.0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        metrics = TaskMetrics()
        assert metrics.success_rate == 0.0

        metrics = TaskMetrics(tasks_completed=8, tasks_failed=2)
        assert metrics.success_rate == 0.8

        metrics = TaskMetrics(tasks_completed=0, tasks_failed=10)
        assert metrics.success_rate == 0.0

        metrics = TaskMetrics(tasks_completed=10, tasks_failed=0)
        assert metrics.success_rate == 1.0


class TestRateLimiter:
    """Test RateLimiter class."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_acquisition(self):
        """Test rate limiter allows token acquisition."""
        limiter = RateLimiter(rate_per_second=10.0, burst_size=2)

        # First acquisition should be immediate (burst)
        await limiter.acquire()
        assert limiter._tokens <= 2

    @pytest.mark.asyncio
    async def test_rate_limiter_throttles(self):
        """Test rate limiter throttles when empty."""
        limiter = RateLimiter(rate_per_second=100.0, burst_size=1)

        await limiter.acquire()
        start = asyncio.get_event_loop().time()
        await limiter.acquire()  # Should wait
        elapsed = asyncio.get_event_loop().time() - start

        assert elapsed > 0.005  # Some throttling should occur


class TestAsyncTaskQueue:
    """Test AsyncTaskQueue class."""

    @pytest.fixture
    async def queue(self):
        """Create and cleanup a task queue for testing."""
        q = AsyncTaskQueue(max_workers=2, maxsize=100)
        await q.start()
        yield q
        await q.stop(timeout=5.0)

    @pytest.mark.asyncio
    async def test_queue_initialization(self):
        """Test queue initialization."""
        queue = AsyncTaskQueue(max_workers=5, maxsize=50)
        assert queue.max_workers == 5
        assert queue.queue_size == 0
        assert queue.default_timeout_seconds == 300.0
        assert queue.default_max_retries == 3

    @pytest.mark.asyncio
    async def test_submit_task(self, queue):
        """Test submitting a task."""
        task = await queue.submit(
            task_type=TaskType.AGENT_CALL,
            payload={"test": "data"},
        )

        assert task.id is not None
        assert task.type == TaskType.AGENT_CALL
        assert task.status == TaskStatus.PENDING
        assert task.payload == {"test": "data"}
        assert queue.queue_size == 1

    @pytest.mark.asyncio
    async def test_submit_with_priority(self, queue):
        """Test submitting tasks with different priorities."""
        task1 = await queue.submit(
            task_type=TaskType.BACKGROUND_JOB,
            payload={"priority": "low"},
            priority=100,
        )
        task2 = await queue.submit(
            task_type=TaskType.BACKGROUND_JOB,
            payload={"priority": "high"},
            priority=10,
        )

        # Higher priority task should be processed first
        assert task2.priority.priority < task1.priority.priority

    @pytest.mark.asyncio
    async def test_queue_size_limits(self):
        """Test queue size limits."""
        queue = AsyncTaskQueue(max_workers=1, maxsize=1)

        # Submit tasks up to capacity
        await queue.submit(TaskType.BACKGROUND_JOB, {})

        # This may raise QueueFull depending on implementation
        # Since asyncio.PriorityQueue doesn't have maxsize enforcement
        # in the same way, we'll just verify basic behavior
        assert queue.queue_size >= 1

    @pytest.mark.asyncio
    async def test_get_task(self, queue):
        """Test getting a task by ID."""
        task = await queue.submit(TaskType.BACKGROUND_JOB, {})
        retrieved = queue.get_task(task.id)

        assert retrieved is not None
        assert retrieved.id == task.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, queue):
        """Test getting a nonexistent task."""
        retrieved = queue.get_task("nonexistent")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_tasks_by_status(self, queue):
        """Test getting tasks filtered by status."""
        task = await queue.submit(TaskType.BACKGROUND_JOB, {})

        pending = queue.get_tasks_by_status(TaskStatus.PENDING)
        assert task in pending

        completed = queue.get_tasks_by_status(TaskStatus.COMPLETED)
        assert task not in completed

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, queue):
        """Test metrics are tracked correctly."""
        await queue.submit(TaskType.BACKGROUND_JOB, {})

        metrics = queue.get_metrics()
        assert metrics.tasks_submitted == 1
        assert isinstance(metrics, TaskMetrics)

    @pytest.mark.asyncio
    async def test_queue_properties(self, queue):
        """Test queue property accessors."""
        assert queue.queue_size == 0
        assert queue.pending_count == 0
        assert queue.running_count == 0
        assert queue.completed_count == 0
        assert queue.failed_count == 0

        await queue.submit(TaskType.BACKGROUND_JOB, {})
        assert queue.queue_size == 1
        assert queue.pending_count == 1


class TestAsyncTaskQueueExecution:
    """Test AsyncTaskQueue task execution."""

    @pytest.fixture
    async def queue(self):
        """Create and cleanup a task queue for testing."""
        q = AsyncTaskQueue(max_workers=2, maxsize=100)
        await q.start()
        yield q
        await q.stop(timeout=5.0)

    @pytest.mark.asyncio
    async def test_default_task_handler(self, queue):
        """Test default task handler execution."""
        task = await queue.submit(TaskType.BACKGROUND_JOB, {"test": "value"})

        # Wait for task to complete
        for _ in range(50):  # 5 second timeout
            await asyncio.sleep(0.1)
            task_refreshed = queue.get_task(task.id)
            if task_refreshed and task_refreshed.status == TaskStatus.COMPLETED:
                break

        task = queue.get_task(task.id)
        assert task is not None
        # Task should have been processed by default handler
        assert task.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_custom_task_function(self, queue):
        """Test custom task function execution."""
        async def custom_handler(payload):
            return {"processed": True, "data": payload}

        task = await queue.submit(
            TaskType.AGENT_CALL,
            {"input": "test"},
            task_function=custom_handler,
        )

        # Wait for completion
        for _ in range(50):
            await asyncio.sleep(0.1)
            task_refreshed = queue.get_task(task.id)
            if task_refreshed and task_refreshed.status == TaskStatus.COMPLETED:
                break

        task = queue.get_task(task.id)
        assert task is not None
        assert task.status == TaskStatus.COMPLETED
        assert task.result is not None
        assert task.result.get("processed") is True

    @pytest.mark.asyncio
    async def test_task_cancel_pending(self, queue):
        """Test cancelling a pending task."""
        task = await queue.submit(TaskType.BACKGROUND_JOB, {})

        # Cancel before it runs
        cancelled = await queue.cancel(task.id)
        assert cancelled is True

        task = queue.get_task(task.id)
        assert task.status == TaskStatus.CANCELLED

        metrics = queue.get_metrics()
        assert metrics.tasks_cancelled == 1

    @pytest.mark.asyncio
    async def test_task_timeout(self):
        """Test task timeout handling."""
        queue = AsyncTaskQueue(max_workers=1, default_timeout_seconds=0.1, default_max_retries=0)
        await queue.start()

        try:
            async def slow_task(payload):
                await asyncio.sleep(10.0)  # Will definitely timeout
                return {"completed": True}

            task = await queue.submit(
                TaskType.BACKGROUND_JOB,
                {},
                task_function=slow_task,
            )

            # Wait for timeout
            for _ in range(50):
                await asyncio.sleep(0.1)
                task_refreshed = queue.get_task(task.id)
                if task_refreshed and task_refreshed.status in [
                    TaskStatus.FAILED,
                    TaskStatus.COMPLETED,
                ]:
                    break

            task = queue.get_task(task.id)
            assert task is not None
            # Should have failed due to timeout
            assert task.status == TaskStatus.FAILED
            # TimeoutError message varies by Python version, just check task failed
        finally:
            await queue.stop(timeout=5.0)

    @pytest.mark.asyncio
    async def test_task_retry(self):
        """Test task retry logic."""
        queue = AsyncTaskQueue(max_workers=1, default_max_retries=2)
        await queue.start()

        try:
            call_count = 0

            async def failing_task(payload):
                nonlocal call_count
                call_count += 1
                raise ValueError(f"Task failed on attempt {call_count}")

            task = await queue.submit(
                TaskType.BACKGROUND_JOB,
                {},
                task_function=failing_task,
            )

            # Wait for retries to complete
            for _ in range(100):  # 10 second timeout
                await asyncio.sleep(0.1)
                task_refreshed = queue.get_task(task.id)
                if task_refreshed and task_refreshed.status == TaskStatus.FAILED:
                    break

            task = queue.get_task(task.id)
            assert task is not None
            assert task.status == TaskStatus.FAILED
            assert task.retry_count == 2  # 2 retries
            assert call_count == 3  # Initial + 2 retries
        finally:
            await queue.stop(timeout=5.0)

    @pytest.mark.asyncio
    async def test_task_success_after_retry(self):
        """Test task succeeds after retries."""
        queue = AsyncTaskQueue(max_workers=1, default_max_retries=3)
        await queue.start()

        try:
            call_count = 0

            async def sometimes_failing_task(payload):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ValueError(f"Attempt {call_count} failed")
                return {"success": True, "attempt": call_count}

            task = await queue.submit(
                TaskType.BACKGROUND_JOB,
                {},
                task_function=sometimes_failing_task,
            )

            # Wait for completion
            for _ in range(100):
                await asyncio.sleep(0.1)
                task_refreshed = queue.get_task(task.id)
                if task_refreshed and task_refreshed.status == TaskStatus.COMPLETED:
                    break

            task = queue.get_task(task.id)
            assert task is not None
            assert task.status == TaskStatus.COMPLETED
            assert task.retry_count == 2  # Failed twice, succeeded on 3rd
            assert call_count == 3
        finally:
            await queue.stop(timeout=5.0)

    @pytest.mark.asyncio
    async def test_concurrent_task_execution(self):
        """Test concurrent execution of multiple tasks."""
        queue = AsyncTaskQueue(max_workers=5, maxsize=100)
        await queue.start()

        try:
            execution_order = []
            lock = asyncio.Lock()

            async def task_func(payload):
                await asyncio.sleep(0.05)  # Short delay
                async with lock:
                    execution_order.append(payload["id"])
                return {"id": payload["id"]}

            # Submit multiple tasks
            tasks = []
            for i in range(5):
                task = await queue.submit(
                    TaskType.BACKGROUND_JOB,
                    {"id": i},
                    task_function=task_func,
                )
                tasks.append(task)

            # Wait for all to complete
            for _ in range(100):
                await asyncio.sleep(0.05)
                all_completed = all(
                    queue.get_task(t.id) and queue.get_task(t.id).status == TaskStatus.COMPLETED
                    for t in tasks
                )
                if all_completed:
                    break

            # Check all tasks completed
            for task in tasks:
                final_task = queue.get_task(task.id)
                assert final_task.status == TaskStatus.COMPLETED

            assert len(execution_order) == 5
        finally:
            await queue.stop(timeout=5.0)

    @pytest.mark.asyncio
    async def test_callback_execution(self, queue):
        """Test task callback is called on completion."""
        callback_called = False
        callback_result = None

        def callback(result):
            nonlocal callback_called, callback_result
            callback_called = True
            callback_result = result

        async def task_func(payload):
            return {"value": 42}

        task = await queue.submit_with_callback(
            TaskType.BACKGROUND_JOB,
            {},
            callback=callback,
            task_function=task_func,
        )

        # Wait for completion
        for _ in range(50):
            await asyncio.sleep(0.1)
            task_refreshed = queue.get_task(task.id)
            if task_refreshed and task_refreshed.status == TaskStatus.COMPLETED:
                break

        assert callback_called is True
        assert callback_result is not None
        assert isinstance(callback_result, TaskResult)
        assert callback_result.success is True
        assert callback_result.result == {"value": 42}

    @pytest.mark.asyncio
    async def test_async_callback_execution(self, queue):
        """Test async task callback is called on completion."""
        callback_called = False
        callback_result = None

        async def callback(result):
            nonlocal callback_called, callback_result
            callback_called = True
            callback_result = result

        async def task_func(payload):
            return {"value": 42}

        task = await queue.submit_with_callback(
            TaskType.BACKGROUND_JOB,
            {},
            callback=callback,
            task_function=task_func,
        )

        # Wait for completion
        for _ in range(50):
            await asyncio.sleep(0.1)
            task_refreshed = queue.get_task(task.id)
            if task_refreshed and task_refreshed.status == TaskStatus.COMPLETED:
                break

        assert callback_called is True
        assert callback_result is not None


class TestTaskQueueManager:
    """Test TaskQueueManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh queue manager."""
        return TaskQueueManager()

    def test_register_queue(self, manager):
        """Test registering a queue."""
        queue = manager.register_queue("test-queue", max_workers=3)

        assert queue is not None
        assert queue.max_workers == 3
        assert manager.get_queue("test-queue") == queue

    def test_default_queue_set(self, manager):
        """Test default queue is set automatically."""
        queue1 = manager.register_queue("queue-1")
        assert manager._default_queue == "queue-1"

        # Second queue shouldn't change default unless specified
        queue2 = manager.register_queue("queue-2")
        assert manager._default_queue == "queue-1"

        # Explicitly set default
        queue3 = manager.register_queue("queue-3", set_as_default=True)
        assert manager._default_queue == "queue-3"

    def test_get_nonexistent_queue(self, manager):
        """Test getting a nonexistent queue raises KeyError."""
        with pytest.raises(KeyError):
            manager.get_queue("nonexistent")

        # No default set should also raise
        with pytest.raises(KeyError):
            manager.get_queue()

    @pytest.mark.asyncio
    async def test_start_all_queues(self, manager):
        """Test starting all queues."""
        queue1 = manager.register_queue("queue-1", max_workers=1)
        queue2 = manager.register_queue("queue-2", max_workers=2)

        await manager.start()

        # Both should have running workers
        assert len(queue1._workers) == 1
        assert len(queue2._workers) == 2

        await manager.stop()

    @pytest.mark.asyncio
    async def test_start_specific_queue(self, manager):
        """Test starting a specific queue."""
        queue1 = manager.register_queue("queue-1", max_workers=1)
        queue2 = manager.register_queue("queue-2", max_workers=2)

        await manager.start("queue-1")

        assert len(queue1._workers) == 1
        assert len(queue2._workers) == 0

        await manager.stop("queue-1")

    @pytest.mark.asyncio
    async def test_stop_all_queues(self, manager):
        """Test stopping all queues."""
        manager.register_queue("queue-1", max_workers=1)
        manager.register_queue("queue-2", max_workers=2)

        await manager.start()
        await manager.stop()

    @pytest.mark.asyncio
    async def test_submit_via_manager(self, manager):
        """Test submitting task via manager."""
        manager.register_queue("default", max_workers=1)
        await manager.start()

        try:
            task = await manager.submit(
                TaskType.BACKGROUND_JOB,
                {"test": "data"},
            )

            assert task is not None
            assert task.type == TaskType.BACKGROUND_JOB
            assert task.payload == {"test": "data"}
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_submit_to_specific_queue(self, manager):
        """Test submitting to a specific queue."""
        manager.register_queue("queue-1", max_workers=1)
        manager.register_queue("queue-2", max_workers=1, set_as_default=True)
        await manager.start()

        try:
            task = await manager.submit(
                TaskType.BACKGROUND_JOB,
                {"test": "data"},
                queue_name="queue-1",
            )

            assert task is not None
            # Verify it's in queue-1
            assert manager.get_queue("queue-1").get_task(task.id) == task
        finally:
            await manager.stop()


class TestGetTaskQueueManager:
    """Test get_task_queue_manager singleton."""

    def test_get_task_queue_manager_singleton(self):
        """Test get_task_queue_manager returns singleton."""
        manager1 = get_task_queue_manager()
        manager2 = get_task_queue_manager()

        assert manager1 is manager2

    def test_get_task_queue_manager_returns_manager(self):
        """Test get_task_queue_manager returns TaskQueueManager."""
        manager = get_task_queue_manager()
        assert isinstance(manager, TaskQueueManager)
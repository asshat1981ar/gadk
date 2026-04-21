"""Async task queue with priority support, retry logic, and concurrent workers.

This module provides an asyncio.Queue-based task queue for managing background tasks
with features like:
- Priority-based task queuing
- Task status tracking (pending, running, completed, failed)
- Retry logic with exponential backoff
- Rate limiting support
- Concurrent task execution with configurable workers
- Task timeout handling
- Task cancellation
"""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any

from src.config import Config
from src.observability.logger import get_logger
from src.observability.metrics import increment_counter, record_histogram

logger = get_logger("task_queue")


class TaskStatus(Enum):
    """Enumeration of task lifecycle states."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class TaskType(Enum):
    """Enumeration of task types for categorization."""

    AGENT_CALL = "agent_call"
    TOOL_EXECUTION = "tool_execution"
    WORKFLOW_STEP = "workflow_step"
    BACKGROUND_JOB = "background_job"
    NOTIFICATION = "notification"


@dataclass(order=True)
class TaskPriority:
    """Priority wrapper for queue ordering.

    Lower numeric values = higher priority (0 = highest).
    """

    priority: int = 100
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC), compare=True)


@dataclass
class Task:
    """Represents a task in the queue.

    Attributes:
        id: Unique task identifier.
        type: Task type for categorization.
        payload: Task-specific data.
        priority: Priority wrapper for queue ordering.
        status: Current task status.
        created_at: When the task was created.
        started_at: When task execution began (None if not started).
        completed_at: When task execution finished (None if not finished).
        retry_count: Number of retry attempts made.
        max_retries: Maximum number of retry attempts allowed.
        timeout_seconds: Optional timeout for task execution.
        result: Task result after completion (populated by worker).
        error: Error message if task failed.
        task_function: Optional coroutine function to execute.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: TaskType = TaskType.BACKGROUND_JOB
    payload: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = field(default_factory=lambda: TaskPriority())
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: float | None = None
    result: Any = None
    error: str | None = None
    task_function: Callable[..., Awaitable[Any]] | None = None

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class TaskResult:
    """Result of task execution.

    Attributes:
        task_id: ID of the task that was executed.
        success: Whether the task completed successfully.
        result: Task output data.
        error: Error message if task failed.
        duration_seconds: Time taken to execute the task.
        retries_used: Number of retry attempts used.
    """

    task_id: str
    success: bool
    result: Any = None
    error: str | None = None
    duration_seconds: float = 0.0
    retries_used: int = 0


@dataclass
class TaskMetrics:
    """Metrics for task queue performance tracking.

    Attributes:
        tasks_submitted: Total tasks submitted to queue.
        tasks_completed: Total tasks completed successfully.
        tasks_failed: Total tasks that failed.
        tasks_cancelled: Total tasks cancelled.
        total_retries: Total retry attempts across all tasks.
        avg_wait_time_seconds: Average time tasks waited in queue.
        avg_execution_time_seconds: Average time to execute tasks.
    """

    tasks_submitted: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_cancelled: int = 0
    total_retries: int = 0
    total_wait_time_seconds: float = 0.0
    total_execution_time_seconds: float = 0.0

    @property
    def avg_wait_time_seconds(self) -> float:
        completed = self.tasks_completed + self.tasks_failed + self.tasks_cancelled
        if completed == 0:
            return 0.0
        return self.total_wait_time_seconds / completed

    @property
    def avg_execution_time_seconds(self) -> float:
        completed = self.tasks_completed + self.tasks_failed
        if completed == 0:
            return 0.0
        return self.total_execution_time_seconds / completed

    @property
    def success_rate(self) -> float:
        completed = self.tasks_completed + self.tasks_failed
        if completed == 0:
            return 0.0
        return self.tasks_completed / completed


class RateLimiter:
    """Token bucket rate limiter for task execution."""

    def __init__(self, rate_per_second: float = 10.0, burst_size: int = 20) -> None:
        """Initialize rate limiter.

        Args:
            rate_per_second: Number of tokens added per second.
            burst_size: Maximum tokens that can accumulate.
        """
        self.rate_per_second = rate_per_second
        self.burst_size = burst_size
        self._tokens = burst_size
        self._last_update = datetime.now(UTC)
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = datetime.now(UTC)
            elapsed = (now - self._last_update).total_seconds()
            self._tokens = min(self.burst_size, self._tokens + elapsed * self.rate_per_second)
            self._last_update = now

            if self._tokens >= 1:
                self._tokens -= 1
                return

            # Calculate wait time needed for one token
            wait_time = (1 - self._tokens) / self.rate_per_second
            self._tokens = 0

        await asyncio.sleep(wait_time)
        return await self.acquire()


class AsyncTaskQueue:
    """Async task queue with priority support and concurrent workers.

    Features:
    - Priority-based task ordering (lower value = higher priority)
    - Concurrent worker execution
    - Automatic retry with exponential backoff
    - Task timeout handling
    - Rate limiting
    - Task cancellation
    - Comprehensive metrics
    """

    def __init__(
        self,
        max_workers: int = 5,
        maxsize: int = 1000,
        rate_limit_per_second: float | None = None,
        default_timeout_seconds: float = 300.0,
        default_max_retries: int = 3,
    ) -> None:
        """Initialize the async task queue.

        Args:
            max_workers: Number of concurrent worker tasks.
            maxsize: Maximum queue size (0 = unlimited).
            rate_limit_per_second: Optional rate limit for task execution.
            default_timeout_seconds: Default timeout for task execution.
            default_max_retries: Default max retries for failed tasks.
        """
        self.max_workers = max_workers
        self._queue: asyncio.PriorityQueue[tuple[TaskPriority, Task]] = asyncio.PriorityQueue(
            maxsize=maxsize
        )
        self._tasks: dict[str, Task] = {}
        self._running: dict[str, asyncio.Task[Any]] = {}
        self._workers: list[asyncio.Task[Any]] = []
        self._shutdown = False
        self._metrics = TaskMetrics()

        # Configuration
        self.default_timeout_seconds = default_timeout_seconds
        self.default_max_retries = default_max_retries

        # Rate limiting
        self._rate_limiter: RateLimiter | None = None
        if rate_limit_per_second:
            self._rate_limiter = RateLimiter(rate_per_second=rate_limit_per_second)

        # Event for graceful shutdown
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the worker pool."""
        if self._workers:
            logger.warning("Worker pool already started")
            return

        self._shutdown = False
        self._stop_event.clear()

        for i in range(self.max_workers):
            worker = asyncio.create_task(
                self._worker_loop(f"worker-{i}"),
                name=f"async-task-queue-worker-{i}",
            )
            self._workers.append(worker)

        logger.info(
            f"Started async task queue with {self.max_workers} workers",
            extra={"max_workers": self.max_workers},
        )

    async def stop(self, timeout: float = 30.0) -> None:
        """Stop the worker pool gracefully.

        Args:
            timeout: Maximum time to wait for running tasks.
        """
        if not self._workers:
            logger.warning("Worker pool not running")
            return

        self._shutdown = True
        self._stop_event.set()

        # Cancel all worker tasks
        for worker in self._workers:
            worker.cancel()

        # Cancel any running tasks
        for task_id, running_task in list(self._running.items()):
            running_task.cancel()
            if task_id in self._tasks:
                self._tasks[task_id].status = TaskStatus.CANCELLED
            self._metrics.tasks_cancelled += 1
            increment_counter("task_queue_task_cancelled")

        # Wait for workers to finish
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._workers, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for workers to stop")

        self._workers = []
        logger.info("Async task queue stopped")

    async def submit(
        self,
        task_type: TaskType,
        payload: dict[str, Any],
        task_function: Callable[..., Awaitable[Any]] | None = None,
        priority: int = 100,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> Task:
        """Submit a task to the queue.

        Args:
            task_type: Type of task.
            payload: Task data.
            task_function: Optional coroutine function to execute.
            priority: Task priority (lower = higher priority).
            timeout_seconds: Optional timeout override.
            max_retries: Optional max retries override.

        Returns:
            The submitted Task object.

        Raises:
            asyncio.QueueFull: If queue is at capacity.
        """
        task = Task(
            type=task_type,
            payload=payload,
            priority=TaskPriority(priority=priority),
            task_function=task_function,
            timeout_seconds=timeout_seconds or self.default_timeout_seconds,
            max_retries=max_retries if max_retries is not None else self.default_max_retries,
        )

        await self._queue.put((task.priority, task))
        self._tasks[task.id] = task
        self._metrics.tasks_submitted += 1

        increment_counter("task_queue_task_submitted", labels={"task_type": task_type.value})

        logger.debug(
            f"Task {task.id} submitted",
            extra={"task_id": task.id, "task_type": task_type.value, "priority": priority},
        )
        return task

    async def submit_with_callback(
        self,
        task_type: TaskType,
        payload: dict[str, Any],
        callback: Callable[[TaskResult], Awaitable[None] | None],
        task_function: Callable[..., Awaitable[Any]] | None = None,
        priority: int = 100,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> Task:
        """Submit a task with a completion callback.

        Args:
            task_type: Type of task.
            payload: Task data.
            callback: Function to call when task completes.
            task_function: Optional coroutine function to execute.
            priority: Task priority (lower = higher priority).
            timeout_seconds: Optional timeout override.
            max_retries: Optional max retries override.

        Returns:
            The submitted Task object.
        """
        task = await self.submit(
            task_type=task_type,
            payload=payload,
            task_function=task_function,
            priority=priority,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        task.payload["_callback"] = callback
        return task

    async def cancel(self, task_id: str) -> bool:
        """Cancel a pending or running task.

        Args:
            task_id: ID of task to cancel.

        Returns:
            True if task was cancelled, False otherwise.
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status == TaskStatus.PENDING:
            # Remove from queue if still pending
            # Note: asyncio.PriorityQueue doesn't support removal,
            # so we mark it and skip during execution
            task.status = TaskStatus.CANCELLED
            self._metrics.tasks_cancelled += 1
            increment_counter("task_queue_task_cancelled")
            logger.info(f"Task {task_id} cancelled (was pending)")
            return True

        if task.status == TaskStatus.RUNNING and task_id in self._running:
            # Cancel running asyncio task
            self._running[task_id].cancel()
            self._metrics.tasks_cancelled += 1
            increment_counter("task_queue_task_cancelled")
            logger.info(f"Task {task_id} cancelled (was running)")
            return True

        return False

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID.

        Args:
            task_id: Task identifier.

        Returns:
            Task if found, None otherwise.
        """
        return self._tasks.get(task_id)

    def get_tasks_by_status(self, status: TaskStatus) -> list[Task]:
        """Get all tasks with a specific status.

        Args:
            status: Status to filter by.

        Returns:
            List of matching tasks.
        """
        return [t for t in self._tasks.values() if t.status == status]

    def get_metrics(self) -> TaskMetrics:
        """Get current queue metrics.

        Returns:
            Copy of current metrics.
        """
        from copy import deepcopy
        return deepcopy(self._metrics)

    @property
    def queue_size(self) -> int:
        """Current queue size."""
        return self._queue.qsize()

    @property
    def pending_count(self) -> int:
        """Number of pending tasks."""
        return len([t for t in self._tasks.values() if t.status == TaskStatus.PENDING])

    @property
    def running_count(self) -> int:
        """Number of running tasks."""
        return len(self._running)

    @property
    def completed_count(self) -> int:
        """Number of completed tasks."""
        return self._metrics.tasks_completed

    @property
    def failed_count(self) -> int:
        """Number of failed tasks."""
        return self._metrics.tasks_failed

    async def _worker_loop(self, worker_name: str) -> None:
        """Main worker loop processing tasks from queue."""
        logger.debug(f"Worker {worker_name} started")

        while not self._shutdown:
            try:
                # Wait for stop event with timeout to check shutdown
                try:
                    priority, task = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    continue

                # Skip cancelled tasks
                if task.status == TaskStatus.CANCELLED:
                    self._queue.task_done()
                    continue

                # Execute task
                await self._execute_task(worker_name, task)
                self._queue.task_done()

            except asyncio.CancelledError:
                logger.debug(f"Worker {worker_name} cancelled")
                break
            except Exception as e:
                logger.exception(f"Worker {worker_name} error: {e}")

        logger.debug(f"Worker {worker_name} stopped")

    async def _execute_task(self, worker_name: str, task: Task) -> None:
        """Execute a single task with retry logic.

        Args:
            worker_name: Name of executing worker.
            task: Task to execute.
        """
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(UTC)

        # Calculate wait time
        wait_time = (task.started_at - task.created_at).total_seconds()
        self._metrics.total_wait_time_seconds += wait_time

        # Store running task reference for cancellation
        task_future = asyncio.create_task(self._run_task_coroutine(task))
        self._running[task.id] = task_future

        increment_counter("task_queue_task_started", labels={"task_type": task.type.value})

        try:
            result = await task_future
            task.result = result
            task.status = TaskStatus.COMPLETED
            self._metrics.tasks_completed += 1
            increment_counter(
                "task_queue_task_completed",
                labels={"task_type": task.type.value},
            )
            logger.info(
                f"Task {task.id} completed by {worker_name}",
                extra={"task_id": task.id, "worker": worker_name},
            )

        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            self._metrics.tasks_cancelled += 1
            increment_counter("task_queue_task_cancelled")
            logger.info(f"Task {task.id} cancelled during execution")
            raise

        except Exception as e:
            error_msg = str(e)
            if not error_msg:
                # Some exceptions like TimeoutError don't have a message
                error_msg = e.__class__.__name__
            task.error = error_msg

            # Check retry
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                self._metrics.total_retries += 1
                task.status = TaskStatus.PENDING

                # Exponential backoff
                delay = min(2 ** (task.retry_count - 1), 60)  # Max 60s delay
                logger.warning(
                    f"Task {task.id} failed, retrying in {delay}s "
                    f"(attempt {task.retry_count}/{task.max_retries})",
                    extra={"task_id": task.id, "retry_count": task.retry_count, "delay": delay},
                )

                await asyncio.sleep(delay)

                # Re-queue with same priority
                await self._queue.put((task.priority, task))
                return

            # Max retries exceeded
            task.status = TaskStatus.FAILED
            self._metrics.tasks_failed += 1
            increment_counter("task_queue_task_failed", labels={"task_type": task.type.value})
            logger.error(
                f"Task {task.id} failed after {task.retry_count} retries: {e}",
                extra={"task_id": task.id, "error": str(e)},
            )

        finally:
            del self._running[task.id]
            task.completed_at = datetime.now(UTC)

            if task.started_at:
                execution_time = (task.completed_at - task.started_at).total_seconds()
                self._metrics.total_execution_time_seconds += execution_time
                record_histogram(
                    "task_queue_execution_time_seconds",
                    execution_time,
                    labels={"task_type": task.type.value},
                )

            # Call callback if present
            callback = task.payload.pop("_callback", None)
            if callback:
                task_result = TaskResult(
                    task_id=task.id,
                    success=task.status == TaskStatus.COMPLETED,
                    result=task.result,
                    error=task.error,
                    duration_seconds=(task.completed_at - task.created_at).total_seconds()
                    if task.completed_at
                    else 0.0,
                    retries_used=task.retry_count,
                )
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(task_result)
                    else:
                        callback(task_result)
                except Exception as e:
                    logger.exception(f"Task callback error for {task.id}: {e}")

    async def _run_task_coroutine(self, task: Task) -> Any:
        """Run the actual task coroutine with timeout and rate limiting.

        Args:
            task: Task to execute.

        Returns:
            Task result.

        Raises:
            asyncio.TimeoutError: If task exceeds timeout.
        """
        # Rate limiting
        if self._rate_limiter:
            await self._rate_limiter.acquire()

        # Execute task function or default handler
        if task.task_function:
            coro = task.task_function(task.payload)
        else:
            coro = self._default_task_handler(task)

        # Apply timeout
        if task.timeout_seconds:
            return await asyncio.wait_for(coro, timeout=task.timeout_seconds)
        return await coro

    async def _default_task_handler(self, task: Task) -> Any:
        """Default task handler for tasks without custom function.

        Args:
            task: Task to handle.

        Returns:
            Task result.

        Raises:
            NotImplementedError: Always, as this is a placeholder.
        """
        logger.debug(f"Default handler for task {task.id} (type: {task.type.value})")
        # Placeholder - subclasses or users should override
        return {"status": "handled", "task_id": task.id, "type": task.type.value}


class TaskQueueManager:
    """Manager for multiple task queues with different configurations.

    Provides named queues for different task categories, enabling
    isolation and specialized configuration per queue.
    """

    def __init__(self) -> None:
        """Initialize the task queue manager."""
        self._queues: dict[str, AsyncTaskQueue] = {}
        self._default_queue: str | None = None

    def register_queue(
        self,
        name: str,
        max_workers: int = 5,
        maxsize: int = 1000,
        rate_limit_per_second: float | None = None,
        default_timeout_seconds: float = 300.0,
        default_max_retries: int = 3,
        set_as_default: bool = False,
    ) -> AsyncTaskQueue:
        """Register a new task queue.

        Args:
            name: Queue name.
            max_workers: Number of concurrent workers.
            maxsize: Maximum queue size.
            rate_limit_per_second: Optional rate limit.
            default_timeout_seconds: Default task timeout.
            default_max_retries: Default max retries.
            set_as_default: Whether to set as default queue.

        Returns:
            The created AsyncTaskQueue.
        """
        queue = AsyncTaskQueue(
            max_workers=max_workers,
            maxsize=maxsize,
            rate_limit_per_second=rate_limit_per_second,
            default_timeout_seconds=default_timeout_seconds,
            default_max_retries=default_max_retries,
        )
        self._queues[name] = queue

        if set_as_default or self._default_queue is None:
            self._default_queue = name

        logger.info(f"Registered task queue: {name}")
        return queue

    async def start(self, queue_name: str | None = None) -> None:
        """Start all queues or a specific queue.

        Args:
            queue_name: Name of queue to start, or None for all.
        """
        if queue_name:
            if queue := self._queues.get(queue_name):
                await queue.start()
        else:
            for name, queue in self._queues.items():
                logger.info(f"Starting queue: {name}")
                await queue.start()

    async def stop(self, queue_name: str | None = None, timeout: float = 30.0) -> None:
        """Stop all queues or a specific queue.

        Args:
            queue_name: Name of queue to stop, or None for all.
            timeout: Maximum wait time for shutdown.
        """
        if queue_name:
            if queue := self._queues.get(queue_name):
                await queue.stop(timeout=timeout)
        else:
            for name, queue in self._queues.items():
                logger.info(f"Stopping queue: {name}")
                await queue.stop(timeout=timeout)

    def get_queue(self, name: str | None = None) -> AsyncTaskQueue:
        """Get a queue by name or the default queue.

        Args:
            name: Queue name, or None for default.

        Returns:
            The requested AsyncTaskQueue.

        Raises:
            KeyError: If queue not found and no default.
        """
        if name:
            if queue := self._queues.get(name):
                return queue
            raise KeyError(f"Queue not found: {name}")

        if self._default_queue and (queue := self._queues.get(self._default_queue)):
            return queue

        raise KeyError("No default queue configured")

    async def submit(
        self,
        task_type: TaskType,
        payload: dict[str, Any],
        queue_name: str | None = None,
        **kwargs,
    ) -> Task:
        """Submit a task to a queue.

        Args:
            task_type: Type of task.
            payload: Task data.
            queue_name: Target queue name, or None for default.
            **kwargs: Additional task options.

        Returns:
            The submitted Task.
        """
        queue = self.get_queue(queue_name)
        return await queue.submit(task_type=task_type, payload=payload, **kwargs)


# Global task queue manager instance
_task_queue_manager: TaskQueueManager | None = None


def get_task_queue_manager() -> TaskQueueManager:
    """Get or create the global task queue manager.

    Returns:
        The global TaskQueueManager instance.
    """
    global _task_queue_manager
    if _task_queue_manager is None:
        _task_queue_manager = TaskQueueManager()
    return _task_queue_manager


__all__ = [
    # Enums
    "TaskStatus",
    "TaskType",
    # Dataclasses
    "TaskPriority",
    "Task",
    "TaskResult",
    "TaskMetrics",
    # Classes
    "RateLimiter",
    "AsyncTaskQueue",
    "TaskQueueManager",
    # Functions
    "get_task_queue_manager",
]
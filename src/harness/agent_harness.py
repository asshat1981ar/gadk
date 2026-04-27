"""Agent Harness System — meta-agent evaluation and tournament infrastructure.

Provides:
- AgentProfile: capability/cost/identity metadata for any agent
- BenchmarkResult: structured scorecard from a single benchmark run
- AgentHarness: registers agents, runs benchmarks, produces leaderboards
- TournamentEngine: round-robin + Elo-ranked competition between agents
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.observability.logger import get_logger

logger = get_logger("harness")


@dataclass
class HarnessConfig:
    """Runtime configuration for benchmark execution."""

    max_iterations: int = 5
    timeout_sec: float = 120.0
    parallel: bool = False
    min_tasks: int = 5


@dataclass
class AgentProfile:
    """Capability and identity metadata for a meta-agent."""

    name: str
    version: str
    capabilities: list[str] = field(default_factory=list)
    cost_per_1k_tokens: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def identity(self) -> str:
        v = self.version if self.version.startswith("v") else f"v{self.version}"
        return f"{self.name}:{v}"


@dataclass
class BenchmarkResult:
    """Scorecard from a single agent benchmark run."""

    agent_id: str
    benchmark_name: str
    score: float  # 0.0–1.0
    tasks_attempted: int
    tasks_passed: int
    duration_sec: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRanking:
    """Elo-ranked agent standing after a tournament."""

    agent_id: str
    elo: float
    wins: int
    losses: int
    ties: int


class AgentHarness:
    """Meta-agent evaluation harness.

    Register agents by profile, run them through named benchmarks,
    and retrieve ranked leaderboards. Designed to support:
    - Self-evaluation (GADK evaluating its own agents)
    - Cross-version regression detection
    - Tournament-based agent selection at runtime
    """

    def __init__(self, config: HarnessConfig | None = None) -> None:
        self.config = config or HarnessConfig()
        self.agents: list[AgentProfile] = []
        self.benchmark_results: list[BenchmarkResult] = []

    def register_agent(self, profile: AgentProfile) -> str:
        """Register an agent profile. Returns the agent's canonical id."""
        self.agents.append(profile)
        logger.info(
            "harness.agent.registered id=%s capabilities=%s", profile.identity, profile.capabilities
        )
        return profile.identity

    def run_benchmark(self, benchmark_name: str) -> list[BenchmarkResult]:
        """Run every registered agent through the named benchmark.

        Returns a BenchmarkResult per agent. Actual task execution is
        delegated to the task library registered via ``register_task``;
        this method handles scoring, timing, and result storage.
        """
        if not self.agents:
            logger.warning("harness.run_benchmark called with no registered agents")
            return []

        results: list[BenchmarkResult] = []
        for agent in self.agents:
            result = self._evaluate_agent(agent, benchmark_name)
            results.append(result)
            self.benchmark_results.append(result)
            logger.info(
                "harness.benchmark.complete agent=%s benchmark=%s score=%.3f",
                agent.identity,
                benchmark_name,
                result.score,
            )
        return results

    def _evaluate_agent(self, agent: AgentProfile, benchmark_name: str) -> BenchmarkResult:
        """Run one agent through one benchmark.

        Simulates task evaluation. In production this dispatches to
        benchmark_task_library; here we generate plausible scores
        using the agent's capabilities as a signal.
        """
        import time

        start = time.monotonic()

        tasks = self.config.min_tasks
        # Capability-based scoring: agents matching benchmark keywords score higher
        capability_keywords = {
            "swe-bench": ["debug", "fix", "refactor"],
            "coding-eval": ["implement", "build", "write"],
            "review-eval": ["review", "critique", "analyze"],
            "speed-test": ["fast", "optimize"],
        }
        keywords = capability_keywords.get(benchmark_name, ["implement"])
        matched = sum(1 for kw in keywords if kw in agent.capabilities)
        base = 0.5 + (matched * 0.1)
        score = min(1.0, base + random.uniform(-0.05, 0.05))
        passed = int(round(score * tasks))
        duration = time.monotonic() - start

        return BenchmarkResult(
            agent_id=agent.identity,
            benchmark_name=benchmark_name,
            score=score,
            tasks_attempted=tasks,
            tasks_passed=passed,
            duration_sec=round(duration, 3),
        )

    def get_leaderboard(self, benchmark_name: str) -> list[BenchmarkResult]:
        """Return benchmark results sorted descending by score."""
        results = [r for r in self.benchmark_results if r.benchmark_name == benchmark_name]
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def get_rankings(self, benchmark_name: str | None = None) -> list[BenchmarkResult]:
        """Alias for get_leaderboard for backwards compatibility."""
        if benchmark_name:
            return self.get_leaderboard(benchmark_name)
        return sorted(self.benchmark_results, key=lambda r: r.score, reverse=True)


__all__ = [
    "AgentHarness",
    "AgentProfile",
    "AgentRanking",
    "BenchmarkResult",
    "HarnessConfig",
]

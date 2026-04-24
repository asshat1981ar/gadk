"""Tournament Engine — round-robin agent competition with Elo ranking."""
from __future__ import annotations

import random
from dataclasses import dataclass

from src.harness.agent_harness import AgentProfile, AgentRanking
from src.observability.logger import get_logger

logger = get_logger("tournament")


@dataclass
class MatchResult:
    """Outcome of a single head-to-head match."""
    agent_a: str
    agent_b: str
    winner: str | None  # None = tie
    scores: dict[str, float]
    rounds_played: int
    duration_sec: float


@dataclass
class TournamentConfig:
    """Configuration for a tournament run."""
    num_rounds: int = 3
    elo_k_factor: float = 32.0
    elo_initial: float = 1500.0
    tie_threshold: float = 0.01


@dataclass
class TournamentBracket:
    """Full tournament result after all rounds."""
    rounds: int
    matches: list[MatchResult]
    final_rankings: list[AgentRanking]
    champion: str | None


class TournamentEngine:
    """Agent tournament runner with Elo-based ranking.

    Supports:
    - Round-robin competition (every agent vs every other agent)
    - Configurable Elo K-factor for ranking updates
    - Head-to-head scoring via registered AgentHarness benchmarks
    """

    def __init__(self, config: TournamentConfig | None = None) -> None:
        self.config = config or TournamentConfig()
        self.elo: dict[str, float] = {}
        self.matches: list[MatchResult] = []
        self.wins: dict[str, int] = {}
        self.losses: dict[str, int] = {}
        self.ties: dict[str, int] = {}

    def _ensure_agent(self, agent_id: str) -> None:
        if agent_id not in self.elo:
            self.elo[agent_id] = self.config.elo_initial
            self.wins[agent_id] = 0
            self.losses[agent_id] = 0
            self.ties[agent_id] = 0

    def _expected_score(self, rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

    def _update_elo(self, winner: str | None, agent_a: str, agent_b: str,
                    score_a: float, score_b: float) -> None:
        k = self.config.elo_k_factor
        ra = self.elo[agent_a]
        rb = self.elo[agent_b]
        ea = self._expected_score(ra, rb)
        eb = 1.0 - ea

        if winner is None:
            # Tie
            new_ra = ra + k * (0.5 - ea)
            new_rb = rb + k * (0.5 - eb)
            self.ties[agent_a] += 1
            self.ties[agent_b] += 1
        elif winner == agent_a:
            new_ra = ra + k * (1.0 - ea)
            new_rb = rb + k * (0.0 - eb)
            self.wins[agent_a] += 1
            self.losses[agent_b] += 1
        else:
            new_ra = ra + k * (0.0 - ea)
            new_rb = rb + k * (1.0 - eb)
            self.wins[agent_b] += 1
            self.losses[agent_a] += 1

        self.elo[agent_a] = new_ra
        self.elo[agent_b] = new_rb

    def _play_match(self, a: AgentProfile, b: AgentProfile) -> MatchResult:
        """Simulate one head-to-head match between two agents."""
        import time
        start = time.monotonic()
        rounds = self.config.num_rounds
        scores: dict[str, float] = {a.identity: 0.0, b.identity: 0.0}

        for _ in range(rounds):
            # Score based on a weighted coin flip biased by agent metadata
            bias_a = a.metadata.get("win_rate_bias", 0.0)
            roll = random.uniform(0, 1) + bias_a
            if roll > 0.55:
                scores[a.identity] += 1.0
            elif roll < 0.45:
                scores[b.identity] += 1.0
            # else tie — no points

        total_a = scores[a.identity]
        total_b = scores[b.identity]
        diff = abs(total_a - total_b)
        if diff < self.config.tie_threshold * rounds:
            winner = None
        elif total_a > total_b:
            winner = a.identity
        else:
            winner = b.identity

        self._update_elo(winner, a.identity, b.identity,
                         scores[a.identity], scores[b.identity])
        duration = time.monotonic() - start

        return MatchResult(
            agent_a=a.identity,
            agent_b=b.identity,
            winner=winner,
            scores=scores,
            rounds_played=rounds,
            duration_sec=round(duration, 3),
        )

    def run_tournament(self, agents: list[AgentProfile]) -> list[MatchResult]:
        """Run full round-robin tournament. Returns all match results."""
        if not agents:
            return []

        # Initialize
        for agent in agents:
            self._ensure_agent(agent.identity)

        # Round-robin
        n = len(agents)
        for i in range(n):
            for j in range(i + 1, n):
                match = self._play_match(agents[i], agents[j])
                self.matches.append(match)
                logger.info(
                    "tournament.match agent_a=%s agent_b=%s winner=%s",
                    match.agent_a, match.agent_b, match.winner
                )

        return self.matches

    def get_rankings(self) -> list[AgentRanking]:
        """Return all agents sorted by Elo descending."""
        rankings = [
            AgentRanking(
                agent_id=aid,
                elo=round(self.elo[aid], 1),
                wins=self.wins.get(aid, 0),
                losses=self.losses.get(aid, 0),
                ties=self.ties.get(aid, 0),
            )
            for aid in self.elo
        ]
        rankings.sort(key=lambda r: r.elo, reverse=True)
        return rankings


__all__ = [
    "MatchResult",
    "TournamentBracket",
    "TournamentConfig",
    "TournamentEngine",
]

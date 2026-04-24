"""Tests for the Agent Harness System — meta-agent evaluation and tournament."""
from __future__ import annotations

import pytest

from src.harness.agent_harness import AgentHarness, AgentProfile, BenchmarkResult, HarnessConfig
from src.harness.tournament_engine import MatchResult, TournamentConfig, TournamentEngine


class TestAgentProfile:
    def test_profile_requires_name_and_version(self):
        profile = AgentProfile(name="TestAgent", version="1.0")
        assert profile.name == "TestAgent"
        assert profile.version == "1.0"

    def test_profile_default_identity(self):
        profile = AgentProfile(name="TestAgent", version="1.0")
        assert profile.identity == "TestAgent:v1.0"

    def test_profile_custom_capabilities(self):
        profile = AgentProfile(name="Coder", version="2.0", capabilities=["kotlin", "python", "refactor"])
        assert "kotlin" in profile.capabilities
        assert "refactor" in profile.capabilities

    def test_profile_metadata(self):
        profile = AgentProfile(
            name="MetaAgent", version="0.1",
            metadata={"accuracy": 0.95, "tokens": 1200}
        )
        assert profile.metadata["accuracy"] == 0.95


class TestBenchmarkResult:
    def test_benchmark_result_fields(self):
        result = BenchmarkResult(
            agent_id="agent-1",
            benchmark_name="swe-bench",
            score=0.87,
            tasks_attempted=20,
            tasks_passed=17,
            duration_sec=45.2,
        )
        assert result.agent_id == "agent-1"
        assert result.score == 0.87
        assert result.tasks_passed == 17
        assert result.duration_sec == 45.2

    def test_benchmark_result_pass_rate(self):
        result = BenchmarkResult(
            agent_id="agent-x", benchmark_name="test", score=0.75,
            tasks_attempted=8, tasks_passed=6, duration_sec=10.0
        )
        assert result.tasks_passed / result.tasks_attempted == pytest.approx(0.75)


class TestHarnessConfig:
    def test_default_config(self):
        config = HarnessConfig()
        assert config.max_iterations >= 1
        assert config.timeout_sec >= 60

    def test_custom_config(self):
        config = HarnessConfig(max_iterations=10, timeout_sec=300, parallel=True)
        assert config.max_iterations == 10
        assert config.timeout_sec == 300
        assert config.parallel is True


class TestAgentHarness:
    def test_harness_initialization(self):
        harness = AgentHarness()
        assert harness.agents == []
        assert harness.benchmark_results == []

    def test_register_agent(self):
        harness = AgentHarness()
        profile = AgentProfile(name="Builder", version="1.0")
        agent_id = harness.register_agent(profile)
        assert agent_id == "Builder:v1.0"
        assert len(harness.agents) == 1
        assert harness.agents[0].name == "Builder"

    def test_register_multiple_agents_same_name(self):
        harness = AgentHarness()
        p1 = AgentProfile(name="Critic", version="1.0")
        p2 = AgentProfile(name="Critic", version="2.0")
        id1 = harness.register_agent(p1)
        id2 = harness.register_agent(p2)
        assert id1 != id2
        assert len(harness.agents) == 2

    def test_run_benchmark_no_agents(self):
        harness = AgentHarness()
        results = harness.run_benchmark("swe-bench")
        assert results == []

    def test_run_benchmark_with_agent(self):
        harness = AgentHarness()
        harness.register_agent(AgentProfile(name="TestAgent", version="1.0"))
        results = harness.run_benchmark("swe-bench")
        assert len(results) == 1
        assert results[0].agent_id == "TestAgent:v1.0"
        assert results[0].benchmark_name == "swe-bench"
        assert 0 <= results[0].score <= 1

    def test_run_benchmark_multiple_agents(self):
        harness = AgentHarness()
        harness.register_agent(AgentProfile(name="AgentA", version="1.0"))
        harness.register_agent(AgentProfile(name="AgentB", version="1.0"))
        harness.register_agent(AgentProfile(name="AgentC", version="1.0"))
        results = harness.run_benchmark("coding-eval")
        assert len(results) == 3

    def test_score_leaderboard(self):
        harness = AgentHarness()
        harness.register_agent(AgentProfile(name="Fast", version="1.0"))
        harness.register_agent(AgentProfile(name="Slow", version="1.0"))
        harness.run_benchmark("speed-test")
        leaderboard = harness.get_leaderboard("speed-test")
        assert len(leaderboard) == 2
        assert leaderboard[0].agent_id != leaderboard[1].agent_id


class TestTournamentEngine:
    def test_tournament_initialization(self):
        config = TournamentConfig(num_rounds=3)
        engine = TournamentEngine(config)
        assert engine.config.num_rounds == 3

    def test_run_tournament_no_agents(self):
        config = TournamentConfig(num_rounds=2)
        engine = TournamentEngine(config)
        bracket = engine.run_tournament([])
        assert bracket == []

    def test_run_tournament_two_agents(self):
        config = TournamentConfig(num_rounds=1)
        engine = TournamentEngine(config)
        harness = AgentHarness()
        harness.register_agent(AgentProfile(name="Alpha", version="1.0"))
        harness.register_agent(AgentProfile(name="Beta", version="1.0"))
        bracket = engine.run_tournament([harness.agents[0], harness.agents[1]])
        assert len(bracket) >= 1

    def test_match_result_fields(self):
        result = MatchResult(
            agent_a="Alpha:v1",
            agent_b="Beta:v1",
            winner="Alpha:v1",
            scores={"Alpha:v1": 0.8, "Beta:v1": 0.6},
            rounds_played=3,
            duration_sec=1.5,
        )
        assert result.winner == "Alpha:v1"
        assert result.scores["Alpha:v1"] == 0.8

    def test_elo_ranking_after_tournament(self):
        config = TournamentConfig(num_rounds=2)
        engine = TournamentEngine(config)
        harness = AgentHarness()
        harness.register_agent(AgentProfile(name="Champ", version="1.0"))
        harness.register_agent(AgentProfile(name="Challenger", version="1.0"))
        engine.run_tournament(harness.agents)
        rankings = engine.get_rankings()
        assert len(rankings) == 2
        # Rankings should be ordered by elo descending
        for i in range(len(rankings) - 1):
            assert rankings[i].elo >= rankings[i + 1].elo

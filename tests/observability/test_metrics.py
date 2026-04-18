import asyncio
import os

import pytest

from src.observability.metrics import MetricsRegistry, agent_timer, registry, tool_timer


class TestMetricsRegistry:
    def setup_method(self):
        registry.reset()
        # Use a temp file for each test to avoid cross-test contamination
        registry.filename = "test_metrics.jsonl"
        if os.path.exists(registry.filename):
            os.remove(registry.filename)

    def test_record_agent_call(self):
        registry.record_agent_call("Builder", 0.5)
        summary = registry.get_summary()
        assert summary["agents"]["Builder"]["calls_total"] == 1
        assert summary["agents"]["Builder"]["avg_duration_seconds"] == 0.5

    def test_record_agent_error(self):
        try:
            raise ValueError("boom")
        except Exception as e:
            registry.record_agent_call("Critic", 0.1, error=e)
        summary = registry.get_summary()
        assert summary["agents"]["Critic"]["errors_total"] == 1
        assert summary["agents"]["Critic"]["last_error"] == "boom"

    def test_record_tool_call(self):
        registry.record_tool_call("GitHubTool", 1.2)
        summary = registry.get_summary()
        assert summary["tools"]["GitHubTool"]["calls_total"] == 1

    def test_record_tokens(self):
        registry.record_tokens("Ideator", 150)
        registry.record_tokens("Ideator", 50)
        summary = registry.get_summary()
        assert summary["token_usage"]["Ideator"] == 200

    def test_reset(self):
        registry.record_agent_call("Pulse", 0.01)
        registry.reset()
        assert registry.get_summary() == {"agents": {}, "tools": {}, "token_usage": {}}

    def test_persistence(self):
        registry.record_agent_call("Builder", 1.0)
        registry.record_tool_call("GitHubTool", 0.5)
        registry.record_tokens("Ideator", 100)

        # Simulate new process: create fresh registry with same file
        reg2 = MetricsRegistry(filename=registry.filename)
        summary = reg2.get_summary()
        assert summary["agents"]["Builder"]["calls_total"] == 1
        assert summary["tools"]["GitHubTool"]["calls_total"] == 1
        assert summary["token_usage"]["Ideator"] == 100
        reg2.reset()

    def test_persistence_file_removed_on_reset(self):
        registry.record_agent_call("AgentX", 0.1)
        assert os.path.exists(registry.filename)
        registry.reset()
        assert not os.path.exists(registry.filename)


class TestDecorators:
    def setup_method(self):
        registry.reset()

    @pytest.mark.asyncio
    async def test_agent_timer_async(self):
        @agent_timer("TestAgent")
        async def work():
            await asyncio.sleep(0.01)
            return 42

        result = await work()
        assert result == 42
        summary = registry.get_summary()
        assert summary["agents"]["TestAgent"]["calls_total"] == 1
        assert summary["agents"]["TestAgent"]["avg_duration_seconds"] > 0

    def test_agent_timer_sync(self):
        @agent_timer("TestAgentSync")
        def work():
            return 99

        result = work()
        assert result == 99
        summary = registry.get_summary()
        assert summary["agents"]["TestAgentSync"]["calls_total"] == 1

    @pytest.mark.asyncio
    async def test_agent_timer_exception(self):
        @agent_timer("FailingAgent")
        async def work():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            await work()
        summary = registry.get_summary()
        assert summary["agents"]["FailingAgent"]["errors_total"] == 1

    @pytest.mark.asyncio
    async def test_tool_timer_async(self):
        @tool_timer("TestTool")
        async def scrape():
            return "data"

        result = await scrape()
        assert result == "data"
        summary = registry.get_summary()
        assert summary["tools"]["TestTool"]["calls_total"] == 1

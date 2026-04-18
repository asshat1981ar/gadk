import os

from src.observability.adk_callbacks import ObservabilityCallback
from src.observability.metrics import registry


class TestObservabilityCallback:
    def setup_method(self):
        registry.reset()
        if hasattr(registry, "filename") and os.path.exists(registry.filename):
            os.remove(registry.filename)

    def test_records_agent_call(self):
        cb = ObservabilityCallback()
        cb.before_agent("TestAgent", "do something")
        cb.after_agent("TestAgent", "do something", response="ok")
        summary = registry.get_summary()
        assert summary["agents"]["TestAgent"]["calls_total"] == 1

    def test_records_tool_call(self):
        cb = ObservabilityCallback()
        cb.before_tool_call("TestTool", {"arg": 1})
        cb.after_tool_call("TestTool", {"arg": 1}, result="ok", error=None)
        summary = registry.get_summary()
        assert summary["tools"]["TestTool"]["calls_total"] == 1

    def test_records_tool_error(self):
        cb = ObservabilityCallback()
        cb.before_tool_call("BadTool", {})
        try:
            raise ValueError("boom")
        except Exception as e:
            cb.after_tool_call("BadTool", {}, result=None, error=e)
        summary = registry.get_summary()
        assert summary["tools"]["BadTool"]["errors_total"] == 1

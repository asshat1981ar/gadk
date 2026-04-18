from src.capabilities import helpers
from src.cli import swarm_cli


class TestSwarmCliCapabilities:
    def test_get_swarm_status_view_uses_capability_payload(self, monkeypatch):
        captured: dict[str, object] = {}

        async def fake_execute_capability(name: str, **arguments: object) -> dict[str, object]:
            captured["name"] = name
            captured["arguments"] = arguments
            return {
                "status": "success",
                "payload": {
                    "pid": 1234,
                    "shutdown_requested": False,
                    "queue_depth": 2,
                    "total_tasks": 4,
                    "planned": 2,
                    "completed": 1,
                    "stalled": 1,
                    "health": "DEGRADED",
                },
                "error": None,
                "source_backend": "local",
                "retryable": False,
            }

        monkeypatch.setattr(helpers, "execute_capability", fake_execute_capability)

        view = helpers.get_swarm_status_view(
            state_file="test_state.json",
            events_file="test_events.jsonl",
        )

        assert captured == {
            "name": "swarm.status",
            "arguments": {
                "state_file": "test_state.json",
                "events_file": "test_events.jsonl",
            },
        }
        assert view["pid"] == 1234
        assert view["queue_depth"] == 2
        assert view["health"] == "DEGRADED"

    def test_get_swarm_status_view_normalizes_missing_pid(self, monkeypatch):
        async def fake_execute_capability(name: str, **arguments: object) -> dict[str, object]:
            return {
                "status": "success",
                "payload": {
                    "shutdown_requested": True,
                    "queue_depth": 0,
                    "total_tasks": 0,
                    "planned": 0,
                    "completed": 0,
                    "stalled": 0,
                    "health": "HEALTHY",
                },
                "error": None,
                "source_backend": "local",
                "retryable": False,
            }

        monkeypatch.setattr(helpers, "execute_capability", fake_execute_capability)

        view = helpers.get_swarm_status_view()

        assert view["pid"] == "Not running"
        assert view["shutdown_requested"] is True
        assert view["health"] == "HEALTHY"

    def test_status_command_uses_capability_helper(self, capsys, monkeypatch):
        monkeypatch.setattr(
            swarm_cli,
            "get_swarm_status_view",
            lambda state_file=None, events_file=None: {
                "pid": "1234",
                "shutdown_requested": False,
                "queue_depth": 3,
                "total_tasks": 0,
                "planned": 0,
                "completed": 0,
                "stalled": 0,
                "health": "HEALTHY",
            },
        )

        ret = swarm_cli.main(["status"])

        assert ret == 0
        out = capsys.readouterr().out
        assert "1234" in out
        assert "Queue depth:   3" in out
        assert "HEALTHY" in out

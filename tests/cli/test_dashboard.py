import asyncio

import pytest

from src.cli.dashboard import Dashboard
from src.state import StateManager


class TestDashboard:
    def test_dashboard_init(self):
        sm = StateManager(storage_type="memory")
        dashboard = Dashboard(sm, refresh_rate=0.1)
        assert dashboard.state_manager is sm
        assert dashboard.refresh_rate == 0.1
        assert dashboard.running is True
        assert dashboard.paused is False

    def test_dashboard_make_tasks_table(self):
        sm = StateManager(storage_type="memory")
        sm.set_task("t1", {"status": "PLANNED", "source": "Ideator"})
        dashboard = Dashboard(sm)
        table = dashboard._make_tasks_table()
        assert table.title == "Active Tasks"

    def test_dashboard_make_metrics_table(self):
        sm = StateManager(storage_type="memory")
        dashboard = Dashboard(sm)
        table = dashboard._make_metrics_table()
        assert table.title == "Metrics"

    def test_dashboard_handle_input(self):
        sm = StateManager(storage_type="memory")
        dashboard = Dashboard(sm)
        dashboard.handle_input("p")
        assert dashboard.paused is True
        dashboard.handle_input("p")
        assert dashboard.paused is False
        dashboard.handle_input("q")
        assert dashboard.running is False

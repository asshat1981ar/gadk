import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

# Allow running directly from src/cli/ by adding project root to path
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.observability.logger import get_logger
from src.observability.metrics import registry
from src.state import StateManager

logger = get_logger("dashboard")


class Dashboard:
    def __init__(self, state_manager: StateManager, refresh_rate: float = 1.0) -> None:
        self.state_manager = state_manager
        self.refresh_rate = refresh_rate
        self.console = Console()
        self.paused = False
        self.running = True

    def _make_tasks_table(self) -> Table:
        table = Table(title="Active Tasks", expand=True)
        table.add_column("Task ID", style="cyan", no_wrap=True)
        table.add_column("Status", style="magenta")
        table.add_column("Source", style="green")

        tasks = self.state_manager.get_all_tasks()
        for task_id, data in tasks.items():
            status = data.get("status", "UNKNOWN")
            style = {
                "PLANNED": "yellow",
                "PENDING": "blue",
                "COMPLETED": "green",
                "STALLED": "red",
                "FAILED": "red",
            }.get(status, "white")
            table.add_row(
                task_id[:40],
                Text(status, style=style),
                data.get("source", ""),
            )
        return table

    def _make_metrics_table(self) -> Table:
        table = Table(title="Metrics", expand=True)
        table.add_column("Agent / Tool", style="cyan")
        table.add_column("Calls", style="magenta")
        table.add_column("Errors", style="red")
        table.add_column("Avg Duration (s)", style="green")

        summary = registry.get_summary()
        for name, m in summary.get("agents", {}).items():
            table.add_row(
                f"[agent] {name}",
                str(m["calls_total"]),
                str(m["errors_total"]),
                f"{m['avg_duration_seconds']:.3f}",
            )
        for name, m in summary.get("tools", {}).items():
            table.add_row(
                f"[tool] {name}",
                str(m["calls_total"]),
                str(m["errors_total"]),
                f"{m['avg_duration_seconds']:.3f}",
            )
        return table

    def _make_token_panel(self) -> Panel:
        summary = registry.get_summary()
        token_usage = summary.get("token_usage", {})
        total = sum(token_usage.values())
        lines = [f"Total: {total}"]
        for agent, count in token_usage.items():
            lines.append(f"  {agent}: {count}")
        return Panel("\n".join(lines), title="Token Usage")

    def _make_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=8),
        )
        layout["body"].split_row(
            Layout(name="tasks"),
            Layout(name="metrics"),
        )
        layout["footer"].split_row(
            Layout(name="tokens"),
            Layout(name="help"),
        )
        return layout

    def _render(self) -> Group:
        header = Text(
            f"Cognitive Foundry Swarm Dashboard  |  {datetime.now(timezone.utc).isoformat()}  |  {'PAUSED' if self.paused else 'RUNNING'}",
            style="bold white on blue",
            justify="center",
        )
        tasks_table = self._make_tasks_table()
        metrics_table = self._make_metrics_table()
        token_panel = self._make_token_panel()
        help_panel = Panel(
            "[q] Quit  [p] Pause/Resume  [r] Reset Metrics  [i] Inject Command",
            title="Controls",
        )

        layout = self._make_layout()
        layout["header"].update(Panel(header, style="blue"))
        layout["tasks"].update(Panel(tasks_table, title="Tasks"))
        layout["metrics"].update(Panel(metrics_table, title="Metrics"))
        layout["tokens"].update(token_panel)
        layout["help"].update(help_panel)
        return layout

    async def run(self) -> None:
        logger.info("Dashboard starting")
        with Live(self._render(), refresh_per_second=1 / self.refresh_rate, console=self.console) as live:
            while self.running:
                if not self.paused:
                    live.update(self._render())
                await asyncio.sleep(self.refresh_rate)
        logger.info("Dashboard stopped")

    def handle_input(self, key: str) -> None:
        if key == "q":
            self.running = False
        elif key == "p":
            self.paused = not self.paused
            logger.info(f"Dashboard {'paused' if self.paused else 'resumed'}")
        elif key == "r":
            registry.reset()
            logger.info("Metrics reset")
        elif key == "i":
            # In a real implementation this would prompt for a command
            logger.info("Inject command triggered (not yet implemented)")


async def main() -> None:
    state_manager = StateManager()
    dashboard = Dashboard(state_manager)
    await dashboard.run()


if __name__ == "__main__":
    asyncio.run(main())

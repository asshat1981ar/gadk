#!/usr/bin/env python3
"""Unified CLI for interacting with the Cognitive Foundry swarm."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from src.capabilities.helpers import get_swarm_status_view
from src.cli.dashboard import Dashboard
from src.cli.swarm_ctl import (
    QUEUE_PATH,
    SENTINEL_PATH,
    clear_shutdown,
    dequeue_prompts,
    enqueue_prompt,
    get_swarm_pid,
    peek_prompts,
    request_shutdown,
)
from src.observability.logger import configure_logging, get_logger
from src.observability.metrics import registry
from src.state import StateManager

logger = get_logger("swarm_cli")


def _get_state_manager(args):
    kwargs = {}
    if getattr(args, "state_file", None):
        kwargs["filename"] = args.state_file
    if getattr(args, "events_file", None):
        kwargs["event_filename"] = args.events_file
    if kwargs:
        kwargs["storage_type"] = "json"
    return StateManager(**kwargs)


def cmd_status(args):
    status_view = get_swarm_status_view(
        state_file=getattr(args, "state_file", None),
        events_file=getattr(args, "events_file", None),
    )

    print("=== Cognitive Foundry Swarm Status ===")
    print(f"PID:           {status_view.get('pid', 'Not running')}")
    print(f"Shutdown req:  {'Yes' if status_view['shutdown_requested'] else 'No'}")
    print(f"Queue depth:   {status_view['queue_depth']}")
    print(f"Total tasks:   {status_view['total_tasks']}")
    print(f"  Planned:     {status_view['planned']}")
    print(f"  Completed:   {status_view['completed']}")
    print(f"  Stalled:     {status_view['stalled']}")
    print(f"Health:        {status_view['health']}")
    return 0


def cmd_prompt(args):
    message = " ".join(args.message or [])
    if not message:
        print("Error: No prompt message provided.")
        return 1
    enqueue_prompt(message, user_id=args.user or "cli_user")
    print(f"Prompt enqueued: {message[:80]}{'...' if len(message) > 80 else ''}")
    print(f"Queue file: {QUEUE_PATH}")
    return 0


def cmd_stop(args):
    pid = get_swarm_pid()
    if pid:
        print(f"Requesting shutdown for swarm PID {pid}...")
    else:
        print("Requesting swarm shutdown (no PID file found)...")
    request_shutdown()
    print(f"Shutdown sentinel created: {SENTINEL_PATH}")
    print("The swarm will exit on its next loop iteration.")
    return 0


def cmd_tasks(args):
    sm = _get_state_manager(args)
    tasks = sm.get_all_tasks()
    if not tasks:
        print("No tasks found.")
        return 0

    if args.status:
        tasks = {k: v for k, v in tasks.items() if v.get("status") == args.status}

    print(f"{'Task ID':<40} {'Status':<12} {'Source':<15}")
    print("-" * 70)
    for task_id, data in sorted(tasks.items()):
        status = data.get("status", "UNKNOWN")
        source = data.get("source", "")
        print(f"{task_id:<40} {status:<12} {source:<15}")
    return 0


def cmd_logs(args):
    # Structured logs go to stdout by default in our logger.
    # For CLI tailing, we check if there's a log file.
    log_file = args.file
    if log_file and os.path.exists(log_file):
        with open(log_file) as f:
            lines = f.readlines()
        tail = args.tail or len(lines)
        for line in lines[-tail:]:
            print(line.rstrip())
    else:
        print("No log file specified or found. Logs are written to stdout by default.")
        print("To capture logs to a file, run the swarm with:")
        print("  python -m src.main 2>&1 | tee swarm.log")
    return 0


def cmd_metrics(args):
    from src.observability.cost_tracker import CostTracker
    summary = registry.get_summary()
    costs = CostTracker().get_summary()

    print("=== Agent Metrics ===")
    for name, m in summary.get("agents", {}).items():
        print(f"  {name}: calls={m['calls_total']} errors={m['errors_total']} avg_duration={m['avg_duration_seconds']:.3f}s")

    print("=== Tool Metrics ===")
    for name, m in summary.get("tools", {}).items():
        print(f"  {name}: calls={m['calls_total']} errors={m['errors_total']} avg_duration={m['avg_duration_seconds']:.3f}s")

    print("=== Token Usage ===")
    for agent, count in summary.get("token_usage", {}).items():
        print(f"  {agent}: {count}")

    print("=== Cost Summary ===")
    print(f"  Total spend: ${costs['total_spend_usd']:.6f}")
    for agent, cost in costs.get("by_agent", {}).items():
        print(f"  {agent}: ${cost:.6f}")

    if not summary["agents"] and not summary["tools"]:
        print("  (No metrics recorded yet. Metrics are populated at runtime.)")
    return 0


def cmd_events(args):
    sm = _get_state_manager(args)
    if args.task:
        events = sm.get_task_history(args.task)
    else:
        events = sm.get_all_events()

    if not events:
        print("No events found.")
        return 0

    tail = args.tail or len(events)
    events = events[-tail:]

    print(f"{'Timestamp':<28} {'Task ID':<25} {'Agent':<12} {'Action':<8} Details")
    print("-" * 100)
    for evt in events:
        ts = evt.get("timestamp", "")
        task = evt.get("task_id", "")[:24]
        agent = evt.get("agent", "")[:10]
        action = evt.get("action", "")
        diff_keys = ", ".join(evt.get("diff", {}).keys()) if evt.get("diff") else ""
        print(f"{ts:<28} {task:<25} {agent:<12} {action:<8} {diff_keys}")
    return 0


def cmd_dashboard(args):
    sm = _get_state_manager(args)
    dashboard = Dashboard(sm, refresh_rate=args.refresh)
    try:
        asyncio.run(dashboard.run())
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    return 0


def cmd_queue(args):
    entries = peek_prompts()
    if not entries:
        print("Prompt queue is empty.")
        return 0
    print(f"{'Timestamp':<28} {'User':<15} Prompt")
    print("-" * 80)
    for entry in entries:
        ts = entry.get("timestamp", "")
        user = entry.get("user_id", "")
        prompt = entry.get("prompt", "")[:50]
        print(f"{ts:<28} {user:<15} {prompt}")
    return 0


def cmd_prs(args):
    from src.tools.github_tool import GitHubTool
    import asyncio
    gh = GitHubTool()
    prs = asyncio.run(gh.list_pull_requests(state=args.state or "open"))
    if not prs:
        print("No pull requests found.")
        return 0
    print(f"{'#':<6} {'State':<8} {'Head':<25} {'Title':<35} URL")
    print("-" * 90)
    for pr in prs:
        head = pr['head'][:23] if pr['head'] else ""
        title = pr['title'][:33] if pr['title'] else ""
        print(f"{pr['number']:<6} {pr['state']:<8} {head:<25} {title:<35} {pr['url']}")
    return 0


def main(argv=None):
    configure_logging(json_format=False)
    parser = argparse.ArgumentParser(
        prog="swarm",
        description="Interact with the Cognitive Foundry swarm.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Show swarm status")
    p_status.add_argument("--state-file", help="Path to state JSON file")
    p_status.add_argument("--events-file", help="Path to events JSONL file")
    p_status.set_defaults(func=cmd_status)

    # prompt
    p_prompt = subparsers.add_parser("prompt", help="Inject a prompt into the swarm")
    p_prompt.add_argument("message", nargs="*", help="The prompt message to inject")
    p_prompt.add_argument("--user", default="cli_user", help="User ID for the prompt")
    p_prompt.set_defaults(func=cmd_prompt)

    # stop
    p_stop = subparsers.add_parser("stop", help="Request swarm shutdown")
    p_stop.set_defaults(func=cmd_stop)

    # tasks
    p_tasks = subparsers.add_parser("tasks", help="List tasks")
    p_tasks.add_argument("--status", help="Filter by status")
    p_tasks.add_argument("--state-file", help="Path to state JSON file")
    p_tasks.add_argument("--events-file", help="Path to events JSONL file")
    p_tasks.set_defaults(func=cmd_tasks)

    # logs
    p_logs = subparsers.add_parser("logs", help="View logs")
    p_logs.add_argument("--file", help="Log file path")
    p_logs.add_argument("--tail", type=int, default=20, help="Number of lines to show")
    p_logs.set_defaults(func=cmd_logs)

    # metrics
    p_metrics = subparsers.add_parser("metrics", help="Show metrics summary")
    p_metrics.set_defaults(func=cmd_metrics)

    # events
    p_events = subparsers.add_parser("events", help="Show audit events")
    p_events.add_argument("--task", help="Filter by task ID")
    p_events.add_argument("--tail", type=int, default=20, help="Number of events to show")
    p_events.add_argument("--state-file", help="Path to state JSON file")
    p_events.add_argument("--events-file", help="Path to events JSONL file")
    p_events.set_defaults(func=cmd_events)

    # dashboard
    p_dash = subparsers.add_parser("dashboard", help="Launch live dashboard")
    p_dash.add_argument("--refresh", type=float, default=1.0, help="Refresh rate in seconds")
    p_dash.add_argument("--state-file", help="Path to state JSON file")
    p_dash.add_argument("--events-file", help="Path to events JSONL file")
    p_dash.set_defaults(func=cmd_dashboard)

    # queue
    p_queue = subparsers.add_parser("queue", help="Show pending prompts")
    p_queue.set_defaults(func=cmd_queue)

    # prs
    p_prs = subparsers.add_parser("prs", help="List pull requests")
    p_prs.add_argument("--state", choices=["open", "closed", "all"], default="open")
    p_prs.set_defaults(func=cmd_prs)

    # If no args provided, enter interactive mode
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) == 0:
        from src.cli.interactive import run_interactive
        return run_interactive()

    args = parser.parse_args(argv)
    return args.func(args)


import asyncio

if __name__ == "__main__":
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    sys.exit(main())

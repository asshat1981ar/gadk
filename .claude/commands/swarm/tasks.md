---
description: List swarm tasks with optional filtering
argument-hint: [--status STATUS]
allowed-tools: Bash(python3:*)
---

$IF($1,
  List filtered tasks through the CLI task view: !`python3 -m src.cli.swarm_cli tasks --status "$1"`,
  List all tasks through the CLI task view: !`python3 -m src.cli.swarm_cli tasks`
)

Summarize the task list and highlight any stalled or failed tasks that may need attention. This command is CLI-backed; do not invent extra task state outside the command output.

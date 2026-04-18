---
description: Show swarm audit events
argument-hint: [--task TASK_ID] [--tail N]
allowed-tools: Bash(python3:*)
---

$IF($1,
  Show events for task through the CLI event view: !`python3 -m src.cli.swarm_cli events --task "$1" --tail 20`,
  Show recent events through the CLI event view: !`python3 -m src.cli.swarm_cli events --tail 20`
)

Summarize the event stream. Point out any interesting patterns such as:
- Rapid status changes on a single task
- Tasks deleted unexpectedly
- Agents making conflicting updates

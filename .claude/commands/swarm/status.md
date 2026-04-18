---
description: Show Cognitive Foundry swarm status
argument-hint: "[none]"
allowed-tools: Bash(python3:*)
---

Run the capability-backed swarm status command: !`python3 -m src.cli.swarm_cli status`

Summarize:
1. Queue depth, total tasks, and breakdown by status
2. Any stalled tasks called out by the status snapshot
3. Whether a shutdown is requested
4. The swarm PID if running
5. Overall health assessment

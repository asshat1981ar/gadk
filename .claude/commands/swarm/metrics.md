---
description: Show swarm metrics summary
argument-hint: "[none]"
allowed-tools: Bash(python:*)
---

Show current metrics: !`python -m src.cli.swarm_cli metrics`

Interpret the results:
- Highlight any agents or tools with high error rates
- Show average execution durations
- Report token usage if available
- Note if no metrics have been recorded yet (swarm may not have run)

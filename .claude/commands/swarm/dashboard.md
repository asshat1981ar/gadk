---
description: Launch the live swarm dashboard
argument-hint: "[none]"
allowed-tools: Bash(python:*)
---

Launch the live dashboard: !`python -m src.cli.swarm_cli dashboard`

Explain to the user:
- The dashboard shows active tasks, metrics, token usage, and controls in real time
- Press `q` to quit, `p` to pause/resume, `r` to reset metrics
- The dashboard runs until manually stopped

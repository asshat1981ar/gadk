---
description: Inject a prompt into the swarm queue
argument-hint: [prompt-message]
allowed-tools: Bash(python:*)
---

Inject the prompt into the swarm: !`python -m src.cli.swarm_cli prompt "$ARGUMENTS"`

If no arguments were provided, ask the user for the prompt message before proceeding.

Confirm the prompt was enqueued and explain when the swarm will process it (on its next loop iteration if running in AUTONOMOUS_MODE).

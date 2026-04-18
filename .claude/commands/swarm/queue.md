---
description: Show pending prompts in the swarm queue
argument-hint: "[none]"
allowed-tools: Bash(python3:*)
---

Show pending prompts through the CLI queue view: !`python3 -m src.cli.swarm_cli queue`

If the queue is empty, confirm no prompts are waiting.
If prompts are pending, summarize who injected them and when.

---
description: Request shutdown of the Cognitive Foundry swarm
argument-hint: "[none]"
allowed-tools: Bash(python:*)
---

Request swarm shutdown: !`python -m src.cli.swarm_cli stop`

Explain that:
1. A shutdown sentinel file was created
2. The swarm will exit on its next loop iteration (within ~2 seconds if in AUTONOMOUS_MODE)
3. If the swarm is not running in loop mode, the sentinel will be cleared on the next startup

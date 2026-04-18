---
description: View swarm logs
argument-hint: [--file FILE] [--tail N]
allowed-tools: Bash(python:*)
---

Show recent swarm logs. If a log file path is provided, tail it. Otherwise, explain that logs are written to stdout by default and suggest:
!`python -m src.cli.swarm_cli logs --tail 20`

If the user mentions a specific file, use:
!`python -m src.cli.swarm_cli logs --file "$1" --tail 20`

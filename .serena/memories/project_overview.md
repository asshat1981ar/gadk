# GADK Project Overview

## Project Name
GADK — Cognitive Foundry Swarm

## Version
0.1.0

## Purpose
Multi-agent SDLC (Software Development Lifecycle) system built on Google ADK. Agents discover, plan, build, review, and govern work against a target repository (default: `project-chimera`) via GitHub.

## Core Concept
Work items traverse an explicit phase ledger — **PLAN → ARCHITECT → IMPLEMENT → REVIEW → GOVERN → OPERATE** — under pluggable quality gates, with a REVIEW↔IMPLEMENT rework edge for bounded retry. An opt-in self-prompting loop synthesizes gap signals (coverage holes, blocked transitions, stale backlog) into new prompts.

## Agents
| Role | File | Phase |
|---|---|---|
| Orchestrator | `src/agents/orchestrator.py` | routing |
| Ideator | `src/agents/ideator.py` | PLAN |
| Architect | `src/agents/architect.py` | ARCHITECT |
| Builder | `src/agents/builder.py` | IMPLEMENT |
| Critic | `src/agents/critic.py` | REVIEW |
| Governor | `src/agents/governor.py` | GOVERN |
| Pulse | `src/agents/pulse.py` | OPERATE |
| FinOps | `src/agents/finops.py` | OPERATE |

## Target Repository
Default target is `project-chimera` (Android RPG game), but the swarm is designed to work with any GitHub repository.
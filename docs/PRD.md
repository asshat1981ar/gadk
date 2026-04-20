# Product Requirements Document  
## Cognitive Foundry — Autonomous SDLC Platform

**Version:** 1.0  
**Status:** Active  
**Scope:** End-state vision and phased delivery roadmap

---

## 1. Product Vision

Cognitive Foundry is an **autonomous, multi-agent Software Development Lifecycle (SDLC) platform** that accepts a natural-language description of a product idea and delivers a production-ready application through a continuous loop of planning, architecture, implementation, review, governance, and operation — with the human in the loop via a chat or code-editor interface at every key decision point.

### One-line pitch

> _"Describe your app in plain English. Cognitive Foundry designs, builds, tests, and ships it — asking you only the questions that matter."_

---

## 2. Target Users

| Persona | Description |
|---------|-------------|
| **Solo founder** | Non-technical operator with a product idea; wants a working MVP without hiring |
| **Small team** | 1-5 developers who want to accelerate routine SDLC work (boilerplate, reviews, PR triage) |
| **Enterprise devtools team** | Platform engineering group wanting an internal AI pair-programmer integrated into VS Code and CI |
| **Open-source maintainer** | Individual maintaining a complex project; wants automated triage, code review, and release notes |

---

## 3. Core Use Cases

### UC-1: Idea to Application
**Actor:** Solo founder  
**Flow:**
1. User opens the Cognitive Foundry web chat and describes their idea in natural language.
2. Platform asks clarifying questions (target platform, tech stack preference, key features).
3. Orchestrator creates a `WorkItem` at PLAN phase with structured acceptance criteria.
4. Architect generates an ADR-style architecture note and awaits user approval.
5. Builder implements the application in the requested language/framework.
6. Critic reviews, proposes rework if needed (bounded to N retries).
7. Governor runs quality gates and confirms release readiness.
8. Platform creates a GitHub repository, pushes the code, opens a PR, and notifies the user.

### UC-2: Feature Request via Chat
**Actor:** Developer using VS Code  
**Flow:**
1. Developer sends a message in the Cognitive Foundry VS Code sidebar: "Add OAuth2 login to my FastAPI app."
2. Ideator scouts the repo, identifies touch points, creates a structured task.
3. Flow proceeds through ARCHITECT → IMPLEMENT → REVIEW → GOVERN.
4. Developer is pinged for approval before each phase transition that touches production paths.

### UC-3: Continuous Codebase Improvement
**Actor:** Open-source maintainer  
**Flow:**
1. `AUTONOMOUS_MODE=true` is set; self-prompt loop runs on a schedule.
2. Platform scans coverage gaps, stale issues, and dependency drift.
3. Synthesizes prompts → creates tasks → implements fixes.
4. All changes surface as GitHub PRs; maintainer reviews and merges.

### UC-4: Q&A During Implementation
**Actor:** Any user  
**Flow:**
1. User asks "Why did you choose Postgres over SQLite?" during the ARCHITECT phase.
2. Platform streams the Architect agent's reasoning back to the chat UI.
3. User replies "Use SQLite for simplicity". Platform revises the ADR and proceeds.

---

## 4. Functional Requirements

### 4.1 Chat & Editor Interface
- [ ] Web-based chat UI with streaming LLM responses (WebSockets or SSE)
- [ ] VS Code extension sidebar with swarm status, task list, and inline Q&A
- [ ] Message threading: user questions are linked to the active `WorkItem`
- [ ] Approval gates: UI blocks phase advance pending user confirm/deny

### 4.2 Project Management
- [ ] Multi-project support: each user session maps to a `project_id` namespace
- [ ] Project creation wizard: name, description, target language/framework, GitHub repo
- [ ] Task board view: Kanban-style display of `WorkItem` phases and status
- [ ] Full audit trail: every agent action logged with timestamps and evidence

### 4.3 SDLC Pipeline
- [ ] End-to-end PLAN → ARCHITECT → IMPLEMENT → REVIEW → GOVERN → OPERATE loop
- [ ] Bounded rework cycles (currently max 2 REVIEW→IMPLEMENT retries)
- [ ] Quality gates at each phase transition (lint, typecheck, security, coverage, critic)
- [ ] Human-approval gate (optional per phase; configurable per project)
- [ ] Rollback capability: revert a work item to a previous phase

### 4.4 Code Generation
- [ ] Language-agnostic builder (Python, TypeScript/JavaScript, Kotlin, Go at minimum)
- [ ] Framework awareness: FastAPI, Next.js, Android (Kotlin), Spring Boot
- [ ] Test generation: unit tests for every new module
- [ ] Documentation generation: README, API docs, ADR notes
- [ ] Dependency management: detect and resolve conflicts automatically

### 4.5 Integrations
- [ ] GitHub: create repos, branches, commits, PRs, issues (existing)
- [ ] VS Code extension (new)
- [ ] CI/CD: detect existing pipelines; generate `.github/workflows` if absent
- [ ] Smithery marketplace for external tool capabilities (existing)
- [ ] MCP server for IDE/tool integrations (existing, extend)

### 4.6 Observability & Cost
- [ ] Per-project token usage and cost tracking (FinOps agent, existing)
- [ ] Budget caps enforced before expensive LLM calls
- [ ] Structured JSON logs streamed to dashboard
- [ ] Metrics API: task throughput, phase dwell times, review retry rates

---

## 5. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Latency** | First assistant response ≤ 3 s for status queries; streaming for generation |
| **Reliability** | Swarm loop must survive transient LLM failures (planner fallback, tenacity retry) |
| **Security** | No secrets in state files or GitHub issues/PRs; `GitHubTool.sanitize_review` enforced |
| **Auditability** | Every phase transition recorded in `events.jsonl` with agent, evidence, timestamp |
| **Multi-tenancy** | Each `project_id` has isolated state, events, and session data |
| **Extensibility** | New agents follow Architect/Governor pattern; new gates extend `QualityGate` ABC |
| **Testability** | All modules importable without `google-adk` when `TEST_MODE=true` |
| **Cost control** | `BUDGET_USD` enforced by Governor; `EMBED_DAILY_TOKEN_CAP` enforced by EmbedQuota |

---

## 6. Out of Scope (v1)

- Hosting / deployment of the _generated_ application (user manages their own infra)
- Real-time collaborative editing (multiple users on same project simultaneously)
- Non-English natural language input
- Native mobile app for the Cognitive Foundry UI

---

## 7. Success Metrics

| Metric | Target |
|--------|--------|
| Idea-to-PR time (simple CRUD app) | ≤ 10 minutes |
| Review retry rate | ≤ 20 % of tasks require rework |
| User approval required per task | ≤ 2 interactions for routine features |
| Test coverage on generated code | ≥ 65 % |
| BUDGET_USD overrun rate | 0 % (hard gate blocks shipment) |

---

## 8. Phased Delivery Roadmap

### Phase 0 (current) — Infrastructure Stabilisation ✅
- SDLC phase model, quality gates, state management, capability registry
- Planner workaround for ADK/OpenRouter tool-call reliability
- Interactive CLI, MCP server, self-prompt loop

### Phase 1 — Platform Generalisation
- Remove hard-coded `project-chimera` target; full multi-project namespace
- Wire Architect + Governor agents into Orchestrator
- Streaming FastAPI backend with WebSocket chat endpoint
- Session-aware conversation context

### Phase 2 — Chat UI + VS Code Extension
- React/Next.js web chat UI with streaming response rendering
- VS Code extension sidebar: swarm status, task list, inline Q&A
- Human approval gates surfaced in UI

### Phase 3 — Full Code Generation Loop
- Language-agnostic Builder (TypeScript/JS, Python, Kotlin, Go)
- Test generation agent
- CI/CD scaffolding generator

### Phase 4 — Production Hardening
- Multi-tenant isolation (per-project state, events, sessions)
- Full coverage of GOVERN quality gates (security scan, test coverage)
- Cost dashboard
- End-to-end integration tests

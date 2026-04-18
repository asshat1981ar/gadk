# Design Specification: Proactive Hybrid Swarm SDLC ("Cognitive Foundry") - v2 (Google ADK)

**Date:** 2026-04-17
**Status:** Approved
**Framework:** Google Agent Development Kit (ADK)
**Topic:** Multi-agent SDLC with autonomous scraping, self-propagation, and evolutionary feedback loops.

## 1. Executive Summary
The "Cognitive Foundry" v2 is a production-grade multi-agent system built on the **Google Agent Development Kit (ADK)**. It utilizes an event-driven, async-first architecture to orchestrate a swarm of specialized agents. This version shifts from Botpress conventions to a Python-based, modular framework that leverages **Gemini/Vertex AI**, **Playwright** for autonomous data retrieval, and **GitHub Issues** as the primary task orchestration layer.

## 2. Goals & Success Criteria
- **Google ADK Alignment:** Native use of Runners, A2A (Agent-to-Agent) communication, and MCP tools.
- **Autonomous Scavenging:** Agents use Playwright to scrape documentation and technical trends to inform their "Ideation."
- **Structural Propagation:** Agents expand capabilities by writing new ADK Python Agents/Tools to a staged environment.
- **Evolutionary Prompting:** Automatic optimization of system prompts based on task performance and error telemetry.
- **Human-in-the-loop (HITL):** Built-in ADK tool confirmation flows for critical architectural decisions.

## 3. Architecture Overview (Google ADK)

### 3.1 Agent Personas (ADK Agents)
- **The Orchestrator:** An ADK Agent managing the global event loop. Communicates via A2A protocol.
- **The Ideator:** Periodically triggers `Playwright` scavenging tasks to find new features or optimizations. Creates **GitHub Issues** for the swarm.
- **The Scraper (Tool):** A specialized ADK Tool wrapping Playwright for headless browsing and data extraction.
- **The Builder:** Python implementation specialist. Writes new ADK Agent definitions and Tool logic.
- **The Critic:** Performs `agentic-eval` using Gemini-1.5-Pro to validate code in a sandbox.
- **The Archivist:** Manages long-term state via **MCP Agent Memory** and ADK Context.

### 3.2 System Primitives
- **Runners:** Manage async execution of agent reasoning and tool calls.
- **Tools:** Specialized MCP-compatible tools for Filesystem, GitHub, and Playwright.
- **State Table (Coordination):** A high-frequency transactional table for real-time swarm coordination. **GitHub Issues** are used for long-term persistence and human visibility.
- **A2A Protocol:** Standardized message passing between the Orchestrator, Builder, and Critic.
- **Observability:** Built-in OpenTelemetry for tracing self-correction loops.

## 4. Key Workflows

### 4.1 Proactive Scavenging & Ideation
1. **Trigger:** An ADK Cron-based Runner activates the **Ideator**.
2. **Scrape & Sandbox:** Ideator calls the **Scraper (Playwright)**. The Scraper enforces a **Domain Allowlist**, **Max Depth (2)**, and a **Scraper Sandbox** that strips non-essential JavaScript.
3. **Tasking:** Ideator updates the **State Table** for immediate swarm action and creates a **GitHub Issue** for user-facing tracking.

### 4.2 Structural Propagation (The Shadow Source)
1. **Builder** generates a new ADK Agent/Tool in `staged_agents/` (Python).
2. **Critic** triggers an `agentic-eval` loop:
   - Spawns a temporary ADK Runner to execute the new agent in a restricted sandbox.
   - Validates outputs against the original GitHub Issue requirements.
3. **Integration:** Upon success, a "Deployment Tool" merges the code into the active `agents/` directory and updates the **State Table**.

### 4.3 Roadblock & Pivot Protocol
1. If a tool call requires human input (HITL), the Runner raises a `ToolConfirmationRequired` event.
2. The **Orchestrator** updates the **State Table**, creates a detailed **Roadblock Report** in the GitHub Issue, and moves the task to `STALLED`.
3. The system immediately pivots to the next high-priority task in the **State Table**.

### 4.4 Evolutionary Feedback & A/B Testing
1. **Archivist** stores trace data in MCP Memory.
2. **A/B Prompt Testing:** The **Optimizer** proposes a refined prompt and runs it against a benchmark "Test Suite" (ADK Eval framework).
3. The system prompt is only updated if the new version improves the success rate without regressing others.

## 5. Security & Safety
- **Scraper Guardrails:** Use of domain allowlists, recursion depth limits, and `zai.check` to prevent "scraped prompt injection."
- **Sandbox Runtime:** Execution isolation for unverified code.
- **Dependency Guard:** Automated package scanning for newly generated code.
- **Observability (Swarm Pulse):** Automated daily reporting via GitHub and `/status` command.
- **Human Override:** A master kill-switch and a mandatory human-approval mode for "destructive" actions.

## 6. Implementation Phases
1. **Phase 1: Google ADK Scaffolding.** Setup Runners, MCP Tool configuration, and basic A2A messaging.
2. **Phase 2: Task & Scrape Integration.** Connect GitHub Issues and Playwright Scraper tool with guardrails.
3. **Phase 3: Propagation Engine.** Implement the `staged_agents/` logic and Critic sandbox.
4. **Phase 4: Optimization & Pulse.** Integrate evolutionary prompting and Swarm Pulse reporting.

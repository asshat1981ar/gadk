# Design Specification: E2E Mock Foundry Test Suite

**Date:** 2026-04-17
**Status:** Drafting
**Framework:** Pytest + Subprocess (Swarm)
**Goal:** Track commands through the system using mock providers to ensure reliability and parallelism.

## 1. Mock Mode Architecture
A new `TEST_MODE=true` environment flag will be introduced. When active:
*   **MockLiteLlm:** Replaces OpenRouter calls. Returns deterministic tool calls (e.g., `batch_execute`) or responses based on input regex.
*   **Mock Scraper/GitHub:** Tools return static success responses instantly.
*   **Delay Tool:** A specialized test tool that sleeps for $N$ seconds. Used to verify that `batch_execute` runs them concurrently ($Time \approx N$).

## 2. Test Lifecycle (The Runner)
A `pytest` fixture will handle the swarm lifecycle:
1.  **Start:** Spawn `python3 -m src.main` as a subprocess with `AUTONOMOUS_MODE=true` and `TEST_MODE=true`.
2.  **Interact:** Use the `swarm prompt` command to inject a test query.
3.  **Verify:** Poll the `state.json` and `events.jsonl` files to ensure the Orchestrator/Ideator updated them.
4.  **Stop:** Create the shutdown sentinel to stop the swarm gracefully.

## 3. Parallelism Tracking
The test will verify that a batch of 3 "Delay Tools" (each sleeping 1s) completes in under 1.5s total execution time. This confirms the **Multiplexed Dispatcher** is working as intended.

## 4. State Verification
The test will assert:
*   `task_id` exists in `state.json`.
*   Audit log (`events.jsonl`) contains entries for `Orchestrator` -> `Ideator` -> `batch_execute`.
*   A "completed" event is logged after the batch.

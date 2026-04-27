---
name: phases
description: "Skill for the Phases area of app. 12 symbols across 7 files."
---

# Phases

12 symbols | 7 files | Cohesion: 92%

## When to Use

- Working with code in `sdlc-workflow/`
- Understanding how chimeraSprintWorkflow, evaluateValidate, runValidatePhase work
- Modifying phases-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `sdlc-workflow/src/workflows/orchestrator.ts` | startNextSprint, saveRun, chimeraSprintWorkflow |
| `sdlc-workflow/src/workflows/phases/validate.ts` | evaluateValidate, runValidatePhase |
| `sdlc-workflow/src/workflows/phases/implement.ts` | dispatchCiWorkflow, runImplementPhase |
| `sdlc-workflow/src/workflows/phases/implement-agent.ts` | dispatchCiWorkflow, runImplementAgentPhase |
| `sdlc-workflow/src/workflows/phases/release.ts` | runReleasePhase |
| `sdlc-workflow/src/workflows/phases/reflect.ts` | runReflectPhase |
| `sdlc-workflow/src/workflows/phases/gate.ts` | runGatePhase |

## Entry Points

Start here when exploring this area:

- **`chimeraSprintWorkflow`** (Function) — `sdlc-workflow/src/workflows/orchestrator.ts:23`
- **`evaluateValidate`** (Function) — `sdlc-workflow/src/workflows/phases/validate.ts:3`
- **`runValidatePhase`** (Function) — `sdlc-workflow/src/workflows/phases/validate.ts:32`
- **`runReleasePhase`** (Function) — `sdlc-workflow/src/workflows/phases/release.ts:2`
- **`runReflectPhase`** (Function) — `sdlc-workflow/src/workflows/phases/reflect.ts:2`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `chimeraSprintWorkflow` | Function | `sdlc-workflow/src/workflows/orchestrator.ts` | 23 |
| `evaluateValidate` | Function | `sdlc-workflow/src/workflows/phases/validate.ts` | 3 |
| `runValidatePhase` | Function | `sdlc-workflow/src/workflows/phases/validate.ts` | 32 |
| `runReleasePhase` | Function | `sdlc-workflow/src/workflows/phases/release.ts` | 2 |
| `runReflectPhase` | Function | `sdlc-workflow/src/workflows/phases/reflect.ts` | 2 |
| `runImplementPhase` | Function | `sdlc-workflow/src/workflows/phases/implement.ts` | 33 |
| `runImplementAgentPhase` | Function | `sdlc-workflow/src/workflows/phases/implement-agent.ts` | 99 |
| `runGatePhase` | Function | `sdlc-workflow/src/workflows/phases/gate.ts` | 2 |
| `startNextSprint` | Function | `sdlc-workflow/src/workflows/orchestrator.ts` | 10 |
| `saveRun` | Function | `sdlc-workflow/src/workflows/orchestrator.ts` | 16 |
| `dispatchCiWorkflow` | Function | `sdlc-workflow/src/workflows/phases/implement.ts` | 3 |
| `dispatchCiWorkflow` | Function | `sdlc-workflow/src/workflows/phases/implement-agent.ts` | 10 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `ChimeraSprintWorkflow → EncodePath` | cross_community | 5 |
| `ChimeraSprintWorkflow → GhHeaders` | cross_community | 5 |
| `ChimeraSprintWorkflow → DispatchCiWorkflow` | intra_community | 3 |
| `ChimeraSprintWorkflow → DispatchCiWorkflow` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tools | 2 calls |

## How to Explore

1. `gitnexus_context({name: "chimeraSprintWorkflow"})` — see callers and callees
2. `gitnexus_query({query: "phases"})` — find related execution flows
3. Read key files listed above for implementation details

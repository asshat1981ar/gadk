# System/User Skills and Servers Consolidation Design

**Date:** 2026-04-26  
**Status:** Approved design, pending review loop  
**Scope:** User/system-level skills plus user-level servers/extensions/tooling  
**Execution intent:** Full execution after plan approval

## 1. Goal

Improve the user-level skills and servers/extensions environment so it becomes cleaner, easier to operate, and still broad in capability. The work should reduce strong-overlap redundancy, preserve important workflows, and introduce a unified operational surface for server-like tooling without forcing risky hard merges.

## 2. User-approved constraints

- Target covers **both** skills and servers/extensions.
- Optimization target is **balanced**: improve cleanliness, capability, and reliability together.
- Default removal policy is **decisive** when confidence is high.
- High confidence for removal means **strong overlap**: one option clearly supersedes another in quality, scope, maintenance, or fit.
- For servers/extensions, prefer **operational combine** rather than hard internal merges.
- Default execution scope is **full execute** after the plan is approved.
- Parallelism is desired, but no two subagents may write to the same target area at once.

## 3. Problem statement

The current user environment has strong breadth of installed skills and likely multiple user-level server/extension entrypoints. The likely problems are not catastrophic breakage but overlap, ambiguity, maintenance noise, and operational fragmentation. The work should therefore focus on rationalization rather than wholesale replacement.

## 4. Recommended approach

Use a **layered consolidation** approach.

This approach splits the work into coordinated layers that can be researched in parallel and executed in controlled batches:

1. inventory and classify skills
2. inventory and classify user-level servers/extensions
3. identify canonical winners and strong-overlap removal candidates
4. design a unified operational wrapper/manager path for server-like tooling
5. validate winners and rollback paths
6. execute cleanup and consolidation in batches
7. run post-change verification and publish final state

### Why this approach

- It matches the user’s balanced preference better than a purely conservative or aggressive sweep.
- It supports subagent-driven work safely because inventory and analysis can run in parallel.
- It avoids risky internal server merges while still reducing user-facing fragmentation.
- It creates a clean handoff into implementation planning.

## 5. Architecture of the work

### Stream A — Skills inventory and classification
Build a canonical inventory of installed skills across user roots. For each skill, capture source root, category, likely purpose, overlap cluster, health notes, and provisional keep/improve/replace/remove status.

### Stream B — Skills consolidation and enhancement
Apply the decisions from Stream A. Remove strong-overlap losers only after validation. Improve high-value survivors by normalizing metadata where safe, tightening triggers and descriptions, and restructuring oversized reference-heavy skills when useful.

### Stream C — User-level server/extension inventory
Enumerate user-level server-like tooling, extension registrations, wrappers, launchers, config files, and other operational entrypoints. Identify overlap, stale registrations, duplicate control paths, and operational confusion.

### Stream D — Operational combine layer
Design one preferred launcher/manager/control path for server-like tooling. Keep technically distinct components separate internally when necessary, but unify how the user starts, inspects, and reasons about them.

### Stream E — Validation and rollback
Before any destructive change, snapshot the current state, produce manifests for removals or changes, verify that replacements cover intended workflows, and preserve recovery instructions.

## 6. Decision model

### Skills
Each skill should fall into one of four states:

- **Keep** — unique, clearly useful, and not worth changing.
- **Keep + improve** — retained but enhanced through safer metadata/structure improvements.
- **Replace** — superseded by a stronger skill after validation.
- **Group under canonical workflow** — partial overlaps remain, but one primary path is documented for the workflow.

Removal should happen only when another skill clearly supersedes the candidate and preserves effective coverage.

### Servers/extensions
Server-like tooling should default to these actions:

- **Keep separate internally** when roles differ materially.
- **Unify operationally** through one preferred launcher/manager/control path.
- **Retire strong-overlap entrypoints** when one clearly wins.
- **Preserve cheap compatibility shims** where they reduce transition risk.

## 7. Parallel subagent decomposition

### Thread 1 — Skill inventory and overlap analysis
Purpose: enumerate skills, cluster overlap, and propose canonical winners plus removal candidates.

Outputs:
- skill inventory report
- overlap matrix draft

### Thread 2 — Skill enhancement and normalization analysis
Purpose: inspect surviving high-value skills for metadata, trigger, structure, and size improvements.

Outputs:
- enhancement recommendations
- normalization/removal manifest draft

### Thread 3 — User-level server/extension inventory and conflict mapping
Purpose: identify server-like tooling, configs, launch paths, and operational duplication.

Outputs:
- server inventory report
- conflict/combine matrix draft

### Thread 4 — Operational combine architecture
Purpose: define the unified launcher/manager/control surface and compatibility path.

Outputs:
- wrapper/manager design
- preferred operational entrypoint plan

### Thread 5 — Validation and rollback strategy
Purpose: define snapshots, checks, rollback points, and acceptance criteria.

Outputs:
- validation checklist
- rollback procedure
- acceptance criteria

### Merge points
After parallel research threads finish:

1. synthesize canonical skills, removal candidates, combine candidates, and wrapper requirements
2. resolve cross-stream conflicts before destructive work
3. produce a final implementation plan with execution order, write partitions, checkpoints, and success criteria

## 8. Safety rules for parallel work

- Inventory and research threads may run in parallel.
- Recommendation threads may run in parallel only if they write to separate files.
- Destructive changes happen only after synthesis.
- No two subagents may modify the same skill directory, config file, or launcher path at the same time.
- Wrapper/manager implementation should begin only after inventory findings are stable enough to avoid churn.

## 9. Validation strategy

### Pre-change validation
- confirm skill roots and inventory contents
- confirm user-level server/extension config locations
- snapshot anything that may be removed or rewritten
- verify each chosen canonical winner is usable

### In-change validation
- re-check inventory integrity after each removal batch
- verify a skill still parses/loads after metadata normalization
- verify wrapper/manager resolution after each server-side change
- stop destructive phases on the first high-severity failure

### Post-change validation
- confirm duplication is reduced
- confirm workflow coverage is preserved
- confirm the unified operational path works for intended server actions
- confirm rollback instructions are accurate and sufficient

## 10. Error handling rules

### Skills
If a deletion candidate cannot be confidently replaced, downgrade it from remove to keep plus documentation. If a metadata change risks compatibility, preserve the current form and defer the improvement.

### Servers/extensions
If two components only appear overlapping but actually serve distinct runtime roles, keep them internally separate and unify only the operational surface. If the wrapper/manager introduces ambiguity, keep the old entrypoint as a compatibility path until validated.

### Cross-stream conflicts
If one stream’s proposal creates risk for another stream, stop destructive execution and resolve the conflict during synthesis.

## 11. Success criteria

The effort is successful when:

### Skills
- strong-overlap skills are reduced where one clearly supersedes another
- canonical skills are easier to identify
- retained high-value skills are cleaner or better documented
- important workflows retain effective coverage

### Servers/extensions
- user-level server/extension setup is easier to operate
- there is one preferred operational control path
- redundant user-facing entrypoints are reduced
- distinct technical roles remain separated where necessary

### Overall
- the environment is cleaner without becoming fragile
- destructive changes are documented and recoverable
- future maintenance becomes simpler

## 12. Recommended implementation order

1. inventory everything
2. classify overlap and choose canonical winners
3. define removal and combine candidates
4. design the wrapper/manager path
5. validate replacements and rollback procedures
6. execute cleanup and consolidation in controlled batches
7. run post-change verification
8. publish the resulting state and recovery notes

## 13. Planning handoff intent

After this spec passes review and the user approves the written document, the next step is to invoke **writing-plans** and produce a subagent-driven implementation plan that:

- partitions work into non-conflicting streams
- identifies parallel-safe research vs sequential destructive actions
- defines explicit file/target ownership for each thread
- includes validation gates before every removal batch
- supports later full execution if approved

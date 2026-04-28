# System/User Skills and Servers Consolidation Plan

**Date:** 2026-04-26  
**Status:** Approved design, plan written, awaiting execution  
**Parent Design:** `docs/superpowers/specs/2026-04-26-system-user-skills-servers-design.md`

---

## 1. Goal

Clean up and consolidate the user-level skills and MCP server environment to reduce redundancy, improve reliability, and establish a single operational control path for server-like tooling.

---

## 2. Streams

### Stream A — Skills Inventory and Classification

**Owner:** Thread 1  
**Output:** `artifacts/system-user-skills-servers/skills-inventory.md`

1. Enumerate all installed skills across user roots
2. For each: source root, category, purpose, overlap cluster, health notes
3. Provisional status: keep / improve / replace / remove

### Stream B — Skills Enhancement and Normalization

**Owner:** Thread 2  
**Output:** `artifacts/system-user-skills-servers/enhancement-manifest.md`

1. Inspect surviving high-value skills
2. Normalize metadata (triggers, descriptions)
3. Restructure oversized reference-heavy skills
4. Produce removal manifest for strong-overlap candidates

### Stream C — MCP Server Inventory and Conflict Mapping

**Owner:** Thread 3  
**Output:** `artifacts/system-user-skills-servers/server-inventory.md`

1. Enumerate MCP server configs in `~/.hermes/config.yaml`
2. Identify: duplicate control paths, stale registrations, operational confusion
3. Map conflict/combine matrix

### Stream D — Operational Combine Layer

**Owner:** Thread 4  
**Output:** `artifacts/system-user-skills-servers/wrapper-design.md`

1. Define unified launcher/manager for server-like tooling
2. Keep technically distinct components separate internally
3. Unify operational surface (start, inspect, stop)
4. Compatibility path for old entrypoints

### Stream E — Validation and Rollback

**Owner:** Thread 5  
**Output:** `artifacts/system-user-skills-servers/validation-checklist.md`

1. Snapshot current state before destructive changes
2. Define rollback points per stream
3. Acceptance criteria for each consolidation action

---

## 3. Safety Rules

- Inventory threads may run in parallel.
- Destructive changes happen ONLY after synthesis.
- No two subagents modify the same skill directory or config simultaneously.
- Wrapper implementation begins only after inventory findings are stable.

---

## 4. Execution Order

1. Run Streams A-E in parallel (research phase).
2. Synthesize findings → canonical winners, removal candidates, combine plan.
3. Resolve cross-stream conflicts.
4. Produce final implementation plan with write partitions.
5. Execute cleanup in controlled batches.
6. Run post-change verification.
7. Publish final state and recovery notes.

---

## 5. Decision Model

### Skills

| State | Action |
|---|---|
| Unique + useful | Keep |
| Useful but messy | Keep + improve |
| Superseded by another | Replace |
| Partial overlap | Group under canonical workflow |

Removal only when another skill clearly supersedes the candidate.

### MCP Servers

| State | Action |
|---|---|
| Distinct roles | Keep separate internally |
| Overlapping entrypoints | Unify operationally |
| Strong overlap, one wins | Retire redundant entrypoint |
| Transition risk | Preserve compatibility shim |

---

## 6. Validation Gates

### Pre-change
- [ ] Confirm skill roots and inventory contents
- [ ] Confirm MCP server config locations
- [ ] Snapshot anything that may be removed
- [ ] Verify each canonical winner is usable

### In-change
- [ ] Re-check inventory integrity after each removal batch
- [ ] Verify skill still parses/loads after metadata normalization
- [ ] Verify wrapper resolution after each server-side change
- [ ] Stop destructive phases on first high-severity failure

### Post-change
- [ ] Duplication is reduced
- [ ] Workflow coverage is preserved
- [ ] Unified operational path works for intended server actions
- [ ] Rollback instructions are accurate

---

## 7. Success Criteria

- Strong-overlap skills reduced where one clearly supersedes another.
- Canonical skills are easier to identify.
- Retained high-value skills are cleaner or better documented.
- Important workflows retain effective coverage.
- MCP server setup is easier to operate.
- One preferred operational control path exists.
- Redundant user-facing entrypoints are reduced.
- Environment is cleaner without becoming fragile.

---

## 8. Current MCP Server Status (Baseline)

| Server | Command | Status | Notes |
|---|---|---|---|
| brave-search | `npx -y @modelcontextprotocol/server-brave-search` | Works (stdio ok) | Requires BRAVE_API_KEY |
| curl | `npx -y @mcp-get-community/server-curl` | Works (stdio ok) | Not `@modelcontextprotocol/server-curl` |
| docker | `uvx docker-mcp` | Works | 8 tools available |
| fetch | `uvx mcp-fetch` | Works | 5 tools available |
| filesystem | `npx -y @modelcontextprotocol/server-filesystem` | Works (stdio ok) | "failed" display artifact |
| git | `uvx mcp-server-git` | Works | 16 tools available |
| github | `npx -y @modelcontextprotocol/server-github` | Works (stdio ok) | "failed" display artifact |
| memory | `npx -y @modelcontextprotocol/server-memory` | Works (stdio ok) | "failed" display artifact |
| puppeteer | `npx -y @modelcontextprotocol/server-puppeteer` | Works (stdio ok) | Needs Chromium; exits after init |
| sequential_thinking | `npx -y @modelcontextprotocol/server-sequential-thinking` | Works (stdio ok) | "failed" display artifact |
| sqlite | `uvx mcp-server-sqlite` | Works | 5 tools available |
| time | `uvx mcp-server-time` | Works | 3 tools available |
| tree-sitter | `uvx mcp-server-tree-sitter` | Works | Registered project: gadk |

**Note:** Servers marked "failed" in Hermes UI all pass stdio initialization tests. Root cause: Hermes startup timing/connectivity display artifact.

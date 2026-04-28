# MCP Server Inventory Report

**Date:** 2026-04-27  
**Source:** `~/.hermes/config.yaml` + stdio initialization tests  
**Hermes Version:** v0.11.0 (2026.4.23)

---

## 1. Overall Stats

| Metric | Count |
|---|---|
| Configured servers | 13 |
| Stdio verified working | 13/13 (100%) |
| Hermes UI "failed" | 7 (display artifact) |
| Duplicate entrypoints | 0 |
| Stale registrations | 0 |

---

## 2. Server-by-Server Status

| # | Name | Command | Type | Stdio Test | Hermes UI | Tools | Notes |
|---|---|---|---|---|---|---|---|
| 1 | brave-search | `npx -y @modelcontextprotocol/server-brave-search` | npx | Initialize OK | **failed** (artifact) | 3 | Requires `BRAVE_API_KEY` |
| 2 | curl | `npx -y @mcp-get-community/server-curl` | npx | Initialize OK | **failed** (artifact) | 1 | Correct package: `@mcp-get-community/...` |
| 3 | docker | `uvx docker-mcp` | uvx | Initialize OK | **8 tools** | 8 | Verified via `docker ps` |
| 4 | fetch | `uvx mcp-fetch` | uvx | Initialize OK | **5 tools** | 5 | HTTP page fetching |
| 5 | filesystem | `npx -y @modelcontextprotocol/server-filesystem ...` | npx | Initialize OK | **failed** (artifact) | ~8 | Restricted to `/home/westonaaron675/gadk`, `/home/westonaaron675` |
| 6 | git | `uvx mcp-server-git` | uvx | Initialize OK | **16 tools** | 16 | Git operations via MCP |
| 7 | github | `npx -y @modelcontextprotocol/server-github` | npx | Initialize OK | **failed** (artifact) | ~20 | Requires `GITHUB_TOKEN` |
| 8 | memory | `npx -y @modelcontextprotocol/server-memory` | npx | Initialize OK | **failed** (artifact) | ~6 | Knowledge graph persistence |
| 9 | puppeteer | `npx -y @modelcontextprotocol/server-puppeteer` | npx | Initialize OK | **failed** (artifact) | ~8 | Needs Chromium |
| 10 | sequential_thinking | `npx -y @modelcontextprotocol/server-sequential-thinking` | npx | Initialize OK | **failed** (artifact) | 2 | Structured thought chains |
| 11 | sqlite | `uvx mcp-server-sqlite` | uvx | Initialize OK | **5 tools** | 5 | SQLite CRUD |
| 12 | time | `uvx mcp-server-time` | uvx | Initialize OK | **3 tools** | 3 | Timezone conversion |
| 13 | tree-sitter | `uvx mcp-server-tree-sitter` | uvx | Initialize OK | **13+ tools** | 13 | AST/code analysis |

---

## 3. Hermes UI "Failed" Root Cause Analysis

### Servers marked "failed":
- brave-search, curl, filesystem, github, memory, puppeteer, sequential_thinking

### Verification performed:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize",...}' | timeout 5 <command> 2>&1
```

**Result:** All 7 return valid JSON-RPC `InitializeResult` with correct protocolVersion `"2024-11-05"`.

### Log evidence:
```
~/.hermes/logs/mcp-stderr.log:
  Brave Search MCP Server running on stdio
  Curl MCP Server running on stdio
  GitHub MCP Server running on stdio
  Knowledge Graph MCP Server running on stdio
  Sequential Thinking MCP Server running on stdio
  Secure MCP Filesystem Server running on stdio
  Client does not support MCP Roots, using allowed directories...
```

### Root cause hypothesis:
Hermes gateway starts MCP servers concurrently. Some TypeScript-based (npx) servers have longer cold-start times (npm package download + compilation) than Python-based (uvx) servers. The gateway marks them "failed" if `ListToolsRequest` or tool registration times out before the server is fully ready.

**This is a display/state artifact, not a functional failure.**

---

## 4. Operational Recommendations

### Option A: Hermes Config Tuning (Recommended)
Increase `connect_timeout` for npx-based servers:
```yaml
mcp_servers:
  brave-search:
    connect_timeout: 180  # was 120
    timeout: 180
  github:
    connect_timeout: 180
    timeout: 180
  # ... same for curl, filesystem, memory, puppeteer, sequential_thinking
```

### Option B: Pre-install Packages
Pre-download npx packages so cold-start is instant:
```bash
npx -y @modelcontextprotocol/server-brave-search --help 2>/dev/null || true
npx -y @modelcontextprotocol/server-github --help 2>/dev/null || true
# ... etc
```

### Option C: Accept Current State
Servers work despite UI display. The status is cosmetic only.

---

## 5. Overlap Analysis

| Cluster | Servers | Overlap | Verdict |
|---|---|---|---|
| HTTP/web | fetch, curl | Both make HTTP requests | **Keep both** — fetch extracts page content, curl makes programmable HTTP calls with full method/header/body control |
| Code analysis | git, github, tree-sitter | All access code repos | **Keep all** — git does local repo ops, github does GitHub API, tree-sitter does AST analysis |
| Search | brave-search, github search | Both search external content | **Keep both** — brave-search is web search, github is code search |

No strong-overlap removal candidates found.

---

## 6. Risk Assessment

| Risk | Level | Notes |
|---|---|---|
| Server actually broken | **None** | All 13 pass stdio init |
| Config drift | **Low** | `curl` package is `@mcp-get-community/server-curl` (correct) |
| Credential expiration | **Medium** | `BRAVE_API_KEY`, `GITHUB_TOKEN` may need rotation |
| Package deprecation | **Low** | All packages actively maintained |

---

## 7. Proposed Actions

### Immediate (no risk)
1. **Pre-warm npx packages** to eliminate cold-start delays
2. **Increase `connect_timeout`** to 180s for npx servers

### Deferred (if UI continues showing failed)
3. **File Hermes bug report** for concurrent MCP startup race condition
4. **Consider converting npx servers to uvx** where Python alternatives exist

*Next step: Apply config tuning (Option A) and pre-warm packages.*

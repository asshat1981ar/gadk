# Memori Cloud MCP Configuration for All CLIs

This document explains how to wire Memori Cloud to every AI CLI on this system.

## Environment (already set in .env)

```bash
export MEMORI_API_KEY="***"
export MEMORI_ENTITY_ID="westonaaron675@gmail.com"
export MEMORI_PROCESS_ID="gadk-cognitive-foundry"
export MEMORI_BASE_URL="https://api.memorilabs.ai"
```

---

## Hermes

Hermes' MCP config (`~/.hermes/config.yaml`) is stdio-only, so HTTP-native MCP
servers like Memori are not directly supported. Use the Memori Python SDK or
hit the REST API manually from tools.

Workaround: create a local stdio bridge or run Hermes with
`hermes --mcp-url https://api.memorilabs.ai/mcp/` if/when Hermes adds HTTP support.

---

## Claude Code

Project-level `.mcp.json` is already created in `/home/westonaaron675/gadk/.mcp.json`.

Or configure via CLI:

```bash
claude mcp add --transport http memori https://api.memorilabs.ai/mcp/ \
  --header "X-Memori-API-Key: ${MEMORI_API_KEY}" \
  --header "X-Memori-Entity-Id: ${MEMORI_ENTITY_ID}" \
  --header "X-Memori-Process-Id: ${MEMORI_PROCESS_ID}"
```

Verify: `/mcp` inside Claude Code.

---

## OpenAI Codex

`~/.codex/config.toml` is already patched with:

```toml
[mcp_servers.memori]
enabled = true
url = "https://api.memorilabs.ai/mcp/"

[mcp_servers.memori.http_headers]
X-Memori-API-Key = "${MEMORI_API_KEY}"
X-Memori-Entity-Id = "${MEMORI_ENTITY_ID}"
X-Memori-Process-Id = "${MEMORI_PROCESS_ID}"
```

Verify: `codex settings` > MCP Servers.

---

## Copilot CLI

Copilot CLI reads MCP from `--mcp-config` flag or `GITHUB_COPILOT_MCP_CONFIG` env:

```bash
# Create config
cat > ~/.config/copilot/mcp.json << 'EOF'
{
  "mcpServers": {
    "memori": {
      "url": "https://api.memorilabs.ai/mcp/",
      "headers": {
        "X-Memori-API-Key": "${MEMORI_API_KEY}",
        "X-Memori-Entity-Id": "${MEMORI_ENTITY_ID}",
        "X-Memori-Process-Id": "${MEMORI_PROCESS_ID}"
      }
    }
  }
}
EOF

# Use with copilot
github-copilot chat --mcp-config ~/.config/copilot/mcp.json
```

---

## Gemini CLI

Gemini CLI supports MCP servers in `~/.gemini/config.yaml`:

```yaml
mcp:
  servers:
    memori:
      url: "https://api.memorilabs.ai/mcp/"
      headers:
        X-Memori-API-Key: "${MEMORI_API_KEY}"
        X-Memori-Entity-Id: "${MEMORI_ENTITY_ID}"
        X-Memori-Process-Id: "${MEMORI_PROCESS_ID}"
```

---

## OpenCode CLI

OpenCode reads `~/.config/opencode/mcp.json`:

```json
{
  "mcpServers": {
    "memori": {
      "url": "https://api.memorilabs.ai/mcp/",
      "headers": {
        "X-Memori-API-Key": "${MEMORI_API_KEY}",
        "X-Memori-Entity-Id": "${MEMORI_ENTITY_ID}",
        "X-Memori-Process-Id": "${MEMORI_PROCESS_ID}"
      }
    }
  }
}
```

---

## GADK Runtime (built-in Memori client)

```python
from src.services.memori_client import MemoriCloudClient

client = MemoriCloudClient(
    api_key=os.getenv("MEMORI_API_KEY"),
    base_url=os.getenv("MEMORI_BASE_URL"),
)
client.attribution(
    entity_id=os.getenv("MEMORI_ENTITY_ID"),
    process_id=os.getenv("MEMORI_PROCESS_ID"),
)

# Persist memory
client.persist([{"role": "user", "content": "Use TDD"}])

# Recall
facts = client.recall("coding style", limit=5)
```

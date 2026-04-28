# Skills Inventory Report

**Date:** 2026-04-27  
**Source:** `~/.hermes/skills/`  
**Method:** `find + frontmatter extraction + trigger grep`

---

## 1. Overall Stats

| Metric | Count |
|---|---|
| Total SKILL.md files | 84 |
| Category directories | 26 |
| Empty placeholder dirs | 5 |
| Single-skill root dirs | 13 |
| Multi-skill category dirs | 8 |

---

## 2. Full Inventory by Category

### Multi-Skill Categories (8 dirs, 60 skills)

| Category | Skills | Description |
|---|---|---|
| creative | 14 | Visual/design generation: SVG diagrams, ASCII art, pixel art, infographics, Excalidraw, p5.js, web designs, Manim |
| mlops | 13 | Machine learning ops: training, inference, evaluation, model serving, quantization, RAG, audio/image segmentation |
| software-development | 10 | Coding workflows: TDD, debugging, plan-driven development, PR review, code review, subagent orchestration |
| github | 6 | GitHub workflows: auth, PR lifecycle, repo management, issues, code review, codebase inspection |
| autonomous-ai-agents | 6 | CLI coding agents: Claude Code, Codex, OpenCode, Hermes agent, self-refactoring, iterative refactoring |
| research | 5 | Academic research: arXiv, blogwatcher, LLM wiki, polymarket, literature monitoring |
| media | 5 | Media tools: YouTube transcripts, GIF search, song generation, audio features, Spotify |
| apple | 4 | Apple ecosystem: iMessage, Apple Notes, Apple Reminders, Find My | Find My |

### Single-Skill Root Directories (13 dirs, 13 skills)

| Skill | Category | Description |
|---|---|---|
| dogfood | devops | Exploratory web app QA |
| email | communication | Himalaya CLI for IMAP/SMTP |
| gaming | infrastructure | Minecraft modpack servers, Pokemon emulator |
| mcp | protocol | Native MCP client configuration |
| note-taking | productivity | Obsidian vault integration |
| productivity | productivity | Productivity workflows |
| red-teaming | security | LLM jailbreak techniques |
| smart-home | iot | OpenHue Philips Hue control |
| social-media | communication | X/Twitter via xurl CLI |
| tool-orchestration | meta | Automated tool/skill/MCP dispatch |
| yuanbao | communication | Yuanbao group chat |
| feeds | monitoring | **EMPTY placeholder** — DESCRIPTION.md only |
| diagramming | visualization | **EMPTY placeholder** |
| domain | networking | **EMPTY placeholder** |
| gifs | media | **EMPTY placeholder** |
| inference-sh | shell | **EMPTY placeholder** |

---

## 3. Empty Placeholder Dirs (Strong-Overlap Removal Candidates)

These 5 directories contain only `DESCRIPTION.md` with no actual SKILL.md:

| Dir | Size | Action |
|---|---|---|
| `inference-sh/` | 706B | **Remove** — no skills, no clear purpose |
| `gifs/` | 109B | **Remove** — skill exists under `media/gif-search/` already |
| `feeds/` | 115B | **Remove** — skill exists under `research/blogwatcher/` already |
| `domain/` | 1142B | **Remove** — DNS/network domain management, no implementation |
| `diagramming/` | 159B | **Remove** — redundant with `creative/architecture-diagram/` |

---

## 4. Overlap Clusters

### Cluster A: Visual/Diagram Generation (5 skills, creative/)

| Skill | Output | Distinct Value |
|---|---|---|
| architecture-diagram | Dark-themed SVG | Cloud/infra/system diagrams |
| excalidraw | Hand-drawn JSON | Whiteboard-style architecture |
| manim-video | MP4 animations | Math/algorithm education videos |
| p5js | Interactive sketches | Generative art, shaders, 3D |
| popular-web-designs | HTML/CSS pages | Real-world design systems (Stripe, Linear, Vercel clones) |

**Verdict:** NO removal recommended. Each serves a distinct visual use case.

---

### Cluster B: Code Review/PR Workflows (overlap: github vs software-development)

`github/github-code-review` vs `software-development/requesting-code-review`

| Skill | Scope | Backend |
|---|---|---|
| github-code-review | GitHub PR inline comments | gh CLI + REST API |
| requesting-code-review | Pre-commit security scan, quality gates | Local tools (ruff, mypy, bandit) |

**Verdict:** Keep both. One is external GitHub review, one is local pre-commit gates.

---

### Cluster C: Agent Coding Delegation (6 skills, autonomous-ai-agents/)

| Skill | Delegates To | Notes |
|---|---|---|
| claude-code | Claude Code CLI | Requires Claude Code installation |
| codex | OpenAI Codex CLI | API key for Codex |
| opencode | OpenCode CLI | Community coding agent |
| hermes-agent | Hermes agent itself | Meta: Hermes agent setup/config |
| autonomous-self-refactoring | Self (this agent) | Agent refactors its own codebase |
| autonomous-iterative-refactoring | Subagent swarm | Long-running iterative development |

**Verdict:** Keep all 6 — they serve different delegation targets and workflows.

---

### Cluster D: Web/App Server Setup Overlap

`gaming/minecraft-modpack-server` (game servers) vs `devops/webhook-subscriptions` (webhook infra) vs `creative/popular-web-designs` (HTML/CSS pages).

**Verdict:** Keep separate. No real overlap — one is game server hosting, one is webhook infrastructure, one is static design systems.

---

### Cluster E: Media Processing (5 skills, media/)

| Skill | Purpose |
|---|---|
| youtube-content | Transcript extraction, summaries |
| gif-search | Tenor GIF search/download |
| heartmula | Suno-like song generation |
| songsee | Audio spectrograms/features |
| spotify | Spotify playback/playlist management |

**Verdict:** Keep all. Distinct media functions.

---

### Cluster F: Research/Monitoring (5 skills, research/)

| Skill | Purpose |
|---|---|
| arxiv | Paper search by keyword/author/category |
| blogwatcher | RSS/Atom feed monitoring |
| llm-wiki | Karpathy's LLM Wiki markdown KB |
| polymarket | Prediction market queries |
| blogwatcher (feeds/) | **DUPLICATE** — feeds/ placeholder is redundant |

**Verdict:** Remove `feeds/` placeholder (already handled by `research/blogwatcher`).

---

## 5. Provisional Keep/Remove Summary

| Action | Count | Items |
|---|---|---|
| **Keep** | 78 | All 78 existing skills across 21 non-empty dirs |
| **Remove** | 5 | `inference-sh/`, `gifs/`, `feeds/`, `domain/`, `diagramming/` (empty placeholders) |
| **Improve** | 4 | Skills without `trigger` frontmatter should add triggers for better dispatch |
| **Group under canonical** | 2 | `github/github-code-review` + `software-development/requesting-code-review` share concept but different phases |

## 6. Recommended Destructive Actions

1. **Remove** `~/.hermes/skills/inference-sh/` (706B, no skills)
2. **Remove** `~/.hermes/skills/gifs/` (109B, no skills — covered by `media/gif-search`)
3. **Remove** `~/.hermes/skills/feeds/` (115B, no skills — covered by `research/blogwatcher`)
4. **Remove** `~/.hermes/skills/domain/` (1142B, no skills)
5. **Remove** `~/.hermes/skills/diagramming/` (159B, no skills — covered by `creative/architecture-diagram`)

**Risk:** ZERO — these directories contain only `DESCRIPTION.md` files with no SKILL.md, no scripts, no templates, no references. Removal is non-breaking.

## 7. Skill Enhancement Candidates

Skills missing `trigger` frontmatter (14 found) should add it for better `tool-orchestration` dispatch:
- `creative/architecture-diagram`, `creative/excalidraw`, `creative/manim-video`, etc.
- `autonomous-ai-agents/claude-code`, `autonomous-ai-agents/codex`
- `mlops/llama-cpp`, `mlops/serving-llms-vllm`

---

*Next step: Execute destructive removals (5 dirs) or proceed to Stream C (MCP server inventory).*

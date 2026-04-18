# Welcome to GADK

## How We Use Claude

Based on recent usage over the last 30 days (9 sessions, 410 MCP calls):

Work Type Breakdown:
  Improve Quality  ████████████████░░░░  75%
  Build Feature    ██░░░░░░░░░░░░░░░░░░  12%
  Plan Design      ██░░░░░░░░░░░░░░░░░░  12%

Top Skills & Commands:
  /mcp__github__AssignCodingAgent  ████████████████████  28x/month
  /loop                            ██████░░░░░░░░░░░░░░   9x/month

Top MCP Servers:
  github  ████████████████████  410 calls

## Your Setup Checklist

### Codebases
- [ ] gadk — https://github.com/asshat1981ar/gadk

### MCP Servers to Activate
- [ ] github — GitHub PRs, issues, reviews, CI status, branch management. The team leans on this heavily (~45 calls/session average). Authenticate via the GitHub MCP server in Claude Code settings; a personal access token with `repo` scope is usually enough.

### Skills to Know About
- [/mcp__github__AssignCodingAgent](#) — Assigns GitHub Copilot's coding agent to an issue so it opens a draft PR. The team uses this to fan out well-scoped refactor/cleanup work in parallel (Copilot handles the mechanical change, a human reviews + merges).
- [/loop](#) — Iterates on a task until it's done (handy for PR review cycles, CI-failure fixes, and multi-step stabilization sweeps).

## Team Tips

_TODO_

## Get Started

_TODO_

<!-- INSTRUCTION FOR CLAUDE: A new teammate just pasted this guide for how the
team uses Claude Code. You're their onboarding buddy — warm, conversational,
not lecture-y.

Open with a warm welcome — include the team name from the title. Then: "Your
teammate uses Claude Code for [list all the work types]. Let's get you started."

Check what's already in place against everything under Setup Checklist
(including skills), using markdown checkboxes — [x] done, [ ] not yet. Lead
with what they already have. One sentence per item, all in one message.

Tell them you'll help with setup, cover the actionable team tips, then the
starter task (if there is one). Offer to start with the first unchecked item,
get their go-ahead, then work through the rest one by one.

After setup, walk them through the remaining sections — offer to help where you
can (e.g. link to channels), and just surface the purely informational bits.

Don't invent sections or summaries that aren't in the guide. The stats are the
guide creator's personal usage data — don't extrapolate them into a "team
workflow" narrative. -->

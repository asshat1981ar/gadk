#!/usr/bin/env bash
# migrate-pass-1a-v2.sh — Repo hygiene for gadk
#
# Context: project-chimera is a separate remote repo
# (asshat1981ar/project-chimera) that gadk targets via GitHub API.
# The Kotlin tree in gadk/src/ is stale shadow copies with no live
# purpose. This script:
#
#   1. Initializes git (was never a git repo)
#   2. Writes a .gitignore matching gadk's runtime
#   3. Baseline commit — preserves current state including Kotlin shadow
#   4. Deletes the Kotlin/Android shadow from working tree (still in git history)
#   5. Removes stray test files, unused demos
#   6. Renames local.properties → .env.example (preserves keys if any)
#
# Each step is its own commit. If any step goes wrong, you can `git revert`
# that single commit without losing the rest.
#
# Usage:
#   ./migrate-pass-1a-v2.sh --dry-run    # show what would happen
#   ./migrate-pass-1a-v2.sh              # execute

set -euo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; fi

# ───────────────────────────────────────────────────────────────────────────
# Decisions (from chat):
#   Staged Kotlin in src/staged_agents/  → delete
#   run_handoff_demo.py                  → delete
#   local.properties                     → rename to .env.example
# ───────────────────────────────────────────────────────────────────────────

run() {
  echo "  $ $*"
  if [ "$DRY_RUN" = "0" ]; then "$@"; fi
}
section() { echo; echo "═══ $* ═══"; }
commit() {
  if [ "$DRY_RUN" = "0" ] && ! git diff --cached --quiet; then
    run git commit -m "$1"
  fi
}

# ───────────────────────────────────────────────────────────────────────────
section "Step 0 — Preconditions"
# ───────────────────────────────────────────────────────────────────────────

if [ ! -d .git ]; then
  echo "  ℹ No git repo yet — will init in Step 1"
fi

if [ -d .git ] && [ -n "$(git status --porcelain)" ]; then
  echo "✗ Working tree not clean:"
  git status --short
  exit 1
fi

# ───────────────────────────────────────────────────────────────────────────
section "Step 1 — Initialize git"
# ───────────────────────────────────────────────────────────────────────────

if [ ! -d .git ]; then
  run git init
  run git checkout -b main
else
  echo "  ✓ Already a git repo (skipping init)"
fi

# ───────────────────────────────────────────────────────────────────────────
section "Step 2 — Write .gitignore"
# ───────────────────────────────────────────────────────────────────────────

if [ "$DRY_RUN" = "0" ]; then
  cat > .gitignore <<'GITIGNORE_EOF'
# Secrets
.env
.env.local
*.secret
*.pem
*.key

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
.pytest_cache/
*.egg-info/
dist/
build/

# IDE / OS
.vscode/
.idea/
*.swp
.DS_Store

# --- gadk runtime artifacts (churn on every swarm run) ---
sessions.db
swarm.pid
.swarm_shutdown
.swarm_history
prompt_queue.jsonl
state.json.bak
events.jsonl.bak
GITIGNORE_EOF

  # Note: logs/*.log and events.jsonl are NOT ignored — user wants them
  # versioned for effectiveness tracking. If they grow past ~10MB, revisit.
  echo "  ✓ .gitignore written"
else
  echo "  (would write .gitignore)"
fi

run git add .gitignore
commit "chore: add .gitignore for Python + gadk runtime"

# ───────────────────────────────────────────────────────────────────────────
section "Step 3 — Baseline commit (everything, including stale Kotlin shadow)"
# ───────────────────────────────────────────────────────────────────────────

run git add -A
commit "initial commit: gadk Cognitive Foundry baseline

190 files. Python agent framework (Google ADK + custom planner for
elephant-alpha on OpenRouter), 5-agent graph (Orchestrator + Ideator,
Builder, Critic, Pulse, FinOps), file-based control plane, capability
layer, structured observability.

Includes 236-entry events.jsonl and runtime logs as pre-git baseline
for effectiveness tracking.

Also includes stale Kotlin shadow of project-chimera in src/main/java/
which will be removed in the next commit — project-chimera is a
separate remote repo (asshat1981ar/project-chimera), not housed here."

# ───────────────────────────────────────────────────────────────────────────
section "Step 4 — Delete stale Kotlin/Android shadow from working tree"
# ───────────────────────────────────────────────────────────────────────────
# project-chimera lives at its own repo; these are dead local copies.

# Top-level Kotlin/Gradle files at src/
for f in src/AndroidManifest.xml src/build.gradle.kts src/settings.gradle.kts \
         src/GameScreen.kt src/GameViewport.kt src/MainActivity.kt; do
  [ -e "$f" ] && run git rm "$f"
done

# Entire src/main/ Android tree
if [ -d src/main ]; then
  run git rm -r src/main
fi

# Kotlin staged_agents outputs (per decision: delete)
for f in src/staged_agents/*.kt src/staged_agents/*.xml src/staged_agents/build.gradle.kts; do
  [ -e "$f" ] && run git rm "$f"
done

commit "refactor: remove stale Kotlin/Android shadow from gadk

project-chimera lives in its own remote repo (asshat1981ar/project-chimera).
gadk targets it via GitHub API (read_repo_file, create_pull_request).
The local Kotlin tree under src/ was orphaned shadow with no live
consumers — deleting makes the architecture legible.

Removed:
  src/{AndroidManifest,build.gradle,settings.gradle,GameScreen,GameViewport,MainActivity}.*
  src/main/                                         (full Kotlin source root)
  src/staged_agents/*.{kt,xml}                      (dead Builder outputs)
  src/staged_agents/build.gradle.kts

If ever needed, recover from git history: git log --all -- src/main/"

# ───────────────────────────────────────────────────────────────────────────
section "Step 5 — Clean stray test files"
# ───────────────────────────────────────────────────────────────────────────

[ -f src/test_cicd.py ] && run git rm src/test_cicd.py
if [ -f test_llm.py ]; then
  run mkdir -p tests
  run git mv test_llm.py tests/test_llm.py
fi

commit "chore: consolidate stray tests under tests/

- Remove src/test_cicd.py (3-line stub picked up by bare pytest)
- Move test_llm.py from repo root to tests/ for consistent discovery"

# ───────────────────────────────────────────────────────────────────────────
section "Step 6 — Delete unused demo"
# ───────────────────────────────────────────────────────────────────────────

[ -f run_handoff_demo.py ] && run git rm run_handoff_demo.py
commit "chore: remove unused run_handoff_demo.py"

# ───────────────────────────────────────────────────────────────────────────
section "Step 7 — local.properties → .env.example"
# ───────────────────────────────────────────────────────────────────────────

if [ -f local.properties ]; then
  # Handle the case where .env.example already exists (it's empty in this repo)
  if [ -f .env.example ]; then
    run git rm .env.example
  fi
  run git mv local.properties .env.example
  commit "chore: rename local.properties → .env.example

File contained \${{ secrets.X }} placeholders (GitHub Actions style),
not Android SDK paths. Rename reflects actual purpose. GEMINI_API_KEY
and GROQ_API_KEY are not currently referenced in code — kept for now
in case future model diversification uses them."
fi

# ───────────────────────────────────────────────────────────────────────────
section "Step 8 — Update .github/copilot-instructions.md"
# ───────────────────────────────────────────────────────────────────────────

if [ -f .github/copilot-instructions.md ] && [ "$DRY_RUN" = "0" ]; then
  # Update the one section that described the mixed tree
  python3 - <<'PY_EOF'
from pathlib import Path
p = Path(".github/copilot-instructions.md")
text = p.read_text()

# Replace the outdated "mixed Python+Kotlin" architecture line with a
# clear statement of the now-clean reality.
old = (
    "This repo is primarily a Python \"Cognitive Foundry\" swarm built on Google ADK, "
    "with a separate Kotlin/Gradle game subtree living under the same top-level `src/` directory. "
    "Treat `src/` as mixed-purpose: Python runtime modules sit directly under `src/*.py`, "
    "while the game code lives under `src/main/java/com/chimera/rpg/...`."
)
new = (
    "This repo is a Python \"Cognitive Foundry\" swarm built on Google ADK. "
    "It targets a separate Kotlin/Android game repo (`asshat1981ar/project-chimera`) "
    "remotely via the GitHub API — see `src/tools/github_tool.py`. "
    "`src/` is Python-only: runtime modules, agents, tools, observability, CLI."
)

if old in text:
    text = text.replace(old, new)
    p.write_text(text)
    print("  ✓ Updated copilot-instructions.md")
else:
    print("  (copilot-instructions.md didn't match expected text — update manually)")
PY_EOF

  run git add .github/copilot-instructions.md
  commit "docs: clarify gadk is Python-only, project-chimera is remote"
fi

# ───────────────────────────────────────────────────────────────────────────
section "Pass 1a complete"
# ───────────────────────────────────────────────────────────────────────────

if [ "$DRY_RUN" = "1" ]; then
  echo "  (dry run — no changes made)"
  echo
  echo "Re-run without --dry-run to execute."
else
  echo "  Commits on main:"
  git log --oneline | sed 's/^/    /'
  echo
  echo "Verify:"
  echo "  python3 -m pytest tests -q"
  echo "  grep -rn 'src/main/java\\|src/AndroidManifest' src/ --include='*.py' || echo 'clean'"
  echo
  echo "Next (not done by this script):"
  echo "  - src/tools/filesystem.py has _WRITE_ALLOWED_DIRS = ['src','tests','docs','staged_agents']"
  echo "    Keep staged_agents/ (it's where Builder stages Python tools for gadk itself now)"
  echo "  - Pass 1b: consolidate 5 __main__ entry points into one foundry CLI"
fi

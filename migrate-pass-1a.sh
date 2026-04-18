#!/usr/bin/env bash
# migrate-pass-1a.sh — Repo hygiene: separate Kotlin chimera-rpg from Python gadk
#
# What this does:
#   1. Branches off current HEAD
#   2. Moves all Kotlin/Android files into chimera-rpg/ sibling dir (preserves git history)
#   3. Moves generated Kotlin artifacts from src/staged_agents/ into chimera-rpg/staging/
#   4. Removes stray test files (src/test_cicd.py, relocates test_llm.py → tests/)
#   5. Commits in logical chunks so each step is individually revertable
#
# Usage:
#   ./migrate-pass-1a.sh --dry-run    # show what would happen, change nothing
#   ./migrate-pass-1a.sh              # do it
#
# Answer these decisions inline by editing the DECISION_* flags below before running.

set -euo pipefail

# ───────────────────────────────────────────────────────────────────────────
# Decisions (edit these based on your answers from chat)
# ───────────────────────────────────────────────────────────────────────────
DECISION_STAGED_KT="move"        # move | delete | keep
DECISION_HANDOFF_DEMO="delete"     # delete | move_to_examples | keep
DECISION_LOCAL_PROPERTIES="env"  # env (rename to .env.example) | keep | example (local.properties.example)

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; fi

run() {
  echo "  $ $*"
  if [ "$DRY_RUN" = "0" ]; then "$@"; fi
}

section() {
  echo
  echo "═══ $* ═══"
}

# ───────────────────────────────────────────────────────────────────────────
# Preconditions
# ───────────────────────────────────────────────────────────────────────────
section "Preconditions"

[ -d .git ] || { echo "✗ Not a git repository"; exit 1; }
echo "  ✓ Git repo"

if [ -n "$(git status --porcelain)" ]; then
  echo "✗ Working tree not clean. Commit or stash first:"
  git status --short
  exit 1
fi
echo "  ✓ Working tree clean"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "  ✓ Current branch: $CURRENT_BRANCH"

if git rev-parse --verify refactor/pass-1a-repo-hygiene >/dev/null 2>&1; then
  echo "✗ Branch refactor/pass-1a-repo-hygiene already exists. Delete it first:"
  echo "    git branch -D refactor/pass-1a-repo-hygiene"
  exit 1
fi

# ───────────────────────────────────────────────────────────────────────────
# Create working branch
# ───────────────────────────────────────────────────────────────────────────
section "Create branch refactor/pass-1a-repo-hygiene"
run git checkout -b refactor/pass-1a-repo-hygiene

# ───────────────────────────────────────────────────────────────────────────
# Step 1: Create chimera-rpg/ sibling dir layout
# ───────────────────────────────────────────────────────────────────────────
section "Step 1 — Scaffold chimera-rpg/"
run mkdir -p chimera-rpg/app/src/main/java
run mkdir -p chimera-rpg/staging

# ───────────────────────────────────────────────────────────────────────────
# Step 2: Move core Kotlin/Android files
# ───────────────────────────────────────────────────────────────────────────
section "Step 2 — Move Kotlin/Android tree"

# Top-level Kotlin/Gradle files in src/
for f in AndroidManifest.xml build.gradle.kts settings.gradle.kts \
         GameScreen.kt GameViewport.kt MainActivity.kt; do
  if [ -e "src/$f" ]; then
    run git mv "src/$f" "chimera-rpg/$f"
  fi
done

# src/main/ Android tree (if it exists — Kotlin source root)
if [ -d src/main/java ]; then
  run git mv src/main/java chimera-rpg/app/src/main/java
fi
if [ -f src/main/AndroidManifest.xml ]; then
  run git mv src/main/AndroidManifest.xml chimera-rpg/app/src/main/AndroidManifest.xml
fi
# Remove now-empty src/main/ if it exists
if [ -d src/main ] && [ -z "$(ls -A src/main 2>/dev/null)" ]; then
  run rmdir src/main
fi

if [ "$DRY_RUN" = "0" ] && ! git diff --cached --quiet; then
  run git commit -m "refactor: move Kotlin/Android tree to chimera-rpg/

Part of Pass 1a repo hygiene. Kotlin game code split into
chimera-rpg/ sibling directory to separate from Python agent
runtime. Prepares for eventual two-repo split (Pass 1c)."
fi

# ───────────────────────────────────────────────────────────────────────────
# Step 3: Handle staged_agents/ Kotlin outputs per decision
# ───────────────────────────────────────────────────────────────────────────
section "Step 3 — Handle src/staged_agents/*.kt"

case "$DECISION_STAGED_KT" in
  move)
    moved=0
    for f in src/staged_agents/*.kt src/staged_agents/*.xml src/staged_agents/build.gradle.kts; do
      [ -e "$f" ] || continue
      run git mv "$f" "chimera-rpg/staging/$(basename "$f")"
      moved=$((moved+1))
    done
    if [ "$moved" -gt 0 ] && [ "$DRY_RUN" = "0" ]; then
      run git commit -m "refactor: move staged Kotlin artifacts to chimera-rpg/staging/

Builder-generated Kotlin files were targeting chimera-rpg;
move them to the chimera-rpg tree where they belong."
    fi
    ;;
  delete)
    for f in src/staged_agents/*.kt src/staged_agents/*.xml; do
      [ -e "$f" ] || continue
      run git rm "$f"
    done
    if [ "$DRY_RUN" = "0" ] && ! git diff --cached --quiet; then
      run git commit -m "chore: remove orphaned staged Kotlin artifacts"
    fi
    ;;
  keep)
    echo "  (keeping staged Kotlin files in src/staged_agents/ per decision)"
    ;;
esac

# ───────────────────────────────────────────────────────────────────────────
# Step 4: Stray test files
# ───────────────────────────────────────────────────────────────────────────
section "Step 4 — Clean stray test files"

if [ -f src/test_cicd.py ]; then
  run git rm src/test_cicd.py
fi

if [ -f test_llm.py ]; then
  run git mv test_llm.py tests/test_llm.py
fi

if [ "$DRY_RUN" = "0" ] && ! git diff --cached --quiet; then
  run git commit -m "chore: consolidate stray tests under tests/

- Remove src/test_cicd.py (3-line stub, picked up by bare pytest)
- Move test_llm.py from repo root into tests/ for consistent discovery"
fi

# ───────────────────────────────────────────────────────────────────────────
# Step 5: Handle run_handoff_demo.py per decision
# ───────────────────────────────────────────────────────────────────────────
section "Step 5 — Handle run_handoff_demo.py"

case "$DECISION_HANDOFF_DEMO" in
  delete)
    if [ -f run_handoff_demo.py ]; then
      run git rm run_handoff_demo.py
      if [ "$DRY_RUN" = "0" ]; then
        run git commit -m "chore: remove unused run_handoff_demo.py"
      fi
    fi
    ;;
  move_to_examples)
    if [ -f run_handoff_demo.py ]; then
      run mkdir -p examples
      run git mv run_handoff_demo.py examples/handoff_demo.py
      if [ "$DRY_RUN" = "0" ]; then
        run git commit -m "chore: move handoff demo to examples/"
      fi
    fi
    ;;
  keep)
    echo "  (keeping run_handoff_demo.py at repo root per decision)"
    ;;
esac

# ───────────────────────────────────────────────────────────────────────────
# Step 6: Handle local.properties per decision
# ───────────────────────────────────────────────────────────────────────────
section "Step 6 — Handle local.properties"

case "$DECISION_LOCAL_PROPERTIES" in
  env)
    if [ -f local.properties ]; then
      # Check if .env.example already exists — if so, we'd need to merge, not overwrite
      if [ -f .env.example ]; then
        echo "  ⚠ .env.example already exists. Skipping rename — merge manually:"
        echo "    diff local.properties .env.example"
        echo "    # then: git rm local.properties"
      else
        run git mv local.properties .env.example
        if [ "$DRY_RUN" = "0" ]; then
          run git commit -m "chore: rename local.properties → .env.example

File contains \${{ secrets.X }} placeholders, not Android SDK paths;
rename to reflect actual purpose."
        fi
      fi
    fi
    ;;
  example)
    if [ -f local.properties ]; then
      run git mv local.properties local.properties.example
      if [ "$DRY_RUN" = "0" ]; then
        run git commit -m "chore: rename local.properties → local.properties.example"
      fi
    fi
    ;;
  keep)
    echo "  (keeping local.properties as-is per decision)"
    ;;
esac

# ───────────────────────────────────────────────────────────────────────────
# Step 7: Add a minimal chimera-rpg README to anchor the new dir
# ───────────────────────────────────────────────────────────────────────────
section "Step 7 — Anchor chimera-rpg/ with README"

if [ "$DRY_RUN" = "0" ] && [ ! -f chimera-rpg/README.md ]; then
  cat > chimera-rpg/README.md <<'EOF'
# chimera-rpg

Android RPG (Jetpack Compose + Canvas). Built autonomously by the gadk
Cognitive Foundry swarm.

This directory will be extracted into its own repository in Pass 1c.
Until then, it lives as a sibling directory to `src/` so gadk's
autonomous SDLC pipeline (`src/android_rpg_sdlc.py`) can write here
without network hops.

## Layout

- `staging/` — Builder-agent outputs awaiting review
- `app/src/main/java/` — integrated game source
- `build.gradle.kts`, `settings.gradle.kts` — Gradle config

## Build

Standard Android build (once extracted):

```
./gradlew assembleDebug
```
EOF
  run git add chimera-rpg/README.md
  run git commit -m "docs: anchor chimera-rpg/ with README"
fi

# ───────────────────────────────────────────────────────────────────────────
# Done
# ───────────────────────────────────────────────────────────────────────────
section "Pass 1a migration complete"

if [ "$DRY_RUN" = "1" ]; then
  echo "  (dry run — no changes made)"
  echo
  echo "Re-run without --dry-run to execute."
else
  echo "  Branch: refactor/pass-1a-repo-hygiene"
  echo "  Commits:"
  git log --oneline "$CURRENT_BRANCH..HEAD" 2>/dev/null | sed 's/^/    /'
  echo
  echo "Next (not done by this script — requires code review):"
  echo "  1. Update src/android_rpg_sdlc.py to write to chimera-rpg/staging/"
  echo "     (currently writes to src/staged_agents/)"
  echo "  2. Update .github/copilot-instructions.md to reflect new layout"
  echo "  3. Run tests: python3 -m pytest tests -q"
  echo "  4. Run lint/type check if configured"
  echo "  5. If green: git checkout main && git merge refactor/pass-1a-repo-hygiene"
fi

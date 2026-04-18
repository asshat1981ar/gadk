"""Android RPG — Full autonomous SDLC from zero to playable game.

Builds an Android RPG using Jetpack Compose + Canvas graphics:
  1. Project scaffolding (build.gradle, Manifest, resources)
  2. Core engine (game loop, state management)
  3. Graphics (Compose Canvas tile renderer, sprites)
  4. World (procedural map, tiles, collision)
  5. Entities (player, NPCs, enemies with stats)
  6. Combat (turn-based with animations)
  7. UI (HUD, inventory, dialogue boxes)
  8. Audio (sound effects placeholder)
  9. Save/load (DataStore serialization)
 10. Polish (splash screen, main menu)

Each component is built → reviewed → committed → PR'd in sequence.
"""

import asyncio
import os
import time

from src.config import Config
from src.observability.logger import configure_logging, get_logger, set_session_id, set_trace_id
from src.observability.metrics import registry
from src.planner import run_planner
from src.state import StateManager
from src.tools.dispatcher import register_tool
from src.tools.filesystem import read_file, write_file, list_directory
from src.tools.github_tool import read_repo_file, list_repo_contents, GitHubTool
from src.tools.content_guards import is_low_value_content
from src.tools.web_search import search_web

register_tool("search_web", search_web)
register_tool("read_file", read_file)
register_tool("write_file", write_file)
register_tool("list_directory", list_directory)
register_tool("read_repo_file", read_repo_file)
register_tool("list_repo_contents", list_repo_contents)

configure_logging(level=os.getenv("LOG_LEVEL", "INFO").upper(), json_format=False)
logger = get_logger("android_rpg")

REPO = Config.REPO_NAME or "asshat1981ar/project-chimera"
BRANCH_PREFIX = "rpg"

# Predefined RPG component pipeline — builds in order with dependencies
RPG_PIPELINE = [
    {
        "id": "scaffold",
        "title": "Android RPG Project Scaffold",
        "priority": "HIGH",
        "description": "Initialize Android project with build.gradle.kts, manifest, and Compose dependencies",
        "files": ["build.gradle.kts", "settings.gradle.kts", "AndroidManifest.xml"],
    },
    {
        "id": "core-engine",
        "title": "RPG Core Game Engine",
        "priority": "HIGH",
        "description": "Game loop, state machine, FPS counter, and main thread handler",
        "files": ["app/src/main/java/com/chimera/rpg/core/GameEngine.kt"],
    },
    {
        "id": "graphics",
        "title": "Compose Canvas Graphics Renderer",
        "priority": "HIGH",
        "description": "Tile-based sprite renderer using Jetpack Compose Canvas with bitmap caching",
        "files": ["app/src/main/java/com/chimera/rpg/graphics/TileRenderer.kt", "app/src/main/java/com/chimera/rpg/graphics/SpriteSheet.kt"],
    },
    {
        "id": "world",
        "title": "Procedural World Map System",
        "priority": "HIGH",
        "description": "2D tile map with procedural generation, collision detection, and camera follow",
        "files": ["app/src/main/java/com/chimera/rpg/world/WorldMap.kt", "app/src/main/java/com/chimera/rpg/world/Tile.kt"],
    },
    {
        "id": "entities",
        "title": "Entity System — Player, NPCs, Enemies",
        "priority": "HIGH",
        "description": "Entity component system with stats (HP, MP, STR, AGI, INT), animations, and AI",
        "files": ["app/src/main/java/com/chimera/rpg/entity/Entity.kt", "app/src/main/java/com/chimera/rpg/entity/Player.kt", "app/src/main/java/com/chimera/rpg/entity/NPC.kt"],
    },
    {
        "id": "combat",
        "title": "Turn-Based Combat System",
        "priority": "HIGH",
        "description": "Combat manager with attack, defend, spell, item actions and turn queue",
        "files": ["app/src/main/java/com/chimera/rpg/combat/CombatSystem.kt", "app/src/main/java/com/chimera/rpg/combat/CombatAction.kt"],
    },
    {
        "id": "ui",
        "title": "RPG UI — HUD, Inventory, Dialogue",
        "priority": "MEDIUM",
        "description": "Compose UI overlays: health/mana bars, inventory grid, dialogue boxes, quest log",
        "files": ["app/src/main/java/com/chimera/rpg/ui/HUD.kt", "app/src/main/java/com/chimera/rpg/ui/InventoryUI.kt", "app/src/main/java/com/chimera/rpg/ui/DialogueBox.kt"],
    },
    {
        "id": "save",
        "title": "Save/Load Game State",
        "priority": "MEDIUM",
        "description": "DataStore-based serialization for player progress, world state, and settings",
        "files": ["app/src/main/java/com/chimera/rpg/save/SaveManager.kt", "app/src/main/java/com/chimera/rpg/save/GameState.kt"],
    },
    {
        "id": "main",
        "title": "MainActivity + Navigation + Polish",
        "priority": "MEDIUM",
        "description": "MainActivity with Compose setContent, splash screen, main menu, settings screen",
        "files": ["app/src/main/java/com/chimera/rpg/MainActivity.kt", "app/src/main/java/com/chimera/rpg/ui/MainMenu.kt"],
    },
]


class AndroidRPGBuilder:
    def __init__(self):
        self.sm = StateManager()
        self.gh = GitHubTool()
        self.completed = 0
        self.failed = 0

    async def _build_component(self, spec: dict) -> str | None:
        """Build one RPG component and return artifact path."""
        cid = spec["id"]
        logger.info(f"=== BUILDING: {spec['title']} ===")
        self.sm.set_task(f"rpg-{cid}", {"status": "IN_PROGRESS", **spec}, agent="Builder")

        # Gather context from previously built components
        context = ""
        if cid != "scaffold":
            try:
                # Read previous main files for continuity
                prev = read_file("src/staged_agents/MainActivity.kt") if os.path.exists("src/staged_agents/MainActivity.kt") else ""
                context = f"Previously built context:\n{prev[:600]}\n\n"
            except Exception:
                pass

        builder_prompt = (
            f"Build Android RPG component: {spec['title']}\n\n"
            f"Description: {spec['description']}\n"
            f"Target files: {', '.join(spec['files'])}\n\n"
            f"{context}"
            "CRITICAL RULES:\n"
            "1. Write PURE KOTLIN code (.kt files only)\n"
            "2. Use Jetpack Compose for ALL UI and graphics\n"
            "3. Use Canvas API for 2D rendering (drawRect, drawCircle, drawImage)\n"
            "4. Package: com.chimera.rpg or subpackages\n"
            "5. Include KDoc, @Preview composables where applicable\n"
            "6. Make it COMPILE — correct imports, no placeholders\n\n"
            "Write each file using write_file with paths starting with 'src/staged_agents/'.\n"
            "For example: 'src/staged_agents/build.gradle.kts' instead of just 'build.gradle.kts'.\n"
            "Then say DONE: <summary>"
        )
        builder_system = (
            "You are a senior Android Kotlin developer building a Jetpack Compose RPG. "
            "You write production-grade Kotlin. NEVER Python. ALWAYS .kt extension. "
            "DO NOT read files. Write all requested files and say DONE."
        )

        build_start = time.time()
        result = await run_planner(
            user_prompt=builder_prompt,
            system_prompt=builder_system,
            max_iterations=10,
            allowed_tools={"write_file"},
            model=Config.OPENROUTER_TOOL_MODEL,
        )

        # Wait briefly for any async file writes
        await asyncio.sleep(1.0)
        
        # Check for newly written files in the staged directory
        staged_dir = "src/staged_agents"
        os.makedirs(staged_dir, exist_ok=True)
        staged = [f for f in os.listdir(staged_dir)
                  if os.path.getmtime(os.path.join(staged_dir, f)) > build_start - 2]

        if staged:
            logger.info(f"Built {len(staged)} files for {cid}: {staged}")
            # Prioritize .kt files if multiple are present
            kt_files = [f for f in staged if f.endswith(".kt")]
            if kt_files:
                return kt_files[0]
            # Next, prioritize files specified in the spec
            for f in staged:
                if f in spec["files"]:
                    return f
            return staged[0]

        # Post-process code blocks
        import re
        blocks = re.findall(r"```kotlin\n(.*?)\n```", result, re.DOTALL)
        if blocks:
            fname = f"rpg_{cid}.kt"
            fpath = f"src/staged_agents/{fname}"
            write_file(fpath, blocks[0])
            logger.info(f"Post-processed → {fpath}")
            return fpath

        logger.warning(f"No artifact for {cid}")
        self.sm.set_task(f"rpg-{cid}", {"status": "FAILED"}, agent="Builder")
        return None

    async def _review(self, artifact: str, spec: dict) -> str:
        """Critic reviews the component."""
        code = read_file(f"src/staged_agents/{artifact}") if os.path.exists(f"src/staged_agents/{artifact}") else ""
        prompt = (
            f"Review this Kotlin RPG component: {spec['title']}\n\n"
            f"```kotlin\n{code[:2000]}\n```\n\n"
            "Check: correctness, Compose best practices, performance, missing imports."
        )
        review = await run_planner(
            user_prompt=prompt,
            system_prompt="You are a code reviewer for Android Kotlin games.",
            max_iterations=3,
            model=Config.OPENROUTER_TOOL_MODEL,
        )
        return review

    async def _deliver(self, artifact: str, spec: dict, review: str):
        """Push to GitHub branch and open PR."""
        cid = spec["id"]
        branch = f"{BRANCH_PREFIX}/{cid}-{int(time.time())}"
        code = read_file(f"src/staged_agents/{artifact}") if os.path.exists(f"src/staged_agents/{artifact}") else ""

        # Empty-content guard: don't commit+PR a stub. This prevents the
        # "Turn-Based Combat System" case where the RPG engine generated an
        # empty .kt file and the PR body was literally "the code snippet is
        # empty. Let me first check if there are any files..."
        if is_low_value_content(code):
            logger.warning(
                "_deliver: skipping low-value RPG artifact %s (%d bytes)",
                artifact,
                len(code or ""),
            )
            self.sm.set_task(
                f"rpg-{cid}",
                {"status": "SKIPPED_LOW_VALUE", "artifact": artifact},
                agent="Builder",
            )
            return None

        # Commit to repo — place in correct Android path
        remote_path = spec["files"][0]  # Use first file path from spec
        commit = await self.gh.create_or_update_file(
            path=remote_path,
            content=code,
            message=f"[RPG] {spec['title']}",
            branch=branch,
        )
        logger.info(f"Commit: {commit}")

        pr_url = await self.gh.create_pull_request(
            title=f"[RPG] {spec['title']}",
            body=f"## Android RPG Component: {spec['title']}\n\n{spec['description']}\n\n**Review:**\n{review[:600]}\n\n---\n*Built by Cognitive Foundry RPG Engine*",
            head=branch,
        )
        logger.info(f"PR: {pr_url}")
        self.sm.set_task(f"rpg-{cid}", {"status": "DELIVERED", "pr": pr_url}, agent="Builder")
        return pr_url

    async def run_pipeline(self):
        logger.info("=== ANDROID RPG SDLC STARTING ===")
        logger.info(f"Target: {REPO}")
        logger.info(f"Components: {len(RPG_PIPELINE)}")

        for idx, spec in enumerate(RPG_PIPELINE, 1):
            cid = spec["id"]
            existing = self.sm.get_task(f"rpg-{cid}")
            if existing and existing.get("status") in ["DELIVERED", "COMPLETED"]:
                logger.info(f"Skipping already delivered component: {spec['title']}")
                self.completed += 1
                continue

            set_trace_id(f"rpg-build-{idx}")
            logger.info(f"\n{'='*50}")
            logger.info(f"Step {idx}/{len(RPG_PIPELINE)}: {spec['title']}")
            logger.info(f"{'='*50}")

            try:
                artifact = await self._build_component(spec)
                if not artifact:
                    self.failed += 1
                    continue

                review = await self._review(artifact, spec)
                pr_url = await self._deliver(artifact, spec, review)
                self.completed += 1
                logger.info(f"✅ {spec['title']} delivered: {pr_url}")

            except Exception as e:
                logger.exception(f"❌ Failed to build {spec['title']}")
                self.failed += 1

            registry.record_tool_call("rpg.component", 0.0)

        logger.info(f"\n=== RPG PIPELINE COMPLETE ===")
        logger.info(f"Completed: {self.completed} | Failed: {self.failed}")


async def main():
    try:
        builder = AndroidRPGBuilder()
        await builder.run_pipeline()
    except Exception as e:
        logger.exception("Fatal error in RPG pipeline")


if __name__ == "__main__":
    asyncio.run(main())

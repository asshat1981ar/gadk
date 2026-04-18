#!/bin/bash
LAST_COUNT=$(python -c "from src.tools.github_tool import GitHubTool; import asyncio; gh=GitHubTool(); print(len(asyncio.run(gh.list_pull_requests('open'))))" 2>/dev/null)
echo "Starting monitor. Current open PRs: $LAST_COUNT"
while true; do
    sleep 60
    NEW_COUNT=$(python -c "from src.tools.github_tool import GitHubTool; import asyncio; gh=GitHubTool(); print(len(asyncio.run(gh.list_pull_requests('open'))))" 2>/dev/null)
    if [ "$NEW_COUNT" != "$LAST_COUNT" ]; then
        echo "[$(date '+%H:%M:%S')] PR count changed: $LAST_COUNT -> $NEW_COUNT"
        python -c "from src.tools.github_tool import GitHubTool; import asyncio; gh=GitHubTool(); prs=asyncio.run(gh.list_pull_requests('open')); [print(f'  #{p[\"number\"]}: {p[\"title\"]}') for p in prs]" 2>/dev/null | tail -3
        LAST_COUNT=$NEW_COUNT
    fi
    # Check if daemon died
    if ! pgrep -f "autonomous_sdlc" > /dev/null; then
        echo "[$(date '+%H:%M:%S')] ⚠️ Daemon died!"
        break
    fi
done

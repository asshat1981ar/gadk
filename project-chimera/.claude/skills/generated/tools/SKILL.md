---
name: tools
description: "Skill for the Tools area of app. 27 symbols across 8 files."
---

# Tools

27 symbols | 8 files | Cohesion: 93%

## When to Use

- Working with code in `sdlc-workflow/`
- Understanding how readFile, listDirectory, writeFile work
- Modifying tools-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tools/security_scanner.py` | _should_scan_file, _scan_file, _scan_gradle, _scan_manifest, _scan_source_files (+5) |
| `sdlc-workflow/src/lib/tools/github-file-tools.ts` | encodePath, ghHeaders, readFile, listDirectory, writeFile (+1) |
| `sdlc-workflow/src/lib/tools/android-version-tool.ts` | parseVersion, bumpVersion, upsertProperty, bumpAndroidVersionStep |
| `sdlc-workflow/src/lib/tools/ci-logs-tool.ts` | redactPii, fetchCILogsStep |
| `sdlc-workflow/src/lib/tools/detekt-tool.ts` | ghHeaders, runDetektStep |
| `sdlc-workflow/src/lib/prompts/implement-system-prompt.ts` | buildImplementSystemPrompt |
| `sdlc-workflow/src/workflows/phases/implement-agent.ts` | runAgent |
| `sdlc-workflow/src/lib/tools/gh-headers.ts` | ghHeaders |

## Entry Points

Start here when exploring this area:

- **`readFile`** (Function) — `sdlc-workflow/src/lib/tools/github-file-tools.ts:18`
- **`listDirectory`** (Function) — `sdlc-workflow/src/lib/tools/github-file-tools.ts:33`
- **`writeFile`** (Function) — `sdlc-workflow/src/lib/tools/github-file-tools.ts:51`
- **`searchCode`** (Function) — `sdlc-workflow/src/lib/tools/github-file-tools.ts:88`
- **`buildImplementSystemPrompt`** (Function) — `sdlc-workflow/src/lib/prompts/implement-system-prompt.ts:0`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `readFile` | Function | `sdlc-workflow/src/lib/tools/github-file-tools.ts` | 18 |
| `listDirectory` | Function | `sdlc-workflow/src/lib/tools/github-file-tools.ts` | 33 |
| `writeFile` | Function | `sdlc-workflow/src/lib/tools/github-file-tools.ts` | 51 |
| `searchCode` | Function | `sdlc-workflow/src/lib/tools/github-file-tools.ts` | 88 |
| `buildImplementSystemPrompt` | Function | `sdlc-workflow/src/lib/prompts/implement-system-prompt.ts` | 0 |
| `scan` | Function | `tools/security_scanner.py` | 282 |
| `ghHeaders` | Function | `sdlc-workflow/src/lib/tools/gh-headers.ts` | 0 |
| `fetchCILogsStep` | Function | `sdlc-workflow/src/lib/tools/ci-logs-tool.ts` | 21 |
| `parseVersion` | Function | `sdlc-workflow/src/lib/tools/android-version-tool.ts` | 12 |
| `bumpVersion` | Function | `sdlc-workflow/src/lib/tools/android-version-tool.ts` | 21 |
| `bumpAndroidVersionStep` | Function | `sdlc-workflow/src/lib/tools/android-version-tool.ts` | 44 |
| `to_dict` | Function | `tools/security_scanner.py` | 69 |
| `format_text_output` | Function | `tools/security_scanner.py` | 303 |
| `main` | Function | `tools/security_scanner.py` | 349 |
| `runDetektStep` | Function | `sdlc-workflow/src/lib/tools/detekt-tool.ts` | 28 |
| `encodePath` | Function | `sdlc-workflow/src/lib/tools/github-file-tools.ts` | 3 |
| `ghHeaders` | Function | `sdlc-workflow/src/lib/tools/github-file-tools.ts` | 7 |
| `runAgent` | Function | `sdlc-workflow/src/workflows/phases/implement-agent.ts` | 37 |
| `_should_scan_file` | Function | `tools/security_scanner.py` | 207 |
| `_scan_file` | Function | `tools/security_scanner.py` | 226 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `ChimeraSprintWorkflow → EncodePath` | cross_community | 5 |
| `ChimeraSprintWorkflow → GhHeaders` | cross_community | 5 |
| `Main → _scan_file` | cross_community | 4 |
| `Main → _should_scan_file` | cross_community | 4 |

## How to Explore

1. `gitnexus_context({name: "readFile"})` — see callers and callees
2. `gitnexus_query({query: "tools"})` — find related execution flows
3. Read key files listed above for implementation details

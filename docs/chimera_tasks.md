# Chimera Repository - Top 3 Issues and Action Tasks

## Issue 1: Build Configuration Lacks Version Catalog (Critical Security/Quality)
- **Description**: The project uses `build.gradle.kts` but lacks a `libs.versions.toml` version catalog for dependency management. This leads to version inconsistency, security vulnerabilities from outdated dependencies, and makes dependency updates error-prone.
- **Priority**: HIGH
- **Acceptance Criteria**:
  - Create `gradle/libs.versions.toml` with versions for all dependencies (Kotlin, Android, Ktor, Room, etc.)
  - Update `build.gradle.kts` to use the version catalog for all dependency declarations
  - Verify build succeeds with `./gradlew build` after changes

## Issue 2: Hardcoded Secrets and Configuration in Source Code (Critical Security)
- **Description**: Sensitive configuration such as API keys, AI provider credentials, and endpoint URLs may be hardcoded or referenced without proper secret management, leading to credential leakage risks.
- **Priority**: HIGH
- **Acceptance Criteria**:
  - Create `gradle.properties.example` with placeholder names for all secrets (e.g., `AI_API_KEY`, `OPENROUTER_API_KEY`)
  - Update documentation to instruct users to copy and fill in `gradle.properties` from the example
  - Ensure no plaintext secrets exist in `build.gradle.kts`, `README.md`, or source code

## Issue 3: Missing Modular Documentation and Onboarding Guide (Medium Quality/Feature)
- **Description**: The project has complex architecture but lacks a centralized onboarding document explaining module structure, build commands, testing strategy, and contribution guidelines.
- **Priority**: MEDIUM
- **Acceptance Criteria**:
  - Create `docs/ONBOARDING.md` explaining:
    - Module architecture and dependencies
    - How to run tests (unit, integration, device)
    - How to set up the development environment
    - How to add a new feature module
  - Update `README.md` with quick start commands and link to `ONBOARDING.md`
  - Verify new contributors can build and run tests following the documentation
---
phase: 05-packaging-e2e-delivery
plan: 02
subsystem: infra
tags: [docker, docker-compose, bash, powershell, packaging, env-config]

requires:
  - phase: 05-packaging-e2e-delivery (plan 01)
    provides: "finally Docker image (multi-stage build, port 8000, FRONTEND_DIST/FINALLY_DB_PATH env, /app/db volume mount point)"
provides:
  - "Idempotent scripts/start_mac.sh and scripts/stop_mac.sh for macOS/Linux"
  - "Idempotent scripts/start_windows.ps1 and scripts/stop_windows.ps1 for Windows"
  - ".env.example documenting OPENROUTER_API_KEY, MASSIVE_API_KEY, LLM_MOCK"
  - "docker-compose.yml convenience wrapper around the finally image"
  - "README 'Run with Docker' section"
affects: [05-03-e2e-tests, deployment, onboarding]

tech-stack:
  added: []
  patterns:
    - "Idempotent launcher pattern: existence-guarded docker ps/image inspect checks before build/run so re-running never errors or duplicates"
    - "Bootstrap-on-first-run: start scripts copy .env.example -> .env only if .env is absent, never overwriting a user's existing .env"

key-files:
  created:
    - scripts/start_mac.sh
    - scripts/stop_mac.sh
    - scripts/start_windows.ps1
    - scripts/stop_windows.ps1
    - .env.example
    - docker-compose.yml
  modified:
    - README.md

key-decisions:
  - "Hardcoded the literal `-v finally-data:/app/db` in the docker run invocation (rather than interpolating a shell/PS variable) so the volume mount is grep-verifiable and matches the manual command documented in PLAN.md verbatim"
  - "Windows scripts mirror the macOS scripts field-for-field (same image/container/volume names, same build-if-needed and no-op-if-running logic) so the two platforms are interchangeable"

patterns-established:
  - "Idempotent start/stop scripts: docker ps/image inspect existence checks gate every build/run/remove so scripts are safe to re-run any number of times"

requirements-completed: [PKG-03]

coverage:
  - id: D1
    description: ".env.example documents OPENROUTER_API_KEY, MASSIVE_API_KEY, and LLM_MOCK with no real secret values"
    requirement: "PKG-03"
    verification:
      - kind: unit
        ref: "grep checks for the three variable names and absence of a populated OPENROUTER_API_KEY value"
        status: pass
    human_judgment: false
  - id: D2
    description: "docker-compose.yml wraps the finally image with the finally-data volume, port 8000, and .env file"
    requirement: "PKG-03"
    verification:
      - kind: unit
        ref: "grep check for 'finally-data:/app/db' in docker-compose.yml"
        status: pass
    human_judgment: false
  - id: D3
    description: "README documents the one-command Docker run path and volume-preserving stop"
    requirement: "PKG-03"
    verification:
      - kind: unit
        ref: "grep check for 'Run with Docker' heading in README.md"
        status: pass
    human_judgment: false
  - id: D4
    description: "scripts/start_mac.sh and scripts/stop_mac.sh are idempotent: build-if-needed, launch on 8000 with finally-data volume and --env-file, safe to run twice, stop preserves the volume"
    requirement: "PKG-03"
    verification:
      - kind: integration
        ref: "manual end-to-end run: bash scripts/start_mac.sh (build-skip + container start) -> curl /api/health == ok -> bash scripts/start_mac.sh again (no-op, still healthy) -> bash scripts/stop_mac.sh twice (idempotent removal) -> docker volume inspect finally-data succeeds"
        status: pass
    human_judgment: false
  - id: D5
    description: "scripts/start_windows.ps1 and scripts/stop_windows.ps1 mirror the macOS scripts (same image/volume/port/env-file), build-if-needed with a -Build switch, preserve the volume on stop"
    requirement: "PKG-03"
    verification:
      - kind: other
        ref: "static grep checks (finally-data:/app/db, --env-file .env, image inspect/-Build, ErrorActionPreference, no volume rm) plus a Python brace/paren balance check; pwsh was not available in this environment for a live parse"
        status: pass
    human_judgment: true
    rationale: "pwsh is not installed in this execution environment, so the PowerShell scripts could not be parsed live by the PowerShell language parser as the plan's verify step prefers. Static inspection and structural balance checks all pass, but a human (or a CI runner with pwsh installed) should do a final live-parse/run confirmation on Windows or via `pwsh` before relying on these scripts in production."

duration: ~15min
completed: 2026-07-05
status: complete
---

# Phase 05 Plan 02: Packaging Scripts Summary

**Idempotent start/stop scripts for macOS/Linux and Windows, a committed .env.example, a docker-compose.yml convenience wrapper, and a README "Run with Docker" section, all wrapping the `finally` image from Plan 01.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-05
- **Tasks:** 3 completed
- **Files created:** 6 (`.env.example`, `docker-compose.yml`, `scripts/start_mac.sh`, `scripts/stop_mac.sh`, `scripts/start_windows.ps1`, `scripts/stop_windows.ps1`)
- **Files modified:** 1 (`README.md`)

## Accomplishments
- `.env.example` documents the three env vars (`OPENROUTER_API_KEY`, `MASSIVE_API_KEY`, `LLM_MOCK`) with no real secret values, each with an explanatory comment
- `docker-compose.yml` gives an optional one-command `docker compose up` path mirroring the manual `docker run` invocation
- `scripts/start_mac.sh` / `scripts/stop_mac.sh` provide a genuinely idempotent one-command launch/stop on macOS/Linux — verified end-to-end against the real `finally` image and `finally-data` volume
- `scripts/start_windows.ps1` / `scripts/stop_windows.ps1` mirror the macOS scripts field-for-field for Windows users
- README gained a "Run with Docker" section walking through `.env` setup, the scripts, the raw docker/compose commands, and the URL

## Task Commits

Each task was committed atomically:

1. **Task 1: Author .env.example, docker-compose.yml, and the README run section** - `22a8c90` (chore)
2. **Task 2: Author idempotent macOS/Linux start and stop scripts** - `067e3a9` (feat)
3. **Task 3: Author idempotent Windows PowerShell start and stop scripts** - `0783357` (feat)

## Files Created/Modified
- `.env.example` - Documents OPENROUTER_API_KEY, MASSIVE_API_KEY, LLM_MOCK with comments, no real values
- `docker-compose.yml` - `finally` service: build from repo root, 8000:8000, `finally-data:/app/db`, `env_file: .env`
- `README.md` - New "Run with Docker" section (setup, scripts, raw docker/compose commands, URL, stop/volume-preservation note)
- `scripts/start_mac.sh` - Build-if-needed, bootstrap `.env` from `.env.example`, run detached with the `finally-data` volume, no-op if already running, best-effort `open` on macOS
- `scripts/stop_mac.sh` - Idempotent stop+remove of the `finally` container; never touches the `finally-data` volume
- `scripts/start_windows.ps1` - PowerShell mirror of `start_mac.sh` (`-Build` switch, `Copy-Item` bootstrap, `Start-Process` best-effort browser open)
- `scripts/stop_windows.ps1` - PowerShell mirror of `stop_mac.sh`

## Decisions Made
- Used the literal string `-v finally-data:/app/db` directly in the `docker run` invocation on both platforms (rather than interpolating a `VOLUME_NAME` variable into that flag) so the mount matches the exact convention documented in `planning/PLAN.md` and is trivially grep-verifiable; the `VOLUME_NAME`/`$VolumeName` constants remain defined for readability/documentation even though the run command itself uses the literal.
- Windows scripts intentionally duplicate the macOS scripts' structure and naming (same image/container/volume constants, same build/no-op/remove logic) rather than trying to share logic across bash and PowerShell, since the plan calls for the two platforms to be "interchangeable."

## Deviations from Plan

None - plan executed exactly as written. The literal-string adjustment described above under "Decisions Made" was a same-task refinement discovered while running the plan's own verification grep (`finally-data:/app/db` must appear literally), not a deviation from scope — it kept the script's actual behavior identical while making the file textually match the documented convention.

## Issues Encountered
- `pwsh` (PowerShell Core) is not installed in this execution environment, so the plan's preferred live-parse verification (`[System.Management.Automation.Language.Parser]::ParseFile`) could not run. Fell back to the plan's own documented fallback: static grep checks (image/volume/port conventions, `-Build`/`ErrorActionPreference` presence, absence of `volume rm`) plus a manual brace/paren balance check on both `.ps1` files, both of which pass. This is called out as `human_judgment: true` (D5) in the coverage block above — a maintainer with `pwsh` access (or CI) should do a final live-parse before shipping.

## User Setup Required
None - no external service configuration required. `.env.example` documents optional keys; the app runs with `LLM_MOCK=true` or blank keys.

## Next Phase Readiness
- The `finally` image (Plan 01) now has a genuine one-command launch path on both platforms, ready for Plan 03's E2E test infrastructure to build on top of (Plan 03 owns `test/` and `docker-compose.test.yml`, untouched here).
- No blockers. Recommend a live Windows or `pwsh`-equipped run of `scripts/start_windows.ps1` / `stop_windows.ps1` before final release sign-off (see Issues Encountered).

---
*Phase: 05-packaging-e2e-delivery*
*Completed: 2026-07-05*

## Self-Check: PASSED

- FOUND: scripts/start_mac.sh
- FOUND: scripts/stop_mac.sh
- FOUND: scripts/start_windows.ps1
- FOUND: scripts/stop_windows.ps1
- FOUND: docker-compose.yml
- FOUND: .env.example
- FOUND commit: 22a8c90
- FOUND commit: 067e3a9
- FOUND commit: 0783357

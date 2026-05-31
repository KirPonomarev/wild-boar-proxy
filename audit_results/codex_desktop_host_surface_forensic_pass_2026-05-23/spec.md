# CODEX_DESKTOP_HOST_SURFACE_FORENSIC_PASS Spec

## Program

`EXECUTION_CORE_FULL_SYSTEM_TO_ISOLATED_CODEX_APP_PASS`

## Goal

Perform a read-only forensic pass over the installed Codex Desktop host surface
and prior GUI-boundary evidence, then decide which next contour is safe:

- official Codex wrapper dry-run,
- copied/renamed `Codex Custom.app` dry-run,
- WBP workbench fallback.

## Canonical Rules

- Canon order: `CANON.md`, `MASTER_PLAN.md`, `RUNTIME_CONTRACT.md`,
  `STATE_SCHEMA.md`, `COMMAND_API.md`, `DELIVERY_RULES.md`, `README.md`,
  `WORKFLOW_OS_V1_2.md`, `AGENTS.md`.
- `CLIProxyAPI` remains the engine.
- Wild Boar Proxy remains the control layer.
- The official host client must not be patched.
- The current working Codex profile/process must not be mutated.
- `launch client --json` proves only bounded OS dispatch, not GUI session
  success.
- Obsidian notes are hints only and never override repo canon.

## Hard Rules

- No GUI launch.
- No prompt through GUI.
- No `.app` build.
- No mutation of `/Applications/Codex.app`.
- No mutation of `~/.codex`.
- No writes to `~/Library/Application Support/Codex`,
  `~/Library/Caches/com.openai.codex`, or
  `~/Library/HTTPStorages/com.openai.codex`.
- No system proxy changes.
- No secret/auth values in artifacts.
- No success from PID, OS dispatch, or headless Codex alone.

## Read Surfaces

- `/Applications/Codex.app/Contents/Info.plist`
- `/Applications/Codex.app/Contents/MacOS/Codex`
- `/Applications/Codex.app/Contents/Resources/codex`
- `/Applications/Codex.app/Contents/Resources/app.asar`
- repo canon docs listed above
- `audit_results/isolated_codex_app_e2e_pass_2026-05-23/*`
- `audit_results/isolated_codex_engine_work_session_retry_with_real_wbp_harness_2026-05-23/*`
- `/Volumes/Work/Pushkin/Pushkin/конфиги.md`
- `/Volumes/Work/Pushkin/Pushkin/план расширение кастома.md`
- `/Volumes/Work/Pushkin/Pushkin/кабан приложение.md`

## Write Surface

Only:

`audit_results/codex_desktop_host_surface_forensic_pass_2026-05-23/*`

## Acceptance Criteria

- Host surface inventory is complete enough to choose a safe next experiment.
- Previous GUI blocker is reclassified from packet evidence.
- Isolation matrix covers `CODEX_HOME`, Electron userData, bundle id, URL
  scheme, app-server socket, cache/storage, process tree, WBP endpoint, auth
  source, model catalog, update mechanism, and LaunchServices risk.
- Recommended next contour is explicit and bounded.
- No mutation outside declared audit path.

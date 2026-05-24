# Spec: WEB_SAFE_APP_COPY_BOUNDED_HELPER_EXECUTION_PASS

## Objective

Prove bounded helper execution for the Safe App Copy web path without launching
Codex.app, touching the current Codex session, using accounts, or entering the
CLIProxyAPI/session-manager layer.

## In Scope

- Server-owned empty JSON `{}` launch request only.
- Server-owned helper executable with explicit provenance.
- Redacted browser-facing launch receipt.
- Regression tests for forbidden payloads, invalid bodies, missing provenance,
  Codex-like targets, `.app` targets, and symlinked targets.
- Web UI projection of the resulting packet.

## Out of Scope

- Original Codex launch.
- Real Codex.app launch.
- GPT account connect.
- CLIProxyAPI inference.
- Custom session manager changes.
- Desktop packaging or design polish.

## Constraints

- `Wild Boar Proxy` remains the control layer.
- `CLIProxyAPI` remains the engine and is not invoked in this contour.
- Browser must not provide path, pid, env, auth, token, route, backend, HOME, or
  CODEX_HOME.
- JSON packets are the primary truth.
- No false green: unsafe target, malformed body, no-body, cleanup failure, or
  missing provenance must block success.

## Acceptance Criteria

- [x] `WEB_SAFE_APP_COPY_BOUNDED_HELPER_EXECUTION_READY` is emitted only after
  owner admission, process start proof, and cleanup proof.
- [x] `launch_performed=true` only on bounded helper execution success.
- [x] `real_codex_app_launched=false`.
- [x] `current_codex_touched=false`.
- [x] `current_codex_home_touched=false`.
- [x] `raw_path_exposed=false`, `raw_pid_exposed=false`, `raw_env_exposed=false`.
- [x] Invalid, non-object, and empty/no-body requests cannot execute helper.
- [x] Missing provenance, Codex-like, `.app`, and symlinked targets block.

## Verification

- tests: `node --check`, 97 targeted launch/UI tests, 200 full launch/live/UI/operator tests.
- build: `git diff --check`.
- manual: bounded live server proof with redacted helper target and no-body rejection.
- live evidence: `helper_execution_packet.json`, `blocked_packets.json`, `browser_projection_proof.json`.

## Open Questions

- None for this contour. Next master-plan contour is safe account connect dry-run.

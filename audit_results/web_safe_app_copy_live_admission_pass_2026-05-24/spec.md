# WEB_SAFE_APP_COPY_LIVE_ADMISSION_PASS Spec

## Goal

Prove that WBP web can admit or block Safe App Copy live launch using a server-owned owner contract without touching the current Codex, current home, Codex home, raw paths, raw pid, or raw env.

## Scope

- Add a machine truth packet for Safe App Copy live admission.
- Wire `/api/codex/app-copy/live-admission` to existing server-side `LaunchCopyContract` preflight.
- Keep `/api/codex/app-copy/launch` blocked in this contour, even when admission is ready.
- Show admission truth in the web panel.
- Gate UI launch readiness on a future `WEB_SAFE_APP_COPY_LAUNCH_READY` packet only.
- Reject browser-supplied path, pid, process, command, env, auth, token, and route fields.

## Out Of Scope

- Real app-copy process launch.
- Current Codex launch or mutation.
- `~/.codex` mutation.
- CLIProxyAPI routing.
- GPT accounts.
- Codex Custom sessions.
- Desktop packaging.
- Design polish.

## Verdicts

- `WEB_SAFE_APP_COPY_LIVE_ADMISSION_READY`: server-owned owner contract is admitted, no process launched, launch-ready not claimed.
- `WEB_SAFE_APP_COPY_LAUNCH_EXECUTION_NOT_IN_CONTOUR`: launch endpoint remains blocked after admission.
- `WEB_SAFE_APP_COPY_LAUNCH_BROWSER_FIELD_REJECTED`: browser tried to control forbidden launch/admission fields.

## Acceptance

- Admission ready packet has `launch_performed=false`, `launch_ready_claimed=false`, and `bounded_live_launch_execution_ready=false`.
- Launch endpoint remains blocked after owner preflight admission.
- Forbidden browser payload has `live_launch_admitted=false`.
- UI launch button remains disabled unless a future packet proves `WEB_SAFE_APP_COPY_LAUNCH_READY`.
- No raw path, pid, env, token, auth, or secret value is projected to browser.

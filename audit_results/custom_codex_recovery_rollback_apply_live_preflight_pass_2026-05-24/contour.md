# CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_LIVE_PREFLIGHT_PASS

Date: 2026-05-24
Branch: codex/external-agent-lab-isolated
Start HEAD: 94835117

## Goal

Add a strict machine preflight for the next bounded rollback-apply contour.

## Scope

In scope:

- Evaluate server-owned rollback apply admission dry-run.
- Publish a read-only GET endpoint for live preflight.
- Project preflight truth into the WBP web UI.
- Reject browser-supplied rollback target, path, backend, auth, HOME, CODEX_HOME, token, api_key, and secret fields.
- Preserve no-apply, no-write, no-kill, no-operator-ready guarantees.

Out of scope:

- No rollback apply.
- No process kill.
- No filesystem write.
- No recovery operator ready claim.
- No current Codex or Original Codex mutation.

## Verdict

Implemented as a preflight-only contour. Successful packets can mark the next bounded apply contour as eligible, but they do not admit or execute rollback apply.

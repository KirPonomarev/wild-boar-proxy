# CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_LIVE_PASS

## Scope

- Create one bounded Codex Custom recovery rollback point artifact after server-side admission recheck.
- Keep WBP as the control layer and CLIProxyAPI as the engine.
- Add only minimal web trigger/render UI; no design polish.
- Preserve Original Codex and current Codex isolation.

## In Scope

- `POST /api/codex/custom/recovery/rollback-point`
- Core packet builder for live rollback-point creation.
- Empty/absent browser body only.
- Redacted artifact proof with digest, no raw path.
- Tests for success, forbidden browser fields, non-object body, shallow admission, and disabled apply/kill paths.

## Out Of Scope

- Rollback apply.
- Process kill.
- Arbitrary cleanup.
- Credential/account/API route mutation.
- Desktop packaging.
- Recovery/operator-ready claim.

## Result

- `result_token`: `CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_LIVE_READY`
- `claim_scope`: `custom_codex_recovery_rollback_point_create_live_only`
- `next_contour`: `CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_VERIFY_PASS`

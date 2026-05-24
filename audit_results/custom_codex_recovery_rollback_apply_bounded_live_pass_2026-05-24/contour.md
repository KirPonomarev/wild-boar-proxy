# CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_BOUNDED_LIVE_PASS

Date: 2026-05-24
Branch: codex/external-agent-lab-isolated
Start HEAD: 20d843af

## Goal

Perform the first bounded recovery apply as a WBP-owned receipt artifact only.

## Scope

In scope:

- Add bounded apply receipt packet builder.
- Add `POST /api/codex/custom/recovery/rollback-apply`.
- Require a successful rollback-apply live preflight.
- Write exactly one bounded apply receipt under the owned generated recovery artifact surface.
- Reject browser target/path/backend/session/auth payloads before read/write.
- Project the receipt packet into the existing WBP web recovery surface.

Out of scope:

- No full rollback restore.
- No current Codex home mutation.
- No Original Codex mutation.
- No auth, account, API credential, provider, or engine mutation.
- No process kill.
- No recovery/operator-ready claim.

## Verdict

Implemented as `bounded_apply_receipt_only`. Success proves receipt creation, not system recovery.

# ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS Risk Matrix

| Risk | Evidence | Verdict |
| --- | --- | --- |
| Sandbox-local owner onboarding binary missing | `onboard_command_packet.json` reports `MISSING_ONBOARD_BIN` for `/Users/kirillponomarev/.codex-custom-test/managed/bin/codex-account-onboard` | blocker |
| Sandbox-local post-proof binaries/scripts missing | `pre_onboard_snapshot.json` shows missing `codex-accounts`, `codex-managed-status`, and `supervisor-sync.sh` inside sandbox | blocker |
| Unsafe fallback to live owner binary would read/write work contour | `/Users/kirillponomarev/.codex-custom-cli/managed/bin/codex-account-onboard` and `codex-accounts` hardcode `Path.home()`, `~/.codex-custom-cli`, and `~/.cli-proxy-api` | blocker |
| Silent live drift during failed onboarding attempt | `forbidden_drift_check.json` shows unchanged live-path snapshots; `changed_files` stayed empty | not observed |
| False success from UI or narrative | UI phase intentionally skipped because command-phase blocker already decided verdict | avoided |

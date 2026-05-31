# API_PROVIDER_OWNER_SETUP_HANDOFF_PASS Closeout

## Goal

Make web `Подключить API` usable when owner credential is missing, while preserving the rule that web never accepts API keys or secrets.

## Result

- status: implemented and verified
- final verdict: closed_success
- next action: continue only to provider-specific owner UX if needed

## Contour Capsule

- goal: missing OpenRouter credential becomes an owner setup handoff with expected env refs and dashboard URL; retry with owner env connects the route.
- branch: codex/external-agent-lab-isolated
- head: final contour commit containing this closeout; see git log
- touched files: `wild_boar_proxy/external_models/credentials.py`, `wild_boar_proxy/external_models/__init__.py`, `wild_boar_proxy/web_design_live_server.py`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, `tests/test_cli_external_models.py`, `tests/test_web_design_live_server.py`, `tests/test_web_design_ui.py`, audit artifacts under this directory
- tests run: `node --check`; required unittest gate; `git diff --check`; closeout resilience before commit
- blocked risks: real provider OAuth/dashboard automation remains out of scope
- next exact command: start the next contour only after this commit is pushed

## Verification

- missing browser proof: `browser-missing-summary.json` shows `action_status=command_error`, `machine_error_code=EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING`, `next_action=owner_action`, `credential_phase=credential_missing`, `api_key_input_count=0`
- retry browser proof: `browser-retry-summary.json` shows `credential_phase=credential_admitted`, `api_route_connect_phase=created_and_validated`, `validate_status=ok`, `route_visible_after_refresh=true`
- ledger proof: missing and retry DOM summaries include credential phase and setup metadata
- redaction: `redaction-check.json` shows sentinel secret absent from text evidence and `secret_value_exposed=false`
- no new command surface was added

## Artifacts

- spec: `audit_results/api_provider_owner_setup_handoff_pass_2026-05-22/spec.md`
- metrics: `audit_results/api_provider_owner_setup_handoff_pass_2026-05-22/metrics.json`
- independent audit: `audit_results/api_provider_owner_setup_handoff_pass_2026-05-22/independent_audit.json`
- browser missing packet: `audit_results/api_provider_owner_setup_handoff_pass_2026-05-22/evidence/browser-missing-action-packet.json`
- browser retry packet: `audit_results/api_provider_owner_setup_handoff_pass_2026-05-22/evidence/browser-retry-action-packet.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: final contour commit containing this closeout; see git log
- pushed: completed during contour closeout

## Scope Check

- unrelated work mixed in: no; unrelated untracked files in the worktree were ignored
- layer boundary: web displays owner setup metadata only; credential material remains owner-side
- private-data risk reviewed: yes; sandbox runtime stayed under temporary OS directories, and secret values are not present in committed evidence

## Notes

- The first missing browser pass exposed a false refresh mismatch for failed `api_route_connect`; this was fixed so command failures remain non-green without claiming route refresh mismatch.
- The OpenRouter dashboard URL was checked against current public setup references during implementation; it remains informational, not an auth callback or success proof.
- resume from here: CLOSED

CONTOUR:
Goal: localize which sync-owned managed write surfaces retake effective runtime truth after stable runtime activation had already been proved, then choose the narrowest corrective contour
Size: M
Risk level: high
Decision owner: Codex
Mode: exploration

In scope:
- bounded owner-path evidence capture via `status --json` and `rollout rotation inspect --json`
- read-only comparison of sync-managed scripts, runtime status readers, and supervisor-state surfaces
- authority ranking across participation, policy, and runtime truth surfaces
- exact next-contour selection

Out of scope:
- sandbox `auth.json` materialization
- onboarding rerun
- exact auth-source admission
- repeating `sync --json`
- repeating `launch smoke --json`
- code repair in this contour

Assumptions:
- the previously recorded sync refresh is the only selector-refresh mutation relevant to this contour
- current runtime state still reflects the last sync-managed lane handoff
- canon authority order from `CANON.md` through `README.md` remains unchanged

Inputs:
- docs:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `RUNTIME_CONTRACT.md`
  - `STATE_SCHEMA.md`
  - `COMMAND_API.md`
- code:
  - `wild_boar_proxy/runtime.py`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-sync.sh`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-healthcheck.sh`
  - `tests/test_cli.py`
- runtime evidence:
  - `python3 -m wild_boar_proxy status --json`
  - `python3 -m wild_boar_proxy rollout rotation inspect --json`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
  - `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
  - `/Users/kirillponomarev/.codex-custom-cli/config.toml`

Commands / files:
- `python3 -m wild_boar_proxy status --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`
- `rg -n "effective_mode|claim_gate|policy_drift|selected_backend_snapshot|stable_runtime_consumer_snapshot" wild_boar_proxy/runtime.py tests/test_cli.py`
- `sed -n` / `nl -ba` against runtime and owner scripts

Acceptance criteria:
- the exact sync-owned managed write surfaces affecting runtime truth are named concretely
- the contour distinguishes selector freshness from runtime truth ownership
- the contour decides whether the issue is transient, over-read, or write-surface driven
- one exact next corrective contour is named without reopening auth-source work

Verification:
- tests:
  - targeted CLI unit tests for sync snapshot materialization and approved-target policy-drift gating
- build:
  - `git diff --check`
- manual:
  - compare current status/rotation packets with current runtime files and supervisor-state fields
- live packet:
  - confirm current `status --json` still reports `effective_mode = managed` while `rollout rotation inspect --json` reports fresh participation evidence

Artifacts:
- spec:
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/lane_drift_basis.json`
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/surface_ownership_comparison.json`
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/drift_localization.json`
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/authority_decision.json`
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/decision_packet.json`
- closeout note:
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/closeout.md`

Stop conditions:
- surface ownership cannot be localized beyond "something in sync"
- next contour would still depend on guessed auth-source truth
- evidence from status, rotation, and files becomes contradictory in a new way

Closeout:
- verification complete: pending
- commit: pending
- push: pending
- next contour: `GO_TO_SYNC_MANAGED_MODE_WRITE_SURFACE_REPAIR_PASS`

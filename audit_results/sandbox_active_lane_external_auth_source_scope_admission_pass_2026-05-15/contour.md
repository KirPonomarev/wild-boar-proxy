CONTOUR:
Goal: Determine the exact canon-admissible next secret-bearing repair contour after the sandbox auth-source STOP.
Size: M
Risk level: high
Decision owner: Codex
Mode: live-proof

In scope:
- external auth-source scope adjudication
- exact source-path admissibility check
- import vs rebind vs combined split
- write-surface and rollback declaration for the next contour

Out of scope:
- real secret mutation
- launcher/materialization execution
- lifecycle rerun
- broader runtime redesign

Assumptions:
- `healthcheck --json` remains owner truth
- previous contour truth is preserved under `audit_results/sandbox_active_lane_auth_source_repair_pass_2026-05-15/`
- registry still points to sandbox auth.json unless contradicted

Inputs:
- docs:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `RUNTIME_CONTRACT.md`
  - `STATE_SCHEMA.md`
  - `COMMAND_API.md`
  - `DELIVERY_RULES.md`
- code:
  - `wild_boar_proxy/runtime.py`
  - `wild_boar_proxy/cli.py`
  - `tests/test_cli.py`
- runtime evidence:
  - previous contour decision and attestation override packets
  - current registry binding and auth metadata facts

Commands / files:
- read prior contour packets
- canon/code searches for `WBP_AUTH_FILE`, `auth_ref_matches`, `legacy import`, and real-runtime config protection

Acceptance criteria:
- one exact next contour selected or honest STOP preserved
- exact external source path declared if GO
- exact write surfaces declared if GO
- exact rollback expectations declared if GO

Verification:
- tests: N/A for scope-only contour beyond evidence review
- build: `git diff --check`
- manual: artifact review and canon references
- live packet: prior contour live packets reused, no new mutation

Artifacts:
- spec: `contour.md`
- packet: `decision_packet.json`
- closeout note: `closeout.md`

Stop conditions:
- no canon-admissible secret-bearing next contour can be justified
- selected outcome depends on hidden launcher/materialization work
- combined contour is chosen without fused-ownership proof

Closeout:
- verification complete: yes
- commit: pending
- push: pending
- next contour: `SANDBOX_ACTIVE_LANE_EXTERNAL_AUTH_IMPORT_REPAIR_PASS`

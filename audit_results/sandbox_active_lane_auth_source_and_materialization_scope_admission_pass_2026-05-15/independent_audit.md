# Independent Audit

## Inputs Reviewed

- Current contour blocker basis and scope matrices
- Prior STOP artifacts from:
  - `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_post_promotion_status_attestation_repair_pass_2026-05-15/`
  - `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_active_lane_auth_runtime_truth_repair_pass_2026-05-15/`
- Local subagent `Locke` responses

## Audit of Subagent Reliability

1. First response was scope-confused.
   - It named the current scope-admission contour instead of the next exact repair contour.
   - That answer was rejected.

2. Second response improved contour selection but still overreached on write surfaces.
   - Correct: chose `SANDBOX_ACTIVE_LANE_AUTH_SOURCE_REPAIR_PASS`.
   - Incomplete: emphasized registry/onboarding surfaces but missed that live attestation reads Bearer auth directly from `paths.auth_file` in `wild_boar_proxy/runtime.py`.

3. Net assessment:
   - contour selection: accepted
   - write-surface details: partially rejected and replaced by local code-grounded analysis

## Independent Findings

- `healthcheck --json` and `status --json` both fail on the same live truth: `HTTP 401: {"error":"Invalid API key"}`.
- `run_healthcheck()` reads the Bearer secret from `read_api_key(paths.auth_file)`, so the primary mutable truth source is the sandbox auth file:
  - `wild_boar_proxy/runtime.py:561`
  - `wild_boar_proxy/runtime.py:5340`
- Materialization remains separate:
  - `launch smoke --json` owns the narrow activation/materialization lane.
  - `sync --json` keeps the sandbox on stable and does not prove managed active truth.
  - current generated/approved-target materialization artifacts are absent.
- Sandbox `external-models` evidence is secondary:
  - adapter `synthetic/stopped`
  - `routes=[]`
  - `models=[]`
  - `secrets.env` empty
  - useful for later materialization/runtime support, but not the primary live 401 source currently exercised by `healthcheck --json`.

## Verdict

The current contour truthfully supports:

- `GO_TO_EXACT_NEXT_REPAIR_CONTOUR`
- exact next contour: `SANDBOX_ACTIVE_LANE_AUTH_SOURCE_REPAIR_PASS`

It does not support:

- materialization-first next contour
- combined auth+materialization next contour
- hidden launch-smoke or lifecycle continuation inside the next pass

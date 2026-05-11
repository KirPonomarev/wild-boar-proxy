SEQUENCE:
1. `python3 -m wild_boar_proxy sync --json`
2. `python3 -m wild_boar_proxy rollout rotation inspect --json`
3. `python3 -m wild_boar_proxy launch smoke --json`
4. final reread:
   - `status --json`
   - `healthcheck --json`
   - `accounts list --json`
   - `rollout rotation inspect --json`

Why admitted:
- `step61` closed with:
  - `GO_COMPOSITE_RUNTIME_RECONCILIATION_PROOF_CONTOUR`
- split single-lane retries are already proven insufficient
- this sequence is bounded, explicit, and owner-disciplined

Owner surfaces:
- `sync --json`
  - admitted only for managed-lane sync plus selected-backend snapshot
    materialization
- `launch smoke --json`
  - admitted only for bounded stable-runtime activation truth

Expected write surfaces from prior owner packets:
- `sync --json`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/backend-registry.json`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/managed-config.yaml`
  - `/Users/kirillponomarev/.codex-custom-cli/config.toml`
  - `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/managed-proxy.pid`
- `launch smoke --json`
  - `/Users/kirillponomarev/.codex-custom-cli/config.toml`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
  - `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/stable-runtime-config.generated.yaml`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/managed-proxy.pid`

Rollback expectation:
- no manual state or registry edits
- if `sync --json` fails to clear rotation midflight:
  - stop immediately
  - do not continue to `launch smoke --json`
- if the full sequence does not leave both runtime truth and rotation evidence
  green:
  - close the contour
  - do not retry single-lane repair
  - escalate to contradiction repair

Known preflight starting point for this contour:
- `status --json`
  - `effective_mode=managed`
  - `claim_gate.status=blocked`
  - `policy_drift.status=detected`
  - `consumer_activation_readiness=STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING`
- `healthcheck --json`
  - `machine_error_code=OK`
  - `launch_readiness.status=ready`
- `rollout rotation inspect --json`
  - `machine_error_code=ROTATION_EVIDENCE_STALE`
  - `evidence_freshness=stale`
  - `evidence_reason=selected_backend_snapshot_stale`

Stop conditions:
- invalid JSON from any owner surface
- either admitted owner surface becomes non-admissible at execution time
- midflight rotation does not become `OK/fresh`
- hidden third mutation surface would be required
- scope drifts into posture normalization, stage-20, same-day validation, or UI

Machine-readable stop triggers:
- pre-`launch smoke`:
  - `sync --json.machine_error_code != OK`
  - or sync succeeds without refreshing snapshot truth
  - canonical stop codes:
    - `MISSING_SYNC_SCRIPT`
    - `SYNC_FAILED`
    - `SYNC_HEALTHCHECK_FAILED`
- midflight gate:
  - `rollout rotation inspect --json.machine_error_code != OK`
  - or snapshot validation is not `valid`
  - or freshness is not `fresh`
  - canonical stop codes:
    - `ROTATION_EVIDENCE_STALE`
    - `ROTATION_EVIDENCE_UNKNOWN`
    - `ROTATION_EVIDENCE_UNAVAILABLE`
    - `ROTATION_EVIDENCE_INSUFFICIENT`
    - `ROTATION_EVIDENCE_CONTRADICTED`
- post-`launch smoke`:
  - launch smoke does not end in healthy stable truth
  - or exits non-zero
  - or falls back instead of proving approved-target activation
  - canonical stop codes:
    - `MISSING_LAUNCHER_SCRIPT`
    - `LAUNCHER_EXIT_NONZERO`
    - `LISTENER_DOWN`

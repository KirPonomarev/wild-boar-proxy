Live operation declaration for `ROTATION_EVIDENCE_STALE_RECLEAR_CONTOUR`

Admitted owner surface:
- `python3 -m wild_boar_proxy sync --json`

Expected write surfaces:
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/managed/managed-proxy.pid`

Expected truth change:
- `rollout rotation inspect --json.machine_error_code` moves from
  `ROTATION_EVIDENCE_STALE` to `OK`
- `rotation_evidence_result.evidence_freshness` moves from `stale` to `fresh`
- `rotation_evidence_result.evidence_reason` clears
- selected-backend snapshot remains present and valid with a refreshed
  `observed_at_utc`

Rollback expectation:
- owner packet must expose truthful `changed_files`
- if sync fails or postflight verification fails, contour closes `NO_GO` and
  does not widen into `launch smoke --json`, posture normalization, or any
  multi-step runtime repair

Stop conditions before mutation:
- independent inspection rejects `sync --json` as the admitted owner lane
- fresh contradictory runtime truth appears that invalidates the lane
- command fails to return a strict JSON owner packet

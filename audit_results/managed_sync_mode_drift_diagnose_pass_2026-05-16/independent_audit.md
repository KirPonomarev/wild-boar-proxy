# Independent Audit

Auditor: `Volta` (`gpt-5.4`, reasoning `high`)

## Verdict

`GO_TO_SYNC_MANAGED_MODE_WRITE_SURFACE_REPAIR_PASS`

## Factual Basis

- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-sync.sh:271-323`
  writes `state["effective_mode"]`, and
  `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-sync.sh:1069`
  calls it with `managed`.
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-healthcheck.sh:50-144`
  writes `state["effective_mode"]`, `runtime-effective-mode.txt`, and
  `config.toml` `base_url`, and
  `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-healthcheck.sh:350`
  calls it with `managed`.
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
  currently contains `managed`,
  `/Users/kirillponomarev/.codex-custom-cli/config.toml`
  currently points to `http://127.0.0.1:8320/v1`,
  and `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
  currently records `effective_mode = managed`.
- `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py:1247-1254`
  makes `runtime-effective-mode.txt` the primary effective-mode read surface,
  ahead of the state-file fallback.
- `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py:5160-5175` and
  `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py:1974-2009`
  show that approved-target policy-drift clearance is unavailable unless live
  runtime remains `stable`.

## Lie Check

- auditor verdict matches local packet truth
- no unsupported jump into auth-source work
- no reliance on stale selector-only evidence

# Rollback Check

## Scope

This rollback applies only to scaffold paths created by `SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_EXECUTION_PHASE_PASS`.
It does not remove the pre-existing sandbox root or any non-target profile data already present under `/Users/kirillponomarev/.codex-custom-test`.

## Created Scaffold Paths

- `/Users/kirillponomarev/.codex-custom-test/managed/backend-registry.json`
- `/Users/kirillponomarev/.codex-custom-test/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-test/managed/managed-config.yaml`
- `/Users/kirillponomarev/.codex-custom-test/runtime-mode.txt`
- `/Users/kirillponomarev/.codex-custom-test/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-test/stable/config.yaml`
- `/Users/kirillponomarev/.codex-custom-test/codex-custom-launch.sh`
- `/Users/kirillponomarev/.codex-custom-test/external-models/routes.json`
- `/Users/kirillponomarev/.codex-custom-test/external-models/state.json`
- `/Users/kirillponomarev/.codex-custom-test/external-models/secrets.env`
- `/Users/kirillponomarev/.codex-custom-test/external-models/evidence/`

## Concrete Rollback Steps

1. Remove created files:
   - `rm -f /Users/kirillponomarev/.codex-custom-test/managed/backend-registry.json`
   - `rm -f /Users/kirillponomarev/.codex-custom-test/managed/supervisor-state.json`
   - `rm -f /Users/kirillponomarev/.codex-custom-test/managed/managed-config.yaml`
   - `rm -f /Users/kirillponomarev/.codex-custom-test/runtime-mode.txt`
   - `rm -f /Users/kirillponomarev/.codex-custom-test/runtime-effective-mode.txt`
   - `rm -f /Users/kirillponomarev/.codex-custom-test/stable/config.yaml`
   - `rm -f /Users/kirillponomarev/.codex-custom-test/codex-custom-launch.sh`
   - `rm -f /Users/kirillponomarev/.codex-custom-test/external-models/routes.json`
   - `rm -f /Users/kirillponomarev/.codex-custom-test/external-models/state.json`
   - `rm -f /Users/kirillponomarev/.codex-custom-test/external-models/secrets.env`
2. Remove created directories if empty:
   - `rmdir /Users/kirillponomarev/.codex-custom-test/external-models/evidence`
   - `rmdir /Users/kirillponomarev/.codex-custom-test/external-models`
   - `rmdir /Users/kirillponomarev/.codex-custom-test/stable`
   - `rmdir /Users/kirillponomarev/.codex-custom-test/managed`
3. Do not remove `/Users/kirillponomarev/.codex-custom-test` itself unless a later operator decision explicitly authorizes cleanup of the pre-existing sandbox profile.

## Residue Check

Rollback is considered clean when:

- every scaffold file listed above is absent
- directories `managed/`, `stable/`, and `external-models/` are absent or empty if explicitly retained by a later contour
- the pre-existing non-target files under `/Users/kirillponomarev/.codex-custom-test` still match their pre-contour classification as untouched data
- forbidden live paths under `/Users/kirillponomarev/.codex-custom-cli` and `/Users/kirillponomarev/.cli-proxy-api/config.yaml` remain unchanged

## Verification Status

- rollback steps are concrete for every created scaffold path
- destructive teardown was not executed in this contour because no extra proof beyond no-drift was required

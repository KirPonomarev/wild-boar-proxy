# Write Surface Declaration

## Declared Active Sandbox Root

`/Users/kirillponomarev/.codex-custom-sandbox-20260515`

This root is declared for the active sandbox wave because it is:

- not equal to any working/live root
- not nested under any working/live root
- currently absent, so no prior mutable state must be trusted or cleaned in
  place

## Writable Surfaces For The Next Sandbox Wave

Only paths under the declared root are admissible for later sandbox writes.

### Runtime companion surfaces

- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/auth.json`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/config.toml`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/runtime-mode.txt`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/codex-custom-launch.sh`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/managed/backend-registry.json`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/managed/managed-config.yaml`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/managed/wild-boar-proxy.lock`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/managed/supervisor-sync.sh`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/managed/bin/`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/managed/stable-repair-target/`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/managed/approved-repair-target.json`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/managed/target-switch-transaction.json`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/managed/stable-runtime-config.generated.yaml`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/stable/config.yaml`

### External-models surfaces

- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/external-models/routes.json`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/external-models/state.json`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/external-models/secrets.env`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/external-models/evidence/`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/external-models/routes.lock`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/external-models/state.lock`

### Host-client local-only sandbox surfaces

- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/launch-logs/`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/logs_2.sqlite*`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/state_5.sqlite*`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/sessions/`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/shell_snapshots/`
- `/Users/kirillponomarev/.codex-custom-sandbox-20260515/tmp/`

## Explicit Non-Write Rule

No later sandbox contour may write outside the declared sandbox root unless a
new contour explicitly re-admits that surface.

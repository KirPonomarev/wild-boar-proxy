STEP41 OPERATION DECLARATION

authorized_by:
- explicit standing owner authorization present in the active thread

commands:
- `python3 -m wild_boar_proxy stable target switch --apply --json`
- `python3 -m wild_boar_proxy stable repair --apply --json`
- `python3 -m wild_boar_proxy launch smoke --json`
- `python3 -m wild_boar_proxy status --json`
- `python3 -m wild_boar_proxy healthcheck --json`
- `python3 -m wild_boar_proxy accounts list --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`

exact real read paths:
- `/Users/kirillponomarev/.codex-custom-cli/managed/`
- `/Users/kirillponomarev/.cli-proxy-api/`
- `/Users/kirillponomarev/.cli-proxy-api/config.yaml`
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`

declared write paths:
- `/Users/kirillponomarev/.codex-custom-cli/managed/stable-repair-target/`
- `/Users/kirillponomarev/.codex-custom-cli/managed/approved-repair-target.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/target-switch-transaction.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/.stable-repair-stage-*`
- `/Users/kirillponomarev/.codex-custom-cli/managed/.stable-repair-backup-*`
- `/Users/kirillponomarev/.codex-custom-cli/managed/stable-runtime-config.generated.yaml`
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`

rollback expectation:
- no manual rollback in this contour
- if target-switch, stable-repair, or launch-smoke owner packets fail, close
  `NO_GO` immediately and stop
- if owner packets report changed files outside the declared control-layer write
  set, close `NO_GO` as contract drift

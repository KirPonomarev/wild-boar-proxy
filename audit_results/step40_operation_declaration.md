# Step40 Operation Declaration

## Contour

- `step40`
- name: `authorized_single_sync_reclear`
- mode: `live-proof`
- branch: `codex/wave-1c-prereq-closeout`
- commit: `d757f1ee40bd42f9193960d34b9264380b3a3f8c`
- generated_at_utc: `2026-05-08T20:56:13Z`

## Reopen Status

- prior precondition gate result: `NOT_AUTHORIZED_NOW`
- reopen status: `authorized`
- contour identity: unchanged

## Owner Authorization Evidence

- active-thread standing approval phrase present:
  `разрешаю тебе любые законные действия в рамках разработки проекта`
- authorization scope:
  - project-scoped
  - includes legal live-runtime contours allowed by canon and runbooks
- bounded step authorized in this contour:
  - exactly one `python3 -m wild_boar_proxy sync --json`

## Exact Command

- `python3 -m wild_boar_proxy sync --json`

## Exact Real Read Paths

- `/Users/kirillponomarev/.codex-custom-cli/managed/`
- `/Users/kirillponomarev/.cli-proxy-api/`
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`

## Exact Real Write Paths

- `/Users/kirillponomarev/.codex-custom-cli/managed/backend-registry.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/managed-config.yaml`
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/managed/managed-proxy.pid`

## Rollback Expectation

- no manual file rollback in this contour
- if sync fails, close `NO_GO`
- if truth remains blocked after the one allowed sync, close `NO_GO`
- if `changed_files` escapes the declared write set, close `NO_GO` as contract drift

## Boundedness Rule

- no second `sync --json`
- no `launch smoke --json` by default
- no posture normalization in this contour

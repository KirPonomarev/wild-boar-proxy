# Spec: ACCOUNT_OWNER_SANDBOX_LOGIN_ADMISSION_PASS

## Objective

Add the minimal owner-owned sandbox login admission surface so web can later
bridge to owner auth flow without becoming auth owner.

## In Scope

- `accounts login start --provider sandbox --json`
- `accounts login complete --session <id> --state <state> --proof <proof> --json`
- sandbox session store under managed dir
- TTL, state/proof checks, replay guard
- synthetic sandbox auth artifact materialization
- strict JSON packet surface
- compatibility proof with `accounts onboard --json` via owner-provided `auth_ref`
- targeted tests and evidence artifacts

## Out of Scope

- web UI bridge wiring
- real OAuth/provider callback
- browser secret/token/path intake
- API route create/adopt
- desktop, packaging, redesign

## Constraints

- Canon order: `CANON.md` -> `MASTER_PLAN.md` -> `RUNTIME_CONTRACT.md` -> `STATE_SCHEMA.md` -> `COMMAND_API.md` -> `DELIVERY_RULES.md` -> `README.md`
- Wild Boar Proxy remains managing layer
- auth flow ownership remains owner/engine lane
- no runtime/private data committed

## Assumptions

- Contour uses sandbox copy paths via `WBP_*` env.
- `accounts onboard --json` consumes explicit owner-provided `auth_ref` reliably.

## Acceptance Criteria

- [x] login start command exists and emits strict JSON with session/state/nonce/expiry/login URL
- [x] login complete command exists and rejects invalid session/state/proof/expired/replay
- [x] completion materializes sandbox synthetic auth and emits `auth_ref` + `auth_ref_scope`
- [x] completion packet redacts proof/token/secret/password
- [x] owner proof packets captured: start, complete, onboard, accounts list
- [x] targeted tests for login admission pass
- [ ] full required `tests.test_cli` gate passes in this workstation environment

## Verification

- tests:
  - targeted login admission tests: pass
  - `tests.test_web_design_live_server tests.test_web_design_command_adapter tests.test_ui_shell`: pass
  - full `tests.test_cli tests.test_web_design_live_server tests.test_web_design_command_adapter tests.test_ui_shell`: fail (6), environment listener interference on `127.0.0.1:8318`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`: pass
- manual:
  - owner proof flow executed in isolated sandbox env
- live evidence:
  - `evidence/login-start-packet.json`
  - `evidence/login-complete-packet.json`
  - `evidence/onboard-packet.json`
  - `evidence/accounts-list-after.json`

## Open Questions

- Should `accounts onboard --json` in this lane auto-consume the latest sandbox login artifact when `--auth-ref` is omitted, or remain explicit-owner-arg only?

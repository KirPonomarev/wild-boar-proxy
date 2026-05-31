# LEGACY_CODEX_RUNTIME_SURFACES_RETIREMENT_PASS

## Goal

Close the migration truth around legacy Codex/CLIProxyAPI operator surfaces after
`CODEX_OWNER_LOGIN_SESSION_BRIDGE_PASS_REOPEN_CLOSEOUT`.

This contour does not remove the `CLIProxyAPI` engine, local auth/profile data,
or external operator assets. It classifies legacy surfaces and retires only the
repo-owned operator entrypoints that are proven superseded by the owner Codex
device login session bridge.

## Canon

Decision order:

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`
8. `WORKFLOW_OS_V1_2.md`

## Scope

Included:

- inventory Codex login/onboard legacy surfaces
- classify runtime-support candidates separately
- retire generated repo-managed operator wrappers by turning them into explicit
  retired stubs
- preserve unmarked operator wrappers
- keep `CLIProxyAPI` and owner helper plumbing intact
- update current operator guidance to the sessionized login bridge
- tests, audit artifacts, commit, push

Excluded:

- deleting `~/.codex-custom-cli` or `~/.cli-proxy-api`
- removing `CLIProxyAPI`
- deleting historical audit artifacts
- web redesign
- OAuth callback work
- promotion to active

## Canonical Replacement

The canonical account connect path is now:

```text
web Connect account
-> accounts login start --provider codex --mode device --json
-> accounts login status --session <id> --json
-> accounts login complete --session <id> --json
-> accounts onboard --json --auth-ref <session auth>
-> reserve
-> readonly refresh + ledger proof
```

## Retirement Action

The repo still materializes profile-level operator wrappers during installer
init. They are no longer allowed to launch old blocking flows:

- `Add Account.command` no longer runs `codex-account-onboard --loop`
- `team-codex-login.command` no longer runs `sandbox_owner_helpers login --no-browser`
- both wrappers print a retired message and point to the canonical owner login
  session command
- unmarked/custom operator wrappers remain untouched
- older repo-managed wrappers with valid markers are upgraded to the retired
  payload

## Acceptance Criteria

- [x] inventory covers repo Codex login/onboard surfaces
- [x] runtime-support candidates are classified separately
- [x] `CLIProxyAPI` remains `still_needed`
- [x] local/external runtime assets are not deleted
- [x] generated legacy operator wrappers are retired stubs
- [x] unmarked/custom wrappers are preserved
- [x] current docs no longer present direct `accounts onboard --json` as the
  primary Add Account UI command
- [x] full verification gate passes
- [x] closeout resilience passes
- [ ] commit and push complete

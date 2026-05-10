CONTOUR_ID: ELIGIBLE_RESERVE_POOL_READINESS_RECOVERY
LIVE_OPERATION_STATUS: ADMITTED
WRITE_STEP_COUNT: 1
OWNER_COMMAND:
- `accounts onboard --json --non-interactive`

COMMAND_JUSTIFICATION:
- `COMMAND_API.md` defines `accounts onboard --json` as the owner surface for reserve-first onboarding truth
- the command contract already owns:
  - selected backend identity proof
  - reserve placement proof
  - no silent active-routing change proof
  - validate outcome
  - sync outcome unless skipped
  - post-onboard status proof summary

DECLARED_WRITE_SURFACES:
- runtime write surfaces detectable under the onboarding owner path:
  - `/Users/kirillponomarev/.codex-custom-cli/managed/backend-registry.json`
  - `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
  - `/Users/kirillponomarev/.codex-custom-cli/config.toml`
  - `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
  - launcher / managed runtime surfaces if the owned sync substep legitimately touches them

ROLLBACK_EXPECTATION:
- no second external owner surface is allowed in this contour
- if onboarding fails to produce an eligible reserve backend, contour closes `NO_GO_RESERVE_READINESS_STILL_INCOMPLETE`
- manual corrective edits are forbidden

STOP_CONDITIONS:
- invalid JSON from any owner surface
- active routing changes silently
- reserve placement proof fails
- more than one external owner surface would be required

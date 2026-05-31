CONTOUR:
Goal: Repair the primary sandbox active-lane auth-source blocker if and only if it can be fixed within the declared auth-source scope.
Size: M
Risk level: high
Decision owner: Codex
Mode: live-proof

In scope:
- sandbox auth-source truth reconfirmation
- bounded auth-source diagnostics
- direct sandbox auth.json mutation only if a valid in-scope secret source exists
- conditional backend-registry auth_ref rebinding only if truly needed
- live post-repair attestation proof

Out of scope:
- importing a new secret from outside the declared sandbox auth surface
- launcher/materialization execution
- lifecycle continuation
- policy or onboarding work

Assumptions:
- healthcheck owner truth remains authoritative
- sandbox root remains `/Users/kirillponomarev/.codex-custom-test`
- no mutation is admissible if repair depends on an external secret source

Inputs:
- docs:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `RUNTIME_CONTRACT.md`
  - `STATE_SCHEMA.md`
  - `COMMAND_API.md`
- code:
  - `wild_boar_proxy/runtime.py`
  - `wild_boar_proxy/sandbox_owner_helpers.py`
  - `wild_boar_proxy/cli.py`
  - `wild_boar_proxy/external_models/*`
- runtime evidence:
  - fresh sandbox `healthcheck --json`
  - fresh sandbox `status --json`
  - read-only diagnostic `healthcheck/status --json` with `WBP_AUTH_FILE` pointed at live auth source

Commands / files:
- `python3 -m wild_boar_proxy healthcheck --json`
- `python3 -m wild_boar_proxy status --json`
- diagnostic override of `WBP_AUTH_FILE=/Users/kirillponomarev/.codex-custom-cli/auth.json`
- auth metadata digests for sandbox and live auth files

Acceptance criteria:
- either repair completes within declared auth-source scope
- or the contour truthfully proves that repair requires an external auth-source admission

Verification:
- tests: targeted auth/healthcheck unittest quartet
- build: `git diff --check`
- manual: artifact review + code/canon references
- live packet: fresh sandbox and override packets preserved

Artifacts:
- spec: `contour.md`
- packet: `decision_packet.json`
- closeout note: `closeout.md`

Stop conditions:
- primary repair requires secret import from outside sandbox auth surface
- owner truth remains contradictory
- launcher/materialization work becomes necessary for proof

Closeout:
- verification complete: yes
- commit: pending
- push: pending
- next contour: `SANDBOX_ACTIVE_LANE_EXTERNAL_AUTH_SOURCE_SCOPE_ADMISSION_PASS`

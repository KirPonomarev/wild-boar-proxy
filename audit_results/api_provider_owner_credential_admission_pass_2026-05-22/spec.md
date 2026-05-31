# Spec: API_PROVIDER_OWNER_CREDENTIAL_ADMISSION_PASS

## Objective

Add an owner-owned credential admission surface for provider API routes without
browser secret intake:

`external-models credentials admit --provider <provider> --source owner-env --json`
`external-models credentials status --provider <provider> --json`

The admitted credential must be sandbox-only, machine-readable, and reusable by
the existing `external-models routes validate` lane.

## In Scope

- Add CLI parser and command dispatch for `external-models credentials`.
- Add owner admission helper with provider allowlist (`openrouter`) and source
  allowlist (`owner-env`).
- Materialize admitted credential to sandbox `secrets.env` only.
- Enforce sandbox write-target proof before credential admission.
- Enforce secret-file permissions (`0600`).
- Emit strict JSON packets with redaction flags and `credential_ref`.
- Add targeted tests for success and failure cases.
- Capture owner proof packets and redaction evidence.

## Out of Scope

- Web login/UI bridge.
- Browser API key input, browser file/path input, OAuth callback.
- Route builder redesign, desktop, packaging, runtime readiness claims.

## Constraints

- Canon order: `CANON.md`, `MASTER_PLAN.md`, `RUNTIME_CONTRACT.md`,
  `STATE_SCHEMA.md`, `COMMAND_API.md`, `DELIVERY_RULES.md`, `README.md`.
- Web/control layer must not own secret intake.
- Owner packet truth only; no narrative-only success.
- No secret values in packets, logs, or audit artifacts.

## Acceptance Criteria

- [x] `external-models credentials admit --provider openrouter --source owner-env --json` exists.
- [x] `external-models credentials status --provider openrouter --json` exists.
- [x] Unsupported provider rejected with non-green packet.
- [x] Unsupported source rejected with non-green packet.
- [x] Missing owner env rejected with non-green packet.
- [x] Sandbox-unproven target rejected with non-green packet.
- [x] Admit writes only sandbox `secrets.env`.
- [x] `secrets.env` permissions enforced as `0600`.
- [x] Success packet includes `credential_ref` and redaction flags.
- [x] Secret value absent from packets/artifacts.
- [x] `routes validate` succeeds after admit against local mock provider.
- [x] Required test gates pass.

## Verification

- targeted tests: `tests.test_cli_external_models`, `tests.test_external_models`.
- full contour gate: `tests.test_cli_external_models tests.test_external_models tests.test_web_design_live_server tests.test_web_design_command_adapter`.
- owner proof packets: `evidence/credential-admit-packet.json`,
  `evidence/credential-status-packet.json`,
  `evidence/routes-add-packet.json`,
  `evidence/routes-validate-packet.json`,
  `evidence/redaction-check.json`.

## Open Questions

- Provider-specific OAuth/dashboard UX remains for the next contour
  `WEB_API_PROVIDER_LOGIN_BRIDGE_PASS`.

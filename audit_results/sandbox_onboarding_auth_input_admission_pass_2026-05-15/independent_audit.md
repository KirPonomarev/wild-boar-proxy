# Independent Audit

## Auditor

- agent: `Chandrasekhar`
- role: cheap independent fact-checker
- model: `gpt-5.4-mini`

## Question

Which onboarding auth input lane is canonically narrower for the next contour:
explicit `--auth-ref` or sandbox-local `auth.json`?

## Factual Findings

- `cmd_onboard` consumes `args.auth_ref` literally when present and otherwise
  falls back to `paths.auth_file`.
- `run_onboard` forwards `--auth-ref` directly into the owner helper and later
  classifies explicit onboarding by exact `auth_ref` path match.
- the declared sandbox boundary already includes
  `/Users/kirillponomarev/.codex-custom-sandbox-20260515/auth.json` as a
  writable surface and keeps rollback root-local.
- explicit `--auth-ref` can legitimately point outside the sandbox root and
  therefore widens reference scope unless a later contour narrows that source
  explicitly.

## Auditor Verdict

- narrower lane: `sandbox-local auth.json`
- explicit `--auth-ref`: broader than the default sandbox path because it can
  anchor the onboarding lane to an external file path
- recommended decision token from the audit evidence:
  `GO_TO_SANDBOX_ONBOARDING_AUTH_JSON_ADMISSION_PASS`

## Reconciliation

I agree with the auditor on the lane ranking and on the reason: the default
sandbox-local `auth.json` lane is already aligned with the declared sandbox
boundary, while explicit `--auth-ref` is a wider reference lane. I narrowed the
final decision further by keeping `upstream_secret_source_admitted_now = false`;
this contour selects the primary input lane but does not yet admit or
materialize any secret-bearing source.

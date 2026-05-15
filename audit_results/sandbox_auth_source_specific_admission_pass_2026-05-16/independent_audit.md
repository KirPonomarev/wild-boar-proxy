# Independent Audit

## Auditor

- agent: `Planck`
- role: cheap independent fact-checker
- model: `gpt-5.4-mini`

## Question

Does current repo evidence support admitting one exact upstream auth source
surface now, or only a narrower transfer-admission contour?

## Factual Findings

- the live registry contains many exact `auth_ref` surfaces, not one unique
  source
- the current supervisor snapshot has `selected_backend_ids = []`
- `STATE_SCHEMA.md` forbids synthesizing selection truth from registry counts or
  active ids
- `COMMAND_API.md` treats eligible registry `auth_ref` files as policy-authorized
  copy inputs, not as automatic direct materialization authority
- the current sandbox-auth admission packet already says materialization is not
  earned

## Auditor Verdict

- selected outcome: `GO_TO_NARROWER_SOURCE_TRANSFER_ADMISSION_PASS`
- why:
  - one exact source cannot be admitted honestly yet
  - direct materialization would still guess inside a forbidden-root candidate
    family

## Reconciliation

I agree with the auditor. The deciding pair of facts is simple and strong:
`allowed_exact_auth_ref_count = 12` while `selected_backend_ids_count = 0`.
That is enough to reject exact-source guessing without turning the result into a
full stop.

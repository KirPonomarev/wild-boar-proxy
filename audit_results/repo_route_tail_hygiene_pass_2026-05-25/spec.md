# REPO_ROUTE_TAIL_HYGIENE_PASS Spec

## Goal

Prevent completed evidence from carrying active-route instructions into future
agent work.

## Scope

- Replace closeout-template route pointers with closure-only fields.
- Enforce closure-only closeouts in `tools/check_closeout_resilience.py`.
- Make the repository bootloader explicit that `audit_results/` is historical
  evidence, not active navigation truth.
- Keep runtime, UI, release claims, and product behavior untouched.

## Acceptance

- New or changed closeout files reject route pointers and historical route
  documents as active guidance.
- `resume from here` is terminal and machine-checked.
- Targeted hygiene tests pass.

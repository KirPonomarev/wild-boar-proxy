Admission analysis:

Observed split-lane behavior:
- `sync --json` is the only owner surface that may materialize
  `runtime_state.selected_backend_snapshot`
- `launch smoke --json` is the only surface that currently exposes the narrow
  stable-runtime activation path
- `status --json` reports approved-target effective truth only when live stable
  runtime is `OK` and fresh activation evidence is present
- `rollout rotation inspect --json` validates rotation evidence without
  requiring live stable runtime for approved-target policy-drift use

Blind retry verdict:
- reopening another blind `sync-only` contour is not lawful enough because it
  already twice produced `rotation green / runtime regressed`
- reopening another blind `launch-smoke-only` contour is not lawful enough
  because it does not answer whether rotation freshness survives the sequence

Composite admission verdict:
- canon does not prohibit a multi-owner contour absolutely
- canon prohibits silently merging write lanes
- `NEXT_CONTOUR_CANON_PLAN.md` explicitly allows a bounded repair program of
  small contours and says contours must not be silently merged unless closeout
  explicitly justifies why the split could not be kept safely
- here that justification exists:
  repeated split-lane retries already proved insufficient to answer whether the
  system can reach simultaneous green truth

Therefore:
- a bounded explicitly admitted composite proof contour is canonically
  admissible
- it must be framed as proof, not as a new generic merged repair lane
- it must declare both owner surfaces, both write scopes, exact order, and
  stop rules
- if the sequence fails, the next lawful contour becomes repo contradiction
  repair


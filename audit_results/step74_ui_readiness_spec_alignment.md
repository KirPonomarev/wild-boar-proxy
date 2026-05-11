UI_READINESS_SPEC classification:

`UI_READINESS_SPEC.md` is aligned with ADR-0002 as a first-pass UI specification
boundary.

Tiny alignment patch applied:

- MASTER_PLAN now says execution core is frozen enough for basic companion UI
  through ADR-0002 while later release/rich UI gates remain separate.
- UI_READINESS_SPEC now states that accepted ADR-0002 scale proof may be used as
  project context, but not as current full-scale live availability.
- UI_READINESS_SPEC now keeps new scale-to-20 proof out of scope, while allowing
  basic UI work to begin.

No UI implementation was performed in this contour.

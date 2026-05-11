<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# ADR: Scale Evidence Finalization For Development Gate

## Status

Accepted

## Date

2026-05-11

## Context

The project has accumulated live validation evidence across the C16, C17, C20,
C22, and C24 contour family.

That evidence established the development-relevant scale architecture claim:

- 24/25-account managed-pool capacity was exercised
- stage-20 owner-path evidence was captured
- same-day live validation was executed
- no-storm behavior was observed under the declared validation shape
- rollback was not required in the accepted validation path
- independent audit passed or preserved exact remaining blockers
- later quota exhaustion was explicitly treated as non-blocking when a working
  launch-capable subset remained available

After that validation campaign, some accounts naturally exhausted quota or
changed live state. The old forward policy could interpret those later
conditions as a reason to reopen execution-core repair before application work.
That is too strict for development. It turns the cost of successful validation
into a reason to cancel the validation result.

## Decision

The C16/C17/C20/C22/C24 evidence family is accepted as closed scale
architecture proof for continued application development.

Subsequent quota exhaustion, account depletion, reserve depletion, or
stable-policy drift after accepted live validation does not invalidate:

- the accepted scale proof
- Gate A development closure
- permission to continue basic companion UI and application-development work

Those later conditions only block fresh claims that the same live account set is
currently available for another full-scale validation, release-facing readiness,
or production-like load run.

The canonical phrase is:

> Subsequent quota exhaustion or account depletion after accepted live
> validation does not invalidate the accepted scale proof, Gate A closure, or
> permission to continue application development. It only blocks fresh claims
> that the same live account set is currently available for another full-scale
> run.

## Consequences

- Positive:
  - development can proceed to the basic companion UI without another runtime
    repair loop
  - accepted live validation remains meaningful even after it consumes quota
  - current runtime drift remains visible without being treated as proof
    invalidation
  - future full-scale live claims still require fresh live evidence
- Negative:
  - the repo now distinguishes development-readiness from current-live
    full-scale availability
  - release/pilot language must be careful not to overclaim current account
    capacity
  - runtime status may still report policy drift while application development
    proceeds
- Follow-up work:
  - open a fresh runtime contour only when making a new current-live scale,
    release, or pilot-readiness claim
  - keep UI surfaces truthful about quota, drift, reserve depletion, and current
    pool state

## Alternatives Considered

1. Keep reopening runtime repair until current live policy drift is clear.
   Not chosen. It blocks application development on the natural after-effect of
   the validation campaign.
2. Ignore quota and drift completely.
   Not chosen. They remain real blockers for fresh full-scale live claims and
   release-facing readiness.
3. Accept scale evidence for development while requiring fresh live truth for
   new full-scale claims.
   Chosen. It matches the evidence and keeps runtime truth honest.

## Evidence

- C16: 24-account scale baseline proof accepted for development evidence
- C17: 24-account no-storm validation shape with zero errors/timeouts under the
  declared command budget
- C20: same-day live 20-account contour, stage-20 owner path, postflight
  attestation, rotation evidence, and independent audit accepted for the scale
  architecture proof
- C22: Gate A handoff recognized as ready to transition when drift is not a
  repo-owned contradiction
- C24: quota exhaustion preserved as non-blocking when a launch-capable working
  subset remained available

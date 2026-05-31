# Spec: Codex Custom Reproof Gap Matrix

## Objective

Build an exact read-only `promised vs proven vs missing` matrix for the
thread-defined Codex Custom contour set `1..8`, using current code and tests as
the primary truth and historical audit artifacts as supporting evidence only.

## In Scope

- Classify contours `1..8` as `pass`, `partial`, `blocked`, or `fail`
- Bind each proven or missing statement to exact evidence refs
- Separate:
  - launch vs dry-run
  - validate/check vs inference
  - GPT-account route vs external API route
  - session endpoint vs launched workbench
  - visible controls vs working controls
- Produce one machine-readable matrix and one short summary

## Out of Scope

- Runtime mutation
- Live prompt reruns
- Launch reruns
- UI edits
- Recovery edits
- Route edits
- Release-claim edits
- New feature work

## Constraints

- `audit_results/` is historical evidence only, never active route truth
- Current code and current tests win when old evidence conflicts
- No waiver is accepted inside this contour
- No remediation roadmap is written into the repo
- Output is limited to one matrix and one short summary

## Assumptions

- The active branch truth is represented by the current working tree and the
  current pushed branch head
- Historical artifacts may still be useful as supporting evidence even when
  their forward-looking text is obsolete
- A bounded final implementation contour still exists if the remaining gaps stay
  limited to launch, route, and recovery execution proof

## Acceptance Criteria

- [x] All eight contours are classified with exact promised/proven/missing rows
- [x] Every proven or missing row has evidence refs
- [x] Launch is separated from dry-run
- [x] Validate/check is separated from inference
- [x] GPT-account proof is separated from external API proof
- [x] Session endpoints are separated from launched workbench proof
- [x] Visible controls are separated from working controls
- [x] The remaining implementation scope stays bounded to one follow-up contour

## Verification

- tests: read-only evidence collection from current tests only
- build: `git diff --check`; closeout resilience validation
- manual: independent read-only artifact audit
- live evidence: none; this contour is intentionally non-live

## Open Questions

- None inside this contour; waiver decisions and implementation choices remain
  outside the repo and outside this audit pass

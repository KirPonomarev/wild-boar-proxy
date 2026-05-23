# Spec: Codex Custom Authorized GPT Account Live Prompt Pass

## Objective

Run one bounded live Codex Custom prompt through the server-side WBP trace
observer and GPT account route, but only after the active thread contains the
exact `CANON.md` owner authorization phrase for live runtime/account/API
actions.

## In Scope

- authorization gate
- one live prompt after authorization
- WBP trace observer proof
- protected Codex snapshot before/after
- post-run runtime reclear
- redaction and independent audit

## Out of Scope

- live runtime/account/API execution without owner authorization
- account rotation or load
- external API route proof
- UI/browser click proof
- current Codex mutation
- package or installer work

## Constraints

- `CANON.md` says generic phrases such as `начинай работу` do not authorize
  live commands.
- If the exact phrase is absent, live prompt must not run and token burn must
  remain zero.
- No success can be claimed from config, response text, or exit code alone.
- Trace observer is a proof surface, not runtime-health owner.

## Acceptance Criteria

- [x] Authorization gate evaluated.
- [x] Live prompt not executed without owner phrase.
- [x] Machine blocker packet created.
- [x] No runtime/account/API command executed.
- [x] Token burn remains zero.
- [ ] Live prompt runs after owner authorization.

## Verification

- tests:
  - closeout resilience and git diff checks for this no-code contour
- build:
  - not applicable; no code was changed
- manual:
  - independent fact-checker verifies authorization gate
- live evidence:
  - blocked by missing owner authorization phrase

## Open Questions

- Owner must decide whether to provide the exact standing authorization phrase
  in the active thread, then resume the live prompt phase.

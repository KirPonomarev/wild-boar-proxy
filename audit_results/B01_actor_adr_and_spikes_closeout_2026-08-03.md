<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B01 Actor/Source-Of-Truth ADR And Reality Spikes Closeout

## Goal

Record the B01 decisions that are expensive to reverse: canonical
actor/binding/assignment/session identity separation, legacy migration
strategy, registry ownership, failover owner, OpenRouter compatibility, DIP
behavior, visible-delivery mode, ledger storage, and CLI isolation; and run
safe reality spikes without touching main Codex credentials.

## Result

- status: decided and recorded
- final verdict: ADR-0003 (multi-actor entity model as one canonical source of
  truth with a legacy projection) accepted as the B01 decision record; reality
  spike findings recorded; visible-delivery spike is BLOCKED by the owner
  safety override (no Codex/Custom Codex processes may be started), so the
  plan's conservative proven delivery mode is the default until physical proof
- closure state: CLOSED

## Contour Capsule

- goal: B01 ADR + reality spikes for the multi-actor entity model
- branch: `codex/b01-actor-adr`
- head: `ad20fb75b5d2c44e1e4c9b89e4db03c095e42381` (base before contour commit)
- touched files: `ADR-0003-multi-actor-entity-model-source-of-truth.md`,
  `audit_results/B01_actor_adr_and_spikes_closeout_2026-08-03.md`
- tests run: none required for a decision-only contour; `make check` green
  (repo hygiene preserved)
- blocked risks: physical visible-delivery proof blocked by the main Codex air
  gap override; isolated Codex CLI (B16) stays DEFERRED
- closure state: CLOSED

## Verification

- tests:
  - no code change; `make check` (compileall + collect) green
- build:
  - n/a (docs-only contour)
- manual:
  - decisions cross-checked against plan contract sections 4, 5, 6, 7, 8, 10,
    12, 14, 15 and the owner safety override message
- live verification:
  - no live mutation; no Codex process started; no main profile access

## Artifacts

- spec: plan contract (external master document) sections 4–15
- packet: no live packet artifact required
- report: ADR-0003 + this closeout

## Git

- branch: `codex/b01-actor-adr`
- commit: contour commit contains ADR-0003 and this closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (no credentials, no profile access)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: visible-delivery physical spike is not executable in
  this environment (owner safety override forbids starting any Codex/Custom
  Codex process); resolved by adopting the plan's conservative proven delivery
  mode and deferring the physical spike to the workflow stage evidence
  contract
- resume from here: CLOSED

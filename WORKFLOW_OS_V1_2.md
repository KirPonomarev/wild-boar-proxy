<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Workflow OS v1.2

Workflow OS is the execution discipline for work in this repository and related
projects.
It is designed to keep high-risk work honest without turning ordinary changes
into bureaucracy.

## Core Principle

Use adaptive discipline:

- strict mode for runtime, proof, rollout, release, migrations, and public
  contracts
- medium mode for multi-file feature work
- light mode for narrow low-risk work
- exploration mode for read-only investigation before implementation

If ritual costs more than the value it protects, simplify it.
If chaos costs more than ritual, tighten it.

## 1. Proportionality First

Process depends on size and risk.

### XS

- 1 file
- up to 30 minutes
- no behavior change or only trivial low-risk local change

### S

- 1-2 files
- up to 2 hours
- bounded behavior change
- no live-risk
- no public contract shift

### M

- 3-5 files
- or noticeable behavior change
- or new test scenario
- or internal contract touch

### L

- 5+ files
- cross-module work
- migration, shared surface, runtime truth, policy, or rollout contour

### XL

- architectural fork
- public API shift
- live-runtime mutation with rollback implications
- release, package, or ship contour

If in doubt between two sizes, choose the larger size.

## 2. Rules File First

Each project should have a persistent rules file covering:

- tech stack
- commands
- conventions
- boundaries
- ask-first rules
- never-do rules

If a rule is not written down, it is not yet stable project law.

## 3. Context Hierarchy

Load context in this order:

1. rules
2. spec
3. relevant source
4. exact errors/tests

Do not flood the agent with entire codebases or entire docs when a small focused
 subset is enough for the task at hand.

### 3.1 Thread / Compaction Resilience

Treat thread context as volatile. Treat repo packets and commits as durable.

- Do not create repo-local thread checkpoint files during normal work.
- Keep temporary recovery notes outside the repo, for example
  `/private/tmp/wbp-thread-checkpoints/`.
- Create repo artifacts only at contour boundaries, and only when the contour or
  closeout discipline requires them.
- Prefer bounded, path-scoped tool output:
  `git status --short --untracked-files=no`, `git diff --stat`,
  `git diff -- <paths>`, `rg`, `sed -n`, and `jq` selectors.
- Do not commit raw tool dumps, archived thread extracts, private research
  notes, external-reference artifacts, tokens, logs, or large JSONL extracts.
- At closeout, include `resume from here` so a new thread can continue without
  replaying long chat history.

## 4. Assumptions Explicit

State key assumptions before work begins, especially when they affect:

- architecture
- API
- runtime
- rollout
- security
- data model

Important hidden assumptions are correctness risks.

## 5. Confusion Must Surface

When `docs`, `code`, `tests`, `live behavior`, or `spec` disagree:

1. name the conflict
2. state the options
3. identify the decision owner
4. record the resolution

Do not silently pick an interpretation.

## 6. Decision Ownership

Use explicit decision ownership.

### Human

- product behavior
- incomplete requirements
- UX/design tradeoffs

### Maintainer

- codebase conventions
- merge strategy
- acceptance of refactors

### Operator

- live-runtime mutation
- rollout and rollback actions
- real-environment recovery actions

### Agent

- local implementation choices inside approved scope
- narrow internal naming/structure decisions
- task decomposition inside an agreed plan

If ownership is unclear, do not continue as if it were obvious.

## 7. Exploration Mode

Use exploration mode for read-only investigation when the problem is not yet
ready for implementation.

Rules:

- read-only
- no code promises
- hypotheses allowed
- contradiction finding allowed
- no stealth transition into implementation

Allowed exits:

- `ready_for_spec`
- `ready_for_repair_contour`
- `insufficient_signal`

## 8. Spec Before Code

`M/L/XL` work needs a spec with:

- objective
- in scope
- out of scope
- constraints
- acceptance
- verification
- open questions

`S` work may use a compact 5-10 line spec.
`XS` work may use intent + acceptance + verify only.

Spec is living.
If the decision changes, update the spec before changing the implementation.

## 9. Small Atomic Contours

One contour should:

- do one logical thing
- be verifiable
- be closable
- be reviewable
- be suitable for an independent closeout
- avoid mixing unrelated subsystems

If the contour title wants an "and", split it unless there is a strong reason
not to.

## 10. Vertical Slices By Default

Default to vertical slices: one complete useful path at a time.

### Foundation-First Exceptions

These may use foundation-first contours:

- schema/migration
- shared contract
- runtime truth surface
- policy gate
- serialization/locking work
- shared infra prerequisite

Vertical slicing is the default, not a religion.

## 11. Risk-First Execution

Do first what:

- carries the highest risk
- is hardest to roll back
- can falsify the approach early
- can block everything else

This is especially required for:

- live-runtime
- rollout
- migrations
- release
- architectural forks

## 12. Contract-First Interfaces

Describe boundaries before relying on them.
Contracts should define:

- required fields
- error semantics
- machine-readable codes
- success criteria
- forbidden inferences
- ownership boundary

Shared surfaces and public APIs require this explicitly.

## 13. Bugfix = Reproduce First

Bugfix flow:

1. reproduce
2. failing test or stable repro
3. root-cause fix
4. regression guard
5. full verification

Do not start with "I think I know the fix".

## 14. Incremental Implementation

Implementation loop:

`implement -> test -> verify -> commit -> next slice`

Do not accumulate large uncommitted piles.
Do not silently mix `runtime`, `docs`, `UI`, and `release` work inside one
unbounded change set.

## 15. Verification Is Evidence

"Seems to work" is not done.

Evidence is proportional to the task.

### XS

- quick manual check or focused test

### S

- test, build, or manual verify

### M

- targeted tests plus brief closeout note

### L / XL

- explicit verification set
- artifacts
- closeout packet
- machine-carried evidence for live work where applicable

Do not require heavyweight evidence packets where they add no signal.

## 16. Review On Risk, Not Ritual

Review is always required, but depth depends on risk.

### XS / S

- focused self-review or paired sanity check

### M

- correctness
- readability
- architecture

### L / XL

- correctness
- readability
- architecture
- security
- performance

## 17. ADR Only For Expensive Decisions

Write an ADR when the decision is expensive to reverse or changes project
philosophy, for example:

- architecture boundary
- data model
- API philosophy
- rollout model
- operating model

Do not write ADRs for ordinary local implementation choices.

## 18. Ship Discipline

Work is closed only when it has:

- verification
- scope check
- atomic commit or logically complete commit set
- push
- final closeout

Do not require `push` after every micro-step.
Require it after a completed contour.

## 19. Staleness Rule

If `rules`, `spec`, `ADR`, `runbook`, or `plan` no longer reflect reality, they
are `suspect until refreshed`.

Old text does not become authoritative merely by existing in the repo.

## 20. Process Override Rule

The process may be simplified only when all of these are true:

- low risk
- cheap rollback
- clear scope
- no live mutation
- no contract change
- no cross-subsystem impact

When doing so, record:

```text
PROCESS_OVERRIDE:
reason = low-risk narrow change
applied_mode = XS/S lightweight path
```

Do not simplify in silence.

## Stop Tokens

### STOP_AND_DIAGNOSE

Use when there is correctness or truth risk:

- failing test or broken build
- unexpected blocker
- contract mismatch
- doc/code/runtime contradiction
- live mutation with unclear rollback
- hidden assumption affecting correctness
- cross-subsystem scope creep
- contradictory command output

After triggering:

1. stop new work
2. preserve evidence
3. localize root cause
4. fix root cause
5. add guard when needed
6. resume only after verification passes

### NOTE_AND_CONTINUE

Use for non-blocking observations:

- unrelated cleanup noticed
- possible refactor idea
- naming rough edge
- future optimization idea
- adjacent inconsistency with no immediate correctness risk

Record it and continue the contour.

## Standard Contour Template

Use [templates/CONTOUR_TEMPLATE.md](templates/CONTOUR_TEMPLATE.md).

Fields:

```text
CONTOUR:
Goal:
Size: XS / S / M / L / XL
Risk level: low / medium / high
Decision owner:
Mode: exploration / implementation / live-proof / release
In scope:
Out of scope:
Assumptions:
Inputs:
Commands / files:
Acceptance criteria:
Verification:
Artifacts:
Stop conditions:
Closeout:
```

## Full Mode Requirements

Full mode is mandatory for:

- live-runtime work
- staged rollout / proof
- public API changes
- multi-file feature work with behavior change
- bugfix with unclear root cause
- migrations
- release / package / ship
- architectural decisions

## Lightweight Mode

Lightweight mode is acceptable for:

- typo
- docs-only clarification
- single-file obvious fix
- harmless local cleanup
- narrow non-behavioral edit
- isolated low-risk test adjustment

## Design Gate

Before rich UI expansion or design polish, require:

`EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`

Until that token is truthfully earned:

- no rich UI expansion
- no design polish contour
- no mixing UI implementation into execution-core repair

After that token:

- basic companion UI contour allowed
- design work opens explicitly
- runtime repair no longer piggybacks on UI work

## Uncommitted Tail Limit

If the worktree contains more than one logically complete contour without
closeout:

- split the work
- or close one contour before continuing

This prevents smart chaos from accumulating in silence.

## Cadence Review

Every week or after every 5-7 closed contours, ask:

- what helped
- what turned into ritual with no signal
- what slowed us down
- what should be simplified
- what should be tightened

Workflow OS is living.
If the process costs more than the risk it protects, revise it.

## Repo-Specific Notes For Wild Boar Proxy

- Live-runtime work includes real-path interactions with companion-managed data,
  stable config, auth inventory, runtime state, and rollout surfaces.
- Strict JSON command packets remain the primary truth interface when they
  exist.
- UI readiness does not authorize UI to outrun execution-core repair.
- Closeout is not real until verification, commit, and push all exist in the
  same contour.

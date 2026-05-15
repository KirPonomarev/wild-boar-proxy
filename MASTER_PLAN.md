<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Wild Boar Proxy Master Plan

PLAN_NAME: Wild Boar Proxy Master Plan
PLAN_VERSION: 1.48
PLAN_DATE: 2026-05-16
PLAN_OWNER: Product and Platform Team
PLAN_STATUS: Stable/sandbox truth recalibration wave active; recent contours truthfully narrowed sandbox onboarding auth blockers through family repair and runtime reproof, but canonical selector refresh via `sync --json` reopened a managed-lane policy/runtime contradiction; next primary contour is `STABLE_POLICY_RUNTIME_RECONCILIATION_PASS`; exact auth-source admission, sandbox auth materialization, onboarding rerun, route mutation, and stage/pilot claims remain parked until stable policy/runtime truth is reconciled and cross-lane drift is cleared
PLAN_CLASS: Experimental managed companion control app

## Summary

Wild Boar Proxy is an experimental managed companion control app built on top of CLIProxyAPI.
We do not fork the host client.
We do not build a second proxy engine.
We build the managing layer: modes, policy, onboarding, diagnostics, recovery, and staged scaling.
Architecture is designed for 20 accounts from day one.
The current contour has operational evidence of correct 16-account work.
Formal scale proof remains staged and must be backed by runtime attestation, rotation evidence, and rollback readiness before any 20-account claim.

## Managed Companion Positioning

Wild Boar Proxy is currently positioned as a managed companion control app for the host client.
It manages a user's own local operating contour: launch configuration, runtime modes, account lifecycle, diagnostics, and recovery.

This positioning does not change the architecture boundary.
The host client remains external.
Wild Boar Proxy does not patch, fork, impersonate, or replace the host client.

The app is intended for local management of a user's own accounts and runtime setup.
It must not be positioned as an account-sharing tool, a bypass mechanism, a resale layer, or a way to obtain unauthorized access.

Active planning docs should keep the neutral term `host client` where the architecture boundary matters.
User-facing product copy may use companion-oriented wording only when it preserves the same boundary.

## Field Evidence Status

The project has field evidence that the current local contour works correctly with 16 accounts.
This is above the formal stage-15 contour and materially lowers uncertainty for the 20-account architecture.
It is not, by itself, a `STABLE_20_PROVED`, `SCALE_COMPLETE`, or `PILOT_READY` claim.

The correct interpretation is:

- 16-account operational evidence exists.
- The formal proof contour must still capture machine-carried evidence.
- Stage-20 remains a controlled rollout target, not an inferred outcome.
- Fallback, rollback, and strict runtime truth rules remain mandatory.

## Same-Day Scale Validation Rule

The active plan accepts a same-day high-load validation contour for 20 accounts.
We do not require a fixed long-window metrics rule as an active gating requirement in this revision.

The accepted interpretation is:

- 20-account proof may be established through one approved live validation contour on the real environment.
- The contour must still produce machine-carried evidence.
- Stress duration is operator-defined and should be long enough to exercise routing, rotation, recovery, and truthful status.
- Architecture claims do not replace live evidence; they only justify the contour design.
- same-day validation may begin only after the reserve-first stage-20 owner path is canonical and available
- a working managed pool alone does not waive the explicit eligible reserve backend requirement for `rollout stage advance 20 <id> --json`
- `managed pool` and `active window` remain distinct truths; a wider managed inventory is not itself proof of staged active-routing progression

Required evidence for same-day 20-account validation:

- `healthcheck --json`
- `status --json`
- `accounts list --json`
- `rollout rotation inspect --json`
- truthful pool counts showing the observed 20-account contour
- runtime attestation under load
- rotation participation evidence under load
- fallback readiness and deterministic stable recovery readiness
- redacted diagnostics export
- commit hash, observation date, and environment note

This contour may support a `scale-to-20 validated` claim.
It must not silently imply `pilot_ready` or `production_ready`.

Current implication:

- the same-day scale lane remains accepted
- the direct re-entry attempt is not currently open
- repair of proof posture and lifecycle truth comes first
- if a later scale re-entry closes with a non-repo-owned `NO_GO` while
  execution-core truth remains green and unambiguous, that scale blocker does
  not by itself force more execution-core repair before `basic companion UI`
  begins; the unresolved scale blocker must instead remain explicit as a
  separate later contour

## Current Recalibration Correction

Recent machine-carried evidence closed part of the stable/sandbox chain and also
exposed a new boundary that this plan now treats as explicit.

What was truthfully gained:

- approved target family reconciliation was completed once through
  `stable repair --apply --json`
- runtime reproof later promoted the approved repair target to effective runtime
  truth through `launch smoke --json`
- stale selected-backend participation evidence was refreshed through the
  canonical owner path `sync --json`

What remains blocked:

- the sync-produced selected-backend snapshot is now fresh, but
  `rollout rotation inspect --json` reports
  `ROTATION_EVIDENCE_CONTRADICTED` with `policy_drift_detected`
- `status --json` reports `claim_gate = blocked`
- `status --json` reports `policy_drift = detected`
- post-sync runtime truth is in the managed lane while the sandbox auth chain
  still depends on stable-lane restoration
- `stable repair --dry-run --json` again reports pending reconciliation work

Interpretation rule:

- this is not treated as stale-selector ambiguity anymore
- this is not treated as sandbox auth-source readiness
- this is treated as a cross-lane stable-policy/runtime contradiction reopened
  by canonical `sync --json`

Current implication:

- the next primary contour is `STABLE_POLICY_RUNTIME_RECONCILIATION_PASS`
- `SELECTOR_REFRESH_OWNER_PATH_PASS` is considered closed and must not be
  repeated by inertia
- `EXACT_AUTH_REF_SOURCE_ADMISSION_PASS` remains parked until stable
  policy/runtime truth is reconciled again
- sandbox `auth.json` materialization remains parked

## Anti-Loop Rule

The active plan now rejects cosmetic contour churn inside the stable/sandbox
auth chain.

Progress is counted only when a contour closes with machine-carried improvement
in at least two of the following surfaces:

- `policy_drift`
- `claim_gate`
- `stable repair --dry-run --json` target reconciliation work
- runtime mode/source truth relevant to the active lane

The following are forbidden as progress claims by themselves:

- re-running `sync --json` without a new contradiction diagnosis
- re-running selector refresh after freshness is already restored
- treating runtime activation success alone as exact auth-source readiness
- reopening sandbox auth admission while stable policy/runtime truth remains
  contradicted

If a contour changes the blocker wording but does not improve at least two of
the surfaces above, the chain must be treated as loop risk and moved back to
`STOP_AND_DIAGNOSE`.

## Active Truth State

This section is the active execution pointer for the current contour chain.
When lower sections contain historical closeout notes with older `next primary
contour` text, this section wins.

Current active truth:

- stable sandbox auth chain is not currently admission-ready
- canonical selector refresh through `sync --json` already happened
- selected-backend participation evidence is fresh
- refreshed participation evidence is contradicted by active `policy_drift`
- `claim_gate` is blocked
- post-sync runtime truth is currently in the managed lane
- stable repair again reports pending reconciliation work

Current active implication:

- the next primary contour is `STABLE_POLICY_RUNTIME_RECONCILIATION_PASS`
- no further selector refresh by inertia
- no exact auth-source admission
- no sandbox `auth.json` materialization
- no onboarding rerun

## Lane Authority Quick Map

The current chain crosses two operational lanes. They must not be merged by
narrative convenience.

| Surface | Lane | Current role | Authority for next step |
| --- | --- | --- | --- |
| `stable repair --dry-run --json` | stable | policy/source-copy reconciliation truth | authoritative |
| `status --json` | runtime | current mode, claim-gate, effective-source truth | authoritative |
| `rollout rotation inspect --json` | participation | validates selected-backend evidence against policy/runtime truth | authoritative |
| `sync --json` selected-backend snapshot | managed participation | refreshes bounded selector evidence only | not sufficient by itself |
| `launch smoke --json` activation evidence | stable runtime activation | proved prior runtime activation success | historical support only, not current selector authority |

Current interpretation rule:

- fresh selector evidence does not outrank contradicted rotation truth
- managed-lane refresh does not by itself restore stable-lane auth readiness
- exact auth-source work may resume only after stable policy/runtime
  reconciliation clears the active contradiction

## Historical Next-Contour Marker Rule

Lower sections in this document contain historical closeout notes such as:

- `the next primary contour is ...`

Those notes remain valuable chronology, but they are not the active execution
pointer once a newer top-level correction or recalibration section exists.

Interpretation rule:

- top-level `PLAN_STATUS`
- `Current Recalibration Correction`
- `Anti-Loop Rule`
- `Active Truth State`

all outrank historical milestone-closeout `next primary contour` text below.

## Managed Pool Operating Contour

The current local contour has exercised a managed pool of 25 accounts under real-load testing.

Default operating contour uses a 10-account active window.
The wider managed pool remains available for ranking, replacement, and staged expansion.

Accounts outside the current active window may remain managed, validated, and eligible for promotion into active routing when higher-ranked accounts degrade, hit quota limits, fail authentication, or are placed on hold.

Observed `401`, `429`, quota exhaustion, or other account-level failures inside the wider managed pool do not, by themselves, invalidate the runtime architecture claim, provided that runtime truth remains correct, fallback remains available, and the system continues selecting a healthy working subset without stale-green behavior.

Current evidence indicates 25-account managed-pool readiness for this experimental contour.
Canonical closeout for this claim still requires committed-and-pushed evidence and governing-document closeout.
It does not claim that all 25 accounts will remain simultaneously healthy under all upstream conditions.
The canonical default operating contour remains the active window, while the wider managed pool provides resilience, replacement depth, and controlled scale headroom.

## Field Evidence Capture Requirements

The 16-account field contour may be promoted from observation to formal evidence only when a redacted evidence packet exists.

Required evidence artifacts:

- `healthcheck --json`
- `status --json`
- `accounts list --json`
- `rollout rotation inspect --json`
- pool counts: active, reserve, retired, healthy, degraded, down
- selected backend ids and rotation participation evidence
- fallback readiness and deterministic stable recovery readiness
- redacted diagnostics export
- commit hash, observation date, and environment note

Evidence packets must not include auth files, private tokens, raw unredacted logs, real account secrets, or private runtime dumps.

Thread exports, planning logs, chat transcripts, and extracted user-turn histories are not accepted as implementation evidence, rollout proof, or scale evidence packets.
They may help reconstruct chronology, but they do not replace a redacted machine-carried evidence packet.

## Canonicalization Rule

This master plan becomes canonical only after the governing document revision is committed and pushed.
A local-only edit is not a closed planning contour.

Canonical closeout requires:

- no uncommitted changes in governing documents
- a commit hash that contains the accepted plan revision
- a pushed branch or merged target branch visible on GitHub
- a short closeout note that names the plan version and commit hash

Until those conditions are true, the plan may guide work but must be treated as pending canonicalization.

## Evidence Packet Acceptance Ownership

The 16-account evidence packet is accepted by the Product and Platform Team.

Responsibility split:

- the operator captures field evidence from the real contour
- the maintainer verifies machine fields, redaction, and reproducibility
- the Product and Platform Team accepts or rejects the evidence packet

An accepted evidence packet must state its scope.
It may prove the observed 16-account contour.
It must not silently upgrade the claim to `STABLE_20_PROVED`, `SCALE_COMPLETE`, or `PILOT_READY`.

## Product Strategy

1. Do not fork the host client.
2. Do not patch the official client app.
3. Build a separate companion control app.
4. Use the host client as the external client layer.
5. Use CLIProxyAPI as the backend engine.
6. Keep runtime data outside the app bundle.
7. Treat the current stage as an experiment.
8. Design the architecture for 20 accounts immediately.
9. Prove load and stability incrementally through staged rollout.

## Positioning

1. We are not building a universal GUI for CLIProxy.
2. We are not building another generic desktop shell for OAuth, config, and log management.
3. We are building a managed control app for profile orchestration, account lifecycle, recovery, diagnostics, and rollout safety.
4. The value is not the GUI itself. The value is the policy layer, truthful runtime status, staged scaling, and operator UX.
5. Every generic GUI feature must pass one filter: Is this needed for managed operations?
6. Any workstream that starts resembling a universal CLIProxy manager is scope drift.

## Primary Goals

1. Turn the current custom contour into a pilot-ready companion app with predictable launch, one-click onboarding, truthful status, fallback, diagnostics, and operator UI.
2. Make the architecture ready for 20 accounts without future schema rewrite.
3. Expand the active pool gradually through updates and rollback points.

## Success Definition

1. The app finds or imports the existing setup.
2. The user completes one-click onboarding.
3. A new account always enters reserve first.
4. Managed sync completes without manual JSON editing.
5. The host client launches through the chosen profile.
6. The UI truthfully shows desired mode, effective mode, endpoint, health, and pool state.
7. Fallback to stable works predictably.
8. The architecture supports 20 accounts without data format redesign.

## Non-Goals

1. Do not rewrite the proxy engine from scratch.
2. Do not build a second proxy engine next to CLIProxy.
3. Do not ship a public production release at this stage.
4. Do not include auth, state, or logs in release artifacts.
5. Do not build a cloud backend, sync service, account platform, or remote control service.
6. Do not make proven 20-account operation a blocker for the first pilot release.

## Terminology Normalization

Brand-specific references to the historical client are intentionally removed from active planning docs.
This plan uses neutral terms to keep the project vendor-neutral and experimental.

| Term | Meaning |
| --- | --- |
| host client | the installed desktop client used by the profile |
| profile orchestration | the logic around profile, runtime mode, launcher path, and proxy routing |
| managed control app | Wild Boar Proxy |
| Launch Client | launch the installed desktop client through the selected profile and runtime path |
| stable and managed runtime | properties of our orchestration contour, not of the host client itself |

Agent rules:

1. Do not reintroduce old branded names into the active master plan, PRD, or product positioning without explicit owner decision.
2. When historical docs use older branded wording, normalize it into the neutral terms above while preserving technical meaning.

## Boundary Decisions

1. CLIProxyAPI remains the engine. Wild Boar Proxy remains the managing layer.
2. Every new feature must be classified first as engine layer or control layer.
3. We do not duplicate generic transport, routing, or auth engine behavior without a hard blocker.

Engine layer ownership:

- Local proxy server.
- HTTP API surface.
- OpenAI-compatible endpoints.
- Provider protocol translation.
- OAuth and device login flows.
- Auth file acquisition and baseline storage.
- Low-level routing inside the active pool.
- Session affinity.
- Reselect behavior.
- Multi-account balancing.
- Upstream execution behavior.

Control layer ownership:

- Companion UI.
- Profile orchestration.
- Stable and managed modes.
- Truth layer for runtime mode.
- Supervisor layer above CLIProxy.
- Lifecycle policy: active, reserve, retired, hold.
- Onboarding orchestration.
- Health policy.
- Fallback.
- Recovery.
- Diagnostics.
- Installer.
- Legacy import.
- Logs access.
- Command API for UI and automation.

Forbidden duplication:

1. Do not write a second proxy server.
2. Do not write a custom transport executor instead of CLIProxy without a blocker.
3. Do not duplicate generic OAuth or auth engine behavior.
4. Do not duplicate generic multi-account router or balancer behavior.
5. Do not treat CLIProxy logs as the main API if a formal command or state path can exist.

Blocker rules:

1. Deeper engine-layer work is allowed only after a concrete blocker is identified.
2. Valid blocker types: stability, observability, embedding, unsupported API, licensing constraint, inability to automate.
3. Convenience alone is not enough reason to duplicate engine behavior.

## Execution Contract V1

Runtime contract, state contract, state transitions, failure model, and command API are one execution core.
No new truth surface may be added unless it reduces ambiguity or removes a real blocker.
The execution core must freeze before UI, installer, or package work becomes active.

## Git Closeout Discipline

Repo work must be synchronized to GitHub in the same closeout cycle as verification and commit.
A local-only commit is not a closed execution contour.

Execution closeout requires:

- the relevant tests or documented verification pass
- the diff is reviewed for scope and private-data safety
- changes are committed with a focused message
- the branch is pushed
- the final closeout names the verification command, commit hash, and branch

Do not mix unrelated execution, documentation, and packaging changes in one commit unless the contour cannot be split safely.

## Real Runtime Config Protection Rule

Development and tests must not mutate real `~/.codex-custom-cli`, `~/.cli-proxy-api`, auth, proxy, profile, or host-client config files unless an operator explicitly approves a live-runtime operation.

Default development and automated verification must use isolated temporary paths through `WBP_PROFILE_DIR`, `WBP_MANAGED_DIR`, `WBP_STABLE_CONFIG`, and related `WBP_*` overrides.

Any live-runtime operation must declare before execution:

- the exact command
- the exact real files or directories that may be read
- the exact real files or directories that may be written
- the rollback or backup expectation

No live-runtime command may be treated as harmless merely because it emits JSON.

## Runtime Contract

1. Stable endpoint is 8318.
2. Managed endpoint is 8320.
3. Desired mode is stored separately from effective mode.
4. Effective mode is written only after successful live preflight.
5. Listener truth beats cached state.
6. If the managed listener is absent, managed is down regardless of stale state.
7. If managed healthcheck fails, launcher writes failed or degraded state and falls back to stable.
8. Stale pid files are cleaned before decisions are made.
9. Locking must prevent split-brain between sync, launcher, and healthcheck.
10. Closing the UI must not silently kill a healthy backend without explicit user action.
11. After reboot, the system either restores cleanly or reports down honestly.
12. Recovery path must be deterministic and not depend on a lucky shell environment.
13. Runtime must not depend on one stale hardcoded outbound proxy port if live local proxy candidates can change across network environments.
14. If outbound proxy connectivity fails with proxy-path errors, the system must reprobe bounded local candidates before declaring generic runtime failure.
15. If no working outbound proxy candidate exists, the runtime must fall back cleanly or report degraded or down honestly without stale healthy claims.
16. Stable recovery must remain available through a deterministic service path and must not depend on a lucky interactive shell launch.

## Runtime Attestation V1

No `healthy`, `PASS`, `alpha-ready`, `pilot-ready`, `stable-10-proved`, or `stable-15-proved` claim is valid without a machine-carried runtime attestation.

Required attestation fields:

- `listener_ok`
- `models_ok`
- `responses_ok`
- `effective_mode_match`
- `base_url_match`
- `selected_backends_digest`
- `observed_at_utc`
- `runtime_version`
- `attestation_source`

If any mandatory field is missing, the attestation is invalid.

## State Contract

1. `backend-registry.json` is the lifecycle source of truth.
2. `supervisor-state.json` is a snapshot, not final truth without live checks.
3. `runtime-mode.txt` stores desired mode.
4. `runtime-effective-mode.txt` stores actual mode after preflight.
5. `managed-config.yaml` is generated only for managed runtime.
6. Diagnostics bundle is a redacted support snapshot.
7. All state files have `schema_version`.
8. All state writes are atomic.
9. The UI must show stale or unknown separately from healthy and down.
10. Registry stores lifecycle values: active, reserve, retired.
11. Registry stores `manual_hold`, `status`, `fail_count`, `success_count`, `last_success`, `last_error`, `cooldown_until`, `auth_ref`, `notes`.
12. Registry schema must support 20 accounts without format redesign.

## State Schema Policy

1. Each schema file must define required fields and optional fields explicitly.
2. Each schema change must define a migration rule.
3. State transitions must be documented, not inferred from scripts.
4. Every write path must declare whether it mutates registry, runtime state, diagnostics, or mode files.

Registry and runtime state use a single-writer mutation model.
Concurrent mutators are forbidden.
Any operation that changes active routing, registry, mode, or managed state must go through one serialized path.

## Command API Contract

1. All operator commands must support `--json`.
2. UI and automation use JSON output as the primary interface.
3. Minimum command set:
   - `status`
   - `sync`
   - `healthcheck`
   - `mode get`
   - `mode set stable`
   - `mode set managed`
   - `policy stage set`
   - `rollout rotation inspect`
   - `rollout evidence capture 16`
   - `rollout stage prove 10`
   - `rollout stage prove 15`
   - `rollout stage advance 15`
   - `rollout stage advance 20`
   - `accounts list`
   - `accounts validate`
   - `accounts promote`
   - `accounts demote`
   - `accounts hold`
   - `accounts release`
   - `accounts retire`
   - `accounts onboard`
   - `diagnostics export`
4. Each command returns: `status`, `exit_code`, `human_message`, `machine_error_code`, `changed_files`, `next_action`.
5. Errors are grouped into: `recoverable`, `needs_user_action`, `fatal`.
6. Runtime and recovery surfaces should classify proxied-network failures separately from generic listener failure when the packet supports that distinction.
7. Preferred `machine_error_code` additions for runtime hardening include:
   - `proxy_path_broken`
   - `proxy_reprobe_failed`
   - `stable_service_disabled`

These codes are control-layer classifications and do not imply engine-layer duplication.

### JSON Output Rule

`stdout` must contain exactly one JSON object and no leading or trailing non-JSON text.
`stderr` may contain human-readable logs.
Invalid JSON is a hard failure even if exit code is 0.
UI and automation may not fall back to plain text or log parsing.
Any command that cannot satisfy this contract is not production-ready for integration.

## Failure Signal Model

Signal axis 1, liveness:

- `healthy`
- `degraded`
- `down`
- `stale`
- `unknown`

Signal axis 2, severity:

- `recoverable`
- `fatal`

Signal axis 3, operator action:

- `none`
- `retry`
- `user_action`
- `stop`

No single token may collapse these three axes into one ambiguous status.

## Data Layout Contract

1. Runtime data lives outside the app bundle.
2. Application Support stores registry, state, mode, configs, and metadata.
3. Logs are stored separately.
4. Caches store probes and temporary data.
5. Legacy import supports the current custom setup.
6. Reset and uninstall clean only companion-app data.

## Platform Boundary

Current implementation target is macOS-first.
Windows and Linux are later lanes and must not be claimed implicitly.
Any cross-platform claim requires explicit checks for path handling, file permissions, newline behavior, case sensitivity, locale, and Unicode normalization.

## State Transition Table

- new auth -> reserve
- reserve -> active only after validate plus sync plus operator or policy decision
- active -> hold when account degrades or becomes suspicious
- hold -> reserve after explicit release
- active -> retired when account is intentionally removed from service
- reserve -> retired when account is rejected or deprecated
- retired -> no automatic return path

Any transition that affects active routing must leave a rollback point.

## Failure Model

Recoverable failures:

- temporary healthcheck miss
- stale pid
- stale lock
- transient listener absence
- single-account probe failure
- broken outbound proxy path
- local proxy candidate drift after VPN or network change
- disabled but recoverable stable service

These should lead to retry, cleanup, reprobe, service recovery, or fallback without structural mutation.

Needs-user-action failures:

- browser callback not captured
- ambiguous new auth detection
- missing dependency
- invalid imported auth

These should stop the flow with a clear next action.

Fatal failures:

- registry corruption
- state schema mismatch without migration
- repeatable managed boot failure after cleanup
- unsafe write failure

These should block forward progress until repaired.

## Migration Transaction Model

Legacy import and schema migration must be transactional.

Required phases:

1. snapshot
2. stage
3. verify
4. switch
5. rollback

No migration is considered passed if old and new state are partially mixed.

## Workstreams

### Workstream 01: Product Spec

Freeze PRD for pilot.
Define roles: user, operator, maintainer.
Define scenarios.
Define screen map.
Define commands and button inventory.
Define acceptance criteria.

Acceptance: PRD is approved and does not conflict with active guide docs.

### Workstream 02: Runtime Hardening

Stabilize launch chain.
Implement listener truth layer.
Fix deterministic PATH and dependency checks.
Clean stale pid.
Enforce lock discipline.
Implement reliable fallback to stable.
Implement runtime attestation.
Implement single-writer state mutation.
Close rollout stage-advance serialization so proof, policy transition, promotion, stable inventory materialization, and postflight verification execute through one serialized owner path or one equivalent owner primitive.
Implement proxy candidate reprobe.
Persist last-known-good outbound proxy.
Classify proxy-path failure separately from listener failure when evidence supports it.
Harden deterministic stable service recovery.

Acceptance:

- Five consecutive launches without false healthy and without effective-mode drift.
- Runtime attestation is valid.
- No stale-green behavior remains in the main launch path.
- No lock handoff or interleaving window remains inside `rollout stage advance 15/20`.
- Broken outbound proxy path does not silently masquerade as generic runtime death.
- Stable recovery path remains deterministic under network-environment drift.

Current closeout note for implementation-order step 7:

- launch-chain stabilization, listener truth, deterministic PATH/dependency
  checks, stale-pid cleanup, lock discipline, reliable stable fallback,
  runtime attestation, single-writer mutation discipline, serialized
  stage-advance owner path, proxy reprobe, last-known-good proxy persistence,
  proxy-path classification, and deterministic stable-service recovery all
  have machine-carried surfaces and acceptance coverage in the current contour
- the `Five consecutive launches without false healthy and without
  effective-mode drift` acceptance bullet is covered by a five-iteration
  machine-checked launch and status proof slice in the current owner path
- implementation-order step 7 is therefore closed for the current contour, and
  the next primary contour is `Productize onboarding`

### Workstream 03: Onboarding

Single orchestrator script.
Add Account launcher with once and loop.
Snapshot auth files before login.
Detect new auth after login.
Import only into reserve.
Run validate plus supervisor sync plus status.
Fallback to manual auth selection.
Print final backend report.

Acceptance: A new account is added without manual JSON editing and without degrading the working pool.

Current closeout note for implementation-order step 8:

- onboarding owner lane now exposes `--once` and `--loop` command-path truth,
  reserve-first enforcement proof, and strict machine-carried onboarding
  outcomes without claim escalation beyond control-layer scope
- pre-login auth snapshot evidence is emitted in onboarding owner packets as
  `auth_snapshot_before_login_status`, `auth_snapshot_before_login_count`,
  `auth_snapshot_before_login_digest`, and
  `auth_snapshot_before_login_source`; these fields provide control-layer
  evidence only and do not duplicate engine-layer OAuth semantics
- acceptance and regression verification for this closeout was executed with
  `python3 -m unittest -q -k accounts_onboard tests.test_cli.CliTests` and
  `python3 -m unittest -q tests.test_cli.CliTests` on branch
  `codex/wave-1c-prereq-closeout`
- onboarding step-8 closeout commits are `6105fde` and `e52f704`, and
  implementation-order step 8 is therefore closed for the current contour;
  the next primary contour is `Build basic companion UI`

### Workstream 04: Pool Architecture 20

Registry schema v2.
Lifecycle active, reserve, retired.
Shallow and deep probing.
Bounded concurrency.
Reserve policy.
Staged promotion logic.
UI capacity model for 20 accounts from day one.

Acceptance: Architecture and data format do not need redesign when moving to 20 accounts.

Current closeout note for implementation-order step 6:

- registry schema v2, lifecycle truth, bounded probing/concurrency, reserve
  policy, staged promotion logic, and the UI-facing capacity data model all
  have machine-carried surfaces and acceptance coverage in the current contour
- for the current control-layer scope, the `Shallow and deep probing` clause is
  satisfied by bounded shallow reprobe plus same-owner live runtime reproof;
  no separate control-layer deep-probing truth surface is required by default
- implementation-order step 6 is therefore closed for the current contour, and
  the next primary contour is `Finish runtime hardening`

### Workstream 05: Staged Pool Rollout

Stage 1 formalizes stable-10 proof.
Stage 2 captures the observed 16-account contour as above-stage-15 field evidence.
Stage 3 advances toward 20 through controlled updates and explicit rollback points.
Every stage requires runtime attestation, healthcheck, runtime test, rotation log review, and rollback point.
Any degrading account moves to reserve or hold.

Acceptance:

- Each stage preserves stable fallback and avoids false healthy.
- The 16-account field contour is documented with machine-carried evidence before it is used as a formal scale claim.
- Stage-20 remains separately gated by bounded probing, rotation evidence, and rollback drills.

Stage-20 stop conditions:

- any false healthy or stale-green runtime claim
- broken or unproven stable fallback
- probe storm or unbounded probe concurrency
- contradicted rotation evidence
- degraded or down account count above the accepted rollout threshold
- proxy-path truth ambiguity
- missing rollback point
- missing or invalid runtime attestation
- any real config mutation outside an approved live-runtime operation

### Workstream 06: Companion UI

Main screen shows desired mode, effective mode, endpoint, proxy status, active, reserve, retired, health summary, and capacity 20.

Primary actions:

- Launch Client
- Run Managed Sync
- Run Stable Repair
- Smoke Test
- Switch Managed
- Switch Stable

Account actions:

- Add
- Promote
- Demote
- Hold
- Release
- Retire
- Recheck
- Validate

Diagnostics actions:

- Open Logs
- Open State
- Open Registry
- Export Diagnostics Bundle
- Open Data Folder

Settings:

- client path
- data directory
- probe limits
- legacy import

Acceptance: Operator can complete core workflows without terminal access.

Current closeout note for implementation-order step 9:

- the baseline companion UI now covers the bounded control-layer workflow for
  mode control, managed sync, launch smoke, reserve-first onboarding truth,
  account mutation actions, and diagnostics export owner-path invocation with
  strict JSON command/result mapping
- onboarding truth fields include machine-carried pre-login auth snapshot
  evidence (`auth_snapshot_before_login_status`, count, digest, source) and
  are rendered in the UI without engine-layer OAuth duplication
- the diagnostics export owner lane is wired through
  `diagnostics export --json` and renders command truth plus bundle-path
  output without log parsing fallback
- acceptance/regression verification for this step-9 closeout executed with:
  `python3 -m unittest -q tests.test_ui_shell`,
  `python3 -m unittest -q -k accounts_onboard tests.test_cli.CliTests`,
  `python3 -m unittest -q tests.test_cli.CliTests`, and `git diff --check`
  on branch `codex/wave-1c-prereq-closeout`
- step-9 closeout commits are `9339ca4` and `bd61ebd`; implementation-order
  step 9 is therefore closed for the current contour, and the next primary
  contour is `Add diagnostics export`

Current closeout note for implementation-order step 10:

- diagnostics export owner path is now integrated and verified across CLI and
  baseline companion UI through `diagnostics export --json` with strict JSON
  command/result mapping and bundle-path truth
- redaction safety surfaces remain control-layer only; diagnostics export and
  supporting tests verify redacted bundle behavior without engine-layer
  protocol duplication or claim escalation
- acceptance/regression verification for step-10 closeout executed with:
  `python3 -m unittest -q tests.test_ui_shell`,
  `python3 -m unittest -q tests.test_cli.CliTests -k diagnostics`,
  `python3 -m unittest -q tests.test_cli.CliTests`, and `git diff --check`
  on branch `codex/wave-1c-prereq-closeout`
- implementation-order step 10 is therefore closed for the current contour,
  and the next primary contour is `Add installer and legacy import`

### Workstream 07: Installer And Data Layout

Release format is zip or dmg.
First-run wizard creates data dirs.
Legacy import is supported.
Reset and uninstall exist.
Checksums exist.
Codesign and notarization are deferred until the experiment goes wider.

Acceptance: Clean install and legacy migration work without manual config edits.

Current closeout note for implementation-order step 11:

- baseline installer/data-layout owner surfaces now include
  `installer init --json`, `legacy import --source-dir <path> --json`,
  `companion reset --json`, and `companion uninstall --json` with strict JSON
  command/result packets and control-layer-only scope
- legacy import uses explicit transaction phases and rollback restoration over
  companion-managed write targets, and baseline reset/uninstall paths preserve
  auth file boundaries by default while removing companion-managed state
- command list and coverage were expanded with parser-guard tests and baseline
  installer/import/reset behavior tests in `tests.test_cli.CliTests`
- acceptance/regression verification for step-11 closeout executed with:
  `python3 -m unittest -q tests.test_cli.CliTests -k diagnostics`,
  `python3 -m unittest -q tests.test_cli.CliTests -k legacy`,
  `python3 -m unittest -q tests.test_cli.CliTests -k installer`,
  `python3 -m unittest -q tests.test_cli.CliTests -k companion`,
  `python3 -m unittest -q tests.test_cli.CliTests`,
  `python3 -m unittest -q tests.test_ui_shell`, and `git diff --check`
  on branch `codex/wave-1c-prereq-closeout`
- implementation-order step 11 is therefore closed for the current contour,
  and the next primary contour is `Prepare experimental package`

Current closeout note for implementation-order step 12:

- experimental package owner surfaces now include
  `package experimental build --output-dir <path> --json` and
  `package experimental verify --manifest <path> --json` with strict JSON
  command/result packets and control-layer-only packaging scope
- package build emits artifact, checksum manifest, and metadata, while package
  verify enforces checksum truth and artifact presence without log parsing
- packaging boundary hardening excludes runtime/private material (auth/state,
  dumps, logs, token/key-like files, hidden runtime traces) and uses a
  deterministic repo-root source default instead of launch-directory drift
- acceptance/regression verification for step-12 closeout executed with:
  `python3 -m unittest -q tests/test_cli.py -k package`,
  `python3 -m unittest -q tests/test_cli.py`,
  `python3 -m unittest -q tests/test_ui_shell.py`, plus manual owner-path smoke
  checks for private-artifact exclusion and foreign-cwd source-root stability
  on branch `codex/wave-1c-prereq-closeout`
- implementation-order step 12 is therefore closed for the current contour,
  and the next primary contour is `Run alpha`

Current closeout note for implementation-order step 13:

- alpha-run preparation contour was executed in isolated-runtime and test-fixture
  lanes with machine-carried gate evidence for `RUNTIME_ATTESTATION_GATE`,
  `STRICT_JSON_COMMAND_API_GATE`, `STATE_SERIALIZATION_GATE`, and
  `FALLBACK_DRILL_GATE`
- command replay and gate verdict evidence is captured in
  `audit_results/step13_alpha_gate_report.md`; the replay explicitly marks
  zero-test command selections as non-gating and excludes them from coverage
- independent audit replay confirmed PASS across all four alpha gates and found
  no P0/P1 issues; one P3 reporting-clarity finding (`Ran 0 tests` wording) was
  remediated in the report without changing gate outcomes
- acceptance/regression verification for step-13 closeout executed with:
  `python3 -m unittest -q tests.test_cli.CliTests.test_healthcheck_returns_attestation`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_status_uses_live_attestation_for_green_state`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_sync_returns_single_json_object`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_15_blocks_cross_thread_mode_mutation_during_policy_step`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_healthcheck_owner_path_reports_observed_source_fallback_recovery`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_evidence_capture_16_reports_complete_packet`,
  `python3 -m unittest -q tests.test_cli -k healthcheck`,
  `python3 -m unittest -q tests.test_cli -k status`,
  `python3 -m unittest -q tests.test_cli -k advance`,
  `python3 -m unittest -q tests.test_cli -k fallback`, and
  `python3 -m unittest -q tests/test_ui_shell.py`
  on branch `codex/wave-1c-prereq-closeout`
- implementation-order step 13 is therefore closed for the current contour,
  and the next primary contour is `Prove stable 10`

Current closeout note for implementation-order step 14:

- stable-10 proof contour was executed in isolated-runtime fixture lanes through
  owner-surface `rollout stage prove 10 --json` with supporting
  `healthcheck --json`, `status --json`, and `rollout rotation inspect --json`
  replay evidence
- command replay and gate verdict evidence is captured in
  `audit_results/step14_stable10_proof_report.md`, including explicit non-gating
  labeling for grouped `-k` expressions that selected zero tests
- independent audit replay confirmed PASS for stable-10 contour coverage and
  found no P0/P1/P2/P3 findings; claim scope remains bounded to
  `stable_10_proved`
- acceptance/regression verification for step-14 closeout executed with:
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_prove_10_reports_success_with_bounded_delegated_evidence`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_prove_10_reports_runtime_attestation_failure`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_prove_10_reports_rotation_insufficiency`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_15_holds_outer_serialization_lock_across_composite_steps`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_15_blocks_held_lock_without_mutation`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_15_fails_on_postflight_contradiction_after_promotion`,
  `python3 -m unittest -q tests.test_cli -k stage_prove`,
  `python3 -m unittest -q tests.test_cli -k rollback_readiness`,
  `python3 -m unittest -q tests.test_cli -k prove_10`, and
  `python3 -m unittest -q tests/test_ui_shell.py`
  on branch `codex/wave-1c-prereq-closeout`
- implementation-order step 14 is therefore closed for the current contour,
  and the next primary contour is `Consolidate observed 16-account evidence`

Current closeout note for implementation-order step 15:

- observed 16-account evidence consolidation contour was executed in isolated
  fixture lanes through owner surfaces `healthcheck --json`, `status --json`,
  `accounts list --json`, `rollout rotation inspect --json`, and
  `rollout evidence capture 16 --json`
- command replay, acceptance checklist, and negative-lane evidence are captured
  in:
  `audit_results/step15_consolidate_16_evidence_report.md`,
  `audit_results/step15_owner_surface_capture.json`,
  `audit_results/step15_negative_fixture_checks.json`, and
  `audit_results/step15_test_runs.json`
- acceptance fields were confirmed machine-readably with
  `packet_status=complete`,
  `final_outcome=field_evidence_packet_complete`,
  `blocked_reasons=[]`,
  `scale_gate_summary.blocked_gate_names=[]`, and
  `claim_scope=field_evidence_observed_only`
- independent audit replay confirmed PASS with no P0/P1/P2/P3 findings and no
  claim-escalation beyond observed-only scope
- acceptance/regression verification for step-15 closeout executed with:
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_evidence_capture_16_reports_complete_packet`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_evidence_capture_16_reports_attestation_incomplete`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_evidence_capture_16_reports_rotation_contradicted`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_evidence_capture_16_reports_redaction_failure_unsafe`,
  `python3 -m unittest -q tests.test_cli -k evidence_capture`, and
  `python3 -m unittest -q tests/test_ui_shell.py`
  on branch `codex/wave-1c-prereq-closeout`
- implementation-order step 15 is therefore closed for the current contour,
  and the next primary contour is `Expand by controlled updates toward 20`

Current closeout note for implementation-order step 16:

- controlled-update contours toward 20 were executed in isolated fixture lanes
  through control-layer owner surfaces only, with deterministic replay for:
  `status --json`, `rollout rotation inspect --json`,
  `rollout stage prove 10 --json`, `rollout stage prove 15 --json`,
  `rollout stage advance 15 <id> --json`, and
  `rollout stage advance 20 <id> --json`
- machine-carried replay, negative lanes, and test-run evidence are captured in:
  `audit_results/step16_controlled_updates_toward20_report.md`,
  `audit_results/step16_owner_surface_capture.json`,
  `audit_results/step16_negative_checks.json`, and
  `audit_results/step16_test_runs.json`
- positive owner-surface lanes show bounded successful step transitions
  (`advance_* final_outcome=advanced_one_step`) from staged preconditions, while
  safety lanes confirm held-lock blocking, invalid-backend rejection, and
  rollback paths for contradiction/proof/policy/promotion/materialization
  failures
- independent audit replay confirmed PASS with no P0/P1/P2/P3 findings and no
  claim-escalation tokens; this contour does not claim `stable_20_proved`,
  `scale_complete`, `pilot_ready`, or `production_ready`
- acceptance/regression verification for step-16 closeout executed with:
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_15_from_stage_10_updates_policy_one_step`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_from_stage_15_updates_policy_one_step`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_15_blocks_held_lock_without_mutation`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_blocks_held_lock_without_mutation`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_fails_on_postflight_contradiction_after_promotion`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_15_holds_outer_serialization_lock_across_composite_steps`,
  `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_15_reports_truthful_changed_files_after_promotion`,
  `python3 -m unittest -q tests.test_cli -k stage_advance_15`,
  `python3 -m unittest -q tests.test_cli -k stage_advance_20`, and
  `python3 -m unittest -q tests/test_ui_shell.py`
  on branch `codex/wave-1c-prereq-closeout`
- implementation-order step 16 is therefore closed for the current contour,
  and the next primary contour is `Release-gate alignment for scale decision and pilot-entry prep`

## Historical Planning Reset Note

Artifacts from implementation-order steps 17 through 29 remain preserved in
`audit_results/` as truthful historical records of the prior gate policy.

Those contours repeatedly captured two real facts:

- repository-scope machine proof for the live 20-account contour was still
  missing
- the then-active policy expected a fixed multi-day metrics window

This plan revision supersedes that forward policy.
The historical artifacts remain useful chronology and regression evidence, but
they do not define the current active execution contour.

The active forward plan is now:

- run live-readonly and sandbox admission first
- prove web live server binding, command action packets, sandbox data
  boundaries, and rollback discipline before account or route mutation
- run sandbox onboarding, lifecycle, API-route, runtime mode, launch,
  diagnostics, and full operator-session contours in order
- repair only packet-proven field defects after the sandbox operator session
- only then reopen stage 10/15/20 and pilot gates with machine-carried
  evidence

No fixed long-window metrics requirement is part of the active governing plan.

## Corrected Live/Sandbox Operating Sequence

This section supersedes the prior practice of continuing narrow execution-core
repair contours by inertia after each `STOP_AND_DIAGNOSE`.

The current branch has already produced later execution-core repair artifacts
than the historical web visual QA note. Those artifacts remain useful evidence,
but the active strategy now resets to a factual live-readonly and sandbox
admission wave before further account, route, runtime, or launch mutation.

This wave is not a rich UI expansion and does not satisfy or bypass the design
gate. It is an operator-safety and truth-surface wave for existing command
surfaces.

Global rules for every contour in this sequence:

1. `git status --short --untracked-files=no` must be clean for tracked files
   before starting.
2. The previous contour must be closed with verification, commit, and push.
3. Strict JSON command packets are the primary truth source.
4. Command `OK` does not equal runtime truth without refresh proof.
5. Live mutation requires owner approval, declared write surfaces, and rollback
   expectations.
6. Web UI actions must not accept path, file, token, secret, or raw config
   payloads from the UI.
7. The UI must not read raw logs, raw config, auth files, state files, or secret
   values.
8. Fixture data must not be treated as live truth.
9. Every contour closes with an audit packet, closeout, commit, and push.
10. If command/write surfaces and rollback are already admitted and current
    packet truth satisfies preconditions, execute the bounded contour instead
    of opening another admission contour.
11. A successful prerequisite that the next contour depends on should remain in
    place unless rollback is required by a failed or contradictory packet.
12. Historical or transient truth is not current truth after rollback.

Final active contour order:

```text
0.  TECH_GATE_AND_ENV_INVENTORY_PASS
1.  WEB_LIVE_SERVER_READONLY_ADMISSION_PASS
2.  READONLY_TRUTH_PACKET_BASELINE_PASS
3.  SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS
4.  SANDBOX_LIVE_SERVER_BINDING_PASS
5.  ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS
6.  ACCOUNT_LIFECYCLE_SANDBOX_ACTIONS_PASS
7.  API_ROUTES_READONLY_AND_SECRET_REF_PASS
8.  API_ROUTE_CHECK_AND_DISABLED_REMOVE_SANDBOX_PASS
9.  RUNTIME_MODE_AND_SYNC_SANDBOX_PASS
10. CLIENT_LAUNCH_SANDBOX_DISPATCH_PASS
11. DIAGNOSTICS_EXPORT_AND_PRIVACY_SANDBOX_PASS
12. ACTION_LEDGER_LIVE_E2E_PASS
13. CONTRACT_ADMISSION_PACKETS_PASS
14. SANDBOX_FULL_OPERATOR_SESSION_PASS
15. FIELD_REPAIR_LOOP_1_PASS
16+. Stage 10 / 15 / 20 / Pilot Gate after evidence
```

The immediate next contour is:

```text
TECH_GATE_AND_ENV_INVENTORY_PASS
```

The previously selected
`SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_VALIDATE_EVIDENCE_PASS` is parked.
It may be resumed only if `TECH_GATE_AND_ENV_INVENTORY_PASS` and later sandbox
binding evidence prove that this route-validation lane is still the correct
owner-surface path.

### 0. `TECH_GATE_AND_ENV_INVENTORY_PASS`

Goal: establish the factual repo/runtime state before live-readonly work.

Actions:

```text
git status --short --untracked-files=no
git log --oneline -n 10
verify git hooks
verify CLI entrypoints
verify web_design_live_server.py
verify web_design_command_adapter.py as read-only first
verify action allowlist read-only surfaces
verify api/actions contract
collect admitted UI actions
collect readonly commands
collect mutation commands
collect deferred or missing surfaces
```

Outputs:

```text
inventory_packet.json
actions_matrix.json
risk_matrix.md
decision: can proceed to live-readonly or STOP_AND_DIAGNOSE
```

Stop conditions:

```text
dirty tracked diff
unclear command entrypoint
allowlist/runtime contradiction
```

### 1. `WEB_LIVE_SERVER_READONLY_ADMISSION_PASS`

Goal: run the live server in read-only mode only.

Actions:

```text
start live server
open ?screen=quick-start&source=live
check /api/actions
check /api/live-readonly
check fixture fallback behavior
check invalid JSON handling
check stale/error copy
check disabled actions without sensitive metadata
```

Forbidden:

```text
onboard
mode set
launch client
import
reset
write config
```

Outputs:

```text
live_server_readonly_packet.json
endpoint_matrix.json
screenshots
```

### 2. `READONLY_TRUTH_PACKET_BASELINE_PASS`

Goal: capture the read-only baseline truth.

Commands:

```text
status --json
mode get --json
accounts list --json
healthcheck --json
rollout rotation inspect --json
external-models status/models/routes read-only, if present
```

UI checks:

```text
Quick Start
Overview
Accounts
API Connections
Diagnostics
Settings summaries
```

Acceptance:

```text
no stale-green
no fixture truth in live failure
no raw logs/secrets
UI state matches packet scope
```

### 3. `SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS`

Goal: prepare a safe sandbox.

Actions:

```text
identify working host-client path
identify sandbox data dir
identify auth/config/state/log boundaries
forbid writes into the working contour
create snapshot and rollback plan
describe teardown
describe sandbox separation proof
```

Forbidden:

```text
copying live auth without explicit decision
onboarding
import
config writes
```

Outputs:

```text
sandbox_boundary_packet.json
rollback_runbook.md
write_surface_declaration.md
```

### 4. `SANDBOX_LIVE_SERVER_BINDING_PASS`

Goal: prove the live server and command runner are bound to sandbox paths.

Actions:

```text
start live server with sandbox env
check status/mode/accounts from sandbox
prove working paths are not used
check changed_files scope
check env vars
check ports
check teardown
```

Acceptance:

```text
sandbox source proven
production/work host-client data untouched
rollback possible
```

### 5. `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`

Goal: run the first sandbox onboarding as reserve-first.

Actions:

```text
owner approval for sandbox mutation
run onboarding only through accounts onboard --json
check selected_backend_id
check new_backend_ids
check reserve_first_enforced
check pool_after_onboarding = reserve
check active_routing_changed = false
check validate outcome
check sync outcome
run accounts list --json after the command
compare UI result and action ledger
```

Stop conditions:

```text
no reserve-first proof
ambiguous auth
no_new_auth shown as green
new backend enters active
refresh failed
```

### 6. `ACCOUNT_LIFECYCLE_SANDBOX_ACTIONS_PASS`

Goal: verify lifecycle actions on a sandbox account.

Actions:

```text
validate_account
hold_account
release_account
promote_account
demote_account
retire_account only for a disposable test account
after each action run accounts list --json
check Account Detail drawer
check disabled reasons
check confirmation for risky actions
```

Acceptance:

```text
payload only ui_action + account_id
disabled action does not dispatch
success only after refresh proof
```

### 7. `API_ROUTES_READONLY_AND_SECRET_REF_PASS`

Goal: verify API route registry display without editing.

Actions:

```text
collect read-only routes snapshot
select main route for Quick Start
check enabled/disabled/unknown states
check secret_ref name/status only
check missing_secret amber state
check support packet is not health truth
```

Forbidden:

```text
raw route JSON
token input
secret value
provider config edit
```

### 8. `API_ROUTE_CHECK_AND_DISABLED_REMOVE_SANDBOX_PASS`

Goal: verify admitted route actions.

Actions:

```text
api_route_check if admitted
api_route_validate if admitted
api_route_remove only for disabled route
preflight
strong confirmation
command result
read-only refresh
route absent proof
```

Stop conditions:

```text
enabled route removal
payload contains raw JSON/provider/model/path/secret
refresh mismatch
```

### 9. `RUNTIME_MODE_AND_SYNC_SANDBOX_PASS`

Goal: verify runtime mode and sync in sandbox.

Actions:

```text
mode get --json
mode set managed --json
refresh
mode set stable --json
refresh
sync --json if admitted
launch smoke --json if admitted
check desired/effective mismatch
```

Acceptance:

```text
green only from fresh consistent packet
mode command OK is not success without refresh
stable_repair_apply remains deferred
```

### 10. `CLIENT_LAUNCH_SANDBOX_DISPATCH_PASS`

Goal: verify launch client as bounded dispatch.

Actions:

```text
check selected client packet
check launch readiness
launch client --json
check runtime precondition
check env sanitization
check dispatch_observed
check claim_scope
```

Rule:

```text
"dispatch requested" is allowed
"client running" or "session ready" requires packet proof
```

### 11. `DIAGNOSTICS_EXPORT_AND_PRIVACY_SANDBOX_PASS`

Goal: verify diagnostics export and privacy posture.

Actions:

```text
diagnostics export --json
artifact reference basename/id only
redaction status
changed files count-only
action ledger entry
Diagnostics / Privacy screen
```

Forbidden:

```text
read bundle in UI
read raw logs
show full path
treat export as runtime healthy
```

### 12. `ACTION_LEDGER_LIVE_E2E_PASS`

Goal: verify unified action result grammar.

Required states:

```text
running
duplicate_blocked
ok_refresh_pending
ok_refresh_complete
ok_refresh_failed
command_error
invalid_json
timeout
integration_failure
partial_success
needs_user_action
```

Acceptance:

```text
no raw argv
no secrets/paths
special fields only in expanded detail
no stale-green
```

### 13. `CONTRACT_ADMISSION_PACKETS_PASS`

Goal: document future missing contracts.

Included admissions:

```text
data_layout_check
data_layout_snapshot
data_layout_rollback
import_existing_preflight
import_existing_dry_run
import_existing_snapshot
import_existing_apply
import_existing_rollback
diagnostics_history_packet
```

Rule:

```text
spec/admission only
no implementation
no live mutation
```

### 14. `SANDBOX_FULL_OPERATOR_SESSION_PASS`

Goal: run the full operator scenario in sandbox.

Scenario:

```text
Quick Start
accounts read-only
onboard test account
validate
hold/release
API check
diagnostics export
mode switch
launch sandbox client
action ledger review
final accounts/status/healthcheck refresh
```

Outputs:

```text
operator_session_packet.json
screenshots
mismatch_list.md
repair_backlog.md
```

### 15. `FIELD_REPAIR_LOOP_1_PASS`

Goal: repair only factually observed issues.

Classification:

```text
UI bug
command adapter bug
runtime/core truth bug
docs/runbook bug
test coverage gap
```

Rule:

```text
do not fix everything in one contour
each fix uses an atomic commit and push
```

### Parking Lot: Stage And Pilot

Do not start these before sandbox evidence:

```text
ACTIVE_POOL_STAGE_10_PROOF_PASS
ACTIVE_POOL_STAGE_15_PROOF_PASS
ACTIVE_POOL_STAGE_20_REENTRY_PASS
PILOT_READINESS_GATE_PASS
```

They become active only after:

```text
sandbox onboarding PASS
lifecycle PASS
runtime mode PASS
diagnostics PASS
fallback readiness PASS
machine-carried evidence exists
```

### Workstream 08: Experiment Package

Package includes source, docs, release artifact, and checksums.
Package excludes auth, runtime state, logs, and real account registry data.
README explains the experimental companion app clearly.

Acceptance: Package can be handed to testers without leaking private runtime data.

### Workstream 09: Minimal License Note

Keep a minimal notice for CLIProxy engine usage.
If the engine is bundled, ship a short notice file next to the artifact.
Do not expand into heavy compliance process at experiment stage.

Acceptance: There is a short and clear notice about the external or bundled engine.

### Workstream 10: QA And SRE

Tests cover install, first run, legacy import, onboarding success, onboarding fallback, mode switch, managed restart, stable fallback, stale pid, stale lock, listener truth, diagnostics redaction, staged pool rollout, 16-account evidence capture, invalid JSON command response, wrong effective mode, wrong base_url, duplicate account_id, partial migration rollback, VPN or network-change proxy drift, broken current proxy candidate, auto-reprobe to a new working proxy candidate, stable service disabled then recovered, and concurrent mutation or interleaving attempts during `rollout stage advance 15/20`.
Observability includes status report, machine error codes, diagnostics bundle, and runtime attestation.
Pilot SLO includes launch success rate, onboarding success rate, managed health stability, and mean recovery time.

Acceptance: Pre-release testing covers same-day high-load validation, fallback drills, recovery drills, and release-candidate regression without false-green behavior.

### Workstream 11: Security

Auth files use mode 600.
Runtime directories are permission-limited.
Secrets do not enter logs.
Diagnostics export redacts sensitive values.
Env is sanitized before login, proxy, and client launch.
Callback URLs and external paths are handled safely.

Acceptance: No obvious secret leaks in logs, package, or diagnostics.

### Workstream 12: Migration And Support

Import legacy setup wizard.
Backward-compatible operator commands.
Incident runbook.
Short recovery playbooks.
Diagnostics export for support.

Acceptance: Existing users migrate without downtime and without manual JSON edits.

## Execution Wave 1 Scope

Freeze execution core:

- runtime contract
- state schema
- state transitions
- failure model
- command API

Implement runtime hardening.
Implement runtime attestation.
Implement truthful status.
Implement fallback.
Do not start installer, packaging, or rich UI work before these are stable.

Explicitly out of scope:

- No polished UI.
- No installer.
- No public package polish.
- No live staged scale execution beyond the current stable pool.
- Freezing command API surfaces for controlled rollout does not itself prove or execute scale.
- No generic CLIProxy management features.

Acceptance:

- Runtime truth works.
- Managed fallback works.
- Command API exists in strict JSON form.
- State schema is frozen enough for UI to build against.
- No stale-green behavior remains in the main launch path.
- Critical user path is covered.
- Proxy-path drift does not silently invalidate truthful runtime classification.

## Critical User Path Gate

1. cold start
2. managed preflight
3. one-click onboarding to reserve
4. validate
5. single-account promotion
6. managed sync
7. launch client
8. forced managed failure
9. stable fallback

Without this path, neither `PILOT_READY` nor `STABLE_10_PROVED` may be claimed.

## Release Gates

1. Alpha gate includes runtime attestation, strict JSON command API, stable fallback, single-writer state mutation, and 20-account registry capacity.
2. Closed beta gate includes onboarding, diagnostics, stable 10-account pool, and staged rollout plan to 20.
3. Scale-prep gate includes documented 16-account field evidence with machine-carried attestation, rotation evidence, fallback readiness, and no stale-green behavior.
4. Scale gate includes same-day controlled validation to 20 with machine-carried evidence, runtime attestation, rotation participation evidence, and fallback readiness.
5. Pilot gate includes installer, legacy import, minimum security, minimum license note, basic companion UI, and pre-release regression readiness.
6. Experimental external package gate requires no private runtime data, working checksums, and a basic README.

## Pilot Entry Criteria

1. Runtime hardening completed.
2. Command API with strict JSON completed.
3. Registry architecture supports 20 accounts.
4. Onboarding completed.
5. Basic companion UI completed.
6. Minimum security completed.
7. Legacy import path tested.

## Pilot Exit Criteria

1. Stable 10-account managed pool.
2. Architecture ready for 20 accounts without schema rewrite.
3. Successful onboarding flow.
4. Valid stable fallback.
5. No false healthy state.
6. Diagnostics export is redacted.
7. Experimental package is ready.

## Scale To 20 Criteria

1. The observed 16-account contour is documented with a redacted evidence packet.
2. A same-day live 20-account contour is executed on the real environment under high load.
3. 20 accounts are registered across active and reserve lifecycle.
4. Bounded probing works without request storm.
5. Staged promotion to 20 passes through rollback points.
6. Rotation logs show participation of the expanded active pool.
7. Runtime attestation remains truthful during the validation contour.
8. Failing accounts are isolated to reserve or hold.
9. Stable fallback remains operational.

## Rollback Matrix

- managed preflight fail -> fallback to stable
- bad imported auth -> keep reserve only, no active routing
- state schema mismatch -> stop, restore previous schema snapshot
- legacy import partial fail -> rollback to pre-import snapshot
- invalid JSON API response -> hard fail integration, no UI fallback parsing
- stale pid or stale lock -> cleanup plus retry
- duplicate account_id suspicion -> reserve or hold, no automatic active promotion
- broken outbound proxy path -> reprobe bounded live candidates, then fallback to stable if none works
- stable service disabled -> re-enable deterministic stable service path, then retry

## Top Risks

1. Browser auth edge cases.
2. State drift.
3. Proxy upstream changes.
4. Dependency updates.
5. False healthy state.
6. Over-expanding pilot scope.
7. Probe storm at higher pool sizes.
8. Duplicate account_id inside the pool.
9. Local outbound proxy drift after VPN, Cisco, or network environment change.
10. Field success may outrun formal machine-carried proof.

## Risk Mitigation

1. Fallback paths.
2. Live truth checks.
3. Staged rollout.
4. Operator tooling.
5. Redacted diagnostics.
6. Bounded concurrency.
7. Reserve-first onboarding.
8. Manual hold for suspicious accounts.
9. Separate proof stages for 10, 15, and 20.
10. No UI growth before execution core freeze.
11. Bounded reprobe of live proxy candidates plus last-known-good proxy persistence.
12. No scale claim without an evidence packet, runtime attestation, rotation evidence, and rollback readiness.

## Network-Dependent Evidence Rule

OAuth callback success, GitHub packaging, upstream provider responsiveness, and browser callback behavior are network-dependent evidence.
They may support a claim, but they are not substitutes for local runtime attestation.

## Minimal Blocking Gates 80/20

- `RUNTIME_ATTESTATION_GATE`
- `STRICT_JSON_COMMAND_API_GATE`
- `STATE_SERIALIZATION_GATE`
- `FALLBACK_DRILL_GATE`
- `SCALE_EVIDENCE_PACKET_GATE`

`SCALE_EVIDENCE_PACKET_GATE` is owned by
`rollout evidence capture 16 --json` for the observed 16-account field contour.
This surface may produce only `field_evidence_observed_only`.
It must not produce `stable_16_proved`, `stable_20_proved`, `scale_complete`,
`pilot_ready`, or `production_ready`.

`STATE_SERIALIZATION_GATE` is satisfied only when composite stage-advance execution does not reopen lock boundaries between proof, policy mutation, promotion, stable inventory materialization, and postflight verification.

## Implementation Order

Active implementation order is now governed by the corrected live/sandbox
operating sequence above.

The previous macro order remains a release roadmap, not the active next-action
queue. Stage and pilot contours are parked until the sandbox evidence gates are
closed.

1. Run `TECH_GATE_AND_ENV_INVENTORY_PASS`.
2. Run live-readonly admission and read-only truth baseline.
3. Prove sandbox data boundaries and live-server sandbox binding.
4. Prove sandbox onboarding reserve-first behavior.
5. Prove sandbox lifecycle actions.
6. Prove API route read-only and admitted route actions.
7. Prove runtime mode/sync, launch dispatch, diagnostics, and action ledger.
8. Run one full sandbox operator session.
9. Run a focused field repair loop for packet-proven defects only.
10. Reopen stage 10/15/20 and pilot gates only after sandbox evidence exists.
11. Continue packaging, installer, diagnostics history, and pre-release
    regression only after the relevant gate evidence is committed and pushed.

## Estimate

Pilot readiness depends on tight scope control and clean closure of the remaining development contours.
The active scale milestone is a same-day 20-account live validation with machine-carried evidence.
The observed 16-account contour lowers scale uncertainty but does not remove the need for formal live 20-account proof.

## Final Verdict

This plan is executable and practical if used as a governing document rather than a single giant TODO list.
Execution begins with one narrow wave: execution core, runtime truth, state, and command API first.
The strongest version of the plan is the one that protects the boundary with CLIProxy, keeps staged scaling honest, turns today's 20-account live contour into machine-carried evidence, forbids stale-green behavior, serializes state mutation, hardens proxy-path resilience against network-environment drift, and then lets UI and release work follow only after runtime truth is already proven.

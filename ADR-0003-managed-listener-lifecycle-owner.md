<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# ADR: Managed Listener Lifecycle Owner Is Engine-Owned And WBP-Orchestrated

## Status

Accepted

## Date

2026-06-01

## Context

The managed runtime endpoint is `127.0.0.1:8320`, but the current repository has
no implemented repo-owned owner path that starts a long-running managed listener
on that endpoint.

This decision is expensive to reverse because the startup owner controls process
lifetime, PID truth, port ownership, runtime truth mutation, recovery behavior,
and the boundary between Wild Boar Proxy as control layer and `CLIProxyAPI` as
engine. If this boundary is wrong, later UI, model-matrix, and live-coding work
will build on false-green runtime claims.

Current canon and contracts already establish these constraints:

- Wild Boar Proxy is the managing layer.
- `CLIProxyAPI` is the engine.
- live listener truth wins over cached state.
- `runtime-effective-mode.txt = managed` is valid only after successful live
  preflight.
- command packets are the runtime truth surface.
- existing `mode get --json`, `mode set --json`, `healthcheck --json`,
  `status --json`, `sync --json`, and `launch smoke --json` do not own
  long-running managed-listener startup.

## Decision

The managed listener process is engine-owned and WBP-orchestrated.

The selected owner boundary is:

- `CLIProxyAPI` owns the long-running listener process that binds `8320`.
- Wild Boar Proxy owns the bounded lifecycle command surface that may request
  startup, record the PID, perform live proof, and publish command packet truth.
- Wild Boar Proxy must not implement a second proxy engine or in-process
  OpenAI-compatible server for the managed runtime.
- Native launch and package delivery remain separate topics and must not be used
  as proof that the managed listener is live.
- Until a concrete `CLIProxyAPI` executable or entrypoint is selected and wired,
  the current implementation must continue to report managed startup ownership
  as blocked, not partially owned.

The future command surface is reserved as:

- `managed listener start --json`

That command is not implemented by this ADR. The reservation names the command
boundary; it does not claim that startup currently exists.

## Scope Boundary

This ADR decides ownership only. It does not:

- implement the command parser
- start or stop a process
- select a concrete engine binary
- mutate runtime state
- change UI, native launch, package delivery, external-models lifecycle, or
  profile/history behavior
- close the current `MANAGED_STARTUP_OWNER_UNDEFINED` blocker

## Startup Contract

The future `managed listener start --json` command may write only these runtime
surfaces, and only after declaring them in the command packet:

- `managed/managed-proxy.pid`
- `runtime-effective-mode.txt`
- `config.toml` `base_url`
- `managed/supervisor-state.json`

Write rules:

- `managed/managed-proxy.pid` may be written only after the engine process has
  started and the PID belongs to that process.
- `runtime-effective-mode.txt` may be written to `managed` only after live
  listener proof passes.
- `config.toml` `base_url` may be written to the managed endpoint only after
  live listener proof passes.
- `supervisor-state.json.effective_mode` may be written to `managed` only after
  live listener proof passes.
- `supervisor-state.json.managed_port` may reflect the configured managed port,
  but must not by itself prove listener ownership.
- `supervisor-state.json.current_proxy_url` must remain separate from startup
  ownership and may not be changed by startup alone.

Disallowed writes:

- account registry mutation
- stable inventory mutation
- stable generated-config mutation
- current-proxy adoption
- UI/native profile mutation
- external-models synthetic state mutation

Process and port rules:

- stale PID cleanup must run before startup.
- wrong-port listeners must be rejected.
- a healthy existing listener on the expected endpoint may produce
  `startup_outcome = already_running_verified`.
- a stale PID with no live listener must not block recovery after cleanup.
- a live listener with mismatched PID must be reported as ambiguous, not adopted
  silently.
- double-start must be rejected unless the existing listener is live-proven on
  the expected endpoint.

Rollback and failure rules:

- failure must leave `runtime-effective-mode.txt` non-managed or restore the
  previous truthful value.
- failure must not report stable fallback as managed startup success.
- failure must not change `current_proxy_url`.
- rollback failure must be machine-readable.

## Packet Contract

`managed_startup_owner` remains the command-packet truth surface.

The reserved startup command and the existing startup-owner readout must preserve
or expose these fields when implementation exists:

- `status`
- `owner_command_surface`
- `startup_attempted`
- `startup_outcome`
- `process_started`
- `pid_recorded`
- `managed_listener_endpoint`
- `managed_listener_reachable`
- `live_attestation_passed`
- `effective_mode_written`
- `repo_owned_startup_owner_path_defined`
- `machine_error_code`
- `blocking_reason`

Required failure classes:

- `MANAGED_STARTUP_OWNER_UNDEFINED`
- `MANAGED_STARTUP_ENGINE_ENTRYPOINT_MISSING`
- `MANAGED_STARTUP_PROCESS_FAILED`
- `MANAGED_STARTUP_LISTENER_UNREACHABLE`
- `MANAGED_STARTUP_ATTESTATION_FAILED`
- `MANAGED_STARTUP_PROBE_MODEL_UNBOUND`
- `MANAGED_STARTUP_WRONG_PORT`
- `MANAGED_STARTUP_STALE_PID_CONFLICT`
- `MANAGED_STARTUP_AMBIGUOUS_EXISTING_LISTENER`
- `MANAGED_STARTUP_ROLLBACK_FAILED`

No success packet may claim managed readiness unless live attestation satisfies
the runtime contract fields:

- `listener_ok`
- `models_ok`
- `responses_ok`
- `effective_mode_match`
- `base_url_match`
- `observed_at_utc`
- `attestation_source`

## Alternatives Considered

1. Make `healthcheck --json` the startup owner.
   Rejected. `healthcheck --json` owns live attestation and recovery reporting.
   Making it also start a long-running managed process would mix truth
   observation with lifecycle mutation and would weaken the existing
   `managed_startup_owner` blocker.

2. Make `mode set managed --json` the startup owner.
   Rejected. `mode set` is desired-mode selection. It must not imply effective
   managed truth before live proof.

3. Make `launch smoke --json` the startup owner.
   Rejected. The current smoke seam is the stable-runtime consumer activation
   seam. It must not become managed listener startup by side effect.

4. Make native launch the startup owner.
   Rejected. Native launch proves OS dispatch, process/window evidence, and
   profile isolation. It does not prove a listener on `8320` or runtime
   attestation.

5. Make package delivery the startup owner.
   Rejected. Package delivery can materialize a launcher bundle, but delivery is
   not lifecycle ownership.

6. Make external-models synthetic lifecycle the startup owner.
   Rejected. The external-models adapter is bounded synthetic lifecycle. It
   reserves `8318` and `8320` away from its own allocated ports and explicitly
   does not claim listener truth.

7. Make an external supervisor or out-of-repo launcher the default startup
   owner.
   Rejected as the repo-owned success path. It matches the current blocker
   truth when no repo-owned owner path exists, but it cannot close
   `MANAGED_STARTUP_OWNER_UNDEFINED` or allow the repository to prove startup
   ownership. External launchers may remain explicit non-proof inputs until a
   separate contract accepts them as verified owner paths.

8. Keep startup out of repo forever.
   Rejected as the accepted product direction. It would preserve the blocker,
   but it would not provide a path to a working Codex Custom managed runtime.

## Consequences

- Positive:
  - keeps `CLIProxyAPI` as the engine
  - prevents WBP from becoming a second hidden proxy server
  - preserves `managed_startup_owner` as packet truth
  - separates native launch proof from listener proof
  - gives the implementation contour a narrow write surface
- Negative:
  - this ADR does not start `8320`
  - managed startup remains blocked until a concrete engine executable or
    entrypoint is selected and wired
  - stop/restart semantics still need implementation-level tests
- Implementation constraints:
  - any implementation must add targeted tests for startup success, failure,
    wrong port, stale PID, ambiguous existing listener, and rollback failure
  - live proof belongs to implementation, not to this ADR

## Evidence

- spec:
  - `templates/ADR_TEMPLATE.md`
- tests:
  - `tests/test_cli.py`
    - `test_mode_set_updates_desired_mode`
    - `test_status_reports_listener_down_when_managed_port_is_absent`
    - `test_mode_get_reports_stable_when_managed_listener_is_absent`
    - `test_mode_get_does_not_claim_startup_owner_when_managed_is_live`
    - `test_launch_smoke_repo_owned_default_launcher_is_deterministic_under_hostile_path`
- runtime packet:
  - `managed_startup_owner`
- supporting code:
  - `wild_boar_proxy/runtime.py`
    - `build_managed_startup_owner_surface`
    - `build_repo_owned_default_launcher_script_payload`
    - `run_current_proxy_owner_path_activation`
    - `run_launch_smoke`
    - `run_sync`
  - `wild_boar_proxy/native_launch_contract.py`
  - `wild_boar_proxy/native_launch_dispatch.py`
  - `wild_boar_proxy/external_models/lifecycle.py`
- supporting docs:
  - `CANON.md`
  - `RUNTIME_CONTRACT.md`
  - `STATE_SCHEMA.md`
  - `COMMAND_API.md`

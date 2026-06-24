<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Command API Contract

All operator commands must support `--json`.

## JSON output rules

- `stdout` must contain exactly one JSON object
- `stdout` must not contain leading or trailing non-JSON text
- `stderr` may contain human-readable logs
- invalid JSON is a hard integration failure even when exit code is `0`
- UI and automation must not fall back to plain-text parsing or log parsing

## Required commands

- `status --json`
- `invariant-check --json`
- `sync --json`
- `launch client --json`
- `healthcheck --json`
- `healthcheck --repair --json`
- `rollback --latest --dry-run --json`
- `rollback --latest --apply --json`
- `mode get --json`
- `mode set stable --json`
- `mode set managed --json`
- `policy stage set <10|15|20> --json`
- `rollout rotation inspect --json`
- `rollout posture inspect <15|20> --json`
- `rollout evidence capture 16 --json`
- `rollout stage prove 10 --json`
- `rollout stage prove 15 --json`
- `rollout stage advance 15 <id> --json`
- `rollout stage advance 20 <id> --json`
- `accounts list --json`
- `accounts validate <id> --json`
- `accounts promote <id> --json`
- `accounts demote <id> --json`
- `accounts hold <id> --json`
- `accounts hold <id> --dry-run --json`
- `accounts release <id> --json`
- `accounts retire <id> --json`
- `accounts onboard --json`
- `accounts login start --provider sandbox --json`
- `accounts login start --provider codex --mode device --json`
- `accounts login status --session <id> --json`
- `accounts login complete --session <id> --state <state> --proof <proof> --json`
- `accounts login complete --session <id> --json`
- `accounts login cancel --session <id> --json`
- `external-models credentials admit --provider <provider> --source owner-env --json`
- `external-models credentials status --provider <provider> --json`
- `diagnostics export --json`
- `installer init --json`
- `legacy import --source-dir <path> --json`
- `companion reset --json`
- `companion uninstall --json`
- `package experimental build --output-dir <path> --json`
- `package experimental verify --manifest <path> --json`
- `package launchable build --output-dir <path> [--runtime-executable <path>] --json`
- `package launchable verify --manifest <path> --json`

## Auxiliary working-tool surfaces

- `tools/wbp_dip --json <task>`

`tools/wbp_dip --json <task>` is a bounded Custom Codex working-tool launcher.
It invokes the WBP-owned `delegate_to_dip` MCP tool through the Custom Codex
CLI flow, then requires a bounded live result from the runtime-context allowed
API route before returning success. It emits one JSON packet.

For repository and development tasks, `tools/wbp_dip` also owns the WBP-mediated
repo/action bridge. The bridge is enabled by default in `auto` mode for
repo/project/code/audit/report/fix/test prompts and can be controlled with
`--repo-bridge auto|on|off`. The remote DIP route never receives direct local
filesystem or shell authority; it must request approved WBP tools through strict
JSON tool-call text, and WBP executes those tools locally.

The repository inspected or mutated by that bridge is the server-owned active
project root, not implicitly the WBP checkout and not the `--cd` execution
directory. Operators may pass `--active-project-root <path>`; WBP may also
provide `WBP_ACTIVE_PROJECT_ROOT` from the active runtime context. `--target-repo`
and `WBP_TARGET_REPO` remain legacy compatibility aliases only. Missing,
non-directory, system-root, or sensitive-name active roots fail closed before any
provider turn. Packets must expose active-root proof fields such as
`active_project_root_available`, `active_project_root_source`,
`active_project_root_sha256`, `active_project_root_is_wbp_repo`, and
`active_project_root_fallback_used=false`, while keeping
`active_project_root_path_recorded=false`. Legacy `target_repo_*` fields may be
emitted as aliases, but they are not the primary truth surface.

`--work-mode full` raises the live-result budget for deep investigation and
large reports. A successful live result must also write
`live-result-full-text.txt` inside the proof directory and expose only artifact
metadata in the packet (`live_result_text_artifact_written=true`,
`live_result_text_artifact_path_recorded=false`).

Before and after the `codex exec` hop, `tools/wbp_dip` must repair a known stale
Custom Codex profile model (`gpt-5.3-codex`) back to the requested working model
(`gpt-5.5` by default). The packet must record the repair booleans without
recording the profile config path.

WBP may also perform bounded repo bootstrap reads before the first provider
turn, such as reading explicitly named files or listing files for broad repo
tasks. If DIP answers with prose before required repo/action/code/verification
facts exist, WBP must issue an in-run corrective gate prompt and continue until
the required fact exists or the bounded step budget is exhausted.

Admitted bridge tools:

- `list_files`, `read_file`, `search`, `git_status`
- `propose_patch`, `apply_patch`
- `run_tests`, `run_command`

A repo-inspection claim must not succeed unless at least one repo bridge tool
call succeeds. A fix/implementation/test claim must not succeed unless at least
one action bridge tool call succeeds. A fix/implementation/edit/code-writing
claim must not succeed unless an `apply_patch` tool call actually mutates code
and a subsequent `run_tests` or `run_command` verification succeeds.
Patches are accepted only as bounded unified diffs and are checked with
`git apply --check` before any apply. Commands are allowlisted and executed
without shell interpolation.

Canonical operator entry:

```sh
tools/wbp_dip "DIP: <bounded task>"
```

Canonical Custom Codex DIP entry for repository work:

```sh
tools/wbp_dip --json --work-mode full --repo-bridge on --target-repo "$PWD" "DIP: <bounded repository task>"
```

This is the only admitted Custom Codex operator path for `DIP` repository
analysis, coding, testing, and audit tasks. `dip run` is a lower-level operator
wrapper for readiness/work/chain-join proof and must not be used as a substitute
for Custom Codex free-chat DIP delegation. If the canonical entrypoint returns a
provider/network/auth failure, callers must surface the packet
`machine_error_code` and stop; they must not silently switch to another wrapper,
ordinary Codex subagent, direct provider request, or local imitation.

Canonical repeatable smoke:

```sh
PROOF_DIR="$(mktemp -d /tmp/wbp-dip-smoke.XXXXXX)"
tools/wbp_dip --json --proof-dir "$PROOF_DIR" \
  "DIP: ответь одним коротким пунктом: WBP operator path работает без локальной имитации."
```

It must not write runtime truth, must not set `product_ready=true`, and must not
claim working-tool success unless both conditions are true:

- the captured Codex JSONL contains a successful `delegate_to_dip` tool result
  with API-lane dispatch and no fallback/local imitation;
- `live_result_available=true` with no raw prompt, route id, secret, fallback,
  local imitation, or backend detail exposure in the emitted packet.

Without `--json`, stdout is the bounded live result text for the operator.
With `--json`, stdout is exactly one JSON object and must include:

- `delegate_to_dip_proven=true`
- `api_lane_called=true`
- `route_bound_dispatch_proven=true`
- `live_result_available=true`
- `fallback_used=false`
- `local_imitation_used=false`
- `raw_prompt_recorded=false`
- `prompt_text_recorded=false`
- `live_result_route_id_recorded=false`
- `dip_repo_direct_access=false`
- `dip_repo_tool_bridge_used=true` for repo-inspection success paths
- `dip_action_bridge_used=true` for fix/implementation/test success paths
- `dip_code_written=true` for fix/implementation/edit/code-writing success paths
- `dip_code_verified=true` for fix/implementation/edit/code-writing success paths
- `dip_action_raw_patch_recorded=false`
- `dip_action_raw_command_recorded=false`
- `repo_bridge_mutation_controlled=true`
- `repo_bridge_direct_shell_access=false`
- `repo_bridge_bootstrap_used=true|false`
- `repo_bridge_tool_names=[...]`
- `dip_action_tool_names=[...]`
- `repo_bridge_context_pack_recorded=false`
- `repo_bridge_raw_tool_results_recorded=false`
- `live_result_text_artifact_written=true` for working-result success paths
- `live_result_text_artifact_path_recorded=false`
- `profile_config_model_repaired_before_codex_exec=true|false`
- `profile_config_model_repaired_after_codex_exec=true|false`
- `profile_config_path_recorded=false`

`tools/wbp_dip --proof-only --json <task>` is admitted only for dispatch-proof
diagnostics. It is not a working-result success path.

## DIP run operator wrapper

`dip run --prompt <prompt> --json` is a bounded operator wrapper over the
existing DIP readiness, work, and chain-join command surfaces.

It emits exactly one JSON packet and must not print prose before or after that
packet. Its effect is `mutate` because it runs the work path and writes evidence
packets.

The wrapper must preserve command-surface ownership:

- `dip status` remains a read-only readiness snapshot and must not become an
  auth grant;
- `dip work` owns the fresh preflight and live work path;
- `dip chain-join` remains a read-only join and must not run status, work, API
  calls, or dispatch;
- `dip run` orchestrates those surfaces and summarizes their packet truth.

Readiness status may contribute to the final proof result, but it must not by
itself authorize or prevent the work path. Dispatch eligibility remains owned by
the fresh `dip work` preflight; unsafe readiness packets or evidence-write
failures may still stop the wrapper fail-closed.

On success the `dip run --json` packet must include:

- `operator_command_surface="wild-boar-proxy dip run"`
- `operator_command_mode="run"`
- `effect="mutate"`
- `status_packet_used_as_auth_grant=false`
- `work_mode_proven=true`
- `single_work_run_proven=true`
- `explicit_dip_work_proven=true`
- `api_lane_called=true`
- `route_bound_dispatch_proven=true`
- `live_result_available=true`
- `delivery_proven=true`
- `full_custom_codex_working_flow_proven=true`
- `product_ready=false`
- `custom_codex_ui_visibility_proven=false`
- `raw_prompt_recorded=false`
- `prompt_text_recorded=false`
- `raw_route_id_recorded=false`
- `selected_api_route_id_recorded=false`
- `raw_backend_details_exposed=false`
- `secret_value_exposed=false`
- `blocking_reasons=[]`

If readiness, work, chain-join, evidence writes, or safety checks fail, `dip run`
must fail closed with machine-readable `blocking_reasons` and must not start an
acceptance loop or product-readiness claim by default.

## API-backed Custom Codex manual gate

`codex-runner real-custom-dip-proof --mode work --api-backed-gate --prompt <prompt> --json`
is the bounded live gate for the API-key-backed Custom Codex flow.

This gate is not a ChatGPT UI-session admission and must not be treated as
product readiness. It joins two live facts:

- `router-hook custom-codex-auth-session-readiness` reports the expected Custom
  Codex process/user-data binding and `session_state="API_KEY_ONLY"`;
- the work-mode DIP runner proves one full Custom Codex hook-origin dispatch to
  DIP through the allowed API route with working-flow delivery.

On success the packet must include:

- `api_backed_custom_codex_auth_session_proven=true`
- `api_backed_custom_codex_flow_proven=true`
- `custom_codex_dip_feature_ready=true`
- `feature_ready=true`
- `feature_ready_mode="api_key_backed_custom_codex_dip"`
- `feature_ready_does_not_require_ui_session=true`
- `feature_ready_does_not_prove_product_ready=true`
- `auth_session_machine_error_code="WBP_CUSTOM_CODEX_API_KEY_ONLY"`
- `api_key_only=true`
- `api_key_only_counts_as_ui_session=false`
- `logged_in_ui_session_proven=false`
- `custom_codex_ui_session_ready=false`
- `work_mode_proven=true`
- `work_mode_uses_full_dip_work_mode=true`
- `delegate_to_dip_proven=true`
- `api_lane_called=true`
- `route_bound_dispatch_proven=true`
- `live_result_available=true`
- `direct_provider_auth_proven=true`
- `provider_auth_ok=true`
- `fallback_used=false`
- `local_imitation_used=false`
- `native_codex_subagent_used_as_dip=false`
- `product_ready=false`
- `blocking_reasons=[]`

If the auth readiness is not exactly API-key-only, if the Custom Codex process
is not bound to the expected user-data directory, or if the work runner does not
prove live API-backed DIP dispatch, the gate must fail closed.

## GPT+API+DIP technical acceptance gate

`codex-runner gpt-api-dip-acceptance-gate --fresh-sealed-proof-file <packet> --dip-feature-proof-file <packet> --dip-action-proof-file <packet> --json`
is a read-only join gate over existing machine-readable proof packets. With
`--proof-dir`, it may write only its own acceptance packet.

It must not run live dispatch, read audit history, infer from narrative, or
claim product readiness. The gate passes only when all three owner surfaces are
simultaneously proven:

- `fresh-sealed-e2e-proof` proves the full Custom Codex runtime/UI dispatch
  chain, sealed admission, external freshness, and wrong-digest negative;
- `real-custom-dip-proof --mode work --api-backed-gate` proves API-backed
  Custom Codex DIP feature readiness without UI-session admission;
- `tools/wbp_dip --json` proves the controlled action bridge, code mutation, and
  verification without raw patch/command leakage or direct shell access.

On success the packet must include:

- `feature_ready=true`
- `feature_ready_mode="gpt_api_dip_custom_codex"`
- `gpt_api_dip_ready=true`
- `custom_codex_ui_visibility_proven=true`
- `native_custom_codex_visible_flow_proven=true`
- `full_runtime_dispatch_proven=true`
- `api_backed_custom_codex_dip_feature_ready=true`
- `api_key_only=true`
- `api_key_only_counts_as_ui_session=false`
- `logged_in_ui_session_proven=false`
- `custom_codex_ui_session_ready=false`
- `dip_action_bridge_proven=true`
- `dip_code_written=true`
- `dip_code_verified=true`
- `gate_runs_live_dispatch=false`
- `gate_reads_audit_history=false`
- `input_file_paths_recorded=false`
- `fallback_used=false`
- `local_imitation_used=false`
- `product_ready=false`
- `blocking_reasons=[]`

If any input packet has the wrong `packet_kind`, misses a required positive
claim, overclaims UI-session/product readiness, records raw sensitive material,
or lacks controlled DIP code-write verification, the gate must fail closed.

## GPT+API+DIP product readiness gate

`codex-runner gpt-api-dip-product-ready-gate --acceptance-gate-file <packet> --json`
is the final product-readiness owner surface for the feature-scoped Custom Codex
GPT+API+DIP workflow. With `--proof-dir`, it may write only its own
product-readiness packet.

It must not run live dispatch, read audit history, infer from narrative, or
claim production/distribution release readiness. It may set `product_ready=true`
only when the input `gpt-api-dip-acceptance-gate` packet is already green,
feature-scoped, non-overclaiming, and free of sensitive raw material.

On success the packet must include:

- `feature_ready=true`
- `feature_ready_mode="gpt_api_dip_custom_codex"`
- `gpt_api_dip_ready=true`
- `product_ready=true`
- `product_ready_scope="gpt_api_dip_custom_codex_feature"`
- `product_ready_is_feature_scoped=true`
- `production_release_ready=false`
- `production_release_claim="not_made"`
- `distribution_release_ready=false`
- `signing_status="not_proven"`
- `notarization_status="not_proven"`
- `dmg_status="not_proven"`
- `pkg_status="not_proven"`
- `does_not_prove_distribution_release=true`
- `dip_code_written=true`
- `dip_code_verified=true`
- `fallback_used=false`
- `local_imitation_used=false`
- `blocking_reasons=[]`

If the acceptance packet is not green, preclaims `product_ready=true`, records
raw sensitive material, lacks Custom Codex UI visibility, or lacks controlled DIP
code-write verification, the product-readiness gate must fail closed and must not
set `product_ready=true`.

## Runtime invariant check owner surface

`invariant-check --json` is a read-only runtime truth guard. It machine-checks a
bounded set of runtime invariants and emits advisory recovery hints.

It must not execute recovery, mutate runtime state, or write runtime files.

Additional required fields:

- `invariant_result`
- `recovery_hints`

`invariant_result` must include:

- `status` (`passed` or `failed`)
- `passed`
- `failed`
- `checks`

Each check must include:

- `id`
- `status` (`pass` or `fail`)
- `severity`
- `evidence_source`
- `human_message`
- `machine_error_code`

Each recovery hint must include:

- `machine_error_code`
- `priority_score`
- `impact`
- `urgency`
- `recoverability`
- `risk`
- `diagnosis`
- `operator_action`
- `allowed_next_commands`

Any critical invariant failure must produce a non-green command packet with
`machine_error_code=RUNTIME_INVARIANT_FAILED`.

## Required response fields

Every command response must include all required fields on both success and failure.

- `status`
- `exit_code`
- `human_message`
- `machine_error_code`
- `changed_files`
- `next_action`

## Response rules

- `status` must not collapse liveness, severity, and operator action into one ambiguous token
- `exit_code` must reflect command success or failure
- `human_message` is for operator-readable summary, not machine parsing
- `machine_error_code` must be stable enough for UI and automation branching
- `changed_files` must be an array and may be empty
- `next_action` must be present even when the correct action is `none`
- `operator_action` must use the generic operator-action vocabulary such as
  `none`, `retry`, `user_action`, or `stop`
- `next_action` must be a machine-readable next-step token. The core generic
  tokens are `none`, `retry`, `user_action`, and `stop`. Command-specific
  tokens such as `wait_for_login`, `accounts_onboard`,
  `accounts_refresh`, `api_route_connect`, and `login_complete` are the
  documented active examples.
- For compatibility, the shared semantic validator accepts other token-shaped
  `next_action` values as legacy values. That compatibility acceptance is not
  new command authority: command owners must document any new command-specific
  token with the surface that emits it.
- `next_action` values must use token shape
  `^[A-Za-z][A-Za-z0-9_]{0,127}$`. They must not contain prose, whitespace,
  path fragments, slashes, shell snippets, secret material, or free-form error
  details.
- `next_action=operator_action` is a reserved placeholder and must not be
  emitted as a positive command result.
- new command surfaces should prefer the core generic `next_action` values
  unless domain-specific machine branching is required; any new
  command-specific token must be documented with the surface that emits it
- commands that report runtime health must expose `liveness`, `severity`, and
  `operator_action` as separate top-level fields instead of overloading
  `status`
- commands that carry runtime attestation must expose an `attestation` object
  containing the required attestation fields from `RUNTIME_CONTRACT.md`

## Effect field

Command packets may include additive field `effect`.

Allowed values:

- `read`
- `probe`
- `mutate`
- `repair`

The field describes the command path effect class, not command success,
liveness, severity, readiness, or attestation quality.

Current `read` surfaces:

- `invariant-check --json`
- `status --json`
- `mode get --json`
- `rollback --latest --dry-run --json`
- `accounts list --json`
- `external-models credentials status --provider <provider> --json`

When `effect=read`, `changed_files` must be `[]` and the command must not write
runtime truth state.

`sync --json` is a `mutate` surface. It may refresh runtime truth state, managed
config, runtime effective-mode artifacts, selected-backend snapshots, and
managed pid files. Any real mutation must be reported through `changed_files`;
lock/preflight failures that do not mutate still keep `effect=mutate` because
the command path is mutation-capable.

Account owner surfaces use the same command-path effect rule:

- `accounts validate <id> --json` is `probe`
- `accounts onboard --json` is `mutate`
- `accounts login start --provider <provider> ... --json` is `mutate`
- `accounts login status --session <id> --json` is `read`
- `accounts login complete --session <id> ... --json` is `mutate`
- `accounts login cancel --session <id> --json` is `mutate`
- `accounts promote|demote|hold|release|retire <id> --json` are `mutate`

`accounts login status --session <id> --json` must not persist session refresh
observations or terminate session processes. It may report device handoff,
stale-process, expiry, and auth-materialization observations from owner-managed
session/log/auth surfaces, but persisted session mutation belongs to the
`start`, `complete`, and `cancel` owner surfaces.

`status --json` is a read-only snapshot surface. It may summarize persisted
state, registry, config, and cached contract surfaces, but it must not delegate
to live healthcheck, recovery, launcher, or owner-path mutation. Its
`changed_files` value must be `[]`.

`healthcheck --json` must not be labeled `read` merely because it is
observational. It is a `probe` surface: it may run live attestation but must not
write runtime truth state, clean stale pid files, run fallback reconciliation,
launch recovery, adopt current proxy, refresh last-known-good proxy, or report
repair writes. Its `changed_files` value must be `[]`.

`healthcheck --repair --json` is the explicit `repair` surface for bounded
healthcheck owner-path recovery, fallback reconciliation, current-proxy
adoption, last-known-good refresh, and stale pid cleanup. Any real mutation must
be reported through `changed_files`.

For Phase 1 mutation-ledger evidence, `healthcheck --repair --json` also emits
packet-only additive fields:

- `mutation_id`
- `mutation_ledger`

`changed_files` remains the compatibility field and stays `list[str]`.
`mutation_ledger.changed_files` is the structured evidence surface with one
record per top-level changed path. Regular files expose before/after SHA-256
where available. Directories, missing paths, and other path kinds must not fake
file hashes.

Phase 1 does not add a persisted mutation store or rollback API. Rollback fields
must remain non-actionable:

- `rollback_available=false`
- `rollback_id=null`
- `rollback_phase=ledger_only`

Phase 2 may expose rollback readiness for a narrow command-owned P0 transaction
only when the command packet, mutation ledger, and transaction metadata all
refer to the same mutation:

- `mutation_id` equals transaction metadata `mutation_id`
- `mutation_ledger.rollback_available=true`
- `mutation_ledger.rollback_id` equals transaction metadata `rollback_id`
- `mutation_ledger.rollback_phase=last_transaction`
- `mutation_ledger.transaction_id` names the committed transaction metadata

For Phase 2 healthcheck repair wiring, this currently applies only to the
`healthcheck_last_known_good_proxy_refresh` scope. The compatibility
`changed_files` field remains a `list[str]` of top-level owner truth-state
changes. Transaction-store writes are accounted separately through
`mutation_ledger.transaction_store_artifacts`; they must not be hidden, but they
also must not be treated as owner truth-state changes.

If a repair packet includes any changed top-level path that is not covered by
the rollback-eligible transaction metadata, rollback fields must stay
non-actionable (`rollback_available=false`, `rollback_id=null`,
`rollback_phase=ledger_only`) and `mutation_ledger.transaction_id` must be
absent.

`rollback --latest --dry-run --json` is a read-only transaction preflight
surface. It must emit `effect=read`, `changed_files=[]`, and must not call the
mutating rollback helper. It may expose:

- `rollback_available`
- `rollback_id`
- `transaction_id`
- `mutation_id`
- `rollback_status`
- `rollback_blocked_reasons`
- `would_change_files`
- `rollback_files`

`rollback --latest --apply --json` is the only rollback apply surface admitted
in this phase. It is an explicit `repair` command and must select only the
latest rollback-eligible committed transaction. It must not accept
`--mutation-id`, arbitrary transaction ids, or history selection. Apply must run
the same transaction-layer preflight before writes, and a green packet requires
both:

- `state_transaction.rollback_latest_state_transaction(...)` completed
- post-rollback filesystem verification proves each target returned to
  `sha256_before`, or is absent when the transaction created it

If preflight is blocked, no transaction is eligible, the target has drifted, a
backup is missing, the transaction store is dirty, or the rollback is repeated
after success, the command must emit an error packet with `changed_files=[]`.
If post-rollback verification fails after writes occurred, the command must
still emit an error packet, but `changed_files` must report the actual files
changed by the attempted apply and `post_rollback_verification` must carry the
failed evidence. Phase 2 does not add `rollback --mutation-id <id> --json`.

## Severity classes

- `recoverable`
- `fatal`

## Additional experimental package owner surface

`package experimental build --output-dir <path> --json` is the owner surface for
local experimental package materialization.

It must emit:

- a package artifact (`tar.gz` or `zip`) built from allowlisted repo
  source/docs material only
- a checksum manifest for the artifact
- metadata with repository truth policy when available

The package surface must not include runtime/private data such as auth files,
runtime dumps, logs, `.env`, or `~/.codex-custom-cli` material.

`package experimental verify --manifest <path> --json` is the owner surface for
artifact existence + checksum verification from the manifest.

## Additional launchable package owner surface

`package launchable build --output-dir <path> [--runtime-executable <path>] --json`
is the owner surface for local launchable desktop package materialization.

It must emit:

- one launchable desktop artifact path
- a checksum manifest for the artifact
- metadata with the selected runtime executable and runtime-capability probe
- runtime dependency truth:
  `runtime_dependency_strategy=external_selected_runtime`,
  `standalone_runtime_embedded=false`, and
  `cross_machine_portability_claim=not_made`
- integrity binding for both the artifact and the companion metadata used for
  launchability claims
- an installer-stage admission packet for the bounded `.app` bundle strategy,
  with production release claims explicitly absent until the release gate admits
  signing and notarization
- only allowlisted repo source/docs material plus the minimal launcher/bundle
  scaffolding required for packaged launch

The launchable package surface must not include runtime/private data such as
auth files, runtime dumps, logs, `.env`, or `~/.codex-custom-cli` material.

The launchable package installer-stage admission is not a production release
claim. Until a separate release gate admits signing and notarization, it must
remain bounded to:

- `strategy=app_bundle_only`
- `production_release_claim=not_made`
- `production_release_status=deferred_by_release_gate`
- `signing_status=not_signed`
- `notarization_status=not_notarized`
- `dmg_status=not_built`
- `pkg_status=not_built`

`package launchable verify --manifest <path> --json` is the owner surface for
artifact existence + checksum verification + launchable bundle boundary +
metadata-integrity verification from the manifest.

Launcher smoke from a copied `.app` may prove relocated local startup only. It
must not be treated as private-data boundary verification, standalone runtime
proof, cross-machine portability proof, or production release proof.

## Additional onboarding owner surface

`accounts onboard --json` is the owner surface for reserve-first onboarding
truth.
The onboarding owner lane supports external launcher invocation modes `--once`
and `--loop`; the selected mode must remain visible in the emitted owner
packet command surface.

When no `--auth-ref` is provided and no sandbox-local auth candidate exists,
the historical owner helper may start the engine-owned Codex login flow through
`cli-proxy-api -codex-login` for compatibility. New web/account-connect flows
must prefer the sessionized Codex login owner surface documented below. In a
web sandbox runner any login flow must write only to a sandbox-scoped auth
directory; the browser still never sends tokens, passwords, auth files, local
paths, backend ids, or auth refs.

Onboarding success must not be inferred from external onboarding process exit
code alone.
Successful owner packets must prove, machine-readably:

- a uniquely selected resulting backend identity
- resulting placement in `reserve`
- no silent active-routing change
- post-onboard validate outcome
- post-onboard sync outcome, unless explicitly skipped
- post-onboard status proof summary

`accounts onboard --json` may expose a nested `onboarding_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `input_mode`
- `explicit_auth_ref`
- `new_backend_ids`
- `selected_backend_id`
- `selection_status`
- `reserve_first_enforced`
- `auth_snapshot_before_login_status`
- `auth_snapshot_before_login_count`
- `auth_snapshot_before_login_digest`
- `auth_snapshot_before_login_source`
- `pool_after_onboarding`
- `validate_attempted`
- `validate_outcome`
- `sync_attempted`
- `sync_outcome`
- `status_observed`
- `external_command_exit_code`
- `external_command_status`
- `active_routing_changed`
- `final_outcome`

Canonical onboarding outcomes include:

- `explicit_auth_imported_to_reserve`
- `reserve_only_success`
- `no_new_auth_detected`
- `ambiguous_new_auth_detection`
- `validate_failed`
- `sync_failed`
- `status_failed`
- `import_failed`

Reserve-first onboarding remains separate from promotion.
`accounts onboard --json` must not place a newly admitted backend directly into
`active`, and any ambiguous or missing identity proof must stop with
`operator_action = user_action`.

## Additional sandbox login owner surface

`accounts login start --provider sandbox --json` is the owner surface for
sandbox-only login admission session issuance.

`accounts login complete --session <id> --state <state> --proof <proof> --json`
is the owner surface for session-bound sandbox login completion.

Sandbox login packets must remain strict JSON and use the command payload
envelope. Session storage is control-layer managed only:

- `<managed_dir>/login-sessions/<id>.json`
- required session fields:
  `login_session_id`, `provider`, `state`, `nonce`, `created_at`, `expires_at`,
  `used`

Completion must enforce machine-readably:

- provider/session validation (`sandbox` only)
- session existence
- exact state match
- proof equality `sandbox-ok`
- TTL expiry rejection
- replay rejection when `used=true`

Start success should expose:

- `next_action=login_complete`
- `login_session_id`
- `state`
- `nonce`
- `expires_at`
- `login_url`
- `login_result.status=started`
- `login_result.auth_materialized=false`

Completion success may materialize only sandbox-owned synthetic auth under
managed storage and must return:

- `next_action=accounts_onboard`
- `auth_ref`
- `auth_ref_scope=sandbox`
- `login_result.status=completed`
- `login_result.auth_materialized=true`
- `login_result.used=true`

Completion packets must not expose token/secret/password values.

## Additional Codex login session owner surface

`accounts login start --provider codex --mode device --json` is the owner
surface for sessionized Codex device login handoff.

`accounts login status --session <id> --json` is the read-only owner surface
for session state, device handoff status, and sandbox auth materialization
proof.

`accounts login complete --session <id> --json` is the owner surface for
session-bound reserve-first onboarding after auth materializes.

`accounts login cancel --session <id> --json` is the owner surface for
bounded cancellation of a session-owned login process.

Codex login session packets must remain strict JSON and use the command payload
envelope. Session storage is owner-managed only:

- `<managed_dir>/login-sessions/<id>.json`
- `<managed_dir>/login-sessions/<id>.stdout.log`
- `<managed_dir>/login-sessions/<id>.stderr.log`

Required session fields include:

- `login_session_id`
- `provider=codex`
- `mode=device`
- `pid`
- `created_at`
- `expires_at`
- `state`
- `device_url`
- `device_code_present`
- `auth_materialized`
- `auth_ref`
- `sandbox_scope`
- `used`

Start must enforce machine-readably:

- provider validation (`codex`)
- mode validation (`device`)
- sandbox-scoped auth-dir proof before spawn
- session creation under managed storage
- bounded spawn of `cli-proxy-api -codex-device-login -no-browser`
- device handoff capture from owner stdout

Start success should expose:

- `next_action=wait_for_login`
- `provider=codex`
- `mode=device`
- `session_id`
- `login_session_id`
- `device_url`
- `device_code`
- `device_code_present=true`
- `login_result.status=waiting_for_user`
- `login_result.auth_materialized=false`
- `login_result.browser_secret_intake=false`
- `login_result.browser_path_intake=false`

Status must enforce machine-readably:

- session existence
- provider/session binding
- TTL expiry detection
- stale pid refresh
- sandbox auth artifact detection without exposing secret contents

Status success should expose:

- `next_action=wait_for_login|accounts_onboard|none`
- `login_result.status`
  (`waiting_for_user|auth_materialized|completed|failed|expired|cancelled`)
- `login_result.device_url`
- `login_result.device_code_present`
- `login_result.auth_materialized`
- `login_result.auth_ref_present`

Complete must enforce machine-readably:

- session existence
- provider/session binding (`codex`)
- replay rejection when `used=true`
- reject before `auth_materialized=true`
- owner-side onboarding only through `accounts onboard --json --auth-ref <session auth>`
- reserve-first onboarding proof
- `active_routing_changed=false`

Complete success should expose:

- `next_action=accounts_refresh`
- `login_result.status=completed`
- `login_result.auth_materialized=true`
- `login_result.used=true`
- nested `onboarding_result`

Cancel must enforce machine-readably:

- session existence
- provider/session binding (`codex`)
- termination bounded to session-owned pid only

Cancel success should expose:

- `next_action=none`
- `login_result.status=cancelled`
- `login_result.cancelled_process_owned_by_session=true`

Codex login packets must not expose token/secret/password values or raw auth
JSON.

## Additional external-models credential admission owner surface

`external-models credentials admit --provider <provider> --source owner-env --json`
is the owner surface for sandbox-only provider credential admission used by API
route connect flows.

`external-models credentials status --provider <provider> --json` is the
read-only owner surface for credential presence proof.

Admission and status packets must remain strict JSON and use the command
payload envelope. The owner surface must enforce machine-readably:

- provider allowlist validation
- source validation (`owner-env` only for this contour)
- sandbox write-target proof before write
- sandbox-only secrets materialization
- secret redaction in packet payloads

Admission success should expose:

- `next_action=api_route_connect`
- `credential_result.status=admitted`
- `credential_result.provider`
- `credential_result.source=owner-env`
- `credential_result.credential_ref`
- `credential_result.credential_present=true`
- `credential_result.secret_value_exposed=false`
- `credential_result.browser_secret_intake=false`
- `credential_result.browser_path_intake=false`
- `credential_result.scope=sandbox`

Status success should expose:

- `next_action=none`
- `credential_result.status` (`present` or `missing`)
- `credential_result.provider`
- `credential_result.credential_ref`
- `credential_result.credential_present`
- `credential_result.secret_value_exposed=false`
- `credential_result.scope=sandbox`

Admission and status packets must not expose token/secret/password values or
raw owner-env dumps.

## Additional local token owner surface

`token --json` is the owner surface for bounded inspection of the local WBP
token contract used by trusted machine consumers.

`token` without `--json` is a machine-consumer surface for trusted local
consumers such as Codex `auth.command`. It prints the plain local listener
bearer token to stdout and must not be used as a browser surface.

In the pinned local observation used by the auth-command contract proof contour
(`codex-cli 0.128.0`), `auth.command` behaved as an exact executable string,
not a command-plus-args packet surface. For that bounded observation, the
repo-owned execution helper lives at the repository root:

- `wbp_codex_auth_command.py`

That helper is allowed to emit the plain local listener bearer token to stdout
for its trusted machine consumer only. It is not a browser surface and it is
not packet truth by itself.

The token contract must remain bounded and machine-readably enforce:

- source kind is the stable runtime generated config
- output shape is `plain_token_stdout`
- token is local-only
- browser secret intake is false
- browser path intake is false
- JSON packet surfaces do not expose the token value

`token --json` success should expose:

- `next_action=none`
- `data.token_source_kind=stable_runtime_generated_config`
- `data.token_output_shape=plain_token_stdout`
- `data.token_present=true`
- `data.token_emitted=false`
- `data.secret_value_exposed=false`
- `data.scope=owner_local_listener`
- `data.local_only=true`

The plain `token` surface is allowed to emit the bearer token only to stdout for
its trusted machine consumer. It is not a packet truth surface and must not be
used as evidence by itself.

## Additional Codex CLI runner surface

`codex-runner smoke --json --prompt <text>` is a bounded non-native Codex CLI
runner surface.

It must remain explicitly non-native and machine-readably enforce:

- `consumer_kind=codex_cli_runner`
- `native_app_claimed=false`
- reusable runner launch surface classification
- isolated session root / `CODEX_HOME` ownership via session packet truth
- transcript packet present
- cleanup packet present

This surface is not native `Codex.app`, not a window proof surface, and not an
Original-via-WBP surface.

## Additional external-models route verification surfaces

`external-models routes validate --route <id> --json` is the owner surface for
route-level provider model visibility proof.

`external-models check --route <id> --json` is the owner surface for route-level
provider smoke proof.

Both surfaces must remain route-local. They may write route observation state and
network evidence, but they must not claim live listener readiness or mutate Codex
account routing.

Verification must block before any provider network call when:

- the route is disabled;
- the route has `cost_class=paid_direct`;
- the route secret is missing or invalid.

Disabled routes must return a non-green packet with
`machine_error_code=route_disabled` and `data.route_state=blocked`.

Successful route validation/check packets should expose:

- `verification_scope=route_provider_only`
- `requested_model`
- `effective_model`
- `provider`
- `listener_proven=false`
- `runtime_claim_blocked=true`
- `profile_ready=false`

## Additional launch-client owner surface

`launch client --json` is the owner surface for bounded external host-client
dispatch truth.

Launch success must not be inferred from OS invocation alone as end-to-end
client-session success.
Successful owner packets must prove, machine-readably:

- explicit bounded client-path input
- runtime precondition checked before dispatch
- effective mode and endpoint observed before dispatch
- env sanitization before launch
- bounded dispatch observation at the OS invocation layer only
- no stronger claim than dispatch truth

`launch client --json` may expose a nested `client_launch_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `client_path`
- `client_path_kind`
- `runtime_precondition_checked`
- `runtime_precondition_status`
- `effective_mode_observed`
- `endpoint_observed`
- `profile_context`
- `env_sanitized`
- `dispatch_method`
- `dispatch_attempted`
- `dispatch_observed`
- `dispatch_exit_code`
- `launch_claim_scope`
- `final_outcome`

Canonical launch-client outcomes include:

- `dispatch_requested`
- `runtime_precondition_failed`
- `client_path_missing`
- `client_path_invalid`
- `dispatch_failed`
- `unsupported_launch_shape`

`launch client --json` remains separate from:

- runtime health ownership in `healthcheck --json`
- read-only runtime snapshot readout in `status --json`
- runtime smoke activation truth in `launch smoke --json`

## Additional staged pool-policy owner surface

`policy stage set <10|15|20> --json` is the owner surface for staged
pool-policy mutation truth.

Stage-policy update success must not be inferred from raw schema mutation alone.
Successful owner packets must prove, machine-readably:

- the requested stage is canonically supported
- the current `pool_policy` is valid before mutation
- the stage-to-policy mapping used for the update
- a rollback point captured before write
- post-write policy verification
- no stronger claim than policy truth itself

`policy stage set <10|15|20> --json` may expose a nested
`pool_policy_update_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `requested_stage`
- `mapped_pool_policy`
- `previous_pool_policy`
- `next_pool_policy`
- `policy_validation_status`
- `stage_mapping_status`
- `rollback_point_captured`
- `write_attempted`
- `write_observed`
- `rollback_attempted`
- `rollback_outcome`
- `final_outcome`

Canonical stage-policy outcomes include:

- `stage_policy_updated`
- `already_on_stage`
- `policy_invalid`
- `unsupported_stage`
- `rollback_completed_after_failed_verification`
- `rollback_failed`

`policy stage set <10|15|20> --json` remains separate from:

- active-pool growth execution in `accounts promote <id> --json`
- stage-completion proof in later rollout contours
- runtime-health ownership in `healthcheck --json`
- delegated registry readout in `accounts list --json`

## Additional rollout rotation evidence surface

`rollout rotation inspect --json` is the bounded read surface for rollout
participation evidence truth.

Participation evidence success must not be inferred from raw blocker tokens or
logs alone.
Successful owner packets must prove, machine-readably:

- the bounded local evidence sources that were inspected
- the observed selected backend ids snapshot
- the observed active-pool posture relevant to participation
- whether policy drift or registry identity contradicts participation evidence
- whether evidence is available, insufficient, contradicted, or unknown
- no stronger claim than bounded local participation evidence itself

`participation_evidence_insufficient` must stay precise:

- it may report that the registry active pool is not yet observably expanded
- it may report that the registry active pool is expanded but routing-eligible
  active candidates are not yet observably expanded

`rollout rotation inspect --json` may expose a nested
`rotation_evidence_result` surface.
Preferred fields include:

- `schema_version`
- `observed_at_utc`
- `evidence_status`
- `evidence_source`
- `evidence_source_layer`
- `evidence_source_class`
- `evidence_source_name`
- `evidence_source_run_id`
- `evidence_producer_version`
- `evidence_freshness`
- `selected_backend_snapshot_validation_status`
- `selected_backend_snapshot_validation_error`
- `selected_backend_snapshot_compatibility`
- `selected_backend_snapshot_present`
- `selected_backend_ids`
- `selected_backends_digest`
- `expected_selected_backends_digest`
- `status`
- `attempted`
- `requested_scope`
- `selected_backend_ids_observed`
- `active_pool_count_observed`
- `runtime_active_pool_count_observed`
- `registry_active_pool_count_observed`
- `active_routing_candidate_ids_observed`
- `active_pool_count_agreement_status`
- `stable_inventory_status`
- `policy_drift_status`
- `registry_identity_status`
- `evidence_sources`
- `evidence_strength`
- `evidence_reason`
- `participation_status`
- `participation_summary`
- `blocker_type`
- `claim_scope`
- `final_outcome`

Canonical rotation-evidence outcomes include:

- `participation_evidence_present`
- `participation_evidence_stale`
- `participation_evidence_available`
- `participation_evidence_insufficient`
- `participation_evidence_contradicted`
- `participation_evidence_unknown`
- `participation_evidence_unavailable`

Preferred selected-backend evidence source is
`runtime_state.selected_backend_snapshot`.
Legacy flat `runtime_state.selected_backend_ids` remains accepted only as a
compatibility surface when it carries a same-event observation timestamp.

`runtime_state.selected_backend_snapshot` is a read contract for cached bounded
runtime participation evidence.
In this contour it may be materialized only by the serialized runtime-state
owner path in `sync --json`, and only after sync succeeded with managed-listener
health verified.
`rollout rotation inspect --json` validates it but does not create, repair, or
mutate it.

Required nested snapshot fields are:

- `schema_version`
- `snapshot_kind`
- `source_class`
- `source_name`
- `source_run_id`
- `producer_version`
- `observed_at_utc`
- `selected_backend_ids`
- `selected_backends_digest`
- `claim_scope`

Accepted `snapshot_kind`:

- `selected_backend_participation`

Accepted `claim_scope`:

- `bounded_local_participation_evidence_only`

Accepted `source_class` values:

- `engine_observed`
- `runtime_observed`
- `supervisor_owner_observed`
- `external_owner_path_observed`

Rejected source classes include registry-synthesized or count-derived claims.
Selected backends must never be synthesized from active registry ids, registry
active counts, or routing-candidate counts.

Invalid nested snapshots must not silently fall back to legacy flat fields.
A digest mismatch is contradicted evidence.
Unsupported schema, kind, source class, or missing source metadata is unknown
evidence and blocks the claim until repaired.

`selected_backend_ids` and `selected_backend_ids_observed` must come from a
runtime, supervisor, engine, or external owner snapshot of selected backends.
They must not be synthesized from registry active ids, registry active counts,
or routing-candidate counts.
Selected backend ids without `observed_at_utc` from the same observation event
must not be treated as available participation evidence.

When the owner path materializes a selected backend snapshot from live-capable
registry entries, candidate ordering must be deterministic and machine-readable.
The current runtime ranking policy is:

1. lower `priority` first;
2. lower `fail_count` first;
3. higher `success_count` first;
4. `backend_id` ascending as a stable tie-breaker.

`auth_pool_hygiene` may expose `ranking_policy.status=applied` and the ordered
`launch_capable_backend_ids`. This ranking is a candidate-selection input only;
it must not bypass lifecycle gates, selected-backend evidence validation, or
reserve/active policy proof.

`evidence_strength` is the normalized strength axis and must use:

- `strong`
- `partial`
- `weak_log_derived`
- `none`

`evidence_reason` carries the narrower local reason such as
`multi_backend_snapshot`, `selected_backend_snapshot_missing`, or
`policy_drift_detected`.

`blocker_type` must use:

- `none`
- `observability`
- `unsupported_api`
- `stale_state`
- `schema_gap`
- `contradicted_state`

Rotation evidence `machine_error_code` values include:

- `OK`
- `ROTATION_EVIDENCE_STALE`
- `ROTATION_EVIDENCE_UNKNOWN`
- `ROTATION_EVIDENCE_UNAVAILABLE`
- `ROTATION_EVIDENCE_INSUFFICIENT`
- `ROTATION_EVIDENCE_CONTRADICTED`

`rollout rotation inspect --json` remains separate from:

- stable-10 proof ownership in later rollout contours
- lifecycle mutation under `accounts ... --json`
- policy mutation under `policy stage set ... --json`
- runtime-health ownership in `healthcheck --json`

## Additional rollout posture classification surface

`rollout posture inspect <15|20> --json` is the read-only owner surface for
pre-stage-advance posture classification.

It must not mutate registry, state, policy, mode files, selected-backend
snapshots, stable inventory, auth files, or repair targets. It may aggregate
cached local state, policy-stage truth, lifecycle candidate classification, and
bounded rotation-evidence observation. It must not run hidden recovery, policy
repair, registry normalization, promotion, demotion, or stage advancement.

Top-level `machine_error_code` remains the authoritative command truth surface.
Nested `classification` and `blocker_code` under `rollout_posture_result`
provide explanatory posture detail only and must not contradict the top-level
command outcome.

The command may expose a nested `rollout_posture_result` surface. Required
fields include:

- `requested_stage`
- `source_stage`
- `classification`
- `blocker_code`
- `pool_count_summary`
- `candidate_summary`
- `runtime_truth_summary`
- `policy_stage_summary`
- `rotation_summary`
- `normalization_decision_packet`
- `final_outcome`

Canonical posture classifications include:

- `INSUFFICIENT_ELIGIBLE_POOL`
- `RESERVE_CANDIDATE_NOT_IDENTIFIED`
- `LIVE_POSTURE_DRIFT_ONLY`
- `ROTATION_EVIDENCE_INSUFFICIENT`
- `READY_FOR_STAGE_ADVANCE`
- `READY_ALREADY_ON_TARGET`

`rollout posture inspect <15|20> --json` may also surface canonical target-stage
blockers such as `STAGE_ADVANCE_POLICY_STAGE_NOT_CANONICAL` when the requested
advance target is not on a canonical policy-stage path.

A `READY_FOR_STAGE_ADVANCE` classification means only that the current read-only
posture is compatible with a later explicit
`rollout stage advance <stage> <reserve-id> --json` attempt. It is not a
`STABLE_20_PROVED`, `SCALE_COMPLETE`, `PILOT_READY`, or live scale-proof claim.

`runtime_truth_summary` is intentionally not a live runtime attestation.
`status --json`, `healthcheck --json`, `rollout rotation inspect --json`, and
any required smoke or fallback checks remain separate gates.

`rollout posture inspect <15|20> --json` remains separate from:

- lifecycle mutation under `accounts ... --json`
- policy mutation under `policy stage set ... --json`
- stage-proof ownership under `rollout stage prove ... --json`
- stage-advance ownership under `rollout stage advance ... --json`
- live runtime attestation under `healthcheck --json`

## Additional scale evidence packet surface

`rollout evidence capture 16 --json` is the owner surface for the
16-account field evidence packet gate.

It may aggregate existing machine evidence, but it is not a new runtime truth
engine.
It must not create a `stable_16_proved`, `stable_20_proved`, `scale_complete`,
`pilot_ready`, or `production_ready` claim.

The only successful claim scope for this contour is:

- `field_evidence_observed_only`

`rollout evidence capture 16 --json` may expose a nested
`scale_evidence_packet_result` surface.
Required fields include:

- `schema_version`
- `claim_target`
- `claim_scope`
- `packet_status`
- `observed_at_utc`
- `commit_hash`
- `runtime_version`
- `environment_note`
- `runtime_attestation_status`
- `strict_json_command_api_status`
- `state_serialization_status`
- `rotation_evidence_status`
- `fallback_readiness_status`
- `pool_counts_status`
- `diagnostics_redaction_status`
- `selected_backend_snapshot_status`
- `accounts_summary_status`
- `pool_counts`
- `selected_backend_snapshot_summary`
- `accounts_summary`
- `runtime_attestation_summary`
- `rotation_evidence_summary`
- `fallback_readiness_summary`
- `diagnostics_bundle_summary`
- `scale_gate_summary`
- `blocked_reasons`
- `final_outcome`

Allowed `claim_target`:

- `16`

Allowed `packet_status` values:

- `complete`
- `incomplete`
- `contradicted`
- `unsafe_to_claim`

Allowed `final_outcome` values:

- `field_evidence_packet_complete`
- `field_evidence_packet_incomplete`
- `field_evidence_packet_contradicted`
- `field_evidence_packet_unsafe_to_claim`

The command may write a redacted evidence bundle to a temp/export directory.
It must not write:

- `backend-registry.json`
- `supervisor-state.json`
- runtime mode or effective-mode files
- `selected_backend_snapshot`
- active/reserve/retired lifecycle state
- proxy adoption state
- last-known-good proxy state

Any delegated healthcheck must be non-mutating:

- no recovery write
- no stable fallback write
- no current-proxy auto-adoption
- no last-known-good proxy write
- no stable repair apply

The evidence packet must treat runtime attestation, rotation evidence, fallback
readiness, accounts summary, and diagnostics redaction as separate axes.
It must not infer selected backend participation from registry active ids,
registry active counts, or pool policy.
`scale_gate_summary` is a derived gate view over existing packet fields and
must not become a new source-of-truth surface.

`scale_gate_summary` must include gates:

- `RUNTIME_ATTESTATION_GATE`
- `STRICT_JSON_COMMAND_API_GATE`
- `STATE_SERIALIZATION_GATE`
- `FALLBACK_DRILL_GATE`
- `SCALE_EVIDENCE_PACKET_GATE`

`STRICT_JSON_COMMAND_API_GATE` must fail if delegated owner-payload shapes are
not valid command-packet JSON surfaces.

`diagnostics_redaction_status=failed` or any runtime write-surface mutation
must produce `packet_status=unsafe_to_claim`.
Contradicted rotation evidence or ambiguous registry identity must produce
`packet_status=contradicted`.
Missing, stale, or insufficient evidence must produce
`packet_status=incomplete`.

## Additional stage-proof owner surfaces

`rollout stage prove 10 --json` and `rollout stage prove 15 --json` are the
owner surfaces for canonical stage-proof truth at stages `10` and `15`.

Stage-proof success must not be inferred from:

- policy stage alone
- stale status alone
- logs alone
- rotation evidence alone
- runtime smoke alone

Successful owner packets must prove, machine-readably:

- the current staged policy matches the requested canonical stage
- active-pool posture is aligned with the requested stage policy
- reserve-pool posture is aligned with the requested stage policy
- bounded rotation evidence is not contradicted
- live runtime attestation passed
- bounded runtime smoke passed
- delegated runtime smoke did not displace or invalidate the managed runtime
  proof surface being certified
- rollback-readiness remained available
- all delegated evidence lines stayed delegated rather than replacing their
  owner surfaces

`rollout stage prove 10 --json` and `rollout stage prove 15 --json` may expose a nested `stage_proof_result`
surface.
Preferred fields include:

- `status`
- `attempted`
- `requested_stage`
- `policy_stage_status`
- `policy_stage_observed`
- `policy_mapping_status`
- `active_pool_count_observed`
- `reserve_pool_count_observed`
- `rotation_evidence_status`
- `runtime_attestation_status`
- `runtime_smoke_status`
- `rollback_readiness_status`
- `delegated_evidence`
- `proof_gate_status`
- `final_outcome`

Canonical stage-proof outcomes include:

- `stable_10_proved`
- `stable_15_proved`
- `stage_policy_mismatch`
- `insufficient_active_pool`
- `reserve_posture_mismatch`
- `rotation_evidence_insufficient`
- `rotation_evidence_contradicted`
- `runtime_attestation_failed`
- `runtime_smoke_failed`
- `rollback_readiness_failed`
- `proof_blocked`

Current reserve-semantics note:

- `accounts promote <id> --json` preserves `reserve_target` as a reserve floor
- `rollout stage prove 10 --json` and `rollout stage prove 15 --json` currently
  require exact reserve-posture alignment against the stage target when closing
  proof
- surplus reserve may therefore remain promotion-legal while still producing
  `reserve_posture_mismatch` in stage proof

`rollout stage prove 10 --json` and `rollout stage prove 15 --json` remain separate from:

- policy mutation under `policy stage set ... --json`
- bounded rotation evidence ownership under `rollout rotation inspect --json`
- runtime-health ownership under `healthcheck --json`
- runtime smoke ownership under `launch smoke --json`
- lifecycle mutation under `accounts ... --json`
- stage execution toward `15` or `20`

## Additional stage-advance owner surfaces

`rollout stage advance 15 <id> --json` and `rollout stage advance 20 <id> --json`
are the owner surfaces for one-step controlled stage progression.

- `rollout stage advance 15 <id> --json` advances from canonical stable stage
  `10` toward canonical stage `15`
- `rollout stage advance 20 <id> --json` advances from proven stage `15`
  toward canonical stage `20`

Stage-advance success must not be inferred from:

- policy write alone
- promotion subprocess exit alone
- implicit reserve-target selection
- hidden best-reserve logic
- any direct lifecycle mutation outside delegated `accounts promote <id> --json`
- any direct policy rewrite outside delegated `policy stage set ... --json`

Successful owner packets must prove, machine-readably:

- explicit backend id input (no fallback selection)
- stable-10 proof gate delegated through `rollout stage prove 10 --json`
  when the current policy stage is canonical `10` for stage-15 advancement
- stable-15 proof gate delegated through `rollout stage prove 15 --json`
  when the current policy stage is canonical `15` for stage-20 advancement
- canon-first one-step sequencing:
  delegated policy transition to the requested stage, then one explicit promotion
  step, or one explicit promotion step when already on the requested canonical stage
- postflight attestation, rotation, and readiness checks delegated to their
  owner surfaces
- delegated failures resolve conservatively and may trigger rollback of the
  bounded advancement step
- no stronger claim than one-step control-layer progression; no stage-proof claim

Current reserve-semantics note:

- postflight promotion verification currently expects exact reserve-posture
  alignment against the target-stage reserve target
- this is stricter than the promotion-floor rule used by
  `accounts promote <id> --json`

`rollout stage advance 15 <id> --json` and `rollout stage advance 20 <id> --json`
may expose a nested
`stage_advancement_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `requested_stage`
- `requested_backend_id`
- `preflight_stage10_proof_status`
- `preflight_stage15_proof_status`
- `preflight_policy_status`
- `policy_transition_status`
- `promotion_status`
- `postflight_attestation_status`
- `postflight_rotation_status`
- `rollback_readiness_status`
- `rollback_attempted`
- `rollback_outcome`
- `delegated_evidence`
- `final_outcome`

Canonical stage-advance outcomes include:

- `advanced_one_step`
- `already_at_stage_15_target`
- `already_at_stage_20_target`
- `stable_10_proof_failed`
- `stable_15_proof_failed`
- `backend_not_eligible`
- `preflight_verification_failed`
- `policy_transition_failed`
- `rollback_completed_after_failed_step`
- `rollback_failed`

`rollout stage advance 15 <id> --json` and `rollout stage advance 20 <id> --json`
remain separate from:

- stable-10 proof ownership under `rollout stage prove 10 --json`
- stable-15 proof ownership under `rollout stage prove 15 --json`
- policy mutation ownership under `policy stage set ... --json`
- lifecycle mutation ownership under `accounts ... --json`
- rotation evidence ownership under `rollout rotation inspect --json`

## Additional promotion owner surface

`accounts promote <id> --json` is the owner surface for single-account
promotion truth.

Promotion packets must emit `effect="mutate"` and packet-only additive field
`mutation_id`.

`mutation_id` must be `null` when promotion exits with `changed_files=[]`,
including precondition failure and validation failure.
When promotion leaves bounded owner truth-state changes in `changed_files`,
`mutation_id` must be a stable planned mutation id for the promotion command,
target backend, and declared changed files.
Rollback-completed failures may still report rollback-touched owner truth-state
surfaces in `changed_files`; those packets must also carry a stable
`mutation_id`.

This phase does not add a promotion `mutation_ledger`, rollback API, or
rollback-available claim. Promotion rollback evidence remains expressed through
`promotion_result` and truthful `changed_files`.

Promotion success must not be inferred from external promote subprocess exit
code alone.
Successful owner packets must prove, machine-readably:

- a unique eligible backend identity
- `reserve` precondition truth
- current `pool_policy` gate truth before routing-impacting promotion
- promotion does not exceed the staged active-pool target
- promotion does not drop reserve below the staged reserve target
- a rollback point captured before routing-impacting mutation
- post-promotion sync outcome
- post-promotion status proof summary
- an explicit verified active-routing consequence

`accounts promote <id> --json` may expose a nested `promotion_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `backend_id`
- `precondition_status`
- `previous_pool`
- `requested_pool`
- `pool_policy_status`
- `pool_policy_observed`
- `active_pool_count_before`
- `active_target_observed`
- `reserve_count_before`
- `reserve_target_observed`
- `rollback_point_captured`
- `routing_change_attempted`
- `routing_change_observed`
- `validate_attempted`
- `validate_outcome`
- `sync_attempted`
- `sync_outcome`
- `status_observed`
- `rollback_attempted`
- `rollback_outcome`
- `external_command_exit_code`
- `external_command_status`
- `final_outcome`

Canonical promotion outcomes include:

- `promoted_to_active`
- `precondition_failed`
- `validate_failed`
- `rollback_completed_after_failed_verification`
- `rollback_failed`
- `promotion_command_failed`

Rollback proof is limited to control-layer state and companion-managed
artifacts.
It does not imply rollback of engine-internal routing behavior.

## Additional demote owner surface

`accounts demote <id> --json` is the owner surface for explicit
active-to-reserve demotion truth.

Demotion success must not be inferred from external demote subprocess exit
code alone.
Successful owner packets must prove, machine-readably:

- a unique backend identity
- explicit `active -> reserve` demote precondition truth
- held backend rejection (`release` lane only)
- retired backend rejection (no demote lane from `retired`)
- already-reserve classification as either:
  reserve-only verified no-op success, or explicit failure when reserve-only
  proof is missing
- a rollback point captured before any routing-impacting mutation
- post-transition sync outcome when routing consequence changes
- post-transition status proof summary when routing consequence changes
- an explicit routing-consequence classification
- strict single-packet JSON behavior even on command execution failure
- truthful `changed_files` across registry/state/runtime write surfaces

`accounts demote <id> --json` may expose a nested `demote_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `backend_id`
- `precondition_status`
- `previous_pool`
- `previous_manual_hold`
- `requested_transition`
- `rollback_point_captured`
- `routing_change_attempted`
- `routing_change_observed`
- `sync_attempted`
- `sync_outcome`
- `status_observed`
- `rollback_attempted`
- `rollback_outcome`
- `external_command_exit_code`
- `external_command_status`
- `reserve_return_confirmed`
- `final_outcome`

Canonical demote outcomes include:

- `backend_demoted_to_reserve`
- `already_reserve`
- `precondition_failed`
- `rollback_completed_after_failed_verification`
- `rollback_failed`
- `demote_command_failed`

## Additional hold and release owner surfaces

`accounts hold <id> --json` is the owner surface for protective isolation
truth.

`accounts release <id> --json` is the owner surface for explicit
hold-to-reserve truth.

Hold and release success must not be inferred from external subprocess exit
code alone.
Successful owner packets must prove, machine-readably:

- a unique backend identity
- explicit precondition truth
- `hold` represented by `manual_hold=true`, not a new pool token
- `release` returns to `reserve`, not directly to `active`
- a rollback point captured before any routing-impacting mutation
- post-transition sync outcome when routing consequence changes
- post-transition status proof summary when routing consequence changes
- an explicit routing-consequence classification

`accounts hold <id> --json` and `accounts release <id> --json` may expose
nested `hold_result` and `release_result` surfaces.
Preferred fields include:

- `status`
- `attempted`
- `backend_id`
- `precondition_status`
- `previous_pool`
- `previous_manual_hold`
- `requested_transition`
- `rollback_point_captured`
- `routing_change_attempted`
- `routing_change_observed`
- `sync_attempted`
- `sync_outcome`
- `status_observed`
- `rollback_attempted`
- `rollback_outcome`
- `external_command_exit_code`
- `external_command_status`
- `final_outcome`

Canonical hold outcomes include:

- `backend_held`
- `already_held`
- `precondition_failed`
- `rollback_completed_after_failed_verification`
- `rollback_failed`
- `hold_command_failed`

Canonical release outcomes include:

- `backend_released_to_reserve`
- `not_on_hold`
- `precondition_failed`
- `rollback_completed_after_failed_verification`
- `rollback_failed`
- `release_command_failed`

Protective hold remains separate from promotion.
Release remains separate from promotion and must not return a backend directly
to `active`.

`accounts hold <id> --dry-run --json` is the first account lifecycle dry-run
contract surface. It is a `mutate` command-class packet, but must not write
truth files, invoke the external accounts command, enter lifecycle locks, run
sync, run status proof, run healthcheck, or attempt repair/recovery.

Dry-run packets must include:

- `effect="mutate"`
- `dry_run=true`
- `mutation_id=null`
- `would_change`
- `precondition_status=eligible|blocked`
- `blocked_by`
- `changed_files=[]`

`would_change` reports the planned bounded write surface only. It must not be
treated as evidence that a write occurred. A blocked dry-run must remain
non-mutating and report the blocker machine-readably. Blocked hold dry-run
packets use `machine_error_code=HOLD_DRY_RUN_BLOCKED` with `blocked_by`
carrying the canonical precondition token.

## Additional retire owner surface

`accounts retire <id> --json` is the owner surface for terminal retirement
truth.

Retirement success must not be inferred from external subprocess exit code
alone.
Successful owner packets must prove, machine-readably:

- a unique backend identity
- explicit retirement precondition truth
- resulting terminal `retired` lifecycle state
- explicit terminal no-return proof (`retired`, not held, not routing-eligible,
  not selected)
- no automatic return path implied by the owner packet
- a rollback point captured before any routing-impacting mutation
- post-transition sync outcome when routing consequence changes
- post-transition status proof summary when routing consequence changes
- an explicit routing-consequence classification
- truthful `changed_files` across registry/state/runtime write surfaces

`accounts retire <id> --json` may expose a nested `retire_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `backend_id`
- `precondition_status`
- `previous_pool`
- `previous_manual_hold`
- `requested_transition`
- `rollback_point_captured`
- `routing_change_attempted`
- `routing_change_observed`
- `sync_attempted`
- `sync_outcome`
- `status_observed`
- `rollback_attempted`
- `rollback_outcome`
- `external_command_exit_code`
- `external_command_status`
- `terminal_no_return_confirmed`
- `final_outcome`

Canonical retirement outcomes include:

- `backend_retired`
- `already_retired`
- `precondition_failed`
- `rollback_completed_after_failed_verification`
- `rollback_failed`
- `retire_command_failed`

Retirement remains separate from demote semantics.
`accounts retire <id> --json` must not define or imply any later
reserve-return or reactivation lane for `retired` backends.

## Additional target-switch contract surface

The current target-switch contour exposes:

- `stable target switch --dry-run --json`
- `stable target switch --apply --json`

`--dry-run` remains a contract and reporting surface.
`--apply` is now a narrow control-layer write surface.

They must remain strict JSON and expose explicit machine-readable separation
between:

- current observed stable inventory source
- approved repair-target reference
- target-switch transaction metadata surface

Current required target-switch contract fields:

- `target_surface.status`
- `target_surface.observed_stable_inventory_source`
- `target_surface.approved_repair_target_reference`
- `target_surface.target_switch_transaction_metadata_surface`
- `declared_write_surfaces`
- `forbidden_surfaces`
- `transaction_phases`
- `verify_scope`

`stable target switch --apply --json` may materialize only:

- `<managed_dir>/stable-repair-target`
- `<managed_dir>/approved-repair-target.json`
- `<managed_dir>/target-switch-transaction.json`

Successful apply means control-layer target activation only.
It does not imply:

- runtime switch success
- engine inventory redirection
- repair success
- stable runtime health improvement

The materialized target directory may remain empty of `codex-*.json` auth
files. That is a success condition for this contour, not a defect.

## Additional stable-repair contract surface

`stable repair --dry-run --json` remains non-mutating.

`stable repair --apply --json` may mutate only:

- `<managed_dir>/stable-repair-target/codex-*.json`

It may also use process-local transaction scratch under companion-managed data:

- `<managed_dir>/.stable-repair-stage-*`
- `<managed_dir>/.stable-repair-backup-*`

These scratch directories are ephemeral transaction mechanics, not persisted
contract surfaces. They must be removed before the command returns on success
or rollback.

Successful apply means approved target inventory reconciliation only.
It does not imply:

- runtime switch success
- engine inventory redirection
- stable runtime health improvement

Apply-time field rules:

- eligible registry `auth_ref` files are policy-authorized copy inputs only
- source files remain non-mutating inputs
- observed-source drift fields remain observation only
- prune authority is limited to unauthorized `codex-*.json` entries already
  inside the approved control-owned target inventory
- basename preservation is exact; no rename or dedup logic is implied

It must expose explicit machine-readable separation between:

- observed stable inventory reporting
- registry source-copy inputs
- approved repair-target contract surface
- future target reconciliation steps
- repair apply authority

Required stable-repair contract groups:

- `transaction_plan.repair_observation`
- `transaction_plan.registry_source_inputs`
- `transaction_plan.repair_target_contract_surface`
- `transaction_plan.target_reconciliation_plan`
- `transaction_plan.repair_apply_authority`
- `transaction_plan.blocked_reasons`

Field meaning rules:

- observed-source fields must not silently imply delete authority over the
  observed stable inventory source
- registry `auth_ref` source files may be policy inputs for future repair apply,
  but this dry-run contract does not grant mutation authority over those source
  files
- target reconciliation fields must describe only the approved control-owned
  target inventory
- `would_change` must reflect future target reconciliation work, not merely
  observed-source drift
- apply blocker paths for missing source files or basename collisions must be
  machine-readable and must not fall back to implicit rename logic

## Additional stable-runtime consumer contract surface

The current stable-runtime consumer line now exposes a narrow activation path
only through `launch smoke --json`.

It must expose explicit machine-readable separation between:

- observed stable inventory source
- approved repair-target reference
- desired stable runtime consumer source
- effective stable runtime consumer source
- derived stable runtime config surface
- explicit fallback contract

Current reporting surfaces for this contract are:

- `status --json`
- `launch smoke --json`

Required contract fields:

- `stable_runtime_consumer.status`
- `stable_runtime_consumer.observed_stable_inventory_source`
- `stable_runtime_consumer.approved_repair_target_reference`
- `stable_runtime_consumer.desired_stable_runtime_consumer_source`
- `stable_runtime_consumer.effective_stable_runtime_consumer_source`
- `stable_runtime_consumer.derived_stable_runtime_config_surface`
- `stable_runtime_consumer.launcher_handoff_contract`
- `stable_runtime_consumer.activation_evidence_surface`
- `stable_runtime_consumer.effective_truth_contract`
- `stable_runtime_consumer.baseline_stable_config_surface`
- `stable_runtime_consumer.fallback_contract`
- `stable_runtime_consumer.deterministic_stable_recovery_contract`
- `stable_runtime_consumer.consumer_activation_readiness`

Field meaning rules:

- desired stable runtime consumer source is control-layer selection truth
- effective stable runtime consumer source is runtime-observed truth only
- desired source must not be reported as effective before successful live
  activation evidence
- launcher handoff for stable-runtime activation is a narrow process-local
  override contract:
  `WBP_STABLE_CONFIG=<managed_dir>/stable-runtime-config.generated.yaml`
- that handoff must remain launcher-scoped and must not silently become a
  generic config-routing platform
- runtime-state activation evidence is a snapshot surface only; snapshot evidence
  alone must not flip effective stable runtime consumer truth
- baseline stable config remains an engine-adjacent observation surface
- `stable-runtime-config.generated.yaml` is a generated control artifact, not a
  truth surface
- deterministic stable recovery entry is owned by the live attestation and
  fallback-reconciliation path exposed through `healthcheck --repair --json`
- `status --json` must not delegate to that owner path; it may report only a
  read-only snapshot and must mark live attestation as not run by status
- silent fallback from approved target to observed source is forbidden
- when desired source is the approved repair target, `launch smoke --json` may:
  - materialize `stable-runtime-config.generated.yaml`
  - pass it through the launcher-scoped `WBP_STABLE_CONFIG` override
  - write `stable_runtime_consumer_snapshot` with outcome
    `approved_target_activated` or `observed_source_fallback`
- when desired source remains the observed stable inventory source, `launch
  smoke --json` may write `stable_runtime_consumer_snapshot` with outcome
  `observed_source_selected`
- approved-target activation success and observed-source fallback must remain
  separately distinguishable in machine-readable output
- deterministic stable recovery in the repair owner path now reuses the same generated
  config path, `WBP_STABLE_CONFIG` handoff, and snapshot topic through
  `healthcheck --repair --json`
- deterministic stable recovery in the owner path must regenerate generated
  config per approved-target attempt and must not treat a stale generated
  config artifact as authoritative truth
- `healthcheck --repair --json` may expose top-level
  `deterministic_stable_recovery_contract`
- `healthcheck --repair --json` may expose top-level
  `deterministic_stable_recovery_result`
- `status --json` must not expose a fresh nested
  `stable_runtime_consumer.deterministic_stable_recovery_result` unless it was
  already present as persisted/cached snapshot evidence
- owner-path packets now emit `deterministic_stable_recovery_result.entry_lane`
- top-level `STABLE_SERVICE_DISABLED` may be emitted only when:
  - the same packet proves `entry_lane = stable_service_disabled`
  - final live runtime truth remains unhealthy
- absent positive evidence for the narrower disabled-service lane, the system
  must stay on generic `LISTENER_DOWN`
- `stable_service_disabled` classification must remain separate from
  `PROXY_PATH_BROKEN` and `PROXY_REPROBE_FAILED`
- `launch smoke --json` must not surface deterministic stable recovery result as
  if it owned the healthcheck recovery lane
- `sync --json` must not expose deterministic stable recovery as an owner lane
- no new persisted recovery metadata file or snapshot-schema widening is
  required for `stable_service_disabled` packet truth by default
- owner-path writes across fallback reconciliation, generated-config
  materialization, and snapshot refresh must remain visible in `changed_files`
- owner-path packets may expose top-level `last_known_good_proxy_contract`
- owner-path packets may expose top-level `last_known_good_proxy`
  with an honest materialization status such as `declared_not_materialized`
- owner-path packets may expose top-level `current_proxy_adoption_contract`
- that contract may declare a dedicated current-proxy activation handoff such as
  `WBP_CURRENT_PROXY_URL`
- that handoff remains a launcher-scoped process-local carrier rather than a
  truth surface for `current_proxy_url`
- owner-path packets may now expose nested
  `proxy_reprobe_adoption_result`
  when proxy-path failure found a bounded working candidate and the owner path
  evaluated or attempted current-proxy adoption
- `proxy_reprobe_adoption_result` must remain nested owner-path truth rather
  than a top-level current-proxy truth surface
- packets with `PROXY_PATH_BROKEN` or `PROXY_REPROBE_FAILED` may expose
  `proxy_path_recovery_hint` as a command-packet-only summary for app-visible
  blocked/action truth
- `proxy_path_recovery_hint` must not start repair, claim recovery, persist new
  metadata, or replace `proxy_reprobe`, `last_known_good_proxy`, or
  `proxy_reprobe_adoption_result` evidence
- materialized `last_known_good_proxy` may inform `proxy_path_recovery_hint`, but
  must not by itself change top-level `machine_error_code` or make
  `healthcheck --repair --json` an immediately allowed repair surface
- that contract may expose an external launcher-path surface for
  `WBP_LAUNCHER_SCRIPT`, but launcher-path presence alone must not be treated as
  proof of current-proxy consumer capability
- the default launcher path may be a bounded repo-owned provisioning target,
  but a preexisting unmarked file at that path must not be silently overwritten
- a repo-owned default launcher artifact may carry a narrow repo-managed marker
  used only for safe refresh of that default-path artifact
- that contract may expose a bounded launcher-consumer readiness surface and
  must report:
  - repo-owned default consumer provisioning availability
  - default-path missing or provisioned state
  - default-path ownership-unverified state
  - explicit external override unverified state
  honestly without implying current-proxy adoption readiness
- absent default-path materialization remains a bounded owner-path prerequisite,
  not lane eligibility by itself
- owner-path current-proxy adoption may proceed only through a recognized
  repo-owned default launcher artifact after any prerequisite materialization
  has been re-evaluated
- explicit external override paths, invalid default-path markers, and
  unrecognized marked default-path files remain ineligible owner-path adoption
  lanes
- that contract may allow a later launcher consumer to derive engine-local proxy
  env keys for the managed runtime child process only
- any such derived proxy env keys remain engine-local routing inputs, not
  control-plane truth surfaces
- owner-path `healthcheck --repair --json` writes may materialize or refresh
  `last_known_good_proxy_url` and `last_known_good_proxy_observed_at`
  in `supervisor-state.json`
- `status --json` may expose static owner-path contracts as read-only snapshot
  data, but it must not report delegated current-proxy adoption results as if
  it had run healthcheck
- `status --json` must not expose a fresh nested
  `proxy_reprobe_adoption_result`; any such field must come only from already
  persisted/cached snapshot evidence
- `proxy_reprobe.working_candidate` remains nested bounded evidence only and
  must not become `current_proxy_url` by mere presence
- current bounded candidate discovery remains
  `shallow_socket_listener_only` and is limited to local listener reachability
  rather than a separate deep-probing truth surface
- top-level current-proxy adoption success still requires same-owner live
  runtime reproof through `healthcheck.attestation`
- no separate control-layer deep-probing surface is active by default; deeper
  runtime validation remains delegated to the live reproof surface above
- `status --json` may expose the same `last_known_good_proxy` readout only as a
  persisted-state snapshot
- `status --json` must not report owner-path writes and must emit
  `changed_files=[]`
- `current_proxy_url` is current live outbound proxy truth and remains separate
  from nested `proxy_reprobe.working_candidate`
- `current_proxy_url` remains separate from persisted
  `last_known_good_proxy.proxy_url`
- ambient shell proxy env must not become the authoritative control-layer truth
  surface for current proxy selection
- derived proxy env keys such as `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and
  lowercase variants may later be generated only inside the bounded launcher
  consumer from `WBP_CURRENT_PROXY_URL`; that allowance does not itself claim
  that the current engine already consumes those keys
- control-plane runtime attestation remains proxyless even if a later managed
  runtime activation lane receives a dedicated current-proxy handoff
- `current_proxy_url` may change only after the same serialized owner path:
  - detected proxy-path failure
  - found a bounded working candidate
  - established an eligible recognized repo-owned launcher lane
  - carried that candidate through `WBP_CURRENT_PROXY_URL`
  - reran live managed runtime attestation successfully
- candidate existence alone must never produce top-level `OK`
- persisted last-known-good proxy truth must never by itself change top-level
  `status`, `liveness`, `machine_error_code`, `endpoint`, or `current_proxy_url`

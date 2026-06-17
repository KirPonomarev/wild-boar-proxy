# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .approved_handoff import (
    APPROVED_HANDOFF_SURFACES,
    HANDOFF_SURFACE_LOCAL_PROOF_COMMAND,
    HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    run_approved_handoff_command,
)
from .cli_runner import run_codex_cli_runner_smoke
from .command_effects import EFFECT_MUTATE, EFFECT_PROBE, EFFECT_READ, EFFECT_REPAIR
from .core import packets as command_packets
from .custom_codex_admission import run_custom_codex_admission_command
from .custom_codex_operator_proof import run_repeatable_operator_proof_command
from .custom_codex_working_flow_visible_source_proof import (
    run_working_flow_visible_source_proof_command,
)
from .interactive_custom_codex_proof import (
    run_interactive_custom_codex_collect_command,
    run_interactive_custom_codex_preflight_command,
)
from .interactive_codex_working_flow_delivery import (
    APPROVED_DELIVERY_SOURCE_KINDS,
    DELIVERY_SOURCE_CODEX_EXEC_JSONL,
    run_interactive_codex_working_flow_delivery_command,
)
from .external_models import run_external_models_command
from .controlled_api_dispatch import run_controlled_api_dispatch_command
from .controlled_dispatch_handoff_proof import (
    run_controlled_dispatch_handoff_proof_command,
)
from .controlled_ingress_api_dispatch_proof import (
    run_controlled_ingress_api_dispatch_proof_command,
)
from .codex_exec_assistant_continuation_proof import (
    run_codex_exec_assistant_continuation_proof_command,
)
from .codex_working_flow_delivery_proof import (
    run_codex_working_flow_delivery_proof_command,
)
from .custom_codex_hook_origin_proof import (
    run_custom_codex_hook_origin_proof_command,
)
from .native_free_chat_router_dispatch_admission import (
    run_native_free_chat_router_dispatch_admission_command,
)
from .native_free_chat_router_handoff_working_flow_join import (
    run_handoff_to_working_flow_join_command,
)
from .codex_transcript_delivery_observation import (
    run_codex_transcript_delivery_observation_command,
)
from .custom_codex_approved_visible_source_observation import (
    APPROVED_VISIBLE_SOURCE_KINDS,
    VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
    run_custom_codex_approved_visible_source_observation_command,
)
from .custom_codex_ingress_proof import run_custom_codex_ingress_proof_command
from .observed_machine_handoff_delivery import (
    APPROVED_DELIVERY_SURFACES,
    DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
    run_observed_machine_handoff_delivery_command,
)
from .proof_seal import (
    run_proof_seal_create_command,
    run_proof_seal_verify_command,
)
from .router_hook_entry import (
    ADMITTED_HOOK_SURFACES,
    HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    HOOK_SURFACE_PROMPT_PREPROCESSOR,
    run_router_hook_entry_command,
)
from .real_custom_codex_hook_proof import (
    run_real_custom_codex_hook_proof_command,
)
from .real_user_prompt_submit_ledger_proof import (
    run_real_user_prompt_submit_ledger_proof_command,
)
from .user_prompt_submit_hook_producer import (
    build_user_prompt_submit_install_packet,
    build_user_prompt_submit_readiness_packet,
)
from .runtime_health import run_healthcheck_probe
from .runtime_repair import run_healthcheck_repair
from .runtime import (
    RuntimeErrorInfo,
    RuntimePaths,
    _health_probe_dependencies,
    _healthcheck_repair_dependencies,
    export_diagnostics,
    list_accounts,
    mode_get,
    mode_set,
    run_accounts_command,
    run_accounts_login_cancel,
    run_accounts_login_status,
    run_accounts_login_complete,
    run_accounts_login_start,
    run_demote,
    run_invariant_check,
    run_installer_init,
    run_hold,
    run_launch_client,
    run_launch_smoke,
    run_legacy_import,
    run_onboard,
    run_policy_stage_set,
    run_promote,
    run_companion_reset,
    run_release,
    run_rollback_latest_apply,
    run_rollback_latest_dry_run,
    run_rollout_evidence_capture,
    run_rollout_posture_inspect,
    run_rollout_rotation_inspect,
    run_rollout_stage_advance,
    run_rollout_stage_prove,
    run_package_experimental_build,
    run_package_experimental_verify,
    run_package_launchable_build,
    run_package_launchable_verify,
    run_retire,
    run_stable_repair_apply,
    run_stable_repair_dry_run,
    run_stable_target_switch_contract,
    run_sync,
    summarize_status,
)
from .token_command import emit_local_token, token_status_payload


def build_parser() -> argparse.ArgumentParser:
    root_parser = argparse.ArgumentParser(prog="wild-boar-proxy")
    subparsers = root_parser.add_subparsers(dest="command", required=True)

    healthcheck = subparsers.add_parser("healthcheck")
    healthcheck.add_argument("--json", action="store_true", required=True)
    healthcheck.add_argument("--repair", action="store_true")
    healthcheck.add_argument("--model")

    status = subparsers.add_parser("status")
    status.add_argument("--json", action="store_true", required=True)

    invariant_check = subparsers.add_parser("invariant-check")
    invariant_check.add_argument("--json", action="store_true", required=True)

    token = subparsers.add_parser("token")
    token.add_argument("--json", action="store_true")

    stable = subparsers.add_parser("stable")
    stable_subparsers = stable.add_subparsers(dest="stable_command", required=True)
    stable_repair = stable_subparsers.add_parser("repair")
    stable_repair_mode = stable_repair.add_mutually_exclusive_group(required=True)
    stable_repair_mode.add_argument("--dry-run", action="store_true")
    stable_repair_mode.add_argument("--apply", action="store_true")
    stable_repair.add_argument("--json", action="store_true", required=True)
    stable_target = stable_subparsers.add_parser("target")
    stable_target_subparsers = stable_target.add_subparsers(
        dest="stable_target_command", required=True
    )
    stable_target_switch = stable_target_subparsers.add_parser("switch")
    stable_target_switch_mode = stable_target_switch.add_mutually_exclusive_group(
        required=True
    )
    stable_target_switch_mode.add_argument("--dry-run", action="store_true")
    stable_target_switch_mode.add_argument("--apply", action="store_true")
    stable_target_switch.add_argument("--json", action="store_true", required=True)

    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("--latest", action="store_true", required=True)
    rollback_mode = rollback.add_mutually_exclusive_group(required=True)
    rollback_mode.add_argument("--dry-run", action="store_true")
    rollback_mode.add_argument("--apply", action="store_true")
    rollback.add_argument("--json", action="store_true", required=True)

    sync = subparsers.add_parser("sync")
    sync.add_argument("--json", action="store_true", required=True)
    sync.add_argument("--model")

    launch = subparsers.add_parser("launch")
    launch_subparsers = launch.add_subparsers(dest="launch_command", required=True)
    launch_smoke = launch_subparsers.add_parser("smoke")
    launch_smoke.add_argument("--json", action="store_true", required=True)
    launch_client = launch_subparsers.add_parser("client")
    launch_client.add_argument("--client-path", required=True)
    launch_client.add_argument("--json", action="store_true", required=True)

    codex_runner = subparsers.add_parser("codex-runner")
    codex_runner_subparsers = codex_runner.add_subparsers(
        dest="codex_runner_command", required=True
    )
    codex_runner_smoke = codex_runner_subparsers.add_parser("smoke")
    codex_runner_smoke.add_argument("--prompt", required=True)
    codex_runner_smoke.add_argument("--json", action="store_true", required=True)
    codex_runner_admission = codex_runner_subparsers.add_parser("admission")
    codex_runner_admission.add_argument("--prompt", required=True)
    codex_runner_admission.add_argument("--codex-bin")
    codex_runner_admission.add_argument("--proof-dir")
    codex_runner_admission.add_argument("--codex-cwd")
    codex_runner_admission.add_argument(
        "--expected-text",
        default="WBP_DIP_DISPATCH_OK",
    )
    codex_runner_admission.add_argument(
        "--sandbox",
        default="danger-full-access",
    )
    codex_runner_admission.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
    )
    codex_runner_admission.add_argument("--json", action="store_true", required=True)
    codex_runner_operator = codex_runner_subparsers.add_parser("operator-proof")
    codex_runner_operator.add_argument("--prompt", required=True)
    codex_runner_operator.add_argument("--codex-bin")
    codex_runner_operator.add_argument("--proof-dir")
    codex_runner_operator.add_argument("--codex-cwd")
    codex_runner_operator.add_argument(
        "--expected-text",
        default="WBP_DIP_DISPATCH_OK",
    )
    codex_runner_operator.add_argument(
        "--sandbox",
        default="danger-full-access",
    )
    codex_runner_operator.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
    )
    codex_runner_operator.add_argument("--json", action="store_true", required=True)
    codex_runner_visible_source = codex_runner_subparsers.add_parser(
        "working-flow-visible-source-proof"
    )
    codex_runner_visible_source.add_argument("--prompt", required=True)
    codex_runner_visible_source.add_argument("--codex-bin")
    codex_runner_visible_source.add_argument("--proof-dir")
    codex_runner_visible_source.add_argument("--codex-cwd")
    codex_runner_visible_source.add_argument(
        "--expected-text",
        default="WBP_DIP_DISPATCH_OK",
    )
    codex_runner_visible_source.add_argument(
        "--sandbox",
        default="danger-full-access",
    )
    codex_runner_visible_source.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
    )
    codex_runner_visible_source.add_argument("--json", action="store_true", required=True)
    codex_runner_interactive_preflight = codex_runner_subparsers.add_parser(
        "interactive-preflight"
    )
    codex_runner_interactive_preflight.add_argument("--prompt", required=True)
    codex_runner_interactive_preflight.add_argument("--proof-dir")
    codex_runner_interactive_preflight.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    codex_runner_interactive_collect = codex_runner_subparsers.add_parser(
        "interactive-collect"
    )
    codex_runner_interactive_collect.add_argument("--prompt", required=True)
    codex_runner_interactive_collect.add_argument(
        "--preflight-packet-file",
        required=True,
    )
    codex_runner_interactive_collect.add_argument("--proof-dir")
    codex_runner_interactive_collect.add_argument(
        "--expected-text",
        default="WBP_DIP_DISPATCH_OK",
    )
    codex_runner_interactive_collect.add_argument("--live-provider-proof-file")
    codex_runner_interactive_collect.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    codex_runner_interactive_working_flow = codex_runner_subparsers.add_parser(
        "interactive-working-flow-delivery"
    )
    codex_runner_interactive_working_flow.add_argument(
        "--interactive-proof-file",
        required=True,
    )
    codex_runner_interactive_working_flow.add_argument(
        "--integrated-live-provider-proof-file",
        required=True,
    )
    codex_runner_interactive_working_flow.add_argument(
        "--codex-exec-jsonl-file",
        required=True,
    )
    codex_runner_interactive_working_flow.add_argument("--proof-dir")
    codex_runner_interactive_working_flow.add_argument(
        "--delivery-source-kind",
        choices=sorted(APPROVED_DELIVERY_SOURCE_KINDS),
        default=DELIVERY_SOURCE_CODEX_EXEC_JSONL,
    )
    codex_runner_interactive_working_flow.add_argument(
        "--json",
        action="store_true",
        required=True,
    )

    router_hook = subparsers.add_parser("router-hook")
    router_hook_subparsers = router_hook.add_subparsers(
        dest="router_hook_command",
        required=True,
    )
    router_hook_entry = router_hook_subparsers.add_parser("entry")
    router_hook_entry.add_argument("--prompt", required=True)
    router_hook_entry.add_argument("--runtime-context-file")
    router_hook_entry.add_argument(
        "--hook-surface-kind",
        choices=sorted(ADMITTED_HOOK_SURFACES),
        default=HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    )
    router_hook_entry.add_argument("--json", action="store_true", required=True)
    router_hook_dispatch = router_hook_subparsers.add_parser("dispatch")
    router_hook_dispatch.add_argument("--prompt", required=True)
    router_hook_dispatch.add_argument("--runtime-context-file")
    router_hook_dispatch.add_argument(
        "--hook-surface-kind",
        choices=sorted(ADMITTED_HOOK_SURFACES),
        default=HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    )
    router_hook_dispatch.add_argument("--json", action="store_true", required=True)
    router_hook_handoff = router_hook_subparsers.add_parser("handoff")
    router_hook_handoff.add_argument("--prompt", required=True)
    router_hook_handoff.add_argument("--runtime-context-file")
    router_hook_handoff.add_argument(
        "--hook-surface-kind",
        choices=sorted(ADMITTED_HOOK_SURFACES),
        default=HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    )
    router_hook_handoff.add_argument(
        "--handoff-surface-kind",
        choices=sorted(APPROVED_HANDOFF_SURFACES),
        default=HANDOFF_SURFACE_LOCAL_PROOF_COMMAND,
    )
    router_hook_handoff.add_argument("--json", action="store_true", required=True)
    router_hook_deliver = router_hook_subparsers.add_parser("deliver")
    router_hook_deliver.add_argument("--prompt", required=True)
    router_hook_deliver.add_argument("--runtime-context-file")
    router_hook_deliver.add_argument(
        "--hook-surface-kind",
        choices=sorted(ADMITTED_HOOK_SURFACES),
        default=HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    )
    router_hook_deliver.add_argument(
        "--delivery-surface-kind",
        choices=sorted(APPROVED_DELIVERY_SURFACES),
        default=DELIVERY_SURFACE_MCP_TOOL_RESPONSE,
    )
    router_hook_deliver.add_argument("--json", action="store_true", required=True)
    router_hook_ingress = router_hook_subparsers.add_parser("ingress")
    router_hook_ingress.add_argument("--prompt", required=True)
    router_hook_ingress.add_argument("--codex-exec-jsonl-file", required=True)
    router_hook_ingress.add_argument("--runtime-context-file")
    router_hook_ingress.add_argument(
        "--hook-surface-kind",
        choices=sorted(ADMITTED_HOOK_SURFACES),
        default=HOOK_SURFACE_PROMPT_PREPROCESSOR,
    )
    router_hook_ingress.add_argument("--json", action="store_true", required=True)
    router_hook_dispatch_proof = router_hook_subparsers.add_parser("dispatch-proof")
    router_hook_dispatch_proof.add_argument("--ingress-proof-file", required=True)
    router_hook_dispatch_proof.add_argument("--prompt", required=True)
    router_hook_dispatch_proof.add_argument("--runtime-context-file")
    router_hook_dispatch_proof.add_argument(
        "--hook-surface-kind",
        choices=sorted(ADMITTED_HOOK_SURFACES),
        default=HOOK_SURFACE_PROMPT_PREPROCESSOR,
    )
    router_hook_dispatch_proof.add_argument("--json", action="store_true", required=True)
    router_hook_handoff_proof = router_hook_subparsers.add_parser("handoff-proof")
    router_hook_handoff_proof.add_argument("--dispatch-proof-file", required=True)
    router_hook_handoff_proof.add_argument(
        "--handoff-surface-kind",
        choices=sorted(APPROVED_HANDOFF_SURFACES),
        default=HANDOFF_SURFACE_MCP_TOOL_RESPONSE,
    )
    router_hook_handoff_proof.add_argument("--json", action="store_true", required=True)
    router_hook_transcript_observe = router_hook_subparsers.add_parser(
        "transcript-observe"
    )
    router_hook_transcript_observe.add_argument("--handoff-proof-file", required=True)
    router_hook_transcript_observe.add_argument(
        "--codex-exec-jsonl-file",
        required=True,
    )
    router_hook_transcript_observe.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    router_hook_assistant_continuation = router_hook_subparsers.add_parser(
        "assistant-continuation-proof"
    )
    router_hook_assistant_continuation.add_argument(
        "--transcript-observation-file",
        required=True,
    )
    router_hook_assistant_continuation.add_argument(
        "--codex-exec-jsonl-file",
        required=True,
    )
    router_hook_assistant_continuation.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    router_hook_visible_source = router_hook_subparsers.add_parser(
        "visible-source-observe"
    )
    router_hook_visible_source.add_argument(
        "--assistant-continuation-proof-file",
        required=True,
    )
    router_hook_visible_source.add_argument(
        "--visible-source-kind",
        choices=sorted(APPROVED_VISIBLE_SOURCE_KINDS),
        default=VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
    )
    router_hook_visible_source.add_argument(
        "--codex-exec-jsonl-file",
        required=True,
    )
    router_hook_visible_source.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    router_hook_user_prompt_submit = router_hook_subparsers.add_parser(
        "user-prompt-submit-proof"
    )
    router_hook_user_prompt_submit.add_argument("--prompt", required=True)
    router_hook_user_prompt_submit.add_argument("--hook-ledger-file", required=True)
    router_hook_user_prompt_submit.add_argument("--runtime-context-file")
    router_hook_user_prompt_submit.add_argument("--live-provider-expected-text")
    router_hook_user_prompt_submit.add_argument("--live-provider-proof-file")
    router_hook_user_prompt_submit.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    router_hook_user_prompt_submit_ledger = router_hook_subparsers.add_parser(
        "user-prompt-submit-ledger-proof"
    )
    router_hook_user_prompt_submit_ledger.add_argument("--prompt", required=True)
    router_hook_user_prompt_submit_ledger.add_argument("--hook-ledger-file")
    router_hook_user_prompt_submit_ledger.add_argument("--runtime-context-file")
    router_hook_user_prompt_submit_ledger.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    router_hook_dispatch_admission = router_hook_subparsers.add_parser(
        "dispatch-admission"
    )
    router_hook_dispatch_admission.add_argument("--prompt", required=True)
    router_hook_dispatch_admission.add_argument("--hook-ledger-file", required=True)
    router_hook_dispatch_admission.add_argument("--runtime-context-file")
    router_hook_dispatch_admission.add_argument("--handoff-file")
    router_hook_dispatch_admission.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    router_hook_handoff_working_flow_join = router_hook_subparsers.add_parser(
        "handoff-working-flow-join"
    )
    router_hook_handoff_working_flow_join.add_argument(
        "--dispatch-admission-file",
        required=True,
    )
    router_hook_handoff_working_flow_join.add_argument(
        "--dispatch-handoff-file",
        required=True,
    )
    router_hook_handoff_working_flow_join.add_argument(
        "--codex-exec-jsonl-file",
        required=True,
    )
    router_hook_handoff_working_flow_join.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    router_hook_working_flow_delivery = router_hook_subparsers.add_parser(
        "working-flow-delivery-proof"
    )
    router_hook_working_flow_delivery.add_argument(
        "--integrated-live-provider-proof-file",
        required=True,
    )
    router_hook_working_flow_delivery.add_argument(
        "--codex-exec-jsonl-file",
        required=True,
    )
    router_hook_working_flow_delivery.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    router_hook_custom_origin = router_hook_subparsers.add_parser(
        "custom-origin-proof"
    )
    router_hook_custom_origin.add_argument(
        "--integrated-live-provider-proof-file",
        required=True,
    )
    router_hook_custom_origin.add_argument(
        "--working-flow-delivery-proof-file",
        required=True,
    )
    router_hook_custom_origin.add_argument(
        "--strict-sealed-evidence",
        action="store_true",
    )
    router_hook_custom_origin.add_argument(
        "--integrated-live-provider-proof-seal-file",
    )
    router_hook_custom_origin.add_argument(
        "--working-flow-delivery-proof-seal-file",
    )
    router_hook_custom_origin.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    router_hook_proof_seal_create = router_hook_subparsers.add_parser(
        "proof-seal-create"
    )
    router_hook_proof_seal_create.add_argument("--packet-file", required=True)
    router_hook_proof_seal_create.add_argument("--seal-file")
    router_hook_proof_seal_create.add_argument("--producer-kind", required=True)
    router_hook_proof_seal_create.add_argument(
        "--producer-command-digest",
        required=True,
    )
    router_hook_proof_seal_create.add_argument("--producer-inputs-digest")
    router_hook_proof_seal_create.add_argument(
        "--input-packet-file",
        action="append",
        default=[],
    )
    router_hook_proof_seal_create.add_argument("--runtime-context-digest")
    router_hook_proof_seal_create.add_argument("--hook-ledger-digest")
    router_hook_proof_seal_create.add_argument("--profile-hook-config-digest")
    router_hook_proof_seal_create.add_argument("--git-commit-sha")
    router_hook_proof_seal_create.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    router_hook_proof_seal_verify = router_hook_subparsers.add_parser(
        "proof-seal-verify"
    )
    router_hook_proof_seal_verify.add_argument("--packet-file", required=True)
    router_hook_proof_seal_verify.add_argument("--seal-file")
    router_hook_proof_seal_verify.add_argument("--expected-packet-kind")
    router_hook_proof_seal_verify.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    router_hook_user_prompt_submit_install = router_hook_subparsers.add_parser(
        "user-prompt-submit-install"
    )
    install_mode = router_hook_user_prompt_submit_install.add_mutually_exclusive_group(
        required=True
    )
    install_mode.add_argument("--dry-run", action="store_true")
    install_mode.add_argument("--apply", action="store_true")
    router_hook_user_prompt_submit_install.add_argument(
        "--json",
        action="store_true",
        required=True,
    )
    router_hook_user_prompt_submit_readiness = router_hook_subparsers.add_parser(
        "user-prompt-submit-readiness"
    )
    router_hook_user_prompt_submit_readiness.add_argument(
        "--json",
        action="store_true",
        required=True,
    )

    accounts = subparsers.add_parser("accounts")
    accounts_subparsers = accounts.add_subparsers(dest="accounts_command", required=True)

    accounts_list = accounts_subparsers.add_parser("list")
    accounts_list.add_argument("--json", action="store_true", required=True)

    accounts_validate = accounts_subparsers.add_parser("validate")
    accounts_validate.add_argument("id")
    accounts_validate.add_argument("--json", action="store_true", required=True)

    for command_name in ("promote", "demote", "release", "retire"):
        command_parser = accounts_subparsers.add_parser(command_name)
        command_parser.add_argument("id")
        command_parser.add_argument("--json", action="store_true", required=True)

    accounts_hold = accounts_subparsers.add_parser("hold")
    accounts_hold.add_argument("id")
    accounts_hold.add_argument("reason", nargs="?")
    accounts_hold.add_argument("--dry-run", action="store_true")
    accounts_hold.add_argument("--json", action="store_true", required=True)

    accounts_onboard = accounts_subparsers.add_parser("onboard")
    accounts_onboard.add_argument("--json", action="store_true", required=True)
    accounts_onboard.add_argument("--auth-ref")
    accounts_onboard.add_argument("--loop", action="store_true")
    accounts_onboard.add_argument("--skip-login", action="store_true")
    accounts_onboard.add_argument("--no-sync", action="store_true")
    accounts_onboard.add_argument("--non-interactive", action="store_true")
    accounts_login = accounts_subparsers.add_parser("login")
    accounts_login_subparsers = accounts_login.add_subparsers(
        dest="accounts_login_command", required=True
    )
    accounts_login_start = accounts_login_subparsers.add_parser("start")
    accounts_login_start.add_argument("--provider", required=True)
    accounts_login_start.add_argument("--mode")
    accounts_login_start.add_argument("--json", action="store_true", required=True)
    accounts_login_status = accounts_login_subparsers.add_parser("status")
    accounts_login_status.add_argument("--session", required=True)
    accounts_login_status.add_argument("--json", action="store_true", required=True)
    accounts_login_complete = accounts_login_subparsers.add_parser("complete")
    accounts_login_complete.add_argument("--session", required=True)
    accounts_login_complete.add_argument("--state")
    accounts_login_complete.add_argument("--proof")
    accounts_login_complete.add_argument("--json", action="store_true", required=True)
    accounts_login_cancel = accounts_login_subparsers.add_parser("cancel")
    accounts_login_cancel.add_argument("--session", required=True)
    accounts_login_cancel.add_argument("--json", action="store_true", required=True)

    diagnostics = subparsers.add_parser("diagnostics")
    diagnostics_subparsers = diagnostics.add_subparsers(
        dest="diagnostics_command", required=True
    )
    diagnostics_export = diagnostics_subparsers.add_parser("export")
    diagnostics_export.add_argument("--json", action="store_true", required=True)

    installer = subparsers.add_parser("installer")
    installer_subparsers = installer.add_subparsers(
        dest="installer_command", required=True
    )
    installer_init = installer_subparsers.add_parser("init")
    installer_init.add_argument("--json", action="store_true", required=True)

    legacy = subparsers.add_parser("legacy")
    legacy_subparsers = legacy.add_subparsers(dest="legacy_command", required=True)
    legacy_import = legacy_subparsers.add_parser("import")
    legacy_import.add_argument("--source-dir", required=True)
    legacy_import.add_argument("--json", action="store_true", required=True)

    companion = subparsers.add_parser("companion")
    companion_subparsers = companion.add_subparsers(
        dest="companion_command", required=True
    )
    companion_reset = companion_subparsers.add_parser("reset")
    companion_reset.add_argument("--json", action="store_true", required=True)
    companion_uninstall = companion_subparsers.add_parser("uninstall")
    companion_uninstall.add_argument("--json", action="store_true", required=True)

    mode = subparsers.add_parser("mode")
    mode_subparsers = mode.add_subparsers(dest="mode_command", required=True)

    mode_get_parser = mode_subparsers.add_parser("get")
    mode_get_parser.add_argument("--json", action="store_true", required=True)

    mode_set = mode_subparsers.add_parser("set")
    mode_set.add_argument("value", choices=["stable", "managed"])
    mode_set.add_argument("--json", action="store_true", required=True)

    policy = subparsers.add_parser("policy")
    policy_subparsers = policy.add_subparsers(dest="policy_command", required=True)
    policy_stage = policy_subparsers.add_parser("stage")
    policy_stage_subparsers = policy_stage.add_subparsers(
        dest="policy_stage_command", required=True
    )
    policy_stage_set = policy_stage_subparsers.add_parser("set")
    policy_stage_set.add_argument("value")
    policy_stage_set.add_argument("--json", action="store_true", required=True)

    rollout = subparsers.add_parser("rollout")
    rollout_subparsers = rollout.add_subparsers(dest="rollout_command", required=True)
    rollout_rotation = rollout_subparsers.add_parser("rotation")
    rollout_rotation_subparsers = rollout_rotation.add_subparsers(
        dest="rollout_rotation_command", required=True
    )
    rollout_rotation_inspect = rollout_rotation_subparsers.add_parser("inspect")
    rollout_rotation_inspect.add_argument("--json", action="store_true", required=True)
    rollout_posture = rollout_subparsers.add_parser("posture")
    rollout_posture_subparsers = rollout_posture.add_subparsers(
        dest="rollout_posture_command", required=True
    )
    rollout_posture_inspect = rollout_posture_subparsers.add_parser("inspect")
    rollout_posture_inspect.add_argument("value", choices=["15", "20"])
    rollout_posture_inspect.add_argument("--json", action="store_true", required=True)
    rollout_evidence = rollout_subparsers.add_parser("evidence")
    rollout_evidence_subparsers = rollout_evidence.add_subparsers(
        dest="rollout_evidence_command", required=True
    )
    rollout_evidence_capture = rollout_evidence_subparsers.add_parser("capture")
    rollout_evidence_capture.add_argument("value")
    rollout_evidence_capture.add_argument("--json", action="store_true", required=True)
    rollout_stage = rollout_subparsers.add_parser("stage")
    rollout_stage_subparsers = rollout_stage.add_subparsers(
        dest="rollout_stage_command", required=True
    )
    rollout_stage_prove = rollout_stage_subparsers.add_parser("prove")
    rollout_stage_prove.add_argument("value", choices=["10", "15"])
    rollout_stage_prove.add_argument("--json", action="store_true", required=True)
    rollout_stage_advance = rollout_stage_subparsers.add_parser("advance")
    rollout_stage_advance.add_argument("value", choices=["15", "20"])
    rollout_stage_advance.add_argument("id")
    rollout_stage_advance.add_argument("--json", action="store_true", required=True)

    package = subparsers.add_parser("package")
    package_subparsers = package.add_subparsers(dest="package_command", required=True)
    package_experimental = package_subparsers.add_parser("experimental")
    package_experimental_subparsers = package_experimental.add_subparsers(
        dest="package_experimental_command", required=True
    )
    package_experimental_build = package_experimental_subparsers.add_parser("build")
    package_experimental_build.add_argument("--output-dir", required=True)
    package_experimental_build.add_argument("--json", action="store_true", required=True)
    package_experimental_verify = package_experimental_subparsers.add_parser("verify")
    package_experimental_verify.add_argument("--manifest", required=True)
    package_experimental_verify.add_argument("--json", action="store_true", required=True)
    package_launchable = package_subparsers.add_parser("launchable")
    package_launchable_subparsers = package_launchable.add_subparsers(
        dest="package_launchable_command", required=True
    )
    package_launchable_build = package_launchable_subparsers.add_parser("build")
    package_launchable_build.add_argument("--output-dir", required=True)
    package_launchable_build.add_argument("--runtime-executable")
    package_launchable_build.add_argument("--json", action="store_true", required=True)
    package_launchable_verify = package_launchable_subparsers.add_parser("verify")
    package_launchable_verify.add_argument("--manifest", required=True)
    package_launchable_verify.add_argument("--json", action="store_true", required=True)

    external_models = subparsers.add_parser("external-models")
    external_models_subparsers = external_models.add_subparsers(
        dest="external_models_command", required=True
    )
    external_models_start = external_models_subparsers.add_parser("start")
    external_models_start.add_argument("--json", action="store_true", required=True)
    external_models_stop = external_models_subparsers.add_parser("stop")
    external_models_stop.add_argument("--json", action="store_true", required=True)
    external_models_status = external_models_subparsers.add_parser("status")
    external_models_status.add_argument("--json", action="store_true", required=True)
    external_models_models = external_models_subparsers.add_parser("models")
    external_models_models.add_argument("--json", action="store_true", required=True)
    external_models_check = external_models_subparsers.add_parser("check")
    external_models_check.add_argument("--route", required=True)
    external_models_check.add_argument("--json", action="store_true", required=True)
    external_models_live_format_check = external_models_subparsers.add_parser(
        "live-format-check"
    )
    external_models_live_format_check.add_argument("--route", required=True)
    external_models_live_format_check.add_argument("--prompt", required=True)
    external_models_live_format_check.add_argument("--expected-text", required=True)
    external_models_live_format_check.add_argument("--json", action="store_true", required=True)
    external_models_credentials = external_models_subparsers.add_parser("credentials")
    external_models_credentials_subparsers = external_models_credentials.add_subparsers(
        dest="credentials_command", required=True
    )
    external_models_credentials_admit = external_models_credentials_subparsers.add_parser(
        "admit"
    )
    external_models_credentials_admit.add_argument("--provider", required=True)
    external_models_credentials_admit.add_argument("--source", required=True)
    external_models_credentials_admit.add_argument(
        "--json", action="store_true", required=True
    )
    external_models_credentials_status = external_models_credentials_subparsers.add_parser(
        "status"
    )
    external_models_credentials_status.add_argument("--provider", required=True)
    external_models_credentials_status.add_argument(
        "--json", action="store_true", required=True
    )

    external_models_routes = external_models_subparsers.add_parser("routes")
    external_models_routes_subparsers = external_models_routes.add_subparsers(
        dest="routes_command", required=True
    )
    external_models_routes_add = external_models_routes_subparsers.add_parser("add")
    external_models_routes_add_source = external_models_routes_add.add_mutually_exclusive_group(
        required=True
    )
    external_models_routes_add_source.add_argument("--file")
    external_models_routes_add_source.add_argument("--stdin", action="store_true")
    external_models_routes_add.add_argument("--json", action="store_true", required=True)
    external_models_routes_update = external_models_routes_subparsers.add_parser("update")
    external_models_routes_update.add_argument("--route", required=True)
    external_models_routes_update_source = (
        external_models_routes_update.add_mutually_exclusive_group(required=True)
    )
    external_models_routes_update_source.add_argument("--file")
    external_models_routes_update_source.add_argument("--stdin", action="store_true")
    external_models_routes_update.add_argument("--json", action="store_true", required=True)
    external_models_routes_remove = external_models_routes_subparsers.add_parser("remove")
    external_models_routes_remove.add_argument("--route", required=True)
    external_models_routes_remove.add_argument("--json", action="store_true", required=True)
    external_models_routes_list = external_models_routes_subparsers.add_parser("list")
    external_models_routes_list.add_argument("--json", action="store_true", required=True)
    external_models_routes_enable = external_models_routes_subparsers.add_parser("enable")
    external_models_routes_enable.add_argument("--route", required=True)
    external_models_routes_enable.add_argument("--json", action="store_true", required=True)
    external_models_routes_disable = external_models_routes_subparsers.add_parser("disable")
    external_models_routes_disable.add_argument("--route", required=True)
    external_models_routes_disable.add_argument("--json", action="store_true", required=True)
    external_models_routes_validate = external_models_routes_subparsers.add_parser("validate")
    external_models_routes_validate.add_argument("--route", required=True)
    external_models_routes_validate.add_argument("--json", action="store_true", required=True)

    external_models_profile = external_models_subparsers.add_parser("profile")
    external_models_profile_subparsers = external_models_profile.add_subparsers(
        dest="profile_command", required=True
    )
    external_models_profile_codex = external_models_profile_subparsers.add_parser(
        "codex-desktop"
    )
    external_models_profile_codex.add_argument("--route", required=True)
    external_models_profile_codex.add_argument("--json", action="store_true", required=True)

    external_models_evidence = external_models_subparsers.add_parser("evidence")
    external_models_evidence_subparsers = external_models_evidence.add_subparsers(
        dest="evidence_command", required=True
    )
    external_models_evidence_capture = external_models_evidence_subparsers.add_parser(
        "capture"
    )
    external_models_evidence_capture.add_argument("--route", required=True)
    external_models_evidence_capture.add_argument("--json", action="store_true", required=True)

    return root_parser


def emit_json(payload: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    return int(payload["exit_code"])


def command_effect_from_args(args: argparse.Namespace) -> str | None:
    command = getattr(args, "command", None)
    if command in {"status", "invariant-check"}:
        return EFFECT_READ
    if command == "sync":
        return EFFECT_MUTATE
    if command == "token":
        return EFFECT_READ
    if command == "healthcheck":
        return EFFECT_REPAIR if getattr(args, "repair", False) else EFFECT_PROBE
    if command == "stable":
        stable_command = getattr(args, "stable_command", None)
        if stable_command == "repair":
            return EFFECT_REPAIR if getattr(args, "apply", False) else EFFECT_READ
        if (
            stable_command == "target"
            and getattr(args, "stable_target_command", None) == "switch"
        ):
            return EFFECT_MUTATE if getattr(args, "apply", False) else EFFECT_READ
    if command == "launch":
        launch_command = getattr(args, "launch_command", None)
        if launch_command == "smoke":
            return EFFECT_MUTATE
        if launch_command == "client":
            return EFFECT_MUTATE
    if command == "codex-runner" and getattr(args, "codex_runner_command", None) == "smoke":
        return EFFECT_PROBE
    if command == "codex-runner" and getattr(args, "codex_runner_command", None) in {
        "admission",
        "operator-proof",
        "working-flow-visible-source-proof",
    }:
        return EFFECT_MUTATE
    if command == "codex-runner" and getattr(args, "codex_runner_command", None) in {
        "interactive-preflight",
        "interactive-collect",
        "interactive-working-flow-delivery",
    }:
        return EFFECT_MUTATE
    if command == "router-hook" and getattr(args, "router_hook_command", None) in {
        "entry",
        "dispatch",
        "handoff",
        "deliver",
        "ingress",
        "dispatch-proof",
        "handoff-proof",
        "transcript-observe",
        "assistant-continuation-proof",
        "visible-source-observe",
        "user-prompt-submit-proof",
        "user-prompt-submit-ledger-proof",
        "handoff-working-flow-join",
        "working-flow-delivery-proof",
        "user-prompt-submit-readiness",
    }:
        return EFFECT_PROBE
    if (
        command == "router-hook"
        and getattr(args, "router_hook_command", None) == "dispatch-admission"
    ):
        return EFFECT_MUTATE
    if (
        command == "router-hook"
        and getattr(args, "router_hook_command", None)
        == "user-prompt-submit-install"
    ):
        return EFFECT_MUTATE if getattr(args, "apply", False) else EFFECT_READ
    if command == "mode":
        mode_command = getattr(args, "mode_command", None)
        if mode_command == "get":
            return EFFECT_READ
        if mode_command == "set":
            return EFFECT_MUTATE
    if command == "rollback":
        if getattr(args, "apply", False):
            return EFFECT_REPAIR
        if getattr(args, "dry_run", False):
            return EFFECT_READ
    if (
        command == "policy"
        and getattr(args, "policy_command", None) == "stage"
        and getattr(args, "policy_stage_command", None) == "set"
    ):
        return EFFECT_MUTATE
    if command == "rollout":
        rollout_command = getattr(args, "rollout_command", None)
        if (
            rollout_command == "rotation"
            and getattr(args, "rollout_rotation_command", None) == "inspect"
        ):
            return EFFECT_READ
        if (
            rollout_command == "posture"
            and getattr(args, "rollout_posture_command", None) == "inspect"
        ):
            return EFFECT_READ
        if (
            rollout_command == "evidence"
            and getattr(args, "rollout_evidence_command", None) == "capture"
        ):
            return EFFECT_MUTATE
        if rollout_command == "stage":
            rollout_stage_command = getattr(args, "rollout_stage_command", None)
            if rollout_stage_command == "prove":
                return EFFECT_PROBE
            if rollout_stage_command == "advance":
                return EFFECT_MUTATE
    if command == "accounts":
        accounts_command = getattr(args, "accounts_command", None)
        if accounts_command == "list":
            return EFFECT_READ
        if accounts_command == "validate":
            return EFFECT_PROBE
        if accounts_command in {
            "demote",
            "hold",
            "onboard",
            "promote",
            "release",
            "retire",
        }:
            return EFFECT_MUTATE
        if accounts_command == "login":
            login_command = getattr(args, "accounts_login_command", None)
            if login_command == "status":
                return EFFECT_READ
            if login_command in {"start", "complete", "cancel"}:
                return EFFECT_MUTATE
    if command == "diagnostics" and getattr(args, "diagnostics_command", None) == "export":
        return EFFECT_MUTATE
    if command == "installer" and getattr(args, "installer_command", None) == "init":
        return EFFECT_MUTATE
    if command == "legacy" and getattr(args, "legacy_command", None) == "import":
        return EFFECT_MUTATE
    if command == "companion" and getattr(args, "companion_command", None) in {
        "reset",
        "uninstall",
    }:
        return EFFECT_MUTATE
    if command == "package":
        package_command = getattr(args, "package_command", None)
        if package_command == "experimental":
            package_experimental_command = getattr(
                args, "package_experimental_command", None
            )
            if package_experimental_command == "build":
                return EFFECT_MUTATE
            if package_experimental_command == "verify":
                return EFFECT_READ
        if package_command == "launchable":
            package_launchable_command = getattr(
                args, "package_launchable_command", None
            )
            if package_launchable_command == "build":
                return EFFECT_MUTATE
            if package_launchable_command == "verify":
                return EFFECT_READ
    if command == "external-models":
        external_models_command = getattr(args, "external_models_command", None)
        if external_models_command in {"start", "stop"}:
            return EFFECT_MUTATE
        if external_models_command in {"status", "models"}:
            return EFFECT_READ
        if external_models_command == "check":
            return EFFECT_MUTATE
        if external_models_command == "live-format-check":
            return EFFECT_PROBE
        if external_models_command == "routes":
            routes_command = getattr(args, "routes_command", None)
            if routes_command in {"add", "update", "remove", "enable", "disable"}:
                return EFFECT_MUTATE
            if routes_command == "list":
                return EFFECT_READ
            if routes_command == "validate":
                return EFFECT_MUTATE
        if external_models_command == "credentials":
            credentials_command = getattr(args, "credentials_command", None)
            if credentials_command == "admit":
                return EFFECT_MUTATE
            if credentials_command == "status":
                return EFFECT_READ
        if (
            external_models_command == "profile"
            and getattr(args, "profile_command", None) == "codex-desktop"
        ):
            return EFFECT_READ
        if (
            external_models_command == "evidence"
            and getattr(args, "evidence_command", None) == "capture"
        ):
            return EFFECT_MUTATE
    return None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = RuntimePaths.from_env()
    command_effect = command_effect_from_args(args)

    try:
        if args.command == "healthcheck":
            if args.repair:
                return emit_json(
                    run_healthcheck_repair(
                        paths,
                        args.model,
                        dependencies=_healthcheck_repair_dependencies(),
                    )
                )
            return emit_json(
                run_healthcheck_probe(
                    paths,
                    args.model,
                    dependencies=_health_probe_dependencies(),
                )
            )
        if args.command == "status":
            return emit_json(summarize_status(paths))
        if args.command == "invariant-check":
            return emit_json(run_invariant_check(paths))
        if args.command == "token":
            if args.json:
                return emit_json(token_status_payload(paths))
            try:
                sys.stdout.write(emit_local_token(paths))
                return 0
            except RuntimeErrorInfo as exc:
                sys.stderr.write(exc.message + "\n")
                return exc.exit_code
        if args.command == "stable" and args.stable_command == "repair":
            if args.apply:
                return emit_json(run_stable_repair_apply(paths))
            return emit_json(run_stable_repair_dry_run(paths))
        if (
            args.command == "stable"
            and args.stable_command == "target"
            and args.stable_target_command == "switch"
        ):
            return emit_json(
                run_stable_target_switch_contract(paths, apply=bool(args.apply))
            )
        if args.command == "rollback":
            if args.apply:
                return emit_json(run_rollback_latest_apply(paths))
            return emit_json(run_rollback_latest_dry_run(paths))
        if args.command == "sync":
            return emit_json(run_sync(paths, args.model))
        if args.command == "launch" and args.launch_command == "smoke":
            return emit_json(run_launch_smoke(paths))
        if args.command == "launch" and args.launch_command == "client":
            return emit_json(run_launch_client(paths, args.client_path))
        if args.command == "codex-runner" and args.codex_runner_command == "smoke":
            return emit_json(run_codex_cli_runner_smoke(paths, args.prompt))
        if args.command == "codex-runner" and args.codex_runner_command == "admission":
            return emit_json(
                run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    codex_bin=args.codex_bin,
                    proof_dir=args.proof_dir,
                    codex_cwd=args.codex_cwd,
                    expected_text=args.expected_text,
                    sandbox=args.sandbox,
                    timeout_seconds=args.timeout_seconds,
                )
            )
        if (
            args.command == "codex-runner"
            and args.codex_runner_command == "operator-proof"
        ):
            return emit_json(
                run_repeatable_operator_proof_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    codex_bin=args.codex_bin,
                    proof_dir=args.proof_dir,
                    codex_cwd=args.codex_cwd,
                    expected_text=args.expected_text,
                    sandbox=args.sandbox,
                    timeout_seconds=args.timeout_seconds,
                )
            )
        if (
            args.command == "codex-runner"
            and args.codex_runner_command == "working-flow-visible-source-proof"
        ):
            return emit_json(
                run_working_flow_visible_source_proof_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    codex_bin=args.codex_bin,
                    proof_dir=args.proof_dir,
                    codex_cwd=args.codex_cwd,
                    expected_text=args.expected_text,
                    sandbox=args.sandbox,
                    timeout_seconds=args.timeout_seconds,
                )
            )
        if (
            args.command == "codex-runner"
            and args.codex_runner_command == "interactive-preflight"
        ):
            return emit_json(
                run_interactive_custom_codex_preflight_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    proof_dir=args.proof_dir,
                )
            )
        if (
            args.command == "codex-runner"
            and args.codex_runner_command == "interactive-collect"
        ):
            return emit_json(
                run_interactive_custom_codex_collect_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    preflight_packet_file=args.preflight_packet_file,
                    proof_dir=args.proof_dir,
                    expected_text=args.expected_text,
                    live_provider_proof_file=args.live_provider_proof_file,
                )
            )
        if (
            args.command == "codex-runner"
            and args.codex_runner_command == "interactive-working-flow-delivery"
        ):
            return emit_json(
                run_interactive_codex_working_flow_delivery_command(
                    interactive_proof_file=args.interactive_proof_file,
                    integrated_live_provider_proof_file=(
                        args.integrated_live_provider_proof_file
                    ),
                    codex_exec_jsonl_file=args.codex_exec_jsonl_file,
                    proof_dir=args.proof_dir,
                    delivery_source_kind=args.delivery_source_kind,
                )
            )
        if args.command == "router-hook" and args.router_hook_command == "entry":
            return emit_json(
                run_router_hook_entry_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    runtime_context_file=args.runtime_context_file,
                    hook_surface_kind=args.hook_surface_kind,
                )
            )
        if args.command == "router-hook" and args.router_hook_command == "dispatch":
            return emit_json(
                run_controlled_api_dispatch_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    runtime_context_file=args.runtime_context_file,
                    hook_surface_kind=args.hook_surface_kind,
                )
            )
        if args.command == "router-hook" and args.router_hook_command == "handoff":
            return emit_json(
                run_approved_handoff_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    runtime_context_file=args.runtime_context_file,
                    hook_surface_kind=args.hook_surface_kind,
                    handoff_surface_kind=args.handoff_surface_kind,
                )
            )
        if args.command == "router-hook" and args.router_hook_command == "deliver":
            return emit_json(
                run_observed_machine_handoff_delivery_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    runtime_context_file=args.runtime_context_file,
                    hook_surface_kind=args.hook_surface_kind,
                    delivery_surface_kind=args.delivery_surface_kind,
                )
            )
        if args.command == "router-hook" and args.router_hook_command == "ingress":
            return emit_json(
                run_custom_codex_ingress_proof_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    codex_exec_jsonl_file=args.codex_exec_jsonl_file,
                    runtime_context_file=args.runtime_context_file,
                    hook_surface_kind=args.hook_surface_kind,
                )
            )
        if args.command == "router-hook" and args.router_hook_command == "dispatch-proof":
            return emit_json(
                run_controlled_ingress_api_dispatch_proof_command(
                    paths=paths,
                    ingress_proof_file=args.ingress_proof_file,
                    prompt_text=args.prompt,
                    runtime_context_file=args.runtime_context_file,
                    hook_surface_kind=args.hook_surface_kind,
                )
            )
        if args.command == "router-hook" and args.router_hook_command == "handoff-proof":
            return emit_json(
                run_controlled_dispatch_handoff_proof_command(
                    dispatch_proof_file=args.dispatch_proof_file,
                    handoff_surface_kind=args.handoff_surface_kind,
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "transcript-observe"
        ):
            return emit_json(
                run_codex_transcript_delivery_observation_command(
                    handoff_proof_file=args.handoff_proof_file,
                    codex_exec_jsonl_file=args.codex_exec_jsonl_file,
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "assistant-continuation-proof"
        ):
            return emit_json(
                run_codex_exec_assistant_continuation_proof_command(
                    transcript_observation_file=args.transcript_observation_file,
                    codex_exec_jsonl_file=args.codex_exec_jsonl_file,
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "visible-source-observe"
        ):
            return emit_json(
                run_custom_codex_approved_visible_source_observation_command(
                    assistant_continuation_proof_file=(
                        args.assistant_continuation_proof_file
                    ),
                    visible_source_kind=args.visible_source_kind,
                    codex_exec_jsonl_file=args.codex_exec_jsonl_file,
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "user-prompt-submit-proof"
        ):
            return emit_json(
                run_real_custom_codex_hook_proof_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    hook_ledger_file=args.hook_ledger_file,
                    runtime_context_file=args.runtime_context_file,
                    live_provider_expected_text=args.live_provider_expected_text,
                    live_provider_proof_file=args.live_provider_proof_file,
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "user-prompt-submit-ledger-proof"
        ):
            return emit_json(
                run_real_user_prompt_submit_ledger_proof_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    hook_ledger_file=args.hook_ledger_file,
                    runtime_context_file=args.runtime_context_file,
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "dispatch-admission"
        ):
            return emit_json(
                run_native_free_chat_router_dispatch_admission_command(
                    paths=paths,
                    prompt_text=args.prompt,
                    hook_ledger_file=args.hook_ledger_file,
                    runtime_context_file=args.runtime_context_file,
                    handoff_file=args.handoff_file,
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "handoff-working-flow-join"
        ):
            return emit_json(
                run_handoff_to_working_flow_join_command(
                    dispatch_admission_file=args.dispatch_admission_file,
                    dispatch_handoff_file=args.dispatch_handoff_file,
                    codex_exec_jsonl_file=args.codex_exec_jsonl_file,
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "working-flow-delivery-proof"
        ):
            return emit_json(
                run_codex_working_flow_delivery_proof_command(
                    integrated_live_provider_proof_file=(
                        args.integrated_live_provider_proof_file
                    ),
                    codex_exec_jsonl_file=args.codex_exec_jsonl_file,
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "custom-origin-proof"
        ):
            return emit_json(
                run_custom_codex_hook_origin_proof_command(
                    paths=paths,
                    integrated_live_provider_proof_file=(
                        args.integrated_live_provider_proof_file
                    ),
                    working_flow_delivery_proof_file=(
                        args.working_flow_delivery_proof_file
                    ),
                    strict_sealed_evidence=bool(args.strict_sealed_evidence),
                    integrated_live_provider_proof_seal_file=(
                        args.integrated_live_provider_proof_seal_file
                    ),
                    working_flow_delivery_proof_seal_file=(
                        args.working_flow_delivery_proof_seal_file
                    ),
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "proof-seal-create"
        ):
            return emit_json(
                run_proof_seal_create_command(
                    packet_file=args.packet_file,
                    seal_file=args.seal_file,
                    producer_kind=args.producer_kind,
                    producer_command_digest=args.producer_command_digest,
                    producer_inputs_digest=args.producer_inputs_digest or "",
                    input_packet_files=args.input_packet_file,
                    runtime_context_digest=args.runtime_context_digest or "",
                    hook_ledger_digest=args.hook_ledger_digest or "",
                    profile_hook_config_digest=(
                        args.profile_hook_config_digest or ""
                    ),
                    git_commit_sha=args.git_commit_sha or "",
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "proof-seal-verify"
        ):
            return emit_json(
                run_proof_seal_verify_command(
                    packet_file=args.packet_file,
                    seal_file=args.seal_file,
                    expected_packet_kind=args.expected_packet_kind or "",
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "user-prompt-submit-install"
        ):
            return emit_json(
                build_user_prompt_submit_install_packet(
                    paths=paths,
                    apply=bool(args.apply),
                )
            )
        if (
            args.command == "router-hook"
            and args.router_hook_command == "user-prompt-submit-readiness"
        ):
            return emit_json(build_user_prompt_submit_readiness_packet(paths=paths))
        if args.command == "accounts" and args.accounts_command == "list":
            return emit_json(list_accounts(paths))
        if args.command == "accounts" and args.accounts_command == "validate":
            return emit_json(
                run_accounts_command(
                    paths,
                    ["validate", args.id],
                    success_message="Account validation completed.",
                    failure_message="Account validation failed.",
                )
            )
        if args.command == "accounts" and args.accounts_command == "promote":
            return emit_json(run_promote(paths, args.id))
        if args.command == "accounts" and args.accounts_command == "demote":
            return emit_json(run_demote(paths, args.id))
        if args.command == "accounts" and args.accounts_command == "hold":
            return emit_json(run_hold(paths, args.id, args.reason, dry_run=args.dry_run))
        if args.command == "accounts" and args.accounts_command == "release":
            return emit_json(run_release(paths, args.id))
        if args.command == "accounts" and args.accounts_command == "retire":
            return emit_json(run_retire(paths, args.id))
        if args.command == "accounts" and args.accounts_command == "onboard":
            return emit_json(
                run_onboard(
                    paths,
                    auth_ref=args.auth_ref,
                    loop=args.loop,
                    skip_login=args.skip_login,
                    no_sync=args.no_sync,
                    non_interactive=args.non_interactive,
                )
            )
        if (
            args.command == "accounts"
            and args.accounts_command == "login"
            and args.accounts_login_command == "start"
        ):
            return emit_json(
                run_accounts_login_start(paths, args.provider, mode=args.mode)
            )
        if (
            args.command == "accounts"
            and args.accounts_command == "login"
            and args.accounts_login_command == "status"
        ):
            return emit_json(run_accounts_login_status(paths, args.session))
        if (
            args.command == "accounts"
            and args.accounts_command == "login"
            and args.accounts_login_command == "complete"
        ):
            return emit_json(
                run_accounts_login_complete(
                    paths,
                    login_session_id=args.session,
                    state=getattr(args, "state", None),
                    proof=getattr(args, "proof", None),
                )
            )
        if (
            args.command == "accounts"
            and args.accounts_command == "login"
            and args.accounts_login_command == "cancel"
        ):
            return emit_json(run_accounts_login_cancel(paths, args.session))
        if args.command == "diagnostics" and args.diagnostics_command == "export":
            return emit_json(export_diagnostics(paths))
        if args.command == "installer" and args.installer_command == "init":
            return emit_json(run_installer_init(paths))
        if args.command == "legacy" and args.legacy_command == "import":
            return emit_json(run_legacy_import(paths, args.source_dir))
        if args.command == "companion" and args.companion_command == "reset":
            return emit_json(run_companion_reset(paths, uninstall=False))
        if args.command == "companion" and args.companion_command == "uninstall":
            return emit_json(run_companion_reset(paths, uninstall=True))
        if args.command == "mode" and args.mode_command == "get":
            return emit_json(mode_get(paths))
        if args.command == "mode" and args.mode_command == "set":
            return emit_json(mode_set(paths, args.value))
        if (
            args.command == "policy"
            and args.policy_command == "stage"
            and args.policy_stage_command == "set"
        ):
            return emit_json(run_policy_stage_set(paths, args.value))
        if (
            args.command == "rollout"
            and args.rollout_command == "rotation"
            and args.rollout_rotation_command == "inspect"
        ):
            return emit_json(run_rollout_rotation_inspect(paths))
        if (
            args.command == "rollout"
            and args.rollout_command == "posture"
            and args.rollout_posture_command == "inspect"
        ):
            return emit_json(run_rollout_posture_inspect(paths, args.value))
        if (
            args.command == "rollout"
            and args.rollout_command == "evidence"
            and args.rollout_evidence_command == "capture"
        ):
            return emit_json(run_rollout_evidence_capture(paths, args.value))
        if (
            args.command == "rollout"
            and args.rollout_command == "stage"
            and args.rollout_stage_command == "prove"
        ):
            return emit_json(run_rollout_stage_prove(paths, args.value))
        if (
            args.command == "rollout"
            and args.rollout_command == "stage"
            and args.rollout_stage_command == "advance"
        ):
            return emit_json(run_rollout_stage_advance(paths, args.value, args.id))
        if (
            args.command == "package"
            and args.package_command == "experimental"
            and args.package_experimental_command == "build"
        ):
            return emit_json(run_package_experimental_build(paths, args.output_dir))
        if (
            args.command == "package"
            and args.package_command == "experimental"
            and args.package_experimental_command == "verify"
        ):
            return emit_json(run_package_experimental_verify(paths, args.manifest))
        if (
            args.command == "package"
            and args.package_command == "launchable"
            and args.package_launchable_command == "build"
        ):
            return emit_json(
                run_package_launchable_build(
                    paths,
                    args.output_dir,
                    runtime_executable_raw=args.runtime_executable,
                )
            )
        if (
            args.command == "package"
            and args.package_command == "launchable"
            and args.package_launchable_command == "verify"
        ):
            return emit_json(run_package_launchable_verify(paths, args.manifest))
        if args.command == "external-models":
            return emit_json(run_external_models_command(args))
        raise RuntimeErrorInfo(
            "Unsupported command",
            machine_error_code="UNSUPPORTED_COMMAND",
            operator_action="user_action",
        )
    except RuntimeErrorInfo as exc:
        next_action = str(getattr(exc, "next_action", exc.operator_action))
        operator_action = (
            exc.operator_action
            if exc.operator_action in command_packets.COMMAND_OPERATOR_ACTION_VALUES
            else "user_action"
        )
        payload = {
            "status": "error",
            "exit_code": exc.exit_code,
            "human_message": exc.message,
            "machine_error_code": exc.machine_error_code,
            "changed_files": [],
            "next_action": next_action,
            "liveness": "unknown",
            "severity": exc.severity,
            "operator_action": operator_action,
        }
        if command_effect is not None:
            payload["effect"] = command_effect
        if (
            args.command == "accounts"
            and getattr(args, "accounts_command", None) == "promote"
        ):
            payload["mutation_id"] = None
        return emit_json(payload)


if __name__ == "__main__":
    raise SystemExit(main())

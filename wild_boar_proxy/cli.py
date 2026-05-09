# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .runtime import (
    RuntimeErrorInfo,
    RuntimePaths,
    export_diagnostics,
    list_accounts,
    mode_get,
    mode_set,
    run_accounts_command,
    run_demote,
    run_healthcheck,
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
    run_rollout_evidence_capture,
    run_rollout_posture_inspect,
    run_rollout_rotation_inspect,
    run_rollout_stage_advance,
    run_rollout_stage_prove,
    run_package_experimental_build,
    run_package_experimental_verify,
    run_retire,
    run_stable_repair_apply,
    run_stable_repair_dry_run,
    run_stable_target_switch_contract,
    run_sync,
    summarize_status,
)


def build_parser() -> argparse.ArgumentParser:
    root_parser = argparse.ArgumentParser(prog="wild-boar-proxy")
    subparsers = root_parser.add_subparsers(dest="command", required=True)

    healthcheck = subparsers.add_parser("healthcheck")
    healthcheck.add_argument("--json", action="store_true", required=True)
    healthcheck.add_argument("--model")

    status = subparsers.add_parser("status")
    status.add_argument("--json", action="store_true", required=True)

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
    accounts_hold.add_argument("--json", action="store_true", required=True)

    accounts_onboard = accounts_subparsers.add_parser("onboard")
    accounts_onboard.add_argument("--json", action="store_true", required=True)
    accounts_onboard.add_argument("--auth-ref")
    accounts_onboard.add_argument("--loop", action="store_true")
    accounts_onboard.add_argument("--skip-login", action="store_true")
    accounts_onboard.add_argument("--no-sync", action="store_true")
    accounts_onboard.add_argument("--non-interactive", action="store_true")

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

    return root_parser


def emit_json(payload: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    return int(payload["exit_code"])


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = RuntimePaths.from_env()

    try:
        if args.command == "healthcheck":
            return emit_json(run_healthcheck(paths, args.model))
        if args.command == "status":
            return emit_json(summarize_status(paths))
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
        if args.command == "sync":
            return emit_json(run_sync(paths, args.model))
        if args.command == "launch" and args.launch_command == "smoke":
            return emit_json(run_launch_smoke(paths))
        if args.command == "launch" and args.launch_command == "client":
            return emit_json(run_launch_client(paths, args.client_path))
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
            return emit_json(run_hold(paths, args.id, args.reason))
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
        raise RuntimeErrorInfo(
            "Unsupported command",
            machine_error_code="UNSUPPORTED_COMMAND",
            operator_action="user_action",
        )
    except RuntimeErrorInfo as exc:
        payload = {
            "status": "error",
            "exit_code": exc.exit_code,
            "human_message": exc.message,
            "machine_error_code": exc.machine_error_code,
            "changed_files": [],
            "next_action": exc.operator_action,
            "liveness": "unknown",
            "severity": exc.severity,
            "operator_action": exc.operator_action,
        }
        return emit_json(payload)

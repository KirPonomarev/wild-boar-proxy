"""Bounded external-models foundation commands."""

from __future__ import annotations

from typing import Any

from wild_boar_proxy.runtime import RuntimeErrorInfo

from . import contracts, errors, routes
from .paths import ExternalModelsPaths
from .state import capture_local_evidence, ensure_secrets_permissions


def run_external_models_command(args: Any) -> dict[str, Any]:
    try:
        paths = ExternalModelsPaths.from_env()
        if args.external_models_command == "status":
            return contracts.build_external_models_payload(
                ok=True,
                human_message="External-models foundation status collected.",
                machine_error_code=errors.OK,
                data=routes.foundation_status(paths),
            )
        if args.external_models_command == "models":
            models = routes.models_listing(paths)
            return contracts.build_external_models_payload(
                ok=True,
                human_message="External-models route models listed from local registry.",
                machine_error_code=errors.OK,
                data={
                    "models": models,
                    "count": len(models),
                    "source": "local_routes_registry",
                },
            )
        if args.external_models_command == "routes":
            return _run_routes_command(paths, args)
        if args.external_models_command == "profile" and args.profile_command == "codex-desktop":
            data = routes.profile_packet(paths, args.route)
            return contracts.build_external_models_payload(
                ok=True,
                human_message="Codex Desktop profile contract generated without mutating config.",
                machine_error_code=errors.OK,
                data=data,
            )
        if args.external_models_command == "evidence" and args.evidence_command == "capture":
            route = routes.find_route(routes.load_routes_file(paths.routes_file), args.route)
            ensure_secrets_permissions(paths.secrets_file)
            packet = contracts.build_external_models_payload(
                ok=True,
                human_message="Local external-models evidence captured from foundation contract.",
                machine_error_code=errors.OK,
                data={"route_id": route["route_id"], "network_dependent_evidence": False},
            )
            evidence_path = capture_local_evidence(
                evidence_dir=paths.evidence_dir,
                route=route,
                packet=packet,
            )
            packet["changed_files"] = [str(evidence_path)]
            packet["data"]["evidence_path"] = str(evidence_path)
            return packet
        raise RuntimeErrorInfo(
            "Unsupported external-models command.",
            machine_error_code=errors.INVALID_REQUEST,
            operator_action="user_action",
        )
    except RuntimeErrorInfo as exc:
        return contracts.build_external_models_payload(
            ok=False,
            human_message=exc.message,
            machine_error_code=exc.machine_error_code,
            next_action=exc.operator_action,
            severity=exc.severity,
            liveness="unknown",
            exit_code=exc.exit_code,
            data={},
        )


def _run_routes_command(paths: ExternalModelsPaths, args: Any) -> dict[str, Any]:
    action = args.routes_command
    if action == "add":
        route = routes.load_route_input(file_path=args.file, use_stdin=args.stdin)
        changed_files = routes.add_route(paths, route)
        return contracts.build_external_models_payload(
            ok=True,
            human_message=f"External-models route added: {route['route_id']}.",
            machine_error_code=errors.OK,
            changed_files=changed_files,
            data={"route_id": route["route_id"]},
        )
    if action == "update":
        route = routes.load_route_input(file_path=args.file, use_stdin=args.stdin)
        changed_files = routes.update_route(paths, args.route, route)
        return contracts.build_external_models_payload(
            ok=True,
            human_message=f"External-models route updated: {args.route}.",
            machine_error_code=errors.OK,
            changed_files=changed_files,
            data={"route_id": args.route},
        )
    if action == "remove":
        changed_files = routes.remove_route(paths, args.route)
        return contracts.build_external_models_payload(
            ok=True,
            human_message=f"External-models route removed: {args.route}.",
            machine_error_code=errors.OK,
            changed_files=changed_files,
            data={"route_id": args.route},
        )
    if action == "list":
        listed = routes.list_routes(paths)
        return contracts.build_external_models_payload(
            ok=True,
            human_message="External-models routes listed from local registry.",
            machine_error_code=errors.OK,
            data={"routes": listed, "count": len(listed)},
        )
    if action == "enable":
        changed_files = routes.set_route_enabled(paths, args.route, True)
        return contracts.build_external_models_payload(
            ok=True,
            human_message=f"External-models route enabled: {args.route}.",
            machine_error_code=errors.OK,
            changed_files=changed_files,
            data={"route_id": args.route, "enabled": True},
        )
    if action == "disable":
        changed_files = routes.set_route_enabled(paths, args.route, False)
        return contracts.build_external_models_payload(
            ok=True,
            human_message=f"External-models route disabled: {args.route}.",
            machine_error_code=errors.OK,
            changed_files=changed_files,
            data={"route_id": args.route, "enabled": False},
        )
    raise RuntimeErrorInfo(
        "Unsupported external-models routes command.",
        machine_error_code=errors.INVALID_REQUEST,
        operator_action="user_action",
    )

# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Local desktop shell boundary for the live web UI."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from typing import Any
from urllib import error, request
import webbrowser

from .loopback_http_server import LoopbackThreadingHTTPServer
from .runtime import RuntimePaths
from .web_design_live_server import (
    FULL_ACTION_PHASE,
    LIVE_READONLY_ACTION_PHASE,
    SANDBOX_ACTION_PHASE,
    LaunchCopyContract,
    build_handler,
    owner_authorization_phrase_present,
)
from .web_ingress import unsafe_bind_requested
from .web_token import (
    WEB_CSRF_META_NAME,
    WEB_TOKEN_META_NAME,
    create_web_token,
    delete_web_token,
)

NO_PROXY_OPENER = request.build_opener(request.ProxyHandler({}))
DESKTOP_WEB_SHELL_SCHEMA_VERSION = 1
DESKTOP_WEB_SHELL_ENTRYPOINT = "wild_boar_proxy.desktop_web_shell"
DESKTOP_WEB_SHELL_STRATEGY = "web_design_live_server_local_only"
DESKTOP_WEB_SHELL_DEFAULT_HOST = "127.0.0.1"
DESKTOP_WEB_SHELL_DEFAULT_PORT = 8788
DESKTOP_WEB_SHELL_UNAUTHORIZED_POST_PATH = "/api/action"
DESKTOP_WEB_SHELL_PUBLIC_BIND_ERROR = "DESKTOP_WEB_SHELL_PUBLIC_BIND_REJECTED"
DESKTOP_WEB_SHELL_BIND_ERROR = "DESKTOP_WEB_SHELL_BIND_FAILED"
DESKTOP_WEB_SHELL_ACTION_PHASES = (
    LIVE_READONLY_ACTION_PHASE,
    SANDBOX_ACTION_PHASE,
    FULL_ACTION_PHASE,
)
DESKTOP_WEB_SHELL_R1_ACTIONS = (
    "onboard_account_dry_run",
    "onboard_account",
    "api_route_connect",
    "api_route_credential_check",
    "launch_custom_client_native",
    "quick_start_check_all",
)


class DesktopWebShellError(ValueError):
    """Raised when the desktop web shell boundary cannot be admitted."""

    def __init__(self, message: str, *, machine_error_code: str) -> None:
        super().__init__(message)
        self.machine_error_code = machine_error_code


def host_is_loopback(host: str) -> bool:
    normalized = str(host or "").strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_desktop_bind_host(host: str) -> str:
    normalized = str(host or "").strip()
    if unsafe_bind_requested(normalized) or not host_is_loopback(normalized):
        raise DesktopWebShellError(
            "Desktop web shell must bind only to a loopback host.",
            machine_error_code=DESKTOP_WEB_SHELL_PUBLIC_BIND_ERROR,
        )
    return normalized


def _base_url(host: str, port: int) -> str:
    if ":" in host and not host.startswith("["):
        return f"http://[{host}]:{port}"
    return f"http://{host}:{port}"


def _fetch_text(url: str, *, timeout_seconds: float = 3.0) -> str:
    with NO_PROXY_OPENER.open(url, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")


def _fetch_json(url: str, *, timeout_seconds: float = 3.0) -> dict[str, Any]:
    payload = json.loads(_fetch_text(url, timeout_seconds=timeout_seconds))
    return payload if isinstance(payload, dict) else {}


def _post_json_without_auth(url: str, *, timeout_seconds: float = 3.0) -> dict[str, Any]:
    post_request = request.Request(
        url,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with NO_PROXY_OPENER.open(post_request, timeout=timeout_seconds) as response:
            return {
                "http_status": int(response.status),
                "payload": json.loads(response.read().decode("utf-8")),
            }
    except error.HTTPError as exc:
        return {
            "http_status": int(exc.code),
            "payload": json.loads(exc.read().decode("utf-8")),
        }


def _desktop_sandbox_copy_port(action_server_port: int) -> int:
    if action_server_port > 0 and action_server_port != 9321:
        return 9321
    if action_server_port > 0:
        return action_server_port + 1
    return 9321


def _desktop_sandbox_root() -> Path:
    return (
        Path(tempfile.gettempdir())
        / f"wild-boar-proxy-desktop-sandbox-{os.getpid()}"
    )


def _desktop_sandbox_launch_copy_contract(
    *, action_server_port: int
) -> LaunchCopyContract:
    sandbox_root = _desktop_sandbox_root()
    profile_dir = sandbox_root / "profile"
    data_dir = sandbox_root / "managed"
    profile_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    return LaunchCopyContract(
        profile_dir=str(profile_dir),
        data_dir=str(data_dir),
        copy_port=_desktop_sandbox_copy_port(action_server_port),
        action_server_port=action_server_port,
    )


def _desktop_launch_copy_contract_for_phase(
    *, action_phase: str, action_server_port: int
) -> LaunchCopyContract | None:
    if action_phase == SANDBOX_ACTION_PHASE:
        return _desktop_sandbox_launch_copy_contract(
            action_server_port=action_server_port
        )
    return None


def _cleanup_desktop_sandbox_root_if_needed(action_phase: str) -> None:
    if action_phase != SANDBOX_ACTION_PHASE:
        return
    sandbox_root = _desktop_sandbox_root()
    temp_root = Path(tempfile.gettempdir()).resolve(strict=False)
    try:
        resolved = sandbox_root.resolve(strict=False)
    except OSError:
        return
    if resolved.parent != temp_root:
        return
    if not resolved.name.startswith("wild-boar-proxy-desktop-sandbox-"):
        return
    shutil.rmtree(resolved, ignore_errors=True)


def build_desktop_web_shell_server(
    *,
    host: str = DESKTOP_WEB_SHELL_DEFAULT_HOST,
    port: int = DESKTOP_WEB_SHELL_DEFAULT_PORT,
    action_phase: str = LIVE_READONLY_ACTION_PHASE,
    owner_authorization_phrase: str | None = None,
) -> tuple[LoopbackThreadingHTTPServer, Any]:
    admitted_host = validate_desktop_bind_host(host)
    if port < 0:
        raise DesktopWebShellError(
            "Desktop web shell port must be non-negative.",
            machine_error_code="DESKTOP_WEB_SHELL_PORT_INVALID",
        )
    if action_phase not in DESKTOP_WEB_SHELL_ACTION_PHASES:
        raise DesktopWebShellError(
            "Desktop web shell admits only live_readonly, sandbox_actions, or owner-authorized full.",
            machine_error_code="DESKTOP_WEB_SHELL_ACTION_PHASE_INVALID",
        )
    if action_phase == FULL_ACTION_PHASE and not owner_authorization_phrase_present(
        owner_authorization_phrase
    ):
        raise DesktopWebShellError(
            "Desktop web shell full action phase requires exact owner authorization phrase.",
            machine_error_code="DESKTOP_WEB_SHELL_OWNER_AUTHORIZATION_REQUIRED",
        )
    web_token_state = create_web_token(RuntimePaths.from_env().managed_dir)
    launch_copy_contract = _desktop_launch_copy_contract_for_phase(
        action_phase=action_phase,
        action_server_port=port,
    )
    try:
        server = LoopbackThreadingHTTPServer(
            (admitted_host, port),
            build_handler(
                action_phase=action_phase,
                launch_copy_contract=launch_copy_contract,
                owner_authorization_phrase=owner_authorization_phrase,
                web_token_state=web_token_state,
            ),
        )
    except OSError as exc:
        delete_web_token(web_token_state)
        _cleanup_desktop_sandbox_root_if_needed(action_phase)
        raise DesktopWebShellError(
            f"Desktop web shell failed to bind {admitted_host}:{port}.",
            machine_error_code=DESKTOP_WEB_SHELL_BIND_ERROR,
        ) from exc
    except Exception:
        delete_web_token(web_token_state)
        _cleanup_desktop_sandbox_root_if_needed(action_phase)
        raise
    return server, web_token_state


def build_desktop_web_shell_packet(
    *,
    host: str,
    base_url: str,
    port: int,
    action_phase: str,
    index_html: str,
    live_readonly: dict[str, Any],
    accounts_readonly: dict[str, Any],
    api_connections_readonly: dict[str, Any],
    action_metadata: dict[str, Any],
    unauthorized_post: dict[str, Any],
) -> dict[str, Any]:
    unauthorized_payload = unauthorized_post.get("payload")
    if not isinstance(unauthorized_payload, dict):
        unauthorized_payload = {}
    unauthorized_machine_error = str(
        unauthorized_payload.get("machine_error_code", "")
    )
    token_meta_present = f'name="{WEB_TOKEN_META_NAME}"' in index_html
    csrf_meta_present = f'name="{WEB_CSRF_META_NAME}"' in index_html
    unauthorized_post_rejected = (
        int(unauthorized_post.get("http_status", 0)) == 401
        and unauthorized_machine_error == "WEB_INGRESS_WEB_TOKEN_REJECTED"
    )
    live_commands = live_readonly.get("commands")
    if not isinstance(live_commands, dict):
        live_commands = {}
    accounts_summary = accounts_readonly.get("summary")
    if not isinstance(accounts_summary, dict):
        accounts_summary = {}
    api_summary = api_connections_readonly.get("summary")
    if not isinstance(api_summary, dict):
        api_summary = {}
    live_readonly_endpoint_ok = "status" in live_readonly
    accounts_readonly_endpoint_ok = "status" in accounts_readonly
    api_connections_readonly_endpoint_ok = "status" in api_connections_readonly
    actions_metadata = action_metadata.get("actions")
    if not isinstance(actions_metadata, dict):
        actions_metadata = {}
    r1_action_metadata: dict[str, dict[str, Any]] = {}
    for ui_action in DESKTOP_WEB_SHELL_R1_ACTIONS:
        action = actions_metadata.get(ui_action)
        if not isinstance(action, dict):
            action = {}
        r1_action_metadata[ui_action] = {
            "available": action.get("available") is True,
            "availability_state": str(action.get("availability_state", "")),
            "disabled_reason_code": str(action.get("disabled_reason_code", "")),
        }
    sandbox_preflight = action_metadata.get("sandbox_preflight")
    if not isinstance(sandbox_preflight, dict):
        sandbox_preflight = {}
    status_ok = (
        token_meta_present
        and csrf_meta_present
        and unauthorized_post_rejected
        and live_readonly_endpoint_ok
        and accounts_readonly_endpoint_ok
        and api_connections_readonly_endpoint_ok
        and isinstance(action_metadata, dict)
        and action_metadata.get("status") == "ok"
    )
    return {
        "schema_version": DESKTOP_WEB_SHELL_SCHEMA_VERSION,
        "status": "ok" if status_ok else "error",
        "machine_error_code": "OK" if status_ok else "DESKTOP_WEB_SHELL_SMOKE_FAILED",
        "source": "desktop_web_shell_smoke",
        "changed_files": [],
        "desktop_shell": {
            "strategy": DESKTOP_WEB_SHELL_STRATEGY,
            "entrypoint": DESKTOP_WEB_SHELL_ENTRYPOINT,
            "default_surface": "web_design_live_server",
            "legacy_tk_shell_compatibility": True,
        },
        "server": {
            "host": host,
            "port": port,
            "base_url": base_url,
            "local_only_bind": True,
            "public_bind_allowed": False,
            "action_phase": action_phase,
            "full_action_phase_admitted_by_desktop_shell": action_phase
            == FULL_ACTION_PHASE,
        },
        "first_screen": {
            "html_loaded": bool(index_html),
            "data_source_live": 'data-source="live"' in index_html,
            "custom_launch_action_present": "quickStartCustomLaunchAction" in index_html,
            "agent_alias_packet_present": "quickStartAgentAliasPacket" in index_html,
            "live_readonly_endpoint_ok": live_readonly_endpoint_ok,
            "status_truth_present": isinstance(live_commands.get("status"), dict),
            "healthcheck_truth_present": isinstance(
                live_commands.get("healthcheck"), dict
            ),
            "mode_truth_present": isinstance(live_commands.get("mode_get"), dict),
            "accounts_readonly_endpoint_ok": accounts_readonly_endpoint_ok,
            "accounts_visible_count": accounts_summary.get("visible_count"),
            "accounts_machine_error_code": accounts_summary.get("machine_error_code"),
            "api_connections_readonly_endpoint_ok": api_connections_readonly_endpoint_ok,
            "api_routes_count": api_summary.get("routes_count"),
            "api_machine_error_code": api_summary.get("machine_error_code"),
        },
        "web_security": {
            "web_token_bootstrap_meta_present": token_meta_present,
            "csrf_bootstrap_meta_present": csrf_meta_present,
            "web_bootstrap_tokens_delivered_to_browser": (
                token_meta_present and csrf_meta_present
            ),
            "unauthorized_post_rejected": unauthorized_post_rejected,
            "unauthorized_post_http_status": unauthorized_post.get("http_status"),
            "unauthorized_post_machine_error_code": unauthorized_machine_error,
        },
        "action_metadata": {
            "status": action_metadata.get("status"),
            "source": action_metadata.get("source"),
            "action_phase": action_metadata.get("action_phase"),
            "sandbox_preflight_status": sandbox_preflight.get("status"),
            "sandbox_preflight_machine_error_code": sandbox_preflight.get(
                "machine_error_code"
            ),
            "r1_actions": r1_action_metadata,
            "live_actions_remain_server_guarded": True,
        },
        "packet_contents": {
            "includes_index_html": False,
            "includes_live_readonly_payload": False,
            "includes_accounts_payload": False,
            "includes_api_connections_payload": False,
            "includes_web_token_value": False,
            "includes_csrf_token_value": False,
        },
        "package_boundary": {
            "evaluated_by_shell_smoke": False,
            "requires_package_launchable_verify": True,
            "expected_boundary": "allowlisted_repo_source_docs_and_launcher_only",
        },
    }


def run_desktop_web_shell_smoke(
    *,
    host: str = DESKTOP_WEB_SHELL_DEFAULT_HOST,
    port: int = 0,
    action_phase: str = LIVE_READONLY_ACTION_PHASE,
    owner_authorization_phrase: str | None = None,
) -> tuple[dict[str, Any], int]:
    try:
        server, web_token_state = build_desktop_web_shell_server(
            host=host,
            port=port,
            action_phase=action_phase,
            owner_authorization_phrase=owner_authorization_phrase,
        )
    except DesktopWebShellError as exc:
        return (
            {
                "schema_version": DESKTOP_WEB_SHELL_SCHEMA_VERSION,
                "status": "error",
                "machine_error_code": exc.machine_error_code,
                "source": "desktop_web_shell_smoke",
                "changed_files": [],
                "human_message": str(exc),
            },
            1,
        )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        actual_port = int(server.server_port)
        admitted_host = validate_desktop_bind_host(host)
        base_url = _base_url(admitted_host, actual_port)
        index_html = _fetch_text(f"{base_url}/")
        live_readonly = _fetch_json(f"{base_url}/api/live-readonly")
        accounts_readonly = _fetch_json(f"{base_url}/api/accounts-readonly")
        api_connections_readonly = _fetch_json(
            f"{base_url}/api/api-connections-readonly"
        )
        action_metadata = json.loads(_fetch_text(f"{base_url}/api/actions"))
        unauthorized_post = _post_json_without_auth(
            f"{base_url}{DESKTOP_WEB_SHELL_UNAUTHORIZED_POST_PATH}"
        )
        packet = build_desktop_web_shell_packet(
            host=admitted_host,
            base_url=base_url,
            port=actual_port,
            action_phase=action_phase,
            index_html=index_html,
            live_readonly=live_readonly,
            accounts_readonly=accounts_readonly,
            api_connections_readonly=api_connections_readonly,
            action_metadata=action_metadata,
            unauthorized_post=unauthorized_post,
        )
        return packet, 0 if packet["status"] == "ok" else 1
    except Exception as exc:
        return (
            {
                "schema_version": DESKTOP_WEB_SHELL_SCHEMA_VERSION,
                "status": "error",
                "machine_error_code": "DESKTOP_WEB_SHELL_SMOKE_FAILED",
                "source": "desktop_web_shell_smoke",
                "changed_files": [],
                "human_message": (
                    "Desktop web shell smoke failed: "
                    f"{exc.__class__.__name__}: {exc}"
                ),
            },
            1,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        delete_web_token(web_token_state)
        _cleanup_desktop_sandbox_root_if_needed(action_phase)


def run_desktop_web_shell(
    *,
    host: str = DESKTOP_WEB_SHELL_DEFAULT_HOST,
    port: int = DESKTOP_WEB_SHELL_DEFAULT_PORT,
    open_browser: bool = True,
    action_phase: str = LIVE_READONLY_ACTION_PHASE,
    owner_authorization_phrase: str | None = None,
) -> int:
    server, web_token_state = build_desktop_web_shell_server(
        host=host,
        port=port,
        action_phase=action_phase,
        owner_authorization_phrase=owner_authorization_phrase,
    )
    base_url = _base_url(validate_desktop_bind_host(host), int(server.server_port))
    print(base_url, flush=True)
    try:
        if open_browser:
            webbrowser.open(base_url)
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        delete_web_token(web_token_state)
        _cleanup_desktop_sandbox_root_if_needed(action_phase)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DESKTOP_WEB_SHELL_DEFAULT_HOST)
    parser.add_argument("--port", type=int)
    parser.add_argument("--no-open-browser", action="store_true")
    parser.add_argument("--smoke-json", action="store_true")
    parser.add_argument(
        "--action-phase",
        default=LIVE_READONLY_ACTION_PHASE,
        choices=DESKTOP_WEB_SHELL_ACTION_PHASES,
    )
    parser.add_argument("--owner-authorization-phrase", default=None)
    args = parser.parse_args(argv)
    if args.smoke_json:
        packet, exit_code = run_desktop_web_shell_smoke(
            host=args.host,
            port=args.port if args.port is not None else 0,
            action_phase=args.action_phase,
            owner_authorization_phrase=args.owner_authorization_phrase,
        )
        print(json.dumps(packet, ensure_ascii=False, sort_keys=True))
        return exit_code
    try:
        return run_desktop_web_shell(
            host=args.host,
            port=args.port if args.port is not None else DESKTOP_WEB_SHELL_DEFAULT_PORT,
            open_browser=not args.no_open_browser,
            action_phase=args.action_phase,
            owner_authorization_phrase=args.owner_authorization_phrase,
        )
    except DesktopWebShellError as exc:
        print(f"{exc.machine_error_code}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

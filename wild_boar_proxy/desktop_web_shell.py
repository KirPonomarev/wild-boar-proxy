# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Local desktop shell boundary for the live web UI."""

from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
import ipaddress
import json
import sys
import threading
from typing import Any
from urllib import error, request
import webbrowser

from .runtime import RuntimePaths
from .web_design_live_server import LIVE_READONLY_ACTION_PHASE, build_handler
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


def build_desktop_web_shell_server(
    *,
    host: str = DESKTOP_WEB_SHELL_DEFAULT_HOST,
    port: int = DESKTOP_WEB_SHELL_DEFAULT_PORT,
) -> tuple[ThreadingHTTPServer, Any]:
    admitted_host = validate_desktop_bind_host(host)
    if port < 0:
        raise DesktopWebShellError(
            "Desktop web shell port must be non-negative.",
            machine_error_code="DESKTOP_WEB_SHELL_PORT_INVALID",
        )
    web_token_state = create_web_token(RuntimePaths.from_env().managed_dir)
    try:
        server = ThreadingHTTPServer(
            (admitted_host, port),
            build_handler(
                action_phase=LIVE_READONLY_ACTION_PHASE,
                web_token_state=web_token_state,
            ),
        )
    except Exception:
        delete_web_token(web_token_state)
        raise
    return server, web_token_state


def build_desktop_web_shell_packet(
    *,
    host: str,
    base_url: str,
    port: int,
    index_html: str,
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
    status_ok = (
        token_meta_present
        and csrf_meta_present
        and unauthorized_post_rejected
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
            "action_phase": LIVE_READONLY_ACTION_PHASE,
        },
        "first_screen": {
            "html_loaded": bool(index_html),
            "data_source_live": 'data-source="live"' in index_html,
            "custom_launch_action_present": "quickStartCustomLaunchAction" in index_html,
            "agent_alias_packet_present": "quickStartAgentAliasPacket" in index_html,
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
            "live_actions_remain_server_guarded": True,
        },
        "packet_contents": {
            "includes_index_html": False,
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
) -> tuple[dict[str, Any], int]:
    try:
        server, web_token_state = build_desktop_web_shell_server(host=host, port=port)
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
        action_metadata = json.loads(_fetch_text(f"{base_url}/api/actions"))
        unauthorized_post = _post_json_without_auth(
            f"{base_url}{DESKTOP_WEB_SHELL_UNAUTHORIZED_POST_PATH}"
        )
        packet = build_desktop_web_shell_packet(
            host=admitted_host,
            base_url=base_url,
            port=actual_port,
            index_html=index_html,
            action_metadata=action_metadata,
            unauthorized_post=unauthorized_post,
        )
        return packet, 0 if packet["status"] == "ok" else 1
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        delete_web_token(web_token_state)


def run_desktop_web_shell(
    *,
    host: str = DESKTOP_WEB_SHELL_DEFAULT_HOST,
    port: int = DESKTOP_WEB_SHELL_DEFAULT_PORT,
    open_browser: bool = True,
) -> int:
    server, web_token_state = build_desktop_web_shell_server(host=host, port=port)
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
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DESKTOP_WEB_SHELL_DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DESKTOP_WEB_SHELL_DEFAULT_PORT)
    parser.add_argument("--no-open-browser", action="store_true")
    parser.add_argument("--smoke-json", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke_json:
        packet, exit_code = run_desktop_web_shell_smoke(
            host=args.host,
            port=args.port,
        )
        print(json.dumps(packet, ensure_ascii=False, sort_keys=True))
        return exit_code
    try:
        return run_desktop_web_shell(
            host=args.host,
            port=args.port,
            open_browser=not args.no_open_browser,
        )
    except DesktopWebShellError as exc:
        print(f"{exc.machine_error_code}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

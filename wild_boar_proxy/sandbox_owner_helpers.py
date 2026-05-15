# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from .runtime import (
    RuntimePaths,
    now_iso,
    read_json,
    read_yaml_value,
    write_json_atomic,
    write_text_atomic,
    write_toml_string_atomic,
)

SCHEMA_VERSION = 2


def load_registry(paths: RuntimePaths) -> dict[str, Any]:
    data = read_json(paths.registry_file)
    data.setdefault("version", SCHEMA_VERSION)
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("backends", [])
    data.setdefault(
        "pool_policy", {"active_target": 0, "active_min": 0, "reserve_target": 0}
    )
    return data


def save_registry(paths: RuntimePaths, data: dict[str, Any]) -> None:
    data["version"] = SCHEMA_VERSION
    data["schema_version"] = SCHEMA_VERSION
    data["updated_at"] = now_iso()
    write_json_atomic(paths.registry_file, data)


def load_state(paths: RuntimePaths) -> dict[str, Any]:
    if not paths.state_file.exists():
        return {}
    data = read_json(paths.state_file)
    if not isinstance(data, dict):
        return {}
    return data


def save_state(paths: RuntimePaths, data: dict[str, Any]) -> None:
    write_json_atomic(paths.state_file, data)


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "backend"


def unique_backend_id(candidate: str, existing_ids: set[str]) -> str:
    candidate = slugify(candidate)
    if candidate not in existing_ids:
        return candidate
    index = 2
    while f"{candidate}-{index}" in existing_ids:
        index += 1
    return f"{candidate}-{index}"


def derive_identity_from_auth_ref(
    auth_ref: str, existing_ids: set[str]
) -> tuple[str, str]:
    auth_path = Path(auth_ref).expanduser()
    stem = auth_path.stem
    if stem.startswith("codex-"):
        stem = stem[len("codex-") :]

    parts = stem.split("-")
    email_token = next((part for part in parts if "@" in part), "")
    tier_token = (
        parts[-1]
        if parts and parts[-1] in {"team", "plus", "pro", "business"}
        else ""
    )

    if email_token:
        local_part = email_token.split("@", 1)[0]
        candidate = f"{local_part}-{tier_token}" if tier_token else local_part
        label = email_token
    else:
        useful = [
            part for part in parts if part and not re.fullmatch(r"[0-9a-f]{6,}", part)
        ]
        if tier_token and useful and useful[-1] == tier_token:
            useful = useful[:-1]
        base = "-".join(useful[:2]) if useful else stem
        candidate = f"{base}-{tier_token}" if tier_token else base
        label = auth_path.name

    return unique_backend_id(candidate, existing_ids), label


def make_backend_entry(
    backend_id: str,
    label: str,
    auth_ref: str,
    pool: str,
    priority: int,
    notes: str,
) -> dict[str, Any]:
    return {
        "id": backend_id,
        "type": "cliproxy-auth-file",
        "label": label,
        "enabled": True,
        "priority": priority,
        "pool": pool,
        "status": "unknown",
        "fail_count": 0,
        "success_count": 0,
        "last_success": None,
        "last_error": "",
        "last_error_class": "",
        "cooldown_until": None,
        "proxy_mode": "auto-detect",
        "auth_ref": auth_ref,
        "added_at": now_iso(),
        "disabled_reason": "",
        "drain_until": None,
        "last_probe_level": None,
        "last_probe_at": None,
        "last_deep_probe_at": None,
        "last_transition_at": None,
        "manual_hold": False,
        "half_open_since": None,
        "notes": notes or "",
    }


def find_backend(registry: dict[str, Any], backend_id: str) -> dict[str, Any]:
    for item in registry.get("backends", []):
        if str(item.get("id")) == backend_id:
            return item
    raise SystemExit(f"Backend not found: {backend_id}")


def backend_by_auth_ref(
    registry: dict[str, Any], auth_ref: str
) -> dict[str, Any] | None:
    normalized = str(Path(auth_ref).expanduser())
    for backend in registry.get("backends", []):
        if str(Path(backend.get("auth_ref", "")).expanduser()) == normalized:
            return backend
    return None


def validate_auth_payload(auth_path: Path) -> dict[str, Any]:
    if not auth_path.exists():
        raise SystemExit(f"auth_ref does not exist: {auth_path}")
    payload = read_json(auth_path)
    if not isinstance(payload, dict):
        raise SystemExit(f"invalid auth payload at {auth_path}: expected object")
    if payload.get("type") not in {"codex", "apikey"}:
        raise SystemExit(f"invalid auth type: {payload.get('type')}")
    if payload.get("type") == "codex":
        for field in ("email", "access_token", "account_id"):
            if not payload.get(field):
                raise SystemExit(f"missing auth field: {field}")
    elif not payload.get("OPENAI_API_KEY"):
        raise SystemExit("missing auth field: OPENAI_API_KEY")
    return payload


def sync_state_counts_from_registry(
    registry: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    active = reserve = retired = healthy = degraded = down = 0
    for backend in registry.get("backends", []):
        pool = str(backend.get("pool", ""))
        status = str(backend.get("status", "unknown"))
        if pool == "active":
            active += 1
        elif pool == "reserve":
            reserve += 1
        elif pool == "retired":
            retired += 1
        if status == "healthy":
            healthy += 1
        elif status == "degraded":
            degraded += 1
        else:
            down += 1
    state["active_count"] = active
    state["reserve_count"] = reserve
    state["retired_count"] = retired
    state["healthy_count"] = healthy
    state["degraded_count"] = degraded
    state["down_count"] = down
    return state


def cmd_accounts_status(paths: RuntimePaths, _args: argparse.Namespace) -> int:
    registry = load_registry(paths)
    state = sync_state_counts_from_registry(registry, load_state(paths))
    save_state(paths, state)
    print("Managed summary")
    print(f"  schema_version: {registry.get('schema_version')}")
    print(f"  stable_default_backend_id: {registry.get('stable_default_backend_id', '')}")
    print(f"  effective_mode: {state.get('effective_mode', '')}")
    print(f"  supervisor_status: {state.get('status', '')}")
    print(f"  current_proxy_url: {state.get('current_proxy_url', '')}")
    print(
        "  counts: "
        f"active={state.get('active_count', 0)} "
        f"reserve={state.get('reserve_count', 0)} "
        f"retired={state.get('retired_count', 0)} "
        f"healthy={state.get('healthy_count', 0)} "
        f"degraded={state.get('degraded_count', 0)} "
        f"down={state.get('down_count', 0)}"
    )
    print(f"  selected_backend_ids: {', '.join(state.get('selected_backend_ids', []))}")
    print(f"  last_sync_at: {state.get('last_sync_at', '')}")
    print(f"  last_error: {state.get('last_error', '')}")
    return 0


def cmd_accounts_add(paths: RuntimePaths, args: argparse.Namespace) -> int:
    registry = load_registry(paths)
    auth_path = Path(args.auth_ref).expanduser()
    validate_auth_payload(auth_path)
    auth_ref = str(auth_path)
    existing_ids = {str(item.get("id", "")) for item in registry.get("backends", [])}
    backend_id = args.id or derive_identity_from_auth_ref(auth_ref, existing_ids)[0]
    if backend_id in existing_ids:
        raise SystemExit(f"Backend already exists: {backend_id}")
    label = args.label or derive_identity_from_auth_ref(
        auth_ref, existing_ids | {backend_id}
    )[1]
    registry.setdefault("backends", []).append(
        make_backend_entry(
            backend_id, label, auth_ref, args.pool, args.priority, args.notes
        )
    )
    save_registry(paths, registry)
    print(f"Added backend: {backend_id} ({label})")
    return 0


def cmd_accounts_hold_release(
    paths: RuntimePaths, args: argparse.Namespace, *, hold: bool
) -> int:
    registry = load_registry(paths)
    backend = find_backend(registry, args.id)
    backend["manual_hold"] = hold
    backend["last_transition_at"] = now_iso()
    if getattr(args, "reason", ""):
        backend["notes"] = args.reason
    save_registry(paths, registry)
    print(f"{'Held' if hold else 'Released'} backend: {args.id}")
    return 0


def cmd_accounts_pool(paths: RuntimePaths, args: argparse.Namespace) -> int:
    registry = load_registry(paths)
    backend = find_backend(registry, args.id)
    backend["pool"] = args.pool
    backend["last_transition_at"] = now_iso()
    save_registry(paths, registry)
    print(f"Set pool for {args.id} -> {args.pool}")
    return 0


def cmd_accounts_priority(paths: RuntimePaths, args: argparse.Namespace) -> int:
    registry = load_registry(paths)
    backend = find_backend(registry, args.id)
    backend["priority"] = args.priority
    save_registry(paths, registry)
    print(f"Set priority for {args.id} -> {args.priority}")
    return 0


def cmd_accounts_default(paths: RuntimePaths, args: argparse.Namespace) -> int:
    registry = load_registry(paths)
    find_backend(registry, args.id)
    registry["stable_default_backend_id"] = args.id
    save_registry(paths, registry)
    print(f"Set stable default backend -> {args.id}")
    return 0


def cmd_accounts_note(paths: RuntimePaths, args: argparse.Namespace) -> int:
    registry = load_registry(paths)
    backend = find_backend(registry, args.id)
    backend["notes"] = args.note
    save_registry(paths, registry)
    print(f"Updated note for {args.id}")
    return 0


def validate_one(backend: dict[str, Any]) -> tuple[bool, str]:
    auth_ref = backend.get("auth_ref", "")
    if not auth_ref:
        return False, "missing auth_ref"
    auth_path = Path(auth_ref).expanduser()
    if not auth_path.exists():
        return False, f"missing auth file: {auth_path}"
    if backend.get("pool") not in {"active", "reserve", "retired"}:
        return False, f"invalid pool: {backend.get('pool')}"
    try:
        payload = read_json(auth_path)
    except Exception as exc:  # noqa: BLE001
        return False, f"invalid auth json: {exc}"
    if not isinstance(payload, dict):
        return False, "invalid auth payload: expected object"
    auth_type = payload.get("type")
    if auth_type == "codex":
        for field in ("email", "access_token", "account_id"):
            if not payload.get(field):
                return False, f"missing auth field: {field}"
        return True, "ok"
    if auth_type == "apikey":
        if not payload.get("OPENAI_API_KEY"):
            return False, "missing auth field: OPENAI_API_KEY"
        return True, "ok"
    return False, f"invalid auth type: {auth_type}"


def cmd_accounts_validate(paths: RuntimePaths, args: argparse.Namespace) -> int:
    registry = load_registry(paths)
    rows = registry.get("backends", [])
    if args.id:
        rows = [find_backend(registry, args.id)]
    failures = 0
    seen_auth_refs: dict[str, list[str]] = {}
    seen_account_ids: dict[str, list[str]] = {}
    for backend in registry.get("backends", []):
        auth_ref = backend.get("auth_ref", "")
        if not auth_ref:
            continue
        normalized = str(Path(auth_ref).expanduser())
        seen_auth_refs.setdefault(normalized, []).append(str(backend["id"]))
        try:
            payload = read_json(Path(normalized))
        except Exception:
            payload = {}
        account_id = payload.get("account_id")
        if account_id:
            seen_account_ids.setdefault(str(account_id), []).append(str(backend["id"]))
    for backend in rows:
        ok, message = validate_one(backend)
        if ok:
            normalized = str(Path(backend.get("auth_ref", "")).expanduser())
            duplicate_auth = seen_auth_refs.get(normalized, [])
            if len(duplicate_auth) > 1:
                ok = False
                message = f"duplicate auth_ref used by: {', '.join(sorted(duplicate_auth))}"
            else:
                try:
                    payload = read_json(Path(normalized))
                except Exception:
                    payload = {}
                account_id = payload.get("account_id")
                duplicate_account = (
                    seen_account_ids.get(str(account_id), []) if account_id else []
                )
                if len(duplicate_account) > 1:
                    message = (
                        "ok (warning: duplicate account_id used by: "
                        + ", ".join(sorted(duplicate_account))
                        + ")"
                    )
        print(f"{backend['id']}: {'OK' if ok else 'FAIL'} - {message}")
        if not ok:
            failures += 1
    return 1 if failures else 0


def cmd_onboard(paths: RuntimePaths, args: argparse.Namespace) -> int:
    registry = load_registry(paths)
    if args.auth_ref:
        auth_path = Path(args.auth_ref).expanduser()
    else:
        auth_path = paths.auth_file
        if not auth_path.exists():
            if args.non_interactive:
                raise SystemExit(
                    "No new auth file detected. Re-run without --non-interactive or pass --auth-ref PATH."
                )
            raise SystemExit("No sandbox-local auth candidate is available.")
    validate_auth_payload(auth_path)
    auth_ref = str(auth_path)
    existing_backend = backend_by_auth_ref(registry, auth_ref)
    if existing_backend is None:
        existing_ids = {str(item.get("id", "")) for item in registry.get("backends", [])}
        backend_id = args.id or derive_identity_from_auth_ref(auth_ref, existing_ids)[0]
        if backend_id in existing_ids:
            raise SystemExit(f"Backend already exists: {backend_id}")
        label = args.label or derive_identity_from_auth_ref(
            auth_ref, existing_ids | {backend_id}
        )[1]
        notes = args.notes or f"Onboarded automatically at {now_iso()}"
        registry.setdefault("backends", []).append(
            make_backend_entry(
                backend_id, label, auth_ref, args.pool, args.priority, notes
            )
        )
        save_registry(paths, registry)
        print(f"Added backend: {backend_id} ({label})")
        return 0
    print(f"Reused backend: {existing_backend['id']}")
    return 0


def cmd_sync(paths: RuntimePaths, args: argparse.Namespace) -> int:
    registry = load_registry(paths)
    state = load_state(paths)
    state.setdefault("schema_version", SCHEMA_VERSION)
    state.setdefault("version", SCHEMA_VERSION)
    state["effective_mode"] = "stable"
    state["status"] = "unknown"
    state["last_error"] = ""
    state["current_proxy_url"] = ""
    state["last_sync_at"] = now_iso()
    sync_state_counts_from_registry(registry, state)
    save_state(paths, state)
    write_text_atomic(paths.runtime_effective_mode_file, "stable")
    stable_port = read_yaml_value(paths.stable_config, "port") or "8318"
    write_toml_string_atomic(
        paths.config_toml, "base_url", f"http://127.0.0.1:{stable_port}/v1"
    )
    print(f"sync-stable:{stable_port}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sandbox-owner-helpers")
    sub = parser.add_subparsers(dest="helper_command", required=True)

    accounts = sub.add_parser("accounts")
    accounts_sub = accounts.add_subparsers(dest="accounts_command", required=True)
    accounts_sub.add_parser("status")

    add = accounts_sub.add_parser("add")
    add.add_argument("--id")
    add.add_argument("--label")
    add.add_argument("--auth-ref", required=True)
    add.add_argument("--pool", choices=["active", "reserve", "retired"], default="reserve")
    add.add_argument("--priority", type=int, default=100)
    add.add_argument("--notes", default="")

    for name in ("hold", "release"):
        p = accounts_sub.add_parser(name)
        p.add_argument("id")
        p.add_argument("reason", nargs="?")

    for name, pool in (("promote", "active"), ("demote", "reserve"), ("retire", "retired")):
        p = accounts_sub.add_parser(name)
        p.add_argument("id")
        p.set_defaults(pool=pool)

    priority = accounts_sub.add_parser("priority")
    priority.add_argument("id")
    priority.add_argument("priority", type=int)

    default = accounts_sub.add_parser("default")
    default.add_argument("id")

    note = accounts_sub.add_parser("note")
    note.add_argument("id")
    note.add_argument("note")

    validate = accounts_sub.add_parser("validate")
    validate.add_argument("id", nargs="?")

    onboard = sub.add_parser("onboard")
    onboard.add_argument("--auth-ref")
    onboard.add_argument("--loop", action="store_true")
    onboard.add_argument("--once", action="store_true")
    onboard.add_argument("--skip-login", action="store_true")
    onboard.add_argument("--no-sync", action="store_true")
    onboard.add_argument("--non-interactive", action="store_true")
    onboard.add_argument("--id")
    onboard.add_argument("--label")
    onboard.add_argument("--pool", choices=["active", "reserve", "retired"], default="reserve")
    onboard.add_argument("--priority", type=int, default=100)
    onboard.add_argument("--notes", default="")

    sub.add_parser("status")

    sync = sub.add_parser("sync")
    sync.add_argument("model", nargs="?")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    paths = RuntimePaths.from_env()

    if args.helper_command == "accounts":
        command = args.accounts_command
        if command == "status":
            return cmd_accounts_status(paths, args)
        if command == "add":
            return cmd_accounts_add(paths, args)
        if command == "hold":
            return cmd_accounts_hold_release(paths, args, hold=True)
        if command == "release":
            return cmd_accounts_hold_release(paths, args, hold=False)
        if command in {"promote", "demote", "retire"}:
            return cmd_accounts_pool(paths, args)
        if command == "priority":
            return cmd_accounts_priority(paths, args)
        if command == "default":
            return cmd_accounts_default(paths, args)
        if command == "note":
            return cmd_accounts_note(paths, args)
        if command == "validate":
            return cmd_accounts_validate(paths, args)
        parser.error(f"Unsupported accounts helper command: {command}")

    if args.helper_command == "onboard":
        return cmd_onboard(paths, args)

    if args.helper_command == "status":
        return cmd_accounts_status(paths, args)

    if args.helper_command == "sync":
        return cmd_sync(paths, args)

    parser.error(f"Unsupported helper command: {args.helper_command}")


if __name__ == "__main__":
    raise SystemExit(main())

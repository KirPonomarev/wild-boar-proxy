# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import threading
from dataclasses import dataclass
from tkinter import StringVar, Tk, messagebox
from tkinter import ttk
from typing import Any


VALID_LIVENESS = {"healthy", "degraded", "down", "stale", "unknown"}
VALID_ACCOUNT_POOLS = {"active", "reserve", "retired"}
POOL_SUMMARY_FIELDS = (
    "active",
    "reserve",
    "retired",
    "healthy",
    "degraded",
    "down",
)
ATTESTATION_SUMMARY_FIELDS = (
    "status",
    "machine_error_code",
    "attestation_source",
    "observed_at_utc",
)
ACCOUNT_FIELDS = (
    "id",
    "label",
    "pool",
    "manual_hold",
    "status",
    "fail_count",
    "success_count",
    "last_success",
    "last_error",
    "cooldown_until",
    "notes",
)
REGISTRY_IDENTITY_FIELDS = (
    "status",
    "machine_error_code",
    "next_action",
)
ACCOUNT_CAPACITY_TARGET = 20


class UiShellError(Exception):
    """Raised when the UI cannot trust a command result."""


def parse_exact_json_object(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    payload, end = decoder.raw_decode(stdout)
    if not isinstance(payload, dict):
        raise UiShellError("stdout JSON must be an object")
    if stdout[end:].strip():
        raise UiShellError("stdout must contain exactly one JSON object")
    return payload


def require_fields(payload: dict[str, Any], fields: tuple[str, ...], context: str) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        missing_fields = ", ".join(sorted(missing))
        raise UiShellError(f"{context} missing required fields: {missing_fields}")


def require_nonnegative_int(value: Any, context: str) -> int:
    if isinstance(value, bool):
        raise UiShellError(f"{context} must be a nonnegative integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise UiShellError(f"{context} must be a nonnegative integer") from exc
    if number < 0:
        raise UiShellError(f"{context} must be a nonnegative integer")
    return number


def require_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        raise UiShellError(f"{context} must be a boolean")
    return value


@dataclass(frozen=True)
class CommandResult:
    payload: dict[str, Any]
    stderr: str


class JsonCommandRunner:
    def __init__(
        self,
        *,
        base_command: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._base_command = base_command or [sys.executable, "-m", "wild_boar_proxy"]
        self._cwd = cwd
        self._env = env

    def run(self, *args: str) -> CommandResult:
        result = subprocess.run(
            [*self._base_command, *args],
            cwd=self._cwd,
            env=self._env,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = parse_exact_json_object(result.stdout)
        require_fields(
            payload,
            (
                "status",
                "exit_code",
                "human_message",
                "machine_error_code",
                "changed_files",
                "next_action",
            ),
            "command payload",
        )
        return CommandResult(payload=payload, stderr=result.stderr)


@dataclass(frozen=True)
class RuntimeSnapshot:
    overall_state: str
    exit_code: int
    human_message: str
    next_action: str
    machine_error_code: str
    desired_mode: str
    effective_mode: str
    endpoint: str
    current_proxy_url: str
    liveness: str
    severity: str
    operator_action: str
    active_count: int
    reserve_count: int
    retired_count: int
    healthy_count: int
    degraded_count: int
    down_count: int
    attestation_status: str
    attestation_machine_error_code: str
    attestation_source: str
    attestation_observed_at: str
    last_error: str
    integration_error: str

    @classmethod
    def integration_failure(cls, message: str) -> "RuntimeSnapshot":
        return cls(
            overall_state="integration_failure",
            exit_code=1,
            human_message="UI integration failure.",
            next_action="retry",
            machine_error_code="UI_INTEGRATION_FAILURE",
            desired_mode="unknown",
            effective_mode="unknown",
            endpoint="",
            current_proxy_url="",
            liveness="unknown",
            severity="recoverable",
            operator_action="retry",
            active_count=0,
            reserve_count=0,
            retired_count=0,
            healthy_count=0,
            degraded_count=0,
            down_count=0,
            attestation_status="unknown",
            attestation_machine_error_code="UI_INTEGRATION_FAILURE",
            attestation_source="",
            attestation_observed_at="",
            last_error="",
            integration_error=message,
        )


@dataclass(frozen=True)
class AccountRecord:
    backend_id: str
    label: str
    pool: str
    manual_hold: bool
    status: str
    fail_count: int
    success_count: int
    last_success: str
    last_error: str
    cooldown_until: str
    notes: str


@dataclass(frozen=True)
class AccountPoolSnapshot:
    human_message: str
    machine_error_code: str
    registry_identity_status: str
    registry_identity_machine_error_code: str
    registry_identity_next_action: str
    active_count: int
    reserve_count: int
    retired_count: int
    capacity_target: int
    accounts: tuple[AccountRecord, ...]
    integration_error: str

    @classmethod
    def integration_failure(cls, message: str) -> "AccountPoolSnapshot":
        return cls(
            human_message="UI integration failure.",
            machine_error_code="UI_INTEGRATION_FAILURE",
            registry_identity_status="unknown",
            registry_identity_machine_error_code="UI_INTEGRATION_FAILURE",
            registry_identity_next_action="retry",
            active_count=0,
            reserve_count=0,
            retired_count=0,
            capacity_target=ACCOUNT_CAPACITY_TARGET,
            accounts=(),
            integration_error=message,
        )


def build_runtime_snapshot(
    *,
    status_payload: dict[str, Any],
    mode_payload: dict[str, Any],
) -> RuntimeSnapshot:
    require_fields(
        status_payload,
        (
            "status",
            "exit_code",
            "human_message",
            "machine_error_code",
            "next_action",
            "liveness",
            "severity",
            "operator_action",
            "desired_mode",
            "effective_mode",
            "endpoint",
            "current_proxy_url",
            "pool_summary",
            "attestation_summary",
        ),
        "status payload",
    )
    require_fields(mode_payload, ("desired_mode", "effective_mode"), "mode payload")

    desired_mode = str(mode_payload["desired_mode"])
    effective_mode = str(mode_payload["effective_mode"])
    if desired_mode != str(status_payload["desired_mode"]):
        raise UiShellError("mode get and status disagree about desired mode")
    if effective_mode != str(status_payload["effective_mode"]):
        raise UiShellError("mode get and status disagree about effective mode")

    liveness = str(status_payload["liveness"])
    if liveness not in VALID_LIVENESS:
        raise UiShellError(f"unsupported liveness value: {liveness}")

    pool_summary = status_payload["pool_summary"]
    if not isinstance(pool_summary, dict):
        raise UiShellError("status pool_summary must be an object")
    require_fields(pool_summary, POOL_SUMMARY_FIELDS, "pool_summary")

    attestation_summary = status_payload["attestation_summary"]
    if not isinstance(attestation_summary, dict):
        raise UiShellError("status attestation_summary must be an object")
    require_fields(attestation_summary, ATTESTATION_SUMMARY_FIELDS, "attestation_summary")

    return RuntimeSnapshot(
        overall_state=str(status_payload["status"]),
        exit_code=require_nonnegative_int(status_payload["exit_code"], "status exit_code"),
        human_message=str(status_payload["human_message"]),
        next_action=str(status_payload["next_action"]),
        machine_error_code=str(status_payload["machine_error_code"]),
        desired_mode=desired_mode,
        effective_mode=effective_mode,
        endpoint=str(status_payload["endpoint"]),
        current_proxy_url=str(status_payload["current_proxy_url"]),
        liveness=liveness,
        severity=str(status_payload["severity"]),
        operator_action=str(status_payload["operator_action"]),
        active_count=require_nonnegative_int(pool_summary["active"], "pool_summary.active"),
        reserve_count=require_nonnegative_int(pool_summary["reserve"], "pool_summary.reserve"),
        retired_count=require_nonnegative_int(pool_summary["retired"], "pool_summary.retired"),
        healthy_count=require_nonnegative_int(pool_summary["healthy"], "pool_summary.healthy"),
        degraded_count=require_nonnegative_int(
            pool_summary["degraded"], "pool_summary.degraded"
        ),
        down_count=require_nonnegative_int(pool_summary["down"], "pool_summary.down"),
        attestation_status=str(attestation_summary["status"]),
        attestation_machine_error_code=str(attestation_summary["machine_error_code"]),
        attestation_source=str(attestation_summary["attestation_source"]),
        attestation_observed_at=str(attestation_summary["observed_at_utc"]),
        last_error=str(status_payload.get("last_error", "")),
        integration_error="",
    )


def normalize_account_record(raw: dict[str, Any]) -> AccountRecord:
    require_fields(raw, ACCOUNT_FIELDS, "account record")
    pool = str(raw["pool"])
    if pool not in VALID_ACCOUNT_POOLS:
        raise UiShellError(f"unsupported account pool value: {pool}")
    return AccountRecord(
        backend_id=str(raw["id"]),
        label=str(raw["label"]),
        pool=pool,
        manual_hold=require_bool(raw["manual_hold"], "account.manual_hold"),
        status=str(raw["status"]),
        fail_count=require_nonnegative_int(raw["fail_count"], "account.fail_count"),
        success_count=require_nonnegative_int(raw["success_count"], "account.success_count"),
        last_success="" if raw["last_success"] is None else str(raw["last_success"]),
        last_error="" if raw["last_error"] is None else str(raw["last_error"]),
        cooldown_until="" if raw["cooldown_until"] is None else str(raw["cooldown_until"]),
        notes="" if raw["notes"] is None else str(raw["notes"]),
    )


def build_account_pool_snapshot(accounts_payload: dict[str, Any]) -> AccountPoolSnapshot:
    require_fields(
        accounts_payload,
        (
            "human_message",
            "machine_error_code",
            "accounts",
            "registry_identity",
        ),
        "accounts payload",
    )
    accounts_raw = accounts_payload["accounts"]
    if not isinstance(accounts_raw, list):
        raise UiShellError("accounts payload accounts must be a list")
    accounts = tuple(normalize_account_record(item) for item in accounts_raw if isinstance(item, dict))
    if len(accounts) != len(accounts_raw):
        raise UiShellError("accounts payload accounts must contain only objects")

    registry_identity = accounts_payload["registry_identity"]
    if not isinstance(registry_identity, dict):
        raise UiShellError("registry_identity must be an object")
    require_fields(registry_identity, REGISTRY_IDENTITY_FIELDS, "registry_identity")

    active_count = sum(1 for account in accounts if account.pool == "active")
    reserve_count = sum(1 for account in accounts if account.pool == "reserve")
    retired_count = sum(1 for account in accounts if account.pool == "retired")

    return AccountPoolSnapshot(
        human_message=str(accounts_payload["human_message"]),
        machine_error_code=str(accounts_payload["machine_error_code"]),
        registry_identity_status=str(registry_identity["status"]),
        registry_identity_machine_error_code=str(registry_identity["machine_error_code"]),
        registry_identity_next_action=str(registry_identity["next_action"]),
        active_count=active_count,
        reserve_count=reserve_count,
        retired_count=retired_count,
        capacity_target=ACCOUNT_CAPACITY_TARGET,
        accounts=accounts,
        integration_error="",
    )


def load_runtime_snapshot(runner: JsonCommandRunner) -> RuntimeSnapshot:
    return build_runtime_snapshot(
        status_payload=runner.run("status", "--json").payload,
        mode_payload=runner.run("mode", "get", "--json").payload,
    )


def load_account_pool_snapshot(runner: JsonCommandRunner) -> AccountPoolSnapshot:
    return build_account_pool_snapshot(runner.run("accounts", "list", "--json").payload)


def run_mode_control_and_refresh(
    runner: JsonCommandRunner, command: tuple[str, ...]
) -> tuple[dict[str, Any], RuntimeSnapshot]:
    action_result = runner.run(*command)
    snapshot = load_runtime_snapshot(runner)
    return action_result.payload, snapshot


def run_sync_and_refresh(
    runner: JsonCommandRunner,
) -> tuple[dict[str, Any], RuntimeSnapshot, AccountPoolSnapshot]:
    action_result = runner.run("sync", "--json")
    status_payload = runner.run("status", "--json").payload
    accounts_payload = runner.run("accounts", "list", "--json").payload
    mode_payload = runner.run("mode", "get", "--json").payload
    runtime_snapshot = build_runtime_snapshot(
        status_payload=status_payload,
        mode_payload=mode_payload,
    )
    account_snapshot = build_account_pool_snapshot(accounts_payload)
    return action_result.payload, runtime_snapshot, account_snapshot


def run_account_validate_and_refresh(
    runner: JsonCommandRunner, backend_id: str
) -> tuple[dict[str, Any], AccountPoolSnapshot]:
    action_result = runner.run("accounts", "validate", backend_id, "--json")
    snapshot = load_account_pool_snapshot(runner)
    return action_result.payload, snapshot


class MinimalCompanionShell:
    def __init__(self, root: Tk, runner: JsonCommandRunner) -> None:
        self.root = root
        self.runner = runner
        self.root.title("Wild Boar Proxy")
        self.root.geometry("1180x760")
        self.root.minsize(960, 640)
        self._busy = False

        self.banner_var = StringVar(value="Refresh required.")
        self.state_var = StringVar(value="unknown")
        self.exit_code_var = StringVar(value="0")
        self.next_action_var = StringVar(value="unknown")
        self.desired_mode_var = StringVar(value="unknown")
        self.effective_mode_var = StringVar(value="unknown")
        self.endpoint_var = StringVar(value="")
        self.current_proxy_var = StringVar(value="")
        self.liveness_var = StringVar(value="unknown")
        self.severity_var = StringVar(value="recoverable")
        self.operator_action_var = StringVar(value="none")
        self.machine_error_var = StringVar(value="")
        self.pool_var = StringVar(value="A:0 R:0 T:0 H:0 D:0 X:0")
        self.attestation_var = StringVar(value="")
        self.last_error_var = StringVar(value="")
        self.integration_var = StringVar(value="")
        self.account_registry_var = StringVar(value="unknown")
        self.account_counts_var = StringVar(value="A:0 R:0 T:0")
        self.account_capacity_var = StringVar(value=str(ACCOUNT_CAPACITY_TARGET))
        self.account_integration_var = StringVar(value="")

        self._build_layout()
        self.root.after(0, self.refresh)

    def _build_layout(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container)
        header.pack(fill="x")
        ttk.Label(header, text="Wild Boar Proxy", font=("TkDefaultFont", 15, "bold")).pack(
            side="left"
        )
        ttk.Button(header, text="Refresh", command=self.refresh).pack(side="right")

        ttk.Label(container, textvariable=self.banner_var, padding=(0, 10, 0, 10)).pack(
            fill="x"
        )

        top = ttk.Frame(container)
        top.pack(fill="both", expand=False)

        status_box = ttk.LabelFrame(top, text="Runtime Status", padding=12)
        status_box.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._add_status_row(status_box, "State", self.state_var)
        self._add_status_row(status_box, "Exit code", self.exit_code_var)
        self._add_status_row(status_box, "Next action", self.next_action_var)
        self._add_status_row(status_box, "Desired mode", self.desired_mode_var)
        self._add_status_row(status_box, "Effective mode", self.effective_mode_var)
        self._add_status_row(status_box, "Endpoint", self.endpoint_var)
        self._add_status_row(status_box, "Current proxy", self.current_proxy_var)
        self._add_status_row(status_box, "Liveness", self.liveness_var)
        self._add_status_row(status_box, "Severity", self.severity_var)
        self._add_status_row(status_box, "Operator action", self.operator_action_var)
        self._add_status_row(status_box, "Machine error", self.machine_error_var)
        self._add_status_row(status_box, "Pool", self.pool_var)
        self._add_status_row(status_box, "Attestation", self.attestation_var)
        self._add_status_row(status_box, "Last error", self.last_error_var)
        self._add_status_row(status_box, "Integration", self.integration_var)

        controls_box = ttk.LabelFrame(top, text="Mode Controls", padding=12)
        controls_box.pack(side="left", fill="y", padx=(8, 0))
        ttk.Button(
            controls_box,
            text="Switch Stable",
            command=lambda: self.run_mode_action(
                "Switch desired mode to stable?",
                ("mode", "set", "stable", "--json"),
            ),
        ).pack(fill="x", pady=4)
        ttk.Button(
            controls_box,
            text="Switch Managed",
            command=lambda: self.run_mode_action(
                "Switch desired mode to managed?",
                ("mode", "set", "managed", "--json"),
            ),
        ).pack(fill="x", pady=4)
        ttk.Button(
            controls_box,
            text="Run Managed Sync",
            command=self.run_sync_action,
        ).pack(fill="x", pady=4)

        accounts_box = ttk.LabelFrame(container, text="Account Pool", padding=12)
        accounts_box.pack(fill="both", expand=True, pady=(16, 0))

        account_summary = ttk.Frame(accounts_box)
        account_summary.pack(fill="x")
        self._add_status_row(account_summary, "Registry identity", self.account_registry_var)
        self._add_status_row(account_summary, "Account counts", self.account_counts_var)
        self._add_status_row(account_summary, "Capacity target", self.account_capacity_var)
        self._add_status_row(account_summary, "Integration", self.account_integration_var)

        account_actions = ttk.Frame(accounts_box)
        account_actions.pack(fill="x", pady=(10, 10))
        ttk.Button(account_actions, text="Validate", command=self.run_validate_action).pack(
            side="left"
        )
        ttk.Button(account_actions, text="Recheck", command=self.run_recheck_action).pack(
            side="left", padx=(8, 0)
        )

        columns = (
            "id",
            "label",
            "pool",
            "hold",
            "status",
            "fail",
            "success",
            "last_success",
            "last_error",
            "cooldown_until",
            "notes",
        )
        self.accounts_tree = ttk.Treeview(
            accounts_box,
            columns=columns,
            show="headings",
            height=14,
        )
        for column, heading, width in (
            ("id", "ID", 140),
            ("label", "Label", 150),
            ("pool", "Pool", 90),
            ("hold", "Hold", 60),
            ("status", "Status", 100),
            ("fail", "Fail", 60),
            ("success", "Success", 70),
            ("last_success", "Last Success", 170),
            ("last_error", "Last Error", 220),
            ("cooldown_until", "Cooldown Until", 170),
            ("notes", "Notes", 180),
        ):
            self.accounts_tree.heading(column, text=heading)
            self.accounts_tree.column(column, width=width, anchor="w")
        self.accounts_tree.pack(fill="both", expand=True)

    def _add_status_row(self, parent: ttk.Widget, label: str, variable: StringVar) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=f"{label}:", width=16).pack(side="left")
        ttk.Label(row, textvariable=variable).pack(side="left", fill="x", expand=True)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy

    def refresh(self) -> None:
        if self._busy:
            return
        self.set_busy(True)
        self.banner_var.set("Refreshing command truth...")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            runtime_snapshot = load_runtime_snapshot(self.runner)
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
        try:
            account_snapshot = load_account_pool_snapshot(self.runner)
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
        self.root.after(
            0,
            lambda: self._apply_refresh_results(runtime_snapshot, account_snapshot),
        )

    def _apply_runtime_snapshot(self, snapshot: RuntimeSnapshot) -> None:
        self.state_var.set(snapshot.overall_state)
        self.exit_code_var.set(str(snapshot.exit_code))
        self.next_action_var.set(snapshot.next_action)
        self.desired_mode_var.set(snapshot.desired_mode)
        self.effective_mode_var.set(snapshot.effective_mode)
        self.endpoint_var.set(snapshot.endpoint)
        self.current_proxy_var.set(snapshot.current_proxy_url)
        self.liveness_var.set(snapshot.liveness)
        self.severity_var.set(snapshot.severity)
        self.operator_action_var.set(snapshot.operator_action)
        self.machine_error_var.set(snapshot.machine_error_code)
        self.pool_var.set(
            "A:{active} R:{reserve} T:{retired} H:{healthy} D:{degraded} X:{down}".format(
                active=snapshot.active_count,
                reserve=snapshot.reserve_count,
                retired=snapshot.retired_count,
                healthy=snapshot.healthy_count,
                degraded=snapshot.degraded_count,
                down=snapshot.down_count,
            )
        )
        self.attestation_var.set(
            (
                f"{snapshot.attestation_status} / "
                f"{snapshot.attestation_machine_error_code} / "
                f"{snapshot.attestation_source} @ {snapshot.attestation_observed_at}"
            ).strip()
        )
        self.last_error_var.set(snapshot.last_error)
        self.integration_var.set(snapshot.integration_error)

    def _apply_account_snapshot(self, snapshot: AccountPoolSnapshot) -> None:
        self.account_registry_var.set(
            (
                f"{snapshot.registry_identity_status} / "
                f"{snapshot.registry_identity_machine_error_code} / "
                f"{snapshot.registry_identity_next_action}"
            ).strip()
        )
        self.account_counts_var.set(
            "A:{active} R:{reserve} T:{retired}".format(
                active=snapshot.active_count,
                reserve=snapshot.reserve_count,
                retired=snapshot.retired_count,
            )
        )
        self.account_capacity_var.set(str(snapshot.capacity_target))
        self.account_integration_var.set(snapshot.integration_error)

        for item in self.accounts_tree.get_children():
            self.accounts_tree.delete(item)
        for account in snapshot.accounts:
            self.accounts_tree.insert(
                "",
                "end",
                iid=account.backend_id,
                values=(
                    account.backend_id,
                    account.label,
                    account.pool,
                    "yes" if account.manual_hold else "no",
                    account.status,
                    account.fail_count,
                    account.success_count,
                    account.last_success,
                    account.last_error,
                    account.cooldown_until,
                    account.notes,
                ),
            )

    def _apply_refresh_results(
        self,
        runtime_snapshot: RuntimeSnapshot,
        account_snapshot: AccountPoolSnapshot,
        *,
        banner: str | None = None,
    ) -> None:
        self._apply_runtime_snapshot(runtime_snapshot)
        self._apply_account_snapshot(account_snapshot)
        self.banner_var.set(banner or runtime_snapshot.human_message)
        self.set_busy(False)

    def run_mode_action(self, prompt: str, command: tuple[str, ...]) -> None:
        if self._busy:
            return
        if not messagebox.askyesno("Confirm action", prompt, parent=self.root):
            return
        self.set_busy(True)
        self.banner_var.set("Running operator action...")
        threading.Thread(target=self._action_worker, args=(command,), daemon=True).start()

    def run_sync_action(self) -> None:
        if self._busy:
            return
        if not messagebox.askyesno(
            "Confirm action",
            "Run managed sync and refresh runtime truth?",
            parent=self.root,
        ):
            return
        self.set_busy(True)
        self.banner_var.set("Running operator action...")
        threading.Thread(target=self._sync_worker, daemon=True).start()

    def _selected_account_id(self) -> str | None:
        selection = self.accounts_tree.selection()
        if not selection:
            return None
        return str(selection[0])

    def run_validate_action(self) -> None:
        self._run_account_check_action("Validate")

    def run_recheck_action(self) -> None:
        self._run_account_check_action("Recheck")

    def _run_account_check_action(self, label: str) -> None:
        if self._busy:
            return
        backend_id = self._selected_account_id()
        if backend_id is None:
            messagebox.showinfo("Select account", "Select an account first.", parent=self.root)
            return
        self.set_busy(True)
        self.banner_var.set(f"Running {label.lower()}...")
        threading.Thread(
            target=self._account_check_worker,
            args=(backend_id,),
            daemon=True,
        ).start()

    def _action_worker(self, command: tuple[str, ...]) -> None:
        try:
            action_payload, runtime_snapshot = run_mode_control_and_refresh(self.runner, command)
            account_snapshot = load_account_pool_snapshot(self.runner)
            banner = str(action_payload["human_message"])
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_refresh_results(
                runtime_snapshot,
                account_snapshot,
                banner=banner,
            ),
        )

    def _sync_worker(self) -> None:
        try:
            action_payload, runtime_snapshot, account_snapshot = run_sync_and_refresh(
                self.runner
            )
            banner = str(action_payload["human_message"])
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_refresh_results(
                runtime_snapshot,
                account_snapshot,
                banner=banner,
            ),
        )

    def _account_check_worker(self, backend_id: str) -> None:
        try:
            action_payload, account_snapshot = run_account_validate_and_refresh(
                self.runner, backend_id
            )
            banner = str(action_payload["human_message"])
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        def apply() -> None:
            self._apply_account_snapshot(account_snapshot)
            self.banner_var.set(banner)
            self.set_busy(False)

        self.root.after(0, apply)


def main() -> int:
    root = Tk()
    runner = JsonCommandRunner()
    MinimalCompanionShell(root, runner)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

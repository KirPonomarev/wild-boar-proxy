from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wild_boar_proxy.desktop_ui.overview_bridge import (
    ALLOWED_OPERATION_IDS,
    FORBIDDEN_REQUEST_FIELDS,
    SOURCE_ID,
    main,
    run_bridge_request,
)


class DesktopUiOverviewBridgeTests(unittest.TestCase):
    def test_refresh_operation_writes_fixed_snapshot(self) -> None:
        calls: list[Path] = []

        def refresh_writer(snapshot_path: Path):
            calls.append(snapshot_path)
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text("{}", encoding="utf-8")
            return {"status": "ok"}

        with TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / "overview_live_snapshot.json"
            result = run_bridge_request(
                {"operation_id": "refresh_overview"},
                snapshot_path=snapshot,
                refresh_writer=refresh_writer,
            )

        self.assertEqual(result["source"], SOURCE_ID)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertTrue(result["snapshot_written"])
        self.assertEqual(calls, [snapshot])

    def test_action_operation_calls_action_runner_with_fixed_snapshot(self) -> None:
        calls = []

        def action_runner(action_id: str, **kwargs):
            calls.append((action_id, kwargs))
            return {
                "status": "ok",
                "machine_error_code": "OK",
                "human_message": "action ok",
                "snapshot_written": True,
                "next_action": "none",
                "operator_action": "none",
            }

        with TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / "overview_live_snapshot.json"
            result = run_bridge_request(
                {"operation_id": "run_overview_action", "action_id": "run_smoke", "confirmed": True},
                snapshot_path=snapshot,
                action_runner=action_runner,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["operation_id"], "run_overview_action")
        self.assertEqual(result["action_result"]["machine_error_code"], "OK")
        self.assertEqual(calls[0][0], "run_smoke")
        self.assertIs(calls[0][1]["confirmed"], True)
        self.assertEqual(calls[0][1]["snapshot_path"], snapshot)

    def test_unknown_operation_is_strict_json_error(self) -> None:
        result = run_bridge_request({"operation_id": "delete_everything"})

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["machine_error_code"], "BRIDGE_OPERATION_FORBIDDEN")
        self.assertFalse(result["snapshot_written"])

    def test_forbidden_request_fields_are_rejected_before_operation(self) -> None:
        for field in FORBIDDEN_REQUEST_FIELDS:
            with self.subTest(field=field):
                result = run_bridge_request({"operation_id": "refresh_overview", field: "value"})
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["machine_error_code"], "BRIDGE_REQUEST_FORBIDDEN_FIELD")
                self.assertFalse(result["snapshot_written"])

    def test_missing_action_id_is_blocked(self) -> None:
        result = run_bridge_request({"operation_id": "run_overview_action", "confirmed": True})

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["machine_error_code"], "BRIDGE_ACTION_ID_REQUIRED")

    def test_request_cannot_choose_snapshot_path(self) -> None:
        result = run_bridge_request({
            "operation_id": "refresh_overview",
            "snapshot_path": "/tmp/attacker.json",
        })

        self.assertEqual(result["machine_error_code"], "BRIDGE_REQUEST_FORBIDDEN_FIELD")
        self.assertEqual(result["snapshot_path"], "")

    def test_action_error_stays_bridge_error(self) -> None:
        def action_runner(action_id: str, **kwargs):
            return {
                "status": "error",
                "machine_error_code": "CONFIRMATION_REQUIRED",
                "human_message": "confirmation required",
                "snapshot_written": False,
                "next_action": "user_action",
                "operator_action": "user_action",
            }

        result = run_bridge_request(
            {"operation_id": "run_overview_action", "action_id": "switch_stable"},
            action_runner=action_runner,
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["machine_error_code"], "CONFIRMATION_REQUIRED")
        self.assertEqual(result["action_result"]["status"], "error")

    def test_operation_allowlist_is_exact(self) -> None:
        self.assertEqual(ALLOWED_OPERATION_IDS, {"refresh_overview", "run_overview_action"})

    def test_cli_emits_json_for_forbidden_field(self) -> None:
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "bridge.json"
            code = main([
                "--request-json",
                json.dumps({"operation_id": "refresh_overview", "command": "status --json"}),
                "--output",
                str(output),
            ])
            packet = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 1)
        self.assertEqual(packet["machine_error_code"], "BRIDGE_REQUEST_FORBIDDEN_FIELD")


if __name__ == "__main__":
    unittest.main()

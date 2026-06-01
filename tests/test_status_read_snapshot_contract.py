# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import runtime as runtime_mod


class StatusReadSnapshotContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.profile_dir = self.root / "profile"
        self.managed_dir = self.root / "managed"
        self.stable_dir = self.root / "stable"
        self.auth_dir = self.root / "auth"
        self.bin_dir = self.managed_dir / "bin"
        for path in (
            self.profile_dir,
            self.managed_dir,
            self.stable_dir,
            self.auth_dir,
            self.bin_dir,
        ):
            path.mkdir(parents=True)

        (self.profile_dir / "config.toml").write_text(
            'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:8318/v1"\n',
            encoding="utf-8",
        )
        (self.profile_dir / "runtime-mode.txt").write_text("stable\n", encoding="utf-8")
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n",
            encoding="utf-8",
        )
        backend_auth = self.auth_dir / "backend-a.json"
        backend_auth.write_text("{}\n", encoding="utf-8")
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "version": 2,
                    "updated_at": "2026-06-01T00:00:00+00:00",
                    "stable_default_backend_id": "default-backend",
                    "pool_policy": {
                        "active_min": 1,
                        "active_target": 2,
                        "reserve_target": 0,
                    },
                    "backends": [
                        {
                            "id": "backend-a",
                            "label": "Backend A",
                            "pool": "active",
                            "status": "healthy",
                            "manual_hold": False,
                            "auth_ref": str(backend_auth),
                            "fail_count": 0,
                            "success_count": 1,
                        }
                    ],
                },
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "version": 2,
                    "status": "healthy",
                    "effective_mode": "stable",
                    "selected_backend_ids": ["backend-a"],
                    "managed_port": 9999,
                    "last_error": "",
                },
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.managed_dir / "managed-config.yaml").write_text(
            "host: 127.0.0.1\nport: 9999\n",
            encoding="utf-8",
        )
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\nport: 8318\n",
            encoding="utf-8",
        )
        self.launcher_script = self.managed_dir / "stable-runtime-launcher.sh"
        self.launcher_script.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        self.launcher_script.chmod(0o755)
        self.paths = runtime_mod.RuntimePaths(
            profile_dir=self.profile_dir,
            managed_dir=self.managed_dir,
            stable_config=self.stable_dir / "config.yaml",
            auth_file=self.profile_dir / "auth.json",
            config_toml=self.profile_dir / "config.toml",
            runtime_mode_file=self.profile_dir / "runtime-mode.txt",
            runtime_effective_mode_file=self.profile_dir / "runtime-effective-mode.txt",
            registry_file=self.managed_dir / "backend-registry.json",
            state_file=self.managed_dir / "supervisor-state.json",
            managed_config_file=self.managed_dir / "managed-config.yaml",
            launcher_script=self.launcher_script,
            sync_script=self.managed_dir / "supervisor-sync.sh",
            accounts_bin=self.bin_dir / "codex-accounts",
            onboard_bin=self.bin_dir / "codex-account-onboard",
            lock_file=self.managed_dir / "wild-boar-proxy.lock",
            launcher_lock_file=self.managed_dir / "stable-runtime-launch.lock",
            repair_target_inventory_dir=self.managed_dir / "stable-repair-target",
            repair_target_reference_file=self.managed_dir / "approved-repair-target.json",
            target_switch_transaction_file=(
                self.managed_dir / "target-switch-transaction.json"
            ),
            stable_runtime_generated_config_file=(
                self.managed_dir / "stable-runtime-config.generated.yaml"
            ),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_status_snapshot_does_not_delegate_to_healthcheck_or_recovery(self) -> None:
        with (
            mock.patch.object(
                runtime_mod,
                "run_healthcheck",
                side_effect=AssertionError("status must not call healthcheck"),
            ),
            mock.patch.object(
                runtime_mod,
                "run_stable_runtime_launcher_attempt",
                side_effect=AssertionError("status must not launch recovery"),
            ),
            mock.patch.object(
                runtime_mod,
                "run_current_proxy_owner_path_activation",
                side_effect=AssertionError("status must not activate owner path"),
            ),
        ):
            payload = runtime_mod.summarize_status(self.paths)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["effect"], "read")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["liveness"], "unknown")
        self.assertEqual(
            payload["attestation_summary"]["machine_error_code"],
            "LIVE_ATTESTATION_NOT_RUN_BY_STATUS",
        )


if __name__ == "__main__":
    unittest.main()

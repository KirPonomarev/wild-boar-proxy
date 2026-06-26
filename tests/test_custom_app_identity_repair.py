# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import custom_app_identity_repair as repair
from wild_boar_proxy.core import packets
from wild_boar_proxy.runtime import RuntimePaths


def _paths(root: Path) -> RuntimePaths:
    profile = root / "profile"
    managed = profile / "managed"
    return RuntimePaths(
        profile_dir=profile,
        managed_dir=managed,
        stable_config=root / "stable-config.yaml",
        auth_file=profile / "auth.json",
        config_toml=profile / "config.toml",
        runtime_mode_file=profile / "runtime-mode.txt",
        runtime_effective_mode_file=profile / "runtime-effective-mode.txt",
        registry_file=managed / "backend-registry.json",
        state_file=managed / "supervisor-state.json",
        managed_config_file=managed / "managed-config.yaml",
        launcher_script=profile / "codex-custom-launch.sh",
        sync_script=managed / "supervisor-sync.sh",
        accounts_bin=root / "bin" / "codex-accounts",
        onboard_bin=root / "bin" / "codex-account-onboard",
        lock_file=managed / "wild-boar-proxy.lock",
        launcher_lock_file=managed / "stable-runtime-launch.lock",
        repair_target_inventory_dir=managed / "stable-repair-target",
        repair_target_reference_file=managed / "approved-repair-target.json",
        target_switch_transaction_file=managed / "target-switch-transaction.json",
        stable_runtime_generated_config_file=(
            managed / "stable-runtime-config.generated.yaml"
        ),
    )


def _write_app(root: Path, name: str, *, bundle_id: str) -> Path:
    app = root / name
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "Resources").mkdir(parents=True)
    (app / "Contents" / "MacOS" / "Codex").write_bytes(b"same-binary")
    (app / "Contents" / "Resources" / "app.asar").write_bytes(b"same-asar")
    with (app / "Contents" / "Info.plist").open("wb") as handle:
        plistlib.dump(
            {
                "CFBundleIdentifier": bundle_id,
                "CFBundleName": "Codex",
                "CFBundleDisplayName": "Codex",
                "CFBundleExecutable": "Codex",
            },
            handle,
        )
    return app


def _read_plist(app: Path) -> dict[str, object]:
    with (app / "Contents" / "Info.plist").open("rb") as handle:
        return plistlib.load(handle)


def _fixture(root: Path) -> tuple[RuntimePaths, Path, Path]:
    paths = _paths(root)
    paths.profile_dir.mkdir(parents=True)
    paths.managed_dir.mkdir(parents=True)
    stock = _write_app(root, "Codex.app", bundle_id="com.openai.codex")
    custom = _write_app(root, "Codex WBP Clean.app", bundle_id="com.openai.codex")
    return paths, stock, custom


class CustomAppIdentityRepairTests(unittest.TestCase):
    def test_dry_run_reports_needed_repair_without_mutating_custom_app(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            before = (custom / "Contents" / "Info.plist").read_bytes()

            packet = repair.build_custom_app_identity_repair_packet(
                paths=paths,
                apply=False,
                stock_app_path=str(stock),
                custom_app_path=str(custom),
            )

            after = (custom / "Contents" / "Info.plist").read_bytes()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["machine_error_code"],
            repair.CUSTOM_APP_IDENTITY_READY,
        )
        self.assertTrue(packet["dry_run"])
        self.assertTrue(packet["repair_needed"])
        self.assertTrue(packet["repair_ready"])
        self.assertFalse(packet["mutation_attempted"])
        self.assertFalse(packet["identity_repaired"])
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(before, after)
        self.assertFalse(packet["stock_app_mutated"])
        self.assertFalse(packet["app_asar_mutated"])
        self.assertFalse(packet["app_binary_mutated"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["dispatch_attempted"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_apply_repairs_only_custom_plist_and_writes_profile_owned_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            stock_before = _read_plist(stock)
            with (
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_verify",
                    side_effect=[(False, 1, "invalid"), (True, 0, "valid")],
                ) as verify,
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_ad_hoc",
                    return_value=(True, 0, "signed"),
                ) as sign,
            ):
                packet = repair.build_custom_app_identity_repair_packet(
                    paths=paths,
                    apply=True,
                    stock_app_path=str(stock),
                    custom_app_path=str(custom),
                )
            stock_after = _read_plist(stock)
            custom_after = _read_plist(custom)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["identity_repaired"])
        self.assertTrue(packet["custom_app_identity_distinct_after"])
        self.assertEqual(
            custom_after["CFBundleIdentifier"],
            repair.DESIRED_CUSTOM_BUNDLE_ID,
        )
        self.assertEqual(custom_after["CFBundleName"], repair.DESIRED_CUSTOM_BUNDLE_NAME)
        self.assertEqual(
            custom_after["CFBundleDisplayName"],
            repair.DESIRED_CUSTOM_BUNDLE_NAME,
        )
        self.assertEqual(custom_after["CFBundleExecutable"], "Codex")
        self.assertEqual(stock_before, stock_after)
        self.assertTrue(packet["backup_written"])
        self.assertTrue(packet["backup_under_profile"])
        self.assertTrue(packet["changed_files_path_recorded"])
        self.assertTrue(packet["binary_hash_matches_stock_after"])
        self.assertTrue(packet["asar_hash_matches_stock_after"])
        self.assertTrue(packet["codesign_repair_needed"])
        self.assertTrue(packet["codesign_attempted"])
        self.assertTrue(packet["codesign_ok"])
        self.assertFalse(packet["codesign_output_recorded"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["dispatch_attempted"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(sign.call_count, 1)
        self.assertTrue(any("Info.plist" in item for item in packet["changed_files"]))
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_apply_repair_does_not_use_legacy_fixed_temp_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            legacy_tmp = custom / "Contents" / ".Info.plist.wbp-tmp"
            legacy_tmp.mkdir()
            with (
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_verify",
                    side_effect=[(False, 1, "invalid"), (True, 0, "valid")],
                ),
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_ad_hoc",
                    return_value=(True, 0, "signed"),
                ),
            ):
                packet = repair.build_custom_app_identity_repair_packet(
                    paths=paths,
                    apply=True,
                    stock_app_path=str(stock),
                    custom_app_path=str(custom),
                )
            custom_after = _read_plist(custom)
            legacy_tmp_still_dir = legacy_tmp.is_dir()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], repair.CUSTOM_APP_IDENTITY_OK)
        self.assertTrue(legacy_tmp_still_dir)
        self.assertEqual(
            custom_after["CFBundleIdentifier"],
            repair.DESIRED_CUSTOM_BUNDLE_ID,
        )
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_backup_dir_outside_profile_blocks_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            outside_backup = Path(tmp_dir) / "outside-backups"

            packet = repair.build_custom_app_identity_repair_packet(
                paths=paths,
                apply=True,
                stock_app_path=str(stock),
                custom_app_path=str(custom),
                backup_dir=str(outside_backup),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            repair.CUSTOM_APP_IDENTITY_NOT_ADMITTED,
        )
        self.assertFalse(packet["backup_under_profile"])
        self.assertFalse(packet["mutation_attempted"])
        self.assertFalse(packet["backup_written"])
        self.assertIn("backup_dir_not_profile_owned", packet["blocking_reasons"])
        self.assertEqual(packet["changed_files"], [])
        self.assertFalse(packet["changed_files_path_recorded"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_signed_wbp_identity_binary_signature_mismatch_needs_no_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            custom_plist = _read_plist(custom)
            custom_plist["CFBundleIdentifier"] = repair.DESIRED_CUSTOM_BUNDLE_ID
            custom_plist["CFBundleName"] = repair.DESIRED_CUSTOM_BUNDLE_NAME
            custom_plist["CFBundleDisplayName"] = repair.DESIRED_CUSTOM_BUNDLE_NAME
            with (custom / "Contents" / "Info.plist").open("wb") as handle:
                plistlib.dump(custom_plist, handle)
            (custom / "Contents" / "MacOS" / "Codex").write_bytes(
                b"same app after ad-hoc signature mutation"
            )

            with mock.patch(
                "wild_boar_proxy.custom_app_identity_repair._codesign_verify",
                return_value=(True, 0, "valid"),
            ):
                packet = repair.build_custom_app_identity_repair_packet(
                    paths=paths,
                    apply=False,
                    stock_app_path=str(stock),
                    custom_app_path=str(custom),
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["machine_error_code"],
            repair.CUSTOM_APP_IDENTITY_NOT_NEEDED,
        )
        self.assertFalse(packet["binary_hash_matches_stock"])
        self.assertTrue(
            packet["binary_hash_mismatch_allowed_as_wbp_signature_mutation"]
        )
        self.assertTrue(packet["asar_hash_matches_stock"])
        self.assertTrue(packet["custom_codesign_valid_before"])
        self.assertFalse(packet["repair_needed"])
        self.assertFalse(packet["mutation_attempted"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_custom_binary_hash_mismatch_blocks_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            (custom / "Contents" / "MacOS" / "Codex").write_bytes(b"different")

            packet = repair.build_custom_app_identity_repair_packet(
                paths=paths,
                apply=True,
                stock_app_path=str(stock),
                custom_app_path=str(custom),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            repair.CUSTOM_APP_IDENTITY_NOT_ADMITTED,
        )
        self.assertFalse(packet["binary_hash_matches_stock"])
        self.assertIn("custom_binary_hash_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["mutation_attempted"])
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_codesign_failure_restores_original_plist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            original = (custom / "Contents" / "Info.plist").read_bytes()
            with (
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_verify",
                    side_effect=[(False, 1, "invalid"), (False, 1, "invalid")],
                ),
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_ad_hoc",
                    return_value=(False, 1, "failed signing /private/path"),
                ),
            ):
                packet = repair.build_custom_app_identity_repair_packet(
                    paths=paths,
                    apply=True,
                    stock_app_path=str(stock),
                    custom_app_path=str(custom),
                )
            restored = (custom / "Contents" / "Info.plist").read_bytes()

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            repair.CUSTOM_APP_IDENTITY_CODESIGN_FAILED,
        )
        self.assertTrue(packet["rollback_restored"])
        self.assertFalse(packet["identity_repaired"])
        self.assertEqual(original, restored)
        self.assertFalse(packet["codesign_output_recorded"])
        self.assertIn("codesign_failed", packet["blocking_reasons"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_plist_write_failure_cleans_temp_files_and_preserves_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            custom_plist_path = custom / "Contents" / "Info.plist"
            original = custom_plist_path.read_bytes()
            original_replace = repair.os.replace
            failed_custom_publish = False

            def fail_first_custom_publish(src: Path | str, dst: Path | str) -> None:
                nonlocal failed_custom_publish
                if Path(dst) == custom_plist_path and not failed_custom_publish:
                    failed_custom_publish = True
                    raise OSError("publish failed")
                original_replace(src, dst)

            with (
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_verify",
                    side_effect=[(False, 1, "invalid"), (False, 1, "invalid")],
                ),
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair.os.replace",
                    side_effect=fail_first_custom_publish,
                ),
            ):
                packet = repair.build_custom_app_identity_repair_packet(
                    paths=paths,
                    apply=True,
                    stock_app_path=str(stock),
                    custom_app_path=str(custom),
                )
            restored = custom_plist_path.read_bytes()
            residue = sorted(
                path.name
                for path in custom_plist_path.parent.glob(".wbp-tmp-*.Info.plist")
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            repair.CUSTOM_APP_IDENTITY_NOT_ADMITTED,
        )
        self.assertTrue(packet["mutation_attempted"])
        self.assertFalse(packet["plist_written"])
        self.assertFalse(packet["codesign_attempted"])
        self.assertTrue(packet["plist_rollback_restored"])
        self.assertTrue(packet["rollback_restored"])
        self.assertEqual(original, restored)
        self.assertEqual(residue, [])
        self.assertIn("plist_write_failed", packet["blocking_reasons"])
        self.assertNotIn(str(custom_plist_path), packet["changed_files"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_backup_write_failure_returns_packet_without_raw_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            custom_plist_path = custom / "Contents" / "Info.plist"
            backup_root = repair._default_backup_dir(paths)
            original = custom_plist_path.read_bytes()
            original_atomic_write = repair._atomic_write_bytes

            def fail_backup(path: Path, data: bytes) -> None:
                if Path(path).suffix == ".bak":
                    raise OSError("backup failed")
                original_atomic_write(path, data)

            with (
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_verify",
                    side_effect=[(False, 1, "invalid"), (False, 1, "invalid")],
                ),
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._atomic_write_bytes",
                    side_effect=fail_backup,
                ),
            ):
                packet = repair.build_custom_app_identity_repair_packet(
                    paths=paths,
                    apply=True,
                    stock_app_path=str(stock),
                    custom_app_path=str(custom),
                )
            restored = custom_plist_path.read_bytes()
            residue = sorted(path.name for path in backup_root.glob(".wbp-tmp-*"))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            repair.CUSTOM_APP_IDENTITY_NOT_ADMITTED,
        )
        self.assertTrue(packet["mutation_attempted"])
        self.assertFalse(packet["backup_written"])
        self.assertFalse(packet["plist_written"])
        self.assertFalse(packet["codesign_attempted"])
        self.assertFalse(packet["plist_rollback_restored"])
        self.assertFalse(packet["rollback_restored"])
        self.assertEqual(original, restored)
        self.assertEqual(residue, [])
        self.assertIn("backup_write_failed", packet["blocking_reasons"])
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_plist_write_failure_with_restore_failure_returns_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            custom_plist_path = custom / "Contents" / "Info.plist"
            original = custom_plist_path.read_bytes()
            original_atomic_write = repair._atomic_write_bytes

            def fail_restore(path: Path, data: bytes) -> None:
                if Path(path) == custom_plist_path and data == original:
                    raise OSError("restore failed")
                original_atomic_write(path, data)

            with (
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_verify",
                    side_effect=[(False, 1, "invalid"), (False, 1, "invalid")],
                ),
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._write_plist_atomic",
                    side_effect=OSError("publish failed"),
                ),
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._atomic_write_bytes",
                    side_effect=fail_restore,
                ),
            ):
                packet = repair.build_custom_app_identity_repair_packet(
                    paths=paths,
                    apply=True,
                    stock_app_path=str(stock),
                    custom_app_path=str(custom),
                )
            restored = custom_plist_path.read_bytes()

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            repair.CUSTOM_APP_IDENTITY_NOT_ADMITTED,
        )
        self.assertTrue(packet["mutation_attempted"])
        self.assertTrue(packet["backup_written"])
        self.assertFalse(packet["plist_written"])
        self.assertFalse(packet["codesign_attempted"])
        self.assertFalse(packet["plist_rollback_restored"])
        self.assertFalse(packet["rollback_restored"])
        self.assertEqual(original, restored)
        self.assertIn("plist_write_failed", packet["blocking_reasons"])
        self.assertIn("plist_restore_failed", packet["blocking_reasons"])
        self.assertNotIn(str(custom_plist_path), packet["changed_files"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_plist_fsync_failure_cleans_temp_files_and_preserves_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            custom_plist_path = custom / "Contents" / "Info.plist"
            original = custom_plist_path.read_bytes()
            original_fsync = repair.os.fsync
            fsync_call_count = 0

            def fail_forward_fsync(fd: int) -> None:
                nonlocal fsync_call_count
                fsync_call_count += 1
                if fsync_call_count == 3:
                    raise OSError("flush failed")
                original_fsync(fd)

            with (
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_verify",
                    side_effect=[(False, 1, "invalid"), (False, 1, "invalid")],
                ),
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair.os.fsync",
                    side_effect=fail_forward_fsync,
                ),
            ):
                packet = repair.build_custom_app_identity_repair_packet(
                    paths=paths,
                    apply=True,
                    stock_app_path=str(stock),
                    custom_app_path=str(custom),
                )
            restored = custom_plist_path.read_bytes()
            residue = sorted(
                path.name
                for path in custom_plist_path.parent.glob(".wbp-tmp-*.Info.plist")
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            repair.CUSTOM_APP_IDENTITY_NOT_ADMITTED,
        )
        self.assertTrue(packet["mutation_attempted"])
        self.assertFalse(packet["plist_written"])
        self.assertFalse(packet["codesign_attempted"])
        self.assertTrue(packet["plist_rollback_restored"])
        self.assertTrue(packet["rollback_restored"])
        self.assertEqual(original, restored)
        self.assertEqual(residue, [])
        self.assertIn("plist_write_failed", packet["blocking_reasons"])
        self.assertNotIn(str(custom_plist_path), packet["changed_files"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_codesign_failure_with_restore_failure_returns_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            custom_plist_path = custom / "Contents" / "Info.plist"
            original = custom_plist_path.read_bytes()
            original_atomic_write = repair._atomic_write_bytes

            def fail_restore(path: Path, data: bytes) -> None:
                if Path(path) == custom_plist_path and data == original:
                    raise OSError("restore failed")
                original_atomic_write(path, data)

            with (
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_verify",
                    side_effect=[(False, 1, "invalid"), (False, 1, "invalid")],
                ),
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_ad_hoc",
                    return_value=(False, 1, "failed signing"),
                ),
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._atomic_write_bytes",
                    side_effect=fail_restore,
                ),
            ):
                packet = repair.build_custom_app_identity_repair_packet(
                    paths=paths,
                    apply=True,
                    stock_app_path=str(stock),
                    custom_app_path=str(custom),
                )
            custom_after = _read_plist(custom)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            repair.CUSTOM_APP_IDENTITY_CODESIGN_FAILED,
        )
        self.assertTrue(packet["mutation_attempted"])
        self.assertTrue(packet["backup_written"])
        self.assertTrue(packet["plist_written"])
        self.assertTrue(packet["codesign_attempted"])
        self.assertFalse(packet["plist_rollback_restored"])
        self.assertFalse(packet["rollback_restored"])
        self.assertEqual(
            custom_after["CFBundleIdentifier"],
            repair.DESIRED_CUSTOM_BUNDLE_ID,
        )
        self.assertIn("codesign_failed", packet["blocking_reasons"])
        self.assertIn("plist_restore_failed", packet["blocking_reasons"])
        self.assertIn(str(custom_plist_path), packet["changed_files"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_codesign_failure_side_effects_do_not_claim_full_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            original_plist = (custom / "Contents" / "Info.plist").read_bytes()
            custom_bin = custom / "Contents" / "MacOS" / "Codex"

            def mutate_and_fail(_app_path: Path) -> tuple[bool, int, str]:
                custom_bin.write_bytes(b"mutated by failed signing")
                return False, 1, "failed signing"

            with (
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_verify",
                    side_effect=[(False, 1, "invalid"), (False, 1, "invalid")],
                ),
                mock.patch(
                    "wild_boar_proxy.custom_app_identity_repair._codesign_ad_hoc",
                    side_effect=mutate_and_fail,
                ),
            ):
                packet = repair.build_custom_app_identity_repair_packet(
                    paths=paths,
                    apply=True,
                    stock_app_path=str(stock),
                    custom_app_path=str(custom),
                )

            restored_plist = (custom / "Contents" / "Info.plist").read_bytes()

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            repair.CUSTOM_APP_IDENTITY_CODESIGN_FAILED,
        )
        self.assertTrue(packet["plist_rollback_restored"])
        self.assertFalse(packet["rollback_restored"])
        self.assertTrue(packet["codesign_failure_side_effects_detected"])
        self.assertFalse(packet["binary_hash_matches_stock_after"])
        self.assertIn("codesign_failed", packet["blocking_reasons"])
        self.assertIn(
            "codesign_side_effects_after_failure",
            packet["blocking_reasons"],
        )
        self.assertEqual(original_plist, restored_plist)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_apply_as_repair_and_dry_run_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        dry_run = parser.parse_args(
            ["launch", "custom-app-identity-repair", "--dry-run", "--json"]
        )
        apply = parser.parse_args(
            ["launch", "custom-app-identity-repair", "--apply", "--json"]
        )

        self.assertEqual(cli_mod.command_effect_from_args(dry_run), "probe")
        self.assertEqual(cli_mod.command_effect_from_args(apply), "repair")

    def test_cli_dispatch_emits_identity_repair_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths, stock, custom = _fixture(Path(tmp_dir))
            stdout = io.StringIO()
            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "WBP_PROFILE_DIR": str(paths.profile_dir),
                        "WBP_MANAGED_DIR": str(paths.managed_dir),
                        "WBP_CONFIG_TOML": str(paths.config_toml),
                        "WBP_RUNTIME_MODE_FILE": str(paths.runtime_mode_file),
                        "WBP_RUNTIME_EFFECTIVE_MODE_FILE": str(
                            paths.runtime_effective_mode_file
                        ),
                        "WBP_REGISTRY_FILE": str(paths.registry_file),
                        "WBP_STATE_FILE": str(paths.state_file),
                        "WBP_MANAGED_CONFIG_FILE": str(paths.managed_config_file),
                    },
                    clear=False,
                ),
                mock.patch("sys.stdout", stdout),
            ):
                exit_code = cli_mod.main(
                    [
                        "launch",
                        "custom-app-identity-repair",
                        "--dry-run",
                        "--stock-app-path",
                        str(stock),
                        "--custom-app-path",
                        str(custom),
                        "--json",
                    ]
                )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertEqual(
            payload["packet_kind"],
            repair.CUSTOM_APP_IDENTITY_REPAIR_PACKET_KIND,
        )
        self.assertFalse(payload["api_lane_called"])
        self.assertFalse(payload["product_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()

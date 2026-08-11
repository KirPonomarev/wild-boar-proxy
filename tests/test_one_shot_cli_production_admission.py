# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""R60: exact production admission and pre-spawn invalidation proofs."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from wild_boar_proxy import one_shot_cli_runtime as osr


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _install_test_sandbox_transport(
    test_case: unittest.TestCase, root: Path
) -> None:
    """Provide deterministic sandbox transport for platform-neutral logic tests.

    These tests exercise admission, identity, redaction, and pre-spawn ordering;
    the real macOS seatbelt boundary is covered separately by
    test_server_owned_sandbox.py and test_r52_sandbox_adversarial.py.  Production
    still fails closed when sandbox-exec is absent.
    """
    shim = root / "sandbox-exec-test-shim"
    shim.write_text(
        "#!/bin/sh\n"
        "[ \"$1\" = \"-f\" ] || exit 64\n"
        "[ \"$#\" -ge 3 ] || exit 64\n"
        "[ -r \"$2\" ] || exit 65\n"
        "shift 2\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    shim.chmod(0o700)
    real_which = osr.shutil.which

    def test_which(name: str, *args: object, **kwargs: object) -> str | None:
        if name == "sandbox-exec":
            return str(shim)
        return real_which(name, *args, **kwargs)

    patcher = mock.patch.object(osr.shutil, "which", side_effect=test_which)
    patcher.start()
    test_case.addCleanup(patcher.stop)


def _operational_entry(**updates: object) -> osr.OneShotToolManifestEntry:
    entry = osr.OneShotToolManifestEntry(
        tool_id="system-echo",
        provider_id="system-echo",
        binary_name="/bin/echo",
        display_name="System Echo",
        version_args=("--version",),
        allowed_argv_schema=("literal:wbp-production-smoke",),
        operational_args=("wbp-production-smoke",),
        allowed_environment_keys=(),
        auth_strategy="none",
        network_policy="denied",
        provider_adapter_admitted=True,
    )
    return replace(entry, **updates)


class ProductionAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        _install_test_sandbox_transport(self, self.root)
        self.homes_root = self.root / "homes"
        self.admission_root = self.root / "admission"
        self.entry = _operational_entry()
        self.facade = osr.ProductionOneShotFacade(
            homes_root=self.homes_root,
            admission_root=self.admission_root,
            manifest=(self.entry,),
        )

    def _admit(self) -> dict[str, object]:
        probe = self.facade.probe(self.entry.tool_id)
        self.assertEqual(probe["status"], "ok")
        packet = self.facade.admit(
            self.entry.tool_id,
            expected_binary_sha256=str(probe["binary_sha256"]),
        )
        self.assertEqual(packet["status"], "ok")
        return packet

    def _load_store(self) -> dict[str, object]:
        return json.loads(
            (self.admission_root / osr.ADMISSION_FILENAME).read_text(encoding="utf-8")
        )

    def _write_store(self, payload: dict[str, object], *, canonical: bool = True) -> None:
        path = self.admission_root / osr.ADMISSION_FILENAME
        data = _canonical(payload) if canonical else json.dumps(payload, indent=2).encode()
        path.write_bytes(data)
        path.chmod(0o600)

    def test_server_manifest_declares_complete_pending_provider_contracts(self) -> None:
        self.assertEqual(
            {entry.provider_id for entry in osr.SERVER_OWNED_TOOL_MANIFEST},
            {"qwen", "kimi"},
        )
        digests = set()
        for entry in osr.SERVER_OWNED_TOOL_MANIFEST:
            declaration = entry.to_dict()
            for field in (
                "provider_id",
                "version_args",
                "allowed_argv_schema",
                "allowed_environment_keys",
                "cwd_policy",
                "output_parser",
                "timeout_seconds",
                "output_cap_bytes",
                "process_group_policy",
                "sandbox_policy",
                "auth_strategy",
                "session_policy",
                "network_policy",
                "provider_adapter_admitted",
            ):
                self.assertIn(field, declaration)
            self.assertFalse(entry.provider_adapter_admitted)
            self.assertTrue(entry.network_policy.startswith("denied_pending_"))
            digests.add(osr.manifest_entry_digest(entry))
        self.assertEqual(len(digests), 2)

    def test_receipt_is_read_only_and_reports_boundary_not_operational(self) -> None:
        receipt = self.facade.receipt()
        self.assertEqual(receipt["status"], "ok")
        self.assertFalse(receipt["cli_disabled"])
        self.assertFalse(receipt["cli_operational"])
        self.assertTrue(receipt["production_admission_supported"])
        self.assertEqual(
            receipt["admission_store_status"], osr.CLI_BINARY_ADMISSION_MISSING
        )
        self.assertEqual(receipt["changed_files"], [])
        self.assertFalse(self.admission_root.exists())
        self.assertFalse(self.homes_root.exists())

    def test_missing_admission_blocks_before_home_or_spawn(self) -> None:
        with mock.patch.object(osr.subprocess, "Popen") as popen:
            session = self.facade.session(self.entry.provider_id)
            run = self.facade.run(self.entry.tool_id)
        for packet in (session, run):
            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"], osr.CLI_BINARY_ADMISSION_MISSING
            )
            self.assertEqual(packet["changed_files"], [])
        popen.assert_not_called()
        self.assertFalse(self.homes_root.exists())
        self.assertFalse(self.admission_root.exists())

    def test_pending_provider_adapter_is_distinct_and_precedes_binary_probe(self) -> None:
        facade = osr.ProductionOneShotFacade(
            homes_root=self.homes_root,
            admission_root=self.admission_root,
        )
        with mock.patch.object(osr.subprocess, "Popen") as popen:
            qwen = facade.run("qwen-cli")
            kimi = facade.session("kimi")
        for packet in (qwen, kimi):
            self.assertEqual(
                packet["machine_error_code"],
                osr.CLI_PROVIDER_ADAPTER_NOT_ADMITTED,
            )
            self.assertEqual(packet["blocked_reason"], "provider_adapter_not_admitted")
        popen.assert_not_called()
        self.assertFalse(self.homes_root.exists())

    def test_probe_plus_expected_digest_writes_canonical_locked_store(self) -> None:
        probe = self.facade.probe(self.entry.tool_id)
        self.assertEqual(probe["status"], "ok")
        self.assertFalse(probe["probe_grants_operational_authority"])
        mismatch = self.facade.admit(
            self.entry.tool_id,
            expected_binary_sha256="0" * 64,
        )
        self.assertEqual(
            mismatch["machine_error_code"], osr.CLI_ADMISSION_DIGEST_MISMATCH
        )
        self.assertFalse(self.admission_root.exists())

        admitted = self.facade.admit(
            self.entry.tool_id,
            expected_binary_sha256=str(probe["binary_sha256"]),
        )
        self.assertEqual(admitted["status"], "ok")
        admission_file = self.admission_root / osr.ADMISSION_FILENAME
        lock_file = self.admission_root / osr.ADMISSION_LOCK_FILENAME
        self.assertEqual(self.admission_root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(admission_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(lock_file.stat().st_mode & 0o777, 0o600)
        payload = self._load_store()
        self.assertEqual(admission_file.read_bytes(), _canonical(payload))
        record = payload["records"][self.entry.tool_id]
        self.assertEqual(record["manifest_sha256"], osr.manifest_entry_digest(self.entry))
        self.assertEqual(record["binary_sha256"], probe["binary_sha256"])
        self.assertEqual(record["binary_realpath"], os.path.realpath("/bin/echo"))

    def test_failed_atomic_replace_preserves_previous_canonical_admission(self) -> None:
        admitted = self._admit()
        admission_file = self.admission_root / osr.ADMISSION_FILENAME
        before = admission_file.read_bytes()
        with mock.patch.object(osr.os, "replace", side_effect=OSError("injected")):
            packet = self.facade.admit(
                self.entry.tool_id,
                expected_binary_sha256=str(admitted["binary_sha256"]),
            )
        self.assertEqual(
            packet["machine_error_code"], osr.CLI_BINARY_ADMISSION_INVALID
        )
        self.assertEqual(packet["blocked_reason"], "atomic_write_failed")
        self.assertEqual(admission_file.read_bytes(), before)
        self.assertEqual(list(self.admission_root.glob(".admissions-*")), [])

    def test_admitted_offline_declaration_revalidates_and_runs(self) -> None:
        self._admit()
        packet = self.facade.run(self.entry.tool_id)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["run"]["stdout"], "wbp-production-smoke\n")
        self.assertTrue(packet["production_admission_revalidated"])
        self.assertEqual(packet["manifest_sha256"], osr.manifest_entry_digest(self.entry))
        session = self.facade.session(self.entry.provider_id)
        self.assertEqual(session["status"], "ok")
        self.assertEqual(Path(session["home_path"]).stat().st_mode & 0o777, 0o700)
        self.assertFalse(session["auth_required"])

    def test_manifest_drift_invalidates_existing_admission_before_spawn(self) -> None:
        self._admit()
        drifted = replace(self.entry, output_cap_bytes=self.entry.output_cap_bytes - 1)
        facade = osr.ProductionOneShotFacade(
            homes_root=self.homes_root,
            admission_root=self.admission_root,
            manifest=(drifted,),
        )
        with mock.patch.object(osr.subprocess, "Popen") as popen:
            packet = facade.run(drifted.tool_id)
        self.assertEqual(
            packet["machine_error_code"], osr.CLI_ADMISSION_DIGEST_MISMATCH
        )
        popen.assert_not_called()

    def test_admission_mode_and_schema_drift_fail_closed(self) -> None:
        self._admit()
        admission_file = self.admission_root / osr.ADMISSION_FILENAME
        admission_file.chmod(0o644)
        with mock.patch.object(osr.subprocess, "Popen") as popen:
            mode_packet = self.facade.run(self.entry.tool_id)
        self.assertEqual(
            mode_packet["machine_error_code"], osr.CLI_BINARY_ADMISSION_INVALID
        )
        self.assertEqual(mode_packet["blocked_reason"], "file_mode_or_owner")
        popen.assert_not_called()

        admission_file.chmod(0o600)
        payload = self._load_store()
        self._write_store(payload, canonical=False)
        with mock.patch.object(osr.subprocess, "Popen") as popen:
            schema_packet = self.facade.run(self.entry.tool_id)
        self.assertEqual(
            schema_packet["machine_error_code"], osr.CLI_BINARY_ADMISSION_INVALID
        )
        self.assertEqual(schema_packet["blocked_reason"], "noncanonical_json")
        popen.assert_not_called()

    def test_symlinked_admission_root_is_rejected_without_following_it(self) -> None:
        target = self.root / "redirect-target"
        target.mkdir(mode=0o700)
        self.admission_root.symlink_to(target, target_is_directory=True)
        with mock.patch.object(osr.subprocess, "Popen") as popen:
            packet = self.facade.run(self.entry.tool_id)
        self.assertEqual(
            packet["machine_error_code"], osr.CLI_BINARY_ADMISSION_INVALID
        )
        self.assertEqual(packet["blocked_reason"], "store_mode_or_owner")
        popen.assert_not_called()
        self.assertEqual(list(target.iterdir()), [])

    def test_digest_and_realpath_drift_block_operational_spawn(self) -> None:
        self._admit()
        payload = self._load_store()
        record = payload["records"][self.entry.tool_id]
        record["binary_sha256"] = "0" * 64
        self._write_store(payload)
        with mock.patch.object(osr.subprocess, "Popen") as popen:
            digest_packet = self.facade.run(self.entry.tool_id)
        self.assertEqual(
            digest_packet["machine_error_code"], osr.CLI_BINARY_IDENTITY_DRIFT
        )
        popen.assert_not_called()

        record["binary_sha256"] = osr.compute_tool_digest("/bin/echo")
        record["binary_realpath"] = os.path.realpath("/usr/bin/false")
        self._write_store(payload)
        with mock.patch.object(osr.subprocess, "Popen") as popen:
            realpath_packet = self.facade.run(self.entry.tool_id)
        self.assertEqual(
            realpath_packet["machine_error_code"], osr.CLI_BINARY_IDENTITY_DRIFT
        )
        self.assertEqual(
            realpath_packet["blocked_reason"], "binary_realpath_missing_or_drifted"
        )
        popen.assert_not_called()

    def test_version_identity_is_reprobed_before_operational_spawn(self) -> None:
        self._admit()
        payload = self._load_store()
        payload["records"][self.entry.tool_id]["version_text"] = "drifted-version"
        self._write_store(payload)
        original_popen = osr.subprocess.Popen
        with mock.patch.object(osr.subprocess, "Popen", wraps=original_popen) as popen:
            packet = self.facade.run(self.entry.tool_id)
        self.assertEqual(
            packet["machine_error_code"], osr.CLI_BINARY_IDENTITY_DRIFT
        )
        self.assertEqual(packet["blocked_reason"], "version_revalidation_failed")
        self.assertEqual(popen.call_count, 1)  # version probe only; no operational run

    def test_declaration_and_admission_do_not_override_provider_policy_gates(self) -> None:
        pending_adapter = replace(self.entry, provider_adapter_admitted=False)
        facade = osr.ProductionOneShotFacade(
            homes_root=self.homes_root,
            admission_root=self.admission_root,
            manifest=(pending_adapter,),
        )
        probe = facade.probe(pending_adapter.tool_id)
        admitted = facade.admit(
            pending_adapter.tool_id,
            expected_binary_sha256=str(probe["binary_sha256"]),
        )
        self.assertEqual(admitted["status"], "ok")
        self.assertFalse(admitted["provider_adapter_admitted"])
        self.assertEqual(
            facade.run(pending_adapter.tool_id)["machine_error_code"],
            osr.CLI_PROVIDER_ADAPTER_NOT_ADMITTED,
        )

        network_pending = replace(self.entry, network_policy="denied_pending_test")
        self.assertEqual(
            osr.ProductionOneShotFacade(
                homes_root=self.homes_root,
                admission_root=self.admission_root,
                manifest=(network_pending,),
            ).run(network_pending.tool_id)["machine_error_code"],
            osr.CLI_NETWORK_POLICY_NOT_ADMITTED,
        )
        auth_pending = replace(self.entry, auth_strategy="interactive_pending_test")
        self.assertEqual(
            osr.ProductionOneShotFacade(
                homes_root=self.homes_root,
                admission_root=self.admission_root,
                manifest=(auth_pending,),
            ).run(auth_pending.tool_id)["machine_error_code"],
            osr.CLI_AUTH_NOT_ADMITTED,
        )

    def test_production_facade_has_no_caller_argv_path_or_sandbox_widening(self) -> None:
        with self.assertRaises(TypeError):
            self.facade.run(self.entry.tool_id, args=("unsafe",))  # type: ignore[call-arg]
        with self.assertRaises(TypeError):
            self.facade.probe(  # type: ignore[call-arg]
                self.entry.tool_id, executable="/tmp/untrusted"
            )
        with self.assertRaises(TypeError):
            self.facade.run(  # type: ignore[call-arg]
                self.entry.tool_id, sandbox_profile="allow-default"
            )

    def test_invalid_server_declaration_fails_before_probe_or_store_access(self) -> None:
        invalid = replace(self.entry, sandbox_policy="allow_default")
        facade = osr.ProductionOneShotFacade(
            homes_root=self.homes_root,
            admission_root=self.admission_root,
            manifest=(invalid,),
        )
        with mock.patch.object(osr.subprocess, "Popen") as popen:
            packet = facade.probe(invalid.tool_id)
        self.assertEqual(packet["machine_error_code"], osr.ONE_SHOT_SCHEMA_INVALID)
        self.assertEqual(packet["blocked_reason"], "declaration_sandbox_policy_invalid")
        popen.assert_not_called()
        self.assertFalse(self.admission_root.exists())


class SecretBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        _install_test_sandbox_transport(self, self.root)
        self.script = self.root / "constant-output.sh"
        self.script.write_text(
            "#!/bin/sh\n"
            "echo 'token=abcdefghijklmnop'\n"
            "echo 'Bearer abcdefghijklmnop' >&2\n",
            encoding="utf-8",
        )
        self.script.chmod(0o755)
        self.entry = osr.OneShotToolManifestEntry(
            tool_id="constant-output",
            provider_id="test",
            binary_name=str(self.script),
            display_name="Constant Output",
            server_owned=False,
        )
        self.runtime = osr.OneShotRuntime(
            homes_root=self.root / "homes",
            manifest=(self.entry,),
        )

    def test_secret_shaped_argv_and_stdin_are_blocked_before_spawn(self) -> None:
        with mock.patch.object(osr.subprocess, "Popen") as popen:
            argv = self.runtime.one_shot_cli_run(
                self.entry.tool_id,
                args=("token=abcdefghijklmnop",),
            )
            stdin = self.runtime.one_shot_cli_run(
                self.entry.tool_id,
                stdin_text="Authorization: Bearer abcdefghijklmnop",
            )
            quoted_json = self.runtime.one_shot_cli_run(
                self.entry.tool_id,
                args=('{"token":"abcdefghijklmnop"}',),
            )
        for packet in (argv, stdin, quoted_json):
            self.assertEqual(
                packet["machine_error_code"], osr.ONE_SHOT_SECRET_INPUT_BLOCKED
            )
            self.assertTrue(packet["input_blocked"])
            self.assertNotIn("abcdefghijklmnop", json.dumps(packet))
        popen.assert_not_called()

    def test_serialized_stdout_stderr_and_parser_output_are_redacted(self) -> None:
        packet = self.runtime.one_shot_cli_run(self.entry.tool_id)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["run"]["output_redacted"])
        serialized = json.dumps(packet)
        self.assertNotIn("abcdefghijklmnop", serialized)
        self.assertIn("<redacted>", serialized)
        parsed = osr.parse_cli_output("token=abcdefghijklmnop", profile="text")
        self.assertNotIn("abcdefghijklmnop", json.dumps(parsed))
        parsed_json = osr.parse_cli_output(
            '{"token":"abcdefghijklmnop"}\n', profile="json_lines"
        )
        self.assertEqual(parsed_json["records"][0]["token"], "<redacted>")
        self.assertNotIn("abcdefghijklmnop", json.dumps(parsed_json))

    def test_raw_spawn_exception_text_is_not_serialized(self) -> None:
        sentinel = "token=spawnexceptionsecret"
        with mock.patch.object(osr.subprocess, "Popen", side_effect=OSError(sentinel)):
            packet = self.runtime.one_shot_cli_run(self.entry.tool_id)
        self.assertEqual(packet["machine_error_code"], osr.ONE_SHOT_RUN_FAILED)
        self.assertNotIn(sentinel, json.dumps(packet))
        self.assertNotIn("spawnexceptionsecret", json.dumps(packet))

    def test_bare_keychain_word_is_not_treated_as_a_secret_value(self) -> None:
        echo_entry = replace(
            self.entry,
            tool_id="echo",
            binary_name="/bin/echo",
        )
        runtime = osr.OneShotRuntime(
            homes_root=self.root / "echo-homes", manifest=(echo_entry,)
        )
        packet = runtime.one_shot_cli_run("echo", args=("keychain",))
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["run"]["stdout"], "keychain\n")


if __name__ == "__main__":
    unittest.main()

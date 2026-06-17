# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wild_boar_proxy import proof_seal
from wild_boar_proxy.core import packets


ROOT = Path(__file__).resolve().parents[1]


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _input_hashes_digest(input_hashes: dict[str, str]) -> str:
    encoded = json.dumps(
        {"input_packet_hashes": input_hashes},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256(encoded)


def _packet(*, packet_kind: str = "wbp_test_packet") -> dict[str, object]:
    return packets.build_command_packet(
        ok=True,
        human_message="test packet",
        machine_error_code="OK",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        effect="probe",
        extra={
            "schema_version": 1,
            "packet_kind": packet_kind,
            "product_ready": False,
            "raw_prompt_recorded": False,
            "raw_route_id_recorded": False,
            "raw_provider_response_recorded": False,
            "secret_value_exposed": False,
        },
    )


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def _create_seal(
    *,
    packet_path: Path,
    input_packet_files: list[Path] | None = None,
) -> Path:
    seal_path = proof_seal.default_seal_path(packet_path)
    args = [
        sys.executable,
        "-m",
        "wild_boar_proxy",
        "router-hook",
        "proof-seal-create",
        "--packet-file",
        str(packet_path),
        "--seal-file",
        str(seal_path),
        "--producer-kind",
        "unit_test_producer",
        "--producer-command-digest",
        _sha256("unit-test-command"),
        "--json",
    ]
    for input_path in input_packet_files or []:
        args.extend(["--input-packet-file", str(input_path)])
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return seal_path


def _verify(
    *,
    packet_path: Path,
    seal_path: Path,
    expected_packet_kind: str = "wbp_test_packet",
) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "router-hook",
            "proof-seal-verify",
            "--packet-file",
            str(packet_path),
            "--seal-file",
            str(seal_path),
            "--expected-packet-kind",
            expected_packet_kind,
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return json.loads(result.stdout)


class ProofSealTests(unittest.TestCase):
    def test_cli_create_and_verify_proof_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet_path = _write_json(root / "source.packet.json", _packet())
            seal_path = _create_seal(packet_path=packet_path)
            packet = _verify(packet_path=packet_path, seal_path=seal_path)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["proof_seal_verified"])
        self.assertTrue(packet["source_file_authenticity_proven"])
        self.assertFalse(packet["source_file_unforgeable"])
        self.assertFalse(packet["cryptographic_authenticity_proven"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_verify_blocks_modified_packet_after_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet_path = _write_json(root / "source.packet.json", _packet())
            seal_path = _create_seal(packet_path=packet_path)
            changed = _packet()
            changed["human_message"] = "changed packet"
            packet_path.write_text(json.dumps(changed) + "\n", encoding="utf-8")
            packet = _verify(packet_path=packet_path, seal_path=seal_path)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], proof_seal.PROOF_SEAL_HASH_MISMATCH)
        self.assertFalse(packet["proof_seal_verified"])
        self.assertIn("sealed_packet_sha256_mismatch", packet["proof_seal_failures"])

    def test_verify_blocks_missing_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet_path = _write_json(root / "source.packet.json", _packet())
            packet = _verify(
                packet_path=packet_path,
                seal_path=root / "missing.seal.json",
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["proof_seal_verified"])
        self.assertIn("proof_seal_file_not_read", packet["proof_seal_failures"])

    def test_verify_blocks_wrong_packet_kind(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet_path = _write_json(root / "source.packet.json", _packet())
            seal_path = _create_seal(packet_path=packet_path)
            packet = _verify(
                packet_path=packet_path,
                seal_path=seal_path,
                expected_packet_kind="other_kind",
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["proof_seal_verified"])
        self.assertIn("sealed_packet_kind_not_expected", packet["proof_seal_failures"])

    def test_verify_blocks_unsafe_seal_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet_path = _write_json(root / "source.packet.json", _packet())
            seal_path = _create_seal(packet_path=packet_path)
            seal = json.loads(seal_path.read_text(encoding="utf-8"))
            seal["product_ready"] = True
            seal_path.write_text(json.dumps(seal) + "\n", encoding="utf-8")
            packet = _verify(packet_path=packet_path, seal_path=seal_path)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], proof_seal.PROOF_SEAL_UNSAFE_CLAIM)
        self.assertFalse(packet["proof_seal_verified"])
        self.assertIn("seal_product_ready_must_not_be_claimed", packet["proof_seal_failures"])

    def test_verify_blocks_input_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = _write_json(root / "input.packet.json", _packet(packet_kind="input_kind"))
            packet_path = _write_json(root / "source.packet.json", _packet())
            seal_path = _create_seal(
                packet_path=packet_path,
                input_packet_files=[input_path],
            )
            seal = json.loads(seal_path.read_text(encoding="utf-8"))
            seal["input_packet_hashes"]["input_kind"] = _sha256("other input")
            seal_path.write_text(json.dumps(seal) + "\n", encoding="utf-8")
            verify_packet, _seal = proof_seal.verify_proof_seal(
                packet_file=packet_path,
                seal_file=seal_path,
                expected_input_packet_hashes={
                    "input_kind": proof_seal.sha256_file(input_path)
                },
            )

        self.assertEqual(verify_packet["status"], "error")
        self.assertEqual(
            verify_packet["machine_error_code"],
            proof_seal.PROOF_SEAL_INPUT_MISMATCH,
        )
        self.assertIn(
            "input_packet_hash_mismatch:input_kind",
            verify_packet["proof_seal_failures"],
        )

    def test_verify_blocks_tampered_producer_inputs_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = _write_json(
                root / "input.packet.json",
                _packet(packet_kind="input_kind"),
            )
            packet_path = _write_json(root / "source.packet.json", _packet())
            seal_path = _create_seal(
                packet_path=packet_path,
                input_packet_files=[input_path],
            )
            seal = json.loads(seal_path.read_text(encoding="utf-8"))
            seal["producer_inputs_digest"] = _sha256("tampered inputs")
            seal_path.write_text(json.dumps(seal) + "\n", encoding="utf-8")
            packet = _verify(packet_path=packet_path, seal_path=seal_path)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], proof_seal.PROOF_SEAL_INPUT_MISMATCH)
        self.assertFalse(packet["proof_seal_verified"])
        self.assertIn("producer_inputs_digest_mismatch", packet["proof_seal_failures"])

    def test_verify_blocks_unexpected_input_hash_when_expected_set_declared(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = _write_json(
                root / "input.packet.json",
                _packet(packet_kind="input_kind"),
            )
            packet_path = _write_json(root / "source.packet.json", _packet())
            seal_path = _create_seal(
                packet_path=packet_path,
                input_packet_files=[input_path],
            )
            seal = json.loads(seal_path.read_text(encoding="utf-8"))
            seal["input_packet_hashes"]["unexpected_kind"] = _sha256("unexpected")
            seal["producer_inputs_digest"] = _input_hashes_digest(
                dict(seal["input_packet_hashes"])
            )
            seal_path.write_text(json.dumps(seal) + "\n", encoding="utf-8")
            verify_packet, _seal = proof_seal.verify_proof_seal(
                packet_file=packet_path,
                seal_file=seal_path,
                expected_input_packet_hashes={
                    "input_kind": proof_seal.sha256_file(input_path)
                },
            )

        self.assertEqual(verify_packet["status"], "error")
        self.assertEqual(
            verify_packet["machine_error_code"],
            proof_seal.PROOF_SEAL_INPUT_MISMATCH,
        )
        self.assertIn(
            "input_packet_hash_unexpected:unexpected_kind",
            verify_packet["proof_seal_failures"],
        )


if __name__ == "__main__":
    unittest.main()

# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import custom_codex_ui_visibility_proof as ui_visibility
from wild_boar_proxy import full_runtime_dispatch_proof as proof
from wild_boar_proxy import native_custom_codex_visible_flow_proof as native_visible
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_custom_codex_ui_visibility_proof import (  # noqa: E402
    _file_metadata as _ui_file_metadata,
    _native_packet,
    _source_packet,
)
from test_native_custom_codex_visible_flow_proof import (  # noqa: E402
    _metadata as _native_visible_metadata,
    _working_flow_packet as _native_visible_working_flow_packet,
)
from test_official_e2e_working_flow_proof_join import (  # noqa: E402
    EXPECTED_TEXT,
    PROMPT,
    RAW_PROVIDER_TEXT,
    ROUTE_ID,
    _packet as _official_e2e_packet,
)


REQUEST_ID = "wbp-full-runtime-dispatch-001"


def _secret_values() -> list[str]:
    return [PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT]


def _full_file_metadata() -> dict[str, object]:
    return {
        "official_e2e_working_flow_proof_file_required": True,
        "official_e2e_working_flow_proof_file_present": True,
        "official_e2e_working_flow_proof_file_read": True,
        "official_e2e_working_flow_proof_file_valid_json": True,
        "official_e2e_working_flow_proof_file_mapping": True,
        "official_e2e_working_flow_proof_file_error_code": "",
        "official_e2e_working_flow_proof_file_path_recorded": False,
        "official_e2e_working_flow_proof_file_sha256": "a" * 64,
        "custom_codex_ui_visibility_proof_file_required": True,
        "custom_codex_ui_visibility_proof_file_present": True,
        "custom_codex_ui_visibility_proof_file_read": True,
        "custom_codex_ui_visibility_proof_file_valid_json": True,
        "custom_codex_ui_visibility_proof_file_mapping": True,
        "custom_codex_ui_visibility_proof_file_error_code": "",
        "custom_codex_ui_visibility_proof_file_path_recorded": False,
        "custom_codex_ui_visibility_proof_file_sha256": "b" * 64,
    }


def _ui_packet_for(
    upstream: dict[str, object],
    *,
    source_overrides: dict[str, object] | None = None,
    native_overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    handoff_digest = str(upstream["handoff_payload_digest"])
    expected_visible_text = f"WBP_FULL_RUNTIME_VISIBLE_{handoff_digest}_{REQUEST_ID}"
    source = _source_packet(
        {
            "handoff_payload_digest": handoff_digest,
            "visible_source_marker_digest": handoff_digest,
            **(source_overrides or {}),
        }
    )
    native = _native_packet(
        expected_text=expected_visible_text,
        request_id=REQUEST_ID,
        overrides=native_overrides,
    )
    packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
        source,
        native,
        expected_visible_text=expected_visible_text,
        request_id=REQUEST_ID,
        file_metadata=_ui_file_metadata(),
    )
    assert packet["status"] == "ok"
    return packet


def _native_visible_packet_for(
    upstream: dict[str, object],
    *,
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    handoff_digest = str(upstream["handoff_payload_digest"])
    expected_visible_text = f"WBP_FULL_RUNTIME_NATIVE_VISIBLE_{handoff_digest}_{REQUEST_ID}"
    native_packet = native_visible.build_native_custom_codex_visible_flow_proof_packet(
        _native_visible_working_flow_packet({"handoff_payload_digest": handoff_digest}),
        _native_packet(
            expected_text=expected_visible_text,
            request_id=REQUEST_ID,
        ),
        expected_visible_text=expected_visible_text,
        request_id=REQUEST_ID,
        file_metadata=_native_visible_metadata(),
    )
    assert native_packet["status"] == "ok"
    if overrides:
        native_packet.update(overrides)
    return native_packet


def _packet(
    *,
    upstream: dict[str, object] | None = None,
    ui: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    upstream_packet = _official_e2e_packet() if upstream is None else upstream
    ui_packet = _ui_packet_for(upstream_packet) if ui is None else ui
    return proof.build_full_runtime_dispatch_proof_packet(
        official_e2e_working_flow_packet=upstream_packet,
        custom_codex_ui_visibility_packet=ui_packet,
        file_metadata=_full_file_metadata() if metadata is None else metadata,
    )


def _assert_no_product_or_raw_claims(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in _secret_values():
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["product_ready"])
    testcase.assertFalse(packet["fallback_used"])
    testcase.assertFalse(packet["local_imitation_used"])
    testcase.assertFalse(packet["native_codex_subagent_used_as_dip"])
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["raw_dom_exposed"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["secret_value_exposed"])
    testcase.assertEqual(packet["changed_files"], [])


class FullRuntimeDispatchProofTests(unittest.TestCase):
    def test_positive_joins_official_e2e_to_native_ui_visibility(self) -> None:
        upstream = _official_e2e_packet()
        packet = _packet(upstream=upstream)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["packet_kind"], proof.FULL_RUNTIME_DISPATCH_PROOF_PACKET_KIND)
        self.assertTrue(packet["full_runtime_dispatch_proven"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["alias_resolved"])
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["handoff_bound_to_dispatch"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["native_response_bound_to_handoff"])
        self.assertTrue(packet["visible_response_after_dispatch"])
        self.assertTrue(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packet["handoff_payload_digest"], upstream["handoff_payload_digest"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertFalse(any("freshness_anchor" in key for key in packet))
        self.assertNotIn("external_freshness_proven", packet)
        _assert_no_product_or_raw_claims(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_accepts_native_visible_flow_as_ui_source(self) -> None:
        upstream = _official_e2e_packet()
        packet = _packet(upstream=upstream, ui=_native_visible_packet_for(upstream))

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["full_runtime_dispatch_proven"])
        self.assertTrue(packet["custom_codex_ui_visibility_proven"])
        self.assertTrue(packet["native_custom_codex_visible_flow_proven"])
        self.assertEqual(
            packet["custom_codex_ui_visibility_source_kind"],
            "native_custom_codex_visible_flow_proof",
        )
        self.assertEqual(packet["handoff_payload_digest"], upstream["handoff_payload_digest"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_product_or_raw_claims(self, packet)

    def test_blocks_forged_native_visible_flow_source(self) -> None:
        upstream = _official_e2e_packet()
        forged = _native_visible_packet_for(
            upstream,
            overrides={"native_custom_codex_visible_flow_proven": False},
        )

        packet = _packet(upstream=upstream, ui=forged)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.FULL_RUNTIME_DISPATCH_UI_INVALID,
        )
        self.assertFalse(packet["full_runtime_dispatch_proven"])
        self.assertIn(
            "native_visible_flow_native_custom_codex_visible_flow_proven_not_true",
            packet["blocking_reasons"],
        )
        _assert_no_product_or_raw_claims(self, packet)

    def test_blocks_native_visible_flow_handoff_digest_mismatch(self) -> None:
        upstream = _official_e2e_packet()
        mismatched = _native_visible_packet_for(
            {**upstream, "handoff_payload_digest": "c" * 64}
        )

        packet = _packet(upstream=upstream, ui=mismatched)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.FULL_RUNTIME_DISPATCH_NOT_BOUND,
        )
        self.assertFalse(packet["full_runtime_dispatch_proven"])
        self.assertIn("handoff_payload_digest_mismatch", packet["blocking_reasons"])
        _assert_no_product_or_raw_claims(self, packet)

    def test_blocks_when_upstream_api_dispatch_is_not_proven(self) -> None:
        upstream = {**_official_e2e_packet(), "api_lane_called": False}
        packet = _packet(upstream=upstream)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.FULL_RUNTIME_DISPATCH_UPSTREAM_INVALID,
        )
        self.assertFalse(packet["full_runtime_dispatch_proven"])
        self.assertIn("official_e2e_api_lane_called_not_true", packet["blocking_reasons"])
        _assert_no_product_or_raw_claims(self, packet)

    def test_blocks_when_ui_visibility_is_only_prompt_echo(self) -> None:
        upstream = _official_e2e_packet()
        bad_ui = _ui_packet_for(upstream)
        bad_ui["custom_response_exact_token_observed"] = False
        bad_ui["custom_response_prompt_echo_candidate_count"] = 1
        bad_ui["custom_codex_ui_visibility_proven"] = False

        packet = _packet(upstream=upstream, ui=bad_ui)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.FULL_RUNTIME_DISPATCH_UI_INVALID,
        )
        self.assertFalse(packet["full_runtime_dispatch_proven"])
        self.assertIn(
            "ui_visibility_custom_codex_ui_visibility_proven_not_true",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "ui_visibility_custom_response_exact_token_observed_not_true",
            packet["blocking_reasons"],
        )
        _assert_no_product_or_raw_claims(self, packet)

    def test_blocks_malformed_ui_candidate_counts(self) -> None:
        upstream = _official_e2e_packet()
        cases = (
            (
                "custom_response_exact_token_candidate_count",
                -1,
                "ui_visibility_exact_token_candidate_count_missing",
            ),
            (
                "custom_response_exact_token_candidate_count",
                "1",
                "ui_visibility_exact_token_candidate_count_missing",
            ),
            (
                "custom_response_like_candidate_count",
                0,
                "ui_visibility_like_candidate_count_missing",
            ),
            (
                "custom_response_like_candidate_count",
                "1",
                "ui_visibility_like_candidate_count_missing",
            ),
        )

        for field, value, reason in cases:
            with self.subTest(field=field, value=value):
                bad_ui = _ui_packet_for(upstream)
                bad_ui[field] = value

                packet = _packet(upstream=upstream, ui=bad_ui)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.FULL_RUNTIME_DISPATCH_UI_INVALID,
                )
                self.assertFalse(packet["full_runtime_dispatch_proven"])
                self.assertIn(reason, packet["blocking_reasons"])
                _assert_no_product_or_raw_claims(self, packet)

    def test_blocks_handoff_digest_mismatch_between_e2e_and_ui(self) -> None:
        upstream = _official_e2e_packet()
        bad_ui = _ui_packet_for({**upstream, "handoff_payload_digest": "c" * 64})

        packet = _packet(upstream=upstream, ui=bad_ui)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.FULL_RUNTIME_DISPATCH_NOT_BOUND,
        )
        self.assertFalse(packet["full_runtime_dispatch_proven"])
        self.assertIn("handoff_payload_digest_mismatch", packet["blocking_reasons"])
        _assert_no_product_or_raw_claims(self, packet)

    def test_blocks_product_ready_or_raw_material_claims(self) -> None:
        upstream = {**_official_e2e_packet(), "product_ready": True}
        packet = _packet(upstream=upstream)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.FULL_RUNTIME_DISPATCH_UNSAFE_SOURCE,
        )
        self.assertFalse(packet["full_runtime_dispatch_proven"])
        self.assertIn("official_e2e_unsafe_product_ready", packet["blocking_reasons"])
        _assert_no_product_or_raw_claims(self, packet)

    def test_run_writes_file_backed_packet_without_recording_paths(self) -> None:
        upstream = _official_e2e_packet()
        ui_packet = _ui_packet_for(upstream)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            upstream_file = root / "official-e2e.json"
            ui_file = root / "ui.json"
            proof_dir = root / "proof"
            upstream_file.write_text(json.dumps(upstream, sort_keys=True), encoding="utf-8")
            ui_file.write_text(json.dumps(ui_packet, sort_keys=True), encoding="utf-8")

            packet = proof.run_full_runtime_dispatch_proof_command(
                official_e2e_working_flow_proof_file=str(upstream_file),
                custom_codex_ui_visibility_proof_file=str(ui_file),
                proof_dir=str(proof_dir),
            )

            written = proof_dir / proof.FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME
            persisted = json.loads(written.read_text(encoding="utf-8"))

        self.assertEqual(packet, persisted)
        self.assertTrue(packet["packet_file_written"])
        self.assertFalse(packet["packet_file_path_recorded"])
        self.assertFalse(packet["official_e2e_working_flow_proof_file_path_recorded"])
        self.assertFalse(packet["custom_codex_ui_visibility_proof_file_path_recorded"])
        self.assertEqual(len(packet["official_e2e_working_flow_proof_file_sha256"]), 64)
        self.assertEqual(len(packet["custom_codex_ui_visibility_proof_file_sha256"]), 64)
        self.assertTrue(packet["full_runtime_dispatch_proven"])
        _assert_no_product_or_raw_claims(self, packet)

    def test_cli_emits_full_runtime_dispatch_packet(self) -> None:
        expected = _packet()
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli.run_full_runtime_dispatch_proof_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "full-runtime-dispatch-proof",
                    "--official-e2e-working-flow-proof-file",
                    "official-e2e.json",
                    "--custom-codex-ui-visibility-proof-file",
                    "ui.json",
                    "--proof-dir",
                    "/tmp/wbp-full-runtime-proof",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertTrue(payload["full_runtime_dispatch_proven"])
        run_command.assert_called_once_with(
            official_e2e_working_flow_proof_file="official-e2e.json",
            custom_codex_ui_visibility_proof_file="ui.json",
            proof_dir="/tmp/wbp-full-runtime-proof",
        )
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()

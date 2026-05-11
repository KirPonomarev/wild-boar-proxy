# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from wild_boar_proxy.external_models import contracts, routes
from wild_boar_proxy.external_models import lifecycle
from wild_boar_proxy.external_models.paths import ExternalModelsPaths
from wild_boar_proxy.external_models.state import capture_local_evidence, load_state_file
from wild_boar_proxy.runtime import RuntimeErrorInfo


def sample_route() -> dict[str, object]:
    return {
        "schema_version": 1,
        "route_id": "wbp-deepseek-v3",
        "display_name": "DeepSeek V3",
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "endpoint_path": "/chat/completions",
        "upstream_model": "deepseek/deepseek-chat",
        "compatibility": "openai_chat_completions",
        "auth": {"type": "bearer", "secret_ref": "OPENROUTER_API_KEY"},
        "cost_class": "paid_or_free_limited",
        "lane_role": "candidate",
        "fallback_eligible": False,
        "enabled": True,
    }


class ExternalModelContractTests(unittest.TestCase):
    def test_default_state_payload_keeps_policy_separate(self) -> None:
        payload = contracts.default_state_payload()
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(
            payload["policy"],
            {
                "paid_routes_enabled": False,
                "paid_route_allowlist": [],
                "paid_route_default": "blocked",
            },
        )
        self.assertEqual(payload["adapter"]["state"], "stopped")
        self.assertFalse(payload["local_auth"]["token_present"])
        self.assertEqual(payload["routes"], {})

    def test_validate_route_schema_rejects_observed_state_field(self) -> None:
        route = sample_route() | {"last_check": "2026-05-12T00:00:00Z"}
        with self.assertRaises(RuntimeErrorInfo) as ctx:
            routes.validate_route_schema(route)
        self.assertEqual(ctx.exception.machine_error_code, "schema_invalid")

    def test_paths_from_env_uses_isolated_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "external-models"
            old = dict(os.environ)
            try:
                os.environ["WBP_EXTERNAL_MODELS_DIR"] = str(root)
                paths = ExternalModelsPaths.from_env()
            finally:
                os.environ.clear()
                os.environ.update(old)
            self.assertEqual(paths.root_dir, root.resolve())
            self.assertEqual(paths.routes_file, (root / "routes.json").resolve())
            self.assertEqual(paths.state_file, (root / "state.json").resolve())

    def test_capture_local_evidence_writes_non_self_referential_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_dir = Path(temp_dir) / "evidence"
            route = sample_route()
            packet = contracts.build_external_models_payload(
                ok=True,
                human_message="ok",
                machine_error_code="OK",
                data={"route_id": route["route_id"]},
            )
            path = capture_local_evidence(
                evidence_dir=evidence_dir,
                route=route,
                packet=packet,
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            artifact_sha = payload.pop("artifact_sha256")
            canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode(
                "utf-8"
            )
            import hashlib

            self.assertEqual(artifact_sha, hashlib.sha256(canonical).hexdigest())

    def test_load_state_file_returns_default_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = load_state_file(Path(temp_dir) / "missing.json")
            self.assertEqual(state["policy"]["paid_route_default"], "blocked")

    def test_load_state_file_migrates_v1_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "policy": {
                            "paid_routes_enabled": True,
                            "paid_route_allowlist": ["wbp-paid"],
                            "paid_route_default": "allow",
                        },
                        "routes": {"wbp-a": {"availability_state": "unverified"}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            state = load_state_file(state_path)
            self.assertEqual(state["schema_version"], 2)
            self.assertEqual(state["adapter"]["state"], "stopped")
            self.assertTrue(state["policy"]["paid_routes_enabled"])
            self.assertIn("wbp-a", state["routes"])

    def test_allocate_synthetic_port_skips_reserved_ports(self) -> None:
        ports = [8318, 8320, 45678]

        class FakeSocket:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def bind(self, addr):
                return None

            def getsockname(self):
                return ("127.0.0.1", ports.pop(0))

        with mock.patch("wild_boar_proxy.external_models.lifecycle.socket.socket", return_value=FakeSocket()):
            self.assertEqual(lifecycle.allocate_synthetic_port(), 45678)


class ZeroTestSelectionGuardTests(unittest.TestCase):
    def test_module_contains_real_tests(self) -> None:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(
            ExternalModelContractTests
        )
        self.assertGreaterEqual(suite.countTestCases(), 4)

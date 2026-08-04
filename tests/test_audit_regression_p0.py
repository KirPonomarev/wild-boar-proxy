# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Audit-driven regression tests (external auditor FAIL_REOPEN findings).

Each test reproduces a specific P0/P1 finding from the independent audit and
asserts the fix holds. These tests exist specifically because the original
suite passed while the bugs were present — they close the greenwash gap.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import actor_dispatcher as ad
from wild_boar_proxy import execution_core_design_gate as ecg
from wild_boar_proxy import one_shot_cli_runtime as osr
from wild_boar_proxy.thread_context_ledger import ThreadContextLedger


class AuditP0PermissionCapabilitySet(unittest.TestCase):
    """P0: network_read grant must NOT yield repo_write."""

    def test_network_read_grant_never_yields_repo_write(self) -> None:
        result = ad.effective_permission(
            binding_permission_ceiling="repo_write",
            explicit_operator_grant="network_read",
            adapter_capability="repo_write",
            runtime_policy="repo_write",
        )
        self.assertNotEqual(result, "repo_write")
        self.assertEqual(result, "context_only")

    def test_cross_axis_intersection_is_context_only(self) -> None:
        result = ad.effective_permission(
            binding_permission_ceiling="network_read",
            explicit_operator_grant="browser_read",
            adapter_capability="repo_write",
            runtime_policy="repo_read",
        )
        self.assertEqual(result, "context_only")


class AuditP0SterileEnvScrub(unittest.TestCase):
    """P0: CODEX_HOME, WBP_PROFILE_DIR, SSH_AUTH_SOCK, proxy vars must be scrubbed."""

    def setUp(self) -> None:
        self._old = {}
        for k in ("CODEX_HOME", "WBP_PROFILE_DIR", "SSH_AUTH_SOCK",
                   "ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY"):
            self._old[k] = os.environ.get(k)
            os.environ[k] = "/fake/" + k

    def tearDown(self) -> None:
        for k, v in self._old.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    def test_forbidden_keys_absent_from_sterile_env(self) -> None:
        env = osr.build_sterile_environment()
        for k in ("CODEX_HOME", "WBP_PROFILE_DIR", "SSH_AUTH_SOCK",
                   "ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY"):
            self.assertNotIn(k, env, f"{k} leaked into sterile env")


class AuditP0SandboxEnforcement(unittest.TestCase):
    """P0: child must not write when repo_write=denied."""

    def test_child_cannot_write_with_denied_sandbox(self) -> None:
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            script = root / "escape.sh"
            script.write_text(
                "#!/bin/sh\necho hacked > escape.txt 2>/dev/null; exit 0\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            manifest = root / "m.json"
            manifest.write_text(
                json.dumps({"tools": [{"tool_id": "w", "binary_name": str(script)}]}),
                encoding="utf-8",
            )
            os.environ[osr.FAKE_MANIFEST_ENV] = str(manifest)
            os.environ[osr.HOMES_ROOT_ENV] = str(root / "h")
            try:
                packet = osr.one_shot_cli_run(
                    "w", sandbox=osr.SandboxProfile(repo_write="denied")
                )
                leaked = list(Path("/tmp").glob("escape.txt"))
                leaked += list(Path(".").glob("escape.txt"))
                leaked += list(Path("/tmp").glob("wbp-sandbox-ro-*/escape.txt"))
                self.assertFalse(leaked, "child wrote file despite repo_write=denied")
            finally:
                os.environ.pop(osr.FAKE_MANIFEST_ENV, None)
                os.environ.pop(osr.HOMES_ROOT_ENV, None)


class AuditP0LedgerPathContainment(unittest.TestCase):
    """P0: ../approved-escape must not pass path containment."""

    def test_path_traversal_in_thread_id_blocked(self) -> None:
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                ThreadContextLedger(root, thread_id="../approved-escape")

    def test_normal_thread_id_works(self) -> None:
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            ledger = ThreadContextLedger(Path(tmp), thread_id="t1")
            self.assertTrue(ledger.ledger_root.exists())


class AuditP0BindingIdUniqueness(unittest.TestCase):
    """P0: duplicate binding_id must be rejected in the registry."""

    def test_duplicate_binding_id_rejected(self) -> None:
        from wild_boar_proxy.actor_registry import validate_actor_registry_document
        doc = {
            "schema_version": 2,
            "kind": "wbp_actor_registry",
            "actors": [
                {"actor_id": "a1", "display_name": "A1", "transport_adapter_id": "api",
                 "provider_id": "deepseek", "permission_ceiling": "context_only",
                 "enabled": True, "revision": 1},
            ],
            "slot_bindings": [
                {"binding_id": "dup", "slot_id": "primary", "actor_id": "a1",
                 "binding_revision": 1, "aliases": ["dip"], "enabled": True},
                {"binding_id": "dup", "slot_id": "agent_1", "actor_id": "a1",
                 "binding_revision": 1, "aliases": ["agent1"], "enabled": True},
            ],
            "role_assignments": [],
            "agent_bindings": [],
        }
        result = validate_actor_registry_document(doc)
        reasons = result.get("reasons", []) if isinstance(result, dict) else result
        dup_reasons = [r for r in reasons if "binding_id_duplicate" in r]
        self.assertTrue(dup_reasons, f"expected binding_id_duplicate reason, got: {reasons}")


class AuditP1DesignGateHonestChecks(unittest.TestCase):
    """P1: design gate must reject fake stages and bad SHA."""

    def test_fake_stages_and_bad_sha_rejected(self) -> None:
        packet = ecg.run_execution_core_design_gate(
            completed_stages=[f"fake{i}" for i in range(1, 11)],
            evidence_index_references=1,
            full_suite_passed=1,
            main_head="not-a-git-sha",
        )
        self.assertFalse(packet["design_gate_earned"])
        self.assertIsNone(packet["design_gate_marker"])

    def test_bad_sha_rejected_even_with_real_stages(self) -> None:
        packet = ecg.run_execution_core_design_gate(
            completed_stages=[
                "B00_BASELINE_ADMISSION_REPAIR",
                "B01_ACTOR_ADR_AND_SPIKES",
                "B02_ACTOR_SCHEMA_V2_AND_MIGRATION",
                "B03_TRANSPORT_AND_EVIDENCE_STATE_MACHINE",
                "B04_THREAD_CONTEXT_LEDGER_V2",
                "B05_DISPATCHER_ASSIGNMENTS_PERMISSIONS_DIAGNOSTICS",
                "B06_LEGACY_SURFACE_AND_EVIDENCE_MATRIX_REGRESSION",
                "B07_CODE_MULTI_API_CORE",
                "B08_CODE_QWEN_API",
                "B09_ONE_SHOT_CLI_RUNTIME",
            ],
            evidence_index_references=10,
            full_suite_passed=4000,
            main_head="abc",
        )
        self.assertFalse(packet["design_gate_earned"])


if __name__ == "__main__":
    unittest.main()

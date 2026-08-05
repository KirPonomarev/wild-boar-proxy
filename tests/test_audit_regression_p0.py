# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Audit-driven regression tests (external auditor FAIL_REOPEN findings).

Each test reproduces a specific P0/P1 finding from the independent audit and
asserts the fix holds. These tests exist specifically because the original
suite passed while the bugs were present — they close the greenwash gap.

R5: one-shot runtime fixtures come from tests/fakes.py as explicit engine
instances; there is no module-level injection hook anymore.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import fakes

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
    """P0: child must not write when repo_write=denied.

    R5: the engine accepts no caller sandbox posture; every child runs
    under the deny-default production profile. The escape script attempts
    both an absolute write outside the allowed roots and a relative write
    into its (read-only-after-use) sandbox cwd.
    """

    def test_child_cannot_write_with_denied_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            escape_abs = root / "escape.txt"
            script_body = (
                "#!/bin/sh\n"
                f'echo hacked > "{escape_abs}" 2>/dev/null\n'
                "echo hacked > escape_rel.txt 2>/dev/null\n"
                "exit 0\n"
            )
            script = fakes.write_fake_cli(root, "escape.sh", script_body)
            manifest = fakes.write_manifest(
                root, [{"tool_id": "w", "binary_name": str(script)}]
            )
            runtime = fakes.make_test_runtime(
                root / "homes", fakes.load_manifest_entries(manifest)
            )
            handle = runtime.one_shot_cli_handle("w")
            if not isinstance(handle, dict):
                handle.wait(timeout_seconds=10)
            self.assertFalse(
                escape_abs.exists(),
                "child wrote outside the allowed roots despite deny-default sandbox",
            )
            leaked = list(
                Path(tempfile.gettempdir()).glob("wbp-sandbox-ro-*/escape_rel.txt")
            )
            self.assertFalse(
                leaked, "child left a written file in a surviving sandbox cwd"
            )


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
            main_head="not-a-git-sha",
        )
        self.assertFalse(packet["design_gate_earned"])
        self.assertIsNone(packet["design_gate_marker"])

    def test_bad_sha_rejected_even_with_real_stages(self) -> None:
        packet = ecg.run_execution_core_design_gate(
            main_head="abc",
        )
        self.assertFalse(packet["design_gate_earned"])


if __name__ == "__main__":
    unittest.main()

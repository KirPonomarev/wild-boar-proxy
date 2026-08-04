# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B15_OPTIONAL: persistent ACP admission tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import optional_acp_admission as acp


class OptionalAcpAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self._old_path = os.environ.get("PATH", "")

    def tearDown(self) -> None:
        os.environ["PATH"] = self._old_path
        self.temp_dir.cleanup()

    def test_probe_reports_facts_without_network_or_stores(self) -> None:
        os.environ["PATH"] = "/usr/bin:/bin"
        facts = acp.probe_acp_availability()
        self.assertEqual(facts["probe_surface"], "path_resolution_only")
        self.assertFalse(facts["network_calls_made"])
        self.assertFalse(facts["credential_stores_touched"])
        self.assertEqual(facts["repo_transport_kind_declared"], "cli_acp")
        self.assertFalse(facts["repo_acp_runtime_implemented"])

    def test_probe_finds_declared_candidates(self) -> None:
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "acp"
        fake.write_text("#!/bin/sh\necho fake-acp\n", encoding="utf-8")
        fake.chmod(0o755)
        os.environ["PATH"] = str(bin_dir) + ":/usr/bin:/bin"
        facts = acp.probe_acp_availability()
        self.assertTrue(facts["physical_server_available"])
        self.assertIn("acp", facts["found_binaries"])

    def test_admission_defers_without_runtime(self) -> None:
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "acp"
        fake.write_text("#!/bin/sh\necho fake-acp\n", encoding="utf-8")
        fake.chmod(0o755)
        os.environ["PATH"] = str(bin_dir) + ":/usr/bin:/bin"
        packet = acp.evaluate_optional_acp()
        # A binary alone is not enough: no stable repository runtime.
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["decision"], acp.ACP_DEFERRED_TERMINAL)
        self.assertEqual(packet["terminal_result"], acp.ACP_DEFERRED_TERMINAL)
        self.assertFalse(packet["criteria"]["stable_repository_runtime"]["confirmed"])
        self.assertEqual(packet["next_phase"], "NONE_DEFERRED")

    def test_admission_defers_on_this_machine(self) -> None:
        os.environ["PATH"] = "/usr/bin:/bin"
        packet = acp.evaluate_optional_acp()
        self.assertEqual(packet["decision"], acp.ACP_DEFERRED_TERMINAL)
        self.assertEqual(packet["terminal_result"], acp.ACP_DEFERRED_TERMINAL)
        self.assertFalse(packet["criteria"]["physical_server"]["confirmed"])
        self.assertFalse(packet["criteria"]["stable_repository_runtime"]["confirmed"])

    def test_packet_never_contains_secrets(self) -> None:
        os.environ["PATH"] = "/usr/bin:/bin"
        packet = acp.evaluate_optional_acp()
        body = json.dumps(packet)
        self.assertNotIn("sk-", body)
        self.assertNotIn("api_key", body.lower())


if __name__ == "__main__":
    unittest.main()

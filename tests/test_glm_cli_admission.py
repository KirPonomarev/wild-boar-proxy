# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B12_ADMISSION: GLM CLI admission tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import glm_cli_admission as gca


class GlmCliAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self._old_path = os.environ.get("PATH", "")

    def tearDown(self) -> None:
        os.environ["PATH"] = self._old_path
        self.temp_dir.cleanup()

    def test_probe_reports_candidates_and_no_codex_touch(self) -> None:
        os.environ["PATH"] = "/usr/bin:/bin"
        probe = gca.probe_glm_cli_presence()
        self.assertEqual(
            probe["checked_candidates"], list(gca.GLM_CLI_CANDIDATES)
        )
        self.assertEqual(probe["probe_surface"], "path_resolution_only")
        self.assertFalse(probe["codex_surface_touched"])
        self.assertFalse(probe["official_client_found"])

    def test_probe_finds_official_looking_candidate(self) -> None:
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "glm"
        fake.write_text("#!/bin/sh\necho fake-glm\n", encoding="utf-8")
        fake.chmod(0o755)
        os.environ["PATH"] = str(bin_dir) + ":/usr/bin:/bin"
        probe = gca.probe_glm_cli_presence()
        self.assertTrue(probe["official_client_found"])
        self.assertIn("glm", probe["found_candidates"])
        self.assertEqual(Path(probe["found_candidates"]["glm"]).name, "glm")

    def test_admission_fails_closed_without_client(self) -> None:
        os.environ["PATH"] = "/usr/bin:/bin"
        packet = gca.evaluate_glm_cli_admission()
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["decision"], gca.GLM_NOT_ADMITTED)
        self.assertEqual(packet["terminal_result"], gca.GLM_API_ONLY_TERMINAL)
        self.assertEqual(packet["machine_error_code"], gca.GLM_ADMISSION_DENIED)
        criteria = packet["criteria"]
        self.assertFalse(criteria["official_client"]["confirmed"])
        self.assertFalse(criteria["auth"]["confirmed"])
        self.assertFalse(criteria["license"]["confirmed"])
        self.assertFalse(criteria["coding_plan"]["confirmed"])
        self.assertEqual(packet["next_phase"], "NONE_API_ONLY")
        self.assertFalse(packet["codex_surface_touched"])

    def test_admission_still_requires_auth_license_coding_plan(self) -> None:
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "zai"
        fake.write_text("#!/bin/sh\necho fake-zai\n", encoding="utf-8")
        fake.chmod(0o755)
        os.environ["PATH"] = str(bin_dir) + ":/usr/bin:/bin"
        packet = gca.evaluate_glm_cli_admission()
        # Official client alone is not enough: auth, license, and Coding
        # Plan are still unconfirmed, so admission fails closed.
        self.assertEqual(packet["decision"], gca.GLM_NOT_ADMITTED)
        self.assertEqual(packet["terminal_result"], gca.GLM_API_ONLY_TERMINAL)
        self.assertTrue(packet["criteria"]["official_client"]["confirmed"])
        self.assertFalse(packet["criteria"]["auth"]["confirmed"])
        self.assertFalse(packet["criteria"]["license"]["confirmed"])
        self.assertFalse(packet["criteria"]["coding_plan"]["confirmed"])

    def test_admission_packet_never_contains_secrets(self) -> None:
        os.environ["PATH"] = "/usr/bin:/bin"
        packet = gca.evaluate_glm_cli_admission()
        body = json.dumps(packet)
        self.assertNotIn("sk-", body)
        self.assertNotIn("api_key", body.lower())
        self.assertNotIn(".codex", body)


if __name__ == "__main__":
    unittest.main()

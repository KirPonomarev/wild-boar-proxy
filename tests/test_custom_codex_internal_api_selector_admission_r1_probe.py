# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import plistlib
import tempfile
import unittest
from pathlib import Path

from tools.custom_codex_internal_api_selector_admission_r1_probe import (
    FINAL_ADMISSIBLE_STATUS,
    FINAL_BLOCKER_STATUS,
    build_admission_packets,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def write_plist(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(payload, handle)


def make_original_app(root: Path) -> Path:
    original = root / "Codex.app"
    (original / "Contents/MacOS").mkdir(parents=True)
    (original / "Contents/Resources").mkdir(parents=True)
    (original / "Contents/MacOS/Codex").write_text("#!/bin/sh\n", encoding="utf-8")
    (original / "Contents/Resources/app.asar").write_text("original-ui", encoding="utf-8")
    write_plist(
        original / "Contents/Info.plist",
        {
            "CFBundleName": "Codex",
            "CFBundleIdentifier": "com.openai.codex",
            "CFBundleVersion": "1",
            "CFBundleShortVersionString": "1.0",
            "ElectronAsarIntegrity": {"Resources/app.asar": {"hash": "not-a-plain-sha"}},
        },
    )
    return original


def make_custom_wrapper(root: Path, launcher: Path) -> Path:
    custom = root / "Codex Custom.app"
    (custom / "Contents/MacOS").mkdir(parents=True)
    (custom / "Contents/Resources").mkdir(parents=True)
    (custom / "Contents/MacOS/CodexCustom").write_text(
        "#!/bin/bash\nexec \"$HOME/.codex-custom-cli/codex-custom-launch.sh\" desktop \"$@\"\n",
        encoding="utf-8",
    )
    write_plist(
        custom / "Contents/Info.plist",
        {
            "CFBundleName": "Codex Custom",
            "CFBundleDisplayName": "Codex Custom",
            "CFBundleIdentifier": "com.kirill.codexcustom",
        },
    )
    launcher.parent.mkdir(parents=True)
    launcher.write_text(
        "#!/bin/bash\n"
        "PROFILE_DIR=\"$HOME/.codex-custom-cli\"\n"
        "CODEX_APP_BIN=\"/Applications/Codex.app/Contents/MacOS/Codex\"\n"
        "export CODEX_HOME=\"$PROFILE_DIR\"\n"
        "exec \"$CODEX_APP_BIN\" --user-data-dir \"$PROFILE_DIR/electron-user-data\" \"$@\"\n",
        encoding="utf-8",
    )
    return custom


class CustomCodexInternalApiSelectorAdmissionR1ProbeTests(unittest.TestCase):
    def test_wrapper_that_delegates_to_original_asar_blocks_internal_api_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            original = make_original_app(root)
            launcher = root / ".codex-custom-cli/codex-custom-launch.sh"
            custom = make_custom_wrapper(root, launcher)

            packets = build_admission_packets(
                original_app=original,
                custom_app=custom,
                launcher=launcher,
            )

        wrapper = packets["custom_app_wrapper_packet"]
        launcher_packet = packets["launcher_surface_packet"]
        admission = packets["ui_surface_admission_packet"]
        probe_scope = packets["probe_scope_non_claim_packet"]

        self.assertFalse(wrapper["custom_app_has_own_asar"])
        self.assertTrue(wrapper["custom_executable_is_script"])
        self.assertTrue(wrapper["wrapper_delegates_to_custom_launcher"])
        self.assertTrue(launcher_packet["launcher_calls_original_codex_binary"])
        self.assertEqual(admission["final_status"], FINAL_BLOCKER_STATUS)
        self.assertEqual(
            admission["reason_code"],
            "CUSTOM_APP_WRAPPER_DELEGATES_TO_ORIGINAL_ASAR",
        )
        self.assertFalse(admission["admitted"])
        self.assertFalse(admission["can_add_internal_api_selector"])
        self.assertTrue(admission["composer_surface_requires_original_asar_change"])
        self.assertFalse(probe_scope["live_api_call_code_path_present"])
        self.assertFalse(probe_scope["secret_file_read_code_path_present"])
        self.assertFalse(probe_scope["negative_fields_are_host_runtime_monitor_claims"])

    def test_forbidden_runtime_injection_marker_blocks_even_before_ui_reasoning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            original = make_original_app(root)
            launcher = root / ".codex-custom-cli/codex-custom-launch.sh"
            custom = make_custom_wrapper(root, launcher)
            launcher.write_text(
                "DYLD_INSERT_LIBRARIES=/tmp/inject.dylib\n"
                "exec /Applications/Codex.app/Contents/MacOS/Codex \"$@\"\n",
                encoding="utf-8",
            )

            packets = build_admission_packets(
                original_app=original,
                custom_app=custom,
                launcher=launcher,
            )

        launcher_packet = packets["launcher_surface_packet"]
        admission = packets["ui_surface_admission_packet"]

        self.assertTrue(launcher_packet["forbidden_runtime_injection_detected"])
        self.assertIn("DYLD_INSERT_LIBRARIES", launcher_packet["forbidden_runtime_injection_markers"])
        self.assertEqual(admission["final_status"], FINAL_BLOCKER_STATUS)
        self.assertEqual(admission["reason_code"], "FORBIDDEN_RUNTIME_INJECTION_MARKER_PRESENT")
        self.assertFalse(admission["admitted"])

    def test_custom_owned_asar_is_not_automatically_enough_for_success_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            original = make_original_app(root)
            launcher = root / ".codex-custom-cli/codex-custom-launch.sh"
            custom = make_custom_wrapper(root, launcher)
            (custom / "Contents/Resources/app.asar").write_text("custom-ui", encoding="utf-8")

            packets = build_admission_packets(
                original_app=original,
                custom_app=custom,
                launcher=launcher,
            )

        wrapper = packets["custom_app_wrapper_packet"]
        admission = packets["ui_surface_admission_packet"]

        self.assertTrue(wrapper["custom_app_has_own_asar"])
        self.assertEqual(admission["final_status"], FINAL_BLOCKER_STATUS)
        self.assertEqual(
            admission["reason_code"],
            "CUSTOM_APP_OWN_ASAR_REQUIRES_SEPARATE_INTEGRITY_ADMISSION",
        )
        self.assertFalse(admission["admitted"])
        self.assertFalse(admission["api_selector_added"])

    def test_success_branch_requires_own_surface_manifest_and_no_original_delegate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            original = make_original_app(root)
            launcher = root / ".codex-custom-cli/codex-custom-launch.sh"
            custom = make_custom_wrapper(root, launcher)
            (custom / "Contents/Resources/app.asar").write_text("custom-ui", encoding="utf-8")
            (custom / "Contents/MacOS/CodexCustom").write_text(
                "#!/bin/bash\nexec \"$APP_ROOT/Contents/MacOS/CodexCustomReal\" \"$@\"\n",
                encoding="utf-8",
            )
            launcher.write_text(
                "#!/bin/bash\nexport CODEX_HOME=\"$HOME/.codex-custom-cli\"\n"
                "exec \"$HOME/Applications/Codex Custom.app/Contents/MacOS/CodexCustomReal\" "
                "--user-data-dir \"$HOME/.codex-custom-cli/electron-user-data\" \"$@\"\n",
                encoding="utf-8",
            )
            manifest = custom / "Contents/Resources/wbp-api-selector-admission.json"
            manifest.write_text(
                json.dumps(
                    {
                        "surface": "custom_codex_internal_composer_api_selector",
                        "server_catalog_only": True,
                        "browser_raw_backend_details_allowed": False,
                        "requires_original_asar_patch": False,
                        "requires_runtime_injection": False,
                    }
                ),
                encoding="utf-8",
            )

            packets = build_admission_packets(
                original_app=original,
                custom_app=custom,
                launcher=launcher,
            )

        admission = packets["ui_surface_admission_packet"]

        self.assertEqual(admission["final_status"], FINAL_ADMISSIBLE_STATUS)
        self.assertEqual(admission["reason_code"], "CUSTOM_APP_HAS_OWN_ADMITTED_INTERNAL_UI_SURFACE")
        self.assertTrue(admission["admitted"])
        self.assertTrue(admission["can_add_internal_api_selector"])
        self.assertFalse(admission["api_selector_added"])


if __name__ == "__main__":
    unittest.main()

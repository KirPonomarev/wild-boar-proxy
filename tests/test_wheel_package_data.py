# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


class WheelPackageDataTests(unittest.TestCase):
    def test_wheel_includes_web_design_ui_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            wheel_dir = Path(tmp_dir)
            env = {
                **os.environ,
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            }
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "wheel",
                        ".",
                        "--no-deps",
                        "--no-build-isolation",
                        "--wheel-dir",
                        str(wheel_dir),
                    ],
                    cwd=ROOT,
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            finally:
                shutil.rmtree(ROOT / "build", ignore_errors=True)
                shutil.rmtree(ROOT / "wild_boar_proxy.egg-info", ignore_errors=True)

            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            wheels = sorted(wheel_dir.glob("wild_boar_proxy-*.whl"))
            self.assertEqual(len(wheels), 1, [str(path) for path in wheels])
            with zipfile.ZipFile(wheels[0]) as wheel:
                names = set(wheel.namelist())

        required_assets = {
            "wild_boar_proxy/web_design_ui/index.html",
            "wild_boar_proxy/web_design_ui/styles/overview.css",
            "wild_boar_proxy/web_design_ui/scripts/overview.js",
            "wild_boar_proxy/web_design_ui/assets/boar_mark.png",
        }
        self.assertTrue(required_assets.issubset(names), sorted(required_assets - names))


if __name__ == "__main__":
    unittest.main()

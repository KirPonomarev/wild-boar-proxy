import tempfile
from pathlib import Path
import unittest

from wild_boar_proxy.active_project_root import (
    ACTIVE_PROJECT_ROOT_STATUS_BLOCKED_SENSITIVE_NAME,
    ACTIVE_PROJECT_ROOT_STATUS_NOT_DIRECTORY,
    active_project_root_metadata,
)


class ActiveProjectRootTests(unittest.TestCase):
    def test_sensitive_parent_path_is_blocked_without_recording_path(self) -> None:
        for sensitive_parent in [".ssh", "node_modules", ".env.local", "secret-cache"]:
            with self.subTest(sensitive_parent=sensitive_parent):
                with tempfile.TemporaryDirectory() as raw_root:
                    candidate = Path(raw_root) / sensitive_parent / "project"
                    candidate.mkdir(parents=True)

                    selected, fields = active_project_root_metadata(
                        candidate,
                        source="test_selected_active_project_root",
                        wbp_repo_root=Path(raw_root) / "wbp",
                        required=True,
                    )

                self.assertIsNone(selected)
                self.assertFalse(fields["active_project_root_available"])
                self.assertEqual(
                    fields["active_project_root_status"],
                    ACTIVE_PROJECT_ROOT_STATUS_BLOCKED_SENSITIVE_NAME,
                )
                self.assertFalse(fields["active_project_root_path_recorded"])
                self.assertTrue(fields["active_project_root_sha256"])

    def test_file_path_is_blocked_as_not_directory(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            candidate = Path(raw_root) / "project.txt"
            candidate.write_text("not a directory", encoding="utf-8")

            selected, fields = active_project_root_metadata(
                candidate,
                source="test_selected_active_project_root",
                wbp_repo_root=Path(raw_root) / "wbp",
                required=True,
            )

        self.assertIsNone(selected)
        self.assertFalse(fields["active_project_root_available"])
        self.assertEqual(
            fields["active_project_root_status"],
            ACTIVE_PROJECT_ROOT_STATUS_NOT_DIRECTORY,
        )
        self.assertFalse(fields["active_project_root_path_recorded"])


if __name__ == "__main__":
    unittest.main()

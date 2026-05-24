import re
import subprocess
import unittest


FORBIDDEN_PLAN_FILE_PATTERN = re.compile(
    r"(^|/)(MASTER_PLAN|NEXT_CONTOUR_CANON_PLAN|EXECUTION_WAVE_1|"
    r".*[Pp]lan.*|.*master_plan.*|.*roadmap.*|recommended_next_contour|"
    r"next_.*contour|.*next.*contour.*|handoff_to_next_contour)\."
    r"(md|json|txt)$"
)


class RepoHygieneTests(unittest.TestCase):
    def test_tracked_repository_does_not_store_plan_files(self) -> None:
        result = subprocess.run(
            ["git", "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        )
        forbidden = [
            path
            for path in result.stdout.splitlines()
            if FORBIDDEN_PLAN_FILE_PATTERN.search(path)
        ]
        self.assertEqual([], forbidden)


if __name__ == "__main__":
    unittest.main()

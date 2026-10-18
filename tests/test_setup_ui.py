from pathlib import Path
import subprocess
import unittest


class SetupUITests(unittest.TestCase):
    def test_actual_welcome_controller_requires_access_review_and_explicit_save(self):
        result = subprocess.run(['node', 'tests/setup.cjs'], cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

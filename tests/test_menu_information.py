"""Run the actual information controller with isolated UI doubles."""
from pathlib import Path
import subprocess
import unittest


class MenuInformationTests(unittest.TestCase):
    def test_information_navigation_and_folder_demonstration(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ['node', str(root / 'tests/menu-information.cjs')], cwd=root,
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

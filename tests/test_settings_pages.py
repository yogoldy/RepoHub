"""Exercise the shipped settings controller without touching saved app data."""
from pathlib import Path
import subprocess
import unittest


class SettingsPagesTests(unittest.TestCase):
    def test_explicit_save_discard_busy_and_failure_preserve_drafts_and_revision_guards(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ['node', str(root / 'tests/settings-pages.cjs')], cwd=root,
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

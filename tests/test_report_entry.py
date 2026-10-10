"""Reachability and controller behavior are release requirements for both surfaces."""
from pathlib import Path
import subprocess
import unittest

class ReportEntryTests(unittest.TestCase):
    def test_both_surfaces_support_report_compose_preview_and_explicit_send(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['node',str(root/'tests/report-entry.cjs')],cwd=root,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from git_discovery import GitDiscovery


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.parent = self.base / 'repos'; self.parent.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def repo(self, relative):
        path = self.parent / relative; path.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(path)], check=True)
        (path / 'work').write_text('synthetic source')
        return path

    def wait(self, scan):
        deadline = time.monotonic() + 5
        while scan.status()['state'] == 'running' and time.monotonic() < deadline:
            time.sleep(.005)
        self.assertNotEqual(scan.status()['state'], 'running')
        return scan.status()

    def test_recursive_candidates_do_not_modify_sources_and_show_unsupported_layouts(self):
        first = self.repo('Client/App'); nested = self.repo('Client/App/child')
        (self.parent / 'ordinary').mkdir()
        bad = self.parent / 'bad'; bad.mkdir(); (bad / '.git').write_text('not Git')
        external = self.parent / 'worktree'; external.mkdir()
        (external / '.git').write_text('gitdir: ../Client/App/.git')
        before = (first / '.git/config').read_bytes()
        scan = GitDiscovery([]); scan.start(str(self.parent)); status = self.wait(scan)
        results = {row['path']: row for row in status['results']}
        self.assertTrue(results[str(first)]['selectable'])
        self.assertTrue(results[str(nested)]['selectable'])
        self.assertFalse(results[str(bad)]['selectable'])
        self.assertEqual(results[str(external)]['reason'], 'external_git_storage')
        self.assertEqual(before, (first / '.git/config').read_bytes())
        self.assertNotIn(str(self.parent / 'ordinary'), results)

    def test_protected_paths_and_links_are_not_traversed_and_limits_disclosed(self):
        protected = self.repo('backups/Hidden')
        visible = self.repo('visible/App')
        (self.parent / 'loop').symlink_to(self.parent)
        scan = GitDiscovery([protected.parent]); scan.start(str(self.parent))
        status = self.wait(scan)
        self.assertEqual([row['path'] for row in status['results']], [str(visible)])
        bounded = GitDiscovery([], max_directories=1)
        bounded.start(str(self.parent)); status = self.wait(bounded)
        self.assertTrue(status['incomplete'])
        self.assertEqual(status['warnings'][0]['reason'], 'traversal_limit')

    def test_missing_git_cancellation_and_permission_failures_are_not_empty_success(self):
        with patch('git_discovery.shutil.which', return_value=None):
            scan = GitDiscovery([]); scan.start(str(self.parent)); status = self.wait(scan)
        self.assertEqual(status['state'], 'failed')
        scan = GitDiscovery([])
        with scan.lock:
            scan.start(str(self.parent)); scan.cancel(scan.job['id'])
        self.assertEqual(self.wait(scan)['state'], 'cancelled')
        self.repo('denied')
        original = os.scandir
        def denied(path):
            if Path(path).name == 'denied':
                raise PermissionError('synthetic denial')
            return original(path)
        with patch('git_discovery.os.scandir', denied):
            scan = GitDiscovery([]); scan.start(str(self.parent)); status = self.wait(scan)
        self.assertTrue(status['incomplete'])
        self.assertTrue(status['warnings'])

"""Outside-item detection and reviewed choices never follow, copy or change status."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import outside_items
from diagnostics import read_events
from repohub import Hub, Handler, ThreadingHTTPServer, tree_entries, workspace_id

ROOT = Path(__file__).resolve().parents[1]


def git(*args, cwd):
    subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                    *args], cwd=cwd, check=True, capture_output=True)


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.outside = self.base / 'outside'
        self.outside.mkdir()
        (self.outside / 'package.js').write_text('outside bytes')
        self.root = self.base / 'Main'
        self.root.mkdir()
        (self.root / 'work.txt').write_text('work')
        git('init', '-q', str(self.root), cwd=self.base)
        for key in ('maintenance.auto', 'gc.auto'):
            git('config', key, '0', cwd=self.root)
        git('add', '.', cwd=self.root)
        git('commit', '-qm', 'fixture', cwd=self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_links_are_classified_without_following_and_git_internals_are_skipped(self):
        (self.root / 'node_modules').symlink_to(self.outside, target_is_directory=True)
        (self.root / 'python3').symlink_to('/opt/repohub-fixture/missing/python3')
        (self.root / 'notes').symlink_to('../outside/package.js')
        (self.root / 'inside').symlink_to('work.txt')
        (self.root / '.git/info/store').symlink_to(self.outside, target_is_directory=True)
        before = sorted(p.name for p in self.outside.iterdir())
        found = outside_items.detect(self.root, tree_entries(self.root))
        by_path = {item['path']: item for item in found['links']}
        self.assertEqual(set(by_path), {'node_modules', 'python3', 'notes'})
        self.assertEqual(by_path['node_modules']['category'], 'linked_folder')
        self.assertEqual(by_path['python3']['category'], 'reinstall')
        self.assertEqual(by_path['python3']['target_type'], 'missing')
        self.assertEqual(by_path['notes']['category'], 'reinstall')
        self.assertEqual(sorted(p.name for p in self.outside.iterdir()), before)
        self.assertEqual(outside_items.counts(found),
                         {'linked_folders': 1, 'reinstall': 2, 'checkouts': 0, 'removed_checkouts': 0})

    def test_absolute_links_that_stay_inside_the_repo_are_not_outside_items(self):
        # Modeled on build trees that link to their own sources with absolute paths.
        (self.root / 'cache').mkdir()
        (self.root / 'cache/data').write_text('cached')
        (self.root / 'build').mkdir()
        for number in range(3):
            (self.root / 'build' / ('obj%d' % number)).symlink_to(str(self.root / 'cache/data'))
        (self.root / 'cache-link').symlink_to(str(self.root / 'cache'), target_is_directory=True)
        # The temporary folder's unresolved spelling (/var vs /private/var on macOS) is still inside.
        (self.root / 'alias').symlink_to(str(Path(self.temp.name) / 'Main' / 'work.txt'))
        (self.root / 'escape').symlink_to(str(self.root / 'cache' / '..' / '..' / 'outside'),
                                          target_is_directory=True)
        (self.root / 'sibling').symlink_to(str(self.root) + '-sibling/tool')
        found = outside_items.detect(self.root, tree_entries(self.root))
        by_path = {item['path']: item for item in found['links']}
        self.assertEqual(set(by_path), {'escape', 'sibling'})
        self.assertEqual(by_path['escape']['category'], 'linked_folder')
        self.assertEqual(by_path['sibling']['category'], 'reinstall')
        self.assertEqual(outside_items.counts(found),
                         {'linked_folders': 1, 'reinstall': 1, 'checkouts': 0, 'removed_checkouts': 0})

    def test_linked_checkouts_follow_git_registrations_and_removed_folders(self):
        kept, gone = self.base / 'kept', self.base / 'gone'
        git('worktree', 'add', '-q', '-b', 'kept', str(kept), cwd=self.root)
        git('worktree', 'add', '-q', '-b', 'gone', str(gone), cwd=self.root)
        subprocess.run(['rm', '-rf', str(gone)], check=True)
        found = outside_items.detect(self.root, tree_entries(self.root))
        states = {Path(item['path']).name: item['state'] for item in found['checkouts']}
        self.assertEqual(states, {'kept': 'present', 'gone': 'removed'})
        counts = outside_items.counts(found)
        self.assertEqual((counts['checkouts'], counts['removed_checkouts']), (1, 1))
        (kept / 'draft.txt').write_text('uncommitted')
        report = outside_items.review(found, lambda path: {'changed_files': 1})
        present = next(row for row in report['checkouts'] if row['state'] == 'present')
        self.assertEqual(present['changed_files'], 1)
        self.assertGreater(present['bytes'], 0)

    def test_malformed_registration_is_reported_invalid_not_followed(self):
        admin = self.root / '.git/worktrees/bad'
        admin.mkdir(parents=True)
        (admin / 'gitdir').write_text('/not/a/marker\n')
        found = outside_items.detect(self.root, tree_entries(self.root))
        self.assertEqual(found['checkouts'], [{'name': 'bad', 'path': None, 'state': 'invalid'}])

    def test_folder_size_reports_incomplete_totals_as_lower_bounds(self):
        for index in range(5):
            (self.outside / ('f%d' % index)).write_text('x' * 10)
        self.assertEqual(outside_items.folder_size(self.outside, max_entries=2)['complete'], False)
        full = outside_items.folder_size(self.outside)
        self.assertTrue(full['complete'])
        self.assertEqual(full['bytes'], 50 + len('outside bytes'))


class OutsideHubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.outside = self.base / 'outside'
        self.outside.mkdir()
        (self.outside / 'package.js').write_text('PRIVATE OUTSIDE BYTES')
        self.repo = self.base / 'repos/Example'
        self.repo.mkdir(parents=True)
        (self.repo / 'work.txt').write_text('work')
        (self.repo / 'node_modules').symlink_to(self.outside, target_is_directory=True)
        (self.repo / 'tool').symlink_to('/opt/repohub-fixture/missing/tool')
        (self.base / 'cloud').mkdir()
        self.hub = Hub({'repos_root': str(self.base / 'repos'), 'backup_root': str(self.base / 'cloud/Snapshots'),
                        'state_dir': str(self.base / 'state'), 'retention': 'latest'})
        self.key = workspace_id('Example')

    def tearDown(self):
        self.temp.cleanup()

    def row(self):
        return next(row for row in self.hub.status['repos'] if row['id'] == self.key)

    def test_scan_counts_outside_items_and_choices_never_change_backup_need(self):
        self.hub.scan()
        self.assertEqual(self.row()['outside'],
                         {'linked_folders': 1, 'reinstall': 1, 'checkouts': 0, 'removed_checkouts': 0})
        before = (self.row()['needs_backup'], self.row().get('verification'))
        status = self.hub.outside_status(self.key)
        self.hub.save_outside_choices(self.key, {'choices': {'linked_folders': {'node_modules': 'include'},
                                                             'checkouts': 'include'},
                                                 'revision': status['revision']})
        self.hub.scan()
        self.assertEqual(self.row()['needs_backup'], before[0])
        self.assertEqual(self.row()['verification'].get('state'), (before[1] or {}).get('state'))

    def test_review_defaults_and_revision_checked_saves(self):
        status = self.hub.outside_status(self.key)
        self.assertEqual(status['choices'], {'linked_folders': {'node_modules': 'link_only'},
                                             'checkouts': 'committed_only'})
        folder = status['items']['linked_folders'][0]
        self.assertEqual((folder['path'], folder['complete']), ('node_modules', True))
        self.assertNotIn('resolved', folder)
        self.assertEqual([item['path'] for item in status['items']['reinstall']], ['tool'])
        choices = {'linked_folders': {'node_modules': 'include'}, 'checkouts': 'committed_only'}
        saved = self.hub.save_outside_choices(self.key, {'choices': choices, 'revision': status['revision']})
        self.assertEqual(saved['choices'], choices)
        self.assertEqual(os.stat(self.hub.data_dir / 'outside-choices.json').st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            self.hub.save_outside_choices(self.key, {'choices': choices, 'revision': status['revision']})
        current = saved['revision']
        for bad in ({'linked_folders': {'elsewhere': 'include'}, 'checkouts': 'committed_only'},
                    {'linked_folders': {'node_modules': 'copy'}, 'checkouts': 'committed_only'},
                    {'linked_folders': {'../escape': 'include'}, 'checkouts': 'committed_only'},
                    {'linked_folders': {}, 'checkouts': 'all'},
                    {'linked_folders': {}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.hub.save_outside_choices(self.key, {'choices': bad, 'revision': current})
        with self.assertRaises(ValueError):
            self.hub.save_outside_choices(self.key, {'choices': choices, 'revision': current, 'extra': 1})
        with self.assertRaises(ValueError):
            self.hub.outside_status('unknown-repo')
        self.assertEqual(self.hub.outside_status(self.key)['choices'], choices)
        # A removed link drops out of the review instead of keeping a stale choice.
        (self.repo / 'node_modules').unlink()
        self.hub.scan()
        self.assertEqual(self.hub.outside_status(self.key)['choices']['linked_folders'], {})
        logs = ''.join(json.dumps(event) for event in read_events(self.hub.diagnostics.directory))
        self.assertIn('outside_review', logs)
        self.assertNotIn(str(self.outside), logs)
        self.assertNotIn('PRIVATE OUTSIDE BYTES', logs)

    def test_http_routes_keep_token_origin_and_revision_guards(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.hub = self.hub
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = 'http://127.0.0.1:%d' % server.server_port
        path = origin + '/api/outside/' + self.key

        def request(payload=None, token=None):
            headers = {'Origin': origin, 'Content-Type': 'application/json',
                       'X-RepoHub-Token': token if token is not None else self.hub.csrf}
            data = json.dumps(payload).encode() if payload is not None else None
            with urllib.request.urlopen(urllib.request.Request(path, data=data, headers=headers)) as response:
                return json.loads(response.read())

        def status_code(payload, token=None):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                request(payload, token)
            caught.exception.close()
            return caught.exception.code
        try:
            current = request()
            choices = {'linked_folders': {'node_modules': 'include'}, 'checkouts': 'committed_only'}
            self.assertEqual(status_code({'choices': choices, 'revision': current['revision']}, token='wrong'), 403)
            self.assertEqual(status_code({'choices': choices, 'revision': 'stale'}), 409)
            self.assertEqual(status_code({'choices': {'linked_folders': {'x': 'include'}, 'checkouts': 'committed_only'},
                                          'revision': current['revision']}), 400)
            self.assertEqual(request({'choices': choices, 'revision': current['revision']})['choices'], choices)
        finally:
            server.shutdown()
            server.server_close()

    def test_review_page_saves_explicitly_and_preserves_drafts(self):
        result = subprocess.run(['node', str(ROOT / 'tests/outside-items.cjs')], cwd=ROOT,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()

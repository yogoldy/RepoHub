"""Linked checkouts follow Git as separate archives; removed items are kept for 30 days."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from diagnostics import read_events
from repohub import Hub, Handler, ThreadingHTTPServer, sha256, utc_now, workspace_id
import restore_audit as audit

CHECKOUT = '::checkout::'


def git(*args, cwd):
    subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', *args],
                   cwd=cwd, check=True, capture_output=True)


class LinkedCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.repos = self.base / 'repos'
        self.repo = self.repos / 'Example'
        self.repo.mkdir(parents=True)
        (self.repo / 'work.txt').write_text('work')
        git('init', '-q', str(self.repo), cwd=self.base)
        for key in ('maintenance.auto', 'gc.auto'):
            git('config', key, '0', cwd=self.repo)
        git('add', '.', cwd=self.repo)
        git('commit', '-qm', 'fixture', cwd=self.repo)
        self.checkout = self.add('draft')
        (self.checkout / 'notes.txt').write_text('uncommitted draft')
        (self.base / 'cloud/Snapshots').mkdir(parents=True)
        self.config = {'repos_root': str(self.repos), 'backup_root': str(self.base / 'cloud/Snapshots'),
                       'state_dir': str(self.base / 'state'), 'retention': 'latest',
                       'require_upload_before_prune': True, 'cloud_helper': '/nonexistent-test-provider',
                       '_setup_test_cloud_root': str(self.base / 'cloud')}
        self.hub = Hub(self.config)
        self.key = workspace_id('Example')

    def tearDown(self):
        self.temp.cleanup()

    def add(self, name, path=None):
        path = path or self.base / 'worktrees' / name
        git('worktree', 'add', '-q', '-b', name, str(path), cwd=self.repo)
        return path

    def drop(self, path):
        git('worktree', 'remove', '--force', str(path), cwd=self.repo)

    def include(self, choice='include'):
        self.hub.scan()
        status = self.hub.outside_status(self.key)
        choices = {'linked_folders': status['choices']['linked_folders'], 'checkouts': choice}
        return self.hub.save_outside_choices(self.key, {'choices': choices, 'revision': status['revision']})

    def backup(self):
        self.hub.backup()
        self.assertEqual(self.hub.status['backup']['errors'], [])
        return self.hub.index[self.key]

    def row(self):
        return next(row for row in self.hub.status['repos'] if row['id'] == self.key)

    def uploaded(self, key, archive):
        self.hub.cloud_states[key] = {'state': 'uploaded', 'archive': archive, 'checked_at': utc_now()}

    def logs(self):
        return ''.join(json.dumps(event) for event in read_events(self.hub.diagnostics.directory))

    def test_included_checkout_is_its_own_verified_archive_and_restore_receipt(self):
        self.include()
        current = self.backup()
        entry = current['checkouts']['draft']
        self.assertEqual(Path(entry['archive']).parent, Path(current['archive']).parent / 'checkouts/draft')
        self.assertEqual((sha256(entry['archive']), entry['source']), (entry['sha256'], str(self.checkout)))
        with tarfile.open(entry['archive']) as stored:
            members = {member.name: member for member in stored}
        self.assertTrue(members['draft/.git'].isfile())
        self.assertIn('draft/notes.txt', members)
        with tarfile.open(current['archive']) as stored:
            self.assertNotIn('Example/notes.txt', stored.getnames())

        def capture(name, *values):
            args = ['capture', '--source', str(self.repo), '--archive-sha256', current['sha256'],
                    '--out', str(self.base / name)]
            for value in values:
                args += ['--checkout', value]
            return audit.main(args)
        for name, value in (('unknown', 'nope=' + entry['sha256']), ('checksum', 'draft=XYZ')):
            with self.subTest(name=name):
                self.assertEqual(capture(name, value), 1)
                self.assertEqual(json.loads((self.base / name / 'result.json').read_text())['reason'],
                                 'invalid_included_checkouts')
        self.assertEqual(capture('good', 'draft=' + entry['sha256']), 0)
        expected = self.base / 'good/expected.json'
        self.assertEqual(audit.main(['verify', '--archive', current['archive'], '--expected', str(expected),
                                     '--manifest-sha256', audit.digest(expected),
                                     '--out', str(self.base / 'restore')]), 0)
        result = json.loads((self.base / 'restore/result.json').read_text())
        self.assertEqual(result['included_checkouts'], [{'name': 'draft', 'archive_sha256': entry['sha256']}])
        logs = self.logs()
        self.assertIn('included_folder_archived', logs)
        self.assertNotIn(str(self.checkout), logs)

    def test_new_checkouts_are_followed_and_a_removed_one_is_kept_for_30_days(self):
        self.include()
        self.backup()
        later = self.add('later')
        self.hub.scan(force=True)
        self.assertTrue(self.row()['needs_backup'])
        self.assertEqual(self.row()['included_folders']['checkouts'], 2)
        current = self.backup()
        self.assertEqual(set(current['checkouts']), {'draft', 'later'})
        self.assertEqual(current['checkouts']['later']['source'], str(later))
        kept_archive = current['checkouts']['draft']['archive']
        self.drop(self.checkout)
        self.hub.scan(force=True)
        self.assertTrue(self.row()['needs_backup'], 'A removed checkout updates the saved set')
        current = self.backup()
        self.assertEqual(set(current['checkouts']), {'later'})
        kept = current['removed']['checkout:draft']
        self.assertEqual((kept['kind'], kept['name'], kept['reason'], kept['archive']),
                         ('checkouts', 'draft', 'removed', kept_archive))
        window = datetime.fromisoformat(kept['keep_until']) - datetime.fromisoformat(kept['removed_at'])
        self.assertEqual(window, timedelta(days=30))
        self.assertTrue(Path(kept_archive).is_file())
        listed = self.hub.outside_status(self.key)['kept']
        self.assertEqual([(item['item'], item['reason']) for item in listed], [('checkout:draft', 'removed')])
        # Kept items are not part of the uploaded set.
        self.uploaded(self.key, current['archive'])
        self.uploaded(self.key + CHECKOUT + 'later', current['checkouts']['later']['archive'])
        self.assertEqual(self.hub.cloud_for(self.key, current)['state'], 'uploaded')
        self.hub.scan(force=True)
        self.assertFalse(self.row()['needs_backup'])
        self.assertEqual(self.row()['included_folders']['kept'], 1)
        self.assertIn('outside_item_kept', self.logs())

    def test_a_temporarily_missing_checkout_is_kept_and_rejoins_when_it_returns(self):
        self.include()
        first = self.backup()['checkouts']['draft']
        away = self.base / 'away'
        self.checkout.rename(away)
        current = self.backup()
        self.assertNotIn('checkouts', current)
        self.assertEqual(current['removed']['checkout:draft']['reason'], 'removed')
        self.assertTrue(Path(first['archive']).is_file(), 'A missing folder is never deleted immediately')
        away.rename(self.checkout)
        current = self.backup()
        self.assertEqual(current['checkouts']['draft']['archive'], first['archive'], 'The verified archive is reused')
        self.assertNotIn('removed', current)

    def test_keep_window_expires_after_30_days_and_remove_now_deletes_on_request(self):
        self.include()
        self.backup()
        self.drop(self.checkout)
        archive = Path(self.backup()['removed']['checkout:draft']['archive'])
        self.hub.refresh_cloud()
        self.assertTrue(archive.is_file(), 'Nothing is deleted inside the window')
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.hub.index[self.key]['removed']['checkout:draft']['keep_until'] = past
        self.hub.retention = 'all'
        self.hub.refresh_cloud()
        self.assertTrue(archive.is_file(), 'Keep-all retention never deletes on a timer')
        self.hub.retention = 'latest'
        self.hub.refresh_cloud()
        self.assertFalse(archive.exists())
        self.assertNotIn('removed', self.hub.index[self.key])
        self.assertNotIn('removed', json.loads((self.hub.state_dir / 'backups.json').read_text())[self.key])
        self.assertIn('keep_window_expired', self.logs())
        # Remove now is explicit, token-guarded and bound to the exact kept archive.
        other = self.add('other')
        self.backup()
        self.drop(other)
        archive = Path(self.backup()['removed']['checkout:other']['archive'])
        item = self.hub.outside_status(self.key)['kept'][0]
        with self.assertRaises(FileExistsError):
            self.hub.remove_kept(self.key, {'item': item['item'], 'ref': 'stale'})
        with self.hub.backup_lock, self.assertRaises(FileExistsError):
            self.hub.remove_kept(self.key, {'item': item['item'], 'ref': item['ref']})
        self.assertTrue(archive.is_file())
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.hub = self.hub
        threading.Thread(target=server.serve_forever, daemon=True).start()
        origin = 'http://127.0.0.1:%d' % server.server_port

        def post(token):
            headers = {'Origin': origin, 'Content-Type': 'application/json', 'X-RepoHub-Token': token}
            body = json.dumps({'item': item['item'], 'ref': item['ref']}).encode()
            request = urllib.request.Request(origin + '/api/outside/' + self.key + '/remove', data=body, headers=headers)
            with urllib.request.urlopen(request) as response:
                return json.loads(response.read())
        try:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                post('wrong')
            caught.exception.close()
            self.assertEqual(caught.exception.code, 403)
            self.assertTrue(archive.is_file())
            self.assertEqual(post(self.hub.csrf)['kept'], [])
        finally:
            server.shutdown()
            server.server_close()
        self.assertFalse(archive.exists())
        self.assertIn('user_removed', self.logs())

    def test_nested_refused_and_excluded_checkouts(self):
        self.add('nested', self.repo / 'nested')
        risky = self.add('risky', self.base / 'cloud/Snapshots/risky')
        self.include()
        self.hub.backup()
        errors = self.hub.status['backup']['errors']
        self.assertEqual(len(errors), 1)
        self.assertIn('Linked checkout risky', errors[0]['error'])
        self.assertIn('backup destination', errors[0]['error'])
        current = self.hub.index[self.key]
        self.assertEqual(set(current['checkouts']), {'draft'}, 'A nested checkout is already in the repo archive')
        with tarfile.open(current['archive']) as stored:
            self.assertIn('Example/nested/.git', stored.getnames())
        self.include('committed_only')
        current = self.backup()
        self.assertNotIn('checkouts', current)
        self.assertEqual(current['removed']['checkout:draft']['reason'], 'excluded')
        self.assertNotIn(str(risky), self.logs())

    def test_upload_and_pruning_require_the_whole_set_including_checkouts(self):
        self.include()
        current = self.backup()
        entry = current['checkouts']['draft']
        self.uploaded(self.key, current['archive'])
        self.hub.cloud_states[self.key + CHECKOUT + 'draft'] = {'state': 'pending', 'archive': entry['archive'],
                                                               'checked_at': utc_now()}
        combined = self.hub.cloud_for(self.key, current)
        self.assertEqual(combined['state'], 'pending')
        self.assertIn('Linked checkout draft', combined['detail'])
        self.uploaded(self.key + CHECKOUT + 'draft', entry['archive'])
        self.assertEqual(self.hub.cloud_for(self.key, current)['state'], 'uploaded')
        old = entry['archive']
        (self.checkout / 'notes.txt').write_text('second draft')
        current = self.backup()
        new = current['checkouts']['draft']['archive']
        self.assertNotEqual(old, new)
        self.uploaded(self.key, current['archive'])
        self.hub.retain_current(self.key, current)
        self.assertTrue(Path(old).exists(), 'The repo upload alone cannot prune checkout archives')
        self.uploaded(self.key + CHECKOUT + 'draft', new)
        self.hub.retain_current(self.key, current)
        self.assertFalse(Path(old).exists())

    def test_upload_helper_is_asked_about_checkout_archives(self):
        helper, log = self.base / 'helper.py', self.base / 'requests.json'
        helper.write_text('#!' + sys.executable + '\nimport json, sys\nrequests = json.load(sys.stdin)\n'
                          'open(%r, "w").write(json.dumps(requests))\n'
                          'print(json.dumps({r["id"]: {"ubiquitous": True, "uploaded": True} for r in requests}))\n' % str(log))
        helper.chmod(0o700)
        self.hub.config['cloud_helper'] = str(helper)
        self.include()
        current = self.backup()
        self.hub.refresh_cloud()
        requested = {item['id']: item['path'] for item in json.loads(log.read_text())}
        self.assertEqual(requested[self.key + CHECKOUT + 'draft'], current['checkouts']['draft']['archive'])
        self.assertEqual(self.row()['cloud']['state'], 'uploaded')

    def test_setup_layout_change_moves_checkout_and_kept_archives(self):
        self.include()
        later = self.add('later')
        self.backup()
        self.drop(later)
        before = json.loads(json.dumps(self.backup()))
        status = self.hub.setup.status()
        draft = {key: status[key] for key in ['source', 'settings', 'revision', 'discovery_parent']}
        draft['destination'] = str(self.base / 'cloud/Snapshots')
        review = self.hub.setup.review(draft)
        self.hub.setup.apply({'draft': draft, 'review': review['review'], 'backup_now': False})
        current = self.hub.index[self.key]
        folder = self.base / 'cloud/Snapshots/Example'
        self.assertEqual(Path(current['checkouts']['draft']['archive']).parent, folder / 'checkouts/draft')
        self.assertEqual(Path(current['removed']['checkout:later']['archive']).parent, folder / 'checkouts/later')
        for entry in (current['checkouts']['draft'], current['removed']['checkout:later']):
            self.assertEqual(sha256(entry['archive']), entry['sha256'])
        self.assertEqual(current['removed']['checkout:later']['keep_until'],
                         before['removed']['checkout:later']['keep_until'])
        self.hub.scan(force=True)
        self.assertFalse(self.row()['needs_backup'])


if __name__ == '__main__':
    unittest.main()

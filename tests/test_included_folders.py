"""Included linked folders are separate verified archives that count toward Backed up."""
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import time
import unittest

from change_evidence import change_reason, repo_facts
from diagnostics import read_events
from repohub import Hub, sha256, utc_now, workspace_id
import restore_audit as audit

SECRET = 'INCLUDED FOLDER BYTES'
LINKED = '::linked::node_modules'


class IncludedFolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.outside = self.base / 'outside/node_modules'
        self.outside.mkdir(parents=True)
        (self.outside / 'package.js').write_text(SECRET)
        self.repos = self.base / 'repos'
        self.repo = self.repos / 'Example'
        self.repo.mkdir(parents=True)
        (self.repo / 'work.txt').write_text('work')
        (self.repo / 'node_modules').symlink_to(self.outside, target_is_directory=True)
        # A link inside the included folder points back at the repos; it must never be followed.
        (self.outside / 'loop').symlink_to(self.repos, target_is_directory=True)
        (self.base / 'cloud/Snapshots').mkdir(parents=True)
        self.config = {'repos_root': str(self.repos), 'backup_root': str(self.base / 'cloud/Snapshots'),
                       'state_dir': str(self.base / 'state'), 'retention': 'latest',
                       'require_upload_before_prune': True, 'cloud_helper': '/nonexistent-test-provider',
                       '_setup_test_cloud_root': str(self.base / 'cloud')}
        self.hub = Hub(self.config)
        self.key = workspace_id('Example')

    def tearDown(self):
        self.temp.cleanup()

    def include(self, path='node_modules'):
        self.hub.scan()
        status = self.hub.outside_status(self.key)
        choices = {'linked_folders': {**status['choices']['linked_folders'], path: 'include'},
                   'checkouts': 'committed_only'}
        return self.hub.save_outside_choices(self.key, {'choices': choices, 'revision': status['revision']})

    def row(self):
        return next(row for row in self.hub.status['repos'] if row['id'] == self.key)

    def linked(self):
        return self.hub.index[self.key]['linked']['node_modules']

    def uploaded(self, key, archive):
        self.hub.cloud_states[key] = {'state': 'uploaded', 'archive': archive, 'checked_at': utc_now()}

    def logs(self):
        return ''.join(json.dumps(event) for event in read_events(self.hub.diagnostics.directory))

    def test_included_folder_gets_its_own_verified_archive_and_restore_receipt(self):
        self.include()
        self.hub.backup()
        self.assertEqual(self.hub.status['backup']['errors'], [])
        current = self.hub.index[self.key]
        entry = current['linked']['node_modules']
        self.assertEqual(Path(entry['archive']).parent, Path(current['archive']).parent / 'linked/node_modules')
        self.assertEqual(sha256(entry['archive']), entry['sha256'])
        self.assertEqual((entry['source'], entry['target']), (str(self.outside), str(self.outside)))
        with tarfile.open(entry['archive']) as stored:
            members = {member.name: member for member in stored}
        self.assertEqual(members['node_modules/package.js'].size, len(SECRET))
        self.assertTrue(members['node_modules/loop'].issym(), 'Links inside an included folder are stored as links')
        self.assertFalse(any(name.startswith('node_modules/loop/') for name in members))
        with tarfile.open(current['archive']) as stored:
            self.assertTrue(stored.getmember('Example/node_modules').issym(), 'The repo archive format is unchanged')
        # The folder archive restores on its own; the repo receipt names it by link path and checksum.
        self.assertEqual(audit.main(['capture', '--source', str(self.outside), '--archive-sha256', entry['sha256'],
                                     '--out', str(self.base / 'folder-capture')]), 0)
        expected = self.base / 'folder-capture/expected.json'
        self.assertEqual(audit.main(['verify', '--archive', entry['archive'], '--expected', str(expected),
                                     '--manifest-sha256', audit.digest(expected),
                                     '--out', str(self.base / 'folder-verify')]), 0)
        self.assertEqual(audit.main(['capture', '--source', str(self.repo), '--archive-sha256', current['sha256'],
                                     '--include', 'node_modules=' + entry['sha256'],
                                     '--out', str(self.base / 'repo-capture')]), 0)
        expected = self.base / 'repo-capture/expected.json'
        self.assertEqual(audit.main(['verify', '--archive', current['archive'], '--expected', str(expected),
                                     '--manifest-sha256', audit.digest(expected),
                                     '--out', str(self.base / 'repo-verify')]), 0)
        receipt = json.loads((self.base / 'repo-verify/result.json').read_text())['outside_links']
        self.assertTrue(receipt['contents_included'])
        self.assertEqual(receipt['included_archives'], [{'path': 'node_modules', 'archive_sha256': entry['sha256']}])
        logs = self.logs()
        self.assertIn('included_folder_archived', logs)
        self.assertNotIn(str(self.outside), logs)
        self.assertNotIn(SECRET, logs)

    def test_backed_up_requires_every_archive_in_the_set_to_upload(self):
        self.include()
        self.hub.backup()
        current = self.hub.index[self.key]
        entry = current['linked']['node_modules']
        self.uploaded(self.key, current['archive'])
        self.assertEqual(self.hub.cloud_for(self.key, current)['state'], 'unknown')
        for state in ('pending', 'uploading', 'error'):
            self.hub.cloud_states[self.key + LINKED] = {'state': state, 'archive': entry['archive'],
                                                       'checked_at': utc_now(), 'detail': 'synthetic'}
            combined = self.hub.cloud_for(self.key, current)
            self.assertEqual((combined['state'], combined['archive']), (state, current['archive']))
            self.assertIn('Included folder node_modules', combined['detail'])
        self.uploaded(self.key + LINKED, entry['archive'])
        self.assertEqual(self.hub.cloud_for(self.key, current)['state'], 'uploaded')
        # An acknowledgement for any other archive never counts.
        self.uploaded(self.key + LINKED, current['archive'])
        self.assertEqual(self.hub.cloud_for(self.key, current)['state'], 'unknown')

    def test_upload_helper_is_asked_about_every_archive(self):
        helper, log = self.base / 'helper.py', self.base / 'requests.json'
        helper.write_text('#!' + sys.executable + '\nimport json, sys\nrequests = json.load(sys.stdin)\n'
                          'open(%r, "w").write(json.dumps(requests))\n'
                          'print(json.dumps({r["id"]: {"ubiquitous": True, "uploaded": True} for r in requests}))\n' % str(log))
        helper.chmod(0o700)
        self.hub.config['cloud_helper'] = str(helper)
        self.include()
        self.hub.backup()
        self.hub.refresh_cloud()
        current = self.hub.index[self.key]
        requested = {item['id']: item['path'] for item in json.loads(log.read_text())}
        self.assertEqual(requested[self.key + LINKED], current['linked']['node_modules']['archive'])
        self.assertEqual((self.row()['cloud']['state'], self.row()['cloud']['archive']), ('uploaded', current['archive']))

    def test_included_folder_changes_mark_the_repo_for_backup(self):
        self.include()
        self.hub.backup()
        self.hub.scan(force=True)
        self.assertFalse(self.row()['needs_backup'])
        self.assertEqual(self.row()['included_folders'], {'included': 1, 'checkouts': 0, 'pending': 0, 'kept': 0})
        first = self.linked()['archive']
        stamp = time.time() + 5
        os.utime(self.outside / 'package.js', (stamp, stamp))
        self.hub.scan(force=True)
        self.assertTrue(self.row()['needs_backup'])
        self.assertTrue(self.row()['linked_pending'])
        self.assertEqual(change_reason(self.row(), repo_facts(self.row())), 'included_folder_changed')
        self.hub.backup()
        self.assertEqual(self.linked()['archive'], first, 'A timestamp-only change reuses the verified archive')
        self.assertFalse(self.row()['needs_backup'])
        (self.outside / 'package.js').write_text(SECRET + ' changed')
        self.hub.scan(force=True)
        self.assertTrue(self.row()['needs_backup'])
        self.hub.backup()
        self.assertNotEqual(self.linked()['archive'], first)
        self.assertFalse(self.row()['needs_backup'])

    def test_superseded_folder_archives_are_pruned_only_after_the_whole_set_uploads(self):
        self.include()
        self.hub.backup()
        old = self.linked()['archive']
        (self.outside / 'package.js').write_text('second version')
        self.hub.backup()
        current = self.hub.index[self.key]
        new = current['linked']['node_modules']['archive']
        self.assertNotEqual(old, new)
        self.assertTrue(Path(old).exists(), 'An unconfirmed replacement cannot prune')
        self.uploaded(self.key, current['archive'])
        self.hub.retain_current(self.key, current)
        self.assertTrue(Path(old).exists(), 'The repo upload alone cannot prune folder archives')
        stale = json.loads(json.dumps(current))
        stale['linked']['node_modules']['archive'] = old
        with self.assertRaises(ValueError):
            self.hub.retain_current(self.key, stale)
        self.uploaded(self.key + LINKED, new)
        self.hub.retain_current(self.key, current)
        self.assertFalse(Path(old).exists())
        self.assertEqual(sha256(new), current['linked']['node_modules']['sha256'])
        self.assertTrue(Path(current['archive']).exists())

    def test_unsafe_or_duplicate_inclusions_are_refused(self):
        other = self.repos / 'Other'
        other.mkdir()
        (other / 'x.txt').write_text('x')
        (self.repo / 'shared').symlink_to(other, target_is_directory=True)
        (self.repo / 'state').symlink_to(self.base / 'state', target_is_directory=True)
        (self.repo / 'snapshots').symlink_to(self.base / 'cloud', target_is_directory=True)
        (self.repo / 'again').symlink_to(self.outside, target_is_directory=True)
        self.hub.scan()
        status = self.hub.outside_status(self.key)
        blocked = {item['path']: item.get('blocked') for item in status['items']['linked_folders']}
        self.assertIn('monitored repo', blocked['shared'])
        self.assertIn("RepoHub's own data", blocked['state'])
        self.assertIn('backup destination', blocked['snapshots'])
        self.assertIsNone(blocked['node_modules'])
        for path in ('shared', 'state', 'snapshots'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.include(path)
        status = self.hub.outside_status(self.key)
        choices = {'linked_folders': {**status['choices']['linked_folders'], 'node_modules': 'include', 'again': 'include'},
                   'checkouts': 'committed_only'}
        with self.assertRaises(ValueError) as caught:
            self.hub.save_outside_choices(self.key, {'choices': choices, 'revision': status['revision']})
        self.assertIn('another included link', str(caught.exception))
        self.assertEqual(self.hub.outside_status(self.key)['revision'], status['revision'], 'Refused choices are not saved')
        self.assertNotIn(str(other), self.logs())

    def test_a_link_retargeted_after_review_is_reported_and_keeps_the_last_archive(self):
        self.include()
        self.hub.backup()
        first = json.loads(json.dumps(self.linked()))
        other = self.repos / 'Other'
        other.mkdir()
        (other / 'x.txt').write_text('x')
        (self.repo / 'node_modules').unlink()
        (self.repo / 'node_modules').symlink_to(other, target_is_directory=True)
        self.hub.backup()
        errors = self.hub.status['backup']['errors']
        self.assertEqual([error['repo_id'] for error in errors], [self.key])
        self.assertIn('monitored repo', errors[0]['error'])
        self.assertEqual(self.linked(), first, 'The last verified folder archive stays referenced')
        self.assertTrue(Path(first['archive']).exists())
        self.assertTrue(self.row()['needs_backup'])
        logs = self.logs()
        self.assertIn('included_folder_refused', logs)
        self.assertNotIn(str(other), logs)

    def test_setup_layout_change_moves_folder_archives_with_their_repo(self):
        self.include()
        self.hub.backup()
        before = json.loads(json.dumps(self.hub.index[self.key]))
        status = self.hub.setup.status()
        draft = {key: status[key] for key in ['source', 'settings', 'revision', 'discovery_parent']}
        draft['destination'] = str(self.base / 'cloud/Snapshots')
        review = self.hub.setup.review(draft)
        self.hub.setup.apply({'draft': draft, 'review': review['review'], 'backup_now': False})
        current = self.hub.index[self.key]
        entry = current['linked']['node_modules']
        folder = self.base / 'cloud/Snapshots/Example'
        self.assertEqual(Path(current['archive']).parent, folder)
        self.assertEqual(Path(entry['archive']).parent, folder / 'linked/node_modules')
        self.assertEqual(sha256(entry['archive']), before['linked']['node_modules']['sha256'])
        self.assertTrue(self.hub.layout.contains_linked(self.key, 'node_modules', entry['archive']))
        self.assertEqual(self.hub.cloud_for(self.key, current)['state'], 'unknown')
        self.hub.scan(force=True)
        self.assertFalse(self.row()['needs_backup'])

    def test_restore_receipt_refuses_invalid_included_archive_claims(self):
        self.include()
        self.hub.backup()
        current = self.hub.index[self.key]
        checksum = current['linked']['node_modules']['sha256']

        def capture(name, *includes):
            args = ['capture', '--source', str(self.repo), '--archive-sha256', current['sha256'],
                    '--out', str(self.base / name)]
            for value in includes:
                args += ['--include', value]
            return audit.main(args)
        for name, includes in (('unknown', ['work.txt=' + checksum]), ('checksum', ['node_modules=XYZ']),
                               ('twice', ['node_modules=' + checksum] * 2)):
            with self.subTest(name=name):
                self.assertEqual(capture(name, *includes), 1)
                self.assertEqual(json.loads((self.base / name / 'result.json').read_text())['reason'],
                                 'invalid_included_contents')
        self.assertEqual(capture('good', 'node_modules=' + checksum), 0)
        expected = self.base / 'good/expected.json'
        baseline = json.loads(expected.read_text())
        baseline['included_contents'] = {'work.txt': checksum}
        expected.write_text(json.dumps(baseline))
        self.assertEqual(audit.main(['verify', '--archive', current['archive'], '--expected', str(expected),
                                     '--manifest-sha256', audit.digest(expected),
                                     '--out', str(self.base / 'tampered')]), 1)
        self.assertEqual(json.loads((self.base / 'tampered/result.json').read_text())['reason'],
                         'invalid_included_contents')
        self.assertFalse((self.base / 'tampered/restored').exists())


if __name__ == '__main__':
    unittest.main()

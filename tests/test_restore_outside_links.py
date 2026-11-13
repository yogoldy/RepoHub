"""Links that point outside a repo restore as links and are reported, never followed."""
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import io
import unittest
from unittest.mock import patch

from repohub import snapshot
import restore_audit as audit

OUTSIDE_SECRET = 'OUTSIDE CONTENT MUST NOT BE CAPTURED'


class RestoreOutsideLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.outside = self.base / 'outside'
        self.outside.mkdir()
        (self.outside / 'secret.txt').write_text(OUTSIDE_SECRET)
        self.root = self.base / 'Sample'
        self.root.mkdir()
        (self.root / 'work.txt').write_text('work')
        self.git('init', '-q', str(self.root), cwd=self.base)
        for key in ('maintenance.auto', 'gc.auto'):
            self.git('config', key, '0')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        # One linked folder, one dangling tool link, one escaping relative link, one inside link.
        (self.root / 'node_modules').symlink_to(self.outside, target_is_directory=True)
        (self.root / 'bin').mkdir()
        (self.root / 'bin/python3').symlink_to('/opt/repohub-fixture/missing/python3')
        (self.root / 'bin/notes').symlink_to('../../outside/secret.txt')
        (self.root / 'inside').symlink_to('work.txt')
        self.archive = Path(snapshot(self.root, self.base / 'archives',
                                     self.base / 'stage')['archive'])

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args, cwd=None):
        return subprocess.run(
            ['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
             *args], cwd=cwd or self.root, check=True, capture_output=True,
        )

    def capture(self, name='capture'):
        output = self.base / name
        code = audit.main(['capture', '--source', str(self.root), '--archive-sha256',
                           audit.digest(self.archive), '--out', str(output)])
        return code, output

    def verify(self, expected, name='verify'):
        return audit.main(['verify', '--archive', str(self.archive), '--expected', str(expected),
                           '--manifest-sha256', audit.digest(expected),
                           '--out', str(self.base / name)])

    def result(self, name):
        return json.loads((self.base / name / 'result.json').read_text())

    def test_outside_links_restore_exactly_and_are_reported(self):
        outside_before = audit.manifest(self.outside)
        code, output = self.capture()
        self.assertEqual(code, 0)
        expected = output / 'expected.json'
        self.assertNotIn(OUTSIDE_SECRET, expected.read_text())
        baseline = json.loads(expected.read_text())
        self.assertNotIn('node_modules/secret.txt', baseline['entries'])
        self.assertEqual(baseline['outside_links'], [
            {'path': 'bin/notes', 'target': '../../outside/secret.txt',
             'scope': 'relative_escaping', 'target_type': 'file'},
            {'path': 'bin/python3', 'target': '/opt/repohub-fixture/missing/python3',
             'scope': 'absolute', 'target_type': 'missing'},
            {'path': 'node_modules', 'target': str(self.outside),
             'scope': 'absolute', 'target_type': 'directory'},
        ])
        self.assertEqual(self.verify(expected), 0)
        restored = self.base / 'verify/restored'
        for name in ('node_modules', 'bin/python3', 'bin/notes', 'inside'):
            self.assertEqual(os.readlink(restored / name), os.readlink(self.root / name))
        self.assertEqual(audit.manifest(restored), audit.manifest(self.root))
        self.assertEqual(audit.manifest(self.outside), outside_before)
        result = self.result('verify')
        self.assertEqual(result['result'], 'passed')
        self.assertEqual(result['git_history'], 'verified')
        self.assertEqual(result['outside_links']['count'], 3)
        self.assertFalse(result['outside_links']['contents_included'])
        self.assertEqual(result['outside_links']['items'], baseline['outside_links'])
        logs = (self.base / 'verify/events.jsonl').read_text()
        self.assertNotIn(str(self.base), logs)
        self.assertNotIn(OUTSIDE_SECRET, logs)

    def test_forged_entry_beneath_an_outside_link_never_writes_outside(self):
        code, output = self.capture()
        self.assertEqual(code, 0)
        expected = output / 'expected.json'
        baseline = json.loads(expected.read_text())
        # A byte-consistent forged pair tries to write through the linked folder.
        with tarfile.open(self.archive, 'r:gz') as old:
            members = [(m, old.extractfile(m).read() if m.isfile() else None) for m in old]
        with tarfile.open(self.archive, 'w:gz') as new:
            for member, data in members:
                new.addfile(member, io.BytesIO(data) if data is not None else None)
            member = tarfile.TarInfo('Sample/node_modules/planted.txt')
            member.size = 7
            member.mode = 0o644
            new.addfile(member, io.BytesIO(b'planted'))
        baseline['entries']['node_modules/planted.txt'] = {
            'kind': 'file', 'mode': 0o644, 'size': 7,
            'sha256': audit.hashlib.sha256(b'planted').hexdigest()}
        baseline['archive_sha256'] = audit.digest(self.archive)
        expected.write_text(json.dumps(baseline))
        self.assertEqual(self.verify(expected, 'forged'), 1)
        self.assertEqual(self.result('forged')['reason'], 'missing_or_unsafe_parent')
        self.assertFalse((self.outside / 'planted.txt').exists())
        self.assertFalse((self.base / 'forged/restored').exists())

    def test_git_internal_outside_links_stay_rejected_before_git(self):
        (self.root / '.git/info/shared-store').symlink_to(self.outside, target_is_directory=True)
        with patch.object(audit, 'git_facts', side_effect=AssertionError('Git ran')):
            code, output = self.capture('git-internal')
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((output / 'result.json').read_text())['reason'],
                         'external_git_layout')

    def test_tampered_link_report_or_target_fails(self):
        code, output = self.capture()
        self.assertEqual(code, 0)
        expected = output / 'expected.json'
        original = json.loads(expected.read_text())
        report_only = json.loads(json.dumps(original))
        report_only['outside_links'][2]['target'] = '/private/elsewhere'
        expected.write_text(json.dumps(report_only))
        self.assertEqual(self.verify(expected, 'report-tamper'), 1)
        self.assertEqual(self.result('report-tamper')['reason'], 'outside_link_summary_mismatch')
        self.assertFalse((self.base / 'report-tamper/restored').exists())
        # A consistent baseline still cannot redirect a link the archive stored differently.
        both = json.loads(json.dumps(original))
        both['entries']['node_modules']['target'] = '/private/elsewhere'
        both['outside_links'][2]['target'] = '/private/elsewhere'
        expected.write_text(json.dumps(both))
        self.assertEqual(self.verify(expected, 'target-tamper'), 1)
        self.assertEqual(self.result('target-tamper')['reason'], 'symlink_mismatch')

    def test_baseline_without_link_report_still_restores_and_discloses(self):
        code, output = self.capture()
        self.assertEqual(code, 0)
        expected = output / 'expected.json'
        baseline = json.loads(expected.read_text())
        baseline.pop('outside_links')
        expected.write_text(json.dumps(baseline))
        self.assertEqual(self.verify(expected, 'legacy'), 0)
        items = self.result('legacy')['outside_links']['items']
        self.assertEqual(len(items), 3)
        self.assertEqual({item['target_type'] for item in items}, {'not_recorded'})


if __name__ == '__main__':
    unittest.main()

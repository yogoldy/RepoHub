"""Contained Git metadata is recoverable without following other checkouts."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from repohub import snapshot
import restore_audit as audit


class RestoreWorktreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'Main'
        self.root.mkdir()
        self.checkout = self.base / 'outside-checkout'
        self.git('init', '-q', str(self.root), cwd=self.base)
        for key in ('maintenance.auto', 'gc.auto'):
            self.git('config', key, '0')
        (self.root / 'main.txt').write_text('main contents')
        self.git('add', '.')
        self.git('commit', '-qm', 'main fixture')
        self.git('worktree', 'add', '-q', '-b', 'linked', str(self.checkout))
        (self.checkout / 'linked.txt').write_text('linked commit')
        self.git('add', '.', cwd=self.checkout)
        self.git('commit', '-qm', 'linked fixture', cwd=self.checkout)
        (self.checkout / 'uncommitted.txt').write_text('outside contents must stay outside')
        self.metadata = next((self.root / '.git/worktrees').iterdir())
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

    def test_registered_worktree_metadata_restores_without_external_checkout(self):
        before = audit.manifest(self.root)
        code, output = self.capture()
        self.assertEqual(code, 0)
        expected = output / 'expected.json'
        baseline = json.loads(expected.read_text())
        self.assertEqual(baseline['worktree_metadata']['registered_worktrees'], 1)
        self.assertFalse(baseline['worktree_metadata']['linked_checkout_contents_verified'])
        self.assertNotIn('uncommitted.txt', baseline['entries'])
        # The restored repo must not depend on the original checkout still existing.
        shutil.rmtree(self.checkout)
        restored = self.base / 'verify'
        self.assertEqual(audit.main([
            'verify', '--archive', str(self.archive), '--expected', str(expected),
            '--manifest-sha256', audit.digest(expected), '--out', str(restored),
        ]), 0)
        self.assertEqual(audit.manifest(restored / 'restored'), before)
        self.assertEqual(audit.manifest(self.root), before)
        result = json.loads((restored / 'result.json').read_text())
        self.assertEqual(result['git_history'], 'verified')
        self.assertFalse(result['worktree_metadata']['linked_checkout_contents_verified'])

    def test_external_or_malformed_common_directory_is_rejected_before_git(self):
        common = self.metadata / 'commondir'
        for number, value in enumerate((
                '../../../../outside', str(self.root / '.git'), '../../objects', '',
                '../..\nextra', '../..' + 'x' * 4096)):
            with self.subTest(value=value[:30]):
                common.write_text(value)
                with patch.object(audit, 'git_facts', side_effect=AssertionError('Git ran')):
                    code, output = self.capture('bad-' + str(number))
                self.assertEqual(code, 1)
                result = json.loads((output / 'result.json').read_text())
                self.assertEqual(result['reason'], 'invalid_worktree_metadata')

    def test_tampered_archive_common_directory_fails_before_git(self):
        code, output = self.capture()
        self.assertEqual(code, 0)
        expected = output / 'expected.json'
        baseline = json.loads(expected.read_text())
        (self.metadata / 'commondir').write_text('../../../../outside')
        # Forge a byte-consistent input pair: structural Git checks must still reject it.
        self.archive = Path(snapshot(self.root, self.base / 'bad-archives',
                                     self.base / 'bad-stage')['archive'])
        baseline['entries'] = audit.manifest(self.root)
        baseline['archive_sha256'] = audit.digest(self.archive)
        expected.write_text(json.dumps(baseline))
        destination = self.base / 'bad-verify'
        with patch.object(audit, 'git_facts', side_effect=AssertionError('Git ran')):
            code = audit.main(['verify', '--archive', str(self.archive), '--expected',
                               str(expected), '--manifest-sha256', audit.digest(expected),
                               '--out', str(destination)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((destination / 'result.json').read_text())['reason'],
                         'invalid_worktree_metadata')

    def test_linked_root_git_markers_and_common_store_redirection_stay_rejected(self):
        code = audit.main(['capture', '--source', str(self.checkout), '--archive-sha256',
                           audit.digest(self.archive), '--out', str(self.base / 'linked-root')])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((self.base / 'linked-root/result.json').read_text())['reason'],
                         'external_git_layout')
        (self.root / '.git/commondir').write_text('../outside')
        code, output = self.capture('redirected-root')
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((output / 'result.json').read_text())['reason'],
                         'external_git_layout')

    def test_missing_or_symlinked_administrative_files_are_rejected(self):
        marker = self.metadata / 'gitdir'
        original = marker.read_bytes()
        marker.unlink()
        code, output = self.capture('missing-marker')
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((output / 'result.json').read_text())['reason'],
                         'invalid_worktree_metadata')
        (self.metadata / 'saved-marker').write_bytes(original)
        marker.symlink_to('saved-marker')
        code, output = self.capture('symlink-marker')
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((output / 'result.json').read_text())['reason'],
                         'invalid_worktree_metadata')

    def test_invalid_registered_head_is_not_a_successful_git_audit(self):
        (self.metadata / 'HEAD').write_text('not a Git object or ref\n')
        code, output = self.capture('invalid-head')
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((output / 'result.json').read_text())['reason'],
                         'git_check_failed')


class ContainedCheckoutTests(unittest.TestCase):
    """Worktrees kept in folders inside the repo, as Claude Code creates them."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'Main'
        self.root.mkdir()
        self.git('init', '-q', str(self.root), cwd=self.base)
        for key in ('maintenance.auto', 'gc.auto'):
            self.git('config', key, '0')
        (self.root / 'main.txt').write_text('main contents')
        self.git('add', '.')
        self.git('commit', '-qm', 'main fixture')

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args, cwd=None):
        return subprocess.run(
            ['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
             *args], cwd=cwd or self.root, check=True, capture_output=True,
        )

    def add_inside_checkout(self, name='feature', relative_paths=False):
        checkout = self.root / '.claude/worktrees' / name
        options = ['-c', 'worktree.useRelativePaths=true'] if relative_paths else []
        self.git(*options, 'worktree', 'add', '-q', '-b', name, str(checkout))
        (checkout / 'work.txt').write_text('uncommitted work inside the repo')
        return checkout

    def capture(self, name):
        self.archive = Path(snapshot(self.root, self.base / (name + '-archives'),
                                     self.base / (name + '-stage'))['archive'])
        output = self.base / name
        code = audit.main(['capture', '--source', str(self.root), '--archive-sha256',
                           audit.digest(self.archive), '--out', str(output)])
        return code, output

    def verify(self, capture, name):
        expected = capture / 'expected.json'
        code = audit.main(['verify', '--archive', str(self.archive), '--expected', str(expected),
                           '--manifest-sha256', audit.digest(expected), '--out', str(self.base / name)])
        return code, json.loads((self.base / name / 'result.json').read_text())

    def reason(self, output):
        return json.loads((output / 'result.json').read_text())['reason']

    def test_checkouts_inside_the_repo_restore_and_are_compared(self):
        self.add_inside_checkout('absolute')
        self.add_inside_checkout('relative', relative_paths=True)
        code, output = self.capture('capture')
        self.assertEqual(code, 0)
        baseline = json.loads((output / 'expected.json').read_text())
        self.assertEqual(baseline['contained_checkouts'], {
            '.claude/worktrees/absolute/.git': 'absolute',
            '.claude/worktrees/relative/.git': 'relative'})
        # The checkout files are part of the archive and the byte-for-byte comparison.
        self.assertIn('.claude/worktrees/absolute/work.txt', baseline['entries'])
        code, result = self.verify(output, 'verify')
        self.assertEqual(code, 0)
        self.assertEqual(result['git_history'], 'verified')
        self.assertEqual(result['worktree_metadata']['checkouts_inside_repo'], 2)
        self.assertEqual(audit.manifest(self.base / 'verify/restored'), audit.manifest(self.root))

    def test_pointer_to_another_repo_or_mismatched_back_pointer_is_refused(self):
        checkout = self.add_inside_checkout()
        pointer = checkout / '.git'
        original = pointer.read_text()
        # Same layout, but naming another repo's worktree registration.
        pointer.write_text('gitdir: ' + str(self.base / 'Other/.git/worktrees/feature') + '\n')
        code, output = self.capture('other-repo')
        self.assertEqual(code, 1)
        self.assertEqual(self.reason(output), 'external_git_layout')
        pointer.write_text(original)
        # The registration must name this exact .git file back.
        gitdir = self.root / '.git/worktrees/feature/gitdir'
        gitdir.write_text(str(self.root / 'somewhere-else/.git') + '\n')
        code, output = self.capture('back-pointer')
        self.assertEqual(code, 1)
        self.assertEqual(self.reason(output), 'external_git_layout')

    def test_baseline_without_the_pairing_is_refused_before_extraction(self):
        self.add_inside_checkout()
        code, output = self.capture('capture')
        self.assertEqual(code, 0)
        expected = output / 'expected.json'
        baseline = json.loads(expected.read_text())
        baseline.pop('contained_checkouts')
        expected.write_text(json.dumps(baseline))
        code, result = self.verify(output, 'stripped')
        self.assertEqual(code, 1)
        self.assertEqual(result['reason'], 'external_git_layout')
        self.assertFalse((self.base / 'stripped/restored').exists())

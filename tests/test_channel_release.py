import base64
import copy
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tools.channel_policy import (
    ACCEPTANCE_CASES, DEV_CHECKS, channel_plan, feed_url, require_acceptance,
    require_focused_gate, require_full_gate, require_promotion, require_testing_run, validate_channel_receipt,
)
from tools.channel_release import (
    ChannelGitHub, LOCK_REF, confirm_uploaded, feed_stage, promote,
    publish_candidate, verify_archive_signature, verify_package, write_proof,
)
from tools.package_app import sha256
from tools.release_policy import release_number, release_plan
from tools.update_feed import appcast
from tools.publish_release import main as retired_publisher

SHA = 'a' * 40


def fixture(folder, stage='dev', distribution='developer_id', build=8):
    plan = channel_plan(build, SHA, stage)
    archive = folder / plan['archive']
    archive.write_bytes(b'controlled immutable archive')
    receipt = dict(plan, distribution=distribution, notarized=distribution == 'developer_id',
                   test_only=False, archive_sha256=sha256(archive), archive_bytes=archive.stat().st_size)
    (folder / 'release-receipt.json').write_text(json.dumps(receipt))
    info = {'CFBundleIdentifier': 'com.leogoldberg.repohub', 'SUPublicEDKey': base64.b64encode(b'x' * 32).decode(),
            'CFBundleName': 'Repo Hub', 'CFBundleVersion': plan['build'],
            'CFBundleShortVersionString': plan['version'], 'LSMinimumSystemVersion': '13.0'}
    (folder / 'appcast.xml').write_bytes(appcast(info, plan['archive_url'],
        base64.b64encode(b's' * 64).decode(), receipt['archive_bytes'], stage))
    write_proof(folder, receipt, stage, 123 if stage == 'testing' else None)
    return receipt


def gate(revision=SHA):
    from tools.release_gate import REGISTER, validate_register
    rules = validate_register(json.loads(REGISTER.read_text()))
    return {'result': 'passed', 'profile': 'macos', 'source_commit': revision,
            'dirty_source': False, 'source_unchanged': True,
            'python': {'successful': True, 'skipped': 0, 'tests_run': 1,
                'outcomes': {name: 'passed' for rule in rules for name in rule['test_ids']}},
            'rules': [{'id': rule['id'], 'result': 'passed'} for rule in rules],
            'commands': [{'check': name, 'result': 'passed'} for name in (
                'native-app-build', 'coordinated-sparkle-package', 'github-workflow-syntax',
                'bridge-checks', 'updater-settings-checks')]}


def acceptance(receipt):
    return {**{key: receipt[key] for key in ('source_revision', 'build', 'archive_sha256')},
            'schema': 1, 'hosts': {
                'pro': {case: 'passed' for case in ACCEPTANCE_CASES},
                'air': {case: 'passed' for case in ACCEPTANCE_CASES | {'onboarding'}},
            }}


class FakeChannelGitHub:
    def __init__(self, folder, fail=''):
        self.remote = {path.name: path.read_bytes() for path in folder.iterdir()}
        self.events = []
        self.fail = fail
        self.latest_tag = 'repohub-v0.0.7-b7'

    def event(self, name):
        self.events.append(name)
        if name == self.fail:
            raise ValueError('controlled_' + name)

    def latest(self):
        return {'tag_name': self.latest_tag}

    def upload(self, plan, folder):
        self.event('upload')
        self.remote = {path.name: path.read_bytes() for path in folder.iterdir()}

    def download(self, tag, folder):
        self.event('download')
        for name, content in self.remote.items():
            (folder / name).write_bytes(content)
        if self.fail == 'corrupt-download':
            (folder / 'appcast.xml').write_text('<invalid/>')

    def publish_candidate(self, plan):
        self.event('publish-candidate')

    def confirm_source_tag(self, receipt):
        self.event('source-tag')

    def publish_feed(self, stage, receipt, folder):
        self.event('feed-' + stage)
        if stage == 'stable':
            self.latest_tag = receipt['tag']

    def testing_run(self, run_id, revision):
        self.event('testing-run')

    def stable_source(self, run_id, revision):
        self.event('protected-main')
        return SHA

    def replace_promotion_metadata(self, tag, folder):
        self.event('metadata')
        for name in ('appcast.xml',):
            self.remote[name] = (folder / name).read_bytes()


class ChannelReleaseTests(unittest.TestCase):
    def test_workflow_targets_testing_and_legacy_stable_entry_is_disabled(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/publish-update.yml').read_text()
        self.assertIn('tools/channel_release.py testing --publish', workflow)
        self.assertIn('release_gate.py --require-clean', workflow)
        self.assertIn('ref: ${{ github.event.workflow_run.head_sha }}', workflow)
        self.assertNotIn('--to stable', workflow)
        self.assertNotIn('tools/publish_release.py --run-id', workflow)
        with self.assertRaisesRegex(ValueError, 'legacy_stable_publication_disabled'):
            retired_publisher()

    def test_immutable_release_settings_are_checked_without_disabling_them(self):
        github = ChannelGitHub()
        with patch.object(github, 'api', return_value={'enabled': False, 'enforced_by_owner': False}), \
                patch.object(github, 'write') as mutation:
            github.require_mutable_repository()
            mutation.assert_not_called()
        for settings in ({'enabled': True, 'enforced_by_owner': False}, {},
                         {'enabled': False, 'enforced_by_owner': True}):
            with patch.object(github, 'api', return_value=settings), patch.object(github, 'write') as mutation:
                with self.assertRaises(ValueError):
                    github.require_mutable_repository()
                mutation.assert_not_called()
        with patch.object(github, 'latest', return_value={'immutable': False}), \
                patch.object(github, 'releases', return_value=[]), patch.object(github, 'api') as admin:
            github.require_mutable_repository(hosted=True)
            admin.assert_not_called()
        with patch.object(github, 'assert_lock'), patch.object(github, 'api', return_value={
                'draft': False, 'prerelease': True, 'immutable': True}), \
                patch('tools.channel_release.command'):
            with self.assertRaisesRegex(ValueError, 'no_feed_change'):
                github.publish_candidate(channel_plan(8, SHA, 'testing'))

    def test_fixed_feeds_global_build_numbers_and_failed_draft_reservations(self):
        self.assertNotEqual(feed_url('dev'), feed_url('testing'))
        self.assertIn('/latest/', feed_url('stable'))
        history = [{'tag_name': channel_plan(8, SHA, 'dev')['tag'], 'draft': True},
                   {'tag_name': 'repohub-channel-dev'}]
        self.assertEqual(release_plan(history, SHA)['build'], '9')
        self.assertIsNone(release_number(history[1]))
        for wrong in ('beta', '', None, []):
            with self.assertRaises(ValueError):
                feed_url(wrong)
        with self.assertRaises(ValueError):
            channel_plan(9, SHA, 'stable')

    def test_testing_requires_exact_successful_nonfork_push_and_real_contract(self):
        run = {'head_branch': 'codex/feature', 'event': 'push', 'status': 'completed',
               'conclusion': 'success', 'path': '.github/workflows/golden-rules.yml',
               'repository': {'full_name': 'yogoldy/RepoHub'},
               'head_repository': {'full_name': 'yogoldy/RepoHub'}, 'head_sha': SHA}
        jobs = [{'name': 'automated-contract', 'status': 'completed', 'conclusion': 'success'}]
        require_testing_run(run, jobs, SHA)
        for field, value in [('head_sha', 'b' * 40), ('event', 'pull_request'),
                             ('head_branch', 'foreign'), ('conclusion', 'failure'),
                             ('head_repository', {'full_name': 'fork/RepoHub'})]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                require_testing_run(dict(run, **{field: value}), jobs, SHA)
        for invalid in ([], jobs * 2, [dict(jobs[0], conclusion='skipped')]):
            with self.assertRaises(ValueError):
                require_testing_run(run, invalid, SHA)

    def test_dev_gate_cannot_be_missing_skipped_stale_dirty_or_full_gate_substitute(self):
        value = {'profile': 'dev', 'result': 'passed', 'source_commit': SHA,
                 'dirty_source': False, 'source_unchanged': True, 'patterns': list(DEV_CHECKS),
                 'tests_run': 1, 'skipped': 0, 'native_build': True, 'source_digest': 'b' * 64}
        require_focused_gate(value, SHA)
        for field, replacement in [('patterns', []), ('tests_run', 0), ('skipped', 1),
                ('source_commit', 'b' * 40), ('dirty_source', True), ('native_build', False),
                ('profile', 'macos'), ('source_unchanged', False), ('source_digest', '')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                require_focused_gate(dict(value, **{field: replacement}), SHA)

    def test_dev_gate_writes_private_failure_receipt_when_source_changes(self):
        from tools.dev_gate import run
        result = SimpleNamespace(testsRun=8, skipped=[], expectedFailures=[], wasSuccessful=lambda: True)
        dummy = unittest.TestSuite([unittest.FunctionTestCase(lambda: None)])
        def git(arguments, **kwargs):
            return SHA if arguments[1] == 'rev-parse' else b''
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'receipt.json'
            with patch('tools.dev_gate.platform.system', return_value='Darwin'), \
                    patch('tools.dev_gate.platform.machine', return_value='arm64'), \
                    patch('tools.dev_gate.source_fingerprint', side_effect=['a' * 64, 'b' * 64]), \
                    patch('tools.dev_gate.subprocess.check_output', side_effect=git), \
                    patch('tools.dev_gate.subprocess.run'), \
                    patch('tools.dev_gate.unittest.defaultTestLoader.discover', return_value=dummy), \
                    patch('tools.dev_gate.unittest.TextTestRunner') as runner:
                runner.return_value.run.return_value = result
                with self.assertRaisesRegex(ValueError, 'source_changed'):
                    run(output)
            receipt = json.loads(output.read_text())
            self.assertEqual(receipt['result'], 'failed')
            self.assertFalse(receipt['source_unchanged'])
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_full_gate_requires_executed_rules_and_native_package_workflow_commands(self):
        receipt = gate()
        require_full_gate(receipt, SHA)
        for field in ('rules', 'commands', 'python'):
            changed = dict(receipt, **{field: {} if field == 'python' else []})
            with self.assertRaises(ValueError):
                require_full_gate(changed, SHA)
        changed = copy.deepcopy(receipt)
        name = next(iter(changed['python']['outcomes']))
        changed['python']['outcomes'][name] = 'skipped'
        with self.assertRaises(ValueError):
            require_full_gate(changed, SHA)

    def test_candidate_publication_compares_download_before_feed_without_moving_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            receipt = fixture(folder)
            github = FakeChannelGitHub(folder)
            checks = []
            result = publish_candidate(github, receipt, folder, lambda: checks.append(True))
            self.assertEqual(result['channel'], 'dev')
            self.assertEqual(len(checks), 2)
            self.assertEqual(github.events, ['upload', 'download', 'publish-candidate', 'source-tag', 'feed-dev'])
            self.assertEqual(github.latest_tag, 'repohub-v0.0.7-b7')
            for failure in ('upload', 'corrupt-download', 'source-tag'):
                github = FakeChannelGitHub(folder, failure)
                with self.assertRaises(ValueError):
                    publish_candidate(github, receipt, folder, lambda: None)
                self.assertNotIn('feed-dev', github.events)

    def test_promotions_are_sequential_and_testing_preserves_archive_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            receipt = fixture(folder)
            proof = verify_package(folder)[1]
            github = FakeChannelGitHub(folder)
            original = (folder / receipt['archive']).read_bytes()
            promote(github, folder, receipt, proof, 'testing', gate(), 123)
            self.assertEqual(original, (folder / receipt['archive']).read_bytes())
            self.assertEqual(github.remote[receipt['archive']], original)
            self.assertEqual(feed_stage((folder / 'appcast.xml').read_bytes())[0], 'testing')
            self.assertNotIn('upload', github.events)
            self.assertIn('feed-testing', github.events)
        for current, target in [('dev', 'stable'), ('stable', 'dev'), ('testing', 'dev')]:
            with self.assertRaises(ValueError):
                require_promotion(current, target)

    def test_stable_requires_exact_approval_both_hosts_notarization_and_protected_main(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            receipt = fixture(folder, 'testing')
            proof = verify_package(folder)[1]
            path = folder.parent / (folder.name + '-acceptance.json')
            try:
                path.write_text(json.dumps(acceptance(receipt)))
                for changed in (dict(receipt, distribution='personal_adhoc', notarized=False),
                                dict(receipt, notarized=False)):
                    with self.assertRaises(ValueError):
                        require_acceptance(acceptance(receipt), changed)
                for field in ('build', 'archive_sha256', 'source_revision'):
                    value = acceptance(receipt)
                    value[field] = 'wrong'
                    with self.assertRaises(ValueError):
                        require_acceptance(value, receipt)
                value = acceptance(receipt)
                value['hosts']['air']['permissions'] = 'pending'
                with self.assertRaises(ValueError):
                    require_acceptance(value, receipt)
                with self.assertRaisesRegex(ValueError, 'approval'):
                    promote(FakeChannelGitHub(folder), folder, receipt, proof, 'stable', gate(), 124, path)
                github = FakeChannelGitHub(folder, 'protected-main')
                with self.assertRaises(ValueError):
                    promote(github, folder, receipt, proof, 'stable', gate(), 124, path, receipt['tag'])
                self.assertNotIn('metadata', github.events)
                github = FakeChannelGitHub(folder)
                github.latest_tag = 'repohub-v0.0.9-b9'
                with self.assertRaisesRegex(ValueError, 'regress'):
                    promote(github, folder, receipt, proof, 'stable', gate(), 124, path, receipt['tag'])
                self.assertNotIn('metadata', github.events)
                github = FakeChannelGitHub(folder)
                promote(github, folder, receipt, proof, 'stable', gate(), 124, path, receipt['tag'])
                self.assertEqual(github.latest_tag, receipt['tag'])
                self.assertNotIn('upload', github.events)
                verify_package(folder, 'stable')
            finally:
                path.unlink(missing_ok=True)

    def test_interrupted_promotion_needs_explicit_resume_and_rechecks_requirements(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            receipt = fixture(folder)
            proof = verify_package(folder)[1]
            github = FakeChannelGitHub(folder, 'feed-testing')
            with self.assertRaises(ValueError):
                promote(github, folder, receipt, proof, 'testing', gate(), 123)
            current = verify_package(folder)[1]
            with self.assertRaises(ValueError):
                promote(github, folder, receipt, current, 'testing', gate(), 123)
            github.fail = ''
            promote(github, folder, receipt, current, 'testing', gate(), 123, resume=True)
            self.assertGreaterEqual(github.events.count('testing-run'), 4)
            self.assertEqual(github.remote[receipt['archive']], (folder / receipt['archive']).read_bytes())

    def test_wrong_channel_or_changed_archive_and_extra_assets_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            receipt = fixture(folder)
            verify_package(folder, 'dev')
            with self.assertRaises(ValueError):
                verify_package(folder, 'testing')
            (folder / 'private.key').write_text('synthetic-only')
            with self.assertRaises(ValueError):
                verify_package(folder)
            (folder / 'private.key').unlink()
            (folder / receipt['archive']).write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                verify_package(folder)

    def test_candidate_checks_draft_metadata_without_requiring_a_published_tag(self):
        plan = channel_plan(9, SHA, 'dev')
        github = ChannelGitHub()
        draft = {'isDraft': True, 'isPrerelease': True, 'targetCommitish': SHA,
                 'tagName': plan['tag']}

        def api(endpoint):
            if endpoint == 'git/matching-refs/tags/' + plan['tag']:
                return []  # GitHub has not created the draft's Git tag yet.
            raise RuntimeError('controlled_github_draft_tag_lookup_404')

        def run_candidate(metadata):
            def command(arguments, **kwargs):
                if arguments[:3] == ['gh', 'release', 'create']:
                    return ''
                if arguments[:3] == ['gh', 'release', 'view']:
                    return json.dumps(metadata)
                raise AssertionError('unexpected_command')
            with patch.object(github, 'assert_lock'), \
                    patch.object(github, 'api', side_effect=api), \
                    patch('tools.channel_release.command', side_effect=command) as commands:
                github.create_candidate(plan)
            return [call.args[0] for call in commands.call_args_list]

        calls = run_candidate(draft)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][calls[0].index('--target') + 1], SHA)
        for flag in ('--draft', '--prerelease', '--latest=false'):
            self.assertIn(flag, calls[0])
        self.assertEqual(calls[1][:4], ['gh', 'release', 'view', plan['tag']])
        for field, value in (('isDraft', False), ('isPrerelease', False),
                             ('targetCommitish', 'main'), ('tagName', 'foreign')):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'exact_candidate_draft'):
                run_candidate(dict(draft, **{field: value}))
        with patch.object(github, 'assert_lock'), patch.object(github, 'api',
                return_value=[{'ref': 'refs/tags/' + plan['tag']}]), \
                patch('tools.channel_release.command') as command:
            with self.assertRaisesRegex(ValueError, 'already_reserved'):
                github.create_candidate(plan)
            command.assert_not_called()

    def test_repository_lock_is_exclusive_and_never_removes_another_owners_lock(self):
        github = ChannelGitHub()
        calls = []
        def write(endpoint, payload=None, method='POST'):
            calls.append((endpoint, method))
            return {'sha': 'owned-lock'}
        with patch.object(github, 'write', side_effect=write), patch.object(github, 'api',
                return_value={'object': {'sha': 'owned-lock'}}):
            with github.locked(SHA):
                github.assert_lock()
        self.assertEqual(calls[-1], ('git/refs/' + LOCK_REF, 'DELETE'))
        calls.clear()
        with patch.object(github, 'write', side_effect=write), patch.object(github, 'api',
                return_value={'object': {'sha': 'someone-else'}}):
            with self.assertRaises(ValueError), github.locked(SHA):
                pass
        self.assertNotIn(('git/refs/' + LOCK_REF, 'DELETE'), calls)

    def test_pointer_is_a_prerelease_never_latest_and_retries_only_identical_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            receipt = fixture(folder)
            raw = (folder / 'appcast.xml').read_bytes()
            github = ChannelGitHub()
            calls = []
            def command(arguments, **kwargs):
                calls.append(arguments)
                if arguments[:3] == ['gh', 'release', 'download']:
                    output = Path(arguments[arguments.index('--dir') + 1])
                    (output / 'appcast.xml').write_bytes(raw)
                return ''
            pointer = {'tag_name': 'repohub-channel-dev', 'draft': False, 'prerelease': True}
            with patch.object(github, 'assert_lock'), patch.object(github, 'releases', return_value=[]), \
                    patch('tools.channel_release.command', side_effect=command):
                github.publish_feed('dev', receipt, folder)
            edits = [call for call in calls if call[:3] in (['gh', 'release', 'create'], ['gh', 'release', 'edit'])]
            self.assertTrue(edits)
            self.assertTrue(all('--latest=false' in call and '--prerelease' in call for call in edits))
            calls.clear()
            with patch.object(github, 'assert_lock'), patch.object(github, 'releases', return_value=[pointer]), \
                    patch('tools.channel_release.command', side_effect=command):
                github.publish_feed('dev', receipt, folder)
                self.assertEqual(len(calls), 1)  # Identical feed is already confirmed; no mutation.
                newer = dict(receipt, build='7')
                with self.assertRaises(ValueError):
                    github.publish_feed('dev', newer, folder)
            self.assertFalse(any(call[:3] == ['gh', 'release', 'upload'] for call in calls))
            calls.clear()
            with patch.object(github, 'assert_lock'), patch.object(github, 'latest', return_value={'tag_name': receipt['tag']}), \
                    patch('tools.channel_release.command', side_effect=command):
                github.publish_feed('stable', receipt, folder)
            self.assertEqual(len(calls), 1)
            self.assertIn('--prerelease=false', calls[0])
            self.assertIn('--latest', calls[0])
            self.assertEqual(calls[0][calls[0].index('--title') + 1], 'RepoHub ' + receipt['version'])

    def test_stable_requires_main_ancestry_and_identical_tree_and_never_regresses(self):
        github = ChannelGitHub()
        main = 'b' * 40
        def api(endpoint):
            if endpoint == 'git/ref/heads/main':
                return {'object': {'sha': main}}
            if endpoint.startswith('commits/'):
                return {'commit': {'tree': {'sha': 'same'}}}
            return {'status': 'ahead'}
        with patch.object(github, 'assert_source') as gate_check, patch.object(github, 'api', side_effect=api):
            self.assertEqual(github.stable_source(123, SHA), main)
            gate_check.assert_called_once_with(123, main)
        def changed_tree(endpoint):
            value = api(endpoint)
            return {'commit': {'tree': {'sha': 'changed'}}} if endpoint == 'commits/' + main else value
        with patch.object(github, 'assert_source'), patch.object(github, 'api', side_effect=changed_tree):
            with self.assertRaisesRegex(ValueError, 'tree'):
                github.stable_source(123, SHA)
        def diverged(endpoint):
            return {'status': 'diverged'} if endpoint.startswith('compare/') else api(endpoint)
        with patch.object(github, 'assert_source'), patch.object(github, 'api', side_effect=diverged):
            with self.assertRaisesRegex(ValueError, 'protected_main'):
                github.stable_source(123, SHA)

    @unittest.skipUnless(platform.system() == 'Darwin', 'Native signature verifier requires macOS')
    def test_promotion_authenticates_archive_using_public_key_without_private_key(self):
        # RFC 8032 test 2: one-byte message, public key and signature only.
        key = bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')
        signature = bytes.fromhex('92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da'
                                  '085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00')
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            receipt = fixture(folder)
            archive = folder / receipt['archive']
            archive.write_bytes(bytes.fromhex('72'))
            receipt.update(archive_bytes=1, archive_sha256=sha256(archive))
            (folder / 'release-receipt.json').write_text(json.dumps(receipt))
            (folder / 'channel-proof.json').unlink()
            raw = (folder / 'appcast.xml').read_bytes().replace(base64.b64encode(b's' * 64), base64.b64encode(signature))
            raw = raw.replace(b'length="27"', b'length="1"')
            # Use XML to set exact size rather than depending on fixture byte count.
            import xml.etree.ElementTree as ET
            root = ET.fromstring(raw)
            root.find('channel/item/enclosure').set('length', '1')
            (folder / 'appcast.xml').write_bytes(ET.tostring(root))
            write_proof(folder, receipt, 'dev')
            with patch.dict(os.environ, {'REPOHUB_UPDATE_PUBLIC_KEY': base64.b64encode(key).decode()}):
                verify_archive_signature(folder)
                archive.write_bytes(b'x')
                receipt['archive_sha256'] = sha256(archive)
                (folder / 'release-receipt.json').write_text(json.dumps(receipt))
                (folder / 'channel-proof.json').unlink()
                write_proof(folder, receipt, 'dev')
                with self.assertRaises(RuntimeError):
                    verify_archive_signature(folder)

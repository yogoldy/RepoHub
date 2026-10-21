#!/usr/bin/env python3
"""Publish local Dev, gated Testing, or explicitly promote an unchanged package.

All mutations require --publish and REPOHUB_RELEASE_ENABLED=true. This command
never installs an app, changes a Mac's channel, or configures signing credentials.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.channel_policy import (
    channel_plan, feed_url, require_acceptance, require_focused_gate, require_full_gate,
    require_promotion, require_testing_run, validate_channel_receipt,
)
from tools.package_app import sha256
from tools.publish_release import (
    GitHub, build_artifacts, command, personal_signing_material, require_gate,
    selected_mode, signing_material,
)
from tools.release_policy import REPOSITORY, release_number
from tools.release_gate import source_fingerprint
from tools.update_feed import SPARKLE

POINTER_PREFIX = 'repohub-channel-'
LOCK_REF = 'tags/repohub-channel-publisher-lock'
PROOF_NAMESPACE = 'https://repohub.invalid/update-proof/v1'


def feed_stage(raw):
    root = ET.fromstring(raw)
    items = root.findall('channel/item')
    if len(items) != 1:
        raise ValueError('single_channel_item_required')
    stage = items[0].findtext('{' + SPARKLE + '}channel') or 'stable'
    if stage not in ('dev', 'testing', 'stable'):
        raise ValueError('unsupported_update_channel')
    return stage, items[0]


def verify_package(folder, expected_stage=None):
    entries = {path.name for path in folder.iterdir()}
    receipt = validate_channel_receipt(json.loads((folder / 'release-receipt.json').read_text()))
    expected = {receipt['archive'], 'release-receipt.json', 'appcast.xml', 'channel-proof.json'}
    if entries != expected or any(path.is_symlink() or not path.is_file() for path in folder.iterdir()):
        raise ValueError('only_channel_public_assets_allowed')
    archive = folder / receipt['archive']
    if sha256(archive) != receipt['archive_sha256'] or archive.stat().st_size != receipt['archive_bytes']:
        raise ValueError('channel_archive_mismatch')
    stage, item = feed_stage((folder / 'appcast.xml').read_bytes())
    enclosure = item.find('enclosure')
    import base64
    try:
        signature = enclosure.get('{' + SPARKLE + '}edSignature', '') if enclosure is not None else ''
        signature_ok = len(base64.b64decode(signature, validate=True)) == 64
    except ValueError:
        signature_ok = False
    if (not signature_ok or enclosure is None or enclosure.get('url') != receipt['archive_url']
            or enclosure.get('length') != str(receipt['archive_bytes'])
            or item.findtext('{' + SPARKLE + '}version') != receipt['build']
            or item.findtext('{' + SPARKLE + '}shortVersionString') != receipt['version']
            or expected_stage is not None and stage != expected_stage):
        raise ValueError('channel_feed_mismatch')
    origin = json.loads((folder / 'channel-proof.json').read_text())
    proof = json.loads(item.findtext('{' + PROOF_NAMESPACE + '}publication', '{}'))
    if (origin.get('channel') != receipt['channel'] or any(origin.get(key) != receipt[key]
            for key in ('source_revision', 'build', 'archive_sha256'))):
        raise ValueError('immutable_origin_proof_mismatch')
    if (proof.get('schema') != 1 or proof.get('channel') != stage
            or any(proof.get(key) != receipt[key]
                   for key in ('source_revision', 'build', 'archive_sha256'))
            or stage != 'dev' and (type(proof.get('run_id')) is not int or proof['run_id'] <= 0)):
        raise ValueError('channel_proof_mismatch')
    return receipt, proof


def write_proof(folder, receipt, stage, run_id=None, acceptance=None, testing_run_id=None):
    proof = {key: receipt[key] for key in ('source_revision', 'build', 'archive_sha256')}
    proof.update(schema=1, channel=stage)
    if run_id is not None:
        proof['run_id'] = run_id
    if acceptance is not None:
        proof['acceptance_sha256'] = hashlib.sha256(acceptance).hexdigest()
    if testing_run_id is not None:
        proof['testing_run_id'] = testing_run_id
    origin = folder / 'channel-proof.json'
    if not origin.exists():
        origin.write_text(json.dumps(proof, indent=2) + '\n')
    root = ET.fromstring((folder / 'appcast.xml').read_bytes())
    item = root.find('channel/item')
    if item is None:
        raise ValueError('single_channel_item_required')
    previous = item.find('{' + PROOF_NAMESPACE + '}publication')
    if previous is not None:
        item.remove(previous)
    ET.SubElement(item, '{' + PROOF_NAMESPACE + '}publication').text = json.dumps(proof, sort_keys=True)
    (folder / 'appcast.xml').write_bytes(ET.tostring(root, encoding='utf-8', xml_declaration=True))


def verify_archive_signature(folder):
    public_key = os.environ.get('REPOHUB_UPDATE_PUBLIC_KEY')
    if not public_key:
        raise ValueError('configured_public_update_key_required')
    receipt, _ = verify_package(folder)
    _, item = feed_stage((folder / 'appcast.xml').read_bytes())
    signature = item.find('enclosure').get('{' + SPARKLE + '}edSignature')
    with tempfile.TemporaryDirectory(prefix='repohub-public-verify-') as temporary:
        verifier = Path(temporary) / 'verify-update'
        command(['/usr/bin/xcrun', 'swiftc', '-parse-as-library',
                 '-module-cache-path', str(Path(temporary) / 'swift-cache'),
                 str(ROOT / 'native/VerifyUpdate.swift'), '-o', str(verifier)])
        command([str(verifier), public_key, signature, str(folder / receipt['archive'])])


def change_feed_stage(folder, stage):
    root = ET.fromstring((folder / 'appcast.xml').read_bytes())
    item = root.find('channel/item')
    if item is None:
        raise ValueError('single_channel_item_required')
    old = item.find('{' + SPARKLE + '}channel')
    if old is not None:
        item.remove(old)
    if stage != 'stable':
        ET.SubElement(item, '{' + SPARKLE + '}channel').text = stage
    (folder / 'appcast.xml').write_bytes(ET.tostring(root, encoding='utf-8', xml_declaration=True))


def require_publication_environment(mode):
    import base64
    try:
        valid_public_key = len(base64.b64decode(os.environ.get('REPOHUB_UPDATE_PUBLIC_KEY', ''), validate=True)) == 32
    except ValueError:
        valid_public_key = False
    required = ['REPOHUB_SPARKLE_PRIVATE_KEY']
    if mode == 'developer_id':
        required += ['REPOHUB_CERTIFICATE_P12', 'REPOHUB_CERTIFICATE_PASSWORD',
                     'REPOHUB_SIGNING_IDENTITY', 'REPOHUB_NOTARY_KEY',
                     'REPOHUB_NOTARY_KEY_ID', 'REPOHUB_NOTARY_ISSUER']
    if not valid_public_key or not all(os.environ.get(name) for name in required):
        raise ValueError('explicit_signing_environment_required_before_remote_writes')


class ChannelGitHub(GitHub):
    lock_sha = None

    def write(self, endpoint, payload=None, method='POST'):
        arguments = ['gh', 'api', '--method', method, f'repos/{REPOSITORY}/{endpoint}']
        if payload is not None:
            arguments += ['--input', '-']
        value = command(arguments, input=json.dumps(payload) if payload is not None else None)
        return json.loads(value) if value.strip() else None

    def expose_dev_source(self, revision):
        # A source tag records provenance without triggering branch-push Actions.
        remote = command(['git', 'remote', 'get-url', 'origin'], cwd=ROOT).strip()
        if remote not in (f'https://github.com/{REPOSITORY}.git', f'https://github.com/{REPOSITORY}',
                          f'git@github.com:{REPOSITORY}.git'):
            raise ValueError('canonical_github_remote_required')
        ref = 'refs/tags/repohub-source-' + revision
        existing = command(['git', 'ls-remote', 'origin', ref], cwd=ROOT).strip()
        if existing and existing.split()[0] != revision:
            raise ValueError('source_tag_collision')
        if not existing:
            command(['git', 'push', 'origin', revision + ':' + ref], cwd=ROOT)
        if self.api('commits/' + revision)['sha'] != revision:
            raise ValueError('remote_source_unconfirmed')

    @contextmanager
    def locked(self, revision):
        tag = self.write('git/tags', {'tag': 'repohub-publisher-session',
            'message': 'Publisher session ' + secrets.token_hex(16), 'object': revision, 'type': 'commit'})
        self.write('git/refs', {'ref': 'refs/' + LOCK_REF, 'sha': tag['sha']})
        self.lock_sha = tag['sha']
        try:
            yield
        finally:
            self.assert_lock()
            self.write('git/refs/' + LOCK_REF, method='DELETE')
            self.lock_sha = None

    def assert_lock(self):
        if not self.lock_sha or self.api('git/ref/' + LOCK_REF)['object']['sha'] != self.lock_sha:
            raise ValueError('exclusive_channel_publisher_lock_required')

    def testing_run(self, run_id, revision):
        run = self.api(f'actions/runs/{run_id}')
        pages = json.loads(command(['gh', 'api', '--paginate', '--slurp',
            f'repos/{REPOSITORY}/actions/runs/{run_id}/jobs?filter=latest&per_page=100']))
        require_testing_run(run, [job for page in pages for job in page['jobs']], revision)

    def stable_source(self, run_id, revision):
        main = self.api('git/ref/heads/main')['object']['sha']
        self.assert_source(run_id, main)
        original = self.api('commits/' + revision)
        merged = self.api('commits/' + main)
        if original['commit']['tree']['sha'] != merged['commit']['tree']['sha']:
            raise ValueError('tested_package_must_match_protected_main_tree')
        comparison = self.api('compare/' + revision + '...' + main)
        if comparison.get('status') not in ('identical', 'ahead'):
            raise ValueError('tested_source_must_be_on_protected_main')
        return main

    def create_candidate(self, plan):
        self.assert_lock()
        refs = self.api('git/matching-refs/tags/' + plan['tag'])
        if any(ref.get('ref') == 'refs/tags/' + plan['tag'] for ref in refs):
            raise ValueError('candidate_build_tag_already_reserved')
        command(['gh', 'release', 'create', plan['tag'], '--repo', REPOSITORY,
            '--target', plan['source_revision'], '--draft', '--prerelease', '--latest=false',
            '--title', 'RepoHub ' + plan['version'] + ' (' + plan['channel'] + ')',
            '--notes', 'Staged ' + plan['channel'] + ' candidate. Not a Stable release.\nSource: '
            + plan['source_revision']])
        draft = self.api('releases/tags/' + plan['tag'])
        if (draft.get('draft') is not True or draft.get('prerelease') is not True
                or draft.get('target_commitish') != plan['source_revision']):
            raise ValueError('exact_candidate_draft_required')

    def publish_candidate(self, plan):
        self.assert_lock()
        command(['gh', 'release', 'edit', plan['tag'], '--repo', REPOSITORY,
                 '--draft=false', '--prerelease', '--latest=false'])

    def replace_promotion_metadata(self, tag, folder):
        self.assert_lock()
        release = self.api('releases/tags/' + tag)
        if release.get('immutable'):
            raise ValueError('mutable_promotion_metadata_required')
        # Archive and its original receipt are never re-uploaded during promotion.
        command(['gh', 'release', 'upload', tag, '--repo', REPOSITORY, '--clobber',
                 str(folder / 'appcast.xml')])

    def confirm_source_tag(self, receipt):
        if self.api('commits/' + receipt['tag'])['sha'] != receipt['source_revision']:
            raise ValueError('candidate_tag_source_mismatch')

    def candidate(self, tag, folder, resume_stable=False):
        if not re.fullmatch(r'repohub-v0\.[0-9]+\.[0-9]+-b[1-9][0-9]*', tag):
            raise ValueError('managed_candidate_required')
        release = self.api('releases/tags/' + tag)
        if release.get('draft') or (release.get('prerelease') is not True and not resume_stable):
            raise ValueError('published_prerelease_candidate_required')
        self.download(tag, folder)
        receipt, proof = verify_package(folder)
        if receipt['tag'] != tag:
            raise ValueError('candidate_receipt_tag_mismatch')
        self.confirm_source_tag(receipt)
        return receipt, proof

    def publish_feed(self, stage, receipt, folder):
        self.assert_lock()
        if stage == 'stable':
            command(['gh', 'release', 'edit', receipt['tag'], '--repo', REPOSITORY,
                     '--prerelease=false', '--latest'])
            if self.latest()['tag_name'] != receipt['tag']:
                raise ValueError('stable_publication_unconfirmed')
            return
        tag = POINTER_PREFIX + stage
        matches = [item for item in self.releases() if item.get('tag_name') == tag]
        if len(matches) > 1:
            raise ValueError('duplicate_channel_pointer')
        if matches:
            release = matches[0]
            if release.get('draft') or not release.get('prerelease') or release.get('immutable'):
                raise ValueError('channel_pointer_not_mutable_prerelease')
            with tempfile.TemporaryDirectory() as temporary:
                command(['gh', 'release', 'download', tag, '--repo', REPOSITORY,
                         '--pattern', 'appcast.xml', '--dir', temporary])
                previous_raw = (Path(temporary) / 'appcast.xml').read_bytes()
                old_stage, old = feed_stage(previous_raw)
            previous_build = int(old.findtext('{' + SPARKLE + '}version', '0'))
            if previous_build == int(receipt['build']) and previous_raw == (folder / 'appcast.xml').read_bytes():
                return  # Retry an interrupted confirmation without changing the feed.
            if old_stage != stage or previous_build >= int(receipt['build']):
                raise ValueError('channel_pointer_must_advance')
        else:
            command(['gh', 'release', 'create', tag, '--repo', REPOSITORY,
                '--target', receipt['source_revision'], '--draft', '--prerelease', '--latest=false',
                '--title', 'RepoHub ' + stage + ' update feed',
                '--notes', 'Opt-in channel feed. This prerelease never becomes public latest.'])
        command(['gh', 'release', 'upload', tag, '--repo', REPOSITORY,
                 '--clobber', str(folder / 'appcast.xml')])
        if not matches:
            command(['gh', 'release', 'edit', tag, '--repo', REPOSITORY,
                     '--draft=false', '--prerelease', '--latest=false'])
        with tempfile.TemporaryDirectory() as temporary:
            command(['gh', 'release', 'download', tag, '--repo', REPOSITORY,
                     '--pattern', 'appcast.xml', '--dir', temporary])
            if (Path(temporary) / 'appcast.xml').read_bytes() != (folder / 'appcast.xml').read_bytes():
                raise ValueError('channel_feed_unconfirmed')


def confirm_uploaded(github, receipt, folder, stage):
    with tempfile.TemporaryDirectory() as temporary:
        received = Path(temporary)
        github.download(receipt['tag'], received)
        verify_package(received, stage)
        if ({p.name: sha256(p) for p in received.iterdir()}
                != {p.name: sha256(p) for p in folder.iterdir()}):
            raise ValueError('uploaded_channel_assets_mismatch')


def publish_candidate(github, plan, folder, recheck):
    verify_package(folder, plan['channel'])
    recheck()
    latest = github.latest()['tag_name']
    github.upload(plan, folder)
    confirm_uploaded(github, plan, folder, plan['channel'])
    recheck()
    github.publish_candidate(plan)
    github.confirm_source_tag(plan)
    github.publish_feed(plan['channel'], plan, folder)
    if github.latest()['tag_name'] != latest:
        raise ValueError('stable_changed_during_experimental_publication')
    return {'published': plan['tag'], 'channel': plan['channel'], 'feed_url': feed_url(plan['channel'])}


def promote(github, folder, receipt, proof, target, gate, run_id, acceptance=None, approve=None, resume=False):
    current = proof['channel']
    if not (resume and current == target):
        require_promotion(current, target)
    verify_package(folder, current)
    if target == 'testing':
        require_full_gate(gate, receipt['source_revision'])
        github.testing_run(run_id, receipt['source_revision'])
    else:
        if approve != receipt['tag']:
            raise ValueError('explicit_exact_tag_stable_approval_required')
        raw = acceptance.read_bytes() if acceptance else b''
        require_acceptance(json.loads(raw), receipt)
        testing_run_id = proof.get('testing_run_id', proof['run_id'])
        github.testing_run(testing_run_id, receipt['source_revision'])
        main = github.stable_source(run_id, receipt['source_revision'])
        require_full_gate(gate, main)
    latest = github.latest()['tag_name']
    if target == 'stable':
        current_build = release_number({'tag_name': latest})
        if current_build is None or int(receipt['build']) < current_build:
            raise ValueError('stable_build_must_not_regress')
    change_feed_stage(folder, target)
    write_proof(folder, receipt, target, run_id, raw if target == 'stable' else None,
                testing_run_id if target == 'stable' else None)
    verify_package(folder, target)
    # No archive generation/signing or upload occurs on this path.
    github.replace_promotion_metadata(receipt['tag'], folder)
    confirm_uploaded(github, receipt, folder, target)
    if target == 'stable':
        github.stable_source(run_id, receipt['source_revision'])
    else:
        github.testing_run(run_id, receipt['source_revision'])
    github.publish_feed(target, receipt, folder)
    if target != 'stable' and github.latest()['tag_name'] != latest:
        raise ValueError('stable_changed_during_experimental_promotion')
    return {'published': receipt['tag'], 'channel': target, 'archive_unchanged': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['dev', 'testing', 'promote'])
    parser.add_argument('--gate-receipt', type=Path, required=True)
    parser.add_argument('--run-id', type=int)
    parser.add_argument('--tag')
    parser.add_argument('--to', choices=['testing', 'stable'])
    parser.add_argument('--acceptance', type=Path)
    parser.add_argument('--approve-stable')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Recheck requirements and finish an interrupted promotion')
    args = parser.parse_args()
    if not args.publish or os.environ.get('REPOHUB_RELEASE_ENABLED') != 'true':
        raise ValueError('explicit_enabled_publication_required')
    os.umask(0o077)
    revision = command(['git', 'rev-parse', 'HEAD'], cwd=ROOT).strip()
    if command(['git', 'status', '--porcelain'], cwd=ROOT).strip():
        raise ValueError('clean_committed_source_required')
    gate = json.loads(args.gate_receipt.read_text())
    github = ChannelGitHub()
    if args.operation in ('dev', 'testing'):
        mode = selected_mode()
        require_publication_environment(mode)
    if args.operation == 'dev':
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            raise ValueError('dev_build_is_local_only')
        require_focused_gate(gate, revision)
        if gate['source_digest'] != source_fingerprint(ROOT):
            raise ValueError('focused_gate_source_digest_mismatch')
        github.expose_dev_source(revision)
    elif args.operation == 'testing':
        require_full_gate(gate, revision)
        # Automated publication is exact accepted main only, never a PR/fork artifact.
        github.assert_source(args.run_id, revision)
    elif not args.tag or not args.to or not args.run_id:
        raise ValueError('promotion_tag_channel_and_run_required')
    with github.locked(revision), tempfile.TemporaryDirectory(prefix='repohub-channel-') as temporary:
        work = Path(temporary)
        if args.operation == 'promote':
            folder = work / 'candidate'
            folder.mkdir()
            receipt, proof = github.candidate(args.tag, folder, args.resume and args.to == 'stable')
            verify_archive_signature(folder)
            print(json.dumps(promote(github, folder, receipt, proof, args.to, gate,
                                   args.run_id, args.acceptance, args.approve_stable, args.resume)))
            return
        history = github.releases()
        build_number = max((release_number(item) or 0 for item in history), default=0) + 1
        plan = channel_plan(build_number, revision, args.operation)
        github.create_candidate(plan)  # Reserve the global build before packaging.
        material = personal_signing_material if mode == 'personal_adhoc' else signing_material
        with material(work) as (notary_key, update_key):
            artifacts = build_artifacts(work, plan, mode, notary_key, update_key)
        receipt = json.loads((artifacts / 'release-receipt.json').read_text())
        write_proof(artifacts, receipt, args.operation, args.run_id)
        verify_archive_signature(artifacts)
        def recheck():
            if command(['git', 'rev-parse', 'HEAD'], cwd=ROOT).strip() != revision or command(['git', 'status', '--porcelain'], cwd=ROOT).strip():
                raise ValueError('source_changed_during_packaging')
            if args.operation == 'testing':
                github.assert_source(args.run_id, revision)
            elif source_fingerprint(ROOT) != gate['source_digest']:
                raise ValueError('source_changed_during_packaging')
        print(json.dumps(publish_candidate(github, receipt, artifacts, recheck)))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError, ET.ParseError) as error:
        reason = str(error) if isinstance(error, (ValueError, RuntimeError)) else 'invalid_channel_input'
        raise SystemExit('Channel release stopped: ' + reason)

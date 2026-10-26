#!/usr/bin/env python3
"""Publish Dev, record GitHub qualification, or explicitly promote unchanged bytes to Stable.

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
    require_promotion, require_github_run, require_qualification, validation_record, validate_channel_receipt,
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
    if stage not in ('dev', 'stable'):
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
    if 'github_run_id' in proof and (type(proof['github_run_id']) is not int
            or proof['github_run_id'] <= 0):
        raise ValueError('positive_github_run_required')
    if 'validation' in proof:
        expected = validation_record(bool(proof.get('github_run_id')), stage == 'stable')
        if proof['validation'] != expected:
            raise ValueError('candidate_validation_mismatch')
    if stage == 'stable' and proof.get('acceptance_scope') not in ('pro_and_air', 'pro_only_exception'):
        raise ValueError('explicit_installed_acceptance_scope_required')
    if stage == 'stable' and ('validation' not in proof
            or type(proof.get('github_run_id')) is not int or proof['github_run_id'] <= 0):
        raise ValueError('qualified_stable_proof_required')
    return receipt, proof


def write_proof(folder, receipt, stage, run_id=None, acceptance=None, github_run_id=None,
                validation=None, acceptance_scope=None):
    if github_run_id is not None and (type(github_run_id) is not int or github_run_id <= 0):
        raise ValueError('positive_github_run_required')
    proof = {key: receipt[key] for key in ('source_revision', 'build', 'archive_sha256')}
    proof.update(schema=1, channel=stage, validation=validation or validation_record())
    if run_id is not None:
        proof['run_id'] = run_id
    if acceptance_scope is not None:
        if stage != 'stable' or acceptance_scope not in ('pro_and_air', 'pro_only_exception'):
            raise ValueError('invalid_installed_acceptance_scope')
        proof['acceptance_scope'] = acceptance_scope
    if acceptance is not None:
        proof['acceptance_sha256'] = hashlib.sha256(acceptance).hexdigest()
    if github_run_id is not None:
        proof['github_run_id'] = github_run_id
    origin = folder / 'channel-proof.json'
    if not origin.exists():
        origin.write_text(json.dumps(proof, indent=2) + '\n')
    root = ET.fromstring((folder / 'appcast.xml').read_bytes())
    item = root.find('channel/item')
    if item is None:
        raise ValueError('single_channel_item_required')
    description = item.find('description')
    if description is None:
        description = ET.SubElement(item, 'description')
    description.text = '\n'.join(label + ': ' + proof['validation'][key] for key, label in (
        ('local_checks', 'Local checks'), ('github_checks', 'GitHub checks'),
        ('installed_acceptance', 'Installed acceptance')))
    if acceptance_scope == 'pro_only_exception':
        description.text += '\nAcceptance scope: Pro only; Air waived by a one-time owner approval.'
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

    def require_mutable_repository(self, hosted=False):
        if hosted:
            # GITHUB_TOKEN intentionally has no Administration permission.
            # Inspect release metadata here, then recheck the new publication
            # before exposing its feed. Never introduce a broader admin token.
            latest = self.latest()
            pointers = [item for item in self.releases()
                        if item.get('tag_name') in ('repohub-channel-dev',)]
            if latest.get('immutable') is not False or any(item.get('immutable') is not False for item in pointers):
                raise ValueError('mutable_channel_release_metadata_required')
        else:
            settings = self.api('immutable-releases')
            if settings.get('enabled') is not False or settings.get('enforced_by_owner') is not False:
                raise ValueError('channel_feed_requires_mutable_releases_no_settings_changed')

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

    def github_run(self, run_id, revision):
        run = self.api(f'actions/runs/{run_id}')
        pages = json.loads(command(['gh', 'api', '--paginate', '--slurp',
            f'repos/{REPOSITORY}/actions/runs/{run_id}/jobs?filter=latest&per_page=100']))
        require_github_run(run, [job for page in pages for job in page['jobs']], revision)

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
        # The release-by-tag REST endpoint does not expose unpublished drafts.
        # gh resolves draft metadata without requiring its not-yet-created tag.
        draft = json.loads(command(['gh', 'release', 'view', plan['tag'], '--repo', REPOSITORY,
            '--json', 'isDraft,isPrerelease,targetCommitish,tagName']))
        if (draft.get('isDraft') is not True or draft.get('isPrerelease') is not True
                or draft.get('targetCommitish') != plan['source_revision']
                or draft.get('tagName') != plan['tag']):
            raise ValueError('exact_candidate_draft_required')

    def publish_candidate(self, plan):
        self.assert_lock()
        command(['gh', 'release', 'edit', plan['tag'], '--repo', REPOSITORY,
                 '--draft=false', '--prerelease', '--latest=false'])
        published = self.api('releases/tags/' + plan['tag'])
        if (published.get('draft') or published.get('prerelease') is not True
                or published.get('immutable') is not False):
            raise ValueError('mutable_prerelease_unconfirmed_no_feed_change')

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

    def publish_feed(self, stage, receipt, folder, refresh=False):
        self.assert_lock()
        if stage == 'stable':
            _, proof = verify_package(folder, 'stable')
            acceptance_note = ('recorded Pro acceptance; one-time owner-approved Air exception.'
                               if proof['acceptance_scope'] == 'pro_only_exception'
                               else 'recorded Pro/Air acceptance.')
            command(['gh', 'release', 'edit', receipt['tag'], '--repo', REPOSITORY,
                     '--prerelease=false', '--latest', '--title', 'RepoHub ' + receipt['version'],
                     '--notes', 'Promoted unchanged from Dev after local and GitHub checks and '
                     + acceptance_note + '\nSource: ' + receipt['source_revision']
                     + '\nBuild: ' + receipt['build']])
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
            if refresh and old_stage == stage and previous_build > int(receipt['build']):
                return  # Qualifying an older candidate must not replace a newer Dev offer.
            same_candidate = False
            if refresh and previous_build == int(receipt['build']) and old_stage == stage:
                old_proof = json.loads(old.findtext('{' + PROOF_NAMESPACE + '}publication', '{}'))
                same_candidate = (old.find('enclosure').get('url') == receipt['archive_url']
                    and all(old_proof.get(key) == receipt[key]
                            for key in ('source_revision', 'build', 'archive_sha256')))
            if old_stage != stage or previous_build >= int(receipt['build']) and not same_candidate:
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


def qualify(github, folder, receipt, proof, gate, run_id):
    verify_package(folder, 'dev')
    require_full_gate(gate, receipt['source_revision'])
    github.github_run(run_id, receipt['source_revision'])
    latest = github.latest()['tag_name']
    write_proof(folder, receipt, 'dev', github_run_id=run_id,
                validation=validation_record(True))
    verify_package(folder, 'dev')
    github.replace_promotion_metadata(receipt['tag'], folder)
    confirm_uploaded(github, receipt, folder, 'dev')
    github.github_run(run_id, receipt['source_revision'])
    github.publish_feed('dev', receipt, folder, refresh=True)
    if github.latest()['tag_name'] != latest:
        raise ValueError('stable_changed_during_dev_qualification')
    return {'qualified': receipt['tag'], 'channel': 'dev',
            'validation': validation_record(True), 'archive_unchanged': True}


def matching_candidate(github, revision):
    candidates = sorted((item for item in github.releases()
                         if release_number(item) and not item.get('draft')
                         and item.get('prerelease') is True),
                        key=release_number, reverse=True)
    for item in candidates:
        if github.api('commits/' + item['tag_name'])['sha'] == revision:
            return item['tag_name']
    return None


def promote(github, folder, receipt, proof, target, gate, run_id, acceptance=None, approve=None,
            resume=False, pro_only_exception=None):
    current = proof['channel']
    if not (resume and current == target):
        require_promotion(current, target)
    if target != 'stable':
        raise ValueError('stable_is_only_promotion_target')
    verify_package(folder, current)
    if approve != receipt['tag']:
        raise ValueError('explicit_exact_tag_stable_approval_required')
    raw = acceptance.read_bytes() if acceptance else b''
    acceptance_scope = require_acceptance(json.loads(raw), receipt, pro_only_exception)
    if current == 'stable' and proof.get('acceptance_scope') != acceptance_scope:
        raise ValueError('resume_acceptance_scope_changed')
    qualified_proof = dict(proof)
    if resume and current == 'stable':
        qualified_proof['validation'] = validation_record(True)
    github_run_id = require_qualification(qualified_proof)
    github.github_run(github_run_id, receipt['source_revision'])
    main = github.stable_source(run_id, receipt['source_revision'])
    require_full_gate(gate, main)
    current_build = release_number({'tag_name': github.latest()['tag_name']})
    if current_build is None or int(receipt['build']) < current_build:
        raise ValueError('stable_build_must_not_regress')
    change_feed_stage(folder, 'stable')
    write_proof(folder, receipt, 'stable', run_id, raw, github_run_id,
                validation_record(True, True), acceptance_scope)
    verify_package(folder, 'stable')
    # Promotion only changes evidence/feed metadata; archive bytes are retained.
    github.replace_promotion_metadata(receipt['tag'], folder)
    confirm_uploaded(github, receipt, folder, 'stable')
    github.github_run(github_run_id, receipt['source_revision'])
    github.stable_source(run_id, receipt['source_revision'])
    github.publish_feed('stable', receipt, folder)
    return {'published': receipt['tag'], 'channel': 'stable',
            'validation': validation_record(True, True), 'archive_unchanged': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['dev', 'qualify', 'promote'])
    parser.add_argument('--gate-receipt', type=Path, required=True)
    parser.add_argument('--run-id', type=int)
    parser.add_argument('--tag')
    parser.add_argument('--auto', action='store_true', help='Qualify the newest existing exact-source Dev candidate')
    parser.add_argument('--to', choices=['stable'])
    parser.add_argument('--acceptance', type=Path)
    parser.add_argument('--approve-stable')
    parser.add_argument('--pro-only-exception', metavar='EXACT_TAG',
                        help='Explicit owner-approved, exact-release Pro-only acceptance exception')
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
    if args.operation == 'dev':
        mode = selected_mode()
        require_publication_environment(mode)
    if args.operation == 'dev':
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            raise ValueError('dev_build_is_local_only')
        require_focused_gate(gate, revision)
        if gate['source_digest'] != source_fingerprint(ROOT):
            raise ValueError('focused_gate_source_digest_mismatch')
        github.expose_dev_source(revision)
    elif args.operation == 'qualify':
        require_full_gate(gate, revision)
        github.github_run(args.run_id, revision)
        if args.auto:
            args.tag = matching_candidate(github, revision)
            if args.tag is None:
                print(json.dumps({'qualified': None, 'reason': 'no_matching_dev_candidate',
                                  'source_revision': revision}))
                return
        if not args.tag:
            raise ValueError('qualification_candidate_tag_required')
    elif not args.tag or args.to != 'stable' or not args.run_id:
        raise ValueError('promotion_tag_channel_and_run_required')
    github.require_mutable_repository(hosted=os.environ.get('GITHUB_ACTIONS') == 'true')
    with github.locked(revision), tempfile.TemporaryDirectory(prefix='repohub-channel-') as temporary:
        work = Path(temporary)
        if args.operation in ('qualify', 'promote'):
            folder = work / 'candidate'
            folder.mkdir()
            receipt, proof = github.candidate(args.tag, folder, args.resume and args.to == 'stable')
            verify_archive_signature(folder)
            if args.operation == 'qualify':
                print(json.dumps(qualify(github, folder, receipt, proof, gate, args.run_id)))
                return
            print(json.dumps(promote(github, folder, receipt, proof, args.to, gate,
                                   args.run_id, args.acceptance, args.approve_stable, args.resume,
                                   args.pro_only_exception)))
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
            if source_fingerprint(ROOT) != gate['source_digest']:
                raise ValueError('source_changed_during_packaging')
        print(json.dumps(publish_candidate(github, receipt, artifacts, recheck)))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError, ET.ParseError) as error:
        reason = str(error) if isinstance(error, (ValueError, RuntimeError)) else 'invalid_channel_input'
        raise SystemExit('Channel release stopped: ' + reason)

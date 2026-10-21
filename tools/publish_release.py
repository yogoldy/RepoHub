#!/usr/bin/env python3
"""Publish an accepted main commit; never install it or modify daily Mac state."""
import argparse
import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import tempfile
import xml.etree.ElementTree as ET

try:
    from tools.package_app import build, sha256
    from tools.update_feed import prepare, SPARKLE
    from tools.release_policy import (
        REPOSITORY, expired_releases, release_number, release_plan,
        require_accepted_run, validate_receipt,
    )
except ModuleNotFoundError:
    from package_app import build, sha256
    from update_feed import prepare, SPARKLE
    from release_policy import (
        REPOSITORY, expired_releases, release_number, release_plan,
        require_accepted_run, validate_receipt,
    )


def command(arguments, **kwargs):
    # Never echo signing arguments or raw subprocess output into public CI logs.
    result = subprocess.run(arguments, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError('release_command_failed:' + Path(arguments[0]).name)
    return result.stdout


class GitHub:
    def api(self, endpoint):
        return json.loads(command(['gh', 'api', f'repos/{REPOSITORY}/{endpoint}']))

    def pages(self, endpoint):
        pages = json.loads(command(['gh', 'api', '--paginate', '--slurp',
                                    f'repos/{REPOSITORY}/{endpoint}']))
        return [item for page in pages for item in page]

    def releases(self):
        return self.pages('releases?per_page=100')

    def assert_source(self, run_id, revision):
        run = self.api(f'actions/runs/{run_id}')
        pages = json.loads(command(['gh', 'api', '--paginate', '--slurp',
                                    f'repos/{REPOSITORY}/actions/runs/{run_id}/jobs?filter=latest&per_page=100']))
        jobs = [job for page in pages for job in page['jobs']]
        require_accepted_run(run, jobs, revision, self.api('git/ref/heads/main')['object']['sha'])

    def download(self, tag, directory):
        command(['gh', 'release', 'download', tag, '--repo', REPOSITORY,
                 '--dir', str(directory)])

    def receipt(self, release):
        with tempfile.TemporaryDirectory() as folder:
            command(['gh', 'release', 'download', release['tag_name'], '--repo', REPOSITORY,
                     '--pattern', 'release-receipt.json', '--dir', folder])
            receipt = json.loads((Path(folder) / 'release-receipt.json').read_text())
        validate_receipt(release, receipt)
        if self.api('commits/' + release['tag_name'])['sha'] != receipt['source_revision']:
            raise ValueError('release_tag_source_mismatch')
        return receipt

    def create_draft(self, plan):
        # GitHub has no tag for a new draft yet. Reject a conflicting existing
        # tag first, then verify the draft's exact target instead of resolving it.
        refs = self.api('git/matching-refs/tags/' + plan['tag'])
        for ref in refs:
            if (ref['ref'] == 'refs/tags/' + plan['tag']
                    and ref['object']['sha'] != plan['source_revision']):
                raise ValueError('release_tag_source_mismatch')
        command(['gh', 'release', 'create', plan['tag'], '--repo', REPOSITORY,
                 '--target', plan['source_revision'], '--draft', '--title', 'RepoHub ' + plan['version'],
                 '--notes', 'Automated Golden Gate passed. Native Mac testing follows delivery. '
                 + ('Personal Sparkle-signed release; not Apple-notarized. ' if selected_mode() == 'personal_adhoc' else '')
                 + '\nSource: '
                 + plan['source_revision'] + '\nBuild: ' + plan['build']])
        draft = json.loads(command(['gh', 'release', 'view', plan['tag'], '--repo', REPOSITORY,
                                    '--json', 'isDraft,targetCommitish,tagName']))
        if (draft.get('isDraft') is not True or draft.get('tagName') != plan['tag']
                or draft.get('targetCommitish') != plan['source_revision']):
            raise ValueError('release_draft_source_mismatch')

    def upload(self, plan, artifacts):
        command(['gh', 'release', 'upload', plan['tag'], '--repo', REPOSITORY,
                 *(str(path) for path in sorted(artifacts.iterdir()))])

    def publish(self, plan):
        command(['gh', 'release', 'edit', plan['tag'], '--repo', REPOSITORY,
                 '--draft=false', '--latest'])
        if self.api('commits/' + plan['tag'])['sha'] != plan['source_revision']:
            raise ValueError('published_tag_source_mismatch_no_cleanup')

    def latest(self):
        return self.api('releases/latest')

    def remove_package(self, release):
        # Omit --cleanup-tag: source tags/history survive package retention.
        command(['gh', 'release', 'delete', release['tag_name'], '--repo', REPOSITORY, '--yes'])


def require_gate(receipt, revision):
    if (receipt.get('result') != 'passed' or receipt.get('profile') != 'macos'
            or receipt.get('source_commit') != revision or receipt.get('dirty_source') is not False
            or receipt.get('source_unchanged') is not True):
        raise ValueError('clean_exact_macos_gate_required')


def verify_artifacts(directory, plan):
    expected_names = {plan['archive'], 'release-receipt.json', 'appcast.xml'}
    if ({path.name for path in directory.iterdir()} != expected_names
            or any(path.is_symlink() or not path.is_file() for path in directory.iterdir())):
        raise ValueError('only_public_release_assets_allowed')
    receipt = json.loads((directory / 'release-receipt.json').read_text())
    validate_receipt({'tag_name': plan['tag']}, receipt)
    if any(receipt.get(field) != plan[field] for field in plan):
        raise ValueError('release_plan_mismatch')
    archive = directory / plan['archive']
    if sha256(archive) != receipt['archive_sha256'] or archive.stat().st_size != receipt['archive_bytes']:
        raise ValueError('release_archive_mismatch')
    item = ET.fromstring((directory / 'appcast.xml').read_bytes()).find('channel/item')
    if item is None:
        raise ValueError('release_feed_mismatch')
    enclosure = item.find('enclosure')
    signature = enclosure.get('{' + SPARKLE + '}edSignature', '') if enclosure is not None else ''
    try:
        valid_signature = len(base64.b64decode(signature, validate=True)) == 64
    except ValueError:
        valid_signature = False
    if (enclosure is None or enclosure.get('url') != plan['archive_url']
            or enclosure.get('length') != str(receipt['archive_bytes']) or not valid_signature
            or item.findtext('{' + SPARKLE + '}version') != plan['build']
            or item.findtext('{' + SPARKLE + '}shortVersionString') != plan['version']):
        raise ValueError('release_feed_mismatch')
    return receipt


def publish_verified(github, plan, artifacts, run_id):
    verify_artifacts(artifacts, plan)
    github.assert_source(run_id, plan['source_revision'])
    github.create_draft(plan)
    github.upload(plan, artifacts)
    with tempfile.TemporaryDirectory() as folder:
        remote = Path(folder)
        github.download(plan['tag'], remote)
        verify_artifacts(remote, plan)
        expected = {path.name: sha256(path) for path in artifacts.iterdir()}
        received = {path.name: sha256(path) for path in remote.iterdir()}
        if received != expected:
            raise ValueError('uploaded_assets_mismatch')
    # A newer merge during packaging supersedes this candidate. Its draft stays
    # unpublished for investigation; it cannot move the existing latest feed.
    github.assert_source(run_id, plan['source_revision'])
    github.publish(plan)
    if github.latest()['tag_name'] != plan['tag']:
        raise ValueError('latest_release_unconfirmed_no_cleanup')
    expired = expired_releases(github.releases(), plan['tag'])
    # Validate every deletion candidate before deleting any package.
    for release in expired:
        github.receipt(release)
    for release in expired:
        github.remove_package(release)
    return {'published': plan['tag'], 'removed_packages': [item['tag_name'] for item in expired]}


@contextmanager
def signing_material(work):
    required = ('REPOHUB_CERTIFICATE_P12', 'REPOHUB_CERTIFICATE_PASSWORD',
                'REPOHUB_SIGNING_IDENTITY', 'REPOHUB_NOTARY_KEY', 'REPOHUB_NOTARY_KEY_ID',
                'REPOHUB_NOTARY_ISSUER', 'REPOHUB_SPARKLE_PRIVATE_KEY')
    if not all(os.environ.get(name) for name in required):
        raise ValueError('release_signing_secrets_incomplete')
    if not os.environ['REPOHUB_SIGNING_IDENTITY'].startswith('Developer ID Application:'):
        raise ValueError('developer_id_required')
    certificate = work / 'signing.p12'
    certificate.write_bytes(base64.b64decode(os.environ['REPOHUB_CERTIFICATE_P12'], validate=True))
    notary = work / 'notary.p8'
    notary.write_text(os.environ['REPOHUB_NOTARY_KEY'])
    update = work / 'sparkle.key'
    update.write_text(os.environ['REPOHUB_SPARKLE_PRIVATE_KEY'])
    for path in (certificate, notary, update):
        path.chmod(0o600)
    keychain = work / 'release.keychain-db'
    password = secrets.token_urlsafe(32)
    previous = shlex.split(command(['security', 'list-keychains', '-d', 'user']))
    try:
        command(['security', 'create-keychain', '-p', password, str(keychain)])
        command(['security', 'set-keychain-settings', '-lut', '7200', str(keychain)])
        command(['security', 'unlock-keychain', '-p', password, str(keychain)])
        command(['security', 'import', str(certificate), '-k', str(keychain),
                 '-P', os.environ['REPOHUB_CERTIFICATE_PASSWORD'], '-T', '/usr/bin/codesign'])
        command(['security', 'set-key-partition-list', '-S', 'apple-tool:,apple:,codesign:',
                 '-s', '-k', password, str(keychain)])
        command(['security', 'list-keychains', '-d', 'user', '-s', str(keychain), *previous])
        yield notary, update
    finally:
        command(['security', 'list-keychains', '-d', 'user', '-s', *previous])
        if keychain.exists():
            command(['security', 'delete-keychain', str(keychain)])
        for path in (certificate, notary, update):
            path.unlink(missing_ok=True)


@contextmanager
def personal_signing_material(work):
    value = os.environ.get('REPOHUB_SPARKLE_PRIVATE_KEY')
    if not value:
        raise ValueError('sparkle_private_key_required')
    path = work / 'sparkle.key'
    path.write_text(value)
    path.chmod(0o600)
    try:
        yield None, path
    finally:
        path.unlink(missing_ok=True)


def selected_mode():
    mode = os.environ.get('REPOHUB_RELEASE_MODE', 'developer_id')
    if mode not in ('developer_id', 'personal_adhoc'):
        raise ValueError('invalid_release_mode')
    return mode


def build_artifacts(work, plan, mode, notary_key, update_key):
    app = work / 'Repo Hub.app'
    cache = work / 'dependencies'
    personal = mode == 'personal_adhoc'
    build(app, cache, plan['version'], plan['build'], 'com.leogoldberg.repohub',
          plan['feed_url'], os.environ['REPOHUB_UPDATE_PUBLIC_KEY'], personal=personal,
          signing_identity=None if personal else os.environ['REPOHUB_SIGNING_IDENTITY'])
    if not personal:
        submission = work / 'notarization.zip'
        command(['/usr/bin/ditto', '-c', '-k', '--keepParent', str(app), str(submission)])
        print('Submitting the signed package for Apple notarization.', flush=True)
        result = json.loads(command(['xcrun', 'notarytool', 'submit', str(submission),
            '--key', str(notary_key), '--key-id', os.environ['REPOHUB_NOTARY_KEY_ID'],
            '--issuer', os.environ['REPOHUB_NOTARY_ISSUER'], '--wait', '--timeout', '20m',
            '--output-format', 'json']))
        if result.get('status') != 'Accepted':
            raise ValueError('apple_notarization_not_accepted')
        command(['xcrun', 'stapler', 'staple', str(app)])
    artifacts = work / 'artifacts'
    channel_options = {'update_channel': plan['channel']} if plan.get('schema') == 2 else {}
    receipt = prepare(app, artifacts, plan['archive_url'], update_key, cache, **channel_options)
    if (receipt['source_revision'] != plan['source_revision'] or receipt['build'] != plan['build']
            or receipt['test_only'] is not False or receipt['distribution'] != mode):
        raise ValueError('prepared_source_mismatch')
    receipt.pop('published', None)
    receipt.update(plan)
    (artifacts / 'release-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return artifacts


def main():
    # The old CLI cannot bypass the explicitly approved staged Stable process.
    raise ValueError('legacy_stable_publication_disabled_use_channel_release')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError, ET.ParseError) as error:
        # Structured reason only. Private signing/notary output stays off public logs.
        raise SystemExit('Release stopped: ' + type(error).__name__ + ': '
                         + (str(error) if isinstance(error, (ValueError, RuntimeError)) else 'invalid_release_input'))

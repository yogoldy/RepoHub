#!/usr/bin/env python3
"""One-time Keychain setup and repeatable, explicitly authorized local Dev release.

Never installs an app, qualifies GitHub checks or promotes Stable. Secrets travel only through
private subprocess pipes/environments and the existing disposable signing files.
The helper is developer tooling and is never included in the shipped app.
"""
import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.channel_policy import feed_url, require_focused_gate
from tools.release_gate import source_fingerprint
from tools.release_policy import REPOSITORY
from tools.signing_identity import TEAM_ID
from tools.update_feed import validate_key_file

HOME = Path.home() / 'Library/Application Support/RepoHub Developer'
HELPER_ID = 'com.leogoldberg.repohub.dev-publisher.credentials'
HELPER_SOURCES = ('PublisherKeychain.swift', 'PublisherCredentials.swift')
CREDENTIAL_NAMES = {
    'REPOHUB_CERTIFICATE_P12', 'REPOHUB_CERTIFICATE_PASSWORD',
    'REPOHUB_SIGNING_IDENTITY', 'REPOHUB_NOTARY_KEY', 'REPOHUB_NOTARY_KEY_ID',
    'REPOHUB_NOTARY_ISSUER', 'REPOHUB_SPARKLE_PRIVATE_KEY', 'REPOHUB_UPDATE_PUBLIC_KEY',
}
SAFE_ERRORS = {
    'local_macos_required', 'clean_source_required', 'private_developer_directory_required',
    'trusted_helper_required', 'credentials_not_configured', 'already_configured',
    'keychain_cancelled_or_locked', 'publisher_credentials_unavailable',
    'secure_terminal_required', 'invalid_setup_profile', 'invalid_credentials',
    'credential_preflight_failed', 'dev_gate_failed', 'dev_source_changed',
    'dev_publication_failed', 'explicit_dev_publication_required',
}


class LocalDevError(Exception):
    def __init__(self, code):
        self.code = code if code in SAFE_ERRORS else 'publisher_credentials_unavailable'
        super().__init__(self.code)


def clean_environment():
    return {name: value for name, value in os.environ.items() if not name.startswith('REPOHUB_')}


def require_local():
    if (platform.system() != 'Darwin' or platform.machine() != 'arm64'
            or os.environ.get('GITHUB_ACTIONS') == 'true'):
        raise LocalDevError('local_macos_required')


def clean_revision():
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise LocalDevError('clean_source_required')
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def private_directory(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if path.is_symlink() or not path.is_dir() or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise LocalDevError('private_developer_directory_required')
    return path


def identity_valid(identity):
    return isinstance(identity, str) and re.fullmatch(
        r'Developer ID Application: [^\n]+ \(' + TEAM_ID + r'\)', identity) is not None


def helper_requirement():
    return (f'anchor apple generic and identifier "{HELPER_ID}" '
            f'and certificate leaf[subject.OU] = {TEAM_ID} '
            'and certificate leaf[field.1.2.840.113635.100.6.1.13]')


def verify_helper(helper):
    try:
        validate_key_file(helper)
        result = subprocess.run(['/usr/bin/codesign', '--verify', '--strict',
                                 '-R', '=' + helper_requirement(), str(helper)], capture_output=True)
        if result.returncode:
            raise LocalDevError('trusted_helper_required')
    except (OSError, ValueError):
        raise LocalDevError('trusted_helper_required') from None


def prepare_helper(identity):
    if not identity_valid(identity):
        raise LocalDevError('invalid_setup_profile')
    private_directory(HOME)
    helper = HOME / 'publisher-credentials'
    record = HOME / 'helper.json'
    digest = hashlib.sha256(b''.join((ROOT / 'native' / name).read_bytes()
                                     for name in HELPER_SOURCES)).hexdigest()
    if helper.exists() and record.exists():
        validate_key_file(record)
        metadata = json.loads(record.read_text())
        verify_helper(helper)
        if metadata.get('source_sha256') == digest and metadata.get('identity') == identity:
            return helper
    with tempfile.TemporaryDirectory(prefix='helper-', dir=HOME) as temporary:
        work = Path(temporary)
        staged = work / 'publisher-credentials'
        commands = [
            ['xcrun', 'swiftc', '-module-cache-path', str(work / 'cache'),
             *(str(ROOT / 'native' / name) for name in HELPER_SOURCES), '-o', str(staged)],
            ['/usr/bin/codesign', '--force', '--sign', identity, '--identifier', HELPER_ID,
             '--options', 'runtime', '--timestamp', str(staged)],
        ]
        for command in commands:
            if subprocess.run(command, capture_output=True).returncode:
                raise LocalDevError('trusted_helper_required')
        staged.chmod(0o700)
        verify_helper(staged)
        staged.replace(helper)
        pending = work / 'helper.json'
        pending.write_text(json.dumps({'source_sha256': digest, 'identity': identity}))
        pending.chmod(0o600)
        pending.replace(record)
    return helper


def keychain(helper, operation, payload=None):
    verify_helper(helper)
    result = subprocess.run([str(helper), operation], input=payload,
                            capture_output=True, env=clean_environment())
    if result.returncode:
        reason = result.stderr.decode(errors='replace').strip()
        raise LocalDevError(reason)
    return result.stdout


def validate_credentials(value):
    try:
        if (not isinstance(value, dict) or set(value) != CREDENTIAL_NAMES
                or any(not isinstance(item, str) or not item for item in value.values())
                or not identity_valid(value['REPOHUB_SIGNING_IDENTITY'])
                or len(base64.b64decode(value['REPOHUB_SPARKLE_PRIVATE_KEY'], validate=True)) != 32
                or len(base64.b64decode(value['REPOHUB_UPDATE_PUBLIC_KEY'], validate=True)) != 32
                or not base64.b64decode(value['REPOHUB_CERTIFICATE_P12'], validate=True)
                or not re.fullmatch('[A-Z0-9]{10}', value['REPOHUB_NOTARY_KEY_ID'])):
            raise ValueError()
        uuid.UUID(value['REPOHUB_NOTARY_ISSUER'])
    except (ValueError, KeyError, TypeError):
        raise LocalDevError('invalid_credentials') from None
    return value


def credential_preflight(credentials):
    # Keep the existing disposable-keychain importer and key-continuity check.
    try:
        configured = subprocess.check_output([
            'gh', 'variable', 'get', 'REPOHUB_UPDATE_PUBLIC_KEY', '--repo', REPOSITORY,
        ], text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        raise LocalDevError('credential_preflight_failed') from None
    if configured != credentials['REPOHUB_UPDATE_PUBLIC_KEY']:
        raise LocalDevError('credential_preflight_failed')
    program = '''
import os, subprocess, tempfile
from pathlib import Path
from tools.publish_release import signing_material
with tempfile.TemporaryDirectory(prefix='repohub-local-preflight-') as folder:
    work = Path(folder)
    checker = work / 'key-check'
    subprocess.run(['xcrun','swiftc','-parse-as-library','-module-cache-path',str(work/'cache'),
        'native/UpdateKey.swift','-o',str(checker)],check=True,capture_output=True)
    with signing_material(work) as (notary, key):
        subprocess.run([str(checker),str(key),os.environ['REPOHUB_UPDATE_PUBLIC_KEY']],
            check=True,capture_output=True)
        subprocess.run(['xcrun','notarytool','history','--key',str(notary),
            '--key-id',os.environ['REPOHUB_NOTARY_KEY_ID'],
            '--issuer',os.environ['REPOHUB_NOTARY_ISSUER'],'--output-format','json'],
            check=True,capture_output=True,timeout=60)
'''
    environment = dict(clean_environment(), **credentials)
    try:
        result = subprocess.run([sys.executable, '-c', program], cwd=ROOT,
                                env=environment, capture_output=True, timeout=180)
        if result.returncode:
            raise LocalDevError('credential_preflight_failed')
    finally:
        for name in CREDENTIAL_NAMES:
            environment.pop(name, None)


def setup(profile_path):
    require_local()
    revision = clean_revision()
    if not sys.stdin.isatty():
        raise LocalDevError('secure_terminal_required')
    try:
        validate_key_file(profile_path)
        profile = json.loads(profile_path.read_text())
        certificate = Path(profile['certificate_path'])
        notary = Path(profile['notary_key_path'])
        validate_key_file(certificate)
        validate_key_file(notary)
        helper = prepare_helper(profile['signing_identity'])
    except (KeyError, ValueError, OSError):
        raise LocalDevError('invalid_setup_profile') from None
    if json.loads(keychain(helper, 'status'))['configured']:
        raise LocalDevError('already_configured')
    print('One-time setup: save existing signing credentials in your Mac Keychain.')
    print('No new keys, release, installation or app permissions are created.')
    print('The following inputs are hidden; do not send them in chat.', flush=True)
    credentials = {
        'REPOHUB_SPARKLE_PRIVATE_KEY': getpass.getpass('Original Sparkle signing key: ').strip(),
        'REPOHUB_CERTIFICATE_PASSWORD': getpass.getpass('Certificates.p12 password: '),
        'REPOHUB_CERTIFICATE_P12': base64.b64encode(certificate.read_bytes()).decode(),
        'REPOHUB_NOTARY_KEY': notary.read_text(),
        'REPOHUB_SIGNING_IDENTITY': profile['signing_identity'],
        'REPOHUB_NOTARY_KEY_ID': profile['notary_key_id'],
        'REPOHUB_NOTARY_ISSUER': profile['notary_issuer'],
        'REPOHUB_UPDATE_PUBLIC_KEY': profile['update_public_key'],
    }
    try:
        validate_credentials(credentials)
        credential_preflight(credentials)
        if clean_revision() != revision:
            raise LocalDevError('dev_source_changed')
        keychain(helper, 'save', json.dumps(credentials).encode())
    finally:
        credentials.clear()
    return {'configured': True, 'published': False, 'installed': False}


def configured_helper(update=True):
    record = HOME / 'helper.json'
    if not record.is_file():
        raise LocalDevError('credentials_not_configured')
    validate_key_file(record)
    metadata = json.loads(record.read_text())
    if update:
        return prepare_helper(metadata.get('identity'))
    helper = HOME / 'publisher-credentials'
    verify_helper(helper)
    return helper


def publish(explicit):
    require_local()
    if not explicit:
        raise LocalDevError('explicit_dev_publication_required')
    revision = clean_revision()
    helper = configured_helper()
    if not json.loads(keychain(helper, 'status'))['configured']:
        raise LocalDevError('credentials_not_configured')
    runs = private_directory(HOME / 'runs')
    work = private_directory(runs / uuid.uuid4().hex)
    gate = work / 'dev-gate.json'
    status_path = work / 'status.json'
    current_stage = 'dev_gate'

    def status(stage, **facts):
        nonlocal current_stage
        current_stage = stage
        status_path.write_text(json.dumps({'stage': stage, 'source_revision': revision, **facts}))
        status_path.chmod(0o600)

    status('dev_gate')
    credentials = {}
    environment = {}
    try:
        with (work / 'checks.log').open('w') as log:
            (work / 'checks.log').chmod(0o600)
            result = subprocess.run([sys.executable, 'tools/dev_gate.py', '--output', str(gate)],
                                    cwd=ROOT, env=clean_environment(), stdout=log, stderr=log)
        if result.returncode:
            raise LocalDevError('dev_gate_failed')
        receipt = json.loads(gate.read_text())
        require_focused_gate(receipt, revision)
        if clean_revision() != revision or source_fingerprint(ROOT) != receipt['source_digest']:
            raise LocalDevError('dev_source_changed')
        status('credential_preflight')
        credentials = validate_credentials(json.loads(keychain(helper, 'load')))
        credential_preflight(credentials)
        environment = dict(clean_environment(), **credentials,
                           REPOHUB_RELEASE_ENABLED='true', REPOHUB_RELEASE_MODE='developer_id')
        status('publishing_dev')
        result = subprocess.run([sys.executable, 'tools/channel_release.py', 'dev', '--publish',
                                 '--gate-receipt', str(gate)], cwd=ROOT, env=environment,
                                capture_output=True, text=True)
        # Never persist/print child output that may have encountered credentials.
        if result.returncode:
            raise LocalDevError('dev_publication_failed')
        publication = json.loads(result.stdout.splitlines()[-1])
        if (set(publication) != {'published', 'channel', 'feed_url'}
                or publication['channel'] != 'dev'
                or publication['feed_url'] != feed_url('dev')
                or not re.fullmatch(r'repohub-v0\.[0-9]+\.[0-9]+-b[1-9][0-9]*', publication['published'])):
            raise LocalDevError('dev_publication_failed')
        status('published', tag=publication['published'], tests_run=receipt['tests_run'], installed=False)
        return publication
    except BaseException as error:
        reason = error.code if isinstance(error, LocalDevError) else 'dev_publication_failed'
        failed_stage = current_stage
        status('failed', failed_stage=failed_stage, reason=reason, installed=False)
        if isinstance(error, LocalDevError):
            error.failed_stage = failed_stage
        raise
    finally:
        credentials.clear()
        for name in CREDENTIAL_NAMES:
            environment.pop(name, None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    provision = commands.add_parser('setup')
    provision.add_argument('--profile', type=Path, required=True)
    commands.add_parser('status')
    release = commands.add_parser('publish')
    release.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.operation == 'setup':
            result = setup(args.profile)
        elif args.operation == 'status':
            require_local()
            result = json.loads(keychain(configured_helper(update=False), 'status'))
        else:
            result = publish(args.publish)
        print(json.dumps(result, sort_keys=True))
    except (Exception, KeyboardInterrupt) as error:
        reason = error.code if isinstance(error, LocalDevError) else 'local_dev_operation_failed'
        result = {'result': 'failed', 'reason': reason, 'installed': False}
        if isinstance(error, LocalDevError) and hasattr(error, 'failed_stage'):
            result['failed_stage'] = error.failed_stage
        print(json.dumps(result))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

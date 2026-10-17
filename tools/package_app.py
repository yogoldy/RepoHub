#!/usr/bin/env python3
"""Build a new coordinated bundle; never install it or run personal migrations."""
import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'tools/update-dependencies.json'
NATIVE = ('RepoHub.swift', 'HelperLaunch.swift', 'BackupReadiness.swift',
          'ProblemAlerts.swift', 'MenuBridge.swift', 'GitHubConnection.swift',
          'PackagedApplication.swift', 'AppUpdates.swift')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def dependency(name, cache):
    entry = json.loads(LOCK.read_text())[name]
    target = cache / (name + '-' + entry['sha256'] + '.tar')
    cache.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        # Download to a temporary file; an interrupted response is never reused.
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as temporary:
            pending = Path(temporary.name)
            try:
                with urlopen(entry['url'], timeout=60) as response:
                    shutil.copyfileobj(response, temporary)
                temporary.flush()
                if sha256(pending) != entry['sha256']:
                    raise ValueError('dependency_hash_mismatch')
                pending.replace(target)
            finally:
                pending.unlink(missing_ok=True)
    if sha256(target) != entry['sha256']:
        raise ValueError('dependency_hash_mismatch')
    return target


def extract(archive, destination):
    # Python's data filter rejects absolute/escaping members and link targets.
    with tarfile.open(archive) as source:
        source.extractall(destination, filter='data')


def runtime_modules():
    tree = ast.parse((ROOT / 'install.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.iter, (ast.Tuple, ast.List)):
            values = ast.literal_eval(node.iter)
            if 'repohub.py' in values:
                return values
    raise ValueError('missing_runtime_modules')


def inventory(resources):
    result = {}
    for path in sorted(resources.rglob('*')):
        relative = path.relative_to(resources).as_posix()
        if relative == 'release.json':
            continue
        if path.is_symlink():
            if not path.resolve().is_relative_to(resources.resolve()):
                raise ValueError('escaping_resource_link')
            result[relative] = {'link': os.readlink(path)}
        elif path.is_file():
            result[relative] = {'sha256': sha256(path)}
    return result


def verify(resources):
    manifest = json.loads((resources / 'release.json').read_text())
    if manifest.get('schema') != 1 or manifest.get('files') != inventory(resources):
        raise ValueError('component_mismatch')
    return manifest


def validate_options(identifier, feed, public_key, test):
    parsed = urlparse(feed)
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError('invalid_update_feed')
    secure = parsed.scheme == 'https' and bool(parsed.hostname)
    local = parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
    if test:
        if not re.fullmatch(r'com\.leogoldberg\.repohub\.test\.[a-z0-9-]+', identifier):
            raise ValueError('test_identity_required')
        if not (secure or local):
            raise ValueError('invalid_test_feed')
    elif identifier != 'com.leogoldberg.repohub' or not secure:
        raise ValueError('production_https_required')
    try:
        decoded = base64.b64decode(public_key, validate=True)
    except ValueError as error:
        raise ValueError('invalid_update_public_key') from error
    if len(decoded) != 32:
        raise ValueError('invalid_update_public_key')


def run(*arguments):
    subprocess.run([str(argument) for argument in arguments], check=True)



def distribution_mode(test, personal, signing_identity):
    if test and personal:
        raise ValueError('conflicting_distribution_modes')
    if personal:
        if signing_identity not in (None, '-'):
            raise ValueError('personal_mode_requires_adhoc')
        return 'personal_adhoc'
    if test:
        return 'test'
    if not (signing_identity or '').startswith('Developer ID Application:'):
        raise ValueError('developer_id_required')
    return 'developer_id'


def update_defaults(test):
    return {
        'SUEnableAutomaticChecks': not test,
        'SUScheduledCheckInterval': 3600,
        'SUAutomaticallyUpdate': False,
        'SUAllowsAutomaticUpdates': False,
        'SUEnableSystemProfiling': False,
    }


def build(output, cache, version, build_number, identifier, feed, public_key,
          test=False, signing_identity=None, personal=False):
    validate_options(identifier, feed, public_key, test)
    mode = distribution_mode(test, personal, signing_identity)
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+){0,2}', version):
        raise ValueError('invalid_version')
    if not re.fullmatch(r'[1-9][0-9]*', build_number):
        raise ValueError('invalid_build_number')
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('arm64_macos_required')
    if output.exists() or output.is_symlink() or output.suffix != '.app':
        raise ValueError('new_app_path_required')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise ValueError('clean_source_required')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='repohub-package-', dir=output.parent) as folder:
        work = Path(folder)
        unpacked = work / 'dependencies'
        unpacked.mkdir()
        extract(dependency('sparkle', cache), unpacked / 'sparkle')
        extract(dependency('python-arm64', cache), unpacked / 'python')
        app = work / output.name
        contents = app / 'Contents'
        resources = contents / 'Resources'
        runtime = resources / 'runtime'
        runtime.mkdir(parents=True)
        (contents / 'MacOS').mkdir()
        (contents / 'Frameworks').mkdir()
        for name in runtime_modules():
            shutil.copy2(ROOT / name, runtime / name)
        shutil.copytree(ROOT / 'web', runtime / 'web')
        shutil.copytree(unpacked / 'python/python', resources / 'python', symlinks=True)
        framework = contents / 'Frameworks/Sparkle.framework'
        shutil.copytree(unpacked / 'sparkle/Sparkle.framework', framework, symlinks=True)
        shutil.copy2(unpacked / 'sparkle/LICENSE', resources / 'Sparkle-LICENSE')
        swift = ['/usr/bin/xcrun', 'swiftc', '-module-cache-path', str(work / 'swift-cache'),
                 '-target', 'arm64-apple-macos13.0']
        run(*swift, ROOT / 'native/CloudStatus.swift', '-o', runtime / 'cloud-status')
        run(*swift, *(ROOT / 'native' / name for name in NATIVE),
            '-F', contents / 'Frameworks', '-framework', 'Sparkle',
            '-Xlinker', '-rpath', '-Xlinker', '@executable_path/../Frameworks',
            '-framework', 'AppKit', '-framework', 'WebKit', '-framework', 'UserNotifications',
            '-o', contents / 'MacOS/RepoHub')
        info = {'CFBundleIdentifier': identifier, 'CFBundleName': 'RepoHub Test' if test else 'Repo Hub',
                'CFBundleDisplayName': 'RepoHub Test' if test else 'Repo Hub',
                'CFBundleExecutable': 'RepoHub', 'CFBundlePackageType': 'APPL',
                'CFBundleVersion': build_number, 'CFBundleShortVersionString': version,
                'LSUIElement': True, 'LSMinimumSystemVersion': '13.0',
                'NSHighResolutionCapable': True, 'RepoHubPackaged': True,
                'RepoHubTestMode': test, 'RepoHubPersonalUpdates': personal,
                'SUFeedURL': feed, 'SUPublicEDKey': public_key, **update_defaults(test),
                'SUVerifyUpdateBeforeExtraction': True,
                'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True}}
        (contents / 'Info.plist').write_bytes(plistlib.dumps(info))
        identity = signing_identity or '-'
        options = ['--options', 'runtime', '--timestamp'] if mode == 'developer_id' else []
        # Sign nested executable code before hashing resources. Never use --deep to sign.
        for path in sorted((resources / 'python').rglob('*')):
            if path.is_file() and not path.is_symlink():
                with path.open('rb') as source:
                    magic = source.read(4)
                if magic in (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe'):
                    run('/usr/bin/codesign', '--force', '--sign', identity, *options, path)
        run('/usr/bin/codesign', '--force', '--sign', identity, *options, runtime / 'cloud-status')
        if mode == 'developer_id':
            # Sparkle's nested XPC services already have upstream signatures. Re-sign
            # from the inside out for this distribution identity.
            for suffix in ('Updater.app', 'Installer.xpc', 'Downloader.xpc'):
                for nested in sorted(framework.rglob(suffix)):
                    run('/usr/bin/codesign', '--force', '--sign', identity, *options, nested)
            run('/usr/bin/codesign', '--force', '--sign', identity, *options, framework / 'Versions/B/Autoupdate')
            run('/usr/bin/codesign', '--force', '--sign', identity, *options, framework)
        manifest = {'schema': 1, 'source_revision': revision, 'version': version,
                    'build': build_number, 'bundle_id': identifier, 'distribution': mode,
                    'dependencies': json.loads(LOCK.read_text()), 'files': inventory(resources)}
        (resources / 'release.json').write_text(json.dumps(manifest, sort_keys=True) + '\n')
        run('/usr/bin/codesign', '--force', '--sign', identity, *options, app)
        run('/usr/bin/codesign', '--verify', '--deep', '--strict', app)
        verify(resources)
        app.rename(output)
    return {'app': str(output), 'source_revision': revision, 'build': build_number,
            'manifest_sha256': sha256(output / 'Contents/Resources/release.json'),
            'test_only': test, 'distribution': mode, 'notarized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--version', required=True)
    parser.add_argument('--build', required=True)
    parser.add_argument('--bundle-id', required=True)
    parser.add_argument('--feed', required=True)
    parser.add_argument('--public-key', required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--test', action='store_true')
    modes.add_argument('--personal', action='store_true', help='Explicit personal ad-hoc app; Sparkle archive signing remains required')
    parser.add_argument('--signing-identity')
    args = parser.parse_args()
    receipt = build(args.output.absolute(), args.cache.absolute(), args.version, args.build,
                    args.bundle_id, args.feed, args.public_key, args.test, args.signing_identity, args.personal)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()

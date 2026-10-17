#!/usr/bin/env python3
"""Prepare a signed archive and appcast locally; never publish or install them."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import stat
import subprocess
import tempfile
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

try:
    from tools.package_app import dependency, extract, sha256, validate_options, verify
except ModuleNotFoundError:
    from package_app import dependency, extract, sha256, validate_options, verify

SPARKLE = 'http://www.andymatuschak.org/xml-namespaces/sparkle'


def validate_key_file(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or info.st_nlink != 1):
        raise ValueError('private_key_file_required')


def appcast(info, archive_url, signature, length):
    parsed = urlparse(archive_url)
    test = info.get('RepoHubTestMode') is True
    validate_options(info['CFBundleIdentifier'], archive_url, info['SUPublicEDKey'], test)
    if parsed.query or parsed.fragment or not parsed.path.endswith('.zip'):
        raise ValueError('direct_archive_url_required')
    ET.register_namespace('sparkle', SPARKLE)
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = info['CFBundleName']
    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = info['CFBundleName'] + ' ' + info['CFBundleShortVersionString']
    ET.SubElement(item, '{' + SPARKLE + '}version').text = info['CFBundleVersion']
    ET.SubElement(item, '{' + SPARKLE + '}shortVersionString').text = info['CFBundleShortVersionString']
    ET.SubElement(item, '{' + SPARKLE + '}minimumSystemVersion').text = info['LSMinimumSystemVersion']
    ET.SubElement(item, 'enclosure', {'url': archive_url, 'length': str(length),
        'type': 'application/octet-stream', '{' + SPARKLE + '}edSignature': signature})
    return ET.tostring(rss, encoding='utf-8', xml_declaration=True)


def archive_distribution(info, manifest):
    test = info.get('RepoHubTestMode') is True
    personal = info.get('RepoHubPersonalUpdates') is True
    if personal:
        if (test or info.get('CFBundleIdentifier') != 'com.leogoldberg.repohub'
                or manifest.get('distribution') != 'personal_adhoc'):
            raise ValueError('personal_distribution_mismatch')
        return 'personal_adhoc'
    if manifest.get('distribution') == 'personal_adhoc':
        raise ValueError('personal_distribution_mismatch')
    return 'test' if test else 'developer_id'


def prepare(app, output, archive_url, key_file, cache):
    validate_key_file(key_file)
    if output.exists() or output.is_symlink():
        raise ValueError('new_output_directory_required')
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    manifest = verify(app / 'Contents/Resources')
    if manifest['bundle_id'] != info['CFBundleIdentifier'] or manifest['build'] != info['CFBundleVersion']:
        raise ValueError('release_identity_mismatch')
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    mode = archive_distribution(info, manifest)
    if mode == 'developer_id':
        # A locally signed build alone does not establish distribution readiness.
        subprocess.run(['/usr/bin/xcrun', 'stapler', 'validate', str(app)], check=True)
        subprocess.run(['/usr/sbin/spctl', '--assess', '--type', 'execute', str(app)], check=True)
    # Validate URL before creating an archive or invoking a signing key.
    appcast(info, archive_url, '', 0)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='repohub-feed-', dir=output.parent) as folder:
        work = Path(folder)
        checker = work / 'update-key-check'
        subprocess.run(['/usr/bin/xcrun', 'swiftc', '-parse-as-library',
                        str(Path(__file__).resolve().parents[1] / 'native/UpdateKey.swift'),
                        '-module-cache-path', str(work / 'swift-cache'), '-o', str(checker)], check=True)
        subprocess.run([str(checker), str(key_file), info['SUPublicEDKey']], check=True)
        extract(dependency('sparkle', cache), work / 'sparkle')
        artifacts = work / 'artifacts'
        artifacts.mkdir(mode=0o700)
        archive = artifacts / Path(urlparse(archive_url).path).name
        subprocess.run(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
                        str(app), str(archive)], check=True)
        signer = work / 'sparkle/bin/sign_update'
        # The explicit file argument prevents a fallback to the daily login Keychain.
        signature = subprocess.check_output([str(signer), '-f', str(key_file), '-p', str(archive)], text=True).strip()
        subprocess.run([str(signer), '-f', str(key_file), '--verify', str(archive), signature], check=True)
        (artifacts / 'appcast.xml').write_bytes(appcast(info, archive_url, signature, archive.stat().st_size))
        receipt = {'source_revision': manifest['source_revision'], 'build': manifest['build'],
                   'archive_sha256': sha256(archive), 'archive_bytes': archive.stat().st_size,
                   'test_only': info.get('RepoHubTestMode') is True, 'distribution': mode,
                   'notarized': mode == 'developer_id', 'published': False}
        (artifacts / 'release-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        artifacts.rename(output)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive-url', required=True)
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.app.absolute(), args.output.absolute(), args.archive_url,
                             args.key_file.absolute(), args.cache.absolute()), indent=2))


if __name__ == '__main__':
    main()

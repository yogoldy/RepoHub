#!/usr/bin/env python3
"""Validate an unpublished Developer ID package; never publish or install it."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.channel_policy import feed_url, require_full_gate
from tools.package_app import sha256
from tools.publish_release import build_artifacts, command, signing_material
from tools.release_gate import source_fingerprint
from tools.release_policy import REPOSITORY
from tools.update_feed import SPARKLE


def source_revision():
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise ValueError('clean_committed_validation_source_required')
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def require_manual_hosted_request(revision):
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        return
    event_path = Path(os.environ['GITHUB_EVENT_PATH'])
    event = json.loads(event_path.read_text())
    if (os.environ.get('GITHUB_REPOSITORY') != REPOSITORY
            or os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
            or os.environ.get('GITHUB_SHA') != revision
            or event.get('inputs', {}).get('validate_signing') not in (True, 'true')):
        raise ValueError('explicit_exact_source_signing_validation_required')


def validation_plan(revision):
    # This deliberately cannot pass the managed-release receipt contract. It
    # reserves no global build number and has no downloadable release target.
    archive = 'RepoHub-signing-validation-arm64.zip'
    return {
        'schema': 2, 'publisher': 'repohub-unpublished-signing-validation',
        'source_revision': revision, 'version': '0.0.0', 'build': '1',
        'channel': 'dev', 'tag': 'repohub-signing-validation-unpublished',
        'archive': archive, 'archive_url': (
            f'https://github.com/{REPOSITORY}/releases/download/'
            f'repohub-signing-validation-unpublished/{archive}'),
        'feed_url': feed_url('dev'),
    }


def verify_result(folder, plan, work):
    expected = {plan['archive'], 'release-receipt.json', 'appcast.xml'}
    if ({path.name for path in folder.iterdir()} != expected
            or any(path.is_symlink() or not path.is_file() for path in folder.iterdir())):
        raise ValueError('validation_artifact_set_mismatch')
    receipt = json.loads((folder / 'release-receipt.json').read_text())
    if (any(receipt.get(key) != value for key, value in plan.items())
            or receipt.get('test_only') is not False
            or receipt.get('distribution') != 'developer_id'
            or receipt.get('notarized') is not True
            or receipt.get('published') not in (None, False)):
        raise ValueError('validation_package_receipt_mismatch')
    archive = folder / plan['archive']
    if (receipt.get('archive_sha256') != sha256(archive)
            or receipt.get('archive_bytes') != archive.stat().st_size):
        raise ValueError('validation_archive_mismatch')
    root = ET.fromstring((folder / 'appcast.xml').read_bytes())
    items = root.findall('channel/item')
    if len(items) != 1:
        raise ValueError('validation_feed_mismatch')
    item = items[0]
    enclosure = item.find('enclosure')
    if (enclosure is None or enclosure.get('url') != plan['archive_url']
            or enclosure.get('length') != str(receipt['archive_bytes'])
            or item.findtext('{' + SPARKLE + '}channel') != 'dev'
            or item.findtext('{' + SPARKLE + '}version') != plan['build']
            or item.findtext('{' + SPARKLE + '}shortVersionString') != plan['version']):
        raise ValueError('validation_feed_mismatch')
    verifier = work / 'verify-update'
    command(['/usr/bin/xcrun', 'swiftc', '-parse-as-library',
             '-module-cache-path', str(work / 'verification-cache'),
             str(ROOT / 'native/VerifyUpdate.swift'), '-o', str(verifier)])
    command([str(verifier), os.environ['REPOHUB_UPDATE_PUBLIC_KEY'],
             enclosure.get('{' + SPARKLE + '}edSignature', ''), str(archive)])
    return {key: receipt[key] for key in ('archive_sha256', 'archive_bytes')}


def run(gate_path, output):
    output = output.absolute()
    if output.resolve().is_relative_to(ROOT):
        raise ValueError('validation_receipt_must_be_outside_source')
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    report = {'schema': 1, 'profile': 'unpublished-signing', 'result': 'failed',
              'published': False, 'installed': False, 'source_unchanged': False,
              'scope': 'Unpublished package only; not live channel or installed-Mac acceptance.'}
    with os.fdopen(descriptor, 'w') as stream:
        try:
            revision = source_revision()
            report['source_revision'] = revision
            digest = source_fingerprint(ROOT)
            require_manual_hosted_request(revision)
            gate = json.loads(gate_path.read_text())
            require_full_gate(gate, revision)
            if gate.get('source_digest') != digest:
                raise ValueError('exact_gate_source_digest_required')
            report['failed_stage'] = 'certificate_import_and_signed_notarized_package'
            with tempfile.TemporaryDirectory(prefix='repohub-signing-validation-') as temporary:
                work = Path(temporary)
                work.chmod(0o700)
                plan = validation_plan(revision)
                with signing_material(work) as (notary_key, update_key):
                    artifacts = build_artifacts(work, plan, 'developer_id', notary_key, update_key)
                    report['failed_stage'] = 'independent_archive_verification'
                    report.update(verify_result(artifacts, plan, work))
                # The app and archive are never launched or uploaded as GitHub
                # artifacts. Only this bounded evidence survives the test.
            report['failed_stage'] = 'source_continuity'
            report['source_unchanged'] = source_revision() == revision and source_fingerprint(ROOT) == digest
            if not report['source_unchanged']:
                raise ValueError('source_changed_during_signing_validation')
            report.pop('failed_stage')
            report['result'] = 'passed'
        except Exception as error:
            # Do not serialize exception messages, subprocess arguments, signing
            # material, or raw Apple responses into public Actions logs.
            report['failure_type'] = type(error).__name__
            raise
        finally:
            json.dump(report, stream, indent=2)
            stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gate-receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        report = run(args.gate_receipt, args.output)
    except Exception:
        # A traceback could include a credential-bearing subprocess invocation.
        raise SystemExit('Unpublished signing validation failed; inspect its bounded receipt.')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()

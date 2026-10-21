#!/usr/bin/env python3
"""Run focused local Dev checks on committed source; never publish or install."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.channel_policy import DEV_CHECKS
from tools.package_app import NATIVE
from tools.release_gate import RecordedResult, source_fingerprint


def run(output):
    if output.exists() or output.is_symlink():
        raise ValueError('new_private_gate_receipt_required')
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('arm64_macos_dev_host_required')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise ValueError('clean_committed_dev_source_required')
    digest = source_fingerprint(ROOT)
    evidence = Path(tempfile.mkdtemp(prefix='repohub-dev-checks-'))
    report = {'schema': 1, 'profile': 'dev', 'source_commit': revision,
              'source_digest': digest, 'dirty_source': False, 'source_unchanged': False,
              'patterns': list(DEV_CHECKS), 'native_build': False, 'result': 'failed',
              'scope': 'Focused regressions and native build only; not full Golden Gate or installed acceptance.'}
    try:
        suite = unittest.TestSuite()
        for pattern in DEV_CHECKS:
            found = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=pattern)
            if not found.countTestCases():
                raise ValueError('missing_focused_test_module')
            suite.addTests(found)
        with (evidence / 'tests.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=RecordedResult).run(suite)
        report.update(tests_run=result.testsRun, skipped=len(result.skipped))
        if not result.wasSuccessful() or result.skipped or result.expectedFailures:
            raise ValueError('focused_regression_failed')
        for script in sorted((ROOT / 'web').glob('*.js')):
            subprocess.run(['node', '--check', str(script)], check=True, timeout=30)
        with (evidence / 'native-build.log').open('w') as log:
            subprocess.run(['/usr/bin/xcrun', 'swiftc', '-module-cache-path', str(evidence / 'swift-cache'),
                '-target', 'arm64-apple-macos13.0', *(str(ROOT / 'native' / name) for name in NATIVE),
                '-o', str(evidence / 'RepoHub'), '-framework', 'AppKit', '-framework', 'WebKit',
                '-framework', 'UserNotifications'], check=True, timeout=180, stdout=log, stderr=log)
        report['native_build'] = True
        report['source_unchanged'] = (source_fingerprint(ROOT) == digest
            and subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == revision
            and not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT))
        if not report['source_unchanged']:
            raise ValueError('dev_source_changed_during_checks')
        report['result'] = 'passed'
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', opener=lambda name, flags: os.open(name, flags | os.O_NOFOLLOW, 0o600)) as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output)))

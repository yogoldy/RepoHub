"""Guard one coordinated replacement using an untouched local rollback bundle.

This process lives in the rollback bundle, outside the app Sparkle replaces.
It never changes settings, source folders, permissions or repository archives.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import plistlib
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.request


def app_info(app):
    return plistlib.loads((app / 'Contents/Info.plist').read_bytes())


def validate_record(record):
    if not isinstance(record, dict) or set(record) != {
            'app', 'rollback', 'state', 'bundle_id', 'target_build', 'port'}:
        raise ValueError('invalid_recovery_record')
    app, rollback, state = (Path(record[key]) for key in ('app', 'rollback', 'state'))
    if (not all(path.is_absolute() for path in (app, rollback, state))
            or app.is_symlink() or rollback.is_symlink() or state.is_symlink()
            or app.suffix != '.app' or rollback.suffix != '.app'
            or not rollback.resolve().is_relative_to(state.resolve() / 'app-rollbacks')
            or type(record['port']) is not int or not 1024 < record['port'] <= 65535
            or not isinstance(record['target_build'], str) or not record['target_build'].isdigit()):
        raise ValueError('invalid_recovery_record')
    old = app_info(rollback)
    if old.get('CFBundleIdentifier') != record['bundle_id']:
        raise ValueError('rollback_identity_mismatch')
    return app, rollback, state


def healthy(status, record):
    if not isinstance(status, dict):
        return False
    release = status.get('application_release')
    return (isinstance(release, dict) and release.get('build') == record['target_build']
            and release.get('bundle_id') == record['bundle_id'])


def running_executable(pid):
    if type(pid) is not int or pid <= 1:
        return None
    library = ctypes.CDLL('/usr/lib/libproc.dylib')
    buffer = ctypes.create_string_buffer(4096)
    count = library.proc_pidpath(pid, buffer, len(buffer))
    return Path(os.fsdecode(buffer.value)) if count > 0 else None


def stop_owned(pid, allowed):
    actual = running_executable(pid)
    if actual is None:
        return True
    if actual not in allowed:
        return False
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if running_executable(pid) is None:
            return True
        time.sleep(.2)
    # Never force-kill a backup; a held publication lock must finish safely.
    return False


def guard(record, timeout=120):
    app, rollback, state = validate_record(record)
    deadline = time.monotonic() + timeout
    url = 'http://127.0.0.1:' + str(record['port']) + '/api/status'
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                status = json.load(response)
            if healthy(status, record):
                return 'healthy'
        except (OSError, ValueError):
            pass
        time.sleep(1)
    installed = app_info(app)
    if installed.get('CFBundleIdentifier') != record['bundle_id']:
        return 'identity_changed'
    if installed.get('CFBundleVersion') != record['target_build']:
        return 'not_installed'
    try:
        processes = json.loads((state / 'application-processes.json').read_text())
    except (OSError, ValueError):
        return 'process_evidence_missing'
    allowed = {app / 'Contents/MacOS/RepoHub',
               app / 'Contents/Resources/python/bin/python3.14'}
    for key in ('helper_pid', 'app_pid'):
        if not stop_owned(processes.get(key), allowed):
            return 'shutdown_blocked'
    # Copy before renaming, so a copy failure leaves the candidate untouched.
    with tempfile.TemporaryDirectory(prefix='repohub-recover-', dir=app.parent) as folder:
        replacement = Path(folder) / app.name
        shutil.copytree(rollback, replacement, symlinks=True)
        subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(replacement)], check=True)
        failed = state / 'app-rollbacks' / ('failed-' + record['target_build'] + '-' + str(time.time_ns()) + '.app')
        app.rename(failed)
        try:
            replacement.rename(app)
        except BaseException:
            failed.rename(app)
            raise
    subprocess.Popen([str(app / 'Contents/MacOS/RepoHub')], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 'restored'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', required=True, type=Path)
    args = parser.parse_args()
    record = json.loads(args.record.read_text())
    try:
        outcome = guard(record)
    except (OSError, ValueError, subprocess.SubprocessError):
        outcome = 'recovery_failed'
    # Bounded local evidence. No paths or exception prose are exported.
    output = args.record.with_suffix('.result.json')
    output.write_text(json.dumps({'result': outcome, 'target_build': record.get('target_build')}))
    output.chmod(0o600)


if __name__ == '__main__':
    main()

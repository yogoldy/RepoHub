#!/usr/bin/env python3
"""Coordinate isolated-account acceptance without cross-user launchctl or sudo.

Both accounts take the same read-only flock before staging/restoration. The daily
account owns its restoration journal; the test account owns its jobs and lease.
Neither account needs access to the other's private configuration or credentials.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
import re
from pathlib import Path
import shutil
import socket
import subprocess
import time
import uuid
try:
    from tools import reliability_acceptance as h
except ImportError:
    import reliability_acceptance as h

COORD_PREFIX = 'repohub-account-coordination-'


def public_json(path, value):
    h.write_json(path, value)
    path.chmod(0o644)


def coord_info(path):
    path = Path(path)
    if path.parent != h.RUN_PARENT or not path.name.startswith(COORD_PREFIX) or path.is_symlink():
        raise ValueError('Unowned coordination directory')
    info = h.read_json(path / 'peer.json')
    if info.get('marker') != h.MARKER or info.get('test_uid') != path.stat().st_uid or path.stat().st_mode & 0o022:
        raise ValueError('Invalid coordination owner')
    for name in ['peer.json', 'lock']:
        file = path / name
        if file.is_symlink() or file.stat().st_uid != info['test_uid'] or file.stat().st_mode & 0o022:
            raise ValueError('Redirected coordination evidence')
    if (not re.fullmatch(r'[0-9a-f]{32}', info.get('run_id', ''))
            or not re.fullmatch(r'[0-9a-f]{40}', info.get('source_commit', ''))
            or not isinstance(info.get('deadline'), (float, int))
            or info.get('state') not in ['prepared', 'active', 'stopped']):
        raise ValueError('Invalid peer state')
    return info


@contextmanager
def coordinated(path):
    info = coord_info(path)
    # flock permits LOCK_EX on a read-only descriptor; other accounts cannot edit
    # this lock or replace its inode in the test-owned directory.
    with (Path(path) / 'lock').open('r') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if os.fstat(lock.fileno()).st_ino != (Path(path) / 'lock').stat().st_ino:
            raise ValueError('Coordination lock replaced')
        yield coord_info(path)


def port_free():
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(('127.0.0.1', 8767))
            return True
        except OSError:
            return False


def wait_for_free_port(seconds=5):
    deadline = time.monotonic() + seconds
    while True:
        if port_free():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def prepare_peer(base, seconds):
    base, marker = h.guarded_run(base)
    if not 60 <= seconds <= 3600:
        raise ValueError('Bounded test lifetime required')
    if (base / 'account-peer.json').exists():
        raise ValueError('Account coordination already prepared')
    coord = h.RUN_PARENT / (COORD_PREFIX + marker['id'])
    coord.mkdir(mode=0o755)
    coord.chmod(0o755)
    (coord / 'lock').touch(mode=0o444)
    (coord / 'lock').chmod(0o444)
    peer = {'marker': h.MARKER, 'run_id': marker['id'], 'test_uid': os.getuid(),
            'source_commit': marker['source_commit'], 'state': 'prepared', 'deadline': time.time() + seconds}
    public_json(coord / 'peer.json', peer)
    h.write_json(base / 'account-peer.json', {'coord': str(coord)})
    return {'coord': str(coord), 'deadline': peer['deadline']}


def loaded_labels(journal):
    return [label for label in journal['test_labels'] if h.job_loaded(label)]


def cleanup_test(base):
    base, marker = h.guarded_run(base)
    journal = h.read_json(base / 'account-journal.json')
    prefix = 'com.leogoldberg.repohub.acceptance.' + marker['id']
    if journal.get('kind') != 'test' or journal['test_labels'] != [prefix + '.service', prefix + '.app']:
        raise ValueError('Unowned test jobs')
    with (base / 'cleanup.lock').open('a') as own_lock:
        fcntl.flock(own_lock, fcntl.LOCK_EX)
        with coordinated(journal['coord']) as peer:
            if peer['test_uid'] != os.getuid() or peer['run_id'] != marker['id']:
                raise ValueError('Foreign test lease')
            for label in reversed(journal['test_labels']):
                h.run(['/bin/launchctl', 'kill', 'SIGCONT', h.domain() + '/' + label], check=False)
                h.run(['/bin/launchctl', 'bootout', h.domain() + '/' + label], check=False)
            stopped = not loaded_labels(journal)
            registration_error = None
            try:
                registration_error = h.unregister_native(base, marker, Path.home())
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                registration_error = type(error).__name__
            try:
                preserved = h.capture([Path(p) for p in journal['protected_before']]) == journal['protected_before']
                capture_error = None
            except OSError as error:
                preserved, capture_error = False, type(error).__name__
            if stopped:
                peer['state'] = 'stopped'
                public_json(Path(journal['coord']) / 'peer.json', peer)
            result = {'owned_jobs_stopped': stopped, 'protected_preserved': preserved,
                      'native_registration_error': registration_error, 'capture_error': capture_error}
            h.write_json(base / 'cleanup.json', result)
            return result


def safe_restore_port(journal):
    if port_free():
        return True
    # A partially paused or already restored daily helper may legitimately own
    # the port. Never launch the daily client against an unknown/test helper.
    service = next(label for label in journal['daily_labels'] if label.endswith('.service'))
    if not h.job_loaded(service) or not journal.get('daily_repos_root'):
        return False
    try:
        return h.get_status().get('repos_root') == journal['daily_repos_root']
    except OSError:
        return False


def cleanup_hold(base):
    base, marker = h.guarded_run(base)
    journal = h.read_json(base / 'account-journal.json')
    if journal.get('kind') != 'hold':
        raise ValueError('Not a daily-account hold')
    h.validate_labels(journal['daily_labels'])
    if not set(journal['restore_intents']) <= set(journal['daily_labels']):
        raise ValueError('Unowned restoration intent')
    with (base / 'cleanup.lock').open('a') as own_lock:
        fcntl.flock(own_lock, fcntl.LOCK_EX)
        with coordinated(journal['coord']) as peer:
            if peer['test_uid'] == os.getuid() or peer['run_id'] != journal['peer_run_id']:
                raise ValueError('Wrong isolated account')
            previous = h.read_json(base / 'cleanup.json') if (base / 'cleanup.json').exists() else {}
            if previous.get('daily_jobs_restored'):
                return previous
            if peer['state'] == 'active' or not safe_restore_port(journal):
                return {'daily_jobs_restored': False, 'waiting_for_test_cleanup': True}
            public_json(base / 'hold.json', {**h.read_json(base / 'hold.json'), 'state': 'restoring'})
            try:
                preserved = h.capture([Path(p) for p in journal['protected_before']]) == journal['protected_before']
                capture_error = None
            except OSError as error:
                preserved, capture_error = False, type(error).__name__
            errors = []
            for label in reversed(journal['restore_intents']):
                if not h.job_loaded(label):
                    plist = Path(journal['daily_home']) / 'Library/LaunchAgents' / (label + '.plist')
                    if h.run(['/bin/launchctl', 'bootstrap', h.domain(), str(plist)], check=False).returncode:
                        errors.append(label)
            restored = all(h.job_loaded(label) for label in journal['restore_intents'])
            result = {'daily_jobs_restored': restored, 'protected_preserved': preserved,
                      'restore_errors': errors, 'capture_error': capture_error}
            h.write_json(base / 'cleanup.json', result)
            if restored:
                public_json(base / 'hold.json', {**h.read_json(base / 'hold.json'), 'state': 'restored'})
            return result


def cleanup(base):
    base, _ = h.guarded_run(base)
    journal = h.read_json(base / 'account-journal.json')
    return cleanup_test(base) if journal['kind'] == 'test' else cleanup_hold(base)


def watchdog(base):
    base, _ = h.guarded_run(base)
    h.write_json(base / 'account-watchdog-ready.json', {'pid': os.getpid()})
    triggered = False
    while True:
        journal = h.read_json(base / 'account-journal.json')
        try:
            os.kill(journal['controller_pid'], 0)
        except ProcessLookupError:
            triggered = True
        triggered = (triggered or time.time() >= journal['deadline'] or (base / 'stop').exists()
                     or (journal['kind'] == 'hold' and coord_info(journal['coord'])['state'] == 'stopped'))
        if triggered:
            result = cleanup(base)
            if result.get('daily_jobs_restored') or result.get('owned_jobs_stopped'):
                return
        time.sleep(0.5)


def start_watchdog(base, python):
    log = (base / 'account-watchdog.log').open('a')
    subprocess.Popen([str(python), str(base / 'account-guard.py'), 'watchdog', '--run', str(base)],
                     stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    log.close()
    for _ in range(100):
        if (base / 'account-watchdog-ready.json').exists():
            return
        time.sleep(0.05)
    raise RuntimeError('Independent account watchdog not ready; no jobs paused')


def own_scripts(base):
    shutil.copy2(Path(__file__), base / 'account-guard.py')
    shutil.copy2(Path(h.__file__), base / 'reliability_acceptance.py')


def hold_daily(coord, python, labels, evidence):
    h.validate_labels(labels)
    peer = coord_info(coord)
    if peer['test_uid'] == os.getuid() or peer['state'] != 'prepared' or not 30 < peer['deadline'] - time.time() <= 3600:
        raise ValueError('Fresh isolated-account peer required')
    if not evidence.is_file() or not evidence.read_text().strip():
        raise ValueError('Native control evidence required')
    home = Path.home()
    labels = sorted(labels, key=lambda label: label.endswith('service'))
    for label in labels:
        plist = home / 'Library/LaunchAgents' / (label + '.plist')
        if not plist.is_file() or h.plistlib.loads(plist.read_bytes()).get('Label') != label or not h.job_loaded(label):
            raise ValueError('Daily registration not loaded')
    daily_status = h.get_status()
    if daily_status.get('backup', {}).get('running') is not False:
        raise ValueError('Cannot pause active or unknown backup')
    base = h.RUN_PARENT / (h.PREFIX + uuid.uuid4().hex)
    base.mkdir(mode=0o755)
    base.chmod(0o755)
    marker = {'marker': h.MARKER, 'run': str(base), 'id': uuid.uuid4().hex}
    public_json(base / 'run.json', marker)
    own_scripts(base)
    before = h.capture(h.protected_paths(home, labels))
    rollback = base / 'rollback'
    rollback.mkdir(mode=0o700)
    for index, path in enumerate(h.protected_paths(home, labels)):
        if path.is_dir(): shutil.copytree(path, rollback / str(index), symlinks=True)
        elif path.is_file(): shutil.copy2(path, rollback / str(index))
    journal = {'kind': 'hold', 'controller_pid': os.getpid(), 'deadline': peer['deadline'] + 30,
               'coord': str(coord), 'peer_run_id': peer['run_id'], 'daily_labels': labels,
               'daily_home': str(home), 'daily_repos_root': daily_status.get('repos_root'),
               'restore_intents': [], 'protected_before': before}
    h.write_json(base / 'account-journal.json', journal)
    public_json(base / 'hold.json', {'state': 'preparing', 'test_run_id': peer['run_id'],
                                  'coord': str(coord), 'daily_uid': os.getuid(), 'source_commit': peer['source_commit']})
    try:
        start_watchdog(base, python)
        with coordinated(coord) as current:
            if current != peer:
                raise ValueError('Peer changed before pause')
            for label in labels:
                journal['restore_intents'].append(label)
                h.write_json(base / 'account-journal.json', journal)
                h.run(['/bin/launchctl', 'bootout', h.domain() + '/' + label])
            if h.capture(h.protected_paths(home, labels)) != before or not wait_for_free_port():
                raise RuntimeError('Pause baseline changed or fixed port still occupied')
            public_json(base / 'hold.json', {**h.read_json(base / 'hold.json'), 'state': 'held'})
        print(json.dumps({'daily_hold': str(base)}), flush=True)
        while (time.time() < journal['deadline'] and not (base / 'stop').exists()
               and not (base / 'cleanup.json').exists() and coord_info(coord)['state'] != 'stopped'):
            time.sleep(0.25)
    finally:
        print(json.dumps(cleanup_hold(base)), flush=True)


def stage_test(base, hold, python, evidence):
    base, marker = h.guarded_run(base)
    if (base / 'account-journal.json').exists():
        raise ValueError('Account run already started')
    if not evidence.is_file() or not evidence.read_text().strip():
        raise ValueError('Native control evidence required')
    coord = Path(h.read_json(base / 'account-peer.json')['coord'])
    peer = coord_info(coord)
    if peer['test_uid'] != os.getuid() or peer['run_id'] != marker['id'] or peer['source_commit'] != marker['source_commit']:
        raise ValueError('Wrong account or candidate')
    home = Path.home()
    before = h.capture(h.protected_paths(home, []))
    prefix = 'com.leogoldberg.repohub.acceptance.' + marker['id']
    labels = [prefix + '.service', prefix + '.app']
    journal = {'kind': 'test', 'controller_pid': os.getpid(), 'deadline': peer['deadline'],
               'coord': str(coord), 'test_labels': labels, 'protected_before': before}
    own_scripts(base)
    h.write_json(base / 'account-journal.json', journal)
    # Existing scoped control operations use this exact owned label journal.
    h.write_json(base / 'journal.json', {'test_labels': labels})
    h.run([str(python), '-c', 'import ast,pathlib,sys; [ast.parse(p.read_text()) for p in pathlib.Path(sys.argv[1]).glob("*.py")]', str(base / 'runtime')])
    h.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(base / 'RepoHub Reliability.app')])
    try:
        start_watchdog(base, python)
        with coordinated(coord) as current:
            record_file = hold / 'hold.json'
            if hold.parent != h.RUN_PARENT or not hold.name.startswith(h.PREFIX) or hold.is_symlink() or record_file.is_symlink():
                raise ValueError('Redirected daily hold')
            record = h.read_json(record_file)
            if (record.get('state') != 'held' or record.get('daily_uid') != hold.stat().st_uid
                    or record_file.stat().st_uid != hold.stat().st_uid or hold.stat().st_uid == os.getuid()
                    or record.get('coord') != str(coord) or record.get('test_run_id') != marker['id']
                    or record.get('source_commit') != marker['source_commit'] or current['state'] != 'prepared'
                    or time.time() >= current['deadline'] or not port_free()):
                raise ValueError('Daily restoration guard is not held for this candidate')
            app = h.register_native(base, marker, home)
            current['state'] = 'active'
            public_json(coord / 'peer.json', current)  # active BEFORE launching; restoration must wait
            env = {'HOME': str(base / 'home'), 'CFFIXED_USER_HOME': str(base / 'home'), 'PYTHONDONTWRITEBYTECODE': '1'}
            for label, argv in zip(labels, [[str(python), str(base / 'runtime/repohub.py'), '--config', str(base / 'config.json')], [str(app / 'Contents/MacOS/RepoHub')]]):
                suffix = label.rsplit('.', 1)[-1]
                plist = {'Label': label, 'ProgramArguments': argv, 'RunAtLoad': True, 'EnvironmentVariables': env,
                         'StandardOutPath': str(base / (suffix + '.log')), 'StandardErrorPath': str(base / (suffix + '.log'))}
                file = base / (suffix + '.plist')
                file.write_bytes(h.plistlib.dumps(plist))
                h.run(['/bin/launchctl', 'bootstrap', h.domain(), str(file)])
        for _ in range(100):
            try:
                observed = h.get_status()
                if observed.get('repos_root') == str(base / 'fixtures/home'): break
            except OSError: pass
            time.sleep(0.1)
        else: raise RuntimeError('Test helper did not start')
        h.write_json(base / 'ready.json', {'status': observed, 'source_commit': marker['source_commit']})
        print(json.dumps({'ready': str(base)}), flush=True)
        while time.time() < journal['deadline'] and not (base / 'stop').exists() and not (base / 'cleanup.json').exists():
            time.sleep(0.25)
    finally:
        print(json.dumps(cleanup_test(base)), flush=True)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('peer'); p.add_argument('--run', type=Path, required=True); p.add_argument('--seconds', type=int, default=1800)
    p = sub.add_parser('hold'); p.add_argument('--coord', type=Path, required=True); p.add_argument('--python', type=Path, required=True)
    p.add_argument('--daily-label', action='append', required=True); p.add_argument('--control-evidence', type=Path, required=True)
    p = sub.add_parser('stage'); p.add_argument('--run', type=Path, required=True); p.add_argument('--hold', type=Path, required=True)
    p.add_argument('--python', type=Path, required=True); p.add_argument('--control-evidence', type=Path, required=True)
    for name in ['cleanup', 'watchdog']:
        p = sub.add_parser(name); p.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'peer': print(json.dumps(prepare_peer(args.run, args.seconds)))
    elif args.command == 'hold': hold_daily(args.coord, args.python, args.daily_label, args.control_evidence)
    elif args.command == 'stage': stage_test(args.run, args.hold, args.python, args.control_evidence)
    elif args.command == 'watchdog': watchdog(args.run)
    else: print(json.dumps(cleanup(args.run)))


if __name__ == '__main__':
    main()

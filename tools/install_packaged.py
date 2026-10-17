#!/usr/bin/env python3
"""One-time guarded legacy-to-bundle install; subsequent updates use Sparkle."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import signal
import subprocess
import sys
import time
from urllib.request import urlopen
import uuid

SERVICE = 'com.leogoldberg.repohub.service'
FRONTEND = 'com.leogoldberg.repohub.app'
PROTECTED = ('config.json', 'data/workspace-registry.json', 'data/settings.json',
             'data/repo-settings.json', 'data/views.json')


def read_json(path):
    return json.loads(path.read_text())


def save(path, value):
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value, indent=2) + '\n')
    pending.chmod(0o600)
    pending.replace(path)


def protected_hashes(state):
    return {name: hashlib.sha256((state / name).read_bytes()).hexdigest()
            if (state / name).is_file() else None for name in PROTECTED}


def require_legacy(home):
    state = home / 'Library/Application Support/RepoHub'
    app = home / 'Applications/Repo Hub.app'
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    config = read_json(state / 'config.json')
    if (info.get('CFBundleIdentifier') != 'com.leogoldberg.repohub'
            or info.get('RepoHubPackaged') is True
            or Path(config['state_dir']).resolve() != state.resolve() or config['port'] != 8767):
        raise ValueError('known_legacy_install_required')
    agents = home / 'Library/LaunchAgents'
    service = plistlib.loads((agents / (SERVICE + '.plist')).read_bytes())
    frontend = plistlib.loads((agents / (FRONTEND + '.plist')).read_bytes())
    expected = [str(app / 'Contents/MacOS/RepoHub'), '--helper']
    arguments = service.get('ProgramArguments', [])
    if (service.get('Label') != SERVICE or arguments[:2] != expected or len(arguments) != 6
            or arguments[3:] != [str(state / 'runtime/repohub.py'), '--config', str(state / 'config.json')]
            or frontend.get('Label') != FRONTEND
            or frontend.get('ProgramArguments') != [str(app / 'Contents/MacOS/RepoHub'), '--background']):
        raise ValueError('known_launch_agents_required')
    return state, app, agents, Path(arguments[2]).resolve()


def command(arguments, check=True):
    result = subprocess.run(arguments, capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError('migration_command_failed:' + Path(arguments[0]).name)
    return result


def pid_path(pid):
    buffer = ctypes.create_string_buffer(4096)
    size = ctypes.CDLL('/usr/lib/libproc.dylib').proc_pidpath(int(pid), buffer, len(buffer))
    return Path(os.fsdecode(buffer.value)).resolve() if size > 0 else None


def interpreter_process_path(interpreter):
    probe = (
        "import ctypes,os; b=ctypes.create_string_buffer(4096); "
        "n=ctypes.CDLL('/usr/lib/libproc.dylib').proc_pidpath(os.getpid(),b,len(b)); "
        "assert n>0; print(os.fsdecode(b.value))"
    )
    result = command([str(interpreter), '-I', '-c', probe])
    path = Path(result.stdout.strip())
    if not path.is_absolute() or not path.is_file():
        raise ValueError('configured_interpreter_identity_unavailable')
    return path.resolve()


def service_pid():
    result = command(['launchctl', 'list'])
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] == SERVICE and fields[0].isdigit():
            return int(fields[0])
    raise ValueError('running_legacy_service_required')


def observation():
    with urlopen('http://127.0.0.1:8767/api/status', timeout=8) as response:
        return json.load(response)


def freeze_idle_legacy(state, expected_executable, record_path):
    if observation().get('backup', {}).get('running') is not False:
        raise ValueError('backup_running_retry_after_completion')
    pid = service_pid()
    if pid_path(pid) != expected_executable:
        raise ValueError('legacy_process_identity_mismatch')
    record = read_json(record_path)
    record['frozen_pid'] = pid
    save(record_path, record)
    os.kill(pid, signal.SIGSTOP)
    # The audited legacy backup function persists running=True before touching
    # archives. Once frozen, a false disk flag proves no archive write is active;
    # a thread stopped before that flag has not started writing an archive yet.
    if read_json(state / 'status.json').get('backup', {}).get('running') is not False:
        os.kill(pid, signal.SIGCONT)
        raise ValueError('backup_started_during_handoff_retry')
    return pid


def stop_legacy(pid):
    stopping = subprocess.Popen(['launchctl', 'bootout', f'gui/{os.getuid()}/{SERVICE}'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.kill(pid, signal.SIGTERM)
    os.kill(pid, signal.SIGCONT)
    if stopping.wait(timeout=30) != 0:
        raise RuntimeError('legacy_bootout_failed')
    command(['launchctl', 'bootout', f'gui/{os.getuid()}/{FRONTEND}'])


def restore(record_path):
    record = read_json(record_path)
    state, app, agents = (Path(record[key]) for key in ('state', 'app', 'agents'))
    if record.get('phase') in ('accepted', 'restored'):
        return
    frozen = record.get('frozen_pid')
    if frozen and pid_path(frozen) == Path(record['legacy_python']):
        try:
            os.kill(frozen, signal.SIGCONT)
        except ProcessLookupError:
            pass
    if record.get('phase') == 'prepared':
        record['phase'] = 'restored'
        save(record_path, record)
        return
    processes = state / 'application-processes.json'
    if processes.exists():
        helper = read_json(processes).get('helper_pid')
        expected = (app / 'Contents/Resources/python/bin/python3').resolve()
        if helper and pid_path(helper) == expected:
            os.kill(helper, signal.SIGTERM)
            for _ in range(180):
                if pid_path(helper) != expected:
                    break
                time.sleep(1)
            else:
                raise RuntimeError('active_packaged_helper_prevents_rollback')
    command(['launchctl', 'bootout', f'gui/{os.getuid()}/{FRONTEND}'], check=False)
    previous = record_path.parent / 'previous.app'
    if previous.exists():
        failed = record_path.parent / 'failed.app'
        if app.exists():
            app.rename(failed)
        previous.rename(app)
    for label in (SERVICE, FRONTEND):
        source = record_path.parent / (label + '.plist')
        target = agents / source.name
        shutil.copy2(source, target)
        command(['launchctl', 'bootout', f'gui/{os.getuid()}/{label}'], check=False)
        command(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(target)])
    record['phase'] = 'restored'
    save(record_path, record)


def watch(record_path, parent):
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if read_json(record_path).get('phase') in ('accepted', 'restored'):
            return
        try:
            os.kill(parent, 0)
        except ProcessLookupError:
            break
        time.sleep(1)
    restore(record_path)


def install(candidate, revision):
    try:
        from tools.package_app import verify
    except ModuleNotFoundError:
        from package_app import verify
    home = Path.home()
    state, app, agents, interpreter = require_legacy(home)
    python = interpreter_process_path(interpreter)
    manifest = verify(candidate / 'Contents/Resources')
    info = plistlib.loads((candidate / 'Contents/Info.plist').read_bytes())
    if (manifest['source_revision'] != revision or manifest['bundle_id'] != 'com.leogoldberg.repohub'
            or info.get('RepoHubPackaged') is not True or info.get('RepoHubTestMode') is not False):
        raise ValueError('accepted_personal_bundle_required')
    command(['codesign', '--verify', '--deep', '--strict', str(candidate)])
    os.umask(0o077)
    journal = state / 'rollback' / ('packaged-' + uuid.uuid4().hex[:12])
    journal.mkdir(parents=True, mode=0o700)
    baseline = protected_hashes(state)
    for label in (SERVICE, FRONTEND):
        shutil.copy2(agents / (label + '.plist'), journal / (label + '.plist'))
    for name in PROTECTED:
        if (state / name).exists():
            target = journal / 'protected' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(state / name, target)
    staged = app.parent / ('.repohub-stage-' + uuid.uuid4().hex[:12] + '.app')
    command(['ditto', str(candidate), str(staged)])
    verify(staged / 'Contents/Resources')
    record_path = journal / 'migration.json'
    save(record_path, {'phase': 'prepared', 'state': str(state), 'app': str(app),
         'agents': str(agents), 'source_revision': revision, 'legacy_python': str(python),
         'protected': baseline, 'build': manifest['build']})
    guard = journal / 'installer.py'
    shutil.copy2(Path(__file__), guard)
    log = (journal / 'watchdog.log').open('w')
    watcher = subprocess.Popen([sys.executable, str(guard), '--watch', str(record_path), '--parent', str(os.getpid())],
                               start_new_session=True, stdout=log, stderr=log)
    try:
        pid = freeze_idle_legacy(state, python, record_path)
        record = read_json(record_path)
        record['phase'] = 'stopping'
        save(record_path, record)
        stop_legacy(pid)
        if protected_hashes(state) != baseline:
            raise ValueError('protected_state_changed_before_install')
        app.rename(journal / 'previous.app')
        staged.rename(app)
        (agents / (SERVICE + '.plist')).rename(journal / 'retired-service.plist')
        command(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(agents / (FRONTEND + '.plist'))])
        for _ in range(90):
            try:
                current = observation()
                release = current.get('application_release', {})
                if release.get('source_revision') == revision and release.get('build') == manifest['build']:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('matching_packaged_helper_unavailable')
        if protected_hashes(state) != baseline:
            raise ValueError('protected_state_changed_after_install')
        record = read_json(record_path)
        record.update(phase='accepted', protected_unchanged=True)
        save(record_path, record)
        print(json.dumps({'installed': revision, 'build': manifest['build'], 'rollback': str(journal),
                          'protected_unchanged': True, 'repos': len(current.get('repos', []))}))
        watcher.wait(timeout=5)
    except BaseException:
        restore(record_path)
        raise
    finally:
        if staged.exists():
            shutil.rmtree(staged)
        log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path)
    parser.add_argument('--source')
    parser.add_argument('--watch', type=Path)
    parser.add_argument('--parent', type=int)
    args = parser.parse_args()
    if sys.platform != 'darwin':
        raise SystemExit('macOS required')
    if args.watch and args.parent:
        watch(args.watch, args.parent)
    elif args.app and args.source:
        install(args.app.resolve(), args.source)
    else:
        parser.error('--app and --source are required')


if __name__ == '__main__':
    main()

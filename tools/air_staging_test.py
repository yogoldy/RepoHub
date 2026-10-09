#!/usr/bin/env python3
"""Destructive checks ONLY inside the explicitly provisioned RepoHub Air test fixture."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = Path.home() / 'Library/Application Support/RepoHub-Air-Test'
STATE = Path.home() / 'Library/Application Support/RepoHub'
ROOT = BASE / 'repos'
REPO = ROOT / 'SampleProject'
SOURCE = BASE / 'source'
ORIGIN = 'http://127.0.0.1:8767'


def main():
    os.umask(0o077)
    config = json.loads((STATE / 'config.json').read_text())
    if Path(config['repos_root']).resolve() != ROOT.resolve():
        raise RuntimeError('Refusing non-staging repo home')
    cloud = Path.home() / 'Library/Mobile Documents/com~apple~CloudDocs/RepoHub Air Test/Snapshots'
    if Path(config['backup_root']).resolve() != cloud.resolve():
        raise RuntimeError('Refusing non-staging backup output')
    for path in (BASE, ROOT, REPO, SOURCE, STATE):
        if path.is_symlink() or not path.is_dir():
            raise RuntimeError('Unsafe/missing staging directory')
    marker = BASE / 'STAGING_TEST_AUTHORIZED.json'
    authorization = json.loads(marker.read_text())
    if authorization != {'repo': 'SampleProject', 'upstream': 'https://github.com/pypa/sampleproject.git',
                         'commit': '621e4974ca25ce531773def586ba3ed8e736b3fc'}:
        raise RuntimeError('Unexpected staging authorization')
    out = BASE / ('stage-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))
    out.mkdir(mode=0o700)
    events = (out / 'events.jsonl').open('x')
    report = {'schema': 1, 'started_at': datetime.now(timezone.utc).isoformat(),
              'checks': [], 'status': 'running', 'limitations': [
                  'SSH does not prove visible menu bar appearance or Finder button interaction.',
                  'Battery unplugging, sleep/wake, network outages and the 15-minute timer are not exercised.',
                  'macOS upload acknowledgement is distinct from independent reception on the other Mac.',
                  'App binaries were compiled on the Air; this is not identical-binary testing.']}

    def emit(event, **fields):
        events.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'event': event, **fields}) + '\n')
        events.flush()

    def save():
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')

    def check(name, condition, **details):
        report['checks'].append({'name': name, 'passed': bool(condition), **details})
        emit('check', **report['checks'][-1]); save()
        if not condition:
            raise AssertionError(name)
        print('PASS ' + name, flush=True)

    def command(args):
        result = subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=120)
        emit('command', args=[str(x) for x in args], returncode=result.returncode,
             stdout=result.stdout, stderr=result.stderr)
        if result.returncode:
            raise RuntimeError('Command failed: ' + str(args[0]))
        return result.stdout.strip()

    def get(path):
        with urllib.request.urlopen(ORIGIN + path, timeout=20) as response:
            return json.load(response)

    def post(path, payload, expect=200):
        token = get('/api/session')['token']
        request = urllib.request.Request(ORIGIN + path, json.dumps(payload).encode(),
            {'Content-Type': 'application/json', 'Origin': ORIGIN, 'X-RepoHub-Token': token})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                code, result = response.status, json.load(response)
        except urllib.error.HTTPError as error:
            code, result = error.code, json.load(error)
        emit('api_write', path=path, code=code)  # Never log the session token.
        if code != expect:
            raise RuntimeError('Unexpected API status: ' + str(code))
        return result

    def wait(label, predicate, timeout=180):
        started = time.monotonic()
        while True:
            status = get('/api/status')
            if predicate(status):
                emit('wait_complete', label=label, seconds=round(time.monotonic()-started, 3))
                return status
            if time.monotonic() - started >= timeout:
                (out / ('timeout-' + label + '.json')).write_text(json.dumps(status, indent=2))
                raise TimeoutError(label)
            time.sleep(2)

    def snapshot(label):
        status = get('/api/status')
        (out / (label + '-status.json')).write_text(json.dumps(status, indent=2))
        return status

    def rows(status):
        return {row['name']: row for row in status['repos']}

    def row(status):
        return rows(status)['SampleProject']

    def scan():
        previous = get('/api/status')['scan_id']
        post('/api/scan', {}, 202)
        return wait('scan', lambda s: s['scan_id'] != previous)

    def backup(label):
        previous = get('/api/status')['backup'].get('run_id')
        post('/api/backup', {}, 202)
        status = wait(label, lambda s: not s['backup'].get('running') and s['backup'].get('run_id') != previous)
        check(label + '_no_errors', not status['backup'].get('errors'), errors=status['backup'].get('errors'))
        scan()
        return snapshot(label)

    def archive_map(status):
        return {name: r.get('last_backup', {}).get('archive') for name,r in rows(status).items()}

    def restore(label, status):
        item = row(status)['last_backup']; capture = out / (label + '-capture'); restored = out / (label + '-restore')
        command([sys.executable, SOURCE/'restore_audit.py', 'capture', '--source', REPO,
                 '--archive-sha256', item['sha256'], '--out', capture])
        manifest_hash = hashlib.sha256((capture/'expected.json').read_bytes()).hexdigest()
        command([sys.executable, SOURCE/'restore_audit.py', 'verify', '--archive', item['archive'],
                 '--expected', capture/'expected.json', '--manifest-sha256', manifest_hash, '--out', restored])
        check(label + '_restore', json.loads((restored/'result.json').read_text())['result'] == 'passed')
        return {'archive': item['archive'], 'archive_sha256': item['sha256'],
                'expected': str(capture/'expected.json'), 'manifest_sha256': manifest_hash}

    original = get('/api/settings')
    override_original = None
    emit('run_start', harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    report['source_revision'] = command(['git', '-C', SOURCE, 'rev-parse', 'HEAD'])
    report['upstream_revision'] = command(['git', '-C', REPO, 'rev-parse', 'HEAD'])
    check('pinned_full_history', report['upstream_revision'] == authorization['commit'] and
          command(['git', '-C', REPO, 'rev-parse', '--is-shallow-repository']) == 'false',
          commits=int(command(['git', '-C', REPO, 'rev-list', '--count', 'HEAD'])))
    try:
        policy = copy.deepcopy(original['settings'])
        policy['battery'].update(frequency_minutes=0, after_edits=False)
        policy['adapter'].update(frequency_minutes=240, after_edits=False)
        post('/api/settings', {'settings': policy, 'revision': original['revision']})
        check('battery_manual_only_saved', get('/api/settings')['settings']['battery'] == policy['battery'])
        initial = backup('baseline')
        check('baseline_hashes_match', row(initial)['verification']['state'] == 'matched')
        restore('baseline', initial)
        uploaded = wait('baseline_upload', lambda s: row(s)['cloud'].get('state') == 'uploaded' and
                        row(s)['cloud'].get('archive') == row(s)['last_backup']['archive'], 180)
        check('baseline_macos_uploaded', True, checked_at=row(uploaded)['cloud']['checked_at'])

        shutil.rmtree(REPO/'src/sample')
        check('deleted_folder_detected', row(scan())['needs_backup'])
        deleted = backup('delete_folder')
        check('delete_only_changes_sample_archive', all(archive_map(deleted)[n] == a for n,a in archive_map(initial).items() if n != 'SampleProject'))
        restore('deleted_folder', deleted)

        added = REPO/'staging-added/nested'; added.mkdir(parents=True)
        (added/'data.bin').write_bytes(bytes(range(256))*16)
        (added/'run.sh').write_text('#!/bin/sh\n# synthetic fixture, never executed\n');(added/'run.sh').chmod(0o755)
        (REPO/'staging-link').symlink_to('staging-added/nested/data.bin')
        (REPO/'.gitignore').write_text((REPO/'.gitignore').read_text()+'\n.env\nstaging-ignored/\n')
        (REPO/'.env').write_text('FAKE_STAGING_VALUE=not-a-secret\n')
        (REPO/'staging-ignored').mkdir(); (REPO/'staging-ignored/cache').write_text('ignored but backed up\n')
        (REPO/'README.md').rename(REPO/'README-renamed.md')
        check('add_rename_ignored_detected', row(scan())['needs_backup'])
        changed = backup('add_rename_ignored')
        restore('added_ignored_and_links', changed)
        check('ignored_files_really_git_ignored', '.env' in command(['git','-C',REPO,'check-ignore','.env','staging-ignored/cache']))

        before = archive_map(changed)
        os.utime(added/'data.bin', None)
        touched = scan(); check('timestamp_only_no_backup', not row(touched)['needs_backup'])
        check('timestamp_only_exact_hashes', row(touched)['verification']['state'] == 'matched')
        (REPO/'.DS_Store').write_text('synthetic Finder metadata 1\n')
        finder = scan(); check('finder_only_no_backup', not row(finder)['needs_backup'] and row(finder)['verification'].get('ignored_finder_only'))
        repeated = backup('finder_manual')
        check('finder_manual_no_repo_replacement', archive_map(repeated) == before)
        (REPO/'.DS_Store').write_text('synthetic Finder metadata 2\n')
        check('finder_repeat_no_backup', not row(scan())['needs_backup'])

        command(['git', '-C', REPO, 'add', 'staging-added/nested/data.bin'])
        command(['git', '-C', REPO, '-c', 'user.name=RepoHub Staging', '-c', 'user.email=staging@example.invalid',
                 'commit', '-m', 'Synthetic staging history, never pushed'])
        check('git_history_change_detected', row(scan())['needs_backup'])
        committed = backup('git_history')
        restore('git_history', committed)
        check('only_git_changed_repo_replaced', all(archive_map(committed)[n] == a for n,a in before.items() if n != 'SampleProject'))

        key = row(committed)['id']; endpoint = '/api/repo-settings/' + key
        override_original = get(endpoint)
        custom = copy.deepcopy(policy); custom['adapter'].update(frequency_minutes=15, after_edits=True, edit_delay_minutes=2)
        post(endpoint, {'settings': custom, 'revision': override_original['revision'], 'defaults_revision': override_original['defaults_revision']})
        check('per_repo_override_saved', get(endpoint)['override'] and get(endpoint)['settings'] == custom)
        current = get('/api/settings'); new_default=copy.deepcopy(policy);new_default['adapter']['frequency_minutes']=30
        post('/api/settings', {'settings':new_default, 'revision':current['revision']})
        post('/api/settings', {'settings':policy,'revision':current['revision']},409)
        check('stale_settings_write_rejected_and_override_independent', get(endpoint)['settings'] == custom)
        before = archive_map(get('/api/status'))
        (added/'data.bin').write_bytes(b'after-edit scheduler fixture\x00'*100)
        observed = scan(); start=time.monotonic(); check('scheduled_edit_detected', row(observed)['needs_backup'])
        time.sleep(5)
        check('quiet_period_not_immediate', row(get('/api/status'))['last_backup']['archive'] == before['SampleProject'])
        scheduled = wait('real_after_edit', lambda s: not s['backup'].get('running') and
                         row(s)['last_backup']['archive'] != before['SampleProject'] and not row(s)['needs_backup'],240)
        report['after_edit_wait_seconds']=round(time.monotonic()-start,3)
        check('automatic_edit_only_replaces_sample', all(archive_map(scheduled)[n] == a for n,a in before.items() if n != 'SampleProject'))
        snapshot('automatic_after_edit'); restore('automatic_after_edit', scheduled)
        expected_settings=get('/api/settings')['settings'];expected_override=get(endpoint)['settings']
        old_session=get('/api/status')['diagnostics']['session_id']
        command(['launchctl','kickstart','-k','gui/'+str(os.getuid())+'/com.leogoldberg.repohub.airtest.service'])
        time.sleep(3)
        restarted=wait('restart',lambda s:s['diagnostics']['session_id']!=old_session and not s['backup'].get('running'))
        check('restart_settings_persist', get('/api/settings')['settings']==expected_settings and get(endpoint)['settings']==expected_override)
        check('restart_archives_persist', archive_map(restarted)==archive_map(scheduled))
        confirmed=wait('final_upload',lambda s:row(s)['cloud'].get('state')=='uploaded' and
                       row(s)['cloud'].get('archive')==row(s)['last_backup']['archive'],180)
        check('final_macos_upload_confirmed', True, checked_at=row(confirmed)['cloud']['checked_at'])
        report['cross_mac_input']=restore('final',confirmed)
        snapshot('final')
        report['status']='passed'
    except Exception as error:
        report['status']='failed'; report['error']={'type':type(error).__name__,'detail':str(error)}
        emit('run_failure',**report['error'])
        raise
    finally:
        try:
            if override_original is not None:
                current=get(endpoint)
                post(endpoint, {'settings':override_original['settings'] if override_original['override'] else None,
                                'revision':current['revision'],'defaults_revision':current['defaults_revision']})
            current=get('/api/settings')
            post('/api/settings',{'settings':original['settings'],'revision':current['revision']})
            report['settings_restored']=get('/api/settings')['settings']==original['settings']
            emit('settings_restored',passed=report['settings_restored'])
        except Exception as error:
            report['settings_restored']=False;report['cleanup_error']=type(error).__name__;report['status']='failed'
        report['finished_at']=datetime.now(timezone.utc).isoformat();save();events.close()
        print('RESULT '+str(out/'result.json'),flush=True)


if __name__=='__main__':
    main()

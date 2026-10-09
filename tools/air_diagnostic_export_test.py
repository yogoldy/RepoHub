#!/usr/bin/env python3
"""Small live test; requires the previously authorized isolated Air staging home."""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
from diagnostic_export import export_bundle
from diagnostics import diagnostic_ref, read_events

BASE = Path.home() / 'Library/Application Support/RepoHub-Air-Test'
STATE = Path.home() / 'Library/Application Support/RepoHub'
ORIGIN = 'http://127.0.0.1:8767'


def main():
    os.umask(0o077)
    config = json.loads((STATE/'config.json').read_text())
    root = BASE/'repos'
    expected = Path.home()/'Library/Mobile Documents/com~apple~CloudDocs/RepoHub Air Test/Snapshots'
    if Path(config['repos_root']).resolve()!=root.resolve() or Path(config['backup_root']).resolve()!=expected.resolve():
        raise RuntimeError('Refusing non-staging configuration')
    if not (BASE/'STAGING_TEST_AUTHORIZED.json').is_file() or root.is_symlink():
        raise RuntimeError('Missing staging authorization')
    case=BASE/('diagnostic-export-test-'+str(time.time_ns()))
    case.mkdir(mode=0o700)
    fixture=root/('DiagnosticFixture-'+case.name.rsplit('-',1)[1])
    fixture.mkdir(mode=0o700)
    (fixture/'note.txt').write_text('baseline\n')
    (fixture/'.gitignore').write_text('ignored/\n')
    (fixture/'ignored').mkdir()
    (fixture/'ignored/cache.bin').write_bytes(b'ignored fixture\n'*512)
    for args in [['git','init','-b','main'],['git','add','note.txt','.gitignore'],['git','-c','user.name=Staging Fixture','-c','user.email=fixture@example.invalid','commit','-m','Synthetic baseline']]:
        subprocess.run(args,cwd=fixture,check=True,capture_output=True,timeout=30)
    def get(path):
        with urllib.request.urlopen(ORIGIN+path,timeout=20) as response:return json.load(response)
    def post(path):
        token=get('/api/session')['token']
        request=urllib.request.Request(ORIGIN+path,b'{}',{'Content-Type':'application/json','Origin':ORIGIN,'X-RepoHub-Token':token})
        with urllib.request.urlopen(request,timeout=20) as response:return json.load(response)
    def wait(predicate,timeout=240):
        start=time.monotonic()
        while time.monotonic()-start<timeout:
            status=get('/api/status')
            row=next((r for r in status['repos'] if r['name']==fixture.name),None)
            if row and predicate(row,status):return row
            time.sleep(2)
        raise TimeoutError('Staging observation timed out')
    post('/api/scan')
    wait(lambda r,s:r.get('last_backup') or not s.get('verifying'))
    post('/api/backup')
    baseline=wait(lambda r,s:r.get('last_backup') and not s['backup']['running'])
    old=baseline['last_backup']['archive']
    (fixture/'note.txt').write_text('controlled meaningful edit\n')
    (fixture/'added').mkdir()
    (fixture/'added/new.txt').write_text('new file\n')
    post('/api/scan')
    wait(lambda r,s:r.get('needs_backup') is True)
    post('/api/backup')
    changed=wait(lambda r,s:r.get('last_backup',{}).get('archive')!=old and r.get('verification',{}).get('state')=='matched' and not s['backup']['running'])
    uploaded=wait(lambda r,s:r.get('cloud',{}).get('state')=='uploaded' and r['cloud'].get('archive')==changed['last_backup']['archive'])
    case_export=export_bundle(STATE/'diagnostics',case,hours=1)
    rows=[json.loads(line) for line in (case_export/'share/events.jsonl').read_text().splitlines()]
    private=json.loads((case_export/'PRIVATE_ALIAS_KEY.json').read_text())
    repo_ref=diagnostic_ref(uploaded['id'])
    repo_alias=next(a['alias'] for a in private['aliases'] if a['namespace']=='repo' and a['original']==repo_ref)
    related=[r for r in rows if r.get('repo_ref')==repo_alias]
    stages={r['event'] for r in related}
    assert {'repo_checked','repo_backup_started','archive_verified','repo_backup_finished','upload_observed'}<=stages,stages
    uploaded_refs={r.get('archive_ref') for r in related if r['event']=='upload_observed' and r.get('state')=='uploaded'}
    verified_refs={r.get('archive_ref') for r in related if r['event']=='archive_verified'}
    # Upload mode is recorded as state by the lifecycle adapter.
    if not uploaded_refs:
        uploaded_refs={r.get('archive_ref') for r in related if r['event']=='upload_observed' and r.get('mode')=='uploaded'}
    assert uploaded_refs & verified_refs, 'No correlated verified/uploaded archive'
    shared=''.join(p.read_text() for p in (case_export/'share').iterdir())
    assert str(Path.home()) not in shared and fixture.name not in shared and uploaded['last_backup']['archive'] not in shared
    originals=list(read_events(STATE/'diagnostics'))
    assert len(rows)<=len(originals)
    result={'result':'passed','fixture':str(fixture),'export':str(case_export),'event_count':len(rows),'repo_alias':repo_alias,'events':sorted(stages),'verified_uploaded_archive_overlap':True,'limitations':['Manual backups exercised; scheduling/power transitions not retested.','Native rendered progress and view visibility not asserted.','Fixture and evidence retained privately; no public upload.']}
    (case/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'result':'passed','event_count':len(rows),'stages':sorted(stages)},indent=2))

if __name__=='__main__':main()

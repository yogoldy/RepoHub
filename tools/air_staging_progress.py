#!/usr/bin/env python3
"""Add one fixed 48 MiB fixture to the authorized staging repo and observe its real upload."""
import hashlib,json,os,subprocess,sys,time,urllib.request
from pathlib import Path
from datetime import datetime,timezone
os.umask(0o077)
base=Path.home()/'Library/Application Support/RepoHub-Air-Test';repo=base/'repos/SampleProject'
state=Path.home()/'Library/Application Support/RepoHub'; origin='http://127.0.0.1:8767'
config=json.loads((state/'config.json').read_text())
if config['repos_root']!=str(base/'repos') or not (base/'STAGING_TEST_AUTHORIZED.json').is_file():raise RuntimeError('Non-staging configuration')
cloud=Path.home()/'Library/Mobile Documents/com~apple~CloudDocs/RepoHub Air Test/Snapshots'
if Path(config['backup_root']).resolve()!=cloud.resolve():raise RuntimeError('Non-staging backup output')
if repo.is_symlink():raise RuntimeError('Symlink staging repo')
output=base/('progress-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'));output.mkdir(mode=0o700)
def get():return json.load(urllib.request.urlopen(origin+'/api/status',timeout=10))
def post(path):
 token=json.load(urllib.request.urlopen(origin+'/api/session',timeout=10))['token']
 request=urllib.request.Request(origin+path,b'{}',{'Origin':origin,'X-RepoHub-Token':token,'Content-Type':'application/json'})
 return json.load(urllib.request.urlopen(request,timeout=10))
def row(s):return next(r for r in s['repos'] if r['name']=='SampleProject')
fixture=repo/'staging-upload-48MiB.bin'
with fixture.open('xb') as f:
 for i in range(48):f.write(hashlib.shake_256(('repohub-stage-block-'+str(i)).encode()).digest(1024*1024))
previous=get()['backup'].get('run_id');post('/api/backup');start=time.monotonic();finished=False;observed=[]
with (output/'observations.jsonl').open('x') as log:
 while time.monotonic()-start<240:
  s=get();r=row(s); observation={'utc':datetime.now(timezone.utc).isoformat(),'backup':s['backup'],'cloud':r['cloud'],'verification':r['verification'],'observation_id':s['diagnostic_observation_id']}
  log.write(json.dumps(observation)+'\n');log.flush();observed.append(observation)
  finished=not s['backup'].get('running') and s['backup'].get('run_id')!=previous
  if finished and s['backup'].get('errors'):raise RuntimeError('Backup failed')
  if finished and r['cloud'].get('state')=='uploaded' and r['cloud'].get('archive')==r['last_backup']['archive']:break
  time.sleep(1)
 else:raise TimeoutError('Real upload not confirmed')
item=r['last_backup'];capture=output/'capture';restored=output/'restore';commands=[]
def run(args):
 p=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=120)
 commands.append({'args':[str(x) for x in args],'code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
 (output/'commands.json').write_text(json.dumps(commands,indent=2))
 if p.returncode:raise RuntimeError('Restore audit failed')
run([sys.executable,base/'source/restore_audit.py','capture','--source',repo,'--archive-sha256',item['sha256'],'--out',capture])
h=hashlib.sha256((capture/'expected.json').read_bytes()).hexdigest()
run([sys.executable,base/'source/restore_audit.py','verify','--archive',item['archive'],'--expected',capture/'expected.json','--manifest-sha256',h,'--out',restored])
result={'result':'passed','fixture_bytes':fixture.stat().st_size,'archive':item['archive'],'archive_sha256':item['sha256'],'expected':str(capture/'expected.json'),'manifest_sha256':h,'elapsed_seconds':round(time.monotonic()-start,3),'cloud_states':sorted({v['cloud']['state'] for v in observed}),'observed_percentages':sorted({v['cloud']['percent'] for v in observed if isinstance(v['cloud'].get('percent'),(int,float))}),'copying_observed':any(v['backup'].get('current_repo')=='SampleProject' and v['backup'].get('running') for v in observed),'rendered_progress_verified':False,'restore_result':json.loads((restored/'result.json').read_text())['result']}
(output/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));print('RESULT '+str(output/'result.json'))

#!/usr/bin/env python3
"""Private, bounded observation of the actual staging service; never submits UI receipts."""
from pathlib import Path
import json,os,time,urllib.request
from datetime import datetime,timezone
os.umask(0o077)
root=Path.home()/'Library/Application Support/RepoHub-Air-Test'
stop=root/'observer.stop';output=root/('observations-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.jsonl')
start=time.monotonic()
with output.open('x') as log:
 while time.monotonic()-start<900 and not stop.exists():
  try:
   with urllib.request.urlopen('http://127.0.0.1:8767/api/status',timeout=3) as response:s=json.load(response)
   expected=str(root/'repos')
   if s['repos_root']!=expected:raise RuntimeError('Non-staging service')
   record={'utc':datetime.now(timezone.utc).isoformat(),'observation_id':s.get('diagnostic_observation_id'),
           'session_id':s.get('diagnostics',{}).get('session_id'),'backup':s['backup'],'power_source':s['power_source'],
           'repos':[{k:r.get(k) for k in ('id','name','needs_backup','verification','cloud','health','last_backup','schedule_override','backup_settings')} for r in s['repos']]}
  except Exception as error:record={'utc':datetime.now(timezone.utc).isoformat(),'error_type':type(error).__name__}
  log.write(json.dumps(record)+'\n');log.flush();time.sleep(1)
print(output)

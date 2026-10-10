"""Private exact public payload previews; no credential access."""
import json
import os
from pathlib import Path
import secrets
from diagnostic_export import export_bundle
from report_delivery import public_payload, digest

DESTINATION = 'https://github.com/yogoldy/RepoHub/issues'


def preview_report(state_dir, log_dir, payload):
    if set(payload) - {'type','title','description','expected','include_diagnostics','hours'}:
        raise ValueError('Unknown report field')
    kind=payload.get('type')
    if kind not in {'bug','feature'}:
        raise ValueError('Choose bug or feature')
    values={}
    for field,limit in [('title',140),('description',8000),('expected',4000)]:
        value=payload.get(field,'')
        if not isinstance(value,str) or len(value)>limit:
            raise ValueError('Invalid '+field)
        values[field]=value.strip()
    if not values['title'] or not values['description'] or (kind=='bug' and not values['expected']):
        raise ValueError('Complete the title, description and expected behavior')
    include=payload.get('include_diagnostics',kind=='bug')
    if type(include) is not bool:
        raise ValueError('Invalid diagnostics choice')
    hours=payload.get('hours',24)
    if type(hours) not in (int,float) or hours not in {1,24,168}:
        raise ValueError('Choose a diagnostic window')
    parent=Path(state_dir)/'reports'
    parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if parent.is_symlink():
        raise ValueError('Unsafe report directory')
    os.chmod(parent,0o700)
    report_id=secrets.token_hex(12)
    case=parent/report_id
    case.mkdir(mode=0o700)
    files=[]
    if include:
        bundle=export_bundle(log_dir,case/'diagnostics',hours=hours,max_events=100,max_bytes=20000)
        for name in ['schema.json','events.jsonl']:
            content=(bundle/'share'/name).read_text()
            files.append({'name':name,'bytes':len(content.encode()),'content':content})
    body=('## What happened\n' if kind=='bug' else '## What I would like\n')+values['description']
    if kind=='bug':body+='\n\n## What I expected\n'+values['expected']
    body+='\n\nReport ID: '+report_id
    result={'schema_version':1,'report_id':report_id,'type':kind,'state':'draft','destination':DESTINATION,
            'title':values['title'],'form':{**values,'include_diagnostics':include,'hours':hours},'body':body,'labels':['bug' if kind=='bug' else 'enhancement','from-app'],
            'files':files,'delivery_available':True,
            'disclosure':'Please don’t send any confidential information. Public GitHub issue. The exact previewed issue body, including any diagnostic blocks, will be shared. The private alias key is excluded. Nothing has been sent.'}
    issue = public_payload(result)
    result.update(github_title=issue['title'], issue_body=issue['body'], preview_digest=digest(issue))
    fd=os.open(case/'draft.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as target:
        json.dump(result,target,indent=2)
        target.flush(); os.fsync(target.fileno())
    directory=os.open(case,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)
    return result

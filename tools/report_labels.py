"""Fixed category routing for public app reports; issue text is never executable."""
import json
import os
from pathlib import Path
import re
import urllib.request


def labels_for(event):
    if not isinstance(event,dict) or not isinstance(event.get('repository'),dict) or not isinstance(event.get('issue'),dict):return None
    if event.get('action') != 'opened' or event.get('repository', {}).get('full_name') != 'yogoldy/RepoHub':
        return None
    issue=event.get('issue', {})
    if 'pull_request' in issue or type(issue.get('number')) is not int or issue['number'] < 1:
        return None
    body=issue.get('body') or '';title=issue.get('title') or ''
    if not isinstance(body,str) or not isinstance(title,str):return None
    match=re.search(r'^Report ID: [a-f0-9]{24}\n\nReport type: (bug|feature)(?:\n|$)',body,re.M)
    if not match:return None
    kind=match[1]
    if not title.startswith('[Bug] ' if kind=='bug' else '[Feature] '):return None
    return ['bug' if kind=='bug' else 'enhancement','from-app']


def main():
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    labels=labels_for(event)
    if labels is None:return
    number=event['issue']['number']
    request=urllib.request.Request('https://api.github.com/repos/yogoldy/RepoHub/issues/'+str(number)+'/labels',
        json.dumps({'labels':labels}).encode(),
        {'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json',
         'X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json','User-Agent':'RepoHub-labels'},method='POST')
    with urllib.request.urlopen(request,timeout=20) as response:
        if response.status!=200:raise SystemExit('Category routing failed')
    print('Applied fixed report category labels')

if __name__=='__main__':main()

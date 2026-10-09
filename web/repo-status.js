/* Pure presentation policy: the same exact archive and fresh checks are required. */
(function(root){
  function view(repo,backup={}){
    const cloud=repo.cloud||{},verification=repo.verification||{},archive=repo.last_backup?.archive;
    const percent=typeof cloud.percent==='number'&&Number.isFinite(cloud.percent)&&cloud.percent>=0&&cloud.percent<=100?cloud.percent:null;
    const issue=repo.error||verification.error||backup.errors?.find(e=>e.repo===repo.name)?.error|| (cloud.state==='error'?(cloud.detail||'iCloud upload issue'):null);
    const ready=repo.health?.fresh===true&&repo.needs_backup===false&&!issue&&!!archive&&typeof repo.last_backup?.sha256==='string'&&repo.last_backup.sha256.length>0&&verification.state==='matched'&&verification.archive===archive&&cloud.state==='uploaded'&&cloud.archive===archive;
    if(repo.health?.fresh!==true)return {phase:'stale',label:'Status outdated',detail:repo.health?.reasons?.join(' · ')||'Waiting for fresh checks',ready:false,percent:null};
    if(issue)return {phase:'error',label:'Needs attention',detail:issue,ready:false,percent:null};
    if(backup.running&&backup.current_repo===repo.name)return {phase:'copying',label:'Backing up',detail:'Building and verifying this backup',ready:false,percent:null};
    if(repo.needs_backup)return {phase:'changed',label:repo.last_backup?'New edits':'First backup pending',detail:cloud.state==='uploading'?'The saved copy is uploading; newer edits still need a backup.':'Waiting for the next backup, or use Back up now.',ready:false,percent:cloud.state==='uploading'?percent:null};
    if(verification.state!=='matched'||verification.archive!==archive)return {phase:'verifying',label:'Verifying',detail:'Checking hashes against the saved backup',ready:false,percent:null};
    if(ready)return {phase:'ready',label:'Backed up',detail:'Hashes verified · iCloud upload confirmed',ready:true,percent:null};
    if(cloud.state==='uploading')return {phase:'uploading',label:'Uploading',detail:percent===100?'Waiting for iCloud confirmation':'Hashes verified · uploading to iCloud',ready:false,percent};
    if(cloud.state==='pending')return {phase:'pending',label:'Waiting for iCloud',detail:'Hashes verified · upload not yet confirmed',ready:false,percent};
    return {phase:'unknown',label:'Awaiting confirmation',detail:'Hashes verified · iCloud status unknown',ready:false,percent:null};
  }
  const policy={view};if(typeof module==='object'&&module.exports)module.exports=policy;else root.RepoStatus=policy;
})(typeof globalThis==='object'?globalThis:this);

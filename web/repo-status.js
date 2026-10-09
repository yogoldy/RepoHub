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
  const paths={
    ready:'<path d="m5 12 4 4L19 6"/>',
    pending:'<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
    unknown:'<circle cx="12" cy="12" r="8"/><path d="M10 9a2 2 0 0 1 4 0c0 2-2 2-2 4m0 3h.01"/>',
    stale:'<circle cx="12" cy="12" r="8"/><path d="M12 7v5m0 4h.01"/>',
    uploading:'<path d="M12 17V5m-5 5 5-5 5 5M5 17v3h14v-3"/>',
    copying:'<path d="M20 8a8 8 0 1 0 0 8m0-13v5h-5"/>',
    verifying:'<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5m-13-10 2 2 4-4"/>',
    changed:'<path d="m5 15 10-10 4 4L9 19H5zm8-8 4 4"/>',
    error:'<path d="m12 3 10 18H2zm0 6v5m0 3h.01"/>'
  };
  function icon(phase){return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(paths[phase]||paths.unknown)+'</svg>';}
  function legend(){return '<span>'+icon('ready')+' Verified + uploaded</span><span>'+icon('pending')+' Waiting for iCloud</span><span>'+icon('changed')+' New edits</span><span>'+icon('uploading')+' Uploading</span><span>'+icon('copying')+' Backing up</span><span>'+icon('verifying')+' Checking hashes</span><span>'+icon('stale')+' Status outdated</span><span>'+icon('error')+' Needs attention</span><span>'+icon('unknown')+' Unconfirmed</span>';}
  const policy={view,icon,legend};if(typeof module==='object'&&module.exports)module.exports=policy;else root.RepoStatus=policy;
})(typeof globalThis==='object'?globalThis:this);

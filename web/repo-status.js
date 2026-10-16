/* Pure presentation policy: the same exact archive and fresh checks are required. */
(function(root){
  function finderOnly(repo){const v=repo.verification||{},b=repo.last_backup||{};return repo.needs_backup===false&&!!b.archive&&typeof b.sha256==='string'&&b.sha256.length>0&&v.state==='different'&&v.archive===b.archive&&v.ignored_finder_only===true&&v.backup_required===false;}
  function view(repo,backup={}){
    const cloud=repo.cloud||{},verification=repo.verification||{},archive=repo.last_backup?.archive;
    const percent=typeof cloud.percent==='number'&&Number.isFinite(cloud.percent)&&cloud.percent>=0&&cloud.percent<=100?cloud.percent:null;
    const issue=repo.error||verification.error||backup.errors?.find(e=>'repo_id' in e?e.repo_id===repo.id:e.repo===repo.name)?.error|| (cloud.state==='error'?(cloud.detail||'iCloud upload issue'):null);
    const ready=repo.health?.fresh===true&&repo.needs_backup===false&&!issue&&!!archive&&typeof repo.last_backup?.sha256==='string'&&repo.last_backup.sha256.length>0&&verification.state==='matched'&&verification.archive===archive&&cloud.state==='uploaded'&&cloud.archive===archive;
    if(repo.health?.fresh!==true)return {phase:'stale',label:'Status outdated',detail:repo.health?.reasons?.join(' · ')||'Waiting for fresh checks',ready:false,percent:null};
    if(issue)return {phase:'error',label:'Needs attention',detail:issue,ready:false,percent:null};
    if(verification.state==='changing')return {phase:'verifying',label:'Files changing',detail:'Files changed during verification. We’ll check again on the next scan.',ready:false,percent:null};
    if(backup.running&&('current_repo_id' in backup?backup.current_repo_id===repo.id:backup.current_repo===repo.name))return {phase:'copying',label:'Backing up',detail:'Building and verifying this backup',ready:false,percent:null};
    if(repo.needs_backup){
      if(repo.last_backup&&verification.state==='checking')return {phase:'verifying',label:'Checking for changes',detail:'Comparing hashes before identifying changed files',ready:false,percent:null};
      const counts=verification.state==='different'&&verification.archive===archive?verification.changes?.counts:null;
      const finder=counts?.finder_metadata||0,git=counts?.git_data||0,files=counts?.repo_files||0;
      const label=!repo.last_backup?'First backup pending':files?'Files changed':finder&&!git?'Finder metadata changed':git&&!finder?'Git data changed':finder&&git?'Finder / Git data changed':'Backup needs updating';
      let detail=files?'Repo files differ from the saved backup.':finder&&!git?'Finder updated folder metadata; your repo files still match.':git||finder?'Version-control or Finder data differs; your repo files still match.':'Waiting for the next backup, or use Back up now.';
      if(finder||git||files)detail+=' Included in the next backup.';
      if(cloud.state==='uploading')detail+=' The saved copy is still uploading.';
      return {phase:'changed',label,detail,ready:false,percent:cloud.state==='uploading'?percent:null};
    }
    if(finderOnly(repo)){
      const detail='Project files, ignored files and Git match. Only .DS_Store differs; no new backup needed.';
      if(cloud.state==='uploaded'&&cloud.archive===archive)return {phase:'background',label:'Project files match',detail,ready:false,percent:null};
      if(cloud.state==='uploading')return {phase:'uploading',label:'Uploading',detail:detail+' The saved archive is uploading.',ready:false,percent};
      if(cloud.state==='pending')return {phase:'pending',label:'Waiting for iCloud',detail:detail+' Upload not yet confirmed.',ready:false,percent};
      return {phase:'unknown',label:'Awaiting confirmation',detail:detail+' iCloud status unknown.',ready:false,percent:null};
    }
    if(verification.state!=='matched'||verification.archive!==archive)return {phase:'verifying',label:'Verifying',detail:'Checking hashes against the saved backup',ready:false,percent:null};
    if(ready)return {phase:'ready',label:'Backed up',detail:'Hashes verified · iCloud upload confirmed',ready:true,percent:null};
    if(cloud.state==='uploading')return {phase:'uploading',label:'Uploading',detail:percent===100?'Waiting for iCloud confirmation':'Hashes verified · uploading to iCloud',ready:false,percent};
    if(cloud.state==='pending')return {phase:'pending',label:'Waiting for iCloud',detail:'Hashes verified · upload not yet confirmed',ready:false,percent};
    return {phase:'unknown',label:'Awaiting confirmation',detail:'Hashes verified · iCloud status unknown',ready:false,percent:null};
  }
  const paths={
    background:'<circle cx="12" cy="12" r="8"/><path d="M12 11v6m0-10h.01"/>',
    ready:'<path d="m5 12 4 4L19 6"/>',
    pending:'<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
    unknown:'<circle cx="12" cy="12" r="8"/><path d="M10 9a2 2 0 0 1 4 0c0 2-2 2-2 4m0 3h.01"/>',
    stale:'<circle cx="12" cy="12" r="8"/><path d="M12 7v5m0 4h.01"/>',
    uploading:'<path d="M12 17V5m-5 5 5-5 5 5M5 17v3h14v-3"/>',
    copying:'<path d="M20 8a8 8 0 1 0 0 8m0-13v5h-5"/>',
    verifying:'<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5m-13-10 2 2 4-4"/>',
    changed:'<path d="M13 3H5v18h14V9zm0 0v6h6M8 13h8m-8 4h5"/>',
    error:'<path d="m12 3 10 18H2zm0 6v5m0 3h.01"/>'
  };
  function icon(phase){return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(paths[phase]||paths.unknown)+'</svg>';}
  function legend(){return '<span>'+icon('ready')+' Verified + uploaded</span><span>'+icon('background')+' Project/Git match; Finder-only difference</span><span>'+icon('pending')+' Waiting for iCloud</span><span>'+icon('changed')+' Files or background data changed</span><span>'+icon('uploading')+' Uploading</span><span>'+icon('copying')+' Backing up</span><span>'+icon('verifying')+' Checking hashes</span><span>'+icon('stale')+' Status outdated</span><span>'+icon('error')+' Needs attention</span><span>'+icon('unknown')+' Unconfirmed</span>';}
  const policy={view,icon,legend,finderOnly,version:'change-evidence-2'};if(typeof module==='object'&&module.exports)module.exports=policy;else root.RepoStatus=policy;
})(typeof globalThis==='object'?globalThis:this);

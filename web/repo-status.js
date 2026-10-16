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
  // Describe the existing policy result without changing its safety decisions.
  function present(repo, backup = {}) {
    const original = view(repo, backup);
    const verification = repo.verification || {};
    let category, label, headline, detail;
    const archive = repo.last_backup?.archive;
    const sameUpload = !!archive && repo.cloud?.archive === archive;
    const verified = !!repo.last_backup?.sha256 && !!archive
      && verification.archive === archive
      && (verification.state === 'matched' || finderOnly(repo));
    const displayPhase = ['uploading', 'pending'].includes(original.phase) && !sameUpload
      ? 'unknown' : original.phase;
    switch (displayPhase) {
      case 'ready':
        category = 'backed_up'; label = 'Backed up';
        headline = 'Your files are backed up.';
        detail = 'Your files match the verified archive, and macOS confirms that same archive uploaded.';
        break;
      case 'background':
        category = 'backed_up'; label = 'Only Finder metadata changed';
        headline = 'Only Finder metadata changed.';
        detail = 'Your project files and Git match the uploaded backup. Finder changed folder metadata; no new backup is needed.';
        break;
      case 'changed': {
        category = 'backup_pending';
        const confirmed = verification.state === 'different'
          && verification.archive === repo.last_backup?.archive
          && ((verification.changes?.counts?.repo_files || 0) > 0
            || (verification.changes?.counts?.git_data || 0) > 0);
        label = !repo.last_backup ? 'First backup pending' : confirmed ? 'Edits confirmed' : 'Backup pending';
        headline = !repo.last_backup ? 'Your first backup is pending.'
          : confirmed ? 'RepoHub confirmed edits.' : 'RepoHub is waiting to back up this repo.';
        detail = confirmed ? 'Your files or Git data contain confirmed changes since the saved backup.'
          : 'Use Back up now or review this repo’s schedule. A pending backup is not a failed status check.';
        // 'Only' needs a complete, current comparison, not missing counts or events.
        const counts = verification.changes?.counts;
        const complete = counts && ['repo_files', 'git_data', 'finder_metadata'].every(
          key => Number.isInteger(counts[key]) && counts[key] >= 0);
        if (repo.last_backup && archive && verification.state === 'different'
            && verification.archive === archive && complete && counts.repo_files === 0) {
          if (counts.git_data > 0 && counts.finder_metadata > 0) {
            label = 'Only Git and Finder metadata changed';
          } else if (counts.git_data > 0) {
            label = 'Only Git data changed';
          } else if (counts.finder_metadata > 0) {
            label = 'Only Finder metadata changed';
          }
          if (counts.git_data > 0 || counts.finder_metadata > 0) {
            headline = label + '.';
            detail = counts.git_data > 0
              ? 'Your project files match the saved backup. The next backup will include the changed Git version-control data'
                + (counts.finder_metadata > 0 ? ' and Finder folder metadata.' : '.')
              : 'Your project files and Git match the saved backup. Finder folder metadata is pending in the next backup.';
          }
        }
        break;
      }
      case 'verifying':
        category = 'working';
        label = verification.state === 'changing' ? 'Checking again' : 'Scanning';
        headline = verification.state === 'changing' ? 'Files changed during the scan.'
          : 'RepoHub is scanning for changes…';
        detail = verification.state === 'changing' ? 'RepoHub will check again on the next scan.'
          : 'RepoHub is comparing your files with the saved backup.';
        break;
      case 'copying':
        category = 'working'; label = 'Creating backup';
        headline = 'RepoHub is creating your backup…';
        detail = 'RepoHub is packaging your files and verifying the archive.';
        break;
      case 'uploading':
        category = 'working'; label = 'Uploading';
        headline = 'macOS is uploading your backup…';
        detail = verified ? 'RepoHub created and verified the backup file. Upload progress is separate from completion confirmation.'
          : 'macOS reports an upload. RepoHub has not established all verification evidence for this archive.';
        break;
      case 'pending':
        category = 'upload_unconfirmed'; label = 'Awaiting upload confirmation';
        headline = 'macOS hasn’t confirmed the upload yet.';
        detail = verified ? 'RepoHub created and verified the backup file.'
          : 'RepoHub is waiting for verification and upload evidence for this archive.';
        break;
      case 'stale':
        category = 'status_unavailable'; label = 'Current status unavailable';
        headline = 'RepoHub can’t get current backup status.';
        detail = 'Expected checks are not providing fresh evidence. This is separate from your backup schedule.';
        break;
      case 'error':
        category = 'failure'; label = 'Needs attention — failure';
        headline = 'Needs attention — failure.';
        detail = original.detail;
        break;
      default:
        category = 'upload_unconfirmed'; label = 'Upload status unavailable';
        headline = 'RepoHub can’t read the upload status.';
        detail = 'RepoHub cannot confirm that the current archive uploaded. See technical details for the available verification evidence.';
    }
    return {...original, category, label, headline, detail, technicalDetail: original.detail};
  }

  function describeSchedule(repo, power) {
    const policy = repo.backup_settings?.[power];
    const scope = repo.schedule_override ? 'Custom schedule' : 'Default schedule';
    if (!['battery', 'adapter'].includes(power) || !policy) {
      return {label: 'Schedule unavailable', detail: scope + ' · Power or policy information is unavailable.'};
    }
    const frequency = policy.frequency_minutes;
    const delay = policy.edit_delay_minutes;
    if (![0, 15, 30, 60, 120, 240].includes(frequency)
        || typeof policy.after_edits !== 'boolean'
        || ![2, 5, 10, 15, 30].includes(delay)) {
      return {label: 'Schedule unavailable', detail: scope + ' · Waiting for valid scheduling information.'};
    }
    const source = power === 'battery' ? 'On battery' : 'On power adapter';
    const parts = [];
    if (frequency) {
      parts.push(frequency < 60 ? `Every ${frequency} minutes`
        : frequency === 60 ? 'Every hour' : `Every ${frequency / 60} hours`);
    }
    if (policy.after_edits) parts.push(`${delay} minutes after edits settle`);
    return {label: parts.length ? parts.join(' or ') : 'Manual only', detail: scope + ' · ' + source};
  }

  function categoryIcon(state) {
    const phases = {backed_up: state.ready ? 'ready' : 'background', backup_pending: 'changed',
      working: 'copying', upload_unconfirmed: 'unknown', status_unavailable: 'stale', failure: 'error'};
    return icon(phases[state.category]);
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
  function legend() {
    const groups = [
      {category: 'backed_up', icon: 'ready', title: 'Backed up', labels: 'Backed up · Only Finder metadata changed',
        explanation: 'Backed up means fresh checks match your files to the verified archive, and macOS confirms that exact archive uploaded.',
        note: 'Only Finder metadata changed uses the information icon instead of a green check when the uploaded archive matches project files and Git. Finder folder metadata differs; no new backup is needed in this exception. It is not full byte-for-byte equality.'},
      {category: 'backup_pending', icon: 'changed', title: 'A backup is waiting to run',
        labels: 'First backup pending · Edits confirmed · Backup pending · Only Git data changed · Only Git and Finder metadata changed · Only Finder metadata changed',
        explanation: 'First backup pending means no archive exists yet. Edits confirmed means a hash comparison found project or Git changes against the saved archive. Backup pending means a backup is needed without that confirmed-edit evidence.',
        note: 'The Only labels require a complete comparison showing no project-file changes. Git data includes version-control history and still needs a backup. A pending Finder-only difference follows the existing backup policy; the expanded explanation distinguishes it from the ignored Finder exception. Review the separate Schedule row or use Back up now. Waiting for a scheduled attempt is normal and does not mean status checks failed.'},
      {category: 'working', icon: 'copying', title: 'RepoHub or macOS is working',
        labels: 'Scanning · Checking again · Creating backup · Uploading',
        explanation: 'Scanning compares files with the archive. Checking again means files changed during that scan; RepoHub retries on the next scan. Creating backup packages and verifies the archive. Uploading means macOS reports transfer activity for that archive.',
        note: 'The expanded sentence names the current step. A progress bar, even at 100%, does not establish upload completion.'},
      {category: 'upload_unconfirmed', icon: 'unknown', title: 'Cloud upload completion is not confirmed',
        labels: 'Awaiting upload confirmation · Upload status unavailable',
        explanation: 'Awaiting upload confirmation means macOS has not acknowledged completion. Upload status unavailable means RepoHub cannot establish upload status for the current archive.',
        note: 'RepoHub creates the archive on this Mac; macOS uploads the iCloud Drive file separately. Neither state proves that uploading failed, and a local file alone is not cloud confirmation.'},
      {category: 'status_unavailable', icon: 'stale', title: 'RepoHub cannot get current information',
        labels: 'Current status unavailable',
        explanation: 'Expected checks are not supplying fresh evidence, or the interface cannot reach the helper. Technical details show available timestamps and reasons.',
        note: 'This is separate from backup frequency. An hourly backup schedule does not make status outdated between backups.'},
      {category: 'failure', icon: 'error', title: 'An operation failed',
        labels: 'Needs attention — failure',
        explanation: 'RepoHub or macOS reported a failure. The expanded view shows the available error; Technical details retain supporting evidence.',
        note: 'Use Retry check now when offered, or Report this status to describe the issue and optionally attach sanitized diagnostics. Review the preview and explicitly Send; opening a report sends nothing.'}
    ];
    return groups.map(group => `<section class="status-guide-item" data-category="${group.category}">
      <div class="guide-heading"><span class="guide-symbol" aria-hidden="true">${icon(group.icon)}</span>
        <h4>${group.title}</h4></div><p class="guide-labels">${group.labels}</p>
      <p>${group.explanation}</p><p class="guide-note">${group.note}</p></section>`).join('');
  }
  const policy={view,present,describeSchedule,categoryIcon,icon,legend,finderOnly,version:'status-clarity-2'};if(typeof module==='object'&&module.exports)module.exports=policy;else root.RepoStatus=policy;
})(typeof globalThis==='object'?globalThis:this);

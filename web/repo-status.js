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
  // Keep backup decisions intact while mapping their evidence to the displayed status.
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
      case 'background':
        category = 'backed_up'; label = 'Backed up';
        headline = 'Your files are backed up.';
        detail = 'Your project files and Git data match the verified backup, and macOS confirms it uploaded to iCloud.';
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
            label = 'Only Git and file metadata changed';
          } else if (counts.git_data > 0) {
            label = 'Only Git data changed';
          } else if (counts.finder_metadata > 0) {
            label = 'Only file metadata changed';
          }
          if (counts.git_data > 0 || counts.finder_metadata > 0) {
            headline = label + '.';
            detail = counts.git_data > 0
              ? 'Your project files match the saved backup. The next backup will include the changed Git version-control data'
                + (counts.finder_metadata > 0 ? ' and file metadata.' : '.')
              : 'Your project files and Git match the saved backup. The next backup will include the changed file metadata.';
          }
        }
        if (repo.last_backup && (!complete || !archive || verification.archive !== archive
            || verification.state !== 'different' || !Object.values(counts).some(value => value > 0))) {
          label = 'Changes need verification';
          headline = 'RepoHub hasn’t established which files changed.';
          detail = 'A complete comparison is needed before RepoHub can identify all changed files.';
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
    // A Finder-only exception remains recorded as a different comparison. It can
    // use the normal green display only after view() establishes fresh verification
    // and upload confirmation for the same archive.
    const finderBackedUp = original.phase === 'background';
    const technicalDetail = finderBackedUp
      ? 'Only Finder view settings (.DS_Store) differ from the saved backup.'
      : original.phase === 'changed' ? detail : original.detail;
    return {...original, phase: finderBackedUp ? 'ready' : original.phase,
      ready: original.ready || finderBackedUp, category, label, headline, detail, technicalDetail};
  }

  function timing(repo, backup = {}, freshness = 'current') {
    const schedule = repo.schedule_evidence || {};
    const location = repo.backup_location || {};
    const receipt = {
      schedule_state: schedule.state || 'unavailable',
      timing_reason: schedule.reason || 'power_unknown',
      location_state: location.state || 'unavailable',
      created_at: location.created_at || null,
      due_at: schedule.due_at || null,
      remaining_minutes: Number.isFinite(schedule.due_in_seconds)
        && schedule.due_in_seconds >= 0 && schedule.due_in_seconds <= 86400
        ? Math.ceil(schedule.due_in_seconds / 60) : null,
      inclusion_state: 'none',
    };
    const copying = !!backup.running && ('current_repo_id' in backup
      ? backup.current_repo_id === repo.id : backup.current_repo === repo.name);
    if (copying) Object.assign(receipt, {
      schedule_state: 'creating', timing_reason: 'active_backup', due_at: null, remaining_minutes: null,
    });
    if (repo.health?.fresh !== true) Object.assign(receipt, {
      schedule_state: 'unavailable', timing_reason: 'checks_unavailable', due_at: null, remaining_minutes: null,
    });
    if (freshness !== 'current') Object.assign(receipt, {
      schedule_state: 'unavailable', timing_reason: 'checks_unavailable', due_at: null,
      remaining_minutes: null, location_state: 'unavailable', created_at: null,
    });
    const verification = repo.verification || {};
    const counts = verification.changes?.counts;
    const complete = counts && ['repo_files', 'git_data', 'finder_metadata'].every(
      key => Number.isInteger(counts[key]) && counts[key] >= 0);
    const phase = view(repo, backup).phase;
    if (freshness === 'current' && repo.health?.fresh === true && phase === 'changed'
        && repo.needs_backup && repo.last_backup?.archive && complete
        && verification.state === 'different' && verification.archive === repo.last_backup.archive) {
      if (counts.repo_files > 0) receipt.inclusion_state = 'confirmed_changes';
      else if (counts.git_data > 0) receipt.inclusion_state = counts.finder_metadata > 0 ? 'git_metadata' : 'git_data';
      else if (counts.finder_metadata > 0) receipt.inclusion_state = 'metadata';
    }
    const formatDate = value => new Date(value).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    });
    let lastLine = 'Backup location unavailable.';
    if (receipt.location_state === 'none') lastLine = 'No backup created yet.';
    else if (receipt.created_at && Number.isFinite(Date.parse(receipt.created_at))) {
      if (receipt.location_state === 'cloud_confirmed') {
        lastLine = 'Latest backup confirmed in iCloud · Created ' + formatDate(receipt.created_at);
      } else if (receipt.location_state === 'local') {
        lastLine = 'Last backup created locally: ' + formatDate(receipt.created_at);
      }
    }
    let locationLabel = receipt.location_state === 'none' ? 'No backup yet' : 'Unavailable';
    let createdLabel = receipt.location_state === 'none' ? 'Not yet' : 'Unavailable';
    if (['cloud_confirmed', 'local'].includes(receipt.location_state)
        && receipt.created_at && Number.isFinite(Date.parse(receipt.created_at))) {
      locationLabel = receipt.location_state === 'cloud_confirmed' ? 'iCloud' : 'This Mac';
      createdLabel = new Intl.DateTimeFormat('en-US', {
        month: 'numeric', day: 'numeric', year: '2-digit',
        hour: 'numeric', minute: '2-digit', hour12: true,
      }).format(new Date(receipt.created_at)).replace(/,\s*/g, ' ')
        .replace(/\s+(AM|PM)$/, (_, period) => period.toLowerCase());
    }
    const nextLabels = {
      due: 'Next scheduled check: due now.',
      busy: 'Check due · waiting for current backup.',
      manual: 'Next backup: manual only.',
      awaiting_edits: 'Next backup: after edits settle.',
      blocked: 'Next backup: source needs attention.',
      creating: 'Backup in progress.',
      unavailable: 'Next check time unavailable.',
    };
    let nextLine = nextLabels[receipt.schedule_state] || nextLabels.unavailable;
    if (receipt.schedule_state === 'scheduled' && receipt.due_at && Number.isFinite(Date.parse(receipt.due_at))) {
      nextLine = 'Next scheduled check due: ' + formatDate(receipt.due_at);
      if (receipt.remaining_minutes !== null) nextLine += ' · in ' + receipt.remaining_minutes + ' min';
    }
    const inclusionLabels = {
      none: '', confirmed_changes: 'The next backup will include the confirmed changes.',
      git_data: 'The next backup will include the changed Git data.',
      metadata: 'The next backup will include the changed file metadata.',
      git_metadata: 'The next backup will include the changed Git data and file metadata.',
    };
    let inclusionLine = inclusionLabels[receipt.inclusion_state];
    if (freshness === 'current' && phase === 'background') inclusionLine = 'No new backup needed.';
    return {receipt, lastLine, locationLabel, createdLabel, nextLine, inclusionLine};
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
      {category: 'backed_up', icon: 'ready', title: 'Backed up',
        explanation: 'RepoHub checked your project files and Git data against the saved backup. macOS confirmed that backup uploaded to iCloud.',
        note: 'Changes to Finder’s folder view settings don’t require a new backup.'},
      {category: 'backup_pending', icon: 'changed', title: 'A backup is waiting to run',
        definitions: [
          ['First backup pending', 'RepoHub hasn’t created a backup for this repo yet.'],
          ['Edits confirmed', 'RepoHub found project-file or Git changes since the saved backup.'],
          ['Backup pending', 'RepoHub needs to create or update this repo’s backup.'],
          ['Changes need verification', 'RepoHub needs a complete comparison before it can identify the changes.'],
          ['Only Git data changed', 'Git history or other Git data changed; your project files match.'],
          ['Only file metadata changed', 'File information changed; your project files and Git match.'],
          ['Only Git and file metadata changed', 'Git data and file information changed; your project files match.'],
        ],
        note: 'Check the schedule or choose Back up now. Waiting for a scheduled backup is normal.'},
      {category: 'working', icon: 'copying', title: 'RepoHub or macOS is working',
        definitions: [
          ['Scanning', 'RepoHub is comparing your files with the saved backup.'],
          ['Checking again', 'Files changed during the scan. RepoHub will try again.'],
          ['Creating backup', 'RepoHub is packaging your files and checking the backup.'],
          ['Uploading', 'macOS is transferring the backup to iCloud.'],
        ],
        note: 'A progress bar reaching 100% does not confirm that the upload finished.'},
      {category: 'upload_unconfirmed', icon: 'unknown', title: 'Upload not yet confirmed',
        explanation: 'RepoHub creates the backup on this Mac. macOS uploads it separately.',
        definitions: [
          ['Awaiting upload confirmation', 'macOS hasn’t confirmed that the upload finished.'],
          ['Upload status unavailable', 'RepoHub can’t determine whether the upload finished.'],
        ],
        note: 'A local backup file does not prove upload completion. These statuses do not prove that the upload failed.'},
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
        <h4>${group.title}</h4></div>
      ${group.labels ? `<p class="guide-labels">${group.labels}</p>` : ''}
      ${group.definitions ? `<dl class="guide-definitions">${group.definitions.map(
        ([label, meaning]) => `<dt>${label}</dt><dd>${meaning}</dd>`).join('')}</dl>` : ''}
      ${group.explanation ? `<p>${group.explanation}</p>` : ''}
      ${group.note ? `<p class="guide-note">${group.note}</p>` : ''}</section>`).join('');
  }
  const policy={view,present,timing,describeSchedule,categoryIcon,icon,legend,finderOnly,version:'status-clarity-5'};if(typeof module==='object'&&module.exports)module.exports=policy;else root.RepoStatus=policy;
})(typeof globalThis==='object'?globalThis:this);

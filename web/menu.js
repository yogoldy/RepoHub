let observedMenuState=null,clientFreshness='current';
let retryingRepo=null;
const technicalOpen = new Set();
const diagnosticView=RepoDiagnostics.create('menu',{native:!!window.webkit?.messageHandlers?.repoHub});
let menuState=null,selectedId=null,sessionToken='',loading=false,lastResponseAt=0,settingsRevision='',settingsRepo=null,defaultsRevision='',settingsDefaults=null;
const $=s=>document.querySelector(s);
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function when(value){if(!value)return 'Not yet';return new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});}
function bytes(n){if(!Number.isFinite(n))return '—';const units=['B','KB','MB','GB'];let i=0;while(n>=1024&&i<3){n/=1024;i++;}return new Intl.NumberFormat(undefined,{maximumFractionDigits:1}).format(n)+' '+units[i];}
async function api(path,payload){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);try{const response=await fetch(path,{signal:controller.signal,...(payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-RepoHub-Token':sessionToken},body:JSON.stringify(payload)})});const value=await response.json();if(!response.ok)throw new Error(value.error||'Request failed');return value;}finally{clearTimeout(timer);}}
function nativeAction(action,repoId){const bridge=window.webkit?.messageHandlers?.repoHub;if(!bridge){$('#notice').textContent='This control is available from the Mac menu bar.';return false;}bridge.postMessage(repoId?{action,repo_id:repoId}:{action});return true;}
function view(repo){return RepoStatus.present(repo,menuState?.backup);}
$('#status-legend').innerHTML=RepoStatus.legend();

const infoDialog = $('#info-dialog');
$('#info').onclick = () => infoDialog.showModal();
$('#info-close').onclick = () => infoDialog.close();
let folderDemoTimer=null;
$('#show-folder').onclick=()=>{
  const card=[...$('#cards').querySelectorAll('.repo-card')].find(b=>b.dataset.repoId===selectedId);
  const folder=card?.parentElement.querySelector('.open-repo');if(!folder)return;
  // Close the information view so the demonstrated folder button is visible.
  infoDialog.close();
  clearTimeout(folderDemoTimer);for(const node of document.querySelectorAll('.demonstrating'))node.classList.remove('demonstrating');
  folder.scrollIntoView({behavior:motion(),block:'nearest',inline:'nearest'});
  void folder.offsetWidth;folder.classList.add('demonstrating');
  const name=menuState?.repos.find(r=>r.id===selectedId)?.name||'the selected repo';
  $('#folder-demo-status').textContent='Folder button highlighted for '+name+'. Click that button to open the repo in Finder.';
  folderDemoTimer=setTimeout(()=>folder.classList.remove('demonstrating'),1400);
};
window.addEventListener('repoHubFinderError',e=>{$('#notice').textContent=e.detail;});
function percentLabel(percent){return percent.toFixed(1).replace(/\.0$/,'')+'%';}
function render(){
  $('#quit').title = menuState.application_release
    ? 'Quit RepoHub after any current backup finishes'
    : 'Quit menu-bar app; the backup helper keeps running';
  const repos=menuState.repos||[];
  if(!repos.some(r=>r.id===selectedId))selectedId=repos[0]?.id||null;
  const ready=repos.filter(r=>view(r).ready).length;
  $('#summary').textContent = repos.length
    ? `${ready} of ${repos.length} repos fully verified and uploaded` : 'No repos found';
  $('#backup').disabled=!!menuState.backup?.running;
  $('#backup').lastElementChild.textContent=menuState.backup?.running?'Backing up…':'Back up now';
  const problems=menuState.problems||[];
  $('#notice').textContent=menuState.backup?.running?`Backing up ${menuState.backup.current_repo||'your repos'}…`:problems.length?`${problems.length} backup issue${problems.length===1?'':'s'} need attention.`:repos.some(r=>r.health?.fresh!==true)?'Waiting for fresh status checks.':'';
  const rail=$('#cards'),existing=new Map([...rail.querySelectorAll('.repo-card')].map(b=>[b.dataset.repoId,b]));
  const buttons=repos.map(repo=>{
    let button=existing.get(repo.id);
    if(!button){const slot=document.createElement('div');slot.className='card-slot';button=document.createElement('button');button.type='button';button.dataset.repoId=repo.id;button.addEventListener('click',()=>selectRepo(repo.id));slot.append(button);const folder=document.createElement('button');folder.type='button';folder.className='open-repo';folder.setAttribute('aria-label','Open '+repo.name+' in Finder');folder.title='Open '+repo.name+' on this Mac in Finder';folder.innerHTML='<span class="folder-shape" aria-hidden="true"></span>';folder.onclick=()=>nativeAction('openRepo',repo.id);folder.disabled=!window.webkit?.messageHandlers?.repoHub;if(folder.disabled)folder.title+=' · Available from the Mac menu bar';slot.append(folder);}
    const state=view(repo),label=state.label+(state.percent===null?'':' · '+percentLabel(state.percent));
    button.className='repo-card '+state.phase;button.dataset.category=state.category;button.dataset.headline=state.headline;button.setAttribute('aria-description',state.headline);button.setAttribute('aria-pressed',String(repo.id===selectedId));button.setAttribute('aria-label',repo.name+' · '+label);button.setAttribute('aria-controls','detail');
    const markup=`<span class="card-top"><span class="folder-placeholder" aria-hidden="true"></span><span class="status-mark" aria-hidden="true">${RepoStatus.categoryIcon(state)}</span></span><span class="card-name">${escape(repo.name)}</span><span class="card-status">${escape(label)}</span>`;
    if(button.innerHTML!==markup)button.innerHTML=markup;
    return button.parentElement;
  });
  const oldIds=[...existing.keys()].join('|'),newIds=repos.map(r=>r.id).join('|');
  if(oldIds!==newIds||!repos.length){const offset=rail.scrollLeft;rail.replaceChildren(...buttons);rail.scrollLeft=offset;if(!repos.length)rail.innerHTML='<p class="empty">Repos will appear here when added to your repos folder.</p>';}
  renderDetail();updatePosition();
  const displayedRows = [...rail.querySelectorAll('.repo-card')].map(button => {
    const row = {repo_id: button.dataset.repoId, phase: button.className.split(' ')[1],
      display_label: button.querySelector('.card-status').textContent.split(' · ')[0],
      ready: button.classList.contains('ready'), category: button.dataset.category,
      display_headline: button.dataset.headline};
    if (row.repo_id === selectedId) row.timing = JSON.parse($('#backup-timing').dataset.receipt);
    return row;
  });
  void diagnosticView.observe(observedMenuState, displayedRows, clientFreshness, selectedId);
  const notifications=menuState.notifications||{},enabled=notifications.enabled===true;
  $('#notifications').setAttribute('aria-pressed',String(enabled));
  $('#notification-caption').textContent=notifications.permission==='denied'?'macOS permission needed':enabled?'On':'Off';
  $('#checked').textContent='Live · Checked '+when(menuState.cloud_checked_at);
  for(const id of ['open-backups','notifications','quit']){$('#'+id).disabled=!window.webkit?.messageHandlers?.repoHub;if($('#'+id).disabled)$('#'+id).title='Available in the Mac menu-bar panel';}
}
function renderDetail() {
  const repo = menuState.repos.find(row => row.id === selectedId);
  if (!repo) {
    $('#detail').innerHTML = '<p class="empty">Select a repo to see its backup.</p>';
    return;
  }
  const state = view(repo);
  const cloud = repo.cloud || {};
  const copying = state.phase === 'copying';
  const uploading = state.phase === 'uploading'
    && cloud.archive === repo.last_backup?.archive;
  const showProgress = repo.health?.fresh === true && (copying || uploading);
  const progressLabel = copying ? 'Creating and verifying the archive'
    : state.percent === null ? 'macOS has not supplied a percentage'
    : state.percent === 100 ? '100% · waiting for completion confirmation' : percentLabel(state.percent);
  const progress = showProgress ? `<div class="progress-line"><progress max="100"
    ${!copying && state.percent !== null ? `value="${state.percent}"` : ''}
    aria-label="${escape(repo.name)} ${copying ? 'backup' : 'upload'} progress"></progress>
    <span>${escape(progressLabel)}</span></div>` : '';
  const retry = ['changing', 'error'].includes(repo.verification?.state)
    ? `<button id="retry-check" class="repo-schedule" ${retryingRepo === repo.id ? 'disabled' : ''}>
      ${retryingRepo === repo.id ? 'Check requested…' : 'Retry check now'}</button>` : '';
  const schedule = RepoStatus.describeSchedule(repo, menuState.power_source);
  const timing = RepoStatus.timing(repo, menuState.backup, clientFreshness);
  const markup = `
    <p class="detail-context">${escape(repo.name)}</p>
    <h2 class="status-headline" data-category="${state.category}">${escape(state.headline)}</h2>
    <p class="status-explanation" data-category="${state.category}">${escape(state.detail)}</p>
    ${progress}${retry}
    <div id="backup-timing" class="backup-timing" data-receipt="${escape(JSON.stringify(timing.receipt))}">
      <dl class="backup-facts" aria-label="Latest backup">
        <dt>Where:</dt><dd>${escape(timing.locationLabel)}</dd>
        <dt>When:</dt><dd>${timing.createdLabel !== 'Unavailable' && timing.createdLabel !== 'Not yet'
          ? `<time datetime="${escape(timing.receipt.created_at)}" title="Backup creation time">${escape(timing.createdLabel)}</time>`
          : escape(timing.createdLabel)}</dd>
      </dl>
      <p class="next-backup">${escape(timing.nextLine)}</p>
      ${timing.inclusionLine ? `<p class="backup-inclusion">${escape(timing.inclusionLine)}</p>` : ''}
    </div>
    <button id="repo-schedule" class="repo-schedule" aria-label="Schedule for ${escape(repo.name)}">
      <span class="schedule-copy"><strong>${escape(schedule.label)}</strong>
        <small>${escape(schedule.detail)}</small></span><span aria-hidden="true">›</span>
    </button>
    <details id="technical-details" ${technicalOpen.has(repo.id) ? 'open' : ''}>
      <summary id="technical-toggle">Technical details</summary>
      <p class="technical-explanation" data-category="${state.category}">${escape(state.technicalDetail)}</p>
      <div class="facts">
        <div class="fact"><small>Hashes last checked</small>${when(repo.verification?.checked_at)}</div>
        <div class="fact"><small>Upload last checked</small>${when(cloud.checked_at)}</div>
        <div class="fact"><small>Archive size</small>${bytes(repo.last_backup?.archive_bytes)}</div>
      </div>
      ${repo.health?.fresh !== true ? `<p>${escape((repo.health?.reasons || ['Fresh evidence unavailable']).join(' · '))}</p>` : ''}
    </details>
    <button id="report-status" type="button" class="report-status">Report this status</button>`;
  if ($('#detail').innerHTML !== markup) {
    const focused = $('#detail').contains(document.activeElement) ? document.activeElement.id : null;
    $('#detail').innerHTML = markup;
    if (focused) document.getElementById(focused)?.focus({preventScroll: true});
  }
  $('#technical-details').ontoggle = () => {
    if ($('#technical-details').open) technicalOpen.add(repo.id);
    else technicalOpen.delete(repo.id);
  };
  $('#repo-schedule').onclick = () => openSettings(repo.id);
  $('#report-status').onclick = () => {
    if (window.RepoHubReports) void window.RepoHubReports.openStatus(state);
    else $('#notice').textContent = 'Reporting is not available yet. Please reload this view.';
  };
  if ($('#retry-check')) $('#retry-check').onclick = async () => {
    retryingRepo = repo.id;
    renderDetail();
    try {
      sessionToken = (await api('/api/session')).token;
      await api('/api/retry-check', {repo_id: repo.id});
      $('#notice').textContent = 'Check requested for ' + repo.name + '.';
    } catch (error) {
      $('#notice').textContent = error.message;
    } finally {
      setTimeout(() => {retryingRepo = null; void load();}, 1000);
    }
  };
}
function selectRepo(id){selectedId=id;render();}
function updatePosition(){const rail=$('#cards'),buttons=[...rail.querySelectorAll('.repo-card')],rect=rail.getBoundingClientRect();const visible=buttons.map((button,i)=>({rect:button.getBoundingClientRect(),index:i})).filter(b=>b.rect.left>=rect.left-2&&b.rect.right<=rect.right+2);$('#position').textContent=visible.length?`${visible[0].index+1}–${visible[visible.length-1].index+1} of ${buttons.length} repos`:`${buttons.length} repos`;$('#previous').disabled=rail.scrollLeft<=2;$('#next').disabled=rail.scrollLeft+rail.clientWidth>=rail.scrollWidth-2;}
const motion=()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth';
$('#previous').onclick=()=>$('#cards').scrollBy({left:-($('#cards').clientWidth+10),behavior:motion()});$('#next').onclick=()=>$('#cards').scrollBy({left:$('#cards').clientWidth+10,behavior:motion()});$('#cards').addEventListener('scroll',updatePosition,{passive:true});
$('#cards').addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;const rows=menuState?.repos||[],index=rows.findIndex(r=>r.id===selectedId);const target=e.key==='Home'?0:e.key==='End'?rows.length-1:Math.max(0,Math.min(rows.length-1,index+(e.key==='ArrowRight'?1:-1)));if(!rows[target])return;e.preventDefault();selectRepo(rows[target].id);const button=[...$('#cards').querySelectorAll('.repo-card')].find(b=>b.dataset.repoId===selectedId);button?.focus({preventScroll:true});button?.scrollIntoView({behavior:motion(),block:'nearest',inline:'nearest'});});
function unreachable(message,reason='request_failed'){clientFreshness=reason;if(observedMenuState){menuState=RepoDiagnostics.displayState(observedMenuState,reason);render();}$('#backup').disabled=true;$('#notice').textContent=message;$('#checked').textContent='Status outdated · reconnecting';}
async function load(){if(loading)return;loading=true;try{observedMenuState=await api('/api/status');clientFreshness='current';menuState=observedMenuState;lastResponseAt=Date.now();render();}catch(e){unreachable('Could not reach the local backup helper.',e.name==='AbortError'?'response_timeout':'request_failed');}finally{loading=false;}}
$('#backup').onclick=async()=>{try{sessionToken=(await api('/api/session')).token;$('#backup').disabled=true;await api('/api/backup',{});$('#notice').textContent='Backup requested.';setTimeout(load,700);}catch(e){$('#notice').textContent=e.message;$('#backup').disabled=false;}};
$('#open-backups').onclick=()=>nativeAction('openBackups');$('#notifications').onclick=()=>{if(nativeAction('toggleNotifications'))setTimeout(load,500);};$('#quit').onclick=()=>nativeAction('quit');window.addEventListener('repoHubNotificationsChanged',load);
const powerName = source => source === 'battery' ? 'On battery'
  : source === 'adapter' ? 'On power adapter' : 'Power source unavailable';
let savedSchedule = null;
let savedScheduleKey = '';
let savingSchedule = false;
let discardDecision = null;
let activeSettingsPage = 'home';

function showSettingsPage(page) {
  const titles = {home: 'Settings', schedule: 'Backup schedule', notifications: 'Notifications',
    updates: 'App updates', help: 'Help & diagnostics', access: 'Access & permissions'};
  if (!(page in titles)) return;
  activeSettingsPage = page;
  for (const name of Object.keys(titles)) {
    const selector = name === 'home' ? '#settings-home' : '#settings-page-' + name;
    $(selector).hidden = name !== page;
  }
  $('#settings-title').textContent = settingsRepo && page === 'schedule'
    ? 'Schedule · ' + (menuState?.repos?.find(row => row.id === settingsRepo)?.name || 'Repository')
    : titles[page];
  $('#settings-back').hidden = page === 'home';
  $('#settings-back').textContent = settingsRepo ? '‹ Backups' : '‹ Settings';
  $('#schedule-actions').hidden = page !== 'schedule';
  $('#settings-content').scrollTop = 0;
  $('#settings-title').focus();
  if (page === 'updates') {
    const native = !!window.webkit?.messageHandlers?.repoHub;
    $('#check-updates').disabled = !native;
    $('#updates-note').textContent = native
      ? 'Your backup folders and settings stay separate.'
      : 'Check for Updates is available in the installed Mac app.';
  }
}

async function settingsBack() {
  if ($('#settings-form').hidden) return window.RepoHubWorkspaces?.close(false);
  if (activeSettingsPage === 'schedule' && !await leaveSchedule()) return;
  if (settingsRepo) $('#settings-dialog').close();
  else showSettingsPage('home');
}


function scheduleDraft() {
  if (settingsRepo !== null && $('#repo-defaults').checked) return null;
  const settings = {};
  for (const source of ['battery', 'adapter']) {
    settings[source] = {
      frequency_minutes: Number($('#' + source + '-frequency').value),
      after_edits: $('#' + source + '-edits').checked,
      edit_delay_minutes: Number($('#' + source + '-delay').value),
    };
  }
  if (!$('#battery-automatic').checked) {
    settings.battery.frequency_minutes = 0;
    settings.battery.after_edits = false;
  }
  return settings;
}

function scheduleDirty() {
  return JSON.stringify(scheduleDraft()) !== savedScheduleKey;
}

function settingsDisabled() {
  const inherited = settingsRepo !== null && $('#repo-defaults').checked;
  $('#settings-close').disabled = savingSchedule;
  $('#settings-back').disabled = savingSchedule;
  $('#repo-defaults').disabled = savingSchedule;
  $('#battery-automatic').disabled = savingSchedule || inherited;
  for (const source of ['battery', 'adapter']) {
    const disabled = savingSchedule || inherited
      || (source === 'battery' && !$('#battery-automatic').checked);
    for (const field of ['frequency', 'edits']) {
      $('#' + source + '-' + field).disabled = disabled;
    }
    $('#' + source + '-delay').disabled = disabled || !$('#' + source + '-edits').checked;
  }
  $('#settings-save').disabled = savingSchedule || !scheduleDirty();
  $('#settings-save').textContent = savingSchedule ? 'Saving…' : 'Save changes';
}

function fillSettings(settings) {
  $('#battery-automatic').checked = !!(settings.battery.frequency_minutes || settings.battery.after_edits);
  for (const source of ['battery', 'adapter']) {
    const policy = settings[source];
    $('#' + source + '-frequency').value = policy.frequency_minutes;
    $('#' + source + '-edits').checked = policy.after_edits;
    $('#' + source + '-delay').value = policy.edit_delay_minutes;
  }
}

function confirmDiscard(dirty) {
  if (!dirty) return Promise.resolve(true);
  if (discardDecision) return Promise.resolve(false);
  $('#settings-discard').showModal();
  $('#settings-keep').focus();
  return new Promise(resolve => { discardDecision = resolve; });
}

function finishDiscard(discard) {
  $('#settings-discard').close();
  const resolve = discardDecision;
  discardDecision = null;
  if (resolve) resolve(discard);
}

async function leaveSchedule() {
  if (savingSchedule) return false;
  if (!await confirmDiscard(scheduleDirty())) return false;
  // Discard restores the saved draft, including its inheritance choice.
  fillSettings(savedSchedule);
  $('#settings-error').textContent = '';
  $('#repo-defaults').checked = settingsRepo !== null && savedScheduleKey === 'null';
  settingsDisabled();
  return true;
}

async function closeSettings() {
  if ($('#settings-form').hidden) return window.RepoHubWorkspaces?.close(true);
  if (await leaveSchedule()) $('#settings-dialog').close();
}

for (const source of ['battery', 'adapter']) {
  $('#' + source + '-frequency').innerHTML = [
    [0, 'Off'], [15, '15 minutes'], [30, '30 minutes'],
    [60, '1 hour'], [120, '2 hours'], [240, '4 hours'],
  ].map(([value, label]) => `<option value="${value}">${label}</option>`).join('');
  $('#' + source + '-delay').innerHTML = [2, 5, 10, 15, 30]
    .map(value => `<option value="${value}">${value} minutes</option>`).join('');
  $('#' + source + '-edits').onchange = settingsDisabled;
}
$('#repo-defaults').onchange = () => {
  if ($('#repo-defaults').checked && settingsDefaults) fillSettings(settingsDefaults);
  settingsDisabled();
};
$('#battery-automatic').onchange = () => {
  if ($('#battery-automatic').checked && Number($('#battery-frequency').value) === 0) {
    $('#battery-frequency').value = 60;
  }
  settingsDisabled();
};
for (const event of ['input', 'change']) {
  $('#settings-form').addEventListener(event, settingsDisabled);
}
$('#settings-keep').onclick = () => finishDiscard(false);
$('#settings-discard-confirm').onclick = () => finishDiscard(true);
$('#settings-discard').addEventListener('cancel', event => {
  event.preventDefault();
  finishDiscard(false);
});
$('#settings-dialog').addEventListener('cancel', event => {
  if ($('#settings-form').hidden) return;
  event.preventDefault();
  void closeSettings();
});

async function openSettings(repoId = null, page = 'home') {
  if ($('#settings-dialog').open) {
    if ($('#settings-form').hidden) {
      if (!await window.RepoHubWorkspaces?.close(false)) return false;
    } else if (activeSettingsPage === 'schedule' && !await leaveSchedule()) return false;
  }
  try {
    const result = await api(repoId ? '/api/repo-settings/' + encodeURIComponent(repoId) : '/api/settings');
    settingsRepo = repoId;
    settingsRevision = result.revision;
    defaultsRevision = result.defaults_revision || '';
    settingsDefaults = result.defaults || result.settings;
    savedSchedule = result.settings;
    fillSettings(savedSchedule);
    $('#repo-defaults-label').hidden = !repoId;
    $('#repo-defaults').checked = !result.override;
    savedScheduleKey = JSON.stringify(scheduleDraft());
    const repo = menuState?.repos?.find(row => row.id === repoId);
    $('#settings-title').textContent = repo ? 'Schedule · ' + repo.name : 'Default backup settings';
    $('#settings-scope').textContent = repo
      ? 'Only this repo. Use defaults to follow the main settings automatically.'
      : 'Default behavior for every repo without a custom schedule. Individual schedules are adjusted from each menu-bar card.';
    settingsDisabled();
    $('#readiness-panel').hidden = !!repoId;
    $('#settings-power').textContent = 'Currently: ' + powerName(result.power_source);
    $('#settings-error').textContent = '';
    $('#settings-form').hidden = false;
    $('#workspace-form').hidden = true;
    if (!$('#settings-dialog').open) $('#settings-dialog').showModal();
    showSettingsPage(repoId ? 'schedule' : page);
    return true;
  } catch (error) {
    $('#notice').textContent = error.message;
    return false;
  }
}
$('#settings').onclick = () => openSettings();
$('#settings-close').onclick = closeSettings;
$('#settings-cancel').onclick = settingsBack;
$('#settings-back').onclick = settingsBack;
for (const page of ['schedule', 'notifications', 'updates', 'help', 'access']) {
  $('#settings-nav-' + page).onclick = () => page === 'schedule'
    ? openSettings(null, 'schedule') : showSettingsPage(page);
}
$('#settings-form').onsubmit = async event => {
  event.preventDefault();
  if (savingSchedule || !scheduleDirty()) return;
  const settings = scheduleDraft();
  savingSchedule = true;
  settingsDisabled();
  $('#settings-error').textContent = '';
  try {
    sessionToken = (await api('/api/session')).token;
    const path = settingsRepo ? '/api/repo-settings/' + encodeURIComponent(settingsRepo) : '/api/settings';
    const payload = settingsRepo
      ? {settings, revision: settingsRevision, defaults_revision: defaultsRevision}
      : {settings, revision: settingsRevision};
    const saved = await api(path, payload);
    settingsRevision = saved.revision;
    savedSchedule = saved.settings;
    savedScheduleKey = JSON.stringify(settings);
    if (settingsRepo) $('#settings-dialog').close();
    else { settingsDefaults = saved.settings; showSettingsPage('home'); }
    $('#notice').textContent = 'Backup schedule saved.';
    await load();
  } catch (error) {
    $('#settings-error').textContent = error.message + ' Your changes are still here; nothing was confirmed saved.';
  } finally {
    savingSchedule = false;
    settingsDisabled();
  }
};
window.RepoHubSettings = {
  confirmDiscard, leaveSchedule,
  showHome: () => showSettingsPage('home'),
  openAccess: async () => { if (await openSettings()) showSettingsPage('access'); },
  workspaceOpened: () => {
    $('#settings-title').textContent = 'Folders to back up';
    $('#settings-back').hidden = false;
    $('#settings-content').scrollTop = 0;
    $('#settings-title').focus();
  },
};
window.addEventListener('resize',updatePosition);setInterval(()=>{if(lastResponseAt&&Date.now()-lastResponseAt>20000)unreachable('Status outdated: waiting for the local helper.','cache_expired');},5000);
(async()=>{try{sessionToken=(await api('/api/session')).token;}catch(e){/* Read status still works; writes acquire a fresh token when needed. */}await load();setInterval(load,5000);})();

$('#connect-github').onclick=()=>nativeAction('connectGitHub');

window.addEventListener('repoHubWorkspacesChanged',()=>void load());

const updateButton = document.getElementById('check-updates');
if (updateButton) {
  updateButton.onclick = () => {
    if (window.webkit?.messageHandlers?.repoHub) {
      window.webkit.messageHandlers.repoHub.postMessage({action: 'checkForUpdates'});
    } else {
      $('#notice').textContent = 'Check for Updates is available in the installed app.';
    }
  };
}

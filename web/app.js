let observedState=null,clientFreshness='current';
const diagnosticView=RepoDiagnostics.create('app');
let state=null, sessionToken='', advanced=false, settingsRevision='', loading=false, lastResponseAt=0,legendOpen=false,thingsOpen=false,folderDemoUntil=0,folderDemoTimer=null;
const $=s=>document.querySelector(s);
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function bytes(n){if(!Number.isFinite(n))return '—';const units=['B','KB','MB','GB','TB'];let i=0;while(n>=1024&&i<4){n/=1024;i++;}return new Intl.NumberFormat(undefined,{maximumFractionDigits:1}).format(n)+' '+units[i];}
function when(value){if(!value)return 'Not yet';return new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});}
async function api(path,payload){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);try{const response=await fetch(path,{signal:controller.signal,...(payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-RepoHub-Token':sessionToken},body:JSON.stringify(payload)})});const result=await response.json();if(!response.ok)throw new Error(result.error||'Request failed');return result;}finally{clearTimeout(timer);}}
function message(text){$('#message').textContent=text;}
async function load(){if(loading)return;loading=true;try{
  observedState=await api('/api/status');clientFreshness='current';state=observedState;lastResponseAt=Date.now();
  $('#backup').disabled=state.backup.running;
  $('#backup').textContent=state.backup.running?'Backing up…':'Back up now';
  $('#footer').textContent=`Live upload status · Checked ${when(state.cloud_checked_at)} · Updates about every ${state.cloud_poll_seconds||5} seconds. Hash verification every 15 minutes or on Refresh.`;
  $('#footer').textContent+=' '+scheduleLabel(state);
  const notifications=state.notifications||{};
  $('#footer').textContent+=' Notifications: '+(notifications.enabled===false?'off':notifications.permission==='allowed'?'on':notifications.permission==='denied'?'allow Repo Hub in System Settings → Notifications':notifications.permission==='waiting'?'waiting for macOS permission':'checking permission')+'.';
  if(state.data_cloud?.state==='error')$('#footer').textContent+=' Saved helper data: '+(state.data_cloud.detail||'iCloud upload issue');
  if(state.repos.some(r=>r.health?.fresh!==true))message('Status outdated for one or more repos. Waiting for fresh checks.');
  else if(state.backup.running)message(`Backing up ${state.backup.current_repo||'your repos'}…`);
  else if(state.backup.errors?.length)message(state.backup.errors.map(e=>(e.repo?e.repo+': ':'')+e.error).join(' · '));
  else if(state.repos.some(r=>r.cloud?.state==='error'))message(`${state.repos.filter(r=>r.cloud?.state==='error').length} repo uploads report an issue. Previous backups are kept; see Advanced for details.`);
  else if(state.repos.some(r=>r.cloud?.state==='uploading'))message(`${state.repos.filter(r=>r.cloud?.state==='uploading').length} repo uploads in progress. Previous backups stay until upload confirmation.`);
  else if(state.verifying)message('Verifying hashes: '+state.verifying+'…');
  else message('');
  render();
}catch(e){markUnreachable('Could not reach the local helper: '+e.message);}finally{loading=false;}}
function backupIssue(repo){return repo.error || repo.verification?.error || state.backup.errors?.find(e=>e.repo===repo.name)?.error;}
function matchLabel(repo){if(repo.health?.fresh!==true)return 'Status outdated';return backupIssue(repo)?'Backup issue':repo.needs_backup?(repo.last_backup?'Needs backup':'First backup pending'):repo.verification?.state==='matched'?'Hashes verified':'Verifying hashes';}
const uploadLabel=r=>r.health?.fresh!==true?'Waiting for fresh checks':({uploaded:'iCloud upload confirmed',uploading:'Uploading to iCloud',pending:'Waiting for iCloud',error:'Upload not confirmed · issue reported',unknown:'iCloud status unknown'}[r.cloud?.state]||'iCloud status unknown');
function progressView(repo){
  if(repo.health?.fresh!==true)return '';
  const cloud=repo.cloud||{};
  if(!['uploading','pending'].includes(cloud.state))return '';
  const known=typeof cloud.percent==='number'&&Number.isFinite(cloud.percent)&&cloud.percent>=0&&cloud.percent<=100;
  const percent=known?cloud.percent.toFixed(1).replace(/\.0$/,'')+'%':'';
  const label=known?(cloud.percent>=99.95?'100% · Waiting for confirmation':percent):'Percentage unavailable';
  return `<div class="upload-progress"><progress max="100" ${known?`value="${cloud.percent}"`:''} aria-label="${escape(repo.name)} upload progress"></progress><span>${label}</span></div>`;
}
function render(){
  if(!state)return;
  const rows=state.repos;
  const uploaded=rows.filter(r=>r.cloud?.state==='uploaded'&&r.health?.fresh===true).length;
  const matched=rows.filter(r=>!r.needs_backup&&!backupIssue(r)&&r.verification?.state==='matched'&&r.health?.fresh===true).length;
  const ignored=rows.filter(r=>r.health?.fresh===true&&!backupIssue(r)&&RepoStatus.finderOnly(r)).length;
  const summary=ignored?`${matched} fully matched · ${ignored} Finder-only · ${uploaded} uploaded`:`${matched} of ${rows.length} hashes verified · ${uploaded} uploaded`;
  $('#content').innerHTML=`<section class="panel repo-panel"><div class="panel-heading"><h2>${summary}</h2><label class="advanced-toggle"><input id="advanced" type="checkbox" ${advanced?'checked':''}> Advanced</label></div><ul class="repo-list">${rows.map(r=>{
    const issue=backupIssue(r), presentation=RepoStatus.view(r,state.backup), iconError=presentation.phase==='error', pending=!presentation.ready;
    return `<li class="repo-row" data-repo-id="${escape(r.id)}" data-diagnostic-phase="${escape(presentation.phase)}" data-diagnostic-ready="${presentation.ready}"><div class="repo-line"><span class="match-icon ${iconError?'error':presentation.phase==='background'?'background':pending?'pending':''}" aria-label="${escape(presentation.label+' · '+presentation.detail)}">${RepoStatus.icon(presentation.phase)}</span><div class="repo-name">${escape(r.name)}<small>${escape(presentation.label)} <span class="upload-state ${escape(r.health?.fresh!==true?'stale':r.cloud?.state||'unknown')}" title="${escape(r.cloud?.detail||'')}"> · ${escape(presentation.detail)}</span></small>${progressView(r)}</div><span class="snapshot-time">${r.verification?.state==='matched'?'Verified '+when(r.verification.checked_at):r.last_backup?'Saved '+when(r.last_backup.completed_at):'Not backed up yet'}</span></div>${advanced?`<div class="repo-detail"><div><span>Git</span>${r.is_git?`${escape(r.branch)} · ${r.staged_files??'—'} staged · ${r.unstaged_files??'—'} unstaged · ${r.untracked_files??'—'} untracked`:'Folder without Git'}</div><div><span>Latest file timestamp</span>${when(r.last_file_change)} · ${escape(r.last_changed_file||'—')}</div>${r.verification?.state==='different'&&r.verification?.changes?.examples?.length?`<div><span>Differences from backup</span>${r.verification.changes.examples.map(item=>escape(item.path)+' ('+escape(item.change)+')').join(' · ')}</div>`:''}${r.health?.fresh!==true?`<div>${escape((r.health?.reasons||['Waiting for fresh checks']).join(' · '))}</div>`:''}${issue?`<div class="error-text">${escape(issue)}</div>`:''}<div><span>iCloud checked</span>${when(r.cloud?.checked_at)}${r.cloud?.detail?' · '+escape(r.cloud.detail):''}</div>${r.cloud?.progress_source?`<div><span>Progress source</span>${escape(r.cloud.progress_source)} · Transfer progress is separate from confirmation.</div>`:''}<div><span>Snapshot</span>${bytes(r.last_backup?.archive_bytes)}<p class="path">${escape(r.last_backup?.archive||'No snapshot yet')}</p></div></div>`:''}</li>`;
  }).join('')}</ul></section><section class="status-key"><button id="status-key-toggle" aria-expanded="${legendOpen}" aria-controls="status-legend">What the status icons mean</button><div id="status-legend" class="status-legend" ${legendOpen?'':'hidden'}>${RepoStatus.legend()}</div></section><section class="status-key things-key"><button id="things-toggle" aria-expanded="${thingsOpen}" aria-controls="things-panel">Things to know</button><div id="things-panel" ${thingsOpen?'':'hidden'}><p class="folder-tip-row"><span id="folder-example" class="folder-example ${Date.now()<folderDemoUntil?'demonstrating':''}" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M3 7V5h6l2 2h10v13H3Z"/></svg></span><span>The folder icon on each menu-bar card opens that repo on your Mac in Finder.</span><button id="show-folder" class="show-me">Show me</button></p><span id="folder-demo-status" class="sr-only" role="status"></span><p>Use the menu-bar Schedule control for custom timing. The main gear sets defaults.</p><p>Backups include ignored files and uncommitted work. Back up now checks every repo.</p></div></section><p class="hint">✓ Hashes verified and macOS confirmed the upload. Backup notifications are controlled from the menu bar. Ignored files and uncommitted work are included.</p>`;
  void diagnosticView.observe(observedState,[...document.querySelectorAll('.repo-row')].map(row=>({repo_id:row.dataset.repoId,phase:row.dataset.diagnosticPhase,display_label:row.querySelector('.repo-name small').firstChild.textContent.trim(),ready:row.dataset.diagnosticReady==='true'})),clientFreshness);
  $('#advanced').onchange=e=>{advanced=e.target.checked;render();};
  $('#show-folder').onclick=()=>{folderDemoUntil=Date.now()+1400;clearTimeout(folderDemoTimer);const icon=$('#folder-example');icon.classList.remove('demonstrating');void icon.offsetWidth;icon.classList.add('demonstrating');$('#folder-demo-status').textContent='This is the folder button shown on each menu-bar repo card. It opens the local repo in Finder.';folderDemoTimer=setTimeout(()=>$('#folder-example')?.classList.remove('demonstrating'),1400);};
  $('#things-toggle').onclick=()=>{thingsOpen=!thingsOpen;$('#things-panel').hidden=!thingsOpen;$('#things-toggle').setAttribute('aria-expanded',String(thingsOpen));};
  $('#status-key-toggle').onclick=()=>{legendOpen=!legendOpen;$('#status-legend').hidden=!legendOpen;$('#status-key-toggle').setAttribute('aria-expanded',String(legendOpen));};
}
$('#refresh').onclick=async()=>{try{await api('/api/scan',{});await load();}catch(e){message(e.message);}};
$('#backup').onclick=async()=>{try{await api('/api/backup',{});message('Backup requested.');setTimeout(load,700);}catch(e){message(e.message);}};
const powerName=source=>source==='battery'?'On battery':source==='adapter'?'On power adapter':'Power source unavailable';
function scheduleLabel(status){const policy=status.settings?.[status.power_source];if(!policy)return 'Automatic backups paused: power source unavailable.';const timed=policy.frequency_minutes?'every '+policy.frequency_minutes+' minutes':'timed backups off',edits=policy.after_edits?'; after '+policy.edit_delay_minutes+' quiet minutes following edits':'';return 'Default schedule · '+powerName(status.power_source)+': '+timed+edits+'. Custom repo schedules are set from the menu bar.';}
function markUnreachable(reason,freshness='request_failed'){clientFreshness=freshness;if(observedState){state=RepoDiagnostics.displayState(observedState,freshness);render();}$('#backup').disabled=true;message(reason);}
setInterval(()=>{if(lastResponseAt&&Date.now()-lastResponseAt>20000)markUnreachable('Status outdated: waiting for the local helper.','cache_expired');},5000);
const frequencies=[[0,'Off'],[15,'15 minutes'],[30,'30 minutes'],[60,'1 hour'],[120,'2 hours'],[240,'4 hours']],delays=[2,5,10,15,30];
for(const source of ['battery','adapter']){$('#'+source+'-frequency').innerHTML=frequencies.map(([value,label])=>`<option value="${value}">${label}</option>`).join('');$('#'+source+'-delay').innerHTML=delays.map(value=>`<option value="${value}">${value} minutes</option>`).join('');$('#'+source+'-edits').onchange=()=>{defaultFieldsDisabled();};}
function defaultFieldsDisabled(){const manual=!$('#battery-automatic').checked;for(const source of ['battery','adapter']){const disabled=source==='battery'&&manual;for(const field of ['frequency','edits'])$('#'+source+'-'+field).disabled=disabled;$('#'+source+'-delay').disabled=disabled||!$('#'+source+'-edits').checked;}}
$('#battery-automatic').onchange=()=>{if($('#battery-automatic').checked&&Number($('#battery-frequency').value)===0)$('#battery-frequency').value=60;defaultFieldsDisabled();};
$('#settings').onclick=async()=>{try{const result=await api('/api/settings');settingsRevision=result.revision;$('#battery-automatic').checked=!!(result.settings.battery.frequency_minutes||result.settings.battery.after_edits);for(const source of ['battery','adapter']){const policy=result.settings[source];$('#'+source+'-frequency').value=policy.frequency_minutes;$('#'+source+'-edits').checked=policy.after_edits;$('#'+source+'-delay').value=policy.edit_delay_minutes;$('#'+source+'-delay').disabled=!policy.after_edits;}defaultFieldsDisabled();$('#settings-power').textContent='Currently: '+powerName(result.power_source);$('#settings-error').textContent='';$('#settings-dialog').showModal();}catch(e){message('Could not open settings: '+e.message);}};
for(const id of ['settings-close','settings-cancel'])$('#'+id).onclick=()=>$('#settings-dialog').close();
$('#settings-form').onsubmit=async e=>{e.preventDefault();$('#settings-save').disabled=true;try{sessionToken=(await api('/api/session')).token;const settings={};for(const source of ['battery','adapter'])settings[source]={frequency_minutes:Number($('#'+source+'-frequency').value),after_edits:$('#'+source+'-edits').checked,edit_delay_minutes:Number($('#'+source+'-delay').value)};if(!$('#battery-automatic').checked){settings.battery.frequency_minutes=0;settings.battery.after_edits=false;}await api('/api/settings',{settings,revision:settingsRevision});$('#settings-dialog').close();await load();}catch(e){$('#settings-error').textContent=e.message;}finally{$('#settings-save').disabled=false;}};
(async()=>{try{sessionToken=(await api('/api/session')).token;await load();setInterval(load,5000);}catch(e){message(e.message);}})();

window.addEventListener('repoHubWorkspacesChanged',()=>void load());

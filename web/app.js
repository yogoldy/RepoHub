let state=null, sessionToken='', advanced=false;
const $=s=>document.querySelector(s);
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const bytes=n=>n?new Intl.NumberFormat(undefined,{maximumFractionDigits:1}).format(n/1024**3)+' GB':'—';
function when(value){if(!value)return 'Not yet';return new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});}
async function api(path,payload){const response=await fetch(path,payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-RepoHub-Token':sessionToken},body:JSON.stringify(payload)});const result=await response.json();if(!response.ok)throw new Error(result.error||'Request failed');return result;}
function message(text){$('#message').textContent=text;}
async function load(){try{state=await api('/api/status');$('#backup').disabled=state.backup.running;$('#backup').textContent=state.backup.running?'Backing up…':'Back up now';$('#footer').textContent=`Status checked ${when(state.scanned_at)} · Refreshes every 30 seconds · Backups run hourly and skip unchanged repos.`;if(state.backup.running)message(`Backing up ${state.backup.current_repo||'your repos'}… You can keep using the hub.`);else if(state.backup.errors?.length)message(state.backup.errors.map(e=>(e.repo?e.repo+': ':'')+e.error).join(' · '));else message('');render();}catch(e){message('Could not reach the local helper: '+e.message);}}
function backupIssue(repo){return repo.error || state.backup.errors?.find(e=>e.repo===repo.name)?.error;}
function matchLabel(repo){return backupIssue(repo)?'Backup issue':repo.needs_backup?(repo.last_backup?'Needs backup':'First backup pending'):'Matches Desktop';}
function render(){
  if(!state)return;
  const rows=state.repos;
  const matched=rows.filter(r=>!r.needs_backup&&!backupIssue(r)).length;
  $('#content').innerHTML=`<section class="panel repo-panel"><div class="panel-heading"><h2>${matched} of ${rows.length} match</h2><label class="advanced-toggle"><input id="advanced" type="checkbox" ${advanced?'checked':''}> Advanced</label></div><ul class="repo-list">${rows.map(r=>{
    const issue=backupIssue(r), pending=r.needs_backup;
    return `<li class="repo-row"><div class="repo-line"><span class="match-icon ${issue?'error':pending?'pending':''}" aria-label="${escape(matchLabel(r))}">${issue?'!':pending?'◷':'✓'}</span><div class="repo-name">${escape(r.name)}<small>${escape(matchLabel(r))}</small></div><span class="snapshot-time">${r.last_backup?'Saved '+when(r.last_backup.completed_at):'Not backed up yet'}</span></div>${advanced?`<div class="repo-detail"><div><span>Git</span>${r.is_git?`${escape(r.branch)} · ${r.staged_files??'—'} staged · ${r.unstaged_files??'—'} unstaged · ${r.untracked_files??'—'} untracked`:'Folder without Git'}</div><div><span>Last file change</span>${when(r.last_file_change)} · ${escape(r.last_changed_file||'—')}</div>${issue?`<div class="error-text">${escape(issue)}</div>`:''}<div><span>Snapshot</span>${bytes(r.last_backup?.archive_bytes)}<p class="path">${escape(r.last_backup?.archive||'No snapshot yet')}</p></div></div>`:''}</li>`;
  }).join('')}</ul></section><p class="hint">✓ The latest backup matches the Desktop files, including uncommitted work. Copies are verified on this Mac; iCloud upload happens separately.</p>`;
  $('#advanced').onchange=e=>{advanced=e.target.checked;render();};
}
$('#refresh').onclick=async()=>{try{await api('/api/scan',{});await load();}catch(e){message(e.message);}};$('#backup').onclick=async()=>{try{await api('/api/backup',{});message('Backup requested.');setTimeout(load,700);}catch(e){message(e.message);}};
(async()=>{try{sessionToken=(await api('/api/session')).token;await load();setInterval(load,30000);}catch(e){message(e.message);}})();

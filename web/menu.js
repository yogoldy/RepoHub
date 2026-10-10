let retryingRepo=null;
const diagnosticView=RepoDiagnostics.create('menu',{native:!!window.webkit?.messageHandlers?.repoHub});
let menuState=null,selectedId=null,sessionToken='',loading=false,lastResponseAt=0,settingsRevision='',settingsRepo=null,defaultsRevision='',settingsDefaults=null;
const $=s=>document.querySelector(s);
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function when(value){if(!value)return 'Not yet';return new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});}
function bytes(n){if(!Number.isFinite(n))return '—';const units=['B','KB','MB','GB'];let i=0;while(n>=1024&&i<3){n/=1024;i++;}return new Intl.NumberFormat(undefined,{maximumFractionDigits:1}).format(n)+' '+units[i];}
async function api(path,payload){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);try{const response=await fetch(path,{signal:controller.signal,...(payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-RepoHub-Token':sessionToken},body:JSON.stringify(payload)})});const value=await response.json();if(!response.ok)throw new Error(value.error||'Request failed');return value;}finally{clearTimeout(timer);}}
function nativeAction(action,repoId){const bridge=window.webkit?.messageHandlers?.repoHub;if(!bridge){$('#notice').textContent='This control is available from the Mac menu bar.';return false;}bridge.postMessage(repoId?{action,repo_id:repoId}:{action});return true;}
function view(repo){return RepoStatus.view(repo,menuState?.backup);}
$('#status-legend').innerHTML=RepoStatus.legend();
let folderDemoTimer=null;
$('#show-folder').onclick=()=>{
  const card=[...$('#cards').querySelectorAll('.repo-card')].find(b=>b.dataset.repoId===selectedId);
  const folder=card?.parentElement.querySelector('.open-repo');if(!folder)return;
  clearTimeout(folderDemoTimer);for(const node of document.querySelectorAll('.demonstrating'))node.classList.remove('demonstrating');
  folder.scrollIntoView({behavior:motion(),block:'nearest',inline:'nearest'});
  void folder.offsetWidth;folder.classList.add('demonstrating');
  const name=menuState?.repos.find(r=>r.id===selectedId)?.name||'the selected repo';
  $('#folder-demo-status').textContent='Folder button highlighted for '+name+'. Click that button to open the repo in Finder.';
  folderDemoTimer=setTimeout(()=>folder.classList.remove('demonstrating'),1400);
};
$('#things-toggle').onclick=()=>{const open=$('#things-panel').hidden;$('#things-panel').hidden=!open;$('#things-toggle').setAttribute('aria-expanded',String(open));};
window.addEventListener('repoHubFinderError',e=>{$('#notice').textContent=e.detail;});
$('#status-key-toggle').onclick=()=>{const open=$('#status-legend').hidden;$('#status-legend').hidden=!open;$('#status-key-toggle').setAttribute('aria-expanded',String(open));};
function percentLabel(percent){return percent.toFixed(1).replace(/\.0$/,'')+'%';}
function render(){
  const repos=menuState.repos||[];
  if(!repos.some(r=>r.id===selectedId))selectedId=repos[0]?.id||null;
  const ready=repos.filter(r=>view(r).ready).length;
  const ignored=repos.filter(r=>view(r).phase==='background').length;
  $('#summary').textContent=repos.length?(ignored?`${ready} fully matched · ${ignored} Finder-only · ${repos.length} repos`:`${ready} of ${repos.length} repos backed up`):'No repos found';
  $('#backup').disabled=!!menuState.backup?.running;
  $('#backup').lastElementChild.textContent=menuState.backup?.running?'Backing up…':'Back up now';
  const problems=menuState.problems||[];
  $('#notice').textContent=menuState.backup?.running?`Backing up ${menuState.backup.current_repo||'your repos'}…`:problems.length?`${problems.length} backup issue${problems.length===1?'':'s'} need attention.`:repos.some(r=>r.health?.fresh!==true)?'Waiting for fresh status checks.':'';
  const rail=$('#cards'),existing=new Map([...rail.querySelectorAll('.repo-card')].map(b=>[b.dataset.repoId,b]));
  const buttons=repos.map(repo=>{
    let button=existing.get(repo.id);
    if(!button){const slot=document.createElement('div');slot.className='card-slot';button=document.createElement('button');button.type='button';button.dataset.repoId=repo.id;button.addEventListener('click',()=>selectRepo(repo.id));slot.append(button);const folder=document.createElement('button');folder.type='button';folder.className='open-repo';folder.setAttribute('aria-label','Open '+repo.name+' in Finder');folder.title='Open '+repo.name+' on this Mac in Finder';folder.innerHTML='<span class="folder-shape" aria-hidden="true"></span>';folder.onclick=()=>nativeAction('openRepo',repo.id);folder.disabled=!window.webkit?.messageHandlers?.repoHub;if(folder.disabled)folder.title+=' · Available from the Mac menu bar';slot.append(folder);}
    const state=view(repo),label=state.label+(state.percent===null?'':' · '+percentLabel(state.percent));
    button.className='repo-card '+state.phase;button.setAttribute('aria-pressed',String(repo.id===selectedId));button.setAttribute('aria-label',repo.name+' · '+label);button.setAttribute('aria-controls','detail');
    const markup=`<span class="card-top"><span class="folder-placeholder" aria-hidden="true"></span><span class="status-mark" aria-hidden="true">${RepoStatus.icon(state.phase)}</span></span><span class="card-name">${escape(repo.name)}</span><span class="card-status">${escape(label)}</span>`;
    if(button.innerHTML!==markup)button.innerHTML=markup;
    return button.parentElement;
  });
  const oldIds=[...existing.keys()].join('|'),newIds=repos.map(r=>r.id).join('|');
  if(oldIds!==newIds||!repos.length){const offset=rail.scrollLeft;rail.replaceChildren(...buttons);rail.scrollLeft=offset;if(!repos.length)rail.innerHTML='<p class="empty">Repos will appear here when added to your repos folder.</p>';}
  renderDetail();updatePosition();
  void diagnosticView.observe(menuState,[...rail.querySelectorAll('.repo-card')].map(button=>({repo_id:button.dataset.repoId,phase:button.className.split(' ')[1],display_label:button.querySelector('.card-status').textContent.split(' · ')[0],ready:button.classList.contains('ready')})));
  const notifications=menuState.notifications||{},enabled=notifications.enabled===true;
  $('#notifications').setAttribute('aria-pressed',String(enabled));
  $('#notification-caption').textContent=notifications.permission==='denied'?'macOS permission needed':enabled?'On':'Off';
  $('#checked').textContent='Live · Checked '+when(menuState.cloud_checked_at);
  for(const id of ['open-backups','notifications','quit']){$('#'+id).disabled=!window.webkit?.messageHandlers?.repoHub;if($('#'+id).disabled)$('#'+id).title='Available in the Mac menu-bar panel';}
}
function renderDetail(){
  const repo=menuState.repos.find(r=>r.id===selectedId);if(!repo){$('#detail').innerHTML='<p class="empty">Select a repo to see its backup.</p>';return;}
  const state=view(repo),cloud=repo.cloud||{},copying=state.phase==='copying',uploading=cloud.state==='uploading'||cloud.state==='pending';
  const showProgress=repo.health?.fresh===true&&(copying||uploading),label=copying?'Building backup':state.percent===null?'Waiting for upload progress':state.percent===100?'100% · awaiting confirmation':percentLabel(state.percent);
  const progress=showProgress?`<div class="progress-line"><progress max="100" ${!copying&&state.percent!==null?`value="${state.percent}"`:''} aria-label="${escape(repo.name)} ${copying?'backup':'upload'} progress"></progress><span>${escape(label)}</span></div>`:'';
  const markup=`<div class="detail-top"><h2>${escape(repo.name)}</h2><span class="pill ${escape(state.phase)}">${escape(state.label)}</span></div><p class="detail-note" title="${escape(state.detail)}">${escape(state.detail)}</p>${progress}${['changing','error'].includes(repo.verification?.state)?`<button id="retry-check" class="repo-schedule" ${retryingRepo===repo.id?'disabled':''}>${retryingRepo===repo.id?'Check requested…':'Retry check now'}</button>`:''}<div class="facts"><div class="fact"><small>Last backup saved</small>${when(repo.last_backup?.completed_at)}</div><div class="fact"><small>Hashes checked</small>${when(repo.verification?.checked_at)}</div><div class="fact"><small>Backup size</small>${bytes(repo.last_backup?.archive_bytes)}</div></div><button id="repo-schedule" class="repo-schedule" aria-label="Schedule for ${escape(repo.name)}">Schedule <span>${repo.schedule_override?'Custom':'Default'}</span><span aria-hidden="true">›</span></button>`;
  if($('#detail').innerHTML!==markup)$('#detail').innerHTML=markup;
  $('#repo-schedule').onclick=()=>openSettings(repo.id);
  if($('#retry-check'))$('#retry-check').onclick=async()=>{
    retryingRepo=repo.id;renderDetail();
    try{sessionToken=(await api('/api/session')).token;await api('/api/retry-check',{repo_id:repo.id});$('#notice').textContent='Check requested for '+repo.name+'.';}
    catch(e){$('#notice').textContent=e.message;}
    finally{setTimeout(()=>{retryingRepo=null;void load();},1000);}
  };
}
function selectRepo(id){selectedId=id;render();}
function updatePosition(){const rail=$('#cards'),buttons=[...rail.querySelectorAll('.repo-card')],rect=rail.getBoundingClientRect();const visible=buttons.map((button,i)=>({rect:button.getBoundingClientRect(),index:i})).filter(b=>b.rect.left>=rect.left-2&&b.rect.right<=rect.right+2);$('#position').textContent=visible.length?`${visible[0].index+1}–${visible[visible.length-1].index+1} of ${buttons.length} repos`:`${buttons.length} repos`;$('#previous').disabled=rail.scrollLeft<=2;$('#next').disabled=rail.scrollLeft+rail.clientWidth>=rail.scrollWidth-2;}
const motion=()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth';
$('#previous').onclick=()=>$('#cards').scrollBy({left:-($('#cards').clientWidth+10),behavior:motion()});$('#next').onclick=()=>$('#cards').scrollBy({left:$('#cards').clientWidth+10,behavior:motion()});$('#cards').addEventListener('scroll',updatePosition,{passive:true});
$('#cards').addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;const rows=menuState?.repos||[],index=rows.findIndex(r=>r.id===selectedId);const target=e.key==='Home'?0:e.key==='End'?rows.length-1:Math.max(0,Math.min(rows.length-1,index+(e.key==='ArrowRight'?1:-1)));if(!rows[target])return;e.preventDefault();selectRepo(rows[target].id);const button=[...$('#cards').querySelectorAll('.repo-card')].find(b=>b.dataset.repoId===selectedId);button?.focus({preventScroll:true});button?.scrollIntoView({behavior:motion(),block:'nearest',inline:'nearest'});});
function unreachable(message){if(menuState){for(const repo of menuState.repos)repo.health={fresh:false,reasons:['Local helper unavailable']};render();}$('#backup').disabled=true;$('#notice').textContent=message;$('#checked').textContent='Status outdated · reconnecting';}
async function load(){if(loading)return;loading=true;try{menuState=await api('/api/status');lastResponseAt=Date.now();render();}catch(e){unreachable('Could not reach the local backup helper.');}finally{loading=false;}}
$('#backup').onclick=async()=>{try{sessionToken=(await api('/api/session')).token;$('#backup').disabled=true;await api('/api/backup',{});$('#notice').textContent='Backup requested.';setTimeout(load,700);}catch(e){$('#notice').textContent=e.message;$('#backup').disabled=false;}};
$('#open-backups').onclick=()=>nativeAction('openBackups');$('#notifications').onclick=()=>{if(nativeAction('toggleNotifications'))setTimeout(load,500);};$('#quit').onclick=()=>nativeAction('quit');window.addEventListener('repoHubNotificationsChanged',load);
const powerName=source=>source==='battery'?'On battery':source==='adapter'?'On power adapter':'Power source unavailable';
for(const source of ['battery','adapter']){$('#'+source+'-frequency').innerHTML=[[0,'Off'],[15,'15 minutes'],[30,'30 minutes'],[60,'1 hour'],[120,'2 hours'],[240,'4 hours']].map(([value,label])=>`<option value="${value}">${label}</option>`).join('');$('#'+source+'-delay').innerHTML=[2,5,10,15,30].map(value=>`<option value="${value}">${value} minutes</option>`).join('');$('#'+source+'-edits').onchange=()=>{settingsDisabled();};}
function settingsDisabled(){const inherited=settingsRepo!==null&&$('#repo-defaults').checked;$('#battery-automatic').disabled=inherited;for(const source of ['battery','adapter']){const disabled=inherited||(source==='battery'&&!$('#battery-automatic').checked);for(const field of ['frequency','edits'])$('#'+source+'-'+field).disabled=disabled;$('#'+source+'-delay').disabled=disabled||!$('#'+source+'-edits').checked;}}
$('#repo-defaults').onchange=()=>{if($('#repo-defaults').checked&&settingsDefaults)fillSettings(settingsDefaults);settingsDisabled();};
$('#battery-automatic').onchange=()=>{if($('#battery-automatic').checked&&Number($('#battery-frequency').value)===0)$('#battery-frequency').value=60;settingsDisabled();};
function fillSettings(settings){$('#battery-automatic').checked=!!(settings.battery.frequency_minutes||settings.battery.after_edits);for(const source of ['battery','adapter']){const policy=settings[source];$('#'+source+'-frequency').value=policy.frequency_minutes;$('#'+source+'-edits').checked=policy.after_edits;$('#'+source+'-delay').value=policy.edit_delay_minutes;}}
async function openSettings(repoId=null){try{const result=await api(repoId?'/api/repo-settings/'+encodeURIComponent(repoId):'/api/settings');settingsRepo=repoId;settingsRevision=result.revision;defaultsRevision=result.defaults_revision||'';settingsDefaults=result.defaults||result.settings;fillSettings(result.settings);$('#repo-defaults-label').hidden=!repoId;$('#repo-defaults').checked=!result.override;const repo=menuState.repos.find(r=>r.id===repoId);$('#settings-title').textContent=repo?'Schedule · '+repo.name:'Default backup settings';$('#settings-scope').textContent=repo?'Only this repo. Use defaults to follow the main settings automatically.':'Default behavior for every repo without a custom schedule. Individual schedules are adjusted from each menu-bar card.';settingsDisabled();$('#settings-power').textContent='Currently: '+powerName(result.power_source);$('#settings-error').textContent='';$('#settings-dialog').showModal();}catch(e){$('#notice').textContent=e.message;}}
$('#settings').onclick=()=>openSettings();
for(const id of ['settings-close','settings-cancel'])$('#'+id).onclick=()=>$('#settings-dialog').close();
$('#settings-form').onsubmit=async e=>{e.preventDefault();$('#settings-save').disabled=true;try{sessionToken=(await api('/api/session')).token;const settings={};for(const source of ['battery','adapter'])settings[source]={frequency_minutes:Number($('#'+source+'-frequency').value),after_edits:$('#'+source+'-edits').checked,edit_delay_minutes:Number($('#'+source+'-delay').value)};if(!$('#battery-automatic').checked){settings.battery.frequency_minutes=0;settings.battery.after_edits=false;}await api(settingsRepo?'/api/repo-settings/'+encodeURIComponent(settingsRepo):'/api/settings',settingsRepo?{settings:$('#repo-defaults').checked?null:settings,revision:settingsRevision,defaults_revision:defaultsRevision}:{settings,revision:settingsRevision});$('#settings-dialog').close();await load();}catch(e){$('#settings-error').textContent=e.message;}finally{$('#settings-save').disabled=false;}};
window.addEventListener('resize',updatePosition);setInterval(()=>{if(lastResponseAt&&Date.now()-lastResponseAt>20000)unreachable('Status outdated: waiting for the local helper.');},5000);
(async()=>{try{sessionToken=(await api('/api/session')).token;}catch(e){/* Read status still works; writes acquire a fresh token when needed. */}await load();setInterval(load,5000);})();

$('#connect-github').onclick=()=>nativeAction('connectGitHub');

/* Helper-observed access, separate from successful backup/upload evidence. */
(function(root){
  const labels={accessible:'Access checked',blocked:'Access blocked',unavailable:'Folder unavailable',changed:'Folder changed · review selection',error:'Access check failed',unchecked:'Not checked'};
  function label(value){return labels[value?.state]||labels.unchecked;}
  function notificationLabel(value){
    if(value.permission==='allowed')return 'allowed';
    if(value.permission==='denied')return 'denied; enable Repo Hub in macOS Notification settings';
    if(value.permission!=='waiting')return 'not checked';
    return {pending:'waiting for macOS permission',failed:'permission request failed; try again or open Notification settings',completed:'macOS has not confirmed permission; open Notification settings',not_requested:'not requested'}[value.request||'not_requested']||'not checked';
  }
  if(typeof module==='object'&&module.exports){module.exports={label,notificationLabel};return;}
  const $=id=>document.getElementById(id),dialog=$('settings-dialog');if(!dialog)return;
  let busy=false;
  async function request(path,payload){
    let options={};if(payload!==undefined){const session=await fetch('/api/session');if(!session.ok)throw new Error('Helper unavailable');options={method:'POST',headers:{'Content-Type':'application/json','X-RepoHub-Token':(await session.json()).token},body:JSON.stringify(payload)};}
    const response=await fetch(path,options),value=await response.json();if(!response.ok)throw new Error(value.error||'Access check failed');return value;
  }
  function native(action){const bridge=root.webkit?.messageHandlers?.repoHub;if(bridge)bridge.postMessage({action});}
  async function refresh(){
    if(busy||!dialog.open||$('settings-form').hidden)return;busy=true;
    try{
      const value=await request('/api/readiness');
      $('readiness-status').textContent=value.result==='failed'?'Access check failed. Retry when the helper is available.':value.result==='deferred'?'Helper busy. Check access again after the current scan or backup.':value.running?'Checking access through the backup helper…':value.checked_at?'Last checked '+new Date(value.checked_at).toLocaleString():'Check folder access before relying on automatic backups.';
      $('readiness-check').disabled=value.running;
      $('readiness-sources').replaceChildren(...value.sources.map(source=>{const li=document.createElement('li');li.textContent=source.name+' · '+label(source)+(source.detail?' · '+source.detail:'');return li;}));
      $('readiness-destination').textContent='Backup destination · '+label(value.destination)+(value.destination.detail?' · '+value.destination.detail:'');
      $('readiness-background').textContent='Backup helper · running. Login operation · '+({registered:'registered',not_registered:'not confirmed for this installation',unknown:'not checked'}[value.background.login]||'not checked')+'.';
      const permission=value.notifications.permission;
      $('readiness-notifications').textContent='Notifications · '+notificationLabel(value.notifications)+(value.notifications.enabled===false?' · turned off in Repo Hub':'')+'. Backups work without notifications.';
      const isNative=!!root.webkit?.messageHandlers?.repoHub;
      $('readiness-enable').hidden=(permission==='allowed'&&value.notifications.enabled!==false)||permission==='denied';
      for(const id of ['readiness-enable','readiness-notification-settings','readiness-privacy','readiness-login'])$(id).disabled=!isNative;
      $('readiness-enable').disabled=!isNative||value.notifications.request==='pending';
    }catch(error){$('readiness-error').textContent=error.message;}finally{busy=false;}
  }
  $('readiness-check').onclick=async()=>{try{$('readiness-error').textContent='';$('readiness-check').disabled=true;await request('/api/readiness/check',{});await refresh();}catch(error){$('readiness-error').textContent=error.message;$('readiness-check').disabled=false;}};
  $('readiness-enable').onclick=()=>native('requestNotifications');$('readiness-notification-settings').onclick=()=>native('notificationSettings');$('readiness-privacy').onclick=()=>native('privacySettings');$('readiness-login').onclick=()=>native('loginSettings');
  new MutationObserver(()=>void refresh()).observe(dialog,{attributes:true,attributeFilter:['open']});
  root.addEventListener('repoHubReadinessRequested',()=>{$('settings').click();setTimeout(()=>void refresh(),300);});
  root.addEventListener('repoHubNotificationsChanged',()=>void refresh());setInterval(()=>void refresh(),1500);
})(globalThis);

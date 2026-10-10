/* Source drafts stay local until a reviewed, revision-checked save succeeds. */
(function(root){
  function draft(value){
    const configuration=value.configuration;
    return {mode:configuration.source.mode,home:configuration.source.home||'',
      paths:configuration.workspaces.filter(row=>row.active).map(row=>row.path),revision:value.revision,
      pending:null,review:null};
  }
  function source(state){return state.mode==='home'?{mode:'home',home:state.home}:{mode:'manual',paths:[...state.paths]};}
  function picked(state,detail){
    if(!detail||detail.request_id!==state.pending)return false;
    state.pending=null;
    if(detail.cancelled)return false;
    if(!Array.isArray(detail.paths)||!detail.paths.length||detail.paths.some(p=>typeof p!=='string'||!p.startsWith('/')))return false;
    if(state.mode==='home'&&detail.paths.length!==1)return false;
    if(state.mode==='home')state.home=detail.paths[0];
    else state.paths=[...new Set([...state.paths,...detail.paths])];
    state.review=null;return true;
  }
  const model={draft,source,picked};
  if(typeof module==='object'&&module.exports){module.exports=model;return;}
  const $=id=>document.getElementById(id),dialog=$('workspace-dialog');
  if(!dialog)return;
  let state=null,busy=false;
  const native=!!root.webkit?.messageHandlers?.repoHub;
  async function request(path,payload){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
    try{
      let options={signal:controller.signal};
      if(payload!==undefined){
        const session=await fetch('/api/session',options);if(!session.ok)throw new Error('Could not connect to the local helper.');
        const token=(await session.json()).token;
        options={...options,method:'POST',headers:{'Content-Type':'application/json','X-RepoHub-Token':token},body:JSON.stringify(payload)};
      }
      const response=await fetch(path,options),value=await response.json();
      if(!response.ok){const error=new Error(value.error||'Could not save folder selection.');error.conflict=response.status===409;throw error;}
      return value;
    }finally{clearTimeout(timer);}
  }
  function row(path,remove){
    const li=document.createElement('li'),content=document.createElement('div'),name=document.createElement('strong'),location=document.createElement('small');
    name.textContent=path.split('/').filter(Boolean).at(-1)||path;location.textContent=path;content.append(name,location);li.append(content);
    if(remove){const button=document.createElement('button');button.type='button';button.textContent='Remove';button.setAttribute('aria-label','Remove '+path);button.onclick=remove;li.append(button);}
    return li;
  }
  function render(){
    if(!state)return;
    const review=state.review;
    $('workspace-edit').hidden=!!review;$('workspace-review').hidden=!review;$('workspace-back').hidden=!review;
    $('workspace-next').textContent=review?'Save monitored folders':'Review folders';$('workspace-next').disabled=busy||!!state.pending;
    $('workspace-pick').disabled=busy||!!state.pending||!native;$('workspace-native-note').hidden=native;
    for(const mode of ['home','manual']){$('workspace-'+mode+'-mode').setAttribute('aria-pressed',String(state.mode===mode));$('workspace-'+mode+'-mode').disabled=busy||!!state.pending;}
    $('workspace-description').textContent=state.mode==='home'?'Each immediate, visible subfolder becomes a repo. Nested folders stay inside their parent repo. New immediate subfolders will be discovered automatically.':'Each selected folder is one repo. Add folders from different locations; there is no shared-parent requirement.';
    $('workspace-pick').textContent=state.mode==='home'?'Select repo-home folder':'Add repo folders';
    const paths=state.mode==='home'?(state.home?[state.home]:[]):state.paths;
    $('workspace-selected').replaceChildren(...paths.map(path=>row(path,state.mode==='manual'?()=>{state.paths=state.paths.filter(p=>p!==path);state.review=null;render();}:null)));
    if(review){
      $('workspace-review-count').textContent=review.workspaces.length?review.workspaces.length+' repos will be monitored':'No repos will be monitored';
      $('workspace-review-mode').textContent=state.mode==='home'?'Immediate subfolders of '+state.home+'. Future immediate subfolders will be discovered automatically.':'Only the individual folders listed below will be monitored.';
      $('workspace-reviewed').replaceChildren(...review.workspaces.map(r=>row(r.path)));
      $('workspace-removals').hidden=!review.removed.length;
      $('workspace-removed').replaceChildren(...review.removed.map(r=>row(r.path)));
    }
  }
  async function open(){
    try{const current=await request('/api/workspaces');state=draft(current);$('settings-dialog')?.close();$('workspace-error').textContent='';$('workspace-feedback').textContent='';$('workspace-reload').hidden=true;if(!dialog.open)dialog.showModal();render();}
    catch(error){const target=$('settings-error')||$('notice');if(target)target.textContent=error.message;}
  }
  function close(){if(busy)return;if(state)state.pending=null;dialog.close();}
  $('workspace-open').onclick=open;$('workspace-reload').onclick=open;
  $('workspace-close').onclick=close;$('workspace-cancel').onclick=close;
  dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();else if(state)state.pending=null;});
  for(const mode of ['home','manual'])$('workspace-'+mode+'-mode').onclick=()=>{state.mode=mode;state.review=null;$('workspace-error').textContent='';render();};
  $('workspace-back').onclick=()=>{state.review=null;$('workspace-error').textContent='';render();};
  $('workspace-pick').onclick=()=>{
    const bytes=new Uint8Array(12);crypto.getRandomValues(bytes);state.pending=[...bytes].map(b=>b.toString(16).padStart(2,'0')).join('');
    $('workspace-feedback').textContent='Choose folders in the Mac dialog.';render();
    root.webkit.messageHandlers.repoHub.postMessage({action:state.mode==='home'?'chooseRepoHome':'chooseRepoFolders',request_id:state.pending});
  };
  root.addEventListener('repoHubSourcesPicked',event=>{
    if(!dialog.open||!state||event.detail?.request_id!==state.pending)return;
    const cancelled=event.detail.cancelled;const accepted=picked(state,event.detail);
    $('workspace-feedback').textContent=cancelled?'Folder selection cancelled. Nothing changed.':accepted?'Selection updated. Review before saving.':'No valid folders selected.';render();
  });
  $('workspace-form').onsubmit=async event=>{
    event.preventDefault();if(busy||!state||state.pending)return;busy=true;render();$('workspace-error').textContent='';
    try{
      if(!state.review){state.review=await request('/api/workspaces/preview',{source:source(state),revision:state.revision});$('workspace-feedback').textContent='Review the exact folders before saving.';}
      else{await request('/api/workspaces',{source:source(state),revision:state.revision,review:state.review.review});dialog.close();state=null;const target=$('notice')||$('message');if(target)target.textContent='Monitored folders saved. Existing backups and schedules are preserved.';}
    }catch(error){$('workspace-error').textContent=error.name==='AbortError'?'The helper took too long to respond. Reopen setup to check the saved selection.':error.message;if(error.conflict){state.review=null;$('workspace-reload').hidden=false;}}
    finally{busy=false;render();}
  };
})(typeof globalThis==='object'?globalThis:this);

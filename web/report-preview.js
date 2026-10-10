/* Exact public preview and explicit delivery; tokens never enter this view. */
(()=>{
  const el=id=>document.getElementById(id), drafts={bug:{},feature:{}};
  let kind='bug',busy=false,preview=null,connection=null,delivery={state:'draft'};
  function saveFields(){drafts[kind]={title:el('report-title').value,description:el('report-description').value,expected:el('report-expected').value,include:el('report-diagnostics').checked,hours:el('report-window').value};}
  function compose(){preview=null;el('report-compose').hidden=false;el('report-preview').hidden=true;el('report-back').hidden=true;el('report-send').hidden=true;el('report-review').hidden=false;}
  function busyFields(value){for(const field of document.querySelectorAll('#report-dialog input, #report-dialog textarea, #report-dialog select, #report-dialog button'))field.disabled=value;if(!value)updateDelivery();}
  function close(){if(busy)return;saveFields();el('report-dialog').close();}
  function updateDelivery(){
    const state=delivery.state,uncertain=state==='uncertain'||state==='sending';
    el('report-delivery-status').textContent=busy&&state==='sending'?'Sending · Waiting for GitHub confirmation':state==='sent'?'Sent · Confirmed by GitHub':uncertain?'Delivery unconfirmed · Checking will not send another issue':state==='failed'?'Send failed · Draft kept on this Mac':'Draft saved on this Mac · Nothing sent';
    el('report-send').textContent=uncertain?'Check delivery':state==='failed'?'Retry send':'Send to GitHub';
    el('report-send').disabled=busy||state==='sent'||!connection?.ready||!preview?.preview_digest;
    if(preview&&!preview.preview_digest)el('report-error').textContent='This older draft needs a new preview before it can be sent.';
    el('report-back').disabled=busy||uncertain||state==='sent';
    const link=el('report-issue-link');link.hidden=state!=='sent';
    if(state==='sent')link.href=delivery.issue_url;
    el('report-connection-status').textContent=connection?.ready?'Posting as '+connection.account+' · Public issue':connection?'GitHub is not connected or could not be reached. Set up the connection from the menu bar, then check again.':'Check your GitHub connection before sending.';
  }
  async function refreshConnection(){connection=await api('/api/reports/connection',{});updateDelivery();}
  async function savedReports(){
    const result=await api('/api/reports/list',{}),select=el('report-saved');select.replaceChildren();
    const empty=document.createElement('option');empty.value='';empty.textContent='Choose a report…';select.append(empty);
    for(const row of result.reports){const option=document.createElement('option');option.value=row.report_id;option.textContent=row.type+' · '+row.title+' · '+row.state;select.append(option);}
  }
  async function open(type){
    kind=type;const d=drafts[kind];el('settings-dialog').close();el('report-heading').textContent=kind==='bug'?'Report a glitch':'Request a feature';el('report-description-label').firstChild.textContent=kind==='bug'?'What happened?':'What would you like, and why?';el('report-expected-label').hidden=kind!=='bug';el('report-expected').required=kind==='bug';el('report-title').value=d.title||'';el('report-description').value=d.description||'';el('report-expected').value=d.expected||'';el('report-diagnostics').checked=d.include??(kind==='bug');el('report-window').value=d.hours||'24';el('report-window-label').hidden=!el('report-diagnostics').checked;el('report-error').textContent='';compose();el('report-dialog').showModal();el('report-title').focus();
    try{sessionToken=(await api('/api/session')).token;await savedReports();}catch{el('report-error').textContent='Could not load saved reports. Your text is kept here.';}
  }
  function showPreview(result,status={state:'draft'}){
    preview=result;kind=result.type;delivery=status;connection=null;
    const form=result.form||{title:result.title,description:result.body,expected:'',include_diagnostics:false,hours:24};
    if(form){el('report-title').value=form.title;el('report-description').value=form.description;el('report-expected').value=form.expected;el('report-diagnostics').checked=form.include_diagnostics;el('report-window').value=String(form.hours);saveFields();}
    el('report-heading').textContent=kind==='bug'?'Report a glitch':'Request a feature';
    el('report-description-label').firstChild.textContent=kind==='bug'?'What happened?':'What would you like, and why?';
    el('report-expected-label').hidden=kind!=='bug';el('report-expected').required=kind==='bug';
    el('report-window-label').hidden=!el('report-diagnostics').checked;
    el('report-preview-title').textContent=result.github_title||result.title;
    el('report-preview-labels').textContent=result.labels.join(' · ');
    el('report-preview-body').textContent=result.issue_body||result.body;
    const files=el('report-preview-files');files.replaceChildren();
    if(!result.files.length){const note=document.createElement('p');note.textContent='No diagnostics included.';files.append(note);}
    // The issue body already includes the exact diagnostic blocks; these are a
    // second convenient inspection view, not separate uploaded attachments.
    for(const file of result.files){const details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent=file.name+' · '+bytes(file.bytes);pre.textContent=file.content;details.append(summary,pre);files.append(details);}
    el('report-compose').hidden=true;el('report-preview').hidden=false;el('report-back').hidden=false;el('report-review').hidden=true;el('report-send').hidden=false;updateDelivery();
  }
  el('report-setup').hidden=!window.webkit?.messageHandlers?.repoHub;
  el('report-setup').onclick=()=>{if(typeof nativeAction==='function')nativeAction('connectGitHub');};
  el('report-bug').onclick=()=>open('bug');el('report-feature').onclick=()=>open('feature');
  el('report-close').onclick=close;el('report-cancel').onclick=close;
  el('report-dialog').addEventListener('cancel',event=>{if(busy)event.preventDefault();saveFields();});
  el('report-diagnostics').onchange=()=>{el('report-window-label').hidden=!el('report-diagnostics').checked;};
  el('report-back').onclick=compose;
  el('report-connect').onclick=async()=>{if(busy)return;busy=true;busyFields(true);try{await refreshConnection();}catch{connection=null;el('report-error').textContent='Could not check GitHub. Your draft is kept.';}finally{busy=false;busyFields(false);}};
  el('report-saved').onchange=async()=>{
    const id=el('report-saved').value;if(!id||busy)return;busy=true;busyFields(true);
    try{const result=await api('/api/reports/draft',{report_id:id});showPreview(result.draft,result.delivery);await refreshConnection();}
    catch{el('report-error').textContent='Could not reopen this report. The saved draft has not been removed.';}
    finally{busy=false;busyFields(false);}
  };
  el('report-form').onsubmit=async event=>{
    event.preventDefault();if(busy)return;busy=true;saveFields();busyFields(true);el('report-review').textContent='Preparing preview…';el('report-error').textContent='';
    try{
      sessionToken=(await api('/api/session')).token;
      const result=await api('/api/reports/preview',{type:kind,title:drafts[kind].title,description:drafts[kind].description,expected:kind==='bug'?drafts[kind].expected:'',include_diagnostics:drafts[kind].include,hours:Number(drafts[kind].hours)});
      showPreview(result);await refreshConnection();
    }catch(error){el('report-error').textContent='Could not prepare or connect the preview. Your text and any saved draft are kept. '+error.message;}
    finally{busy=false;busyFields(false);el('report-review').textContent='Preview report';}
  };
  el('report-send').onclick=async()=>{
    if(busy||!preview||!connection?.ready||delivery.state==='sent')return;
    busy=true;delivery={state:'sending'};busyFields(true);el('report-error').textContent='';
    try{
      sessionToken=(await api('/api/session')).token;
      delivery=await api('/api/reports/send',{report_id:preview.report_id,preview_digest:preview.preview_digest,account:connection.account,confirm:true});
      if(delivery.state==='failed')el('report-error').textContent='GitHub did not accept the report. Check your connection and permissions, then retry. Your draft is kept.';
      if(delivery.state==='uncertain')el('report-error').textContent='GitHub may have received this report. Check delivery later; this will not post another copy.';
    }catch{
      // A lost helper response may hide a successful send. Never recreate the
      // preview: reopen the same durable report and reconcile its receipt.
      delivery={state:'uncertain'};el('report-error').textContent='Delivery could not be confirmed. Your draft is kept. Check delivery or reopen this saved report.';
    }finally{busy=false;busyFields(false);}
  };
})();

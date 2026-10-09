/* Local draft preview; no external submission or private-key access. */
(()=>{
  const el=id=>document.getElementById(id);
  const drafts={bug:{},feature:{}};
  let kind='bug',busy=false;
  function saveFields(){drafts[kind]={title:el('report-title').value,description:el('report-description').value,expected:el('report-expected').value,include:el('report-diagnostics').checked,hours:el('report-window').value};}
  function compose(){el('report-compose').hidden=false;el('report-preview').hidden=true;el('report-back').hidden=true;el('report-send').hidden=true;el('report-review').hidden=false;}
  function busyFields(value){for(const field of document.querySelectorAll('#report-compose input, #report-compose textarea, #report-compose select'))field.disabled=value;el('report-close').disabled=value;el('report-cancel').disabled=value;}
  function close(){if(busy)return;saveFields();el('report-dialog').close();}
  function open(type){kind=type;const d=drafts[kind];el('settings-dialog').close();el('report-heading').textContent=kind==='bug'?'Report a glitch':'Request a feature';el('report-description-label').firstChild.textContent=kind==='bug'?'What happened?':'What would you like, and why?';el('report-expected-label').hidden=kind!=='bug';el('report-expected').required=kind==='bug';el('report-title').value=d.title||'';el('report-description').value=d.description||'';el('report-expected').value=d.expected||'';el('report-diagnostics').checked=d.include??(kind==='bug');el('report-window').value=d.hours||'24';el('report-window-label').hidden=!el('report-diagnostics').checked;el('report-error').textContent='';compose();el('report-dialog').showModal();el('report-title').focus();}
  el('report-bug').onclick=()=>open('bug');el('report-feature').onclick=()=>open('feature');
  el('report-close').onclick=close;el('report-cancel').onclick=close;
  el('report-dialog').addEventListener('cancel',event=>{if(busy)event.preventDefault();saveFields();});
  el('report-diagnostics').onchange=()=>{el('report-window-label').hidden=!el('report-diagnostics').checked;};
  el('report-back').onclick=compose;
  el('report-form').onsubmit=async event=>{
    event.preventDefault();if(busy)return;busy=true;saveFields();busyFields(true);el('report-review').disabled=true;el('report-review').textContent='Preparing preview…';el('report-error').textContent='';
    try{
      sessionToken=(await api('/api/session')).token;
      const result=await api('/api/reports/preview',{type:kind,title:drafts[kind].title,description:drafts[kind].description,expected:kind==='bug'?drafts[kind].expected:'',include_diagnostics:drafts[kind].include,hours:Number(drafts[kind].hours)});
      el('report-preview-title').textContent=result.title;el('report-preview-labels').textContent=result.labels.join(' · ');el('report-preview-body').textContent=result.body;
      const files=el('report-preview-files');files.replaceChildren();
      if(!result.files.length){const note=document.createElement('p');note.textContent='No diagnostics attached.';files.append(note);}
      for(const file of result.files){const details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent=file.name+' · '+bytes(file.bytes);pre.textContent=file.content;details.append(summary,pre);files.append(details);}
      el('report-compose').hidden=true;el('report-preview').hidden=false;el('report-back').hidden=false;el('report-review').hidden=true;el('report-send').hidden=false;
    }catch(error){el('report-error').textContent='Could not prepare the preview. Your text is kept here. '+error.message;}
    finally{busy=false;busyFields(false);el('report-review').disabled=false;el('report-review').textContent='Preview report';}
  };
})();

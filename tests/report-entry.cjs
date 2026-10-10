/* Exercise the actual shared report controller from both shipped entry points. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
async function surface(file){
  const html=fs.readFileSync(path.join(root,'web',file),'utf8');
  const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
  assert.equal(new Set(ids).size,ids.length,'unique IDs');
  for(const id of ['report-bug','report-feature','report-dialog','report-form','report-send'])assert(ids.includes(id),`${file}: ${id} reachable`);
  assert(html.includes('/report.css'));
  assert(html.indexOf(file==='menu.html'?'/menu.js':'/app.js')<html.indexOf('/report-preview.js'),'host initializes before report controller');
  class Element{
    constructor(){this.value='';this.checked=false;this.hidden=false;this.disabled=false;this.textContent='';this.children=[];this.firstChild={textContent:''};this.open=false;}
    close(){this.open=false;}showModal(){this.open=true;}focus(){}addEventListener(){}
    append(...items){this.children.push(...items);}replaceChildren(){this.children=[];}
  }
  const nodes=new Map(ids.map(id=>[id,new Element()]));
  const get=id=>{assert(nodes.has(id),`${file}: controller requests absent ${id}`);return nodes.get(id);};
  const calls=[];let accepted=false;
  async function api(url,payload){
    calls.push({url,payload});
    if(url==='/api/session')return {token:'synthetic-session'};
    if(url==='/api/reports/list')return {reports:[]};
    if(url==='/api/reports/connection')return {ready:true,account:'synthetic-account'};
    if(url==='/api/reports/preview')return {type:payload.type,title:payload.title,github_title:payload.title,issue_body:payload.description,report_id:'a'.repeat(24),preview_digest:'b'.repeat(64),labels:[payload.type],files:[],form:{...payload}};
    if(url==='/api/reports/send'){accepted=true;return {state:'sent',issue_url:'https://github.com/yogoldy/RepoHub/issues/1'};}
    throw new Error('unexpected '+url);
  }
  const nativeCalls=[];const context={window:{webkit:{messageHandlers:{repoHub:{}}}},nativeAction:action=>nativeCalls.push(action),document:{getElementById:get,querySelectorAll:()=>[...nodes.values()],createElement:()=>new Element()},api,bytes:String,sessionToken:''};
  vm.runInNewContext(fs.readFileSync(path.join(root,'web/report-preview.js'),'utf8'),context);
  assert(!get('report-setup').hidden);get('report-setup').onclick();assert.equal(nativeCalls[0],'connectGitHub');
  await get('report-bug').onclick();
  assert(get('report-dialog').open);assert.equal(get('report-heading').textContent,'Report a glitch');assert(get('report-expected').required);assert(get('report-diagnostics').checked);
  get('report-title').value='Synthetic bug';get('report-description').value='Synthetic glitch';get('report-expected').value='Expected behavior';
  await get('report-form').onsubmit({preventDefault(){}});assert(!get('report-preview').hidden);assert(!accepted);
  const bug=calls.find(x=>x.url==='/api/reports/preview').payload;assert.equal(bug.type,'bug');assert.equal(bug.expected,'Expected behavior');assert.equal(bug.include_diagnostics,true);
  get('report-back').onclick();
  get('report-cancel').onclick();await get('report-feature').onclick();assert.equal(get('report-heading').textContent,'Request a feature');assert(!get('report-diagnostics').checked);assert(get('report-expected-label').hidden);
  get('report-title').value='Synthetic feature';get('report-description').value='Synthetic idea';
  get('report-cancel').onclick();await get('report-bug').onclick();assert.equal(get('report-title').value,'Synthetic bug','independent bug draft retained');
  get('report-cancel').onclick();await get('report-feature').onclick();assert.equal(get('report-title').value,'Synthetic feature');
  await get('report-form').onsubmit({preventDefault(){}});
  assert(!get('report-preview').hidden);assert(!get('report-send').disabled);assert(!accepted,'preview never sends');
  const preview=calls.filter(x=>x.url==='/api/reports/preview').at(-1).payload;assert.equal(preview.type,'feature');assert.equal(preview.include_diagnostics,false);
  await get('report-send').onclick();assert(accepted);assert.equal(get('report-delivery-status').textContent,'Sent · Confirmed by GitHub');assert(get('report-send').disabled);
  const send=calls.find(x=>x.url==='/api/reports/send').payload;assert.equal(send.confirm,true);assert.equal(send.preview_digest,'b'.repeat(64));assert.equal(send.account,'synthetic-account');
  await get('report-send').onclick();assert.equal(calls.filter(x=>x.url==='/api/reports/send').length,1,'no repeated sent issue');
}
(async()=>{await surface('index.html');await surface('menu.html');console.log('Main and menu report entry/preview/explicit-send checks passed');})().catch(e=>{console.error(e);process.exitCode=1;});

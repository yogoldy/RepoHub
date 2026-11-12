// Execute the shipped action controller against isolated status and request doubles.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/menu.js', 'utf8');
const nodes = new Map();
const rows = [{id:'first',name:'First',access:{}}, {id:'second',name:'Second',access:{}}];
const inputs = [];
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {disabled:false, textContent:'', lastElementChild:{},
    parentElement:null, append(child){child.parentElement=this;}, insertBefore(child){child.parentElement=this;},
    addEventListener(){}, close(){this.open=false;}, showModal(){this.open=true;},
    querySelectorAll(selector){return inputs.filter(input=>selector.includes(':checked') ? input.checked : !input.disabled);}});
  return nodes.get(id);
}
node('repo-expansion').parentElement=node('main');
Object.defineProperty(node('action-repos'),'innerHTML',{set(markup){
  inputs.splice(0,inputs.length,...[...markup.matchAll(/value="([^"]+)"\s*(disabled)?/g)].map(m=>({value:m[1],disabled:!!m[2],checked:false})));
}});
let reject = false;
const calls=[];
const context=vm.createContext({$:s=>node(s.slice(1)),selectedId:'first',menuState:{repos:rows,backup:{}},
  escape:s=>s,RepoStatus:{present:()=>({label:'Backed up'})},sessionToken:'old',
  setTimeout(){},load(){}, api:async(path,payload)=>{
    calls.push({path,payload});
    if(path==='/api/workspaces')return {revision:'current',configuration:{workspaces:rows.map(r=>({...r,active:true}))}};
    if(path==='/api/session')return {token:'fresh'};
    assert.match(path,/^\/api\/actions\/(scan|backup)$/);
    if(reject)throw Error('Selection changed');
    return {accepted:true};
  }});
vm.runInContext(source.slice(source.indexOf('// Capture the controls once:'),source.indexOf("$('#open-backups').onclick")),context);
(async()=>{
  await node('rescan').onclick();
  assert.equal(calls.at(-1).path,'/api/actions/scan');
  assert.equal(JSON.stringify(calls.at(-1).payload),JSON.stringify({repo_ids:['first'],revision:'current'}));
  await node('backup').onclick();
  assert.equal(calls.at(-1).path,'/api/actions/backup');
  context.selectedId=null;
  const prior=calls.filter(c=>c.path.startsWith('/api/actions/')).length;
  await node('rescan').onclick();
  assert.equal(node('action-dialog').open,true);
  assert.equal(inputs.filter(i=>i.checked).length,0);
  assert.equal(node('action-submit').disabled,true);
  assert.equal(calls.filter(c=>c.path.startsWith('/api/actions/')).length,prior);
  inputs[1].checked=true;
  node('action-repos').onchange();
  await node('action-form').onsubmit({preventDefault(){}});
  await new Promise(r=>setImmediate(r));
  assert.equal(JSON.stringify(calls.at(-1).payload.repo_ids),'["second"]');
  context.selectedId='first'; reject=true;
  await node('rescan').onclick();
  assert.match(node('notice').textContent,/Selection changed/);
  assert.equal(node('rescan').disabled,false);
  console.log('Actual action controller: explicit single scope, empty overview selection, chosen subset and rejection passed');
})().catch(e=>{console.error(e);process.exitCode=1;});

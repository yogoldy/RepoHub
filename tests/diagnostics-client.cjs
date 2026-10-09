const assert=require('node:assert/strict');
const {create}=require('../web/diagnostics-client.js');
(async()=>{
  let now=0,calls=[],fail=false;
  const fetcher=async(url,options={})=>{calls.push({url,options});if(fail)throw new Error('unreachable');return {ok:true,json:async()=>({token:'test-current-token'})};};
  const client=create('menu',{native:true,fetcher,clock:()=>now,clientId:'a'.repeat(24)});
  const status={diagnostic_observation_id:'b'.repeat(24)},rows=[{repo_id:'known',phase:'changed',display_label:'Finder metadata changed',ready:false}];
  assert.equal(await client.observe({},rows),false);assert.equal(calls.length,0);
  assert.equal(await client.observe(status,rows),true);assert.equal(calls.length,2);
  const sent=JSON.parse(calls[1].options.body);
  assert.equal(sent.surface,'menu');assert.equal(sent.native,true);assert.equal(sent.rows[0].display_label,'Finder metadata changed');
  assert.equal(calls[1].options.headers['X-RepoHub-Token'],'test-current-token');
  assert.equal(await client.observe(status,rows),false);assert.equal(calls.length,2);
  now=60000;assert.equal(await client.observe(status,rows),true);
  rows[0].display_label='Files changed';assert.equal(await client.observe(status,rows),true);
  fail=true;rows[0].display_label='Git data changed';assert.equal(await client.observe(status,rows),false);
  fail=false;assert.equal(await client.observe(status,rows),true);
  console.log('Diagnostic delivery checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});

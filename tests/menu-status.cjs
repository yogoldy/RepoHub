const assert=require('node:assert/strict');
const {view}=require('../web/repo-status.js');
const good={id:'Example',name:'Example',health:{fresh:true},needs_backup:false,last_backup:{archive:'/current',sha256:'abc'},verification:{state:'matched',archive:'/current'},cloud:{state:'uploaded',archive:'/current'}};
let count=0;
function check(repo,phase,ready=false,backup={}){const value=view(repo,backup);assert.equal(value.phase,phase);assert.equal(value.ready,ready);count++;return value;}
check(good,'ready',true);
check({...good,health:{fresh:false}},'stale');
check({...good,health:undefined},'stale');
check({...good,needs_backup:true},'changed');
check({...good,needs_backup:undefined},'unknown');
check({...good,error:'copy error'},'error');
check(good,'error',false,{errors:[{repo:'Example',error:'index publication failed'}]});
check(good,'copying',false,{running:true,current_repo:'Example'});
check(good,'ready',true,{running:true,current_repo:'Other'});
check({...good,verification:{state:'checking'}},'verifying');
check({...good,verification:{state:'matched',archive:'/old'}},'verifying');
check({...good,cloud:{state:'uploaded',archive:'/old'}},'unknown');
check({...good,last_backup:undefined},'verifying');
check({...good,last_backup:{archive:'/current'}},'unknown');
check({...good,cloud:{state:'unknown'}},'unknown');
check({...good,cloud:{state:'error',detail:'iCloud issue'}},'error');
for(const percent of [null,NaN,Infinity,-1,101,'50',true]){const value=check({...good,cloud:{state:'uploading',percent,error_code:4355}},'uploading');assert.equal(value.percent,null);}
for(const percent of [0,55.4,100]){const value=check({...good,cloud:{state:'uploading',percent}},'uploading');assert.equal(value.percent,percent);}
check({...good,cloud:{state:'pending',percent:100}},'pending');
check({...good,needs_backup:true,cloud:{state:'uploading',percent:42}},'changed');
console.log(count+' menu status checks passed');

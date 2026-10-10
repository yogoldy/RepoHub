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
function changed(counts,archive='/current'){
  return {...good,needs_backup:true,verification:{state:'different',archive,changes:{counts}}};
}
assert.equal(check(changed({finder_metadata:2,git_data:0,repo_files:0}),'changed').label,'Finder metadata changed');
assert.match(view(changed({finder_metadata:2,git_data:0,repo_files:0})).detail,/repo files still match/);
assert.equal(check(changed({finder_metadata:0,git_data:1,repo_files:0}),'changed').label,'Git data changed');
assert.equal(check(changed({finder_metadata:1,git_data:1,repo_files:0}),'changed').label,'Finder / Git data changed');
assert.equal(check(changed({finder_metadata:1,git_data:1,repo_files:2}),'changed').label,'Files changed');
assert.doesNotMatch(view(changed({finder_metadata:1,git_data:1,repo_files:2})).detail,/repo files still match/);
assert.equal(check(changed({finder_metadata:1,git_data:0,repo_files:0},'/old'),'changed').label,'Backup needs updating');
assert.equal(check({...good,needs_backup:true,verification:{state:'checking'}},'verifying').label,'Checking for changes');
const finderIgnored={...good,verification:{state:'different',archive:'/current',backup_required:false,ignored_finder_only:true,changes:{counts:{finder_metadata:2,git_data:0,repo_files:0}}}};
assert.equal(check(finderIgnored,'background').label,'Project files match');
assert.match(view(finderIgnored).detail,/Only .DS_Store differs/);
check({...finderIgnored,health:{fresh:false}},'stale');
check({...finderIgnored,verification:{...finderIgnored.verification,archive:'/old'}},'verifying');
check({...finderIgnored,last_backup:{archive:'/current'}},'verifying');
check({...finderIgnored,verification:{...finderIgnored.verification,backup_required:true}},'verifying');
check({...finderIgnored,needs_backup:true},'changed');
check({...finderIgnored,cloud:{state:'uploaded',archive:'/old'}},'unknown');
check({...finderIgnored,cloud:{state:'uploading',archive:'/current',percent:49}},'uploading');
check({...finderIgnored,cloud:{state:'pending',archive:'/current'}},'pending');
check({...finderIgnored,cloud:{state:'error',archive:'/current'}},'error');
check(finderIgnored,'copying',false,{running:true,current_repo:'Example'});
console.log(count+' menu status checks passed');

const changing={...good,needs_backup:true,verification:{state:'changing'}};
assert.equal(check(changing,'verifying').label,'Files changing');
assert.match(view(changing).detail,/next scan/);
check({...changing,error:'real error'},'error');
check({...changing,cloud:{state:'error'}},'error');

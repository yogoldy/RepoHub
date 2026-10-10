/* Observes rendered labels. Delivery failure must never block rendering or backups. */
(function(root){
  function create(surface,{native=false,fetcher=root.fetch.bind(root),clock=Date.now,clientId}={}){
    if(!clientId){const bytes=new Uint8Array(12);root.crypto.getRandomValues(bytes);clientId=[...bytes].map(b=>b.toString(16).padStart(2,'0')).join('');}
    let last='',lastAt=0,pending=false,deferred=null;
    async function observe(status,rows,clientFreshness="current"){
      if(!status?.diagnostic_observation_id)return false;
      const body={surface,native,client_id:clientId,observation_id:status.diagnostic_observation_id,policy_version:root.RepoStatus?.version||'change-evidence-1',client_freshness:clientFreshness,rows};
      const signature=JSON.stringify(body),now=clock();
      if(clientFreshness!=='current')deferred=signature;
      if(pending)return false;
      if(signature===last&&now-lastAt<60000&&!deferred)return false;
      pending=true;
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),3000);
      try{
        const session=await fetcher('/api/session',{signal:controller.signal});
        if(!session.ok)return false;
        const token=(await session.json()).token;
        const post=body=>fetcher('/api/diagnostics/presentation',{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json','X-RepoHub-Token':token},body});
        // Keep only the latest unavailable frame. Flush after reconnect if its
        // original observation is still retained; an expired observation is a gap.
        if(deferred){
          const queued=deferred,response=await post(queued);
          if((response.ok||response.status===409)&&deferred===queued)deferred=null;
          if(queued===signature&&response.ok){last=signature;lastAt=now;return true;}
        }
        const response=await fetcher('/api/diagnostics/presentation',{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json','X-RepoHub-Token':token},body:signature});
        if(!response.ok)return false;
        last=signature;lastAt=now;return true;
      }catch(_){return false;}finally{pending=false;clearTimeout(timer);}
    }
    return {observe};
  }
  function displayState(status,reason='current'){
    if(reason==='current')return status;
    return {...status,repos:(status.repos||[]).map(repo=>({...repo,health:{fresh:false,reasons:['Local status unavailable · '+reason.replaceAll('_',' ')]}}))};
  }
  const api={create,displayState};if(typeof module==='object'&&module.exports)module.exports=api;else root.RepoDiagnostics=api;
})(typeof globalThis==='object'?globalThis:this);

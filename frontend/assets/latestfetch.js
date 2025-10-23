<script>
window.LatestFetch=(function(){
  const ctrls=new Map();
  let seq=0;

  function keyOf(input){ return typeof input==="string" ? input : input.url; }

  async function latestFetch(input, init={}, group){
    const k = group || keyOf(input);
    if(ctrls.has(k)){ try{ ctrls.get(k).abort(); }catch{} }
    const controller=new AbortController();
    ctrls.set(k, controller);
    const token=++seq;

    const opts={...init, signal: controller.signal};
    const res = await fetch(input, opts);
    if(ctrls.get(k)!==controller) throw new Error("stale");
    ctrls.delete(k);
    res.__latestToken=token;
    return res;
  }

  function active(group){ return ctrls.has(group); }
  function cancel(group){ if(ctrls.has(group)){ ctrls.get(group).abort(); ctrls.delete(group); } }

  return { latestFetch, active, cancel };
})();
</script>

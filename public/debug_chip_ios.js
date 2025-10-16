// === debug_chip_ios.js ===
// Debug long-press sui chip per iOS / tablet
// Mostra eventi touch/drag/click su chip e logga nel terminale e in console.

(function(){
  console.log('[debug_chip_ios] attivato');

  const MOVE_THR = 10;
  const isCoarse = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
  const isiOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || (isCoarse && /Macintosh/.test(navigator.userAgent));

  function logTerm(msg){
    console.log(msg);
    const t = document.getElementById('terminal');
    if (!t) return;
    const line = document.createElement('div');
    line.className = 'ln ln-cell';
    line.textContent = `[debug] ${msg}`;
    t.appendChild(line);
    t.scrollTop = t.scrollHeight;
  }

  function attachDebugToChip(chip, td){
    if (chip.__dbgBound) return;
    chip.__dbgBound = true;

    let lpTimer = null;
    let startX = 0, startY = 0;

    function cancelLP(){ if(lpTimer){ clearTimeout(lpTimer); lpTimer = null; } }

    chip.addEventListener('touchstart', (e)=>{
      const t = e.touches && e.touches[0];
      if (!t) return;
      startX = t.clientX; startY = t.clientY;
      cancelLP();
      lpTimer = setTimeout(()=>{
        const r = chip.getBoundingClientRect();
        const cx = t.clientX || (r.left + r.width/2);
        const cy = t.clientY || (r.top  + r.height/2);
        logTerm(`LONGPRESS → openCtx (${Math.round(cx)},${Math.round(cy)})`);
        try { openCtxForCell(td, cx, cy); } catch(err){ logTerm('openCtx ERR: '+err.message); }
      }, 500);
      logTerm('touchstart');
    }, {passive:false});

    chip.addEventListener('touchmove', (e)=>{
      const t = e.touches && e.touches[0];
      if(!t) return;
      const dx = Math.abs(t.clientX - startX);
      const dy = Math.abs(t.clientY - startY);
      if(dx>MOVE_THR || dy>MOVE_THR){ cancelLP(); }
      logTerm(`touchmove dx=${dx} dy=${dy}`);
    }, {passive:false});

    chip.addEventListener('touchend', ()=>{
      cancelLP();
      logTerm('touchend');
    }, {passive:false});

    chip.addEventListener('touchcancel', ()=>{
      cancelLP();
      logTerm('touchcancel');
    }, {passive:false});

    chip.addEventListener('dragstart', ()=> logTerm('dragstart'));
    chip.addEventListener('click', ()=> logTerm('click'));
    chip.addEventListener('contextmenu', (e)=>{ e.preventDefault(); logTerm('contextmenu'); });
  }

  function bindAllChips(){
    const chips = document.querySelectorAll('.chip');
    chips.forEach(chip=>{
      const td = chip.closest('td.cell');
      if(td) attachDebugToChip(chip, td);
    });
    logTerm(`[debug_chip_ios] Bound ${chips.length} chip`);
  }

  // Avvia debug una volta caricata la pagina
  window.addEventListener('load', ()=>{
    bindAllChips();
    // Rilega se vengono generati nuovi chip dinamicamente
    const obs = new MutationObserver(()=> bindAllChips());
    obs.observe(document.body, {childList:true, subtree:true});
  });

})();

// === safe_debug_chip_ios.js ===
// Debug long-press sui chip su iOS/tablet, senza MAI bloccare l'app.

(function(){
  // Non rompere mai se qualcosa va storto
  function safe(fn){ try { fn(); } catch(e){ console && console.warn && console.warn('[debug] err:', e); } }

  function logTerm(msg){
    safe(()=>console.log('[debug]', msg));
    const t = document.getElementById('terminal');
    if (!t) return;
    const line = document.createElement('div');
    line.className = 'ln ln-cell';
    line.textContent = `[debug] ${msg}`;
    t.appendChild(line);
    t.scrollTop = t.scrollHeight;
  }

  function attachDebugToChip(chip){
    if (!chip || chip.__dbgBound) return;
    chip.__dbgBound = true;

    let lpTimer = null;
    let startX = 0, startY = 0;
    const MOVE_THR = 10;

    const cancelLP = ()=>{ if(lpTimer){ clearTimeout(lpTimer); lpTimer = null; } };

    chip.addEventListener('touchstart', (e)=>{
      safe(()=>{
        const t = (e.touches && e.touches[0]) || null;
        if (!t) return;
        startX = t.clientX; startY = t.clientY;
        cancelLP();
        lpTimer = setTimeout(()=>{
          const r = chip.getBoundingClientRect();
          const cx = t.clientX || (r.left + r.width/2);
          const cy = t.clientY || (r.top  + r.height/2);
          logTerm(`LONGPRESS visto su chip @${Math.round(cx)},${Math.round(cy)}`);

          // Chiama openCtxForCell SOLO se esiste, altrimenti logga e basta
          const td = chip.closest && chip.closest('td.cell');
          if (typeof window.openCtxForCell === 'function' && td){
            safe(()=> window.openCtxForCell(td, cx, cy));
          } else if (typeof window.showCtx === 'function'){
            // fallback: mostra solo il menu (senza selezione cella)
            safe(()=> window.showCtx(cx, cy));
          } else {
            logTerm('Nota: openCtxForCell/showCtx non sono disponibili.');
          }
        }, 500);
        logTerm('touchstart');
      });
    }, {passive:true}); // solo debug: non blocchiamo lo scroll

    chip.addEventListener('touchmove', (e)=>{
      safe(()=>{
        const t = (e.touches && e.touches[0]) || null;
        if(!t) return;
        const dx = Math.abs(t.clientX - startX);
        const dy = Math.abs(t.clientY - startY);
        if (dx > MOVE_THR || dy > MOVE_THR) cancelLP();
        logTerm(`touchmove dx=${dx} dy=${dy}`);
      });
    }, {passive:true});

    chip.addEventListener('touchend', ()=> safe(()=>{
      cancelLP();
      logTerm('touchend');
    }));

    chip.addEventListener('touchcancel', ()=> safe(()=>{
      cancelLP();
      logTerm('touchcancel');
    }));

    chip.addEventListener('dragstart', ()=> safe(()=> logTerm('dragstart')));
    chip.addEventListener('click', ()=> safe(()=> logTerm('click')));
    chip.addEventListener('contextmenu', (e)=> safe(()=>{
      e.preventDefault(); // non richiesto ma evita menu nativo desktop
      logTerm('contextmenu');
    }));
  }

  function bindAllChips(){
    safe(()=>{
      const chips = document.querySelectorAll('.chip');
      chips.forEach(chip => attachDebugToChip(chip));
      logTerm(`Bound ${chips.length} chip`);
    });
  }

  // Avvia debug quando il DOM è pronto (prima non serve)
  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', bindAllChips);
  } else {
    bindAllChips();
  }

  // Rilega se cambiano i nodi (senza rompere se MutationObserver non c'è)
  safe(()=>{
    if (typeof MutationObserver === 'function'){
      const obs = new MutationObserver(()=> bindAllChips());
      obs.observe(document.documentElement || document.body, {childList:true, subtree:true});
    }
  });

  logTerm('safe_debug_chip_ios pronto');
})();

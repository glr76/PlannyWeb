// export_year.js
console.log('[export] script loaded');

(function(){
  function logOK(...a){ try{ console.log('[export]', ...a); }catch(_){} }
  function logWarn(...a){ try{ console.warn('[export]', ...a); }catch(_){} }

  // Scarica testo come file locale
  function downloadTextFile(filename, text) {
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    logOK('downloaded', filename);
  }

  // Leggi dal backend; preferisci l’helper dell’app se c’è
  async function getText(filename){
    if (typeof window.getTextFromServer === 'function') {
      return await window.getTextFromServer(filename);
    }
    const res = await fetch(`/api/files/public/${encodeURIComponent(filename)}`, {
      cache: 'no-store',
      headers: {
        'Cache-Control': 'no-cache, no-store, max-age=0, must-revalidate',
        'Pragma': 'no-cache'
      }
    });
    if (!res.ok) throw new Error('HTTP '+res.status);
    return res.text();
  }

  async function fetchAndDownload(filename){
    try{
      const txt = await getText(filename);
      downloadTextFile(filename, txt);
      return true;
    }catch(e){
      logWarn('missing or error', filename, e && e.message || e);
      return false;
    }
  }

  async function exportYearFiles(btn){
    const y  = (window.state && window.state.year) || new Date().getFullYear();
    const mm = String((new Date()).getMonth() + 1).padStart(2,'0');
    const selectionsName = `selections_${y}.txt`;
    const logName        = `planny_log_${y}_${mm}.txt`; // LOG MENSILE

    const original = btn?.textContent || 'Download';
    try{
      if (btn){ btn.disabled = true; btn.textContent = 'Esporto…'; }
      logOK('start', { y, selectionsName, logName });
      const okSel = await fetchAndDownload(selectionsName);
      const okLog = await fetchAndDownload(logName);
      if (!okSel && !okLog) logWarn('Nessun file esportato (entrambi mancanti?)');
    } finally {
      if (btn){ btn.disabled = false; btn.textContent = original; }
    }
  }

  // ✅ Collega il bottone ESISTENTE quando il DOM è pronto
  function wire(){
    const btn = document.getElementById('btn-export-year');
    if (!btn){ setTimeout(wire, 150); return; }
    if (!btn.__wired){
      btn.addEventListener('click', ()=> exportYearFiles(btn));
      btn.__wired = true;
      logOK('listener collegato al pulsante', btn);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire);
  } else {
    wire();
  }
})();

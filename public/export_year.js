// export_year.js
// Scarica selections_<ANNO>.txt e planny_log_<ANNO>.txt al click del bottone #btn-export-year

console.log('[export] script loaded');

(function(){
  function logOK(...a){ try{ console.log('[export]', ...a); }catch(_){} }
  function logWarn(...a){ try{ console.warn('[export]', ...a); }catch(_){} }
  function logErr(...a){ try{ console.error('[export]', ...a); }catch(_){} }

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

  // Legge testo dal backend; usa l’helper dell’app se disponibile
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
    const year = (window.state && window.state.year) || new Date().getFullYear();
    const selectionsName = `selections_${year}.txt`;
    const logName        = `planny_log_${year}.txt`;

    const originalLabel = btn?.textContent || 'Download';
    try{
      if (btn){ btn.disabled = true; btn.textContent = 'Esporto…'; }
      logOK('start', { year, selectionsName, logName });

      const okSel = await fetchAndDownload(selectionsName);
      const okLog = await fetchAndDownload(logName);

      if (!okSel && !okLog){
        logWarn('Nessun file esportato (entrambi mancanti?)');
      }else{
        logOK('Export completato');
      }
    }finally{
      if (btn){ btn.disabled = false; btn.textContent = originalLabel; }
    }
  }

  // Collega il click quando il DOM è pronto
  function wire(){
    const btn = document.getElementById('btn-export-year');
    if (!btn){
      logWarn('pulsante con id="btn-export-year" non trovato (ritento)…');
      setTimeout(wire, 150);
      return;
    }
    if (!btn.__wired){
      btn.addEventListener('click', ()=> exportYearFiles(btn));
      btn.__wired = true;
      logOK('listener collegato al pulsante', btn);
    }
  }

  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', wire);
  } else {
    wire();
  }
})();

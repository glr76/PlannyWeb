// export_year.js
// Aggiunge un pulsante "Esporta anno" alla top bar e scarica selections_<ANNO>.txt e planny_log_<ANNO>.txt

(function(){
  // --- util logging sicuro ---
  function safeLog(msg, type){
    try {
      if (typeof window.log === 'function') {
        window.log(msg, type || 'info');
      } else {
        (type === 'err' ? console.error : type === 'warn' ? console.warn : console.log)(msg);
      }
    } catch(_) {}
  }

  // --- helper: scarica testo come file locale ---
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
  }

  // --- helper: legge testo dal server, usa getTextFromServer se disponibile ---
  async function getText(filename){
    // Preferisci l'helper interno dell'app se esiste (gestisce cache-busting e header)
    if (typeof window.getTextFromServer === 'function') {
      return await window.getTextFromServer(filename);
    }
    // Fallback generico: /api/files/public/<filename>
    const res = await fetch(`/api/files/public/${encodeURIComponent(filename)}`, {
      cache: 'no-store',
      headers: {
        'Cache-Control': 'no-cache, no-store, max-age=0, must-revalidate',
        'Pragma': 'no-cache'
      }
    });
    if(!res.ok) throw new Error('HTTP '+res.status);
    return res.text();
  }

  async function fetchAndDownload(filename){
    try{
      const txt = await getText(filename);
      downloadTextFile(filename, txt);
      safeLog('Scaricato: ' + filename, 'ok');
      return true;
    }catch(e){
      safeLog('File non trovato o errore nel download: ' + filename + ' (' + (e && e.message || e) + ')', 'warn');
      return false;
    }
  }

  async function exportYearFiles(btn){
    const year = (window.state && window.state.year) || new Date().getFullYear();
    const selectionsName = `selections_${year}.txt`;
    const logName        = `planny_log_${year}.txt`;

    try{
      if (btn){ btn.disabled = true; btn.textContent = 'Esporto…'; }
      safeLog(`Avvio export anno ${year}…`, 'info');

      const okSel = await fetchAndDownload(selectionsName);
      const okLog = await fetchAndDownload(logName);

      if (!okSel && !okLog){
        safeLog('Nessun file esportato (entrambi mancanti?).', 'warn');
      } else {
        safeLog('Export completato.', 'ok');
      }
    } finally {
      if (btn){ btn.disabled = false; btn.textContent = 'Esporta anno'; }
    }
  }

  // --- inserisci il pulsante nella UI quando il DOM è pronto ---
  function injectButton(){
  // cerca se esiste già il pulsante
  const btn = document.getElementById('btn-export-year');
  if (!btn){
    console.warn('[export] nessun pulsante con id="btn-export-year" trovato');
    return;
  }

  // collega il click (una volta sola)
  if (!btn.__wired){
    btn.addEventListener('click', ()=> exportYearFiles(btn));
    btn.__wired = true;
    console.log('[export] listener collegato al pulsante', btn);
  } else {
    console.log('[export] listener già collegato');
  }
}

    // Evita doppioni
    if (document.getElementById('btn-export-year')) return;

    const btn = document.createElement('button');
    btn.id = 'btn-export-year';
    btn.className = 'btn mini';
    btn.type = 'button';
    btn.title = "Scarica selections e log dell'anno corrente";
    btn.textContent = 'Esporta anno';
    btn.addEventListener('click', ()=> exportYearFiles(btn));

    barRight.appendChild(btn);
    safeLog('Pulsante "Esporta anno" aggiunto alla toolbar.', 'ok');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectButton);
  } else {
    injectButton();
  }
})();

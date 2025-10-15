// export_year.js
// Scarica i log mensili: mese attuale + mese precedente (solo se esistono)

console.log('[export] script loaded');

(function () {
  // --- util log ---
  const logOK   = (...a) => { try { console.log('[export]', ...a); } catch(_) {} };
  const logWarn = (...a) => { try { console.warn('[export]', ...a); } catch(_) {} };

  // --- helper: scarica testo come file locale ---
  function downloadTextFile(filename, text) {
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    logOK('downloaded', filename);
  }

  // --- helper: leggi testo dal backend (preferisci helper app se presente) ---
  async function getText(filename) {
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
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.text();
  }

  // --- helper: mese precedente rispetto a "base" ---
  function prevMonthTuple(base = new Date()) {
    const d = new Date(base.getFullYear(), base.getMonth(), 1);
    d.setMonth(d.getMonth() - 1);
    return { y: d.getFullYear(), m: d.getMonth() + 1 }; // m: 1..12
  }

  // --- tenta download; se il file non esiste, silenzio (ritorna true/false) ---
  async function fetchAndMaybeDownload(name) {
    try {
      const txt = await getText(name);
      downloadTextFile(name, txt);
      return true;
    } catch (_) {
      // file assente o errore → ignora senza rumore
      logWarn('not found (skipped):', name);
      return false;
    }
  }

  // === ENTRYPOINT: scarica SOLO mese attuale + precedente (se esistono) ===
  async function exportYearFiles(btn) {
    const today = new Date();
    const curY  = (window.state && window.state.year) || today.getFullYear();
    const curM  = today.getMonth() + 1;
    const { y: prevY, m: prevM } = prevMonthTuple(today);
	await fetchAndMaybeDownload(`selections_${curY}.txt`);
    const files = [
      `planny_log_${curY}_${String(curM).padStart(2, '0')}.txt`,
      `planny_log_${prevY}_${String(prevM).padStart(2, '0')}.txt`,
    ];

    const original = btn?.textContent || 'Download';
    try {
      if (btn) { btn.disabled = true; btn.textContent = 'Scarico…'; }
      logOK('start', { current: files[0], previous: files[1] });

      const results = await Promise.allSettled(files.map(fetchAndMaybeDownload));
      const ok = results.filter(r => r.status === 'fulfilled' && r.value === true).length;

      // feedback nel Terminale interno (se disponibile)
      if (typeof window.log === 'function') {
        window.log(`Scaricati ${ok}/${files.length} log (attuale + precedente)`, 'cell');
      }
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = original; }
    }
  }

  // --- collega il bottone ESISTENTE (#btn-export-year) quando il DOM è pronto ---
  function wire() {
    const btn = document.getElementById('btn-export-year');
    if (!btn) { setTimeout(wire, 150); return; }
    if (!btn.__wired) {
      btn.addEventListener('click', () => exportYearFiles(btn));
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

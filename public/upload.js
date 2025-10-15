/* upload_public.js */
(function () {
  'use strict';

  // --- logger coerente col tuo terminale
  function log(msg, type) {
    try {
      (type === 'err' ? console.error : type === 'warn' ? console.warn : console.log)(msg);
      if (type === 'cell') return;
      var t = document.getElementById('terminal');
      if (!t) return;
      var ts = new Date().toLocaleTimeString();
      var line = document.createElement('div');
      line.className = 'ln ln-cell';
      line.textContent = '[' + ts + '] ' + msg;
      t.appendChild(line);
      t.scrollTop = t.scrollHeight;
    } catch (_) {}
  }

  // Usa guardedFetch se esiste, altrimenti fetch
  const _fetch = (typeof window.guardedFetch === 'function') ? window.guardedFetch : fetch;

  async function putBinaryToServer(filename, file, { timeoutMs = 20000 } = {}) {
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort('timeout'), timeoutMs);
    try {
      const res = await _fetch(`/api/files/public/${encodeURIComponent(filename)}`, {
        method: 'PUT',
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
        body: file,
        cache: 'no-store',
        signal: ctrl.signal
      });
      const body = await res.text().catch(() => '');
      if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}${body ? ' - ' + body : ''}`);
      // bust cache locale
      window.__fileVersion = window.__fileVersion || {};
      window.__fileVersion[filename] = Date.now();
      return true;
    } finally {
      clearTimeout(to);
    }
  }

  function ensureUI() {
    // Se l'HTML non ha ancora i controlli, li inseriamo prima del bottone Download
    let btnUpload = document.getElementById('btn-upload-file');
    let inputFile = document.getElementById('upload-input');

    const btnDownload = document.getElementById('btn-export-year');
    const barRight = document.querySelector('.bar-right');

    if (!btnUpload) {
      btnUpload = document.createElement('button');
      btnUpload.id = 'btn-upload-file';
      btnUpload.className = 'btn mini';
      btnUpload.title = 'Carica un file nella cartella public';
      btnUpload.textContent = 'Upload';
      // posizione: accanto al Download se possibile
      if (btnDownload && btnDownload.parentNode) {
        btnDownload.parentNode.insertBefore(btnUpload, btnDownload);
      } else if (barRight) {
        barRight.appendChild(btnUpload);
      } else {
        document.body.appendChild(btnUpload);
      }
    }

    if (!inputFile) {
      inputFile = document.createElement('input');
      inputFile.id = 'upload-input';
      inputFile.type = 'file';
      inputFile.style.display = 'none';
      // default: qualsiasi file; se vuoi limitare: inputFile.accept = '.txt,text/plain';
      btnUpload.parentNode.insertBefore(inputFile, btnUpload);
    }

    return { btnUpload, inputFile };
  }

  function hookUpload() {
    const { btnUpload, inputFile } = ensureUI();
    if (!btnUpload || !inputFile) return;

    btnUpload.addEventListener('click', () => inputFile.click());

    inputFile.addEventListener('change', async () => {
      try {
        const f = inputFile.files && inputFile.files[0];
        if (!f) return;

        // Coerenza con resto app: richiede permessi di scrittura
        if (window.__canWrite === false) {
          log('Permessi insufficienti: effettua il login come admin per caricare.', 'warn');
          inputFile.value = '';
          return;
        }

        // Nome destinazione (di default il nome originale)
        let dest = prompt('Nome file da salvare in /public:', f.name);
        if (dest == null || !dest.trim()) { inputFile.value = ''; return; }
        dest = dest.trim();

        log(`Caricamento in corso: ${dest} (${Math.round(f.size / 1024)} KB)`, 'info');
        await putBinaryToServer(dest, f);
        log('Upload completato: ' + dest, 'ok');

        // Aggiorna badge/status, se presente
        try {
          const status = document.getElementById('cloud-status');
          if (status) status.textContent = `Caricato: ${dest}`;
        } catch (_) { }
      } catch (err) {
        log('Upload fallito: ' + (err && err.message || err), 'err');
      } finally {
        // reset per permettere nuovo upload dello stesso file
        inputFile.value = '';
      }
    });
  }

  // boot
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hookUpload);
  } else {
    hookUpload();
  }
})();

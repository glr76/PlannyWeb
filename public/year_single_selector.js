(function () {
  // --- Logger compatto
  function tlog(msg, lvl) {
    try {
      var p = "[" + new Date().toLocaleTimeString() + "] " + (lvl || "info").toUpperCase() + ": ";
      console.log(p + msg);
    } catch (_) {}
  }

  // --- Aggiorna lo status nella cloud bar (se esiste)
  function updateCloudStatus(text) {
    var el = document.querySelector("#cloud-year-box #cloud-status");
    if (el) el.textContent = text;
  }

  // --- Forza il ridisegno del planner con i vari nomi storici
  function refreshUI() {
    var fns = [
      "renderCalendar",
      "refreshCalendar",
      "renderPlanner",
      "buildCalendar",
      "drawCalendar",
      "updateCalendarUI",
      "renderMonthly",
      "renderVisualPlanner",
      "refreshUI",
      "updateUI",
    ];
    for (var i = 0; i < fns.length; i++) {
      var fn = fns[i];
      if (typeof window[fn] === "function") {
        try {
          window[fn]();
          tlog("Ridisegno via " + fn, "ok");
          return;
        } catch (e) {
          tlog("Errore redraw " + fn + ": " + e, "error");
        }
      }
    }
    try {
      document.dispatchEvent(new CustomEvent("planner:reload", { detail: { reason: "single-year" } }));
      window.dispatchEvent(new CustomEvent("planner:year-changed", { detail: { year: window.state && window.state.year } }));
      tlog("Eventi planner dispatchati", "info");
    } catch (e) {
      tlog("Errore dispatch eventi: " + e, "warn");
    }
  }

  // --- Imposta anno nello stato + ricarica festività + refresh UI
  function applyYear(year) {
    window.state = window.state || {};
    var y = parseInt(year, 10) || new Date().getFullYear();
    window.state.year = y;
    tlog("Anno impostato: " + y, "ok");
    updateCloudStatus("Anno: " + y);

    try {
      if (typeof loadHolidaysFromLocalOrWeb === "function") {
        loadHolidaysFromLocalOrWeb();
      }
    } catch (e) {
      tlog("loadHolidaysFromLocalOrWeb(): " + e, "warn");
    }

    refreshUI();
  }

  // --- Popola il select anni se vuoto e allinea al valore in state.year
  function populateYears(sel) {
    var now = new Date().getFullYear();
    if (sel.options.length === 0) {
      var years = [now - 1, now, now + 1, now + 2];
      years.forEach(function (y) {
        var o = document.createElement("option");
        o.value = y;
        o.textContent = y;
        sel.appendChild(o);
      });
      sel.value = now;
    }
    if (window.state && window.state.year) {
      sel.value = String(window.state.year);
    }
    tlog("Select anno pronto (" + sel.value + ")", "info");
    applyYear(sel.value);
  }

  // --- Collega eventi al select e ai bottoni prev/next
  function wireControls(root, sel) {
    if (window.__singleYearWired) return; // evita doppi wiring
    window.__singleYearWired = true;

    populateYears(sel);

    // cambio da select
    sel.addEventListener("change", function () {
      applyYear(sel.value);
    });

    // bottoni prev/next se presenti
    var btnPrev = root.querySelector("#btn-cloud-prev");
    var btnNext = root.querySelector("#btn-cloud-next");

    if (btnPrev) {
      btnPrev.addEventListener("click", function () {
        var cur = parseInt(sel.value, 10) || new Date().getFullYear();
        var target = cur - 1;
        // se l'opzione non esiste, la aggiungo on-the-fly
        if (!Array.from(sel.options).some(function (o) { return parseInt(o.value, 10) === target; })) {
          var o = document.createElement("option");
          o.value = target;
          o.textContent = target;
          sel.insertBefore(o, sel.firstChild);
        }
        sel.value = target;
        applyYear(target);
      });
    }

    if (btnNext) {
      btnNext.addEventListener("click", function () {
        var cur = parseInt(sel.value, 10) || new Date().getFullYear();
        var target = cur + 1;
        if (!Array.from(sel.options).some(function (o) { return parseInt(o.value, 10) === target; })) {
          var o = document.createElement("option");
          o.value = target;
          o.textContent = target;
          sel.appendChild(o);
        }
        sel.value = target;
        applyYear(target);
      });
    }

    tlog("Agganciato a select#" + sel.id, "ok");
  }

  // --- Entry: cerca la cloud bar statica e collega il select
  function boot() {
    // Preferisci il selettore statico nella cloud bar, ma accetta anche #yearSingle
    var root = document.querySelector("#cloud-year-box") || document;
    var sel = root.querySelector("#cloud-year-select") || document.querySelector("#yearSingle");

    if (sel) {
      wireControls(root, sel);
      return;
    }

    // Se non c'è ancora nel DOM, osservo finché compare
    tlog("Select anno non presente al DOMContentLoaded: in attesa…", "warn");

    var timeoutId = setTimeout(function () {
      if (!window.__singleYearWired) tlog("Timeout attesa select anno (10s): nessun aggancio", "warn");
    }, 10000);

    var obs = new MutationObserver(function () {
      var r = document.querySelector("#cloud-year-box") || document;
      var s = (r && r.querySelector("#cloud-year-select")) || document.querySelector("#yearSingle");
      if (s) {
        try { obs.disconnect(); } catch (_) {}
        clearTimeout(timeoutId);
        wireControls(r, s);
      }
    });
    obs.observe(document.documentElement || document.body, { childList: true, subtree: true });
  }

  // --- Singola installazione
  if (!window.__singleYearInstalled) {
    window.__singleYearInstalled = true;
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", boot);
    } else {
      boot();
    }
  }
})();

(function(){
  function tlog(msg,lvl){ try{ var p='['+(new Date().toLocaleTimeString())+'] '+(lvl||'info').toUpperCase()+': '; console.log(p+msg);}catch(_){ } }

  function refreshUI(){
    var fns=['renderCalendar','refreshCalendar','renderPlanner','buildCalendar','drawCalendar','updateCalendarUI','renderMonthly','renderVisualPlanner','refreshUI','updateUI'];
    for (var i=0;i<fns.length;i++){
      var fn=fns[i];
      if(typeof window[fn]==='function'){
        try{ window[fn](); tlog('Ridisegno via '+fn,'ok'); return; }catch(e){ tlog('Errore redraw '+fn+': '+e,'error'); }
      }
    }
    try{
      document.dispatchEvent(new CustomEvent('planner:reload',{detail:{reason:'single-year'}}));
      window.dispatchEvent(new CustomEvent('planner:year-changed',{detail:{year:window.state && window.state.year}}));
      tlog('Eventi planner dispatchati','info');
    }catch(e){ tlog('Errore dispatch eventi: '+e,'warn'); }
  }

  function applyYear(year){
    window.state = window.state || {};
    window.state.year = parseInt(year,10) || new Date().getFullYear();
    tlog('Anno impostato: '+window.state.year,'ok');
    try{ if(typeof loadHolidaysFromLocalOrWeb==='function'){ loadHolidaysFromLocalOrWeb(); } }catch(e){}
    refreshUI();
  }

  function populateYears(sel){
    var now = new Date().getFullYear();
    // se già popolato dall’HTML, non tocco le option
    if (sel.options.length === 0){
      var years=[now-1, now, now+1, now+2];
      years.forEach(function(y){ var o=document.createElement('option'); o.value=y; o.textContent=y; sel.appendChild(o); });
      sel.value = now;
    }
    // se l’app ha già deciso l’anno (autoload), sincronizzo il select
    if (window.state && window.state.year){
      sel.value = String(window.state.year);
    }
    tlog('Select anno pronto ('+sel.value+')','info');
    applyYear(sel.value);
  }

  function wireSelect(sel){
    if (window.__singleYearWired) return; // evita doppi wiring
    window.__singleYearWired = true;
    populateYears(sel);
    sel.addEventListener('change', function(){ applyYear(sel.value); });
    tlog('Agganciato a select#yearSingle','ok');
  }

  function waitForSelect(){
    var sel = document.querySelector('#yearSingle');
    if (sel){ wireSelect(sel); return; }
    tlog('yearSingle non presente al DOMContentLoaded: in attesa…','warn');

    var timeoutId = setTimeout(function(){
      if (!window.__singleYearWired) tlog('Timeout attesa yearSingle (10s): nessun aggancio','warn');
    }, 10000);

    var obs = new MutationObserver(function(){
      var s = document.querySelector('#yearSingle');
      if (s){
        try{ obs.disconnect(); }catch(_){}
        clearTimeout(timeoutId);
        wireSelect(s);
      }
    });
    obs.observe(document.documentElement || document.body, { childList:true, subtree:true });
  }

  if(!window.__singleYearInstalled){
    window.__singleYearInstalled = true;
    if (document.readyState === 'loading'){
      document.addEventListener('DOMContentLoaded', waitForSelect);
    } else {
      waitForSelect();
    }
  }
})();

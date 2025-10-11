(function(){
  function getTerm(){ return document.getElementById('terminal'); }
  function tlog(msg, lvl){
    try{
      var prefix = '['+(new Date().toLocaleTimeString())+'] '+(lvl||'info').toUpperCase()+': ';
      var t = getTerm();
      if(t){ t.textContent += prefix + String(msg) + '\n'; t.scrollTop = t.scrollHeight; }
      if(typeof console !== 'undefined' && console.log){
        if(lvl === 'error' && console.error) console.error(prefix, msg);
        else if(lvl === 'warn' && console.warn) console.warn(prefix, msg);
        else console.log(prefix, msg);
      }
      if(typeof log === 'function'){ try{ log(String(msg), lvl||'info'); }catch(_){ } }
    }catch(_){}
  }

  function ensureBar(){
    var bar = document.getElementById('yearBarSingle');
    if(!bar){
      bar = document.createElement('div');
      bar.id = 'yearBarSingle';
      bar.style.cssText = [
        'display:flex','gap:10px','align-items:center','justify-content:flex-start',
        'position:sticky','top:0','z-index:50',
        'padding:10px 12px','margin:8px 0 12px',
        'background:linear-gradient(180deg,#f8fafc 0,#ffffff 100%)',
        'border:1px solid #e2e8f0','border-radius:14px',
        'box-shadow:0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(2,6,23,.06)'
      ].join(';');
      var host = document.querySelector('header, .toolbar, .topbar, body');
      host.insertBefore(bar, host.firstChild);
    }
    bar.innerHTML = '';
    var label = document.createElement('span');
    label.textContent = 'Anno';
    label.style.cssText = 'font-weight:600;color:#0f172a;letter-spacing:.2px';
    var selWrap = document.createElement('div');
    selWrap.style.cssText = [
      'display:flex','align-items:center','gap:8px',
      'padding:6px 10px','border:1px solid #cbd5e1','border-radius:10px',
      'background:#fff','box-shadow:inset 0 1px 0 rgba(255,255,255,.6)'
    ].join(';');
    var sel = document.createElement('select');
    sel.id = 'yearSingle';
    sel.style.cssText = [
      'appearance:none','-moz-appearance:none','-webkit-appearance:none',
      'border:none','outline:none','background:transparent',
      'font-weight:600','color:#0f172a','padding-right:14px','min-width:90px','cursor:pointer'
    ].join(';');
    var chevron = document.createElement('span');
    chevron.textContent = '▾';
    chevron.style.cssText = 'color:#475569;font-size:12px;';
    selWrap.appendChild(sel); selWrap.appendChild(chevron);
    var btn = document.createElement('button');
    btn.id = 'applySingleYear';
    btn.textContent = 'Carica';
    btn.style.cssText = [
      'padding:6px 12px','border:1px solid #334155',
      'border-radius:10px','background:#0f172a','color:#f8fafc',
      'font-weight:600','cursor:pointer','box-shadow:0 1px 2px rgba(0,0,0,.08)'
    ].join(';');
    btn.onmouseenter = function(){ btn.style.background = '#111827'; };
    btn.onmouseleave = function(){ btn.style.background = '#0f172a'; };
    bar.appendChild(label); bar.appendChild(selWrap); bar.appendChild(btn);
    return { bar:bar, select:sel, button:btn };
  }

  function refreshUI(){
    var fns=['renderCalendar','refreshCalendar','renderPlanner','buildCalendar','drawCalendar','updateCalendarUI','renderMonthly','renderVisualPlanner','refreshUI','updateUI'];
    var called=false; 
    for(var j=0;j<fns.length && !called;j++){
      var fn=fns[j]; 
      if(typeof window[fn]==='function'){
        try{ window[fn](); tlog('Ridisegno via '+fn,'ok'); called=true; }
        catch(e){ tlog('Errore redraw '+fn+': '+e,'error'); }
      }
    }
    if(!called){
      try{
        document.dispatchEvent(new CustomEvent('planner:reload',{detail:{reason:'single-year'}}));
        window.dispatchEvent(new CustomEvent('planner:year-changed',{detail:{year:window.state.year}}));
        tlog('Eventi planner dispatchati','info');
      }catch(e){ tlog('Errore dispatch eventi: '+e,'warn'); }
    }
  }

  function applyYear(year, els){
    window.state = window.state || {}; 
    window.state.year = parseInt(year,10)||new Date().getFullYear(); 
    tlog('Carico anno '+window.state.year,'ok');
    if(els && els.button){ els.button.disabled=true; els.button.textContent='Carico…'; }

    try{ if(typeof loadHolidaysFromLocalOrWeb==='function'){ loadHolidaysFromLocalOrWeb(); } }catch(e){}
    refreshUI(); 
    if(els && els.button){ els.button.disabled=false; els.button.textContent='Carica'; }
  }

  // ✅ versione senza /api/years
  function populateYears(els, done){
    var now = new Date().getFullYear();
    var years = [now - 1, now, now + 1, now + 2];
    els.select.innerHTML = '';
    for (var i = 0; i < years.length; i++) {
      var y = years[i];
      var opt = document.createElement('option');
      opt.value = y;
      opt.textContent = y;
      els.select.appendChild(opt);
    }
    els.select.value = now;
    tlog('Anni disponibili (statici): ' + years.join(', '), 'info');
    done(now);
  }

  function init(){
    var els=ensureBar();
    populateYears(els,function(defYear){
      applyYear(defYear,els);
      els.button.addEventListener('click',function(){ applyYear(els.select.value,els); });
      els.select.addEventListener('change',function(){ applyYear(els.select.value,els); });
    });
  }

  if(!window.__singleYearInstalled){
    window.__singleYearInstalled=true;
    if(document.readyState==='loading'){
      document.addEventListener('DOMContentLoaded', init);
    } else { setTimeout(init,0); }
  }
})();

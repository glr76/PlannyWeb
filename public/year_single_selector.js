
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
  function $(sel){ return document.querySelector(sel); }
  function toInt(v, fb){ var n = parseInt(v,10); return isNaN(n)?fb:n; }
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
  function fetchJSON(url){ return fetch(url,{cache:'no-store'}).then(function(r){ return r.ok?r.json():null; }); }
  function fetchText(url){ return fetch(url,{cache:'no-store'}).then(function(r){ return r.ok?r.text():''; }); }
  function getByPath(pathStr){
    try{ var parts=String(pathStr).split('.'); var cur=window; for(var i=0;i<parts.length;i++){ cur = cur[parts[i]]; if(!cur) return null; } return cur; }catch(e){ return null; }
  }
  function resolveImporter(maxWaitMs, preferredPath, cb){
    var waited = 0;
    var tryList = [
      'importSelectionsFromText','importSelections','loadSelectionsFromText','loadSelections',
      'applySelectionsFromText','applySelections','setSelectionsFromText',
      'planner.importSelectionsFromText','Planner.importSelectionsFromText',
      'app.importSelectionsFromText','App.importSelectionsFromText'
    ];
    function step(){
      var fn = null;
      if(preferredPath){ fn = getByPath(preferredPath); if(typeof fn==='function'){ return cb(fn, preferredPath); } }
      for(var i=0;i<tryList.length;i++){ var cand=getByPath(tryList[i]); if(typeof cand==='function'){ return cb(cand, tryList[i]); } }
      waited += 200; if(waited>=maxWaitMs){ return cb(null,null); } setTimeout(step,200);
    }
    step();
  }
  function refreshUI(){
    var fns=['renderCalendar','refreshCalendar','renderPlanner','buildCalendar','drawCalendar','updateCalendarUI','renderMonthly','renderVisualPlanner','refreshUI','updateUI'];
    var called=false; for(var j=0;j<fns.length && !called;j++){ var fn=fns[j]; if(typeof window[fn]==='function'){ try{ window[fn](); tlog('Ridisegno via '+fn,'ok'); called=true; }catch(e){ tlog('Errore redraw '+fn+': '+e,'error'); } } }
    if(!called){ try{ document.dispatchEvent(new CustomEvent('planner:reload',{detail:{reason:'single-year'}})); window.dispatchEvent(new CustomEvent('planner:year-changed',{detail:{year:window.state.year}})); tlog('Eventi planner dispatchati','info'); }catch(e){ tlog('Errore dispatch eventi: '+e,'warn'); } }
  }
  function applyYear(year, els){
    window.state = window.state || {}; window.state.year = parseInt(year,10)||new Date().getFullYear(); tlog('Carico anno '+window.state.year,'ok');
    if(els && els.button){ els.button.disabled=true; els.button.textContent='Carico…'; }
    try{ if(typeof loadHolidaysFromLocalOrWeb==='function'){ loadHolidaysFromLocalOrWeb(); } }catch(e){}
    var url='/api/selections/'+String(window.state.year); var pref=(window.__SINGLE_IMPORTER && typeof window.__SINGLE_IMPORTER==='string')?window.__SINGLE_IMPORTER:null;
    resolveImporter(8000, pref, function(importer, pathStr){
      if(!importer){ tlog('Importer non trovato. Imposta `window.__SINGLE_IMPORTER = "nomeFunzione"`.', 'warn'); } else { tlog('Importer risolto: '+(pathStr||'(fn)'),'info'); }
      fetchText(url).then(function(t){
        var text=t||''; if(!text){ tlog('Nessun selections per '+window.state.year+' (vuoto o assente). Pulizia e redraw.','warn'); } else { tlog('Selections '+window.state.year+' caricati ('+text.length+' chars)','ok'); }
        if(importer){ try{ importer.call(window,text); }catch(e){ tlog('Errore in importer: '+e,'error'); } } else { window.__singleSelectionsText=text; }
        refreshUI(); if(els && els.button){ els.button.disabled=false; els.button.textContent='Carica'; }
      })['catch'](function(e){
        tlog('Errore fetch selections: '+e,'error'); if(importer){ try{ importer.call(window,''); }catch(_){ } } else { window.__singleSelectionsText=''; }
        refreshUI(); if(els && els.button){ els.button.disabled=false; els.button.textContent='Carica'; }
      });
    });
  }
  function populateYears(els, done){
    fetch('/api/years',{cache:'no-store'}).then(function(r){ return r.ok?r.json():null; }).then(function(data){
      var years=(data && data.ok && data.years)?data.years.slice():[]; years.sort(function(a,b){return a-b;});
      els.select.innerHTML=''; for(var i=0;i<years.length;i++){ var y=years[i],opt=document.createElement('option'); opt.value=y; opt.textContent=y; els.select.appendChild(opt); }
      var now=new Date().getFullYear(); var def=(years.indexOf(now)>=0)?now:(years.length?years[years.length-1]:now); els.select.value=def; tlog('Anni disponibili: '+(years.join(', ')||'(nessuno)')+' | selezionato '+els.select.value,'info'); done(parseInt(els.select.value,10)||now);
    })['catch'](function(e){
      var now=new Date().getFullYear(); els.select.innerHTML=''; var opt=document.createElement('option'); opt.value=now; opt.textContent=now; els.select.appendChild(opt); done(now);
    });
  }
  function init(){
    var els=ensureBar(); populateYears(els,function(defYear){ applyYear(defYear,els); els.button.addEventListener('click',function(){ applyYear(els.select.value,els); }); els.select.addEventListener('change',function(){ applyYear(els.select.value,els); }); });
  }
  if(!window.__singleYearInstalled){ window.__singleYearInstalled=true; if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', init); } else { setTimeout(init,0);} }
})();

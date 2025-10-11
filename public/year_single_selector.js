(function(){
  function tlog(msg, lvl){
    try{
      var prefix = '['+(new Date().toLocaleTimeString())+'] '+(lvl||'info').toUpperCase()+': ';
      if(typeof console!=='undefined') console.log(prefix+msg);
    }catch(_){}
  }

  function refreshUI(){
    var fns=['renderCalendar','refreshCalendar','renderPlanner','buildCalendar',
             'drawCalendar','updateCalendarUI','renderMonthly','renderVisualPlanner',
             'refreshUI','updateUI'];
    for(let fn of fns){
      if(typeof window[fn]==='function'){
        try{ window[fn](); tlog('Ridisegno via '+fn,'ok'); return; }
        catch(e){ tlog('Errore redraw '+fn+': '+e,'error'); }
      }
    }
    try{
      document.dispatchEvent(new CustomEvent('planner:reload',{detail:{reason:'single-year'}}));
      window.dispatchEvent(new CustomEvent('planner:year-changed',{detail:{year:window.state.year}}));
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
    if(sel.options.length===0){
      let years=[now-1, now, now+1, now+2];
      for(let y of years){
        let opt=document.createElement('option');
        opt.value=y; opt.textContent=y;
        sel.appendChild(opt);
      }
      sel.value=now;
    }
    tlog('Select anno pronto ('+sel.value+')','info');
    applyYear(sel.value);
  }

  function init(){
    var sel=document.querySelector('#yearSingle');
    if(!sel){ tlog('Nessun select#yearSingle trovato: niente barra creata','warn'); return; }
    populateYears(sel);
    sel.addEventListener('change',()=>applyYear(sel.value));
  }

  if(!window.__singleYearInstalled){
    window.__singleYearInstalled=true;
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init);
    else setTimeout(init,0);
  }
})();

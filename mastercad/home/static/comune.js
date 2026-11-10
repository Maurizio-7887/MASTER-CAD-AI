/* MASTER CAD AI · funzioni comuni alle pagine dell'officina: progetto aperto, chiamate al server, download. */
(function () {
  'use strict';
  var CSRF = document.body.getAttribute('data-csrf') || '';
  function leggi(k) { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } }
  function scriviLocale(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

  var MC = {
    csrf: CSRF,
    progetto: function () { var p = leggi('mcad-progetto'); return p && p.base ? p : null; },
    salvaProgetto: function (p) { scriviLocale('mcad-progetto', p); },
    nome: function () { var p = MC.progetto(); return (p && p.nome) || 'Pezzo'; },
    leggi: leggi, scriviLocale: scriviLocale,
    esc: function (t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); },
    num: function (v, dec) { return Number(v).toLocaleString('it-IT', {minimumFractionDigits: dec || 0, maximumFractionDigits: dec == null ? 2 : dec}); },
    euro: function (v) { return Number(v).toLocaleString('it-IT', {style: 'currency', currency: 'EUR'}); },
    api: async function (url, corpo, metodo) {
      var opz = {method: metodo || (corpo === undefined ? 'GET' : 'POST'), credentials: 'same-origin', headers: {'X-CSRF-Token': CSRF}};
      if (corpo instanceof FormData) opz.body = corpo;
      else if (corpo !== undefined) { opz.headers['Content-Type'] = 'application/json'; opz.body = JSON.stringify(corpo); }
      var r = await fetch(url, opz);
      if (r.status === 401) { location.href = '/login?expired=1'; throw new Error('Sessione scaduta'); }
      var j = await r.json().catch(function () { return {error: 'Risposta non valida dal server'}; });
      if (!r.ok) throw new Error(j.error || 'Errore del server');
      return j;
    },
    scarica: async function (url, corpo, nomeFile) {
      var r = await fetch(url, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRF-Token': CSRF, 'Content-Type': 'application/json'}, body: JSON.stringify(corpo)});
      if (!r.ok) { var j = await r.json().catch(function () { return {}; }); throw new Error(j.error || 'Download non riuscito'); }
      var b = await r.blob(), a = document.createElement('a');
      a.href = URL.createObjectURL(b); a.download = nomeFile; document.body.appendChild(a); a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 800);
    },
    occupato: function (btn, si, testo) {
      if (!btn) return;
      if (si) { btn.dataset.testo = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="carico"></span> ' + (testo || 'Calcolo…'); }
      else { btn.disabled = false; if (btn.dataset.testo) btn.innerHTML = btn.dataset.testo; }
    },
    kpi: function (chiave, valore, etichetta) {
      var k = leggi('mcad-kpi') || {};
      k[chiave] = {valore: valore, etichetta: etichetta, pezzo: MC.nome()};
      scriviLocale('mcad-kpi', k);
    },
    messaggio: function (el, testo, tipo) { el.hidden = !testo; el.className = 'messaggio ' + (tipo || 'info'); el.textContent = testo || ''; },
    descriviBase: function (p) {
      if (!p) return '';
      var b = p.base, n = (p.lavorazioni || []).filter(function (l) { return !l.sospesa; }).length;
      var t = b.tipo === 'estrudi' ? 'piastra/sagoma estrusa ' + MC.num(b.altezza) + ' mm' : b.tipo === 'rivoluzione' ? 'pezzo tornito' : 'pezzo a due viste';
      return t + ' · ' + n + (n === 1 ? ' lavorazione' : ' lavorazioni');
    },
    /* riquadro «pezzo aperto» in cima alle pagine; se non c'è un pezzo spiega da dove partire */
    riquadroPezzo: function (el, testoAzione) {
      var p = MC.progetto();
      if (!p) {
        el.innerHTML = '<div class="vuoto-stato"><h2>Nessun pezzo aperto</h2><p>Questa funzione lavora sul pezzo che costruisci nel CAD. Parti da qui:</p>' +
          '<a class="btn" href="/disegno#foto">📷 Dalla foto</a><a class="btn sec" href="/disegno">📐 Disegno CAD</a><a class="btn sec" href="/libreria">📚 Libreria a norma</a></div>';
        return null;
      }
      el.innerHTML = '<div class="pezzo"><div class="icona"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 2 3 7v10l9 5 9-5V7z"/><path d="M3 7l9 5 9-5M12 12v10"/></svg></div>' +
        '<div class="info"><b>' + MC.esc(MC.nome()) + '</b><div>' + MC.esc(MC.descriviBase(p)) + (testoAzione ? ' — ' + MC.esc(testoAzione) : '') + '</div></div>' +
        '<a class="btn sec" href="/disegno">Modifica nel CAD</a></div>';
      return p;
    },
    esci: async function () {
      var r = await fetch('/logout', {method: 'POST', credentials: 'same-origin', headers: {'X-CSRF-Token': CSRF}});
      var j = await r.json().catch(function () { return {}; });
      location.href = j.redirect || '/login';
    }
  };
  window.MC = MC;
  var b = document.getElementById('esci');
  if (b) b.onclick = MC.esci;
})();

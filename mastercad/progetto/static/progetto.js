/* MASTER CAD AI · progetto parametrico: forma di base + albero delle lavorazioni + indicazioni del tecnico.
   Il pezzo si ricostruisce da capo a ogni modifica: si può sospendere o togliere una lavorazione senza rifare tutto. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); }, CSRF = document.body.getAttribute('data-csrf') || '';
  var P = {base: null, lavorazioni: []}, ultimaStoria = [];
  var ORDINE = {rialzo: 0, tasca: 1, asola: 2, foro: 3, serie_polare: 3, serie_rett: 3, raccordo: 5, smusso: 6, guscio: 7};

  function salva() { try { localStorage.setItem('mcad-progetto', JSON.stringify(P)); } catch (e) {} }
  try { var v = JSON.parse(localStorage.getItem('mcad-progetto') || 'null'); if (v && typeof v === 'object' && Array.isArray(v.lavorazioni)) P = v; } catch (e) {}

  async function chiama(url, corpo) {
    var r = await fetch(url, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': CSRF}, body: JSON.stringify(corpo)});
    if (r.status === 401) { location.href = '/login?expired=1'; throw new Error('Sessione scaduta'); }
    var j = await r.json().catch(function () { return {error: 'Risposta non valida dal server'}; });
    if (!r.ok) throw new Error(j.error || 'Errore del server');
    return j;
  }
  var log = function (t) { if (window.MCAD) window.MCAD.scrivi(t); };
  var g = function (v) { return Math.round(Number(v) * 100) / 100; };

  function foroTesto(f) {
    if (!f) return '';
    var t = f.filetto ? f.filetto + ' filettato' : 'Ø' + g(f.d);
    t += f.prof == null ? ' passante' : ' prof. ' + g(f.prof);
    if (f.lamatura) t += ', lamatura Ø' + g(f.lamatura.d) + '×' + g(f.lamatura.prof);
    if (f.svasatura) t += ', svasatura Ø' + g(f.svasatura.d);
    if (f.tolleranza) t += ' ' + f.tolleranza;
    return t;
  }
  function descrivi(l) {
    var c = l.centro ? ' in ' + g(l.centro[0]) + ',' + g(l.centro[1]) : '', prof = l.prof == null ? 'passante' : 'prof. ' + g(l.prof);
    switch (l.tipo) {
      case 'foro': return 'Foro ' + foroTesto(l) + ' in ' + g(l.x) + ',' + g(l.y) + (l.origine === 'foto+tecnico' ? ' · misura del tecnico' : l.origine ? ' · dal disegno' : '');
      case 'serie_polare': return l.n + ' fori ' + foroTesto(l.foro) + ' su interasse Ø' + g(l.diametro);
      case 'serie_rett': return (l.nx * l.ny) + ' fori ' + foroTesto(l.foro) + ' in griglia ' + l.nx + '×' + l.ny + ' passo ' + g(l.passo_x) + '×' + g(l.passo_y);
      case 'tasca': return 'Tasca ' + (l.forma === 'cerchio' ? 'Ø' + g(l.d) : g(l.l) + '×' + g(l.w)) + ' ' + prof + c + (l.raggio_angoli ? ' R' + g(l.raggio_angoli) : '');
      case 'asola': return 'Asola ' + g(l.lunghezza) + '×' + g(l.larghezza) + ' a ' + g(l.angolo || 0) + '° ' + prof + c;
      case 'rialzo': return 'Rialzo ' + (l.forma === 'cerchio' ? 'Ø' + g(l.d) : g(l.l) + '×' + g(l.w)) + ' alto ' + g(l.h) + c;
      case 'raccordo': return 'Raccordo R' + g(l.r) + ' spigoli ' + (l.spigoli || 'verticali');
      case 'smusso': return 'Smusso ' + g(l.d) + '×45° spigoli ' + (l.spigoli || 'superiori');
      case 'guscio': return 'Guscio spessore ' + g(l.spessore) + ', aperto ' + (l.aperta || 'sopra');
    }
    return String(l.tipo);
  }
  function testoBase() {
    var b = P.base;
    if (!b) return 'Nessuna forma di base: disegna (o ricava dalla foto) il contorno e premi ESTRUDI o RIVOLUZIONE.';
    if (b.tipo === 'estrudi') return 'Base: contorno della tavola estruso di ' + g(b.altezza) + ' mm.';
    if (b.tipo === 'rivoluzione') return 'Base: mezza sezione tornita (' + g(b.angolo || 360) + '°).';
    return 'Base a due viste: dall’alto ' + (b.alto ? '✓' : '— manca') + ' · di fronte ' + (b.fronte ? '✓' : '— manca (foto «di fronte» o «Tavola = vista di fronte»)') + '.';
  }
  function mostra() {
    $('prog-base').textContent = testoBase();
    var ol = $('prog-albero'); ol.innerHTML = '';
    P.lavorazioni.forEach(function (l, i) {
      var li = document.createElement('li'), st = ultimaStoria[i + 1];
      li.className = l.sospesa ? 'sospesa' : (st && st.ok === false ? 'saltata' : '');
      var t = document.createElement('span'); t.textContent = descrivi(l); li.appendChild(t);
      if (st && st.ok === false) { var w = document.createElement('small'); w.textContent = st.dettaglio; li.appendChild(w); }
      var b1 = document.createElement('button'); b1.type = 'button'; b1.textContent = l.sospesa ? 'Riattiva' : 'Sospendi';
      b1.onclick = function () { l.sospesa = !l.sospesa; costruisci(); };
      var b2 = document.createElement('button'); b2.type = 'button'; b2.textContent = '✕'; b2.title = 'Togli dall’albero';
      b2.onclick = function () { P.lavorazioni.splice(i, 1); costruisci(); };
      var box = document.createElement('div'); box.appendChild(b1); box.appendChild(b2); li.appendChild(box);
      ol.appendChild(li);
    });
    salva();
  }

  async function costruisci() {
    mostra();
    if (!P.base) { log('Manca la forma di base: disegna il contorno e premi ESTRUDI.'); return; }
    log('Costruisco il progetto: base + ' + P.lavorazioni.length + ' lavorazioni…');
    $('prog-costruisci').disabled = true;
    P.nome = $('nome-pezzo').value.trim() || P.nome || 'Pezzo';
    try {
      var j = await chiama('/api/progetto/costruisci', {progetto: P, nome: P.nome});
      ultimaStoria = j.history || [];
      window.MCAD.mostra3d(j);
      ultimaStoria.forEach(function (s) { log((s.ok === false ? '⚠ ' : '  ✓ ') + s.op + ': ' + s.dettaglio); });
      if (j.saltate) log('⚠ ' + j.saltate + ' lavorazioni saltate: correggi le misure (sono segnate in rosso nell’albero).');
      fattibilita();
    } catch (e) { log('⛔ ' + e.message); }
    finally { $('prog-costruisci').disabled = false; mostra(); }
  }

  /* il tecnico esperto controlla il pezzo appena costruito (pareti, fori al bordo, filetti…) */
  function fattibilita() {
    var box = $('prog-dfm');
    if (!box) return;
    box.innerHTML = '<span class="info">Verifico la fattibilità…</span>';
    chiama('/api/fattibilita', {progetto: P}).then(function (j) {
      var t = j.errori ? '⛔ ' + j.errori + (j.errori === 1 ? ' errore' : ' errori') + (j.attenzioni ? ' e ' + j.attenzioni + ' attenzioni' : '') :
        j.attenzioni ? '⚠ ' + j.attenzioni + (j.attenzioni === 1 ? ' attenzione' : ' attenzioni') + ' di fattibilità' : '✓ Fattibile: nessun problema dalle regole di officina';
      box.innerHTML = '';
      var a = document.createElement('a');
      a.href = '/fattibilita'; a.textContent = t + (j.errori || j.attenzioni ? ' — vedi dove e come rimediare' : '');
      a.className = j.errori ? 'dfm err' : j.attenzioni ? 'dfm att' : 'dfm ok';
      box.appendChild(a);
      if (j.errori) log('⛔ Fattibilità: ' + j.avvisi.filter(function (x) { return x.livello === 'errore'; }).slice(0, 3).map(function (x) { return x.dove + ': ' + x.testo; }).join(' · '));
    }).catch(function () { box.innerHTML = ''; });
  }

  async function impostaBase(come, dati) {
    var j = await chiama('/api/progetto/da-disegno', Object.assign({come: come, progetto: P}, dati));
    P = j.progetto; ultimaStoria = [];
    if (P.base && P.base.tipo === 'due_viste' && (!P.base.alto || !P.base.fronte)) { mostra(); log(testoBase()); return; }
    await costruisci();
  }

  function aggiungi(lav) {
    P.lavorazioni.push(lav);
    P.lavorazioni.sort(function (a, b) { return (ORDINE[a.tipo] == null ? 4 : ORDINE[a.tipo]) - (ORDINE[b.tipo] == null ? 4 : ORDINE[b.tipo]); });
    return costruisci();
  }

  $('prog-applica').onclick = async function () {
    var testo = $('prog-direttive').value.trim();
    if (!testo) { $('prog-direttive').focus(); return; }
    var ul = $('prog-esito'); ul.innerHTML = '';
    try {
      var j = await chiama('/api/progetto/direttive', {testo: testo, progetto: P});
      P = j.progetto;
      j.capito.forEach(function (c) { var li = document.createElement('li'); li.textContent = '✓ ' + c; ul.appendChild(li); });
      j.non_capito.forEach(function (c) { var li = document.createElement('li'); li.className = 'no'; li.textContent = '? Non capito: «' + c + '» — riscrivilo (es. «foro Ø10 in 20,30», «tasca 40x20 profonda 5»)'; ul.appendChild(li); });
      await costruisci();
    } catch (e) { var li = document.createElement('li'); li.className = 'no'; li.textContent = '⛔ ' + e.message; ul.appendChild(li); }
  };
  $('prog-costruisci').onclick = costruisci;
  $('prog-svuota').onclick = function () { P.lavorazioni = []; ultimaStoria = []; costruisci(); };
  var daTavola = function (come) {
    return function () {
      var ent = window.MCAD.cad.stato.entita;
      if (!ent.length) { log('La tavola è vuota.'); return; }
      impostaBase(come, {entita: ent}).catch(function (e) { log('⛔ ' + e.message); });
    };
  };
  $('prog-alto').onclick = daTavola('alto');
  $('prog-fronte').onclick = daTavola('fronte');

  window.MCADP = {impostaBase: impostaBase, aggiungi: aggiungi, costruisci: costruisci, progetto: function () { return P; }};
  if (P.nome && !$('nome-pezzo').value) $('nome-pezzo').value = P.nome;
  $('nome-pezzo').addEventListener('change', function () { P.nome = this.value.trim() || 'Pezzo'; salva(); });
  mostra();
  // arrivo dalla libreria o dal pannello docente: il pezzo è già pronto, si costruisce subito
  if (location.hash === '#costruisci') { history.replaceState(null, '', location.pathname); if (P.base) costruisci(); }
  else if (location.hash === '#foto') { var f = document.getElementById('foto'); if (f) { f.scrollIntoView({behavior: 'smooth'}); f.style.outline = '3px solid #ffd34d'; } }
})();

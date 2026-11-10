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
    if (f.lamatura) t += (f.lamatura.tolleranza ? ', sede Ø' + g(f.lamatura.d) + ' ' + f.lamatura.tolleranza : ', lamatura Ø' + g(f.lamatura.d)) + '×' + g(f.lamatura.prof);
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
  var nuovoId = function () { return Math.random().toString(36).slice(2, 10); };
  var utente = function () { try { return JSON.parse(localStorage.getItem('mcad-utente') || 'null') || 'Ufficio tecnico'; } catch (e) { return 'Ufficio tecnico'; } };
  /* registro delle decisioni: chi, cosa, in base a quale norma o calcolo */
  function registra(cosa, norma, verifica) {
    P.registro = P.registro || [];
    P.registro.push({quando: new Date().toISOString(), chi: utente(), cosa: cosa, norma: norma || '', verifica: verifica || ''});
    salva();
  }
  function identifica() {
    if (!P.uid) P.uid = nuovoId() + nuovoId();
    P.lavorazioni.forEach(function (l) { if (!l.id) l.id = nuovoId(); });
  }
  var TIPI_FZ = {sede_cuscinetto: ['Sede cuscinetto', 'es. 6204'], foro_spina: ['Foro spina', 'Ø spina, es. 8'], sede_boccola: ['Sede boccola', 'es. 20x23'],
    passaggio_vite: ['Passaggio vite', 'es. M8'], filetto: ['Foro filettato', 'es. M8'], libera: ['Quota libera', '']};
  function editorScopo(li, i) {
    var l = P.lavorazioni[i], fz = l.funzione || {};
    var box = document.createElement('div'); box.className = 'scopo';
    box.innerHTML = '<label>Perché esiste questo foro?<select data-k="tipo">' + Object.keys(TIPI_FZ).map(function (k) { return '<option value="' + k + '"' + (fz.tipo === k ? ' selected' : '') + '>' + TIPI_FZ[k][0] + '</option>'; }).join('') + '</select></label>' +
      '<label>Componente<input data-k="componente"></label><label>Tolleranza<input data-k="sigla" placeholder="H7"></label>' +
      '<div class="actions"><button type="button" data-az="prova">Vedi cosa cambia</button><button type="button" class="sec" data-az="chiudi">Chiudi</button></div><div class="impatto"></div>';
    var sel = box.querySelector('[data-k=tipo]'), comp = box.querySelector('[data-k=componente]'), sig = box.querySelector('[data-k=sigla]');
    comp.value = fz.tipo === 'foro_spina' ? String(fz.componente || '').replace(/[^\d.,]/g, '') : (fz.componente || '').replace('Boccola ', '').replace('×', 'x');
    sig.value = fz.sigla || '';
    var ph = function () { comp.placeholder = TIPI_FZ[sel.value][1]; };
    sel.onchange = ph; ph();
    var proposta = null;
    box.querySelector('[data-az=chiudi]').onclick = function () { box.remove(); };
    box.querySelector('[data-az=prova]').onclick = async function () {
      var f = {tipo: sel.value, componente: comp.value.trim(), diametro: comp.value.trim().replace(',', '.')};
      if (sig.value.trim()) f.sigla = sig.value.trim();
      var out = box.querySelector('.impatto');
      out.textContent = 'Calcolo l’impatto…';
      try {
        var j = await chiama('/api/progetto/funzione', {progetto: P, indice: i, funzione: f});
        proposta = j;
        var im = j.impatto, h = '<b>' + (j.funzione.perche || '') + '</b><br><small>Norma: ' + (j.funzione.norma || '—') + '</small><ul>';
        (im.modifiche.length ? im.modifiche : ['Nessuna modifica alle misure']).forEach(function (m) { h += '<li>' + m.replace(/</g, '&lt;') + '</li>'; });
        im.problemi_nuovi.forEach(function (x) { h += '<li class="no">⚠ ' + (x.dove + ': ' + x.testo).replace(/</g, '&lt;') + '</li>'; });
        (im.problemi_restano || []).forEach(function (x) { h += '<li class="no">⚠ resta: ' + (x.dove + ': ' + x.testo).replace(/</g, '&lt;') + '</li>'; });
        im.problemi_risolti.forEach(function (x) { h += '<li>✓ risolto: ' + x.testo.replace(/</g, '&lt;') + '</li>'; });
        out.innerHTML = h + '</ul><div class="actions"><button type="button" data-az="ok">Conferma e ricostruisci</button></div>';
        out.querySelector('[data-az=ok]').onclick = function () {
          var vecchio = P.lavorazioni[i];
          P = proposta.progetto;
          registra('Scopo di «' + descrivi(vecchio) + '»: ' + TIPI_FZ[proposta.funzione.tipo][0] + ' ' + (proposta.funzione.componente || '') + (proposta.funzione.sigla ? ' ' + proposta.funzione.sigla : ''),
            proposta.funzione.norma, (im.modifiche.join('; ') || 'nessuna modifica di misura') + (im.problemi_nuovi.length ? ' — ' + im.problemi_nuovi.length + ' avvisi di fattibilità' : ''));
          costruisci();
        };
      } catch (e) { out.textContent = '⛔ ' + e.message; }
    };
    li.appendChild(box);
  }
  function mostra() {
    identifica();
    $('prog-base').textContent = testoBase();
    var ol = $('prog-albero'); ol.innerHTML = '';
    P.lavorazioni.forEach(function (l, i) {
      var li = document.createElement('li'), st = ultimaStoria[i + 1];
      li.className = l.sospesa ? 'sospesa' : (st && st.ok === false ? 'saltata' : '');
      var t = document.createElement('span'); t.textContent = descrivi(l); li.appendChild(t);
      if (l.funzione && l.funzione.tipo !== 'libera') { var fz = document.createElement('em'); fz.className = 'fz'; fz.title = l.funzione.perche || ''; fz.textContent = '⚙ ' + (l.funzione.componente || '') + (l.funzione.sigla ? ' · ' + l.funzione.sigla : ''); li.appendChild(fz); }
      if (st && st.ok === false) { var w = document.createElement('small'); w.textContent = st.dettaglio; li.appendChild(w); }
      var box = document.createElement('div');
      if (['foro', 'serie_polare', 'serie_rett'].indexOf(l.tipo) >= 0) {
        var b0 = document.createElement('button'); b0.type = 'button'; b0.textContent = 'Scopo'; b0.title = 'Perché esiste: cuscinetto, spina, boccola, vite… (tolleranza ISO 286)';
        b0.onclick = function () { if (!li.querySelector('.scopo')) editorScopo(li, i); };
        box.appendChild(b0);
      }
      var b1 = document.createElement('button'); b1.type = 'button'; b1.textContent = l.sospesa ? 'Riattiva' : 'Sospendi';
      b1.onclick = function () { l.sospesa = !l.sospesa; registra((l.sospesa ? 'Sospesa' : 'Riattivata') + ' «' + descrivi(l) + '»'); costruisci(); };
      var b2 = document.createElement('button'); b2.type = 'button'; b2.textContent = '✕'; b2.title = 'Togli dall’albero';
      b2.onclick = function () { registra('Tolta «' + descrivi(l) + '»'); P.lavorazioni.splice(i, 1); costruisci(); };
      box.appendChild(b1); box.appendChild(b2); li.appendChild(box);
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

  /* costo dal vivo: a ogni lavorazione si vede quanto costa il pezzo nella tua officina */
  function costo() {
    var box = $('prog-costo');
    if (!box) return;
    box.textContent = 'Calcolo il costo…';
    var mat = (function () { try { return (JSON.parse(localStorage.getItem('mcad-cartiglio') || '{}').materiale) || 'S235'; } catch (e) { return 'S235'; } })();
    chiama('/api/preventivo', {progetto: P, materiale: mat, parametri: {quantita: [1, 10]}}).then(function (j) {
      var r = j.preventivo.righe, prima = P._costo10;
      var t = '€ ' + r[1].prezzo.toLocaleString('it-IT', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + '/pz su 10 · ' + r[1].quantita + ' pz';
      var d = prima != null ? r[1].prezzo - prima : 0;
      box.innerHTML = '';
      var a = document.createElement('a'); a.href = '/preventivo'; a.className = 'dfm costo';
      a.textContent = '💶 ' + t.replace(' · 10 pz', '') + ' (1 pz: € ' + r[0].prezzo.toLocaleString('it-IT', {maximumFractionDigits: 0}) + ', ' + j.preventivo.tempi.macchina_min.toLocaleString('it-IT') + ' min macchina)' +
        (Math.abs(d) >= 0.01 ? (d > 0 ? '  ▲ +€ ' : '  ▼ −€ ') + Math.abs(d).toLocaleString('it-IT', {maximumFractionDigits: 2}) + ' con l’ultima modifica' : '');
      box.appendChild(a);
      P._costo10 = r[1].prezzo; salva();
    }).catch(function () { box.textContent = ''; });
  }

  /* il tecnico esperto controlla il pezzo appena costruito (pareti, fori al bordo, filetti…) */
  function fattibilita() {
    costo();
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
      identifica();
      if (j.capito.length) registra('Indicazioni del tecnico: «' + testo.slice(0, 200) + '»', 'Interprete a regole; tolleranze ISO 286 dove indicate', j.capito.join('; ').slice(0, 400));
      j.capito.forEach(function (c) { var li = document.createElement('li'); li.textContent = '✓ ' + c; ul.appendChild(li); });
      j.non_capito.forEach(function (c) { var li = document.createElement('li'); li.className = 'no'; li.textContent = '? Non capito: «' + c + '» — riscrivilo (es. «foro Ø10 in 20,30», «tasca 40x20 profonda 5»)'; ul.appendChild(li); });
      await costruisci();
    } catch (e) { var li = document.createElement('li'); li.className = 'no'; li.textContent = '⛔ ' + e.message; ul.appendChild(li); }
  };
  $('prog-costruisci').onclick = costruisci;
  $('prog-versione').onclick = async function () {
    var m = $('prog-messaggio').value.trim(), out = $('prog-versione-esito');
    if (!m) { $('prog-messaggio').focus(); out.textContent = 'Scrivi in una riga cosa è cambiato.'; return; }
    if (!P.base) { out.textContent = 'Prima costruisci il pezzo.'; return; }
    try {
      identifica();
      var j = await chiama('/api/versioni', {progetto: P, messaggio: m, autore: utente()});
      out.innerHTML = '✓ Versione ' + j.numero + ' salvata: ' + j.differenze.slice(0, 3).join(' · ').replace(/</g, '&lt;') + ' — <a href="/versioni">storico</a>';
      $('prog-messaggio').value = '';
    } catch (e) { out.textContent = '⛔ ' + e.message; }
  };
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

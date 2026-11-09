/* MASTER CAD AI · interfaccia della tavola 2D: disegno, riga di comando, snap, selezione come AutoCAD. */
(function () {
  'use strict';
  var G = window.G2D, $ = function (id) { return document.getElementById(id); };
  var CSRF = document.body.getAttribute('data-csrf') || '';
  var tela = $('tavola'), ctx = tela.getContext('2d'), input = $('cmd'), etichetta = $('cmd-prompt'), storia = $('storia');
  var vista = {cx: 60, cy: 40, scala: 4};          // centro in mm, pixel per mm (pixel CSS)
  var mouse = {mm: [0, 0], px: [0, 0], dentro: false}, snapAttivo = null, anteprima = [], finestra = null, panning = null;
  var attesa = null;            // {req, risolvi} mentre un comando chiede un dato
  var selezionando = null;      // {risolvi} mentre un comando chiede di selezionare
  var vista3d = window.Vista3D($('vista3d'));

  // ── riga di comando ──
  function scrivi(t) { var d = document.createElement('div'); d.textContent = t; if (/^⛔/.test(t)) d.className = 'err'; storia.appendChild(d); while (storia.childNodes.length > 400) storia.removeChild(storia.firstChild); storia.scrollTop = storia.scrollHeight; }
  function prompt(t) { etichetta.textContent = t || 'Comando:'; }
  var io = {
    scrivi: scrivi,
    chiedi: function (req) { return new Promise(function (ris) { attesa = {req: req, risolvi: ris}; anteprima = []; prompt(req.prompt); disegna(); }); },
    seleziona: function (t) {
      return new Promise(function (ris) { selezionando = {risolvi: ris}; prompt(t + ' (clic o finestra, INVIO per confermare, T = tutto):'); disegna(); });
    },
    zoomEstensioni: zoomEstensioni, aggiorna: function () { prompt('Comando:'); attesa = null; selezionando = null; anteprima = []; disegna(); salvaLocale(); },
    scarica: function (nome, testo, mime) { var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([testo], {type: mime || 'application/octet-stream'})); a.download = nome; document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500); },
    apriFile: function (accept) { return new Promise(function (ris) { var f = $('file-dxf'); f.value = ''; f.accept = accept; f.onchange = function () { var x = f.files[0]; if (!x) return ris(null); var r = new FileReader(); r.onload = function () { ris(String(r.result)); }; r.readAsText(x); }; f.click(); }); },
    solido: solido,
    lavorazione: function (lav) { if (!window.MCADP) throw new Error('Pannello Progetto non disponibile'); return window.MCADP.aggiungi(lav); }
  };
  var cad = window.CAD.crea(io), S = cad.stato;

  function invia(testo) {
    if (selezionando) {
      var u = String(testo).trim().toUpperCase();
      if (u === 'T' || u === 'TUTTO' || u === 'ALL') { S.sel = S.entita.map(function (e) { return e.id; }); disegna(); return; }
      if (u === '') { var r = selezionando; selezionando = null; var ids = S.sel.slice(); S.sel = []; r.risolvi(ids); return; }
      scrivi('Durante la selezione: clic sugli oggetti, finestra, T = tutto, INVIO per confermare.'); return;
    }
    if (attesa) { var a = attesa; attesa = null; a.risolvi({testo: testo, cursore: mouse.mm}); return; }
    cad.esegui(testo);
  }
  function annulla() {
    if (selezionando) { var r = selezionando; selezionando = null; S.sel = []; r.risolvi(null); return; }
    if (attesa) { var a = attesa; attesa = null; a.risolvi({annulla: true}); return; }
    S.sel = []; finestra = null; disegna();
  }
  input.addEventListener('keydown', function (e) {
    var tipoTesto = attesa && attesa.req.tipo === 'testo';
    if (e.key === 'Enter' || (e.key === ' ' && !tipoTesto)) { e.preventDefault(); var t = input.value; input.value = ''; invia(t); }
    else if (e.key === 'Escape') { e.preventDefault(); input.value = ''; annulla(); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'F8') { e.preventDefault(); S.orto = !S.orto; scrivi('<Orto ' + (S.orto ? 'attivato' : 'disattivato') + '>'); stato(); }
    else if (e.key === 'F9') { e.preventDefault(); S.snap = !S.snap; scrivi('<Snap ' + (S.snap ? 'attivato' : 'disattivato') + '>'); stato(); }
    else if (e.key === 'F3') { e.preventDefault(); S.osnap = !S.osnap; scrivi('<Osnap ' + (S.osnap ? 'attivato' : 'disattivato') + '>'); stato(); }
    else if (e.key === 'F1') { e.preventDefault(); cad.esegui('AIUTO'); }
    else if (e.key === 'Delete' && document.activeElement !== input && !attesa && !selezionando) { cad.cancellaSelezione(); }
    else if (e.key === 'Escape' && document.activeElement !== input) { annulla(); }
    else if (e.ctrlKey && (e.key === 'z' || e.key === 'Z') && !attesa) { e.preventDefault(); cad.esegui('ANNULLA'); }
    else if (!e.ctrlKey && !e.altKey && !e.metaKey && e.key.length === 1 && document.activeElement !== input && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      input.focus();       // come AutoCAD: si scrive sempre nella riga di comando
    }
  });

  // ── coordinate ──
  var aMm = function (px) { return [vista.cx + (px[0] - tela.clientWidth / 2) / vista.scala, vista.cy - (px[1] - tela.clientHeight / 2) / vista.scala]; };
  var aPx = function (p) { return [tela.clientWidth / 2 + (p[0] - vista.cx) * vista.scala, tela.clientHeight / 2 - (p[1] - vista.cy) * vista.scala]; };
  function zoomEstensioni() {
    var b = G.estensione(S.entita);
    if (!b) { vista = {cx: 60, cy: 40, scala: Math.min(tela.clientWidth / 180, tela.clientHeight / 120) || 4}; disegna(); return; }
    var w = Math.max(1, b.hi[0] - b.lo[0]), h = Math.max(1, b.hi[1] - b.lo[1]);
    vista.cx = (b.lo[0] + b.hi[0]) / 2; vista.cy = (b.lo[1] + b.hi[1]) / 2;
    vista.scala = Math.max(0.01, Math.min(tela.clientWidth / (w * 1.25), tela.clientHeight / (h * 1.25)));
    disegna();
  }

  // ── snap ad oggetto e alla griglia ──
  function trovaSnap(pmm) {
    if (!S.osnap) return null;
    var tol = 12 / vista.scala, best = null, bd = tol;
    var vicine = S.entita.filter(function (e) { return G.distanza(pmm, e) < tol * 3; });
    vicine.forEach(function (e) { G.puntiSnap(e).forEach(function (s) { var d = G.dist(pmm, s.p); if (d < bd) { bd = d; best = s; } }); });
    for (var i = 0; i < vicine.length; i++) for (var j = i + 1; j < vicine.length; j++) {
      G.primitive(vicine[i]).forEach(function (a) { G.primitive(vicine[j]).forEach(function (b) { G.interseca(a, b).forEach(function (p) { var d = G.dist(pmm, p); if (d < bd) { bd = d; best = {p: p, k: 'intersezione'}; } }); }); });
    }
    return best;
  }
  function puntoCursore(px) {
    var p = aMm(px); snapAttivo = attesa || selezionando ? trovaSnap(p) : null;
    if (snapAttivo) return snapAttivo.p;
    if (S.snap) return [Math.round(p[0] / S.passo) * S.passo, Math.round(p[1] / S.passo) * S.passo];
    return p;
  }

  // ── mouse ──
  tela.addEventListener('contextmenu', function (e) { e.preventDefault(); });
  tela.addEventListener('pointerdown', function (e) {
    tela.setPointerCapture(e.pointerId);
    var px = [e.offsetX, e.offsetY];
    if (e.button === 1 || e.button === 2) {        // tasto centrale o destro: PAN (destro senza trascinare = INVIO, come AutoCAD)
      panning = {px: px, cx: vista.cx, cy: vista.cy, mosso: false, destro: e.button === 2}; return;
    }
    var p = puntoCursore(px);
    if (attesa) {
      var t = attesa.req.tipo;
      if (t === 'punto' || t === 'distanza' || t === 'angolo' || t === 'entita') {
        var a = attesa; attesa = null; a.risolvi({clic: t === 'entita' ? aMm(px) : p, snap: !!snapAttivo, tolleranza: 8 / vista.scala, cursore: p});
      }
      return;
    }
    // selezione: clic su un oggetto o inizio finestra
    var e2 = cad.vicina(aMm(px), 6 / vista.scala);
    if (e2) { var i = S.sel.indexOf(e2.id); if (i >= 0 && e.shiftKey) S.sel.splice(i, 1); else if (i < 0) S.sel.push(e2.id); disegna(); return; }
    finestra = {a: px, b: px};
  });
  tela.addEventListener('pointermove', function (e) {
    var px = [e.offsetX, e.offsetY];
    if (panning) {
      var dx = px[0] - panning.px[0], dy = px[1] - panning.px[1];
      if (Math.abs(dx) + Math.abs(dy) > 3) panning.mosso = true;
      vista.cx = panning.cx - dx / vista.scala; vista.cy = panning.cy + dy / vista.scala; disegna(); return;
    }
    mouse.px = px; mouse.mm = puntoCursore(px);
    if (finestra) finestra.b = px;
    if (attesa && attesa.req.anteprima) { try { anteprima = attesa.req.anteprima(snapAttivo ? mouse.mm : cad.applicaOrto(mouse.mm, attesa.req.base)) || []; } catch (er) { anteprima = []; } }
    $('coord').textContent = mouse.mm[0].toFixed(2) + ', ' + mouse.mm[1].toFixed(2) + (snapAttivo ? '   · ' + snapAttivo.k.toUpperCase() : '');
    disegna();
  });
  tela.addEventListener('pointerup', function () {
    if (panning) { var p = panning; panning = null; if (p.destro && !p.mosso) invia(''); return; }
    if (!finestra) return;
    var f = finestra; finestra = null;
    if (Math.abs(f.a[0] - f.b[0]) + Math.abs(f.a[1] - f.b[1]) > 4) {
      var a = aMm(f.a), b = aMm(f.b), lo = [Math.min(a[0], b[0]), Math.min(a[1], b[1])], hi = [Math.max(a[0], b[0]), Math.max(a[1], b[1])];
      var interseca = f.b[0] < f.a[0];       // da destra a sinistra: anche gli oggetti toccati (come AutoCAD)
      S.entita.forEach(function (e) {
        var ok = G.dentroFinestra(e, lo, hi);
        if (!ok && interseca) { var bb = G.estensione([e]); ok = bb && bb.lo[0] <= hi[0] && bb.hi[0] >= lo[0] && bb.lo[1] <= hi[1] && bb.hi[1] >= lo[1]; }
        if (ok && S.sel.indexOf(e.id) < 0) S.sel.push(e.id);
      });
    } else if (!selezionando) S.sel = [];
    disegna();
  });
  tela.addEventListener('wheel', function (e) {
    e.preventDefault();
    var prima = aMm([e.offsetX, e.offsetY]); vista.scala = Math.max(0.005, Math.min(500, vista.scala * Math.exp(-e.deltaY * 0.0015)));
    var dopo = aMm([e.offsetX, e.offsetY]); vista.cx += prima[0] - dopo[0]; vista.cy += prima[1] - dopo[1]; disegna();
  }, {passive: false});
  tela.addEventListener('dblclick', function (e) { if (e.button === 1) zoomEstensioni(); });
  tela.addEventListener('pointerleave', function () { mouse.dentro = false; disegna(); });
  tela.addEventListener('pointerenter', function () { mouse.dentro = true; });

  // ── disegno della tavola ──
  function resize() { var r = tela.getBoundingClientRect(); tela.width = Math.floor(r.width * devicePixelRatio); tela.height = Math.floor(r.height * devicePixelRatio); disegna(); }
  function linea(a, b) { var p = aPx(a), q = aPx(b); ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); }
  function traccia(e) {
    ctx.beginPath();
    if (e.t === 'line') linea(e.a, e.b);
    else if (e.t === 'pline') { var p0 = aPx(e.pts[0]); ctx.moveTo(p0[0], p0[1]); e.pts.slice(1).forEach(function (p) { var q = aPx(p); ctx.lineTo(q[0], q[1]); }); if (e.closed) ctx.closePath(); }
    else if (e.t === 'circle') { var c = aPx(e.c); ctx.arc(c[0], c[1], e.r * vista.scala, 0, 2 * Math.PI); }
    else if (e.t === 'arc') { var c2 = aPx(e.c); ctx.arc(c2[0], c2[1], e.r * vista.scala, -e.a0 * Math.PI / 180, -(e.a0 + G.sweep(e)) * Math.PI / 180, true); }
    else if (e.t === 'dim') { quota(e); return; }
    else if (e.t === 'text') { var p = aPx(e.p); ctx.save(); ctx.font = Math.max(8, e.h * vista.scala) + 'px system-ui'; ctx.fillStyle = ctx.strokeStyle; ctx.fillText(e.testo, p[0], p[1]); ctx.restore(); return; }
    ctx.stroke();
  }
  function quota(e) {
    var dx = e.b[0] - e.a[0], dy = e.b[1] - e.a[1], L = Math.hypot(dx, dy) || 1, ux = dx / L, uy = dy / L;
    var off = (e.o[0] - e.a[0]) * -uy + (e.o[1] - e.a[1]) * ux, A = [e.a[0] - uy * off, e.a[1] + ux * off], B = [e.b[0] - uy * off, e.b[1] + ux * off];
    ctx.save(); ctx.strokeStyle = '#7fe0a8'; ctx.fillStyle = '#7fe0a8'; ctx.lineWidth = 1;
    ctx.beginPath(); linea(e.a, A); linea(e.b, B); linea(A, B); ctx.stroke();
    var pa = aPx(A), pb = aPx(B), g = Math.atan2(pb[1] - pa[1], pb[0] - pa[0]);
    [[pa, g], [pb, g + Math.PI]].forEach(function (x) { ctx.beginPath(); ctx.moveTo(x[0][0], x[0][1]); ctx.lineTo(x[0][0] + 9 * Math.cos(x[1] + .3), x[0][1] + 9 * Math.sin(x[1] + .3)); ctx.lineTo(x[0][0] + 9 * Math.cos(x[1] - .3), x[0][1] + 9 * Math.sin(x[1] - .3)); ctx.fill(); });
    ctx.translate((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2); var rot = g; if (rot > Math.PI / 2 || rot < -Math.PI / 2) rot += Math.PI; ctx.rotate(rot);
    ctx.font = '12px system-ui'; ctx.textAlign = 'center'; ctx.fillText(e.testo || G.dist(e.a, e.b).toFixed(2), 0, -5); ctx.restore();
  }
  function griglia(w, h) {
    var passo = S.passo; while (passo * vista.scala < 12) passo *= 5; while (passo * vista.scala > 120) passo /= 5;
    var a = aMm([0, h]), b = aMm([w, 0]);
    ctx.strokeStyle = 'rgba(120,160,200,.10)'; ctx.lineWidth = 1; ctx.beginPath();
    for (var x = Math.floor(a[0] / passo) * passo; x <= b[0]; x += passo) linea([x, a[1]], [x, b[1]]);
    for (var y = Math.floor(a[1] / passo) * passo; y <= b[1]; y += passo) linea([a[0], y], [b[0], y]);
    ctx.stroke();
    ctx.strokeStyle = 'rgba(255,90,90,.45)'; ctx.beginPath(); linea([a[0], 0], [b[0], 0]); ctx.stroke();
    ctx.strokeStyle = 'rgba(90,255,120,.45)'; ctx.beginPath(); linea([0, a[1]], [0, b[1]]); ctx.stroke();
  }
  function disegna() {
    var w = tela.clientWidth, h = tela.clientHeight;
    ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    ctx.fillStyle = '#0d1b2a'; ctx.fillRect(0, 0, w, h);
    griglia(w, h);
    ctx.lineWidth = 1.4;
    S.entita.forEach(function (e) {
      var sel = S.sel.indexOf(e.id) >= 0;
      ctx.setLineDash(sel ? [6, 4] : []); ctx.strokeStyle = sel ? '#4fb3ff' : '#f2f6fb'; traccia(e);
    });
    ctx.setLineDash([5, 4]); ctx.strokeStyle = '#ffd34d';
    anteprima.forEach(traccia);
    ctx.setLineDash([]);
    if (finestra) {
      var f = finestra, cross = f.b[0] < f.a[0];
      ctx.fillStyle = cross ? 'rgba(80,200,120,.12)' : 'rgba(80,140,255,.12)'; ctx.strokeStyle = cross ? '#50c878' : '#508cff';
      ctx.setLineDash(cross ? [5, 4] : []); ctx.fillRect(f.a[0], f.a[1], f.b[0] - f.a[0], f.b[1] - f.a[1]); ctx.strokeRect(f.a[0], f.a[1], f.b[0] - f.a[0], f.b[1] - f.a[1]); ctx.setLineDash([]);
    }
    if (snapAttivo) {
      var s = aPx(snapAttivo.p); ctx.strokeStyle = '#3dff8a'; ctx.lineWidth = 2; ctx.beginPath();
      if (snapAttivo.k === 'centro') ctx.arc(s[0], s[1], 7, 0, 7);
      else if (snapAttivo.k === 'medio') { ctx.moveTo(s[0], s[1] - 8); ctx.lineTo(s[0] + 8, s[1] + 6); ctx.lineTo(s[0] - 8, s[1] + 6); ctx.closePath(); }
      else if (snapAttivo.k === 'intersezione') { ctx.moveTo(s[0] - 7, s[1] - 7); ctx.lineTo(s[0] + 7, s[1] + 7); ctx.moveTo(s[0] + 7, s[1] - 7); ctx.lineTo(s[0] - 7, s[1] + 7); }
      else if (snapAttivo.k === 'quadrante') { ctx.moveTo(s[0], s[1] - 8); ctx.lineTo(s[0] + 8, s[1]); ctx.lineTo(s[0], s[1] + 8); ctx.lineTo(s[0] - 8, s[1]); ctx.closePath(); }
      else ctx.rect(s[0] - 6, s[1] - 6, 12, 12);
      ctx.stroke(); ctx.lineWidth = 1;
    }
    if (mouse.dentro || attesa) {           // mirino come AutoCAD
      var m = aPx(mouse.mm); ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.beginPath();
      ctx.moveTo(m[0] - 2000, m[1]); ctx.lineTo(m[0] + 2000, m[1]); ctx.moveTo(m[0], m[1] - 2000); ctx.lineTo(m[0], m[1] + 2000); ctx.stroke();
      if (!attesa || attesa.req.tipo === 'entita' || selezionando) { ctx.strokeStyle = '#fff'; ctx.strokeRect(m[0] - 5, m[1] - 5, 10, 10); }
    }
    stato();
  }
  function stato() {
    [['b-orto', S.orto], ['b-snap', S.snap], ['b-osnap', S.osnap]].forEach(function (x) { $(x[0]).classList.toggle('on', !!x[1]); });
    $('n-oggetti').textContent = S.entita.length + ' oggetti' + (S.sel.length ? ' · ' + S.sel.length + ' selezionati' : '');
  }
  new ResizeObserver(resize).observe(tela);

  // ── 3D ──
  function mostra3d(j) {
    vista3d.mostra(j.mesh.triangles);
    $('dl-step').href = j.exports.step; $('dl-stl').href = j.exports.stl; $('download3d').hidden = false;
    $('info3d').textContent = 'Ingombro ' + j.mesh.bounds.x + ' × ' + j.mesh.bounds.y + ' × ' + j.mesh.bounds.z + ' mm · volume ' + Math.round(j.mesh.volume_mm3).toLocaleString('it-IT') + ' mm³';
    scrivi('Solido creato: ' + $('info3d').textContent + '. Scarica STEP o STL qui a destra.');
  }
  async function solido(op, dati) {
    if (window.MCADP) {          // la tavola diventa la base del progetto: le lavorazioni già decise restano
      scrivi('Costruisco il solido 3D…');
      await window.MCADP.impostaBase(op, dati);
      return;
    }
    scrivi('Costruisco il solido 3D…');
    var r = await fetch('/api/disegno/solido', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': CSRF},
      body: JSON.stringify(Object.assign({op: op, nome: $('nome-pezzo').value || ('Disegno ' + op)}, dati))});
    var j = await r.json().catch(function () { return {error: 'Risposta non valida dal server'}; });
    if (r.status === 401) { location.href = '/login?expired=1'; return; }
    if (!r.ok) throw new Error(j.error || 'Errore del motore 3D');
    mostra3d(j);
    if (j.avviso) scrivi('⚠ ' + j.avviso);
  }

  // ── pulsanti della barra ──
  document.querySelectorAll('[data-cmd]').forEach(function (b) {
    b.addEventListener('click', function () {
      if (attesa || selezionando) annulla();
      setTimeout(function () { cad.esegui(b.getAttribute('data-cmd')); input.focus(); }, 0);
    });
  });
  $('b-orto').onclick = function () { S.orto = !S.orto; stato(); input.focus(); };
  $('b-snap').onclick = function () { S.snap = !S.snap; stato(); input.focus(); };
  $('b-osnap').onclick = function () { S.osnap = !S.osnap; stato(); input.focus(); };

  // elenco dei comandi
  var tab = $('elenco-comandi');
  Object.keys(window.CAD.COMANDI).forEach(function (k) {
    var c = window.CAD.COMANDI[k], tr = document.createElement('tr');
    tr.innerHTML = '<td><b></b></td><td></td><td></td>'; tr.children[0].firstChild.textContent = c[0][0];
    tr.children[1].textContent = c[0].slice(1).join(' · '); tr.children[2].textContent = c[1]; tab.appendChild(tr);
  });

  // ── memoria del disegno nel browser (comodità: il disegno resta se ricarichi la pagina) ──
  function salvaLocale() { try { localStorage.setItem('mcad-disegno', JSON.stringify(S.entita)); } catch (e) {} }
  try { var vecchio = JSON.parse(localStorage.getItem('mcad-disegno') || '[]'); if (Array.isArray(vecchio) && vecchio.length) { cad.carica(vecchio, true); S.annulla = []; scrivi('Ripreso il disegno lasciato in questo browser (' + vecchio.length + ' oggetti). NUOVO per ripartire da zero.'); } } catch (e) {}

  // ── dal reverse engineering da foto ──
  window.addEventListener('mcad:entita', function (ev) {
    var d = ev.detail || {};
    cad.carica(d.entita || [], !!d.sostituisci);
    zoomEstensioni();
    scrivi(d.messaggio || 'Profilo caricato.');
    input.focus();
  });
  window.MCAD = {cad: cad, scrivi: scrivi, zoomEstensioni: zoomEstensioni, aPx: aPx, mostra3d: mostra3d};
  scrivi('MASTER CAD AI · Disegno. Scrivi un comando come in AutoCAD (es. L, C, REC, PL, TR, F, O, EXT) oppure F1 per l’elenco.');
  setTimeout(zoomEstensioni, 50);
  input.focus();
})();

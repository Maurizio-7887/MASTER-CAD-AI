(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var S = MC.leggi('mcad-generativo') || {viti: [], carichi: [], zone: []}, modo = 'vite', zonaInizio = null, ultimo = null;
  var aperto = MC.progetto();
  var dominio = aperto && aperto.base.tipo === 'estrudi' ? aperto.base.entita : null;
  $('g-nome').textContent = dominio ? MC.nome() : 'nessun pezzo piano aperto';
  $('g-usa').disabled = !dominio;
  $('g-usa').checked = !!dominio && !!S.usa;
  var NS = 'http://www.w3.org/2000/svg', svg = $('piano'), tr = null;

  function bordi() {
    if ($('g-usa').checked && dominio) {
      var xs = [], ys = [];
      dominio.forEach(function (e) {
        if (e.t === 'circle' || e.t === 'arc') { xs.push(e.c[0] - e.r, e.c[0] + e.r); ys.push(e.c[1] - e.r, e.c[1] + e.r); }
        else if (e.t === 'line') { xs.push(e.a[0], e.b[0]); ys.push(e.a[1], e.b[1]); }
        else if (e.pts) e.pts.forEach(function (p) { xs.push(p[0]); ys.push(p[1]); });
      });
      return [Math.min.apply(0, xs), Math.min.apply(0, ys), Math.max.apply(0, xs), Math.max.apply(0, ys)];
    }
    return [0, 0, Number($('g-l').value) || 100, Number($('g-h').value) || 60];
  }
  function el(tag, att) { var e = document.createElementNS(NS, tag); for (var k in att) e.setAttribute(k, att[k]); svg.appendChild(e); return e; }
  function disegna() {
    var b = bordi(), W = b[2] - b[0], H = b[3] - b[1], k = Math.min(360 / W, 260 / H);
    tr = {k: k, x0: b[0] - (400 / k - W) / 2, y1: b[3] + (300 / k - H) / 2};
    var P = function (x, y) { return [(x - tr.x0) * tr.k, (tr.y1 - y) * tr.k]; };
    svg.innerHTML = '';
    if ($('g-usa').checked && dominio) {
      dominio.forEach(function (e) {
        if (e.t === 'circle') { var c = P(e.c[0], e.c[1]); el('circle', {cx: c[0], cy: c[1], r: e.r * k, fill: '#e8f1fb', stroke: '#12324f', 'stroke-width': 1.5}); }
        else if (e.pts) el('polygon', {points: e.pts.map(function (p) { return P(p[0], p[1]).join(','); }).join(' '), fill: '#e8f1fb', stroke: '#12324f', 'stroke-width': 1.5});
        else if (e.t === 'line') { var a = P(e.a[0], e.a[1]), c2 = P(e.b[0], e.b[1]); el('line', {x1: a[0], y1: a[1], x2: c2[0], y2: c2[1], stroke: '#12324f', 'stroke-width': 1.5}); }
      });
    } else {
      var a = P(b[0], b[3]);
      el('rect', {x: a[0], y: a[1], width: W * k, height: H * k, fill: '#e8f1fb', stroke: '#12324f', 'stroke-width': 1.5});
    }
    S.zone.forEach(function (z) { var a = P(Math.min(z[0], z[2]), Math.max(z[1], z[3])); el('rect', {x: a[0], y: a[1], width: Math.abs(z[2] - z[0]) * k, height: Math.abs(z[3] - z[1]) * k, fill: 'rgba(210,10,10,.18)', stroke: '#d20a0a', 'stroke-dasharray': '4 3'}); });
    S.viti.forEach(function (v, i) { var c = P(v.x, v.y); el('circle', {cx: c[0], cy: c[1], r: 7, fill: '#188918'}); var t = el('text', {x: c[0] + 9, y: c[1] - 7, 'font-size': 11, fill: '#188918'}); t.textContent = 'V' + (i + 1) + ' ' + (v.vite || ''); });
    S.carichi.forEach(function (c, i) {
      var p = P(c.x, c.y), F = Math.hypot(c.fx || 0, c.fy || 0) || 1, dx = (c.fx || 0) / F * 40, dy = -(c.fy || 0) / F * 40;
      el('line', {x1: p[0] - dx, y1: p[1] - dy, x2: p[0], y2: p[1], stroke: '#0070f2', 'stroke-width': 3});
      el('circle', {cx: p[0], cy: p[1], r: c.d ? c.d / 2 * k : 4, fill: 'none', stroke: '#0070f2', 'stroke-width': 2});
      var t = el('text', {x: p[0] + 8, y: p[1] + 16, 'font-size': 11, fill: '#0070f2'}); t.textContent = 'F' + (i + 1) + ' ' + MC.num(F / 1000, 2) + ' kN';
    });
    tabelle();
    MC.scriviLocale('mcad-generativo', S);
  }
  function inp(arr, i, k, w) { return '<input data-a="' + arr + '" data-i="' + i + '" data-k="' + k + '" value="' + MC.esc(S[arr][i][k] == null ? '' : S[arr][i][k]) + '" style="width:' + (w || 64) + 'px">'; }
  function tabelle() {
    $('t-viti').innerHTML = S.viti.length ? '<tr><th>Vite</th><th>X</th><th>Y</th><th>Tipo</th><th></th></tr>' + S.viti.map(function (v, i) {
      return '<tr><td>V' + (i + 1) + '</td><td>' + inp('viti', i, 'x') + '</td><td>' + inp('viti', i, 'y') + '</td><td>' + inp('viti', i, 'vite', 54) + '</td><td><button class="btn sec" data-del="viti" data-i="' + i + '">✕</button></td></tr>'; }).join('') : '<tr><td class="sotto">Nessuna vite: clicca sulla sagoma con 🔩 Vite.</td></tr>';
    $('t-carichi').innerHTML = S.carichi.length ? '<tr><th>Carico</th><th>X</th><th>Y</th><th>Fx N</th><th>Fy N</th><th>Perno Ø</th><th></th></tr>' + S.carichi.map(function (c, i) {
      return '<tr><td>F' + (i + 1) + '</td><td>' + inp('carichi', i, 'x', 46) + '</td><td>' + inp('carichi', i, 'y', 46) + '</td><td>' + inp('carichi', i, 'fx', 58) + '</td><td>' + inp('carichi', i, 'fy', 58) + '</td><td>' + inp('carichi', i, 'd', 38) +
        '</td><td><button class="btn sec" data-del="carichi" data-i="' + i + '">✕</button></td></tr>'; }).join('') : '';
    $('t-zone').innerHTML = S.zone.length ? '<tr><th>Zona vietata</th><th colspan="4">X1, Y1 → X2, Y2</th><th></th></tr>' + S.zone.map(function (z, i) {
      return '<tr><td>Z' + (i + 1) + '</td><td colspan="4">' + z.map(function (v) { return MC.num(v, 1); }).join(' · ') + '</td><td><button class="btn sec" data-del="zone" data-i="' + i + '">✕</button></td></tr>'; }).join('') : '';
    document.querySelectorAll('[data-a]').forEach(function (x) {
      x.onchange = function () { var v = x.value.trim(); S[x.getAttribute('data-a')][x.getAttribute('data-i')][x.getAttribute('data-k')] = x.getAttribute('data-k') === 'vite' ? v.toUpperCase() : Number(v.replace(',', '.')) || 0; disegna(); };
    });
    document.querySelectorAll('[data-del]').forEach(function (x) { x.onclick = function () { S[x.getAttribute('data-del')].splice(Number(x.getAttribute('data-i')), 1); disegna(); }; });
  }
  svg.addEventListener('click', function (ev) {
    var r = svg.getBoundingClientRect(), sx = (ev.clientX - r.left) / r.width * 400, sy = (ev.clientY - r.top) / r.height * 300;
    var x = Math.round((sx / tr.k + tr.x0) * 2) / 2, y = Math.round((tr.y1 - sy / tr.k) * 2) / 2;
    if (modo === 'vite') S.viti.push({x: x, y: y, vite: 'M8'});
    else if (modo === 'carico') S.carichi.push({x: x, y: y, fx: 0, fy: -1000, d: 0});
    else if (!zonaInizio) { zonaInizio = [x, y]; MC.messaggio($('msg'), 'Clicca l\'angolo opposto della zona vietata.', 'info'); return; }
    else { S.zone.push([zonaInizio[0], zonaInizio[1], x, y]); zonaInizio = null; MC.messaggio($('msg'), ''); }
    disegna();
  });
  document.querySelectorAll('[data-modo]').forEach(function (b) {
    b.onclick = function () { modo = b.getAttribute('data-modo'); zonaInizio = null; document.querySelectorAll('[data-modo]').forEach(function (x) { x.classList.toggle('on', x === b); }); };
  });
  $('g-pulisci').onclick = function () { S = {viti: [], carichi: [], zone: []}; disegna(); };
  ['g-l', 'g-h'].forEach(function (id) { $(id).onchange = disegna; });
  $('g-usa').onchange = function () { S.usa = this.checked; $('g-rett').hidden = this.checked; disegna(); };
  $('g-rett').hidden = $('g-usa').checked;
  if (!S.viti.length && !S.carichi.length) {         // esempio di partenza: staffa con 2 viti M10 e un perno caricato
    S.viti = [{x: 12, y: 15, vite: 'M10'}, {x: 12, y: 65, vite: 'M10'}];
    S.carichi = [{x: 105, y: 40, fx: 0, fy: -6000, d: 12}];
  }
  disegna();

  $('g-calcola').onclick = async function () {
    var b = this;
    MC.occupato(b, true, 'Calcolo la forma (10–20 s)…');
    MC.messaggio($('msg'), '');
    var spec = {spessore: Number($('g-t').value), materiale: $('g-mat').value, sicurezza: Number($('g-sic').value) || 2,
      viti: S.viti, carichi: S.carichi, zone_vietate: S.zone};
    if ($('g-massa').value) spec.massa_max_g = Number($('g-massa').value);
    if ($('g-usa').checked && dominio) spec.dominio_entita = dominio; else { spec.larghezza = Number($('g-l').value); spec.altezza = Number($('g-h').value); }
    try {
      var r = await MC.api('/api/generativo', spec);
      ultimo = r;
      $('risultato').hidden = false;
      $('g-kpi').innerHTML = [['Massa', MC.num(r.massa_g, 0) + ' g'], ['Spessore', r.spessore + ' mm' + (r.spessore !== r.spessore_iniziale ? ' (da ' + r.spessore_iniziale + ')' : '')],
        ['Sicurezza', MC.num(r.sicurezza, 2) + ' (voluta ' + MC.num(r.sicurezza_voluta, 1) + ')'], ['Tensione max', MC.num(r.tensione_max, 0) + ' / ' + r.snervamento + ' MPa'],
        ['Freccia max', MC.num(r.spostamento_max_mm, 3) + ' mm']].map(function (x) { return '<div class="kpi-box"><small>' + x[0] + '</small><b style="font-size:17px">' + x[1] + '</b></div>'; }).join('');
      var c = $('densita'), d = r.densita, ctx = c.getContext('2d');
      c.width = d.nx; c.height = d.ny;
      var img = ctx.createImageData(d.nx, d.ny);
      for (var j = 0; j < d.ny; j++) for (var i = 0; i < d.nx; i++) { var v = 255 - Math.round(255 * d.valori[j * d.nx + i]), o = (j * d.nx + i) * 4; img.data[o] = v; img.data[o + 1] = v + (255 - v) * 0.15; img.data[o + 2] = 255 - (255 - v) * 0.4; img.data[o + 3] = 255; }
      ctx.putImageData(img, 0, 0);
      $('mappa').src = r.mappa_tensioni;
      $('g-avvisi').innerHTML = r.avvisi.map(function (a) { return '<li>' + MC.esc(a) + '</li>'; }).join('');
      MC.kpi('generativo', MC.num(r.massa_g, 0) + ' g', 'SF ' + MC.num(r.sicurezza, 1));
      $('risultato').scrollIntoView({behavior: 'smooth'});
    } catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
    finally { MC.occupato(b, false); }
  };
  $('g-usa-forma').onclick = function () {
    if (!ultimo) return;
    var p = JSON.parse(JSON.stringify(ultimo.progetto));
    p.nome = 'Pezzo ottimizzato ' + MC.num(ultimo.massa_g, 0) + ' g';
    p.uid = Math.random().toString(36).slice(2, 12);
    p.registro = [{quando: new Date().toISOString(), chi: MC.leggi('mcad-utente') || 'Ufficio tecnico', cosa: 'Forma generata da carichi e vincoli: ' +
      S.carichi.map(function (c) { return MC.num(Math.hypot(c.fx || 0, c.fy || 0), 0) + ' N'; }).join(', ') + ', ' + S.viti.length + ' viti, massa ' + MC.num(ultimo.massa_g, 0) + ' g, spessore ' + ultimo.spessore + ' mm',
      norma: 'Ottimizzazione topologica SIMP 2D, verifica von Mises', verifica: 'Sicurezza ' + MC.num(ultimo.sicurezza, 2) + ' su snervamento ' + ultimo.snervamento + ' MPa'}];
    if (MC.progetto() && !confirm('Il pezzo aperto verrà sostituito dalla forma ottimizzata. Continuo?')) return;
    MC.salvaProgetto(p);
    var tav = p.base.entita.slice();
    p.lavorazioni.forEach(function (l) { if (l.tipo === 'foro') tav.push({t: 'circle', c: [l.x, l.y], r: l.d / 2}); });
    MC.scriviLocale('mcad-disegno', tav);
    location.href = '/disegno#costruisci';
  };
})();

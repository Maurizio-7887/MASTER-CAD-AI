/* MASTER CAD AI · geometria 2D del Disegno (come AutoCAD): entità, trasformazioni, intersezioni,
   OFFSET, RACCORDO, CIMA, TAGLIA, ESTENDI. Puro JavaScript, nessuna dipendenza: testabile con Node.
   Entità (mm):
     {t:'line',a:[x,y],b:[x,y]}  {t:'circle',c:[x,y],r}  {t:'arc',c:[x,y],r,a0,a1}  (gradi, antiorario)
     {t:'pline',pts:[[x,y]...],closed}  {t:'dim',a:[x,y],b:[x,y],o:[x,y],testo}  {t:'text',p:[x,y],h,testo} */
(function (root) {
  'use strict';
  var EPS = 1e-9, TOL = 1e-6;
  var rad = function (g) { return g * Math.PI / 180; }, deg = function (r) { return r * 180 / Math.PI; };
  var norm360 = function (a) { a = a % 360; return a < 0 ? a + 360 : a; };
  var dist = function (p, q) { return Math.hypot(q[0] - p[0], q[1] - p[1]); };
  var ang = function (p, q) { return norm360(deg(Math.atan2(q[1] - p[1], q[0] - p[0]))); };
  var polare = function (p, d, g) { return [p[0] + d * Math.cos(rad(g)), p[1] + d * Math.sin(rad(g))]; };
  var round = function (v) { return Math.round(v * 1e6) / 1e6; };
  var rp = function (p) { return [round(p[0]), round(p[1])]; };
  var copia = function (o) { return JSON.parse(JSON.stringify(o)); };
  var puntoArco = function (e, g) { return polare(e.c, e.r, g); };
  var sweep = function (e) { var s = norm360(e.a1 - e.a0); return s < TOL ? 360 : s; };
  var angoloSuArco = function (e, g) { return norm360(g - e.a0) <= sweep(e) + 1e-7; };

  // ── trasformazioni (SPOSTA, RUOTA, SCALA, SPECCHIO) ──
  function trasforma(e, f, specchia) {
    e = copia(e);
    var tp = function (p) { return rp(f(p)); };
    if (e.t === 'line') { e.a = tp(e.a); e.b = tp(e.b); }
    else if (e.t === 'pline') { e.pts = e.pts.map(tp); }
    else if (e.t === 'dim') { e.a = tp(e.a); e.b = tp(e.b); e.o = tp(e.o); }
    else if (e.t === 'text') { e.p = tp(e.p); }
    else if (e.t === 'circle' || e.t === 'arc') {
      var c = e.c, nc = tp(c), p0 = e.t === 'arc' ? puntoArco(e, e.a0) : [c[0] + e.r, c[1]], q0 = f(p0);
      e.r = round(dist(nc, q0));
      if (e.t === 'arc') {
        var p1 = f(puntoArco(e, e.a1)), A0 = ang(nc, q0), A1 = ang(nc, p1);
        if (specchia) { e.a0 = round(A1); e.a1 = round(A0); } else { e.a0 = round(A0); e.a1 = round(A1); }
      }
      e.c = nc;
    }
    return e;
  }
  var sposta = function (e, dx, dy) { return trasforma(e, function (p) { return [p[0] + dx, p[1] + dy]; }); };
  var ruota = function (e, b, g) { var c = Math.cos(rad(g)), s = Math.sin(rad(g)); return trasforma(e, function (p) { var x = p[0] - b[0], y = p[1] - b[1]; return [b[0] + x * c - y * s, b[1] + x * s + y * c]; }); };
  var scala = function (e, b, k) { return trasforma(e, function (p) { return [b[0] + (p[0] - b[0]) * k, b[1] + (p[1] - b[1]) * k]; }); };
  function specchia(e, a, b) {
    var dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy;
    return trasforma(e, function (p) { var t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2, fx = a[0] + t * dx, fy = a[1] + t * dy; return [2 * fx - p[0], 2 * fy - p[1]]; }, true);
  }

  // ── punti notevoli per lo snap ad oggetto (OSNAP) ──
  function puntiSnap(e) {
    var out = [];
    if (e.t === 'line') { out.push({p: e.a, k: 'fine'}, {p: e.b, k: 'fine'}, {p: [(e.a[0] + e.b[0]) / 2, (e.a[1] + e.b[1]) / 2], k: 'medio'}); }
    else if (e.t === 'pline') {
      e.pts.forEach(function (p) { out.push({p: p, k: 'fine'}); });
      segmentiPline(e).forEach(function (s) { out.push({p: [(s.a[0] + s.b[0]) / 2, (s.a[1] + s.b[1]) / 2], k: 'medio'}); });
    }
    else if (e.t === 'circle') { out.push({p: e.c, k: 'centro'}); [0, 90, 180, 270].forEach(function (g) { out.push({p: polare(e.c, e.r, g), k: 'quadrante'}); }); }
    else if (e.t === 'arc') { out.push({p: e.c, k: 'centro'}, {p: puntoArco(e, e.a0), k: 'fine'}, {p: puntoArco(e, e.a1), k: 'fine'}, {p: puntoArco(e, e.a0 + sweep(e) / 2), k: 'medio'}); }
    return out;
  }
  function segmentiPline(e) {
    var s = [];
    for (var i = 0; i + 1 < e.pts.length; i++) s.push({t: 'line', a: e.pts[i], b: e.pts[i + 1]});
    if (e.closed && e.pts.length > 2) s.push({t: 'line', a: e.pts[e.pts.length - 1], b: e.pts[0]});
    return s;
  }
  // entità «semplici» (linee, archi, cerchi) per intersezioni
  function primitive(e) { return e.t === 'pline' ? segmentiPline(e) : (e.t === 'line' || e.t === 'circle' || e.t === 'arc') ? [e] : []; }

  // ── distanza punto-entità (per selezionare col clic) ──
  function distSeg(p, a, b) {
    var dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy;
    var t = l2 < EPS ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2));
    return dist(p, [a[0] + t * dx, a[1] + t * dy]);
  }
  function distanza(p, e) {
    if (e.t === 'line') return distSeg(p, e.a, e.b);
    if (e.t === 'pline') return Math.min.apply(null, segmentiPline(e).map(function (s) { return distSeg(p, s.a, s.b); }));
    if (e.t === 'circle') return Math.abs(dist(p, e.c) - e.r);
    if (e.t === 'arc') return angoloSuArco(e, ang(e.c, p)) ? Math.abs(dist(p, e.c) - e.r) : Math.min(dist(p, puntoArco(e, e.a0)), dist(p, puntoArco(e, e.a1)));
    if (e.t === 'dim') return Math.min(distSeg(p, e.a, e.b), dist(p, e.o));
    if (e.t === 'text') return dist(p, e.p);
    return Infinity;
  }
  function estensione(lista) {
    var lo = [Infinity, Infinity], hi = [-Infinity, -Infinity];
    var add = function (p) { lo[0] = Math.min(lo[0], p[0]); lo[1] = Math.min(lo[1], p[1]); hi[0] = Math.max(hi[0], p[0]); hi[1] = Math.max(hi[1], p[1]); };
    lista.forEach(function (e) {
      if (e.t === 'line') { add(e.a); add(e.b); }
      else if (e.t === 'pline') e.pts.forEach(add);
      else if (e.t === 'circle' || e.t === 'arc') { add([e.c[0] - e.r, e.c[1] - e.r]); add([e.c[0] + e.r, e.c[1] + e.r]); }
      else if (e.t === 'dim') { add(e.a); add(e.b); add(e.o); }
      else if (e.t === 'text') add(e.p);
    });
    return lo[0] === Infinity ? null : {lo: lo, hi: hi};
  }
  function dentroFinestra(e, lo, hi) {
    var b = estensione([e]); return !!b && b.lo[0] >= lo[0] && b.lo[1] >= lo[1] && b.hi[0] <= hi[0] && b.hi[1] <= hi[1];
  }

  // ── intersezioni ──
  function interLL(a1, a2, b1, b2, infinite) {
    var d = (a2[0] - a1[0]) * (b2[1] - b1[1]) - (a2[1] - a1[1]) * (b2[0] - b1[0]);
    if (Math.abs(d) < EPS) return [];
    var t = ((b1[0] - a1[0]) * (b2[1] - b1[1]) - (b1[1] - a1[1]) * (b2[0] - b1[0])) / d;
    var u = ((b1[0] - a1[0]) * (a2[1] - a1[1]) - (b1[1] - a1[1]) * (a2[0] - a1[0])) / d;
    if (!infinite && (t < -TOL || t > 1 + TOL || u < -TOL || u > 1 + TOL)) return [];
    return [{p: [a1[0] + t * (a2[0] - a1[0]), a1[1] + t * (a2[1] - a1[1])], t: t, u: u}];
  }
  function interLC(a, b, c, r, infinite) {
    var dx = b[0] - a[0], dy = b[1] - a[1], fx = a[0] - c[0], fy = a[1] - c[1];
    var A = dx * dx + dy * dy, B = 2 * (fx * dx + fy * dy), C = fx * fx + fy * fy - r * r, D = B * B - 4 * A * C;
    if (D < -EPS || A < EPS) return [];
    D = Math.sqrt(Math.max(0, D));
    return [(-B - D) / (2 * A), (-B + D) / (2 * A)].filter(function (t, i, arr) { return (infinite || (t >= -TOL && t <= 1 + TOL)) && (i === 0 || Math.abs(t - arr[0]) > 1e-9); })
      .map(function (t) { return {p: [a[0] + t * dx, a[1] + t * dy], t: t}; });
  }
  function interCC(c1, r1, c2, r2) {
    var d = dist(c1, c2);
    if (d < EPS || d > r1 + r2 + TOL || d < Math.abs(r1 - r2) - TOL) return [];
    var a = (r1 * r1 - r2 * r2 + d * d) / (2 * d), h = Math.sqrt(Math.max(0, r1 * r1 - a * a));
    var mx = c1[0] + a * (c2[0] - c1[0]) / d, my = c1[1] + a * (c2[1] - c1[1]) / d;
    var out = [[mx + h * (c2[1] - c1[1]) / d, my - h * (c2[0] - c1[0]) / d]];
    if (h > 1e-9) out.push([mx - h * (c2[1] - c1[1]) / d, my + h * (c2[0] - c1[0]) / d]);
    return out.map(function (p) { return {p: p}; });
  }
  // intersezioni fra due primitive (punti su entrambe)
  function interseca(e, f) {
    var sulCurvo = function (x, p) { return x.t === 'circle' || angoloSuArco(x, ang(x.c, p)); };
    if (e.t === 'line' && f.t === 'line') return interLL(e.a, e.b, f.a, f.b).map(function (x) { return x.p; });
    if (e.t === 'line') return interLC(e.a, e.b, f.c, f.r).map(function (x) { return x.p; }).filter(function (p) { return sulCurvo(f, p); });
    if (f.t === 'line') return interseca(f, e);
    return interCC(e.c, e.r, f.c, f.r).map(function (x) { return x.p; }).filter(function (p) { return sulCurvo(e, p) && sulCurvo(f, p); });
  }

  // ── OFFSET ──
  function offsetPunti(pts, d, chiusa) {
    var n = pts.length, out = [];
    var lato = function (a, b) { var dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1; return [-dy / l * d, dx / l * d]; };
    for (var i = 0; i < n; i++) {
      var prev = i > 0 ? pts[i - 1] : (chiusa ? pts[n - 1] : null), next = i < n - 1 ? pts[i + 1] : (chiusa ? pts[0] : null), p = pts[i];
      if (!prev) { var o = lato(p, next); out.push([p[0] + o[0], p[1] + o[1]]); continue; }
      if (!next) { var o2 = lato(prev, p); out.push([p[0] + o2[0], p[1] + o2[1]]); continue; }
      var o1 = lato(prev, p), o3 = lato(p, next);
      var x = interLL([prev[0] + o1[0], prev[1] + o1[1]], [p[0] + o1[0], p[1] + o1[1]], [p[0] + o3[0], p[1] + o3[1]], [next[0] + o3[0], next[1] + o3[1]], true);
      out.push(x.length ? x[0].p : [p[0] + o1[0], p[1] + o1[1]]);
    }
    return out.map(rp);
  }
  // distanza con segno: positiva = a sinistra della direzione (o fuori dal cerchio)
  function offset(e, d, lato) {
    if (e.t === 'line') {
      var s = latoDi(e.a, e.b, lato) ? d : -d, o = offsetPunti([e.a, e.b], s, false);
      return {t: 'line', a: o[0], b: o[1]};
    }
    if (e.t === 'circle' || e.t === 'arc') {
      var fuori = dist(e.c, lato) > e.r, r = e.r + (fuori ? d : -d);
      if (r <= TOL) throw new Error('Offset impossibile: il raggio diventerebbe nullo');
      var n = copia(e); n.r = round(r); return n;
    }
    if (e.t === 'pline') {
      var pts = e.pts, k = 0, best = Infinity;
      segmentiPline(e).forEach(function (sg, i) { var dd = distSeg(lato, sg.a, sg.b); if (dd < best) { best = dd; k = i; } });
      var sg = segmentiPline(e)[k], sgn = latoDi(sg.a, sg.b, lato) ? d : -d;
      return {t: 'pline', pts: offsetPunti(pts, sgn, e.closed), closed: e.closed};
    }
    throw new Error('OFFSET: seleziona una linea, un cerchio, un arco o una polilinea');
  }
  function latoDi(a, b, p) { return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) > 0; }

  // ── RACCORDO e CIMA fra due linee ──
  function raccordo(l1, p1, l2, p2, r) {
    var x = interLL(l1.a, l1.b, l2.a, l2.b, true);
    if (!x.length) throw new Error('Le due linee sono parallele');
    var X = x[0].p;
    // di ogni linea resta la parte dalla quale si è cliccato
    var A = estremoVerso(l1, X, p1), B = estremoVerso(l2, X, p2);
    if (r <= TOL) return {linee: [{t: 'line', a: rp(A), b: rp(X)}, {t: 'line', a: rp(B), b: rp(X)}], arco: null};
    var ga = ang(X, A), gb = ang(X, B), meta = norm360(gb - ga); if (meta > 180) meta -= 360;
    var mezzo = Math.abs(meta) / 2;
    if (mezzo < 0.01 || mezzo > 89.99) throw new Error('Angolo non adatto al raccordo');
    var t = r / Math.tan(rad(mezzo));
    if (t > dist(X, A) + TOL || t > dist(X, B) + TOL) throw new Error('Raggio troppo grande per queste linee');
    var T1 = polare(X, t, ga), T2 = polare(X, t, gb), bis = ga + meta / 2, C = polare(X, r / Math.sin(rad(mezzo)), bis);
    var a0 = ang(C, T1), a1 = ang(C, T2);
    if (norm360(a1 - a0) > 180) { var tmp = a0; a0 = a1; a1 = tmp; }
    return {linee: [{t: 'line', a: rp(A), b: rp(T1)}, {t: 'line', a: rp(B), b: rp(T2)}], arco: {t: 'arc', c: rp(C), r: round(r), a0: round(a0), a1: round(a1)}};
  }
  // estremo della linea che resta (dalla parte del clic rispetto all'intersezione)
  function estremoVerso(l, X, p) {
    var ta = (l.a[0] - X[0]) * (p[0] - X[0]) + (l.a[1] - X[1]) * (p[1] - X[1]);
    var tb = (l.b[0] - X[0]) * (p[0] - X[0]) + (l.b[1] - X[1]) * (p[1] - X[1]);
    return (ta >= tb) ? l.a : l.b;
  }
  function cima(l1, p1, l2, p2, d1, d2) {
    var x = interLL(l1.a, l1.b, l2.a, l2.b, true);
    if (!x.length) throw new Error('Le due linee sono parallele');
    var X = x[0].p, A = estremoVerso(l1, X, p1), B = estremoVerso(l2, X, p2);
    if (d1 > dist(X, A) + TOL || d2 > dist(X, B) + TOL) throw new Error('Distanza di cima troppo grande');
    var T1 = polare(X, d1, ang(X, A)), T2 = polare(X, d2, ang(X, B));
    return {linee: [{t: 'line', a: rp(A), b: rp(T1)}, {t: 'line', a: rp(B), b: rp(T2)}], smusso: d1 + d2 > TOL ? {t: 'line', a: rp(T1), b: rp(T2)} : null};
  }

  // ── TAGLIA (modalità rapida: taglia fino alle intersezioni più vicine con gli altri oggetti) ──
  function taglia(e, p, altri) {
    var tagli = [];
    altri.forEach(function (o) { primitive(o).forEach(function (q) { primitive(e).forEach(function (s) { interseca(s, q).forEach(function (x) { tagli.push(x); }); }); }); });
    if (e.t === 'line') {
      var L = dist(e.a, e.b), tp = proiezione(e, p), ts = tagli.map(function (x) { return proiezione(e, x); }).filter(function (t) { return t > TOL && t < L - TOL; });
      var prima = ts.filter(function (t) { return t < tp; }), dopo = ts.filter(function (t) { return t > tp; });
      if (!prima.length && !dopo.length) return null;
      var u = function (t) { return rp([e.a[0] + (e.b[0] - e.a[0]) * t / L, e.a[1] + (e.b[1] - e.a[1]) * t / L]); };
      var out = [];
      if (prima.length) out.push({t: 'line', a: e.a, b: u(Math.max.apply(null, prima))});
      if (dopo.length) out.push({t: 'line', a: u(Math.min.apply(null, dopo)), b: e.b});
      return out;
    }
    if (e.t === 'circle' || e.t === 'arc') {
      var gp = ang(e.c, p), base = e.t === 'arc' ? e.a0 : gp, S = e.t === 'arc' ? sweep(e) : 360;
      var gs = tagli.map(function (x) { return norm360(ang(e.c, x) - base); }).filter(function (g) { return g > 1e-6 && g < S - 1e-6; });
      if (e.t === 'circle') {
        if (gs.length < 2) return null;
        gs.sort(function (a, b) { return a - b; });
        // il pezzo cliccato va da ultimo a primo (attorno a gp): resta l'arco complementare
        return [{t: 'arc', c: e.c, r: e.r, a0: round(norm360(base + gs[0])), a1: round(norm360(base + gs[gs.length - 1]))}];
      }
      var g = norm360(gp - base), prima2 = gs.filter(function (x) { return x < g; }), dopo2 = gs.filter(function (x) { return x > g; });
      if (!prima2.length && !dopo2.length) return null;
      var out2 = [];
      if (prima2.length) out2.push({t: 'arc', c: e.c, r: e.r, a0: e.a0, a1: round(norm360(base + Math.max.apply(null, prima2)))});
      if (dopo2.length) out2.push({t: 'arc', c: e.c, r: e.r, a0: round(norm360(base + Math.min.apply(null, dopo2))), a1: e.a1});
      return out2;
    }
    throw new Error('TAGLIA: funziona su linee, archi e cerchi (le polilinee vanno prima ESPLOSE)');
  }
  function proiezione(l, p) { var dx = l.b[0] - l.a[0], dy = l.b[1] - l.a[1], L = Math.hypot(dx, dy); return ((p[0] - l.a[0]) * dx + (p[1] - l.a[1]) * dy) / L; }

  // ── ESTENDI: allunga l'estremo più vicino al clic fino al primo oggetto ──
  function estendi(l, p, altri) {
    if (l.t !== 'line') throw new Error('ESTENDI: funziona sulle linee');
    var versoB = dist(p, l.b) < dist(p, l.a), da = versoB ? l.a : l.b, verso = versoB ? l.b : l.a;
    var L = dist(da, verso), migliore = null;
    altri.forEach(function (o) { primitive(o).forEach(function (q) {
      var xs = q.t === 'line' ? interLL(da, verso, q.a, q.b, true).filter(function (x) { return x.u >= -TOL && x.u <= 1 + TOL; }) :
        interLC(da, verso, q.c, q.r, true).filter(function (x) { return q.t === 'circle' || angoloSuArco(q, ang(q.c, x.p)); });
      xs.forEach(function (x) { var t = x.t * L; if (t > L + TOL && (migliore === null || t < migliore.t)) migliore = {t: t, p: x.p}; });
    }); });
    if (!migliore) return null;
    return versoB ? {t: 'line', a: l.a, b: rp(migliore.p)} : {t: 'line', a: rp(migliore.p), b: l.b};
  }

  function esplodi(e) {
    if (e.t === 'pline') return segmentiPline(e).map(function (s) { return {t: 'line', a: s.a, b: s.b}; });
    return [e];
  }
  function poligono(n, c, r, inscritto, g0) {
    var rr = inscritto ? r : r / Math.cos(Math.PI / n), pts = [];
    var start = g0 === undefined ? (inscritto ? 90 : 90 + 180 / n) : g0;
    for (var i = 0; i < n; i++) pts.push(rp(polare(c, rr, start + 360 * i / n)));
    return {t: 'pline', pts: pts, closed: true};
  }
  function arco3p(p1, p2, p3) {
    var ax = p1[0], ay = p1[1], bx = p2[0], by = p2[1], cx = p3[0], cy = p3[1];
    var d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by));
    if (Math.abs(d) < EPS) throw new Error('I tre punti sono allineati: non formano un arco');
    var ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d;
    var uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d;
    var c = [ux, uy], g1 = ang(c, p1), g2 = ang(c, p2), g3 = ang(c, p3);
    var antiorario = norm360(g2 - g1) < norm360(g3 - g1);
    return {t: 'arc', c: rp(c), r: round(dist(c, p1)), a0: round(antiorario ? g1 : g3), a1: round(antiorario ? g3 : g1)};
  }
  function areaPerimetro(e) {
    if (e.t === 'circle') return {area: Math.PI * e.r * e.r, perimetro: 2 * Math.PI * e.r};
    if (e.t === 'pline') {
      var p = e.pts, a = 0, l = 0;
      for (var i = 0; i < p.length; i++) { var q = p[(i + 1) % p.length]; if (i + 1 < p.length || e.closed) { a += p[i][0] * q[1] - q[0] * p[i][1]; l += dist(p[i], q); } }
      return {area: e.closed ? Math.abs(a) / 2 : 0, perimetro: l};
    }
    if (e.t === 'line') return {area: 0, perimetro: dist(e.a, e.b)};
    if (e.t === 'arc') return {area: 0, perimetro: rad(sweep(e)) * e.r};
    return {area: 0, perimetro: 0};
  }

  root.G2D = {dist: dist, ang: ang, polare: polare, norm360: norm360, rp: rp, copia: copia, sweep: sweep, puntoArco: puntoArco,
    sposta: sposta, ruota: ruota, scala: scala, specchia: specchia, puntiSnap: puntiSnap, segmentiPline: segmentiPline,
    distanza: distanza, estensione: estensione, dentroFinestra: dentroFinestra, interseca: interseca, primitive: primitive,
    offset: offset, raccordo: raccordo, cima: cima, taglia: taglia, estendi: estendi, esplodi: esplodi, poligono: poligono,
    arco3p: arco3p, areaPerimetro: areaPerimetro};
})(typeof window !== 'undefined' ? window : globalThis);

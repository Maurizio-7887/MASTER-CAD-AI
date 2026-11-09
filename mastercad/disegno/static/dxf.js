/* MASTER CAD AI · DXF: scrive un DXF R12 (lo apre AutoCAD, LibreCAD, DraftSight, FreeCAD)
   e legge LINE, CIRCLE, ARC, LWPOLYLINE, POLYLINE dai DXF fatti con AutoCAD. Unità: millimetri. */
(function (root) {
  'use strict';
  var n = function (v) { return (Math.round(v * 1e6) / 1e6).toString(); };
  function scrivi(entita) {
    var o = ['0', 'SECTION', '2', 'HEADER', '9', '$INSUNITS', '70', '4', '0', 'ENDSEC',
      '0', 'SECTION', '2', 'TABLES', '0', 'TABLE', '2', 'LAYER', '70', '2',
      '0', 'LAYER', '2', '0', '70', '0', '62', '7', '6', 'CONTINUOUS',
      '0', 'LAYER', '2', 'QUOTE', '70', '0', '62', '3', '6', 'CONTINUOUS', '0', 'ENDTAB', '0', 'ENDSEC',
      '0', 'SECTION', '2', 'ENTITIES'];
    var linea = function (a, b, layer) { o.push('0', 'LINE', '8', layer || '0', '10', n(a[0]), '20', n(a[1]), '30', '0', '11', n(b[0]), '21', n(b[1]), '31', '0'); };
    var testo = function (p, h, t, rot) { o.push('0', 'TEXT', '8', 'QUOTE', '10', n(p[0]), '20', n(p[1]), '30', '0', '40', n(h), '1', String(t), '50', n(rot || 0), '72', '1', '11', n(p[0]), '21', n(p[1]), '31', '0'); };
    entita.forEach(function (e) {
      if (e.t === 'line') linea(e.a, e.b);
      else if (e.t === 'circle') o.push('0', 'CIRCLE', '8', '0', '10', n(e.c[0]), '20', n(e.c[1]), '30', '0', '40', n(e.r));
      else if (e.t === 'arc') o.push('0', 'ARC', '8', '0', '10', n(e.c[0]), '20', n(e.c[1]), '30', '0', '40', n(e.r), '50', n(e.a0), '51', n(e.a1));
      else if (e.t === 'pline') {
        o.push('0', 'POLYLINE', '8', '0', '66', '1', '10', '0', '20', '0', '30', '0', '70', e.closed ? '1' : '0');
        e.pts.forEach(function (p) { o.push('0', 'VERTEX', '8', '0', '10', n(p[0]), '20', n(p[1]), '30', '0'); });
        o.push('0', 'SEQEND', '8', '0');
      } else if (e.t === 'dim') {
        var g = root.G2D, dx = e.b[0] - e.a[0], dy = e.b[1] - e.a[1], L = Math.hypot(dx, dy) || 1, ux = dx / L, uy = dy / L;
        var off = (e.o[0] - e.a[0]) * -uy + (e.o[1] - e.a[1]) * ux, A = [e.a[0] - uy * off, e.a[1] + ux * off], B = [e.b[0] - uy * off, e.b[1] + ux * off];
        linea(e.a, A, 'QUOTE'); linea(e.b, B, 'QUOTE'); linea(A, B, 'QUOTE');
        var rot = Math.atan2(dy, dx) * 180 / Math.PI; if (rot > 90 || rot <= -90) rot += 180;
        testo([(A[0] + B[0]) / 2 - uy * 2, (A[1] + B[1]) / 2 + ux * 2], e.h || 3.5, e.testo || (g ? g.dist(e.a, e.b).toFixed(2) : ''), rot);
      } else if (e.t === 'text') testo(e.p, e.h || 3.5, e.testo || '', 0);
    });
    o.push('0', 'ENDSEC', '0', 'EOF');
    return o.join('\r\n') + '\r\n';
  }
  function leggi(testo) {
    var righe = String(testo).replace(/\r/g, '').split('\n'), coppie = [];
    for (var i = 0; i + 1 < righe.length; i += 2) coppie.push([parseInt(righe[i].trim(), 10), righe[i + 1].trim()]);
    var out = [], i2 = 0, inEnt = false, saltate = {};
    var gruppo = function () { var g = {codici: []}; i2++; while (i2 < coppie.length && coppie[i2][0] !== 0) { g.codici.push(coppie[i2]); i2++; } return g; };
    var val = function (g, c) { for (var k = 0; k < g.codici.length; k++) if (g.codici[k][0] === c) return parseFloat(g.codici[k][1]); return 0; };
    while (i2 < coppie.length) {
      var c = coppie[i2];
      if (c[0] === 2 && c[1] === 'ENTITIES') { inEnt = true; i2++; continue; }
      if (c[0] === 0 && c[1] === 'ENDSEC') { inEnt = false; i2++; continue; }
      if (!inEnt || c[0] !== 0) { i2++; continue; }
      var tipo = c[1], g = gruppo();
      if (tipo === 'LINE') out.push({t: 'line', a: [val(g, 10), val(g, 20)], b: [val(g, 11), val(g, 21)]});
      else if (tipo === 'CIRCLE') out.push({t: 'circle', c: [val(g, 10), val(g, 20)], r: val(g, 40)});
      else if (tipo === 'ARC') out.push({t: 'arc', c: [val(g, 10), val(g, 20)], r: val(g, 40), a0: val(g, 50), a1: val(g, 51)});
      else if (tipo === 'LWPOLYLINE') {
        var pts = [], x = null;
        g.codici.forEach(function (k) { if (k[0] === 10) x = parseFloat(k[1]); if (k[0] === 20 && x !== null) { pts.push([x, parseFloat(k[1])]); x = null; } });
        out.push({t: 'pline', pts: pts, closed: (val(g, 70) & 1) === 1});
      } else if (tipo === 'POLYLINE') {
        var pl = {t: 'pline', pts: [], closed: (val(g, 70) & 1) === 1};
        while (i2 < coppie.length && coppie[i2][1] === 'VERTEX') { var v = gruppo(); pl.pts.push([val(v, 10), val(v, 20)]); }
        if (i2 < coppie.length && coppie[i2][1] === 'SEQEND') gruppo();
        out.push(pl);
      } else if (tipo !== 'SEQEND') saltate[tipo] = (saltate[tipo] || 0) + 1;
    }
    return {entita: out, saltate: saltate};
  }
  root.DXF = {scrivi: scrivi, leggi: leggi};
})(typeof window !== 'undefined' ? window : globalThis);

/* MASTER CAD AI · motore dei comandi come AutoCAD.
   Nomi italiani (AutoCAD in italiano), inglesi e alias: LINEA/LINE/L, CERCHIO/CIRCLE/C, …
   Coordinate come AutoCAD: 100,50 (assolute) · @30,0 (relative) · @50<45 (polari) · 40 (distanza diretta verso il cursore).
   INVIO o SPAZIO a vuoto ripete l'ultimo comando; ESC annulla.
   Il motore non conosce lo schermo: chiede input all'interfaccia (io.chiedi) e restituisce entità. Testabile con Node. */
(function (root) {
  'use strict';
  var G = root.G2D;

  // nome canonico → nomi accettati (italiano, inglese, alias) e descrizione
  var COMANDI = {
    LINEA: [['LINEA', 'LINE', 'L'], 'Linea da punto a punto. [Chiudi/Annulla]'],
    PLINEA: [['PLINEA', 'PLINE', 'PL'], 'Polilinea: una sola entità di più segmenti. [Chiudi/Annulla]'],
    CERCHIO: [['CERCHIO', 'CIRCLE', 'C', 'CE'], 'Cerchio da centro e raggio [Diametro]'],
    ARCO: [['ARCO', 'ARC', 'A'], 'Arco per tre punti [Centro]'],
    RETTANGOLO: [['RETTANGOLO', 'RECTANG', 'RECTANGLE', 'REC', 'RET'], 'Rettangolo da due angoli opposti (anche @larghezza,altezza)'],
    POLIGONO: [['POLIGONO', 'POLYGON', 'POL'], 'Poligono regolare [Inscritto/Circoscritto]'],
    CANCELLA: [['CANCELLA', 'ERASE', 'E', 'CA', 'DEL'], 'Cancella gli oggetti selezionati'],
    SPOSTA: [['SPOSTA', 'MOVE', 'M', 'S'], 'Sposta: punto base e secondo punto'],
    COPIA: [['COPIA', 'COPY', 'CO', 'CP'], 'Copia (anche più volte)'],
    RUOTA: [['RUOTA', 'ROTATE', 'RO'], 'Ruota attorno a un punto base'],
    SPECCHIO: [['SPECCHIO', 'MIRROR', 'MI'], 'Specchia rispetto a una linea [cancella origine Sì/No]'],
    SCALA: [['SCALA', 'SCALE', 'SC'], 'Scala rispetto a un punto base'],
    OFFSET: [['OFFSET', 'O', 'OF'], 'Copia parallela a una distanza'],
    RACCORDO: [['RACCORDO', 'FILLET', 'F', 'RA'], 'Raccorda due linee con un arco [Raggio]'],
    CIMA: [['CIMA', 'CHAMFER', 'CHA', 'CI'], 'Smussa l’angolo fra due linee [Distanze]'],
    TAGLIA: [['TAGLIA', 'TRIM', 'TR', 'TA'], 'Taglia il pezzo cliccato fino agli oggetti che lo incrociano'],
    ESTENDI: [['ESTENDI', 'EXTEND', 'EX', 'ES'], 'Allunga una linea fino al primo oggetto'],
    ESPLODI: [['ESPLODI', 'EXPLODE', 'X'], 'Divide polilinee e rettangoli in linee'],
    ANNULLA: [['ANNULLA', 'UNDO', 'U'], 'Annulla l’ultimo comando'],
    RIPRISTINA: [['RIPRISTINA', 'REDO'], 'Rifà il comando annullato'],
    ZOOM: [['ZOOM', 'Z'], 'Zoom [Estensioni/Tutto]'],
    DIST: [['DIST', 'DI', 'DISTANZA'], 'Misura distanza, ΔX, ΔY e angolo fra due punti'],
    ID: [['ID'], 'Coordinate di un punto'],
    LISTA: [['LISTA', 'LIST', 'LI', 'LS'], 'Dati degli oggetti selezionati (area, perimetro, raggio…)'],
    QUOTA: [['QUOTA', 'DIMLINEAR', 'DIMALIGNED', 'DLI', 'DAL', 'QUOTALIN'], 'Quota allineata fra due punti'],
    TESTO: [['TESTO', 'TEXT', 'DT', 'T'], 'Scrive un testo'],
    ORTO: [['ORTO', 'ORTHO', 'F8'], 'Modo orto acceso/spento (solo orizzontale/verticale)'],
    SNAP: [['SNAP', 'SN', 'F9', 'GRIGLIA', 'GRID'], 'Snap alla griglia acceso/spento [passo]'],
    OSNAP: [['OSNAP', 'OS', 'F3'], 'Snap ad oggetto (estremo, medio, centro, quadrante, intersezione) acceso/spento'],
    ESTRUDI: [['ESTRUDI', 'EXTRUDE', 'EXT'], '3D: estrude i contorni chiusi (i contorni interni diventano fori)'],
    RIVOLUZIONE: [['RIVOLUZIONE', 'REVOLVE', 'REV'], '3D: fa ruotare la mezza sezione attorno a un asse'],
    DXFOUT: [['DXFOUT', 'SALVADXF', 'ESPORTADXF', 'SALVA', 'SAVE', 'SAVEAS'], 'Scarica il disegno in DXF (si apre in AutoCAD)'],
    DXFIN: [['DXFIN', 'APRIDXF', 'APRI', 'OPEN', 'IMPORTA'], 'Apre un DXF fatto con AutoCAD'],
    NUOVO: [['NUOVO', 'NEW', 'CANCELLATUTTO'], 'Nuovo disegno vuoto'],
    SELEZIONATUTTO: [['SELEZIONATUTTO', 'TUTTO', 'ALL'], 'Seleziona tutti gli oggetti'],
    AIUTO: [['AIUTO', 'HELP', '?', 'COMANDI'], 'Elenco dei comandi']
  };
  var ALIAS = {};
  Object.keys(COMANDI).forEach(function (k) { COMANDI[k][0].forEach(function (a) { ALIAS[a] = k; }); });

  function Annullato() { this.message = '*Annulla*'; }

  function crea(io) {
    var s = {entita: [], sel: [], ultimo: [0, 0], orto: false, osnap: true, snap: false, passo: 10,
      raggio: 0, cima: [5, 5], offset: 10, estrudi: 10, ultimoComando: null, annulla: [], ripristina: [], prossimoId: 1, inCorso: null};

    var scrivi = function (t) { io.scrivi(t); };
    var nuovoId = function () { return s.prossimoId++; };
    var aggiungi = function (e) { e = G.copia(e); e.id = nuovoId(); s.entita.push(e); return e; };
    var perId = function (id) { for (var i = 0; i < s.entita.length; i++) if (s.entita[i].id === id) return s.entita[i]; return null; };
    var togli = function (ids) { s.entita = s.entita.filter(function (e) { return ids.indexOf(e.id) < 0; }); s.sel = s.sel.filter(function (i) { return ids.indexOf(i) < 0; }); };
    var sostituisci = function (id, nuove) { var i = s.entita.findIndex(function (e) { return e.id === id; }); var add = nuove.map(function (e) { e = G.copia(e); e.id = nuovoId(); return e; }); s.entita.splice.apply(s.entita, [i, 1].concat(add)); return add; };
    var istantanea = function () { s.annulla.push(JSON.stringify(s.entita)); if (s.annulla.length > 60) s.annulla.shift(); s.ripristina = []; };

    // ── interpretazione dell'input, come la riga di comando di AutoCAD ──
    function numero(t) { var v = parseFloat(String(t).replace(',', '.')); return isFinite(v) && /^\s*[-+]?(\d+([.,]\d*)?|[.,]\d+)\s*$/.test(t) ? v : null; }
    function interpretaPunto(t, base, cursore) {
      t = String(t).trim().replace(/\s+/g, '');
      var m;
      if ((m = /^@?([-+]?[\d.]+)<([-+]?[\d.]+)$/.exec(t)) && t.charAt(0) === '@') {
        var b = base || s.ultimo; return G.polare(b, parseFloat(m[1]), parseFloat(m[2]));
      }
      if ((m = /^(@?)([-+]?[\d.]+),([-+]?[\d.]+)$/.exec(t))) {
        var x = parseFloat(m[2]), y = parseFloat(m[3]);
        if (m[1]) { var b2 = base || s.ultimo; return [b2[0] + x, b2[1] + y]; }
        return [x, y];
      }
      // tastiera con virgola decimale: 12.5;30 oppure 12,5;30
      if ((m = /^(@?)([-+]?[\d.,]+);([-+]?[\d.,]+)$/.exec(t))) {
        var x2 = parseFloat(m[2].replace(',', '.')), y2 = parseFloat(m[3].replace(',', '.'));
        if (m[1]) { var b3 = base || s.ultimo; return [b3[0] + x2, b3[1] + y2]; }
        return [x2, y2];
      }
      var d = numero(t);
      if (d !== null && base) {      // distanza diretta: lungo la direzione del cursore (con ORTO, orizzontale/verticale)
        var dir = cursore ? G.ang(base, cursore) : 0;
        if (s.orto) dir = Math.round(dir / 90) * 90;
        return G.polare(base, d, dir);
      }
      return null;
    }
    function opzione(t, opzioni) {
      if (!opzioni) return null;
      var u = String(t).trim().toUpperCase();
      if (!u) return null;
      var chiavi = Object.keys(opzioni);
      for (var i = 0; i < chiavi.length; i++) {
        var k = chiavi[i], nome = opzioni[k].toUpperCase();
        if (u === k || nome.indexOf(u) === 0) return k;
      }
      return null;
    }
    function applicaOrto(p, base) {
      if (!s.orto || !base) return p;
      return Math.abs(p[0] - base[0]) >= Math.abs(p[1] - base[1]) ? [p[0], base[1]] : [base[0], p[1]];
    }
    function testoOpzioni(o) { return o ? ' [' + Object.keys(o).map(function (k) { return o[k]; }).join('/') + ']' : ''; }

    // chiede un dato finché è valido. Ritorna: punto [x,y] | numero | {opzione} | null (INVIO a vuoto)
    async function chiedi(req) {
      for (;;) {
        var r = await io.chiedi({prompt: req.prompt + testoOpzioni(req.opzioni) + (req.predefinito !== undefined ? ' <' + req.predefinito + '>' : '') + ':', tipo: req.tipo, base: req.base, anteprima: req.anteprima});
        if (r === null || r === undefined) throw new Annullato();
        if (r.annulla) throw new Annullato();
        if (r.clic) {
          if (req.tipo === 'punto') { var p = r.snap ? r.clic : applicaOrto(r.clic, req.base); return G.rp(p); }
          if (req.tipo === 'distanza' && req.base) return G.dist(req.base, r.snap ? r.clic : applicaOrto(r.clic, req.base));
          if (req.tipo === 'angolo' && req.base) return G.ang(req.base, r.clic);
          if (req.tipo === 'entita') { var e = vicina(r.clic, r.tolleranza); if (e) return {entita: e, punto: r.clic}; scrivi('Nessun oggetto trovato in quel punto.'); continue; }
          continue;
        }
        var t = String(r.testo === undefined ? '' : r.testo).trim();
        if (!t) { if (req.opzioni && req.predefinito !== undefined && req.opzioni[req.predefinito]) return {opzione: String(req.predefinito)}; if (req.predefinito !== undefined) return req.tipo === 'testo' || req.tipo === 'opzione' ? String(req.predefinito) : Number(req.predefinito); if (req.vuotoOk) return null; continue; }
        var op = opzione(t, req.opzioni);
        if (op) return {opzione: op};
        if (req.tipo === 'punto') { var q = interpretaPunto(t, req.base, r.cursore); if (q) return G.rp(q); scrivi('Punto non valido: scrivi x,y oppure @dx,dy oppure @distanza<angolo'); continue; }
        if (req.tipo === 'distanza' || req.tipo === 'numero' || req.tipo === 'angolo') {
          var v = numero(t);
          if (v === null && req.tipo !== 'numero' && req.base) { var q2 = interpretaPunto(t, req.base, r.cursore); if (q2) v = req.tipo === 'angolo' ? G.ang(req.base, q2) : G.dist(req.base, q2); }
          if (v !== null && (req.minimo === undefined || v >= req.minimo)) return v;
          scrivi(req.tipo === 'angolo' ? 'Angolo non valido (gradi)' : 'Valore non valido' + (req.minimo !== undefined ? ' (minimo ' + req.minimo + ')' : '')); continue;
        }
        if (req.tipo === 'testo' || req.tipo === 'opzione') return t;
        scrivi('Input non valido');
      }
    }
    function vicina(p, tol) {
      var best = null, bd = tol || 2;
      s.entita.forEach(function (e) { var d = G.distanza(p, e); if (d <= bd) { bd = d; best = e; } });
      return best;
    }
    var punto = function (prompt, base, extra) { return chiedi(Object.assign({prompt: prompt, tipo: 'punto', base: base, vuotoOk: true}, extra || {})); };
    async function selezione(prompt) {
      if (s.sel.length) { var pre = s.sel.slice(); return pre; }
      var ids = await io.seleziona(prompt || 'Selezionare oggetti');
      if (!ids) throw new Annullato();
      s.sel = [];
      if (!ids.length) scrivi('Nessun oggetto selezionato.');
      return ids;
    }
    var fine = function (p) { if (p && p.length) s.ultimo = p; };

    // ── i comandi ──
    var C = {};
    C.LINEA = async function (polilinea) {
      var p0 = await punto('Specificare primo punto'); if (!p0 || p0.opzione) return;
      fine(p0);
      var pts = [p0], creati = [];
      for (;;) {
        var opz = pts.length >= 3 ? {C: 'Chiudi', A: 'Annulla'} : {A: 'Annulla'};
        var base = pts[pts.length - 1];
        var q = await punto('Specificare punto successivo', base, {opzioni: opz, anteprima: function (c) { return [{t: 'line', a: base, b: applicaOrto(c, base)}]; }});
        if (!q) break;
        if (q.opzione === 'A') { if (pts.length > 1) { pts.pop(); if (!polilinea) togli([creati.pop().id]); } continue; }
        if (q.opzione === 'C') { if (!polilinea) creati.push(aggiungi({t: 'line', a: base, b: pts[0]})); else pts.chiusa = true; fine(pts[0]); break; }
        if (!polilinea) creati.push(aggiungi({t: 'line', a: base, b: q}));
        pts.push(q); fine(q);
      }
      if (polilinea && pts.length > 1) { aggiungi({t: 'pline', pts: pts.slice(), closed: !!pts.chiusa}); }
    };
    C.PLINEA = function () { return C.LINEA(true); };
    C.CERCHIO = async function () {
      var c = await punto('Specificare centro del cerchio'); if (!c || c.opzione) return;
      var r = await chiedi({prompt: 'Specificare raggio del cerchio', tipo: 'distanza', base: c, opzioni: {D: 'Diametro'}, minimo: 0.001, predefinito: s.raggioCerchio,
        anteprima: function (q) { return [{t: 'circle', c: c, r: Math.max(0.001, G.dist(c, q))}]; }});
      if (r && r.opzione === 'D') r = (await chiedi({prompt: 'Specificare diametro del cerchio', tipo: 'distanza', base: c, minimo: 0.001})) / 2;
      s.raggioCerchio = r; aggiungi({t: 'circle', c: c, r: r}); fine(c);
    };
    C.ARCO = async function () {
      var p1 = await punto('Specificare punto iniziale dell’arco', null, {opzioni: {C: 'Centro'}}); if (!p1) return;
      if (p1.opzione === 'C') {
        var c = await punto('Specificare centro dell’arco'); var a = await punto('Specificare punto iniziale dell’arco', c);
        var b = await punto('Specificare punto finale dell’arco (antiorario)', c, {anteprima: function (q) { return [{t: 'arc', c: c, r: G.dist(c, a), a0: G.ang(c, a), a1: G.ang(c, q)}]; }});
        aggiungi({t: 'arc', c: c, r: G.dist(c, a), a0: G.ang(c, a), a1: G.ang(c, b)}); fine(b); return;
      }
      var p2 = await punto('Specificare secondo punto dell’arco', p1);
      var p3 = await punto('Specificare punto finale dell’arco', p2, {anteprima: function (q) { try { return [G.arco3p(p1, p2, q)]; } catch (e) { return []; } }});
      aggiungi(G.arco3p(p1, p2, p3)); fine(p3);
    };
    C.RETTANGOLO = async function () {
      var a = await punto('Specificare primo punto d’angolo'); if (!a || a.opzione) return;
      var rect = function (b) { return {t: 'pline', pts: [a, [b[0], a[1]], b, [a[0], b[1]]], closed: true}; };
      var b = await chiedi({prompt: 'Specificare altro punto d’angolo (es. @120,80)', tipo: 'punto', base: a, anteprima: function (q) { return [rect(q)]; }});
      if (!b || b.opzione) return;
      if (Math.abs(b[0] - a[0]) < 1e-9 || Math.abs(b[1] - a[1]) < 1e-9) { scrivi('Rettangolo con un lato nullo: ignorato.'); return; }
      aggiungi(rect(b)); fine(b);
    };
    C.POLIGONO = async function () {
      var n = await chiedi({prompt: 'Immettere numero dei lati', tipo: 'numero', predefinito: s.lati || 6, minimo: 3});
      n = Math.round(n); if (n > 1024) { scrivi('Massimo 1024 lati'); return; } s.lati = n;
      var c = await punto('Specificare centro del poligono'); if (!c || c.opzione) return;
      var tipo = await chiedi({prompt: 'Immettere un’opzione', tipo: 'opzione', opzioni: {I: 'Inscritto nel cerchio', C: 'Circoscritto attorno al cerchio'}, predefinito: 'I'});
      var ins = !(tipo && tipo.opzione === 'C');
      var r = await chiedi({prompt: 'Specificare raggio del cerchio', tipo: 'distanza', base: c, minimo: 0.001, anteprima: function (q) { return [G.poligono(n, c, G.dist(c, q), ins, G.ang(c, q))]; }});
      aggiungi(G.poligono(n, c, r, ins)); fine(c);
    };
    C.CANCELLA = async function () { var ids = await selezione(); if (ids.length) { togli(ids); scrivi(ids.length + ' oggetti cancellati.'); } };
    async function trasformaSel(nome, f, copia) {
      var ids = await selezione(); if (!ids.length) return;
      var originali = ids.map(perId).filter(Boolean);
      var b = await punto('Specificare punto base'); if (!b || b.opzione) return;
      return {ids: ids, originali: originali, base: b};
    }
    C.SPOSTA = async function () {
      var t = await trasformaSel(); if (!t) return;
      var q = await punto('Specificare secondo punto', t.base, {anteprima: function (c) { c = applicaOrto(c, t.base); return t.originali.map(function (e) { return G.sposta(e, c[0] - t.base[0], c[1] - t.base[1]); }); }});
      if (!q || q.opzione) return;
      t.originali.forEach(function (e) { var n = G.sposta(e, q[0] - t.base[0], q[1] - t.base[1]); n.id = e.id; s.entita[s.entita.indexOf(e)] = n; });
      fine(q); s.sel = [];
    };
    C.COPIA = async function () {
      var t = await trasformaSel(); if (!t) return;
      for (;;) {
        var q = await punto('Specificare secondo punto', t.base, {anteprima: function (c) { c = applicaOrto(c, t.base); return t.originali.map(function (e) { return G.sposta(e, c[0] - t.base[0], c[1] - t.base[1]); }); }});
        if (!q || q.opzione) break;
        t.originali.forEach(function (e) { aggiungi(G.sposta(e, q[0] - t.base[0], q[1] - t.base[1])); });
        fine(q);
      }
      s.sel = [];
    };
    C.RUOTA = async function () {
      var t = await trasformaSel(); if (!t) return;
      var g = await chiedi({prompt: 'Specificare angolo di rotazione (gradi, antiorario)', tipo: 'angolo', base: t.base, predefinito: s.angolo || 0,
        anteprima: function (c) { var a = G.ang(t.base, c); return t.originali.map(function (e) { return G.ruota(e, t.base, a); }); }});
      s.angolo = g;
      t.originali.forEach(function (e) { var n = G.ruota(e, t.base, g); n.id = e.id; s.entita[s.entita.indexOf(e)] = n; });
      s.sel = [];
    };
    C.SCALA = async function () {
      var t = await trasformaSel(); if (!t) return;
      var k = await chiedi({prompt: 'Specificare fattore di scala', tipo: 'numero', minimo: 1e-6});
      if (k <= 0) { scrivi('Il fattore deve essere maggiore di zero'); return; }
      t.originali.forEach(function (e) { var n = G.scala(e, t.base, k); n.id = e.id; s.entita[s.entita.indexOf(e)] = n; });
      s.sel = [];
    };
    C.SPECCHIO = async function () {
      var ids = await selezione(); if (!ids.length) return;
      var orig = ids.map(perId).filter(Boolean);
      var a = await punto('Specificare primo punto della linea di specchio'); if (!a || a.opzione) return;
      var b = await punto('Specificare secondo punto della linea di specchio', a, {anteprima: function (c) { c = applicaOrto(c, a); return G.dist(a, c) > 1e-9 ? orig.map(function (e) { return G.specchia(e, a, c); }) : []; }});
      if (!b || b.opzione || G.dist(a, b) < 1e-9) return;
      var canc = await chiedi({prompt: 'Cancellare gli oggetti di origine?', tipo: 'opzione', opzioni: {S: 'Sì', N: 'No'}, predefinito: 'N'});
      orig.forEach(function (e) { aggiungi(G.specchia(e, a, b)); });
      if (canc && canc.opzione === 'S') togli(ids);
      s.sel = [];
    };
    C.OFFSET = async function () {
      var d = await chiedi({prompt: 'Specificare distanza di offset', tipo: 'distanza', minimo: 0.0001, predefinito: s.offset});
      s.offset = d;
      for (;;) {
        var pk = await chiedi({prompt: 'Selezionare oggetto di cui eseguire l’offset (INVIO per finire)', tipo: 'entita', vuotoOk: true});
        if (!pk) break;
        var lato = await punto('Specificare punto sul lato di cui eseguire l’offset', null, {anteprima: function (c) { try { return [G.offset(pk.entita, d, c)]; } catch (e) { return []; } }});
        if (!lato || lato.opzione) break;
        try { aggiungi(G.offset(pk.entita, d, lato)); } catch (e) { scrivi(e.message); }
      }
    };
    async function dueLinee(nome) {
      for (;;) {
        var r1 = await chiedi({prompt: 'Selezionare primo oggetto', tipo: 'entita', opzioni: nome === 'R' ? {R: 'Raggio'} : {D: 'Distanze'}});
        if (r1.opzione === 'R') { s.raggio = await chiedi({prompt: 'Specificare raggio di raccordo', tipo: 'distanza', minimo: 0, predefinito: s.raggio}); continue; }
        if (r1.opzione === 'D') { var d1 = await chiedi({prompt: 'Specificare prima distanza di cima', tipo: 'distanza', minimo: 0, predefinito: s.cima[0]});
          var d2 = await chiedi({prompt: 'Specificare seconda distanza di cima', tipo: 'distanza', minimo: 0, predefinito: d1}); s.cima = [d1, d2]; continue; }
        var r2 = await chiedi({prompt: 'Selezionare secondo oggetto', tipo: 'entita'});
        if (r1.entita.t !== 'line' || r2.entita.t !== 'line') { scrivi('Seleziona due LINEE (le polilinee vanno prima ESPLOSE con X).'); return null; }
        if (r1.entita.id === r2.entita.id) { scrivi('Seleziona due linee diverse.'); continue; }
        return [r1, r2];
      }
    }
    C.RACCORDO = async function () {
      scrivi('Impostazioni correnti: raggio = ' + s.raggio);
      var l = await dueLinee('R'); if (!l) return;
      var r = G.raccordo(l[0].entita, l[0].punto, l[1].entita, l[1].punto, s.raggio);
      sostituisci(l[0].entita.id, [r.linee[0]]); sostituisci(l[1].entita.id, [r.linee[1]]);
      if (r.arco) aggiungi(r.arco);
    };
    C.CIMA = async function () {
      scrivi('Impostazioni correnti: distanze = ' + s.cima[0] + ', ' + s.cima[1]);
      var l = await dueLinee('D'); if (!l) return;
      var r = G.cima(l[0].entita, l[0].punto, l[1].entita, l[1].punto, s.cima[0], s.cima[1]);
      sostituisci(l[0].entita.id, [r.linee[0]]); sostituisci(l[1].entita.id, [r.linee[1]]);
      if (r.smusso) aggiungi(r.smusso);
    };
    C.TAGLIA = async function () {
      scrivi('Modalità rapida: clicca la parte da togliere. Taglia fino agli oggetti che la incrociano.');
      for (;;) {
        var pk = await chiedi({prompt: 'Selezionare oggetto da tagliare (INVIO per finire)', tipo: 'entita', vuotoOk: true});
        if (!pk) break;
        var altri = s.entita.filter(function (e) { return e.id !== pk.entita.id; });
        var parti = G.taglia(pk.entita, pk.punto, altri);
        if (parti === null) { togli([pk.entita.id]); scrivi('Nessun oggetto incrocia: oggetto cancellato.'); }
        else sostituisci(pk.entita.id, parti);
      }
    };
    C.ESTENDI = async function () {
      for (;;) {
        var pk = await chiedi({prompt: 'Selezionare la linea da estendere, vicino all’estremo (INVIO per finire)', tipo: 'entita', vuotoOk: true});
        if (!pk) break;
        var n = G.estendi(pk.entita, pk.punto, s.entita.filter(function (e) { return e.id !== pk.entita.id; }));
        if (!n) scrivi('Nessun oggetto da raggiungere in quella direzione.'); else sostituisci(pk.entita.id, [n]);
      }
    };
    C.ESPLODI = async function () { var ids = await selezione(); var k = 0; ids.forEach(function (id) { var e = perId(id); if (e && e.t === 'pline') { sostituisci(id, G.esplodi(e)); k++; } }); s.sel = []; scrivi(k + ' polilinee esplose.'); };
    C.ANNULLA = async function () {
      if (!s.annulla.length) { scrivi('Niente da annullare.'); return; }
      s.ripristina.push(JSON.stringify(s.entita)); s.entita = JSON.parse(s.annulla.pop()); s.sel = []; scrivi('Annullato.');
    };
    C.RIPRISTINA = async function () {
      if (!s.ripristina.length) { scrivi('Niente da ripristinare.'); return; }
      s.annulla.push(JSON.stringify(s.entita)); s.entita = JSON.parse(s.ripristina.pop()); scrivi('Ripristinato.');
    };
    C.ZOOM = async function () { io.zoomEstensioni(); };
    C.DIST = async function () {
      var a = await punto('Specificare primo punto'); if (!a || a.opzione) return;
      var b = await punto('Specificare secondo punto', a, {anteprima: function (c) { return [{t: 'line', a: a, b: c}]; }}); if (!b || b.opzione) return;
      scrivi('Distanza = ' + G.dist(a, b).toFixed(4) + ',  Angolo nel piano XY = ' + G.ang(a, b).toFixed(2) + '°,  Delta X = ' + (b[0] - a[0]).toFixed(4) + ',  Delta Y = ' + (b[1] - a[1]).toFixed(4));
    };
    C.ID = async function () { var p = await punto('Specificare punto'); if (p && !p.opzione) { scrivi('X = ' + p[0].toFixed(4) + '   Y = ' + p[1].toFixed(4)); fine(p); } };
    C.LISTA = async function () {
      var ids = await selezione();
      ids.map(perId).filter(Boolean).forEach(function (e) {
        var m = G.areaPerimetro(e), r = '';
        if (e.t === 'line') r = 'LINEA da ' + e.a.join(',') + ' a ' + e.b.join(',') + ' · lunghezza ' + m.perimetro.toFixed(3);
        else if (e.t === 'circle') r = 'CERCHIO centro ' + e.c.join(',') + ' · raggio ' + e.r + ' · diametro ' + (2 * e.r) + ' · area ' + m.area.toFixed(3) + ' · circonferenza ' + m.perimetro.toFixed(3);
        else if (e.t === 'arc') r = 'ARCO centro ' + e.c.join(',') + ' · raggio ' + e.r + ' · da ' + e.a0 + '° a ' + e.a1 + '° · lunghezza ' + m.perimetro.toFixed(3);
        else if (e.t === 'pline') r = 'POLILINEA ' + (e.closed ? 'chiusa' : 'aperta') + ' · ' + e.pts.length + ' vertici · ' + (e.closed ? 'area ' + m.area.toFixed(3) + ' · ' : '') + 'lunghezza ' + m.perimetro.toFixed(3);
        else r = e.t.toUpperCase();
        scrivi(r);
      });
      s.sel = [];
    };
    C.QUOTA = async function () {
      var a = await punto('Specificare origine della prima linea di estensione'); if (!a || a.opzione) return;
      var b = await punto('Specificare origine della seconda linea di estensione', a); if (!b || b.opzione) return;
      var o = await punto('Specificare posizione della linea di quota', b, {anteprima: function (c) { return [{t: 'dim', a: a, b: b, o: c}]; }}); if (!o || o.opzione) return;
      aggiungi({t: 'dim', a: a, b: b, o: o, testo: G.dist(a, b).toFixed(2).replace(/\.?0+$/, '')});
    };
    C.TESTO = async function () {
      var p = await punto('Specificare punto iniziale del testo'); if (!p || p.opzione) return;
      var h = await chiedi({prompt: 'Specificare altezza', tipo: 'distanza', base: p, minimo: 0.01, predefinito: s.altezzaTesto || 3.5}); s.altezzaTesto = h;
      var t = await chiedi({prompt: 'Immettere testo', tipo: 'testo'});
      if (t) aggiungi({t: 'text', p: p, h: h, testo: String(t).slice(0, 200)});
    };
    C.ORTO = async function () { s.orto = !s.orto; scrivi('<Orto ' + (s.orto ? 'attivato' : 'disattivato') + '>'); };
    C.OSNAP = async function () { s.osnap = !s.osnap; scrivi('<Snap ad oggetto ' + (s.osnap ? 'attivato' : 'disattivato') + '>'); };
    C.SNAP = async function () {
      var v = await chiedi({prompt: 'Specificare passo dello snap o', tipo: 'numero', opzioni: {A: 'Attivato', D: 'Disattivato'}, predefinito: s.passo, minimo: 0.001});
      if (v && v.opzione) s.snap = v.opzione === 'A'; else { s.passo = v; s.snap = true; }
      scrivi('<Snap griglia ' + (s.snap ? 'attivato, passo ' + s.passo : 'disattivato') + '>');
    };
    C.SELEZIONATUTTO = async function () { s.sel = s.entita.map(function (e) { return e.id; }); scrivi(s.sel.length + ' oggetti selezionati.'); };
    C.NUOVO = async function () {
      if (s.entita.length) { var ok = await chiedi({prompt: 'Cancellare tutto il disegno?', tipo: 'opzione', opzioni: {S: 'Sì', N: 'No'}, predefinito: 'N'}); if (!ok || ok.opzione !== 'S') return; }
      s.entita = []; s.sel = []; scrivi('Nuovo disegno.');
    };
    C.DXFOUT = async function () {
      if (!s.entita.length) { scrivi('Il disegno è vuoto.'); return; }
      var nome = await chiedi({prompt: 'Nome del file', tipo: 'testo', predefinito: 'disegno'});
      io.scarica(String(nome).replace(/[^\w\-]+/g, '_') + '.dxf', root.DXF.scrivi(s.entita), 'application/dxf');
      scrivi('DXF scaricato: si apre con AutoCAD (unità: millimetri).');
    };
    C.DXFIN = async function () {
      var testo = await io.apriFile('.dxf'); if (!testo) return;
      var r = root.DXF.leggi(testo);
      r.entita.forEach(aggiungi);
      var salt = Object.keys(r.saltate);
      scrivi(r.entita.length + ' oggetti importati dal DXF.' + (salt.length ? ' Non importati: ' + salt.map(function (k) { return k + ' ×' + r.saltate[k]; }).join(', ') + ' (esplodili in AutoCAD).' : ''));
      io.zoomEstensioni();
    };
    C.ESTRUDI = async function () {
      if (!s.entita.length) { scrivi('Disegna prima un contorno chiuso.'); return; }
      var h = await chiedi({prompt: 'Specificare altezza di estrusione (mm)', tipo: 'distanza', minimo: 0.001, predefinito: s.estrudi});
      s.estrudi = h;
      var ent = (s.sel.length ? s.sel.map(perId) : s.entita).filter(Boolean);
      await io.solido('estrudi', {entita: ent, altezza: h});
      s.sel = [];
    };
    C.RIVOLUZIONE = async function () {
      if (!s.entita.length) { scrivi('Disegna prima la mezza sezione chiusa.'); return; }
      var a = await punto('Specificare punto iniziale dell’asse di rivoluzione', null, {opzioni: {X: 'asse X', Y: 'asse Y'}, predefinito: 'X'});
      var A, B;
      if (!a || a.opzione === 'X') { A = [0, 0]; B = [1, 0]; }
      else if (a.opzione === 'Y') { A = [0, 0]; B = [0, 1]; }
      else { A = a; B = await punto('Specificare punto finale dell’asse', a); if (!B || B.opzione) return; }
      var g = await chiedi({prompt: 'Specificare angolo di rivoluzione', tipo: 'numero', predefinito: 360, minimo: 0.001});
      var ent = (s.sel.length ? s.sel.map(perId) : s.entita).filter(Boolean);
      await io.solido('rivoluzione', {entita: ent, asse: [A, B], angolo: Math.min(360, g)});
      s.sel = [];
    };
    C.AIUTO = async function () {
      scrivi('COMANDI (italiano · inglese · alias):');
      Object.keys(COMANDI).forEach(function (k) { scrivi('  ' + COMANDI[k][0].join(' · ') + ' — ' + COMANDI[k][1]); });
      scrivi('Coordinate: x,y · @dx,dy · @distanza<angolo · un numero = distanza verso il cursore. INVIO/SPAZIO ripete l’ultimo comando. ESC annulla.');
    };

    var nonModificano = {ZOOM: 1, DIST: 1, ID: 1, LISTA: 1, ORTO: 1, OSNAP: 1, SNAP: 1, AIUTO: 1, DXFOUT: 1, ANNULLA: 1, RIPRISTINA: 1, SELEZIONATUTTO: 1, ESTRUDI: 1, RIVOLUZIONE: 1};
    async function esegui(testo) {
      var nome = String(testo || '').trim().toUpperCase().replace(/^[_.'-]+/, '');
      if (!nome) { if (!s.ultimoComando) return; nome = s.ultimoComando; }
      var k = ALIAS[nome];
      if (!k) { scrivi('Comando sconosciuto «' + nome + '». Premi F1 o scrivi AIUTO per l’elenco.'); return; }
      if (s.inCorso) return;
      s.inCorso = k;
      if (!nonModificano[k]) istantanea();
      scrivi('Comando: ' + k);
      try { await C[k](); }
      catch (e) {
        if (e instanceof Annullato) scrivi('*Annulla*');
        else scrivi('⛔ ' + (e && e.message ? e.message : String(e)));
      } finally {
        s.inCorso = null;
        if (k !== 'ANNULLA' && k !== 'RIPRISTINA') s.ultimoComando = k;
        if (!nonModificano[k] && s.annulla.length && s.annulla[s.annulla.length - 1] === JSON.stringify(s.entita)) s.annulla.pop();   // nessuna modifica: niente da annullare
        io.aggiorna && io.aggiorna();
      }
    }
    function cancellaSelezione() { if (!s.sel.length) return; istantanea(); togli(s.sel.slice()); io.aggiorna && io.aggiorna(); }
    function carica(entita, sostituisciTutto) { istantanea(); if (sostituisciTutto) s.entita = []; entita.forEach(aggiungi); io.aggiorna && io.aggiorna(); }
    return {stato: s, esegui: esegui, interpretaPunto: interpretaPunto, cancellaSelezione: cancellaSelezione, carica: carica, vicina: vicina, applicaOrto: applicaOrto};
  }
  root.CAD = {crea: crea, COMANDI: COMANDI, ALIAS: ALIAS};
})(typeof window !== 'undefined' ? window : globalThis);

/* Test del motore comandi AutoCAD: node tests/js/comandi.test.js */
'use strict';
const assert = require('node:assert/strict');
require('../../mastercad/disegno/static/geometria2d.js');
require('../../mastercad/disegno/static/dxf.js');
require('../../mastercad/disegno/static/comandi.js');
const {CAD, G2D, DXF} = globalThis;

function sessione() {
  const coda = [], log = [], solidi = [];
  const io = {
    chiedi: async () => { const v = coda.shift(); if (v === undefined) throw new Error('script finito'); return v; },
    seleziona: async () => coda.shift(),
    scrivi: t => log.push(t), zoomEstensioni() {}, aggiorna() {},
    solido: async (op, dati) => solidi.push([op, dati]), lavorazione: async l => solidi.push(['lav', l]), scarica: (n, t) => log.push('FILE ' + n + ' ' + t.length), apriFile: async () => coda.shift()
  };
  const cad = CAD.crea(io);
  const t = x => ({testo: x}), clic = (x, y, extra) => Object.assign({clic: [x, y], tolleranza: 1}, extra || {});
  return {cad, coda, log, solidi, t, clic, s: cad.stato};
}
(async () => {
  // LINEA con coordinate assolute, relative, polari, distanza diretta e Chiudi
  let k = sessione();
  k.coda.push(k.t('0,0'), k.t('@100,0'), k.t('@60<90'), {testo: '100', cursore: [-500, 60]}, k.t('C'));
  await k.cad.esegui('L');
  assert.equal(k.s.entita.length, 4, 'quattro linee');
  assert.deepEqual(k.s.entita[1].b, [100, 60]);
  assert.deepEqual(k.s.entita[2].b, [0, 60]);
  assert.deepEqual(k.s.entita[3].b, [0, 0], 'Chiudi torna al primo punto');
  // INVIO a vuoto ripete l'ultimo comando (LINEA)
  k.coda.push(k.t('200,0'), k.t('@10,0'), k.t(''));
  await k.cad.esegui('');
  assert.equal(k.s.entita.length, 5, 'INVIO ripete LINEA');
  // ANNULLA e RIPRISTINA
  await k.cad.esegui('U'); assert.equal(k.s.entita.length, 4);
  await k.cad.esegui('REDO'); assert.equal(k.s.entita.length, 5);

  // RETTANGOLO @120,80, CERCHIO D, ESTRUDI → richiesta del solido
  k = sessione();
  k.coda.push(k.t('0,0'), k.t('@120,80')); await k.cad.esegui('REC');
  k.coda.push(k.t('20,40'), k.t('D'), k.t('10')); await k.cad.esegui('CERCHIO');
  assert.equal(k.s.entita[1].r, 5, 'diametro 10 → raggio 5');
  k.coda.push(k.t('8')); await k.cad.esegui('EXT');
  assert.equal(k.solidi[0][0], 'estrudi'); assert.equal(k.solidi[0][1].altezza, 8); assert.equal(k.solidi[0][1].entita.length, 2);

  // RACCORDO raggio 10 fra due linee ad angolo retto
  k = sessione();
  k.coda.push(k.t('0,0'), k.t('100,0'), k.t('100,50'), k.t('')); await k.cad.esegui('LINEA');
  k.coda.push(k.t('R'), k.t('10'), k.clic(50, 0), k.clic(100, 30)); await k.cad.esegui('F');
  assert.equal(k.s.entita.filter(e => e.t === 'arc').length, 1, 'arco di raccordo');
  assert.deepEqual(k.s.entita.find(e => e.t === 'arc').c, [90, 10]);

  // TAGLIA: linea fra due verticali
  k = sessione();
  k.coda.push(k.t('0,10'), k.t('100,10'), k.t('')); await k.cad.esegui('L');
  k.coda.push(k.t('30,0'), k.t('30,20'), k.t('')); await k.cad.esegui('L');
  k.coda.push(k.t('70,0'), k.t('70,20'), k.t('')); await k.cad.esegui('L');
  k.coda.push(k.clic(50, 10), k.t('')); await k.cad.esegui('TR');
  const orizz = k.s.entita.filter(e => e.t === 'line' && e.a[1] === 10 && e.b[1] === 10);
  assert.equal(orizz.length, 2, 'la parte centrale è tolta');

  // OFFSET di un cerchio verso l'esterno
  k = sessione();
  k.coda.push(k.t('0,0'), k.t('10')); await k.cad.esegui('C');
  k.coda.push(k.t('5'), k.clic(10, 0), k.t('20,0'), k.t('')); await k.cad.esegui('O');
  assert.equal(k.s.entita[1].r, 15);

  // SPOSTA, COPIA, RUOTA, SCALA, SPECCHIO con selezione
  k = sessione();
  k.coda.push(k.t('0,0'), k.t('10,0'), k.t('')); await k.cad.esegui('L');
  const id = k.s.entita[0].id;
  k.coda.push([id], k.t('0,0'), k.t('@5,5')); await k.cad.esegui('M');
  assert.deepEqual(k.s.entita[0].a, [5, 5]);
  k.coda.push([id], k.t('0,0'), k.t('@0,10'), k.t('@0,20'), k.t('')); await k.cad.esegui('CO');
  assert.equal(k.s.entita.length, 3, 'due copie');
  k.coda.push([id], k.t('5,5'), k.t('90')); await k.cad.esegui('RO');
  assert.deepEqual(k.s.entita[0].b, [5, 15]);
  k.coda.push([id], k.t('5,5'), k.t('2')); await k.cad.esegui('SC');
  assert.deepEqual(k.s.entita[0].b, [5, 25]);
  k.coda.push([id], k.t('0,0'), k.t('1,0'), k.t('N')); await k.cad.esegui('MI');
  assert.equal(k.s.entita.length, 4);

  // POLIGONO esagono inscritto, ESPLODI, LISTA, DIST
  k = sessione();
  k.coda.push(k.t('6'), k.t('0,0'), k.t('I'), k.t('10')); await k.cad.esegui('POL');
  assert.equal(k.s.entita[0].pts.length, 6);
  k.coda.push([k.s.entita[0].id]); await k.cad.esegui('X');
  assert.equal(k.s.entita.length, 6);
  k.coda.push(k.t('0,0'), k.t('3,4')); await k.cad.esegui('DI');
  assert.ok(k.log.some(l => /Distanza = 5\.0000/.test(l)));

  // RIVOLUZIONE attorno all'asse X (predefinito) di una mezza sezione
  k = sessione();
  k.coda.push(k.t('0,0'), k.t('@50,0'), k.t('@0,10'), k.t('@-50,0'), k.t('C')); await k.cad.esegui('PL');
  assert.equal(k.s.entita[0].closed, true);
  k.coda.push(k.t(''), k.t('')); await k.cad.esegui('REV');
  assert.deepEqual(k.solidi[0][1].asse, [[0, 0], [1, 0]]); assert.equal(k.solidi[0][1].angolo, 360);

  // lavorazioni 3D: FORO filettato, serie polare lamata, TASCA, ASOLA, RACCORDASPIGOLI, GUSCIO
  k = sessione();
  k.coda.push(k.t('30,20'), k.t('M8'), k.t('12'), k.t('')); await k.cad.esegui('FORO');
  assert.deepEqual(k.solidi[0], ['lav', {tipo: 'foro', x: 30, y: 20, filetto: 'M8', prof: 12}]);
  k.coda.push(k.t('P'), k.t('0,0'), k.t('70'), k.t('6'), k.t('15'), k.t('9'), k.t('P'), k.t('L'), k.t('15'), k.t('8.6')); await k.cad.esegui('HOLE');
  assert.deepEqual(k.solidi[1][1], {tipo: 'serie_polare', centro: [0, 0], diametro: 70, n: 6, angolo0: 15, foro: {d: 9, lamatura: {d: 15, prof: 8.6}}});
  k.coda.push(k.t('10,10'), k.t(''), k.t('40'), k.t('20'), k.t(''), k.t('3'), k.t('6')); await k.cad.esegui('TASCA');
  assert.deepEqual(k.solidi[2][1], {forma: 'rett', centro: [10, 10], l: 40, w: 20, angolo: 0, raggio_angoli: 3, tipo: 'tasca', prof: 6});
  k.coda.push(k.t('0,0'), k.t('30,0'), k.t('8'), k.t('')); await k.cad.esegui('SLOT');
  assert.deepEqual(k.solidi[3][1], {tipo: 'asola', centro: [15, 0], lunghezza: 38, larghezza: 8, angolo: 0, prof: null});
  k.coda.push(k.t('2'), k.t('S')); await k.cad.esegui('FILLETEDGE');
  assert.deepEqual(k.solidi[4][1], {tipo: 'raccordo', r: 2, spigoli: 'superiori'});
  k.coda.push(k.t('2'), k.t('SOTTO')); await k.cad.esegui('SHELL');
  assert.deepEqual(k.solidi[5][1], {tipo: 'guscio', spessore: 2, aperta: 'sotto'});
  assert.equal(k.s.entita.length, 0, 'le lavorazioni 3D non toccano la tavola');

  // SERIEPOLARE e SERIERETT 2D
  k = sessione();
  k.coda.push(k.t('35,0'), k.t('4')); await k.cad.esegui('C');
  k.coda.push([k.s.entita[0].id], k.t('0,0'), k.t('4'), k.t('')); await k.cad.esegui('ARRAYPOLAR');
  assert.equal(k.s.entita.length, 4);
  assert.ok(k.s.entita.some(e => Math.abs(e.c[0]) < 1e-6 && Math.abs(e.c[1] - 35) < 1e-6), 'copia a 90°');
  k = sessione();
  k.coda.push(k.t('0,0'), k.t('2')); await k.cad.esegui('C');
  k.coda.push([k.s.entita[0].id], k.t('3'), k.t('2'), k.t('10'), k.t('15')); await k.cad.esegui('AR');
  assert.equal(k.s.entita.length, 6); assert.ok(k.s.entita.some(e => e.c[0] === 20 && e.c[1] === 15));
  // DXF: scrittura e rilettura
  k = sessione();
  k.coda.push(k.t('0,0'), k.t('@120,80')); await k.cad.esegui('REC');
  k.coda.push(k.t('60,40'), k.t('15')); await k.cad.esegui('C');
  k.coda.push(k.t('0,0'), k.t('10,0'), k.t('5,5')); await k.cad.esegui('A');
  const dxf = DXF.scrivi(k.s.entita), letto = DXF.leggi(dxf);
  assert.deepEqual(letto.entita.map(e => e.t), ['pline', 'circle', 'arc']);
  assert.equal(letto.entita[1].r, 15);
  // ESC annulla senza lasciare entità
  k = sessione(); k.coda.push(k.t('0,0'), {annulla: true}); await k.cad.esegui('C');
  assert.equal(k.s.entita.length, 0); assert.ok(k.log.includes('*Annulla*'));
  // comando sconosciuto
  await k.cad.esegui('PIPPO'); assert.ok(k.log.some(l => /sconosciuto/.test(l)));
  console.log('OK: comandi AutoCAD (LINEA, PLINEA, CERCHIO, ARCO, RETTANGOLO, POLIGONO, SPOSTA, COPIA, RUOTA, SCALA, SPECCHIO, OFFSET, RACCORDO, TAGLIA, ESPLODI, DIST, ANNULLA, ESTRUDI, RIVOLUZIONE, DXF, FORO, TASCA, ASOLA, RACCORDASPIGOLI, GUSCIO, SERIEPOLARE, SERIERETT)');
})().catch(e => { console.error(e); process.exit(1); });

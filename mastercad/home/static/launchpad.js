/* Home: pezzo aperto e numeri sulle tile (ultimi risultati salvati da ogni pagina in questo browser). */
(function () {
  'use strict';
  var p = MC.progetto(), kpi = MC.leggi('mcad-kpi') || {};
  var box = document.getElementById('pezzo');
  if (p) MC.riquadroPezzo(box, 'è il pezzo su cui lavorano tavola, ciclo, preventivo e controlli');
  else box.innerHTML = '<div class="pezzo"><div class="icona">＋</div><div class="info"><b>Nessun pezzo aperto</b><div>Comincia da «Dalla foto al 3D», dal «Disegno CAD» o dalla «Libreria a norma».</div></div></div>';
  var lav = p ? (p.lavorazioni || []).filter(function (l) { return !l.sospesa; }).length : 0;
  var valori = {
    lavorazioni: p ? [lav, lav === 1 ? 'lavorazione' : 'lavorazioni'] : null,
    libreria: [5, 'pezzi tipo'],
    tavola: p ? ['A3', 'PDF · DXF'] : null,
    foto: ['A4', 'riferimento']
  };
  Object.keys(kpi).forEach(function (k) { if (kpi[k] && kpi[k].pezzo === MC.nome()) valori[k] = [kpi[k].valore, kpi[k].etichetta]; });
  document.querySelectorAll('.tile').forEach(function (t) {
    var v = valori[t.getAttribute('data-kpi')], el = t.querySelector('.kpi');
    if (v) el.innerHTML = '<big>' + MC.esc(v[0]) + '</big>' + MC.esc(v[1] || '');
    else { t.classList.add('vuoto'); el.textContent = 'Apri'; }
  });
  var esercizi = document.querySelector('.tile[data-kpi="esercizi"] .kpi');
  if (esercizi) MC.api('/api/corso/allievo/esercizi').then(function (j) {
    var da = j.esercizi.filter(function (e) { return !e.consegnato; }).length;
    esercizi.innerHTML = '<big>' + da + '</big>da fare';
  }).catch(function () {});
  var doc = document.querySelector('.tile[data-kpi="docente"] .kpi');
  if (doc) MC.api('/api/corso/docente/corsi').then(function (j) {
    var dc = j.reduce(function (s, c) { return s + Number(c.da_correggere || 0); }, 0);
    doc.innerHTML = dc ? '<big>' + dc + '</big>da correggere' : '<big>' + j.length + '</big>' + (j.length === 1 ? 'corso' : 'corsi');
    doc.parentNode.parentNode.classList.remove('vuoto');
  }).catch(function () {});
})();

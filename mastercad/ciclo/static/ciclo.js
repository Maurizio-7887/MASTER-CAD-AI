(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var p = MC.riquadroPezzo($('pezzo'));
  if (!p) return;
  $('corpo').hidden = false;
  $('c-mat').value = (MC.leggi('mcad-cartiglio') || {}).materiale || 'S235';
  var dati = function () { return {progetto: MC.progetto(), materiale: $('c-mat').value, nome: MC.nome()}; };
  $('calcola').onclick = async function () {
    var b = this;
    MC.occupato(b, true, 'Calcolo…');
    MC.messaggio($('msg'), '');
    try {
      var j = await MC.api('/api/ciclo', dati()), c = j.ciclo, t = c.tempi;
      var cart = MC.leggi('mcad-cartiglio') || {}; cart.materiale = $('c-mat').value; MC.scriviLocale('mcad-cartiglio', cart);
      $('kpi').innerHTML = [['Grezzo', c.grezzo.descrizione], ['Tempo macchina', MC.num(t.macchina_min, 1) + ' min'], ['Banco e controllo', MC.num(t.banco_min, 1) + ' min'],
        ['Attrezzaggio (lotto)', MC.num(t.attrezzaggio_min, 0) + ' min'], ['Utensili', c.utensili.length]].map(function (k) {
        return '<div class="kpi-box"><small>' + k[0] + '</small><b style="font-size:' + (String(k[1]).length > 18 ? 14 : 20) + 'px">' + MC.esc(k[1]) + '</b></div>'; }).join('');
      var h = '<tr><th>Fase</th><th>Operazione</th><th>Utensile</th><th class="num">Giri/min</th><th class="num">Avanz. mm/min</th><th class="num">Tempo min</th></tr>';
      c.fasi.forEach(function (f) {
        h += '<tr><td colspan="6" style="background:#f5f6f7"><b>' + f.n + ' · ' + MC.esc(f.nome) + '</b> <span style="color:var(--testo2)">— ' + MC.esc(f.macchina) + '</span></td></tr>';
        f.operazioni.forEach(function (o) {
          h += '<tr><td></td><td>' + MC.esc(o.descrizione) + '</td><td>' + (o.T ? 'T' + o.T : '—') + '</td><td class="num">' + (o.giri ? MC.num(o.giri, 0) : '—') +
            '</td><td class="num">' + (o.vf ? MC.num(o.vf, 0) : '—') + '</td><td class="num">' + MC.num(o.tempo, 2) + '</td></tr>';
        });
      });
      $('t-fasi').innerHTML = h;
      $('t-ut').innerHTML = '<tr><th>T</th><th>Utensile</th></tr>' + c.utensili.map(function (u) { return '<tr><td>T' + u.T + '</td><td>' + MC.esc(u.descrizione) + '</td></tr>'; }).join('');
      $('gcode').textContent = j.gcode || '(pezzo tornito: il programma del tornio si prepara con il CAM del tornio)';
      $('scarica-nc').hidden = !j.gcode;
      $('fasi').hidden = $('sotto').hidden = false;
      if (j.saltate.length) MC.messaggio($('msg'), j.saltate.length + ' lavorazioni non eseguite sono escluse dal ciclo: correggile nel CAD.', 'err');
      MC.kpi('ciclo', MC.num(t.macchina_min, 1), 'min macchina');
    } catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
    finally { MC.occupato(b, false); }
  };
  $('scarica-nc').onclick = async function () {
    try { await MC.scarica('/api/ciclo/gcode', dati(), 'O1001_' + MC.nome().replace(/[^\w\-]+/g, '_') + '.nc'); }
    catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
  };
  $('calcola').click();
})();

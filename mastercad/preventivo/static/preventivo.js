(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var p = MC.riquadroPezzo($('pezzo'));
  if (!p) return;
  $('corpo').hidden = false;
  var salvati = MC.leggi('mcad-preventivo') || {};
  if (salvati['p-qta'] != null) $('p-qta').value = salvati['p-qta'];
  var OFF = null;
  $('p-mat').value = (MC.leggi('mcad-cartiglio') || {}).materiale || 'S235';
  var eur = function () { var m = OFF && OFF.materiali[$('p-mat').value]; $('p-eurkg').value = m ? m.euro_kg : ''; };
  $('p-mat').onchange = function () { eur(); calcola(); };
  async function calcola() {
    var b = $('calcola');
    MC.occupato(b, true, 'Calcolo…');
    MC.messaggio($('msg'), '');
    var par = {euro_kg: $('p-eurkg').value, trattamento: $('p-tr').value, scarto: $('p-scarto').value, margine: $('p-margine').value,
      quantita: $('p-qta').value.split(/[;,\s]+/).filter(Boolean).map(Number)};
    var mem = {};
    mem['p-qta'] = $('p-qta').value;
    MC.scriviLocale('mcad-preventivo', mem);
    try {
      var j = await MC.api('/api/preventivo', {progetto: MC.progetto(), materiale: $('p-mat').value, parametri: par}), v = j.preventivo;
      var oggi = new Date().toLocaleDateString('it-IT');
      var h = '<div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><div><h2 style="margin:0">Offerta · ' + MC.esc(MC.nome()) + '</h2>' +
        '<div class="sotto" style="margin:2px 0 0">' + ($('p-cliente').value ? 'Cliente: <b>' + MC.esc($('p-cliente').value) + '</b> · ' : '') + 'del ' + oggi + '</div></div>' +
        '<div class="kpi-box"><small>Prezzo da ' + v.righe[v.righe.length - 1].quantita + ' pz</small><b>' + MC.euro(v.righe[v.righe.length - 1].prezzo) + '</b></div></div>';
      h += '<div class="kpi-riga"><div class="kpi-box"><small>Materiale</small><b style="font-size:14px">' + MC.esc(v.materiale) + '</b></div><div class="kpi-box"><small>Grezzo</small><b style="font-size:14px">' + MC.esc(v.grezzo) + '</b></div>' +
        '<div class="kpi-box"><small>Peso grezzo / finito</small><b>' + MC.num(v.kg_grezzo, 2) + ' / ' + MC.num(v.kg_finito, 2) + ' kg</b></div><div class="kpi-box"><small>Tempo macchina</small><b>' + MC.num(v.tempi.macchina_min, 1) + ' min</b></div></div>';
      h += '<div class="scorri"><table class="dati"><tr><th class="num">Quantità</th><th class="num">Materiale</th><th class="num">Lavorazione</th><th class="num">Trattamento</th><th class="num">Attrezzaggio</th><th class="num">Costo/pz</th><th class="num">Prezzo/pz</th><th class="num">Totale</th></tr>' +
        v.righe.map(function (r) {
          return '<tr><td class="num"><b>' + r.quantita + '</b></td><td class="num">' + MC.euro(r.materiale) + '</td><td class="num">' + MC.euro(r.lavorazione) + '</td><td class="num">' + MC.euro(r.trattamento) +
            '</td><td class="num">' + MC.euro(r.attrezzaggio) + '</td><td class="num">' + MC.euro(r.costo) + '</td><td class="num"><b>' + MC.euro(r.prezzo) + '</b></td><td class="num">' + MC.euro(r.totale) + '</td></tr>';
        }).join('') + '</table></div>';
      h += '<h3 style="margin-top:16px">Da dove vengono tempi e costi</h3><table class="dati"><tr><th>Fase</th><th>Macchina / terzista</th><th class="num">€/ora</th><th class="num">Minuti/pz</th><th class="num">€/pz</th></tr>' +
        v.voci_ciclo.map(function (f) { return '<tr><td>' + f.fase + ' · ' + MC.esc(f.nome) + '</td><td>' + MC.esc(f.macchina) + '</td><td class="num">' + MC.num(f.costo_ora, 0) + '</td><td class="num">' + MC.num(f.minuti, 2) + '</td><td class="num">' + MC.euro(f.euro) + '</td></tr>'; }).join('') +
        '<tr><td>Attrezzaggio macchina (una volta per lotto)</td><td></td><td class="num">' + MC.num(v.tempi.attrezzaggio_min, 0) + '</td></tr></table>';
      h += '<p class="sotto" style="margin-top:12px;font-size:12px">Scarto ' + MC.num(v.scarto, 1) + '%, margine ' + MC.num(v.margine, 0) + '%. Lotti da 10 pezzi in su: tempo macchina ridotto (programma rodato). Prezzi IVA esclusa, validità 30 giorni. ' + MC.esc(j.avviso) + '</p>';
      (v.terzisti || []).forEach(function (t) { h += '<div class="messaggio info">Fase ' + t.fase + ' affidata a <b>' + MC.esc(t.macchina.replace('Terzista: ', '')) + '</b>' + (t.motivo ? ': ' + MC.esc(t.motivo) : '') + (t.giorni ? ' (circa ' + t.giorni + ' giorni)' : '') + '.</div>'; });
      if (j.saltate.length) h += '<div class="messaggio err">' + j.saltate.length + ' lavorazioni non eseguite non sono nel prezzo: correggile nel CAD.</div>';
      $('offerta').innerHTML = h;
      $('stampa').hidden = false;
      MC.kpi('preventivo', MC.euro(v.righe[0].prezzo), 'al pezzo (' + v.righe[0].quantita + ')');
    } catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
    finally { MC.occupato(b, false); }
  }
  $('calcola').onclick = calcola;
  $('stampa').onclick = function () { window.print(); };
  MC.api('/api/officina').then(function (o) { OFF = o; eur(); $('p-scarto').value = o.costi.scarto; $('p-margine').value = o.costi.margine; calcola(); })
    .catch(function () { calcola(); });
})();

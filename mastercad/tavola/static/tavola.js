(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var p = MC.riquadroPezzo($('pezzo'));
  if (!p) return;
  $('corpo').hidden = false;
  var pref = MC.leggi('mcad-cartiglio') || {};
  $('t-nome').value = MC.nome();
  $('t-dis').value = pref.disegnatore || '';
  $('t-mat').value = pref.materiale || 'S235';
  $('t-tr').value = pref.trattamento || 'nessuno';
  function dati() {
    var c = {nome: $('t-nome').value, numero: $('t-num').value, revisione: $('t-rev').value, disegnatore: $('t-dis').value, controllato: $('t-con').value};
    MC.scriviLocale('mcad-cartiglio', {disegnatore: c.disegnatore, materiale: $('t-mat').value, trattamento: $('t-tr').value});
    return {progetto: MC.progetto(), cartiglio: c, materiale: $('t-mat').value, trattamento: $('t-tr').value};
  }
  $('genera').onclick = async function () {
    var b = this;
    MC.occupato(b, true, 'Disegno le viste…');
    MC.messaggio($('msg'), '');
    try {
      var j = await MC.api('/api/tavola', dati());
      $('foglio').innerHTML = j.svg;
      $('scarica').hidden = false;
      var h = '<div class="kpi-riga"><div class="kpi-box"><small>Scala</small><b>' + MC.esc(j.scala) + '</b></div><div class="kpi-box"><small>Massa</small><b>' + MC.num(j.massa_kg, 2) + ' kg</b></div><div class="kpi-box"><small>Fori</small><b>' + j.tabella_fori.length + '</b></div></div>';
      if (j.viti.length) h += '<p><b>Viteria:</b> ' + j.viti.map(function (v) { return v.quantita + '× ' + MC.esc(v.descrizione); }).join(', ') + '</p>';
      if (j.saltate.length) h += '<div class="messaggio err">' + j.saltate.length + ' lavorazioni non eseguite non sono in tavola: correggile nel CAD.</div>';
      $('riepilogo').innerHTML = h;
      MC.kpi('tavola', j.scala, 'tavola pronta');
    } catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
    finally { MC.occupato(b, false); }
  };
  document.querySelectorAll('[data-fmt]').forEach(function (b) {
    b.onclick = async function () {
      var fmt = b.getAttribute('data-fmt');
      MC.occupato(b, true, 'Preparo…');
      try { await MC.scarica('/api/tavola/' + fmt, dati(), ($('t-nome').value || 'tavola').replace(/[^\w\-]+/g, '_') + '.' + fmt); }
      catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
      finally { MC.occupato(b, false); }
    };
  });
})();

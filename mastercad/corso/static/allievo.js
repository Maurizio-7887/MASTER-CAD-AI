(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  MC.api('/api/corso/allievo/esercizi').then(function (j) {
    if (!j.esercizi.length) { $('esercizi').innerHTML = '<div class="vuoto-stato">Il docente non ha ancora pubblicato esercizi.</div>'; return; }
    $('esercizi').innerHTML = j.esercizi.map(function (e) {
      var voto = e.voto_docente != null ? e.voto_docente : e.voto_auto;
      var stato = e.consegnato ? '<span class="stato ' + (voto >= 6 ? 'ok' : 'att') + '">Consegnato ' + MC.esc(e.consegnato) + (voto != null ? ' · voto ' + MC.num(voto, 1) + (e.voto_docente != null ? ' (docente)' : ' (automatico)') : '') + '</span>' : '<span class="stato info">Da fare</span>';
      var fb = '';
      if (e.esito && e.esito.messaggi) fb = '<details><summary>Cosa dice la correzione</summary><ul>' + e.esito.messaggi.map(function (m) { return '<li>' + MC.esc(m) + '</li>'; }).join('') + '</ul></details>';
      if (e.commento) fb += '<div class="aiuto"><b>Commento del docente:</b> ' + MC.esc(e.commento) + '</div>';
      return '<section class="carta"><h2>' + MC.esc(e.titolo) + '</h2>' + stato +
        (e.ha_foto ? '<p><img alt="Foto del pezzo" src="/corso/esercizio/' + e.id + '/foto"></p>' : '') +
        (e.consegna ? '<h3>Consegna</h3><pre>' + MC.esc(e.consegna) + '</pre>' : '') +
        (e.indicazioni ? '<h3>Indicazioni del tecnico</h3><pre>' + MC.esc(e.indicazioni) + '</pre>' : '') + fb +
        '<div class="azioni"><button class="btn" data-id="' + e.id + '">Lavora nel CAD</button>' + (e.ha_foto ? '<a class="btn sec" href="/corso/esercizio/' + e.id + '/foto" download="esercizio_' + e.id + '.jpg">Scarica la foto</a>' : '') + '</div></section>';
    }).join('');
    document.querySelectorAll('[data-id]').forEach(function (b) {
      b.onclick = function () {
        var e = j.esercizi.find(function (x) { return String(x.id) === b.getAttribute('data-id'); });
        MC.scriviLocale('mcad-esercizio', {id: e.id, titolo: e.titolo, indicazioni: e.indicazioni, ha_foto: e.ha_foto});
        if (e.indicazioni) { try { localStorage.setItem('mcad-direttive-suggerite', e.indicazioni); } catch (er) {} }
        location.href = '/disegno';
      };
    });
  }).catch(function (e) { MC.messaggio($('msg'), e.message, 'err'); $('esercizi').innerHTML = ''; });
})();

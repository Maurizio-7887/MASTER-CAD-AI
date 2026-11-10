/* Elenco segnalazioni: l'utente vede le sue con la risposta, l'amministratore tutte e le gestisce. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var L = $('s-lista'), admin = L.getAttribute('data-admin') === '1', stati = L.getAttribute('data-stati').split('|'), tutte = [];
  var colore = {'nuova': 'att', 'in lavorazione': 'info', 'fatta': 'ok', 'scartata': 'ko'};
  function disegna() {
    var f = $('s-filtro').value, l = tutte.filter(function (s) { return !f || s.stato === f; });
    L.innerHTML = l.length ? l.map(function (s) {
      return '<section class="carta"><div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap"><h3 style="margin:0">n. ' + s.id + ' · ' + MC.esc(s.tipo_testo) + '</h3>' +
        '<span><span class="stato ' + (colore[s.stato] || 'info') + '">' + MC.esc(s.stato) + '</span> <small>' + MC.esc(s.nome) + ' · ' + MC.esc(s.creato.replace('T', ' ')) + (s.pagina ? ' · pagina ' + MC.esc(s.pagina) : '') + '</small></span></div>' +
        '<p style="white-space:pre-wrap">' + MC.esc(s.testo) + '</p>' +
        (s.ha_immagine ? '<p><a href="/api/segnalazioni/' + s.id + '/immagine" target="_blank" rel="noopener"><img src="/api/segnalazioni/' + s.id + '/immagine" alt="Immagine allegata" style="max-width:320px;max-height:220px;border-radius:8px;border:1px solid #d5dadd"></a></p>' : '') +
        (s.ha_progetto ? '<p><button class="btn sec" data-pezzo="' + s.id + '">Apri il pezzo allegato nel CAD</button></p>' : '') +
        (admin ? '<div class="azioni"><select data-stato="' + s.id + '" style="width:170px">' + stati.map(function (x) { return '<option' + (x === s.stato ? ' selected' : '') + '>' + x + '</option>'; }).join('') + '</select>' +
          '<input data-risp="' + s.id + '" placeholder="Risposta per ' + MC.esc(s.nome) + '" value="' + MC.esc(s.risposta || '') + '" style="flex:1;min-width:220px"><button class="btn" data-salva="' + s.id + '">Salva</button></div>'
          : (s.risposta ? '<p class="messaggio info">Risposta: ' + MC.esc(s.risposta) + '</p>' : '')) + '</section>';
    }).join('') : '<p class="vuoto-stato">Nessuna segnalazione' + (f ? ' in questo stato' : '') + '.</p>';
    document.querySelectorAll('[data-salva]').forEach(function (b) { b.onclick = async function () {
      var n = b.getAttribute('data-salva');
      try { await MC.api('/api/segnalazioni/' + n, {stato: document.querySelector('[data-stato="' + n + '"]').value, risposta: document.querySelector('[data-risp="' + n + '"]').value}); MC.messaggio($('msg'), 'Segnalazione n. ' + n + ' aggiornata.', 'ok'); carica(); }
      catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
    }; });
    document.querySelectorAll('[data-pezzo]').forEach(function (b) { b.onclick = async function () {
      var s = await MC.api('/api/segnalazioni/' + b.getAttribute('data-pezzo'));
      if (MC.progetto() && !confirm('Il pezzo aperto verrà sostituito da quello allegato. Continuo?')) return;
      MC.salvaProgetto(s.progetto); location.href = '/disegno#costruisci';
    }; });
  }
  async function carica() { tutte = await MC.api('/api/segnalazioni'); disegna(); }
  $('s-filtro').onchange = disegna;
  $('s-nuova').onclick = function () { MC.suggerisci(carica); };
  carica().catch(function (e) { MC.messaggio($('msg'), e.message, 'err'); });
})();

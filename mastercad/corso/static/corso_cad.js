/* Nel CAD, per gli allievi: banner dell'esercizio, pulsante Consegna e diario delle azioni per il docente.
   Registra i comandi usati e le chiamate al motore (foto, indicazioni, costruzione) e invia ogni 8 secondi. */
(function () {
  'use strict';
  if (!document.body.hasAttribute('data-allievo')) return;
  var CSRF = document.body.getAttribute('data-csrf');
  var es = null;
  try { es = JSON.parse(localStorage.getItem('mcad-esercizio') || 'null'); } catch (e) {}
  var coda = [];
  function registra(tipo, dettaglio) { coda.push({tipo: tipo, dettaglio: String(dettaglio || '').slice(0, 300), t: Date.now()}); }
  function progetto() { try { return JSON.parse(localStorage.getItem('mcad-progetto') || 'null'); } catch (e) { return null; } }
  var conProgetto = false;
  function invia() {
    if (!coda.length) return;
    var corpo = JSON.stringify({azioni: coda.splice(0), esercizio_id: es && es.id, progetto: conProgetto ? progetto() : null});
    conProgetto = false;
    fetch('/api/corso/allievo/azioni', {method: 'POST', keepalive: true, credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': CSRF}, body: corpo}).catch(function () {});
  }
  setInterval(invia, 8000);
  window.addEventListener('pagehide', function () { invia(); });
  // comandi della riga di comando e dei pulsanti
  var cmd = document.getElementById('cmd');
  if (cmd) cmd.addEventListener('keydown', function (e) { if (e.key === 'Enter' && cmd.value.trim()) registra('comando', cmd.value.trim().toUpperCase()); });
  document.querySelectorAll('[data-cmd]').forEach(function (b) { b.addEventListener('click', function () { registra('comando', b.getAttribute('data-cmd')); }); });
  // chiamate al motore
  var f0 = window.fetch;
  window.fetch = function (url, opz) {
    var u = String(url);
    if (u.indexOf('/api/reverse/foto') === 0) registra('foto', 'Foto analizzata');
    else if (u.indexOf('/api/progetto/direttive') === 0) { try { registra('indicazioni', JSON.parse(opz.body).testo); } catch (e) { registra('indicazioni', ''); } }
    else if (u.indexOf('/api/progetto/costruisci') === 0) { registra('costruisci', 'Pezzo ricostruito'); conProgetto = true; }
    else if (u.indexOf('/api/progetto/da-disegno') === 0) { try { registra('base', JSON.parse(opz.body).come); } catch (e) { registra('base', ''); } }
    return f0.apply(this, arguments);
  };
  registra('apertura', es ? 'Aperto il CAD per «' + es.titolo + '»' : 'Aperto il CAD');
  if (!es) return;
  // banner con la consegna
  var b = document.createElement('div');
  b.style.cssText = 'background:#ffe08a;color:#3a2a00;padding:8px 14px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;font:14px system-ui';
  b.innerHTML = '<b>Esercizio:</b> <span id="es-titolo"></span>' + (es.ha_foto ? ' · <a href="/corso/esercizio/' + es.id + '/foto" target="_blank" rel="noopener">vedi la foto</a>' : '') +
    '<span style="flex:1"></span><a href="/corso/allievo" style="color:#3a2a00">Torna agli esercizi</a><button id="es-consegna" style="background:#0070f2;color:#fff;border:0;border-radius:8px;padding:7px 14px;font-weight:700;cursor:pointer">Consegna il pezzo</button>';
  document.body.insertBefore(b, document.body.firstChild);
  document.getElementById('es-titolo').textContent = es.titolo;
  var dir = document.getElementById('prog-direttive');
  if (dir && !dir.value && es.indicazioni) dir.value = es.indicazioni;
  document.getElementById('es-consegna').onclick = async function () {
    var p = progetto();
    if (!p || !p.base) { if (window.MCAD) window.MCAD.scrivi('⛔ Prima costruisci il pezzo (ESTRUDI o RIVOLUZIONE), poi consegna.'); return; }
    var bt = this;
    bt.disabled = true; bt.textContent = 'Correggo…';
    invia();
    try {
      var r = await f0('/api/corso/allievo/consegna', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': CSRF}, body: JSON.stringify({esercizio_id: es.id, progetto: p})});
      var j = await r.json();
      if (!r.ok) throw new Error(j.error || 'Consegna non riuscita');
      var m = j.esito.messaggi.join('\n• ');
      if (window.MCAD) window.MCAD.scrivi('CONSEGNATO' + (j.esito.voto != null ? ' · voto automatico ' + j.esito.voto + '/10' : '') + '\n• ' + m);
      bt.textContent = j.esito.voto != null ? 'Consegnato · ' + j.esito.voto + '/10' : 'Consegnato';
    } catch (e) { bt.textContent = 'Consegna il pezzo'; if (window.MCAD) window.MCAD.scrivi('⛔ ' + e.message); }
    finally { bt.disabled = false; }
  };
})();

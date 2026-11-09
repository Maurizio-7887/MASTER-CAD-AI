/* MASTER CAD AI · reverse engineering da foto: invia la foto, riceve il contorno in mm e lo apre nella tavola. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); }, CSRF = document.body.getAttribute('data-csrf') || '';
  $('foto-rif').addEventListener('change', function () { $('foto-misura-box').hidden = this.value !== 'misura'; });
  $('foto-vai').addEventListener('click', async function () {
    var f = $('foto-file').files[0];
    if (!f) { $('foto-stato').textContent = 'Scegli prima una foto.'; return; }
    var fd = new FormData();
    var vista = $('foto-vista').value;
    fd.append('image', f); fd.append('vista', vista === 'fronte' ? 'alto' : vista); fd.append('riferimento', $('foto-rif').value);
    fd.append('misura', $('foto-misura').value); fd.append('misura_di', $('foto-misura-di').value);
    $('foto-vai').disabled = true; $('foto-stato').textContent = 'Analizzo la foto…';
    try {
      var r = await fetch('/api/reverse/foto', {method: 'POST', body: fd, credentials: 'same-origin', headers: {'X-CSRF-Token': CSRF}});
      if (r.status === 401) { location.href = '/login?expired=1'; return; }
      var j = await r.json();
      if (!r.ok) throw new Error(j.error || 'Analisi non riuscita');
      $('foto-anteprima').src = j.anteprima; $('foto-anteprima').hidden = false;
      var i = j.info, riass = j.vista === 'alto' ? ('Contorno ' + i.larghezza_mm + ' × ' + i.altezza_mm + ' mm, ' + i.fori + ' fori') : ('Profilo tornito lungo ' + i.lunghezza_mm + ' mm, diametro massimo ' + i.diametro_max_mm + ' mm');
      $('foto-stato').textContent = '✓ ' + riass + '. Aperto nella tavola: controlla con DIST, correggi, poi ' + j.comando_3d + '.';
      $('foto-avvisi').innerHTML = ''; j.avvisi.forEach(function (a) { var li = document.createElement('li'); li.textContent = a; $('foto-avvisi').appendChild(li); });
      if (vista === 'fronte' && window.MCADP) {      // la vista di fronte non va sulla tavola: entra direttamente nel progetto
        $('foto-stato').textContent = '✓ Vista di fronte ' + i.larghezza_mm + ' × ' + i.altezza_mm + ' mm: unita alla vista dall’alto nel progetto.';
        await window.MCADP.impostaBase('fronte', {entita: j.entita});
        return;
      }
      window.dispatchEvent(new CustomEvent('mcad:entita', {detail: {entita: j.entita, sostituisci: false,
        messaggio: 'Dalla foto: ' + riass + '. Controlla le quote (DIST, LISTA), correggi con i comandi, poi ' + j.comando_3d + (j.vista === 'lato' ? ' attorno all’asse X (predefinito).' : ' con lo spessore del pezzo.')}}));
    } catch (e) { $('foto-stato').textContent = '⛔ ' + e.message; }
    finally { $('foto-vai').disabled = false; }
  });
})();

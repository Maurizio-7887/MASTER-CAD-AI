(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var p = MC.riquadroPezzo($('pezzo'));
  if (!p) return;
  $('corpo').hidden = false;
  var ETI = {errore: ['ko', 'Errore'], attenzione: ['att', 'Attenzione'], consiglio: ['info', 'Consiglio']};
  async function controlla() {
    var b = $('ripeti');
    MC.occupato(b, true, 'Controllo…');
    MC.messaggio($('msg'), '');
    try {
      var j = await MC.api('/api/fattibilita', {progetto: MC.progetto()});
      $('kpi').innerHTML = '<div class="kpi-box"><small>Errori</small><b style="color:var(--rosso)">' + j.errori + '</b></div><div class="kpi-box"><small>Attenzioni</small><b style="color:var(--giallo)">' + j.attenzioni +
        '</b></div><div class="kpi-box"><small>Esito</small><b>' + (j.errori ? 'Da correggere' : j.attenzioni ? 'Fattibile con attenzione' : 'Fattibile') + '</b></div>';
      $('avvisi').innerHTML = '<tr><th>Livello</th><th>Dove</th><th>Problema</th><th>Come rimediare</th></tr>' + j.avvisi.map(function (a) {
        var e = ETI[a.livello];
        return '<tr><td><span class="stato ' + e[0] + '">' + e[1] + '</span></td><td>' + MC.esc(a.dove) + '</td><td>' + MC.esc(a.testo) + '</td><td>' + MC.esc(a.rimedio) + '</td></tr>';
      }).join('');
      MC.kpi('fattibilita', j.errori ? j.errori : (j.attenzioni ? j.attenzioni : 'OK'), j.errori ? 'errori' : (j.attenzioni ? 'attenzioni' : 'fattibile'));
    } catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
    finally { MC.occupato(b, false); }
  }
  $('ripeti').onclick = controlla;
  controlla();
})();

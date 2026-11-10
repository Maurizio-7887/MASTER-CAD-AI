/* Utenti: creazione con password temporanea, reimpostazione, disattivazione. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  function mostraPw(r) {
    $('u-pw').hidden = false;
    $('u-pw').innerHTML = 'Utente <b>' + MC.esc(r.username) + '</b> · password temporanea <code style="font-size:16px;user-select:all">' + MC.esc(r.password) + '</code><br><small>' + MC.esc(r.nota) + ' Indirizzo: ' + MC.esc(location.origin) + '/login</small>';
  }
  async function carica() {
    var l = await MC.api('/api/utenti');
    $('u-tab').innerHTML = '<tr><th>Utente</th><th>Nome</th><th>Ruolo</th><th>Stato</th><th>Ultimo accesso</th><th></th></tr>' + l.map(function (u) {
      return '<tr><td>' + MC.esc(u.username) + '</td><td>' + MC.esc(u.nome) + '</td><td>' + MC.esc(u.ruolo) + '</td><td>' +
        (!u.attivo ? '<span class="stato ko">disattivato</span>' : u.deve_cambiare ? '<span class="stato att">primo accesso da fare</span>' : '<span class="stato ok">attivo</span>') +
        '</td><td>' + MC.esc(u.ultimo_accesso ? u.ultimo_accesso.replace('T', ' ') : '—') + '</td><td style="white-space:nowrap">' +
        '<button class="btn sec" data-u="' + MC.esc(u.username) + '" data-a="reimposta">Nuova password</button> ' +
        '<button class="btn sec" data-u="' + MC.esc(u.username) + '" data-a="' + (u.attivo ? 'disattiva' : 'attiva') + '">' + (u.attivo ? 'Disattiva' : 'Riattiva') + '</button></td></tr>';
    }).join('');
    document.querySelectorAll('#u-tab [data-a]').forEach(function (b) { b.onclick = async function () {
      var a = b.getAttribute('data-a'), u = b.getAttribute('data-u');
      if (!confirm((a === 'reimposta' ? 'Generare una nuova password temporanea per «' : a === 'disattiva' ? 'Disattivare «' : 'Riattivare «') + u + '»?')) return;
      try { var r = await MC.api('/api/utenti/' + encodeURIComponent(u), {azione: a}); if (r.password) mostraPw(r); carica(); }
      catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
    }; });
  }
  $('u-crea').onclick = async function () {
    try {
      var r = await MC.api('/api/utenti', {username: $('u-user').value, nome: $('u-nome').value, ruolo: $('u-ruolo').value});
      mostraPw(r); $('u-user').value = ''; $('u-nome').value = ''; carica();
    } catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
  };
  carica().catch(function (e) { MC.messaggio($('msg'), e.message, 'err'); });
})();

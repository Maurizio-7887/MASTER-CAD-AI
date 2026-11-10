(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var p = MC.riquadroPezzo($('pezzo'));
  $('corpo').hidden = false;
  $('v-utente').value = MC.leggi('mcad-utente') || '';
  $('v-utente').onchange = function () { MC.scriviLocale('mcad-utente', this.value.trim()); };
  function decisione(d) {
    return '<div class="dec"><b>' + MC.esc(d.cosa) + '</b><br><small>' + MC.esc(new Date(d.quando).toLocaleString('it-IT')) + ' · ' + MC.esc(d.chi) +
      (d.norma ? ' · norma/calcolo: ' + MC.esc(d.norma) : '') + (d.verifica ? ' · verifica: ' + MC.esc(d.verifica) : '') + '</small></div>';
  }
  function apri(vid, nome) {
    MC.api('/api/versioni/' + vid).then(function (r) {
      if (MC.progetto() && !confirm('Il pezzo aperto verrà sostituito dalla versione ' + r.numero + ' di «' + r.nome + '». Continuo?')) return;
      MC.salvaProgetto(r.progetto);
      try { localStorage.removeItem('mcad-disegno'); } catch (e) {}
      location.href = '/disegno#costruisci';
    }).catch(function (e) { MC.messaggio($('msg'), e.message, 'err'); });
  }
  async function storico(uid) {
    var v = await MC.api('/api/versioni?uid=' + encodeURIComponent(uid || ''));
    var reg = (p && p.uid === uid ? p.registro || [] : []);
    var nuove = reg.slice(v.reduce(function (s, x) { return s + (x.decisioni || []).length; }, 0));
    $('v-registro').innerHTML = nuove.length ? '<h3>Decisioni non ancora in una versione</h3>' + nuove.map(decisione).join('') : '';
    if (!v.length) return;
    $('v-storico').innerHTML = v.map(function (x) {
      return '<div class="ver"><b>Versione ' + x.numero + '</b> — ' + MC.esc(x.messaggio) + '<br><small class="sotto">' + MC.esc(x.creato) + ' · ' + MC.esc(x.autore) + '</small>' +
        '<ul>' + x.differenze.map(function (d) { return '<li>' + MC.esc(d) + '</li>'; }).join('') + '</ul>' + (x.decisioni || []).map(decisione).join('') +
        '<button class="btn sec" data-v="' + x.id + '">Riapri questa versione</button></div>';
    }).join('');
    document.querySelectorAll('[data-v]').forEach(function (b) { b.onclick = function () { apri(b.getAttribute('data-v')); }; });
  }
  MC.api('/api/versioni/progetti').then(function (r) {
    $('v-progetti').innerHTML = r.length ? r.map(function (x) {
      return '<tr><td><a href="#" data-uid="' + MC.esc(x.uid) + '">' + MC.esc(x.nome) + '</a><br><small>v' + x.numero + ' · ' + MC.esc(x.creato) + ' · ' + MC.esc(x.autore) + '</small></td></tr>'; }).join('') : '<tr><td class="sotto">Nessuno.</td></tr>';
    document.querySelectorAll('[data-uid]').forEach(function (a) { a.onclick = function (e) { e.preventDefault(); $('v-titolo').textContent = 'Storico di «' + a.textContent + '»'; storico(a.getAttribute('data-uid')); }; });
  }).catch(function () {});
  if (p && p.uid) { $('v-titolo').textContent = 'Storico di «' + MC.nome() + '»'; storico(p.uid).catch(function (e) { MC.messaggio($('msg'), e.message, 'err'); }); }
})();

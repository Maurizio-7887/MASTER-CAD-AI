(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var mm = function (v) { return Number(v).toLocaleString('it-IT', {minimumFractionDigits: 3, maximumFractionDigits: 3}); };
  async function acc() {
    try {
      var r = await MC.api('/api/tolleranze/accoppiamento', {diametro: $('a-d').value, foro: $('a-f').value, albero: $('a-a').value});
      var colore = r.tipo === 'con gioco' ? 'ok' : r.tipo === 'incerto' ? 'att' : 'ko';
      $('a-out').innerHTML = '<div class="kpi-riga"><div class="kpi-box"><small>' + MC.esc(r.foro.testo) + '</small><b>' + mm(r.foro.min) + ' – ' + mm(r.foro.max) + '</b></div>' +
        '<div class="kpi-box"><small>' + MC.esc(r.albero.testo) + '</small><b>' + mm(r.albero.min) + ' – ' + mm(r.albero.max) + '</b></div></div>' +
        '<p><span class="stato ' + colore + '">Accoppiamento ' + MC.esc(r.tipo) + '</span> gioco da ' + MC.num(r.gioco_min_um, 0) + ' a ' + MC.num(r.gioco_max_um, 0) + ' µm (negativo = interferenza).<br>' + MC.esc(r.uso) + '. <small>Norma: ' + r.norma + '</small></p>';
    } catch (e) { $('a-out').innerHTML = '<div class="messaggio err">' + MC.esc(e.message) + '</div>'; }
  }
  $('a-calc').onclick = acc;
  document.querySelectorAll('[data-acc]').forEach(function (a) { a.onclick = function (e) { e.preventDefault(); var p = a.getAttribute('data-acc').split('/'); $('a-f').value = p[0]; $('a-a').value = p[1]; acc(); }; });
  var anelli = [{nome: 'Larghezza sede', nominale: 50, sup: 0.1, inf: -0.1, verso: 1}, {nome: 'Cuscinetto B', nominale: 20, sup: 0, inf: -0.12, verso: -1}, {nome: 'Distanziale', nominale: 29.5, sup: 0, inf: -0.1, verso: -1}];
  function tab() {
    $('c-tab').innerHTML = '<tr><th>Quota</th><th>Nominale</th><th>Sup</th><th>Inf</th><th>Verso</th><th></th></tr>' + anelli.map(function (a, i) {
      return '<tr>' + ['nome', 'nominale', 'sup', 'inf'].map(function (k) { return '<td><input data-i="' + i + '" data-k="' + k + '" value="' + MC.esc(a[k]) + '" style="width:' + (k === 'nome' ? 130 : 70) + 'px"></td>'; }).join('') +
        '<td><select data-i="' + i + '" data-k="verso"><option value="1"' + (a.verso > 0 ? ' selected' : '') + '>+</option><option value="-1"' + (a.verso < 0 ? ' selected' : '') + '>−</option></select></td><td><button class="btn sec" data-del="' + i + '">✕</button></td></tr>';
    }).join('');
    document.querySelectorAll('#c-tab [data-k]').forEach(function (x) { x.onchange = function () { var a = anelli[x.getAttribute('data-i')], k = x.getAttribute('data-k'); a[k] = k === 'nome' ? x.value : Number(String(x.value).replace(',', '.')); }; });
    document.querySelectorAll('#c-tab [data-del]').forEach(function (b) { b.onclick = function () { anelli.splice(Number(b.getAttribute('data-del')), 1); tab(); }; });
  }
  $('c-add').onclick = function () { anelli.push({nome: 'Quota', nominale: 10, sup: 0.05, inf: -0.05, verso: 1}); tab(); };
  $('c-calc').onclick = async function () {
    try {
      var r = await MC.api('/api/tolleranze/catena', {anelli: anelli});
      var ok = r.min_peggiore >= 0;
      $('c-out').innerHTML = '<div class="kpi-riga"><div class="kpi-box"><small>Nominale</small><b>' + mm(r.nominale) + '</b></div><div class="kpi-box"><small>Caso peggiore</small><b>' + mm(r.min_peggiore) + ' – ' + mm(r.max_peggiore) +
        '</b></div><div class="kpi-box"><small>Statistico (RSS)</small><b>' + mm(r.min_rss) + ' – ' + mm(r.max_rss) + '</b></div></div><p><span class="stato ' + (ok ? 'ok' : 'ko') + '">' + (ok ? 'Montaggio sempre possibile (gioco ≥ 0)' : 'Nel caso peggiore c\'è interferenza: rivedi le tolleranze') + '</span></p>';
    } catch (e) { $('c-out').innerHTML = '<div class="messaggio err">' + MC.esc(e.message) + '</div>'; }
  };
  tab(); acc();
})();

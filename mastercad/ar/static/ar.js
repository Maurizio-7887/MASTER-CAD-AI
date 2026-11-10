(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var p = MC.riquadroPezzo($('pezzo'));
  if (!p) return;
  $('corpo').hidden = false;
  MC.api('/api/ar', {progetto: MC.progetto(), nome: MC.nome()}).then(function (j) {
    $('mv').setAttribute('src', j.glb);
    $('qr').innerHTML = j.qr;
    $('link').innerHTML = '<a href="' + MC.esc(j.link) + '" target="_blank" rel="noopener">' + MC.esc(j.link) + '</a>';
    $('misure').textContent = 'Ingombro ' + j.misure + ' — in AR il pezzo appare a grandezza reale.';
    MC.kpi('ar', 'QR', 'pronto');
  }).catch(function (e) { $('qr').innerHTML = ''; MC.messaggio($('msg'), e.message, 'err'); });
})();

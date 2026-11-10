(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var p = MC.riquadroPezzo($('pezzo'));
  if (!p) return;
  $('corpo').hidden = false;
  $('q-rif').onchange = function () { $('q-misura-box').hidden = this.value !== 'misura'; };
  async function storico() {
    try {
      var r = await MC.api('/api/qualita/storico');
      $('storico').innerHTML = r.length ? '<tr><th>Data</th><th>Pezzo</th><th>Lotto</th><th>Esito</th></tr>' + r.map(function (c) {
        return '<tr><td>' + MC.esc(c.creato) + '</td><td>' + MC.esc(c.nome) + '</td><td>' + MC.esc(c.lotto || '') + '</td><td><span class="stato ' + (c.esito === 'CONFORME' ? 'ok' : 'ko') + '">' + MC.esc(c.esito) + '</span></td></tr>';
      }).join('') : '<tr><td class="vuoto-stato">Nessun controllo ancora.</td></tr>';
    } catch (e) {}
  }
  $('controlla').onclick = async function () {
    var f = $('q-foto').files[0];
    if (!f) { MC.messaggio($('msg'), 'Scegli la foto del pezzo prodotto', 'err'); return; }
    var b = this, fd = new FormData();
    fd.append('image', f);
    fd.append('progetto', JSON.stringify(MC.progetto()));
    fd.append('nome', MC.nome());
    [['riferimento', 'q-rif'], ['misura', 'q-misura'], ['misura_di', 'q-misura-di'], ['lotto', 'q-lotto'], ['operatore', 'q-op'], ['tol_pos', 'q-tpos'], ['tol_d', 'q-td'], ['tol_ing', 'q-ting']].forEach(function (c) { fd.append(c[0], $(c[1]).value); });
    MC.occupato(b, true, 'Misuro la foto…');
    MC.messaggio($('msg'), '');
    try {
      var j = await MC.api('/api/qualita/controlla', fd), ok = j.esito === 'CONFORME';
      var h = '<div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:flex-start"><div><h2 style="margin:0">Verbale di controllo n. ' + j.id + '</h2><div class="sotto" style="margin:2px 0 0">' +
        MC.esc(MC.nome()) + ' · ' + MC.esc(j.data) + ($('q-lotto').value ? ' · lotto ' + MC.esc($('q-lotto').value) : '') + ($('q-op').value ? ' · operatore ' + MC.esc($('q-op').value) : '') + '</div></div>' +
        '<span class="stato ' + (ok ? 'ok' : 'ko') + '" style="font-size:18px;padding:6px 14px">' + MC.esc(j.esito) + '</span></div>';
      h += '<div class="scorri" style="margin-top:12px"><table class="dati"><tr><th>Quota</th><th>Nominale</th><th>Misurato</th><th>Scostamento</th><th>Tolleranza</th><th>Esito</th></tr>' + j.righe.map(function (r) {
        return '<tr><td>' + MC.esc(r.voce) + '</td><td>' + MC.esc(r.nominale) + '</td><td>' + MC.esc(r.misurato) + '</td><td>' + MC.esc(r.scostamento) + '</td><td>' + MC.esc(r.tolleranza) +
          '</td><td><span class="stato ' + (r.esito === 'OK' ? 'ok' : 'ko') + '">' + r.esito + '</span>' + (r.nota ? ' <small>' + MC.esc(r.nota) + '</small>' : '') + '</td></tr>';
      }).join('') + '</table></div>';
      h += '<div class="due" style="margin-top:14px"><div><h3>Sovrapposizione</h3><div class="legenda"><span><i style="border-color:#1b8a4a"></i>progetto</span><span><i style="border-color:#d0342c;border-top-style:dashed"></i>foto</span></div><div id="sovrapposizione">' + j.sovrapposizione + '</div></div>' +
        '<div><h3>Foto analizzata</h3>' + (j.anteprima ? '<img alt="Foto analizzata" style="width:100%;border-radius:8px;border:1px solid var(--bordo)" src="' + j.anteprima + '">' : '') + '</div></div>';
      h += '<p class="sotto" style="font-size:12px;margin-top:10px">' + MC.esc(j.limiti) + (j.rotazione ? ' Foto ruotata di ' + j.rotazione + '° per allinearla al disegno.' : '') + '</p>';
      h += '<div class="azioni no-stampa"><button class="btn sec" onclick="window.print()">Stampa il verbale</button></div>';
      $('verbale').innerHTML = h;
      MC.kpi('qualita', ok ? 'OK' : 'KO', ok ? 'ultimo controllo' : 'non conforme');
      storico();
    } catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
    finally { MC.occupato(b, false); }
  };
  storico();
})();

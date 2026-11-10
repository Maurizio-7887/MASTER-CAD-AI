(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var corsoId = null, allievoId = null, ultimo = null;
  var errore = function (e) { MC.messaggio($('msg'), e.message || e, 'err'); window.scrollTo(0, 0); };
  var TIPI = {accesso: '🔑 Accesso', apertura: '📂 Apertura CAD', comando: '⌨️ Comando', foto: '📷 Foto', indicazioni: '📝 Indicazioni', costruisci: '🧊 Costruisce', base: '📐 Base', consegna: '📤 Consegna'};

  async function corsi() {
    var c = await MC.api('/api/corso/docente/corsi');
    $('corsi').innerHTML = c.length ? '<tr><th>Corso</th><th>Codice</th><th class="num">Allievi</th><th class="num">Da correggere</th></tr>' + c.map(function (x) {
      return '<tr class="cliccabile" data-c="' + x.id + '"><td><b>' + MC.esc(x.nome) + '</b><br><small>' + x.esercizi + ' esercizi · dal ' + x.creato + '</small></td><td>' + MC.esc(x.codice) + '</td><td class="num">' + x.allievi + '</td><td class="num">' + (x.da_correggere ? '<span class="stato att">' + x.da_correggere + '</span>' : '0') + '</td></tr>';
    }).join('') : '<tr><td class="vuoto-stato">Nessun corso: creane uno qui sotto.</td></tr>';
    document.querySelectorAll('[data-c]').forEach(function (r) { r.onclick = function () { apriCorso(Number(r.getAttribute('data-c'))); }; });
    if (!corsoId && c.length) apriCorso(c[0].id);
  }

  async function apriCorso(id) {
    corsoId = id;
    var j = await MC.api('/api/corso/docente/corso/' + id);
    $('corso').hidden = false; $('nuovo-es').hidden = false; $('allievo').hidden = true;
    $('c-nome').textContent = j.corso.nome; $('c-codice').textContent = j.corso.codice;
    var media = j.allievi.filter(function (a) { return a.media != null; });
    $('c-kpi').innerHTML = '<div class="kpi-box"><small>Allievi</small><b>' + j.allievi.length + '</b></div><div class="kpi-box"><small>Esercizi attivi</small><b>' + j.esercizi.filter(function (e) { return e.attivo; }).length +
      '</b></div><div class="kpi-box"><small>Media voti</small><b>' + (media.length ? MC.num(media.reduce(function (s, a) { return s + a.media; }, 0) / media.length, 1) : '—') + '</b></div>';
    $('c-es').innerHTML = j.esercizi.length ? '<tr><th>Esercizio</th><th>Foto</th><th>Voto</th><th class="num">Consegne</th><th></th></tr>' + j.esercizi.map(function (e) {
      return '<tr><td><b>' + MC.esc(e.titolo) + '</b>' + (e.attivo ? '' : ' <span class="stato att">nascosto</span>') + '</td><td>' + (e.ha_foto ? '📷' : '—') + '</td><td>' + (e.ha_soluzione ? 'automatico' : 'a mano') +
        '</td><td class="num">' + e.consegne + '</td><td><button class="btn sec" data-att="' + e.id + '">' + (e.attivo ? 'Nascondi' : 'Mostra') + '</button></td></tr>';
    }).join('') : '<tr><td class="vuoto-stato">Nessun esercizio: pubblicane uno con il modulo a sinistra.</td></tr>';
    document.querySelectorAll('[data-att]').forEach(function (b) { b.onclick = async function () { await MC.api('/api/corso/docente/esercizio/' + b.getAttribute('data-att') + '/attivo', {}); apriCorso(corsoId); }; });
    $('c-al').innerHTML = j.allievi.length ? '<tr><th>Allievo</th><th>Ultimo accesso</th><th class="num">Tempo lavorato</th><th class="num">Azioni</th><th class="num">Consegne</th><th class="num">Media</th></tr>' + j.allievi.map(function (a) {
      return '<tr class="cliccabile" data-a="' + a.id + '"><td><b>' + MC.esc(a.nome) + '</b></td><td>' + MC.esc(a.ultimo_accesso) + '</td><td class="num">' + MC.esc(a.tempo) + '</td><td class="num">' + a.azioni +
        '</td><td class="num">' + a.consegne + '</td><td class="num">' + (a.media != null ? MC.num(a.media, 1) : '—') + '</td></tr>';
    }).join('') : '<tr><td class="vuoto-stato">Ancora nessun allievo: dai il codice ' + MC.esc(j.corso.codice) + '.</td></tr>';
    document.querySelectorAll('[data-a]').forEach(function (r) { r.onclick = function () { apriAllievo(Number(r.getAttribute('data-a'))); }; });
  }

  async function apriAllievo(id) {
    allievoId = id;
    var j = await MC.api('/api/corso/docente/allievo/' + id);
    ultimo = j.ultimo_progetto;
    $('allievo').hidden = false;
    $('a-nome').textContent = j.allievo.nome;
    $('a-lavoro').hidden = !ultimo;
    $('a-kpi').innerHTML = '<div class="kpi-box"><small>Tempo lavorato</small><b>' + MC.esc(j.allievo.tempo) + '</b></div><div class="kpi-box"><small>Azioni registrate</small><b>' + j.azioni.length + '</b></div><div class="kpi-box"><small>Consegne</small><b>' + j.consegne.length + '</b></div>';
    $('a-consegne').innerHTML = j.consegne.length ? j.consegne.map(function (k) {
      var es = k.esito || {}, p = es.punteggi || {};
      return '<div class="carta" style="box-shadow:none;border:1px solid var(--bordo)"><div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap"><b>' + MC.esc(k.titolo) + '</b><span>' + MC.esc(k.creato) + '</span></div>' +
        '<div class="kpi-riga"><div class="kpi-box"><small>Voto automatico</small><b>' + MC.num(k.voto_auto, 1) + '</b></div>' + (p.volume != null ? '<div class="kpi-box"><small>Volumi coincidenti</small><b>' + MC.num(p.volume, 0) + '%</b></div><div class="kpi-box"><small>Fori giusti</small><b>' + MC.num(p.fori, 0) + '%</b></div><div class="kpi-box"><small>Ingombri</small><b>' + MC.num(p.ingombro, 0) + '%</b></div>' + (p.lavorazioni != null ? '<div class="kpi-box"><small>Lavorazioni</small><b>' + MC.num(p.lavorazioni, 0) + '%</b></div>' : '') : '') + '</div>' +
        '<ul style="margin:0 0 8px;padding-left:18px">' + (es.messaggi || []).map(function (m) { return '<li>' + MC.esc(m) + '</li>'; }).join('') + '</ul>' +
        '<div class="due"><div><label>Voto del docente (vuoto = conferma automatico)</label><input type="number" step="0.5" min="0" max="10" data-voto="' + k.id + '" value="' + (k.voto_docente != null ? k.voto_docente : '') + '"></div>' +
        '<div><label>Commento per l\'allievo</label><input data-comm="' + k.id + '" value="' + MC.esc(k.commento || '') + '"></div></div>' +
        '<div class="azioni"><button class="btn" data-salva="' + k.id + '">Salva correzione</button><button class="btn sec" data-apri="' + k.id + '">Apri la consegna nel CAD</button></div></div>';
    }).join('') : '<p class="sotto">Nessuna consegna.</p>';
    j.consegne.forEach(function (k) {
      document.querySelector('[data-salva="' + k.id + '"]').onclick = async function () {
        try { await MC.api('/api/corso/docente/consegna/' + k.id, {voto: document.querySelector('[data-voto="' + k.id + '"]').value, commento: document.querySelector('[data-comm="' + k.id + '"]').value}); this.textContent = 'Salvato ✓'; apriCorso(corsoId); }
        catch (e) { errore(e); }
      };
      document.querySelector('[data-apri="' + k.id + '"]').onclick = function () { apriNelCad(k.progetto, j.allievo.nome + ' · ' + k.titolo); };
    });
    $('a-diario').innerHTML = '<tr><th>Quando</th><th>Esercizio</th><th>Azione</th><th>Dettaglio</th></tr>' + j.azioni.map(function (z) {
      return '<tr><td style="white-space:nowrap">' + MC.esc(z.ts) + '</td><td>' + MC.esc(z.titolo || '') + '</td><td style="white-space:nowrap">' + (TIPI[z.tipo] || MC.esc(z.tipo)) + '</td><td>' + MC.esc(z.dettaglio) + '</td></tr>';
    }).join('');
    $('allievo').scrollIntoView({behavior: 'smooth'});
  }

  function apriNelCad(p, nome) {
    if (!p) return;
    if (MC.progetto() && !confirm('Il pezzo aperto verrà sostituito dal lavoro dell\'allievo. Continuo?')) return;
    p = JSON.parse(JSON.stringify(p)); p.nome = nome;
    MC.salvaProgetto(p);
    try { localStorage.removeItem('mcad-disegno'); } catch (e) {}
    location.href = '/disegno#costruisci';
  }
  $('a-lavoro').onclick = function () { apriNelCad(ultimo, $('a-nome').textContent + ' · lavoro in corso'); };
  $('a-pin').onclick = async function () {
    try { var j = await MC.api('/api/corso/docente/allievo/' + allievoId + '/pin', {}); MC.messaggio($('msg'), 'Nuovo PIN per ' + $('a-nome').textContent + ': ' + j.pin + ' (comunicalo all\'allievo)', 'ok'); window.scrollTo(0, 0); }
    catch (e) { errore(e); }
  };
  $('crea-corso').onclick = async function () {
    try { var j = await MC.api('/api/corso/docente/corsi', {nome: $('nuovo-corso').value}); $('nuovo-corso').value = ''; corsoId = j.id; await corsi(); apriCorso(j.id); MC.messaggio($('msg'), 'Corso creato. Codice per gli allievi: ' + j.codice, 'ok'); }
    catch (e) { errore(e); }
  };
  $('e-sol-nome').textContent = MC.progetto() ? MC.nome() : 'nessun pezzo aperto';
  if (!MC.progetto()) { $('e-sol').checked = false; $('e-sol').disabled = true; }
  $('crea-es').onclick = async function () {
    var fd = new FormData(), b = this;
    fd.append('corso_id', corsoId); fd.append('titolo', $('e-titolo').value); fd.append('consegna', $('e-consegna').value); fd.append('indicazioni', $('e-ind').value);
    if ($('e-foto').files[0]) fd.append('foto', $('e-foto').files[0]);
    if ($('e-sol').checked && MC.progetto()) fd.append('riferimento', JSON.stringify(MC.progetto()));
    MC.occupato(b, true, 'Pubblico…');
    try { await MC.api('/api/corso/docente/esercizi', fd); ['e-titolo', 'e-consegna', 'e-ind', 'e-foto'].forEach(function (k) { $(k).value = ''; }); MC.messaggio($('msg'), 'Esercizio pubblicato: gli allievi lo vedono subito.', 'ok'); apriCorso(corsoId); }
    catch (e) { errore(e); }
    finally { MC.occupato(b, false); }
  };
  corsi().catch(errore);
})();

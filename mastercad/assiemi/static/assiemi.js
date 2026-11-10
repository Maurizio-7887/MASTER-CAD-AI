(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var nuovoId = function () { return Math.random().toString(36).slice(2, 10); };
  var A = MC.leggi('mcad-assieme') || {uid: nuovoId(), nome: 'Nuovo assieme', componenti: []};
  var proposte = [], esito = null;
  var salvaLocale = function () { MC.scriviLocale('mcad-assieme', A); };
  $('a-nome').value = A.nome;
  $('a-nome').onchange = function () { A.nome = this.value.trim() || 'Assieme'; salvaLocale(); };

  function pezzi() {
    $('t-pezzi').innerHTML = A.componenti.length ? '<tr><th>Pezzo</th><th>X</th><th>Y</th><th>Z</th><th>Rot.</th><th>Capov.</th><th></th></tr>' + A.componenti.map(function (c, i) {
      var n = function (k, j) { return '<input type="number" step="0.5" style="width:62px" data-i="' + i + '" data-p="' + j + '" value="' + Number((c.pos || [0, 0, 0])[j]) + '">'; };
      return '<tr><td><b>' + MC.esc(c.nome) + '</b>' + (i === 0 ? '<br><small>base fissa</small>' : '') + '</td><td>' + n('x', 0) + '</td><td>' + n('y', 1) + '</td><td>' + n('z', 2) + '</td>' +
        '<td><select data-i="' + i + '" data-k="rz">' + [0, 90, 180, 270].map(function (r) { return '<option' + (Number(c.rz || 0) === r ? ' selected' : '') + '>' + r + '</option>'; }).join('') + '</select></td>' +
        '<td><input type="checkbox" style="width:auto" data-i="' + i + '" data-k="capovolto"' + (c.capovolto ? ' checked' : '') + '></td><td><button class="btn sec" data-del="' + i + '">✕</button></td></tr>';
    }).join('') : '<tr><td class="sotto">Nessun pezzo: aggiungi il pezzo aperto nel CAD o un progetto salvato.</td></tr>';
    document.querySelectorAll('#t-pezzi [data-p]').forEach(function (x) { x.onchange = function () { var c = A.componenti[x.getAttribute('data-i')]; c.pos = c.pos || [0, 0, 0]; c.pos[Number(x.getAttribute('data-p'))] = Number(x.value) || 0; salvaLocale(); }; });
    document.querySelectorAll('#t-pezzi [data-k]').forEach(function (x) { x.onchange = function () { var c = A.componenti[x.getAttribute('data-i')]; c[x.getAttribute('data-k')] = x.type === 'checkbox' ? x.checked : Number(x.value); salvaLocale(); }; });
    document.querySelectorAll('#t-pezzi [data-del]').forEach(function (b) { b.onclick = function () { A.componenti.splice(Number(b.getAttribute('data-del')), 1); salvaLocale(); pezzi(); }; });
    salvaLocale();
  }
  function aggiungi(progetto, nome) {
    if (A.componenti.length >= 20) { MC.messaggio($('msg'), 'Massimo 20 pezzi per assieme.', 'err'); return; }
    var p = JSON.parse(JSON.stringify(progetto)); delete p.registro; delete p._costo10;
    A.componenti.push({id: nuovoId(), tipo: 'pezzo', nome: nome || p.nome || 'Pezzo ' + (A.componenti.length + 1), progetto: p, pos: [0, 0, 0], rz: 0, capovolto: false,
      materiale: p.materiale || (MC.leggi('mcad-cartiglio') || {}).materiale || 'S235'});
    proposte = []; $('proposte').innerHTML = ''; $('monta').hidden = true;
    pezzi();
  }
  $('add-aperto').onclick = function () {
    var p = MC.progetto();
    if (!p) { MC.messaggio($('msg'), 'Nessun pezzo aperto nel CAD.', 'err'); return; }
    var nome = MC.nome(), n = A.componenti.filter(function (c) { return c.nome.indexOf(nome) === 0; }).length;
    aggiungi(p, n ? nome + ' (' + (n + 1) + ')' : nome);
  };
  MC.api('/api/versioni/progetti').then(function (r) {
    r.forEach(function (x) { var o = document.createElement('option'); o.value = x.uid; o.textContent = x.nome + ' (v' + x.numero + ')'; $('add-versione').appendChild(o); });
  }).catch(function () {});
  $('add-versione').onchange = async function () {
    var uid = this.value; this.value = '';
    if (!uid) return;
    try { var v = await MC.api('/api/versioni?uid=' + encodeURIComponent(uid)); var r = await MC.api('/api/versioni/' + v[0].id); aggiungi(r.progetto, r.nome); }
    catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
  };
  MC.api('/api/assiemi').then(function (r) {
    r.forEach(function (x) { var o = document.createElement('option'); o.value = x.uid; o.textContent = x.nome + ' · ' + x.pezzi + ' pezzi · ' + x.aggiornato; $('a-aperti').appendChild(o); });
  }).catch(function () {});
  $('a-aperti').onchange = async function () {
    if (!this.value) return;
    try { A = await MC.api('/api/assiemi/' + encodeURIComponent(this.value)); $('a-nome').value = A.nome; proposte = A.montaggi || []; mostraProposte(); pezzi(); }
    catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
  };
  $('a-nuovo').onclick = function () { A = {uid: nuovoId(), nome: 'Nuovo assieme', componenti: []}; $('a-nome').value = A.nome; proposte = []; $('proposte').innerHTML = ''; pezzi(); };
  $('a-salva').onclick = async function () {
    A.nome = $('a-nome').value.trim() || 'Assieme'; A.montaggi = proposte.filter(function (p) { return p.scelta !== false; });
    try { await MC.api('/api/assiemi', {assieme: A}); MC.messaggio($('msg'), 'Assieme salvato.', 'ok'); } catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
  };

  function mostraProposte() {
    $('proposte').innerHTML = proposte.length ? proposte.map(function (p, i) {
      return '<label class="prop"><input type="checkbox" data-pr="' + i + '"' + (p.scelta !== false ? ' checked' : '') + '><span><b>' + (p.tipo === 'impila' ? '🧩 ' : '⚙ ') + MC.esc(p.descrizione) + '</b></span></label>';
    }).join('') : '<p class="sotto">Nessuna proposta: dai lo scopo ai fori nel CAD (foro spina, passaggio vite, filetto, sede cuscinetto) in modo che due pezzi abbiano fori corrispondenti.</p>';
    document.querySelectorAll('[data-pr]').forEach(function (x) { x.onchange = function () { proposte[x.getAttribute('data-pr')].scelta = x.checked; }; });
    $('monta').hidden = !A.componenti.length;
  }
  $('proponi').onclick = async function () {
    var b = this; MC.occupato(b, true, 'Leggo lo scopo dei fori…'); MC.messaggio($('msg'), '');
    try { var r = await MC.api('/api/assiemi/proponi', {assieme: A}); proposte = r.proposte; mostraProposte(); }
    catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
    finally { MC.occupato(b, false); }
  };
  var ETI = {ok: ['ok', 'OK'], attenzione: ['att', 'Attenzione'], errore: ['ko', 'Errore']};
  $('monta').onclick = async function () {
    var b = this; MC.occupato(b, true, 'Monto e verifico…'); MC.messaggio($('msg'), '');
    try {
      var scelte = proposte.filter(function (p) { return p.scelta !== false; });
      var r = await MC.api('/api/assiemi/monta', {assieme: A, montaggi: scelte});
      esito = r;
      // le posizioni calcolate tornano nei pezzi
      r.componenti.forEach(function (c) { var x = A.componenti.find(function (y) { return y.id === c.id; }); if (x) { x.pos = c.pos; x.rz = c.rz; x.capovolto = c.capovolto; } });
      pezzi();
      $('vista').hidden = $('verifiche').hidden = $('distinta').hidden = false;
      $('mv').setAttribute('src', r.glb);
      $('qr').innerHTML = r.qr; $('link-ar').href = r.link_ar;
      $('t-ver').innerHTML = '<tr><th>Esito</th><th>Cosa</th><th>Verifica</th><th>Norma</th></tr>' + r.verifiche.map(function (v) {
        var e = ETI[v.livello] || ETI.ok; return '<tr><td><span class="stato ' + e[0] + '">' + e[1] + '</span></td><td>' + MC.esc(v.voce) + '</td><td>' + MC.esc(v.testo) + '</td><td><small>' + MC.esc(v.norma || '') + '</small></td></tr>'; }).join('');
      $('t-dist').innerHTML = '<tr><th>Liv.</th><th>Descrizione</th><th>Tipo</th><th>Materiale / norma</th><th class="num">Q.tà</th><th class="num">Massa kg</th></tr>' +
        '<tr><td>1</td><td><b>' + MC.esc(A.nome) + '</b></td><td>Assieme</td><td></td><td class="num">1</td><td class="num">' + MC.num(r.distinta.reduce(function (s, d) { return s + (d.massa_kg || 0) * d.quantita; }, 0), 2) + '</td></tr>' +
        r.distinta.map(function (d) { return '<tr><td>' + d.livello + '</td><td>' + MC.esc(d.descrizione) + '</td><td>' + MC.esc(d.tipo) + '</td><td>' + MC.esc(d.materiale || d.norma) + '</td><td class="num">' + d.quantita + '</td><td class="num">' + (d.massa_kg != null ? MC.num(d.massa_kg, 3) : '—') + '</td></tr>'; }).join('');
      var gen = r.componenti.filter(function (c) { return c.generato; });
      $('generati').innerHTML = gen.length ? '<h3 style="margin-top:12px">Pezzi generati dal montaggio</h3>' + gen.map(function (c) { return '<p>' + MC.esc(c.nome) + ' <button class="btn sec" data-apri="' + MC.esc(c.id) + '">Apri nel CAD (tavola, ciclo, preventivo)</button></p>'; }).join('') : '';
      gdt(r); istruzioni(r);
      document.querySelectorAll('[data-apri]').forEach(function (x) { x.onclick = function () { apriNelCad(r.componenti.find(function (c) { return c.id === x.getAttribute('data-apri'); })); }; });
      var err = r.verifiche.filter(function (v) { return v.livello === 'errore'; }).length;
      MC.kpi('assiemi', err ? err : 'OK', err ? 'errori di montaggio' : 'montaggio verificato');
      MC.scriviLocale('mcad-assieme', A);
    } catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
    finally { MC.occupato(b, false); }
  };
  function apriNelCad(c) {
    var p = JSON.parse(JSON.stringify(c.progetto_tollerato || c.progetto)), tg = c.tolleranze_geometriche;
    p.uid = (!c.generato && c.progetto.uid) || nuovoId() + nuovoId();     // stesso pezzo, stessa storia delle versioni
    p.nome = p.nome || c.nome;
    var reg = p.registro || [];
    reg.push({quando: new Date().toISOString(), chi: MC.leggi('mcad-utente') || 'Ufficio tecnico',
      cosa: c.generato ? 'Generato dal montaggio dell\'assieme «' + A.nome + '»' : 'Tolleranze geometriche dedotte dall\'assieme «' + A.nome + '»' + (tg && tg.in_opera.length ? '; fori spina alesati in opera' : ''),
      norma: c.generato ? (p.quote_funzionali || []).map(function (q) { return q.norma; }).join('; ') : 'ISO 1101, ISO 2692, ISO 10578'});
    p.registro = reg;
    if (MC.progetto() && !confirm('Il pezzo aperto verrà sostituito da «' + c.nome + '». Continuo?')) return;
    MC.salvaProgetto(p); try { localStorage.removeItem('mcad-disegno'); } catch (e) {} location.href = '/disegno#costruisci';
  }
  var MOD = {M: 'Ⓜ', P: 'Ⓟ'};
  function fcf(v) {
    var val = (v.diametrale ? 'Ø' : '') + String(v.valore).replace('.', ',');
    var m = v.modificatori || [];
    if (m.length) val += ' ' + MOD[m[0]] + (m[1] != null ? ' ' + String(m[1]).replace('.', ',') : '');
    return '<span class="fcf" title="' + MC.esc(v.nome) + '"><b>' + MC.esc(v.segno) + '</b><b>' + MC.esc(val) + '</b>' + (v.riferimenti || []).map(function (x) { return '<b>' + MC.esc(x) + '</b>'; }).join('') + '</span>';
  }
  function gdt(r) {
    var con = r.componenti.filter(function (c) { return c.tolleranze_geometriche && c.tolleranze_geometriche.voci.length; });
    $('gdt').hidden = !con.length;
    $('gdt-pezzi').innerHTML = con.map(function (c) {
      var t = c.tolleranze_geometriche;
      return '<div class="gdt-p"><h3>' + MC.esc(c.nome) + ' <button class="btn sec" data-apri="' + MC.esc(c.id) + '">Apri nel CAD con le tolleranze</button></h3>' +
        '<small>Riferimenti: ' + t.riferimenti.map(function (x) { return '<b>' + MC.esc(x.lettera) + '</b> = ' + MC.esc(x.elemento); }).join(' · ') + '</small>' +
        (t.in_opera.length ? '<p class="messaggio" style="margin:6px 0">🔩 ' + MC.esc(t.in_opera[0].perche) + '</p>' : '') +
        '<div class="scorri"><table class="dati"><tr><th>Riquadro</th><th>Elemento</th><th>Perché</th><th>Controllo</th><th>Officina</th></tr>' + t.voci.map(function (v) {
          return '<tr><td>' + fcf(v) + '</td><td>' + MC.esc(v.elemento) + '</td><td><details><summary>perché</summary>' + MC.esc(v.perche) + ' <small>(' + MC.esc(v.norma) + ')</small></details></td><td>' + MC.esc(v.controllo) +
            '</td><td>' + (v.ok_officina ? '<span class="stato ok">OK</span> <small>' + MC.esc(v.capacita.macchina) + '</small>' : '<span class="stato att">Attenzione</span> <small>' + MC.esc(v.consiglio || '') + '</small>') + '</td></tr>';
        }).join('') + '</table></div></div>';
    }).join('');
  }
  var montaggio = null;
  function istruzioni(r, conferme) {
    var ist = r.istruzioni; montaggio = r.montaggio;
    $('istr').hidden = false;
    $('m-qr').innerHTML = r.montaggio.qr; $('m-link').href = r.montaggio.link;
    $('m-sintesi').textContent = ist.passi.length + ' passi · ' + MC.num(ist.tempo_min, 1) + ' min · costo montaggio ' + MC.num(ist.costo, 2) + ' € (banco ' + MC.num(ist.costo_banco_ora, 0) + ' €/h). ' + ist.nota;
    var conf = conferme || [];
    $('m-passi').innerHTML = ist.passi.map(function (p) {
      var c = conf.filter(function (x) { return x.passo === p.n; }).pop();
      return '<li><b>' + MC.esc(p.titolo) + '</b>' + (c ? ' <span class="stato ' + (c.esito === 'ok' ? 'ok">fatto' : 'ko">problema') + '</span> <small>' + MC.esc(c.operatore + ' · ' + c.quando.replace('T', ' ') + (c.nota ? ' · «' + c.nota + '»' : '')) + '</small>' : '') +
        '<ul>' + p.azioni.map(function (a) { return '<li>' + MC.esc(a) + '</li>'; }).join('') + '</ul>' +
        '<div class="meta">' + MC.num(p.tempo_min, 1) + ' min' + (p.attrezzi.length ? ' · 🔧 ' + MC.esc(p.attrezzi.join(' · ')) : '') + (p.controllo ? ' · ✔ ' + MC.esc(p.controllo) : '') + '</div></li>';
    }).join('');
  }
  $('m-aggiorna').onclick = async function () {
    if (!montaggio || !esito) return;
    try { var r = await MC.api('/api/assiemi/montaggio/' + montaggio.token); istruzioni(esito, r.conferme); MC.messaggio($('msg'), r.conferme.length + ' conferme dal montatore.', 'ok'); }
    catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
  };
  $('m-stampa').onclick = function () { if (montaggio) window.open(montaggio.link, '_blank', 'noopener'); };
  $('v-normale').onclick = function () { if (esito) $('mv').setAttribute('src', esito.glb); };
  $('v-esploso').onclick = function () { if (esito) $('mv').setAttribute('src', esito.glb_esploso); };
  $('csv').onclick = function () {
    if (!esito) return;
    var righe = [['Livello', 'Descrizione', 'Tipo', 'Materiale/Norma', 'Quantita', 'Massa kg']].concat(esito.distinta.map(function (d) { return [d.livello, d.descrizione, d.tipo, d.materiale || d.norma, d.quantita, d.massa_kg == null ? '' : d.massa_kg]; }));
    var csv = righe.map(function (r) { return r.map(function (v) { return '"' + String(v).replace(/"/g, '""') + '"'; }).join(';'); }).join('\r\n');
    var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(['﻿' + csv], {type: 'text/csv'})); a.download = (A.nome || 'assieme').replace(/[^\w\-]+/g, '_') + '_distinta.csv'; document.body.appendChild(a); a.click(); setTimeout(function () { a.remove(); }, 500);
  };
  pezzi();
})();

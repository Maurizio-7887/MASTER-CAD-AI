(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var C = JSON.parse($('cataloghi').textContent), O = null;
  var num = function (v) { return v == null ? '' : v; };
  function rendi() {
    $('t-mac').innerHTML = '<tr><th>Nome</th><th>Tipo</th><th>X</th><th>Y</th><th>Z</th><th>Ø max</th><th>Lungh.</th><th title="Precisione che la macchina garantisce su posizione e forma (mm)">Precis. mm</th><th>€/ora</th><th>Attiva</th><th></th></tr>' + O.macchine.map(function (m, i) {
      return '<tr><td><input data-m="' + i + '" data-k="nome" value="' + MC.esc(m.nome) + '"></td><td><select data-m="' + i + '" data-k="tipo">' + Object.keys(C.tipi).map(function (k) { return '<option value="' + k + '"' + (m.tipo === k ? ' selected' : '') + '>' + MC.esc(C.tipi[k]) + '</option>'; }).join('') + '</select></td>' +
        ['x', 'y', 'z', 'diametro', 'lunghezza', 'precisione', 'costo_ora'].map(function (k) { return '<td><input class="n" type="number" data-m="' + i + '" data-k="' + k + '"' + (k === 'precisione' ? ' step="0.001"' : '') + ' value="' + num(m[k]) + '"></td>'; }).join('') +
        '<td><input type="checkbox" style="width:auto" data-m="' + i + '" data-k="attiva"' + (m.attiva !== false ? ' checked' : '') + '></td><td><button class="btn sec" data-delm="' + i + '">✕</button></td></tr>';
    }).join('');
    $('t-ter').innerHTML = '<tr><th>Nome</th><th>Lavorazioni</th><th>€/ora</th><th>Giorni</th><th></th></tr>' + O.terzisti.map(function (t, i) {
      return '<tr><td><input data-t="' + i + '" data-k="nome" value="' + MC.esc(t.nome) + '"></td><td>' + Object.keys(C.lavorazioni).map(function (k) {
        return '<label style="display:inline-flex;gap:4px;margin:2px 8px 2px 0;color:var(--testo)"><input type="checkbox" style="width:auto" data-t="' + i + '" data-l="' + k + '"' + (t.lavorazioni.indexOf(k) >= 0 ? ' checked' : '') + '>' + MC.esc(C.lavorazioni[k]) + '</label>'; }).join('') +
        '</td><td><input class="n" type="number" data-t="' + i + '" data-k="costo_ora" value="' + num(t.costo_ora) + '"></td><td><input class="n" type="number" data-t="' + i + '" data-k="giorni" value="' + num(t.giorni) + '"></td><td><button class="btn sec" data-delt="' + i + '">✕</button></td></tr>';
    }).join('');
    $('t-mat').innerHTML = Object.keys(C.materiali).map(function (k) { return '<tr><td>' + MC.esc(C.materiali[k]) + '</td><td><input class="n" type="number" step="0.01" data-mat="' + k + '" value="' + num((O.materiali[k] || {}).euro_kg) + '"></td></tr>'; }).join('');
    $('t-tr').innerHTML = Object.keys(C.trattamenti).filter(function (k) { return k !== 'nessuno'; }).map(function (k) { return '<tr><td>' + MC.esc(C.trattamenti[k]) + '</td><td><input class="n" type="number" step="0.01" data-tr="' + k + '" value="' + num((O.trattamenti[k] || {}).euro_kg) + '"></td></tr>'; }).join('');
    $('t-costi').innerHTML = [['banco', 'Banco e controllo €/ora'], ['attrezzaggio', 'Attrezzaggio €/ora'], ['margine', 'Margine %'], ['scarto', 'Scarto %']].map(function (c) {
      return '<tr><td>' + c[1] + '</td><td><input class="n" type="number" data-c="' + c[0] + '" value="' + num(O.costi[c[0]]) + '"></td></tr>'; }).join('');
    document.querySelectorAll('[data-delm]').forEach(function (b) { b.onclick = function () { leggiForm(); O.macchine.splice(Number(b.getAttribute('data-delm')), 1); rendi(); }; });
    document.querySelectorAll('[data-delt]').forEach(function (b) { b.onclick = function () { leggiForm(); O.terzisti.splice(Number(b.getAttribute('data-delt')), 1); rendi(); }; });
  }
  function leggiForm() {
    document.querySelectorAll('[data-m]').forEach(function (x) { var m = O.macchine[x.getAttribute('data-m')], k = x.getAttribute('data-k'); m[k] = x.type === 'checkbox' ? x.checked : x.type === 'number' ? (x.value === '' ? null : Number(x.value)) : x.value; });
    O.terzisti.forEach(function (t) { t.lavorazioni = []; });
    document.querySelectorAll('[data-t]').forEach(function (x) {
      var t = O.terzisti[x.getAttribute('data-t')];
      if (x.hasAttribute('data-l')) { if (x.checked) t.lavorazioni.push(x.getAttribute('data-l')); }
      else t[x.getAttribute('data-k')] = x.type === 'number' ? Number(x.value || 0) : x.value;
    });
    document.querySelectorAll('[data-mat]').forEach(function (x) { if (x.value !== '') O.materiali[x.getAttribute('data-mat')] = {euro_kg: Number(x.value)}; });
    document.querySelectorAll('[data-tr]').forEach(function (x) { if (x.value !== '') O.trattamenti[x.getAttribute('data-tr')] = {euro_kg: Number(x.value)}; });
    document.querySelectorAll('[data-c]').forEach(function (x) { O.costi[x.getAttribute('data-c')] = Number(x.value || 0); });
    O.macchine.forEach(function (m) { ['x', 'y', 'z', 'diametro', 'lunghezza', 'precisione'].forEach(function (k) { if (m[k] == null) delete m[k]; }); });
  }
  $('add-mac').onclick = function () { leggiForm(); O.macchine.push({nome: 'Nuova macchina', tipo: 'fresa', x: 600, y: 400, z: 400, costo_ora: 50, attiva: true}); rendi(); };
  $('add-ter').onclick = function () { leggiForm(); O.terzisti.push({nome: 'Nuovo terzista', lavorazioni: [], costo_ora: 60, giorni: 7}); rendi(); };
  $('salva').onclick = async function () {
    leggiForm();
    var b = this; MC.occupato(b, true, 'Salvo…');
    try { var j = await MC.api('/api/officina', O); O = j.officina; rendi(); MC.messaggio($('msg'), 'Officina salvata: ciclo, preventivo e fattibilità useranno questi dati.', 'ok'); }
    catch (e) { MC.messaggio($('msg'), e.message, 'err'); }
    finally { MC.occupato(b, false); }
  };
  MC.api('/api/officina').then(function (o) { O = o; rendi(); }).catch(function (e) { MC.messaggio($('msg'), e.message, 'err'); });
})();

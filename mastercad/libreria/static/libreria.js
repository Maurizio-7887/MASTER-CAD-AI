(function () {
  'use strict';
  document.querySelectorAll('form[data-codice]').forEach(function (f) {
    f.onsubmit = async function (ev) {
      ev.preventDefault();
      var par = {};
      Array.prototype.forEach.call(f.elements, function (el) { if (el.name) par[el.name] = el.type === 'checkbox' ? el.checked : el.value; });
      var b = f.querySelector('button');
      MC.occupato(b, true, 'Preparo…');
      try {
        var j = await MC.api('/api/libreria/genera', {codice: f.getAttribute('data-codice'), parametri: par});
        if (MC.progetto() && !confirm('Il pezzo aperto («' + MC.nome() + '») verrà sostituito da «' + j.nome + '». Continuo?')) return;
        MC.salvaProgetto(j.progetto);
        MC.scriviLocale('mcad-disegno', j.tavola);
        location.href = '/disegno#costruisci';
      } catch (e) { MC.messaggio(document.getElementById('msg'), e.message, 'err'); window.scrollTo(0, 0); }
      finally { MC.occupato(b, false); }
    };
  });
})();

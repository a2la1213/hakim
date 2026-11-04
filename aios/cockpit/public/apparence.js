/* (04/11, 21:05, Ahmed : « pour toute l'appli, un mode sombre, un mode clair et un mode automatique avec le smartphone ») son apparence :
   chargée en tête de chaque page, avant theme.css (pas de flash) ; le choix (auto, clair, sombre) est gardé pour toutes les pages ;
   auto suit le téléphone ou le Mac (prefers-color-scheme), et l'appli Android le prévient quand il change (Apparence.systeme()). */
(function () {
  var CLE = 'cockpit-apparence';
  var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;
  function choix() { try { var c = localStorage.getItem(CLE); return c === 'clair' || c === 'sombre' ? c : 'auto'; } catch (_) { return 'auto'; } }
  function resolu(c) { return c === 'auto' ? (media && media.matches ? 'clair' : 'sombre') : c; }
  function appliquer() {
    var c = choix(), r = resolu(c), h = document.documentElement;
    h.setAttribute('data-theme', r);
    h.setAttribute('data-apparence', c);
    h.style.colorScheme = r === 'clair' ? 'light' : 'dark';
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute('content', r === 'clair' ? '#eef4f2' : '#04141a');
    try { document.dispatchEvent(new CustomEvent('apparence', { detail: { choix: c, theme: r } })); } catch (_) {}
  }
  window.Apparence = {
    choix: choix,
    theme: function () { return resolu(choix()); },
    choisir: function (c) { try { localStorage.setItem(CLE, c === 'clair' || c === 'sombre' ? c : 'auto'); } catch (_) {} appliquer(); },
    systeme: appliquer
  };
  if (media && media.addEventListener) media.addEventListener('change', appliquer);
  window.addEventListener('storage', function (e) { if (e.key === CLE) appliquer(); });
  appliquer();
  document.addEventListener('DOMContentLoaded', appliquer);
})();

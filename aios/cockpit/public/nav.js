/* Cockpit v2 — shell commun : esc(), nav, horloge, statut daemon, reduced-motion. */
window.esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
// Jeton du démarrage du cockpit, injecté par le serveur dans chaque page : exigé par tout POST.
window.jeton = () => (document.querySelector('meta[name="cockpit-jeton"]') || {}).content || '';
// Verrou d'empreinte du téléphone (lot A) : une réponse « verrouillé » (401 + X-Verrou) recharge la page,
// que le cockpit remplace alors par celle du verrou.
(() => {
  const f = window.fetch.bind(window);
  let recharge = false;
  window.fetch = async (...a) => {
    const r = await f(...a);
    if (r.status === 401 && r.headers.get('X-Verrou') && !recharge) { recharge = true; location.reload(); }
    return r;
  };
})();
window.REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

window.initNav = function (active) {
  document.body.classList.add('shell');
  const views = [['dashboard', '/', 'DASHBOARD'], ['brain', '/brain', 'CERVEAU 3D'], ['dreams', '/dreams', 'LABO DES RÊVES'], ['memory', '/memory', 'MÉMOIRE'], ['chat', '/chat', 'CHAT'], ['parler', '/parler', 'PARLER'], ['interieur', '/interieur', 'INTÉRIEUR'], ['immunite', '/immunite', 'IMMUNITÉ']];
  const nav = document.createElement('nav');
  nav.className = 'topnav';
  nav.innerHTML = '<div class="beacon"></div><span class="brand">AIOS</span>'
    + views.map(([k, href, label]) => `<a class="pill ${k === active ? 'active' : ''}" href="${href}">${label}</a>`).join('')
    + '<span class="status" id="nav-status">● …</span>';
  document.body.prepend(nav);
  const st = nav.querySelector('#nav-status');
  const tick = () => {
    const h = new Date().toTimeString().slice(0, 8);
    st.textContent = `● ${st.dataset.d || 'daemon ?'} · ${h}`;
  };
  setInterval(tick, 1000); tick();
  const poll = async () => {
    try {
      const a = await (await fetch('/api/anamnese')).json();
      const up = a.daemon_started && (Date.now() / 1000 - a.daemon_started) > 0;
      st.dataset.d = up ? 'daemon up' : 'daemon ?';
      st.classList.toggle('down', !up);
    } catch (_) { st.dataset.d = 'hors ligne'; st.classList.add('down'); }
  };
  poll(); setInterval(poll, 60000);
};

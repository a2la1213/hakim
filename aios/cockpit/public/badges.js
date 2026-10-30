/* (30/10, Ahmed via Hakim) les pastilles rouges des onglets : il s'est passé quelque chose qu'il n'a pas vu (café,
   Immunité, Parler). En ouvrant une de ces pages, une bulle dit d'où vient la pastille (« Depuis ta dernière visite : … »),
   et la page est notée vue (Mac et téléphone ensemble : le cockpit la tient). Fermé aux chantiers de Hakim : la page
   Immunité le charge. Les résumés viennent du cockpit et sont posés en texte, jamais en HTML. */
(() => {
  const PAGES = { cafe: '/cafe', immunite: '/immunite', parler: '/parler' };
  const jet = () => (typeof window.jeton === 'function' ? window.jeton() : (document.querySelector('meta[name="cockpit-jeton"]') || {}).content || '');
  const style = document.createElement('style');
  style.textContent = '.pastille{display:inline-block;min-width:16px;height:16px;padding:0 4px;margin-left:5px;border-radius:8px;'
    + 'background:#ef4444;color:#fff;font-size:10px;font-weight:700;line-height:16px;text-align:center;vertical-align:1px}'
    + '.nouveautes{position:fixed;left:12px;right:12px;top:calc(10px + env(safe-area-inset-top));z-index:30;max-width:640px;margin:0 auto;'
    + 'padding:10px 36px 10px 12px;border-radius:10px;border:1px solid rgba(239,68,68,.5);background:#1a0f12;color:#fde2e2;font-size:13px;'
    + 'box-shadow:0 6px 24px rgba(0,0,0,.35)}.nouveautes button{position:absolute;right:6px;top:6px;border:0;background:transparent;'
    + 'color:inherit;font-size:16px;cursor:pointer}.nouveau{box-shadow:inset 3px 0 0 #ef4444;padding-left:8px !important}';
  document.head.appendChild(style);

  async function lire() {
    const r = await fetch('/api/badges', { headers: { 'X-Jeton': jet() }, cache: 'no-store' });
    return r.ok ? r.json() : null;
  }
  function poser(nav, d, active) {
    for (const [page, href] of Object.entries(PAGES)) {
      const a = nav && nav.querySelector(`a[href="${href}"]`);
      if (!a) continue;
      const p = (d.pages || {})[page] || {};
      const n = page === active ? 0 : Number(p.n) || 0;
      let b = a.querySelector('.pastille');
      if (!n) { if (b) b.remove(); continue; }
      if (!b) { b = document.createElement('span'); b.className = 'pastille'; a.appendChild(b); }
      b.textContent = n > 99 ? '99+' : String(n);
      b.title = (p.resume || []).join(' ; ');
    }
  }
  function suivre(nav, active) {
    const tour = async () => { try { const d = await lire(); if (d) poser(nav, d, active); } catch (_) {} };
    tour();
    setInterval(tour, 60000);
  }
  // à l'ouverture : la bulle « Depuis ta dernière visite », puis « vu » ; rend l'heure de sa visite précédente (ms) pour
  // que la page marque ce qui est nouveau
  async function ouvrir(page) {
    let depuis = Date.now();
    try {
      const d = await lire();
      const p = d && (d.pages || {})[page];
      depuis = Number(d && d.vus && d.vus[page]) || depuis;
      if (p && p.n && (p.resume || []).length) {
        const bulle = document.createElement('div');
        bulle.className = 'nouveautes';
        bulle.setAttribute('role', 'status');
        bulle.textContent = `Depuis ta dernière visite : ${p.resume.join(' ; ')}.`;
        const x = document.createElement('button');
        x.type = 'button'; x.textContent = '×'; x.setAttribute('aria-label', 'Fermer');
        x.addEventListener('click', () => bulle.remove());
        bulle.appendChild(x);
        document.body.appendChild(bulle);
        setTimeout(() => bulle.remove(), 15000);
      }
    } catch (_) {}
    const vu = () => fetch('/api/badges/vu', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jet() },
      body: JSON.stringify({ page }) }).catch(() => {});
    if (document.visibilityState === 'visible') setTimeout(vu, 1500);
    else document.addEventListener('visibilitychange', function f() { if (document.visibilityState === 'visible') { document.removeEventListener('visibilitychange', f); vu(); } });
    return depuis;
  }
  window.Badges = { PAGES, suivre, ouvrir };
})();

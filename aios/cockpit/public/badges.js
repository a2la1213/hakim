/* (30/10, Ahmed via Hakim) les pastilles rouges : il s'est passé quelque chose qu'il n'a pas vu (café, Immunité, Parler,
   SENS, Code). En ouvrant une de ces pages, une bulle dit d'où vient la pastille (« Depuis ta dernière visite : … »), et la
   page est notée vue (Mac et téléphone ensemble : le cockpit la tient). Fermé aux chantiers de Hakim : la page Immunité et
   la page Code le chargent. Les résumés viennent du cockpit et sont posés en texte, jamais en HTML.
   (30/10, Ahmed : « les onglets du cockpit, ça devient chargé : un menu hamburger, avec un seul bouton en plus pour parler ;
   le point rouge dans le menu quand il y a du nouveau, et une petite notification sur mon interface ») suivre() fait de la
   barre du haut un menu : ☰ (le point rouge s'il y a du nouveau ailleurs), AIOS, PARLER ; le menu ouvert liste toutes les
   pages avec leurs pastilles ; une nouveauté qui arrive s'annonce par une petite notification en haut de l'écran (une fois ;
   le téléphone, lui, a sa notification à lui, par l'appli). */
(() => {
  const PAGES = { cafe: '/cafe', immunite: '/immunite', parler: '/parler', sens: '/sens', code: '/code' };
  const MENU = [['dashboard', '/', 'Dashboard'], ['parler', '/parler', 'Parler'], ['sens', '/sens', 'Sens'], ['telephone', '/telephone', 'Téléphone'], ['immunite', '/immunite', 'Immunité'], ['synapses', '/synapses', 'Synapses'],
    ['cafe', '/cafe', 'Café'], ['code', '/code', 'Code'], ['interieur', '/interieur', 'Intérieur'], ['memory', '/memory', 'Mémoire'],
    ['brain', '/brain', 'Cerveau 3D'], ['dreams', '/dreams', 'Labo des rêves'], ['chat', '/chat', 'Chat']];
  const NOMS = Object.fromEntries(MENU.map(([k, , l]) => [k, l]));
  // (03/11, 13:59, Ahmed : « le bandeau rouge : je dois pouvoir cliquer dessus pour être redirigé au bon endroit du café, des sens ou
  // des autres trucs qui envoient des notifs ») où aller sur chaque page : le premier nouveau (café, Immunité), le dernier geste qui
  // attend papa (Parler), ses mesures (SENS), les modifications à relire (Code)
  const LIEUX = { cafe: '.msg.nouveau', immunite: '.ligne.nouveau', parler: '.mission-boutons', sens: '#mesures', code: '#promos' };
  const jet = () => (typeof window.jeton === 'function' ? window.jeton() : (document.querySelector('meta[name="cockpit-jeton"]') || {}).content || '');
  const style = document.createElement('style');
  style.textContent = '.pastille{display:inline-block;min-width:16px;height:16px;padding:0 4px;margin-left:5px;border-radius:8px;'
    + 'background:#ef4444;color:#fff;font-size:10px;font-weight:700;line-height:16px;text-align:center;vertical-align:1px}'
    + '.annonces{position:fixed;left:12px;right:12px;top:calc(10px + env(safe-area-inset-top));z-index:30;max-width:640px;margin:0 auto;'
    + 'display:flex;flex-direction:column;gap:8px;pointer-events:none;max-height:45vh;overflow-y:auto;overscroll-behavior:contain}.annonces>*{pointer-events:auto;flex:none}'
    + '.nouveautes{position:relative;padding:10px 36px 10px 12px;border-radius:10px;border:1px solid rgba(239,68,68,.5);background:#1a0f12;color:#fde2e2;font-size:13px;'
    + 'box-shadow:0 6px 24px rgba(0,0,0,.35)}.nouveautes button{position:absolute;right:6px;top:6px;border:0;background:transparent;'
    + 'color:inherit;font-size:16px;cursor:pointer}.nouveau{box-shadow:inset 3px 0 0 #ef4444;padding-left:8px !important}'
    + '.burger{position:relative;width:40px;height:40px;flex:none;border-radius:10px;border:1px solid rgba(255,255,255,.16);background:transparent;'
    + 'color:#e6edf3;font-size:20px;line-height:1;cursor:pointer;display:inline-flex;align-items:center;justify-content:center}'
    + '.burger:focus-visible,.menu-panneau a:focus-visible,.parler-bouton:focus-visible{outline:2px solid #2dd4bf;outline-offset:2px}'
    + '.burger .point{position:absolute;top:6px;right:6px;width:9px;height:9px;border-radius:50%;background:#ef4444;box-shadow:0 0 0 2px #0b1216}'
    + '.parler-bouton{margin-left:auto;display:inline-flex;align-items:center;min-height:36px;padding:0 14px;border-radius:999px;'
    + 'border:1px solid rgba(45,212,191,.5);background:rgba(45,212,191,.14);color:#e6fffa;font-size:12px;font-weight:600;letter-spacing:1.5px;text-decoration:none}'
    + '.parler-bouton + .status{margin-left:10px}'
    + '.menu-voile{position:fixed;inset:0;z-index:40;background:rgba(0,0,0,.45)}'
    + '.menu-panneau{position:fixed;z-index:41;top:0;bottom:0;left:0;width:min(300px,86vw);overflow-y:auto;padding:calc(14px + env(safe-area-inset-top)) 10px 20px;'
    + 'background:#0f171c;border-right:1px solid rgba(255,255,255,.12);box-shadow:8px 0 30px rgba(0,0,0,.4);display:flex;flex-direction:column;gap:2px}'
    + '.menu-panneau .titre{color:#93a4b0;font-size:11px;letter-spacing:2px;padding:4px 10px 10px}'
    + '.menu-panneau a{display:flex;align-items:center;min-height:44px;padding:0 12px;border-radius:10px;color:#c9d4dc;font-size:15px;text-decoration:none}'
    + '.menu-panneau a:hover{background:rgba(255,255,255,.05)}.menu-panneau a[aria-current="page"]{color:#2dd4bf;background:rgba(45,212,191,.10)}'
    + '.menu-panneau a .pastille{margin-left:auto}.menu-panneau .resume{color:#f3b6b6;font-size:12px;padding:0 12px 6px;margin-top:-4px}'
    + '.annonce-ligne{cursor:pointer;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.annonce-ligne:hover{text-decoration:underline}'
    + '.nouveautes{overflow-wrap:anywhere}.nouveautes.touchable{cursor:pointer}'
    + '.menu-languette{position:fixed;left:0;top:50%;transform:translateY(-50%);z-index:35;width:18px;height:56px;padding:0;border:1px solid rgba(255,255,255,.16);'
    + 'border-left:0;border-radius:0 12px 12px 0;background:rgba(15,23,28,.72);color:#c9d4dc;font-size:16px;line-height:1;cursor:pointer;'
    + 'display:flex;align-items:center;justify-content:center;-webkit-tap-highlight-color:transparent}'
    + '.menu-languette:focus-visible{outline:2px solid #2dd4bf;outline-offset:2px}.menu-languette .point{top:4px;right:3px;width:7px;height:7px}'
    + '[hidden]{display:none !important}';
  document.head.appendChild(style);

  async function lire() {
    const r = await fetch('/api/badges', { headers: { 'X-Jeton': jet() }, cache: 'no-store' });
    return r.ok ? r.json() : null;
  }
  // les bulles et les notifications s'empilent en haut de l'écran, sans se couvrir
  const pile = () => document.querySelector('.annonces') || document.body.appendChild(Object.assign(document.createElement('div'), { className: 'annonces' }));
  const lireLocal = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (_) { return d; } };
  const ecrireLocal = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) {} };

  function pastille(a, n, titre) {
    let b = a.querySelector('.pastille');
    if (!n) { if (b) b.remove(); return; }
    if (!b) { b = document.createElement('span'); b.className = 'pastille'; a.appendChild(b); }
    b.textContent = n > 99 ? '99+' : String(n);
    b.title = titre || '';
  }

  // la barre du haut devient : ☰ · AIOS · PARLER (· l'état du démon, s'il y est) ; le menu ouvert : toutes les pages
  function monterMenu(nav, active) {
    if (!nav || nav.dataset.menu) return null;
    nav.dataset.menu = '1';
    for (const a of [...nav.querySelectorAll('a.pill')]) a.remove();
    const burger = document.createElement('button');
    burger.type = 'button'; burger.className = 'burger'; burger.textContent = '☰';
    burger.setAttribute('aria-label', 'Menu'); burger.setAttribute('aria-expanded', 'false'); burger.setAttribute('aria-controls', 'menu-panneau');
    const point = document.createElement('span'); point.className = 'point'; point.hidden = true; burger.appendChild(point);
    nav.prepend(burger);
    if (active !== 'parler') {
      const p = document.createElement('a');
      p.className = 'parler-bouton'; p.href = '/parler'; p.textContent = 'PARLER';
      const st = nav.querySelector('.status');
      if (st) nav.insertBefore(p, st); else nav.appendChild(p);
    }
    const voile = document.createElement('div'); voile.className = 'menu-voile'; voile.hidden = true;
    const panneau = document.createElement('nav');
    panneau.id = 'menu-panneau'; panneau.className = 'menu-panneau'; panneau.hidden = true; panneau.setAttribute('aria-label', 'Les pages du cockpit');
    const titre = document.createElement('div'); titre.className = 'titre'; titre.textContent = 'AIOS · HAKIM'; panneau.appendChild(titre);
    const liens = {};
    for (const [k, href, label] of MENU) {
      const a = document.createElement('a');
      a.href = href; a.textContent = label;
      if (k === active) a.setAttribute('aria-current', 'page');
      const r = document.createElement('div'); r.className = 'resume'; r.hidden = true;
      panneau.appendChild(a); panneau.appendChild(r);
      liens[k] = { a, r };
    }
    document.body.appendChild(voile); document.body.appendChild(panneau);
    // (30/10, Ahmed : « le retour en arrière par le bouton retour natif du smartphone aussi ») le menu ouvert est une étape de
    // l'historique : « retour » (le téléphone, le navigateur) le ferme d'abord
    const cacher = () => { panneau.hidden = true; voile.hidden = true; burger.setAttribute('aria-expanded', 'false'); };
    const fermer = () => { if (panneau.hidden) return; cacher(); if (history.state && history.state.menuOuvert) history.back(); };
    const ouvrir = () => {
      panneau.hidden = false; voile.hidden = false; burger.setAttribute('aria-expanded', 'true');
      try { history.pushState({ menuOuvert: true }, ''); } catch (_) {}
      (panneau.querySelector('a') || panneau).focus();
    };
    window.addEventListener('popstate', () => { if (!panneau.hidden) cacher(); });
    burger.addEventListener('click', () => (panneau.hidden ? ouvrir() : fermer()));
    // (03/11, 15:20, Ahmed : « le menu burger aussi en glissant de gauche à droite, et une petite flèche dans un petit conteneur, au
    // milieu à gauche de l'écran, sur toute l'interface ») la languette « › » l'ouvre ; un glissement parti du bord gauche aussi
    const languette = document.createElement('button');
    languette.type = 'button'; languette.className = 'menu-languette'; languette.textContent = '›';
    languette.setAttribute('aria-label', 'Ouvrir le menu'); languette.setAttribute('aria-controls', 'menu-panneau');
    languette.addEventListener('click', () => (panneau.hidden ? ouvrir() : fermer()));
    document.body.appendChild(languette);
    // (15:35, Ahmed : « il doit apparaître au rythme de mon doigt, pas juste en un clic ») le panneau suit le doigt : parti du bord
    // gauche, il sort avec lui ; ouvert, un glissement vers la gauche le rentre avec lui ; lâché, il finit le geste (ou revient)
    let glisse = null;
    const suivre = (p) => { panneau.style.transform = `translateX(${(p - 1) * 100}%)`; voile.style.opacity = String(p); };
    const lacher = (ouvert) => {
      panneau.style.transition = 'transform .18s ease-out'; voile.style.transition = 'opacity .18s ease-out';
      suivre(ouvert ? 1 : 0);
      setTimeout(() => {
        panneau.style.transition = voile.style.transition = panneau.style.transform = voile.style.opacity = '';
        if (ouvert) { if (!(history.state && history.state.menuOuvert)) ouvrir(); } else fermer();
      }, 190);
    };
    document.addEventListener('touchstart', (e) => {
      const t = e.touches && e.touches[0];
      if (!t) { glisse = null; return; }
      if (panneau.hidden && t.clientX <= 28) glisse = { x: t.clientX, y: t.clientY, ouvrant: true, actif: false };
      else if (!panneau.hidden && (panneau.contains(e.target) || e.target === voile)) glisse = { x: t.clientX, y: t.clientY, ouvrant: false, actif: false };
      else glisse = null;
    }, { passive: true });
    document.addEventListener('touchmove', (e) => {
      const t = glisse && e.touches && e.touches[0];
      if (!t) return;
      const dx = t.clientX - glisse.x, dy = Math.abs(t.clientY - glisse.y), w = panneau.offsetWidth || 300;
      if (!glisse.actif) {
        if (dy > 24 && dy > Math.abs(dx)) { glisse = null; return; }          // un geste vertical : on fait défiler, pas le menu
        if (Math.abs(dx) < 8) return;
        glisse.actif = true;
        panneau.style.transition = voile.style.transition = 'none';
        if (glisse.ouvrant) { panneau.hidden = false; voile.hidden = false; burger.setAttribute('aria-expanded', 'true'); }
      }
      glisse.p = glisse.ouvrant ? Math.max(0, Math.min(1, dx / w)) : Math.max(0, Math.min(1, 1 + dx / w));
      suivre(glisse.p);
    }, { passive: true });
    document.addEventListener('touchend', () => {
      const g = glisse; glisse = null;
      if (!g || !g.actif) return;
      lacher(g.ouvrant ? g.p > 0.35 : g.p > 0.65);
    }, { passive: true });
    voile.addEventListener('click', fermer);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !panneau.hidden) { fermer(); burger.focus(); } });
    // une page choisie : l'étape « menu ouvert » s'efface d'abord, puis on y va ; « retour » depuis elle revient ici, pas au menu
    panneau.addEventListener('click', (e) => {
      const a = e.target.closest && e.target.closest('a[href]');
      if (!a) return;
      const etape = !!(history.state && history.state.menuOuvert);
      cacher();
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
      if (e.defaultPrevented) { if (etape) history.back(); return; }          // (Parler l'ouvre ailleurs : sa conversation continue)
      if (!etape) return;
      e.preventDefault();
      const aller = a.href;
      window.addEventListener('popstate', function f() { window.removeEventListener('popstate', f); location.href = aller; });
      history.back();
    });
    // le point rouge aussi sur la languette, s'il y a du nouveau ailleurs
    const pointL = point.cloneNode(); languette.appendChild(pointL);
    new MutationObserver(() => { pointL.hidden = point.hidden; }).observe(point, { attributes: true, attributeFilter: ['hidden'] });
    return { burger, point, liens };
  }

  // une petite notification en haut de l'écran pour ce qui vient d'arriver (une fois par nouveauté, sur cet appareil)
  function annoncer(pages, active) {
    const vu = lireLocal('badges-annonces', null);
    const neuf = {}, a_dire = [];
    for (const [page, p] of Object.entries(pages || {})) {
      const n = Number(p && p.n) || 0;
      neuf[page] = n;
      if (page !== active && n > (vu ? Number(vu[page]) || 0 : 0)) a_dire.push([page, p]);
    }
    ecrireLocal('badges-annonces', neuf);
    if (!a_dire.length) return;
    const b = document.createElement('div');
    b.className = 'nouveautes'; b.setAttribute('role', 'status');
    for (const [page, p] of a_dire) {
      const l = document.createElement('div');
      const lien = document.createElement('a');
      lien.href = `${PAGES[page] || '/'}#nouveau`; lien.textContent = NOMS[page] || page; lien.style.color = '#fff'; lien.style.fontWeight = '600';
      // toute la ligne se touche : elle mène à l'endroit du nouveau sur sa page
      const aller = () => { location.href = `${PAGES[page] || '/'}#nouveau`; };
      l.className = 'annonce-ligne'; l.setAttribute('role', 'link'); l.tabIndex = 0;
      l.addEventListener('click', aller);
      l.addEventListener('keydown', (e) => { if (e.key === 'Enter') aller(); });
      l.appendChild(lien);
      l.appendChild(document.createTextNode(` : ${(p.resume || []).join(' ; ') || 'du nouveau'}`));
      b.appendChild(l);
    }
    const x = document.createElement('button');
    x.type = 'button'; x.textContent = '×'; x.setAttribute('aria-label', 'Fermer');
    x.addEventListener('click', () => b.remove());
    b.appendChild(x);
    pile().appendChild(b);
    setTimeout(() => b.remove(), 12000);
  }

  function poser(menu, d, active) {
    let ailleurs = 0;
    for (const [k, { a, r }] of Object.entries(menu.liens)) {
      const p = (d.pages || {})[k] || {};
      const n = k === active ? 0 : Number(p.n) || 0;
      ailleurs += n;
      pastille(a, n, (p.resume || []).join(' ; '));
      r.hidden = !n; r.textContent = n ? (p.resume || []).join(' ; ') : '';
    }
    menu.point.hidden = !ailleurs;
    menu.burger.setAttribute('aria-label', ailleurs ? `Menu — du nouveau (${ailleurs})` : 'Menu');
  }

  function suivre(nav, active) {
    const menu = monterMenu(nav, active);
    if (!menu) return;
    const tour = async () => { try { const d = await lire(); if (d) { poser(menu, d, active); annoncer(d.pages, active); } } catch (_) {} };
    tour();
    setInterval(tour, 30000);
  }
  // à l'ouverture : la bulle « Depuis ta dernière visite », puis « vu » ; rend l'heure de sa visite précédente (ms) pour
  // que la page marque ce qui est nouveau
  // arrivé par le bandeau (#nouveau) : la page se rend, puis elle va à l'endroit (8 s au plus pour qu'il apparaisse)
  function allerAuNouveau(page) {
    const sel = LIEUX[page];
    try { history.replaceState(null, '', location.pathname + location.search); } catch (_) {}
    if (!sel) return;
    const t0 = Date.now();
    const essai = () => {
      const l = [...document.querySelectorAll(sel)];
      const x = page === 'parler' ? (l.length ? (l[l.length - 1].closest('.mission') || l[l.length - 1]) : null) : l[0];
      if (x) { x.scrollIntoView({ behavior: 'smooth', block: 'center' }); x.classList.add('nouveau'); return; }
      if (Date.now() - t0 < 8000) setTimeout(essai, 300);
    };
    essai();
  }
  async function ouvrir(page) {
    if (location.hash === '#nouveau') allerAuNouveau(page);
    let depuis = Date.now();
    try {
      const d = await lire();
      const p = d && (d.pages || {})[page];
      depuis = Number(d && d.vus && d.vus[page]) || depuis;
      if (p && p.n && (p.resume || []).length) {
        const bulle = document.createElement('div');
        bulle.className = 'nouveautes touchable';
        bulle.setAttribute('role', 'status');
        bulle.textContent = `Depuis ta dernière visite : ${p.resume.join(' ; ')}.`;
        // (15:35, Ahmed : « cliquer sur la bande rouge, et ça me ramène directement sur le bon truc ») elle mène au nouveau de la page
        bulle.addEventListener('click', (e) => { if (e.target.closest('button')) return; allerAuNouveau(page); bulle.remove(); });
        const x = document.createElement('button');
        x.type = 'button'; x.textContent = '×'; x.setAttribute('aria-label', 'Fermer');
        x.addEventListener('click', () => bulle.remove());
        bulle.appendChild(x);
        pile().appendChild(bulle);
        setTimeout(() => bulle.remove(), 15000);
      }
    } catch (_) {}
    const vu = () => fetch('/api/badges/vu', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeton': jet() },
      body: JSON.stringify({ page }) }).catch(() => {});
    if (document.visibilityState === 'visible') setTimeout(vu, 1500);
    else document.addEventListener('visibilitychange', function f() { if (document.visibilityState === 'visible') { document.removeEventListener('visibilitychange', f); vu(); } });
    return depuis;
  }
  window.Badges = { PAGES, MENU, suivre, ouvrir };
})();

/* (06/11, Ahmed : « j'aimerais que l'orbe apparaisse sur toutes les pages du cockpit ») la petite orbe de Hakim dans la barre du
   haut, à côté de PARLER (la toucher ouvre Parler). badges.js la monte sur chaque page qui a le menu ; Parler a déjà la sienne.
   Fichier FERMÉ aux chantiers de Hakim. orbe.js (ouvert) peint dans un Worker (orbe-travail.js) : il ne voit rien de la page.
   Sa couleur : son humeur, lue toutes les 30 s sur /api/jarvis/interieur (la même lecture que Parler) ; aucun flux SSE en plus.
   Sans OffscreenCanvas (vieux navigateur) : pas d'orbe, la page ne change pas. */
(() => {
  let montee = false;
  function monter(nav) {
    if (montee || !nav || typeof OffscreenCanvas === 'undefined' || !HTMLCanvasElement.prototype.transferControlToOffscreen) return null;
    montee = true;
    const lien = document.createElement('a');
    lien.className = 'orbe-coin'; lien.href = '/parler'; lien.title = 'Parler à Hakim'; lien.setAttribute('aria-label', 'Parler à Hakim');
    const toile = document.createElement('canvas'); toile.setAttribute('aria-hidden', 'true');
    lien.appendChild(toile);
    const parler = nav.querySelector('.parler-bouton'), st = nav.querySelector('.status');
    nav.insertBefore(lien, parler || st || null);
    let travail;
    try { travail = new Worker('/orbe-travail.js'); } catch (_) { lien.remove(); return null; }
    travail.onerror = () => { lien.remove(); };
    const dpr = () => Math.min(2, window.devicePixelRatio || 1);
    const reduit = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    const off = toile.transferControlToOffscreen();
    travail.postMessage({ canvas: off, w: toile.clientWidth || 44, h: toile.clientHeight || 44, dpr: dpr(), reduit }, [off]);
    if (window.ResizeObserver) new ResizeObserver(() => travail.postMessage({ w: toile.clientWidth, h: toile.clientHeight, dpr: dpr() })).observe(toile);
    const visible = () => travail.postMessage({ visible: document.visibilityState === 'visible' });
    let derniere = 0;
    const humeur = async () => {
      if (document.visibilityState !== 'visible') return;
      derniere = Date.now();
      try {
        const o = await (await fetch('/api/jarvis/interieur', { cache: 'no-store' })).json();
        travail.postMessage({ humeur: String((o && o.humeur_code) || 'calme') });   // le même code que Parler
      } catch (_) {}
    };
    document.addEventListener('visibilitychange', () => { visible(); if (document.visibilityState === 'visible' && Date.now() - derniere > 30000) humeur(); });
    visible(); humeur(); setInterval(humeur, 30000);
    return lien;
  }
  window.OrbeCoin = { monter };
})();

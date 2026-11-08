/* (06/11, Ahmed : « j'aimerais que l'orbe apparaisse sur toutes les pages du cockpit ») la petite orbe de Hakim dans la barre du
   haut, à côté de PARLER (la toucher ouvre Parler). badges.js la monte sur chaque page qui a le menu ; Parler a déjà la sienne.
   Fichier FERMÉ aux chantiers de Hakim. orbe.js (ouvert) peint dans un Worker (orbe-travail.js) : il ne voit rien de la page,
   la page ne lui envoie que des états (humeur, mode, impulsion, durée de parole, taille, visible), jamais un texte.
   Sa couleur : son humeur, lue toutes les 30 s sur /api/jarvis/interieur (la même lecture que Parler).
   (06/11, Ahmed : « l'orbe sur chaque page du cockpit doit bouger comme partout ailleurs ») ses modes, comme dans Parler : repos (elle
   respire), écoute (quelqu'un lui parle), pense (ses brouillons, ses ribosomes), parle (ce qu'il dit, une voix simulée de la longueur
   de sa phrase) ; ses rires et ses impulsions la font battre. Lus sur /api/jarvis/flux-orbe : un TÉMOIN du flux de Parler (il ne compte
   ni comme une page qui dit ses réponses, ni comme une Conversation, ni comme un appareil), une seule connexion par page, fermée quand
   la page est cachée. Un cockpit d'avant ce témoin répond 404 : l'orbe reste alors à sa respiration, sans jamais s'abonner au vrai flux.
   Sans OffscreenCanvas (vieux navigateur) : pas d'orbe, la page ne change pas. */
(() => {
  // ce que chaque événement du flux fait à l'orbe ; pur (testé dans test-pages-orbe.js)
  const borne = (x, a, b) => Math.max(a, Math.min(b, x));
  function Etat() {
    const e = { parle: 0, ecoute: 0, pense: 0 };
    const parler = (texte, t) => {
      const n = String(texte || '').trim().length;
      if (!n) return 0;
      const ms = borne(n * 60, 1200, 25000);                         // ~ le débit de sa voix ; les morceaux qui se suivent s'enchaînent
      e.parle = Math.min(t + 40000, Math.max(e.parle, t) + ms);
      return ms;
    };
    return {
      // rend { pulser } (0..1) ou {} ; le mode se lit ensuite avec mode(t)
      recevoir(nom, d, t) {
        d = d || {};
        if (nom === 'souffle') {
          if (d.niveau === 'papa') { e.ecoute = t + 3000; return { pulser: 0.12 }; }
          if ((d.niveau === 'bouton' && d.id === 'stop') || d.niveau === 'ribosome_stop') { e.parle = e.pense = e.ecoute = 0; return {}; }
          if (d.niveau === 'reglages' || d.niveau === 'bouton') return {};
          if (d.pret === true && parler(d.texte, t)) return {};
          e.pense = t + 5000; return {};
        }
        if (nom === 'entendu') { if (d.quoi === 'dire' && parler(d.texte, t)) return {}; e.pense = t + 4000; return {}; }
        if (nom === 'spontane') { parler(d.texte, t); return { pulser: 0.2 }; }
        if (nom === 'voix_vers') {
          if (d.quoi === 'rire') return { pulser: 0.5 };
          if (d.quoi === 'impulsion') return { pulser: 0.35 };
          parler(d.texte, t); return {};
        }
        if (nom === 'echange_montre') {
          if (d.qui === 'u') { e.ecoute = t + 2500; return { pulser: 0.12 }; }
          if (d.qui === 'j') { e.pense = t + 3000; return {}; }
          return {};
        }
        if (nom === 'rire') return { pulser: borne(0.25 + 0.12 * (Number(d.degre) || 1), 0.25, 1) };
        if (nom === 'impulsion') return { pulser: 0.35 };
        if (nom === 'pensee') { e.pense = Math.max(e.pense, t + 3000); return { pulser: 0.2 }; }
        return {};
      },
      // comme Parler : quand quelqu'un lui parle, l'écoute passe devant ; puis sa voix, puis sa pensée
      mode(t) { return t < e.ecoute ? 'ecoute' : t < e.parle ? 'parle' : t < e.pense ? 'pense' : 'repos'; },
    };
  }
  const EVENEMENTS = ['souffle', 'entendu', 'spontane', 'voix_vers', 'echange_montre', 'rire', 'impulsion', 'pensee'];

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
    const visible = () => document.visibilityState === 'visible';
    let derniere = 0;
    const humeur = async () => {
      if (!visible()) return;
      derniere = Date.now();
      try {
        const o = await (await fetch('/api/jarvis/interieur', { cache: 'no-store' })).json();
        travail.postMessage({ humeur: String((o && o.humeur_code) || 'calme') });   // le même code que Parler
      } catch (_) {}
    };

    // ses modes : le flux témoin, ouvert seulement quand la page se voit (un onglet caché ne garde aucune connexion)
    const etat = Etat();
    let flux = null, absent = false, modeEnvoye = '', minuteur = 0;
    const tic = () => {
      const m = etat.mode(Date.now());
      if (m !== modeEnvoye) { modeEnvoye = m; travail.postMessage({ mode: m }); }
    };
    const ouvrir = () => {
      if (flux || absent || typeof EventSource === 'undefined') return;
      flux = new EventSource('/api/jarvis/flux-orbe');
      flux.onerror = () => { if (flux && flux.readyState === 2) { flux = null; absent = true; } };   // 404 : un cockpit d'avant le témoin
      for (const nom of EVENEMENTS) {
        flux.addEventListener(nom, (ev) => {
          let d = null; try { d = JSON.parse(ev.data); } catch (_) { return; }
          const t = Date.now(), r = etat.recevoir(nom, d, t);
          if (r.pulser) travail.postMessage({ pulser: r.pulser });
          tic();
        });
      }
    };
    const fermer = () => { if (flux) { flux.close(); flux = null; } };
    const suivreVisibilite = () => {
      travail.postMessage({ visible: visible() });
      if (visible()) {
        ouvrir();
        if (!minuteur) minuteur = setInterval(tic, 250);
        if (Date.now() - derniere > 30000) humeur();
      } else { fermer(); clearInterval(minuteur); minuteur = 0; }
    };
    document.addEventListener('visibilitychange', suivreVisibilite);
    window.addEventListener('pagehide', fermer);
    suivreVisibilite(); setInterval(humeur, 30000);
    return lien;
  }
  window.OrbeCoin = { monter, Etat, EVENEMENTS };
})();

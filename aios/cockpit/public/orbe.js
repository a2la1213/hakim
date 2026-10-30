/* L'orbe de Jarvis (demande d'Ahmed, 2026-10-16) : elle bouge au son de sa voix et prend la couleur
   de son humeur, en dégradé. Canvas 2D, sans dépendance.
   - source(fn) : fn() rend { niveau: 0..1, bandes: [graves, médiums, aigus] } à chaque image
     (analyseur de la voix de Jarvis, ou du micro d'Ahmed) ; sinon pulser() donne des impulsions ;
   - humeur(code) : la palette de son humeur (interieur.py) ; mode('ecoute') : celle de la voix d'Ahmed ;
   - mode : repos (respire), ecoute, pense (tourne plus vite), parle. */
(function (racine) {
  'use strict';
  const PALETTES = {
    joie: ['#fde68a', '#f472b6', '#2dd4bf'],
    elan: ['#5eead4', '#22d3ee', '#a3e635'],
    content: ['#99f6e4', '#2dd4bf', '#60a5fa'],
    calme: ['#2dd4bf', '#0ea5e9', '#6366f1'],
    tension: ['#fbbf24', '#f97316', '#ef4444'],
    impatience: ['#fbbf24', '#a78bfa', '#f472b6'],
    ennui: ['#94a3b8', '#6366f1', '#334155'],
    morose: ['#64748b', '#6366f1', '#1e293b'],
    veille: ['#3b4a7a', '#1e3a8a', '#0f172a'],          // en veille : bleus de nuit, apaisés
    // les émotions soudaines de l'affect v2 (2026-10-21)
    alarme: ['#ef4444', '#f97316', '#7f1d1d'],
    surprise: ['#fde047', '#22d3ee', '#f472b6'],
    apaisement: ['#a7f3d0', '#5eead4', '#93c5fd'],
    ecoute: ['#f9a8d4', '#ec4899', '#a855f7'],
    coupe: ['#86efac', '#22c55e', '#15803d'],            // (30/10, 22:31, Hakim) il a coupé le micro de papa : vert
  };
  const rgb = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  const melange = (a, b, t) => a.map((x, i) => x + (b[i] - x) * t);
  const css = (c, a) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
  const BLANC = [255, 255, 255];

  function creer(canvas, options) {
    const opts = options || {};
    const ctx = canvas.getContext('2d');
    const reduit = !!opts.reduit;
    let paletteHumeur = PALETTES.calme.map(rgb);
    let couleurs = paletteHumeur.map(c => c.slice()), cible = paletteHumeur;
    let mode = 'repos', source = null, niveau = 0, impulsion = 0, bandes = [0, 0, 0], raf = 0;
    // (30/10, 21:29, « son orbe part grave en couille ») la phase avance image par image, à une vitesse qui glisse : avant,
    // elle valait « temps depuis l'ouverture × vitesse », et chaque changement d'état (écoute, pense, parle) la téléportait
    let phase = 0, vitesseCourante = null, derniere = null;
    // (30/10, 21:36, idée d'Ahmed) la couleur de celui qui a la parole : 'papa' (rose violet), 'hakim' (son humeur), 'partage'
    // (papa parle, l'oreille ouverte de Hakim peut le couper : les deux mêlées) ; null : l'ancien choix par le mode
    let qui = null;
    function viser() {
      const ec = PALETTES.ecoute.map(rgb);
      cible = qui === 'papa' ? ec : qui === 'partage' ? [ec[0], paletteHumeur[1], ec[2]] : qui === 'coupe' ? PALETTES.coupe.map(rgb)
        : qui ? paletteHumeur : (mode === 'ecoute' ? ec : paletteHumeur);
    }
    const t0 = performance.now();

    function dimensionner() {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      }
      return { w, h, dpr };
    }

    function image(maintenant) {
      raf = requestAnimationFrame(image);
      if (document.hidden || !canvas.isConnected || canvas.offsetParent === null) return;   // invisible : rien à peindre
      const { w, h, dpr } = dimensionner();
      let brut = 0, b = [0, 0, 0];
      const r = source ? source() : null;
      if (r) { brut = r.niveau || 0; b = r.bandes || [brut, brut, brut]; }
      impulsion *= 0.9;
      const vise = Math.min(1, brut + impulsion);
      niveau += (vise - niveau) * (vise > niveau ? 0.35 : 0.07);          // attaque vive, relâche douce
      bandes = bandes.map((x, i) => x + ((b[i] || 0) - x) * 0.25);
      couleurs = couleurs.map((c, i) => melange(c, cible[i], 0.035));     // l'humeur glisse, ne saute pas
      const t = (maintenant - t0) / 1000;
      const vitesse = reduit ? 0.15 : (mode === 'pense' ? 1.7 : (mode === 'parle' || mode === 'ecoute' ? 1.1 : 0.45));
      vitesseCourante = vitesseCourante == null ? vitesse : vitesseCourante + (vitesse - vitesseCourante) * 0.05;
      phase += (derniere == null ? 0 : Math.min(0.1, Math.max(0, (maintenant - derniere) / 1000))) * vitesseCourante;
      derniere = maintenant;
      const respire = mode === 'repos' && !reduit ? 0.025 * Math.sin(t * 1.1) : 0;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const cx = w / 2, cy = h / 2;
      const R = Math.min(w, h) * 0.3 * (1 + 0.17 * niveau + respire);

      const halo = ctx.createRadialGradient(cx, cy, R * 0.3, cx, cy, Math.min(w, h) * 0.5);
      halo.addColorStop(0, css(couleurs[0], 0.2 + 0.3 * niveau));
      halo.addColorStop(0.6, css(couleurs[1], 0.06 + 0.1 * niveau));
      halo.addColorStop(1, css(couleurs[2], 0));
      ctx.fillStyle = halo;
      ctx.fillRect(0, 0, w, h);

      // Voiles d'aura derrière : la forme bouge avec les bandes de la voix, en transparence.
      const forme = (echelle, amp, ph) => {
        ctx.beginPath();
        for (let i = 0; i <= 120; i++) {
          const th = (i / 120) * Math.PI * 2;
          const rr = R * echelle * (1 + amp * (0.6 * Math.sin(3 * th + ph) + 0.3 * Math.sin(5 * th - 1.3 * ph)
            + 0.4 * Math.sin(2 * th + 0.7 * ph)));
          const x = cx + rr * Math.cos(th), y = cy + rr * Math.sin(th);
          if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y);
        }
        ctx.closePath();
      };
      for (let k = 2; k >= 1; k--) {
        const amp = reduit ? 0.01 : 0.03 + 0.16 * bandes[k] + 0.04 * niveau;
        forme(1.08 + 0.06 * k, amp, phase * (1 + k * 0.37) + k * 2.1);
        const aura = ctx.createRadialGradient(cx, cy, R * 0.7, cx, cy, R * 1.35);
        aura.addColorStop(0, css(couleurs[k], 0.22 + 0.18 * niveau));
        aura.addColorStop(1, css(couleurs[k], 0));
        ctx.fillStyle = aura;
        ctx.fill();
      }
      // Le corps : un dégradé CONIQUE des couleurs de son humeur, qui tourne, dans une forme vivante.
      const ph0 = phase;
      forme(1, reduit ? 0.008 : 0.018 + 0.1 * bandes[0] + 0.03 * niveau, ph0);
      ctx.save();
      ctx.clip();
      const angle = ph0 * 0.6;
      let peinture;
      const pcx = cx + Math.cos(ph0 * 0.7) * R * 0.22, pcy = cy + Math.sin(ph0 * 0.5) * R * 0.22;
      if (ctx.createConicGradient) {
        peinture = ctx.createConicGradient(angle, pcx, pcy);
        peinture.addColorStop(0, css(couleurs[0], 1));
        peinture.addColorStop(0.33, css(couleurs[1], 1));
        peinture.addColorStop(0.66, css(couleurs[2], 1));
        peinture.addColorStop(1, css(couleurs[0], 1));
      } else {
        peinture = ctx.createLinearGradient(cx - R * Math.cos(angle), cy - R * Math.sin(angle), cx + R * Math.cos(angle), cy + R * Math.sin(angle));
        couleurs.forEach((c, i) => peinture.addColorStop(i / 2, css(c, 1)));
      }
      ctx.fillStyle = peinture;
      ctx.fillRect(cx - R * 1.6, cy - R * 1.6, R * 3.2, R * 3.2);
      // le centre du dégradé conique est adouci (sinon un point de « roue » se voit)
      const moyenne = couleurs.reduce((a, c) => a.map((x, i) => x + c[i] / 3), [0, 0, 0]);
      const coeur = ctx.createRadialGradient(pcx, pcy, 0, pcx, pcy, R * 0.55);
      coeur.addColorStop(0, css(melange(moyenne, BLANC, 0.2), 0.7));
      coeur.addColorStop(1, css(moyenne, 0));
      ctx.fillStyle = coeur;
      ctx.fillRect(cx - R * 1.6, cy - R * 1.6, R * 3.2, R * 3.2);
      // des nappes de lumière qui dérivent à l'intérieur (fondu doux entre les couleurs)
      for (let k = 0; k < 3; k++) {
        const a = ph0 * (0.5 + 0.2 * k) + k * 2.1;
        const lx = cx + Math.cos(a) * R * 0.45, ly = cy + Math.sin(a * 1.3) * R * 0.45;
        const n = ctx.createRadialGradient(lx, ly, 0, lx, ly, R * 0.75);
        n.addColorStop(0, css(melange(couleurs[(k + 1) % 3], BLANC, 0.15), 0.55));
        n.addColorStop(1, css(couleurs[(k + 1) % 3], 0));
        ctx.fillStyle = n;
        ctx.fillRect(cx - R * 1.6, cy - R * 1.6, R * 3.2, R * 3.2);
      }
      // volume : bord plus sombre, comme une sphère
      const ombre = ctx.createRadialGradient(cx, cy, R * 0.55, cx, cy, R * 1.12);
      ombre.addColorStop(0, 'rgba(0,0,0,0)');
      ombre.addColorStop(1, 'rgba(2,10,14,0.45)');
      ctx.fillStyle = ombre;
      ctx.fillRect(cx - R * 1.6, cy - R * 1.6, R * 3.2, R * 3.2);
      const reflet = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.42, 0, cx - R * 0.35, cy - R * 0.42, R * 0.7);
      reflet.addColorStop(0, 'rgba(255,255,255,0.22)');
      reflet.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = reflet;
      ctx.fillRect(cx - R * 1.6, cy - R * 1.6, R * 3.2, R * 3.2);
      ctx.restore();
      // liseré lumineux, plus vif quand il parle fort
      ctx.lineWidth = Math.max(1, R * 0.01);
      ctx.strokeStyle = css(melange(couleurs[1], BLANC, 0.4), 0.12 + 0.35 * niveau);
      ctx.stroke();
    }
    raf = requestAnimationFrame(image);

    return {
      humeur(code) {
        paletteHumeur = (PALETTES[code] || PALETTES.calme).map(rgb);
        viser();
      },
      mode(m) {
        if (m === mode) return;
        mode = m;
        viser();
      },
      parole(x) { const q = x || null; if (q === qui) return; qui = q; viser(); },
      source(fn) { source = fn || null; },
      pulser(x) { impulsion = Math.min(1, impulsion + (x == null ? 0.25 : x)); },
      arreter() { cancelAnimationFrame(raf); },
    };
  }

  racine.Orbe = { creer, PALETTES };
})(window);

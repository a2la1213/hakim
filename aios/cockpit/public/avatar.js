/* Son avatar (07/11, Ahmed : « qu'il crée un avatar avec mon visage pour lui : en mode Conversation ou Télépathie, c'est son avatar qui
   reprend mon image et qui parle, en faisant correctement les mouvements des lèvres et du visage à chaque émotion, parole, réaction »).
   Tout tourne DANS LA PAGE, sur l'appareil : la photo choisie par papa, ses 478 points (MediaPipe Face Landmarker, déjà servi par le
   cockpit pour la vision), un maillage triangulé une fois (Delaunay), puis chaque image (WebGL) : le maillage déformé par quelques
   « formes » (mâchoire, coins des lèvres, sourire, tristesse, sourcils, paupières), mélangées selon :
   - sa VOIX : le niveau et le timbre de ce qui sort (l'analyseur de sa voix) ouvrent la mâchoire, étirent ou arrondissent la bouche ;
   - son ÉMOTION (son humeur, l'émotion de sa voix, son éveil) : une expression qui s'installe en douceur ;
   - ses RÉACTIONS : son rire, son écoute quand papa parle, ses clignements, sa respiration, de petits mouvements de tête.
   La bouche ouverte montre l'intérieur (sombre) et le haut des dents. Aucune image ne sort de l'appareil.
   Les parties pures (triangulation, formes, cibles) sont testées sous Node : node --test test-avatar.js */
(function (racine) {
  'use strict';

  // ---------- les points du visage (MediaPipe, 478 points ; mêmes numéros que le maillage de 468)
  const COINS = [61, 291];
  const LEVRES_INT_HAUT = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308];
  const LEVRES_INT_BAS = [95, 88, 178, 87, 14, 317, 402, 318, 324];
  const LEVRE_HAUT = [185, 40, 39, 37, 0, 267, 269, 270, 409, 191, 80, 81, 82, 13, 312, 311, 310, 415];
  const PAUPIERES = {
    g: { haut: [246, 161, 160, 159, 158, 157, 173], bas: [7, 163, 144, 145, 153, 154, 155] },
    d: { haut: [466, 388, 387, 386, 385, 384, 398], bas: [249, 390, 373, 374, 380, 381, 382] },
  };
  const SOURCILS = { g: [70, 63, 105, 66, 107, 46, 53, 52, 65, 55], d: [300, 293, 334, 296, 336, 276, 283, 282, 295, 285] };
  const SOURCILS_INT = { g: [107, 66, 55, 65], d: [336, 296, 285, 295] };
  const JOUES = [205, 425, 50, 280];
  const FORMES = ['machoire', 'largeur', 'sourire', 'tristesse', 'sourcils', 'sourcilsInt', 'froncement', 'clignementG', 'clignementD', 'plisser'];

  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const borne = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const lisse = (x) => { const t = borne(x); return t * t * (3 - 2 * t); };

  // ---------- Delaunay (Bowyer-Watson) : une fois par photo, ~500 points
  function trianguler(pts) {
    const n = pts.length;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
    const d = Math.max(x1 - x0, y1 - y0) * 20 + 1, mx = (x0 + x1) / 2, my = (y0 + y1) / 2;
    const P = pts.map(p => [p[0], p[1]]).concat([[mx - d, my - d], [mx, my + d], [mx + d, my - d]]);
    const cercle = (a, b, c) => {
      const [ax, ay] = P[a], [bx, by] = P[b], [cx, cy] = P[c];
      const D = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by));
      if (Math.abs(D) < 1e-12) return { x: 0, y: 0, r2: Infinity };
      const a2 = ax * ax + ay * ay, b2 = bx * bx + by * by, c2 = cx * cx + cy * cy;
      const x = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / D, y = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / D;
      return { x, y, r2: (ax - x) ** 2 + (ay - y) ** 2 };
    };
    let tris = [{ v: [n, n + 1, n + 2], c: cercle(n, n + 1, n + 2) }];
    for (let i = 0; i < n; i++) {
      const [px, py] = P[i];
      const mauvais = [], bons = [];
      for (const t of tris) ((px - t.c.x) ** 2 + (py - t.c.y) ** 2 <= t.c.r2 * (1 + 1e-12) ? mauvais : bons).push(t);
      const aretes = new Map();
      for (const t of mauvais) for (let k = 0; k < 3; k++) {
        const a = t.v[k], b = t.v[(k + 1) % 3], cle = a < b ? `${a},${b}` : `${b},${a}`;
        aretes.set(cle, aretes.has(cle) ? null : [a, b]);
      }
      tris = bons;
      for (const e of aretes.values()) if (e) tris.push({ v: [e[0], e[1], i], c: cercle(e[0], e[1], i) });
    }
    const out = [];
    for (const t of tris) if (t.v.every(k => k < n)) out.push(t.v[0], t.v[1], t.v[2]);
    return out;
  }

  // ---------- la photo cadrée : un portrait 4:5 autour du visage (points MediaPipe normalisés 0..1 → pixels du cadre)
  // (07/11, « éditer ») cadrage : zoom (0,6 à 1,8 : le visage plus petit ou plus grand), dy (−0,35 à 0,35 : plus haut ou plus bas)
  function cadrer(points, largeurImage, hauteurImage, L = 480, H = 600, cadrage = {}) {
    const zoom = borne(Number.isFinite(Number(cadrage.zoom)) ? Number(cadrage.zoom) : 1, 0.6, 1.8);
    const dy = borne(Number.isFinite(Number(cadrage.dy)) ? Number(cadrage.dy) : 0, -0.35, 0.35);
    const px = points.map(p => [p.x * largeurImage, p.y * hauteurImage]);
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const [x, y] of px) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
    const lv = x1 - x0, hv = y1 - y0, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const largeur = Math.max(lv * 1.8, hv * 1.45) / zoom, hauteur = largeur * H / L;
    const sx = cx - largeur / 2, sy = cy - hauteur * (0.47 + dy);          // le visage un peu au-dessus du milieu
    const k = L / largeur;
    return { source: { x: sx, y: sy, l: largeur, h: hauteur }, L, H, points: px.map(([x, y]) => [(x - sx) * k, (y - sy) * k]) };
  }

  // ---------- le repère du visage et ses formes (champs de déplacement, calculés une fois)
  function preparer(points, L, H) {
    const pts = points.map(p => [p[0], p[1]]);
    // deux points presque confondus (lèvres fermées) : écartés d'un demi-pixel, la triangulation reste propre
    const vus = new Map();
    for (let i = 0; i < pts.length; i++) {
      const cle = `${Math.round(pts[i][0] * 2)},${Math.round(pts[i][1] * 2)}`;
      if (vus.has(cle)) pts[i][1] += 0.6; else vus.set(cle, i);
    }
    const nVisage = pts.length;
    const P = (i) => pts[i];
    const xc = (P(234)[0] + P(454)[0]) / 2, demi = Math.abs(P(454)[0] - P(234)[0]) / 2;
    const yHaut = P(10)[1], yMenton = P(152)[1], hv = yMenton - yHaut, yc = (yHaut + yMenton) / 2;
    // une couronne autour du visage (cheveux, cou) qui suit la tête à moitié, et le cadre, immobile
    const tete = new Array(nVisage).fill(1);
    for (let k = 0; k < 20; k++) {
      const a = (k / 20) * Math.PI * 2;
      pts.push([borne(xc + Math.cos(a) * demi * 1.55, 1, L - 1), borne(yc + Math.sin(a) * hv * 0.8, 1, H - 1)]); tete.push(0.55);
    }
    for (const [x, y] of [[0, 0], [L / 2, 0], [L, 0], [L, H / 2], [L, H], [L / 2, H], [0, H], [0, H / 2], [L / 4, 0], [3 * L / 4, 0], [L / 4, H], [3 * L / 4, H]]) {
      pts.push([x, y]); tete.push(0);
    }
    const n = pts.length;
    const lb = dist(P(61), P(291)), yCoins = (P(61)[1] + P(291)[1]) / 2, xBouche = (P(61)[0] + P(291)[0]) / 2;
    const yLevreBas = P(14)[1], ey = dist(P(33), P(263));
    const champ = () => new Float32Array(n * 2);
    const F = {}; for (const f of FORMES) F[f] = champ();
    const ajouter = (f, i, dx, dy) => { F[f][2 * i] += dx; F[f][2 * i + 1] += dy; };
    const hautSet = new Set(LEVRE_HAUT), basInt = new Set(LEVRES_INT_BAS);

    for (let i = 0; i < nVisage; i++) {
      const [x, y] = pts[i];
      // la mâchoire : tout ce qui est sous la bouche descend (plein sous la lèvre du bas, s'efface sous le menton et vers les oreilles)
      if (!hautSet.has(i) && y > yCoins - lb * 0.05) {
        let w = y <= yLevreBas ? lisse((y - yCoins) / Math.max(1, yLevreBas - yCoins)) : 1;
        if (y > yMenton) w *= borne(1 - (y - yMenton) / (0.5 * (yMenton - yCoins)));
        w *= borne(1.25 - Math.abs(x - xBouche) / (demi * 1.05));
        // une bouche qui s'ouvre en ovale : plein au milieu de la lèvre, moins vers les coins (pas une boîte)
        const milieu = borne(1 - Math.abs(x - xBouche) / (0.5 * lb));
        if (y < yLevreBas + 0.6 * lb) w *= 0.3 + 0.7 * milieu ** 0.8;
        if (basInt.has(i)) w = 0.15 + 0.85 * milieu ** 0.8;
        if (i === 61 || i === 291 || i === 78 || i === 308) w = 0.1;     // les coins bougent à peine : l'ouverture en amande
        ajouter('machoire', i, 0, 0.5 * lb * w);
      }
      if (hautSet.has(i)) ajouter('machoire', i, 0, -0.05 * lb);          // la lèvre du haut se lève à peine
      // les coins des lèvres : étirer (largeur > 0) ou arrondir (< 0), sourire, tristesse
      for (const c of COINS) {
        const d = dist(pts[i], P(c)), R = 0.5 * lb;
        if (d >= R) continue;
        const w = (1 - d / R) ** 2, sens = Math.sign(P(c)[0] - xBouche) || 1;
        ajouter('largeur', i, sens * 0.14 * lb * w, 0);
        ajouter('sourire', i, sens * 0.11 * lb * w, -0.24 * lb * w);
        ajouter('tristesse', i, -sens * 0.03 * lb * w, 0.15 * lb * w);
      }
      for (const c of JOUES) {                                              // les pommettes montent avec le sourire
        const d = dist(pts[i], P(c)), R = 0.55 * lb;
        if (d < R) ajouter('sourire', i, 0, -0.08 * lb * (1 - d / R) ** 2);
      }
      // les sourcils (et la peau autour), au-dessus des yeux
      for (const cote of ['g', 'd']) {
        const dMin = Math.min(...SOURCILS[cote].map(k => dist(pts[i], P(k)))), R = 0.32 * ey;
        const yOeil = P(PAUPIERES[cote].haut[3])[1];
        if (dMin < R && y < yOeil) {
          const w = (1 - dMin / R) ** 1.5;
          ajouter('sourcils', i, 0, -0.11 * ey * w);
        }
        const dInt = Math.min(...SOURCILS_INT[cote].map(k => dist(pts[i], P(k)))), Ri = 0.22 * ey;
        if (dInt < Ri && y < yOeil) {
          const w = (1 - dInt / Ri) ** 1.5, versCentre = Math.sign(xc - x) || 0;
          ajouter('sourcilsInt', i, 0, -0.09 * ey * w);
          ajouter('froncement', i, versCentre * 0.05 * ey * w, 0.08 * ey * w);
        }
      }
    }
    // les paupières : celle du haut descend sur celle du bas ; celle du bas monte un peu (plisser, le rire)
    for (const [cote, forme] of [['g', 'clignementG'], ['d', 'clignementD']]) {
      const { haut, bas } = PAUPIERES[cote];
      haut.forEach((h, k) => {
        const b = bas[k];
        ajouter(forme, h, (pts[b][0] - pts[h][0]) * 0.92, (pts[b][1] - pts[h][1]) * 0.92);
        ajouter('plisser', b, 0, (pts[h][1] - pts[b][1]) * 0.28);
      });
    }
    // les dents du haut : un bandeau sous la lèvre du haut, qui suit la lèvre
    const a = P(78), b = P(308), m = P(13);
    const dents = [[a[0] + (b[0] - a[0]) * 0.2, (a[1] + m[1]) / 2], [b[0] - (b[0] - a[0]) * 0.2, (b[1] + m[1]) / 2]];
    const iDents = n;
    for (const d of [dents[0], dents[1], [dents[1][0], dents[1][1] + 0.1 * lb], [dents[0][0], dents[0][1] + 0.1 * lb]]) {
      pts.push(d); tete.push(1);
      for (const f of FORMES) { const c = new Float32Array(F[f].length + 2); c.set(F[f]); F[f] = c; }
    }
    for (let k = 0; k < 4; k++) ajouter('machoire', iDents + k, 0, -0.05 * lb);
    const total = pts.length;
    const triangles = trianguler(pts.slice(0, n));
    const interieur = new Set([...LEVRES_INT_HAUT, ...LEVRES_INT_BAS]);
    const peau = [], bouche = [];
    for (let k = 0; k < triangles.length; k += 3) {
      const t = [triangles[k], triangles[k + 1], triangles[k + 2]];
      (t.every(v => interieur.has(v)) ? bouche : peau).push(...t);
    }
    return { L, H, n: total, repos: pts, tete, formes: F, peau, bouche, dents: [iDents, iDents + 1, iDents + 2, iDents, iDents + 2, iDents + 3],
      centre: [xc, yc], lb, ey };
  }

  // la position de chaque point pour ces poids de formes, et le mouvement de la tête (rotation, déplacement, respiration)
  function deformer(m, poids, tete = { angle: 0, dx: 0, dy: 0, echelle: 1 }, sortie = new Float32Array(m.n * 2)) {
    const [cx, cy] = m.centre, cos = Math.cos(tete.angle || 0), sin = Math.sin(tete.angle || 0), e = tete.echelle || 1;
    for (let i = 0; i < m.n; i++) {
      let x = m.repos[i][0], y = m.repos[i][1];
      for (const f of FORMES) { const p = poids[f]; if (p) { x += m.formes[f][2 * i] * p; y += m.formes[f][2 * i + 1] * p; } }
      const w = m.tete[i];
      if (w) {
        const rx = (x - cx) * e, ry = (y - cy) * e;
        const xr = cx + rx * cos - ry * sin + (tete.dx || 0), yr = cy + rx * sin + ry * cos + (tete.dy || 0);
        x += (xr - x) * w; y += (yr - y) * w;
      }
      sortie[2 * i] = x; sortie[2 * i + 1] = y;
    }
    return sortie;
  }

  // ---------- ce qu'il ressent et ce qu'il dit → les formes visées
  const EXPRESSIONS = {
    joie: { sourire: 0.55, sourcils: 0.2, plisser: 0.25 },
    tendresse: { sourire: 0.3, plisser: 0.12, sourcilsInt: 0.1 },
    calme: { sourire: 0.12 },
    tristesse: { tristesse: 0.55, sourcilsInt: 0.65, clignement: 0.18 },
    fatigue: { clignement: 0.35, tristesse: 0.15 },
    colere: { froncement: 0.85, sourcils: -0.25, tristesse: 0.15 },
    surprise: { sourcils: 0.95, machoire: 0.12 },
    peur: { sourcilsInt: 0.7, sourcils: 0.45, largeur: 0.25 },
    doute: { sourcilsInt: 0.35, froncement: 0.2, tristesse: 0.08 },
    neutre: {},
  };
  const FAMILLES = [
    [/joie|heureu|enthousias|élan|elan|émerveill|emerveill|fier|fierté|amus|ravi|excit|gai/, 'joie'],
    [/tendre|amour|affection|apais|douceur|sereine?|serein|gratitude|reconnaiss/, 'tendresse'],
    [/calme|paisible|tranquill|repos|neutre/, 'calme'],
    [/trist|chagrin|peine|mélancol|melancol|nostalg|déçu|decu|lassitude|seul/, 'tristesse'],
    [/fatigu|somnol|sommeil|épuis|epuis|las\b/, 'fatigue'],
    [/colère|colere|agac|énerv|enerv|frustr|irrit/, 'colere'],
    [/surpri|étonn|etonn|stupé|stupe/, 'surprise'],
    [/peur|inquiét|inquiet|anxi|crainte|angoiss|stress/, 'peur'],
    [/doute|perplex|curio|intrigu|pensif|réfléch|reflech|concentr/, 'doute'],
  ];
  function expressionDe(mot) {
    const t = String(mot || '').toLowerCase();
    for (const [rx, e] of FAMILLES) if (rx.test(t)) return e;
    return 'neutre';
  }
  // la bouche depuis le son : le niveau ouvre la mâchoire ; un son aigu (i, é) étire, un son grave et rond (o, ou) arrondit
  function boucheDeLaVoix(niveau, aigu) {
    const machoire = borne((Number(niveau) || 0) * 7 - 0.05);
    return { machoire, largeur: borne(Number(aigu) || 0, -1, 1) * 0.7 * borne(machoire * 2.5) };
  }
  // les formes visées à l'instant t (secondes) : l'expression, la voix, l'écoute, le rire, les clignements
  function cibles(d, t) {
    const e = EXPRESSIONS[d.expression || 'neutre'] || {};
    const force = 0.75 + 0.5 * borne(Number.isFinite(d.eveil) ? d.eveil : 0.45);
    const c = {};
    for (const f of FORMES) c[f] = 0;
    for (const [k, v] of Object.entries(e)) {
      if (k === 'clignement') { c.clignementG += v; c.clignementD += v; } else c[k] += v * force;
    }
    if (d.voix) { const b = boucheDeLaVoix(d.voix.niveau, d.voix.aigu); c.machoire += b.machoire; c.largeur += b.largeur; }
    else if (d.parleSansSon) {                               // sa voix sort ailleurs (le moteur du téléphone) : des syllabes vraisemblables
      const s = Math.max(0, Math.sin(t * 2 * Math.PI * 4.2) * 0.6 + Math.sin(t * 2 * Math.PI * 2.7 + 1) * 0.4);
      c.machoire += 0.15 + 0.45 * s; c.largeur += 0.2 * Math.sin(t * 5.3);
    }
    if (d.ecoute) c.sourcils += 0.12;
    if (d.rire > 0) { c.sourire += 0.9 * d.rire; c.plisser += 0.6 * d.rire; c.machoire += d.rire * (0.25 + 0.2 * Math.max(0, Math.sin(t * 2 * Math.PI * 5))); }
    if (d.cligne) { c.clignementG = 1; c.clignementD = 1; }
    for (const f of FORMES) c[f] = borne(c[f], f === 'largeur' || f === 'sourcils' ? -1 : 0, 1.2);
    return c;
  }
  // le mouvement de la tête : un balancement lent, la respiration, plus vif quand il parle, un hochement quand il écoute
  function mouvementTete(t, d, m) {
    const parle = d.voix ? borne(d.voix.niveau * 6) : d.parleSansSon ? 0.5 : 0;
    const angle = 0.012 * Math.sin(t * 0.6) + 0.006 * Math.sin(t * 1.7 + 1) + parle * 0.012 * Math.sin(t * 3.1) + (d.rire || 0) * 0.02 * Math.sin(t * 9);
    const hoche = d.ecoute ? 0.012 * Math.max(0, Math.sin(t * 1.4)) : 0;
    return { angle, dx: m.L * 0.004 * Math.sin(t * 0.45), dy: m.H * (0.003 * Math.sin(t * 1.1) + hoche), echelle: 1 + 0.004 * Math.sin(t * 1.1) };
  }

  // ---------- le rendu (navigateur seulement)
  const VS = 'attribute vec2 p;attribute vec2 uv;uniform vec2 taille;varying vec2 v;void main(){v=uv;vec2 c=p/taille*2.0-1.0;gl_Position=vec4(c.x,-c.y,0.0,1.0);}';
  const FS = 'precision mediump float;varying vec2 v;uniform sampler2D tex;uniform vec4 couleur;uniform float mode;'
    + 'void main(){if(mode<0.5){gl_FragColor=texture2D(tex,v);}else{gl_FragColor=couleur;}}';
  function creer(toile, o) {
    const m = o.maillage;
    const gl = toile.getContext('webgl', { stencil: true, alpha: false, antialias: true, preserveDrawingBuffer: false });
    if (!gl) throw new Error('WebGL indisponible');
    toile.width = m.L; toile.height = m.H;
    const shader = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; };
    const prog = gl.createProgram();
    gl.attachShader(prog, shader(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(prog);
    gl.useProgram(prog);
    const uvs = new Float32Array(m.n * 2);
    for (let i = 0; i < m.n; i++) { uvs[2 * i] = m.repos[i][0] / m.L; uvs[2 * i + 1] = m.repos[i][1] / m.H; }
    const bufPos = gl.createBuffer(), bufUv = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, bufUv); gl.bufferData(gl.ARRAY_BUFFER, uvs, gl.STATIC_DRAW);
    const aUv = gl.getAttribLocation(prog, 'uv'); gl.enableVertexAttribArray(aUv); gl.vertexAttribPointer(aUv, 2, gl.FLOAT, false, 0, 0);
    const aP = gl.getAttribLocation(prog, 'p');
    const indices = (l) => { const b = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, b); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(l), gl.STATIC_DRAW); return { b, n: l.length }; };
    const iPeau = indices(m.peau), iBouche = indices(m.bouche), iDents = indices(m.dents);
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, o.image);
    for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
    const uTaille = gl.getUniformLocation(prog, 'taille'), uMode = gl.getUniformLocation(prog, 'mode'), uCouleur = gl.getUniformLocation(prog, 'couleur');
    gl.uniform2f(uTaille, m.L, m.H);
    const positions = new Float32Array(m.n * 2);
    const actuel = {}; for (const f of FORMES) actuel[f] = 0;
    let rire = 0, rireJusqua = 0, prochainClin = 0, clinJusqua = 0, boucle = null, lire = null, t0 = performance.now();
    function dessiner(d) {
      const t = (performance.now() - t0) / 1000;
      if (!prochainClin) prochainClin = t + 1.5 + Math.random() * 3;
      if (t >= prochainClin) { clinJusqua = t + 0.14; prochainClin = t + 2.5 + Math.random() * 3.5 + (Math.random() < 0.15 ? -2.2 : 0); }
      rire = t < rireJusqua ? Math.min(1, rire + 0.15) : Math.max(0, rire - 0.04);
      const c = cibles({ ...d, rire: rire * (d.rireForce || 1), cligne: t < clinJusqua }, t);
      for (const f of FORMES) {                               // la bouche suit vite la voix ; l'expression s'installe en douceur
        const vite = f === 'machoire' || f === 'largeur' ? (c[f] > actuel[f] ? 0.55 : 0.32) : f.startsWith('clignement') ? 0.6 : 0.06;
        actuel[f] += (c[f] - actuel[f]) * vite;
      }
      deformer(m, actuel, o.reduit ? { angle: 0, dx: 0, dy: 0, echelle: 1 } : mouvementTete(t, d, m), positions);
      gl.viewport(0, 0, m.L, m.H);
      gl.clearColor(0, 0, 0, 1); gl.clearStencil(0); gl.clear(gl.COLOR_BUFFER_BIT | gl.STENCIL_BUFFER_BIT);
      gl.bindBuffer(gl.ARRAY_BUFFER, bufPos); gl.bufferData(gl.ARRAY_BUFFER, positions, gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(aP); gl.vertexAttribPointer(aP, 2, gl.FLOAT, false, 0, 0);
      gl.uniform1f(uMode, 0); gl.disable(gl.STENCIL_TEST);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, iPeau.b); gl.drawElements(gl.TRIANGLES, iPeau.n, gl.UNSIGNED_SHORT, 0);
      // bouche fermée : ses lèvres, telles que sur la photo ; ouverte : l'intérieur (sombre), puis le haut des dents, dans l'ouverture
      const ouverture = actuel.machoire;
      if (ouverture < 0.06) { gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, iBouche.b); gl.drawElements(gl.TRIANGLES, iBouche.n, gl.UNSIGNED_SHORT, 0); return; }
      gl.enable(gl.STENCIL_TEST); gl.stencilFunc(gl.ALWAYS, 1, 0xff); gl.stencilOp(gl.KEEP, gl.KEEP, gl.REPLACE);
      gl.uniform1f(uMode, 1); gl.uniform4f(uCouleur, 0.16, 0.05, 0.06, 1);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, iBouche.b); gl.drawElements(gl.TRIANGLES, iBouche.n, gl.UNSIGNED_SHORT, 0);
      gl.stencilFunc(gl.EQUAL, 1, 0xff); gl.stencilOp(gl.KEEP, gl.KEEP, gl.KEEP);
      if (ouverture > 0.14) {                                  // les dents apparaissent en douceur avec l'ouverture
        gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.uniform4f(uCouleur, 0.76, 0.73, 0.67, 0.85 * borne((ouverture - 0.14) / 0.3));
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, iDents.b); gl.drawElements(gl.TRIANGLES, iDents.n, gl.UNSIGNED_SHORT, 0);
        gl.disable(gl.BLEND);
      }
      gl.disable(gl.STENCIL_TEST);
    }
    const A = {
      dessiner,
      // lire() rend, à chaque image : { voix: {niveau, aigu} | null, parleSansSon, expression, eveil, ecoute, rireForce }
      demarrer(l) { lire = l; if (boucle) return; const tour = () => { boucle = requestAnimationFrame(tour); try { dessiner(lire ? lire() || {} : {}); } catch (_) {} }; tour(); },
      arreter() { if (boucle) cancelAnimationFrame(boucle); boucle = null; },
      rire(degre = 1) { rireJusqua = (performance.now() - t0) / 1000 + 0.9 + 0.35 * Math.min(5, degre); },
      get actif() { return !!boucle; },
      detruire() { A.arreter(); try { gl.getExtension('WEBGL_lose_context')?.loseContext(); } catch (_) {} },
    };
    return A;
  }

  // ---------- les points du visage sur la photo (MediaPipe, mode image, sur l'appareil)
  async function detecter(image) {
    const BASE = '/vendor/mediapipe';
    const { FilesetResolver, FaceLandmarker } = await import(`${BASE}/vision_bundle.mjs`);
    const fichiers = await FilesetResolver.forVisionTasks(`${BASE}/wasm`);
    const lm = await FaceLandmarker.createFromOptions(fichiers, { baseOptions: { modelAssetPath: `${BASE}/face_landmarker.task`, delegate: 'CPU' },
      runningMode: 'IMAGE', numFaces: 1 });
    try {
      const r = lm.detect(image);
      const pts = r && r.faceLandmarks && r.faceLandmarks[0];
      if (!pts || pts.length < 468) throw new Error('aucun visage trouvé sur la photo');
      return pts.map(p => ({ x: p.x, y: p.y }));
    } finally { try { lm.close(); } catch (_) {} }
  }
  // la photo cadrée, prête pour la texture
  function photoCadree(image, cadre) {
    const c = document.createElement('canvas'); c.width = cadre.L; c.height = cadre.H;
    const cx = c.getContext('2d');
    cx.fillStyle = '#101418'; cx.fillRect(0, 0, c.width, c.height);
    const s = cadre.source;
    cx.drawImage(image, s.x, s.y, s.l, s.h, 0, 0, cadre.L, cadre.H);
    return c;
  }

  const Avatar = { FORMES, EXPRESSIONS, trianguler, cadrer, preparer, deformer, cibles, expressionDe, boucheDeLaVoix, mouvementTete, creer, detecter, photoCadree,
    LEVRES_INT_HAUT, LEVRES_INT_BAS, PAUPIERES, SOURCILS };
  if (typeof module === 'object' && module.exports) module.exports = Avatar;
  else racine.Avatar = Avatar;
})(typeof window !== 'undefined' ? window : globalThis);

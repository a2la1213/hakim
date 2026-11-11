/* (11/11, ~01:15, Ahmed : « Il peut chanter en même temps qu'une musique, s'il le veut ? En coordonnant la sortie de sa voix avec la sortie
   du son, sur le smartphone ou en Bluetooth. » ; « ouiii ») CHANTER AVEC LA MUSIQUE, les calculs purs, partagés page / node (comme
   studio-calage.js). node --test test-chanter.js ; le banc : node mesure/chanter-banc.js.
   Pas de chant juste note à note en direct (impossible aujourd'hui) : il se joint au REFRAIN, ou à une phrase déjà entendue (paroles.js),
   en la RAPPANT sur les temps.
   1. LES TEMPS : la grille des temps forts, tirée des trames du téléphone (100 ms : niveau, graves… ; l'heure de l'appli, à la capture) :
      les attaques (les graves qui montent), repliées sur la période du tempo ; la période est affinée (± 4 %) et la phase est la direction
      moyenne des attaques (leur résultante : sa force dit si la grille est sûre).
   2. L'HORLOGE DU MORCEAU : la position du lecteur (l'appli : MediaSession, sa position à un instant et sa vitesse), quand elle la donne.
   3. LA PRÉVISION : un morceau déjà entendu en entier (mémoire, par la position du lecteur) dit l'instant exact de chaque phrase ; sinon le
      refrain : ses passages, alignés sur le plus complet, leur écart (arrondi aux mesures) dit quand il revient, et le passage en cours dit
      ses lignes qui restent. Chaque instant prévu est calé sur la grille (au demi-temps près).
   4. LE DÉBIT : ses syllabes dans la durée de la phrase (le rate SSML d'Azure), corrigé une fois sur la durée vraiment rendue.
   5. LE DÉPART : sa voix doit SONNER quand le temps SONNE. Par le micro (les deux chemins mesurés : la musique, capture → micro, le calage
      du cockpit ; sa voix, page → micro, le chemin de son écho) : départ = temps + calage − écho (le retard du micro s'annule). Sans eux :
      les deux sortent par le même appareil (le haut-parleur, ou la même enceinte), ce qui suit le mélangeur d'Android s'annule ; reste ce
      qui le précède : le tampon de la page et celui de la capture.
   6. SES GARDE-FOUS : son réglage, son intérieur coupé, un appel, papa qui parle, lui qui parle, la page absente, une fois par morceau. */
(function (racine) {
  'use strict';

  const DEFAUTS = {
    pas_ms: 100, fenetre_ms: 20000, affiner: 0.04, affiner_pas: 0.0005, grille_r_min: 0.45, attaques_min: 20,   // (au banc : du bruit seul monte à 0,33 en cherchant sa période ; la musique, 0,9 et plus)
   
    biais_grille_ms: 0,              // calibré au banc (mesure/chanter-banc.js) : l'attaque repérée par rapport au vrai temps
    ecart_passage_ms: 9000,          // deux lignes du refrain plus loin que 9 s : deux passages
    horizon_min_ms: 3500,            // le temps de fabriquer sa voix (Azure ~0,5-1 s, deux fois au plus), de la recevoir, de la décoder
    horizon_max_ms: 45000, confiance_min: 0.4, lignes_max: 2, colle_ms: 1500,
    temps_par_morceau: 2, morceaux_max: 4,
    syllabes_s: 5.2, debit_min: 0.8, debit_max: 1.6, tolerance_duree: 0.12,
    capture_ms: 20, tampon_page_ms: 20,   // (sans micro) ce qui précède le mélangeur : la capture de l'appli, le tampon de la page
    cadres_micro_ms: 36.5,           // (par le micro) le décalage de leurs fenêtres (calerSons : trames de 100 ms ; l'écho : fenêtres de 20 ms)
    incertitude_micro_ms: 40, incertitude_annonce_ms: 80,
    par_morceau: 1, ecart_s: 60, papa_ms: 3000,
  };
  const DEUX_PI = 2 * Math.PI;
  const fini = (x) => typeof x === 'number' && Number.isFinite(x);
  const mediane = (v) => { const s = (v || []).filter(fini).sort((a, b) => a - b); if (!s.length) return NaN; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const borne = (x, a, b) => Math.max(a, Math.min(b, x));

  /* ---- 1. les temps forts. trames : [{ tb (l'heure de l'appli au début de la trame), v: [niveau, graves, …] }] (ou t à la place de tb).
     (appli 1.96) v[6], v[7] : l'attaque la plus forte de la trame, à 10 ms près (sa place dans la trame, ms ; sa force) : sans elles, une
     attaque n'est connue qu'à sa trame (le milieu, ± 50 ms), et un tempo dont le temps tombe toujours au même endroit des trames (120 BPM :
     500 ms, 150, 100, 75…) garde ce biais entier (mesuré au banc : +47 ms à 120 BPM) */
  const heure = (x) => (x && fini(Number(x.tb)) ? Number(x.tb) : Number(x && x.t));
  const fines = (v) => v.length >= 8 && fini(Number(v[6])) && Number(v[6]) >= 0 && Number(v[6]) < 100 && fini(Number(v[7])) && Number(v[7]) >= 0;
  function attaques(trames, o = {}) {
    const r = { ...DEFAUTS, ...o };
    const l = (Array.isArray(trames) ? trames : []).filter(x => x && Array.isArray(x.v) && x.v.length >= 2 && fini(heure(x))).sort((a, b) => heure(a) - heure(b));
    if (!l.length) return [];
    const fin = heure(l[l.length - 1]), out = [];
    const toutesFines = l.every(x => fines(x.v));
    for (let i = 1; i < l.length; i++) {
      const t = heure(l[i]), u = heure(l[i - 1]);
      if (t < fin - r.fenetre_ms) continue;
      if (toutesFines) { out.push({ t: t + Number(l[i].v[6]), a: Number(l[i].v[7]) }); continue; }
      if (t - u > 1.5 * r.pas_ms || t - u <= 0) continue;   // un trou : pas d'attaque mesurable
      const a = Math.max(0, Number(l[i].v[1]) - Number(l[i - 1].v[1])) + 0.5 * Math.max(0, Number(l[i].v[0]) - Number(l[i - 1].v[0]));
      if (fini(a)) out.push({ t: t + r.pas_ms / 2, a });
    }
    // au-dessus de leur moyenne seulement : le fond qui bouge ne tire pas la phase
    const m = out.reduce((s, x) => s + x.a, 0) / Math.max(1, out.length);
    return out.map(x => ({ t: x.t, a: Math.max(0, x.a - m) })).filter(x => x.a > 0);
  }
  function resultante(att, P, tR) {
    let c = 0, s = 0, w = 0;
    for (const x of att) { const th = DEUX_PI * (x.t - tR) / P; c += x.a * Math.cos(th); s += x.a * Math.sin(th); w += x.a; }
    return { r: w > 0 ? Math.hypot(c, s) / w : 0, phi: Math.atan2(s, c) };
  }
  // la période sans tempo donné : l'autocorrélation des attaques, de 60 à 180 BPM (comme analyseMusicale du cockpit)
  function periodeDe(att, pas = DEFAUTS.pas_ms) {
    if (att.length < 20) return null;
    const t0 = att[0].t, n = Math.round((att[att.length - 1].t - t0) / pas) + 1, x = new Array(n).fill(0);
    for (const a of att) x[Math.round((a.t - t0) / pas)] += a.a;
    const ac = (lag) => { let s = 0; for (let i = lag; i < n; i++) s += x[i] * x[i - lag]; return s; };
    let m = null;
    for (let lag = Math.round(60000 / 180 / pas); lag <= Math.round(60000 / 60 / pas); lag++) { const v = ac(lag); if (!m || v > m.v) m = { lag, v }; }
    if (!m || !(m.v > 0)) return null;
    const a = ac(m.lag - 1), b = m.v, d = ac(m.lag + 1), den = a - 2 * b + d;
    return (den < 0 ? m.lag + 0.5 * (a - d) / den : m.lag) * pas;
  }
  /* la grille : { periode_ms, t0 (un temps, à l'heure de l'appli, près de la fin), r (sa force, 0 à 1), bpm, n, fin } ; null : pas de battement */
  function grille(trames, o = {}) {
    const r = { ...DEFAUTS, ...o };
    const att = attaques(trames, r);
    if (att.length < r.attaques_min) return null;
    const P0 = fini(Number(r.bpm)) && Number(r.bpm) >= 40 && Number(r.bpm) <= 240 ? 60000 / Number(r.bpm) : periodeDe(att, r.pas_ms);
    if (!fini(P0)) return null;
    const tR = att[att.length - 1].t, n = Math.round(r.affiner / r.affiner_pas);
    let m = null;
    for (let k = -n; k <= n; k++) { const P = P0 * (1 + k * r.affiner_pas), x = resultante(att, P, tR); if (!m || x.r > m.r) m = { P, ...x }; }
    const t0 = tR + (m.phi / DEUX_PI) * m.P + r.biais_grille_ms;
    return { periode_ms: Math.round(m.P * 100) / 100, t0: Math.round(t0), r: Math.round(m.r * 1000) / 1000, bpm: Math.round(60000 / m.P * 10) / 10, n: att.length, fin: Math.round(tR) };
  }
  /* le calage de la musique, capture → micro (ms) : la corrélation des niveaux des deux (comme calerSons du cockpit), mais seulement dans ce
     qu'un vrai chemin peut être (−50 à 700 ms) : une musique en boucle se ressemble aussi un temps ou une mesure plus loin (mesuré au banc :
     calerSons rendait −1 800 ms, corrélation 0,9, pour 220 ms) ; null : pas sûr */
  function caler(tel, mic, o = {}) {
    const de = fini(o.de) ? o.de : -50, a = fini(o.a) ? o.a : 700, pas = o.pas || 10, min = fini(o.min) ? o.min : 0.7;
    const T = (tel || []).filter(x => x && Array.isArray(x.v) && fini(heure(x))).sort((x, y) => heure(x) - heure(y));
    const M = (mic || []).filter(x => x && Array.isArray(x.v) && fini(heure(x))).sort((x, y) => heure(x) - heure(y));
    if (T.length < 40 || M.length < 40) return null;
    const val = (t) => {
      let i = 0, j = M.length - 1;
      if (t < heure(M[0]) || t > heure(M[j])) return null;
      while (j - i > 1) { const k = (i + j) >> 1; if (heure(M[k]) <= t) i = k; else j = k; }
      const ti = heure(M[i]), tj = heure(M[j]), f = tj === ti ? 0 : (t - ti) / (tj - ti);
      return Number(M[i].v[0]) * (1 - f) + Number(M[j].v[0]) * f;
    };
    const courbe = [];
    for (let lag = de; lag <= a; lag += pas) {
      const xs = [], ys = [];
      for (const x of T) { const y = val(heure(x) + lag); if (y != null) { xs.push(Number(x.v[0])); ys.push(y); } }
      if (xs.length < 40) { courbe.push({ ms: lag, c: -1 }); continue; }
      const mx = xs.reduce((s, v) => s + v, 0) / xs.length, my = ys.reduce((s, v) => s + v, 0) / ys.length;
      let nu = 0, dx = 0, dy = 0;
      for (let i = 0; i < xs.length; i++) { nu += (xs[i] - mx) * (ys[i] - my); dx += (xs[i] - mx) ** 2; dy += (ys[i] - my) ** 2; }
      courbe.push({ ms: lag, c: dx > 0 && dy > 0 ? nu / Math.sqrt(dx * dy) : 0 });
    }
    // ses pics (pas au bord : le vrai est peut-être dehors), les plus forts d'abord
    const pics = courbe.filter((x, i) => i > 0 && i < courbe.length - 1 && x.c >= min && x.c >= courbe[i - 1].c && x.c > courbe[i + 1].c)
      .map(x => ({ ms: x.ms, c: Math.round(x.c * 100) / 100 })).sort((x, y) => y.c - x.c).slice(0, 6);
    if (!pics.length) return null;
    return { ms: pics[0].ms, correlation: pics[0].c, pics };
  }
  /* le bon pic : une musique en boucle en a un par temps. Sa voix, page → micro (son écho), et la musique, capture → micro, passent presque
     toujours par le même appareil : le vrai calage est près de l'écho moins leurs fenêtres ; le pic le plus proche de là. Sans écho : un seul
     pic, sinon rien (ambigu). */
  function choisirCalage(cal, attendu, o = {}) {
    const r = { ...DEFAUTS, ...o };
    if (!cal || !Array.isArray(cal.pics) || !cal.pics.length) return null;
    const forts = cal.pics.filter(x => x.c >= cal.pics[0].c - 0.2);
    if (!fini(attendu)) return forts.length === 1 ? forts[0].ms : null;
    return forts.reduce((m, x) => (Math.abs(x.ms - (attendu - r.cadres_micro_ms)) < Math.abs(m.ms - (attendu - r.cadres_micro_ms)) ? x : m), forts[0]).ms;
  }
  const grilleSure = (g, o = {}) => !!(g && fini(g.periode_ms) && g.periode_ms > 0 && fini(g.t0) && g.r >= ({ ...DEFAUTS, ...o }).grille_r_min);
  // le point de la grille le plus proche de t (division 2 : au demi-temps près)
  function tempsProche(g, t, division = 1) {
    if (!g || !(g.periode_ms > 0) || !fini(t)) return t;
    const p = g.periode_ms / division;
    return g.t0 + Math.round((t - g.t0) / p) * p;
  }

  /* ---- 2. l'horloge du morceau : { titre, position_ms, a (l'heure de l'appli à cette position), vitesse, etat: 'lecture'|'pause' } */
  function horlogeA(historique, t, titre) {
    let h = null;
    for (const x of Array.isArray(historique) ? historique : [historique]) {
      if (!x || !fini(Number(x.a)) || !fini(Number(x.position_ms)) || Number(x.a) > t + 50) continue;
      if (titre && x.titre && x.titre !== titre) continue;
      if (!h || Number(x.a) >= Number(h.a)) h = x;
    }
    return h;
  }
  function positionA(h, t) {
    if (!h || h.etat !== 'lecture' || !fini(Number(h.a)) || !fini(Number(h.position_ms))) return null;
    const v = fini(Number(h.vitesse)) && Number(h.vitesse) > 0 ? Number(h.vitesse) : 1;
    return Number(h.position_ms) + (t - Number(h.a)) * v;
  }
  function instantDe(h, pos) {
    if (!h || h.etat !== 'lecture') return null;
    const v = fini(Number(h.vitesse)) && Number(h.vitesse) > 0 ? Number(h.vitesse) : 1;
    return Number(h.a) + (pos - Number(h.position_ms)) / v;
  }

  /* ---- 3. la prévision. lignes : celles du morceau (paroles.js) : { tb, texte, groupe, d (sa durée, ms), mots: [[mot, dt ms]] } */
  const tl = (x) => (fini(Number(x && x.tb)) ? Number(x.tb) : Number(x && x.t));
  // les passages du refrain : des lignes qui reviennent, à la suite (9 s au plus entre deux)
  function passages(lignes, o = {}) {
    const r = { ...DEFAUTS, ...o };
    const l = (lignes || []).filter(x => x && fini(tl(x))).slice().sort((a, b) => tl(a) - tl(b));
    const compte = new Map();
    for (const x of l) compte.set(x.groupe, (compte.get(x.groupe) || 0) + 1);
    const out = [];
    let cur = null;
    for (const x of l) {
      if ((compte.get(x.groupe) || 0) < 2) { cur = null; continue; }
      if (cur && tl(x) - tl(cur.lignes[cur.lignes.length - 1]) <= r.ecart_passage_ms && !cur.groupes.has(x.groupe)) { cur.lignes.push(x); cur.groupes.add(x.groupe); continue; }
      cur = { lignes: [x], groupes: new Set([x.groupe]) };
      out.push(cur);
    }
    return out;
  }
  // le passage le plus complet (le plus récent à égalité) : la place de chaque ligne dans le refrain
  function modele(ps) {
    let m = null;
    for (const p of ps) if (!m || p.lignes.length >= m.lignes.length) m = p;
    if (!m) return null;
    const t0 = tl(m.lignes[0]), rel = new Map();
    for (const x of m.lignes) rel.set(x.groupe, tl(x) - t0);
    const der = m.lignes[m.lignes.length - 1];
    return { passage: m, rel, lignes: m.lignes.map(x => ({ ...x, rel: tl(x) - t0 })), etendue: tl(der) - t0 + (Number(der.d) > 0 ? Number(der.d) : 2000) };
  }
  // le début de chaque passage, à la place du modèle (la médiane de ses lignes communes) ; null : rien en commun
  function debutAligne(p, M) {
    const v = p.lignes.filter(x => M.rel.has(x.groupe)).map(x => tl(x) - M.rel.get(x.groupe));
    return v.length ? mediane(v) : null;
  }
  function candidat(x, t, par, confiance) {
    return { texte: String(x.texte || ''), t: Math.round(t), d: Number(x.d) > 0 ? Math.round(Number(x.d)) : null, mots: Array.isArray(x.mots) ? x.mots : null,
      groupe: x.groupe, par, confiance };
  }
  /* o : { maintenant (l'heure de l'appli), grille, horloge (son historique), memoire: { titre, lignes: [{ pos, texte, d, mots, groupe }] }, titre } ;
     rend les phrases à venir, dans l'ordre : { texte, t (l'instant voulu, heure de l'appli, comme les trames), d, mots, par, confiance, cale } */
  function prevoir(lignes, o = {}) {
    const r = { ...DEFAUTS, ...o };
    const now = Number(o.maintenant), out = [];
    if (!fini(now)) return out;
    // (a) un morceau déjà entendu : la position du lecteur dit l'instant exact de chaque phrase
    const h = horlogeA(o.horloge, now, o.titre || '');
    const pos = positionA(h, now);
    if (pos != null && o.memoire && Array.isArray(o.memoire.lignes) && (!o.titre || o.memoire.titre === o.titre))
      for (const m of o.memoire.lignes) if (fini(Number(m.pos)) && m.pos > pos) out.push(candidat(m, instantDe(h, Number(m.pos)), 'memoire', 0.85));
    // (b) le refrain du morceau en cours : le passage en cours dit ses lignes qui restent ; leur écart dit quand il revient
    const ps = passages(lignes, r), M = modele(ps);
    if (M && M.lignes.length) {
      const debuts = ps.map(p => debutAligne(p, M)).filter(fini);
      const dernier = debuts[debuts.length - 1];
      if (fini(dernier) && now < dernier + M.etendue)
        for (const x of M.lignes) { const t = dernier + x.rel; if (t > now && !ps[ps.length - 1].groupes.has(x.groupe)) out.push(candidat(x, t, 'suite', 0.6)); }
      if (debuts.length >= 2) {
        const ecarts = debuts.slice(1).map((d, i) => d - debuts[i]).filter(x => x > M.etendue * 0.5);
        let per = mediane(ecarts);
        const g = grilleSure(o.grille, r) ? o.grille : null;
        if (fini(per) && g && per > 4 * g.periode_ms) per = Math.round(per / (4 * g.periode_ms)) * 4 * g.periode_ms;   // en mesures de 4 temps
        if (fini(per) && per > 0) {
          const ecart = Math.max(0, ...ecarts.map(x => Math.abs(x - per)));
          const conf = ecarts.length >= 2 && ecart < (g ? 2 * g.periode_ms : 1500) ? 0.65 : 0.45;
          let prochain = dernier + per;
          while (prochain + M.etendue < now) prochain += per;
          for (const x of M.lignes) { const t = prochain + x.rel; if (t > now) out.push(candidat(x, t, 'retour', conf)); }
        }
      }
    }
    // calées sur la grille (au demi-temps près)
    const g = grilleSure(o.grille, r) ? o.grille : null;
    for (const c of out) if (g) { c.t = Math.round(tempsProche(g, c.t, 2)); c.cale = true; }
    return out.filter(c => c.t > now && c.texte).sort((a, b) => a.t - b.t);
  }
  /* la phrase à chanter : la première assez loin pour préparer sa voix, assez sûre ; et la suivante si elle la suit de près (deux au plus) */
  function choisir(cands, maintenant, o = {}) {
    const r = { ...DEFAUTS, ...o };
    const ok = (cands || []).filter(c => c.t - maintenant >= r.horizon_min_ms && c.t - maintenant <= r.horizon_max_ms && c.confiance >= r.confiance_min);
    if (!ok.length) return null;
    // la plus sûre parmi celles qui arrivent ensemble (5 s) ; la mémoire d'abord
    const premier = ok[0], proches = ok.filter(c => c.t - premier.t <= 5000);
    const c = proches.reduce((m, x) => (x.confiance > m.confiance ? x : m), proches[0]);
    const lignes = [c];
    for (const x of ok) {
      if (lignes.length >= r.lignes_max) break;
      const der = lignes[lignes.length - 1];
      if (x.t > der.t && x.par === c.par && x.t - (der.t + (der.d || 0)) <= r.colle_ms && x.texte !== der.texte) lignes.push(x);
    }
    return { ...c, lignes };
  }

  /* ---- la mémoire d'un morceau (par la position du lecteur) : ses lignes, à leur position */
  function memoriser(lignes, historique, titre) {
    const out = [];
    for (const x of lignes || []) {
      const t = tl(x), h = horlogeA(historique, t, titre), pos = positionA(h, t);
      if (pos == null || pos < 0) continue;
      out.push({ pos: Math.round(pos), texte: String(x.texte || '').slice(0, 300), d: Number(x.d) > 0 ? Math.round(Number(x.d)) : null,
        mots: Array.isArray(x.mots) ? x.mots.slice(0, 30) : null, groupe: x.groupe });
    }
    return { titre: titre || '', lignes: out.sort((a, b) => a.pos - b.pos) };
  }

  /* ---- 4. la scansion : la phrase en morceaux de 2 temps au moins (ses mots à leur place d'origine), placés sur la grille */
  function decouper(ligne, periode_ms, o = {}) {
    const r = { ...DEFAUTS, ...o };
    const mots = Array.isArray(ligne && ligne.mots) ? ligne.mots.filter(m => Array.isArray(m) && String(m[0] || '').trim() && fini(Number(m[1]))) : [];
    const d = Number(ligne && ligne.d) > 0 ? Number(ligne.d) : null;
    if (mots.length < 3 || !(periode_ms > 0)) return [{ texte: String((ligne && ligne.texte) || ''), dt: 0, d }];
    const out = [];
    let cur = null;
    for (const m of mots) {
      const dt = Number(m[1]);
      if (!cur || (dt - cur.dt >= r.temps_par_morceau * periode_ms && cur.mots.length >= 2 && out.length < r.morceaux_max - 1)) { cur = { dt, mots: [] }; out.push(cur); }
      cur.mots.push(String(m[0]));
    }
    const base = out[0].dt;
    return out.map((x, i) => ({ texte: x.mots.join(' '), dt: x.dt - base,
      d: i + 1 < out.length ? out[i + 1].dt - x.dt : (d != null ? Math.max(300, d - (x.dt - base)) : null) }));
  }
  /* le plan : chaque morceau à son instant (l'heure de l'appli, celle des trames : quand la musique joue ce temps à la capture) et sa durée */
  function planifier(choix, g, o = {}) {
    const r = { ...DEFAUTS, ...o };
    const sure = grilleSure(g, r), P = sure ? g.periode_ms : null, out = [];
    for (const l of (choix && choix.lignes) || []) {
      for (const m of decouper(l, P, r)) {
        let a = l.t + m.dt;
        if (sure) a = tempsProche(g, a, 2);
        out.push({ texte: m.texte, a: Math.round(a), d: m.d });
      }
    }
    out.sort((x, y) => x.a - y.a);
    for (let i = 0; i < out.length; i++) {
      const suivant = out[i + 1];
      if (suivant && suivant.a <= out[i].a) suivant.a = out[i].a + (P ? P / 2 : 250);
      if (suivant) out[i].d = Math.max(250, Math.min(out[i].d || Infinity, suivant.a - out[i].a));
      if (!(out[i].d > 0)) out[i].d = Math.max(800, syllabes(out[i].texte) / r.syllabes_s * 1000);
      out[i].d = Math.round(out[i].d);
    }
    return out.filter(x => x.texte.trim());
  }

  /* ---- 5. le débit : ses syllabes (une estimation : les groupes de voyelles, le « e » muet final ; en lettres arabes, une pour deux lettres) */
  function syllabes(texte) {
    let n = 0;
    for (const mot of String(texte || '').split(/\s+/).filter(Boolean)) {
      if (/\p{Script=Arabic}/u.test(mot)) { n += Math.max(1, Math.round(mot.replace(/[^\p{Script=Arabic}]/gu, '').replace(/[ً-ْٰ]/g, '').length / 2)); continue; }
      if (/^\d+$/.test(mot)) { n += 2 * mot.length; continue; }
      const m = mot.toLowerCase().replace(/[^a-zàâäéèêëîïôöûùüÿœæ]/g, '');
      if (!m) continue;
      let k = (m.match(/[aeiouyàâäéèêëîïôöûùüÿœæ]+/g) || []).length;
      if (k > 1 && /(?:[^aeiouy]e|[^aeiouy]es|[^aeiouy]ent)$/.test(m)) k--;            // le « e » muet de la fin
      n += Math.max(1, k);
    }
    return n;
  }
  function debit(texte, d_ms, o = {}) {
    const r = { ...DEFAUTS, ...o };
    const s = syllabes(texte);
    if (!(d_ms > 0) || !s) return { rate: 1, syllabes: s };
    return { rate: Math.round(borne(s / (d_ms / 1000) / r.syllabes_s, r.debit_min, r.debit_max) * 100) / 100, syllabes: s };
  }
  const rateSsml = (rate) => { const p = Math.round((borne(Number(rate) || 1, 0.5, 2) - 1) * 100); return `${p >= 0 ? '+' : ''}${p}%`; };
  // rendue trop longue ou trop courte (au-delà de 12 %) : le débit corrigé d'autant ; null : elle tient
  function corrigerDebit(rate, obtenu_ms, voulu_ms, o = {}) {
    const r = { ...DEFAUTS, ...o };
    if (!(obtenu_ms > 0) || !(voulu_ms > 0) || Math.abs(obtenu_ms - voulu_ms) / voulu_ms <= r.tolerance_duree) return null;
    return Math.round(borne((Number(rate) || 1) * obtenu_ms / voulu_ms, r.debit_min, r.debit_max) * 100) / 100;
  }

  /* ---- 6. le départ. cible : l'instant voulu (l'heure de l'appli, celle des trames) ; calage_ms : la musique, capture → micro (calerSons du
     cockpit, sûr) ; echo_ms : sa voix, page → micro (le chemin de son écho, actif) ; base_ms : le retard de base du contexte audio de la page ;
     attaque_ms : le blanc au début de sa voix rendue. Rend l'instant (l'horloge de la page) où le contexte audio doit la jouer. */
  function depart({ cible, calage_ms = null, echo_ms = null, base_ms = 0, attaque_ms = 0 } = {}, o = {}) {
    const r = { ...DEFAUTS, ...o };
    if (!fini(Number(cible))) return null;
    const att = fini(Number(attaque_ms)) ? Math.max(0, Number(attaque_ms)) : 0;
    if (fini(calage_ms) && fini(echo_ms))
      return { t: Math.round(Number(cible) + calage_ms - echo_ms + r.cadres_micro_ms - att), par: 'micro', incertitude_ms: r.incertitude_micro_ms };
    const b = fini(Number(base_ms)) ? Math.max(0, Number(base_ms)) : 0;
    return { t: Math.round(Number(cible) - r.capture_ms - r.tampon_page_ms - b - att), par: 'annonce', incertitude_ms: r.incertitude_annonce_ms };
  }
  // le blanc au début d'une voix rendue (ms) : le premier échantillon au-dessus de seuil × son maximum
  function attaqueDe(echantillons, taux, seuil = 0.1) {
    let m = 0;
    for (let i = 0; i < echantillons.length; i++) { const v = Math.abs(echantillons[i]); if (v > m) m = v; }
    if (!(m > 0) || !(taux > 0)) return 0;
    for (let i = 0; i < echantillons.length; i++) if (Math.abs(echantillons[i]) >= seuil * m) return Math.round(i / taux * 1000);
    return 0;
  }

  /* ---- 7. ses garde-fous. etat : creer() ; ctx : { reglage, coupe, appel, musique, papaA (sa dernière parole), ilParle, page, morceau } */
  function creer() { return { morceau: null, chants: 0, dernier: -Infinity, demande: null, plan: null, memoires: new Map(), horloges: [] }; }
  // un autre morceau : ses compteurs repartent (une fois par morceau)
  function morceau(e, cle) {
    if (cle == null || cle === '' || e.morceau === cle) return false;
    e.morceau = cle; e.chants = 0; e.demande = null; e.plan = null;
    return true;
  }
  function garde(e, ctx = {}, o = {}, maintenant = Date.now()) {
    const r = { ...DEFAUTS, ...o };
    if (ctx.reglage === false) return { ok: false, raison: 'reglage' };
    if (ctx.coupe) return { ok: false, raison: 'interieur_coupe' };
    if (ctx.appel) return { ok: false, raison: 'appel' };
    if (!ctx.musique) return { ok: false, raison: 'pas_de_musique' };
    if (fini(Number(ctx.papaA)) && maintenant - Number(ctx.papaA) < r.papa_ms) return { ok: false, raison: 'papa_parle' };
    if (ctx.ilParle) return { ok: false, raison: 'il_parle' };
    if (ctx.page === false) return { ok: false, raison: 'pas_de_page' };
    if (e.chants >= r.par_morceau) return { ok: false, raison: 'deja_chante' };
    if (maintenant - e.dernier < r.ecart_s * 1000) return { ok: false, raison: 'ecart' };
    return { ok: true };
  }
  // un chant prévu, pas encore fini : ce qui l'annule (papa, son intérieur coupé, un appel, son réglage éteint, la musique arrêtée)
  function annuler(ctx = {}, o = {}, maintenant = Date.now()) {
    const r = { ...DEFAUTS, ...o };
    if (ctx.reglage === false) return 'reglage';
    if (ctx.coupe) return 'interieur_coupe';
    if (ctx.appel) return 'appel';
    if (fini(Number(ctx.papaA)) && maintenant - Number(ctx.papaA) < r.papa_ms) return 'papa_parle';
    if (ctx.musique === false) return 'musique_arretee';
    return null;
  }
  function chante(e, maintenant = Date.now(), plan = null) { e.chants++; e.dernier = maintenant; e.plan = plan; }

  const Chanter = { DEFAUTS, mediane, attaques, resultante, periodeDe, grille, caler, choisirCalage, grilleSure, tempsProche, horlogeA, positionA, instantDe, passages, modele,
    prevoir, choisir, memoriser, decouper, planifier, syllabes, debit, rateSsml, corrigerDebit, depart, attaqueDe, creer, morceau, garde, annuler, chante };
  racine.Chanter = Chanter;
  if (typeof module !== 'undefined' && module.exports) module.exports = Chanter;
})(typeof window !== 'undefined' ? window : globalThis);

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
    // (v2) chaque syllabe sur la grille (le temps, le demi-temps ou la double croche), à moins de 20 % d'un temps (140 ms au plus) de là où
    // elle tombait quand une place y est ; une syllabe ne s'étale pas sur plus de 420 ms à l'origine (une pause n'est pas une syllabe)
    tolerance_temps: 0.2, tolerance_max_ms: 140, syllabe_max_ms: 420,
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
  // (v2) source_tb : l'instant où cette ligne a été entendue (l'heure de l'appli) : la mélodie que la voix du morceau y tenait ; notes : celle
  // gardée avec un morceau déjà entendu (sa mémoire)
  function candidat(x, t, par, confiance) {
    return { texte: String(x.texte || ''), t: Math.round(t), d: Number(x.d) > 0 ? Math.round(Number(x.d)) : null, mots: Array.isArray(x.mots) ? x.mots : null,
      groupe: x.groupe, par, confiance, ...(fini(tl(x)) && par !== 'memoire' ? { source_tb: tl(x) } : {}), ...(x.notes && Array.isArray(x.notes.hz) ? { notes: x.notes } : {}) };
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
  // (v2) melodies : la mélodie de la voix du morceau (hauteurA) ; chaque ligne garde la sienne, pour la chanter juste la prochaine fois
  function memoriser(lignes, historique, titre, melodies = null) {
    const out = [];
    for (const x of lignes || []) {
      const t = tl(x), h = horlogeA(historique, t, titre), pos = positionA(h, t);
      if (pos == null || pos < 0) continue;
      const n = melodies ? notesLigne(melodies, t, Number(x.d) > 0 ? Number(x.d) : 3000, 80) : null;   // (toutes les 80 ms : sa mémoire reste légère)
      out.push({ pos: Math.round(pos), texte: String(x.texte || '').slice(0, 300), d: Number(x.d) > 0 ? Math.round(Number(x.d)) : null,
        mots: Array.isArray(x.mots) ? x.mots.slice(0, 30) : null, groupe: x.groupe, ...(n ? { notes: n } : {}) });
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

  /* ---- 8. (v2, 11/11 ~03:00, Ahmed : « je veux tout » ; « chaque syllabe sur le temps », « suivre la mélodie, le chant juste, au mieux »)
     CHAQUE SYLLABE SUR LE TEMPS, ET SUR SA NOTE. Le plan d'une ligne : ses syllabes, chacune posée sur la grille du morceau (le temps, le
     demi-temps ou la double croche) au plus près de là où elle tombait dans le morceau (les heures des mots d'Azure, ses syllabes réparties
     dans le mot), et la note que la voix du morceau tenait sous cette syllabe la dernière fois (la mélodie de la voix séparée : hauteurA).
     Le son (couper sa voix Azure en mots et en syllabes, les recoller à leur instant, chacune à sa hauteur) : chanter-voix.js, au cockpit. */
  const VOY = 'aeiouyàâäéèêëîïôöûùüÿœæ';
  const RE_VOY = new RegExp(`[${VOY}]+`, 'g');
  const INSEPARABLES = /^(?:[bcdfgkptv][lr]|ch|ph|th|gn)$/;
  const nettoyerMot = (m) => String(m || '').replace(/[^\p{L}\p{N}'’-]/gu, '').replace(/^['’-]+|['’-]+$/g, '');
  /* les syllabes d'un mot (l'écrit, au mieux : les groupes de voyelles, une consonne seule va à la suivante, deux se partagent sauf « bl, tr,
     ch… », le « e » muet final rejoint la précédente ; en lettres arabes, une pour deux lettres ; un nombre, deux par chiffre). Leur nombre
     est celui de syllabes(). */
  function syllabesMot(mot) {
    const brut = nettoyerMot(mot);
    if (!brut) return [];
    if (/\p{Script=Arabic}/u.test(brut)) {
      const l = [...brut.replace(/[^\p{Script=Arabic}]/gu, '').replace(/[\u064B-\u0652\u0670]/g, '')], k = Math.max(1, Math.round(l.length / 2)), out = [];
      for (let i = 0; i < k; i++) out.push(l.slice(Math.round(i * l.length / k), Math.round((i + 1) * l.length / k)).join(''));
      return out;
    }
    if (/^\d+$/.test(brut)) return [...brut].flatMap(c => [c, c]);
    const m = brut.toLowerCase().replace(/[^a-zàâäéèêëîïôöûùüÿœæ]/g, '');
    if (!m) return [brut];
    const g = [];
    let x; RE_VOY.lastIndex = 0;
    while ((x = RE_VOY.exec(m))) g.push([x.index, x.index + x[0].length]);
    if (!g.length) return [m];
    if (g.length > 1 && /(?:[^aeiouy]e|[^aeiouy]es|[^aeiouy]ent)$/.test(m)) g.pop();          // le « e » muet de la fin
    const coupes = [0];
    for (let i = 0; i + 1 < g.length; i++) {
      const c0 = g[i][1], c1 = g[i + 1][0], c = m.slice(c0, c1);
      coupes.push(c.length <= 1 ? c0 : c.length === 2 ? (INSEPARABLES.test(c) ? c0 : c0 + 1) : (INSEPARABLES.test(c.slice(-2)) ? c1 - 2 : c1 - 1));
    }
    coupes.push(m.length);
    return coupes.slice(0, -1).map((a, i) => m.slice(a, coupes[i + 1]));
  }
  /* une ligne (t : son instant voulu, d, mots : [[mot, dt ms]], texte) → ses syllabes sur la grille g : { a (l'instant de la première), d, mots,
     syllabes: [{ texte, m (son mot), t (ms depuis a), d (sa place), div (1 temps, 2 demi-temps, 4 double croche, 8 serrée), ecart (sa place −
     là où elle tombait), orig, nat }], cale (la grille était sûre) } ; sans grille sûre : à leur place d'origine */
  function scander(ligne, g, o = {}) {
    const r = { ...DEFAUTS, ...o };
    const t = Number(ligne && ligne.t);
    if (!fini(t)) return null;
    const d = Number(ligne.d) > 0 ? Number(ligne.d) : null;
    let mots = (Array.isArray(ligne.mots) ? ligne.mots : []).filter(m => Array.isArray(m) && syllabesMot(m[0]).length && fini(Number(m[1])))
      .map(m => ({ w: nettoyerMot(m[0]), dt: Math.max(0, Number(m[1])) })).sort((x, y) => x.dt - y.dt);
    let sansTemps = false;
    if (!mots.length) {   // sans les heures des mots : ses syllabes à parts égales dans sa durée
      const ws = String(ligne.texte || '').split(/\s+/).map(nettoyerMot).filter(w => syllabesMot(w).length);
      if (!ws.length) return null;
      const tot = ws.reduce((n, w) => n + syllabesMot(w).length, 0), D = d || tot * 1000 / r.syllabes_s;
      let acc = 0;
      mots = ws.map((w) => { const x = { w, dt: Math.round(acc * D / tot) }; acc += syllabesMot(w).length; return x; });
      sansTemps = true;
    }
    const base = mots[0].dt, syl = [];
    mots.forEach((m, i) => {
      const p = syllabesMot(m.w), k = p.length;
      const fin = i + 1 < mots.length ? mots[i + 1].dt : (d != null ? Math.max(base + d, m.dt + 120 * k) : m.dt + k * 1000 / r.syllabes_s);
      const pas = Math.max(60, Math.min((fin - m.dt) / k, r.syllabe_max_ms));
      p.forEach((x, j) => syl.push({ texte: x, m: i, orig: m.dt - base + j * pas, nat: pas, dans: m.dt + j * pas }));
    });
    const sure = grilleSure(g, r), P = sure ? g.periode_ms : null;
    let prev = -Infinity;
    for (const s of syl) {
      const T = t + s.orig;
      if (!sure) { s.a = Math.max(T, prev + 60); s.div = 0; prev = s.a; continue; }
      // les doubles croches autour de là où elle tombait, toujours après la précédente ; la plus proche, une place forte un peu préférée (le
      // demi-temps coûte 5 % d'un temps de plus que le temps, la double croche 10 %), jamais au-delà de la tolérance si une autre y est
      const p16 = P / 4, tol = Math.min(r.tolerance_temps * P, r.tolerance_max_ms), q0 = Math.round((T - g.t0) / p16), cands = [];
      for (let q = q0 - 3; q <= q0 + 3; q++) {
        const a = g.t0 + q * p16;
        if (a <= prev + 1) continue;
        const k4 = ((q % 4) + 4) % 4, div = k4 === 0 ? 1 : k4 === 2 ? 2 : 4;
        cands.push({ a, div, e: Math.abs(a - T), cout: Math.abs(a - T) + (div === 1 ? 0 : div === 2 ? 0.05 : 0.1) * P });
      }
      let c = cands.filter(x => x.e <= tol).sort((x, y) => x.cout - y.cout)[0] || cands.sort((x, y) => x.e - y.e)[0];
      if (!c) { const p32 = P / 8; c = { a: g.t0 + (Math.floor((prev - g.t0) / p32 + 1e-6) + 1) * p32, div: 8 }; }   // trop serrées : la triple croche suivante
      s.a = c.a; s.div = c.div; prev = s.a;
    }
    for (let i = 0; i < syl.length; i++) {
      const s = syl[i], n = syl[i + 1];
      s.d = n ? n.a - s.a : Math.max(P ? P / 4 : 150, Math.min(s.nat * 1.4, P || 600));
    }
    const a0 = syl[0].a, der = syl[syl.length - 1];
    return { a: Math.round(a0), d: Math.round(der.a + der.d - a0), mots: mots.map(m => m.w), cale: sure, sans_temps: sansTemps,
      // dans : sa place dans la ligne telle qu'elle a été entendue (depuis son début : l'heure de son mot, ses syllabes réparties dans le mot) ;
      // mesuré au banc : la note suit mieux la syllabe par là que par sa place sur la grille (une syllabe posée une double croche plus loin
      // y prendrait la note de sa voisine)
      syllabes: syl.map(s => ({ texte: s.texte, m: s.m, t: Math.round(s.a - a0), d: Math.round(s.d), div: s.div, ecart: Math.round(s.a - (t + s.orig)), orig: Math.round(s.orig), nat: Math.round(s.nat),
        dans: Math.round(s.dans) })) };
  }

  /* la mélodie de la voix du morceau. melodies : [{ tb0 (l'heure de l'appli de sa première trame), pas (ms), hz: [], src: 'voix' (la voix
     séparée, jarvis/separation.py) | 'trames' (la hauteur des trames du téléphone, sur le mélange : moins sûre) }]. La hauteur sous [a, b) :
     la médiane de ses trames qui en ont une (ses sauts d'octave ramenés), la voix séparée d'abord ; 0 : rien de net */
  const midiDe = (hz) => 69 + 12 * Math.log2(hz / 440), hzDe = (m) => 440 * Math.pow(2, (m - 69) / 12);
  function hauteurA(melodies, a, b, min = null) {
    const l = Array.isArray(melodies) ? melodies : [];
    for (const src of ['voix', 'trames']) {
      const v = [];
      let pas = 40, n = 0;
      for (const x of l) {
        if (!x || x.src !== src || !Array.isArray(x.hz) || !(x.pas > 0) || !fini(x.tb0)) continue;
        if (x.tb0 > b || x.tb0 + x.hz.length * x.pas < a) continue;
        pas = x.pas;
        for (let i = Math.max(0, Math.floor((a - x.tb0) / x.pas)); i < x.hz.length && x.tb0 + i * x.pas < b; i++) {
          const c = x.tb0 + (i + 0.5) * x.pas;
          if (c < a || c >= b) continue;
          n++;
          if (x.hz[i] >= 50 && x.hz[i] <= 1500) v.push(midiDe(x.hz[i]));
        }
      }
      // la hauteur des trames est prise sur le mélange (la basse, la batterie) : seulement quand la moitié au moins de la fenêtre a une hauteur
      // nette ; sinon rien (sa voix garde sa hauteur, plutôt qu'une fausse note)
      if (src === 'trames' && v.length < 0.5 * n) continue;
      if (v.length >= (min != null ? min : pas >= 100 ? 1 : 2)) {
        const m = mediane(v);
        return Math.round(hzDe(mediane(v.map(u => u - 12 * Math.round((u - m) / 12)))) * 10) / 10;
      }
    }
    return 0;
  }
  // la mélodie d'une ligne entendue à tb (durée d), toutes les 40 ms, pour la garder avec elle (la mémoire d'un morceau) ; null : rien de net
  function notesLigne(melodies, tb, d, pas = 40) {
    if (!fini(tb) || !(d > 0)) return null;
    const D = Math.min(d, 12000) + 200, ici = (Array.isArray(melodies) ? melodies : []).filter(x => x && fini(x.tb0) && x.tb0 <= tb + D && x.tb0 + (x.hz || []).length * x.pas >= tb);
    if (!ici.length) return null;
    const hz = [];
    for (let t = 0; t < D; t += pas) hz.push(Math.round(hauteurA(ici, tb + t, tb + t + pas, 1)));
    return hz.some(v => v > 0) ? { pas, hz } : null;
  }
  // la note sous une syllabe : là où elle tombait quand la ligne a été entendue (le milieu de sa place d'origine, depuis le début de la ligne)
  function noteSyllabe(ligne, s, melodies) {
    const w = Math.max(60, s.nat), o = fini(s.dans) ? s.dans : s.orig, a = o + FEN_NOTE[0] * w, b = o + Math.max(FEN_NOTE[1] * w, FEN_NOTE[0] * w + 40);
    if (ligne && ligne.notes && Array.isArray(ligne.notes.hz) && ligne.notes.pas > 0)
      return hauteurA([{ tb0: 0, pas: ligne.notes.pas, hz: ligne.notes.hz, src: 'voix' }], a, b);
    if (ligne && fini(Number(ligne.source_tb))) return hauteurA(melodies, Number(ligne.source_tb) + a, Number(ligne.source_tb) + b);
    return 0;
  }
  // sa fenêtre dans la place d'origine de la syllabe (mesuré au banc, mesure/chanter-syllabes-banc.js : 0,15-0,85 → 516 notes justes sur 570,
  // 0,1-0,9 → 520, 0,25-0,6 → 417 ; plus large, la médiane résiste mieux à l'erreur d'Azure sur l'heure des mots)
  const FEN_NOTE = [0.1, 0.9];
  /* juste : chaque note posée sur le demi-ton le plus proche, dans l'accord du morceau (son écart au La 440, la moyenne de ses écarts sur le
     cercle : un morceau accordé un peu haut reste juste) ; 0 reste 0 */
  function justes(hz) {
    const m = (hz || []).map(v => (v > 0 ? midiDe(v) : null));
    let c = 0, si = 0;
    for (const x of m) if (x != null) { const th = 2 * Math.PI * (x - Math.round(x)); c += Math.cos(th); si += Math.sin(th); }
    const off = c || si ? Math.atan2(si, c) / (2 * Math.PI) : 0;
    return m.map(x => (x == null ? 0 : Math.round(hzDe(Math.round(x - off) + off) * 10) / 10));
  }
  /* le plan v2 : chaque ligne en ses syllabes, sur la grille et sur leurs notes ; deux lignes qui se chevauchent : la première s'arrête où la
     suivante commence. Rend [{ texte, a, d, mots, syllabes: [{ texte, m, t, d, hz, div }], cale }] ; null : une ligne sans syllabes */
  function planifierSyllabes(choix, g, melodies, o = {}) {
    const out = [];
    for (const l of (choix && choix.lignes) || []) {
      const sc = scander(l, g, o);
      if (!sc || !sc.syllabes.length) return null;
      const hz = justes(sc.syllabes.map(x => noteSyllabe(l, x, melodies)));
      out.push({ texte: String(l.texte || ''), a: sc.a, d: sc.d, mots: sc.mots, cale: sc.cale,
        syllabes: sc.syllabes.map((x, i) => ({ texte: x.texte, m: x.m, t: x.t, d: x.d, hz: hz[i], div: x.div, ecart: x.ecart })) });
    }
    out.sort((x, y) => x.a - y.a);
    for (let i = 1; i < out.length; i++) {
      const p = out[i - 1], fin = out[i].a - p.a;
      if (p.d <= fin) continue;
      p.syllabes = p.syllabes.filter(x => x.t < fin - 60);
      if (!p.syllabes.length) return null;
      const der = p.syllabes[p.syllabes.length - 1]; der.d = Math.min(der.d, fin - der.t); p.d = fin;
    }
    return out;
  }

  /* ---- 9. (v2) sa conscience peut décider de chanter : le tableau de l'instant dit si c'est le moment (la musique du téléphone joue ; ni
     papa, ni lui, ni la pièce ne parlent ; pas d'appel ; son intérieur ouvert), ses garde-fous restent ceux de garde (son réglage, une fois
     par morceau, l'écart, papa il y a moins de 3 s, la page). Rend { ok, raison } ; ok : texte, ce qu'il en lit pour son prompt */
  function momentDeChanter(tab, e, ctx = {}, o = {}, maintenant = Date.now()) {
    if (!tab) return { ok: false, raison: 'pas_de_tableau' };
    if (tab.interieur === 'coupé') return { ok: false, raison: 'interieur_coupe' };
    if (tab.appel) return { ok: false, raison: 'appel' };
    const m = tab.musique || {}, p = tab.parole || {};
    if (!m.joue || m.ou === 'micro') return { ok: false, raison: 'pas_de_musique' };
    if (p.papa && p.papa.parle) return { ok: false, raison: 'papa_parle' };
    if (p.lui && p.lui.parle) return { ok: false, raison: 'il_parle' };
    if (p.piece && p.piece.parle) return { ok: false, raison: 'la_piece_parle' };
    if (e && (e.demande === 'oui' || e.demande === 'en_vol')) return { ok: false, raison: 'deja_decide' };
    const g = garde(e, ctx, o, maintenant);
    if (!g.ok) return g;
    const place = tab.place && tab.place.role === 'auditeur' ? 'tu écoutes (on ne te parle pas)' : tab.place ? 'tu es dedans' : '';
    return { ok: true, texte: `la musique joue${m.intensite ? ` (intensité ${m.intensite})` : ''} au téléphone${p.dedans && p.dedans.parle ? ', sa voix chante' : ''}${place ? ` ; ${place}` : ''}` };
  }

  const Chanter = { DEFAUTS, syllabesMot, scander, hauteurA, notesLigne, noteSyllabe, justes, planifierSyllabes, momentDeChanter, mediane, attaques, resultante, periodeDe, grille, caler, choisirCalage, grilleSure, tempsProche, horlogeA, positionA, instantDe, passages, modele,
    prevoir, choisir, memoriser, decouper, planifier, syllabes, debit, rateSsml, corrigerDebit, depart, attaqueDe, creer, morceau, garde, annuler, chante };
  racine.Chanter = Chanter;
  if (typeof module !== 'undefined' && module.exports) module.exports = Chanter;
})(typeof window !== 'undefined' ? window : globalThis);

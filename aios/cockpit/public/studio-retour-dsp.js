/* (14/11, Ahmed : « un retour de voix au casque pendant que j'enregistre, avec des préréglages et de l'autotune comme je veux, de façon
   par défaut ») LA CHAÎNE DU RETOUR CASQUE, la même partout : dans la page (AudioWorklet, studio-retour-worklet.js), dans node (tests,
   mesure/retour-casque-banc.js) et, mot pour mot, dans l'appli Android (hakim-android, retour_dsp.c), vérifiée par les mêmes vecteurs
   (retour-vecteurs.txt). Rien n'attend l'avenir, sauf le déplacement de hauteur (voir plus bas). La prise, elle, reste BRUTE : cette
   chaîne ne sert qu'à l'oreille de papa. Spec : docs/superpowers/specs/2026-11-14-retour-casque-design.md.

   coupe-bas → autotune → égaliseur (graves, médiums, présence, aigus) → compresseur → dé-esseur → réverb, délai (envois) → volume.

   L'AUTOTUNE, en temps réel, les mêmes règles que celui du mix (anamnese/jarvis/autotune.py, NIVEAUX « leger » et « fort ») mais
   causales : la hauteur par YIN (le son ramené à ~16 kHz, fenêtre 20 ms, toutes les 5 ms), une note n'est touchée qu'après tenue_min_ms
   de voix tenue (le rap, les syllabes courtes ne le sont jamais), la gamme ne départage que les notes ambiguës (une note chantée à 25
   cents d'un demi-ton reste la sienne), léger = 40 % de l'écart à la moyenne de la note, glissés respectés ; fort = 100 % vers la note,
   vibrato aplati à 85 %. Le DÉPLACEMENT : PSOLA à deux prises de retard fondues sur une période de sortie T' ; chaque prise lit à
   vitesse 1 (les formants restent) ; d'une période à l'autre, le retard change de T' − m·T (m = 1 ; 0 ou 2 pour répéter ou sauter une
   période quand le retard sort de [0,5 ms ; 0,5 ms + T]). Sans correction, le retard ne bouge pas : la voix sort intacte. LA LATENCE de
   l'algorithme : 0,5 ms hors des notes corrigées ; sur une note corrigée, 0,5 ms + entre 0 et une période (une demi en moyenne). */
(function (racine) {
  'use strict';
  // (tests seulement) un mécanisme coupé, pour prouver que son test échoue sans lui : globalThis.RETOUR_COUPE avant le chargement
  const COUPE = String(racine.RETOUR_COUPE || '');

  // les niveaux de l'autotune du mix (jarvis/autotune.py, NIVEAUX), ceux qui servent en temps réel
  const NIVEAUX = {
    leger: { force: 0.4, aplatir: 0, retune_ms: 80, tendance_ms: 150, tenue_min_ms: 120, note_min_ms: 60, creux_max: 0.12, glisse_cents_s: 400, max_cents: 60 },
    fort: { force: 1, aplatir: 0.85, retune_ms: 15, tendance_ms: 60, tenue_min_ms: 60, note_min_ms: 0, creux_max: 0.15, glisse_cents_s: 0, max_cents: 120 },
  };
  // la gamme d'une tonalité (comme chant.gamme : « A minor », « F# major », « Am » ; inconnue → les 12)
  const NOTES = { c: 0, 'c#': 1, db: 1, d: 2, 'd#': 3, eb: 3, e: 4, f: 5, 'f#': 6, gb: 6, g: 7, 'g#': 8, ab: 8, a: 9, 'a#': 10, bb: 10, b: 11, cb: 11, 'e#': 5, fb: 4, 'b#': 0 };
  const FR = { do: 'c', ré: 'd', re: 'd', mi: 'e', fa: 'f', sol: 'g', la: 'a', si: 'b' };
  function gamme(tonalite) {
    let t = String(tonalite || '').trim().toLowerCase().replace(/♯/g, '#').replace(/♭/g, 'b');
    t = t.replace(/^(do|ré|re|mi|fa|sol|la|si)(?=$|[\s#b])/, (m) => FR[m]).replace(/\bmineur\b/, 'minor').replace(/\bmajeur\b/, 'major');
    const m = t.match(/^([a-g])\s*([#b]?)\s*(.*)$/);
    if (!m || NOTES[m[1] + m[2]] === undefined) return [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
    const racine = NOTES[m[1] + m[2]], mode = m[3].trim();
    const mineur = mode.startsWith('min') || mode === 'm' || mode.startsWith('m ') || mode.includes('minor');
    return (mineur ? [0, 2, 3, 5, 7, 8, 10] : [0, 2, 4, 5, 7, 9, 11]).map(i => (racine + i) % 12).sort((a, b) => a - b);
  }

  /* ---------- les réglages : un objet lisible (la page, le cockpit, la prise), et le VECTEUR que lisent la chaîne et Android ---------- */
  const NOTES_DELAI = { '1/4': 1, '1/8': 0.5, '1/8.': 0.75, '1/16': 0.25, '1/4.': 1.5, '1/2': 2 };
  const SANS = { coupe_bas_hz: 0, eq: { grave_db: 0, grave_hz: 120, medium_db: 0, medium_hz: 1000, medium_q: 1, presence_db: 0, presence_hz: 3500, aigu_db: 0, aigu_hz: 10000 },
    comp: { actif: false, seuil_db: -20, ratio: 3, attaque_ms: 5, relache_ms: 100, gain_db: 0 }, deesser: 0, reverb: 0, delai: 0, delai_note: '1/8.',
    autotune: { niveau: '', tonalite: '', vitesse_ms: null, force: null }, volume_db: 0 };
  // « Rap propre » : la chaîne de la voix du mix simple (jarvis/studio.py, chaine_voix : −3 dB à 250 Hz, présence +2,5 dB à 3,5 kHz,
  // air +2 dB, dé-esseur 0,4, compression 3:1 à −20 dB, +2 dB), un peu de réverb
  const RAP = { coupe_bas_hz: 90, eq: { grave_db: 0, grave_hz: 120, medium_db: -3, medium_hz: 250, medium_q: 1, presence_db: 2.5, presence_hz: 3500, aigu_db: 2, aigu_hz: 10000 },
    comp: { actif: true, seuil_db: -20, ratio: 3, attaque_ms: 5, relache_ms: 100, gain_db: 2 }, deesser: 0.4, reverb: 0.12, delai: 0, delai_note: '1/8.' };
  const PRESETS = {
    sans_effet: { nom: 'Sans effet', ...SANS },
    rap_propre: { nom: 'Rap propre', ...SANS, ...RAP },
    autotune_naturel: { nom: 'Autotune naturel', ...SANS, ...RAP, reverb: 0.15, autotune: { niveau: 'leger', tonalite: '', vitesse_ms: null, force: null } },
    autotune_effet: { nom: 'Autotune effet', ...SANS, ...RAP, reverb: 0.18, delai: 0.12, autotune: { niveau: 'fort', tonalite: '', vitesse_ms: null, force: null } },
  };
  const DEFAUT = 'rap_propre';
  const num = (v, a, b, d) => { const x = Number(v); return v === null || v === undefined || v === '' || !Number.isFinite(x) ? d : Math.max(a, Math.min(b, x)); };
  /** Des réglages venus de n'importe où (la page, le disque, une prise) → des réglages complets et bornés. */
  function borner(r) {
    const x = r && typeof r === 'object' ? r : {}, e = x.eq || {}, c = x.comp || {}, a = x.autotune || {};
    const niveau = a.niveau === 'leger' || a.niveau === 'fort' ? a.niveau : '';
    return {
      preset: typeof x.preset === 'string' && (PRESETS[x.preset] || x.preset === 'perso') ? x.preset : 'perso',
      coupe_bas_hz: num(x.coupe_bas_hz, 0, 400, 0),
      eq: { grave_db: num(e.grave_db, -12, 12, 0), grave_hz: num(e.grave_hz, 40, 500, 120), medium_db: num(e.medium_db, -12, 12, 0),
        medium_hz: num(e.medium_hz, 100, 8000, 1000), medium_q: num(e.medium_q, 0.3, 6, 1), presence_db: num(e.presence_db, -12, 12, 0),
        presence_hz: num(e.presence_hz, 1000, 8000, 3500), aigu_db: num(e.aigu_db, -12, 12, 0), aigu_hz: num(e.aigu_hz, 3000, 16000, 10000) },
      comp: { actif: c.actif === true || c.actif === 1 || c.actif === '1', seuil_db: num(c.seuil_db, -50, 0, -20), ratio: num(c.ratio, 1, 20, 3),
        attaque_ms: num(c.attaque_ms, 0.1, 50, 5), relache_ms: num(c.relache_ms, 5, 1000, 100), gain_db: num(c.gain_db, -12, 18, 0) },
      deesser: num(x.deesser, 0, 1, 0), reverb: num(x.reverb, 0, 1, 0), delai: num(x.delai, 0, 1, 0),
      delai_note: NOTES_DELAI[x.delai_note] ? x.delai_note : '1/8.',
      autotune: { niveau, tonalite: String(a.tonalite || '').replace(/[^\w#♯♭ éè-]/g, '').trim().slice(0, 20),
        vitesse_ms: a.vitesse_ms === null || a.vitesse_ms === undefined || a.vitesse_ms === '' ? null : num(a.vitesse_ms, 1, 400, null),
        force: a.force === null || a.force === undefined || a.force === '' ? null : num(a.force, 0, 1, null) },
      volume_db: num(x.volume_db, -30, 12, 0),
    };
  }
  const preset = (nom) => borner({ ...JSON.parse(JSON.stringify(PRESETS[nom] || PRESETS[DEFAUT])), preset: PRESETS[nom] ? nom : DEFAUT });
  /** Le niveau de l'autotune du MIX pour ces réglages (« ce que j'entends = ce que j'obtiens ») : le niveau choisi ; réglé à la main, le
   *  plus proche (une force ≥ 0,7 : fort). */
  function niveauMix(r) {
    const a = borner(r).autotune;
    if (!a.niveau) return '';
    if (a.force === null) return a.niveau;
    return a.force >= 0.7 ? 'fort' : 'leger';
  }

  // le vecteur : l'ordre que lisent la chaîne et Android (retour_dsp.h, RETOUR_*) ; 44 nombres
  const V = { COUPE_BAS: 0, GRAVE_DB: 1, GRAVE_HZ: 2, MEDIUM_DB: 3, MEDIUM_HZ: 4, MEDIUM_Q: 5, PRESENCE_DB: 6, PRESENCE_HZ: 7, AIGU_DB: 8, AIGU_HZ: 9,
    COMP: 10, SEUIL: 11, RATIO: 12, ATTAQUE: 13, RELACHE: 14, GAIN: 15, DEESSER: 16, REVERB: 17, DELAI: 18, DELAI_S: 19, VOLUME: 20,
    AT: 21, FORCE: 22, APLATIR: 23, RETUNE: 24, TENDANCE: 25, TENUE: 26, NOTE_MIN: 27, CREUX: 28, GLISSE: 29, MAX_CENTS: 30, DIAP: 31, GAMME: 32, TAILLE: 44 };
  /** réglages (+ le tempo du morceau, le diapason de l'instru en cents, la tonalité trouvée si « auto ») → le vecteur */
  function vecteur(r, o = {}) {
    const x = borner(r), a = x.autotune, v = new Array(V.TAILLE).fill(0);
    v[V.COUPE_BAS] = x.coupe_bas_hz;
    v[V.GRAVE_DB] = x.eq.grave_db; v[V.GRAVE_HZ] = x.eq.grave_hz; v[V.MEDIUM_DB] = x.eq.medium_db; v[V.MEDIUM_HZ] = x.eq.medium_hz; v[V.MEDIUM_Q] = x.eq.medium_q;
    v[V.PRESENCE_DB] = x.eq.presence_db; v[V.PRESENCE_HZ] = x.eq.presence_hz; v[V.AIGU_DB] = x.eq.aigu_db; v[V.AIGU_HZ] = x.eq.aigu_hz;
    v[V.COMP] = x.comp.actif ? 1 : 0; v[V.SEUIL] = x.comp.seuil_db; v[V.RATIO] = x.comp.ratio; v[V.ATTAQUE] = x.comp.attaque_ms; v[V.RELACHE] = x.comp.relache_ms; v[V.GAIN] = x.comp.gain_db;
    v[V.DEESSER] = x.deesser; v[V.REVERB] = x.reverb; v[V.DELAI] = x.delai;
    const bpm = num(o.tempo, 0, 300, 0);
    v[V.DELAI_S] = Math.min(1.9, bpm >= 50 && bpm <= 220 ? 60 / bpm * NOTES_DELAI[x.delai_note] : 0.375);
    v[V.VOLUME] = x.volume_db;
    const P = NIVEAUX[a.niveau];
    if (P) {
      v[V.AT] = 1;
      v[V.FORCE] = a.force === null ? P.force : a.force;
      v[V.APLATIR] = P.aplatir; v[V.RETUNE] = a.vitesse_ms === null ? P.retune_ms : a.vitesse_ms; v[V.TENDANCE] = P.tendance_ms;
      v[V.TENUE] = P.tenue_min_ms; v[V.NOTE_MIN] = P.note_min_ms; v[V.CREUX] = P.creux_max; v[V.GLISSE] = P.glisse_cents_s; v[V.MAX_CENTS] = P.max_cents;
    }
    v[V.DIAP] = num(o.diap_cents, -50, 50, 0);
    const cl = gamme(a.tonalite || o.tonalite || '');
    for (const k of cl) v[V.GAMME + k] = 1;
    return v;
  }

  /* ---------- les briques ---------- */
  // un filtre du second ordre (Robert Bristow-Johnson) ; type : 'pb' passe-bas, 'ph' passe-haut, 'bande', 'cloche', 'grave' (étagère basse), 'aigu'
  function biquad() { return { b0: 1, b1: 0, b2: 0, a1: 0, a2: 0, x1: 0, x2: 0, y1: 0, y2: 0 }; }
  function bqRegler(f, type, sr, hz, db, q) {
    hz = Math.max(1, Math.min(hz, sr * 0.49));
    const A = Math.pow(10, db / 40), w = 2 * Math.PI * hz / sr, cs = Math.cos(w), sn = Math.sin(w), al = sn / (2 * q);
    let b0, b1, b2, a0, a1, a2;
    if (type === 'pb') { b0 = (1 - cs) / 2; b1 = 1 - cs; b2 = (1 - cs) / 2; a0 = 1 + al; a1 = -2 * cs; a2 = 1 - al; }
    else if (type === 'ph') { b0 = (1 + cs) / 2; b1 = -(1 + cs); b2 = (1 + cs) / 2; a0 = 1 + al; a1 = -2 * cs; a2 = 1 - al; }
    else if (type === 'bande') { b0 = al; b1 = 0; b2 = -al; a0 = 1 + al; a1 = -2 * cs; a2 = 1 - al; }
    else if (type === 'cloche') { b0 = 1 + al * A; b1 = -2 * cs; b2 = 1 - al * A; a0 = 1 + al / A; a1 = -2 * cs; a2 = 1 - al / A; }
    else {
      const s = 2 * Math.sqrt(A) * (sn / 2) * Math.SQRT2;              // étagère, pente S = 1
      if (type === 'grave') { b0 = A * ((A + 1) - (A - 1) * cs + s); b1 = 2 * A * ((A - 1) - (A + 1) * cs); b2 = A * ((A + 1) - (A - 1) * cs - s);
        a0 = (A + 1) + (A - 1) * cs + s; a1 = -2 * ((A - 1) + (A + 1) * cs); a2 = (A + 1) + (A - 1) * cs - s; }
      else { b0 = A * ((A + 1) + (A - 1) * cs + s); b1 = -2 * A * ((A - 1) + (A + 1) * cs); b2 = A * ((A + 1) + (A - 1) * cs - s);
        a0 = (A + 1) - (A - 1) * cs + s; a1 = 2 * ((A - 1) - (A + 1) * cs); a2 = (A + 1) - (A - 1) * cs - s; }
    }
    f.b0 = b0 / a0; f.b1 = b1 / a0; f.b2 = b2 / a0; f.a1 = a1 / a0; f.a2 = a2 / a0;
  }
  function bqNeutre(f) { f.b0 = 1; f.b1 = 0; f.b2 = 0; f.a1 = 0; f.a2 = 0; }
  function bq(f, x) {
    const y = f.b0 * x + f.b1 * f.x1 + f.b2 * f.x2 - f.a1 * f.y1 - f.a2 * f.y2;
    f.x2 = f.x1; f.x1 = x; f.y2 = f.y1; f.y1 = y;
    return y;
  }
  const HIST = 8192, DEC = 1024, REV_PEIGNES = [1116, 1188, 1277, 1356], REV_PASSE = [556, 441];

  /** Une chaîne pour un taux d'échantillonnage. */
  function creer(sr) {
    const D = Math.max(1, Math.round(sr / 16000)), srd = sr / D;
    const st = {
      sr, v: new Array(V.TAILLE).fill(0),
      // le coupe-bas, l'anti-repliement (2 étages) de la détection
      ph: biquad(), aa1: biquad(), aa2: biquad(),
      // la détection : le son ramené à srd, l'historique, YIN
      // (la hauteur toutes les 2,5 ms, sur une fenêtre de 1,6 période — 8 à 20 ms — : moins de retard sur le vibrato)
      D, srd, dPhase: 0, dec: new Float64Array(DEC), nd: 0, hop: Math.max(1, Math.round(srd * 0.0025)), Wmax: Math.round(srd * 0.02),
      Wmin: Math.round(srd * 0.008), W: Math.round(srd * 0.02),
      tauMin: Math.max(2, Math.floor(srd / 1000)), tauMax: Math.min(Math.ceil(srd / 65), DEC - Math.round(srd * 0.02) - 2),
      yd: new Float64Array(DEC), yc: new Float64Array(DEC), lin: new Float64Array(DEC),
      voise: false, f0: 0, creux: 1, sansVoix: 99, tVoise: 0,
      // la note
      note: NaN, tr: 0, trPrec: 0, cible: 0, sommeM: 0, nM: 0, tNote: 0, cL: 0, fG: 1, c: 0,
      // le déplacement (PSOLA à deux prises)
      hist: new Float64Array(HIST), n: 0, dA: 0, dB: 0, segLen: 1, segPos: 1, dMin: Math.round(0.0005 * sr), latSomme: 0, latN: 0, latMax: 0,
      // l'égaliseur, le compresseur, le dé-esseur
      eqG: biquad(), eqM: biquad(), eqP: biquad(), eqA: biquad(), env: 0, gr: 0, bp: biquad(), eb: 0, ef: 0,
      // la réverb (Freeverb, mono), le délai
      peignes: REV_PEIGNES.map(l => ({ b: new Float64Array(Math.max(1, Math.round(l * sr / 44100))), i: 0, f: 0 })),
      passes: REV_PASSE.map(l => ({ b: new Float64Array(Math.max(1, Math.round(l * sr / 44100))), i: 0 })),
      dl: new Float64Array(Math.ceil(sr * 2)), dlI: 0, dlLp: 0,
      // la mesure de la latence : des clics par la sortie, l'entrée enregistrée
      mes: null,
    };
    st.dA = st.dB = st.dMin;
    bqRegler(st.aa1, 'pb', sr, Math.min(5000, 0.42 * srd), 0, 0.5412);
    bqRegler(st.aa2, 'pb', sr, Math.min(5000, 0.42 * srd), 0, 1.3066);
    bqRegler(st.bp, 'bande', sr, 6500, 0, 1.0);
    regler(st, vecteur(preset('sans_effet')));
    return st;
  }

  function regler(st, v) {
    const sr = st.sr;
    for (let i = 0; i < V.TAILLE; i++) st.v[i] = Number.isFinite(Number(v[i])) ? Number(v[i]) : 0;
    const x = st.v;
    if (x[V.COUPE_BAS] >= 20) bqRegler(st.ph, 'ph', sr, x[V.COUPE_BAS], 0, Math.SQRT1_2); else bqNeutre(st.ph);
    if (x[V.GRAVE_DB]) bqRegler(st.eqG, 'grave', sr, x[V.GRAVE_HZ], x[V.GRAVE_DB], 0.707); else bqNeutre(st.eqG);
    if (x[V.MEDIUM_DB]) bqRegler(st.eqM, 'cloche', sr, x[V.MEDIUM_HZ], x[V.MEDIUM_DB], x[V.MEDIUM_Q] || 1); else bqNeutre(st.eqM);
    if (x[V.PRESENCE_DB]) bqRegler(st.eqP, 'cloche', sr, x[V.PRESENCE_HZ], x[V.PRESENCE_DB], 1.2); else bqNeutre(st.eqP);
    if (x[V.AIGU_DB]) bqRegler(st.eqA, 'aigu', sr, x[V.AIGU_HZ], x[V.AIGU_DB], 0.707); else bqNeutre(st.eqA);
  }

  /* ---------- la hauteur : YIN sur les dernières W + tauMax valeurs ramenées à srd ---------- */
  function yin(st) {
    st.W = st.sansVoix <= 4 && st.f0 > 0 ? Math.max(st.Wmin, Math.min(st.Wmax, Math.round(1.6 * st.srd / st.f0))) : st.Wmax;
    const W = st.W, tM = st.tauMax, d = st.yd, c = st.yc, b = st.lin, debut = st.nd - (W + tM);
    for (let j = 0; j < W + tM; j++) b[j] = st.dec[(debut + j) % DEC];
    let e = 0;
    for (let j = tM; j < W + tM; j++) e += b[j] * b[j];
    const fort = Math.sqrt(e / W) > 0.00316;                           // −50 dBFS
    c[0] = 1;
    let somme = 0;
    for (let tau = 1; tau <= tM; tau++) {
      let s = 0;
      for (let j = 0; j < W; j++) { const a = b[j] - b[j + tau]; s += a * a; }
      d[tau] = s; somme += s;
      c[tau] = somme > 0 ? s * tau / somme : 1;
    }
    let tau = -1;
    for (let t = st.tauMin; t <= tM; t++) if (c[t] < 0.2) { tau = t; while (tau + 1 <= tM && c[tau + 1] < c[tau]) tau++; break; }
    if (tau < 0) { tau = st.tauMin; for (let t = st.tauMin + 1; t <= tM; t++) if (c[t] < c[tau]) tau = t; }
    let r = tau;
    if (tau > 1 && tau < tM) {
      const a = c[tau - 1], m = c[tau], z = c[tau + 1], den = a - 2 * m + z;
      if (den > 1e-12) r = tau + Math.max(-0.5, Math.min(0.5, (a - z) / (2 * den)));
    }
    st.creux = c[tau];
    const f0 = st.srd / r, P = st.v;
    const creuxMax = P[V.AT] ? P[V.CREUX] : 0.15;
    const voise = fort && c[tau] <= creuxMax && f0 >= 65 && f0 <= 1000;
    if (voise) { st.sansVoix = 0; st.f0 = f0; }
    else st.sansVoix++;
    st.voise = st.sansVoix <= 2;                                       // un trou de 5 ms dans une note : la note continue
  }

  // la note la plus proche dans la gamme ; une note chantée nettement (à 25 cents d'un demi-ton) reste la sienne (autotune._note_proche)
  function noteProche(st, m) {
    const r = Math.round(m), g = st.v;
    if (COUPE === 'gamme') return r;
    if (g[V.GAMME + (((r % 12) + 12) % 12)] || (COUPE !== 'nette' && Math.abs(m - r) <= 0.25)) return r;
    const base = Math.floor(m);
    let meilleur = NaN;
    for (let n = base - 2; n < base + 4; n++) if (g[V.GAMME + (((n % 12) + 12) % 12)] && (Number.isNaN(meilleur) || Math.abs(n - m) < Math.abs(meilleur - m))) meilleur = n;
    return Number.isNaN(meilleur) ? r : meilleur;
  }

  // toutes les 5 ms : la correction (demi-tons) que le déplacement doit appliquer
  function noteSuivante(st) {
    const P = st.v, hopMs = st.hop / st.srd * 1000;
    if (!P[V.AT] || !st.voise) { st.c = 0; st.cL = 0; st.note = NaN; st.tVoise = 0; st.fG = 1; return; }
    const m = 69 + 12 * Math.log2(st.f0 / 440) - P[V.DIAP] / 100;
    if (st.tVoise === 0) { st.tr = m; st.trPrec = m; st.note = NaN; st.mPrec = m; }
    else st.tr += (1 - Math.exp(-hopMs / Math.max(1, P[V.TENDANCE]))) * (m - st.tr);
    // la hauteur mesurée est celle d'il y a ~la moitié de la fenêtre : pour aplatir le vibrato (le fort), prolongée de sa pente sur 10 ms
    // (au banc, vibrato de ±29 cents à 5,5 Hz : il en reste 19 sans, 14 avec ; 3 au mieux, la tendance garde 15 % du vibrato)
    const mP = COUPE === 'prediction' ? m : m + (10 / hopMs) * (m - st.mPrec);
    st.mPrec = m;
    st.tVoise += hopMs;
    const cand = noteProche(st, st.tr);
    if (Number.isNaN(st.note) || (cand !== st.note && Math.abs(st.tr - st.note) > Math.abs(cand - st.note) / 2 + 0.1)) {
      st.note = cand; st.sommeM = 0; st.nM = 0; st.tNote = 0;          // (la cible du fort continue d'une note à l'autre, comme au mix)
    }
    st.sommeM += m; st.nM++; st.tNote += hopMs;
    const aR = 1 - Math.exp(-hopMs / Math.max(1, P[V.RETUNE]));
    let c = 0;
    if (st.tVoise < P[V.TENUE] && COUPE !== 'tenue') { st.cible = st.tr; st.cL = 0; }
    else if (P[V.APLATIR] > 0) {                                       // FORT : vers la note à la vitesse de correction, vibrato aplati
      st.cible += aR * (st.note - st.cible);
      c = P[V.FORCE] * (st.cible - st.tr) + (COUPE === 'aplatir' ? 0 : P[V.APLATIR]) * (st.tr - mP);
    } else {                                                           // LÉGER : la moyenne de la note rapprochée, installée en retune_ms
      const cT = st.tNote >= P[V.NOTE_MIN] ? P[V.FORCE] * (st.note - st.sommeM / st.nM) : 0;
      st.cL += aR * (cT - st.cL);
      c = st.cL;
    }
    if (P[V.GLISSE] > 0 && COUPE !== 'glisse') {                                             // un glissé : la correction s'efface, le glissé reste le sien
      const pente = Math.abs(st.tr - st.trPrec) * 100 / (hopMs / 1000), g0 = P[V.GLISSE] / 2;
      st.fG += (1 - Math.exp(-hopMs / 45)) * (Math.max(0, Math.min(1, 1 - (pente - g0) / g0)) - st.fG);
      c *= st.fG;
    }
    st.trPrec = st.tr;
    const mx = P[V.MAX_CENTS] / 100;
    // sous 2 cents, rien (une voix juste reste intacte, au retard le plus court : pas de dérive du retard pour rien)
    st.c = Math.abs(c) < 0.02 && COUPE !== 'zone_morte' ? 0 : Math.max(-mx, Math.min(mx, c));
  }

  // à chaque début de période de sortie : la longueur de la suivante et son retard
  function segment(st) {
    st.dA = st.dB;
    const T = st.voise && st.f0 > 0 && st.v[V.AT] ? st.sr / st.f0 : 0;
    if (T > 0) {
      const Tp = COUPE === 'deplacement' ? T : T / Math.pow(2, st.c / 12);
      st.segLen = Tp;
      let nb = st.dA + Tp - T;                                         // m = 1
      if (nb < st.dMin) nb = st.dA + Tp;                               // m = 0 : une période répétée (vers l'aigu)
      else if (nb > st.dMin + T) { nb = st.dA + Tp - 2 * T; if (nb < st.dMin) nb = st.dA + Tp - T; }   // m = 2 : une période sautée
      st.dB = nb;
    } else {
      st.segLen = Math.max(1, Math.round(st.sr * 0.005));
      // dans le sourd (30 ms), ou l'autotune coupé, le retard revient au plus court, par le même fondu
      st.dB = (st.sansVoix >= 12 && COUPE !== 'retour_court') || !st.v[V.AT] ? st.dMin : st.dA;
    }
  }

  /* ---------- la chaîne, échantillon par échantillon ---------- */
  function traiter(st, entree, sortie, n) {
    const P = st.v, sr = st.sr;
    const at = P[V.AT] > 0, comp = P[V.COMP] > 0, dees = P[V.DEESSER], rev = P[V.REVERB], del = P[V.DELAI];
    const aAtt = 1 - Math.exp(-1 / (sr * Math.max(0.1, P[V.ATTAQUE]) / 1000)), aRel = 1 - Math.exp(-1 / (sr * Math.max(5, P[V.RELACHE]) / 1000));
    const dA1 = 1 - Math.exp(-1 / (sr * 0.001)), dR50 = 1 - Math.exp(-1 / (sr * 0.05));
    const vol = Math.pow(10, P[V.VOLUME] / 20), dlN = Math.max(1, Math.min(st.dl.length - 1, Math.round(P[V.DELAI_S] * sr)));
    const mes = st.mes;
    for (let i = 0; i < n; i++) {
      const brut = entree ? +entree[i] || 0 : 0;
      if (mes) { mesurer(st, mes, brut, sortie, i); continue; }
      let x = bq(st.ph, brut);
      // la détection, à ~16 kHz
      if (at) {
        const z = bq(st.aa2, bq(st.aa1, x));
        if (++st.dPhase >= st.D) {
          st.dPhase = 0;
          st.dec[st.nd % DEC] = z; st.nd++;
          if (st.nd >= st.W + st.tauMax && st.nd % st.hop === 0) { yin(st); noteSuivante(st); }
        }
      }
      // le déplacement : deux prises de retard, fondues sur la période de sortie
      st.hist[st.n % HIST] = x;
      if (st.segPos >= st.segLen) { st.segPos -= st.segLen; segment(st); }
      let y;
      if (st.dA === st.dB) y = st.hist[(st.n - Math.round(st.dA) + HIST) % HIST];
      else {
        const r = 0.5 - 0.5 * Math.cos(Math.PI * st.segPos / st.segLen);
        const ya = st.hist[(st.n - Math.round(st.dA) + HIST) % HIST], yb = st.hist[(st.n - Math.round(st.dB) + HIST) % HIST];
        y = ya + r * (yb - ya);
      }
      const lat = st.dA + (st.dB - st.dA) * Math.min(1, st.segPos / st.segLen);
      st.latSomme += lat; st.latN++; if (lat > st.latMax) st.latMax = lat;
      st.segPos += 1; st.n++;
      // l'égaliseur
      y = bq(st.eqA, bq(st.eqP, bq(st.eqM, bq(st.eqG, y))));
      // le compresseur (sans anticipation)
      if (comp) {
        const a = Math.abs(y);
        st.env += (a > st.env ? aAtt : aRel) * (a - st.env);
        const over = 20 * Math.log10(st.env + 1e-9) - P[V.SEUIL];
        let g = 0;
        if (over > 3) g = over * (1 - 1 / P[V.RATIO]);
        else if (over > -3) g = (1 - 1 / P[V.RATIO]) * (over + 3) * (over + 3) / 12;
        y *= Math.pow(10, (P[V.GAIN] - g) / 20);
      }
      // le dé-esseur : la bande des « s » (≈ 6,5 kHz) baissée quand elle monte près du niveau de la voix
      const bande = bq(st.bp, y);
      if (dees > 0) {
        st.eb += (Math.abs(bande) > st.eb ? dA1 : dR50) * (Math.abs(bande) - st.eb);
        st.ef += (Math.abs(y) > st.ef ? dA1 : dR50) * (Math.abs(y) - st.ef);
        if (st.ef > 0.00316) {
          const rel = 20 * Math.log10((st.eb + 1e-9) / (st.ef + 1e-9)) + 9;
          const gr = Math.max(0, Math.min(12 * dees, rel * 1.5 * dees));
          y -= (1 - Math.pow(10, -gr / 20)) * bande;
        }
      }
      // les envois : la réverb (Freeverb), le délai calé sur le tempo
      let mouille = 0;
      if (rev > 0) {
        const e = y * 0.06;
        let s = 0;
        for (const p of st.peignes) { const o = p.b[p.i]; p.f = o * 0.75 + p.f * 0.25; p.b[p.i] = e + p.f * 0.8; if (++p.i >= p.b.length) p.i = 0; s += o; }
        for (const p of st.passes) { const o = p.b[p.i]; const w = -s + o; p.b[p.i] = s + o * 0.5; if (++p.i >= p.b.length) p.i = 0; s = w; }
        mouille += s * rev;
      }
      if (del > 0) {
        const j = (st.dlI - dlN + st.dl.length) % st.dl.length, o = st.dl[j];
        st.dlLp += 0.45 * (o - st.dlLp);
        st.dl[st.dlI] = y + 0.35 * st.dlLp;
        if (++st.dlI >= st.dl.length) st.dlI = 0;
        mouille += o * del * 0.6;
      } else { st.dl[st.dlI] = 0; if (++st.dlI >= st.dl.length) st.dlI = 0; }
      const s = (y + mouille) * vol;
      sortie[i] = s > 1 ? 1 : s < -1 ? -1 : s;
    }
  }

  /** La latence de l'algorithme depuis la dernière lecture (ms) : moyenne et pire, puis remise à zéro. */
  function latence(st) {
    const r = { moyenne_ms: st.latN ? st.latSomme / st.latN / st.sr * 1000 : st.dMin / st.sr * 1000, max_ms: st.latMax / st.sr * 1000 };
    st.latSomme = 0; st.latN = 0; st.latMax = 0;
    return r;
  }
  const etat = (st) => ({ voise: st.voise, f0: st.voise ? st.f0 : 0, correction_cents: st.c * 100, note: Number.isNaN(st.note) ? null : st.note });

  /* ---------- la mesure : n clics joués PAR LA SORTIE DU RETOUR, l'entrée enregistrée (ni la voix ni les effets pendant ce temps) ----------
     x[0] est 0,5 s avant le premier clic : StudioCalage.analyserClics(x, sr, { debut: 0.5, pas, n }) rend le retard sortie → entrée,
     c'est-à-dire le retour lui-même (sans l'algorithme). Le clic : 1 500 Hz, montée en 0,25 ms, 30 ms. */
  function mesureDemarrer(st, n = 8, pas = 0.3, fort = 0.3) {
    const sr = st.sr, total = Math.round((0.5 + n * pas + 0.4) * sr);
    st.mes = { n, pas, fort, i: 0, total, x: new Float32Array(total), premier: Math.round(0.5 * sr), pasN: Math.round(pas * sr) };
  }
  function mesurer(st, m, brut, sortie, i) {
    m.x[m.i] = brut;
    const k = m.i - m.premier;
    let s = 0;
    if (k >= 0 && Math.floor(k / m.pasN) < m.n) {
      const t = (k % m.pasN) / st.sr;
      if (t < 0.03) s = m.fort * Math.sin(2 * Math.PI * 1500 * t) * Math.min(1, t / 0.00025) * Math.exp(-t / 0.008);
    }
    sortie[i] = s;
    if (++m.i >= m.total) { st.mesFinie = { x: m.x, sr: st.sr, debut: 0.5, pas: m.pas, n: m.n }; st.mes = null; }
  }
  const mesureResultat = (st) => { const r = st.mesFinie || null; st.mesFinie = null; return r; };

  const RetourDSP = { NIVEAUX, PRESETS, DEFAUT, NOTES_DELAI, V, gamme, borner, preset, niveauMix, vecteur, creer, regler, traiter, latence, etat,
    mesureDemarrer, mesureResultat, _bq: { biquad, bqRegler, bq } };
  racine.RetourDSP = RetourDSP;
  if (typeof module !== 'undefined' && module.exports) module.exports = RetourDSP;
})(typeof window !== 'undefined' ? window : globalThis);

/* (14/11, Ahmed : « un retour de voix au casque … avec de l'autotune comme je veux ») LE BANC du retour casque (public/studio-retour-dsp.js) :
   des voix de SYNTHÈSE à vérité connue (une source glottale riche, trois formants d'un « a », vibrato, glissés, syllables de rap avec
   leurs souffles), passées dans la chaîne ; la hauteur de sortie jugée par un AUTRE détecteur que celui de la chaîne (la somme des
   harmoniques sur une grille d'un demi-cent, pas YIN).
   Les mêmes voix et la même chaîne sont refaites en C dans l'appli Android (retour_dsp.c) : ce fichier écrit les VECTEURS partagés
   (retour-vecteurs.txt : chaque cas, son vecteur de réglages, et des points de contrôle de l'entrée et de la sortie) que le test C relit.
   node mesure/retour-casque-banc.js            → le tableau du banc
   node mesure/retour-casque-banc.js --vecteurs → réécrit mesure/retour-vecteurs.txt */
const R = require('../public/studio-retour-dsp.js');
const SR = 48000;

/* ---------- la voix de synthèse (refaite à l'identique en C : retour_test.c, synth) ---------- */
// un segment : { d (s), f0 (Hz au début), f1 (Hz à la fin), vib_hz, vib_cents, voise (0/1), amp }
function synth(segments, sr = SR, graine = 12345) {
  const n = segments.reduce((a, s) => a + Math.round(s.d * sr), 0), x = new Float64Array(n);
  const B = R._bq, F = [[700, 6, 1], [1200, 8, 0.5], [2600, 10, 0.25]].map(([hz, q, g]) => { const f = B.biquad(); B.bqRegler(f, 'bande', sr, hz, 0, q); return { f, g }; });
  const bruit = B.biquad(); B.bqRegler(bruit, 'ph', sr, 3000, 0, 0.707);
  let ph = 0, i = 0, g = graine >>> 0;
  const alea = () => { g = (Math.imul(g, 1103515245) + 12345) >>> 0; return (g / 4294967296) * 2 - 1; };
  for (const s of segments) {
    const m = Math.round(s.d * sr), bord = Math.round(0.01 * sr);
    for (let k = 0; k < m; k++, i++) {
      const t = k / sr, env = Math.min(1, k / bord, (m - 1 - k) / bord) * (s.amp || 0.1);
      let v = 0;
      if (s.voise) {
        const f = s.f0 * Math.pow(s.f1 / s.f0, k / m) * Math.pow(2, (s.vib_cents || 0) * Math.sin(2 * Math.PI * (s.vib_hz || 0) * t) / 1200);
        ph += 2 * Math.PI * f / sr;
        if (ph > 2 * Math.PI * 1e4) ph -= 2 * Math.PI * 1e4;
        const H = Math.floor(4000 / f);
        let src = 0;
        for (let h = 1; h <= H; h++) src += Math.sin(h * ph) / Math.pow(h, 1.2);
        for (const o of F) v += o.g * B.bq(o.f, src);
        v *= 1.6;
      } else if (s.voise === 0 && s.amp) v = B.bq(bruit, alea()) * 0.8;
      x[i] = v * env;
    }
  }
  return x;
}
const hz = (midi) => 440 * Math.pow(2, (midi - 69) / 12);
const cents = (f) => 1200 * Math.log2(f / 440) + 6900;

/* ---------- le juge : la somme des harmoniques (5), fenêtre de Hann de 2048, grille d'un demi-cent autour d'une estimation ---------- */
function hauteurJuge(x, centre, guess, sr = SR, N = 2048) {
  const a = Math.max(0, Math.round(centre - N / 2));
  if (a + N > x.length) return NaN;
  const w = new Float64Array(N);
  for (let i = 0; i < N; i++) w[i] = x[a + i] * (0.5 - 0.5 * Math.cos(2 * Math.PI * i / (N - 1)));
  // le module de la transformée à une fréquence (Goertzel : sans trigonométrie par échantillon)
  const S = (f) => { let s = 0; for (let h = 1; h <= 5; h++) { const k = 2 * Math.cos(2 * Math.PI * h * f / sr); let a1 = 0, a2 = 0; for (let i = 0; i < N; i++) { const a0 = w[i] + k * a1 - a2; a2 = a1; a1 = a0; } s += Math.sqrt(Math.max(0, a1 * a1 + a2 * a2 - k * a1 * a2)); } return s; };
  let best = guess, bs = -1;
  for (let c = -150; c <= 150; c += 6) { const f = guess * Math.pow(2, c / 1200), v = S(f); if (v > bs) { bs = v; best = f; } }
  let pas = 3;
  while (pas >= 0.5) { for (const c of [-pas, pas]) { const f = best * Math.pow(2, c / 1200), v = S(f); if (v > bs) { bs = v; best = f; } } pas /= 2; }
  return best;
}

/* ---------- passer une voix dans la chaîne, par blocs de 128 comme l'AudioWorklet ---------- */
function passer(x, reglages, o = {}, sr = SR) {
  const st = R.creer(sr), y = new Float64Array(x.length);
  R.regler(st, Array.isArray(reglages) ? reglages : R.vecteur(reglages, o));
  const lat = [];
  for (let p = 0; p < x.length; p += 128) {
    const n = Math.min(128, x.length - p);
    R.traiter(st, x.subarray(p, p + n), y.subarray(p, p + n), n);
    if ((p / 128) % 8 === 0) lat.push(st.dA);
  }
  return { y, st, lat };
}
// la chaîne réduite à l'autotune (sans égaliseur, compression ni envois) : pour juger la hauteur et l'intégrité
const seulAutotune = (niveau, tonalite = 'C major') => ({ ...R.preset('sans_effet'), autotune: { niveau, tonalite, vitesse_ms: null, force: null } });

/* ---------- les cas (la vérité : l'entrée et la note visée) ---------- */
const NOTE = (midi, d, o = {}) => ({ d, f0: hz(midi), f1: hz(midi + (o.glisse || 0)), vib_hz: o.vib_hz || 0, vib_cents: o.vib_cents || 0, voise: 1, amp: o.amp || 0.1 });
const SOUFFLE = (d, amp = 0.03) => ({ d, voise: 0, amp });
const SILENCE = (d) => ({ d, voise: 0, amp: 0 });
const CAS = {
  // des notes tenues chantées fausses (do majeur) : +35 cents au-dessus de mi3, −45 sous sol3, +30 au-dessus de do#3 (hors gamme :
  // ré3 visé), une note chantée à 25 cents d'un fa# (hors gamme, nette : la sienne)
  fausses: [SILENCE(0.1), NOTE(52.35, 1.2), SILENCE(0.15), NOTE(55 - 0.45, 1.2), SILENCE(0.15), NOTE(49.3, 1.2), SILENCE(0.15), NOTE(54.2, 1.2), SILENCE(0.1)],
  // des notes justes : droite, puis avec un vibrato naturel (5,5 Hz, ±25 cents)
  justes: [SILENCE(0.1), NOTE(48, 1.0), SILENCE(0.15), NOTE(52, 1.2, { vib_hz: 5.5, vib_cents: 25 }), SILENCE(0.1)],
  // une note fausse de 40 cents avec vibrato (le fort doit l'aplatir)
  vibrato: [SILENCE(0.1), NOTE(55.4, 1.5, { vib_hz: 5.5, vib_cents: 30 }), SILENCE(0.1)],
  // un glissé (portamento) de 3 demi-tons en 300 ms entre deux notes justes
  glisse: [SILENCE(0.1), NOTE(48, 0.4), NOTE(48, 0.3, { glisse: 3 }), NOTE(51, 0.4), SILENCE(0.1)],
  // du RAP : des syllabes voisées de 60 à 150 ms à l'intonation de la parole (des descentes de 1 à 4 demi-tons), des souffles (« s »,
  // « ch ») et des silences ; 128 à 200 Hz (voix d'homme)
  rap: (() => {
    const l = [SILENCE(0.1)];
    const syl = [[0.09, 52, -2], [0.06, 50.5, -1], [0.12, 53.2, -3.5], [0.08, 51, -1.5], [0.15, 54.4, -4], [0.07, 49.8, 1], [0.11, 52.6, -2.5],
      [0.09, 50.2, -1], [0.13, 53.7, -3], [0.06, 51.4, -0.5], [0.1, 52.1, -2.2], [0.14, 50.9, -3.1]];
    syl.forEach(([d, m, g], k) => { l.push({ d, f0: hz(m), f1: hz(m + g), vib_hz: 0, vib_cents: 0, voise: 1, amp: 0.1 }); l.push(k % 3 === 1 ? SOUFFLE(0.07) : SILENCE(0.05)); });
    l.push(SILENCE(0.1));
    return l;
  })(),
};

// la hauteur d'entrée et de sortie trame par trame (10 ms) sur les parties voisées (la vérité dit où), en cents
function pistes(cas, x, y, decalage, pas = 480) {
  const segs = CAS[cas], out = [];
  let t0 = 0;
  for (const s of segs) {
    const m = Math.round(s.d * SR);
    if (s.voise) for (let k = Math.round(0.03 * SR); k < m - Math.round(0.03 * SR); k += pas) {
      const ci = t0 + k, f = s.f0 * Math.pow(s.f1 / s.f0, k / m) * Math.pow(2, (s.vib_cents || 0) * Math.sin(2 * Math.PI * (s.vib_hz || 0) * k / SR) / 1200);
      const fi = hauteurJuge(x, ci, f), fo = hauteurJuge(y, ci + decalage, f);
      out.push({ t: (ci / SR), dans: k / SR, d: s.d, vrai: cents(f), entree: cents(fi), sortie: cents(fo), seg: s });
    }
    t0 += m;
  }
  return out;
}
const med = (v) => { const s = v.filter(Number.isFinite).slice().sort((a, b) => a - b); return s.length ? (s.length % 2 ? s[s.length >> 1] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : NaN; };
const quantile = (v, q) => { const s = v.filter(Number.isFinite).slice().sort((a, b) => a - b); return s.length ? s[Math.min(s.length - 1, Math.floor(q * s.length))] : NaN; };
// la note visée par l'autotune du mix pour une hauteur moyenne (do majeur, la gamme ne départage que les ambiguës)
const GAMME_DO = [0, 2, 4, 5, 7, 9, 11];
function visee(m, classes = GAMME_DO) {
  const r = Math.round(m);
  if (classes.includes(((r % 12) + 12) % 12) || Math.abs(m - r) <= 0.25) return r;
  let b = null;
  for (let n = Math.floor(m) - 2; n < Math.floor(m) + 4; n++) if (classes.includes(((n % 12) + 12) % 12) && (b === null || Math.abs(n - m) < Math.abs(b - m))) b = n;
  return b;
}
// le rapport signal / différence (dB) entre la sortie et l'entrée retardée du retard minimal (la voix intacte ?)
function intacte(x, y, dMin, de = 0, a = x.length) {
  let s = 0, e = 0;
  for (let i = Math.max(de, dMin); i < a; i++) { const r = x[i - dMin]; s += r * r; e += (y[i] - r) * (y[i] - r); }
  return 10 * Math.log10(s / Math.max(1e-20, e));
}

/** Le banc : chaque cas, chaque niveau ; les chiffres que juge le test (test-retour-casque.js). */
function banc() {
  const r = {};
  const dMin = Math.round(0.0005 * SR);
  for (const niveau of ['leger', 'fort']) {
    const x = synth(CAS.fausses), { y } = passer(x, seulAutotune(niveau));
    const p = pistes('fausses', x, y, 0);
    const notes = [];
    let t0 = 0;
    for (const s of CAS.fausses) {
      if (s.voise) {
        const ici = p.filter(q => q.seg === s && q.dans >= 0.45);           // la note installée (après tenue + vitesse)
        const vrai = cents(s.f0) / 100, cible = visee(vrai);
        notes.push({ chantee_cents: Math.round((vrai - Math.round(vrai)) * 100), visee: cible, ecart_entree: (vrai - cible) * 100,
          ecart_sortie: med(ici.map(q => q.sortie - cible * 100)), p90: quantile(ici.map(q => Math.abs(q.sortie - cible * 100)), 0.9) });
      }
      t0 += s.d;
    }
    r[`fausses_${niveau}`] = notes;
    const xj = synth(CAS.justes), oj = passer(xj, seulAutotune(niveau));
    const pj = pistes('justes', xj, oj.y, 0);
    const finDroite = Math.round((CAS.justes[0].d + CAS.justes[1].d) * SR);
    r[`justes_${niveau}`] = { droite: med(pj.filter(q => !q.seg.vib_cents).map(q => Math.abs(q.sortie - q.entree))),
      vibrato: med(pj.filter(q => q.seg.vib_cents).map(q => Math.abs(q.sortie - q.entree))),
      droite_intacte_db: intacte(xj, oj.y, dMin, 0, finDroite), intacte_db: intacte(xj, oj.y, dMin) };
    const xv = synth(CAS.vibrato), ov = passer(xv, seulAutotune(niveau)), pv = pistes('vibrato', xv, ov.y, 0).filter(q => q.dans >= 0.45);
    const amp = (k) => { const v = pv.map(q => q[k]); return (quantile(v, 0.95) - quantile(v, 0.05)) / 2; };
    r[`vibrato_${niveau}`] = { entree_cents: amp('entree'), sortie_cents: amp('sortie'), centre_sortie: med(pv.map(q => q.sortie)) - visee(cents(hz(55.4)) / 100) * 100 };
    const xg = synth(CAS.glisse), og = passer(xg, seulAutotune(niveau)), pg = pistes('glisse', xg, og.y, 0).filter(q => q.seg.f1 !== q.seg.f0);
    r[`glisse_${niveau}`] = { mediane: med(pg.map(q => Math.abs(q.sortie - q.entree))), p90: quantile(pg.map(q => Math.abs(q.sortie - q.entree)), 0.9) };
    const xr = synth(CAS.rap), or_ = passer(xr, seulAutotune(niveau)), pr = pistes('rap', xr, or_.y, 0);
    const d = pr.map(q => Math.abs(q.sortie - q.entree));
    r[`rap_${niveau}`] = { mediane: med(d), p95: quantile(d, 0.95), part_20c: d.filter(v => v > 20).length / Math.max(1, d.length), trames: d.length,
      intacte_db: intacte(xr, or_.y, dMin) };
    // la latence de l'algorithme : sur les notes corrigées, et après (dans le sourd elle revient au plus court)
    const o2 = passer(synth([SILENCE(0.1), NOTE(52.35, 1.0), SILENCE(0.2), NOTE(48, 0.6), SILENCE(0.05)]), seulAutotune(niveau));
    const ms = o2.lat.map(v => v / SR * 1000), parBloc = 128 * 8 / SR;
    const pendant = ms.filter((_, k) => k * parBloc > 0.35 && k * parBloc < 1.05), apres = ms.filter((_, k) => k * parBloc > 1.35 && k * parBloc < 1.85);
    r[`latence_${niveau}`] = { min_ms: dMin / SR * 1000, note_corrigee_moy_ms: pendant.reduce((a, b) => a + b, 0) / pendant.length,
      note_corrigee_max_ms: Math.max(...pendant), note_juste_apres_ms: Math.max(...apres) };
  }
  // sans autotune (Rap propre) : la hauteur ne bouge pas, rien n'attend
  const xr = synth(CAS.rap), o = passer(xr, R.preset('rap_propre'));
  const pr = pistes('rap', xr, o.y, 0).map(q => Math.abs(q.sortie - q.entree));
  r.rap_propre = { mediane: med(pr), p95: quantile(pr, 0.95), retard_max_ms: Math.max(...o.lat) / SR * 1000 };
  return r;
}

/* ---------- les vecteurs partagés avec Android : l'ENTRÉE même (PCM 16 bits, retour-vecteurs.pcm : exacte des deux côtés — refaire la voix
   en C donnerait des écarts de 1e-14, et la phase des périodes du PSOLA les amplifie), le vecteur de réglages, et des points de contrôle
   de la sortie (un échantillon sur 37) que le test C (hakim-android, retour_test.c) doit retrouver à 1e-9 près ---------- */
const COURT = {
  fausse: [SILENCE(0.05), NOTE(52.35, 0.6), SILENCE(0.05)],
  vibrato: [SILENCE(0.05), NOTE(55.4, 0.65, { vib_hz: 5.5, vib_cents: 30 }), SILENCE(0.05)],
  juste: [SILENCE(0.05), NOTE(52, 0.6, { vib_hz: 5.5, vib_cents: 25 }), SILENCE(0.05)],
  rap: CAS.rap.slice(0, 13),
};
const VECTEURS = [
  ['fausse_fort', 'fausse', seulAutotune('fort')], ['fausse_leger', 'fausse', seulAutotune('leger')], ['vibrato_fort', 'vibrato', seulAutotune('fort')],
  ['juste_leger', 'juste', seulAutotune('leger')], ['rap_leger', 'rap', seulAutotune('leger')], ['rap_propre', 'rap', R.preset('rap_propre')],
  ['effet_complet', 'vibrato', { ...R.preset('autotune_effet'), autotune: { niveau: 'fort', tonalite: 'C major', vitesse_ms: null, force: null } }],
];
const pcm16 = (x) => Int16Array.from(x, v => Math.max(-32768, Math.min(32767, Math.round(v * 32768))));
function vecteurs() {
  const l = ['# Les vecteurs du retour casque (cockpit mesure/retour-casque-banc.js --vecteurs). Chaque cas : son entrée dans retour-vecteurs.pcm',
    '# (PCM 16 bits little-endian, à partir de l\'échantillon « debut »), le vecteur de réglages (RetourDSP.vecteur, 44 nombres), et des points',
    '# de contrôle de la sortie (un échantillon sur 37). Le test C (hakim-android, retour_test.c) passe la même entrée dans sa chaîne.'];
  const tout = [];
  let debut = 0;
  for (const [nom, cas, reg] of VECTEURS) {
    const q = pcm16(synth(COURT[cas])), x = Float64Array.from(q, v => v / 32768), v = R.vecteur(reg, { tempo: 140 }), { y } = passer(x, v);
    l.push(`cas ${nom} ${SR} ${debut} ${q.length}`);
    l.push(`v ${v.map(a => String(a)).join(' ')}`);
    const pts = [];
    for (let i = 0; i < x.length; i += 37) pts.push(`${i}:${y[i].toPrecision(15)}`);
    l.push(`pts ${pts.length} ${pts.join(' ')}`);
    l.push('fin');
    tout.push(q); debut += q.length;
  }
  const pcm = new Int16Array(debut);
  let k = 0;
  for (const q of tout) { pcm.set(q, k); k += q.length; }
  return { texte: l.join('\n') + '\n', pcm: Buffer.from(pcm.buffer, pcm.byteOffset, pcm.byteLength) };
}

module.exports = { SR, synth, hz, cents, hauteurJuge, passer, seulAutotune, CAS, pistes, med, quantile, visee, intacte, banc, vecteurs, VECTEURS };

if (require.main === module) {
  if (process.argv.includes('--vecteurs')) {
    const v = vecteurs(), fs = require('fs'), path = require('path');
    fs.writeFileSync(path.join(__dirname, 'retour-vecteurs.txt'), v.texte); fs.writeFileSync(path.join(__dirname, 'retour-vecteurs.pcm'), v.pcm);
    console.log(`retour-vecteurs.txt et .pcm écrits (${v.pcm.length} octets)`);
  } else {
    const t = Date.now(), r = banc();
    console.log(JSON.stringify(r, (k, v) => (typeof v === 'number' ? Math.round(v * 100) / 100 : v), 1));
    console.log(`(${((Date.now() - t) / 1000).toFixed(1)} s)`);
  }
}

/* (11/11, ~03:00, Ahmed : « je veux tout » : chaque syllabe sur le temps, et sur la note) SA VOIX CHANTÉE, le traitement du son (le cockpit
   seulement ; les calculs du plan restent dans public/chanter.js). Une ligne du refrain arrive avec ses syllabes placées sur la grille
   (Chanter.scander : chacune à son instant, sa place, et la note que la voix du morceau tenait là) ; sa voix Azure, rendue avec un blanc
   entre chaque mot (SSML <break>), devient la ligne chantée :
   1. LES MOTS : la voix est coupée aux n − 1 plus longs blancs (ceux qu'Azure a mis entre les mots : l'API REST ne donne pas les limites de
      mots, le blanc les donne à coup sûr) ;
   2. LES SYLLABES : chaque mot coupé en ses k syllabes aux creux les plus profonds de son enveloppe (les voyelles sont les bosses) ;
   3. LA HAUTEUR : sa hauteur trame par trame (YIN, 5 ms), ses marques de période ;
   4. CHAQUE SYLLABE (TD-PSOLA : des grains de deux périodes, recollés) : sa voyelle étirée ou serrée pour tenir sa place (0,7 à 1,8 fois, les
      consonnes gardent leur durée), sa hauteur posée sur la note du morceau (sa propre intonation gardée à 15 %), l'octave choisie une fois
      pour la phrase (la plus proche de sa voix) ;
   5. LE RECOLLAGE : l'attaque de chaque syllabe posée sur son instant, fondus de 6 ms, rien ne déborde sur la suivante.
   Pourquoi TD-PSOLA en JavaScript : rien à installer (ni librosa, ni rubberband sur ce Mac), pas de processus à lancer (Python + librosa :
   1 à 3 s de démarrage), quelques dizaines de ms par ligne (mesuré au banc), et la meilleure qualité pour une voix seule et propre à moins
   d'une quinte : les formants restent (pas de voix de canard, contrairement au ré-échantillonnage), et pas le flou de phase du vocodeur de
   librosa. Le SSML prosody pitch d'Azure ne vise pas une note : il décale l'intonation d'Azure, mot par mot au mieux.
   node --test test-chanter.js ; le banc : node mesure/chanter-banc.js */
'use strict';

const DEFAUTS = {
  pause_ms: 260,            // le blanc demandé à Azure entre deux mots
  silence_min_ms: 70,       // un blanc entre deux mots, au moins
  seuil_silence: 0.05,      // sous 5 % du plus fort de l'enveloppe : du silence
  fondu_ms: 6,
  marge_ms: 40,             // le zéro de la ligne dans le son rendu (la place du fondu et de la consonne avant la première attaque)
  etirer_min: 0.7, etirer_max: 1.8,
  force: 0.85,              // la hauteur posée sur la note (1 : plate, 0 : son intonation telle quelle)
  f0_min: 60, f0_max: 500, yin_seuil: 0.15,
  attaque_seuil: 0.3,       // l'attaque d'une syllabe : son enveloppe à 30 % de son plus fort (le début de sa voyelle)
  decalage_max_st: 7,       // au-delà d'une quinte, la note est prise à l'octave d'à côté (la même note)
  queue_ms: 300,            // la dernière syllabe tient au plus 300 ms au-delà de sa place
};
const fini = (x) => typeof x === 'number' && Number.isFinite(x);
const mediane = (v) => { const s = Array.from(v).filter(fini).sort((a, b) => a - b); if (!s.length) return NaN; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const borne = (x, a, b) => Math.max(a, Math.min(b, x));
const cents = (a, b) => 1200 * Math.log2(a / b);

// ---- le son : PCM 16 bits mono (Azure : riff-24khz-16bit-mono-pcm) ↔ flottants
function lirePcm(buf) {
  if (!Buffer.isBuffer(buf) || buf.length < 44 || buf.toString('ascii', 0, 4) !== 'RIFF' || buf.toString('ascii', 8, 12) !== 'WAVE') return null;
  let i = 12, fmt = null;
  while (i + 8 <= buf.length) {
    const id = buf.toString('ascii', i, i + 4), taille = buf.readUInt32LE(i + 4), corps = i + 8;
    if (id === 'fmt ' && taille >= 16) fmt = { format: buf.readUInt16LE(corps), canaux: buf.readUInt16LE(corps + 2), sr: buf.readUInt32LE(corps + 4), bits: buf.readUInt16LE(corps + 14) };
    if (id === 'data') {
      if (!fmt || fmt.format !== 1 || fmt.bits !== 16 || fmt.canaux !== 1) return null;
      const fin = Math.min(buf.length, taille > 0 ? corps + taille : buf.length), n = Math.floor((fin - corps) / 2), x = new Float32Array(n);
      for (let k = 0; k < n; k++) x[k] = buf.readInt16LE(corps + 2 * k) / 32768;
      return { x, sr: fmt.sr };
    }
    i = corps + taille + (taille % 2);
  }
  return null;
}
function ecrirePcm(x, sr) {
  const n = x.length, b = Buffer.alloc(44 + 2 * n);
  b.write('RIFF', 0, 'ascii'); b.writeUInt32LE(36 + 2 * n, 4); b.write('WAVE', 8, 'ascii'); b.write('fmt ', 12, 'ascii');
  b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22); b.writeUInt32LE(sr, 24); b.writeUInt32LE(sr * 2, 28);
  b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36, 'ascii'); b.writeUInt32LE(2 * n, 40);
  for (let k = 0; k < n; k++) b.writeInt16LE(Math.round(borne(x[k], -1, 32767 / 32768) * 32768), 44 + 2 * k);
  return b;
}

// ---- l'enveloppe : la force (RMS) sur fen_ms, toutes les pas_ms
function enveloppe(x, sr, pasMs = 5, fenMs = 10, a = 0, b = x.length) {
  const pas = Math.max(1, Math.round(sr * pasMs / 1000)), w = Math.max(1, Math.round(sr * fenMs / 1000)), out = [];
  for (let i = a; i < b; i += pas) {
    let s = 0, n = 0;
    for (let j = Math.max(a, i - (w >> 1)); j < Math.min(b, i + (w >> 1) + 1); j++) { s += x[j] * x[j]; n++; }
    out.push(Math.sqrt(s / Math.max(1, n)));
  }
  return { e: out, pas };
}

/* ---- 1. les mots : n morceaux, coupés aux n − 1 plus longs blancs. Rend [[a, b] (échantillons)] ; null : pas assez de blancs (Azure ne les
   a pas mis, ou un mot a été lu en deux) — la ligne est alors chantée d'un bloc (le plan d'avant) */
function decouperMots(x, sr, n, o = {}) {
  const r = { ...DEFAUTS, ...o };
  const { e, pas } = enveloppe(x, sr, 5, 10);
  let m = 0; for (const v of e) if (v > m) m = v;
  if (!(m > 0) || !(n >= 1)) return null;
  const seuil = m * r.seuil_silence;
  let debut = e.findIndex(v => v >= seuil), fin = e.length - 1;
  while (fin > 0 && e[fin] < seuil) fin--;
  if (debut < 0 || fin <= debut) return null;
  const blancs = [];
  let i0 = -1;
  for (let i = debut; i <= fin; i++) {
    if (e[i] < seuil) { if (i0 < 0) i0 = i; }
    else if (i0 >= 0) { if ((i - i0) * 5 >= r.silence_min_ms) blancs.push([i0, i]); i0 = -1; }
  }
  if (blancs.length < n - 1) return null;
  const choisis = blancs.slice().sort((p, q) => (q[1] - q[0]) - (p[1] - p[0])).slice(0, n - 1).sort((p, q) => p[0] - q[0]);
  const bords = [debut, ...choisis.flatMap(([a, b]) => [a, b]), fin + 1];
  const out = [];
  for (let k = 0; k < n; k++) out.push([Math.max(0, bords[2 * k] * pas - pas), Math.min(x.length, bords[2 * k + 1] * pas + pas)]);
  return out;
}

/* ---- 2. les syllabes d'un mot : k morceaux, coupés aux creux les plus profonds de l'enveloppe lissée (30 ms au moins chacun) ;
   sans assez de creux : à parts égales pour ce qui manque */
function decouperSyllabes(x, sr, a, b, k) {
  if (!(k > 1) || b - a < sr * 0.06 * k) return k > 1 ? partsEgales(a, b, k) : [[a, b]];
  const { e, pas } = enveloppe(x, sr, 5, 25, a, b);
  const min = Math.round(30 / 5);
  const creux = [];
  for (let i = min; i < e.length - min; i++) {
    if (!(e[i] <= e[i - 1] && e[i] <= e[i + 1])) continue;
    let g = 0, d = 0;
    for (let j = 0; j < i; j++) g = Math.max(g, e[j]);
    for (let j = i + 1; j < e.length; j++) d = Math.max(d, e[j]);
    const prof = Math.min(g, d) - e[i];
    if (prof > 0) creux.push({ i, prof });
  }
  creux.sort((p, q) => q.prof - p.prof);
  const coupes = [];
  for (const c of creux) {
    if (coupes.length >= k - 1) break;
    if (coupes.every(i => Math.abs(i - c.i) >= min)) coupes.push(c.i);
  }
  if (coupes.length < k - 1) return partsEgales(a, b, k);
  coupes.sort((p, q) => p - q);
  const bords = [a, ...coupes.map(i => a + i * pas), b];
  return bords.slice(0, -1).map((v, i) => [v, bords[i + 1]]);
}
function partsEgales(a, b, k) { const out = []; for (let i = 0; i < k; i++) out.push([Math.round(a + (b - a) * i / k), Math.round(a + (b - a) * (i + 1) / k)]); return out; }

/* ---- 3. la hauteur, trame par trame : YIN (la différence cumulée normalisée), sur le son ramené vers 12 kHz ; 0 : pas de hauteur nette.
   Rend { f0: Float32Array (une valeur toutes les pas échantillons du son d'origine), pas } */
function hauteurs(x, sr, o = {}) {
  const r = { ...DEFAUTS, ...o };
  // ramené vers 8 kHz (la moyenne de q échantillons : assez pour une voix, jusqu'à 500 Hz), une trame toutes les 10 ms
  const q = Math.max(1, Math.round(sr / 8000)), s2 = sr / q, n2 = Math.floor(x.length / q), y = new Float32Array(n2);
  for (let i = 0; i < n2; i++) { let s = 0; for (let j = 0; j < q; j++) s += x[i * q + j]; y[i] = s / q; }
  const pas2 = Math.round(s2 * (r.pas_f0_ms || 10) / 1000), W = Math.round(s2 * 0.02), tmin = Math.floor(s2 / r.f0_max), tmax = Math.ceil(s2 / r.f0_min);
  const nb = Math.ceil(n2 / pas2), f0 = new Float32Array(nb), d = new Float32Array(tmax + 2);
  let emax = 0; for (let i = 0; i < n2; i++) emax = Math.max(emax, Math.abs(y[i]));
  for (let k = 0; k < nb; k++) {
    const c = k * pas2 - (W >> 1);
    if (c < 0 || c + W + tmax >= n2) continue;
    let e = 0; for (let j = 0; j < W; j++) e += y[c + j] * y[c + j];
    if (Math.sqrt(e / W) < 0.02 * emax) continue;
    // la différence cumulée normalisée, calculée jusqu'au premier creux sous le seuil (et sa remontée) : la suite n'est pas lue
    let cum = 0, tau = -1, sous = false;
    d[0] = 1;
    for (let t = 1; t <= tmax; t++) {
      let s = 0; for (let j = 0; j < W; j++) { const v = y[c + j] - y[c + j + t]; s += v * v; }
      cum += s; d[t] = cum > 0 ? s * t / cum : 1;
      if (t >= tmin && d[t] < r.yin_seuil) sous = true;
      if (sous && t > tmin && d[t] > d[t - 1]) { tau = t - 1; d[t + 1] = d[t]; break; }
    }
    // rien sous le seuil : le plus profond, s'il reste net (le repli de YIN)
    if (tau < 0) { let m = tmin; for (let t = tmin + 1; t <= tmax; t++) if (d[t] < d[m]) m = t; if (d[m] < 0.3) tau = m; }
    if (tau < 0) continue;
    const a = d[tau - 1], b = d[tau], cc = d[tau + 1], den = a - 2 * b + cc;
    const tf = den > 0 && tau > 1 && tau < tmax ? tau + 0.5 * (a - cc) / den : tau;
    f0[k] = s2 / tf;
  }
  // un trou bref (60 ms au plus) dans une voyelle, entre deux hauteurs proches (à 2 demi-tons) : comblé
  for (let k = 1; k < nb - 1; k++) {
    if (f0[k] > 0 || !(f0[k - 1] > 0)) continue;
    let j = k; while (j < nb && !(f0[j] > 0) && (j - k) * pas2 / s2 <= 0.06) j++;
    if (j < nb && f0[j] > 0 && (j - k) * pas2 / s2 <= 0.06 && Math.abs(cents(f0[j], f0[k - 1])) < 200)
      for (let i = k; i < j; i++) f0[i] = f0[k - 1] * Math.pow(f0[j] / f0[k - 1], (i - k + 1) / (j - k + 1));
    k = j;
  }
  // les trames isolées (une seule de suite) : jetées ; les sauts d'octave d'une trame : ramenés sur leurs voisines
  for (let k = 1; k < nb - 1; k++) {
    if (f0[k] > 0 && !(f0[k - 1] > 0) && !(f0[k + 1] > 0)) f0[k] = 0;
    else if (f0[k] > 0 && f0[k - 1] > 0 && f0[k + 1] > 0) {
      const v = Math.sqrt(f0[k - 1] * f0[k + 1]), c = cents(f0[k], v);
      if (Math.abs(Math.abs(c) - 1200) < 150) f0[k] = c > 0 ? f0[k] / 2 : f0[k] * 2;
    }
  }
  // (mesuré au banc : 2 syllabes sur 570 chantées une octave trop bas, sa hauteur lue au double) une voix parlée tient moins d'une octave autour
  // de sa médiane : une trame à plus de 0,8 octave d'elle est prise à l'octave d'à côté
  const v = []; for (const x of f0) if (x > 0) v.push(x);
  if (v.length >= 5) { const m = mediane(v); for (let k = 0; k < nb; k++) if (f0[k] > 0) { if (f0[k] > 1.75 * m) f0[k] /= 2; else if (f0[k] < m / 1.75) f0[k] *= 2; } }
  return { f0, pas: pas2 * q };
}
const f0A = (H, i) => { const k = Math.round(i / H.pas); return k >= 0 && k < H.f0.length ? H.f0[k] : 0; };

/* les marques de période (le haut de chaque période, sur le son adouci) ; sans hauteur : une marque toutes les 8 ms. [{ i, T, voisee }] */
function marques(x, sr, H) {
  const lp = new Float32Array(x.length);
  let v = 0; const al = 1 - Math.exp(-2 * Math.PI * 900 / sr);
  for (let i = 0; i < x.length; i++) { v += al * (x[i] - v); lp[i] = v; }
  const out = [], sourd = Math.round(sr * 0.008);
  let i = 0, prev = null;
  while (i < x.length) {
    const f = f0A(H, i);
    if (f > 0) {
      const T = sr / f;
      let a, b;
      if (prev && prev.voisee) { a = Math.round(prev.i + 0.8 * T); b = Math.round(prev.i + 1.2 * T); }
      else { a = i; b = Math.round(i + T); }
      let m = a, mv = -Infinity;
      for (let j = Math.max(0, a); j < Math.min(x.length, b); j++) if (lp[j] > mv) { mv = lp[j]; m = j; }
      if (prev && m <= prev.i) m = prev.i + Math.max(1, Math.round(T));
      if (m >= x.length) break;
      prev = { i: m, T: Math.round(T), voisee: true }; out.push(prev);
      i = m + Math.round(0.5 * T);
      continue;
    }
    const m = prev ? Math.max(i, prev.i + (prev.voisee ? prev.T : sourd)) : i;
    if (m >= x.length) break;
    prev = { i: m, T: sourd, voisee: false }; out.push(prev);
    i = m + sourd;
  }
  return out;
}

/* ---- 4. une syllabe [a, b) du son x, rendue : sa voyelle étirée par alpha (les consonnes gardent leur durée), sa hauteur posée sur cible
   (Hz, ou 0 : la sienne) ; rend { y (Float32Array), attaque (sa place dans y, échantillons), f0_in (la médiane de sa voix) } */
function attaqueDans(x, a, b, sr, seuil = DEFAUTS.attaque_seuil) {
  const { e, pas } = enveloppe(x, sr, 2, 10, a, b);
  let m = 0; for (const v of e) if (v > m) m = v;
  const k = e.findIndex(v => v >= seuil * m);
  return k < 0 ? 0 : k * pas;
}
function rendreSyllabe(x, sr, H, M, a, b, { duree, cible = 0, force = DEFAUTS.force, o = {} } = {}) {
  const r = { ...DEFAUTS, ...o };
  // sa partie voisée (la voyelle) : la première et la dernière trame qui ont une hauteur
  let v0 = -1, v1 = -1;
  for (let i = a; i < b; i += H.pas) if (f0A(H, i) > 0) { if (v0 < 0) v0 = i; v1 = i + H.pas; }
  v1 = Math.min(b, v1);
  const voix = [];
  for (let i = Math.max(a, v0); v0 >= 0 && i < v1; i += H.pas) { const f = f0A(H, i); if (f > 0) voix.push(f); }
  const f0in = voix.length ? mediane(voix) : 0;
  // jamais plus d'une quinte de décalage pour une syllabe : sa note prise à l'octave d'à côté (la même note)
  if (cible > 0 && f0in > 0) { while (12 * Math.log2(cible / f0in) > r.decalage_max_st) cible /= 2; while (12 * Math.log2(cible / f0in) < -r.decalage_max_st) cible *= 2; }
  const pre = v0 >= 0 ? v0 - a : 0, post = v0 >= 0 ? b - v1 : 0, lv = v0 >= 0 ? v1 - v0 : b - a;
  let alpha = duree > 0 ? (duree - pre - post) / Math.max(1, lv) : 1;
  alpha = borne(alpha, r.etirer_min, r.etirer_max);
  // la carte du temps (sortie → entrée) : les consonnes à 1, la voyelle à alpha
  const s0 = v0 >= 0 ? pre : 0, s1 = s0 + lv * alpha, total = Math.round(s1 + post);
  const versEntree = (t) => (t < s0 ? a + t : t < s1 ? (v0 >= 0 ? v0 : a) + (t - s0) / alpha : (v0 >= 0 ? v1 : b) + (t - s1));
  const ms = M.filter(m => m.i >= a - 2 * m.T && m.i < b + m.T);
  if (!ms.length) return { y: new Float32Array(0), attaque: 0, f0_in: 0 };
  const y = new Float32Array(total + 1), w = new Float32Array(total + 1);
  const rapport = (f) => {   // la hauteur voulue sur sa hauteur : la note, sa propre intonation gardée à (1 − force)
    if (!(cible > 0) || !(f > 0) || !(f0in > 0)) return 1;
    return (cible * Math.pow(f / f0in, 1 - force)) / f;
  };
  let t = 0, k = 0;
  while (t < total) {
    const ti = versEntree(t);
    while (k + 1 < ms.length && Math.abs(ms[k + 1].i - ti) <= Math.abs(ms[k].i - ti)) k++;
    const m = ms[k], T = m.T;
    const beta = m.voisee ? borne(rapport(f0A(H, m.i) || f0in), 0.5, 2) : 1;
    // le grain : deux périodes autour de la marque, fenêtre de Hann, posé à t
    for (let j = -T; j < T; j++) {
      const src = m.i + j, dst = Math.round(t) + j;
      if (src < a - T || src >= b + T || src < 0 || src >= x.length || dst < 0 || dst > total) continue;
      const h = 0.5 + 0.5 * Math.cos(Math.PI * j / T);
      // hors de la syllabe, le grain s'éteint (pas de voisin qui revient)
      const dedans = src < a ? Math.max(0, 1 - (a - src) / T) : src >= b ? Math.max(0, 1 - (src - b + 1) / T) : 1;
      y[dst] += h * dedans * x[src]; w[dst] += h;
    }
    t += m.voisee ? Math.max(sr / r.f0_max, T / beta) : T;
  }
  for (let i = 0; i <= total; i++) y[i] = w[i] > 0.3 ? y[i] / w[i] : y[i] / 0.3;
  const att = attaqueDans(y, 0, y.length, sr, r.attaque_seuil);
  return { y, attaque: att, f0_in: f0in, alpha, cible, voisee_ms: Math.round(lv * alpha / sr * 1000) };
}
function fondre(y, sr, a = 0, b = y.length, ms = DEFAUTS.fondu_ms) {
  const n = Math.min(Math.round(sr * ms / 1000), (b - a) >> 1);
  for (let i = 0; i < n; i++) { const g = 0.5 - 0.5 * Math.cos(Math.PI * i / n); y[a + i] *= g; y[b - 1 - i] *= g; }
}

/* ---- l'octave de la phrase : celle qui rapproche le plus les notes du morceau de sa voix (la même pour toute la phrase : la mélodie garde
   sa forme) ; une note encore à plus d'une quinte de sa voix : prise à l'octave d'à côté. cibles : Hz (0 : inconnue, tenue de la voisine) */
function cibles(hz, f0voix, o = {}) {
  const r = { ...DEFAUTS, ...o };
  const l = (hz || []).map(v => (v > 0 ? v : 0));
  // une syllabe sans note : celle d'avant (ou d'après) ; aucune : sa voix telle quelle
  for (let i = 0; i < l.length; i++) if (!l[i]) { const p = l.slice(0, i).reverse().find(v => v > 0) || l.slice(i + 1).find(v => v > 0); if (p) l[i] = p; }
  if (!l.some(v => v > 0) || !(f0voix > 0)) return l.map(() => 0);
  const k = Math.round(mediane(l.map(v => Math.log2(f0voix / v))));
  return l.map((v) => {
    let c = v * Math.pow(2, k);
    const st = 12 * Math.log2(c / f0voix);
    if (st > r.decalage_max_st) c /= 2; else if (st < -r.decalage_max_st) c *= 2;
    return c;
  });
}

/* ---- 5. la ligne chantée. wav : sa voix Azure (blancs entre les mots) ; mots : leurs textes ; syllabes : [{ m (son mot), t (ms, depuis le zéro
   de la ligne : la première syllabe à 0), d (sa place, ms), hz (la note du morceau, 0 : inconnue) }] (Chanter.scander). Rend { wav, zero_ms
   (la place du zéro dans le son), syllabes: [{ t, attaque_ms, cible_hz, f0_in }], ms } ; null : la voix ne se laisse pas couper en ses mots */
function chanterLigne(wav, mots, syllabes, o = {}) {
  const r = { ...DEFAUTS, ...o }, t0 = Date.now();
  const p = lirePcm(wav);
  if (!p || !Array.isArray(mots) || !mots.length || !Array.isArray(syllabes) || !syllabes.length) return null;
  const { x, sr } = p;
  const parMot = mots.map((_, i) => syllabes.filter(s => s.m === i));
  if (parMot.some(l => !l.length)) return null;
  const segs = decouperMots(x, sr, mots.length, r);
  if (!segs) return null;
  const H = hauteurs(x, sr, r), M = marques(x, sr, H);
  const morceaux = [];
  segs.forEach(([a, b], i) => decouperSyllabes(x, sr, a, b, parMot[i].length).forEach(([u, v]) => morceaux.push([u, v])));
  const ordre = syllabes.slice().sort((p1, p2) => p1.t - p2.t);
  // sa voix, sa médiane : l'octave de la phrase
  const vf = []; for (const v of H.f0) if (v > 0) vf.push(v);
  const f0voix = vf.length ? mediane(vf) : 0;
  const notes = cibles(ordre.map(s => Number(s.hz) || 0), f0voix, r);
  const marge = Math.round(sr * r.marge_ms / 1000);
  const fin = Math.round(sr * ((ordre[ordre.length - 1].t + ordre[ordre.length - 1].d + r.queue_ms) / 1000)) + 2 * marge;
  const out = new Float32Array(fin);
  // l'attaque de chaque syllabe (avant traitement), pour ce qui la précède (sa consonne) : la place de la précédente s'arrête là
  const pres = morceaux.map(([a, b]) => attaqueDans(x, a, b, sr, r.attaque_seuil));
  const rendu = [];
  ordre.forEach((s, i) => {
    const [a, b] = morceaux[i];
    const ici = marge + Math.round(sr * s.t / 1000);
    const suivant = i + 1 < ordre.length ? marge + Math.round(sr * ordre[i + 1].t / 1000) - pres[i + 1] : ici + Math.round(sr * (s.d + r.queue_ms) / 1000);
    const place = Math.max(Math.round(sr * 0.04), suivant - (ici - pres[i]));
    const R = rendreSyllabe(x, sr, H, M, a, b, { duree: Math.min(place, Math.round(sr * s.d / 1000) + pres[i]), cible: notes[i], o: r });
    let debut = ici - R.attaque, n = Math.min(R.y.length, place, out.length - Math.max(0, debut));
    let src0 = 0;
    if (debut < 0) { src0 = -debut; n -= src0; debut = 0; }
    if (n <= 0) { rendu.push({ t: s.t, attaque_ms: null, cible_hz: notes[i], f0_in: R.f0_in }); return; }
    const y = R.y.subarray(src0, src0 + n);
    const z = Float32Array.from(y); fondre(z, sr, 0, z.length, r.fondu_ms);
    for (let j = 0; j < z.length; j++) out[debut + j] += z[j];
    rendu.push({ t: s.t, attaque_ms: Math.round(((debut + R.attaque - src0) - marge) / sr * 1000), cible_hz: Math.round((R.cible || notes[i]) * 10) / 10, f0_in: Math.round(R.f0_in), alpha: Math.round((R.alpha || 1) * 100) / 100 });
  });
  let m = 0; for (const v of out) m = Math.max(m, Math.abs(v));
  if (m > 0.98) for (let i = 0; i < out.length; i++) out[i] *= 0.98 / m;
  // la queue : jusqu'au dernier son
  let n = out.length; while (n > marge && Math.abs(out[n - 1]) < 1e-4) n--;
  return { wav: ecrirePcm(out.subarray(0, Math.min(out.length, n + Math.round(sr * 0.02))), sr), zero_ms: r.marge_ms, sr, syllabes: rendu, f0_voix: Math.round(f0voix), ms: Date.now() - t0 };
}

/* ---- les mesures (le banc, les tests) : les attaques trouvées dans un son sans rien savoir du plan (la force qui monte d'un coup), et la
   hauteur d'un passage */
function attaquesDe(x, sr, o = {}) {
  const { e, pas } = enveloppe(x, sr, 5, 10);
  const l = e.map(v => Math.log10(v + 1e-4));
  let m = 0; for (const v of e) m = Math.max(m, v);
  const out = [];
  let der = -Infinity;
  for (let i = 3; i < l.length; i++) {
    const monte = l[i] - Math.min(l[i - 1], l[i - 2], l[i - 3]);
    if (monte < (o.saut || 0.5) || e[i] < 0.15 * m) continue;
    if (i * pas - der < sr * 0.07) continue;
    // le point où elle passe 30 % du plus fort qui suit (60 ms), comme le plan
    let pic = 0; for (let j = i; j < Math.min(e.length, i + 12); j++) pic = Math.max(pic, e[j]);
    let k = i - 3; while (k < i + 12 && e[k] < 0.3 * pic) k++;
    out.push(k * pas); der = i * pas;
  }
  return out;
}
function hauteurDe(x, sr, a, b, o = {}) {
  const H = hauteurs(x.subarray(Math.max(0, a), Math.min(x.length, b)), sr, o);
  const v = Array.from(H.f0).filter(f => f > 0);
  // le milieu de la partie voisée (son début et sa fin glissent)
  const c = v.slice(Math.floor(v.length * 0.2), Math.ceil(v.length * 0.8));
  return c.length ? mediane(c) : 0;
}

module.exports = { DEFAUTS, lirePcm, ecrirePcm, enveloppe, decouperMots, decouperSyllabes, hauteurs, marques, rendreSyllabe, cibles, chanterLigne, attaquesDe, hauteurDe, attaqueDans, cents, mediane };

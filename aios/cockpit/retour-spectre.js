/* (11/11, Ahmed : « un bouton pour qu'il n'entende pas le retour du micro ») LE RETOUR DU MICRO, BIN PAR BIN (la logique pure ; retour-micro.js
   garde l'enveloppe, ses mesures et ses gardes). Le cockpit reçoit le SON même de son intérieur (les blocs que l'appli envoie à ses oreilles :
   ses mots vifs toutes les 1,5 s, ses blocs de 8 s), à l'heure du téléphone. Chaque morceau du micro est comparé à ce son, en spectre (fenêtres
   de 32 ms, pas de 8 ms, de 100 Hz à 4 kHz) : au bon retard, le module de chaque bin du micro est-il expliqué par celui de l'intérieur, à sa
   force près (le haut-parleur, la pièce : un gain par bin, la médiane du morceau) ? Ce qui DÉPASSE le retour prédit (6 dB au-dessus) est une
   autre voix, dans les creux du live, entre ses harmoniques, dans les graves que le petit haut-parleur ne rend pas : papa, même plus bas que
   le live (au banc, à − 8 dB, la moyenne sur 100 ms ne le voyait plus).
   Rend la part de l'énergie du morceau que le retour n'explique pas, ses trames de « voix proche », et la ressemblance (corrélation des
   logarithmes des modules) au meilleur retard.
   MESURÉ au banc (mesure/retour-spectre-banc.js : voix de say, haut-parleur et micro calés sur les graves du vrai du 11/11, retards 40-300 ms,
   gain automatique ± 3 dB, 2 graines × 180 s par niveau ; avec la garde « papa vient de parler », sans son oreille des voix ni ses mots) :
   morceaux de pur retour écartés 76 % (papa à 0 dB du live), 66 % (− 6), 61 % (− 8), 72 % (− 12) ; au témoin (le son de l'intérieur d'un
   autre moment) 0 sur 998 ; phrases de papa intactes 100 % à 0 dB (125), 94 % à − 6, 96 % à − 8, 83 % à − 12 dB (papa 4 fois plus bas que le
   live : là, l'acoustique seule ne le protège plus). Le retour était 8 dB au-dessus de papa au micro le 11/11 (niveaux médians 0,22 et 0,09). */
'use strict';

const N = 512, PAS = 128, SR = 16000;               // 32 ms, un pas de 8 ms
const MS_PAS = PAS * 1000 / SR;
const K0 = Math.round(100 * N / SR), K1 = Math.round(4000 * N / SR);   // de 100 Hz à 4 kHz
const EPS = 1e-6;
const FENETRE = Float64Array.from({ length: N }, (_, i) => 0.5 - 0.5 * Math.cos(2 * Math.PI * i / N));
const EXCES_X = 2;                                   // un bin au-dessus de 2 fois (6 dB) son retour prédit : autre chose
// une trame de VOIX PROCHE : ce qui y dépasse le retour vaut au moins 5 % de l'énergie médiane des trames sonores du morceau, et 5 % de la sienne
// (au banc, papa à − 8 dB : la moitié de ses trames passent le premier seuil ; le retour seul, 1 à 2 % ; une part seule, sans le premier,
// comptait les trames faibles du retour, ses débuts et ses traînes, toutes « dépassées »)
const VOIX_REL = 0.05, VOIX_PART = 0.05;
const VOIX_MS = 40;                                  // 40 ms de ces trames (5 pas) dans le morceau : un bout de syllabe de papa suffit à le garder
const PART_MAX = 0.08;                               // au plus 8 % de l'énergie du morceau non expliquée, pour l'écarter
// (au banc calé sur le vrai : 64 ms et 12 % écartaient 66 à 80 % du pur retour mais abîmaient 8 % des phrases de papa à − 6 / − 8 dB ; 40 ms et
// 8 % : 61 à 76 % écartés, 4 à 6 % abîmées ; papa à 0 dB : 100 % intact dans les deux cas)
const RESSEMBLANCE_MIN = 0.45;

function fft(re, im) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) { let b = n >> 1; for (; j & b; b >>= 1) j ^= b; j ^= b; if (i < j) { let t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; } }
  for (let len = 2; len <= n; len <<= 1) {
    const a = -2 * Math.PI / len, h = len >> 1;
    for (let k = 0; k < h; k++) {
      const c = Math.cos(a * k), s = Math.sin(a * k);
      for (let i = k; i < n; i += len) { const j = i + h, xr = re[j] * c - im[j] * s, xi = re[j] * s + im[j] * c; re[j] = re[i] - xr; im[j] = im[i] - xi; re[i] += xr; im[i] += xi; }
    }
  }
}
// les modules d'un signal (Float32 16 kHz), trame par trame : [j][k - K0] ; et l'énergie de chaque trame (sur les mêmes bins)
function spectre(x) {
  const J = Math.max(0, Math.floor((x.length - N) / PAS) + 1), mod = new Array(J), en = new Float64Array(J);
  const re = new Float64Array(N), im = new Float64Array(N);
  for (let j = 0; j < J; j++) {
    const o = j * PAS;
    for (let i = 0; i < N; i++) { re[i] = x[o + i] * FENETRE[i]; im[i] = 0; }
    fft(re, im);
    const m = new Float32Array(K1 - K0); let e = 0;
    for (let k = K0; k < K1; k++) { const v = Math.hypot(re[k], im[k]); m[k - K0] = v; e += v * v; }
    mod[j] = m; en[j] = e;
  }
  return { mod, en, J };
}
// le son de son intérieur sur [de, a[ (ms, l'horloge du téléphone), assemblé de ses blocs [{ t0, pcm (Float32 16 kHz) }] ; couvert : la part reçue
function assembler(blocs, de, a) {
  const n = Math.max(0, Math.round((a - de) * SR / 1000)), x = new Float32Array(n), vu = new Uint8Array(n);
  for (const b of blocs || []) {
    if (!b || !b.pcm || !(b.t0 > 0)) continue;
    const o = Math.round((b.t0 - de) * SR / 1000);
    for (let i = Math.max(0, -o); i < b.pcm.length && o + i < n; i++) { x[o + i] = b.pcm[i]; vu[o + i] = 1; }
  }
  let c = 0; for (let i = 0; i < n; i++) c += vu[i];
  return { x, vu, couvert: n ? c / n : 0 };
}

/* JUGER un morceau du micro contre le son de son intérieur. mic : { pcm (Float32 16 kHz), t0 } ; blocs : les blocs de son intérieur ;
   prior : le retard appris (ms) ou null ; o : { de, a } la plage de retards cherchée sans prior.
   Rend { retardMs, ressemblance, part (non expliquée), voixMs (trames de voix proche), couvert, trames, sonores } ou null (rien à comparer). */
function juger(mic, blocs, prior = null, o = {}) {
  if (!mic || !mic.pcm || mic.pcm.length < N * 2 || !(mic.t0 > 0)) return null;
  const dureeMs = mic.pcm.length * 1000 / SR;
  const lags = [];
  if (Number.isFinite(prior)) for (let d = prior - 96; d <= prior + 96; d += MS_PAS) lags.push(Math.round(d));
  else for (let d = Number.isFinite(o.de) ? o.de : -200; d <= (Number.isFinite(o.a) ? o.a : 1200); d += 2 * MS_PAS) lags.push(Math.round(d));
  const dMin = Math.min(...lags), dMax = Math.max(...lags);
  // le son de l'intérieur qui a pu revenir : de t0 - dMax - 64 ms (sa traîne) à la fin du morceau - dMin
  const de = mic.t0 - dMax - 64, ref = assembler(blocs, de, mic.t0 + dureeMs - dMin + 40);
  if (ref.couvert < 0.3) return { couvert: Math.round(ref.couvert * 100) / 100, retardMs: null };
  const M = spectre(mic.pcm), R = spectre(ref.x);
  // les trames sonores du micro (au-dessus de son plancher : le 20e centile de ses énergies × 4, et un seuil absolu)
  const ens = Array.from(M.en).sort((a, b) => a - b), plancher = Math.max(1e-4, 4 * (ens[Math.floor(ens.length * 0.2)] || 0));
  const sonores = []; for (let j = 0; j < M.J; j++) if (M.en[j] > plancher) sonores.push(j);
  if (sonores.length < 10) return { couvert: Math.round(ref.couvert * 100) / 100, retardMs: null, sonores: sonores.length };
  // la trame de l'intérieur qui a pu revenir à la trame j du micro, pour un retard d (ms) : son indice (arrondi) dans R
  const indice = (j, d) => Math.round((mic.t0 + j * MS_PAS - d - de) / MS_PAS);
  const vuTrame = (r) => { const i = r * PAS + (N >> 1); return i >= 0 && i < ref.vu.length && ref.vu[i]; };
  // le meilleur retard : la corrélation des logarithmes des modules (les bins des trames sonores, là où l'intérieur a joué)
  let meilleur = { c: -2, d: null };
  const courbe = [];
  // (une trame sonore sur deux, un bin sur trois : la courbe des retards garde sa forme, en un sixième du temps)
  const lm = M.mod.map(a => a && Float32Array.from(a, v => Math.log(v + EPS))), lr = R.mod.map(a => a && Float32Array.from(a, v => Math.log(v + EPS)));
  for (const d of lags) {
    let n = 0, sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0;
    for (let q = 0; q < sonores.length; q += 2) {
      const j = sonores[q], r = indice(j, d); if (r < 0 || r >= R.J || !vuTrame(r)) continue;
      const a = lm[j], b = lr[r];
      for (let k = 0; k < a.length; k += 3) { const x = a[k], y = b[k]; n++; sx += x; sy += y; sxx += x * x; syy += y * y; sxy += x * y; }
    }
    const vx = sxx - sx * sx / Math.max(1, n), vy = syy - sy * sy / Math.max(1, n);
    const c = n > 100 && vx > 1e-9 && vy > 1e-9 ? (sxy - sx * sy / n) / Math.sqrt(vx * vy) : null;
    courbe.push({ d, c });
    if (c !== null && c > meilleur.c) meilleur = { c, d };
  }
  if (meilleur.d === null) return { couvert: Math.round(ref.couvert * 100) / 100, retardMs: null, sonores: sonores.length };
  // sans prior : un pic net (les autres sommets, à plus de 150 ms, au moins 0,05 plus bas)
  let net = true;
  if (!Number.isFinite(prior)) {
    for (let i = 1; i < courbe.length - 1; i++) {
      const x = courbe[i]; if (x.c === null || Math.abs(x.d - meilleur.d) <= 150) continue;
      if (x.c >= (courbe[i - 1].c ?? -2) && x.c >= (courbe[i + 1].c ?? -2) && meilleur.c - x.c < 0.05) net = false;
    }
  }
  const d = meilleur.d;
  // sa force, bin par bin : la médiane du rapport micro / intérieur sur les trames sonores (une voix proche, éparse, ne la déplace guère)
  const H = new Float32Array(K1 - K0);
  for (let k = 0; k < H.length; k++) {
    const rs = [];
    for (const j of sonores) { const r = indice(j, d); if (r >= 0 && r < R.J && vuTrame(r) && R.mod[r][k] > 1e-4) rs.push(M.mod[j][k] / R.mod[r][k]); }
    rs.sort((a, b) => a - b);
    H[k] = rs.length >= 5 ? rs[rs.length >> 1] : 0;
  }
  // son retour prédit, bin par bin : la force × le plus fort de l'intérieur à ±1 pas, et sa traîne (la pièce : ×0,7 par 16 ms)
  let nonExplique = 0, total = 0, voix = 0, run = 0, runMax = 0;
  const detail = o.detail ? [] : null;
  const enSon = sonores.map(j => M.en[j]).sort((a, b) => a - b), mediane = enSon[enSon.length >> 1] || 1e-9;
  const vRel = Number.isFinite(o.voix_rel) ? o.voix_rel : VOIX_REL, vPart = Number.isFinite(o.voix_part) ? o.voix_part : VOIX_PART;
  for (const j of sonores) {
    const r = indice(j, d);
    const a = M.mod[j];
    let ex = 0, tot = 0, pred = 0;
    for (let k = 0; k < a.length; k++) {
      let p = 0;
      for (const [dr, f] of [[-1, 1], [0, 1], [1, 1], [2, 0.7], [4, 0.49]]) { const rr = r - dr; if (rr >= 0 && rr < R.J && vuTrame(rr)) p = Math.max(p, f * R.mod[rr][k]); }
      p *= H[k];
      const e = a[k] * a[k]; tot += e; pred += p * p;
      if (a[k] > EXCES_X * p) ex += e - p * p;
    }
    if (detail) detail.push({ j, t: mic.t0 + j * MS_PAS + 16, ex, tot, pred });
    nonExplique += ex; total += tot;
    if (tot > 0 && ex > vRel * mediane && ex > vPart * tot) { voix++; run++; if (run > runMax) runMax = run; } else run = 0;
  }
  const r2 = (x) => Math.round(x * 100) / 100;
  return { retardMs: d, ressemblance: r2(meilleur.c), net, part: r2(total ? nonExplique / total : 1), voixMs: Math.round(voix * MS_PAS), voixSuiteMs: Math.round(runMax * MS_PAS),
    couvert: r2(ref.couvert), trames: M.J, sonores: sonores.length, ...(detail ? { detail } : {}) };
}

/* Le verdict : 'retour' (écarté) seulement si tout le dit : un retard net, une ressemblance suffisante, presque toute l'énergie expliquée, pas
   une syllabe de voix proche ; 'doute' si le retour y est mais pas seul (gardé) ; 'garde' sinon. o : seuils (pour le banc). */
function verdict(j, o = {}) {
  if (!j || j.retardMs === null || j.retardMs === undefined) return { verdict: 'garde', raison: j && j.couvert < 0.3 ? 'interieur_absent' : 'rien_a_comparer' };
  const partMax = Number.isFinite(o.part_max) ? o.part_max : PART_MAX, voixMs = Number.isFinite(o.voix_ms) ? o.voix_ms : VOIX_MS;
  const rMin = Number.isFinite(o.ressemblance) ? o.ressemblance : RESSEMBLANCE_MIN;
  if (j.couvert < 0.7) return { verdict: 'doute', raison: 'couverture' };
  if (j.ressemblance < rMin || !j.net) return { verdict: j.ressemblance >= rMin - 0.15 ? 'doute' : 'garde', raison: 'pas_le_retour' };
  if (j.voixMs >= voixMs) return { verdict: 'doute', raison: 'voix_au_dessus' };
  if (j.part > partMax) return { verdict: 'doute', raison: 'partiel' };
  return { verdict: 'retour', raison: 'spectre' };
}

module.exports = { N, PAS, SR, MS_PAS, EXCES_X, VOIX_REL, VOIX_PART, VOIX_MS, PART_MAX, RESSEMBLANCE_MIN, fft, spectre, assembler, juger, verdict };

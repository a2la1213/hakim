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

/* ---- (13/11, Ahmed : « le bouton ne marche pas » ; Nour : mesuré, 🔁 allumé, 0 morceau écarté sur 54 : chacun gardé ENTIER dès que son
   oreille des voix entendait papa dedans, et en live papa parle presque tout le temps) SOUSTRAIRE LE RETOUR au lieu d'écarter le morceau :
   le chemin haut-parleur → micro (son retard, sa force bin par bin, la traîne de la pièce) est estimé sur le morceau même, comme le juge ;
   le retour PRÉDIT est retiré du son du micro, bin par bin (32 ms, toutes les fréquences), et ce qui reste (papa, les gens à côté de lui)
   est rendu en son, pour être transcrit. Deux étages :
   - un MASQUE par bin : ce qui ne dépasse pas le retour prédit est retiré, ce qui le dépasse nettement (2 fois, 6 dB) est gardé tel quel,
     entre les deux une pente (la soustraction de puissance, α) ;
   - une PORTE par trame : une trame où rien ne dépasse le retour (pas une « trame de voix proche », la règle du juge) est éteinte, sauf
     autour d'une voix proche (GARDE_MS avant et après : ses débuts et ses fins de mots, plus faibles) ; sans elle, le live atténué de
     20 dB restait intelligible dans les blancs de papa (une transcription ne s'arrête pas au niveau).
   Ce qui n'est PAS touché : un morceau où le retour n'est pas net (ressemblance, retard, couverture : le son entier, comme avant) ; les
   trames que l'intérieur ne couvre pas (gardées telles quelles). La force du chemin, par bin : la médiane du rapport micro / intérieur sur
   les trames où l'intérieur est fort, refaite sans les cases où une voix dépasse (papa ne la tire pas vers le haut), lissée sur 3 bins et
   plafonnée à 3 fois sa valeur médiane de 300 Hz à 3 kHz (dans les graves que le petit haut-parleur ne rend pas, le rapport ne mesure que
   papa et le souffle : sans plafond, ses graves partaient). ---- */
const NB = N / 2 + 1;                                // 257 bins, de 0 à 8 kHz
const BORD = N - PAS;                                // les bords : chaque échantillon couvert par N / PAS = 4 trames
const ALPHA = 2;                                     // la soustraction de puissance : G = √(1 − α P² / |X|²)
const GARDE_MS = 120;                                // autour d'une trame de voix proche, la porte reste ouverte
const SOL = 0;                                       // ce que garde une trame fermée par la porte (0 : rien)
const LIEN_MIN = 0.2;                                // un bin où le micro ne suit pas l'intérieur (corrélation des modules) : rien n'y est retiré
const LAMBDA = 0.9;                                  // la traîne de la pièce : 0,9 par pas de 8 ms (− 3 dB en 50 ms)
// le spectre complet d'un signal (ses bords ajoutés), trame par trame : re, im (J × NB), et le module ; la trame j commence à l'échantillon j·PAS − BORD
function stft(x) {
  const L = x.length + 2 * BORD, J = Math.max(0, Math.floor((L - N) / PAS) + 1);
  const re = new Float32Array(J * NB), im = new Float32Array(J * NB), mod = new Float32Array(J * NB);
  const fr = new Float64Array(N), fi = new Float64Array(N);
  for (let j = 0; j < J; j++) {
    const o = j * PAS - BORD;
    for (let i = 0; i < N; i++) { const k = o + i; fr[i] = k >= 0 && k < x.length ? x[k] * FENETRE[i] : 0; fi[i] = 0; }
    fft(fr, fi);
    for (let k = 0; k < NB; k++) { re[j * NB + k] = fr[k]; im[j * NB + k] = fi[k]; mod[j * NB + k] = Math.hypot(fr[k], fi[k]); }
  }
  return { re, im, mod, J, n: x.length };
}
// le son rendu d'un spectre modifié par ses gains (J × NB) : la transformée inverse, fenêtrée, additionnée, divisée par la somme des fenêtres²
function istft(S, G) {
  const L = S.n + 2 * BORD, y = new Float64Array(L), w2 = new Float64Array(L);
  const fr = new Float64Array(N), fi = new Float64Array(N);
  for (let j = 0; j < S.J; j++) {
    for (let k = 0; k < NB; k++) { const g = G ? G[j * NB + k] : 1; fr[k] = S.re[j * NB + k] * g; fi[k] = -S.im[j * NB + k] * g; }   // conjugué : l'inverse par l'aller
    for (let k = 1; k < N / 2; k++) { fr[N - k] = fr[k]; fi[N - k] = -fi[k]; }
    fft(fr, fi);
    const o = j * PAS;
    for (let i = 0; i < N; i++) { const w = FENETRE[i]; y[o + i] += (fr[i] / N) * w; w2[o + i] += w * w; }
  }
  const out = new Float32Array(S.n);
  for (let i = 0; i < S.n; i++) { const q = w2[i + BORD]; out[i] = q > 1e-6 ? y[i + BORD] / q : 0; }
  return out;
}
const mediane = (a) => { if (!a.length) return 0; const s = Float64Array.from(a).sort(); return s[s.length >> 1]; };

/* LE MASQUE du retour d'un morceau, au retard d (ms). mic : { pcm, t0 } ; blocs : son intérieur. Rend { G (J × NB, porte comprise), S (le
   spectre du micro), voixMs (trames de voix proche), ouvertMs (la porte ouverte), couvert } ou null (l'intérieur absent). o : réglages (banc). */
function masque(mic, blocs, d, o = {}) {
  const alpha = Number.isFinite(o.alpha) ? o.alpha : ALPHA, gardeMs = Number.isFinite(o.garde_ms) ? o.garde_ms : GARDE_MS;
  const sol = Number.isFinite(o.sol) ? o.sol : SOL, porte = o.porte !== false, plafond = o.plafond !== false, raffine = o.raffine !== false, trainee = o.trainee !== false, lien = o.lien !== false;
  const S = stft(mic.pcm);
  if (S.J < 8) return null;
  // l'intérieur aligné trame pour trame : la trame r = j + AVANT du son de l'intérieur commence d ms (+ AVANT pas) avant la trame j du micro ;
  // AVANT : 300 ms d'histoire, pour la traîne de la pièce dès le début du morceau
  const AVANT = 40;
  const deRef = mic.t0 - BORD * 1000 / SR - d - AVANT * MS_PAS;
  const ref = assembler(blocs, deRef, deRef + ((S.J + AVANT + 4) * PAS + N) * 1000 / SR);
  if (ref.couvert < 0.05) return null;
  const R = stft(ref.x);
  const rDe = (j) => j + AVANT + BORD / PAS;          // la trame de R qui commence au même instant (moins d) que la trame j du micro
  const vuR = (r) => { const i = r * PAS - BORD + (N >> 1); return i >= 0 && i < ref.vu.length && ref.vu[i] === 1; };
  // deux parts du retour prédit, bin par bin : le DIRECT (le plus fort de l'intérieur à ±1 trame : le retard à 8 ms près) et la TRAÎNE de la
  // pièce (l'intérieur passé, qui s'éteint de λ par trame, à partir de 2 trames plus tôt)
  const T = new Float32Array(R.J * NB);
  for (let r = 0; r < R.J; r++) for (let k = 0; k < NB; k++) T[r * NB + k] = (r ? LAMBDA * T[(r - 1) * NB + k] : 0) + (1 - LAMBDA) * R.mod[r * NB + k];
  const D = new Float32Array(S.J * NB), Tr = new Float32Array(S.J * NB), couv = new Uint8Array(S.J);
  for (let j = 0; j < S.J; j++) {
    const r = rDe(j);
    if (!vuR(r) || r + 1 >= R.J || r < 2) continue;
    couv[j] = 1;
    for (let k = 0; k < NB; k++) { D[j * NB + k] = Math.max(R.mod[(r - 1) * NB + k], R.mod[r * NB + k], R.mod[(r + 1) * NB + k]); Tr[j * NB + k] = T[(r - 2) * NB + k]; }
  }
  // la force de chaque part, bin par bin : les moindres carrés (X ≈ a·D + b·T, a et b positifs) sur les trames où l'intérieur est fort (ses 40 %
  // les plus fortes), refaits sans les cases où une voix dépasse 2 fois le prédit (papa ne la tire pas vers le haut)
  const A = new Float32Array(NB), Bt = new Float32Array(NB);
  const ajuster = (cases) => {
    let dd = 0, dt = 0, tt = 0, xd = 0, xt = 0;
    for (const i of cases) { const x = S.mod[i], dv = D[i], tv = Tr[i]; dd += dv * dv; dt += dv * tv; tt += tv * tv; xd += x * dv; xt += x * tv; }
    const det = dd * tt - dt * dt;
    let a = det > 1e-12 ? (xd * tt - xt * dt) / det : 0, b = det > 1e-12 ? (xt * dd - xd * dt) / det : 0;
    if (!(a >= 0) || !(b >= 0) || !trainee) { if (!trainee || !(b > 0)) { a = dd > 1e-12 ? Math.max(0, xd / dd) : 0; b = 0; } else { b = tt > 1e-12 ? Math.max(0, xt / tt) : 0; a = 0; } }
    return [a, b];
  };
  for (let k = 0; k < NB; k++) {
    const vals = []; for (let j = 0; j < S.J; j++) if (couv[j]) vals.push(D[j * NB + k]);
    if (vals.length < 8) continue;
    const seuil = Math.max(1e-4, Float64Array.from(vals).sort()[Math.floor(vals.length * 0.6)]);
    let cases = []; for (let j = 0; j < S.J; j++) if (couv[j] && D[j * NB + k] >= seuil) cases.push(j * NB + k);
    if (cases.length < 5) continue;
    // (le LIEN) le micro suit-il l'intérieur dans ce bin ? la corrélation de leurs modules sur les trames couvertes ; sans lien (sous LIEN_MIN),
    // rien n'y est retiré : là où le petit haut-parleur ne rend rien (les graves des voix du live), le micro n'entend que papa et la pièce,
    // et un gain ajusté quand même (des modules toujours positifs ne s'annulent jamais) retirait ses graves
    if (lien) {
      let n = 0, sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0;
      for (let j = 0; j < S.J; j++) if (couv[j]) { const x = S.mod[j * NB + k], y = D[j * NB + k]; n++; sx += x; sy += y; sxx += x * x; syy += y * y; sxy += x * y; }
      const vx = sxx - sx * sx / n, vy = syy - sy * sy / n, c = vx > 1e-12 && vy > 1e-12 ? (sxy - sx * sy / n) / Math.sqrt(vx * vy) : 0;
      if (c < LIEN_MIN) continue;
    }
    let [a, b] = ajuster(cases);
    if (raffine) for (let it = 0; it < 2; it++) {
      const sans = cases.filter(i => S.mod[i] <= EXCES_X * (a * D[i] + b * Tr[i]));
      if (sans.length < 5) break;
      [a, b] = ajuster(sans);
    }
    A[k] = a; Bt[k] = b;
  }
  const lisse = (H) => Float32Array.from(H, (_, k) => mediane([H[Math.max(0, k - 1)], H[k], H[Math.min(NB - 1, k + 1)]]));
  const Al = lisse(A), Bl = lisse(Bt);
  if (plafond) for (const H of [Al, Bl]) {
    const bande = []; for (let k = Math.round(300 * N / SR); k <= Math.round(3000 * N / SR); k++) if (H[k] > 0) bande.push(H[k]);
    const hb = mediane(bande);
    if (hb > 0) for (let k = 0; k < NB; k++) H[k] = Math.min(H[k], 3 * hb);
  }
  const Hl = Al;
  // le masque, et les trames de voix proche (la règle du juge, de 100 Hz à 4 kHz : ce qui dépasse 2 fois le prédit, relatif à la médiane des
  // trames sonores du morceau et à la trame même)
  const G = new Float32Array(S.J * NB), ex = new Float64Array(S.J), tot = new Float64Array(S.J);
  for (let j = 0; j < S.J; j++) {
    for (let k = 0; k < NB; k++) {
      const i = j * NB + k, x = S.mod[i];
      if (!couv[j]) { G[i] = 1; continue; }
      const p = Al[k] * D[i] + Bl[k] * Tr[i];
      G[i] = x > 1e-9 ? Math.sqrt(Math.max(0, 1 - alpha * p * p / (x * x))) : 0;
      if (k >= K0 && k < K1) { tot[j] += x * x; if (x > EXCES_X * p) ex[j] += x * x - p * p; }
    }
  }
  const ens = Array.from(tot).filter((_, j) => couv[j]).sort((a, b) => a - b);
  const plancher = Math.max(1e-4, 4 * (ens[Math.floor(ens.length * 0.2)] || 0));
  const medSon = mediane(Array.from(tot).filter((v, j) => couv[j] && v > plancher)) || 1e-9;
  const vRel = Number.isFinite(o.voix_rel) ? o.voix_rel : VOIX_REL, vPart = Number.isFinite(o.voix_part) ? o.voix_part : VOIX_PART;
  const voix = new Uint8Array(S.J); let nVoix = 0;
  for (let j = 0; j < S.J; j++) if (couv[j] && tot[j] > plancher && ex[j] > vRel * medSon && ex[j] > vPart * tot[j]) { voix[j] = 1; nVoix++; }
  // la porte : ouverte sur une trame de voix proche et GARDE_MS autour ; toujours ouverte là où l'intérieur ne couvre pas
  const g = Math.round(gardeMs / MS_PAS), ouvert = new Uint8Array(S.J); let nOuvert = 0;
  for (let j = 0; j < S.J; j++) {
    if (!couv[j] || !porte) { ouvert[j] = 1; continue; }
    for (let q = Math.max(0, j - g); q <= Math.min(S.J - 1, j + g); q++) if (voix[q]) { ouvert[j] = 1; break; }
  }
  const Gdoux = o.doux ? Float32Array.from(G) : null;   // le masque seul, sans la porte (le reste « doux » : dans le doute)
  for (let j = 0; j < S.J; j++) {
    if (ouvert[j]) { if (couv[j]) nOuvert++; continue; }
    for (let k = 0; k < NB; k++) G[j * NB + k] *= sol;
  }
  const nCouv = couv.reduce((a, b) => a + b, 0);
  return { G, Gdoux, S, H: Hl, voixMs: Math.round(nVoix * MS_PAS), ouvertMs: Math.round(nOuvert * MS_PAS), couvert: Math.round(100 * nCouv / S.J) / 100 };
}
// le même masque appliqué à un autre son de même longueur (au banc : la voix de papa seule, le retour seul)
const appliquer = (x, G) => istft(stft(x), G);

/* SOUSTRAIRE le retour d'un morceau du micro : le juge d'abord (retard, ressemblance, couverture) ; le retour net, son masque et le son qui
   reste. Rend { applique, jugement, verdict, pcm (le reste), retireDb (ce qui est parti), voixMs, ouvertMs, couvert } ; applique: false
   (et pas de son) quand le retour n'y est pas net : le son entier est alors transcrit, comme avant. */
function soustraire(mic, blocs, prior = null, o = {}) {
  const jg = juger(mic, blocs, prior, o);
  const v = verdict(jg, o);
  const rMin = Number.isFinite(o.ressemblance) ? o.ressemblance : RESSEMBLANCE_MIN;
  if (!jg || jg.retardMs === null || jg.retardMs === undefined || !(jg.couvert >= 0.7) || !jg.net || !(jg.ressemblance >= rMin)) return { applique: false, jugement: jg, verdict: v };
  const m = masque(mic, blocs, jg.retardMs, { ...o, doux: true });
  if (!m) return { applique: false, jugement: jg, verdict: v };
  const pcm = istft(m.S, m.G), pcmDoux = istft(m.S, m.Gdoux);
  const retire = (y) => { let e0 = 0, e1 = 0; for (let i = 0; i < y.length; i++) { e0 += mic.pcm[i] * mic.pcm[i]; e1 += y[i] * y[i]; } return Math.round(10 * Math.log10((e0 + 1e-12) / (e1 + 1e-12)) * 10) / 10; };
  return { applique: true, jugement: jg, verdict: v, pcm, pcmDoux, retireDb: retire(pcm), retireDouxDb: retire(pcmDoux),
    voixMs: m.voixMs, ouvertMs: m.ouvertMs, couvert: m.couvert, ...(o.masque ? { G: m.G, Gdoux: m.Gdoux, H: m.H } : {}) };
}

/* LA DÉCISION pour un morceau soustrait (le cockpit, et le banc). x : le rendu de soustraire ; o.papaRecent (papa a parlé dans les 2 s).
   - 'entier' : le retour n'y est pas net (rien n'a été soustrait) : le son entier, comme avant ;
   - 'reste' : la porte a trouvé une voix proche : le son qui reste (masque et porte) est transcrit ;
   - 'ecarte' : aucune voix proche, ni pour la porte ni pour le juge (pur retour, la règle du 11/11), et papa n'a pas parlé dans les 2 s :
     écarté, sans transcription ;
   - 'doux' : aucune voix proche pour la porte, mais un doute (papa vient de parler, ou le juge n'y voit pas un pur retour) : le masque
     seul, sans la porte (la voix de papa qui dépasse le retour, même faible, y reste ; le live y est atténué). MESURÉ au banc (Whisper) :
     le son entier ne protège pas papa (sous le live, l'oreille ne rend que 0 à 10 % de ses mots, elle transcrit le live), le reste en
     rend 3 fois plus ; le son entier n'aurait fait que rendre le live. */
function decider(x, o = {}) {
  if (!x || !x.applique) return 'entier';
  if (x.voixMs >= VOIX_MS) return 'reste';
  return x.verdict && x.verdict.verdict === 'retour' && !o.papaRecent ? 'ecarte' : 'doux';
}
// une voix proche vue par la porte ET par le juge : un reste muet repasse alors par le son entier (dans le doute). MESURÉ au banc (live à 0,
// − 6, − 12 dB, 93 morceaux de pur retour, 15 de papa par-dessus) : la porte seule voit une « voix » dans la moitié des purs retours (40 ms
// et plus : ses erreurs de prédiction), et le repli rendait alors le live entier ; les deux ensemble : 19 % des purs retours, 87 % de papa
const voixVue = (x) => !!(x && x.voixMs >= VOIX_MS && x.jugement && x.jugement.voixMs >= VOIX_MS);

module.exports = { N, PAS, SR, MS_PAS, NB, EXCES_X, VOIX_REL, VOIX_PART, VOIX_MS, PART_MAX, RESSEMBLANCE_MIN, ALPHA, GARDE_MS, SOL,
  fft, spectre, assembler, juger, verdict, stft, istft, masque, appliquer, soustraire, decider, voixVue };

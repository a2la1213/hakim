/* (11/11, v2) une voix de synthèse pour les tests et le banc de son chant (aucun réseau, aucun modèle) : des mots séparés d'un blanc (comme
   sa voix Azure avec ses <break>), chaque syllabe une consonne (un bruit bref) puis une voyelle (les harmoniques de sa hauteur, deux formants),
   sa hauteur qui dérive comme une intonation parlée. Rend { wav (PCM 16 bits mono), sr, syllabes: [{ a, b, voyelle (échantillons), f0 }] }.
   Et une mesure de hauteur indépendante de celle du traitement (l'autocorrélation normalisée, 40 ms, à 24 kHz), et des trames de mélodie. */
'use strict';
const V = require('../chanter-voix.js');

function voixSynthetique(sylParMot, o = {}) {
  const sr = o.sr || 24000, f0 = o.f0 || 120, pause = o.pause_s ?? 0.26, dv = o.voyelle_s || 0.16, dc = o.consonne_s || 0.03;
  let g = o.graine || 99; const alea = () => { g = (g * 1103515245 + 12345) & 0x7fffffff; return g / 0x7fffffff; };
  const tot = sylParMot.reduce((n, k) => n + k, 0);
  const n = Math.round(sr * (0.1 + tot * (dv + dc + 0.03) + sylParMot.length * pause + 0.1)), x = new Float32Array(n), syl = [];
  let i = Math.round(sr * 0.1), ph = 0, k = 0;
  for (let w = 0; w < sylParMot.length; w++) {
    for (let s = 0; s < sylParMot[w]; s++, k++) {
      const a = i;
      for (let j = 0; j < sr * dc; j++, i++) x[i] += 0.06 * (alea() * 2 - 1) * Math.sin(Math.PI * j / (sr * dc));     // la consonne
      const v0 = i, nv = Math.round(sr * dv);
      const fs = f0 * (1 + 0.08 * Math.sin(k * 1.7)) ;                                                            // son intonation
      for (let j = 0; j < nv; j++, i++) {
        const f = fs * (1 + 0.03 * Math.sin(2 * Math.PI * 5 * j / sr)) * (1 - 0.06 * j / nv);
        ph += 2 * Math.PI * f / sr;
        let v = 0;
        for (let h = 1; h * f < 4000; h++) { const fh = h * f, am = 1 / (1 + ((fh - 700) / 250) ** 2) + 0.6 / (1 + ((fh - 1200) / 300) ** 2) + 0.05; v += am * Math.sin(h * ph); }
        const env = Math.min(1, j / (sr * 0.015)) * Math.min(1, (nv - j) / (sr * 0.03));
        x[i] += 0.12 * v * env;
      }
      syl.push({ a, b: i, voyelle: v0, f0: fs });
      i += Math.round(sr * 0.02);                                                                               // le creux entre deux syllabes
    }
    i += Math.round(sr * pause);
  }
  let m = 0; for (const v of x) m = Math.max(m, Math.abs(v));
  for (let j = 0; j < n; j++) x[j] = x[j] / m * 0.7 + 0.0005 * (alea() * 2 - 1);
  return { wav: V.ecrirePcm(x, sr), sr, syllabes: syl, x };
}
// la hauteur d'un passage, mesurée autrement que le traitement : l'autocorrélation normalisée (40 ms, toutes les 10 ms, à pleine résolution),
// le premier pic presque aussi haut que le meilleur (pas l'octave du dessous)
function hauteurMesuree(x, sr, a, b) {
  const W = Math.round(sr * 0.04), lmin = Math.floor(sr / 500), lmax = Math.ceil(sr / 60), out = [];
  for (let c = Math.max(0, a); c + W + lmax < Math.min(x.length, b + lmax); c += Math.round(sr * 0.01)) {
    let e0 = 0; for (let j = 0; j < W; j++) e0 += x[c + j] * x[c + j];
    if (e0 < 1e-5 * W) continue;
    const r = new Float64Array(lmax + 2);
    let best = 0;
    for (let l = lmin; l <= lmax; l++) { let s = 0, e1 = 0; for (let j = 0; j < W; j++) { s += x[c + j] * x[c + j + l]; e1 += x[c + j + l] * x[c + j + l]; } r[l] = s / Math.sqrt(e0 * e1 + 1e-12); if (r[l] > best) best = r[l]; }
    if (best < 0.6) continue;
    for (let l = lmin + 1; l < lmax; l++) if (r[l] >= 0.92 * best && r[l] >= r[l - 1] && r[l] >= r[l + 1]) {
      const den = r[l - 1] - 2 * r[l] + r[l + 1], lf = den < 0 ? l + 0.5 * (r[l - 1] - r[l + 1]) / den : l;
      out.push(sr / lf); break;
    }
  }
  const c = out.slice(Math.floor(out.length * 0.2), Math.ceil(out.length * 0.8));
  return c.length ? V.mediane(c) : 0;
}
module.exports = { voixSynthetique, hauteurMesuree };

#!/usr/bin/env node
/* (11/11, Ahmed : « un bouton pour qu'il n'entende pas le retour du micro ») MESURE, en lecture seule, sur son-flux.jsonl : pendant un live joué
   sur le haut-parleur, le micro suit-il l'enveloppe de ce que joue le téléphone (son intérieur), à un retard stable ? Fenêtres de 30 s (pas
   de 10 s) ; corrélation des logarithmes des niveaux (trames de 100 ms) au meilleur retard de -1,5 à +1,5 s ; TÉMOIN : le même calcul avec le
   téléphone décalé de 10 et 20 min (rien ne peut s'y expliquer, sauf par hasard).
   Usage : node mesure/retour-micro-journaux.js [son-flux.jsonl] [debut HH:MM] [fin HH:MM] */
'use strict';
const fs = require('fs');
const path = require('path');
const F = process.argv[2] || path.join(process.env.HOME, 'AIOS/jarvis/son-flux.jsonl');
const JOUR = '2026-11-11';
const heure = (h) => Date.parse(`${JOUR}T${h}:00+01:00`);
const DE = heure(process.argv[3] || '05:36'), A = heure(process.argv[4] || '08:02');
const tel = [], mic = [];
for (const l of fs.readFileSync(F, 'utf8').split('\n')) {
  if (!l) continue;
  let o; try { o = JSON.parse(l); } catch (_) { continue; }
  if (!o || !Array.isArray(o.l) || (o.s !== 'telephone' && o.s !== 'micro')) continue;
  const p = Number(o.p) || 100;
  o.l.forEach((v, i) => { const t = o.t + i * p; if (t >= DE - 1300e3 && t <= A + 60e3) (o.s === 'telephone' ? tel : mic).push({ t, v: Number(v[0]) || 0 }); });
}
tel.sort((a, b) => a.t - b.t); mic.sort((a, b) => a.t - b.t);
const EPS = 1e-3;
function valeur(l, t) {                                   // interpolée ; null hors des trames (ou dans un trou de plus de 250 ms)
  let a = 0, b = l.length - 1;
  if (!l.length || t < l[0].t || t > l[b].t) return null;
  while (b - a > 1) { const m = (a + b) >> 1; if (l[m].t <= t) a = m; else b = m; }
  if (l[b].t - l[a].t > 250) return null;
  const k = l[b].t === l[a].t ? 0 : (t - l[a].t) / (l[b].t - l[a].t);
  return l[a].v * (1 - k) + l[b].v * k;
}
function correlation(xs, ys) {
  const n = xs.length; if (n < 40) return null;
  let sx = 0, sy = 0; for (let i = 0; i < n; i++) { sx += xs[i]; sy += ys[i]; }
  const mx = sx / n, my = sy / n; let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < n; i++) { num += (xs[i] - mx) * (ys[i] - my); dx += (xs[i] - mx) ** 2; dy += (ys[i] - my) ** 2; }
  return dx > 1e-9 && dy > 1e-9 ? num / Math.sqrt(dx * dy) : null;
}
// le meilleur retard du micro sur le téléphone dans [t0, t0 + 30 s] ; decal : le téléphone pris decal ms plus tôt (témoin)
function fenetre(t0, decal) {
  const ref = tel.filter(x => x.t >= t0 - decal && x.t < t0 - decal + 30000);
  if (ref.length < 200) return null;
  const actifs = ref.filter(x => x.v > 0.01).length / ref.length;
  if (actifs < 0.3) return null;                          // le téléphone presque muet : rien à mesurer
  let best = { c: -2, lag: 0 };
  for (let lag = -1500; lag <= 1500; lag += 20) {
    const xs = [], ys = [];
    for (const x of ref) { const y = valeur(mic, x.t + decal + lag); if (y !== null) { xs.push(Math.log(x.v + EPS)); ys.push(Math.log(y + EPS)); } }
    const c = correlation(xs, ys);
    if (c !== null && c > best.c) best = { c, lag };
  }
  return best.c > -2 ? best : null;
}
const res = { reel: [], t10: [], t20: [] };
for (let t0 = DE; t0 + 30000 <= A; t0 += 10000) {
  const r = fenetre(t0, 0); if (!r) continue;
  res.reel.push({ t0, ...r });
  const a = fenetre(t0, 600e3), b = fenetre(t0, 1200e3);
  if (a) res.t10.push({ t0, ...a }); if (b) res.t20.push({ t0, ...b });
}
const part = (l, s) => (l.length ? Math.round(100 * l.filter(x => x.c >= s).length / l.length) : 0);
const med = (xs) => { const s = xs.slice().sort((a, b) => a - b); return s.length ? s[s.length >> 1] : null; };
console.log(`${new Date(DE).toTimeString().slice(0, 5)}-${new Date(A).toTimeString().slice(0, 5)} : trames tel ${tel.length}, micro ${mic.length}`);
for (const k of ['reel', 't10', 't20']) {
  const l = res[k];
  console.log(`${k.padEnd(4)} fenêtres ${String(l.length).padStart(4)} · corrélation médiane ${med(l.map(x => x.c))?.toFixed(2)} · ≥0,5 : ${part(l, 0.5)} % · ≥0,6 : ${part(l, 0.6)} % · ≥0,7 : ${part(l, 0.7)} %`);
}
const forts = res.reel.filter(x => x.c >= 0.6);
console.log(`retards des fenêtres réelles ≥ 0,6 : médiane ${med(forts.map(x => x.lag))} ms, quartiles ${(() => { const s = forts.map(x => x.lag).sort((a, b) => a - b); return s.length ? `${s[s.length >> 2]} / ${s[(3 * s.length) >> 2]}` : '-'; })()}`);
if (process.env.DETAIL) for (const x of res.reel) console.log(new Date(x.t0).toTimeString().slice(0, 8), x.c.toFixed(2), x.lag);
module.exports = { valeur, correlation };

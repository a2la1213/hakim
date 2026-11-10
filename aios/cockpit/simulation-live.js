#!/usr/bin/env node
'use strict';
/* (10/11, Ahmed : « le tout en real time continu pour qu'il ait le temps chaque seconde d'évaluer » ; Nour : « mesure le coût, appels par minute
   en live ») simulation SANS aucun appel à Claude : son garde du live (live.js) rejoué sur un vrai live, à partir de son fil long
   (jarvis/fil-stimuli-long.jsonl : les mots du téléphone, qui y parle, les mots de papa, la musique) et des trames du téléphone
   (jarvis/son-flux.jsonl : sa pause). Rien n'est écrit. Par défaut, le live du 09/11 de 23:00 à 00:10.
   Hypothèses, toutes du côté du coût le plus haut : chaque appel répond « DIRE » (la conversation avec cette voix s'ouvre), sa voix et sa
   tête sont toujours libres, la Conversation toujours ouverte ; les mots du téléphone arrivent 3 s après leur instant (la médiane mesurée,
   fil_delais « telephone ») ; papa « parle » 2,5 s après chacun de ses mots au fil (le micro y met aussi le live entendu par le haut-parleur).
   node simulation-live.js [debut ISO] [fin ISO] [pas_ms] */
const fs = require('fs');
const path = require('path');
const os = require('os');
const L = require('./live.js');

const JARVIS = process.env.JARVIS_DIR || path.join(os.homedir(), 'AIOS', 'jarvis');
const debut = Date.parse(process.argv[2] || '2026-11-09T23:00:00+01:00'), fin = Date.parse(process.argv[3] || '2026-11-10T00:10:00+01:00');
const pas = Number(process.argv[4]) || 1000, ARRIVEE_MS = 3000;
const lignes = (f) => fs.readFileSync(path.join(JARVIS, f), 'utf8').split('\n').filter(Boolean).map(l => { try { return JSON.parse(l); } catch (_) { return null; } }).filter(Boolean);

const fil = lignes('fil-stimuli-long.jsonl').filter(o => o.t >= debut - 60000 && o.t <= fin);
const trames = [];
for (const o of lignes('son-flux.jsonl')) if (o.s === 'telephone' && o.t >= debut - 60000 && o.t <= fin) o.l.forEach((v, i) => trames.push({ t: o.t + i * o.p, v }));
trames.sort((a, b) => a.t - b.t);
const mots = fil.filter(o => o.s === 'telephone').map(o => ({ ...o, arrivee: o.t + ARRIVEE_MS })).sort((a, b) => a.arrivee - b.arrivee);
const qui = fil.filter(o => o.s === 'qui_telephone').map(o => ({ t: o.t, v: String(o.x).replace(/ parle\b.*$/, '').trim() }));
const papa = fil.filter(o => o.s === 'papa').map(o => o.t);
const musique = fil.filter(o => o.s === 'musique_telephone').map(o => o.t).sort((a, b) => a - b);

// sa pause dans les trames (comme pauseDansLesTrames, server.js) ; sinon 2 s sans un mot ni une voix
function pause(t, dernierMot, dernierQui) {
  const l = trames.filter(x => x.t > t - 10000 && x.t <= t);
  const motsPause = t - dernierMot >= 2000 && t - dernierQui >= 2000;
  if (!l.length || t - l[l.length - 1].t > 2500) return motsPause;
  const niv = l.map(x => Number(x.v[0]) || 0), forts = niv.filter(v => v >= 0.003).sort((a, b) => a - b);
  const seuil = Math.max(0.003, forts.length ? 0.15 * forts[Math.floor(forts.length / 2)] : 0);
  let k = l.length; while (k > 0 && niv[k - 1] < seuil) k--;
  return (k < l.length && l[l.length - 1].t - l[k].t + 100 >= 400) || motsPause;
}
const e = L.creer();
let im = 0, accum = [], cle = 0, dernierQui = 0;
const minutes = [];
for (let t = debut; t <= fin; t += 250) {
  // ses mots arrivés jusqu'ici : un bloc qui grandit (200 mots au plus, puis le suivant)
  let neuf = false;
  while (im < mots.length && mots[im].arrivee <= t) { accum.push(mots[im].x); im++; neuf = true; if (accum.length >= 200) { L.recevoir(e, { cle: `c${cle}`, texte: accum.join(' '), fin: true, qui: quiA(t) }, t); accum = []; cle++; } }
  if (neuf && accum.length) L.recevoir(e, { cle: `c${cle}`, texte: accum.join(' '), qui: quiA(t) }, t);
  for (const q of qui) if (q.t + ARRIVEE_MS <= t && q.t > dernierQui) dernierQui = q.t;
  const pp = papa.some(x => x <= t && t - x < 2500);
  for (const x of papa) if (x <= t && t - x < 250) { const w = fil.filter(o => o.s === 'papa' && Math.abs(o.t - x) < 4000).map(o => o.x).join(' '); L.papaDit(e, w, t); }
  const mus = musique.filter(x => x <= t && t - x < 600000);
  let md = null;
  if (mus.length && t - mus[mus.length - 1] <= 6000) { md = mus[mus.length - 1]; for (let k = mus.length - 1; k > 0 && mus[k] - mus[k - 1] < 20000; k--) md = mus[k - 1]; }
  const d = L.evaluer(e, { actif: true, pause: pause(t, e.dernierMot, dernierQui + ARRIVEE_MS), papaParle: pp, tuParles: false, occupe: false, forfait: false, placeLibre: true,
    derniereParole: Math.max(0, ...papa.filter(x => x <= t).slice(-1)), musique: md ? { joue: true, debut: md } : { joue: false } }, t, { pas_ms: pas });
  if (d.action === 'appeler') { L.repondu(e, 'DIRE : (simulé)', t + 1500); }
  else if (d.action === 'dire') L.dit(e, d, t);
  if ((t - debut) % 60000 === 0 && t > debut) minutes.push(L.minute(e, t));
}
function quiA(t) { let v = ''; for (const q of qui) if (q.t + ARRIVEE_MS <= t && t - q.t - ARRIVEE_MS < 8000) v = q.v; return v; }
const appels = minutes.map(m => m.appels_total), motifs = {};
for (const m of minutes) for (const [k, n] of Object.entries(m.appels)) motifs[k] = (motifs[k] || 0) + n;
const tot = appels.reduce((a, b) => a + b, 0), evals = minutes.reduce((a, m) => a + m.evaluations, 0), phrases = minutes.reduce((a, m) => a + m.phrases, 0);
const refus = {}; for (const m of minutes) for (const [k, n] of Object.entries(m.refus)) refus[k] = (refus[k] || 0) + n;
console.log(JSON.stringify({ de: new Date(debut).toString().slice(0, 24), a: new Date(fin).toString().slice(0, 24), pas_ms: pas, minutes: minutes.length,
  evaluations: evals, phrases_du_telephone: phrases, appels: tot, par_minute_moyen: Math.round((tot / Math.max(1, minutes.length)) * 100) / 100,
  par_minute_max: Math.max(0, ...appels), minutes_sans_appel: appels.filter(x => !x).length, motifs, refus, dits: minutes.reduce((a, m) => a + m.dits, 0),
  expirees: minutes.reduce((a, m) => a + m.expirees, 0) }, null, 1));

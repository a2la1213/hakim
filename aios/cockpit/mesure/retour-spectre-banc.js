#!/usr/bin/env node
/* (11/11) LE BANC du juge en spectre (retour-spectre.js), papa par-dessus le live : le même live simulé que mesure/retour-micro-banc.js (ses voix
   de say, le haut-parleur calé sur le vrai, le micro, son gain automatique, les morceaux découpés comme la page), mais le juge reçoit le SON de
   l'intérieur (comme les blocs que l'appli envoie au cockpit), à l'heure du téléphone (captée 30 ms après le mélange).
   TÉMOIN : les mêmes morceaux jugés avec le son de l'intérieur de 97 s plus loin.
   Compte : les morceaux de pur retour écartés ; les phrases de papa intactes (aucun morceau écarté qui porte 100 ms de sa voix) ; le temps.
   Usage : BANC_VOIX=<dossier des voix> node mesure/retour-spectre-banc.js */
'use strict';
const B = require('./retour-micro-banc.js');
const S = require('../retour-spectre.js');
const SR = 16000;
const rmsDe = (x, a, b) => { let s = 0; for (let i = Math.max(0, a); i < Math.min(x.length, b); i++) s += x[i] * x[i]; return Math.sqrt(s / Math.max(1, b - a)); };

function banc(cfg, o = {}) {
  const s = B.simuler(cfg);
  const niveauPapa = 0.08 * Math.pow(10, (cfg.papaDb || 0) / 20);
  const papaActif = (i) => rmsDe(s.papa, i, i + 320) * s.kp > 0.25 * niveauPapa;
  // son intérieur : des blocs de 8 s, à l'heure du téléphone (captés 30 ms après le mélange) ; le témoin : les mêmes, 97 s plus tôt
  const blocs = [], temoin = [];
  for (let a = 0; a < s.live.length; a += 8 * SR) {
    const pcm = s.live.slice(a, a + 8 * SR);
    blocs.push({ t0: a / 16 + 30, pcm });
    temoin.push({ t0: a / 16 + 30 - 97000, pcm });
  }
  let prior = null, papaFin = 0;
  const morceaux = [], ms = [];
  for (const m of s.morceaux) {
    const t0 = m.a / 16, pcm = s.mic.slice(m.a, m.b);
    const tA = process.hrtime.bigint();
    const j = S.juger({ pcm, t0 }, blocs.filter(b => b.t0 + 8000 > t0 - 2000 && b.t0 < t0 + pcm.length / 16 + 2000), prior);
    let v = S.verdict(j, o);
    // comme au cockpit : un morceau qui suit de moins de 2 s un morceau où une voix proche dépassait le retour reste en doute (« papa vient de parler »)
    if (!o.sans_suite && v.verdict === 'retour' && papaFin && t0 - papaFin < 2000) v = { verdict: 'doute', raison: 'papa_vient_de_parler' };
    if (v.raison === 'voix_au_dessus') papaFin = Math.max(papaFin, t0 + pcm.length / 16);
    ms.push(Number(process.hrtime.bigint() - tA) / 1e6);
    const jt = S.juger({ pcm, t0 }, temoin.filter(b => b.t0 + 8000 > t0 - 2000 && b.t0 < t0 + pcm.length / 16 + 2000), prior);
    const vt = S.verdict(jt, o);
    // le retard appris au fil : seulement d'un morceau qui ressemble nettement (comme au cockpit)
    if (j && j.retardMs !== null && j.net && j.ressemblance >= 0.6) prior = prior === null ? j.retardMs : Math.round(0.7 * prior + 0.3 * j.retardMs);
    let papaMs = 0, liveMs = 0;
    const dl = Math.round(cfg.retardMs * 16);
    for (let i = m.a; i + 320 <= m.b; i += 320) { if (papaActif(i)) papaMs += 20; if (rmsDe(s.live, i - dl, i - dl + 320) > 0.01) liveMs += 20; }
    const vrai = papaMs === 0 ? 'retour' : papaMs >= 100 ? (liveMs >= 200 ? 'papaSur' : 'papaSeul') : 'frontiere';
    morceaux.push({ a: m.a, b: m.b, vrai, j, v, vt });
  }
  const phrases = s.papaPhrases.map(p => {
    let liveMs = 0, n = 0; for (let i = p.a; i + 320 <= p.b; i += 320) { n += 20; if (rmsDe(s.live, i, i + 320) > 0.01) liveMs += 20; }
    const abimee = morceaux.some(x => x.v.verdict === 'retour' && (() => { let k = 0; for (let i = Math.max(x.a, p.a); i + 320 <= Math.min(x.b, p.b); i += 320) if (papaActif(i)) k += 20; return k >= 100; })());
    return { sur: liveMs >= n * 0.5, abimee };
  });
  return { morceaux, phrases, ms };
}
const pc = (a, b) => (b ? `${Math.round(100 * a / b)} %` : '-');
function grille(o = {}, hp = 'vrai', niveaux = [-12, -8, -6, 0, 6], graines = [1], duree = 180) {
  const lignes = [], total = {};
  for (const papaDb of niveaux) {
    const t = { retour: 0, ecartes: 0, doute: 0, temoin: 0, papa: 0, papaEcartes: 0, phrases: 0, abimees: 0, sur: 0, surAbimees: 0, ms: [], raisons: {} };
    for (const retardMs of [40, 150, 300]) for (const agcDb of [0, 3]) for (const graine of graines) {
      const r = banc({ graine: graine + retardMs + agcDb * 10 + papaDb * 100, retardMs, papaDb, agcDb, duree, hp }, o);
      for (const m of r.morceaux) {
        const k = `${m.vrai}:${m.v.verdict}:${m.v.raison}`; t.raisons[k] = (t.raisons[k] || 0) + 1;
        if (m.vrai === 'retour') { t.retour++; if (m.v.verdict === 'retour') t.ecartes++; if (m.v.verdict === 'doute') t.doute++; if (m.vt.verdict === 'retour') t.temoin++; }
        if (m.vrai === 'papaSur' || m.vrai === 'papaSeul') { t.papa++; if (m.v.verdict === 'retour') t.papaEcartes++; }
      }
      for (const p of r.phrases) { t.phrases++; if (p.abimee) t.abimees++; if (p.sur) { t.sur++; if (p.abimee) t.surAbimees++; } }
      t.ms.push(...r.ms);
    }
    total[papaDb] = t;
    const s = t.ms.slice().sort((a, b) => a - b);
    lignes.push(`papa ${papaDb >= 0 ? '+' : ''}${papaDb} dB : morceaux de pur retour ${t.retour}, écartés ${pc(t.ecartes, t.retour)} (en doute ${pc(t.doute, t.retour)}) · témoin écartés ${pc(t.temoin, t.retour)} | `
      + `phrases de papa ${t.phrases}, intactes ${pc(t.phrases - t.abimees, t.phrases)} (par-dessus le live : ${t.sur}, intactes ${pc(t.sur - t.surAbimees, t.sur)}) ; morceaux avec sa voix écartés ${t.papaEcartes}/${t.papa} | `
      + `juge ${s[s.length >> 1].toFixed(1)} ms (p95 ${s[Math.floor(s.length * 0.95)].toFixed(1)})`);
  }
  return { total, lignes };
}
if (require.main === module) {
  const hp = process.env.HP || 'vrai', o = process.env.REGLAGES ? JSON.parse(process.env.REGLAGES) : {};
  const g = grille(o, hp, process.env.NIVEAUX ? process.env.NIVEAUX.split(',').map(Number) : undefined, (process.env.GRAINES || '1').split(',').map(Number), Number(process.env.DUREE) || 180);
  console.log(`== le juge en spectre (haut-parleur ${hp}) ${JSON.stringify(o)}`);
  for (const l of g.lignes) console.log(l);
  if (process.env.DETAIL) for (const [db, t] of Object.entries(g.total)) console.log(db, JSON.stringify(Object.entries(t.raisons).sort((a, b) => b[1] - a[1])));
}
module.exports = { banc, grille };

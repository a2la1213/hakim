#!/usr/bin/env node
/* (11/11) MESURE en lecture seule : le juge du retour (retour-micro.js) rejoué sur les morceaux du micro d'un live, avec les journaux du jour.
   - les trames : son-flux.jsonl (micro de la page, intérieur de l'appli), à l'heure du Mac (le transport de chaque lot y ajoute un flou de
     100-300 ms ; en service, le juge lit l'heure du téléphone : tb) ;
   - le chemin appris toutes les 10 s sur les 30 s d'avant (comme au cockpit) ;
   - les morceaux : voix-diagnostic.jsonl (voix_papa_azure + transcription_serveur : la fin, la durée du son, qui parlait selon l'oreille des voix) ;
     leurs trames : celles du micro de son-flux dans leur durée (des instantanés de 43 ms, pas l'enveloppe exacte du WAV qu'aura le cockpit) ;
   - TÉMOIN A : tout refait avec l'intérieur décalé de 10 min (chemin compris) ; TÉMOIN B : le vrai chemin, mais l'intérieur décalé au jugement.
   Étiquettes (l'oreille des voix) : « papa » (verdict ahmed, score ≥ 0,6, lui seul) ; « autres » (aucune voix de papa, ni « papa ? ») ; « mêlé ».
   Usage : node mesure/retour-micro-morceaux.js [debut HH:MM] [fin HH:MM] */
'use strict';
const fs = require('fs'), path = require('path');
const R = require('./retour-enveloppe.js');
const J = path.join(process.env.HOME, 'AIOS/jarvis');
const heure = (h) => Date.parse(`2026-11-11T${h}:00+01:00`);
const DE = heure(process.argv[2] || '08:09'), A = heure(process.argv[3] || '09:19');
const DECAL = 600e3;
const tel = [], mic = [];
for (const l of fs.readFileSync(path.join(J, 'son-flux.jsonl'), 'utf8').split('\n')) {
  if (!l) continue; let o; try { o = JSON.parse(l); } catch (_) { continue; }
  if (!o || !Array.isArray(o.l) || (o.s !== 'telephone' && o.s !== 'micro')) continue;
  o.l.forEach((v, i) => { const t = o.t + i * (o.p || 100) + 50; if (t >= DE - DECAL - 60e3 && t <= A + 60e3) (o.s === 'telephone' ? tel : mic).push({ t, v: Number(v[0]) || 0 }); });
}
tel.sort((a, b) => a.t - b.t); mic.sort((a, b) => a.t - b.t);
const decale = (d) => tel.map(x => ({ t: x.t + d, v: x.v }));
const telB = decale(DECAL);
// les chemins appris (causal) : toutes les 10 s, sur les 30 s d'avant
function chemins(ref) {
  const out = [];
  for (let t = DE - 30e3; t <= A; t += 10e3) {
    const c = R.apprendreChemin(ref.filter(x => x.t >= t - 30e3 && x.t < t), mic.filter(x => x.t >= t - 31.5e3 && x.t < t + 1.5e3));
    if (c) out.push({ ...c, ts: t });
  }
  return out;
}
const CH = chemins(tel), CHA = chemins(telB);
const cheminA = (liste, t) => { let c = null; for (const x of liste) { if (x.ts <= t) c = x; else break; } return c; };
// les morceaux du micro
const D = fs.readFileSync(path.join(J, 'voix-diagnostic.jsonl'), 'utf8').trim().split('\n').map(l => { try { return JSON.parse(l); } catch (_) { return null; } }).filter(o => o && o.t >= DE && o.t <= A);
const morceaux = [];
for (let i = 0; i < D.length; i++) {
  const v = D[i]; if (v.e !== 'voix_papa_azure') continue;
  const s = D.slice(i, i + 6).find(o => o.e === 'transcription_serveur' && Math.abs(o.t - v.t) < 100);
  if (!s || !(s.octets > 3244)) continue;
  const dur = (s.octets - 44) / 32000 * 1000, fin = s.t - s.ms - 300;
  const loc = Array.isArray(v.locuteurs) ? v.locuteurs : [];
  const avecPapa = loc.some(l => /^(ahmed|papa ?\??)$/i.test(l));
  const etiquette = v.verdict === 'ahmed' && v.score >= 0.6 && loc.length === 1 ? 'papa' : !avecPapa ? 'autres' : 'mêlé';
  morceaux.push({ debut: fin - dur, fin, dur, etiquette, voix: { verdict: v.verdict, score: v.score, locuteurs: loc } });
}
const comptes = {};
const noter = (cas, etiquette, verdict) => { const k = `${cas}|${etiquette}`; comptes[k] = comptes[k] || { retour: 0, doute: 0, garde: 0, n: 0, raisons: {} }; comptes[k][verdict.verdict]++; comptes[k].n++; comptes[k].raisons[verdict.raison] = (comptes[k].raisons[verdict.raison] || 0) + 1; };
const t0 = process.hrtime.bigint();
let juges = 0;
for (const m of morceaux) {
  const trames = mic.filter(x => x.t >= m.debut && x.t < m.fin);
  if (trames.length < 3) continue;
  for (const [cas, ref, liste, voix] of [['reel', tel, CH, m.voix], ['reel_sans_oreille', tel, CH, null], ['temoinA', telB, CHA, null], ['temoinB', telB, CH, null]]) {
    const c = cheminA(liste, m.debut);
    noter(cas, m.etiquette, R.jugerMorceau({ mic: trames, tel: ref.filter(x => x.t >= m.debut - 2500 && x.t <= m.fin + 2500), chemin: c, voix, maintenant: m.debut }));
    juges++;
  }
}
const ms = Number(process.hrtime.bigint() - t0) / 1e6;
console.log(`${new Date(DE).toTimeString().slice(0, 5)}-${new Date(A).toTimeString().slice(0, 5)} : ${morceaux.length} morceaux du micro (papa ${morceaux.filter(m => m.etiquette === 'papa').length}, autres ${morceaux.filter(m => m.etiquette === 'autres').length}, mêlés ${morceaux.filter(m => m.etiquette === 'mêlé').length}) ; chemins appris : ${CH.length} (témoin A : ${CHA.length}) sur ${Math.round((A - DE) / 10e3)} pas`);
for (const k of Object.keys(comptes).sort()) { const c = comptes[k]; console.log(`${k.padEnd(28)} n=${String(c.n).padStart(3)}  écartés ${String(c.retour).padStart(3)} · doute ${String(c.doute).padStart(3)} · gardés ${String(c.garde).padStart(3)}   ${JSON.stringify(c.raisons)}`); }
console.log(`temps du juge : ${(ms / Math.max(1, juges)).toFixed(2)} ms par morceau (${juges} jugements)`);

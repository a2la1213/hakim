#!/usr/bin/env node
/* (11/11) LE BILAN du retour du micro après un live, en lecture seule (voix-diagnostic.jsonl) : combien de morceaux du micro écartés (le live
   revenu), en doute, gardés, et pourquoi ; le temps ajouté à ta voix (attente du son de l'intérieur + jugement) ; les mots de chaque morceau
   écarté, pour vérifier qu'aucun n'était papa.
   Usage : node mesure/retour-micro-bilan.js [depuis HH:MM] [jusqu'à HH:MM] [jour AAAA-MM-JJ] */
'use strict';
const fs = require('fs'), path = require('path');
const F = path.join(process.env.HOME, 'AIOS/jarvis/voix-diagnostic.jsonl');
const jour = process.argv[4] || new Date().toISOString().slice(0, 10);
const h = (x, d) => (x ? Date.parse(`${jour}T${x}:00`) : d);
const DE = h(process.argv[2], 0), A = h(process.argv[3], Infinity);
const L = fs.readFileSync(F, 'utf8').split('\n').map(l => { try { return JSON.parse(l); } catch (_) { return null; } })
  .filter(o => o && /^retour_(ecarte|en_doute|garde)$/.test(o.e) && o.t >= DE && o.t <= A);
const q = (xs, p) => { const s = xs.filter(Number.isFinite).sort((a, b) => a - b); return s.length ? s[Math.min(s.length - 1, Math.floor(p * s.length))] : '-'; };
const par = (e) => L.filter(o => o.e === e);
console.log(`${L.length} morceaux du micro jugés : écartés ${par('retour_ecarte').length}, en doute ${par('retour_en_doute').length}, gardés ${par('retour_garde').length}`);
for (const e of ['retour_ecarte', 'retour_en_doute', 'retour_garde']) {
  const r = {}; for (const o of par(e)) r[o.raison] = (r[o.raison] || 0) + 1;
  console.log(`  ${e} : ${JSON.stringify(r)}`);
}
const ajout = L.map(o => (Number(o.attente_ms) || 0) + (Number(o.ms) || 0));
console.log(`temps ajouté (attente + jugement) : médiane ${q(ajout, 0.5)} ms, p90 ${q(ajout, 0.9)} ms, max ${q(ajout, 1)} ms`);
const garde = par('retour_garde').map(o => (Number(o.attente_ms) || 0) + (Number(o.ms) || 0));
console.log(`  sur les morceaux gardés (ta voix) : médiane ${q(garde, 0.5)} ms, p90 ${q(garde, 0.9)} ms`);
const vif = Math.max(0, ...L.map(o => Number(o.vif_ecartes) || 0));
console.log(`mots vifs écartés (depuis le démarrage du cockpit) : ${vif}`);
console.log('\nles morceaux écartés (à relire : aucun ne doit être papa) :');
for (const o of par('retour_ecarte')) console.log(`  ${new Date(o.t).toTimeString().slice(0, 8)}  ${String(o.duree_ms).padStart(5)} ms  r=${o.ressemblance} part=${o.part} voix=${o.voix_ms} ms  « ${o.texte || ''} »`);

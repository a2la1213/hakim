/* (09/11, Ahmed à 17:24 : « que les données de ma montre soient directement récupérées depuis l'APK de la montre […] et qu'elles te
   soient directement transférées, avec rafraîchissement à la seconde ») Le cœur de papa en direct, depuis le capteur de sa montre
   (appli montre 0.28, CoeurPapa) : en lecture seule, étiqueté « mesure, pas un diagnostic ».
   - POST /api/corps/coeur-montre : un lot { nature, ecran, mesures: [{ t, bpm, p }] } (1 s écran allumé, 5 s éteint), ou, une fois au
     démarrage, ce que la montre sait faire ({ capacite, capteur, fabricant, en_fond }) ;
   - chaque lot reçu s'ajoute à jarvis/montre-coeur.jsonl (en ajout seul, comme ses autres mesures) ; les 10 dernières minutes restent
     en mémoire pour sa situation (blocSituation) et GET /api/corps/coeur-montre ;
   - le sommeil, l'oxygène et les pas restent à Health Connect (le téléphone, /api/capteurs).
   node --test test-coeur-montre.js */
'use strict';
const fs = require('node:fs');

const NATURE = 'mesure, pas un diagnostic';
const BPM_MIN = 25, BPM_MAX = 250, LOT_MAX = 120, GARDE_MS = 10 * 60000, FRAIS_MS = 120000, PASSE_MS = 15 * 60000, FUTUR_MS = 120000;

/** Un lot de la montre, nettoyé : seules les mesures d'un cœur, à leur heure, sans contact jeté ; null s'il n'y a rien à garder. */
function lotDe(q, maintenant) {
  if (!q || typeof q !== 'object') return null;
  const mesures = [];
  for (const m of Array.isArray(q.mesures) ? q.mesures.slice(-LOT_MAX) : []) {
    if (!m || typeof m !== 'object') continue;
    const t = Number(m.t), bpm = Number(m.bpm), p = Number(m.p);
    if (!Number.isFinite(t) || t < maintenant - PASSE_MS || t > maintenant + FUTUR_MS) continue;
    if (!Number.isFinite(bpm) || bpm < BPM_MIN || bpm > BPM_MAX) continue;
    if (!Number.isInteger(p) || p < 0 || p > 3) continue;      // -1 : la montre ne touche pas la peau
    mesures.push({ t: Math.round(t), bpm: Math.round(bpm), p });
  }
  const mot = (x, n) => (typeof x === 'string' ? x.replace(/[^\p{L}\p{N} ._()-]/gu, '').slice(0, n) : null);
  const capacite = ['aucun', 'normal', 'réveil'].includes(q.capacite)
    ? { capacite: q.capacite, capteur: mot(q.capteur, 80), fabricant: mot(q.fabricant, 60), en_fond: q.en_fond === true } : null;
  if (!mesures.length && !capacite) return null;
  return { mesures, ecran: q.ecran === true, capacite };
}

function creer({ fichier, horloge = Date.now } = {}) {
  let recentes = [];                                           // les 10 dernières minutes, dans l'ordre
  let capacite = null, recuA = 0;

  function recevoir(q) {
    const maintenant = horloge(), lot = lotDe(q, maintenant);
    if (!lot) return { ok: false, erreur: 'mesures illisibles' };
    if (lot.capacite) capacite = { ...lot.capacite, t: maintenant };
    if (lot.mesures.length) {
      const vues = new Set(recentes.map((m) => m.t));
      for (const m of lot.mesures) if (!vues.has(m.t)) recentes.push(m);   // un lot renvoyé (réseau coupé) ne compte pas deux fois
      recentes.sort((a, b) => a.t - b.t);
      recentes = recentes.filter((m) => m.t >= maintenant - GARDE_MS);
      recuA = maintenant;
    }
    if (fichier) try {
      fs.appendFileSync(fichier, JSON.stringify({ ts: maintenant, nature: NATURE, ecran: lot.ecran, ...(lot.capacite ? { capacite: lot.capacite } : {}),
        mesures: lot.mesures }) + '\n', { mode: 0o600 });
    } catch (_) {}
    return { ok: true, gardees: lot.mesures.length };
  }

  /** La dernière mesure fraîche (2 min au plus), et ce qu'en disent les 5 dernières minutes ; null sinon. */
  function derniere(maintenant = horloge()) {
    const d = recentes[recentes.length - 1];
    if (!d || maintenant - d.t > FRAIS_MS) return null;
    const cinq = recentes.filter((m) => m.t >= maintenant - 5 * 60000).map((m) => m.bpm);
    return { bpm: d.bpm, p: d.p, age_s: Math.max(0, Math.round((maintenant - d.t) / 1000)), min5: Math.min(...cinq), max5: Math.max(...cinq), n5: cinq.length };
  }

  /** Sa phrase pour la situation de Hakim (des données, jamais un diagnostic) ; '' sans mesure fraîche. */
  function texte(maintenant = horloge()) {
    const d = derniere(maintenant);
    if (!d) return '';
    const plage = d.n5 >= 3 && d.max5 > d.min5 ? `, entre ${d.min5} et ${d.max5} sur 5 min` : '';
    return `cœur ${d.bpm} bpm il y a ${d.age_s} s${plage}${d.p === 0 ? ' (lecture peu fiable)' : ''} — le capteur de son poignet, `
      + `en direct ; une ${NATURE}`;
  }

  /** Ce qui change vraiment (par 5 bpm) : la situation ne le redit pas à chaque tour pour une seconde de plus. */
  function cle(maintenant = horloge()) {
    const d = derniere(maintenant);
    return d ? `${Math.round(d.bpm / 5)}|${Math.round(d.min5 / 5)}|${Math.round(d.max5 / 5)}|${d.p === 0 ? 0 : 1}` : null;
  }

  /** GET : la dernière, la plage, la capacité de la montre, les mesures des 10 dernières minutes. */
  function vue(maintenant = horloge()) {
    return { nature: NATURE, derniere: derniere(maintenant), capacite, recu_il_y_a_s: recuA ? Math.round((maintenant - recuA) / 1000) : null,
      mesures: recentes.filter((m) => m.t >= maintenant - GARDE_MS) };
  }

  return { recevoir, derniere, texte, cle, vue };
}

module.exports = { creer, lotDe, NATURE };

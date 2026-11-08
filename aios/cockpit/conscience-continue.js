/* (07/11, Ahmed : « j'aimerais qu'il tourne chaque milliseconde, et qu'à chaque seconde il soit conscient et décide de ce qu'il pense, fait
   ou sollicite » ; il a choisi Mini Hakim) sa conscience continue, la logique pure. Chaque seconde, le cockpit regarde son présent (le fil :
   les mots de papa, ce qu'il entend, ce qu'il ressent) ; s'il y a du neuf, Mini Hakim décide en une ligne : RIEN, PENSER, FAIRE ou SOLLICITER.
   Une décision à la fois, 2 s au moins entre deux, 20 par minute au plus (son forfait). Penser passe toujours (montré, gardé pour la suite) ;
   solliciter papa attend que papa se taise et que sa tête soit libre, 90 s au moins entre deux ; faire, 3 min. Ce qui attend reste une pensée. */
'use strict';

const PAS_MS = 2000, PAR_MINUTE = 20, ENTRE_SOLLICITATIONS_MS = 90_000, ENTRE_ACTES_MS = 180_000;

function etatInitial() {
  return { enVol: false, signature: 0, derniere: -Infinity, appels: [], sollicitationA: -Infinity, acteA: -Infinity, pensees: [] };
}

function lireDecision(texte) {
  const t = String(texte || '').replace(/[*_`]/g, '').trim();
  const m = /^\s*(RIEN|PENSER|FAIRE|SOLLICITER)\b\s*:?\s*([\s\S]*)$/i.exec(t.split('\n').find(l => l.trim()) || '');
  if (!m) return { genre: 'rien', texte: '' };
  const genre = m[1].toLowerCase(), dit = m[2].replace(/\s+/g, ' ').trim().slice(0, 300);
  if (genre === 'rien' || !dit) return { genre: 'rien', texte: '' };
  return { genre, texte: dit };
}

// du neuf dans son présent (le dernier instant du fil a changé), rien en cours, 2 s depuis la dernière, 20 dans la minute au plus
// (08/11, Ahmed : « une zone PFC avec des barres ») pasMs et parMinute se règlent (Réglages, Son cortex préfrontal)
function doitDecider(e, signature, maintenant, pasMs = PAS_MS, parMinute = PAR_MINUTE) {   // pasMs : plus long quand papa est absent (son forfait)
  if (e.enVol || !signature || signature <= e.signature) return false;
  if (maintenant - e.derniere < pasMs) return false;
  e.appels = e.appels.filter(t => maintenant - t < 60_000);
  return e.appels.length < parMinute;
}
// (08/11, mesuré : 2 729 décisions en 6 h, 90 % « rien » : chaque mot entendu changeait son présent) du neuf qui compte, depuis « vu » (sa
// dernière décision) : un événement (son corps, son milieu, un ressenti, un son), tout de suite ; des mots (le téléphone, papa, la pièce), à la
// fin de la phrase (pauseMs de blanc) ou au bout de maxMs ; jamais sa propre voix ; jamais la redite exacte de ce qui est arrivé juste avant
function aDuNeuf(flux, vu, maintenant, { pauseMs = 1500, maxMs = 15_000, redite = 30_000 } = {}) {
  const l = (flux || []).filter(o => o && Number(o.t) <= maintenant + 3000 && maintenant - Number(o.t) < 120_000);
  const avant = new Set(l.filter(o => Number(o.t) <= vu && maintenant - Number(o.t) < redite).map(o => `${o.s}|${o.x}`));
  const neufs = l.filter(o => Number(o.t) > vu && o.s !== 'ta_voix' && !avant.has(`${o.s}|${o.x}`));
  if (!neufs.length) return false;
  if (neufs.some(o => o.i == null)) return true;
  const ts = neufs.map(o => Number(o.t)), dernier = Math.max(...ts), premier = Math.min(...ts);
  return maintenant - dernier >= pauseMs || maintenant - premier >= maxMs;
}
function commencer(e, signature, maintenant) {
  e.enVol = true; e.signature = signature; e.derniere = maintenant; e.appels.push(maintenant);
}

// ce qui passe maintenant : « penser » toujours ; « solliciter » / « faire » si papa ne parle pas, que sa tête est libre, et pas trop souvent
function permis(e, d, maintenant, { papaParle = false, occupe = false, entreSollicitationsMs = ENTRE_SOLLICITATIONS_MS, entreActesMs = ENTRE_ACTES_MS } = {}) {
  if (!d || d.genre === 'rien') return 'rien';
  let action = d.genre;
  if (action === 'solliciter' && (papaParle || occupe || maintenant - e.sollicitationA < entreSollicitationsMs)) action = 'penser';
  if (action === 'faire' && (papaParle || occupe || maintenant - e.acteA < entreActesMs)) action = 'penser';
  if (action === 'solliciter') e.sollicitationA = maintenant;
  if (action === 'faire') e.acteA = maintenant;
  e.pensees.push({ t: maintenant, genre: d.genre, texte: d.texte });
  e.pensees = e.pensees.slice(-8);
  return action;
}

module.exports = { etatInitial, lireDecision, doitDecider, aDuNeuf, commencer, permis, PAS_MS, PAR_MINUTE, ENTRE_SOLLICITATIONS_MS, ENTRE_ACTES_MS };

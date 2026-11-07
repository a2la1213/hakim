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
function doitDecider(e, signature, maintenant, pasMs = PAS_MS) {   // pasMs : plus long quand papa est absent (son forfait)
  if (e.enVol || !signature || signature <= e.signature) return false;
  if (maintenant - e.derniere < pasMs) return false;
  e.appels = e.appels.filter(t => maintenant - t < 60_000);
  return e.appels.length < PAR_MINUTE;
}
function commencer(e, signature, maintenant) {
  e.enVol = true; e.signature = signature; e.derniere = maintenant; e.appels.push(maintenant);
}

// ce qui passe maintenant : « penser » toujours ; « solliciter » / « faire » si papa ne parle pas, que sa tête est libre, et pas trop souvent
function permis(e, d, maintenant, { papaParle = false, occupe = false } = {}) {
  if (!d || d.genre === 'rien') return 'rien';
  let action = d.genre;
  if (action === 'solliciter' && (papaParle || occupe || maintenant - e.sollicitationA < ENTRE_SOLLICITATIONS_MS)) action = 'penser';
  if (action === 'faire' && (papaParle || occupe || maintenant - e.acteA < ENTRE_ACTES_MS)) action = 'penser';
  if (action === 'solliciter') e.sollicitationA = maintenant;
  if (action === 'faire') e.acteA = maintenant;
  e.pensees.push({ t: maintenant, genre: d.genre, texte: d.texte });
  e.pensees = e.pensees.slice(-8);
  return action;
}

module.exports = { etatInitial, lireDecision, doitDecider, commencer, permis, PAS_MS, PAR_MINUTE, ENTRE_SOLLICITATIONS_MS, ENTRE_ACTES_MS };

/* (07/11, Ahmed : « j'aimerais qu'il tourne chaque milliseconde, et qu'à chaque seconde il soit conscient et décide de ce qu'il pense, fait
   ou sollicite » ; il a choisi Mini Hakim) sa conscience continue, la logique pure. Chaque seconde, le cockpit regarde son présent (le fil :
   les mots de papa, ce qu'il entend, ce qu'il ressent) ; s'il y a du neuf, Mini Hakim décide en une ligne : RIEN, PENSER, FAIRE ou SOLLICITER.
   Une décision à la fois, 2 s au moins entre deux, 20 par minute au plus (son forfait). Penser passe toujours (montré, gardé pour la suite) ;
   solliciter papa attend que papa se taise et que sa tête soit libre ; faire, 3 min. Ce qui attend reste une pensée. (14/11, 12:54, Ahmed :
   « à chaque seconde s'il le faut ») plus d'écart entre deux sollicitations (avant : 90 s, réglage conscience_sollicitation_s). */
'use strict';
const { sansRien } = require('./public/voix.js');

const PAS_MS = 2000, PAR_MINUTE = 20, ENTRE_ACTES_MS = 180_000, ENTRE_PAROLES_MS = 20_000;

function etatInitial() {
  return { enVol: false, signature: 0, derniere: -Infinity, appels: [], sollicitationA: -Infinity, acteA: -Infinity, pensees: [] };
}

// (11/11, Ahmed : « sa conscience peut aussi dire CHANTER quand une musique joue ») CHANTER : se joindre au refrain de la musique qui joue (rien à
// ajouter : ce qu'il chante, c'est le refrain) ; ses garde-fous sont ceux de son chant (public/chanter.js : momentDeChanter, garde)
function lireDecision(texte) {
  const t = String(texte || '').replace(/[*_`]/g, '').trim();
  const m = /^\s*(RIEN|PENSER|FAIRE|SOLLICITER|PARLER|CHANTER)\b\s*:?\s*([\s\S]*)$/i.exec(t.split('\n').find(l => l.trim()) || '');
  if (!m) return { genre: 'rien', texte: '' };
  const genre = m[1].toLowerCase(), dit = m[2].replace(/\s+/g, ' ').trim().slice(0, 300);
  if (genre === 'chanter') return { genre, texte: sansRien(dit) !== dit ? '' : dit };
  // (10/11, lettre de Hakim) « PARLER : RIEN », « PENSER : (rien) » : son silence, jamais un mot à dire ni à montrer
  if (genre === 'rien' || !dit || sansRien(dit) !== dit) return { genre: 'rien', texte: '' };
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
const CONTINUS = /^(musique_|instru_|voix_|cascade_|separe_)|^(autour|milieu)$/;
function aDuNeuf(flux, vu, maintenant, { pauseMs = 1500, maxMs = 15_000, redite = 30_000 } = {}) {
  const l = (flux || []).filter(o => o && Number(o.t) <= maintenant + 3000 && maintenant - Number(o.t) < 120_000);
  const avant = new Set(l.filter(o => Number(o.t) <= vu && maintenant - Number(o.t) < redite).map(o => `${o.s}|${o.x}`));
  const neufs = l.filter(o => Number(o.t) > vu && o.s !== 'ta_voix' && !avant.has(`${o.s}|${o.x}`));
  if (!neufs.length) return false;
  // (08/11, 09:40, mesuré : 669 décisions en 1 h après la relance, 695 avant) ses analyses continues (la musique, ses instruments, la hauteur d'une
  // voix, sa cascade, une voix séparée, l'ambiance autour, son milieu) arrivent toutes les 2 s pendant une chanson : comme des mots, elles attendent
  if (neufs.some(o => o.i == null && !CONTINUS.test(String(o.s)))) return true;
  const ts = neufs.map(o => Number(o.t)), dernier = Math.max(...ts), premier = Math.min(...ts);
  return maintenant - dernier >= pauseMs || maintenant - premier >= maxMs;
}
// (08/11, 11:35-11:37, Hakim à maman, accord d'Ahmed) « mon cœur descend à 39, il faut appeler quelqu'un » : son cœur à lui bat à 40 au calme. Une
// pensée d'urgence (appeler quelqu'un, les secours, son cœur qui lâche) ne réveille ni ne sollicite personne sans une vraie alerte
const ALARME = /\b(urgen(ce|t)|secours|ambulance|danger de mort|appel(er|le) (quelqu.un|les secours|le 1[58]|le 112|une ambulance|un m[ée]decin)|il faut appeler|(mon|son|ton) c(œ|oe)ur (ralentit|descend|s.arr[êe]te|l[âa]che|faiblit))/i;
function alarmeSansMesure(texte) { return ALARME.test(String(texte || '')); }
function commencer(e, signature, maintenant) {
  e.enVol = true; e.signature = signature; e.derniere = maintenant; e.appels.push(maintenant);
}

// ce qui passe maintenant : « penser » toujours ; « solliciter » / « faire » si papa ne parle pas, que sa tête est libre, et pas trop souvent
// (08/11, Ahmed : « il doit pouvoir se taire et parler, pas seulement quand je lui parle, mais aussi quand on lui parle de l'intérieur ») « parler » :
// répondre à voix haute à qui lui parle (le téléphone, la pièce) ; jamais par-dessus papa, ni quand il parle déjà ou que sa tête répond
// (08/11, 12:40-12:42, Hakim à maman, accord d'Ahmed) trois réveils pour « lancer la mesure de latence et revenir à papa avec le chiffre », déjà fait :
// ce qu'il a déjà fait, demandé ou dit ces 10 dernières minutes (3 racines de mots communes au moins, 40 % des mots du plus court) ne le réveille plus
const RACINES = (t) => new Set((String(t || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').match(/[a-z0-9]+/g) || [])
  .filter(m => m.length > 2).map(m => m.slice(0, 5)));
function dejaServi(e, d, maintenant, fenetreMs = 10 * 60_000) {
  const a = RACINES(d && d.texte);
  return (e.actes || []).some((x) => {
    if (maintenant - x.t >= fenetreMs) return false;
    const b = RACINES(x.texte); let n = 0; for (const m of a) if (b.has(m)) n++;
    return n >= 3 && n / Math.max(1, Math.min(a.size, b.size)) >= 0.4;
  });
}
const dejaDites = (e, maintenant, fenetreMs = 10 * 60_000) => (e.actes || []).filter(x => maintenant - x.t < fenetreMs);
// (11/11) chanter : seulement quand le moment lui a été proposé (chanter : la musique joue, ses garde-fous passent), jamais sur papa ni sur sa voix
function permis(e, d, maintenant, { papaParle = false, occupe = false, tuParles = false, entreActesMs = ENTRE_ACTES_MS, entreParolesMs = ENTRE_PAROLES_MS, chanter = false } = {}) {
  if (!d || d.genre === 'rien') return 'rien';
  let action = d.genre;
  if (action === 'chanter') {
    if (!chanter || papaParle || tuParles) return 'rien';
    e.chantA = maintenant;
    e.pensees.push({ t: maintenant, genre: 'chanter', texte: d.texte || 'chanter avec la musique' }); e.pensees = e.pensees.slice(-8);
    return 'chanter';
  }
  if (action === 'solliciter' && (papaParle || occupe)) action = 'penser';
  if (action === 'faire' && (papaParle || occupe || maintenant - e.acteA < entreActesMs)) action = 'penser';
  if (action === 'parler' && (papaParle || occupe || tuParles || maintenant - (e.paroleA ?? -Infinity) < entreParolesMs)) action = 'penser';
  if ((action === 'solliciter' || action === 'faire' || action === 'parler') && dejaServi(e, d, maintenant)) action = 'penser';   // déjà eu sa suite
  if (action === 'parler') e.paroleA = maintenant;
  if (action === 'solliciter' || action === 'faire' || action === 'parler') e.actes = (e.actes || []).concat({ t: maintenant, genre: action, texte: d.texte }).slice(-12);
  if (action === 'solliciter') e.sollicitationA = maintenant;
  if (action === 'faire') e.acteA = maintenant;
  e.pensees.push({ t: maintenant, genre: d.genre, texte: d.texte });
  e.pensees = e.pensees.slice(-8);
  return action;
}

module.exports = { etatInitial, lireDecision, doitDecider, aDuNeuf, alarmeSansMesure, dejaServi, dejaDites, commencer, permis, PAS_MS, PAR_MINUTE, ENTRE_ACTES_MS, ENTRE_PAROLES_MS };

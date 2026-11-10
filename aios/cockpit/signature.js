/* (10/11, ~23:00, Ahmed : « ma voix est reconnue sous 19 voix différentes, qui sont ma signature vocale… papa et tonton Ali partagent tous
   les deux la voix 127. Sous cette voix, il y a écrit "papa" et "tonton Ali", et ça crée sa confusion, qui est acceptable et exactement
   l'effet souhaité. ») LE DOUTE D'UNE VOIX PARTAGÉE, la logique pure (aucun modèle, aucun effet de bord ; server.js la branche,
   test-signature.js la prouve). Les signatures elles-mêmes vivent dans anamnese/jarvis/signature_vocale.py.

   Quand son oreille entend une voix de deux signatures (« [papa ou Ali ?] »), le contexte peut trancher QUI parle, du plus sûr au plus faible :
   - le nom prononcé : la voix se nomme (« c'est Ali », « moi c'est Ali », « c'est papa », « c'est ton père ») ; ou elle appelle l'un des deux
     par son nom (« Ali, tu viens ? ») : ce n'est pas lui ;
   - qui est là : un seul des deux entendu sans doute dans la scène (les dernières minutes) ;
   - le lieu : un seul des deux déjà entendu ici ;
   sinon le doute reste, et le sujet de ce qui est dit peut l'aider (lui seul le comprend). Le contexte ne tranche que la CONVERSATION : jamais la
   vérification de papa (une voix partagée n'est jamais sa voix vérifiée ; le sensible attend sa confirmation, écrite ou de sa voix reconnue). */
'use strict';

const PRESENCE_MS = 10 * 60_000;                 // « dans la scène » : entendu sans doute dans les 10 dernières minutes
const LIEUX_MAX = 40;                            // les lieux gardés par personne

const echapper = (s) => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const PERE = /(?<![\p{L}])(?:ton (?:père|pere|papa|daron)|ton vieux|ton baba|baba)(?![\p{L}])/iu;
const estPapa = (n) => /^(papa|ahmed)$/i.test(String(n || ''));

// la voix se nomme : « c'est (moi) Ali », « moi c'est Ali », « ici Ali », « je suis Ali », « c'est tonton Ali » ; papa : aussi « c'est ton père »
function seNomme(texte, nom) {
  const t = String(texte || '');
  const n = estPapa(nom) ? '(?:papa|ahmed)' : `(?:tonton |tata |oncle |tante )?${echapper(nom)}`;
  const re = new RegExp(`(?<![\\p{L}])(?:c['’]est(?: moi,?)?|moi,? c['’]est|ici|je suis|moi,?)\\s+${n}(?![\\p{L}])`, 'iu');
  return re.test(t) || (estPapa(nom) && new RegExp(`(?<![\\p{L}])(?:c['’]est(?: moi,?)?|je suis)\\s+${PERE.source}`, 'iu').test(t));
}
// elle appelle quelqu'un par son nom, en apostrophe (« Ali, tu viens ? », « …, Ali ! ») : ce n'est pas lui qui parle
function appelle(texte, nom) {
  const t = String(texte || '').trim();
  const n = estPapa(nom) ? '(?:papa|ahmed)' : `(?:tonton |tata )?${echapper(nom)}`;
  return new RegExp(`^(?:(?:eh|hé|he|oh|yo|wesh|dis)\\s+)?${n}\\s*[,!?]`, 'iu').test(t) || new RegExp(`[,]\\s*${n}\\s*[.!?…]*$`, 'iu').test(t);
}

/* o : { personnes (ceux de la voix, papa d'abord), texte (ce que la voix a dit), presents (Map nom → dernière fois entendu sans doute), lieu,
   lieux ({ nom: { lieu: fois } }), maintenant }. Rend { qui (le plus probable, ou null), indice ('nom' | 'appel' | 'presence' | 'lieu' | null),
   raison }. */
function trancher(o = {}) {
  const personnes = [...new Set((o.personnes || []).map(String))].filter(Boolean);
  if (personnes.length < 2) return { qui: personnes[0] || null, indice: null, raison: '' };
  const texte = String(o.texte || '');
  const nommes = personnes.filter(n => seNomme(texte, n));
  if (nommes.length === 1) return { qui: nommes[0], indice: 'nom', raison: `la voix se nomme (${nommes[0]})` };
  const appeles = personnes.filter(n => appelle(texte, n));
  if (appeles.length === 1 && personnes.length === 2) {
    const autre = personnes.find(n => n !== appeles[0]);
    return { qui: autre, indice: 'appel', raison: `la voix appelle ${appeles[0]} par son nom : ce n'est pas ${estPapa(appeles[0]) ? 'papa' : appeles[0]}` };
  }
  const t = Number.isFinite(o.maintenant) ? o.maintenant : Date.now();
  const presents = o.presents instanceof Map ? o.presents : new Map(Object.entries(o.presents || {}));
  const la = personnes.filter(n => t - (Number(presents.get(n)) || 0) < PRESENCE_MS);
  if (la.length === 1) return { qui: la[0], indice: 'presence', raison: `seul ${la[0]} a été entendu sans doute dans la scène (les dix dernières minutes)` };
  if (o.lieu) {
    const ici = personnes.filter(n => Number(((o.lieux || {})[n] || {})[o.lieu]) > 0);
    if (ici.length === 1) return { qui: ici[0], indice: 'lieu', raison: `seul ${ici[0]} a déjà été entendu ici (${o.lieu})` };
  }
  return { qui: null, indice: null, raison: '' };
}

/* sa ligne du tour (une seule, pour toutes les voix partagées du message) ; doutes : [{ etiquette, voix, personnes, texte }] */
function ligne(doutes = [], ctx = {}) {
  const l = (Array.isArray(doutes) ? doutes : []).filter(d => d && Array.isArray(d.personnes) && d.personnes.length >= 2).slice(0, 3);
  if (!l.length) return '';
  const morceaux = l.map((d) => {
    const qui = d.personnes.map(n => (estPapa(n) ? 'papa' : n));
    const t = trancher({ ...ctx, personnes: d.personnes, texte: d.texte });
    const sig = `la voix ${d.voix} est dans la signature de ${qui.slice(0, -1).join(', ')} et de ${qui[qui.length - 1]}`;
    return `« ${d.etiquette || `${qui.join(' ou ')} ?`} » : ${sig} ; `
      + (t.qui ? `le contexte penche pour ${estPapa(t.qui) ? 'papa' : t.qui} (${t.raison})` : 'rien dans le contexte ne tranche : le doute reste');
  });
  return `\n[Voix partagée (ton oreille, papa 10/11 : « ça crée sa confusion, et c'est l'effet souhaité ») — ${morceaux.join(' ; ')}. `
    + 'Ce qui est dit (le sujet, la façon de parler) peut t’aider à savoir qui parle ; garde le doute s’il le faut, tu peux demander gentiment. '
    + 'Jamais sa voix vérifiée : rien de sensible sans sa confirmation, écrite ou de sa voix reconnue.]';
}

// qui a été entendu SANS doute dans ce morceau (une personne nommée, ou papa vérifié) : pour la présence et les lieux
function entendusSansDoute(voix = {}) {
  const l = Array.isArray(voix.locuteurs) ? voix.locuteurs.map(String) : [];
  const out = l.filter(n => n && !/\?$/.test(n) && !/^voix \d+$/i.test(n) && !estPapa(n) && n !== 'moi' && n !== 'Ahmed');
  if (voix.verdict === 'ahmed' && (!l.length || l.some(n => estPapa(n) || n === 'Ahmed'))) out.unshift('papa');
  return [...new Set(out)];
}
function noterLieu(lieux, nom, lieu) {
  if (!nom || !lieu) return false;
  const p = lieux[nom] || (lieux[nom] = {});
  p[lieu] = (Number(p[lieu]) || 0) + 1;
  const cles = Object.keys(p);
  if (cles.length > LIEUX_MAX) delete p[cles.sort((a, b) => p[a] - p[b])[0]];
  return true;
}

module.exports = { trancher, ligne, seNomme, appelle, entendusSansDoute, noterLieu, PRESENCE_MS };

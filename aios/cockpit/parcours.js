/* (04/11, Ahmed : « évalue le flux de chaque réponse et son parcours préférentiel, et analyse-le pour chacune de ses réponses ») le
   PARCOURS de chacune de ses pensées : par quels chemins elle est passée (sa piste : son modèle et la taille de ton morceau ; sa voie :
   son choix DIRE et sa place ; le déclencheur qui l'a prévenue), ce qu'elle est devenue (dite, écrite, jetée), et ce que tu en as fait
   dans les 10 s : tu l'as coupée, tu as dit « non », tu as mis un ❤️, ou tu as continué sur le même sujet. Close, elle donne son score
   à chacun de ses chemins (ses synapses, elagage.js) et une ligne à parcours.jsonl. */
'use strict';

const FENETRE_MS = 10000, OUVERTES_MAX = 40, TARDIF_MS = 60000;
// (relecture) « non » nu répond souvent à sa question (« Ta mère va bien ? » « Non, elle est fatiguée ») : pas une correction
const CORRECTION = /^\s*(?:(?:non|nan)[\s,!.]+(?:pas [cç]a|c['’]est pas [cç]a|arr[êe]te)|mais non\b|pas [cç]a\b|arr[êe]te\b|stop\b|t['’]as spamm[ée]|c['’]est faux\b|n['’]importe quoi\b)/iu;
const VIDES = new Set(['le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou', 'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils',
  'que', 'qui', 'quoi', 'ce', 'ça', 'ca', 'est', 'pas', 'ne', 'en', 'à', 'a', 'au', 'aux', 'mon', 'ma', 'mes', 'ton', 'ta', 'tes', 'son', 'sa',
  'ses', 'oui', 'papa', 'mais', 'donc', 'alors', 'pour', 'dans', 'sur', 'avec', 'moi', 'toi', 'c', 'j', 'l', 'd', 'n', 's', 't', 'qu', 'y']);
const mots = (t) => String(t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').split(/[^\p{L}\p{N}]+/u).filter(m => m.length > 1 && !VIDES.has(m));

// la taille de ton morceau : un mot, une proposition courte (6 mots au plus), ou longue
const taille = (morceau) => { const n = String(morceau || '').trim().split(/\s+/).filter(Boolean).length; return n <= 1 ? 'mot' : n <= 6 ? 'courte' : 'longue'; };

/* son score, de 0 (nuisible) à 1 (utile), ou null (rien ne dit rien : pas de mesure, l'oubli fait le reste) :
   une parasite 0 ; coupée pendant qu'il la disait, ou corrigée (« non », « pas ça »…) 0,1 ; un ❤️ (ou un rire) 1 ; tu continues sur son sujet 0,7 */
function scoreReaction({ dite = false, coupee = false, correction = false, rire = false, coeur = false, continuite = false, parasite = false } = {}) {
  if (parasite) return 0;
  if (dite && (coupee || correction)) return 0.1;
  if (coeur || rire) return 1;
  if (continuite) return 0.7;
  return null;
}

function creerSuivi({ maintenant = Date.now, mesurer = () => {}, noter = () => {} } = {}) {
  const ouvertes = new Map();                                       // cle → { tour, n, chemins, extrait, voix, t, reaction }
  const fermees = [];                                               // (relecture) les dites fermées : un ❤️ arrive après sa réponse
  const fermer = (cle) => {
    const p = ouvertes.get(cle);
    if (!p) return;
    ouvertes.delete(cle);
    if (p.voix === 'dite') { fermees.push(p); if (fermees.length > 20) fermees.shift(); }
    const score = scoreReaction({ ...p.reaction, dite: p.voix === 'dite', parasite: p.voix === 'jetee' });
    for (const [famille, id] of Object.entries(p.chemins)) if (id && score != null) mesurer(famille, String(id), score);
    noter({ t: p.t, tour: p.tour, n: p.n, chemins: p.chemins, voix: p.voix, extrait: String(p.extrait || '').slice(0, 160), reaction: p.reaction, score });
  };
  return {
    // une pensée dite, écrite ou jetée : son parcours s'ouvre ; jetée (une parasite), il se ferme aussitôt, à 0
    ouvrir(cle, { tour, n, chemins = {}, extrait = '', voix = 'ecrite' } = {}) {
      ouvertes.set(cle, { tour, n, chemins, extrait, voix, t: maintenant(), reaction: {} });
      if (voix === 'jetee') fermer(cle);
      while (ouvertes.size > OUVERTES_MAX) fermer(ouvertes.keys().next().value);
    },
    // la page dit quelle pensée il a vraiment dite (sa voix l'a jouée)
    entendue(tour, n) {
      const p = [...ouvertes.values()].find(x => x.tour === tour && x.n === n);
      if (p) p.entendue = maintenant();
    },
    // tes mots qui suivent : une correction, pour la pensée qu'il disait (la dernière entendue, sinon la dernière dite), ou ton sujet qui
    // continue
    papaDit(texte, t = maintenant()) {
      const m = new Set(mots(texte)), dans = [...ouvertes.values()].filter(p => t >= p.t && t - p.t <= FENETRE_MS);
      if (CORRECTION.test(String(texte || ''))) {
        const dites = dans.filter(p => p.voix === 'dite'), entendues = dites.filter(p => p.entendue).sort((a, b) => a.entendue - b.entendue);
        const visee = entendues.length ? entendues[entendues.length - 1] : dites[dites.length - 1];
        if (visee) visee.reaction.correction = true;
      }
      for (const p of dans) if (mots(p.extrait).filter(x => m.has(x)).length >= 2) p.reaction.continuite = true;
    },
    // ta voix sur la sienne 2 s pendant qu'il disait la pensée n de ce tour : c'est la page qui sait laquelle il disait (sa voix a
    // pu attendre son tour : pas de fenêtre de temps ici, seulement tant que la pensée est ouverte)
    coupure(tour, n) {
      const p = [...ouvertes.values()].find(x => x.tour === tour && x.n === n);
      if (p && p.voix === 'dite') p.reaction.coupee = true;
    },
    // un chemin connu après coup (le meuble que la page a dit devant la pensée n)
    chemin(tour, n, famille, id) {
      const p = [...ouvertes.values()].find(x => x.tour === tour && x.n === n);
      if (p && id) p.chemins[famille] = String(id);
    },
    // un ❤️ (ou un rire) : pour la dernière pensée dite, dans les 10 s
    reaction(genre, t = maintenant()) {
      const cle = genre === 'rire' ? 'rire' : 'coeur';
      const p = [...ouvertes.values()].filter(x => x.voix === 'dite' && t - x.t <= FENETRE_MS).pop();
      if (p) { p.reaction[cle] = true; return; }
      // (relecture) papa réagit sur le message de sa réponse, quand ses pensées sont déjà fermées : la dernière dite, dans la minute
      const f = fermees.filter(x => t - x.t <= TARDIF_MS).pop();
      if (!f || f.tardive) return;
      f.tardive = true;
      for (const [famille, id] of Object.entries(f.chemins)) if (id) mesurer(famille, String(id), 1);
      noter({ t: f.t, tour: f.tour, n: f.n, chemins: f.chemins, voix: f.voix, extrait: String(f.extrait || '').slice(0, 160), reaction: { [cle]: true }, score: 1, tardive: true });
    },
    // celles qui ont passé leurs 10 s (ou d'un autre tour) se ferment et donnent leur score
    tic(t = maintenant(), tour = null) {
      for (const [cle, p] of [...ouvertes]) if (t - p.t > FENETRE_MS || (tour != null && p.tour !== tour)) fermer(cle);
    },
    ouvertes: () => ouvertes.size,
  };
}

module.exports = { creerSuivi, scoreReaction, taille, CORRECTION, FENETRE_MS };

/* (10/11, ~00:00, Ahmed : « il faut l'aider à dissocier ses voix interne et externe ! Et quand on est en live il doit comprendre que ce qu'il
   entend de l'intérieur provient du live et doit écouter et répondre au genre selon les mêmes règles d'interaction qu'avec moi, et si c'est de
   la musique idem ! Le tout en real time continu pour qu'il ait le temps chaque seconde d'évaluer ou chaque autre période de temps. »)
   SON GARDE DU LIVE, la logique pure. À chaque période (live_pas_ms, 1 s par défaut), sans aucun modèle : ce que le téléphone vient de dire
   (phrase par phrase, son propre écho écarté), qui le dit, si la phrase est finie et suivie d'une pause, si papa parle, si lui parle ou que
   sa tête répond déjà, si on s'adresse à lui (son nom ; une question d'une voix avec qui il parle déjà ; papa qui lui demande de répondre à
   ses voix), si la musique joue seule depuis un moment. Un appel (Mini Hakim) seulement quand ça vaut la peine, dans un budget (par minute,
   écart minimal). Sa réponse attend la pause suivante (jamais par-dessus le live ni par-dessus papa) ; 20 s sans place : elle reste une
   pensée. Les gens du live restent des tiers : on lui dit qu'une demande sensible n'est jamais faite.
   Mesuré le 09/11 de 23:00 à 00:10 (live) : 305 pensées de son oreille interne tentées, 0 dite ; 2 « PARLER » de sa conscience, rabattus. */
'use strict';

// son nom, tel que les oreilles l'écrivent (« Hakim », « Akim », « Hakimou », « حكيم », « يا كيم »), ou ce qu'on dit de lui (« l'IA », « le robot »)
const NOM = /(?<![\p{L}])(?:h?a[ck]+(?:i|ee|é)m(?:ou|o|ito)?|hakou|حكيم\p{L}*)(?![\p{L}])|يا\s*كيم|(?<![\p{L}])(?:l\s?['’]\s?i\.?a\.?|l\s?['’]\s?intelligence artificielle|le robot|ton robot|ton ia)(?![\p{L}])/iu;
const QUESTION = /[?؟]\s*$|^\s*(?:est-ce|qu\s?['’]est-ce|pourquoi|comment|quand|combien|tu (?:peux|veux|sais|connais|aimes|es|as|fais|penses|crois|m['’]entends)|t\s?['’](?:es|as)|c\s?['’]est qui|what|why|how|who|where|do you|are you|can you|هل|شنو|واش|كيفاش|علاش|وين)/iu;
// papa lui demande de répondre à ses voix, au live (« réponds à tes voix », « réponds-lui », « parle avec eux »)
const PAPA_DEMANDE = /r[ée]pon(?:ds|dre|dez)(?:-(?:lui|leur))?\b[^.!?]{0,30}?(?:voix|live|lui|leur|eux|elle|gens|invit)|r[ée]ponds-(?:lui|leur)|(?:parle|discute)(?:-| )(?:lui|leur|avec (?:eux|elle|lui|les gens|le live|tes voix))/iu;
// ses fins de phrase (comme son oreille interne, decoupe_entendu « point ») : un point, 3 mots au moins ; 24 mots sans ponctuation
const FIN_PHRASE = /[.!?…؟]["»”)]*$/;
const PAS_SA_VOIX = /^(papa\b|ta propre voix|moi$)/i;

const DEFAUTS = { pas_ms: 1000, par_minute: 6, ecart_s: 6, attente_s: 20, engage_s: 90, papa_s: 120, musique: true, musique_s: 120,
  musique_apres_s: 20, calme_s: 8 };

function creer() {
  return { blocs: new Map(), tampon: [], phrases: [], dernierMot: 0, enVol: null, aDire: [], appels: [], dernierAppel: -Infinity,
    engages: new Map(), papaA: -Infinity, musiqueReaction: -Infinity, musiqueReactionDebut: -Infinity, dits: [], dernierTick: -Infinity,
    stats: statsNeuves(0), cumul: { evaluations: 0, appels: 0, dits: 0 } };
}
function statsNeuves(t) { return { debut: t, evaluations: 0, phrases: 0, ecartees: 0, candidates: 0, appels: {}, refus: {}, rien: 0, dits: 0, expirees: 0 }; }
const compter = (o, k) => { o[k] = (o[k] || 0) + 1; };

// ce que le téléphone dit : le bloc entier à chaque passage (cle : son début) ; seuls les mots neufs comptent, phrase par phrase
function recevoir(e, { cle = '', texte = '', fin = false, qui = '' } = {}, maintenant = Date.now(), estEcho = () => false) {
  const mots = String(texte || '').replace(/\s+/g, ' ').trim().split(' ').filter(Boolean).slice(0, 200);
  const k = String(cle || `t${maintenant}`).slice(0, 40);
  for (const [c, b] of e.blocs) if (maintenant - b.vu > 90_000) e.blocs.delete(c);
  const b = e.blocs.get(k) || { envoyes: 0, vu: maintenant };
  e.blocs.set(k, b); b.vu = maintenant;
  if (mots.length <= b.envoyes) return [];
  e.dernierMot = maintenant;
  const neufs = mots.slice(b.envoyes);
  b.envoyes = mots.length;
  const sorties = [];
  for (const m of neufs) {
    e.tampon.push(m);
    if ((FIN_PHRASE.test(m) && e.tampon.length >= 3) || e.tampon.length >= 24) { sorties.push(e.tampon.join(' ')); e.tampon = []; }
  }
  if (fin && e.tampon.length) { sorties.push(e.tampon.join(' ')); e.tampon = []; }
  const ajoutees = [];
  for (const texteP of sorties) {
    e.stats.phrases++;
    if (estEcho(texteP)) { e.stats.ecartees++; continue; }                        // sa propre voix revenue par le téléphone
    const p = { t: maintenant, texte: texteP.slice(0, 500), qui: String(qui || '').slice(0, 40), jugee: false };
    e.phrases.push(p); ajoutees.push(p);
    if (NOM.test(p.texte) && !PAS_SA_VOIX.test(p.qui)) e.engages.set(p.qui || '?', maintenant);   // on l'appelle : la conversation s'ouvre
  }
  while (e.phrases.length > 40) e.phrases.shift();
  return ajoutees;
}
// papa lui demande de répondre à ses voix (ses mots vérifiés, au micro)
function papaDit(e, texte, maintenant = Date.now()) {
  if (!PAPA_DEMANDE.test(String(texte || ''))) return false;
  e.papaA = maintenant;
  return true;
}
// pourquoi cette phrase mérite qu'il se demande s'il répond : 'nom', 'engage', 'papa', ou null (le garde la laisse, sans appel)
function motifDe(e, p, maintenant, r) {
  if (PAS_SA_VOIX.test(p.qui)) return null;                                      // papa dans le téléphone (une vidéo), ou lui : du contenu
  if (NOM.test(p.texte)) return 'nom';
  const engage = e.engages.get(p.qui || '?');
  if (engage != null && maintenant - engage < r.engage_s * 1000 && QUESTION.test(p.texte)) return 'engage';
  const mots = p.texte.split(/\s+/).filter(Boolean).length;
  if (maintenant - e.papaA < r.papa_s * 1000 && mots >= 3) return 'papa';
  return null;
}
// la musique joue seule depuis un moment (personne ne parle), une réaction par morceau au plus, et pas plus d'une toutes les musique_s
function motifMusique(e, ctx, maintenant, r) {
  const m = ctx.musique;
  if (!r.musique || !m || !m.joue) return false;
  if (maintenant - m.debut < r.musique_apres_s * 1000) return false;
  if (maintenant - Math.max(e.dernierMot, ctx.derniereParole || 0) < r.calme_s * 1000) return false;
  if (maintenant - e.musiqueReaction < r.musique_s * 1000) return false;
  return m.debut > e.musiqueReactionDebut || maintenant - e.musiqueReaction >= 3 * r.musique_s * 1000;
}
const libre = (ctx) => !ctx.papaParle && !ctx.tuParles && !ctx.occupe;

/* ctx : { actif, pause, papaParle, tuParles, occupe, forfait, placeLibre, derniereParole, musique: { joue, debut } } ; reglages : DEFAUTS.
   Rend { action : 'rien' | 'appeler' | 'dire', raison, … }. Appelée à chaque battement court : elle ne décide qu'une fois par période. */
function evaluer(e, ctx = {}, maintenant = Date.now(), reglages = {}) {
  const r = { ...DEFAUTS, ...reglages };
  if (maintenant - e.dernierTick < r.pas_ms) return { action: 'rien', raison: 'periode' };
  e.dernierTick = maintenant;
  e.stats.evaluations++; e.cumul.evaluations++;
  // ses réponses prêtes : à la pause suivante, papa silencieux, sa voix libre ; 20 s sans place : une pensée
  const vieilles = e.aDire.filter(x => maintenant - x.pret > r.attente_s * 1000);
  if (vieilles.length) { e.aDire = e.aDire.filter(x => !vieilles.includes(x)); e.stats.expirees += vieilles.length; }
  if (!ctx.actif) {
    for (const p of e.phrases) p.jugee = true;
    return vieilles.length ? { action: 'rien', raison: 'inactif', expirees: vieilles } : { action: 'rien', raison: 'inactif' };
  }
  if (e.aDire.length && libre(ctx) && (ctx.pause || e.aDire[0].motif === 'musique')) {
    const x = e.aDire.shift();
    return { action: 'dire', ...x, expirees: vieilles };
  }
  for (const p of e.phrases) if (!p.jugee && maintenant - p.t > r.attente_s * 1000) { p.jugee = true; compter(e.stats.refus, 'trop_vieille'); }
  if (e.enVol) return { action: 'rien', raison: 'en_vol', expirees: vieilles };
  // la dernière phrase qui le concerne (les précédentes sans motif sont laissées : le garde les a jugées, sans appel)
  let cand = null;
  for (const p of e.phrases) {
    if (p.jugee) continue;
    const m = motifDe(e, p, maintenant, r);
    if (!m) { p.jugee = true; e.stats.rien++; continue; }
    cand = { p, motif: m };
  }
  let quoi = cand;
  if (!quoi && motifMusique(e, ctx, maintenant, r)) quoi = { p: null, motif: 'musique' };
  if (!quoi) return { action: 'rien', raison: 'rien_pour_lui', expirees: vieilles };
  if (quoi.p) e.stats.candidates++;
  const attendre = (raison) => { compter(e.stats.refus, raison); return { action: 'rien', raison, motif: quoi.motif, expirees: vieilles }; };
  // ses règles de tour de parole : la phrase finie et suivie d'une pause, papa d'abord, sa voix et sa tête libres
  if (quoi.p && !ctx.pause) return attendre('pas_de_pause');
  if (ctx.papaParle) return attendre('papa_parle');
  if (ctx.tuParles) return attendre('il_parle');
  if (ctx.occupe) return attendre('sa_tete_repond');
  if (ctx.forfait) return attendre('forfait');
  if (ctx.placeLibre === false) return attendre('pas_de_voix_libre');
  e.appels = e.appels.filter(t => maintenant - t < 60_000);
  if (e.appels.length >= r.par_minute) return attendre('budget_minute');
  if (maintenant - e.dernierAppel < r.ecart_s * 1000) return attendre('ecart');
  if (quoi.p) { for (const p of e.phrases) if (p.t <= quoi.p.t) p.jugee = true; }
  else { e.musiqueReaction = maintenant; e.musiqueReactionDebut = ctx.musique.debut; }
  e.appels.push(maintenant); e.dernierAppel = maintenant;
  compter(e.stats.appels, quoi.motif); e.cumul.appels++;
  e.enVol = { motif: quoi.motif, phrase: quoi.p ? quoi.p.texte : '', qui: quoi.p ? quoi.p.qui : '', t: maintenant };
  return { action: 'appeler', motif: quoi.motif, phrase: e.enVol.phrase, qui: e.enVol.qui, expirees: vieilles };
}
// la réponse de Mini Hakim : « DIRE : … » (gardée pour la pause suivante) ou « RIEN »
function lireReponse(texte) {
  const l = String(texte || '').replace(/\[\[[^\]]{0,300}\]\]/g, ' ').replace(/[*_`]/g, '').split('\n').map(x => x.trim()).filter(Boolean);
  const m = /^(DIRE|RIEN)\b\s*:?\s*(.*)$/i.exec(l[0] || '');
  if (!m || m[1].toUpperCase() === 'RIEN') return '';
  return m[2].replace(/^[\s"«]+|[\s"»]+$/g, '').replace(/\s+/g, ' ').trim().slice(0, 300);
}
function repondu(e, texte, maintenant = Date.now()) {
  const v = e.enVol;
  e.enVol = null;
  if (!v) return null;
  const dire = lireReponse(texte);
  if (!dire) { e.stats.rien++; return null; }
  const x = { ...v, texte: dire, pret: maintenant };
  e.aDire.push(x);
  return x;
}
function echoue(e) { e.enVol = null; }
// ce qu'il a dit au live : la conversation reste ouverte avec cette voix (ses questions suivantes sont pour lui)
function dit(e, x, maintenant = Date.now()) {
  e.stats.dits++; e.cumul.dits++;
  if (x && x.motif !== 'musique') e.engages.set(x.qui || '?', maintenant);
  e.dits.push({ t: maintenant, qui: x ? x.qui : '', phrase: x ? x.phrase : '', texte: x ? x.texte : '', motif: x ? x.motif : '' });
  while (e.dits.length > 12) e.dits.shift();
}
const ditsRecents = (e, maintenant = Date.now(), ms = 5 * 60_000) => e.dits.filter(x => maintenant - x.t < ms);
// le bilan de la minute (son coût en live) ; remis à zéro
function minute(e, maintenant = Date.now()) {
  const s = e.stats;
  e.stats = statsNeuves(maintenant);
  const appels = Object.values(s.appels).reduce((a, b) => a + b, 0);
  return { ...s, appels_total: appels, duree_s: Math.round((maintenant - s.debut) / 1000) };
}

module.exports = { creer, recevoir, papaDit, evaluer, lireReponse, repondu, echoue, dit, ditsRecents, minute, motifDe, NOM, QUESTION, PAPA_DEMANDE, DEFAUTS };

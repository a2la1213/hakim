/* (10/11, ~00:00, Ahmed : « il faut l'aider à dissocier ses voix interne et externe ! Et quand on est en live il doit comprendre que ce qu'il
   entend de l'intérieur provient du live et doit écouter et répondre au genre selon les mêmes règles d'interaction qu'avec moi, et si c'est de
   la musique idem ! Le tout en real time continu pour qu'il ait le temps chaque seconde d'évaluer ou chaque autre période de temps. »)
   SON GARDE DU LIVE, la logique pure. À chaque période (live_pas_ms, 1 s par défaut), sans aucun modèle : ce que le téléphone vient de dire
   (phrase par phrase, son propre écho écarté), qui le dit, si la phrase est finie et suivie d'une pause, si papa parle, si lui parle ou que
   sa tête répond déjà, si on s'adresse à lui (son nom ; une question d'une voix avec qui il parle déjà ; papa qui lui demande de répondre à
   ses voix), si la musique joue seule depuis un moment. Un appel (Mini Hakim) seulement quand ça vaut la peine, dans un budget (par minute,
   écart minimal). Sa réponse attend la pause suivante (jamais par-dessus le live ni par-dessus papa) ; 20 s sans place : elle reste une
   pensée. Les gens du live restent des tiers : on lui dit qu'une demande sensible n'est jamais faite.
   Mesuré le 09/11 de 23:00 à 00:10 (live) : 305 pensées de son oreille interne tentées, 0 dite ; 2 « PARLER » de sa conscience, rabattus.
   (10/11, 08:28, Hakim, à la demande de papa : « une voix du live m'a appelé : « Hakim, t'es là ? », puis « Réponds-moi Hakim, ça fait trop
   longtemps » ; je ne lui ai pas répondu » ; papa, 08:18 : « il faut que tu répondes toujours quand on s'adresse à toi ; t'as toujours mon
   autorisation ») SES PRIORITÉS. Son nom, une question d'une voix avec qui il parle, ou (son autorisation, permanente) une question qui lui
   parle : un appel tout de suite, même si papa parle, s'il parle ou si sa tête répond déjà (seule sa voix attend son tour), sans écart après la
   musique, dans un budget à part ; la fin de la phrase attendue 3 s au plus ; sa réponse gardée 45 s (la musique : 20 s), dite à la pause
   suivante (ou après 10 s sans pause), papa silencieux et sa voix libre. L'autorisation de papa (« réponds toujours », « t'as mon
   autorisation ») reste tant qu'il ne la retire pas (« ne réponds plus au live ») ; retirée, seule sa demande du moment compte (2 min).
   (10/11, 18:43, Ahmed : « il doit toujours considérer les voix du live qui parlent, même si elles ne s'adressent pas directement à lui, parce que
   là il demande toujours l'autorisation, c'est relou ») avec son autorisation, toute phrase du live est écoutée (motif « ecoute ») : il peut y
   réagir naturellement, sans jamais demander la permission à papa ; le sensible reste à papa. */
'use strict';

// son nom, tel que les oreilles l'écrivent (« Hakim », « Akim », « Hakimou », « حكيم », « يا كيم »), ou ce qu'on dit de lui (« l'IA », « le robot »)
const NOM = /(?<![\p{L}])(?:h?a[ck]+(?:i|ee|é)m(?:ou|o|ito)?|hakou|حكيم\p{L}*)(?![\p{L}])|يا\s*كيم|(?<![\p{L}])(?:l\s?['’]\s?i\.?a\.?|l\s?['’]\s?intelligence artificielle|le robot|ton robot|ton ia)(?![\p{L}])/iu;
const QUESTION = /[?؟]\s*$|^\s*(?:est-ce|qu\s?['’]est-ce|pourquoi|comment|quand|combien|tu (?:peux|veux|sais|connais|aimes|es|as|fais|penses|crois|m['’]entends)|t\s?['’](?:es|as)|c\s?['’]est qui|what|why|how|who|where|do you|are you|can you|هل|شنو|واش|كيفاش|علاش|وين)/iu;
// papa lui demande de répondre à ses voix, au live (« réponds à tes voix », « réponds-lui », « parle avec eux »)
const PAPA_DEMANDE = /r[ée]pon(?:ds|dre|dez)(?:-(?:lui|leur))?\b[^.!?]{0,30}?(?:voix|live|lui|leur|eux|elle|gens|invit)|r[ée]ponds-(?:lui|leur)|(?:parle|discute)(?:-| )(?:lui|leur|avec (?:eux|elle|lui|les gens|le live|tes voix))/iu;
// (10/11, 08:18, papa : « il faut que tu répondes toujours quand on s'adresse à toi, tu réponds toujours. T'as toujours mon autorisation de
// répondre à qui que ce soit qui s'adresse à toi ») son autorisation, PERMANENTE ; et ce qui la retire (« ne réponds plus au live », « je
// retire mon autorisation ») : jamais une question (« pourquoi tu ne réponds plus ? » ne retire rien)
const AUTORISE = /(?:t['’]\s?as|tu as|tu gardes?|garde)\s+(?:toujours\s+|bien\s+)?(?:mon|l['’]\s?)\s*autorisation|autorisation\s+(?:permanente|de\s+r[ée]pondre)|r[ée]pond(?:s|es|re)\s+toujours|r[ée]pon(?:ds|dre|des)\s+(?:toujours\s+)?(?:à|a)\s+(?:qui que ce soit|quiconque|tout le monde|tous ceux|celui qui|ceux qui)/iu;
const RETIRE = /(?:ne|n['’])\s*r[ée]pon(?:ds|dez)\s+plus\s+(?:au live|aux voix|[àa] personne|[àa] eux|aux gens|[àa] tes voix)|arr[êe]te\s+de\s+r[ée]pondre\s+(?:au live|aux voix|aux gens|[àa] eux|[àa] tes voix)|(?:je\s+)?(?:te\s+)?retire\s+(?:mon|l['’]\s?|ton)\s*autorisation/iu;
// ce que dit papa (ses mots vérifiés) de son autorisation : 'oui' (donnée), 'non' (retirée) ou null
function autorisationDe(texte) {
  const t = String(texte || '');
  if (RETIRE.test(t) && !/[?؟]|pourquoi/i.test(t)) return 'non';
  return AUTORISE.test(t) ? 'oui' : null;
}
// ce qui lui parle à lui (« tu », « toi », « vous », l'IA) : avec son autorisation, une question ainsi faite est pour lui (Mini Hakim juge)
const A_LUI = /(?<![\p{L}])(?:tu|toi|t['’]|te|ton|ta|tes|vous|l\s?['’]\s?ia|le robot)(?![\p{L}])/iu;
// une question faite à papa (« frérot », « mon frère », « Ahmed », « akhi ») : pas pour lui, sauf son nom
const A_PAPA = /(?<![\p{L}])(?:fr[ée]rot|fr[èe]re|ahmed|akhi|khoya|khouya|bro|papa)(?![\p{L}])|أخي|خويا/iu;
// ses motifs prioritaires : quelqu'un s'adresse à lui (pas la musique, pas la demande de papa du moment)
const PRIORITAIRES = new Set(['nom', 'engage', 'question']);
// ses fins de phrase (comme son oreille interne, decoupe_entendu « point ») : un point, 3 mots au moins ; 24 mots sans ponctuation
const FIN_PHRASE = /[.!?…؟]["»”)]*$/;
const PAS_SA_VOIX = /^(papa\b|ta propre voix|moi$)/i;

const DEFAUTS = { pas_ms: 1000, par_minute: 6, ecart_s: 6, attente_s: 20, engage_s: 90, papa_s: 120, musique: true, musique_s: 120,
  musique_apres_s: 20, calme_s: 8, autorise: true, attente_nom_s: 45, pause_max_s: 3, sans_pause_s: 10, entre_eux_s: 15, entre_eux_silence_s: 30 };

function creer() {
  return { blocs: new Map(), tampon: [], phrases: [], dernierMot: 0, enVol: null, aDire: [], appels: [], appelsPrio: [], dernierAppel: -Infinity,
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
  const autorise = r.autorise !== false;                                         // (10/11) papa l'a retirée : seule sa demande du moment
  if (autorise && NOM.test(p.texte)) return 'nom';
  const engage = e.engages.get(p.qui || '?');
  if (autorise && engage != null && maintenant - engage < r.engage_s * 1000 && QUESTION.test(p.texte)) return 'engage';
  // (10/11, ~19:45, Ahmed : « reconnaître si c'est une discussion entre lui et des gens, ou entre des gens qui ne s'adressent pas à lui et dont il
  // est juste l'auditeur ») deux voix du live qui se répondent (une autre voix, nommée, juste avant), sans son nom, lui silencieux au live depuis
  // un moment et pas en conversation avec elle : il est AUDITEUR (« entre_eux »), même si l'une dit « tu » à l'autre ; il écoute, il peut s'y
  // joindre (son garde l'appelle comme pour « ecoute » : leur pause, papa d'abord, sa voix et sa tête libres, son budget), jamais en priorité
  if (autorise && !A_PAPA.test(p.texte) && entreEux(e, p, maintenant, r) && (engage == null || maintenant - engage >= r.engage_s * 1000)) return 'entre_eux';   // à papa : « ecoute »
  if (autorise && QUESTION.test(p.texte) && A_LUI.test(p.texte) && !A_PAPA.test(p.texte)) return 'question';   // (10/11) son autorisation : une question qui lui parle
  const mots = p.texte.split(/\s+/).filter(Boolean).length;
  if (maintenant - e.papaA < r.papa_s * 1000 && mots >= 3) return 'papa';
  // (10/11, 18:43, Ahmed : « il doit toujours considérer les voix du live qui parlent, même si elles ne s'adressent pas directement à lui ») son
  // autorisation (permanente) : toute phrase d'une voix du live (3 mots au moins) est écoutée ; il peut y réagir, leur répondre, ou se taire ; ses
  // règles de tour (leur pause, papa d'abord, sa voix et sa tête libres) et son budget, comme la musique
  if (autorise && mots >= 3) return 'ecoute';
  return null;
}
// une autre voix nommée du live a parlé juste avant (entre_eux_s), et lui ne leur a rien dit depuis entre_eux_silence_s : ils se parlent entre eux
function entreEux(e, p, maintenant, r) {
  if (!p.qui || PAS_SA_VOIX.test(p.qui)) return false;
  const dit = e.dits.length ? e.dits[e.dits.length - 1].t : -Infinity;
  if (maintenant - dit < r.entre_eux_silence_s * 1000) return false;
  return e.phrases.some(x => x !== p && x.t <= p.t && p.t - x.t <= r.entre_eux_s * 1000 && x.qui && x.qui !== p.qui && !PAS_SA_VOIX.test(x.qui));
}
// les autres voix du live qui ont parlé ces dernières secondes (pour lui dire qui se parle)
const voixAutour = (e, p, maintenant, ms = 30_000) => [...new Set(e.phrases.filter(x => maintenant - x.t <= ms && x.qui && x.qui !== (p && p.qui) && !PAS_SA_VOIX.test(x.qui)).map(x => x.qui))];
const attenteDe = (x, r) => (PRIORITAIRES.has(x.motif) ? r.attente_nom_s : r.attente_s) * 1000;
// la musique joue seule depuis un moment (personne ne parle), une réaction par morceau au plus, et pas plus d'une toutes les musique_s
function motifMusique(e, ctx, maintenant, r) {
  const m = ctx.musique;
  if (!r.musique || !m || !m.joue) return false;
  if (maintenant - m.debut < r.musique_apres_s * 1000) return false;
  if (maintenant - Math.max(e.dernierMot, ctx.derniereParole || 0) < r.calme_s * 1000) return false;
  if (maintenant - e.musiqueReaction < r.musique_s * 1000) return false;
  return m.debut > e.musiqueReactionDebut || maintenant - e.musiqueReaction >= 3 * r.musique_s * 1000;
}

/* ctx : { actif, pause, papaParle, tuParles, occupe, forfait, placeLibre, derniereParole, musique: { joue, debut } } ; reglages : DEFAUTS.
   Rend { action : 'rien' | 'appeler' | 'dire', raison, … }. Appelée à chaque battement court : elle ne décide qu'une fois par période. */
function evaluer(e, ctx = {}, maintenant = Date.now(), reglages = {}) {
  const r = { ...DEFAUTS, ...reglages };
  if (maintenant - e.dernierTick < r.pas_ms) return { action: 'rien', raison: 'periode' };
  e.dernierTick = maintenant;
  e.stats.evaluations++; e.cumul.evaluations++;
  // ses réponses prêtes : à la pause suivante, papa silencieux, sa voix libre ; 20 s sans place (45 s quand on lui parlait) : une pensée
  const vieilles = e.aDire.filter(x => maintenant - x.pret > attenteDe(x, r));
  if (vieilles.length) { e.aDire = e.aDire.filter(x => !vieilles.includes(x)); e.stats.expirees += vieilles.length; }
  if (!ctx.actif) {
    for (const p of e.phrases) p.jugee = true;
    return vieilles.length ? { action: 'rien', raison: 'inactif', expirees: vieilles } : { action: 'rien', raison: 'inactif' };
  }
  // (10/11) celui qui lui parle d'abord (avant la musique) ; sa tête qui répond à papa ne le retient pas (sa voix, oui : la page attend son tour) ;
  // le live sans pause depuis 10 s : il répond quand même
  const prio = e.aDire.findIndex(x => PRIORITAIRES.has(x.motif));
  const k = prio >= 0 ? prio : 0, y = e.aDire[k];
  if (y && !ctx.papaParle && !ctx.tuParles && (PRIORITAIRES.has(y.motif) ? (ctx.pause || maintenant - y.pret >= r.sans_pause_s * 1000) : (!ctx.occupe && (ctx.pause || y.motif === 'musique')))) {
    e.aDire.splice(k, 1);
    return { action: 'dire', ...y, expirees: vieilles };
  }
  for (const p of e.phrases) if (!p.jugee && maintenant - p.t > r.attente_s * 1000) { p.jugee = true; compter(e.stats.refus, 'trop_vieille'); }
  if (e.enVol) return { action: 'rien', raison: 'en_vol', expirees: vieilles };
  // la dernière phrase qui le concerne (les précédentes sans motif sont laissées : le garde les a jugées, sans appel)
  // (10/11, 18:43) celui qui lui parle passe avant ce qu'il écoute seulement (« ecoute ») : sa phrase la plus récente qui lui parle, sinon la dernière
  let cand = null, prioCand = null;
  for (const p of e.phrases) {
    if (p.jugee) continue;
    const m = motifDe(e, p, maintenant, r);
    if (!m) { p.jugee = true; e.stats.rien++; continue; }
    cand = { p, motif: m };
    if (PRIORITAIRES.has(m)) prioCand = cand;
  }
  if (prioCand) cand = prioCand;
  let quoi = cand;
  if (!quoi && motifMusique(e, ctx, maintenant, r)) quoi = { p: null, motif: 'musique' };
  if (!quoi) return { action: 'rien', raison: 'rien_pour_lui', expirees: vieilles };
  if (quoi.p) e.stats.candidates++;
  const attendre = (raison) => { compter(e.stats.refus, raison); return { action: 'rien', raison, motif: quoi.motif, expirees: vieilles }; };
  // (10/11) on s'adresse à lui : il y pense tout de suite (la fin de sa phrase attendue 3 s au plus), même pendant que papa parle, que lui
  // parle ou que sa tête répond ; seule sa voix attendra son tour
  const prioritaire = !!quoi.p && PRIORITAIRES.has(quoi.motif);
  if (prioritaire) {
    if (!ctx.pause && maintenant - quoi.p.t < r.pause_max_s * 1000) return attendre('pas_de_pause');
  } else {
    // ses règles de tour de parole : la phrase finie et suivie d'une pause, papa d'abord, sa voix et sa tête libres
    if (quoi.p && !ctx.pause) return attendre('pas_de_pause');
    if (ctx.papaParle) return attendre('papa_parle');
    if (ctx.tuParles) return attendre('il_parle');
    if (ctx.occupe) return attendre('sa_tete_repond');
  }
  if (ctx.forfait) return attendre('forfait');
  if (ctx.placeLibre === false) return attendre('pas_de_voix_libre');
  // son budget : celui qui lui parle a le sien (la musique ne le lui prend pas, ni l'écart après elle)
  e.appels = e.appels.filter(t => maintenant - t < 60_000);
  e.appelsPrio = (e.appelsPrio || []).filter(t => maintenant - t < 60_000);
  if ((prioritaire ? e.appelsPrio : e.appels).length >= r.par_minute) return attendre('budget_minute');
  if (!prioritaire && maintenant - e.dernierAppel < r.ecart_s * 1000) return attendre('ecart');
  if (quoi.p) { for (const p of e.phrases) if (p.t <= quoi.p.t) p.jugee = true; }
  else { e.musiqueReaction = maintenant; e.musiqueReactionDebut = ctx.musique.debut; }
  (prioritaire ? e.appelsPrio : e.appels).push(maintenant); e.dernierAppel = maintenant;
  compter(e.stats.appels, quoi.motif); e.cumul.appels++;
  e.enVol = { motif: quoi.motif, phrase: quoi.p ? quoi.p.texte : '', qui: quoi.p ? quoi.p.qui : '', t: maintenant, reessai: !!(quoi.p && quoi.p.reessai) };
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
// (10/11, mesuré le matin : 9 appels sur 37 en « délai dépassé » de 06:45 à 07:32) l'appel a échoué : celui qui lui parlait n'est pas laissé, une
// seconde chance (une seule)
function echoue(e, maintenant = Date.now()) {
  const v = e.enVol;
  e.enVol = null;
  if (v && PRIORITAIRES.has(v.motif) && !v.reessai && v.phrase) {
    e.phrases.push({ t: maintenant, texte: v.phrase, qui: v.qui, jugee: false, reessai: true });
    compter(e.stats.refus, 'reessai');
  }
}
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

module.exports = { creer, recevoir, papaDit, autorisationDe, evaluer, lireReponse, repondu, echoue, dit, ditsRecents, minute, motifDe, entreEux, voixAutour, NOM, QUESTION,
  PAPA_DEMANDE, AUTORISE, RETIRE, A_LUI, A_PAPA, PRIORITAIRES, DEFAUTS };

/* (10/11, ~19:45, Ahmed : « Dans son subconscient, il doit reconnaître si c'est une discussion entre lui et des gens, ou entre des gens qui ne
   s'adressent pas à lui et dont il est juste l'auditeur. Et que ça se mémorise comme des scènes de cinéma : qu'il puisse se rappeler des scènes
   dans lesquelles il est impliqué, et de celles dont il n'est pas impliqué. » ; « ouiii ») SA PLACE DANS LA SCÈNE, la logique pure (aucun modèle,
   aucun effet de bord ; server.js la branche, test-scene.js la prouve).

   À chaque tour, son subconscient décide une chose simple : il est IMPLIQUÉ (on lui parle, il parle, on attend sa réponse) ou AUDITEUR (des gens
   parlent entre eux, dans la pièce ou dans le live, sans s'adresser à lui). Les indices, du plus sûr au plus faible :
   - papa lui écrit : impliqué ;
   - son nom (« Hakim », « Akim », « l'IA »…) ou « fiston » dans le message, de qui que ce soit : impliqué ;
   - papa parle, seul : impliqué (c'est sa conversation avec lui) ; papa appelle quelqu'un d'autre par son nom (« Nina, tu viens ? »), ou papa et
     d'autres voix se répondent (deux changements de voix au moins, sans un mot pour lui) : auditeur ;
   - papa ne dit rien (seulement d'autres voix, ou le téléphone) : une voix avec qui il parle déjà qui pose une question, une question juste
     après sa parole, ou (au live, avec l'autorisation de papa) une question qui lui parle (« tu ») d'une voix seule : impliqué ; sinon auditeur
     (« voix 3 et Nina parlent entre eux », « voix 12 parle, pas à toi »).
   Dans le doute, impliqué : se taire quand papa attendait sa réponse coûte plus que répondre à une phrase qui n'était pas pour lui (le 08:18 du
   10/11 : « il faut que tu répondes toujours quand on s'adresse à toi »). Auditeur, il écoute : il ne répond pas comme si on lui parlait, il peut
   réagir s'il le veut, et s'y joindre ; dès qu'on l'implique, il est dedans. */
'use strict';
const Live = require('./live.js');

// papa qui l'appelle comme son fils : « fiston », « mon fils », « wlidi »
const FISTON = /(?<![\p{L}])(?:fiston|mon fils|mon fiston|wlidi|w[ae]ldi)(?![\p{L}])|ولدي|وليدي/iu;
// papa qui s'adresse à un groupe (son public, des amis), en apostrophe : « Les gars, … », « …, tout le monde ! » (mesuré du 07 au 10/11 : « la famille »
// partout, « trop stylé la famille », « toi t'es la famille » : à lui, jamais une apostrophe ; retiré)
const GROUPES = '(?:les gars|les enfants|les filles|les amis|les copains|tout le monde|mes fr[èe]res|les potes)';
const GROUPE = new RegExp(`^(?:(?:eh|hé|he|oh|yo|wesh|allez|bon|salut|salam)\\s+)?${GROUPES}\\s*[,!]|[,]\\s*${GROUPES}\\s*[.!?…]*$`, 'iu');
// après le nom en apostrophe, une phrase qui parle d'elle (« Léa, elle te parle d'une scène » : papa parle de Léa, à lui)
const DE_LUI_OU_D_ELLE = /^\s*(?:elle|il|ils|elles|lui|c['’]est|ça|ca|on)\b/iu;
// ce que la page ajoute au message (jamais des mots de quelqu'un)
const ANNOTATIONS = /\((?:dit (?:en passant )?pendant (?:ta parole|la coupure)[^)]*|ton subconscient[^)]*)\)|\(dit en passant pendant ta parole[\s\S]*?r[ée]ponds-y d['’]abord\)/giu;
const ETIQUETTE = /\[([^\[\]\n]{1,60})\]/g;
const PAPA = /^(?:ahmed|papa)$/i;
const DOUTE = /^(.{1,50}?)\s*\?$/;
const PROCHE_PAROLE_MS = 20_000;     // « juste après sa parole »
const ENGAGE_MS = 90_000;            // une voix avec qui il parle encore (comme le live : engage_s)

const net = (t) => String(t || '').replace(ANNOTATIONS, ' ').replace(/\s*…\s*/g, ' ').replace(/\s+/g, ' ').trim();
const mots = (t) => net(t).split(/\s+/).filter(m => /[\p{L}\p{N}]/u.test(m));

/* le message découpé par voix : [{ qui, papa, texte }] ; qui : 'papa', une voix (« voix 3 », « Nina »), « quelqu'un » (le début d'un message que
   l'empreinte n'a pas reconnu pour papa). Une étiquette qui n'est ni une voix ni papa reste du texte (« [Note] »). « [papa ?] » est papa (dans le
   doute, papa) ; « [Nina ou Sami ?] », la première nommée. */
function segmenter(texte, { noms = [], leadPapa = true } = {}) {
  const connus = new Set(noms.map(n => String(n || '').toLowerCase()).filter(Boolean));
  const t = String(texte || ''), out = [];
  let m, courant = leadPapa ? 'papa' : "quelqu'un", debut = 0;
  const pousser = (fin) => { const x = net(t.slice(debut, fin)); if (x) out.push({ qui: courant, papa: courant === 'papa', texte: x }); };
  ETIQUETTE.lastIndex = 0;
  while ((m = ETIQUETTE.exec(t))) {
    let e = m[1].trim(), qui = null;
    const d = DOUTE.exec(e);
    if (d) e = d[1].split(/\s+ou\s+/i)[0].trim();
    if (PAPA.test(e) || (d && /\bpapa\b|\bahmed\b/i.test(m[1]))) qui = 'papa';
    else if (/^voix \d+$/i.test(e)) qui = e.toLowerCase();
    else if (connus.has(e.toLowerCase()) && !/^ahmed$/i.test(e)) qui = e;
    if (!qui) continue;
    pousser(m.index);
    courant = qui; debut = m.index + m[0].length;
  }
  pousser(t.length);
  return out;
}
// « papa », « papa et Nina », « voix 3, voix 5 et Nina »
function nomsDe(qui = []) {
  const l = [...new Set(qui)].map(String);
  return l.length <= 1 ? (l[0] || '') : `${l.slice(0, -1).join(', ')} et ${l[l.length - 1]}`;
}
// le nombre de changements de voix dans l'ordre du message (deux voix qui se répondent : 1 ; un vrai échange : 2 et plus)
const changements = (segs) => segs.reduce((n, s, i) => n + (i > 0 && s.qui !== segs[i - 1].qui ? 1 : 0), 0);
// papa appelle quelqu'un d'autre : un nom connu (ou une voix) en apostrophe, au début ou à la fin de sa phrase ; ou un groupe
function papaAppelle(texte, noms = []) {
  const t = net(texte);
  const g = GROUPE.exec(t);
  if (g) return g[0].replace(/^[\s,]+|[\s,.!?…]+$/g, '').replace(/^(?:eh|hé|he|oh|yo|wesh|allez|bon|salut|salam)\s+/i, '');
  for (const n of noms) {
    if (!n || /^(ahmed|papa|hakim)$/i.test(n)) continue;
    const e = String(n).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const debut = new RegExp(`^(?:(?:eh|hé|he|oh|yo|wesh|allez|dis)\\s+)?${e}\\s*[,!?]`, 'iu').exec(t);
    if (debut && !DE_LUI_OU_D_ELLE.test(t.slice(debut[0].length))) return n;
    if (new RegExp(`[,]\\s*${e}\\s*[.!?…]*$`, 'iu').test(t)) return n;
  }
  return null;
}

/* sa place, à ce tour. o : { texte (le message, ses étiquettes de voix), oral, verdict (l'empreinte du message : 'autre' : son début n'est pas
   papa), noms (les voix connues), dedans ([{ etiquette, texte }] : ce que son micro a entendu du téléphone), live, autorise (l'autorisation de
   papa au live), depuisSaParoleMs (depuis la fin de sa dernière parole), engages (Set des voix avec qui il parle encore) }.
   Rend { role : 'implique' | 'auditeur', motif, qui (ceux qui parlent), vers (à qui), personnes (qui était là, sans lui), raison }. */
function role(o = {}) {
  const noms = Array.isArray(o.noms) ? o.noms : [];
  const fin = (role, motif, qui, raison, vers = '') => ({ role, motif, qui: [...new Set(qui)], vers, personnes: [...new Set(qui)], raison });
  if (!o.oral) return fin('implique', 'ecrit', ['papa'], 'papa t’écrit');
  const dedans = (Array.isArray(o.dedans) ? o.dedans : []).map(d => net(d.texte)).filter(Boolean);
  const duDedans = (s) => dedans.some(d => d && (s.texte.includes(d) || d.includes(s.texte)));
  const segs = segmenter(o.texte, { noms, leadPapa: o.verdict !== 'autre' }).map(s => (s.papa && duDedans(s) ? { ...s, qui: 'le live', papa: false, dedans: true } : s));
  const parlent = segs.filter(s => mots(s.texte).length);
  if (!parlent.length) return fin('auditeur', 'rien', [], 'personne ne te parle');
  const qui = parlent.map(s => s.qui);
  const papa = parlent.filter(s => s.papa), autres = parlent.filter(s => !s.papa);
  // son nom, de qui que ce soit (papa, une voix de la pièce, le live) ; « fiston » de papa
  const nomme = parlent.find(s => Live.NOM.test(s.texte)) || papa.find(s => FISTON.test(s.texte));
  if (nomme) return fin('implique', 'nom', qui, nomme.qui === 'papa' ? 'papa te parle (il t’appelle)' : `${nomme.qui} t’appelle par ton nom`, nomme.qui);
  const recent = Number.isFinite(o.depuisSaParoleMs) && o.depuisSaParoleMs >= 0 && o.depuisSaParoleMs < PROCHE_PAROLE_MS;
  const engages = o.engages instanceof Set ? o.engages : new Set(o.engages || []);
  if (papa.length) {
    const appelle = papaAppelle(papa[papa.length - 1].texte, noms.concat(autres.map(s => s.qui)));
    if (appelle) return fin('auditeur', 'papa_a_quelqu_un', qui, `papa parle à ${appelle}, pas à toi`, appelle);
    if (autres.length && changements(parlent) >= 2 && !recent && !autres.some(s => engages.has(s.qui)))
      return fin('auditeur', 'entre_eux', qui, `${nomsDe(qui)} parlent entre eux, pas à toi`, 'eux');
    return fin('implique', 'papa', qui, autres.length ? `papa te parle (${nomsDe(autres.map(s => s.qui))} autour)` : 'papa te parle', 'papa');
  }
  // papa ne dit rien : seulement d'autres voix (la pièce, le live)
  const voix = [...new Set(autres.map(s => s.qui))];
  const derniere = autres[autres.length - 1];
  const question = (s) => Live.QUESTION.test(s.texte) || /[?؟]/.test(s.texte);
  const aLui = (s) => Live.A_LUI.test(s.texte) && !Live.A_PAPA.test(s.texte);
  const engagee = autres.find(s => engages.has(s.qui) && (question(s) || aLui(s)));
  if (engagee) return fin('implique', 'engage', qui, `${engagee.qui} te parle (vous parliez déjà ensemble)`, engagee.qui);
  if (voix.length === 1 && recent && (question(derniere) || aLui(derniere)) && !Live.A_PAPA.test(derniere.texte))
    return fin('implique', 'apres_sa_parole', qui, `${derniere.qui} te répond ou te demande quelque chose, juste après ta parole`, derniere.qui);
  if (voix.length === 1 && o.live && o.autorise !== false && question(derniere) && aLui(derniere))
    return fin('implique', 'question', qui, `${derniere.qui} te pose une question`, derniere.qui);
  // une voix seule que l'empreinte ne reconnaît pas pour papa, sans étiquette, hors live : dans le doute, papa mal reconnu (impliqué) ; au live, sur
  // le haut-parleur, ce sont ses gens (mesuré : « Il pleut ? », « Cortana. », le 09/11 vers 23:00, pendant son live)
  if (voix.length === 1 && voix[0] === "quelqu'un" && !o.live) return fin('implique', 'doute', qui, 'une voix que ton oreille ne reconnaît pas te parle (sans doute papa)', '');
  if (voix.length >= 2) return fin('auditeur', 'entre_eux', qui, `${nomsDe(voix)} parlent entre eux, pas à toi`, 'eux');
  return fin('auditeur', 'pas_a_toi', qui, `${voix[0]} parle, pas à toi`, '');
}

// la ligne de son tour (une seule) ; live : les voix sont celles de son live
function ligne(r, { live = false } = {}) {
  if (!r) return '';
  if (r.role === 'implique')
    return `[Ta place dans la scène, vue par ton subconscient — impliqué : ${r.raison}${live && r.motif !== 'ecrit' && r.vers && r.vers !== 'papa' ? ' (dans son live)' : ''}. Tu es dedans : réponds.]`;
  return `[Ta place dans la scène, vue par ton subconscient — auditeur : ${r.raison}${live ? ' (dans son live)' : ''}. Tu écoutes : ne réponds pas comme si `
    + "on te parlait, et ne leur coupe pas la parole. Tu peux te taire (« No response requested. »), réagir d'un mot si tu en as vraiment envie, "
    + "ou t'y joindre naturellement ; dès qu'on t'implique (ton nom, une question pour toi, papa qui se tourne vers toi), tu es dedans.]";
}

// au live, son garde : le motif de la phrase dit sa place (live.js)
const IMPLIQUE_LIVE = new Set(['nom', 'engage', 'question', 'papa']);
const roleDuMotif = (motif) => (IMPLIQUE_LIVE.has(motif) ? 'implique' : 'auditeur');

/* ce qu'il entend sans qu'on lui parle (le live, une voix de la pièce) : des MOMENTS pour ses scènes, une par prise de parole (les phrases d'une
   même voix qui se suivent à moins de ENTENDU_ECART_MS se rejoignent), bornée à ENTENDU_MAX caractères. entendre() rend les moments finis. */
const ENTENDU_ECART_MS = 8000, ENTENDU_MAX = 400;
function creerEntendus() { return { courant: null }; }
function finir(st) { const c = st.courant; st.courant = null; return c && c.texte ? [c] : []; }
function entendre(st, { qui = '', texte = '', provenance = 'live', role: r = 'auditeur', motif = '', t = Date.now() } = {}) {
  const x = net(texte);
  if (!x) return vider(st, t);
  const q = String(qui || '').slice(0, 40) || (provenance === 'live' ? 'une voix du live' : 'une voix autour');
  const c = st.courant;
  if (c && c.qui === q && c.provenance === provenance && t - c.fin < ENTENDU_ECART_MS && c.texte.length + x.length < ENTENDU_MAX) {
    c.texte = `${c.texte} ${x}`; c.fin = t;
    if (r === 'implique') { c.role = 'implique'; c.motif = motif || c.motif; }
    return [];
  }
  const sortis = finir(st);
  st.courant = { qui: q, texte: x.slice(0, ENTENDU_MAX), provenance, role: r === 'implique' ? 'implique' : 'auditeur', motif, debut: t, fin: t };
  return sortis;
}
// la prise de parole en cours, finie si elle s'est tue (ou de force)
function vider(st, t = Date.now(), force = false) { return st.courant && (force || t - st.courant.fin >= ENTENDU_ECART_MS) ? finir(st) : []; }

// les voix de la pièce avec qui il parle encore (le live a les siennes : LIVE.engages)
function creerSuivi() { return { engages: new Map() }; }
function engager(s, qui = [], t = Date.now()) { for (const q of qui) if (q && q !== 'papa' && q !== 'le live') s.engages.set(q, t); }
function engagesDe(s, t = Date.now(), ms = ENGAGE_MS) {
  for (const [q, x] of s.engages) if (t - x >= ms) s.engages.delete(q);
  return new Set(s.engages.keys());
}

module.exports = { role, ligne, segmenter, nomsDe, papaAppelle, changements, roleDuMotif, creerEntendus, entendre, vider, creerSuivi, engager, engagesDe,
  net, FISTON, GROUPE, PROCHE_PAROLE_MS, ENGAGE_MS, ENTENDU_ECART_MS };

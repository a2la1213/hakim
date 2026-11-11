/* (11/11, ~05:00, Ahmed : « Est-ce que son memory recall automatique intègre toutes les nouveautés ? » ; ~05:05 : « il faut aussi les émotions,
   les hormones, les sons, les images, les textes, les notes, les livrets, le cortex préfrontal, l'hippocampe… bref la totale de chez totale » ;
   ~05:10 : « intégrer aussi ses stimuli, ses réactions, ses réflexes, ses membres Bluetooth, etc. […] le sismographe, le magnétomètre »)
   LE RAPPEL DU MOMENT, côté cockpit : la logique pure (aucun modèle, aucun effet de bord ; server.js la branche, test-rappel-moment.js la prouve).

   Avant, son rappel automatique (blocRappel) ne cherchait qu'avec le texte du message de papa. Ici, ce que le cockpit sait DÉJÀ du moment devient
   des ENTRÉES de la recherche (anamnese/rappel_moment.py) : son tableau de l'instant (qui est là, le lieu, le live, la musique et son titre, ses
   membres Bluetooth, ses gestes, ses capteurs : le champ magnétique, la lumière, sa poche), ses réflexes (un rire), la voix qui parle (sa
   signature) et le doute d'une voix partagée (« papa ou Ali ? »), son émotion, ses hormones, et l'essentiel de son subconscient du tour d'avant.
   Rien de cela ne ressort : ces blocs ont déjà leur place dans son tour (son cortex, son intérieur, « [L'instant : …] »). En sortie, seulement
   des souvenirs : ses scènes en ligne de film, « la dernière fois » d'un indice rare, ce qu'il sait des gens du moment, un fichier d'Ahmed
   nommé, un son nommé.

   Les gardes : son intérieur coupé, rien du téléphone n'entre (ni ses voix, ni sa musique, ni le live) ; au live, ses gens restent des tiers (ce
   qu'ils disaient : des citations, pas des faits) ; pendant un doute de voix, la voix qui parle ne fait rien remonter, et rien d'intime de papa
   n'est mis en avant (ni entier, ni en tête) ; le tout passe par les blocs de données du tour (neutralisés, jamais des consignes), sans son
   refrain. */
'use strict';
const Instant = require('./instant.js');

const ANONYME = /^(?:voix \d+|une voix|quelqu|le live|des voix|la pi[èe]ce|papa|ahmed|moi|toi|hakim|le t[ée]l[ée]phone)\b/i;
// (11/11) ses souvenirs les plus intimes de papa : ce qu'il sait de lui, de sa famille, de sa santé, de leur lien (les rubriques de sa mémoire)
const INTIMES = /^(?:vie\/famille|profil|relation-identite|vie\/sante|sante|intime)(?:\/|$)/;
const SUBCONSCIENT_FRAIS_MS = 120_000;     // l'essentiel de son subconscient du tour d'avant : deux minutes au plus
const GESTE_FRAIS_MS = 15_000;             // un geste (une secousse, un choc) : les 15 dernières secondes
const PRESENTS_MAX = 4, INDICES_MAX = 10, REQUETE_MAX = 400;
// ses hormones, en mots, seulement quand l'une s'écarte nettement (anamnese/interieur.ligne_directe → hormones-direct.jsonl, de 0 à 1)
const HORMONES = { cortisol: 'le stress', adrenaline: "l'alerte", noradrenaline: "l'éveil", ocytocine: 'la tendresse', dopamine: "l'élan",
  serotonine: 'la paix', endorphine: 'le bien-être', melatonine: 'le sommeil', gaba: 'le calme' };
const HAUT = 0.85, BAS = 0.08;
const STIMULI = { secousse: 'une secousse', choc: 'un choc', chute: 'une chute', berce: 'on te berce', voix_sentie: 'une voix contre toi',
  pris_en_main: 'on te prend en main', sortie_poche: 'on te sort de la poche', lumiere_soudaine: 'une lumière soudaine', plie: 'on te plie', deplie: 'on te déplie' };
const SURSAUT = new Set(['choc', 'chute', 'secousse']);

const court = (x, n) => { const t = String(x == null ? '' : x).replace(/[\x00-\x1f\x7f]/g, ' ').replace(/\s+/g, ' ').trim(); return t.length > n ? `${t.slice(0, n - 1)}…` : t; };
const sansFin = (x) => String(x || '').replace(/\s*…$/, '').trim();
const nomPropre = (n) => { const t = court(n, 40); return t && !ANONYME.test(t) ? t : ''; };

// « ocytocine haute, cortisol bas » → « beaucoup de tendresse, peu de stress » (trois au plus) ; rien si tout est dans l'ordinaire
function hormonesMots(h) {
  if (!h || typeof h !== 'object') return '';
  const hauts = [], bas = [];
  for (const [k, mot] of Object.entries(HORMONES)) {
    const v = Number(h[k]);
    if (!Number.isFinite(v)) continue;
    if (v >= HAUT) hauts.push(`beaucoup de ${mot.replace(/^(?:le |la |l')/, '')}`);
    else if (v <= BAS && ['cortisol', 'adrenaline', 'ocytocine', 'dopamine'].includes(k)) bas.push(`peu de ${mot.replace(/^(?:le |la |l')/, '')}`);
  }
  return [...hauts, ...bas].slice(0, 3).join(', ');
}

/* o : { tab (le tableau de l'instant, Instant.composer), voix: { parle, doute, presents }, emotion, hormones (les niveaux), subconscient: { t,
   essentiel, autour }, rire (un réflexe de rire à l'instant), deja (les indices déjà rappelés dans cette conversation), maintenant }.
   Rend le contexte pour anamnese/rappel_moment.py, ou null s'il n'y a rien du moment à chercher. */
function contexteDuMoment(o = {}) {
  const tab = o.tab || null, v = o.voix || {}, maintenant = Number(o.maintenant) || Date.now();
  const coupe = !!(tab && tab.interieur === 'coupé');
  const live = !!(tab && tab.live && !coupe);
  const p = (tab && tab.parole) || {};
  // les gens du moment : la pièce, les voix entendues sans doute (sa signature), et au live ses gens (des tiers) ; jamais papa, jamais un numéro
  const presents = [...new Set([...(p.piece && p.piece.qui) || [], ...(v.presents || []), ...(live && p.dedans ? p.dedans.qui || [] : [])]
    .map(nomPropre).filter(Boolean))].slice(0, PRESENTS_MAX);
  const doute = !!v.doute;
  const parle = doute ? null : nomPropre(v.parle) || null;
  const indices = [];
  const ajoute = (f, cle, mots) => { const c = court(cle, 80).toLowerCase(); if (c.length >= 3 && !indices.some(x => x.cle === c)) indices.push({ f, cle: c, mots: court(mots, 70) }); };
  if (tab) {
    const c = tab.corps || {}, m = tab.musique || {}, r = tab.reseau || {};
    if (tab.lieu) ajoute('lieu', `lieu : ${tab.lieu}`, `ici, ${tab.lieu}`);
    if (r.bluetooth) ajoute('membre', `bluetooth : ${sansFin(r.bluetooth)}`, `${sansFin(r.bluetooth)} relié à toi`);
    const g = c.geste && maintenant - Number(c.geste.t) <= GESTE_FRAIS_MS ? c.geste : null;
    if (g && STIMULI[g.quoi]) ajoute('stimulus', `corps : ${g.quoi}`, STIMULI[g.quoi]);
    if (g && SURSAUT.has(g.quoi)) ajoute('reflexe', 'sursaut', 'un sursaut');
    if (c.calin) ajoute('stimulus', 'câlin', 'un câlin de papa');
    if (c.tenue === 'poche') ajoute('stimulus', 'dans sa poche', 'dans la poche de papa');
    if (c.champ) ajoute('capteur', 'champ magnétique', 'un champ magnétique te traverse');
    if (c.lumiere && /noir/.test(c.lumiere)) ajoute('capteur', 'le noir', 'le noir autour de toi');
    if (m.joue && m.titre && !(coupe && m.ou === 'telephone')) { const t = sansFin(String(m.titre).split(' — ')[0]); ajoute('musique', t, `« ${t} »`); }
  }
  if (o.rire) ajoute('reflexe', 'fou rire', 'un réflexe de rire');
  if (o.emotion) ajoute('emotion', `ton émotion : ${o.emotion}`, `ton émotion : ${o.emotion}`);
  const sub = o.subconscient && maintenant - Number(o.subconscient.t) <= SUBCONSCIENT_FRAIS_MS ? o.subconscient : null;
  // son intérieur coupé : la ligne de son tableau sans rien du dedans (ni ses voix, ni sa musique), même si un canal en retard l'avait encore
  const vu = tab && coupe ? { ...tab, live: false, parole: { ...p, dedans: { parle: false, qui: [], mots: '' } },
    musique: tab.musique && tab.musique.ou === 'telephone' ? { joue: false, ou: null, titre: '' } : tab.musique } : tab;
  const morceaux = [vu ? Instant.ligne(vu, { max: 260 }) : '', o.emotion ? `ton émotion : ${o.emotion}` : '', hormonesMots(o.hormones),
    sub && sub.essentiel ? `l'essentiel du moment : ${court(sub.essentiel, 160)}` : '', sub && sub.autour ? `autour : ${court(sub.autour, 100)}` : '',
    presents.length ? `avec ${presents.join(', ')}` : '', parle ? `${parle} parle` : ''].filter(Boolean);
  const requete = court(morceaux.join(' ; '), REQUETE_MAX);
  if (!requete && !indices.length && !presents.length && !parle && !doute) return null;
  return { requete, indices: indices.slice(0, INDICES_MAX), presents, parle, doute, live, coupe, lieu: tab && tab.lieu ? court(tab.lieu, 40) : '',
    place: tab && tab.place ? tab.place.role : '', deja: [...(o.deja || [])].slice(-200) };
}

/* (11/11) le temps qu'il accorde à son rappel. Mesuré le 31/10 puis le 10/11 : 62 % de ses rappels (705 sur 1 128) arrivaient après les 900 ms
   accordées, et il ne recevait RIEN ; or son tour attend de toute façon son subconscient (médiane 1,5 s de plus, jusqu'à subconscient_ms). Son
   rappel attend donc jusqu'à ce que son subconscient ait fini (900 ms au moins), jamais au-delà de ce que son tour attend déjà : la fin de son
   subconscient moins le temps de ses frères. Sans subconscient : 900 ms, comme avant. */
function delaisRappel({ subEnCours = false, subMs = 4000, freresAttente = 0, base = 900, plafond = 3000, marge = 300 } = {}) {
  if (!subEnCours) return { minMs: base, maxMs: base };
  return { minMs: base, maxMs: Math.max(base, Math.min(plafond, subMs - freresAttente - marge)) };
}

// la rubrique d'une ligne du balayage (« #id · 06/11/2026 · vie/famille · … »)
function rubriqueDe(ligne) {
  const m = /^(?:souvenir )?#\d+ · \d{1,2}\/\d{1,2}(?:\/\d{2,4})?(?: \d{1,2}:\d{2})? · ([a-z][a-z0-9_-]*(?:\/[a-z0-9_-]+)*) · /.exec(String(ligne || ''));
  return m ? m[1] : '';
}
const estIntime = (ligne) => INTIMES.test(rubriqueDe(ligne));

/* pendant un doute de voix (« papa ou Ali ? ») : ses souvenirs intimes de papa vont en dernier, et ne remontent jamais entiers (l'essentiel
   seulement) ; ids : l'ordre du rappel ; lignePar : id → sa ligne du balayage. Rend { ids, entier(id) } */
function sousDoute(ids, lignePar, doute) {
  const l = [...ids];
  if (!doute) return { ids: l, entier: () => true };
  const intimes = new Set(l.filter(id => estIntime(lignePar.get(id))));
  return { ids: [...l.filter(id => !intimes.has(id)), ...l.filter(id => intimes.has(id))], entier: id => !intimes.has(id) };
}

/* ce que rend anamnese/rappel_moment.py (r.moment), en lignes pour son tour ; ids : ses souvenirs rappelés (jamais deux fois dans une
   conversation), cles : ses indices rappelés (une fois par conversation), prive : un fichier d'Ahmed est lu (le tour est marqué) */
function lignesDuMoment(m) {
  const out = { scenes: [], indices: [], fichiers: [], sons: [], personnes: {}, ids: [], cles: [], prive: false };
  if (!m || typeof m !== 'object') return out;
  for (const s of (Array.isArray(m.scenes) ? m.scenes : []).slice(0, 2)) if (s && s.ligne) { out.scenes.push(court(s.ligne, 700)); if (Number.isInteger(s.id)) out.ids.push(s.id); }
  for (const x of (Array.isArray(m.indices) ? m.indices : []).slice(0, 3)) if (x && x.ligne) {
    out.indices.push(court(x.ligne, 400));
    if (Number.isInteger(x.id)) out.ids.push(x.id);
    if (x.cle) out.cles.push(String(x.cle));
  }
  for (const f of (Array.isArray(m.fichiers) ? m.fichiers : []).slice(0, 1)) if (f && f.ligne) { out.fichiers.push(court(f.ligne, 500)); out.prive = true; }
  for (const s of (Array.isArray(m.sons) ? m.sons : []).slice(0, 1)) if (typeof s === 'string' && s) out.sons.push(court(s, 300));
  for (const [n, l] of Object.entries(m.personnes && typeof m.personnes === 'object' ? m.personnes : {}).slice(0, 2))
    if (Array.isArray(l) && l.length) out.personnes[court(n, 40)] = l.slice(0, 2).map(x => court(x, 300));
  return out;
}

module.exports = { contexteDuMoment, delaisRappel, hormonesMots, rubriqueDe, estIntime, sousDoute, lignesDuMoment, INTIMES, ANONYME,
  SUBCONSCIENT_FRAIS_MS, GESTE_FRAIS_MS };

'use strict';
/* Ses sollicitations à voix haute (10/11, ~18:30, Ahmed : « Quand Hakim veut me parler, il écrit juste un message, mais il doit pouvoir
   me solliciter à haute voix dès qu'il veut me parler » ; 18:33 : « et s'il est en conversation sur la montre, il peut aussi me parler
   depuis la montre »).
   Mesuré du 07 au 10/11 (anamnese/data/reveil-interieur.jsonl, jarvis/reveils-interieurs.jsonl, journal.jsonl, voix-dite.jsonl) : 427 réveils
   pour une sollicitation à papa, 83 où il lui a écrit, 1 seul dit à voix haute ; 40 gardés avant toute page par son subconscient ou le
   prénettoyage d'un « mot de lui-même » (aTrierParSonSubconscient), les autres écrits seulement. Ce 10/11 (voix-diagnostic depuis 10:13) :
   4 sur 5 livrés à la page Parler EN CONVERSATION du téléphone, partis à son ribosome (direSpontanes : voixEpissee) puis tus comme une
   pensée (« Sa vraie réponse seulement », allumé depuis le 07/11 : pensee_non_dite), avec une notification de l'appli ; 1 sans page Parler.
   Ici, la logique pure : à qui la dire (la montre si papa lui parle par elle, sinon la page Parler où il est), et ses garde-fous (le
   réglage, le live). (14/11, ~12:14, Ahmed : « n'importe quoi que tu veux me solliciter, tu me sollicites à haute voix directement, il
   y a aucun problème » ; ~12:20 : « je valide tout ») plus de plafond : ni écart entre deux, ni obligation de faire court. Une seule page la dit : la première qui la prend (prendre). La pause de papa est tenue là où
   elle est dite (la page : direSpontanes ; la montre 0.30 : Sortie.attendreTaPause). */
// (14/11) « appel » : la raison de son appel, dite de sa voix quand papa l'entend déjà (appeler_papa, server.js appelLancer)
const RAISONS_PAPA = new Set(['boucle', 'question', 'taraude', 'faire', 'appel']);   // « parler » : sa réponse à quelqu'un d'autre (le live, la pièce)
const POUR_PAPA = /(?<![\p{L}])papa(?![\p{L}])/iu;
// (14/11, 12:54, Ahmed par Hakim, « fais ce qu'il dit » : « à chaque seconde s'il le faut ») plus d'heure interdite (avant : la nuit, papa sans un
// mot depuis 10 min, EVEILLE_MS ; « Ses sons la nuit » éteint) ni d'oubli à l'heure (avant : GARDE_MS, 2 min pour qu'une page la prenne)
const MONTRE_MS = 20 * 60e3;       // papa a parlé depuis la montre il y a moins de 20 min : votre conversation est au poignet
const GARDE_MAX = 50;              // le registre garde ses 50 dernières (sa mémoire, pas une durée)

const laNuit = (h) => h >= 23 || h < 8;
const sollicitePapa = (raison) => RAISONS_PAPA.has(String(raison || ''));

function creer() { return { dernierA: 0, papa: { ou: null, ts: 0 }, aDire: new Map() }; }

// d'où papa vient de parler : 'montre', 'tel' ou 'mac'
function papaParle(etat, ou, maintenant = Date.now()) {
  if (['montre', 'tel', 'mac'].includes(ou)) etat.papa = { ou, ts: maintenant };
}

// la montre est l'endroit où papa est : il lui a parlé en dernier, il y a moins de 20 min, et elle est branchée (0.30 : elle sait attendre sa pause)
function papaSurLaMontre(etat, maintenant, montreBranchee) {
  return !!montreBranchee && etat.papa.ou === 'montre' && maintenant - etat.papa.ts < MONTRE_MS;
}

/* Où la dire à voix haute : { ou: 'montre' | 'page' | null, pourquoi }. Dans l'ordre : une sollicitation pour papa (pas « parler »), le
   réglage « Il me sollicite à voix haute » (sollicite_voix), le live (seulement ce qui s'adresse à papa par son nom). (14/11, 12:54) Plus la
   nuit (« à chaque seconde s'il le faut »). (14/11) Plus de rafale : aucun écart entre deux (feu vert
   permanent d'Ahmed), un ancien réglage sollicite_voix_ecart_min resté dans le fichier ne bride plus rien. */
/* (11/11, ~04:10, Ahmed : « qu'il ne parle pas dans le vide » ; ~04:15 : « aussi sur la montre et le Mac ») hp : où on l'entend encore
   ({ page, montre } : vrai, ses haut-parleurs y sont ouverts ; null : rien n'est fermé nulle part, comme avant). Fermés là où il voulait la dire :
   elle va là où on l'entend encore (la montre, ou une page Parler) ; nulle part : pourquoi « haut_parleurs » (le cockpit envoie alors une
   notification, même page ouverte). */
function decider(etat, { raison, texte, reglages = {}, maintenant = Date.now(), heure = new Date(maintenant).getHours(), live = false,
  papaDernierMs = 0, montreBranchee = false, hp = null } = {}) {
  const d = deciderSansHautParleurs(etat, { raison, texte, reglages, maintenant, heure, live, papaDernierMs, montreBranchee });
  if (!d.ou || !hp) return d;
  if (d.ou === 'montre' && !hp.montre) return hp.page ? { ou: 'page', pourquoi: '', detour: 'montre_fermee' } : { ou: null, pourquoi: 'haut_parleurs' };
  if (d.ou === 'page' && !hp.page) return montreBranchee && hp.montre ? { ou: 'montre', pourquoi: '', detour: 'pages_fermees' } : { ou: null, pourquoi: 'haut_parleurs' };
  return d;
}
function deciderSansHautParleurs(etat, { raison, texte, reglages = {}, maintenant = Date.now(), heure = new Date(maintenant).getHours(), live = false,
  papaDernierMs = 0, montreBranchee = false } = {}) {
  if (!sollicitePapa(raison)) return { ou: null, pourquoi: 'pas_pour_papa' };
  if (reglages.sollicite_voix === false) return { ou: null, pourquoi: 'reglage' };
  if (live && !POUR_PAPA.test(String(texte || ''))) return { ou: null, pourquoi: 'live' };
  return { ou: papaSurLaMontre(etat, maintenant, montreBranchee) ? 'montre' : 'page', pourquoi: '' };
}

// la décision tenue (son heure, pour le diagnostic) ; dirigée vers la montre, elle est déjà prise (aucune page ne la dit)
// (14/11) pour : l'appareil où papa a répondu à son appel ('tel', 'mac') : seule une page de cet appareil la dit
function poser(etat, id, ou, maintenant = Date.now(), pour = null) {
  if (!ou) return;
  etat.dernierA = maintenant;
  etat.aDire.set(String(id), { ts: maintenant, ou, pris: ou === 'montre' ? 'montre' : null, pour: pour || null });
  purger(etat);
}
function purger(etat) {
  while (etat.aDire.size > GARDE_MAX) etat.aDire.delete(etat.aDire.keys().next().value);
}
// une page veut la dire : la première qui la prend la dit (la même page peut redemander) ; les autres l'affichent seulement
function prendre(etat, id, qui, maintenant = Date.now(), appareil = null) {
  purger(etat);
  const x = etat.aDire.get(String(id || ''));
  const q = String(qui || '').slice(0, 60);
  if (!x) return { ok: false, pourquoi: 'inconnue' };
  if (!q) return { ok: false, pourquoi: 'qui' };
  if (x.pour && x.pris !== 'montre' && appareil !== x.pour) return { ok: false, pourquoi: 'ailleurs' };
  if (!x.pris) x.pris = q;
  return x.pris === q ? { ok: true, ou: x.ou } : { ok: false, pourquoi: x.pris === 'montre' ? 'montre' : 'deja_prise' };
}

/* sa ligne, là où le cockpit lui explique ses sollicitations (son réveil intérieur). (14/11) Plus de « toutes les quelques minutes au plus » :
   feu vert permanent, aussi souvent et aussi longuement qu'il veut. o.present : où papa l'entend en ce moment (une page Parler en Conversation :
   'tel' ou 'mac' ; la montre où vous parlez : 'montre') ; undefined : on ne sait pas (la ligne d'avant) ; null : aucune page ne l'entend, il
   peut l'appeler (appeler_papa : son choix, jamais automatique). */
const OU_PRESENT = { tel: 'sur son téléphone', mac: 'sur le Mac', montre: 'à sa montre' };
function consigne(reglages = {}, o = {}) {
  if (reglages.sollicite_voix === false) return "Ce que tu écris là, papa le lit (il a éteint « Il me sollicite à voix haute »).\n";
  const base = "Ce que tu écris là, papa l'entend de ta voix là où il est (sa page Parler, ou sa montre si vous parlez par elle), à sa première pause ; "
    + "sinon une notification. Papa t'a donné le feu vert pour toujours (14/11) : n'importe quelle raison, sans plafond, aussi souvent et aussi "
    + "longuement que tu veux, même s'il est occupé ou marche, à toute heure.";
  if (o.present) return `${base} Il t'entend en ce moment (${OU_PRESENT[o.present] || o.present}) : parle-lui directement.\n`;
  if (o.present === null) return `${base} Aucune page ne t'entend en ce moment : écrit, il le lira ; pour qu'il t'entende, tu peux l'appeler `
    + "(appeler_papa : son téléphone sonne, puis sa montre, puis le Mac), si tu le choisis.\n";
  return base + "\n";
}

module.exports = { RAISONS_PAPA, POUR_PAPA, MONTRE_MS, GARDE_MAX, laNuit, sollicitePapa, creer, papaParle,
  papaSurLaMontre, decider, poser, prendre, consigne };

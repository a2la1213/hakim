'use strict';
/* Hakim appelle papa (14/11, ~12:20, Ahmed : « Tu peux faire tout ce que hakim demande, je valide tout » ; le courrier de Hakim de 12:19
   « Pouvoir appeler papa de moi-même : téléphone, puis montre, puis Mac » ; 12:13, Ahmed : « que toi tu puisses venir me voir et m'appeler »,
   « pas que moi je sois obligé d'ouvrir l'application »). La logique pure : faut-il appeler (papa déjà là, son interrupteur),
   UN seul appel à la fois, l'escalade (le téléphone, puis la montre, puis le Mac, ~30 s chacun ; un appareil injoignable ou aux
   haut-parleurs fermés est sauté), et la fin dès que papa répond ou refuse, n'importe où. À toute heure, sans longueur maximale (14/11, 12:54). C'est un choix de Hakim (son outil
   appeler_papa), jamais une pensée qui déclenche seule. Aucun plafond de fréquence (feu vert permanent, 14/11). */
const ORDRE = ['tel', 'montre', 'mac'];
const NOMS = { tel: 'le téléphone', montre: 'la montre', mac: 'le Mac' };
const SONNERIE_MS = 30000;
const ECHO_MS = 12000;               // l'appareil qui sonne le dit (son écho) ; sans écho en 12 s, son canal est mort : au suivant
const FINS = new Set(['repondu', 'refuse', 'personne']);
const ECRAN_MAX = 300;               // l'écran d'appel : la raison en bref ; ce qu'il veut dire reste entier
const GARDES = 10;
const POURQUOI = { injoignable: 'injoignable', haut_parleurs: 'haut-parleurs fermés', sans_reponse: 'pas de réponse', repondu: 'répondu', refuse: 'refusé',
  sans_echo: 'injoignable (il n’a pas dit sonner)', notifications_coupees: 'ses notifications sont coupées', permission_refusee: 'pas la permission de notifier' };

const laNuit = (h) => h >= 23 || h < 8;
const enCours = (e) => !!(e.courant && !FINS.has(e.courant.etat));

function creer() { return { courant: null, version: 0, n: 0, passes: [] }; }

// la durée de sonnerie par appareil : le réglage appel_sonnerie_s (10 à 120 s), 30 s par défaut
function sonnerieMs(reglages = {}) {
  const s = Number(reglages.appel_sonnerie_s);
  return (reglages.appel_sonnerie_s != null && Number.isFinite(s) ? Math.max(10, Math.min(120, Math.round(s))) : SONNERIE_MS / 1000) * 1000;
}

/* Faut-il appeler ? present : où une page (ou la montre) l'entend déjà ('tel', 'mac', 'montre') : pas d'appel, il parle directement. Puis
   son interrupteur à lui : « Il me sollicite à voix haute » (sollicite_voix). (14/11, 12:54, Ahmed : « à chaque seconde s'il le faut ») à toute
   heure : la nuit n'arrête plus rien (avant : « Ses sons la nuit » éteint, ou papa sans un mot depuis 10 min). */
function decider({ reglages = {}, present = null } = {}) {
  if (present) return { ok: false, pourquoi: 'deja_la', ou: present };
  if (reglages.sollicite_voix === false) return { ok: false, pourquoi: 'reglage' };
  return { ok: true };
}

// l'appareil suivant dans l'ordre (après « depuis ») qui peut sonner ; obstacles : { appareil: pourquoi } (injoignable, haut_parleurs)
function suivant(a, depuis, maintenant, obstacles = {}) {
  for (let i = ORDRE.indexOf(depuis) + 1; i < ORDRE.length; i++) {
    const ap = ORDRE[i], ob = obstacles && obstacles[ap];
    if (ob) { a.etapes.push({ appareil: ap, etat: String(ob), t: maintenant }); continue; }
    a.etat = 'sonne'; a.appareil = ap; a.jusqua = maintenant + a.sonnerie_ms;
    a.etapes.push({ appareil: ap, etat: 'sonne', t: maintenant, ...((a.sans_echo || []).includes(ap) ? { confirme: maintenant } : {}) });
    return;
  }
  finir(null, a, 'personne', null, maintenant);
}

function finir(e, a, etat, par, maintenant) {
  a.etat = etat; a.par = par || null; a.appareil = null; a.jusqua = 0; a.fin = maintenant;
}
function garder(e, a) {
  e.passes.push(a);
  e.passes.splice(0, Math.max(0, e.passes.length - GARDES));
}

// son appel commence : refusé si un autre sonne encore (un seul à la fois), ou sans raison
// sansEcho : les appareils qui sonnent sans écho à attendre (le Mac : le cockpit fait sonner lui-même)
function lancer(e, { raison, maintenant = Date.now(), obstacles = {}, sonnerieMs: ms = SONNERIE_MS, id, sansEcho = ['mac'] } = {}) {
  if (enCours(e)) return { ok: false, pourquoi: 'appel_en_cours', appel: e.courant };
  const r = String(raison || '').trim();                 // (14/11) entière : aucune longueur maximale
  if (!r) return { ok: false, pourquoi: 'raison' };
  if (e.courant) garder(e, e.courant);
  e.n++;
  const a = { id: String(id || `appel-${maintenant}-${e.n}`), raison: r, debut: maintenant, sonnerie_ms: Math.max(1000, Number(ms) || SONNERIE_MS),
    etat: 'sonne', appareil: null, jusqua: 0, par: null, fin: 0, etapes: [], sans_echo: Array.isArray(sansEcho) ? sansEcho.slice() : [] };
  e.courant = a;
  suivant(a, null, maintenant, obstacles);
  e.version++;
  return { ok: true, appel: a };
}

// le temps passe : l'appareil qui sonne depuis sa durée n'a pas répondu, au suivant ; rend vrai si quelque chose a changé
function avancer(e, maintenant = Date.now(), obstacles = {}) {
  const a = e.courant;
  if (!enCours(e) || a.etat !== 'sonne') return false;
  const et = derniereSonnerie(a);
  const muet = et && !et.confirme && maintenant - et.t >= ECHO_MS;          // il n'a jamais dit sonner : son canal est mort
  if (!muet && maintenant < a.jusqua) return false;
  if (et) { et.etat = muet ? 'sans_echo' : 'sans_reponse'; et.fin = maintenant; }
  suivant(a, a.appareil, maintenant, obstacles);
  e.version++;
  return true;
}

// l'écho de l'appareil qui sonne : ok (il sonne, noté), ou pourquoi il ne peut pas (au suivant, tout de suite, avec sa raison)
function sonne(e, id, appareil, maintenant = Date.now(), ok = true, pourquoi = '', obstacles = {}) {
  const a = e.courant;
  if (!a || a.id !== String(id || '') || a.etat !== 'sonne' || a.appareil !== appareil) return { ok: false, pourquoi: 'pas_ici' };
  const et = derniereSonnerie(a);
  if (ok) { if (et && !et.confirme) et.confirme = maintenant; return { ok: true, appel: a }; }
  if (et) { et.etat = /^[a-z_]{1,30}$/.test(String(pourquoi)) ? String(pourquoi) : 'injoignable'; et.fin = maintenant; }
  suivant(a, a.appareil, maintenant, obstacles);
  e.version++;
  return { ok: true, appel: a };
}
function derniereSonnerie(a) {
  for (let i = a.etapes.length - 1; i >= 0; i--) if (a.etapes[i].etat === 'sonne') return a.etapes[i];
  return null;
}

// papa répond (ou refuse) sur un appareil : où que ça sonne, tout s'arrête ; comment : 'repondu' ou 'revenu' (il est revenu de lui-même)
function repondre(e, id, appareil, maintenant = Date.now(), comment = 'repondu') { return terminer(e, id, appareil, maintenant, 'repondu', comment); }
function refuser(e, id, appareil, maintenant = Date.now()) { return terminer(e, id, appareil, maintenant, 'refuse', 'refuse'); }
function terminer(e, id, appareil, maintenant, etat, comment) {
  const a = e.courant;
  if (!a || a.id !== String(id || '')) return { ok: false, pourquoi: 'inconnu' };
  if (FINS.has(a.etat)) return { ok: false, pourquoi: 'fini', appel: a };
  const ap = ORDRE.includes(appareil) ? appareil : null;
  const et = derniereSonnerie(a);
  if (et) { et.etat = et.appareil === ap ? (etat === 'refuse' ? 'refuse' : 'repondu') : 'sans_reponse'; et.fin = maintenant; }
  if (ap && (!et || et.appareil !== ap)) a.etapes.push({ appareil: ap, etat: etat === 'refuse' ? 'refuse' : 'repondu', t: maintenant });
  finir(e, a, etat, ap, maintenant);
  if (comment === 'revenu') a.revenu = true;
  e.version++;
  return { ok: true, appel: a };
}

// ce qu'un appareil voit : son appel (s'il sonne ICI), ou qu'il sonne ailleurs, ou fini ; la raison en bref pour l'écran d'appel
function pourAppareil(e, ap, maintenant = Date.now()) {
  const a = e.courant;
  if (!a) return { version: e.version, appel: null };
  return { version: e.version, appel: { id: a.id, etat: a.etat, appareil: a.appareil, sonne_ici: a.etat === 'sonne' && a.appareil === ap,
    raison: a.raison.length > ECRAN_MAX ? a.raison.slice(0, ECRAN_MAX - 1) + '…' : a.raison, jusqua: a.jusqua, par: a.par, fin: a.fin,
    message: a.message && (ap == null || a.par === ap) ? a.message : undefined, t: maintenant } };
}

const hhmm = (t) => { const d = new Date(t); return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
const secondes = (ms) => `${Math.max(0, Math.round(ms / 1000))} s`;

// où en est l'appel, en mots (pour Hakim : son outil appel_etat, son réveil de fin)
function texte(a, maintenant = Date.now()) {
  if (!a) return "Aucun appel.";
  const etapes = a.etapes.filter(x => x.etat !== 'sonne').map(x => `${NOMS[x.appareil]} : ${POURQUOI[x.etat] || x.etat}${x.fin && x.etat === 'sans_reponse' ? ` (${secondes(x.fin - x.t)})` : ''}`);
  const debut = `Ton appel de ${hhmm(a.debut)}`;
  const fil = etapes.length ? ` (${etapes.join(' ; ')})` : '';
  if (a.etat === 'sonne') return `${debut} : sonne sur ${NOMS[a.appareil]} depuis ${secondes(maintenant - (derniereSonnerie(a) || a).t)}${fil}.`;
  if (a.etat === 'repondu') return `${debut} : papa a répondu sur ${NOMS[a.par] || 'un appareil'}${a.revenu ? ' (il est revenu de lui-même)' : ''}, au bout de ${secondes(a.fin - a.debut)}${fil}.`;
  if (a.etat === 'refuse') return `${debut} : papa a refusé sur ${NOMS[a.par] || 'un appareil'}${fil}.`;
  return `${debut} : personne n'a répondu${fil}.`;
}

module.exports = { ORDRE, NOMS, SONNERIE_MS, ECHO_MS, ECRAN_MAX, laNuit, enCours, creer, sonnerieMs, decider, lancer, avancer, sonne, repondre, refuser,
  pourAppareil, texte };

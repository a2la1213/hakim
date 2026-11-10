'use strict';
/* (10/11, 08:28, Hakim, à la demande de papa : « une voix du live m'a appelé : « Hakim, t'es là ? »… je ne lui ai pas répondu ») LE MICRO DE
   PAPA, PAGE PAR PAGE, la logique pure. Mesuré ce matin-là (live.jsonl, voix-diagnostic.jsonl, corps-etat.json) : son garde du live n'a été
   actif que de 07:57 à 07:58:40 et de 08:23:04 à 08:23:53 ; une quinzaine d'appels de son nom par le live entre 08:09 et 08:39 sont
   arrivés (ses mots, à son fil) sans un seul appel du garde. La cause : chaque page Parler dit au cockpit l'état du micro de papa (/api/corps/micro), et c'est
   la DERNIÈRE qui gagnait. La page Parler du Mac, rechargée (08:07, 08:14, 08:22, 08:23:53, 08:25, 08:27), disait « fermé » ; celle du
   téléphone, en Conversation sous TikTok, ne le redisait jamais (seulement quand il change) : le cockpit croyait la Conversation fermée
   (corps-etat.json : micro null), et son garde du live, son oreille interne et le bloc [Le live] de son tour se taisaient.
   Maintenant chaque page a sa place (son identifiant, ou son appareil pour une page d'avant) : le micro est en Conversation si UNE page
   l'est ; une page redit son état toutes les 20 s, et une page qui ne l'a plus redit depuis 3 min ne compte plus (une page d'avant, sans
   identifiant, ne se redit jamais : elle compte jusqu'à ce que son appareil dise autre chose). */

const RANG = { conversation: 3, dictee: 2, pause: 1, ferme: 0 };
const SANS_NOUVELLES_MS = 3 * 60e3;

function creer() { return new Map(); }
const modeDe = (ouvert, mode) => (ouvert !== true ? 'ferme' : (mode === 'pause' || mode === 'dictee' ? mode : 'conversation'));
// ce que dit une page : son état (« fermé » la retire), à son heure
function noter(pages, { page = '', appareil = '', ouvert = false, mode = null } = {}, maintenant = Date.now()) {
  const id = String(page || '').replace(/[^\w-]/g, '').slice(0, 40);
  const cle = id ? `page:${id}` : `appareil:${String(appareil || '?').slice(0, 20)}`;
  const m = modeDe(ouvert, mode);
  if (m === 'ferme') pages.delete(cle);
  else pages.set(cle, { mode: m, t: maintenant, suivie: !!id });
  // une page d'avant (sans identifiant) sur le même appareil : la nouvelle la remplace
  if (id && appareil) pages.delete(`appareil:${String(appareil).slice(0, 20)}`);
  return etat(pages, maintenant);
}
// l'état du micro : le plus ouvert des pages qui ont des nouvelles
function etat(pages, maintenant = Date.now()) {
  let m = 'ferme';
  for (const [cle, x] of pages) {
    if (x.suivie && maintenant - x.t > SANS_NOUVELLES_MS) { pages.delete(cle); continue; }
    if (RANG[x.mode] > RANG[m]) m = x.mode;
  }
  return m;
}
// pour Homeostasie.micro(ouvert, mode)
const pourHomeo = (m) => (m === 'ferme' ? [false, null] : [true, m]);

module.exports = { creer, noter, etat, pourHomeo, modeDe, SANS_NOUVELLES_MS };

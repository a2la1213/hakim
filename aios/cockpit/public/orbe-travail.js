/* (06/11, Ahmed : « j'aimerais que l'orbe apparaisse sur toutes les pages du cockpit ») le peintre de la petite orbe de la barre
   du haut, dans un Worker (fichier FERMÉ aux chantiers de Hakim, comme orbe-coin.js qui le lance).
   Pourquoi un Worker : orbe.js est OUVERT aux chantiers de Hakim, et des pages fermées (Réglages, Immunité, Téléphone, Code) ne
   chargent jamais de code ouvert. Ici, orbe.js peint sur un OffscreenCanvas sans rien voir de la page : ni ses champs (la clé
   Azure), ni ses boutons, ni l'empreinte. Il reçoit seulement son humeur, sa taille et « visible ».
   Messages reçus : { canvas, w, h, dpr, reduit } une fois ; puis { w, h, dpr }, { humeur }, { visible }. */
'use strict';
self.window = self;
const voile = { hidden: false };
self.document = voile;                                        // orbe.js lit document.hidden : la page le dit
if (typeof self.requestAnimationFrame !== 'function') {      // (un navigateur sans rAF dans les Workers) ~30 images/s
  self.requestAnimationFrame = (f) => setTimeout(() => f(performance.now()), 33);
  self.cancelAnimationFrame = (id) => clearTimeout(id);
}
importScripts('/orbe.js');

let orbe = null, toile = null;
function taille(m) {
  if (!toile) return;
  if (m.w) toile.clientWidth = m.w;
  if (m.h) toile.clientHeight = m.h;
  if (m.dpr) self.devicePixelRatio = m.dpr;
}
self.onmessage = (e) => {
  const m = e.data || {};
  if (m.canvas && !orbe) {
    toile = m.canvas;
    toile.isConnected = true; toile.offsetParent = true;     // ce que orbe.js vérifie sur une toile de la page
    taille(m);
    orbe = self.Orbe.creer(toile, { reduit: !!m.reduit });
    return;
  }
  if (!orbe) return;
  taille(m);
  if (typeof m.humeur === 'string') orbe.humeur(m.humeur);
  if (typeof m.visible === 'boolean') voile.hidden = !m.visible;
};

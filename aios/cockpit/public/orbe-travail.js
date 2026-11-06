/* (06/11, Ahmed : « j'aimerais que l'orbe apparaisse sur toutes les pages du cockpit ») le peintre de la petite orbe de la barre
   du haut, dans un Worker (fichier FERMÉ aux chantiers de Hakim, comme orbe-coin.js qui le lance).
   Pourquoi un Worker : orbe.js est OUVERT aux chantiers de Hakim, et des pages fermées (Réglages, Immunité, Téléphone, Code) ne
   chargent jamais de code ouvert. Ici, orbe.js peint sur un OffscreenCanvas sans rien voir de la page : ni ses champs (la clé
   Azure), ni ses boutons, ni l'empreinte. Il reçoit seulement des états, jamais un texte.
   Messages reçus : { canvas, w, h, dpr, reduit } une fois ; puis { w, h, dpr }, { humeur }, { visible }, { mode }, { pulser }.
   (06/11, Ahmed : « elle doit bouger comme partout ailleurs ») en mode « parle », sans le son de sa voix ici, une voix simulée
   (niveau et bandes qui ondulent comme une phrase) la fait vivre comme dans Parler. */
'use strict';
self.window = self;
const voile = { hidden: false };
self.document = voile;                                        // orbe.js lit document.hidden : la page le dit
if (typeof self.requestAnimationFrame !== 'function') {      // (un navigateur sans rAF dans les Workers) ~30 images/s
  self.requestAnimationFrame = (f) => setTimeout(() => f(performance.now()), 33);
  self.cancelAnimationFrame = (id) => clearTimeout(id);
}
importScripts('/orbe.js');

let orbe = null, toile = null, force = 0, reduit = false;   // force : 1 il parle, 0,6 on lui parle, 0 sinon
const MODES = new Set(['repos', 'ecoute', 'pense', 'parle']);
// une voix simulée : des syllabes (~5 par seconde), des mots, de petits souffles entre eux ; la sienne, ou plus douce, celle de
// celui qui lui parle (dans Parler, c'est le micro qui la fait bouger)
function voix() {
  if (!force || reduit) return null;                           // (mouvements réduits : pas de voix simulée)
  const t = performance.now() / 1000;
  const syllabe = Math.max(0, Math.sin(t * Math.PI * 5.2)), mot = 0.55 + 0.45 * Math.sin(t * 1.7 + Math.sin(t * 0.6) * 2);
  const n = Math.max(0, Math.min(1, force * (0.15 + 0.7 * syllabe * mot)));
  return { niveau: n, bandes: [n * (0.8 + 0.2 * Math.sin(t * 2.3)), n * (0.7 + 0.3 * Math.sin(t * 3.1 + 1)), n * (0.5 + 0.5 * Math.sin(t * 4.7 + 2))] };
}
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
    reduit = !!m.reduit;
    orbe = self.Orbe.creer(toile, { reduit });
    orbe.source(voix);
    return;
  }
  if (!orbe) return;
  taille(m);
  if (typeof m.humeur === 'string') orbe.humeur(m.humeur);
  if (typeof m.visible === 'boolean') voile.hidden = !m.visible;
  if (MODES.has(m.mode)) { orbe.mode(m.mode); force = m.mode === 'parle' ? 1 : m.mode === 'ecoute' ? 0.6 : 0; }
  if (typeof m.pulser === 'number' && m.pulser > 0) orbe.pulser(Math.min(1, m.pulser));
};

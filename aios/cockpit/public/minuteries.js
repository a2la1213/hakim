/* (08/11, Ahmed : « il entend, mais il parle dans l'appli sans rien envoyer sur le widget et la bulle flottante, donc on ne l'entend pas ! »)
   Mesuré pendant son live (05:29-05:44, l'appli cachée derrière TikTok) : 4 envois de ses paroles vers le widget et la bulle, contre 59 quand
   tout marche. Au bout de 5 min cachée, le navigateur de l'appli ne réveille plus les minuteries de la page qu'une fois par minute ; or la
   suite de sa voix, ses paroles vers la bulle, ses fins de tour en dépendent. Un worker n'est pas ralenti : setTimeout et setInterval de la
   page passent par lui (minuteries-worker.js), pareils à ceux du navigateur. Chargé avant tout le reste. Sans worker : rien ne change. */
(function (w) {
  'use strict';
  if (!w || typeof w.Worker !== 'function' || w.__minuteriesFiables) return;
  let worker;
  try { worker = new w.Worker('/minuteries-worker.js'); } catch (_) { return; }
  const natif = { st: w.setTimeout, si: w.setInterval, ct: w.clearTimeout, ci: w.clearInterval };
  const rappels = new Map();
  let suivant = 1e6;
  worker.onmessage = (e) => {
    const r = rappels.get(e.data);
    if (!r) return;
    if (!r.repete) rappels.delete(e.data);
    try { r.fn(...r.args); } catch (err) { natif.st.call(w, () => { throw err; }, 0); }   // l'erreur se voit, les autres continuent
  };
  const poser = (repete) => function (fn, ms, ...args) {
    if (typeof fn !== 'function') return (repete ? natif.si : natif.st).call(w, fn, ms, ...args);   // jamais de texte évalué ici
    const id = suivant++;
    rappels.set(id, { fn, args, repete });
    worker.postMessage({ c: 'pose', id, ms: Number(ms) || 0, r: repete });
    return id;
  };
  const effacer = (repete) => function (id) {
    if (rappels.has(id)) { rappels.delete(id); worker.postMessage({ c: 'efface', id }); return; }
    (repete ? natif.ci : natif.ct).call(w, id);                     // une minuterie native d'avant
  };
  w.setTimeout = poser(false); w.setInterval = poser(true);
  w.clearTimeout = effacer(false); w.clearInterval = effacer(true);
  w.__minuteriesFiables = true;
})(typeof window !== 'undefined' ? window : undefined);

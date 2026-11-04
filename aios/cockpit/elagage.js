/* (04/11, Ahmed : « évalue le flux de chaque réponse et son parcours préférentiel ; comme le système nerveux humain, qui mûrit en
   consolidant les bonnes synapses et en éliminant, de façon autonome, celles qui sont inutiles ou parasites : un élagage, qui amoindrit
   les poids des synapses élaguées ») ses SYNAPSES : par famille (déclencheur, meuble, voie, piste), un chemin et son poids.
   - chaque mesure (de 0, nuisible, à 1, utile) rapproche son poids de son score : w ← w + PAS × (score − w), au plancher de 0,05 ;
   - sans mesure, il revient lentement vers le neutre (0,5) : 2 % par jour (oublier) ;
   - sous le SEUIL, et après MIN_MESURES, elle est élaguée : elle ne sert plus, sauf 5 fois sur 100 (l'exploration), assez pour
     qu'elle repousse si elle redevient utile ; épinglée par Ahmed, ou la meilleure de sa famille, jamais ;
   - chaque élagage, repousse, épinglage ou rétablissement est noté (historique), et tout se rétablit d'un geste.
   Lu une fois du disque ; ensuite tout est en mémoire ; sauvé d'un coup (fichier temporaire puis renommage), au plus toutes les 10 s. */
'use strict';
const fs = require('node:fs');

const SEUIL = 0.2, MIN_MESURES = 20, EXPLORATION = 0.05, PAS = 0.1, OUBLI_JOUR = 0.02, TEMOIN = 0.1;
const PLANCHER = 0.05, NEUTRE = 0.5, SAUVER_MS = 10000, HISTORIQUE_MAX = 500, JOUR = 86400000;

function creer({ fichier, maintenant = Date.now, hasard = Math.random, fsx = fs } = {}) {
  let etat = { familles: {}, historique: [] };
  try {
    const d = JSON.parse(fsx.readFileSync(fichier, 'utf8'));
    if (d && typeof d.familles === 'object' && d.familles) etat = { familles: d.familles, historique: Array.isArray(d.historique) ? d.historique : [], consolidee: Number(d.consolidee) || 0 };
  } catch (_) {}
  // (relecture) une entrée abîmée (poids absent ou hors bornes) est remise d'aplomb : jamais de NaN qui se propage
  for (const fam of Object.values(etat.familles)) for (const s of Object.values(fam || {})) {
    if (!s || typeof s !== 'object') continue;
    s.poids = Number.isFinite(Number(s.poids)) ? Math.max(PLANCHER, Math.min(1, Number(s.poids))) : 1;
    s.n = Math.max(0, Math.floor(Number(s.n)) || 0);
  }
  let sale = false, derniereSauvegarde = -Infinity;
  const synapse = (f, id) => (etat.familles[f] || {})[id];
  const elaguee = (s) => !s.epingle && s.n >= MIN_MESURES && s.poids < SEUIL;
  // (relecture) la meilleure de sa famille, ou de son groupe (les voies « |suite » entre elles)
  const meilleure = (f, groupe) => {
    let m = null;
    for (const [id, s] of Object.entries(etat.familles[f] || {})) if ((!groupe || groupe(id)) && (!m || s.poids > m.poids)) m = { id, poids: s.poids };
    return m && m.id;
  };
  const noter = (famille, id, evenement, poids) => {
    etat.historique.push({ t: maintenant(), famille, id, evenement, poids: Math.round(poids * 1000) / 1000 });
    if (etat.historique.length > HISTORIQUE_MAX) etat.historique.splice(0, etat.historique.length - HISTORIQUE_MAX);
    sale = true;
  };
  const obtenir = (f, id) => {
    const fam = etat.familles[f] || (etat.familles[f] = {});
    return fam[id] || (fam[id] = { poids: 1, n: 0, vu: maintenant(), oubli: maintenant(), epingle: false, elaguee: false });
  };
  // l'élagage ou la repousse, quand son état change
  const suivre = (f, id, s) => {
    const maintenantElaguee = elaguee(s);
    if (maintenantElaguee !== !!s.elaguee) { s.elaguee = maintenantElaguee; noter(f, id, maintenantElaguee ? 'elaguee' : 'repousse', s.poids); }
  };
  const oublier = () => {
    const t = maintenant();
    for (const [f, fam] of Object.entries(etat.familles)) for (const [id, s] of Object.entries(fam)) {
      const jours = (t - Math.max(Number(s.vu) || 0, Number(s.oubli) || 0)) / JOUR;
      if (jours <= 0) continue;
      s.poids = s.poids + (NEUTRE - s.poids) * (1 - Math.pow(1 - OUBLI_JOUR, jours));
      s.oubli = t; sale = true;
      suivre(f, id, s);
    }
  };
  return {
    poids(f, id) { const s = synapse(f, id); return s ? s.poids : 1; },
    // (relecture) un essai témoin, 1 fois sur 10 : un chemin qui agit (un déclencheur qui prévient) n'agit pas, pour être mesuré sans biais
    temoin() { return hasard() < TEMOIN; },
    vivante(f, id, groupe = null) {
      const s = synapse(f, id);
      if (!s || !elaguee(s) || meilleure(f, groupe) === id) return true;
      return hasard() < EXPLORATION;
    },
    mesurer(f, id, score) {
      const x = Number(score);
      if (score == null || !Number.isFinite(x)) return;
      const s = obtenir(f, id);
      s.poids = Math.max(PLANCHER, Math.min(1, s.poids + PAS * (Math.max(0, Math.min(1, x)) - s.poids)));
      s.n += 1; s.vu = maintenant(); s.oubli = s.vu;
      sale = true;
      suivre(f, id, s);
    },
    oublier,
    // (04/11, Ahmed : « l'élagage doit être un process continu, qui se fait à chaque sommeil, veille ou sieste ») sa consolidation, à chaque
    // passage de son état : l'oubli lent, puis le bilan depuis la précédente (ce qui a été élagué, ce qui a repoussé), noté
    consolider(raison = '') {
      oublier();
      const depuis = Number(etat.consolidee) || 0, ev = etat.historique.filter(h => h.t > depuis);
      const ids = (e) => ev.filter(h => h.evenement === e).map(h => `${h.famille}|${h.id}`);
      const toutes = Object.values(etat.familles).flatMap(fam => Object.values(fam));
      const bilan = { elaguees: ids('elaguee'), repoussees: ids('repousse'), vivantes: toutes.filter(x => !x.elaguee).length, endormies: toutes.filter(x => x.elaguee).length };
      etat.consolidee = maintenant();
      noter('sommeil', String(raison).slice(0, 40), 'consolidation', 0);
      return bilan;
    },
    epingler(f, id, oui) { const s = obtenir(f, id); s.epingle = !!oui; noter(f, id, oui ? 'epinglee' : 'desepinglee', s.poids); suivre(f, id, s); },
    retablir(f, id) { const s = obtenir(f, id); Object.assign(s, { poids: NEUTRE, n: 0, elaguee: false, vu: maintenant(), oubli: maintenant() }); noter(f, id, 'retablie', s.poids); },
    historique() { return etat.historique.map(h => ({ ...h })); },
    tout() { return JSON.parse(JSON.stringify(etat.familles)); },
    sauver(force = false) {
      if (!sale || (!force && maintenant() - derniereSauvegarde < SAUVER_MS)) return false;
      const tmp = `${fichier}.${process.pid}.tmp`;
      fsx.writeFileSync(tmp, JSON.stringify(etat), { mode: 0o600 });
      fsx.renameSync(tmp, fichier);
      sale = false; derniereSauvegarde = maintenant();
      return true;
    },
  };
}

module.exports = { creer, SEUIL, MIN_MESURES, EXPLORATION, PAS, OUBLI_JOUR, PLANCHER, NEUTRE, TEMOIN };

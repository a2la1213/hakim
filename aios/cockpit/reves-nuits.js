/* (13/11, Ahmed : « des rêves simples de consolidation, et des rêves créatifs et incongrus ; lucides ou non ; idem pour cauchemar ; selon
   ce qu'il a dans sa tête, son cœur et tout le reste ») ses rêves de la nuit, lus dans ~/AIOS/jarvis/reves-nuits.jsonl (écrit par
   anamnese/reves.py) et rangés par nuit pour la page de ses rêves : chaque rêve avec son type, s'il était lucide, ce qui l'a déclenché,
   son récit (l'action qu'il a choisie et la réponse du rêve), et, au réveil, s'il s'en est souvenu (net, flou) ou l'a oublié.
   Lecture seule. Papa voit tout, même ce que Hakim a oublié. node --test test-reves-nuits.js */
'use strict';
const fs = require('fs');

const LIBELLES = { consolidation: 'consolidation', creatif: 'rêve créatif', cauchemar: 'cauchemar' };

// la fin du journal seulement (les nuits récentes) ; une ligne coupée ou fausse est sautée
function lire(fichier, octets = 2_000_000) {
  let texte = '';
  try {
    const fd = fs.openSync(fichier, 'r');
    try {
      const taille = fs.fstatSync(fd).size, debut = Math.max(0, taille - octets), buf = Buffer.alloc(taille - debut);
      fs.readSync(fd, buf, 0, buf.length, debut);
      texte = buf.toString('utf8');
      if (debut > 0) texte = texte.slice(texte.indexOf('\n') + 1);
    } finally { fs.closeSync(fd); }
  } catch (_) { return []; }
  const out = [];
  for (const l of texte.split('\n')) { if (!l.trim()) continue; try { const o = JSON.parse(l); if (o && typeof o === 'object') out.push(o); } catch (_) {} }
  return out;
}

function jour(ts) {
  const d = new Date(Number(ts) * 1000);
  if (!Number.isFinite(d.getTime())) return '?';
  const z = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

function libelle(o) {
  const t = LIBELLES[o.type] || o.type || 'rêve';
  if (o.type === 'consolidation' || !o.type) return t;
  return t + (o.lucide && o.suite ? ' lucide' : o.lucide ? ' lucide (perdue)' : ' non lucide');
}

function resume(o) {
  return {
    quoi: o.quoi, ts: Number(o.ts) || null, cycle: o.cycle ?? null, type: o.type || 'consolidation', lucide: !!o.lucide,
    lucide_perdu: !!o.lucide_perdu, libelle: o.quoi === 'tri' ? 'consolidation (le tri de la nuit)' : libelle(o),
    titre: String(o.titre || ''), recit: String(o.recit || ''), choix: Array.isArray(o.choix) ? o.choix.map(String) : [],
    action: o.action ? String(o.action) : '', suite: o.suite ? String(o.suite) : '',
    declencheurs: Array.isArray(o.declencheurs) ? o.declencheurs.map(String) : [],
    probas: o.probas && typeof o.probas === 'object' ? o.probas : null, nombres: o.nombres && typeof o.nombres === 'object' ? o.nombres : null,
    graine: o.graine ?? null, intensite: Number.isFinite(Number(o.intensite)) ? Number(o.intensite) : null,
    affect: o.affect && typeof o.affect === 'object' ? o.affect : null, erreur: o.erreur ? String(o.erreur) : '',
    idees: Array.isArray(o.idees) ? o.idees.map(String) : [], graines: o.graines ?? null,
    souvenir: null,
  };
}

// [{ nuit, date, debut, reves: [...], reveil }] : les nuits les plus récentes d'abord, leurs rêves dans l'ordre
function parNuit(lignes, max = 14) {
  const nuits = new Map();
  for (const o of lignes || []) {
    if (!o || !['cycle', 'tri', 'reveil'].includes(o.quoi)) continue;
    const cle = o.nuit != null ? `n${o.nuit}` : `j${jour(o.ts)}`;
    if (!nuits.has(cle)) nuits.set(cle, { nuit: o.nuit ?? null, date: jour(o.nuit ?? o.ts), debut: Number(o.nuit ?? o.ts) || 0, reves: [], reveil: null });
    const n = nuits.get(cle);
    if (o.quoi === 'reveil') {
      n.reveil = { ts: Number(o.ts) || null, par: o.par || '', reves: o.reves ?? null, gardes: o.gardes ?? null,
        souvenirs: Array.isArray(o.souvenirs) ? o.souvenirs : [] };
    } else n.reves.push(resume(o));
  }
  for (const n of nuits.values()) {
    n.reves.sort((a, b) => (a.ts || 0) - (b.ts || 0));
    for (const s of (n.reveil && n.reveil.souvenirs) || []) {
      // par l'heure du rêve (sûre) ; par son numéro de cycle pour une ligne qui n'a pas l'heure
      const r = n.reves.find(x => x.quoi === 'cycle' && (s.ts != null ? x.ts === Number(s.ts) : x.cycle === s.cycle));
      if (r) r.souvenir = { garde: !!s.garde, nettete: s.nettete || '', p: s.p ?? null };
    }
  }
  return [...nuits.values()].sort((a, b) => b.debut - a.debut).slice(0, max);
}

module.exports = { lire, parNuit, jour, libelle };

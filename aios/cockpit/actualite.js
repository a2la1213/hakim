/* (10/11, lettre de Hakim de 18:14 écrite à la demande d'Ahmed : « que toi aussi tu puisses m'envoyer directement dans mes documents et
   dans le fil de l'actualité » ; accord d'Ahmed : « ouii ») LE FIL D'ACTUALITÉ de papa : ce que Hakim y publie (son outil
   actualite_publier : anamnese/actualite.py écrit jarvis/actualite.jsonl ; un fichier y est une pièce, copiée par pieces.py), montré
   par la page /actualite (le menu ☰ et son point rouge, le bandeau des nouveautés) ; Parler en fait une notification de l'appli quand
   elle est cachée (l'événement « actualite » du flux).
   - Rien n'est cru du fichier : l'identifiant, la date, le texte (2 000 caractères), la pièce (relue dans l'index des pièces par
     pieceDe, jamais un lien) sont vérifiés ;
   - ce qu'il publie passe par les mêmes filtres que sa parole : filtrer est donné par server.js (sa balise d'affect et son refrain
     retirés ; ses résidus marqués une fois, à l'arrivée) ; une publication qui n'était que ça, sans fichier, ne s'affiche pas ;
   - pur, sans dépendance : node --test test-actualite.js */
'use strict';
const fs = require('fs');

const ID = /^\d{8}-\d{6}-[0-9a-f]{6}$/;
const TEXTE_MAX = 2000;

// une ligne du fil → { id, ts (ms), texte, titre, piece } ou null
function valide(o, { pieceDe = () => null, filtrer = (t) => t } = {}) {
  if (!o || typeof o !== 'object' || !ID.test(String(o.id))) return null;
  const s = Number(o.ts);
  if (!Number.isFinite(s) || s <= 0) return null;
  const texte = String(filtrer(typeof o.texte === 'string' ? o.texte.slice(0, TEXTE_MAX) : '') || '').trim();
  const titre = typeof o.titre === 'string' ? o.titre.replace(/\s+/g, ' ').trim().slice(0, 160) : '';
  let piece = null;
  if (o.piece && typeof o.piece === 'object' && ID.test(String(o.piece.id))) {
    const p = pieceDe(String(o.piece.id));
    if (p) { const { fichier, ...sans } = p; piece = sans; }          // le chemin sur le Mac ne sort jamais
  }
  if (!texte && !piece) return null;
  return { id: String(o.id), ts: Math.round(s * 1000), texte, titre, piece };
}

// le fil, le plus récent d'abord
function lire(fichier, options = {}) {
  const n = Math.max(1, Math.min(500, Number(options.limite) || 200));
  let lignes = [];
  try { lignes = fs.readFileSync(fichier, 'utf8').split('\n').filter(Boolean).slice(-n); } catch (_) { return []; }
  const out = [];
  for (const l of lignes) {
    let o = null; try { o = JSON.parse(l); } catch (_) {}
    const p = valide(o, options);
    if (p) out.push(p);
  }
  return out.reverse();
}

// ce qui est arrivé depuis le dernier regard (etat : { taille }) ; le premier regard ne fait que se souvenir (rien d'ancien ne s'annonce)
function nouvelles(fichier, etat) {
  let st = null; try { st = fs.statSync(fichier); } catch (_) {}
  const taille = st && st.isFile() ? st.size : 0;
  if (etat.taille == null) { etat.taille = taille; return []; }
  if (taille < etat.taille) etat.taille = 0;                        // le fil a été remplacé : on repart de son début
  if (taille === etat.taille) return [];
  let morceau = Buffer.alloc(0);
  try {
    const fd = fs.openSync(fichier, 'r');
    try { morceau = Buffer.alloc(Math.min(taille - etat.taille, 4 << 20)); fs.readSync(fd, morceau, 0, morceau.length, etat.taille); }
    finally { fs.closeSync(fd); }
  } catch (_) { return []; }
  const fin = morceau.lastIndexOf(0x0a);
  if (fin < 0) return [];                                           // une ligne en cours d'écriture : au prochain regard
  etat.taille += fin + 1;
  const out = [];
  for (const l of morceau.subarray(0, fin).toString('utf8').split('\n')) {
    if (!l.trim()) continue;
    try { out.push(JSON.parse(l)); } catch (_) {}
  }
  return out;
}

module.exports = { ID, TEXTE_MAX, valide, lire, nouvelles };

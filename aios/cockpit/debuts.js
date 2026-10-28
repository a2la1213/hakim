/* Ses débuts de réponse, prêts d'avance (28/10, Ahmed : « tout en même temps » ; anamnese/eval/latence). La voix d'un début
   connu (Voix.DEBUTS, public/voix.js), une fois fabriquée et plausible, est gardée par réglage de voix dans
   ~/AIOS/jarvis/voix-debuts/ (jamais publié) et resservie sans passer par la synthèse (~1,5 s fixes par morceau). */
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const DOSSIER = path.join(process.env.JARVIS_DIR || path.join(require('os').homedir(), 'AIOS', 'jarvis'), 'voix-debuts');
const norme = (t) => String(t || '').toLowerCase().replace(/\s+/g, ' ').trim();
const palier = (x, pas) => (Number.isFinite(Number(x)) && x !== null ? (Math.round(Number(x) / pas) * pas).toFixed(2) : '-');

function cle(texte, langue, emotion, tempo) {
  return crypto.createHash('sha256').update([norme(texte), langue || 'fr', palier(emotion, 0.1), palier(tempo, 0.05)].join('|'))
    .digest('hex').slice(0, 32);
}
// la durée qu'on attend pour ce texte (comme /api/voix/reecouter) : au-delà de 1,6 fois, la voix a divagué
function plausible(texte, duree) {
  const d = Number(duree);
  return Number.isFinite(d) && d > 0.2 && d <= 1.6 * (String(texte).length / 14 + 0.6);
}
function lire(c) {
  if (!/^[0-9a-f]{32}$/.test(String(c))) return null;
  try { return { data: fs.readFileSync(path.join(DOSSIER, `${c}.wav`)), duree: Number(fs.readFileSync(path.join(DOSSIER, `${c}.duree`), 'utf8')) }; }
  catch (_) { return null; }
}
function garder(c, data, duree) {
  if (!/^[0-9a-f]{32}$/.test(String(c))) return;
  try {
    fs.mkdirSync(DOSSIER, { recursive: true, mode: 0o700 });
    fs.writeFileSync(path.join(DOSSIER, `${c}.wav`), data, { mode: 0o600 });
    fs.writeFileSync(path.join(DOSSIER, `${c}.duree`), String(duree), { mode: 0o600 });
  } catch (_) {}
}
module.exports = { cle, plausible, lire, garder, palier, norme, DOSSIER };

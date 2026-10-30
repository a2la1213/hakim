/* (30/10, Hakim, accord d'Ahmed) les verdicts des juges de Hakim, gardés par le cockpit dans son atelier :
   atelier/verdicts/AAAAMMJJ-HHMM-<prénom>.md, un fichier par verdict, jamais écrasé. Le juge Octave a vu ce matin que les
   verdicts de Lucien et de Bastien du 29/10 n'existaient qu'à l'oral. L'atelier est à Hakim (son terminal y pose ce qu'il
   veut) : rien n'est écrit à travers un lien. */
const fs = require('node:fs');
const path = require('node:path');

const VERDICT_MAX = 200000;

const estJuge = (a) => !!a && /juge/i.test(String(a.type || ''));
const slug = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 30);
const deux = (n) => String(n).padStart(2, '0');

function dossierReel(d) {
  try { return fs.lstatSync(d).isDirectory(); } catch (e) { return e.code === 'ENOENT' ? null : false; }
}

// le chemin du fichier écrit, ou null (pas un juge, rien à garder, un lien dans le chemin)
function garder({ atelier, agent, prenom, texte, quand = Date.now() }) {
  const corps = String(texte || '').trim().slice(0, VERDICT_MAX);
  if (!estJuge(agent) || !corps) return null;
  if (dossierReel(atelier) !== true) return null;
  const dossier = path.join(atelier, 'verdicts');
  const etat = dossierReel(dossier);
  if (etat === false) return null;
  if (etat === null) { try { fs.mkdirSync(dossier); } catch (_) { return null; } if (dossierReel(dossier) !== true) return null; }
  const d = new Date(quand);
  const base = `${d.getFullYear()}${deux(d.getMonth() + 1)}${deux(d.getDate())}-${deux(d.getHours())}${deux(d.getMinutes())}-`
    + (slug(prenom) || `juge-${slug(agent.id)}`);
  const qui = String(prenom || '').trim() || 'son juge';
  const de = /^[aeiouyhàâéèêîôû]/i.test(qui) ? `d’${qui}` : `de ${qui}`;
  const tete = `# Verdict ${de} — ${String(agent.description || '').replace(/\s+/g, ' ').slice(0, 200)}\n\n`
    + `Juge (agent ${String(agent.id || '?').slice(0, 20)}), le ${deux(d.getDate())}/${deux(d.getMonth() + 1)}/${d.getFullYear()} à `
    + `${deux(d.getHours())}:${deux(d.getMinutes())}. Gardé par le cockpit, tel qu'il l'a rendu à Hakim.\n\n`;
  for (let k = 1; k <= 50; k++) {
    const f = path.join(dossier, `${base}${k > 1 ? `-${k}` : ''}.md`);
    let fd;
    try { fd = fs.openSync(f, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_NOFOLLOW, 0o644); }
    catch (e) { if (e.code === 'EEXIST') continue; return null; }
    try { fs.writeSync(fd, tete + corps + '\n'); } finally { fs.closeSync(fd); }
    return f;
  }
  return null;
}

// (30/10) un réveil pour le café n'est pas un travail : vrai si le dernier message reçu par l'agent (sa consigne, ou ce que
// Hakim lui a envoyé) commence par « ☕ Café : » (le signe que le cockpit demande à Hakim pour ces réveils)
function tourCafe(fil) {
  let lignes = [];
  try { lignes = fs.readFileSync(fil, 'utf8').slice(-4 * 1024 * 1024).split('\n'); } catch (_) { return false; }
  for (let i = lignes.length - 1; i >= 0; i--) {
    let o; try { o = JSON.parse(lignes[i]); } catch (_) { continue; }
    if (!o || o.type !== 'user' || !o.message) continue;
    const c = o.message.content;
    const texte = typeof c === 'string' ? c
      : Array.isArray(c) && !c.some(b => b && b.type === 'tool_result') ? c.filter(b => b && b.type === 'text').map(b => b.text).join('\n') : null;
    if (texte !== null) return /☕ Café :/.test(texte);
  }
  return false;
}

module.exports = { garder, estJuge, tourCafe, VERDICT_MAX };

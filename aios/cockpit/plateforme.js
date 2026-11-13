/* La couche de plateforme du cockpit (13/11, Ahmed : « que tout le code tourne aussi sur le PC de son ami, par WSL2 ; le Mac doit
   rester EXACTEMENT comme aujourd'hui »).

   Chaque endroit du cockpit qui fait une chose propre au Mac garde son code tel quel ; une ligne demande d'abord « suis-je sur le
   Mac ? » et, sinon, passe ici :
   - les clés : le trousseau (security) → un fichier 600 par clé dans ~/.config/naissance/cles (plateforme/cles.py d'Anamnèse) ;
   - les services : launchctl → systemd utilisateur (les unités écrites par naissance/installer.sh) ;
   - le son : afconvert → ffmpeg ; la mémoire : sysctl → /proc/meminfo ; le GPU : ioreg → rien (pas de GPU lisible) ;
   - Tailscale : l'appli du Mac → le tailscale de Windows (tailscale.exe, par l'interopérabilité de WSL) ou celui de Linux ;
   - les profils de modules (anamnese/plateforme/profils.json) : « complet » pour Hakim, rien ne change ; un PC sans GPU éteint le
     studio, le chant, les oreilles MLX et le cerveau local, et règle sa voix et son écoute sur Azure. */
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFile, execFileSync } = require('child_process');

const SYSTEME = process.env.ANAMNESE_SYSTEME || (process.platform === 'darwin' ? 'mac' : process.platform === 'linux' ? 'linux' : process.platform);
const MAC = SYSTEME === 'mac';
const LINUX = SYSTEME === 'linux';
const HOME = os.homedir();
const ANAMNESE = process.env.ANAMNESE_DIR || path.join(HOME, 'Desktop', 'anamnese');
const JARVIS = process.env.JARVIS_DIR || path.join(HOME, 'AIOS', 'jarvis');

let wsl = null;
function estWsl() {
  if (wsl === null) {
    try { wsl = fs.existsSync('/proc/sys/fs/binfmt_misc/WSLInterop') || /microsoft/i.test(fs.readFileSync('/proc/version', 'utf8')); }
    catch (_) { wsl = false; }
  }
  return wsl;
}

/* ---- les profils de modules (relus toutes les 5 s au plus) ---- */
const lireJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } };
let profilLu = { t: 0, v: null };
function profil(o = {}) {
  if (!o.fichier && profilLu.v && Date.now() - profilLu.t < 5000) return profilLu.v;
  const tous = (lireJson(o.profils || path.join(ANAMNESE, 'plateforme', 'profils.json'), {}) || {}).profils || {};
  const choix = lireJson(o.fichier || path.join(JARVIS, 'profil-modules.json'), {}) || {};
  let nom = process.env.JARVIS_PROFIL || choix.profil || 'complet';
  if (!tous[nom]) nom = 'complet';
  const base = (tous.complet && tous.complet.modules) || {};
  const p = tous[nom] || {};
  const modules = { ...base, ...(p.modules || {}) };
  if (choix.modules && typeof choix.modules === 'object') for (const [k, v] of Object.entries(choix.modules)) if (k in base) modules[k] = v;
  const v = { ...p, nom, modules, reglages: { ...(p.reglages || {}) } };
  if (!o.fichier) profilLu = { t: Date.now(), v };
  return v;
}
function moduleActif(nom, o) {
  const v = profil(o).modules[nom];
  return !!v && !['eteint', 'non', 'off'].includes(v);
}
// les réglages par défaut du profil (le fichier de réglages, s'il dit autre chose, l'emporte) ; « complet » : {}
function reglagesDuProfil(o) {
  const p = profil(o);
  // Gemma éteinte : ses mots à risque ne passent plus par elle (sinon chaque mot attendrait un Ollama absent)
  return { ...(p.reglages || {}), ...(['eteint', 'non', 'off'].includes(p.modules.gemma) ? { filtre_gemma: false } : {}) };
}
function phraseEteint(nom) {
  return `Ce module (${nom}) est éteint sur cette machine (profil « ${profil().nom} ») : il demande un vrai GPU ou n'a pas été choisi à l'installation.`;
}

/* ---- les clés ---- */
const CLES_DIR = process.env.NAISSANCE_CLES_DIR || path.join(HOME, '.config', 'naissance', 'cles');
const nomCle = (s) => String(s).replace(/[^A-Za-z0-9._-]+/g, '_');
function cheminCle(service, compte) { return path.join(CLES_DIR, nomCle(service) + (compte ? `@${nomCle(compte)}` : '')); }
function lireSecret(service, compte) {
  if (MAC) {
    try { return execFileSync('/usr/bin/security', ['find-generic-password', '-s', service, ...(compte ? ['-a', compte] : []), '-w'], { encoding: 'utf8', timeout: 3000 }).trim() || null; }
    catch (_) { return null; }
  }
  const essais = [cheminCle(service, compte)];
  if (!compte) { try { for (const n of fs.readdirSync(CLES_DIR).sort()) if (n.startsWith(nomCle(service) + '@')) essais.push(path.join(CLES_DIR, n)); } catch (_) {} }
  for (const f of essais) { try { const v = fs.readFileSync(f, 'utf8').trim(); if (v) return v; } catch (_) {} }
  return null;
}
function ecrireSecret(service, valeur, compte) {
  valeur = String(valeur || '').trim();
  if (!valeur) return false;
  if (MAC) {
    try { execFileSync('/usr/bin/security', ['add-generic-password', '-U', '-s', service, '-a', compte || 'cle', '-w', valeur], { timeout: 5000 }); return true; }
    catch (_) { return false; }
  }
  try {
    fs.mkdirSync(CLES_DIR, { recursive: true, mode: 0o700 }); fs.chmodSync(CLES_DIR, 0o700);
    const f = cheminCle(service, compte), tmp = `${path.dirname(f)}/.${path.basename(f)}.${process.pid}`;
    fs.writeFileSync(tmp, valeur + '\n', { mode: 0o600 }); fs.renameSync(tmp, f);
    return true;
  } catch (_) { return false; }
}
// une commande shell qui écrit la clé (apiKeyHelper de claude) ; la clé n'y figure pas
function commandeSecret(service, compte) {
  if (MAC) return `/usr/bin/security find-generic-password -s ${service} -w`;
  return `/bin/cat '${cheminCle(service, compte).replace(/'/g, "'\\''")}'`;
}

/* ---- le son ---- */
const FFMPEG = ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg'].find(f => fs.existsSync(f)) || 'ffmpeg';
// un fichier (m4a, webm…) en WAV PCM 16 kHz mono (afconvert sur le Mac, ffmpeg ailleurs)
function versWav16k(fichier, sortie, fini) {
  execFile(FFMPEG, ['-loglevel', 'error', '-y', '-i', fichier, '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', sortie], { timeout: 15000 }, fini);
}

/* ---- la mémoire du système (orchestrateur.js : la pression mémoire) ---- */
function pressionMemoire(cb) {
  fs.readFile('/proc/meminfo', 'utf8', (e, t) => {
    if (e) return cb(null);
    const v = (k) => { const m = new RegExp(`^${k}:\\s+(\\d+)`, 'm').exec(t); return m ? Number(m[1]) : null; };
    const total = v('MemTotal'), dispo = v('MemAvailable'), st = v('SwapTotal'), sf = v('SwapFree');
    cb({ libre_pct: total && dispo != null ? Math.round(100 * dispo / total) : NaN, swap_total_mo: st != null ? st / 1024 : null,
      swap_utilise_mo: st != null && sf != null ? (st - sf) / 1024 : null });
  });
}

/* ---- les services (systemd utilisateur ; noms des unités : naissance/installer.sh) ---- */
const UNITES = { 'com.aios.cockpit': 'naissance-cockpit.service', 'com.anamnese.daemon': 'naissance-demon.service' };
function pidService(label) {
  try {
    const so = execFileSync('systemctl', ['--user', 'show', '-p', 'MainPID', '--value', UNITES[label] || label], { encoding: 'utf8', timeout: 5000 }).trim();
    return Number(so) > 0 ? Number(so) : null;
  } catch (_) { return null; }
}
// la commande qui relance un service : [programme, arguments]
function relanceService(label) { return ['systemctl', ['--user', 'restart', UNITES[label] || label]]; }

/* ---- Tailscale (le téléphone joint le cockpit par « tailscale serve ») ---- */
function clisTailscale() {
  return [process.env.TAILSCALE_CLI, '/usr/bin/tailscale', '/usr/local/bin/tailscale',
    ...(estWsl() ? ['/mnt/c/Program Files/Tailscale/tailscale.exe'] : [])];
}

module.exports = { SYSTEME, MAC, LINUX, estWsl, profil, moduleActif, reglagesDuProfil, phraseEteint, lireSecret, ecrireSecret, commandeSecret,
  cheminCle, versWav16k, pressionMemoire, pidService, relanceService, clisTailscale, UNITES };

/* (06/11, Ahmed : « qu'il parle avec sa voix de rap, sur le Mac, le téléphone et la montre, en darija, français et anglais mélangés »)
   Sa voix, au choix dans Réglages (voix_hakim) : « azure » (rapide, en ligne) ou « rap » (le timbre de ses chansons faites avec
   ACE-Step, ~/AIOS/jarvis/voix-hakim-rap.wav, cloné par Chatterbox au Mac). En rap :
   - le texte est découpé en morceaux arabe / français / anglais, un lang_code chacun, recollés par le processus voix ;
   - Azure prend le relais seul quand Chatterbox ne peut pas suivre : pas encore chargé, une chanson ou un travail du Studio en
     calcul, une file trop longue, une erreur, ou une synthèse plus lente que son budget. Chaque relais est noté (voix-diagnostic.jsonl). */
const fs = require('fs');
const path = require('path');
const Voix = require('./public/voix.js');

// (08/11, Ahmed : « prendre sa voix rap et la rattacher à Azure ») « azure_rap » : Azure dit, sa voix est refaite au timbre de rap, au Mac
const VOIX = ['azure', 'rap', 'azure_rap'];
const choixVoix = (r) => (r && (r.voix_hakim === 'rap' || r.voix_hakim === 'azure_rap') ? r.voix_hakim : 'azure');

// les mots qui disent l'anglais ou le français (les mêmes que langueDePensee, parler.js)
const MOTS_ANGLAIS = new Set(['the', 'and', 'you', 'your', 'is', 'are', 'am', 'i', "i'm", 'to', 'of', 'what', 'how', 'my', 'it', "it's", 'this', 'that',
  'with', 'for', 'be', 'do', "don't", 'have', 'we', 'they', 'he', 'she', 'was', 'were', 'will', 'can', 'not', 'so', 'just', 'love', 'thank', 'thanks',
  'please', 'hello', 'yes', 'good', 'morning', 'night', 'know', 'want', "let's", 'well', 'see', 'bro', 'man', 'yeah', 'go', 'get', 'got', 'all', 'right',
  'no', 'one', 'come', 'on', 'like', 'never', 'stop', 'baby', 'life', 'money', 'real', 'keep', 'feel', 'make', 'way', 'time', 'up', 'down', 'now']);
const MOTS_FRANCAIS = new Set(['le', 'la', 'les', 'et', 'je', 'tu', 'de', 'des', 'du', 'un', 'une', 'est', 'que', 'qui', 'pas', 'mon', 'ma', 'mes', 'ton',
  'ta', 'il', 'elle', 'nous', 'vous', 'ce', 'ça', 'à', 'en', 'pour', 'dans', 'avec', 'sur', 'mais', 'oui', 'non', 'bien', 'suis', 'es', "c'est", "j'ai", 'moi',
  'toi', 'frérot', 'tonton', 'papa', 'on', 'au', 'aux', 'se', 'sa', 'son', 'ses', 'y', 'vais', 'fait', 'faire', 'tout', 'très', 'merci', 'aussi']);
/* une proposition en lettres latines : 'en', 'fr', ou null (rien ne le dit : elle suit sa voisine). « on », « no » : dans les deux. */
function langueLatine(texte) {
  const mots = String(texte || '').toLowerCase().replace(/[’`]/g, "'").split(/[^\p{L}']+/u).filter(Boolean);
  const en = mots.filter(m => MOTS_ANGLAIS.has(m) && !MOTS_FRANCAIS.has(m)).length, fr = mots.filter(m => MOTS_FRANCAIS.has(m) && !MOTS_ANGLAIS.has(m)).length;
  if (!en && !fr) return null;
  return en > fr ? 'en' : fr > en ? 'fr' : null;
}
/* [{langue: 'ar' | 'fr' | 'en', texte}] : l'écriture d'abord (Voix.segmenter : arabe / latin), puis chaque passage latin coupé à sa
   ponctuation, chaque proposition reconnue (anglais ou français ; la darija en lettres latines reste au français, en lettres arabes à
   l'arabe), les voisines de même langue recollées. */
function segmenterLangues(texte) {
  const out = [];
  const pousser = (langue, t) => {
    t = t.trim();
    if (!t) return;
    const der = out[out.length - 1];
    if (der && (der.langue === langue || !/\p{L}/u.test(t))) der.texte += ` ${t}`;
    else out.push({ langue, texte: t });
  };
  for (const s of Voix.segmenter(texte)) {
    if (s.langue === 'ar') { pousser('ar', s.texte); continue; }
    const props = s.texte.split(/(?<=[.!?;:,…—])\s+/).filter(x => x.trim());
    const langues = props.map(langueLatine);
    // une proposition muette prend la langue de sa voisine (d'abord celle d'avant), sinon le français
    for (let i = 0; i < props.length; i++) {
      const l = langues[i] || langues.slice(0, i).reverse().find(Boolean) || langues.slice(i + 1).find(Boolean) || 'fr';
      pousser(l, props[i]);
    }
  }
  return out;
}

/* ---- le relais d'Azure ---- */
// (07/11, Ahmed : « pour sa voix, le secours Azure doit partir seulement à 60 s ») sa voix de rap attend jusqu'à 60 s avant de laisser la place à Azure
const SECOURS_S = 60;
const SEUIL_FILE_S = SECOURS_S;    // ce qui attend avant lui, en secondes de parole : au-delà, Azure
const CARACTERES_PAR_S = 14;        // son débit (comme debuts.plausible) ; Chatterbox calcule à peu près au temps réel (mesuré le 06/11 : 2,3 s pour 2,1 s)
const dureeParlee = (t) => String(t || '').length / CARACTERES_PAR_S + 0.6;
// le temps qu'on lui laisse pour une phrase : 4 s, plus 1,5 fois sa durée parlée ; au-delà, Azure
const budgetMs = (texte) => Math.max(SECOURS_S * 1000, Math.round(1000 * (4 + 1.5 * dureeParlee(texte))));   // (07/11) 60 s au moins
// ce qui attend devant elle, en secondes de parole, et la moitié de la phrase en cours ; sans `tout`, le fond (fabriqué d'avance,
// il passe après sa parole) ne compte pas
function attenteFile(file, enCours, tout = false) {
  return (enCours ? dureeParlee(enCours.texte) / 2 : 0) + (file || []).filter(x => x && (tout || !x.fond) && !x.annulee && !x.cle).reduce((s, x) => s + dureeParlee(x.texte), 0);
}
/* pourquoi Azure plutôt que lui, ou null : { chaude (le processus parole a déjà parlé), studio (une chanson ou un travail du Studio
   en calcul), attente_s } */
function raisonSecours({ chaude, studio, attente_s }) {
  // (07/11) ni une chanson en calcul ni son chargement ne passent plus tout de suite à Azure : il attend jusqu'à 60 s (budgetMs), puis Azure
  void chaude; void studio;
  if (attente_s > SEUIL_FILE_S) return `file de ${Math.round(attente_s * 10) / 10} s`;
  return null;
}
const vivant = (pid) => { try { process.kill(Number(pid), 0); return true; } catch (e) { return !!(e && e.code === 'EPERM'); } };
const lireJson = (f) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return null; } };
/* (chant.py, studio.py) une chanson d'ACE-Step (12 à 15 Go) ou un travail du Studio en cours : la même règle que studio.chant_en_cours
   et studio.occupe ; relu toutes les 3 s au plus */
const cacheStudio = { t: 0, v: null };
function studioOccupe(jarvis, maintenant = Date.now()) {
  if (maintenant - cacheStudio.t < 3000 && cacheStudio.jarvis === jarvis) return cacheStudio.v;
  let v = null;
  const dans = (d, re) => { try { return fs.readdirSync(d).filter(n => re.test(n)).map(n => lireJson(path.join(d, n))).filter(Boolean); } catch (_) { return []; } };
  for (const t of dans(path.join(jarvis, 'cwd', 'taches'), /^T-[\w-]+\.json$/))
    if (t.chanson && t.etat === 'en cours' && (!t.superviseur || vivant(t.superviseur))) { v = 'une chanson se calcule'; break; }
  if (!v) for (const t of dans(path.join(jarvis, 'chansons', 'studio', 'travaux'), /^J-[\w-]+\.json$/))
    if (t.etat === 'en cours' && vivant(t.pid)) { v = `le Studio (${String(t.type || 'travail').slice(0, 20)})`; break; }
  Object.assign(cacheStudio, { t: maintenant, v, jarvis });
  return v;
}

/* (07/11, Ahmed : « relie partout ses émotions au ton de sa voix, sinon ça fait ado mal léché ») sa voix Azure suivait le texte seul : le même
   ton plat quelle que soit son humeur. Son expressivité du moment (0 calme, triste ; 1 vif, joyeux, excité : celle que la page et Chatterbox
   reçoivent déjà) règle la hauteur, la force et, vers le haut seulement, le débit (05/11, Ahmed : « le timbre au ralenti » : jamais plus lent). */
function prosodieAzure(emotion) {
  const e = Number(emotion);
  if (emotion == null || !Number.isFinite(e)) return { pitch: '+0%', volume: '+0%', rate: '+0%' };
  const x = Math.max(0, Math.min(1, e)) - 0.5;                     // -0,5 .. +0,5
  const pc = (v) => `${v >= 0 ? '+' : ''}${Math.round(v)}%`;
  return { pitch: pc(x * 16), volume: pc(x * 20), rate: pc(Math.max(0, x) * 12) };
}
module.exports = { prosodieAzure, VOIX, choixVoix, langueLatine, segmenterLangues, SEUIL_FILE_S, dureeParlee, budgetMs, attenteFile, raisonSecours, studioOccupe };

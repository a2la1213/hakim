/* Tests de la transcription PENDANT qu'Ahmed parle, côté page (public/parler.js) : node --test test-transcription.js
   Relecture Opus du 2026-10-16 (prouvée par ses simulations, reprises ici) :
   - un morceau dont la transcription ÉCHOUE ne doit pas disparaître de la phrase (3,6 s perdues) ;
   - un tour qui se finit pendant l'attente ne prête pas sa queue au tour précédent ;
   - Whisper, amorcé par le texte compris, le répète parfois : la répétition est écartée.
   Les fonctions sont extraites de parler.js ; le capteur et Whisper sont simulés (un mot par fenêtre). */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
function extraire(debut) {
  const i = SRC.indexOf(debut);
  assert.ok(i >= 0, `introuvable dans parler.js : ${debut}`);
  if (debut.startsWith('const ')) return SRC.slice(i, SRC.indexOf('\n', i) + 1);
  return SRC.slice(i, SRC.indexOf('\n}\n', i) + 3);
}

function charger(whisper) {
  const cx = { console, Float32Array, ArrayBuffer, DataView, Math, Blob, Date, entendreEnCours: () => {} };   // (30/10) son oreille : hors sujet ici
  cx.window = cx;
  vm.createContext(cx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'public', 'conversation.js'), 'utf8'), cx);  // le vrai filtre utile()
  cx.transcrireVite = whisper;
  vm.runInContext(['const sansAccents', 'function morceauNeuf', 'function surPauseConversation', 'async function texteDuTour']
    .map(extraire).join('\n') + '\nthis.surPauseConversation = surPauseConversation; this.texteDuTour = texteDuTour;', cx);
  return cx;
}

// un tour de n fenêtres ; Whisper rend les mots des fenêtres reçues
function capteurSimule(n, prefixe = 'mot') {
  const c = { tour: Array.from({ length: n }, (_, i) => `${prefixe}${i}`), enParole: true };
  c.precedent = c.tour;
  c.segment = (de, a) => { const m = c.tour.slice(de, a === undefined ? c.tour.length : a); return m.length ? m : null; };
  c.segmentFini = (de, tourFini = c.precedent) => { const m = tourFini.slice(de); return m.length ? m : null; };
  Object.defineProperty(c, 'dernierTour', { get: () => c.precedent });
  return c;
}
const attendre = (ms) => new Promise(r => setTimeout(r, ms));

test('un morceau dont la transcription échoue reste dans la phrase', async () => {
  let echec = true;
  const p = charger(async (wav) => { await attendre(5); return echec ? null : wav.join(' '); });
  const capteur = capteurSimule(400);
  const conv = { capteur, ecrit: { coupe: 0, confirme: '', partiel: null } };
  p.surPauseConversation(conv, 200);                  // le processus voix tombe sur ce morceau
  await conv.ecrit.partiel;
  echec = false;
  capteur.enParole = false;                           // le tour finit
  const texte = await p.texteDuTour(conv);
  assert.strictEqual(texte.split(' ').length, 400, 'les 400 mots, aucun perdu');
  assert.strictEqual(texte, capteur.tour.join(' '));
});

test('la queue qui échoue est signalée (null), pas prise pour du silence', async () => {
  let n = 0;
  const p = charger(async (wav) => { n++; return n === 1 ? wav.join(' ') : null; });
  const capteur = capteurSimule(400);
  const conv = { capteur, ecrit: { coupe: 0, confirme: '', partiel: null } };
  p.surPauseConversation(conv, 200);
  await conv.ecrit.partiel;
  capteur.enParole = false;
  assert.strictEqual(await p.texteDuTour(conv), null);
});

test('un tour qui finit pendant l\'attente ne prête pas sa queue au précédent', async () => {
  const p = charger(async (wav) => { await attendre(30); return wav.join(' '); });
  const capteur = capteurSimule(400);
  const conv = { capteur, ecrit: { coupe: 0, confirme: '', partiel: null } };
  p.surPauseConversation(conv, 200);
  capteur.enParole = false;                            // tour N fini (« j'ai fini »), morceau encore en vol
  const promesse = p.texteDuTour(conv);
  capteur.precedent = Array.from({ length: 300 }, (_, i) => `NOUVEAU${i}`);   // le tour N+1 finit pendant l'attente
  const texte = await promesse;
  assert.ok(!texte.includes('NOUVEAU'), texte.slice(-60));
  assert.strictEqual(texte, capteur.tour.join(' '));
});

test('Whisper qui répète le texte déjà compris : la répétition est écartée, le neuf gardé', async () => {
  const confirme = 'je voudrais que tu regardes le projet Anamnèse';
  const repete = charger(async () => 'le projet Anamnèse.');
  const conv = { capteur: Object.assign(capteurSimule(10), { enParole: false }), ecrit: { coupe: 5, confirme, partiel: null } };
  assert.strictEqual(await repete.texteDuTour(conv), confirme);
  const neuf = charger(async () => 'et la consolidation de cette nuit.');
  conv.ecrit = { coupe: 5, confirme, partiel: null };
  assert.strictEqual(await neuf.texteDuTour(conv), confirme + ' et la consolidation de cette nuit.');
  const invention = charger(async () => "Sous-titres réalisés par la communauté d'Amara.org");
  conv.ecrit = { coupe: 5, confirme, partiel: null };
  assert.strictEqual(await invention.texteDuTour(conv), confirme);
});

// ---- (28/10, Ahmed : « la réactivité de la transcription de ma voix ») la transcription EN AVANCE (après 0,7 s de silence)
// était jetée quand la patience finissait le tour avant elle, et la fin de tour retranscrivait tout DERRIÈRE elle, dans le
// même processus (backtest : 9 tours sur 200 seulement finissaient en avance). Désormais la fin de tour la reprend.
function chargerAvance(whisper) {
  const cx = charger(whisper);
  vm.runInContext(['const SILENCE_ANTICIPE_MS', 'const FIN_SUSPENDUE', 'function phraseFinie', 'function anticiperConversation',
    'function transcriptionEnAvance'].map(extraire).join('\n')
    + '\nthis.anticiperConversation = anticiperConversation; this.transcriptionEnAvance = transcriptionEnAvance;', cx);
  return cx;
}

test('la fin de tour reprend la transcription en avance de ce silence : une seule transcription', async () => {
  let appels = 0;
  const cx = chargerAvance(async (m) => { appels++; await attendre(30); return m.join(' '); });
  const capteur = capteurSimule(4);
  Object.assign(capteur, { derniereVoix: 5000, assezDeVoix: true, finirTour() {} });
  const conv = { capteur, ecrit: { coupe: 0, confirme: '', partiel: null } };
  cx.etat = { reglages: {}, conversation: conv };
  cx.anticiperConversation(conv, 800);
  assert.strictEqual(appels, 1);
  const avance = cx.transcriptionEnAvance(conv, { derniere_voix: 5000 });
  assert.ok(avance, 'reprise : aucune voix depuis la transcription en avance');
  assert.strictEqual(await avance, 'mot0 mot1 mot2 mot3');
  assert.strictEqual(appels, 1, 'pas de deuxième transcription');
  // il a repris la parole depuis : la transcription en avance ne vaut plus pour ce tour
  cx.anticiperConversation(conv, 800);
  assert.strictEqual(cx.transcriptionEnAvance(conv, { derniere_voix: 6000 }), null);
  assert.strictEqual(cx.transcriptionEnAvance({ capteur }, { derniere_voix: 5000 }), null, 'rien en avance : rien');
});

test('câblage : la fin de tour reprend la transcription en avance avant de retranscrire', () => {
  const tour = extraire('async function tourDeParole');
  assert.match(tour, /const avance = transcriptionEnAvance\(conv, infos\);\n\s*conv\.spec = null;/);
  assert.match(tour, /const deAvance = avance \? await avance : null;/);
  assert.match(tour, /: deAvance !== null \? deAvance\n/);
  assert.match(extraire('function anticiperConversation'), /sp\.texte = texteDuTour\(conv\);/);
});

test('(30/10, 22:33, Ahmed) la fin de ta parole se décide après 0,5 s de silence, dans la reconnaissance ; ta patience des réglages ne bouge pas', () => {
  const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  assert.match(page, /const SILENCE_ANTICIPE_MS = 500;/);
  assert.match(page, /patience: 3\.5,/, 'le réglage par défaut reste');
});

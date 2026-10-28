/* Tests du mode Conversation (public/conversation.js) : node --test test-conversation.js
   La transcription EN CONTINU (demande d'Ahmed, 2026-10-16 : « ok pour la transcription pendant que
   je parle ») : à chaque respiration de 0,4 s, la page coupe le tour à l'endroit exact du silence ;
   segment() rend le morceau déjà dit, segmentFini() la queue du tour qui vient de finir. Les deux
   morceaux doivent se recoller SANS perte ni doublon. Faux micro, faux temps : aucun matériel. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const TAUX = 16000, PAR_FENETRE = 320;          // 20 ms à 16 kHz : pas de rééchantillonnage

function charger() {
  let t = 1e6, noeud = null;
  const ctx = { console, Float32Array, ArrayBuffer, DataView, Math, Blob, Date: { now: () => t },
    URL: { createObjectURL: () => 'blob:capteur', revokeObjectURL() {} },
    navigator: { mediaDevices: { getUserMedia: async () => ({ getTracks: () => [], getAudioTracks: () => [] }) } },
    AudioWorkletNode: class { constructor() { noeud = this; this.port = { postMessage() {}, onmessage: null }; } connect() {} disconnect() {} } };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'public', 'conversation.js'), 'utf8'), ctx);
  const actx = { sampleRate: TAUX, destination: {}, audioWorklet: { addModule: async () => {} },
    createMediaStreamSource: () => ({ connect() {}, disconnect() {} }),
    createGain: () => ({ gain: { value: 1 }, connect() {}, disconnect() {} }) };
  // une fenêtre de 20 ms : voix (sinus, marqué par son numéro) ou silence
  let numero = 0;
  const fenetre = (voix) => {
    const f = new Float32Array(PAR_FENETRE);
    numero++;
    for (let i = 0; i < f.length; i++) f[i] = voix ? 0.3 * Math.sin(i / 3) : 0.0005;
    if (voix) f[0] = (numero % 1000) / 4000;      // une signature par fenêtre : retrouver les recollages
    t += 20;
    noeud.port.onmessage({ data: f });
    return f;
  };
  return { Conversation: ctx.Conversation, actx, fenetre, horloge: () => t };
}

async function lireWav(blob) {
  const b = Buffer.from(await blob.arrayBuffer());
  assert.strictEqual(b.toString('ascii', 0, 4), 'RIFF');
  const n = (b.length - 44) / 2, x = new Float32Array(n);
  for (let i = 0; i < n; i++) x[i] = b.readInt16LE(44 + 2 * i) / 0x7fff;
  return x;
}

test('respiration : le tour est coupé dans le silence, et morceau + queue = le tour entier', async () => {
  const { Conversation, actx, fenetre } = charger();
  const pauses = [], fins = [];
  const capteur = await Conversation.demarrer({ ctx: actx, patienceMs: () => 1000, jarvisParle: () => false,
    surPause: (f) => pauses.push({ f, morceau: capteur.segment(0, f) }), surFin: (wav, infos) => fins.push({ wav, infos }) });
  for (let i = 0; i < 15; i++) fenetre(false);                  // le bruit de fond est appris
  const dites = [];
  for (let i = 0; i < 175; i++) dites.push(fenetre(true));      // 3,5 s de parole
  for (let i = 0; i < 25; i++) fenetre(false);                  // une respiration de 0,5 s
  for (let i = 0; i < 50; i++) dites.push(fenetre(true));       // 1 s de plus
  for (let i = 0; i < 60; i++) fenetre(false);                  // silence au-delà de la patience (1 s)
  // deux respirations vues : celle du milieu, et le début du silence final (avant la patience)
  assert.strictEqual(pauses.length, 2, 'une coupure par respiration');
  assert.strictEqual(fins.length, 1, 'le tour est clos après la patience');
  const { f, morceau } = pauses[0];
  const tour = await lireWav(fins[0].wav), avant = await lireWav(morceau), queue = await lireWav(capteur.segmentFini(f));
  assert.strictEqual(avant.length + queue.length, tour.length, 'ni perte ni doublon au recollage');
  assert.deepStrictEqual(Array.from(avant.slice(0, 3200)), Array.from(tour.slice(0, 3200)));
  assert.deepStrictEqual(Array.from(queue.slice(-3200)), Array.from(tour.slice(-3200)));
  // la coupure tombe au DÉBUT du silence : la fin du morceau est la dernière fenêtre parlée
  const fin = avant.slice(-PAR_FENETRE);
  assert.ok(Math.abs(fin[0] - dites[174][0]) < 1e-3, 'le morceau finit sur la dernière fenêtre dite avant la respiration');
  assert.ok(Math.max(...queue.slice(0, PAR_FENETRE).map(Math.abs)) < 0.01, 'la queue commence dans le silence');
});

test('une phrase courte (moins de 3 s) : pas de coupure, tout part en un seul morceau', async () => {
  const { Conversation, actx, fenetre } = charger();
  const pauses = [], fins = [];
  const capteur = await Conversation.demarrer({ ctx: actx, patienceMs: () => 800, jarvisParle: () => false,
    surPause: (f) => pauses.push(f), surFin: (wav) => fins.push(wav) });
  for (let i = 0; i < 15; i++) fenetre(false);
  for (let i = 0; i < 60; i++) fenetre(true);
  for (let i = 0; i < 50; i++) fenetre(false);
  // surPause est appelé (la page décide : moins de 150 fenêtres depuis la dernière coupure → rien)
  assert.strictEqual(fins.length, 1);
  assert.ok(pauses.length <= 1);
  assert.ok(capteur.segmentFini(0).size > 44);
});

test('un morceau sans voix n\'est jamais transcrit (Whisper invente sur le silence)', async () => {
  const { Conversation, actx, fenetre } = charger();
  const pauses = [], fins = [];
  const capteur = await Conversation.demarrer({ ctx: actx, patienceMs: () => 1000, jarvisParle: () => false,
    surPause: (f) => pauses.push(f), surFin: (wav) => fins.push(wav) });
  for (let i = 0; i < 15; i++) fenetre(false);
  for (let i = 0; i < 175; i++) fenetre(true);
  for (let i = 0; i < 60; i++) fenetre(false);                  // la phrase finit : seule reste du silence
  assert.strictEqual(fins.length, 1);
  const coupe = pauses[pauses.length - 1];
  assert.strictEqual(capteur.segmentFini(coupe), null, 'la queue après la dernière respiration est muette : rien à envoyer');
  assert.ok(capteur.segmentFini(0) instanceof Blob, 'le tour entier, lui, a de la voix');
});

test('couper le micro PENDANT qu’on parle : ce qui a été dit part quand même (Ahmed, 2026-10-20)', async () => {
  const { Conversation, actx, fenetre } = charger();
  const fins = [];
  const capteur = await Conversation.demarrer({ ctx: actx, patienceMs: () => 1000, jarvisParle: () => false,
    surFin: (wav, infos) => fins.push({ wav, infos }) });
  for (let i = 0; i < 15; i++) fenetre(false);
  for (let i = 0; i < 100; i++) fenetre(true);                  // 2 s de parole, sans silence
  assert.strictEqual(capteur.enParole, true);
  capteur.muet(true);                                          // le micro coupé en pleine phrase
  assert.strictEqual(fins.length, 1, 'le tour part tout de suite');
  assert.ok(fins[0].infos.voix_ms >= 1500);
  assert.ok((await lireWav(fins[0].wav)).length > 16000, 'avec la parole dite');
  for (let i = 0; i < 100; i++) fenetre(true);                  // micro coupé : plus rien n'est écouté
  assert.strictEqual(capteur.enParole, false);
  assert.strictEqual(fins.length, 1);
  capteur.muet(false);
  capteur.muet(true);                                          // couper sans parler : rien n'est envoyé
  assert.strictEqual(fins.length, 1);
});

// ---- (28/10, Ahmed : « filtrer la vibration du cœur dans le micro », téléphone posé, un « Okay » inventé à 11:08) la page
// sait quand le téléphone vibre (battementCoeur) : 250 ms après chaque battement, le micro n'entend pas une voix
function battements(fenetre, dernier, n, avecMasque) {
  for (let k = 0; k < n; k++) {
    if (avecMasque) dernier.t = fenetre.t();
    for (let i = 0; i < 9; i++) fenetre(true);                  // 180 ms de vibration sur la table, forte comme une voix
    for (let i = 0; i < 36; i++) fenetre(false);                 // le reste du battement (~66 par minute)
  }
}
async function capteurAvecCoeur(avecMasque) {
  const c = charger();
  const dernier = { t: 0 }, fins = [], debuts = [];
  c.fenetre.t = () => c.horloge();
  const capteur = await c.Conversation.demarrer({ ctx: c.actx, patienceMs: () => 1000, jarvisParle: () => false,
    dernierBattement: () => dernier.t, surDebut: () => debuts.push(1), surFin: (wav, infos) => fins.push(infos) });
  for (let i = 0; i < 15; i++) c.fenetre(false);
  return { ...c, capteur, dernier, fins, debuts };
}

test('la vibration de son cœur ne fait jamais un tour ; sans le masque (le témoin), elle en faisait un', async () => {
  const avec = await capteurAvecCoeur(true);
  battements(avec.fenetre, avec.dernier, 10, true);
  assert.strictEqual(avec.debuts.length, 0, 'aucun début de tour sur la vibration');
  assert.strictEqual(avec.fins.length, 0);
  const sans = await capteurAvecCoeur(false);
  battements(sans.fenetre, sans.dernier, 10, false);
  assert.ok(sans.debuts.length > 0, 'le témoin : sans masque, la vibration passe pour une voix');
});

test('une vraie phrase pendant une vibration est entendue, et la vibration ne prolonge pas son tour', async () => {
  const c = await capteurAvecCoeur(true);
  c.dernier.t = c.horloge();
  for (let i = 0; i < 100; i++) c.fenetre(true);                 // 2 s de parole qui commence pendant le battement
  assert.strictEqual(c.debuts.length, 1, 'le tour commence (au plus 250 ms plus tard ; la pré-écoute garde le début)');
  battements(c.fenetre, c.dernier, 4, true);                     // ensuite, seulement son cœur qui vibre
  assert.strictEqual(c.fins.length, 1, 'le tour finit après la patience, malgré les battements');
  assert.ok(c.fins[0].voix_ms < 2400, `la vibration ne compte pas comme voix (${c.fins[0].voix_ms} ms)`);
});

test('la fenêtre de la vibration : de son battement à 250 ms après, pas avant, et rien sans battement', () => {
  const { Conversation } = charger();
  assert.strictEqual(Conversation.enVibration(1000, 1000), true);
  assert.strictEqual(Conversation.enVibration(1250, 1000), true);
  assert.strictEqual(Conversation.enVibration(1260, 1000), false);
  assert.strictEqual(Conversation.enVibration(990, 1000), false);
  assert.strictEqual(Conversation.enVibration(1000, 0), false);
});

test('câblage : la page note chaque battement (même sans animation) et le donne au micro', () => {
  const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  assert.match(page, /window\.battementCoeur = \(\) => \{\n\s+dernierBattementCoeur = Date\.now\(\);/);
  assert.match(page, /dernierBattement: \(\) => dernierBattementCoeur,/);
});

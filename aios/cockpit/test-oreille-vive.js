/* (03/11, 13:25, papa via Hakim : « aucun « je t'écoute » : la transcription en direct dès mon premier mot ; le premier mot arrive en
   retard ») : node --test test-oreille-vive.js
   Une seule oreille vive (le petit Whisper) sert trois usages : la voix de papa, le son du téléphone, les familles de sons.
   Avant : occupée, elle refusait tout (429) — le premier mot de papa attendait 0,5 s de voix de plus pour retenter. Mesuré le
   03/11 à 13:28 (Mac à 13,5 de charge) : 0,6 à 1,3 s par demande. Maintenant la voix de papa passe avant : occupée, sa demande
   attend son tour (une seule, la plus récente) ; les autres sont refusées tant qu'une demande de papa attend. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const fonction = (nom) => { const i = SRC.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2); };

function monter() {
  const ecrits = [];
  const ctx = { setTimeout: () => 0, clearTimeout() {}, j: JSON.stringify,
    oreilleVive: { proc: { stdin: { write: (l) => ecrits.push(JSON.parse(l)) } }, pret: true, attente: null, suivante: null, n: 0, ids: 0 } };
  vm.createContext(ctx);
  vm.runInContext(['oreilleDemander', 'oreilleEnvoyer', 'oreilleSuivante', 'oreilleRecue'].map(fonction).join('\n'), ctx);
  // la réponse de Whisper à la demande en cours
  const repondre = (texte) => ctx.oreilleRecue({ id: ctx.oreilleVive.attente.id, texte });
  return { ctx, ecrits, repondre };
}

test('libre : la demande part tout de suite', async () => {
  const m = monter();
  const p = m.ctx.oreilleDemander({ fichier: 'a.wav' }, true);
  assert.strictEqual(m.ecrits.length, 1);
  m.repondre('bonjour');
  assert.strictEqual((await p).texte, 'bonjour');
});

test('occupée par le téléphone : la voix de papa attend son tour, puis passe ; le téléphone est refusé tant qu\'elle attend', async () => {
  const m = monter();
  const tel = m.ctx.oreilleDemander({ fichier: 'tel.wav' }, false);
  const papa = m.ctx.oreilleDemander({ fichier: 'papa.wav' }, true);
  assert.strictEqual(m.ecrits.length, 1, 'une seule à la fois');
  assert.deepStrictEqual({ ...(await m.ctx.oreilleDemander({ fichier: 'tel2.wav' }, false)) }, { occupee: true });
  m.repondre('la musique');
  assert.strictEqual((await tel).texte, 'la musique');
  assert.strictEqual(m.ecrits.length, 2, 'la voix de papa part dès que l\'oreille est libre');
  assert.strictEqual(m.ecrits[1].fichier, 'papa.wav');
  m.repondre('bonjour mon fils');
  assert.strictEqual((await papa).texte, 'bonjour mon fils');
});

test('deux demandes de papa en attente : seule la plus récente reste (elle contient tout), l\'ancienne est remplacée', async () => {
  const m = monter();
  m.ctx.oreilleDemander({ fichier: 'famille.wav', op: 'famille' }, false);
  const vieille = m.ctx.oreilleDemander({ fichier: 'papa1.wav' }, true);
  const neuve = m.ctx.oreilleDemander({ fichier: 'papa2.wav' }, true);
  assert.deepStrictEqual({ ...(await vieille) }, { occupee: true, remplacee: true });
  m.repondre('');
  assert.strictEqual(m.ecrits[1].fichier, 'papa2.wav');
  m.repondre('bonjour');
  assert.strictEqual((await neuve).texte, 'bonjour');
});

test('pas encore prête : refus, sans rien écrire', async () => {
  const m = monter();
  m.ctx.oreilleVive.pret = false;
  assert.deepStrictEqual({ ...(await m.ctx.oreilleDemander({ fichier: 'a.wav' }, true)) }, { occupee: true });
  assert.strictEqual(m.ecrits.length, 0);
});

// la page : le premier mot plus tôt, et un refus ne coûte plus 0,5 s
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
function page() {
  const i = PAGE.indexOf('function vifConversation(');
  const appels = [];
  let reponse = { ok: true, json: () => Promise.resolve({ texte: 'Bonjour' }) };
  const ctx = { etat: { reglages: { langue: 'fr' } }, jeton: () => 'x', encodeURIComponent, sousTitre() {}, entendreEnCours() {},
    tempsMorceau: () => '', morceauNeuf: (t) => t, journalVoix() {}, Date, patienceConversation: () => 300,
    fetch: (url) => { appels.push(url); return Promise.resolve(reponse); } };
  vm.createContext(ctx);
  vm.runInContext(PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 2), ctx);
  const cap = { enParole: true, fenetres: 0, segment: () => 'wav', debutTour: Date.now() - 400 };
  const conv = { ecrit: { coupe: 0, confirme: '', partiel: null }, capteur: cap };
  return { ctx, appels, cap, conv, refuser: () => { reponse = { ok: false, json: () => Promise.resolve({}) }; },
    accepter: () => { reponse = { ok: true, json: () => Promise.resolve({ texte: 'Bonjour' }) }; } };
}
const tour = () => new Promise(r => setImmediate(r));

// (04/11, 11:03, Ahmed : « tout relier ») le premier mot et chaque suite après le délai de la Conversation (0,3 s : 15 fenêtres)
test('page : la première demande part dès 0,3 s de voix (15 fenêtres), les suivantes aussi toutes les 0,3 s', async () => {
  const p = page();
  p.cap.fenetres = 14; p.ctx.vifConversation(p.conv); assert.strictEqual(p.appels.length, 0);
  p.cap.fenetres = 15; p.ctx.vifConversation(p.conv); assert.strictEqual(p.appels.length, 1, 'premier mot : 0,3 s suffisent');
  await tour(); await tour();
  p.cap.fenetres = 29; p.ctx.vifConversation(p.conv); assert.strictEqual(p.appels.length, 1, 'ensuite : 0,3 s de neuf');
  p.cap.fenetres = 30; p.ctx.vifConversation(p.conv); assert.strictEqual(p.appels.length, 2);
});

test('page : un refus de l\'oreille ne coûte plus 0,5 s : la demande repart au tic suivant', async () => {
  const p = page();
  p.refuser();
  p.cap.fenetres = 15; p.ctx.vifConversation(p.conv);
  await tour(); await tour(); await tour();
  p.accepter();
  p.cap.fenetres = 20; p.ctx.vifConversation(p.conv);
  assert.strictEqual(p.appels.length, 2, 'repartie 0,1 s après, pas 0,5 s');
});

test('page : aucun « je t\'écoute » à la place de ses mots', () => {
  assert.doesNotMatch(PAGE, /sousTitre\('je t’écoute…'\)/);
  assert.doesNotMatch(PAGE, /surDebut: \(\) => \{[^\n]*sousTitre\('…'\)/);
  assert.doesNotMatch(PAGE, /surDebut: \(\) => \{[^\n]*je t’écoute/);
});

// (13:59, papa : « l'écoute de Hakim et la transcription en parallèle, avec un mot de décalage ; sur l'interface, le micro quand je
// parle, le mot qui se transcrit, et s'il réfléchit, sur la même ligne »)
function ligne(mots = true) {
  const ctx = { etat: { flux: null }, motsEnConversation: () => mots, enTelepathie: () => false };
  vm.createContext(ctx);
  const i = PAGE.indexOf('function ligneEnDirect('), k = PAGE.indexOf('function motsEnCours(');
  vm.runInContext(PAGE.slice(k, PAGE.indexOf('\n}\n', k) + 2) + PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 2), ctx);   // (04/11) morceau par morceau
  return ctx;
}
test('une seule ligne en direct : le micro quand papa parle, ses mots, la transcription en cours, et sa réflexion', () => {
  const p = ligne();
  const conv = { capteur: { enParole: true }, ecrit: { confirme: 'Bonjour mon fils,', vif: 'tu vas', vifEnCours: {} }, pense: true };
  assert.strictEqual(p.ligneEnDirect(conv), '🎙️ Bonjour mon fils, tu vas ✍️ 💭');
  conv.capteur.enParole = false; conv.ecrit.vifEnCours = null; conv.pense = false;
  p.etat.flux = {};
  assert.strictEqual(p.ligneEnDirect(conv), 'Bonjour mon fils, tu vas 💭', 'il s\'est tu : ses mots, et Hakim réfléchit');
  conv.ecrit.vif = 'x'.repeat(200);
  assert.ok(p.ligneEnDirect(conv).length < 110, 'une ligne : la fin de ses mots seulement');
});
// (16:08, Ahmed : « même en Conversation, pas mes mots par défaut ») sans mots_conversation : le micro, la transcription, la réflexion
test('(16:08) par défaut, la ligne en direct ne montre pas les mots de papa', () => {
  const p = ligne(false);
  const conv = { capteur: { enParole: true }, ecrit: { confirme: 'Bonjour mon fils,', vif: 'tu vas', vifEnCours: {} }, pense: true };
  assert.strictEqual(p.ligneEnDirect(conv), '🎙️ ✍️ 💭');
});

test('le cockpit dit à la page quand ses trois voix réfléchissent déjà pendant que papa parle', () => {
  const i = SRC.indexOf('async function routeVif(');
  assert.match(SRC.slice(i, SRC.indexOf('\n}\n', i)), /pense: !!\(speculation\.promesse && !speculation\.fini\)/);
  assert.match(PAGE, /conv\.pense = !!o\.pense;/);
  assert.match(PAGE, /journalVoix\('vif_decalage', \{ ms: /);
});

/* Le Mac injoignable (2026-10-23, Ahmed en voiture : 9 min à parler sans que rien n'arrive) : node --test test-hors-ligne.js
   Le module de la page (parler.js) et le tour de parole sont lus dans le fichier et joués à part, sans réseau. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const fonction = (nom) => { const i = src.indexOf(`async function ${nom}(`) >= 0 ? src.indexOf(`async function ${nom}(`) : src.indexOf(`function ${nom}(`);
  return src.slice(i, src.indexOf('\n}\n', i) + 2); };

function page({ mac = true, transcrire = async () => 'bonjour' } = {}) {
  const banniere = { hidden: true, textContent: '', classList: { toggle() {} } };
  const envois = [], journal = [];
  const ctx = {
    Math, JSON, String, Array, Date, Promise, encodeURIComponent, URLSearchParams,
    etat: { messages: [] }, $: () => banniere, journalVoix: (e, d) => journal.push([e, d]), humeur() {}, jeton: () => 'j',
    envoyerJournalVoix() {}, setTimeout: (f) => 0, clearTimeout() {},
    AbortController: class { constructor() { this.signal = {}; } abort() {} },
    Conversation: { utile: (t) => /\p{L}{2,}/u.test(String(t || '')) },
    transcrireVite: (...a) => transcrire(...a),
    envoyer: async (...a) => { envois.push(a); },
    fetch: async (url) => {
      if (!ctx.mac) throw new TypeError('Failed to fetch');
      const id = new URL(url, 'http://x').searchParams.get('tour_id');
      if (url.startsWith('/api/jarvis/recu') && ctx.ancienCockpit) return { ok: false, status: 404, json: async () => ({}) };
      return { ok: true, json: async () => ({ recu: ctx.recus.has(id) }) };
    },
    mac, recus: new Set(),
  };
  vm.createContext(ctx);
  const debut = src.indexOf('/* ---------- le Mac injoignable'), fin = src.indexOf('setInterval(reprendreHorsLigne, 5000);');
  vm.runInContext("const horsLigne = { depuis: 0, tours: [], envois: [], enCours: false, panne: 'reseau' };"
    + src.slice(debut, fin) + 'this.horsLigne = horsLigne; this.garder = garderHorsLigne; this.reprendre = reprendreHorsLigne;', ctx);
  return { ctx, banniere, envois, journal };
}

test("une coupure : l'écran le dit, avec le nombre de messages gardés ; rien ne part tant que le Mac ne répond pas", async () => {
  const p = page({ mac: false });
  p.ctx.garder('wav1', Date.UTC(2026, 9, 23, 16, 10)); p.ctx.garder('wav2', Date.UTC(2026, 9, 23, 16, 12));
  assert.equal(p.banniere.hidden, false);
  assert.match(p.banniere.textContent, /Pas de connexion avec le Mac — je garde ce que tu dis \(2 messages en attente\)/);
  await p.ctx.reprendre();
  assert.equal(p.envois.length, 0);
  assert.equal(p.ctx.horsLigne.tours.length, 2);
});

test('au retour du Mac : tout est transcrit dans l’ordre et part en UN message, daté', async () => {
  const textes = { wav1: 'tu m’entends ?', wav2: 'je suis dans la voiture', wav3: '' };
  const p = page({ transcrire: async (w) => textes[w] });
  p.ctx.garder('wav1', new Date(2026, 9, 23, 18, 10).getTime());
  p.ctx.garder('wav2', new Date(2026, 9, 23, 18, 11).getTime());
  p.ctx.garder('wav3', new Date(2026, 9, 23, 18, 16).getTime());           // du bruit : transcrit vide, pas envoyé
  await p.ctx.reprendre();
  assert.equal(p.envois.length, 1);
  assert.equal(p.envois[0][0], '(dit pendant la coupure, de 18:10 à 18:16) tu m’entends ? … je suis dans la voiture');
  assert.equal(p.envois[0][1], true);
  assert.equal(p.ctx.horsLigne.depuis, 0);
  assert.equal(p.ctx.horsLigne.tours.length, 0);
});

test('rien n’est jeté : un tour déjà compris garde son texte si la suite échoue encore', async () => {
  let appels = 0, panne = true;
  const p = page({ transcrire: async (w) => { appels++; return w === 'wav2' && panne ? null : `texte de ${w}`; } });
  p.ctx.garder('wav1', 1); p.ctx.garder('wav2', 2);
  await p.ctx.reprendre();
  assert.equal(p.envois.length, 0);
  assert.equal(p.ctx.horsLigne.tours[0].texte, 'texte de wav1');
  panne = false; appels = 0;
  await p.ctx.reprendre();
  assert.equal(appels, 1, 'seul le tour pas encore compris est retranscrit');
  assert.match(p.envois[0][0], /texte de wav1 … texte de wav2$/);
});

test('un cockpit pas encore relancé (sans /api/jarvis/recu) : dans le doute, le message est renvoyé', async () => {
  const p = page();
  p.ctx.ancienCockpit = true;
  const m = { id: 21, texte: '' };
  p.ctx.etat.messages.push(m);
  p.ctx.horsLigne.depuis = 1;
  p.ctx.horsLigne.envois.push({ tourId: '21', texte: 'peut-être perdu', oral: true, m });
  await p.ctx.reprendre();
  assert.deepEqual(p.envois.map(e => e[0]), ['peut-être perdu']);
});

test('un message parti pendant la coupure : renvoyé seulement si le Mac ne l’a pas reçu', async () => {
  const p = page();
  const m1 = { id: 11, texte: '' }, m2 = { id: 12, texte: '' };
  p.ctx.etat.messages.push(m1, m2);
  p.ctx.recus.add('12');
  p.ctx.horsLigne.depuis = 1;
  p.ctx.horsLigne.envois.push({ tourId: '11', texte: 'pas arrivé', oral: true, m: m1 }, { tourId: '12', texte: 'arrivé', oral: false, m: m2 });
  await p.ctx.reprendre();
  assert.deepEqual(p.envois.map(e => e[0]), ['pas arrivé']);
  assert.ok(!p.ctx.etat.messages.includes(m1), 'sa réponse vide en attente est remplacée par le renvoi');
  assert.ok(p.ctx.etat.messages.includes(m2));
});

/* le tour de parole : une transcription ratée n'est plus prise pour du bruit */
function tour({ transcrire }) {
  const gardes = [], journal = [];
  const ctx = {
    Date, Math, String, journalVoix: (e) => journal.push(e), humeur() {}, reprendreVoix: () => false,
    Conversation: { utile: (t) => /\p{L}{2,}/u.test(String(t || '')) },
    transcrireVite: transcrire, texteDuTour: async () => null,
    horsLigne: { depuis: 0 }, garderHorsLigne: (w) => gardes.push(w),
    etat: {}, retirerEcho: (t) => ({ texte: t, retire: false }),
  };
  vm.createContext(ctx);
  vm.runInContext(fonction('tourDeParole') + 'this.tourDeParole = tourDeParole;', ctx);
  const conv = { enAttente: 0, ecrit: null };
  ctx.etat.conversation = conv;
  return { ctx, conv, gardes, journal };
}

test('transcription ratée (réseau) : le tour est gardé, pas jeté comme du bruit', async () => {
  const t = tour({ transcrire: async () => null });
  await t.ctx.tourDeParole(t.conv, 'wav', {}, null);
  assert.deepEqual(t.gardes, ['wav']);
  assert.ok(!t.journal.includes('tour_bruit'));
  assert.equal(t.conv.enAttente, 0);
});

test('Mac déjà injoignable : gardé tout de suite, sans attendre une transcription impossible', async () => {
  let appels = 0;
  const t = tour({ transcrire: async () => { appels++; return 'x'; } });
  t.ctx.horsLigne.depuis = 1;
  await t.ctx.tourDeParole(t.conv, 'wav', {}, null);
  assert.deepEqual(t.gardes, ['wav']);
  assert.equal(appels, 0);
});

test('un vrai bruit (transcription vide, réussie) reste du bruit', async () => {
  const t = tour({ transcrire: async () => '' });
  await t.ctx.tourDeParole(t.conv, 'wav', {}, null);
  assert.deepEqual(t.gardes, []);
  assert.ok(t.journal.includes('tour_bruit'));
});

/* le cockpit : se souvenir des messages arrivés (borné) */
test('le cockpit retient les messages arrivés, 500 au plus', () => {
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  const i = srv.indexOf('const toursRecus'), f = srv.indexOf('\n}\n', srv.indexOf('function noterTourRecu')) + 2;
  const ctx = {}; vm.createContext(ctx);
  vm.runInContext(srv.slice(i, f) + 'this.noter = noterTourRecu; this.recus = toursRecus;', ctx);
  for (let k = 0; k < 520; k++) ctx.noter(`t${k}`);
  assert.equal(ctx.recus.size, 500);
  assert.ok(ctx.recus.has('t519') && !ctx.recus.has('t0'));
});

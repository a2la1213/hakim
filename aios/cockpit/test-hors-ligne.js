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
const VOIX = { ton: { f0: 130, energie_db: -20 } };
function tour({ transcrire }) {
  const gardes = [], journal = [];
  const ctx = {
    Date, Math, String, journalVoix: (e) => journal.push(e), humeur() {}, reprendreVoix: () => { ctx.reprises = (ctx.reprises || 0) + 1; return true; },
    Conversation: { utile: (t) => /\p{L}{2,}/u.test(String(t || '')) },
    transcrireVite: transcrire, texteDuTour: async () => null,
    horsLigne: { depuis: 0 }, garderHorsLigne: (w) => gardes.push(w),
    etat: {}, retirerEcho: (t) => ({ texte: t, retire: false }),
  };
  vm.createContext(ctx);
  vm.runInContext('const tourSansVoix = (infos) => !(infos && infos.ton);' + fonction('transcriptionEnAvance') + fonction('tourDeParole') + 'this.tourDeParole = tourDeParole;', ctx);
  const conv = { enAttente: 0, ecrit: null };
  ctx.etat.conversation = conv;
  return { ctx, conv, gardes, journal };
}

test('transcription ratée (réseau) : le tour est gardé, pas jeté comme du bruit', async () => {
  const t = tour({ transcrire: async () => null });
  await t.ctx.tourDeParole(t.conv, 'wav', VOIX, null);
  assert.deepEqual(t.gardes, ['wav']);
  assert.ok(!t.journal.includes('tour_bruit'));
  assert.equal(t.conv.enAttente, 0);
});

test('Mac déjà injoignable : gardé tout de suite, sans attendre une transcription impossible', async () => {
  let appels = 0;
  const t = tour({ transcrire: async () => { appels++; return 'x'; } });
  t.ctx.horsLigne.depuis = 1;
  await t.ctx.tourDeParole(t.conv, 'wav', VOIX, null);
  assert.deepEqual(t.gardes, ['wav']);
  assert.equal(appels, 0);
});

test('un vrai bruit (transcription vide, réussie) reste du bruit', async () => {
  const t = tour({ transcrire: async () => '' });
  await t.ctx.tourDeParole(t.conv, 'wav', VOIX, null);
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

/* le micro bloqué par le téléphone (un appel) : dit, noté, le son relancé */
function veille({ trameIlYa = 0, prise = false } = {}) {
  let t = 1_800_000_000_000;
  const bandeau = [], journal = [], relances = [];
  const capteur = { derniereTrame: t - trameIlYa, pisteMuette: prise };
  const ctx = {
    Math, Promise, journalVoix: (e) => journal.push(e), montrerHorsLigne: (x) => bandeau.push(x),
    Date: class extends Date { constructor(...a) { super(...(a.length ? a : [t])); } static now() { return t; } },
    etat: { conversation: { capteur } }, horsLigne: { depuis: 0 }, document: { visibilityState: 'hidden' },
    actx: { state: 'running', suspend: async () => { relances.push('s'); }, resume: async () => { relances.push('r'); } },
    $: () => ({ addEventListener() {} }), setInterval() {}, finirConversation() {}, basculerConversation() {}, setTimeout() {},
  };
  vm.createContext(ctx);
  const d = src.indexOf('const veilleMicro'), f = src.indexOf("$('horsLigne').addEventListener('click'");
  vm.runInContext(src.slice(d, f) + 'this.surveiller = surveillerMicro; this.veille = veilleMicro;', ctx);
  return { ctx, capteur, bandeau, journal, relances, avancer: (ms) => { t += ms; }, maintenant: () => t };
}

test('micro qui ne reçoit plus rien (2,5 s) : bandeau, trace, son relancé — une fois toutes les 3 s', async () => {
  const v = veille({ trameIlYa: 3000 });
  v.ctx.surveiller(); await new Promise(r => setImmediate(r));
  assert.match(v.bandeau.at(-1), /Le micro ne reçoit plus rien/);
  assert.deepEqual(v.journal, ['micro_bloque']);
  assert.deepEqual(v.relances, ['s', 'r']);
  v.avancer(1000); v.ctx.surveiller(); await new Promise(r => setImmediate(r));
  assert.equal(v.relances.length, 2, 'pas avant 3 s');
  v.capteur.derniereTrame = v.maintenant();                              // les trames reviennent
  v.ctx.surveiller();
  assert.deepEqual(v.journal, ['micro_bloque', 'micro_repris']);
  assert.equal(v.bandeau.at(-1), '');
});

test('le téléphone a pris le micro (un appel) : dit, sans relancer le son', async () => {
  const v = veille({ prise: true });
  v.ctx.surveiller(); await new Promise(r => setImmediate(r));
  assert.match(v.bandeau.at(-1), /Le téléphone a pris le micro/);
  assert.equal(v.relances.length, 0);
});

test('tout va bien : rien ne s’affiche', () => {
  const v = veille({ trameIlYa: 100 });
  v.ctx.surveiller();
  assert.equal(v.bandeau.length, 0);
  assert.equal(v.journal.length, 0);
});

test('Mac injoignable mais un simple bruit (pas de voix) : rien n’est gardé, il reprend sa parole', async () => {
  const t = tour({ transcrire: async () => null });
  await t.ctx.tourDeParole(t.conv, 'wav', {}, null);
  assert.deepEqual(t.gardes, []);
  assert.equal(t.ctx.reprises, 1);
});

test('coupé par un bruit et déjà repris : ce tour-là n’est ni transcrit ni envoyé', async () => {
  let appels = 0;
  const t = tour({ transcrire: async () => { appels++; return 'klaxon'; } });
  t.conv.bruitDuTour = true;
  await t.ctx.tourDeParole(t.conv, 'wav', {}, null);
  assert.equal(appels, 0);
  assert.equal(t.conv.bruitDuTour, false);
  assert.ok(t.journal.includes('tour_bruit'));
});

/* la coupure : 1,2 s sans voix → il reprend tout de suite ; une voix → on l'écoute */
function coupure({ tonTour }) {
  let t = 1_800_000_000_000, tic = null;
  const ctx = {
    Date: class extends Date { constructor(...a) { super(...(a.length ? a : [t])); } static now() { return t; } },
    setInterval: (f) => { tic = f; return 1; }, clearInterval: () => { tic = null; }, journalVoix() {},
    lecteur: { enPause: true }, reprendreVoix: () => { ctx.reprises = (ctx.reprises || 0) + 1; ctx.lecteur.enPause = false; return true; },
    etat: {},
  };
  vm.createContext(ctx);
  vm.runInContext(fonction('surveillerCoupure') + 'this.surveiller = surveillerCoupure;', ctx);
  const conv = { capteur: { enParole: true, tonTour } };
  ctx.etat.conversation = conv;
  ctx.surveiller(conv);
  return { ctx, conv, avancer: (ms) => { t += ms; if (tic) tic(); } };
}

test('coupé par un bruit : il reprend après 1,2 s sans voix', () => {
  const c = coupure({ tonTour: 2 });
  c.avancer(600);
  assert.equal(c.ctx.reprises, undefined);
  c.avancer(700);
  assert.equal(c.ctx.reprises, 1);
  assert.equal(c.conv.bruitDuTour, true);
});

test('coupé par sa voix (assez de son voisé) : il reste en pause et l’écoute', () => {
  const c = coupure({ tonTour: 25 });
  c.avancer(1500); c.avancer(1500);
  assert.equal(c.ctx.reprises, undefined);
  assert.ok(!c.conv.bruitDuTour);
});

/* le jeton change à chaque démarrage du cockpit (journal du 23/10, 18:56 : onze transcriptions refusées « 403 ») */
test('transcription refusée « 403 » : le jeton est repris et la même demande repart', async () => {
  const appels = [];
  let jetonCourant = 'ancien';
  const ctx = {
    Date, Math, encodeURIComponent, setTimeout: () => 1, clearTimeout() {}, journalVoix() {},
    AbortController: class { constructor() { this.signal = {}; } abort() {} },
    etat: { reglages: { langue: 'fr' } }, horsLigne: { panne: '' }, jeton: () => jetonCourant,
    rafraichirJeton: async () => { jetonCourant = 'neuf'; return true; },
    fetch: async (url, o) => { appels.push(o.headers['X-Jeton']);
      return o.headers['X-Jeton'] === 'neuf' ? { ok: true, status: 200, json: async () => ({ texte: 'bonjour' }) } : { ok: false, status: 403, json: async () => ({}) }; },
  };
  vm.createContext(ctx);
  vm.runInContext(fonction('delaiTranscription') + fonction('transcrireVite') + 'this.transcrire = transcrireVite;', ctx);
  assert.equal(await ctx.transcrire('wav', 'audio/wav'), 'bonjour');
  assert.deepEqual(appels, ['ancien', 'neuf']);
});

test('le nouveau jeton est lu dans la page Parler redemandée au cockpit', async () => {
  const meta = { content: 'a'.repeat(48) };
  const ctx = { journalVoix() {}, setTimeout: () => 1,
    document: { querySelector: () => meta },
    fetch: async () => ({ text: async () => `<head>\n  <meta name="cockpit-jeton" content="${'b'.repeat(48)}">\n</head>` }) };
  vm.createContext(ctx);
  const d = src.indexOf('let jetonEnCours'), f = src.indexOf('// la réponse du Mac');
  vm.runInContext(src.slice(d, f) + 'this.rafraichir = rafraichirJeton;', ctx);
  assert.equal(await ctx.rafraichir(), true);
  assert.equal(meta.content, 'b'.repeat(48));
});

test('25 s sans réponse : le Mac est dit « débordé », pas « sans connexion »', async () => {
  const ctx = {
    Date, Math, encodeURIComponent, setTimeout: () => 1, clearTimeout() {}, journalVoix() {},
    AbortController: class { constructor() { this.signal = {}; } abort() {} },
    etat: { reglages: { langue: 'fr' } }, horsLigne: { panne: '' }, jeton: () => 'j', rafraichirJeton: async () => false,
    fetch: async () => { const e = new Error('délai'); e.name = 'AbortError'; throw e; },
  };
  vm.createContext(ctx);
  vm.runInContext(fonction('delaiTranscription') + fonction('transcrireVite') + 'this.transcrire = transcrireVite;', ctx);
  assert.equal(await ctx.transcrire('wav'), null);
  assert.equal(ctx.horsLigne.panne, 'lent');
});

/* l'écho (2026-10-23, 20:05 : Ahmed pris pour l'écho de Hakim) : seulement si SA voix jouait pendant le tour */
test('écho possible seulement pendant sa voix (ou 1,5 s après) ; sinon les mots d’Ahmed sont les siens', () => {
  let t = 1_000_000;
  const ctx = { Date: class extends Date { static now() { return t; } }, etat: { parleDepuis: 0 }, noterPresent() {} };
  vm.createContext(ctx);
  const d = src.indexOf('const voixJouee = [];'), f = src.indexOf('\n}\n', src.indexOf('function noterParoleJarvis')) + 2;
  vm.runInContext(src.slice(d, f) + 'this.pendant = voixPendant; this.noter = noterParoleJarvis;', ctx);
  ctx.noter(true); t += 4000; ctx.noter(false);                      // il a parlé de 1 000 000 à 1 004 000
  assert.equal(ctx.pendant(1_003_000, 1_005_000), true);            // pendant sa voix
  assert.equal(ctx.pendant(1_005_000, 1_007_000), true);            // juste après (la pièce résonne)
  assert.equal(ctx.pendant(1_010_000, 1_013_000), false);           // 6 s après : c'est Ahmed
  ctx.noter(true);                                                   // il reparle maintenant
  assert.equal(ctx.pendant(t - 200, t + 2000), true);
});

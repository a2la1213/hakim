/* (14/11, 12:54, Ahmed par Hakim : « quand on parle longtemps, tu n'attends pas qu'on finisse de parler pour rebondir, tu sautes dans nos
   pauses » ; « que tu puisses nous écouter jusqu'au bout de nos paroles et rebondir au bon moment » ; validé par Ahmed vers 13 h)
   Mesuré le 14/11 (mesure/fin-de-phrase.py) : 204 fins de tour anticipées à 0,5 s de silence, dont 183 alors qu'il attendait que papa
   raconte ; papa a repris moins de 3 s après sa dernière voix 73 fois ; 172 suites collées, 76 réponses coupées (67 jamais entendues).
   Ce que ces tests tiennent :
   1. sa parole longue (2 s de voix) ou sa phrase reprise (moins de 4 s, Hakim muet entre-temps) : son tour ne se ferme qu'après 2 s de
      silence, par TOUS les chemins (sa patience, la fin anticipée, la transcription en avance) ; sa parole courte : 1 s (14/11, 14:25,
      Ahmed : « Gooo » ; avant : 0,5 s quand sa phrase semblait finie, 9 fins trop tôt de plus évitées au rejeu, ~1 ms de coût) ;
   2. la transcription en avance (à 0,5 s de silence) est gardée : un tour fermé plus tard la reprend sans tout retranscrire ;
   3. sa réponse lâchée parce que papa continuait sa phrase : ni coupure, ni « [coupé : Ahmed a repris la parole] », ni arrêt à lui redire.
   node --test test-fin-de-phrase.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const CONV = fs.readFileSync(path.join(__dirname, 'public', 'conversation.js'), 'utf8');
function extraire(src, debut) {
  const i = src.indexOf(debut);
  assert.ok(i >= 0, debut);
  if (debut.startsWith('const ')) return src.slice(i, src.indexOf('\n', i) + 1).replace(/^const /, 'var ');
  return src.slice(i, src.indexOf('\n}\n', i) + 3);
}
// le bloc de la fin de phrase longue (constantes et fonctions), tel quel
const BLOC = (() => {
  const i = PAGE.indexOf('const PAROLE_REPRISE_MS'), j = PAGE.indexOf('// fin de la phrase longue (14/11)');
  assert.ok(i >= 0 && j > i, 'le bloc de la fin de phrase longue');
  return PAGE.slice(i, j).replace(/^const /gm, 'var ');
})();

// ---- la page, en vm : le vrai bloc, la vraie patience de fin de tour ----
function pageFin(rythme = {}) {
  const journal = [];
  const ctx = { Date, Math, Number, String, Object, Promise, setTimeout, clearTimeout,
    etat: { reglages: { patienceConversation: 0.5 }, conversation: null, dernierMotDitA: 0 },
    voixEpissee: () => true, journalVoix: (e, d) => journal.push([e, d]),
    rythmeVoix: (k, d) => (k in rythme ? rythme[k] : d) };
  vm.createContext(ctx);
  vm.runInContext([BLOC, extraire(PAGE, 'const patienceConversation = '), extraire(PAGE, 'const finDeTourConversation = ')].join('\n'), ctx);
  return { ctx, journal };
}

test('sa parole courte : son tour se ferme à 1 s, jamais avant (avant : 0,5 s) ; longue ou reprise : 2 s', () => {
  const { ctx } = pageFin();
  const conv = { capteur: { enParole: true, voixTour: 800 } };
  ctx.etat.conversation = conv;
  ctx.debutDeParole(conv, 1e6);
  assert.strictEqual(ctx.plancherFinDeTour(conv), 1000, 'courte : 1 s (14/11, 14:25, « Gooo »)');
  assert.strictEqual(ctx.finDeTourConversation(), 1000, 'son codon stop');
  ctx.voixEpissee = () => false;
  assert.strictEqual(ctx.finDeTourConversation(), 1000, 'sans épissage non plus : plus jamais son délai de 0,5 s');
  ctx.voixEpissee = () => true;
  conv.capteur.voixTour = 2100;
  assert.strictEqual(ctx.plancherFinDeTour(conv), 2000, 'longue (2 s de voix) : 2 s de silence');
  assert.strictEqual(ctx.finDeTourConversation(), 2000);
  ctx.etat.conversation = null;
  assert.strictEqual(ctx.finDeTourConversation(), 1000, 'sans Conversation : rien ne change');
});

test('sa phrase reprise moins de 4 s après sa dernière voix, Hakim muet entre-temps : la même parole, traitée longue', () => {
  const { ctx, journal } = pageFin();
  const conv = { capteur: { enParole: true, voixTour: 0 } };
  ctx.debutDeParole(conv, 1e6);
  ctx.finDeParole(conv, { voix_ms: 900, derniere_voix: 1e6 + 1200 });
  ctx.debutDeParole(conv, 1e6 + 1200 + 1500);                        // il reprend 1,5 s plus tard
  conv.capteur.voixTour = 300;
  assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.paroleDePapa(conv))), { voixMs: 1200, suite: true });
  assert.strictEqual(ctx.plancherFinDeTour(conv), 2000, 'une suite : 2 s, même courte');
  assert.deepStrictEqual(JSON.parse(JSON.stringify(journal.find(x => x[0] === 'parole_reprise')[1])), { blanc_ms: 1500, voix_ms: 900, tours: 1 });
  // Hakim a dit un mot depuis : c'est un nouvel échange
  ctx.finDeParole(conv, { voix_ms: 300, derniere_voix: 1e6 + 3000 });
  ctx.etat.dernierMotDitA = 1e6 + 3500;
  ctx.debutDeParole(conv, 1e6 + 4000);
  conv.capteur.voixTour = 200;
  assert.strictEqual(ctx.plancherFinDeTour(conv), 1000, 'il avait parlé : nouvel échange, court');
  // un long blanc (plus de 4 s) : une nouvelle parole
  ctx.finDeParole(conv, { voix_ms: 300, derniere_voix: 1e6 + 5000 });
  ctx.debutDeParole(conv, 1e6 + 5000 + 4500);
  assert.strictEqual(ctx.paroleDePapa(conv).suite, false);
});

test('ses trois réglages sont à lui (rythme_regler) : parole_longue, silence_parole_longue, silence_parole_courte', () => {
  const { ctx } = pageFin({ parole_longue: 4, silence_parole_longue: 2.6, silence_parole_courte: 1.2 });
  const conv = { capteur: { enParole: true, voixTour: 3000 } };
  ctx.debutDeParole(conv, 1e6);
  assert.strictEqual(ctx.plancherFinDeTour(conv), 1200, '3 s de voix sous son seuil de 4 s : son silence de parole courte');
  conv.capteur.voixTour = 4100;
  assert.strictEqual(ctx.plancherFinDeTour(conv), 2600);
  const { ctx: c2 } = pageFin({ parole_longue: 'x', silence_parole_longue: -1, silence_parole_courte: 'y' });
  assert.strictEqual(c2.plancherFinDeTour(conv), 2000, 'un réglage abîmé : les valeurs de départ');
  conv.capteur.voixTour = 500;
  assert.strictEqual(c2.plancherFinDeTour(conv), 1000);
});

// ---- le vrai capteur (conversation.js) : sa parole longue avec des blancs de marche, puis sa parole courte ----
async function capteurReel(sansPlancher) {
  let t = 1e6, noeud = null;
  const ctx = { console, Float32Array, ArrayBuffer, DataView, Math, Blob, Date: { now: () => t },
    URL: { createObjectURL: () => 'blob:x', revokeObjectURL() {} },
    navigator: { mediaDevices: { getUserMedia: async () => ({ getTracks: () => [], getAudioTracks: () => [] }) } },
    AudioWorkletNode: class { constructor() { noeud = this; this.port = { postMessage() {}, onmessage: null }; } connect() {} disconnect() {} } };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(CONV, ctx);
  const p = pageFin();
  p.ctx.Date = { now: () => t };
  if (sansPlancher) p.ctx.plancherFinDeTour = () => 0;               // le témoin : le mécanisme coupé
  const conv = {};
  p.ctx.etat.conversation = conv;
  const fins = [];
  const actx = { sampleRate: 16000, destination: {}, audioWorklet: { addModule: async () => {} },
    createMediaStreamSource: () => ({ connect() {}, disconnect() {} }), createGain: () => ({ gain: { value: 1 }, connect() {}, disconnect() {} }) };
  conv.capteur = await ctx.Conversation.demarrer({ ctx: actx, patienceMs: p.ctx.finDeTourConversation, jarvisParle: () => false,
    surDebut: () => p.ctx.debutDeParole(conv, t), surFin: (wav, infos) => { p.ctx.finDeParole(conv, infos); fins.push({ t, infos }); } });
  const fenetre = (voix) => { const f = new Float32Array(320); for (let i = 0; i < f.length; i++) f[i] = voix ? 0.3 * Math.sin(i / 3) : 0.0005; t += 20; noeud.port.onmessage({ data: f }); };
  const voix = (ms) => { for (let i = 0; i < ms / 20; i++) fenetre(true); };
  const blanc = (ms) => { for (let i = 0; i < ms / 20; i++) fenetre(false); };
  blanc(300);
  return { voix, blanc, fins, conv, horloge: () => t, ctx: p.ctx };
}

test('le vrai capteur : sa phrase longue avec des blancs de 1,5 s reste UN tour ; sans le plancher (le témoin), elle partait en trois', async () => {
  const a = await capteurReel(false);
  a.voix(2400); a.blanc(1500); a.voix(1800); a.blanc(1500); a.voix(1200);
  const fin = a.horloge();
  a.blanc(2500);
  assert.strictEqual(a.fins.length, 1, `un seul tour (vu : ${a.fins.length})`);
  const attente = a.fins[0].t - fin;
  assert.ok(attente >= 1900 && attente <= 2200, `fermé 2 s après sa dernière voix (${attente} ms)`);
  const b = await capteurReel(true);
  b.voix(2400); b.blanc(1500); b.voix(1800); b.blanc(1500); b.voix(1200); b.blanc(2500);
  assert.strictEqual(b.fins.length, 3, 'le témoin : sans plancher, chaque blanc de marche fermait son tour');
});

test('le vrai capteur : sa parole courte (« Ça va fiston ? ») se ferme toujours à 1 s, même juste après une parole longue répondue', async () => {
  const a = await capteurReel(false);
  a.voix(800);
  const fin = a.horloge();
  a.blanc(1600);
  assert.strictEqual(a.fins.length, 1);
  const attente = a.fins[0].t - fin;
  assert.ok(attente >= 950 && attente <= 1100, `1 s (${attente} ms)`);
  // une parole longue, à laquelle Hakim répond (un mot dit) ; puis papa repose une petite question : courte à nouveau
  a.voix(2400); a.blanc(2200);
  assert.strictEqual(a.fins.length, 2);
  a.ctx.etat.dernierMotDitA = a.horloge();
  a.blanc(1000);
  a.voix(700);
  const fin2 = a.horloge();
  a.blanc(1600);
  assert.strictEqual(a.fins.length, 3);
  assert.ok(a.fins[2].t - fin2 <= 1100, `sa petite question après sa réponse : 1 s (${a.fins[2].t - fin2} ms)`);
});

test('le capteur dit la voix de son tour en cours (voixTour), 0 hors de son tour', async () => {
  const a = await capteurReel(false);
  assert.strictEqual(a.conv.capteur.voixTour, 0);
  a.voix(1000);
  assert.ok(a.conv.capteur.voixTour >= 800 && a.conv.capteur.voixTour <= 1100, String(a.conv.capteur.voixTour));
  a.blanc(1500);
  assert.strictEqual(a.conv.capteur.voixTour, 0);
});

// ---- la fin anticipée : ni ses mots en direct, ni son brouillon, ni la transcription en avance ne ferment sa parole longue avant 2 s ----
function pageAnticipe({ voixTour = 2500, vif = 'Je vais te dire un truc.', souffle = null } = {}) {
  const p = pageFin();
  const fins = [], transcriptions = [];
  let resoudre = null;
  Object.assign(p.ctx, { SILENCE_ANTICIPE_MS: 500, choisirSouffle: () => souffle, penseePrete: () => null, direPenseeSiPossible: () => false,
    transcriptionEnPause: () => false,
    texteDuTour: () => { transcriptions.push(1); return new Promise((r) => { resoudre = r; }); } });
  vm.runInContext(['const FIN_SUSPENDUE', 'function phraseFinie', 'function anticiperConversation', 'function transcriptionEnAvance']
    .map(d => extraire(PAGE, d)).join('\n'), p.ctx);
  p.ctx.Conversation = { utile: (x) => String(x || '').replace(/[^\p{L}]/gu, '').length >= 2 };
  const capteur = { enParole: true, voixTour, derniereVoix: 5000, assezDeVoix: true, finirTour: (x) => fins.push(x || null) };
  const conv = { capteur, ecrit: { coupe: 0, confirme: '', vif, partiel: null } };
  p.ctx.etat.conversation = conv;
  p.ctx.debutDeParole(conv, 1);
  return { ...p, conv, fins, transcriptions, resoudre: (x) => resoudre(x) };
}

test('fin anticipée : sa parole longue qui « semble finie » à 0,6 s ne se ferme pas ; à 2 s, si ; courte : à 1 s, plus à 0,5 s', () => {
  const longue = pageAnticipe();
  longue.ctx.anticiperConversation(longue.conv, 600);
  assert.strictEqual(longue.fins.length, 0, 'longue : 0,6 s ne ferme pas son tour');
  assert.strictEqual(longue.transcriptions.length, 1, 'mais sa transcription part en avance, comme avant');
  longue.conv.spec = null;                                            // (sa transcription revenue)
  longue.ctx.anticiperConversation(longue.conv, 1500);
  assert.strictEqual(longue.fins.length, 0);
  longue.ctx.anticiperConversation(longue.conv, 2000);
  assert.strictEqual(longue.fins.length, 1, 'à 2 s : fermé');
  assert.strictEqual(longue.journal.find(x => x[0] === 'fin_anticipee')[1].plancher_ms, 2000);
  const courte = pageAnticipe({ voixTour: 900 });
  courte.ctx.anticiperConversation(courte.conv, 500);
  assert.strictEqual(courte.fins.length, 0, 'courte : plus à 0,5 s (14/11, « Gooo ») — le témoin : avant, fermé ici');
  assert.strictEqual(courte.transcriptions.length, 1, 'sa transcription part toujours à 0,5 s');
  courte.conv.spec = null;
  courte.ctx.anticiperConversation(courte.conv, 900);
  assert.strictEqual(courte.fins.length, 0);
  courte.ctx.anticiperConversation(courte.conv, 1000);
  assert.strictEqual(courte.fins.length, 1, 'courte : à 1 s');
  assert.strictEqual(courte.journal.find(x => x[0] === 'fin_anticipee')[1].plancher_ms, 1000);
  const vite = pageAnticipe({ voixTour: 900, souffle: { pret: true, fini: true, rebond: 0.3 } });
  vite.ctx.anticiperConversation(vite.conv, 600);
  assert.strictEqual(vite.fins.length, 0, 'courte, même avec son brouillon prêt et un rebond de 0,3 s : pas avant 1 s');
  const brouillon = pageAnticipe({ souffle: { pret: true, fini: true, rebond: 0.5 } });
  brouillon.ctx.anticiperConversation(brouillon.conv, 700);
  assert.strictEqual(brouillon.fins.length, 0, 'son brouillon prêt ne ferme pas non plus sa parole longue avant 2 s');
});

test('la transcription en avance : revenue « finie » à 0,8 s, elle ne ferme pas sa parole longue ; gardée, le tour fermé plus tard la reprend', async () => {
  const p = pageAnticipe();
  p.ctx.Date = { now: () => 5800 };
  p.ctx.anticiperConversation(p.conv, 600);
  assert.strictEqual(p.transcriptions.length, 1);
  p.resoudre('Je vais te dire un truc.');
  await new Promise(r => setImmediate(r));
  assert.strictEqual(p.fins.length, 0, 'revenue à 0,8 s de silence : son tour reste ouvert');
  const avance = p.ctx.transcriptionEnAvance(p.conv, { derniere_voix: 5000 });
  assert.ok(avance, 'gardée');
  assert.strictEqual(await avance, 'Je vais te dire un truc.');
  assert.strictEqual(p.transcriptions.length, 1, 'pas de deuxième transcription');
  assert.strictEqual(p.ctx.transcriptionEnAvance(p.conv, { derniere_voix: 6000 }), null, 'il a reparlé depuis : plus valable');
  // courte : revenue finie à 0,6 s, elle ne ferme plus son tour avant 1 s (sa patience le fera, avec ce texte gardé) ; revenue après 1 s, si
  const c = pageAnticipe({ voixTour: 900, vif: '' });
  c.ctx.Date = { now: () => 5600 };
  c.ctx.anticiperConversation(c.conv, 600);
  c.resoudre('Ça va fiston ?');
  await new Promise(r => setImmediate(r));
  assert.strictEqual(c.fins.length, 0, 'revenue à 0,6 s : pas encore');
  assert.ok(c.ctx.transcriptionEnAvance(c.conv, { derniere_voix: 5000 }), 'gardée pour sa fin de tour à 1 s');
  const d = pageAnticipe({ voixTour: 900, vif: '' });
  d.ctx.Date = { now: () => 6100 };
  d.ctx.anticiperConversation(d.conv, 600);
  d.resoudre('Ça va fiston ?');
  await new Promise(r => setImmediate(r));
  assert.strictEqual(d.fins.length, 1, 'revenue après 1 s de silence : fermé');
});

test('câblage de la page : le capteur, ses rappels, et rien de lui dans la pause d’une parole longue', () => {
  assert.match(CONV, /get voixTour\(\) \{ return etatV === 'parole' \? voixMs : 0; \},/);
  assert.match(PAGE, /surDebut: \(\) => \{ marquerAvantTon\(conv\);[^\n]*if \(typeof debutDeParole === 'function'\) debutDeParole\(conv\); \},/);
  assert.match(PAGE, /surFin: \(wav, infos, extra\) => \{ if \(typeof finDeParole === 'function'\) finDeParole\(conv, infos\); return tourDeParole\(conv, wav, infos, extra\); \},/);
  const a = extraire(PAGE, 'function anticiperConversation');
  assert.match(a, /const plancher = typeof plancherFinDeTour === 'function' \? plancherFinDeTour\(conv\) : 0, pause = Math\.max\(patienceConversation\(\), plancher\);/);
  assert.match(a, /if \(silenceMs >= pause && typeof direPenseeSiPossible === 'function'\) direPenseeSiPossible\(\);/);
  assert.match(a, /if \(typeof rebondirDernierePensee === 'function' && silenceMs >= plancher\) rebondirDernierePensee\(conv, silenceMs\);/);
  assert.match(a, /if \(silenceMs >= pause && typeof direRibosome === 'function'\) direRibosome\(\);/);
});

// ---- sa réponse lâchée parce que papa continuait sa phrase : propre ----
test('la page : ta phrase qui continue lâche sa réponse sans coupure (suite_papa), et le dit au cockpit', () => {
  const envois = [], coupures = [], fins = [];
  const ctx = { etat: { flux: { abort() {} }, fluxId: '42', transcription: null, lectureDe: 'm1', parleDepuis: 0 }, lecteur: { actif: false, arreter() {} },
    garderNonDit() {}, finirParole: (cause) => fins.push(cause), couperSaVoix() {}, finirSaPhraseActif: () => false, jeton: () => 'j',
    fetch: (url, o) => { envois.push(JSON.parse(o.body)); return Promise.resolve(); } };
  vm.createContext(ctx); vm.runInContext(extraire(PAGE, 'function arreterTout('), ctx);
  ctx.arreterTout(true, { garder: false, raison: 'parole', suite_papa: true });
  assert.deepStrictEqual(envois, [{ tour_id: '42', raison: 'parole', suite_papa: true }], 'raison « parole » (un cockpit d’avant la comprend), et suite_papa');
  assert.deepStrictEqual(fins, ['suite_papa']);
  // finirParole : la cause suite_papa ne part jamais en coupure ; s'il avait déjà dit un mot, c'est une vraie coupure
  const f = { journalVoix: (e, d) => coupures.push(['journal', e, d]), envoyerCoupure: (c) => coupures.push(['coupure', c.cause]),
    etatDeLaCoupure: (cause) => ({ cause, mode: 'oral', dits: f.dits, tour: 'm1' }), memeId: () => true, coupureEnCours: null, parole: { id: 'm1' },
    etat: {}, texteNonDit: () => '', localStorage: { removeItem() {} }, dits: 0 };
  vm.createContext(f); vm.runInContext(extraire(PAGE, 'function finirParole('), f);
  f.finirParole('suite_papa');
  assert.deepStrictEqual(JSON.parse(JSON.stringify(coupures)), [['journal', 'coupure_evitee', { cause: 'suite_papa' }]]);
  coupures.length = 0; f.dits = 3; f.parole.id = 'm1';
  f.finirParole('suite_papa');
  assert.deepStrictEqual(JSON.parse(JSON.stringify(coupures)), [['coupure', 'voix_ahmed']], 'des mots dits : une vraie coupure par sa voix');
  // tourDeParole : la suite se décide AVANT de lâcher l'ancienne réponse (ton message d'avant se complétera)
  const tour = extraire(PAGE, 'async function tourDeParole');
  assert.match(tour, /const suitePapa = etat\.conversation === conv && typeof messageAFusionner === 'function' && !!messageAFusionner\(\);/);
  assert.match(tour, /arreterTout\(true, \{ garder: false, raison: 'parole', suite_papa: suitePapa \}\);/);
  assert.ok(tour.indexOf('const suitePapa') < tour.indexOf("journalVoix('ancienne_reponse_lachee'"));
});

test('le cockpit : « parole » + suite_papa devient suite_papa ; ni arrêt à lui redire, ni « coupé », ni souvenir d’un demi-échange', () => {
  const ctx = { Date, Math, String, Object }; vm.createContext(ctx);
  vm.runInContext(SRC.slice(SRC.indexOf('const RAISONS_ARRET'), SRC.indexOf('/* ---- les tâches de fond de Hakim'))
    + 'this.raison = raisonDuStop; this.noter = noterArret; this.liste = arretsNonDits; this.arret = arretDuTour;', ctx);
  assert.strictEqual(ctx.raison({ raison: 'parole', suite_papa: true }), 'suite_papa');
  assert.strictEqual(ctx.raison({ raison: 'parole' }), 'parole');
  assert.strictEqual(ctx.raison({ raison: 'stop', suite_papa: true }), 'stop', 'seulement avec « parole »');
  assert.strictEqual(ctx.raison({ raison: 'toString' }), 'stop');
  assert.strictEqual(ctx.raison(null), 'stop');
  assert.match(ctx.arret({ coupe: true }, 'suite_papa', ''), /continuait sa phrase/);
  ctx.noter(ctx.arret({ coupe: true }, 'suite_papa', ''), 'Non non, que tu m’appelles sur le smartphone ?', false, 'suite_papa', 'Ah, compris pap');
  assert.strictEqual(ctx.liste.length, 0, 'rien à lui redire : sa phrase entière arrive');
  ctx.noter(ctx.arret({ coupe: true }, 'parole', ''), 'Autre chose', false, 'parole', 'Oui');
  assert.strictEqual(ctx.liste.length, 1, 'une vraie reprise de parole, si');
  assert.match(SRC, /if \(t\) t\.arreter\(raisonDuStop\(q\)\);/);
  assert.match(SRC, /const lachee = !!o\.coupe && raisonArret === 'suite_papa';/);
  assert.match(SRC, /journaliser\('jarvis', saParole \+ \(lachee \? ' \[lâchée : papa continuait sa phrase\]' : o\.coupe \? ` \[coupé : \$\{pourquoi\}\]` : ''\)/);
  assert.match(SRC, /if \(!lachee\) deposerEchange\(\{ ahmed: texte, hakim: saParole/);
});

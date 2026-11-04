// (03/11, 16:00, Ahmed : « fais le test de décalage entre la dernière parole de son subconscient avant que je finisse et le moment où
// il parle, trouve pourquoi, et corrige pour que ça tombe 1 ou 2 s avant que je finisse ») son subconscient en relais (deux brouillons
// en vol, le plus récent gagne), son REBOND senti, la fin d'un long tour reconnue, et la page qui dit le brouillon prêt à ta fin.
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');

// le bloc du serveur, de ressemble() à speculerFreres() : ses brouillons, la prise, la fin d'un long tour
function serveur() {
  const i = SRC.indexOf('function ressemble('), k = SRC.indexOf('function speculerFreres(');
  assert.ok(i > 0 && k > i);
  let T = 10000;                                                      // l'horloge du Mac, au-delà du premier départ
  const appels = [], diffuses = [], minuteurs = [];
  const ctx = {
    Date: { now: () => T }, setTimeout: (f, ms) => { minuteurs.push({ f, ms }); return minuteurs.length; }, Promise, Math, Number, String, Set,
    corpsReglages: () => ({}), chargeMac: () => 0.2, VIVANTS: [], VIVANT_RENOUVELER: 6,
    lireJson: () => ({ silence_normal: 0.7 }), path, JARVIS: '/x', fs: { existsSync: () => false },
    blocInterieur: async () => 'humeur joyeuse', enMatiere: (t) => t, PROCESSUS_VISIBLES: '/x/p',
    derniersEchanges: () => [], bulbe: () => '', instantTexte: () => '', fluxTexte: () => '', personaLocale: () => 'Hakim', lirePersona: () => '',
    neutraliser: (t) => t, enLigne: (t, n) => String(t).slice(0, n), j: JSON.stringify, abonnesPensees: null,
    diffuser: (_, e, d) => diffuses.push([e, JSON.parse(d)]),
    sonnetTeteDeFond: (prompt, etiquette) => new Promise((resoudre) => appels.push({ prompt, etiquette, resoudre })),
  };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.lire = () => souffles; this.souffler = soufflerReponse; this.prendre = prendreSouffle;'
    + ' this.couvreLaFin = couvreLaFin; this.ressemble = ressemble; this.ditParLaPage = souffleDitParLaPage;', ctx);
  return { ctx, appels, diffuses, minuteurs, temps: (t) => { T = t; } };
}
const attendre = () => new Promise(r => setImmediate(r));

test('son subconscient en relais : deux brouillons en vol, 0,8 s entre deux départs, le plus récent gagne', async () => {
  const s = serveur();
  s.ctx.souffler('papa me dit bonjour', 'sub');
  assert.strictEqual(s.appels.length, 1);
  s.temps(10100); s.ctx.souffler('papa me dit bonjour et puis', 'sub');
  assert.strictEqual(s.appels.length, 1, 'moins de 0,8 s après le premier départ : il attend');
  assert.strictEqual(s.minuteurs.length, 1); assert.strictEqual(s.minuteurs[0].ms, 700);
  s.temps(10800); s.minuteurs[0].f();
  assert.strictEqual(s.appels.length, 2, 'le deuxième part sans attendre la fin du premier');
  s.temps(11700); s.ctx.souffler('papa me dit bonjour et puis il raconte sa journée', 'sub');
  assert.strictEqual(s.appels.length, 2, 'deux en vol : le troisième attend une place');
  s.appels[1].resoudre({ texte: 'DIRE : oui\nFINI : non\nREBOND : 0,4\nSalut papa, raconte-moi' });
  await attendre(); await attendre();
  assert.strictEqual(s.ctx.lire().sub.reponse, 'Salut papa, raconte-moi');
  assert.strictEqual(s.ctx.lire().sub.rebond, 0.4);
  assert.deepStrictEqual(s.diffuses.at(-1)[1].rebond, 0.4, 'son rebond part à la page avec le brouillon');
  assert.strictEqual(s.appels.length, 3, 'une place libérée : le texte en attente part');
  s.appels[0].resoudre({ texte: 'DIRE : oui\nFINI : oui\nBonjour papa' });
  await attendre(); await attendre();
  assert.strictEqual(s.ctx.lire().sub.reponse, 'Salut papa, raconte-moi', 'un brouillon plus ancien arrivé après est jeté');
});

test('son REBOND est borné (0,2 à 3 s) ; sans REBOND, rien d’inventé', async () => {
  const s = serveur();
  s.ctx.souffler('un deux trois', 'sub');
  s.appels[0].resoudre({ texte: 'DIRE : oui\nFINI : oui\nREBOND : 9\nOui' });
  await attendre(); await attendre();
  assert.strictEqual(s.ctx.lire().sub.rebond, 3);
  s.temps(11000); s.ctx.souffler('un deux trois quatre', 'sub');
  s.appels[1].resoudre({ texte: 'DIRE : oui\nFINI : oui\nD’accord' });
  await attendre(); await attendre();
  assert.strictEqual(s.ctx.lire().sub.rebond, null);
  assert.match(s.appels[0].prompt, /REBOND : /, 'son subconscient est invité à le sentir');
  assert.match(s.appels[0].prompt, /Ton intérieur en ce moment|d'habitude 0,7 s/);
});

test('un long tour : le brouillon qui a la fin de ses mots est reconnu (ressemble le refusait)', async () => {
  const s = serveur();
  const debut = Array.from({ length: 80 }, (_, i) => `mot${i}`).join(' ');
  const fin = 'alors je voulais te demander comment tu te sens aujourd’hui avec tout ce qu’on a construit ensemble depuis ce matin';
  const final = `${debut} ${fin}`, pour = `${Array.from({ length: 10 }, (_, i) => `mot${70 + i}`).join(' ')} ${fin}`;
  assert.strictEqual(s.ctx.ressemble(pour, final), false);
  assert.strictEqual(s.ctx.couvreLaFin(pour, final), true);
  assert.strictEqual(s.ctx.couvreLaFin('rien à voir', final), false);
  s.ctx.souffler(pour, 'sub');
  s.appels[0].resoudre({ texte: 'DIRE : oui\nFINI : oui\nJe me sens bien, papa' });
  await attendre(); await attendre();
  assert.strictEqual((await s.ctx.prendre(final)).reponse, '', '(16:30) son subconscient ne parle plus : « coupe le glisse-mot »');
  Object.assign(s.ctx.lire().cer, { reponse: 'Bien, papa, très bien', pret: true, pour, t: 10000 });
  const r = await s.ctx.prendre(final);
  assert.strictEqual(r.reponse, 'Bien, papa, très bien', 'la pensée de son cerveau, écrite pour la fin de ses mots');
  assert.strictEqual(r.niveau, 'cerveau');
});

test('la page l’a déjà dit : plus rien à prendre pour ce tour', async () => {
  const s = serveur();
  Object.assign(s.ctx.lire().cer, { reponse: 'Oui papa', pret: true, pour: 'un deux trois', t: 10000 });
  s.ctx.ditParLaPage();
  assert.strictEqual((await s.ctx.prendre('un deux trois')).reponse, '');
});

// la page : à ta fin, son rebond règle le silence, et le brouillon prêt part aussitôt (sans aller-retour au Mac)
function extraire(debut) {
  const i = PAGE.indexOf(debut);
  assert.ok(i >= 0, debut);
  if (debut.startsWith('const ')) return PAGE.slice(i, PAGE.indexOf('\n', i) + 1);
  return PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 3);
}
function page() {
  const dits = [], journal = [];
  const ctx = { Date, Math, Number, String, Set, journalVoix: (e, d) => journal.push([e, d]), rythmeVoix: (k, d) => d,
    souffleAutorise: () => true, lecteurNeuronal: { parle: false }, voixPrete: () => ({}),
    direSouffle: (conv, s, par) => { s.dite = true; dits.push([s.texte, par, conv.souffleLocal]); } };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'public', 'conversation.js'), 'utf8'), ctx);   // le vrai filtre (phraseFinie)
  vm.runInContext(['const SILENCE_ANTICIPE_MS', 'const FIN_SUSPENDUE', 'function phraseFinie', 'function recouvre', 'function choisirSouffle',
    'function penseePrete', 'function direPenseeSiPossible', 'function anticiperConversation'].map(extraire).join('\n')
    + '\nthis.anticiper = anticiperConversation; this.direPensee = direPenseeSiPossible;', ctx);
  return { ctx, dits, journal };
}
test('page : son rebond (1,5 s) règle le silence ; à ta fin, la pensée prête de son cerveau est dite tout de suite', () => {
  const p = page();
  const fins = [];
  const conv = { capteur: { finirTour: () => fins.push(1), derniereVoix: 1, assezDeVoix: false }, ecrit: { confirme: 'papa dit bonjour à son fils', vif: '' } };
  p.ctx.etat = { reglages: {}, conversation: conv,
    souffles: { sub: { texte: 'Bonjour papa', pret: true, fini: true, rebond: 1.5, pour: 'papa dit bonjour à son fils', t: Date.now(), niveau: 'sub' } },
    pensee: { texte: 'Bonjour mon papa, ça va ?', pret: true, fini: null, rebond: null, pour: 'papa dit bonjour à son fils', t: Date.now(), niveau: 'cerveau' } };
  p.ctx.anticiper(conv, 800);
  assert.strictEqual(fins.length, 0, 'son rebond de 1,5 s : pas encore');
  p.ctx.anticiper(conv, 1600);
  assert.strictEqual(fins.length, 1);
  assert.deepStrictEqual(p.dits, [['Bonjour mon papa, ça va ?', 'pensee', true]], 'sa pensée, dite par la page, marquée pour que la prise du Mac ne la redise pas');
  assert.strictEqual(p.journal.find(x => x[0] === 'fin_anticipee')[1].rebond_ms, 1500);
});
test('page : (16:30) son subconscient seul finit ton tour, mais ne parle pas (« coupe le glisse-mot »)', () => {
  const p = page();
  const fins = [];
  const conv = { capteur: { finirTour: () => fins.push(1), derniereVoix: 1, assezDeVoix: false }, ecrit: { confirme: 'papa dit bonjour à son fils', vif: '' } };
  p.ctx.etat = { reglages: {}, conversation: conv,
    souffles: { sub: { texte: 'Bonjour papa', pret: true, fini: true, rebond: 0.6, pour: 'papa dit bonjour à son fils', t: Date.now(), niveau: 'sub' } } };
  p.ctx.anticiper(conv, 700);
  assert.strictEqual(fins.length, 1);
  assert.deepStrictEqual(p.dits, []);
});
test('page : un brouillon écrit pour d’autres mots, ou pas prêt, n’est pas dit', () => {
  const p = page();
  const conv = { capteur: { finirTour() {}, derniereVoix: 1, assezDeVoix: false }, ecrit: { confirme: 'tout autre chose maintenant vraiment', vif: '' } };
  p.ctx.etat = { reglages: {}, conversation: conv,
    souffles: { sub: { texte: 'Bonjour papa', pret: true, fini: true, rebond: 0.5, pour: 'papa dit bonjour à son fils', t: Date.now(), niveau: 'sub' } } };
  p.ctx.anticiper(conv, 900);
  assert.deepStrictEqual(p.dits, []);
  conv.ecrit.confirme = 'papa dit bonjour à son fils'; conv.finAnticipee = false;
  p.ctx.etat.souffles.sub.pret = false; p.ctx.etat.souffles.sub.fini = false;
  p.ctx.anticiper(conv, 900);
  assert.deepStrictEqual(p.dits, []);
});

test('(16:30) une voix fabriquée d’avance (fond) passe après tout ce qu’il dit vraiment ; la page la demande ainsi', () => {
  assert.match(SRC, /if \(q && q\.fond === true\) tache\.fond = true;/);
  assert.match(SRC, /else \{ const k = fileVoix\.findIndex\(x => x\.fond\); if \(k >= 0\) fileVoix\.splice\(k, 0, tache\); else fileVoix\.push\(tache\); \}/);
  assert.match(PAGE, /body: JSON\.stringify\(\{ texte, langue: 'fr', fond: true,/);
  assert.match(PAGE, /if \(niveau !== 'cerveau'\) return;[^]{0,900}preparerVoixSouffle\(texte, niveau, \(\) => direPenseeSiPossible\(\)\);/,
    'seule la pensée de son cerveau a sa voix d’avance, et se dit dès qu’elle est faite');
});

test('page : (16:40) sa pensée se dit dès qu’elle est prête, jamais pendant ton tour, jamais pendant sa réponse, une seule fois', () => {
  const p = page();
  const conv = { capteur: { enParole: true } };
  p.ctx.etat = { conversation: conv, pensee: { texte: 'Je suis là, papa', pret: true, t: Date.now(), niveau: 'cerveau' } };
  assert.strictEqual(p.ctx.direPensee(), false, 'ton tour est ouvert : elle attend ta fin');
  conv.capteur.enParole = false; p.ctx.etat.flux = {};
  assert.strictEqual(p.ctx.direPensee(), false, 'sa vraie réponse s’écrit : elle ne passe plus');
  p.ctx.etat.flux = null;
  assert.strictEqual(p.ctx.direPensee(), true);
  assert.strictEqual(p.ctx.direPensee(), false, 'déjà dite');
  p.ctx.etat.pensee = { texte: 'Je t’écoute, finis ta phrase', pret: false, t: Date.now(), niveau: 'cerveau' };
  assert.strictEqual(p.ctx.direPensee(), false, 'celle qui attend la suite s’écrit seulement');
  assert.deepStrictEqual(p.dits.map(d => d[0]), ['Je suis là, papa']);
});

// (16:45, Ahmed : « que Chatterbox écrive la voix directement à partir de l'input qui donne naissance à l'écriture, puis relie la parole
// à l'écriture dans un second temps ») la voix de sa pensée naît au cockpit avec elle, une seule fois ; la page la reçoit ensuite
test('(16:45) la voix de sa pensée naît avec elle, au cockpit, une seule fois ; la page reçoit celle-là', async () => {
  const i = SRC.indexOf('const voixALaSource = new Map();'), k = SRC.indexOf('async function routeDire(');
  assert.ok(i > 0 && k > i);
  const taches = [];
  const ctx = { Map, Date, Math, Number, String, Promise, Buffer, console, process: { pid: 1 },
    prononcer: (t) => String(t).replace(/😊/g, '').replace(/[ \t]{2,}/g, ' ').trim(),
    etatInterieur: async () => ({ ts: Date.now() / 1000, voix: { expressivite: 0.5, vitesse: 1.05 } }), FRAICHEUR_S: 300,
    VoixPage: { expressivitePhrase: (b) => b }, fileVoix: taches, pomperVoix() {}, path, os: { tmpdir: () => '/tmp' },
    crypto: { randomBytes: () => ({ toString: () => 'abcd' }) }, j: JSON.stringify, JARVIS_VOIX_DIAGNOSTIC: '/dev/null',
    fs: { readFileSync: () => Buffer.from('RIFF'), unlink() {}, appendFileSync() {} } };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.naitre = voixDeLaSource; this.cache = voixALaSource;', ctx);
  const p1 = ctx.naitre('Bonjour  papa 😊');
  assert.ok(p1, 'la synthèse part tout de suite');
  assert.strictEqual(ctx.naitre('Bonjour papa'), null, 'déjà en train de naître : pas deux fois');
  await new Promise(r => setImmediate(r));
  assert.strictEqual(taches.length, 1);
  assert.strictEqual(taches[0].fond, true, 'elle passe après ce qu’il dit vraiment');
  assert.strictEqual(taches[0].tempo, 1.05);
  taches[0].fin({ duree_s: 1.2 });
  const v = await p1;
  assert.strictEqual(String(v.data), 'RIFF');
  assert.ok(ctx.cache.has('Bonjour papa'));
  assert.match(SRC, /const source = voixALaSource\.get\(texte\.replace\(\/\\s\+\/g, ' '\)\.trim\(\)\);/, 'la page la reçoit au lieu d’une deuxième synthèse');
  assert.match(SRC, /voixDeLaSource\(s0\.reponse\.slice\(0, 400\)\);/, 'au moment même où son cerveau écrit sa pensée');
});

// (16:45, Ahmed : « que la réflexion soit inexistante par défaut, remplacée par la pensée qui sort au même moment du haut-parleur et en
// message sur l'interface ») en Conversation, sa réponse s'écrit au rythme de sa voix
test('(16:45) sa réponse s’écrit au rythme de sa voix : rien avant son premier son, puis ce qu’elle a dit, puis tout', () => {
  const ctx = { Voix: require('./public/voix.js'), Math, String };
  vm.createContext(ctx);
  vm.runInContext(extraire('function texteAuRythme') + '\nthis.vu = texteAuRythme;', ctx);
  const texte = 'Bonjour papa, je suis là. Tu vas bien ce soir ?';
  assert.strictEqual(ctx.vu({ texte, ditCar: 0 }), '', 'pas encore dit : rien');
  const dit = ctx.Voix.prononcable('Bonjour papa, je suis là.').map(x => x.texte).join(' ').length + 1;
  const vu = ctx.vu({ texte, ditCar: dit });
  assert.ok(vu.startsWith('Bonjour papa, je suis là'), vu);
  assert.ok(!/bien/.test(vu), 'la suite attend sa voix');
  assert.strictEqual(ctx.vu({ texte, ditCar: 9999 }), texte);
  assert.match(PAGE, /if \(!vu\) return `<div class="m j" data-id="\$\{esc\(m\.id\)\}" hidden><\/div>`;/, 'ni « réfléchit… » ni texte avant sa voix');
  assert.match(PAGE, /if \(mR && mR\.auRythme\) \{ mR\.ditCar = \(mR\.ditCar \|\| 0\) \+ String\(t \|\| ''\)\.length \+ 1; majMessage\(mR\); \}/, 'chaque bout qui part dévoile la suite');
  assert.match(PAGE, /for \(const x of etat\.messages\.slice\(-6\)\) if \(x\.auRythme && !x\.enCours\) x\.auRythme = false;/, 'sa voix a fini : tout s’écrit');
  assert.match(PAGE, /pense \? \(etat\.conversation \? '' : 'réfléchit…'\)/, 'plus de « réfléchit… » dans la ligne d’état en Conversation');
});

// (17:10, audit d'Ahmed : « ça ne fonctionne pas ») ce que l'audit a trouvé sur le chemin de sa voix
test('(17:10) une nouvelle pensée annule la voix d’une plus ancienne qui n’a pas encore commencé', async () => {
  const i = SRC.indexOf('const voixALaSource = new Map();'), k = SRC.indexOf('async function routeDire(');
  const taches = [];
  const ctx = { Map, Date, Math, Number, String, Promise, Buffer, console, process: { pid: 1 },
    prononcer: (t) => String(t), etatInterieur: async () => ({}), FRAICHEUR_S: 300, VoixPage: { expressivitePhrase: (b) => b },
    fileVoix: taches, pomperVoix() {}, path, os: { tmpdir: () => '/tmp' }, crypto: { randomBytes: () => ({ toString: () => 'ab' }) },
    j: JSON.stringify, JARVIS_VOIX_DIAGNOSTIC: '/dev/null', fs: { readFileSync: () => Buffer.from('RIFF'), unlink() {}, appendFileSync() {} } };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.naitre = voixDeLaSource;', ctx);
  ctx.naitre('Première pensée, longue');
  await new Promise(r => setImmediate(r));
  ctx.naitre('Deuxième pensée');
  await new Promise(r => setImmediate(r));
  assert.strictEqual(taches.length, 2);
  assert.strictEqual(taches[0].annulee, true, 'la plus ancienne, pas commencée : annulée');
  assert.strictEqual(taches[1].annulee, false);
  assert.match(SRC, /if \(pret\) voixDeLaSource\(s0\.reponse\.slice\(0, 400\)\);/, 'seule la pensée à dire naît avec sa voix');
  assert.match(SRC, /for \(const x of fileVoix\) if \(x\.fond\) x\.annulee = true;/, 'sa vraie réponse annule ce qui attend en fond');
  assert.match(PAGE, /if \(s\.pret\) preparerVoixSouffle\(texte, niveau, \(\) => direPenseeSiPossible\(\)\);/);
});

test('(17:10) ses trois frères commencent pendant que papa parle si leurs voix vivantes sont libres ; un long tour est repris', () => {
  const i = SRC.indexOf('const voixFreresLibres'), k = SRC.indexOf('\n}\n', SRC.indexOf('function speculerFreres(')) + 3;
  let lances = 0;
  const vivant = (m) => ({ modele: m, attente: null, proc: { exitCode: null }, n: 0 });
  const ctx = { Date, String, VIVANT_RENOUVELER: 6, VIVANTS: [], corpsReglages: () => ({ trois_freres: true }), chargeMac: () => 1.8,
    speculation: { texte: '', debut: 0, promesse: null, fini: false }, ressemble: () => false, bulbe: () => '', instantTexte: () => '',
    fluxTexte: () => '', troisFreres: () => { lances++; return Promise.resolve('ok'); } };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.speculer = speculerFreres;', ctx);
  ctx.speculer('papa me raconte toute sa journée au travail');
  assert.strictEqual(lances, 0, 'Mac chargé, pas de voix libres : comme avant, elles attendent');
  ctx.VIVANTS.push(vivant('haiku'), vivant('sonnet'), vivant('opus'));
  ctx.speculer('papa me raconte toute sa journée au travail');
  assert.strictEqual(lances, 1, 'Mac chargé mais ses trois voix vivantes libres : elles commencent');
  assert.match(SRC, /const reprise = !!\(spec\.promesse && Date\.now\(\) - spec\.debut < 60000 && \(ressemble\(spec\.texte, texte\) \|\| couvreLaFin\(spec\.texte, texte\)\)\);/);
});

// (04/11, choix d'Ahmed après l'audit : « un seul, à ta pause » ; « attendre 2 s au plus »)
test('(04/11) son cerveau est réveillé une seule fois par tour, à la pause où son subconscient sent que tu as fini', () => {
  const i = SRC.indexOf('let morceauxCerveau'), k = SRC.indexOf('\n}\n', SRC.indexOf('function reveilMorceau(')) + 3;
  const ecrits = [];
  const ctx = { Date, Intl, String, console: { error() {} }, corpsReglages: () => ({}), hakimDort: () => false, cerveauVivant: () => true,
    occupe: () => false, cerveau: { enCours: null, enfant: { stdin: { write: (x) => ecrits.push(x) } } }, NONCE_REVEIL: 'n', MORCEAU_MARQUE: 'm',
    neutraliser: (t) => t, j: JSON.stringify, souffles: { sub: { fini: null } } };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.reveil = reveilMorceau; this.etat = () => morceauxCerveau;', ctx);
  assert.strictEqual(ctx.reveil('papa me raconte sa journée au travail').raison, 'il continue', 'son subconscient sent qu’il continue');
  ctx.souffles.sub.fini = true;
  assert.strictEqual(ctx.reveil('papa me raconte sa journée au travail, voilà').ok, true);
  assert.strictEqual(ctx.reveil('papa me raconte sa journée au travail, voilà, et puis').raison, 'déjà réveillé pour ce tour');
  assert.strictEqual(ecrits.length, 1);
  assert.match(SRC, /morceauxCerveau\.duTour = false;/, 'sa phrase entière arrivée : le tour suivant aura son réveil');
  assert.match(SRC, /const FRERES_ATTENTE_MS = 2000;/);
  assert.match(SRC, /new Promise\(r => setTimeout\(\(\) => r\(''\), FRERES_ATTENTE_MS\)\)\]\)\.catch\(\(\) => ''\)\) : '';/, 'ses frères : 2 s au plus après ta phrase');
});

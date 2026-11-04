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
  assert.strictEqual(fins.length, 0, 'son rebond de 1,5 s : ton tour n’est pas encore fini');
  assert.deepStrictEqual(p.dits.map(d => [d[0], d[1]]), [['Bonjour mon papa, ça va ?', 'pensee']], '(04/11) sa pensée prête se dit dès ta pause');
  p.ctx.anticiper(conv, 1600);
  assert.strictEqual(fins.length, 1);
  assert.strictEqual(p.dits.length, 1, 'une seule fois');
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
  assert.match(PAGE, /if \(niveau !== 'cerveau'\) return;[^]{0,1100}preparerVoixSouffle\(texte, niveau, \(\) => direPenseeSiPossible\(\)\);/,
    'seule la pensée de son cerveau a sa voix d’avance, et se dit dès qu’elle est faite');
});

test('page : (04/11) sa pensée se dit dès qu’elle est prête, dans ta pause (jamais pendant que tu parles), jamais pendant sa réponse, une seule fois', () => {
  const p = page();
  const conv = { capteur: { enParole: true, derniereVoix: Date.now() } };
  p.ctx.etat = { conversation: conv, pensee: { texte: 'Je suis là, papa', pret: true, t: Date.now(), niveau: 'cerveau' } };
  assert.strictEqual(p.ctx.direPensee(), false, 'tu parles à cet instant : elle attend ta pause');
  conv.capteur.derniereVoix = Date.now() - 400; p.ctx.etat.flux = {};
  assert.strictEqual(p.ctx.direPensee(), false, 'sa vraie réponse s’écrit : elle ne passe plus');
  p.ctx.etat.flux = null;
  assert.strictEqual(p.ctx.direPensee(), true, 'ta pause, ton tour encore ouvert : elle se dit');
  assert.strictEqual(conv.penseeEnPause, true, 'ton tour ouvert ne bloque pas sa voix');
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
  assert.match(PAGE, /if \(!vu && !\(m\.outils \|\| \[\]\)\.length\) return `<div class="m j" data-id="\$\{esc\(m\.id\)\}" hidden><\/div>`;/, 'ni « réfléchit… » ni texte avant sa voix');
  assert.match(PAGE, /m = \{ \.\.\.m, texte: vu \};/, '(04/11) ses badges d’outils restent, à chaque bout');
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
test('(04/11) son cerveau est réveillé une seule fois par tour, à ta première pause', () => {
  const i = SRC.indexOf('let morceauxCerveau'), k = SRC.indexOf('\n}\n', SRC.indexOf('function reveilMorceau(')) + 3;
  const ecrits = [];
  const ctx = { Date, Intl, String, console: { error() {} }, corpsReglages: () => ({}), hakimDort: () => false, cerveauVivant: () => true, envieDeCouper: () => 0.4,
    occupe: () => false, cerveau: { enCours: null, enfant: { stdin: { write: (x) => ecrits.push(x) } } }, NONCE_REVEIL: 'n', MORCEAU_MARQUE: 'm',
    neutraliser: (t) => t, j: JSON.stringify, souffles: { sub: { fini: null } } };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.reveil = reveilMorceau; this.etat = () => morceauxCerveau;', ctx);
  assert.strictEqual(ctx.reveil('papa me raconte sa journée au travail, voilà').ok, true, '(04/11) au premier morceau, sans attendre le deuxième');
  assert.match(ecrits[0], /UNE phrase courte/, 'une pensée courte : sa voix part vite');
  assert.strictEqual(ctx.reveil('papa me raconte sa journée au travail, voilà, et puis').raison, 'déjà réveillé pour ce tour');
  assert.strictEqual(ecrits.length, 1);
  assert.match(SRC, /morceauxCerveau\.duTour = false;/, 'sa phrase entière arrivée : le tour suivant aura son réveil');
  assert.match(SRC, /const FRERES_ATTENTE_MS = 2000;/);
  assert.match(SRC, /new Promise\(r => setTimeout\(\(\) => r\(''\), FRERES_ATTENTE_MS\)\)\]\)\.catch\(\(\) => ''\)\) : '';/, 'ses frères : 2 s au plus après ta phrase');
});

test('(04/11) sa pensée dite dans ta pause : ton tour ne bloque pas sa voix, et ton message la porte comme déjà dite', () => {
  const ctx = { etat: { conversation: { capteur: { enParole: true }, enAttente: 0, penseeEnPause: false } } };
  vm.createContext(ctx);
  vm.runInContext(extraire('function jarvisPeutParler') + '\nthis.peut = jarvisPeutParler;', ctx);
  assert.strictEqual(ctx.peut(), false, 'ton tour ouvert : il attend');
  ctx.etat.conversation.penseeEnPause = true;
  assert.strictEqual(ctx.peut(), true, 'sa pensée dans ta pause : elle passe');
  assert.match(PAGE, /etat\.conversation\.souffleDit \|\| etat\.conversation\.penseeDite/, 'ton message la porte (souffle_dit)');
  assert.match(PAGE, /if \(etat\.conversation\) etat\.conversation\.penseeEnPause = false;/, 'sa voix finie : ton tour reprend la main');
});

// (04/11, Ahmed : « il doit pouvoir me couper la parole au moment du premier chunk aussi, selon son choix »)
test('(04/11) son choix de te couper : COUPER : oui, sa pensée part même pendant que tu parles ; non, elle attend ta pause', () => {
  const i = SRC.indexOf('function brouillonDuCerveau('), k = SRC.indexOf('\n}\n', i) + 3;
  const diffuses = [];
  const ctx = { String, Date, console: { error() {} }, sansBaliseAffect: (t) => t, NON_REPONSE_SERVEUR: /^No response requested/,
    souffles: { cer: {} }, morceauxCerveau: { dernier: 'papa parle' }, voixDeLaSource() {}, abonnesPensees: null,
    diffuser: (_, e, d) => diffuses.push(JSON.parse(d)), j: JSON.stringify };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.brouillon = brouillonDuCerveau;', ctx);
  ctx.brouillon('FINI : non\nCOUPER : oui\nAttends papa, c’est exactement ça !');
  assert.strictEqual(diffuses[0].couper, true);
  assert.strictEqual(diffuses[0].texte, 'Attends papa, c’est exactement ça !', 'la ligne COUPER ne s’écrit ni ne se dit');
  ctx.brouillon('FINI : non\nCOUPER : non\nJe t’écoute.');
  assert.strictEqual(diffuses[1].couper, false);
  const p = page();
  const conv = { capteur: { enParole: true, derniereVoix: Date.now() } };
  p.ctx.etat = { conversation: conv, pensee: { texte: 'Attends papa !', pret: true, couper: false, t: Date.now(), niveau: 'cerveau' } };
  assert.strictEqual(p.ctx.direPensee(), false, 'il attend ta pause');
  p.ctx.etat.pensee.couper = true;
  assert.strictEqual(p.ctx.direPensee(), true, 'son choix : il te coupe');
});

// (04/11, Ahmed : « enlève tous les blancs, même entre les mots qu'il dit » ; « c'est ça qui le ralentit »)
test('(04/11) le silence autour de chaque bout de sa voix est rogné ; ses meubles automatiques éteints par défaut', () => {
  const faireTampon = (donnees, sr = 1000) => ({ numberOfChannels: 1, sampleRate: sr, length: donnees.length, duration: donnees.length / sr,
    getChannelData: () => donnees, copyToChannel(src) { this.copie = Array.from(src); } });
  const ctx = { Math, actx: { createBuffer: (c, n, sr) => ({ ...faireTampon(new Float32Array(n), sr), numberOfChannels: c }) } };
  vm.createContext(ctx);
  vm.runInContext(extraire('function rognerSilences') + '\nthis.rogner = rognerSilences;', ctx);
  const d = new Float32Array(1000);                               // 1 s à 1 000 Hz : 300 ms de silence, 400 ms de voix, 300 ms de silence
  for (let i = 300; i < 700; i++) d[i] = 0.2;
  const r = ctx.rogner(faireTampon(d));
  assert.strictEqual(r.length, 400 + 2 * 15, 'sa voix, plus 15 ms de marge de chaque côté');
  const tout = new Float32Array(1000).fill(0.2);
  const t = faireTampon(tout);
  assert.strictEqual(ctx.rogner(t), t, 'rien à rogner : le même');
  assert.match(PAGE, /x\.pret = L\.rogner\(x\.pret\);/, 'chaque bout de sa voix passe par là');
  assert.match(PAGE, /lecteurNeuronal\.peutHesiter = \(\) => typeof reglagesCorps !== 'undefined' && reglagesCorps\.meubles_auto === true/,
    'ses meubles automatiques seulement si SENS les allume');
});

// (04/11, Ahmed : « parallélise encore plus ses processus, sur tous les CPU et le GPU, sans trop surcharger »)
test('(04/11) son oreille et sa voix ont chacune leur processus : elles ne s’attendent plus', () => {
  const i = SRC.indexOf('const voieVoix');
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, SRC.indexOf('\n', i) + 1) + '\nthis.voie = voieVoix;', ctx);
  assert.strictEqual(ctx.voie({ op: 'dire' }), 'parole');
  assert.strictEqual(ctx.voie({ op: 'transcrire' }), 'ecoute');
  assert.match(SRC, /env: \{ \.\.\.process\.env, PATH: CHEMIN_OUTILS, JARVIS_VOIX_ROLE: voie \}/, 'chaque processus sait son rôle');
  const pomper = SRC.slice(SRC.indexOf('async function pomperVoix('), SRC.indexOf('\n}\n', SRC.indexOf('async function pomperVoix(')));
  assert.doesNotMatch(pomper, /transcriptionsEnAttente > 0\) return/, 'sa voix n’attend plus les transcriptions');
});

// (04/11, Ahmed : « coupe par chunk de mot, le premier mot incluant le déterminant : il prévoit le reste et parle direct ; 8 chunks =
// 8 mots = 8 réponses, le GPU les dit une par une, au fur et à mesure » ; « ses trois voix ensemble » ; « oui, sans garde-fous »)
function pistesSandbox(places = { haiku: 12, sonnet: 3, opus: 3 }) {
  const i = SRC.indexOf('const PISTES_MAX'), k = SRC.indexOf('function speculerFreres(');
  const appels = [], diffuses = [], voix = [];
  const ctx = { String, Math, Date, Promise, RegExp, Object, VIVANTS: [], VIVANTS_MAX: places, VIVANT_RENOUVELER: 6, cerveau: { modele: 'haiku' },
    corpsReglages: () => ({}), personaLocale: (p) => p, lirePersona: () => 'Hakim', neutraliser: (t) => t, j: JSON.stringify, abonnesPensees: null,
    voixDeLaSource: (t, o) => voix.push([t, o]), diffuser: (_, e, d) => diffuses.push(JSON.parse(d)),
    sonnetTeteDeFond: (prompt, etiquette, modele) => new Promise((resoudre) => {
      const v = { modele, attente: {}, proc: { exitCode: null }, n: 1 };                  // sa voix vivante, occupée le temps de répondre
      ctx.VIVANTS.push(v);
      appels.push({ prompt, etiquette, modele, resoudre: (o) => { v.attente = null; resoudre(o); } });
    }) };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.morceau = pisteMorceau; this.etat = () => pistes; this.decouper = morceauxDeMots;', ctx);
  return { ctx, appels, diffuses, voix };
}
test('(04/11) un morceau par mot, avec ses petits mots d’avant ; un petit mot en fin attend le mot qui le suit', () => {
  const { ctx } = pistesSandbox();
  assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.decouper('papa me dit bonjour ce matin à la'.split(' ')))),
    { morceaux: ['papa', 'me dit', 'bonjour', 'ce matin'], reste: 2 });
});
test('(04/11) ses pistes mot par mot : une seule voix, celle qui tient son conscient, 8 à la fois ; chaque bout continue les précédents', async () => {
  const { ctx, appels, diffuses, voix } = pistesSandbox();
  ctx.morceau('papa me dit bonjour ce matin et puis il raconte sa journée au travail encore');
  assert.ok(appels.every(a => a.modele === 'haiku'), '(04/11) seul celui qui tient son conscient (ici Mini Hakim) parle');
  assert.strictEqual(appels.length, 8, '8 mots à la fois');
  assert.match(appels[0].prompt, /Son mot 1, qu'il vient de dire : « papa »/);
  assert.match(appels[0].prompt, /PREDIT :/, 'il devine la suite de ta phrase');
  ctx.morceau('papa me dit bonjour ce matin et puis il raconte sa journée au travail encore demain');
  assert.strictEqual(ctx.etat().attente.map(x => x.texte).join('|'), 'encore|demain', '(04/11) chaque mot garde sa piste : le 9e, le 10e attendent, chacun la sienne');
  appels[0].resoudre({ texte: 'PREDIT : me dit bonjour\nCOMPRENDS : il m’appelle\nOui papa,' });
  await new Promise(r => setImmediate(r)); await new Promise(r => setImmediate(r));
  assert.deepStrictEqual(diffuses.map(d => [d.n, d.texte]), [[1, 'Oui papa,']]);
  assert.strictEqual(JSON.stringify(voix), JSON.stringify([['Oui papa,', { garder: true }]]), 'sa voix naît avec le bout, sans annuler les bouts d’avant');
  const deuxieme = appels.find(a => /Son mot 2/.test(a.prompt));
  assert.ok(deuxieme, 'le mot 2 a sa piste');
  assert.match(SRC, /Ce que tu as déjà commencé à lui répondre \(dit ou en train de l'être\)/, 'chaque bout continue les précédents');
  assert.match(SRC, /pisteMorceau\(String\(q\.texte \|\| ''\)\.slice\(-3000\)\);/, 'tes mots en direct partent à ses pistes');
});

test('(04/11) la page envoie tes mots en direct à ses pistes dès un mot neuf, et dit leurs bouts l’un après l’autre', () => {
  assert.match(PAGE, /if \(neufs >= 1\) \{/);
  assert.match(PAGE, /if \(niveau === 'piste'\) \{ recevoirBout\(s, Number\(o\.n\) \|\| 0, o\.tour\); return; \}/);
  assert.match(PAGE, /lecteurNeuronal\.direAudio\(b\.texte, b\.buf\);/, 'dans l’ordre des mots, à la suite');
});

test('(04/11) rien n’est gardé de ce qui est prononcé : sa voix servie s’efface aussitôt', () => {
  assert.match(SRC, /voixALaSource\.delete\(texte\.replace\(\/\\s\+\/g, ' '\)\.trim\(\)\);/, 'la voix d’une pensée, servie une fois, effacée');
  const dire = SRC.slice(SRC.indexOf('async function routeDire('), SRC.indexOf('\n}\n', SRC.indexOf('async function routeDire(')));
  assert.doesNotMatch(dire, /garderVoixRecente\(tache/, 'plus gardée pour la réécoute');
  assert.match(dire, /fs\.unlink\(tache\.fichier, \(\) => \{\}\);\n    if \(res\.writableEnded\) return;/);
});

// (04/11, Ahmed : « il prononce son premier chunk direct dès qu'il le reçoit » ; « input → pensée = input → vibration = input → parole » ;
// Hakim : « une de mes pistes s'est prise pour Claude Code »)
test('(04/11) chaque bout part dès que sa voix est prête ; sa vibration sur le même input ; une piste ne se prend pas pour Claude Code', () => {
  const dits = [];
  const ctx = { etat: { conversation: {} }, lecteurNeuronal: { direAudio: (t) => dits.push(t) } };
  vm.createContext(ctx);
  vm.runInContext('let bouts = { tour: 1, prochain: 1, liste: new Map(), enFile: [], dits: [] };\n' + extraire('function direBouts') + '\nthis.dire = direBouts; this.b = () => bouts;', ctx);
  ctx.b().liste.set(2, { n: 2, texte: 'deux', buf: {}, t: 0 });
  ctx.dire();
  assert.deepStrictEqual(dits, ['deux'], 'le bout 2 arrivé d’abord part tout de suite, sans attendre le 1');
  ctx.b().liste.set(1, { n: 1, texte: 'un', buf: {}, t: 0 });
  ctx.b().liste.set(3, { n: 3, texte: 'trois', buf: {}, t: 0 });
  ctx.dire();
  assert.deepStrictEqual(dits, ['deux', 'trois'], 'un bout plus ancien que le dernier dit est sauté');
  assert.match(SRC, /if \(typeof rireEnDirect === 'function'\) rireEnDirect\(morceaux\.join\(' '\)\);/, 'sa vibration sur tes mots en direct');
  assert.match(SRC, /Tu es Hakim, le fils d'Ahmed \(papa\) : ni Claude, ni Claude Code, ni un assistant\./);
  assert.match(SRC, /const pasLui = /);
});

// (04/11, Ahmed : « quand je clique sur Stop juste après avoir parlé, il répond direct ; sinon il galère ; arrange ça »)
test('(04/11) en Conversation, ta phrase finie fait ce que faisait ton Stop ; ses bouts ne gardent plus ta phrase en attente', () => {
  const i = PAGE.indexOf('async function tourDeParole('), bloc = PAGE.slice(i, PAGE.indexOf('\n}\n', i));
  assert.match(bloc, /if \(enTelepathie\(\)\) \{ garderPourSonTour\(conv, texte\); return; \}\n    journalVoix\('stop_par_ta_phrase'/);
  assert.match(bloc, /arreterTout\(true, \{ garder: true, raison: 'parole' \}\); majBoutonsPause\(\);/, 'ce qu’il n’a pas dit est gardé pour plus tard');
  assert.match(PAGE, /lecteurNeuronal\.retirerAudio\(bouts\.enFile\.slice\(\)\)/, 'ses bouts pas encore dits s’effacent quand ta phrase part');
});

// (04/11, Ahmed : « enlève le résultat et toutes les paroles de lui-même, ça alourdit le process ; seule la pensée persiste ; même le
// glisser un mot »)
test('(04/11) en conversation, il ne se réveille plus de lui-même pour parler ; seule sa pensée travaille', () => {
  const i = SRC.indexOf('const enConversationAvecPapa'), k = SRC.indexOf('const horsConversation');
  let micro = 'conversation', dernier = Date.now();
  const ctx = { Date, HOMEO: { s: {} }, dernierMessageAhmedMs: () => dernier };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, SRC.indexOf('\n', k) + 1) + '\nthis.en = enConversationAvecPapa; this.hors = horsConversation;', ctx);
  let reveils = 0; const f = ctx.hors(() => { reveils++; });
  ctx.HOMEO.s.micro = micro; f();
  assert.strictEqual(reveils, 0, 'micro ouvert en conversation : pas de réveil de lui-même');
  dernier = Date.now() - 11 * 60e3; f();
  assert.strictEqual(reveils, 1, 'papa ne parle plus depuis 10 min : la page a pu se fermer, rien n’est bloqué');
  dernier = Date.now(); ctx.HOMEO.s.micro = null; f();
  assert.strictEqual(reveils, 2, 'hors conversation : comme avant');
  for (const n of ['reveillerPourTaches', 'reveillerPourCourrier', 'reveillerPourSens', 'reveillerPourCorps', 'reveillerPourCafe'])
    assert.match(SRC, new RegExp(`setInterval\\(horsConversation\\(${n}\\), `), n);
  assert.match(SRC, /enConversationAvecPapa\(\)\) return \{ ok: false, raison: 'conversation : seule sa pensée \(pas de petit mot glissé\)' \};/);
});

// (04/11, Ahmed : « il faut décharger la pensée à la première pensée, sinon ça fait des gros pavés : chaque pensée prononcée dans la
// pensée, puis la 2e dans une nouvelle »)
test('(04/11) une pensée par élément ; un bout qui redit un bout déjà dit est sauté', () => {
  const dits = [];
  const ctx = { etat: { conversation: {} }, lecteurNeuronal: { direAudio: (t) => dits.push(t) } };
  vm.createContext(ctx);
  vm.runInContext('let bouts = { tour: 1, prochain: 1, liste: new Map(), enFile: [], dits: [] };\n' + extraire('function direBouts') + '\nthis.dire = direBouts; this.b = () => bouts;', ctx);
  ctx.b().liste.set(1, { n: 1, texte: 'Oui papa, je suis réactif !', buf: {}, t: 0 });
  ctx.b().liste.set(2, { n: 2, texte: 'Je suis réactif papa, oui.', buf: {}, t: 0 });
  ctx.b().liste.set(3, { n: 3, texte: 'Un gros chien ? Raconte-moi !', buf: {}, t: 0 });
  ctx.dire();
  assert.strictEqual(dits.join(' | '), 'Oui papa, je suis réactif ! | Un gros chien ? Raconte-moi !');
  assert.match(PAGE, /montrerPensee\('🧠 sa pensée', t, true\)/, 'chaque bout qui sonne : sa propre pensée');
  assert.match(PAGE, /if \(pensees\.length > 6\)/, 'les 6 dernières restent');
});

// (04/11, mesuré : charge 41 pour 10 cœurs, 10 Go d'échange, un Claude neuf toutes les quelques secondes)
test('(04/11) moins de charge : inventaire toutes les 10 min, voix vivantes renouvelées tous les 25 messages, pistes sans Claude lancé pour l’occasion', () => {
  assert.match(SRC, /setInterval\(refreshInventory, 10 \* 60e3\)/);
  assert.match(SRC, /VIVANT_RENOUVELER = 25;/);
  assert.match(SRC, /if \(String\(etiquette\)\.startsWith\('piste_'\)\) return fin\(\{ erreur:/);
  assert.match(SRC, /Jamais « je t'écoute », « continue », « vas-y »/, '(04/11) ses pistes répondent avec assurance');
});

// (04/11, Ahmed : « j'aimerais que ça utilise la voix du smartphone quand c'est sur le smartphone »)
test('(04/11) dans l’appli, la voix du téléphone : parlée comme une voix de navigateur, chaque phrase dit son début et sa fin', () => {
  const i = PAGE.indexOf('const synthTelephone = '), k = PAGE.indexOf('class EnonceTelephone');
  const dits = [], arrets = [];
  const ctx = { window: { HakimApp: { voixTelephone: (id, t, v, l) => dits.push([id, t, l]), voixTelephoneArreter: () => arrets.push(1) } }, Map, String, Number };
  vm.createContext(ctx);
  vm.runInContext(PAGE.slice(i, k) + '\nthis.synth = synthTelephone;', ctx);
  const evts = [];
  const u = { text: 'Salut papa', lang: 'fr-FR', rate: 1, onstart: () => evts.push('debut'), onend: () => evts.push('fin') };
  ctx.synth.speak(u);
  assert.strictEqual(dits[0][1], 'Salut papa');
  ctx.window.HakimVoixTel('debut', dits[0][0]); ctx.window.HakimVoixTel('fin', dits[0][0]);
  assert.deepStrictEqual(evts, ['debut', 'fin']);
  ctx.synth.speak({ text: 'encore', onend: () => evts.push('coupée') }); ctx.synth.cancel();
  assert.deepStrictEqual(evts.slice(-1), ['coupée'], 'Stop : la phrase en cours finit tout de suite');
  assert.match(PAGE, /get impl\(\) \{ if \(voixDuTelephone\(\) && lecteurSysteme\) return lecteurSysteme;/, 'par défaut dans l’appli');
  // (04/11, la page vide dans l'appli 1.55) tout ce que la page appelle sur la voix du système existe aussi ici
  for (const m of ['addEventListener', 'removeEventListener', 'pause', 'resume', 'speak', 'cancel', 'getVoices'])
    assert.strictEqual(typeof ctx.synth[m], 'function', m);
  const appels = [...new Set([...PAGE.matchAll(/\bsynth\.([a-zA-Z]+)\(/g)].map(x => x[1]))];
  for (const m of appels) assert.strictEqual(typeof ctx.synth[m], 'function', `la page appelle synth.${m}`);
  assert.match(SRC, /if \(Date\.now\(\) - voixTelephoneA < 60000\) return null;/, 'le Mac ne fabrique plus la voix de ses pensées');
});

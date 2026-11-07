/* (06/11, Ahmed : « qu'il parle avec sa voix de rap, sur le Mac, le téléphone et la montre, en darija, français et anglais mélangés »)
   le choix de sa voix (voix_hakim), le découpage par langue, le relais d'Azure quand Chatterbox ne suit pas.
   node --test test-voix-rap.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const V = require('./voix-hakim.js');
const D = require('./debuts.js');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const REGLAGES = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
const extraire = (debut, fin) => { const i = SRC.indexOf(debut), k = SRC.indexOf(fin, i + 1); assert.ok(i >= 0 && k > i, debut); return SRC.slice(i, k); };

test('le choix de sa voix : azure par défaut, rap seulement si choisi ; dans les réglages du corps, la page et le POST', () => {
  assert.strictEqual(V.choixVoix({}), 'azure');
  assert.strictEqual(V.choixVoix({ voix_hakim: 'rap' }), 'rap');
  assert.strictEqual(V.choixVoix({ voix_hakim: '/tmp/x.wav' }), 'azure');
  assert.strictEqual(V.choixVoix(null), 'azure');
  const ctx = { lireJson: () => ({ voix_hakim: 'rap' }), CORPS_REGLAGES: 'x', CORPS_INTERVALLES: [120] };
  vm.createContext(ctx);
  vm.runInContext(extraire('function corpsReglages(', '\nfunction corpsActif(') + '\nthis.f = corpsReglages;', ctx);
  assert.strictEqual(ctx.f().voix_hakim, 'rap');
  ctx.lireJson = () => ({ voix_hakim: 'autre' });
  assert.strictEqual(ctx.f().voix_hakim, 'azure');
  assert.match(SRC, /if \(VoixHakim\.VOIX\.includes\(q\.voix_hakim\)\) \{ r\.voix_hakim = q\.voix_hakim; noterAjustementPapa\(\['voix_hakim'\]\); \}/);
  assert.match(REGLAGES, /\['voix_hakim', '🎤 Sa voix', [^\n]*'liste', \[\['azure', 'Azure \(rapide\)'\], \['rap', 'Sa voix de rap \(Chatterbox, sur le Mac\)'\]\], 'corps'\]/);
});

test('en rap, le téléphone prend la voix du Mac (jamais Supertonic), et ses débuts et meubles se rechargent dans la nouvelle voix', () => {
  assert.match(PAGE, /if \(reglagesCorps\.voix_azure \|\| reglagesCorps\.voix_hakim === 'rap'\) etat\.reglages\.voix = 'neuronale';/);
  assert.match(PAGE, /lireReglagesCorps\.voix !== reglagesCorps\.voix_hakim\) \{ debutsPrets = new Set\(\); meublesPrets\.clear\(\);/);
});

test('ses débuts gardés : une clé par voix, celle d’avant inchangée sans voix', () => {
  const avant = D.cle('Oui frérot,', 'fr', 0.7, 1);
  assert.strictEqual(D.cle('Oui frérot,', 'fr', 0.7, 1, null), avant);
  assert.notStrictEqual(D.cle('Oui frérot,', 'fr', 0.7, 1, 'rap'), avant);
  assert.match(D.cle('Oui frérot,', 'fr', 0.7, 1, 'rap'), /^[0-9a-f]{32}$/);
  assert.match(SRC, /const cleVoix = debut \? D\.cle\(texte, langueVoix, emotion, tempo, rap\) : null;/);
  assert.match(SRC, /D\.lire\(D\.cle\(d, langue, e, tempo, typeof voixRap === 'function' \? voixRap\(\) : null\)\)/, '/api/voix/debuts : ceux de sa voix du moment');
});

test('le découpage par langue : arabe, français, anglais, un lang_code par morceau, voisins recollés', () => {
  assert.deepStrictEqual(V.segmenterLangues("Wesh frérot, let's go! On y va tonton."),
    [{ langue: 'fr', texte: 'Wesh frérot,' }, { langue: 'en', texte: "let's go!" }, { langue: 'fr', texte: 'On y va tonton.' }]);
  assert.deepStrictEqual(V.segmenterLangues('كيراك خويا، ça va? I love you bro.'),
    [{ langue: 'ar', texte: 'كيراك خويا،' }, { langue: 'fr', texte: 'ça va?' }, { langue: 'en', texte: 'I love you bro.' }]);
  assert.deepStrictEqual(V.segmenterLangues('Bonjour papa, je suis là.'), [{ langue: 'fr', texte: 'Bonjour papa, je suis là.' }]);
  // une proposition muette (« Wallah, ») suit sa voisine
  assert.deepStrictEqual(V.segmenterLangues('Yeah, wallah, you know.'), [{ langue: 'en', texte: 'Yeah, wallah, you know.' }]);
  assert.deepStrictEqual(V.segmenterLangues(''), []);
  assert.strictEqual(V.langueLatine('the money never stops'), 'en');
  assert.strictEqual(V.langueLatine('je reste moi'), 'fr');
  assert.strictEqual(V.langueLatine('wesh'), null);
});

test('le relais d’Azure : le Studio, un Chatterbox froid, une file trop longue ; sinon lui', () => {
  assert.strictEqual(V.raisonSecours({ chaude: true, studio: null, attente_s: 1 }), null);
  assert.strictEqual(V.raisonSecours({ chaude: false, studio: null, attente_s: 0 }), null);   // (07/11) plus tout de suite : 60 s
  assert.strictEqual(V.raisonSecours({ chaude: true, studio: 'une chanson se calcule', attente_s: 0 }), null);
  assert.ok(V.budgetMs('Bonjour.') >= 60000, '(07/11) Azure seulement après 60 s');
  assert.match(V.raisonSecours({ chaude: true, studio: null, attente_s: V.SEUIL_FILE_S + 1 }), /^file de/);
  const longue = 'x'.repeat(14 * 62);                                    // ~62 s de parole (07/11 : seuil 60 s)
  assert.ok(V.attenteFile([{ texte: longue }], null) > V.SEUIL_FILE_S);
  assert.strictEqual(V.attenteFile([{ texte: longue, fond: true }], null), 0, 'le fond passe après : il ne compte pas');
  assert.ok(V.attenteFile([{ texte: longue, fond: true }], null, true) > 8, 'sauf pour une voix de fond elle-même');
  assert.ok(V.budgetMs('Bonjour.') >= 4000 && V.budgetMs(longue) > V.budgetMs('Bonjour.'));
});

test('le Studio occupé : une chanson en calcul ou un travail du Studio vivant ; terminé ou orphelin : libre', () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'voixrap-'));
  const taches = path.join(d, 'cwd', 'taches'), travaux = path.join(d, 'chansons', 'studio', 'travaux');
  fs.mkdirSync(taches, { recursive: true }); fs.mkdirSync(travaux, { recursive: true });
  let t = 1e12;
  assert.strictEqual(V.studioOccupe(d, t += 5000), null);
  fs.writeFileSync(path.join(taches, 'T-1.json'), JSON.stringify({ chanson: true, etat: 'en cours', superviseur: 999999999 }));
  assert.strictEqual(V.studioOccupe(d, t += 5000), null, 'superviseur mort : orpheline');
  fs.writeFileSync(path.join(taches, 'T-1.json'), JSON.stringify({ chanson: true, etat: 'en cours', superviseur: process.pid }));
  assert.strictEqual(V.studioOccupe(d, t += 5000), 'une chanson se calcule');
  fs.writeFileSync(path.join(taches, 'T-1.json'), JSON.stringify({ chanson: true, etat: 'fini', superviseur: process.pid }));
  fs.writeFileSync(path.join(travaux, 'J-1.json'), JSON.stringify({ type: 'mixer', etat: 'en cours', pid: process.pid }));
  assert.strictEqual(V.studioOccupe(d, t += 5000), 'le Studio (mixer)');
  fs.rmSync(d, { recursive: true, force: true });
});

/* routeDire, avec ses voisins remplacés : ce que sert la route selon la voix, l'état de Chatterbox et ce qui arrive à la synthèse */
function route({ rap = true, chaude = true, studio = null, azure = true, voixAzureReglage = false, budget = null } = {}) {
  const journal = [], file = [], chauffes = [];
  const VH = { ...V, studioOccupe: () => studio, ...(budget ? { budgetMs: () => budget } : {}) };
  const ctx = { Date, Math, Number, String, Promise, Buffer, JSON, setTimeout, clearTimeout, encodeURIComponent, console, process: { pid: 1 },
    lireCorps: async (req) => req.corps, prononcer: (t) => t, VoixPage: { debutDe: () => null }, estMeuble: () => false, D,
    voixRap: () => (rap ? 'rap' : null), VoixHakim: VH, fileVoix: file, voixEnCours: null, parolePrete: () => chaude,
    chaufferVoixRap: () => chauffes.push(1), JARVIS: '/nulle-part', voixALaSource: new Map(),
    corpsReglages: () => ({ voix_azure: voixAzureReglage }), optionsVoix: (t, l) => ({ voix: 'rap', langue: l }),
    pomperVoix() {}, voixAzure: async () => (azure ? { data: Buffer.from('AZURE'), ms: 120 } : null),
    path, os: { tmpdir: () => '/tmp' }, crypto: { randomBytes: () => ({ toString: () => 'ab' }) }, j: JSON.stringify, JARVIS_VOIX_DIAGNOSTIC: '/dev/null',
    fs: { appendFileSync: (f, l) => journal.push(JSON.parse(l)), unlink: (f, cb) => { journal.push({ e: 'efface' }); if (cb) cb(); },
      readFile: (f, cb) => cb(null, Buffer.from('RAP')) } };
  vm.createContext(ctx);
  vm.runInContext(extraire('async function routeDire(', '\nfunction etatStt(') + '\nthis.routeDire = routeDire;', ctx);
  const res = { tetes: null, corps: null, writableEnded: false, writableFinished: false, on() {},
    writeHead(c, h) { this.code = c; this.tetes = h; }, end(d) { this.corps = String(d); this.writableEnded = true; } };
  const fini = ctx.routeDire({ corps: JSON.stringify({ texte: "Wesh frérot, let's go!", langue: 'fr' }) }, res);
  return { res, fini, journal, file, chauffes };
}

test('en rap, Chatterbox chaud : sa voix de rap, le timbre et les langues dans la tâche', async () => {
  const r = route();
  await new Promise(x => setImmediate(x));
  assert.strictEqual(r.file.length, 1);
  assert.strictEqual(r.file[0].voix, 'rap');
  r.file[0].fin({ duree_s: 1.4 });
  await r.fini;
  assert.strictEqual(r.res.corps, 'RAP');
  assert.ok(!r.journal.some(x => x.e === 'secours_azure'));
});

test('en rap, Chatterbox froid ou le Studio en calcul : (07/11) plus d’Azure tout de suite, sa phrase attend sa voix (60 s au plus)', async () => {
  let r = route({ chaude: false });
  await new Promise(x => setImmediate(x));
  assert.strictEqual(r.file.length, 1, 'sa phrase attend Chatterbox');
  assert.strictEqual(r.chauffes.length, 1, 'froid : il se chauffe');
  assert.deepStrictEqual(r.journal.filter(x => x.e === 'secours_azure'), []);
  r = route({ studio: 'une chanson se calcule' });
  await new Promise(x => setImmediate(x));
  assert.strictEqual(r.file.length, 1);
  assert.deepStrictEqual(r.journal.filter(x => x.e === 'secours_azure'), []);
});

test('en rap, une erreur ou une synthèse trop lente : Azure prend la phrase ; le son tardif est jeté', async () => {
  let r = route();
  await new Promise(x => setImmediate(x));
  r.file[0].fin({ erreur: 'processus voix arrêté' });
  await r.fini;
  assert.strictEqual(r.res.corps, 'AZURE');
  assert.match(r.journal.find(x => x.e === 'secours_azure').raison, /^erreur : processus voix arrêté/);
  r = route({ budget: 20 });
  await new Promise(x => setImmediate(x));
  const tache = r.file[0];
  await r.fini;
  assert.strictEqual(r.res.corps, 'AZURE');
  assert.strictEqual(r.journal.find(x => x.e === 'secours_azure').raison, 'trop lente');
  assert.strictEqual(r.file.length, 0, 'pas encore commencée : sortie de la file');
  const avant = r.journal.filter(x => x.e === 'efface').length;
  tache.fin({ duree_s: 1 });                                            // si elle finit quand même : son son est jeté
  assert.strictEqual(r.journal.filter(x => x.e === 'efface').length, avant + 1);
});

test('en rap, Azure aussi en panne : Chatterbox quand même (rien n’est perdu) ; en Azure, comme avant', async () => {
  let r = route({ chaude: false, azure: false });
  await new Promise(x => setImmediate(x));
  assert.strictEqual(r.file.length, 1, 'il attend Chatterbox');
  r.file[0].fin({ duree_s: 1 });
  await r.fini;
  assert.strictEqual(r.res.corps, 'RAP');
  r = route({ rap: false, voixAzureReglage: true });
  await r.fini;
  assert.strictEqual(r.res.corps, 'AZURE');
  assert.ok(!r.journal.some(x => x.e === 'secours_azure'), 'Azure choisi : pas un relais');
});

test('le processus voix reçoit le timbre et les morceaux ; un Chatterbox froid se chauffe une seule fois', () => {
  assert.match(SRC, /\.\.\.\(tache\.voix \? \{ voix: tache\.voix \} : \{\}\), \.\.\.\(tache\.segments \? \{ segments: tache\.segments \} : \{\}\)/);
  const file = [];
  const ctx = { fileVoix: file, pomperVoix() {}, path, os: { tmpdir: () => '/tmp' }, process: { pid: 1 }, Date,
    crypto: { randomBytes: () => ({ toString: () => 'ab' }) }, fs: { unlink() {} } };
  vm.createContext(ctx);
  vm.runInContext(extraire('function chaufferVoixRap(', '\n}\n') + '\n}\nthis.f = chaufferVoixRap;', ctx);
  ctx.f(); ctx.f();
  assert.strictEqual(file.length, 1);
  assert.strictEqual(file[0].voix, 'rap');
  assert.strictEqual(file[0].fond, true, 'derrière ce qu’il dit vraiment');
});

// (07/11, Hakim, accord d'Ahmed : chanson bloquée au chargement, swap plein) pendant une chanson, sa voix Chatterbox et la séparation sont déchargées
test('pendant une chanson : sa voix et la séparation déchargées (jamais pendant une demande), et rien ne les relance', () => {
  const srv = require('node:fs').readFileSync(require('node:path').join(__dirname, 'server.js'), 'utf8');
  const i = srv.indexOf('function memoirePourChanson('), f = srv.slice(i, srv.indexOf('\n}\n', i) + 3);
  const tues = [];
  const proc = (nom) => ({ exitCode: null, signalCode: null, kill: () => tues.push(nom) });
  const cx = { VoixHakim: { studioOccupe: () => null }, JARVIS: '/x', fs: { appendFileSync() {} }, j: JSON.stringify, JARVIS_VOIX_DIAGNOSTIC: '/x/d',
    voixProcs: { parole: proc('voix') }, voixAttente: new Map(), fileVoix: [], separation: { proc: proc('separation'), attente: null } };
  require('node:vm').createContext(cx); require('node:vm').runInContext(f + 'this.m = memoirePourChanson;', cx);
  assert.deepEqual(cx.m(null), [], 'rien ne se calcule : on garde tout');
  cx.voixAttente.set(1, { proc: cx.voixProcs.parole });
  assert.deepEqual(cx.m('une chanson se calcule'), ['separation'], 'sa voix répond à une demande : gardée');
  cx.voixAttente.clear(); cx.separation.proc = proc('separation');
  assert.deepEqual(cx.m('une chanson se calcule'), ['voix', 'separation']);
  assert.equal(cx.voixProcs.parole, null);
  assert.match(srv, /function chaufferVoixRap\(\) \{\n  if \(fileVoix\.some\(x => x\.chauffe\)\) return;\n  if \(typeof VoixHakim !== 'undefined' && VoixHakim\.studioOccupe\(JARVIS\)\) return;/);
  assert.match(srv, /function lancerSeparation\(\) \{\n  if \(separation\.proc \|\| !fs\.existsSync\(PYTHON_SEPARATION\)\) return;\n  if \(typeof VoixHakim !== 'undefined' && VoixHakim\.studioOccupe\(JARVIS\)\) return;/);
});

/* (27/10, Ahmed : « option 3 OK », « OK pour les simulations ») Mesurer où passe le temps d'un tour oral :
   node --test test-vitesse.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const lire = (f) => fs.readFileSync(path.join(__dirname, f), 'utf8');
const ligne = (debut) => { const i = serveur.indexOf(debut); return serveur.slice(i, serveur.indexOf('\n', i) + 1); };
const prendreDans = (src, nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const serveur = lire('server.js'), page = lire('public/parler.js');

test('le cockpit note le temps de sa préparation (avant le cerveau) et celui du cerveau jusqu’à son premier mot', () => {
  const route = prendreDans(serveur, 'routeJarvis');
  assert.match(route, /const corps = await lireCorps\(req, 1 << 20\);\n\s*const recuMs = Date\.now\(\);/);
  assert.match(route, /if \(!envoyeMs\) envoyeMs = Date\.now\(\);\s*\n\s*enfant\.stdin\.write\(/);
  assert.match(route, /if \(!premierTexteMs\) premierTexteMs = Date\.now\(\);/);
  assert.match(route, /if \(!premierOutilMs\) premierOutilMs = Date\.now\(\);/);
  assert.match(route, /noterJetons\(\{[^}]*\.\.\.vitesseDuTour\(recuMs, envoyeMs, premierTexteMs, premierOutilMs\)/);
});

test('les temps du tour : préparation, premier mot du cerveau, premier outil ; rien d’inventé quand il manque une étape', () => {
  const ctx = { Math };
  vm.createContext(ctx);
  vm.runInContext(prendreDans(serveur, 'vitesseDuTour') + 'this.f = vitesseDuTour;', ctx);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.f(1000, 2500, 9000, 4000))),
    { prep_ms: 1500, cerveau_premier_mot_ms: 6500, cerveau_premier_outil_ms: 1500 });
  assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.f(1000, 2500, 0, 0))), { prep_ms: 1500 });
  assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.f(1000, 0, 0, 0))), {});
});

test('Parler journalise les pauses de ta phrase, la patience et la fin anticipée (pour rejouer la fin de tour)', () => {
  const journal = [];
  const ctx = { Math, journalVoix: (e, d) => journal.push([e, d]), mesureTour: null };
  vm.createContext(ctx);
  vm.runInContext('let mesureTour = null;' + prendreDans(page, 'finMesureTour')
    + 'this.f = finMesureTour; this.poser = (m) => { mesureTour = m; };', ctx);
  ctx.poser({ fin: 1000, debut: 3000, transcrit: 5000, premier_texte: 12000, premier_son: 14000,
    pauses: [700, 1200], anticipe: false, patience: 2000 });
  ctx.f();
  const [e, d] = journal[0];
  assert.strictEqual(e, 'tour_temps');
  assert.deepStrictEqual(JSON.parse(JSON.stringify(d.pauses_ms)), [700, 1200]);
  assert.strictEqual(d.patience_ms, 2000);
  assert.strictEqual(d.anticipe, false);
  assert.strictEqual(d.attente_fin_tour_ms, 2000);
  assert.match(page, /mesureTour = \{[^}]*pauses: \(\(infos && infos\.pauses\) \|\| \[\]\)\.slice\(0, 30\), anticipe: extra != null, patience: patienceConversation\(\)/);
});

// ---- (27/10, idée d'Ahmed, erreur de Hakim du 22/10, du 25/10 deux fois et du 27/10 à 00:30) « No response requested. »
// en réponse à un VRAI message d'Ahmed : le cockpit le relance une fois au lieu de laisser Ahmed sans réponse
test('« No response requested. » à un vrai message d’Ahmed : une seule relance, jamais en local ni sur une erreur', () => {
  const ctx = { String, corpsReglages: () => ({ afficher_papa: true }) };
  vm.createContext(ctx);
  vm.runInContext(ligne('const NON_REPONSE_SERVEUR') + 'const sansBaliseAffect = (t) => String(t || "");'
    + prendreDans(serveur, 'relanceNonReponse') + 'this.f = relanceNonReponse;', ctx);
  assert.strictEqual(ctx.f('No response requested.', false, 'abonnement', {}, false), true);
  assert.strictEqual(ctx.f('  no response requested  ', false, 'api', {}, false), true);
  ctx.corpsReglages = () => ({ afficher_papa: false });
  assert.strictEqual(ctx.f('No response requested.', false, 'abonnement', {}, false), false, '(21:00) « dans sa tête » : son silence est permis');
  ctx.corpsReglages = () => ({ afficher_papa: true });
  assert.strictEqual(ctx.f('No response requested.', false, 'abonnement', {}, true), false, 'un invité parlait : pas forcément à lui');
  assert.strictEqual(ctx.f('No response requested.', true, 'abonnement', {}), false, 'une seule fois');
  assert.strictEqual(ctx.f('No response requested.', false, 'local', {}), false);
  assert.strictEqual(ctx.f('No response requested.', false, 'abonnement', { is_error: true }), false);
  assert.strictEqual(ctx.f('Frérot, voilà.', false, 'abonnement', {}), false);
});

test('la relance repart dans le MÊME tour (remis en tête de file, texte effacé côté page) et Parler sait effacer', () => {
  const route = prendreDans(serveur, 'routeJarvis');
  assert.match(route, /if \(relanceNonReponse\(reponse, tour\.relance, source, o, voixTierce\)\) \{[\s\S]*?tour\.relance = true;[\s\S]*?reponse = ''; dejaTexte = false; premierTexteMs = 0;[\s\S]*?envoyer\(\{ t: 'efface' \}\);[\s\S]*?c\.attente\.unshift\(tour\);[\s\S]*?enfant\.stdin\.write\(/);
  assert.match(route, /const voixTierce = q\.voix === 'autre' \|\| declencheursDuTour\(q, texte\)\.includes\('plusieurs_voix'\);/);
  assert.match(page, /else if \(o\.t === 'efface'\) \{ m\.texte = ''; if \(auto\) decoupe\.finir\(\); majMessage\(m\); \}/, 'la voix oublie aussi la non-réponse');
});

// ---- (28/10, Ahmed via Hakim, 10:29 : « on ne coupe rien, on accélère » ; d'abord mesurer CHAQUE étape de la préparation)
test('le chronomètre des étapes : la durée de chaque étape, même quand elle échoue', async () => {
  const ctx = { Date, Promise };
  vm.createContext(ctx);
  vm.runInContext(prendreDans(serveur, 'chronometre') + 'this.f = chronometre;', ctx);
  const etapes = {};
  const chrono = ctx.f(etapes);
  assert.strictEqual(await chrono('vite', Promise.resolve(7)), 7);
  await assert.rejects(chrono('rate', new Promise((_, r) => setTimeout(() => r(new Error('x')), 30))));
  assert.ok(etapes.vite >= 0 && etapes.vite < 20, etapes.vite);
  assert.ok(etapes.rate >= 25, etapes.rate);
});

test('chaque étape de la préparation est chronométrée et notée avec le tour (jetons.jsonl)', () => {
  const route = prendreDans(serveur, 'routeJarvis');
  assert.match(route, /const etapes = \{\}, chrono = chronometre\(etapes\);/);
  for (const nom of ['interieur', 'reflexe', 'sagesse', 'briefing'])
    assert.match(route, new RegExp(`await chrono\\('${nom}', `), nom);
  assert.match(route, /chrono\('rappel', blocRappel\(/);              // lancé en premier, attendu plus loin
  assert.match(route, /etapes\.cerveau_ms = Date\.now\(\) - tCerveau;/);
  assert.match(route, /etapes\.cerveau_neuf = /);
  assert.match(route, /noterJetons\(\{[^}]*etapes,/);
});

// (28/10) l'oreille : la transcription passe par le même processus que la voix ; une synthèse en cours la fait attendre
test('chaque transcription est mesurée côté serveur : sa durée, et si une synthèse de voix tournait à son arrivée', () => {
  const route = prendreDans(serveur, 'routeTranscrire');
  assert.match(route, /const tTranscription = Date\.now\(\), syntheseEnCours = voixOccupee;/);
  assert.match(route, /e: 'transcription_serveur', ms: Date\.now\(\) - tTranscription, synthese_en_cours: syntheseEnCours, octets: audio\.length/);
});

// (28/10) la voix : combien chaque phrase a attendu dans la file, puis combien sa synthèse a pris
test('chaque synthèse de voix est mesurée côté serveur : attente dans la file, durée de synthèse, longueur', () => {
  const pompe = prendreDans(serveur, 'pomperVoix');
  assert.match(pompe, /const tSynthese = Date\.now\(\);/);
  assert.match(pompe, /e: 'synthese_serveur', attente_ms: tSynthese - \(tache\.recu \|\| tSynthese\), ms: Date\.now\(\) - tSynthese, caracteres: tache\.texte\.length/);
  assert.match(serveur, /tache\.recu = Date\.now\(\); tache\.fin = resolve; if \(q && q\.prioritaire === true\) fileVoix\.unshift\(tache\); else fileVoix\.push\(tache\);/);
});

// (28/10, backtest : 90 % de la préparation est le rappel et son tri) le rappel part dès le début de la préparation, en
// parallèle du reste (intérieur, réflexe, sagesse) ; rien n'est coupé, il est attendu avant d'écrire le message
test('le rappel part en premier, en parallèle du reste de la préparation', () => {
  const route = prendreDans(serveur, 'routeJarvis');
  const iRappel = route.indexOf("const rappelP = chrono('rappel', blocRappel(session, texte, nonce)");
  const iInterieur = route.indexOf("const interieurTexte = await chrono('interieur'");
  assert.ok(iRappel > 0 && iRappel < iInterieur, 'le rappel est lancé avant l’intérieur');
  assert.match(route, /const rappelBloc = await rappelP;/);
  assert.strictEqual((route.match(/const nonce = crypto\.randomBytes\(4\)\.toString\('hex'\);/g) || []).length, 1);
});

test('le tri ne fait aucun trafic accessoire (mesuré : ~0,15 s de moins par appel)', () => {
  const tri = prendreDans(serveur, 'trierSouvenirs');
  assert.match(tri, /CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1'/);
});

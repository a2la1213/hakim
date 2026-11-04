// (04/11, 12:15, Ahmed : « l'arrivée de tous les sons doit être constamment ouverte, excepté quand il parle ; et encore, pas totalement
// fermée : des fenêtres d'ouverture d'oreille à chaque fois qu'il finit un chunk de phrase, pour voir si on va le couper ; et si on le
// coupe, il a le choix de continuer ou pas, selon le sujet abordé, la voix qu'il entend et l'importance générale qu'il considère dans
// le fait d'être coupé »)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (s, nom) => { const i = s.indexOf(`function ${nom}(`); return s.slice(i, s.indexOf('\n}\n', i) + 2); };
const attendre = () => new Promise(r => setImmediate(r));

test('son oreille : fermée seulement quand sa voix sonne (ni son attention choisie, ni son micro coupé avant sa voix)', () => {
  const ctx = { Date, reglagesCorps: { micro_ouvert: false }, enTelepathie: () => false, sonTourEnCours: () => true, lecteur: { actif: false, enPause: false },
    etat: { conversation: { attentionJusqua: Date.now() + 15000, muetParHakim: { attente: 0, avantVoix: true }, penseeEnPause: false } } };
  vm.createContext(ctx);
  vm.runInContext(prendre(PAGE, 'transcriptionEnPause') + 'this.f = transcriptionEnPause;', ctx);
  assert.strictEqual(ctx.f(), false, 'il pense, son micro « coupé » avant sa voix, son attention en pause : tu es entendu');
  ctx.lecteur.actif = true;
  assert.strictEqual(ctx.f(), true, 'sa voix sonne : fermée');
  ctx.lecteur.enPause = true;
  assert.strictEqual(ctx.f(), false, 'sa voix en pause : ouverte');
});

test('il ne coupe plus ton micro de lui-même par défaut (réglage micro_hakim décoché)', () => {
  assert.match(SRC, /micro_hakim: r\.micro_hakim === true/);
});

test('une fenêtre d’oreille après chaque morceau qu’il dit ; ta voix pendant son morceau ne le coupe plus au milieu : il finit, puis il choisit', () => {
  assert.match(PAGE, /const finLecture = \(\) => \{\n  segmentTelephone = null;\n(?:  \/\/[^\n]*\n)*  if \(typeof direRibosome === 'function'\) setTimeout\(direRibosome, typeof patienceConversation === 'function' \? patienceConversation\(\) : 0\);/);
  const f = PAGE.slice(PAGE.indexOf('surInterruption: (mesure) => {'), PAGE.indexOf('surFin: (wav, infos, extra) =>'));
  assert.match(f, /if \(voixEpissee\(\)\) \{ conv\.coupeAuChunk = Date\.now\(\); journalVoix\('coupure_au_chunk', mesure \|\| \{\}\); return; \}/);
  assert.ok(f.indexOf('voixEpissee()') < f.indexOf('veillerDeuxSecondes(conv)'), 'avant les 2 s qui le faisaient taire');
  assert.match(PAGE, /if \(chacunSonTour\(\) && sonTourEnCours\(\) && !conv\.souffleParle && !conv\.penseeDite && !voixEpissee\(\)\)/);
  assert.doesNotMatch(PAGE, /deciderCoupure/, '(13:10) rien de traduit n’est laissé : plus de choix de lâcher');
});






// (04/11, 12:25, Ahmed : « il n'arrête pas de s'autocouper la parole ») mesuré : sa voix reprise par le micro passait pour ta phrase
test('son écho : une phrase faite de ses mots des 30 dernières secondes n’est pas la tienne ; la tienne passe', () => {
  let t = 1_800_000_000_000;
  const ctx = { Date: class extends Date { static now() { return t; } }, String, Set, etat: {} };
  vm.createContext(ctx);
  vm.runInContext(prendre(PAGE, 'noterSaVoix') + prendre(PAGE, 'echoDeSaVoix') + 'this.noter = noterSaVoix; this.echo = echoDeSaVoix;', ctx);
  ctx.noter("Oui papa, je continue de parler même si tu me coupes, c'est le test. Je commence direct, sans me couper moi-même.");
  t += 5000;
  assert.strictEqual(ctx.echo("C'est le test, je commence direct et tout."), true, '12:22:56, rejoué');
  assert.strictEqual(ctx.echo('Il va plus vite que la musique.'), false);
  assert.strictEqual(ctx.echo('Tranquille fiston.'), false, 'trop court pour juger : à toi');
  assert.strictEqual(ctx.echo('[voix 11] Fiston répond à ma question.'), false);
  t += 31000;
  assert.strictEqual(ctx.echo("C'est le test, je commence direct et tout."), false, 'plus de 30 s : plus son écho');
  assert.match(PAGE, /if \(echoDeSaVoix\(texte\)\) \{ journalVoix\('echo_de_sa_voix'[^\n]*\n[^\n]*\n  activite\(\);\n  if \(COMMANDE_STOP\.test\(texte\)\)/);
  assert.match(PAGE, /dire\(phrase\) \{\n      if \(typeof noterSaVoix === 'function'\) noterSaVoix\(phrase\);/);
  assert.match(PAGE, /if \(typeof noterSaVoix === 'function'\) noterSaVoix\(u\.text\);/);
});

// (04/11, 12:30, Ahmed : « il faut que quand la traduction du ribosome commence, il ne coupe jamais sa parole »)

// (04/11, 12:35, Ahmed : « il ne doit plus pouvoir se couper non plus : enlève-lui la capacité de couper sa réponse, ça lui est inutile
// maintenant ») avec l'épissage : ni « DIRE : coupe » dans ses pistes, ni [[bout: annuler]] / [[bout: remiser]], ni [[pause: …]]
test('avec l’épissage, ses pistes ne lui proposent plus de se couper ; sans, comme avant', async () => {
  const i = SRC.indexOf('const PISTES_MAX'), k = SRC.indexOf('function speculerFreres(');
  const sandbox = (reglages) => {
    const appels = [];
    const ctx = { String, Math, Date, Promise, RegExp, Object, VIVANTS: [], VIVANTS_MAX: { haiku: 12, sonnet: 12, opus: 12 }, VIVANT_RENOUVELER: 6,
      cerveau: { modele: 'sonnet' }, corpsReglages: () => reglages, personaLocale: (p) => p, lirePersona: () => 'Hakim', neutraliser: (t) => t, j: JSON.stringify,
      abonnesPensees: null, path, JARVIS: '/x', fs: { appendFile() {}, readFile() {}, writeFile() {} }, voixDeLaSource() {}, diffuser() {},
      sonnetTeteDeFond: (prompt) => new Promise(() => appels.push(prompt)) };
    vm.createContext(ctx);
    vm.runInContext(SRC.slice(i, k) + '\nthis.morceau = pisteMorceau;', ctx);
    ctx.morceau('papa, tu sais quoi,'); ctx.morceau('papa, tu sais quoi, le sable,');
    return appels;
  };
  for (const p of sandbox({ epissage: true })) assert.doesNotMatch(p, /DIRE : coupe/);
  assert.ok(sandbox({ epissage: false }).some(p => /DIRE : coupe/.test(p)), 'épissage décoché : comme avant');
});

test('avec l’épissage, sa consigne de réponse ne lui apprend plus à annuler ni à remiser ses bouts', () => {
  const ctx = { Date, boutsRemises: new Map(), reglages: { epissage: true } };
  ctx.corpsReglages = () => ctx.reglages;
  vm.createContext(ctx);
  vm.runInContext(prendre(SRC, 'blocBouts') + 'this.f = blocBouts;', ctx);
  assert.doesNotMatch(ctx.f(), /\[\[bout: annuler\]\]|\[\[bout: remiser\]\]|remisée d'office/);
  ctx.reglages = { epissage: false };
  assert.match(ctx.f(), /\[\[bout: annuler\]\]/, 'épissage décoché : comme avant');
});

test('avec l’épissage, [[pause: …]] ne retient plus la suite de sa réponse', () => {
  const ctx = { RegExp, String, prendreParoleEnPause: () => '' };
  vm.createContext(ctx);
  const ligne = (debut) => { const a = SRC.indexOf(debut); return SRC.slice(a, SRC.indexOf('\n', a) + 1); };
  vm.runInContext(ligne('const prefixeBalise') + ligne('const BALISE_PAUSE') + ligne('const DEBUT_PAUSE') + prendre(SRC, 'filtrePause')
    + 'this.f = filtrePause;', ctx);
  const sans = ctx.f({ sansPause: true });
  assert.strictEqual(sans.pousser('Oui papa [[pause: j’attends]] et la suite.') + sans.finir(), 'Oui papa  et la suite.');
  const avec = ctx.f();
  assert.strictEqual(avec.pousser('Oui papa [[pause: j’attends]] et la suite.'), 'Oui papa ', 'décoché : comme avant, la suite retenue');
  assert.match(SRC, /let fluxPause = filtrePause\(\{ sansPause: corpsReglages\(\)\.epissage !== false \}\);/);
});

// (04/11, 13:10, Ahmed : « dès que le ribosome commence, il ne s'arrête jamais jusqu'à la fin, excepté si je parle : il attend la fin de ma
// parole ») ta phrase qui arrive ne fait plus taire sa voix ; tu parles : elle attend ta fin, puis reprend ; rien de traduit n'est laissé
test('ce qui est traduit sort jusqu’au bout : il attend pendant que tu parles, puis reprend ; chaque envoi a son numéro neuf', () => {
  assert.match(PAGE, /arreterTout\(true, \{ garder: true, raison: 'message', garderVoix: !!souffleDit \|\| voixEpissee\(\) \}\);/);
  assert.match(PAGE, /arreterTout\(true, \{ garder: true, raison: 'parole', garderVoix: voixEpissee\(\) \}\);/);
  const dits = [];
  const ctx = { Math, etat: { riboFile: [{ tour: 4, texte: 'Oui papa' }], paves: { 4: { dits: [] } }, conversation: { capteur: { enParole: false } } },
    lecteur: { actif: false }, bouts: { tour: 4, prochain: 1 }, recevoirBout: (s, n) => dits.push([s.texte, n, s.ribosome]) };
  vm.createContext(ctx);
  vm.runInContext(prendre(PAGE, 'direRibosome') + 'this.f = direRibosome;', ctx);
  ctx.f();
  ctx.etat.riboFile = [{ tour: 4, texte: 'le calcul a fini' }];
  ctx.etat.conversation.capteur.enParole = true;
  ctx.f();
  assert.strictEqual(dits.length, 1, 'tu parles : il attend');
  ctx.etat.conversation.capteur.enParole = false;
  ctx.f();
  assert.deepStrictEqual(JSON.parse(JSON.stringify(dits)), [['Oui papa', 1, true], ['le calcul a fini', 2, true]], 'ta fin : il reprend, numéro neuf (Chatterbox calculait encore)');
  assert.match(PAGE, /if \(!conv \|\| !n \|\| \(!s\.ribosome && !souffleAutorise\(\)\)\) return;/, 'ce qui est traduit passe toujours');
  assert.match(PAGE, /\(!s\.ribosome && m1\.length && bouts\.dits\.some/, 'jamais sauté parce qu’il ressemble à ce qu’il a dit');
  assert.doesNotMatch(SRC, /deciderCoupure|coupure-choix/);
});

// (04/11, 13:15, Ahmed : « l'épissure a été notée, mais je n'ai rien entendu ») mesuré : traduit à 13:13:47 pendant que papa parlait ; sa voix
// attendait sa fin, et rien ne la relançait après (le signal de ta pause part quand tu parles encore)
test('ta fin de tour relance sa voix ; et toutes les 0,3 s en Conversation, ce qui est traduit et en attente part', () => {
  const i = PAGE.indexOf('async function tourDeParole('), f = PAGE.slice(i, i + 400);
  assert.match(f, /^async function tourDeParole\(conv, wav, infos, extra\) \{\n  if \(typeof direRibosome === 'function'\) setTimeout\(direRibosome, 0\);/);
  assert.match(PAGE, /setInterval\(\(\) => \{\n  const c = etat\.conversation;\n  if \(!c \|\| typeof direRibosome !== 'function'\) return;[\s\S]{0,600}?\n  direRibosome\(\);\n\}, 300\);/);
});

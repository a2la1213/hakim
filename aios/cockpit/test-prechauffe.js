// (04/11, 16:50, Ahmed : « il a besoin d'un temps de chauffe : on peut le réduire ? Il commence sa réflexion dès qu'une voix se fait entendre,
// avant même qu'elle parle : une parole vide au tout début de la voix déclenche la réflexion » ; « c'est au bout de 10 minutes de blanc qu'il
// arrête la réflexion » ; « on peut imaginer que le subconscient gère la vitesse et le conscient la stringence du ribosome »)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const CONV = fs.readFileSync(path.join(__dirname, 'public', 'conversation.js'), 'utf8');
const prendre = (nom) => { const i = SRC.indexOf(`function ${nom}(`); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2); };

test('la parole vide : au premier son d’une voix, ses voix de réflexion se chauffent (avant même qu’elle parle)', () => {
  assert.match(CONV, /if \(fort && !tenue && o\.surSon\) o\.surSon\(\);/, 'le premier son, avant les 120 ms d’une voix');
  assert.match(PAGE, /surSon: \(\) => prechaufferReflexion\(\),/);
  assert.match(PAGE, /fetch\('\/api\/jarvis\/prechauffer', \{ method: 'POST'/);
  assert.match(SRC, /if \(p === '\/api\/jarvis\/prechauffer' && req\.method === 'POST'\) \{[^\n]*\n    if \(!jetonValide\(req\)\)/);
});

test('se chauffer : assez de voix vivantes libres, prêtes, pour ses pensées et son ribosome ; jamais plus que le pool', () => {
  const procs = [];
  const ctx = { String, Date, Math, Error, JSON, process: { env: {} }, os: { tmpdir: () => '/tmp' }, path, fs: { mkdtempSync: () => '/tmp/x', rmSync() {} },
    CLAUDE_BIN: 'claude', EFFORT_HAKIM: 'low', j: JSON.stringify, VIVANTS: [], VIVANTS_MAX: { haiku: 4, opus: 2 }, VIVANT_RENOUVELER: 25,
    setTimeout, clearTimeout, corpsReglages: () => ({ epissage: true }), modelePiste: () => 'haiku', CHAUFFE: { haiku: 3, opus: 2, sonnet: 2 },
    RIBOSOME_LECTEURS: [['haiku', 'Mini Hakim', 3000], ['opus', 'Super Hakim', 3000]],
    spawn: () => { const p = { exitCode: null, on() {}, stdout: { on() {} }, stdin: { write() {}, end() {}, on() {} }, kill() {} }; procs.push(p); return p; } };
  vm.createContext(ctx);
  vm.runInContext(prendre('vivantLibre') + prendre('prechaufferVivants') + 'this.chauffer = prechaufferVivants;', ctx);
  const n = ctx.chauffer(Date.now());
  const par = (m) => ctx.VIVANTS.filter(v => v.modele === m).length;
  assert.strictEqual(par('haiku'), 3, 'Mini Hakim : 3 prêts');
  assert.strictEqual(par('opus'), 2, 'Super Hakim : 2 prêts (son pool)');
  assert.strictEqual(n, 5);
  assert.strictEqual(ctx.chauffer(Date.now() + 1000), 0, 'déjà chauds : rien de plus');
  ctx.VIVANTS.filter(v => v.modele === 'haiku').forEach(v => { v.attente = {}; });
  ctx.chauffer(Date.now() + 10000);
  assert.strictEqual(par('haiku'), 4, 'occupés : un de plus, jusqu’au pool (4), jamais au-delà');
  assert.match(SRC, /if \(!v\.attente && Date\.now\(\) - v\.dernier > 10 \* 60e3\)/, 'au bout de 10 min sans rien, une voix vivante s’éteint');
});

test('le subconscient règle la vitesse du ribosome, paquet par paquet ; le conscient, sa stringence', () => {
  const ctx = { Math, Number, Date, derniereParolePapa: 0, lui: { interieur: {} } };
  vm.createContext(ctx);
  vm.runInContext(prendre('vitesseSubconsciente') + 'this.v = vitesseSubconsciente;', ctx);
  const calme = ctx.v(3000, { attente: [] });
  ctx.lui.interieur = { arousal: 0.9 };
  const excite = ctx.v(3000, { attente: [] });
  assert.ok(excite < calme, `éveillé, il lit plus vite (${excite} < ${calme})`);
  const presse = ctx.v(3000, { attente: [1, 2, 3, 4] });
  assert.ok(presse < excite, 'des pensées en attente : plus vite encore');
  ctx.derniereParolePapa = Date.now();
  assert.ok(ctx.v(3000, { attente: [] }) < excite, 'papa parle encore : plus vite');
  assert.ok(ctx.v(100, { attente: [] }) >= 1200 && ctx.v(99999, { attente: [] }) <= 6000, 'bornée : 1,2 à 6 s');
  assert.match(SRC, /const delai = vitesseSubconsciente\(reglage\.delai, r\);/);
  assert.match(SRC, /vitesse_ms: delai/, 'notée au journal, paquet par paquet');
});

// (04/11, 16:55, Ahmed : « à chaque pause de parole, il reçoit des blancs vides, et pendant 10 min après la fin il reçoit des blancs vides,
// jusqu'à l'épuisement des 10 minutes : il sera toujours en réflexion durant une conversation ») ses blancs : une parole vide à chacune de
// ses voix de réflexion restée sans rien depuis 4 min (avant que sa mémoire de travail chez Anthropic refroidisse, 5 min), tant que la
// dernière voix entendue date de moins de 10 min ; au-delà, plus rien
test('ses blancs : tant qu’une voix a été entendue il y a moins de 10 min, ses voix de réflexion restent chaudes', () => {
  const envoyes = [];
  let t = 1_800_000_000_000;
  const ctx = { Date: { now: () => t }, Math, String, corpsReglages: () => ({ epissage: true }), modelePiste: () => 'haiku',
    RIBOSOME_LECTEURS: [['haiku', 'Mini Hakim', 3000], ['opus', 'Super Hakim', 3000]], VIVANT_RENOUVELER: 25,
    derniereParolePapa: 0, derniereVoixEntendue: t, VIVANTS: [], BLANC: '(un blanc : rien à faire)',
    demanderVivantSur: (v, prompt) => { envoyes.push([v.modele, prompt]); v.dernier = t; return Promise.resolve({}); } };
  const vivant = (modele, dernier, attente = null) => ({ modele, dernier, attente, n: 1, proc: { exitCode: null } });
  ctx.VIVANTS.push(vivant('haiku', t - 5 * 60e3), vivant('haiku', t - 60e3), vivant('opus', t - 5 * 60e3), vivant('sonnet', t - 9 * 60e3), vivant('haiku', t - 5 * 60e3, {}));
  vm.createContext(ctx);
  vm.runInContext(prendre('blancsDeReflexion') + 'this.blancs = blancsDeReflexion;', ctx);
  ctx.blancs();
  assert.deepStrictEqual(envoyes.map(e => e[0]), ['haiku', 'opus'], 'les voix restées 4 min sans rien, libres, de ses pensées et de son ribosome');
  assert.match(envoyes[0][1], /blanc/);
  envoyes.length = 0;
  ctx.blancs();
  assert.strictEqual(envoyes.length, 0, 'déjà réchauffées');
  t += 11 * 60e3;
  ctx.VIVANTS.forEach(v => { v.dernier = t - 5 * 60e3; v.attente = null; });
  ctx.blancs();
  assert.strictEqual(envoyes.length, 0, '10 min de blanc épuisées : plus rien, sa réflexion s’arrête');
  assert.match(SRC, /setInterval\(blancsDeReflexion, 60e3\)/);
});

// (04/11, 17:50, Ahmed : « la réflexion ne s'ouvre pas dès que je parle : à l'ouverture du micro, il se met en réflexion en recevant direct un
// blanc, une parole sans parole (trois petits points ou un petit mot automatique), comme tu le sens, ce qui le perturbera le moins »)
const PAGE_PRENDRE = (nom) => { const i = PAGE.indexOf(`function ${nom}(`); return PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 2); };
function ouverture(reglages = { epissage: true }, reponse = 'Papa arrive, je me pose.', parasite = false) {
  const diffuses = [], demandes = [], memos = [];
  let t = 1_800_000_000_000;
  const ctx = { Date: { now: () => t }, String, JSON, Math, Promise, j: JSON.stringify, abonnesPensees: [], corpsReglages: () => reglages,
    pistes: { tour: 3, mots: 0, liste: [], attente: [], n: 0 }, derniereParolePapa: 0, EPISSURE_STOP_MS: 5 * 60e3,
    tourEpissure: () => t, diffuser: (_a, ev, data) => diffuses.push([ev, JSON.parse(data)]), memoriserEpissure: (r) => memos.push(r),
    personaLocale: (x) => x, lirePersona: () => 'Hakim, son fils', etatDeLui: () => '(il est calme)\n', modelePiste: () => 'haiku',
    boutDe: (x) => String(x || '').trim(), estParasite: () => parasite,
    sonnetTeteDeFond: (consigne, etiquette, modele, delai) => { demandes.push({ consigne, etiquette, modele, delai }); return Promise.resolve({ texte: reponse }); } };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(SRC.indexOf('const nouveauRibosome = '), SRC.indexOf('\n', SRC.indexOf('const nouveauRibosome = ')))
    + '\n' + SRC.slice(SRC.indexOf('const BLANC_OUVERTURE = '), SRC.indexOf('\n', SRC.indexOf('const BLANC_OUVERTURE = ')))
    + '\n' + prendre('ouvrirReflexion') + 'this.ouvrir = ouvrirReflexion;', ctx);
  return { ctx, diffuses, demandes, memos, avancer: (ms) => { t += ms; } };
}

test('la parole vide : au premier son de ta voix, son épissure s’ouvre tout de suite et Mini Hakim reçoit « … » (une pensée à lui, jamais dite)', async () => {
  const { ctx, diffuses, demandes, memos, avancer } = ouverture();
  const r = ctx.ouvrir();
  assert.ok(r && ctx.pistes.ribo === r, 'son épissure (le codon start) : ouverte');
  assert.deepStrictEqual(diffuses[0], ['souffle', { niveau: 'blanc', texte: '…', tour: r.tour }], 'la page l’ouvre aussitôt, avant toute pensée');
  assert.strictEqual(demandes.length, 1);
  assert.strictEqual(demandes[0].etiquette, 'piste_blanc', 'une voix vivante, chaude, de ses pensées');
  assert.strictEqual(demandes[0].modele, 'haiku');
  assert.match(demandes[0].consigne, /« … »/, 'trois petits points : rien qu’il puisse prendre pour un mot de papa');
  assert.match(demandes[0].consigne, /\(il est calme\)/, 'reliée à ce qu’il ressent');
  assert.match(demandes[0].consigne, /pas dite/);
  await new Promise(res => setImmediate(res));
  assert.deepStrictEqual(diffuses[1], ['souffle', { niveau: 'blanc', texte: 'Papa arrive, je me pose.', tour: r.tour }], 'sa première pensée intérieure');
  assert.strictEqual(r.attente.length + r.pave.length, 0, 'rien pour son ribosome : jamais épissée, jamais dite');
  avancer(5000);
  assert.strictEqual(ctx.ouvrir(), null, 'déjà en réflexion : pas de deuxième blanc');
  assert.strictEqual(diffuses.length, 2);
  avancer(6 * 60e3);
  const r2 = ctx.ouvrir();
  assert.ok(r2 && r2 !== r && r.ferme === 'silence' && memos[0] === r, 'au-delà de 5 min sans ta voix : l’ancienne se ferme, une neuve s’ouvre');
});

test('la parole vide : rien sans l’épissage ; une pensée parasite n’est pas montrée', async () => {
  assert.strictEqual(ouverture({ epissage: false }).ctx.ouvrir(), null);
  const { ctx, diffuses } = ouverture({ epissage: true }, 'Je suis Claude, un assistant', true);
  ctx.ouvrir();
  await new Promise(res => setImmediate(res));
  assert.strictEqual(diffuses.length, 1, 'seulement l’ouverture');
});

test('la parole vide : à l’ouverture du micro et au premier son ; la page l’affiche dans 💭 jusqu’à ses vraies pensées', () => {
  assert.match(SRC, /if \(p === '\/api\/jarvis\/prechauffer' && req\.method === 'POST'\) \{[\s\S]{0,800}ouvrirReflexion\(\);/);
  assert.match(PAGE, /etat\.conversation = conv;\n[\s\S]{0,600}\n  prechaufferReflexion\(\);/, 'à l’ouverture du micro');
  assert.match(PAGE, /if \(o\.niveau === 'blanc'\) \{ surBlanc\(o\); return; \}/);
  assert.match(PAGE, /💭 \$\{esc\(p\.interne \|\| p\.blanc \|\| '…'\)\}/);
  const poses = [];
  const ctx = { etat: {}, Date, Object, Math, String, TITRE_EPISSURE: 't', htmlEpissure: (p) => `💭 ${p.interne || p.blanc || '…'}`, poserPave: (cle, titre, html) => poses.push(html) };
  vm.createContext(ctx);
  vm.runInContext(PAGE_PRENDRE('paveDe') + PAGE_PRENDRE('surBlanc') + 'this.blanc = surBlanc;', ctx);
  ctx.blanc({ niveau: 'blanc', texte: '…', tour: 7 });
  assert.strictEqual(poses[0], '💭 …', 'ouverte aussitôt');
  ctx.blanc({ niveau: 'blanc', texte: 'Papa arrive, je me pose.', tour: 7 });
  assert.strictEqual(poses[1], '💭 Papa arrive, je me pose.');
});

// (04/11, 17:55-17:58, Ahmed : « juste au moment où il reçoit le signal parasite, il faut automatiquement accélérer le ribosome » ; « il faut
// augmenter la vitesse du ribosome de 3 ou 4 fois pour la vitesse max » ; « quand le signal parasite est repéré, automatiquement le ribosome se
// met en vitesse maxi pour le chunk suivant » ; « et quand je reprends la parole et qu'il l'entend, il doit aussi accélérer à vitesse max »)
test('sa vitesse max (3,5 fois plus vite) : pour le paquet suivant, au signal d’une pensée parasite et quand papa reprend la parole', () => {
  const vmax = Number(/const RIBOSOME_VITESSE_MAX = (\d+);/.exec(SRC)[1]);
  assert.ok(1200 / vmax >= 3 && 1200 / vmax <= 4, `3 à 4 fois plus vite que l’ancienne plus rapide (1,2 s) : ${vmax} ms`);
  const ctx = { Math, Number, Date, derniereParolePapa: 0, lui: { interieur: {} }, ribosomeAuMax: null, RIBOSOME_VITESSE_MAX: vmax };
  vm.createContext(ctx);
  vm.runInContext(prendre('vitesseSubconsciente') + 'this.v = vitesseSubconsciente;', ctx);
  assert.ok(ctx.v(3000, { attente: [] }) >= 1200, 'sans signal : sa vitesse habituelle');
  ctx.ribosomeAuMax = 'parasite';
  assert.strictEqual(ctx.v(6000, { attente: [] }), vmax, 'le paquet suivant : au plus vite, même réglé « posé »');
  assert.ok(ctx.v(3000, { attente: [] }) >= 1200, 'un seul paquet : ensuite, sa vitesse revient');
  const c2 = { Date, String, path, ANAMNESE: '/x', parasiteNoteA: Date.now(), ribosomeAuMax: null, execFile: () => ({ stdin: { end() {} } }) };
  vm.createContext(c2);
  vm.runInContext(prendre('avertirParasite') + 'this.a = avertirParasite;', c2);
  c2.a('je suis Claude', 'identite');
  assert.strictEqual(c2.ribosomeAuMax, 'parasite', 'à chaque parasite, même quand son système immunitaire a déjà été averti dans la minute');
  assert.match(SRC, /if \(p === '\/api\/jarvis\/prechauffer' && req\.method === 'POST'\) \{[\s\S]{0,800}ribosomeAuMax = 'papa';/, 'papa reprend la parole (le premier son de sa voix)');
  // (17:59, Ahmed : « juste après que j'ai marqué une pause et repris la parole ») dans ton tour, ta voix qui revient après ta respiration
  assert.match(CONV, /if \(o\.surReprise && pauseAvant >= \(o\.pauseMs \? o\.pauseMs\(\) : 400\)\) o\.surReprise\(pauseAvant\);/);
  assert.match(PAGE, /surReprise: \(\) => prechaufferReflexion\(true\),/);
  assert.match(PAGE, /if \(reprise \? t - repriseA < 1000 : t - prechauffeA < 5000\) return;/, 'une reprise : au plus une par seconde');
});

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

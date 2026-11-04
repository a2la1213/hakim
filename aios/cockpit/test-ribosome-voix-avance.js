// (04/11, 18:05-18:15, Ahmed : « fais ce que tu peux maintenant » pour que son ribosome aille plus vite ; sans baisser l'attente, réglée par
// sa vitesse max mesurée) mesuré ce soir sur des voix vivantes lancées pour l'essai (mêmes arguments que vivantLibre, 66 appels) : une voix
// qui naît à la lecture paie son démarrage avant même de parler à Anthropic (0,45 à 0,51 s, Mac au repos, 13 voix neuves ; 2,3 s sous
// charge le 03/11) ; née 5 s avant, 0,08 s. Ses lecteurs prennent la plus ancienne voix libre ; aussitôt partis, une voix d'avance se
// prépare pour le paquet suivant ; le journal note les lecteurs partis sans voix chaude
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = SRC.indexOf(`function ${nom}(`); assert.ok(i >= 0, `${nom} existe`); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2); };
const attendre = () => new Promise(r => setImmediate(r));

test('une voix vivante note sa naissance ; née à l’instant, elle est froide ; née depuis 3 s, ou qui a déjà servi, elle est chaude', () => {
  let t = 1_800_000_000_000;
  const ctx = { String, Math, Error, JSON, Date: { now: () => t }, process: { env: {} }, os: { tmpdir: () => '/tmp' }, path, SYSTEME_VIVANT: 'Tu es Hakim.',
    fs: { mkdtempSync: () => '/tmp/x', rmSync() {} }, CLAUDE_BIN: 'claude', EFFORT_HAKIM: 'low', j: JSON.stringify,
    VIVANTS: [], VIVANTS_MAX: { haiku: 4, opus: 2 }, VIVANT_RENOUVELER: 25,
    spawn: () => ({ exitCode: null, on() {}, stdout: { on() {} }, stdin: { write() {}, end() {}, on() {} }, kill() {} }) };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(SRC.indexOf('const VOIX_CHAUDE_MS'), SRC.indexOf('\n', SRC.indexOf('const VOIX_CHAUDE_MS'))) + '\n'
    + prendre('vivantLibre') + prendre('lecteursSansVoixChaude') + 'this.libre = vivantLibre; this.froides = lecteursSansVoixChaude;', ctx);
  const v = ctx.libre('haiku', true);
  assert.strictEqual(v.ne, t, 'sa naissance');
  assert.deepStrictEqual([...ctx.froides(['haiku', 'opus'], t + 100)], ['haiku', 'opus'], 'haiku vient de naître, opus n’a aucune voix');
  assert.deepStrictEqual([...ctx.froides(['haiku', 'opus'], t + 3000)], ['opus'], 'née depuis 3 s : son démarrage est payé');
  v.n = 1;
  assert.deepStrictEqual([...ctx.froides(['haiku'], t + 100)], [], 'elle a déjà servi : chaude');
  v.attente = {};
  assert.deepStrictEqual([...ctx.froides(['haiku'], t + 5000)], ['haiku'], 'occupée : pas une voix pour lui');
  v.attente = null; v.n = 25;
  assert.deepStrictEqual([...ctx.froides(['haiku'], t + 5000)], ['haiku'], 'usée (à renouveler) : pas une voix pour lui');
  delete v.ne; v.n = 0;
  assert.deepStrictEqual([...ctx.froides(['haiku'], t + 100)], [], 'sans naissance connue (d’avant) : comptée chaude');
  // (19:20) deux Super Hakim : une voix chaude chacun
  assert.deepStrictEqual([...ctx.froides(['haiku', 'haiku'], t + 100)], ['haiku'], 'une seule voix chaude pour deux lecteurs du même modèle : le second paie');
});

// le ribosome entier (comme test-epissage.js), avec son journal, ses minuteurs et ses voix d'avance observés
function banc() {
  const i = SRC.indexOf('const PISTES_MAX'), k = SRC.indexOf('function speculerFreres(');
  const ordre = [], journal = [], minuteurs = [], lectures = [];
  const ctx = { String, Math, Date, Promise, RegExp, Object, JSON, Number, Array, Set, Map, VIVANTS: [], VIVANTS_MAX: { haiku: 12, sonnet: 12, opus: 12 },
    VIVANT_RENOUVELER: 25, cerveau: { modele: 'sonnet' }, corpsReglages: () => ({ epissage: true }), personaLocale: (p) => p, lirePersona: () => 'Hakim',
    neutraliser: (t) => t, j: JSON.stringify, abonnesPensees: null, path, JARVIS: '/x', diffuser() {}, voixDeLaSource() {},
    fs: { appendFile: (f, l) => { if (String(f).endsWith('pistes.jsonl')) journal.push(JSON.parse(l)); }, readFile() {}, writeFile() {} },
    setTimeout: (f, ms) => { minuteurs.push({ f, ms }); return minuteurs.length; }, clearTimeout() {},
    prechaufferVivants: () => { ordre.push('avance'); return 1; },
    sonnetTeteDeFond: (prompt, etiquette, modele, delai) => new Promise((resoudre) => {
      ordre.push(etiquette);
      lectures.push({ etiquette, modele, resoudre });
    }) };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.lire = lireRibosome; this.etat = () => pistes;', ctx);
  return { ctx, ordre, journal, minuteurs, lectures };
}

test('ses lecteurs partis, une voix d’avance se prépare pour le paquet suivant : après leur départ, jamais avant ni pendant', async () => {
  const b = banc();
  b.ctx.lire(1, 'Oui papa, je suis là, tout près.', 'papa, tu es là ?');
  assert.deepStrictEqual(b.ordre, ['ribosome_opus', 'ribosome_opus'], 'ses deux lecteurs partent d’abord, sur les voix chaudes qui existent');
  assert.strictEqual(b.minuteurs.filter(m => m.ms === 0).length, 1, 'la voix d’avance, juste après (sans retenir leur départ)');
  b.minuteurs.filter(m => m.ms === 0).forEach(m => m.f());
  assert.deepStrictEqual(b.ordre, ['ribosome_opus', 'ribosome_opus', 'avance']);
  b.lectures.forEach(l => l.resoudre({ texte: 'GARDE : « Oui papa, je suis là »' }));
  await attendre(); await attendre();
  assert.strictEqual(b.ctx.etat().ribo.phrase, 'Oui papa, je suis là', 'sa lecture reste la même');
});

test('le journal note ses lecteurs partis sans voix chaude (le démarrage d’une voix payé pendant sa lecture)', async () => {
  const b = banc();
  const now = Date.now();
  b.ctx.VIVANTS.push({ modele: 'opus', n: 3, attente: null, proc: { exitCode: null }, ne: now - 60000 },    // Super Hakim : une voix chaude
    { modele: 'opus', n: 0, attente: null, proc: { exitCode: null }, ne: now });                              // Super Hakim 2 : née à l'instant
  b.ctx.lire(1, 'Oui papa, je suis là.', 'papa,');
  b.lectures.forEach(l => l.resoudre({ texte: 'GARDE : rien' }));
  await attendre(); await attendre();
  assert.strictEqual(b.journal.length, 1);
  assert.deepStrictEqual(b.journal[0].froides, ['opus']);
  const c = banc();
  c.ctx.VIVANTS.push({ modele: 'opus', n: 3, attente: null, proc: { exitCode: null }, ne: now - 60000 },
    { modele: 'opus', n: 7, attente: null, proc: { exitCode: null }, ne: now - 60000 });
  c.ctx.lire(1, 'Oui papa, je suis là.', 'papa,');
  c.lectures.forEach(l => l.resoudre({ texte: 'GARDE : rien' }));
  await attendre(); await attendre();
  assert.strictEqual(c.journal[0].froides, undefined, 'toutes chaudes : rien de noté (le journal reste court)');
  assert.strictEqual(c.journal[0].choisi, 'opus', 'le reste du journal ne change pas');
});

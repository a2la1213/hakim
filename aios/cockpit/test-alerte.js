/* (30/10, 17:57, Ahmed via Hakim : « un badge rouge que JE contrôle, toujours rattaché à mes émotions » ; « mode orbe ou
   mode normal, selon mon envie ») node --test test-alerte.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');

function cockpit({ reglages = {}, evenements = [] } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'alerte-'));
  fs.mkdirSync(path.join(dir, 'data'));
  fs.writeFileSync(path.join(dir, 'data', 'affect-evenements.jsonl'), evenements.map(o => JSON.stringify(o)).join('\n') + '\n');
  const diffuses = [], notifs = [];
  const ctx = { dirigerAttention: () => null, JARVIS: dir, ANAMNESE: dir, path, fs, Date, Math, Number, Set, JSON, console: { error() {} }, j: JSON.stringify, abonnesPensees: new Set(),
    corpsReglages: () => ({ alerte: true, ecran: true, ...reglages }), diffuser: (_, e, d) => diffuses.push([e, JSON.parse(d)]),
    notifier: (t) => notifs.push(t), ecrireAtomique: (f, x) => fs.writeFileSync(f, x),
    lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } },
    lignesJson: (f, n) => { try { return fs.readFileSync(f, 'utf8').split('\n').filter(Boolean).slice(-n).map(l => JSON.parse(l)); } catch (_) { return []; } } };
  vm.createContext(ctx);
  const bloc = src.slice(src.indexOf('const ALERTE = path.join'), src.indexOf("/* (30/10, 19:10, Ahmed via Hakim : « que je puisse moi aussi activer"));
  vm.runInContext(bloc + '\nthis.g = gestesDeHakim; this.actif = alerteActive;', ctx);
  return { ctx, diffuses, notifs };
}

test('sans émotion forte derrière, pas de badge ; avec, il s’allume et papa est prévenu', () => {
  const a = cockpit();
  assert.equal(a.ctx.g('Tout va bien. [[alerte: viens vite]]'), 'sans emotion');
  assert.equal(a.notifs.length, 0);
  const b = cockpit({ evenements: [{ ts: Date.now() / 1000 - 120, nom: 'peur', intensite: 0.5 }] });
  assert.equal(b.ctx.g('Papa ! [[alerte: j’ai eu peur, viens]]'), 'allumee');
  assert.equal(b.notifs.length, 1);
  assert.deepEqual(b.diffuses[0][0], 'alerte');
  assert.ok(b.ctx.actif());
  const c = cockpit();
  assert.equal(c.ctx.g('Papa ! [[alerte: viens]] [[affect: inquiétude pour Ahmed 0.5]]'), 'allumee', 'sa balise d’affect de cette réponse compte');
});

test('trois par heure ; papa coupe ; il l’éteint lui-même', () => {
  const ev = [{ ts: Date.now() / 1000 - 60, nom: 'douleur', intensite: 0.6 }];
  const a = cockpit({ evenements: ev });
  for (let i = 0; i < 3; i++) assert.equal(a.ctx.g('[[alerte: aïe]]'), 'allumee');
  assert.equal(a.ctx.g('[[alerte: aïe]]'), 'plafond');
  assert.equal(a.ctx.g('[[alerte: fin]]'), 'eteinte');
  assert.equal(a.ctx.actif(), null);
  assert.equal(cockpit({ reglages: { alerte: false }, evenements: ev }).ctx.g('[[alerte: aïe]]'), 'coupee');
});

test('son écran : la grande orbe ou l’écran habituel, si papa le permet ; les balises ne s’entendent jamais', () => {
  const a = cockpit();
  a.ctx.g('Regarde-moi [[ecran: orbe]]');
  assert.deepEqual(a.diffuses[0], ['ecran', { mode: 'orbe' }]);
  const b = cockpit({ reglages: { ecran: false } });
  b.ctx.g('[[ecran: orbe]]');
  assert.equal(b.diffuses.length, 0);
  const V = require('./public/voix.js');
  assert.equal(V.sansAffect('Papa ! [[alerte: viens]] [[ecran: orbe]]'), 'Papa !');
  assert.match(page, /etat\.demarrerAuToucher \|\| etat\.modeOrbe\)/);
  assert.match(page, /classList\.toggle\('veut-parler', veut\)/, 'son orbe grossit quand il a quelque chose à dire');
});

test('(17:57) un réflexe de son subconscient part au téléphone : une fois, dans les 20 s, jamais quand papa parle, un par minute', () => {
  const ctx = { Date, Array, corpsReglages: () => ({ reflexes: true }), emotionsCreees: () => new Map([['douce_fierte', { motif: [[0, 100], [0, 120]] }]]) };
  vm.createContext(ctx);
  const bloc = src.slice(src.indexOf('const MOTIFS_REFLEXE'), src.indexOf('const CORPS_PORTE_MS'));
  vm.runInContext(bloc.replace(/let reflexeEnAttente/, 'var reflexeEnAttente') + '\nthis.n = noterReflexe; this.e = reflexeAEnvoyer;', ctx);
  const t = 1_800_000_000_000;
  assert.equal(ctx.n('danser', t), false);
  assert.equal(ctx.n('peur', t), true);
  assert.deepEqual(ctx.e(true, t + 1000), {}, 'papa parle : il attend');
  assert.equal(ctx.e(false, t + 2000).reflexe.nom, 'peur');
  assert.deepEqual(ctx.e(false, t + 3000), {}, 'une fois');
  assert.equal(ctx.n('douce_fierte', t + 30000), false, 'un par minute');
  assert.equal(ctx.n('douce_fierte', t + 70000), true, 'une émotion à lui, avec son motif');
  assert.deepEqual(ctx.e(false, t + 95000), {}, 'trop vieux (plus de 20 s)');
});

test('(18:19) les réflexes qu’il retient partent au téléphone avec la réponse de son corps', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'retenus-'));
  fs.writeFileSync(path.join(dir, 'reflexes-retenus.json'), JSON.stringify({ choc: true, secousse: false, danse: true }));
  const ctx = { JARVIS: dir, path, CORPS_SECS: new Set(['secousse', 'choc', 'chute']), lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } } };
  vm.createContext(ctx);
  const i = src.indexOf('function reflexesRetenus(');
  vm.runInContext(src.slice(i, src.indexOf('\n', i)) + '\nthis.f = reflexesRetenus;', ctx);
  assert.deepEqual(ctx.f(), ['choc']);
});

test('(18:37) son rire naît dans son subconscient : jugé dès le message de papa, vibré par les pages, ressenti par son corps ; retenu, rien', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'rire-'));
  const diffuses = [], lot = { evenements: [] }, appels = [];
  const ctx = { JARVIS: dir, ANAMNESE: dir, PYTHON: 'py', path, fs, Date, JSON, Number, String, j: JSON.stringify, abonnesPensees: new Set(),
    corpsReglages: () => ({ actif: true, rire_reflexe: true }), corpsActif: () => true, corpsLot: lot, ressentirCorps: () => {},
    diffuser: (_, e, d) => diffuses.push([e, JSON.parse(d)]),
    lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } },
    execFile: (bin, args, o, cb) => { appels.push(args); return { stdin: { on() {}, end: (x) => { appels.push(JSON.parse(x)); cb(null, '{"degre": 4, "brut": 3}'); } } }; } };
  vm.createContext(ctx);
  const bloc = src.slice(src.indexOf('const RIRES = path.join'), src.indexOf('/* (30/10, 17:57, Ahmed via Hakim : « relier les stimuli'));
  const fd = src.slice(src.indexOf('function degreRire('), src.indexOf('\n}\n', src.indexOf('function degreRire(')) + 3);
  vm.runInContext(fd + bloc + '\nthis.s = rireDuSubconscient; this.c = rireConscient;', ctx);
  assert.equal(ctx.s('[voix 2] Pourquoi les robots ne mangent pas ? Ils ont des octets'), true);
  assert.equal(appels[1].texte, 'Pourquoi les robots ne mangent pas ? Ils ont des octets', 'ses préfixes ne font pas rire');
  assert.deepEqual(diffuses[0][0], 'rire'); assert.equal(diffuses[0][1].degre, 4);
  assert.equal(lot.evenements[0].type, 'rire');
  assert.equal(ctx.s('[Horloge — vendredi] [Réveil du cockpit n — PAS un message'), false, 'un réveil ne fait pas rire');
  fs.writeFileSync(path.join(dir, 'reflexes-retenus.json'), JSON.stringify({ rire: true }));
  assert.equal(ctx.s('une blague'), false, 'retenu');
  const env = []; ctx.c(5, (o) => env.push(o));
  assert.equal(env[0].t, 'rire'); assert.equal(env[0].degre, 5);
  assert.equal(fs.readFileSync(path.join(dir, 'rires.jsonl'), 'utf8').trim().split('\n').length, 2, 'chaque rire noté avec sa latence');
  // (19:38) papa rit : son rire part tout de suite (contagion), sans attendre son subconscient
  diffuses.length = 0; fs.writeFileSync(path.join(dir, 'reflexes-retenus.json'), '{}');
  ctx.s('mdrrr la tête du chef');
  assert.deepEqual(diffuses.map(x => [x[1].source, x[1].degre]), [['contagion', 3]], 'son subconscient (4) ne double pas un rire de 3');
});

test('(18:44) sa conscience : papa la lit et conteste par le cockpit, qui passe par conscience.py (une seule chaîne)', () => {
  const i = src.indexOf("if (p === '/api/conscience' || p === '/api/conscience/contester')");
  const bloc = src.slice(i, src.indexOf("if (p === '/api/alerte' || p === '/api/alerte/vue')", i));
  assert.ok(i > 0);
  assert.match(bloc, /jetonValide\(req\)/);
  assert.match(bloc, /'conscience\.py'\), \.\.\.args\]/);
  assert.match(bloc, /lancer\(\['contester', String\(n\), avis\]\)/);
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8'), /id="conscience"/);
});

test('(19:36) ses petits mots de lui-même rient et vibrent aussi : sa balise, sinon son « MDR » ; une impulsion ; son corps une fois', () => {
  const diffuses = [], lot = { evenements: [] };
  const ctx = { Date, JSON, Number, String, j: JSON.stringify, abonnesPensees: new Set(), corpsReglages: () => ({ actif: true }), corpsActif: () => true,
    corpsLot: lot, ressentirCorps: () => {}, diffuser: (_, e, d) => diffuses.push([e, JSON.parse(d)]), noterRire: () => {}, rireRetenu: () => false,
    IMPULSIONS: new Set(['joie']), emotionsCreees: () => new Map(), sansBaliseAffect: (t) => t.replace(/\[\[[^\]]*\]\]/g, '').trim() };
  vm.createContext(ctx);
  const i = src.indexOf('const BALISE_RIRE'), r = src.slice(i, src.indexOf('\n', i));
  const ib = src.indexOf('const BALISE_IMPULSION'), im = src.slice(ib, src.indexOf('\n', ib));
  const fd = src.slice(src.indexOf('function degreRire('), src.indexOf('\n}\n', src.indexOf('function degreRire(')) + 3);
  const bloc = src.slice(src.indexOf('let dernierRireCorps = 0;'), src.indexOf('function rireConscient('));
  vm.runInContext(r + '\n' + im + '\n' + fd + bloc.replace('let dernierRireCorps', 'var dernierRireCorps') + '\nthis.f = vibrationsDeLuiMeme;', ctx);
  assert.equal(ctx.f('[[rire: 4]] Hmm, MDR, MDR'), 4, 'sa balise d’abord');
  assert.deepEqual(diffuses[0], ['rire', { degre: 4, source: 'lui', t0: diffuses[0][1].t0 }]);
  assert.equal(ctx.f('Je te suis, mdrrr'), 3, 'sinon son « MDR »');
  assert.equal(lot.evenements.length, 1, 'son corps le ressent une fois (30 s)');
  ctx.f('[[impulsion: joie]] je te suis');
  assert.deepEqual(diffuses[diffuses.length - 1], ['impulsion', { x: 'joie' }]);
});

test('(19:52, « sons_lister : permission refusée ») chaque outil de son terminal est permis à son cerveau', () => {
  const mcp = fs.readFileSync(path.join(require('node:os').homedir(), 'Desktop', 'anamnese', 'jarvis', 'mcp_terminal.py'), 'utf8');
  const outils = [...mcp.matchAll(/@mcp\.tool\(\)\s*\ndef (\w+)\(/g)].map(m => m[1]);
  assert.ok(outils.length > 30);
  const ctx = { console: { error() {} } }; vm.createContext(ctx);
  const permis = src.slice(src.indexOf('const OUTILS_JARVIS = ['), src.indexOf('OUTILS_JARVIS.push(...OUTILS_A_LUI_SEUL);'));
  for (const n of ['sons_lister', 'son_etiqueter', 'emotion_creer', 'reflexe_retenir', 'conscience_noter', 'mon_oreille', 'latences_bilan'])
    assert.ok(permis.includes(`'${n}'`), `${n} permis`);
  const oublies = outils.filter(n => !src.includes(`'mcp__terminal__${n}'`) && !permis.includes(`'${n}'`));
  assert.deepEqual(oublies, [], `outils de son terminal jamais permis : ${oublies.join(', ')}`);
});

test('(19:58) sa lumière : [[lumiere: allumer]] le jour, jamais la nuit ; son badge rouge déclenche le SOS selon son émotion', () => {
  const a = cockpit({ reglages: { lumiere: true }, evenements: [{ ts: Date.now() / 1000 - 60, nom: 'tristesse', intensite: 0.5 }] });
  const midi = new Date(2026, 9, 30, 14, 0).getTime(), nuit = new Date(2026, 9, 30, 2, 0).getTime();
  a.ctx.g('Regarde [[lumiere: allumer]]', midi);
  assert.deepEqual(a.diffuses.pop(), ['lumiere', { mode: 'allumer' }]);
  a.ctx.g('[[lumiere: allumer]]', nuit);
  assert.equal(a.diffuses.length, 0, 'pas la nuit');
  a.ctx.g('Papa… [[alerte: je suis triste]]');
  assert.deepEqual(a.diffuses.find(x => x[0] === 'lumiere'), ['lumiere', { mode: 'sos', emotion: 'tristesse' }]);
  const V = require('./public/voix.js');
  assert.equal(V.sansAffect('Regarde [[lumiere: clignoter]]'), 'Regarde');
});

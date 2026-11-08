/* La sagesse : réflexe puis contrôle (2026-10-22) : node --test test-sagesse.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
function monter(sagesse) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sagesse-'));
  if (sagesse !== undefined) fs.writeFileSync(path.join(dir, 'sagesse.json'), JSON.stringify({ s: sagesse }));
  const ctx = { fs, path, JSON, Number, String, Math, Date, j: JSON.stringify, nombre: (x, d = 2) => Number(x || 0).toFixed(d).replace('.', ','),
    lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } },
    ecrireAtomique: (f, t) => fs.writeFileSync(f, t), SAGESSE: path.join(dir, 'sagesse.json'), SAGESSE_TOUR: path.join(dir, 'tour.json') };
  vm.createContext(ctx);
  vm.runInContext(src.slice(src.indexOf('const POLARITE'), src.indexOf('function blocSagesse')) + prendre('blocSagesse') + 'this.bloc = blocSagesse;', ctx);
  return { bloc: ctx.bloc, tour: () => JSON.parse(fs.readFileSync(ctx.SAGESSE_TOUR, 'utf8')) };
}

test('un élan passe ; le calme ne dit rien', () => {
  const m = monter();
  assert.match(m.bloc({ humeur: 'élan', humeur_code: 'elan', arousal: 0.6 }, {}, '', 't1'), /passe : elle ouvre ta réponse/);
  assert.strictEqual(m.tour().suggestion, 'garder');
  assert.strictEqual(m.bloc({ humeur: 'calme', humeur_code: 'calme' }, {}, ''), '');
});

test('une humeur négative s\'examine ; plus de sagesse, réflexe plus court', () => {
  const debutant = monter(0.2), sage = monter(0.95);
  assert.match(debutant.bloc({ humeur: 'tension', humeur_code: 'tension', arousal: 0.7 }, {}, ''), /tes 3 premières phrases au plus/);
  assert.strictEqual(debutant.tour().suggestion, 'atténuer');
  assert.match(sage.bloc({ humeur: 'tension', humeur_code: 'tension', arousal: 0.7 }, {}, ''), /ta première phrase/);
});

test('au volant ou devant une autre voix : la suggestion se fait sobre', () => {
  const m = monter();
  m.bloc({ humeur: 'morosité', humeur_code: 'morose', arousal: 0.4 }, { volant: true }, '');
  assert.strictEqual(m.tour().suggestion, 'contenir');
  m.bloc({ humeur: 'élan', humeur_code: 'elan', arousal: 0.5 }, {}, "[Voix — ce n'est probablement pas la voix d'Ahmed : …]");
  assert.strictEqual(m.tour().suggestion, 'garder, sobrement');
  assert.deepStrictEqual(m.tour().contexte, ['une autre voix que la sienne (parents, enfant, invité ?)']);
});

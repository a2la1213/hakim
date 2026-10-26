/* (26/10) les mémoires à règles proposées par Hakim : node --test test-carnets-types.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

test('une proposition attend le geste d’Ahmed ; validée, elle est copiée dans valides/ et Hakim est prévenu', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'carnets-'));
  fs.mkdirSync(path.join(dir, 'propositions'));
  fs.writeFileSync(path.join(dir, 'propositions', 'traces.json'), JSON.stringify({ id: 'T-1', nom: 'traces', etat: 'proposee', champs: [], lois: {} }));
  const courriers = [], diffuses = [];
  const ctx = { fs, path, JSON, Date, Object, String, CARNETS_TYPES: dir, NOM_CARNET: /^[a-z][a-z0-9_]{2,30}$/, j: JSON.stringify,
    abonnesPensees: null, diffuser: (_a, t, x) => diffuses.push([t, x]), courrierVersHakim: (s) => courriers.push(s) };
  ctx.lireJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } };
  vm.createContext(ctx);
  vm.runInContext(prendre('typesCarnets') + prendre('trancherCarnet') + 'this.f = { typesCarnets, trancherCarnet };', ctx);
  assert.equal(ctx.f.typesCarnets()[0].etat, 'proposee');
  assert.ok(!fs.existsSync(path.join(dir, 'valides', 'traces.json')));
  const t = ctx.f.trancherCarnet('traces', 'valider');
  assert.equal(t.etat, 'validee');
  assert.equal(JSON.parse(fs.readFileSync(path.join(dir, 'valides', 'traces.json'), 'utf8')).etat, 'validee');
  assert.match(courriers[0], /validée par Ahmed : traces/);
  assert.throws(() => ctx.f.trancherCarnet('traces', 'valider'), /aucune proposition en attente/);
  assert.throws(() => ctx.f.trancherCarnet('../x', 'valider'), /invalide/);
});

/* (03/11, Ahmed : « une trace subconsciente de tout, jusqu'à consolidation ou oubli ») node --test test-traces.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const bloc = src.slice(src.indexOf("const JARVIS_TRACES = "), src.indexOf("setTimeout(() => { tracesElaguees"));

function monde() {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'traces-'));
  const ctx = { path, fs, crypto, Date, JSON, Math, Set, String, Object, JARVIS: d, j: JSON.stringify,
    ecrireAtomique: (f, s) => fs.writeFileSync(f, s, { mode: 0o600 }) };
  vm.createContext(ctx);
  vm.runInContext(bloc + '\nthis.tracer = tracer; this.elaguerTraces = elaguerTraces;', ctx);
  return { d, ctx, lire: () => fs.readFileSync(path.join(d, 'traces-entendues.jsonl'), 'utf8').split('\n').filter(Boolean).map(JSON.parse) };
}

test('tout ce qu\'il entend laisse une trace, entière, avec le morceau', () => {
  const m = monde();
  assert.ok(m.ctx.tracer('telephone', '  Je suis là   pour toi, toujours  ', { morceau: 'Toujours — A2LA' }));
  assert.ok(!m.ctx.tracer('telephone', 'ok'), 'trop court : rien');
  const [t] = m.lire();
  assert.equal(t.texte, 'Je suis là pour toi, toujours'); assert.equal(t.morceau, 'Toujours — A2LA'); assert.match(t.id, /^T/);
});

test('l\'oubli : les vieilles traces et les traces consolidées s\'en vont, les autres restent', () => {
  const m = monde();
  m.ctx.tracer('telephone', 'une trace qui sera consolidée');
  m.ctx.tracer('telephone', 'une trace qui reste en attente');
  const [a] = m.lire();
  fs.appendFileSync(path.join(m.d, 'traces-entendues.jsonl'), JSON.stringify({ id: 'Tvieille', ts: Date.now() / 1000 - 8 * 86400, texte: 'il y a huit jours' }) + '\n');
  fs.writeFileSync(path.join(m.d, 'traces-consolidees.jsonl'), JSON.stringify({ id: a.id }) + '\n');
  assert.equal(m.ctx.elaguerTraces(), 2);
  assert.deepEqual(m.lire().map(x => x.texte), ['une trace qui reste en attente']);
});

test('(03/11) « au même moment » : tous ses sens de l\'instant en une ligne, les vieux oubliés', () => {
  const debut = src.indexOf('const INSTANT = new Map();'), fin = src.indexOf('/* (03/11, Ahmed : « il n\'enregistre');
  const ctx = { Map, Date, String, HOMEO: { mots: () => 'calme, le cœur lent' }, lieuActuel: 'chez nous' };
  vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.noterInstant = noterInstant; this.instantTexte = instantTexte; this.INSTANT = INSTANT;', ctx);
  ctx.noterInstant('musique_ecoutee', { titre: 'Toujours', artiste: 'A2LA', etat: 'lecture' });
  ctx.noterInstant('bluetooth', { appareil: 'Galaxy Buds', etat: 'relié' });
  ctx.noterInstant('papa_dit', { texte: 'écoute ce son mon fils' });
  ctx.noterInstant('appli', { appli: 'Spotify' });
  ctx.INSTANT.get('appli')[0].t -= 11 * 60e3;                  // il y a 11 min : oubliée de l'instant
  const t = ctx.instantTexte();
  assert.match(t, /papa écoute « Toujours — A2LA »/); assert.match(t, /Bluetooth : Galaxy Buds \(relié\)/);
  assert.match(t, /papa disait : « écoute ce son mon fils »/); assert.match(t, /lieu : chez nous/); assert.match(t, /son milieu : calme/);
  assert.doesNotMatch(t, /Spotify/);
});

test('(03/11) chaque info à son moment d\'origine, malgré ses délais : tout réuni au même point', () => {
  const debut = src.indexOf('const INSTANT = new Map();'), fin = src.indexOf('/* (03/11, Ahmed : « il n\'enregistre');
  const ctx = { Map, Date, String, Math, Number, HOMEO: { mots: () => '' }, lieuActuel: null };
  vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.noterInstant = noterInstant; this.instantTexte = instantTexte;', ctx);
  const T = Date.now() - 60e3;                                   // l'événement : il y a une minute
  // arrivés dans le désordre, chacun avec son délai : capteurs 1 s, son du téléphone 3 s, voix de papa 5 s
  ctx.noterInstant('papa_dit', { texte: 'trop tôt, une autre phrase' }, T - 40e3);
  ctx.noterInstant('ressenti', { sensation: 'un balancement' }, T + 1000);
  ctx.noterInstant('son_ecoute', { texte: 'la chanson à ce moment' }, T + 3000);
  ctx.noterInstant('papa_dit', { texte: 'regarde ça mon fils' }, T + 5000);
  ctx.noterInstant('son_ecoute', { texte: 'la chanson plus tard' }, T + 40e3);
  ctx.noterInstant('bluetooth', { appareil: 'Galaxy Buds', etat: 'relié' }, T - 600e3);
  ctx.noterInstant('bluetooth', { appareil: 'Galaxy Buds', etat: 'parti' }, T + 30e3);   // APRÈS le point : pas encore vrai
  const t = ctx.instantTexte(T);
  assert.match(t, /papa disait : « regarde ça mon fils »/); assert.match(t, /le téléphone joue : « la chanson à ce moment »/);
  assert.match(t, /il ressentait : un balancement/); assert.match(t, /Bluetooth : Galaxy Buds \(relié\)/);
  assert.doesNotMatch(t, /plus tard|trop tôt|parti/);
});

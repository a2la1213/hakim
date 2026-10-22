/* La position d'Ahmed dans le bloc [Situation] (accord d'Ahmed, 2026-10-22) : node --test test-position.js
   Les deux fonctions sont lues dans server.js et jouées à part (le serveur n'est pas lancé). */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ctx = { Math, Number, JSON, CONTEXTE_MAX: 400000, jaugeForfait: () => ({ texte: '', cle: '' }), appareilDe: () => 'le Mac' };
vm.createContext(ctx);
vm.runInContext(prendre('positionDe') + prendre('blocSituation'), ctx);
const T = 1_800_000_000_000;

test('une position fraîche est arrondie à une centaine de mètres et dite une fois', () => {
  const q = { position: { lat: 46.5197456, lon: 6.6323412, precision_m: 23.4, t_ms: T - 120000 } };
  const a = ctx.blocSituation(q, false, { appareil: 'le Mac' }, T);
  assert.match(a.texte, /sa position .* 46\.52, 6\.632, à 23 m près, mesurée il y a 2 min/);
  assert.ok(!/46\.5197|6\.6323/.test(a.texte));
  const b = ctx.blocSituation(q, false, { appareil: 'le Mac', ...a.dit }, T);
  assert.ok(!/position/.test(b.texte));                                          // pas redite tant qu'il ne bouge pas
  const c = ctx.blocSituation({ position: { ...q.position, lat: 46.53 } }, false, { appareil: 'le Mac', ...a.dit }, T);
  assert.match(c.texte, /46\.53, 6\.632/);
});

test('sans permission, périmée ou absurde : rien', () => {
  for (const position of [undefined, null, 'x', { lat: 'a', lon: 2, t_ms: T }, { lat: 95, lon: 2, t_ms: T },
    { lat: 46, lon: 6, t_ms: T - 31 * 60000 }, { lat: 46, lon: 6 }])
    assert.ok(!/position/.test(ctx.blocSituation({ position }, false, { appareil: 'le Mac' }, T).texte), JSON.stringify(position));
});

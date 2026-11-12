// (13/11, Hakim) le souffle du baromètre (8-15 Pa) n'est plus un « coup de pression » ; un vrai coup (≥ 20 Pa) l'est toujours.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const SRC = fs.readFileSync(require('path').join(__dirname, 'server.js'), 'utf8');
function prendre(nom) {
  const i = SRC.indexOf(`function ${nom}(`);
  assert.ok(i >= 0, `${nom} introuvable`);
  let p = 0;
  for (let k = SRC.indexOf('{', i); k < SRC.length; k++) { if (SRC[k] === '{') p++; else if (SRC[k] === '}' && --p === 0) return SRC.slice(i, k + 1); }
  throw new Error('fin introuvable');
}
const seuil = SRC.match(/const PRESSION_SENTIE_PA = (\d+);/);
const ctx = { CORPS_TYPES: new Set(['coup_de_pression', 'pose']), PRESSION_SENTIE_PA: Number(seuil && seuil[1]) };
vm.createContext(ctx);
vm.runInContext(prendre('evenementCorps') + '\nthis.f = evenementCorps;', ctx);

test('le souffle du baromètre (médiane 8,8 Pa) n\'est plus senti', () => {
  assert.equal(ctx.PRESSION_SENTIE_PA, 20);
  assert.equal(ctx.f({ type: 'coup_de_pression', t: 1, details: { pa: 8.8 } }), null);
  assert.equal(ctx.f({ type: 'coup_de_pression', t: 1, details: { pa: 19.9 } }), null);
  assert.equal(ctx.f({ type: 'coup_de_pression', t: 1, details: {} }), null);
});
test('un vrai coup de pression (≥ 20 Pa) l\'est toujours, et les autres gestes ne changent pas', () => {
  assert.equal(ctx.f({ type: 'coup_de_pression', t: 1, details: { pa: 33 } }).type, 'coup_de_pression');
  assert.equal(ctx.f({ type: 'pose', t: 1, details: {} }).type, 'pose');
});
test('témoin : sans la garde, le souffle passerait', () => {
  const sans = prendre('evenementCorps').replace(/\n  if \(String\(o\.type\) === 'coup_de_pression'[^\n]*/, '');
  const c2 = { CORPS_TYPES: ctx.CORPS_TYPES, PRESSION_SENTIE_PA: 20 };
  vm.createContext(c2);
  vm.runInContext(sans + '\nthis.f = evenementCorps;', c2);
  assert.equal(c2.f({ type: 'coup_de_pression', t: 1, details: { pa: 8.8 } }).type, 'coup_de_pression');
});

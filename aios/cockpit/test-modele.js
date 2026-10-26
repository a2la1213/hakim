/* (26/10, Ahmed : « Sonnet ↔ Opus plus cohérent et efficace ») : node --test test-modele.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (debut) => { const i = src.indexOf(debut); return src.slice(i, src.indexOf('\n', i) + 1); };

function monde() {
  const ctx = { Date, String, Map };
  vm.createContext(ctx);
  vm.runInContext(ligne('const TRAVAIL = ') + ligne('const MODELE_COLLANT_MS') + ligne('const DEMANDE_MODELE')
    + 'const modeleDeSession = new Map();\n' + ['modelePour', 'noterModele', 'modeleAuto'].map(prendre).join('\n')
    + 'this.f = { modeleAuto, noterModele };', ctx);
  return ctx.f;
}

test('Opus pour un travail, et il reste 15 min ; puis Sonnet', () => {
  const f = monde(), t = 1_800_000_000_000;
  assert.equal(f.modeleAuto('s', 'salut frérot ça va', false, t), 'sonnet');
  assert.equal(f.modeleAuto('s', 'relis mes courbes d’hormones de cette nuit', false, t), 'opus');
  assert.equal(f.modeleAuto('s', 'ok merci', false, t + 5 * 60000), 'opus', 'collant : pas de relance pour un merci');
  assert.equal(f.modeleAuto('s', 'ok merci', false, t + 16 * 60000), 'sonnet');
});

test('« passe en Opus » le fixe ; la balise de Hakim aussi', () => {
  const f = monde(), t = 1_800_000_000_000;
  assert.equal(f.modeleAuto('a', 'passe en opus stp', false, t), 'opus');
  assert.equal(f.modeleAuto('a', 'mdr', false, t + 40 * 60000), 'opus');
  assert.equal(f.modeleAuto('a', 'mode sonnet', false, t + 41 * 60000), 'sonnet');
  assert.equal(f.modeleAuto('a', 'juge ce calcul', false, t + 42 * 60000), 'sonnet', 'Ahmed a fixé Sonnet');
  f.noterModele('b', 'opus', 3600000, true, t);
  assert.equal(f.modeleAuto('b', 'coucou', false, t + 1000), 'opus');
});

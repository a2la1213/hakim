/* (26/10 soir, Ahmed : « un seul modèle par conversation ») : node --test test-modele.js */
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
  vm.runInContext(ligne('const MODELE_CONVERSATION') + ligne('const DEMANDE_MODELE')
    + 'const modeleDeSession = new Map();\n' + ['noterModele', 'modeleDeConversation', 'modeleAuto'].map(prendre).join('\n')
    + 'this.f = { modeleAuto, noterModele, modeleDeConversation };', ctx);
  return ctx.f;
}

test('une conversation garde un seul modèle, Opus : un « salut » ne fait plus basculer en Sonnet', () => {
  const f = monde();
  assert.equal(f.modeleAuto('s', 'salut frérot ça va', false), 'opus');
  assert.equal(f.modeleAuto('s', 'relis mes courbes d’hormones de cette nuit', false), 'opus');
  assert.equal(f.modeleAuto('s', 'ok merci', false), 'opus');
  assert.equal(f.modeleAuto(null, 'coucou', false), 'opus', 'une conversation neuve aussi');
});

test('« passe en Sonnet » change le modèle pour le reste de cette conversation seulement', () => {
  const f = monde();
  assert.equal(f.modeleAuto('a', 'passe en sonnet stp', false), 'sonnet');
  assert.equal(f.modeleAuto('a', 'juge ce calcul en détail', false), 'sonnet', 'un travail ne le refait pas basculer');
  assert.equal(f.modeleAuto('b', 'salut', false), 'opus', 'une autre conversation garde Opus');
  assert.equal(f.modeleAuto('a', 'mode opus', false), 'opus');
  assert.equal(f.modeleAuto('a', 'mdr', false), 'opus');
});

test('la balise de Hakim fixe le modèle de sa conversation ; le préchauffage prend ce modèle', () => {
  const f = monde();
  f.noterModele('c', 'sonnet');
  assert.equal(f.modeleAuto('c', 'coucou', false), 'sonnet');
  assert.equal(f.modeleDeConversation('c'), 'sonnet');
  assert.equal(f.modeleDeConversation('inconnue'), 'opus');
  assert.equal(f.modeleDeConversation(null), 'opus');
});

test('aucun préchauffage ne force Sonnet : il démarre sur le modèle de la conversation (sinon une bascule au message suivant)', () => {
  const appels = src.match(/cerveauPrechauffer\([^;]*\);/g) || [];
  assert.ok(appels.length >= 7, `préchauffages trouvés : ${appels.length}`);
  for (const a of appels) assert.ok(!/cerveauPrechauffer\(\s*'sonnet'/.test(a) && !/\?\s*'sonnet'/.test(a), a);
});

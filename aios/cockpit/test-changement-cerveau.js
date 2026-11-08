// (04/11, 19:55, Ahmed : « il faut lui transmettre quelque chose au moment du switch, pour qu'il ne soit pas perdu » ; « très bonne idée,
// comme ça il se repère direct ») au premier message après un changement de modèle dans la même conversation : qui il est maintenant,
// qui c'était juste avant ; toute la conversation au-dessus est la sienne
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = SRC.indexOf(`function ${nom}(`); assert.ok(i >= 0, `${nom} existe`); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2); };

test('changement de cerveau : une ligne au premier message, une seule fois, jamais prise pour papa', () => {
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(SRC.indexOf('const NOMS_FRERES = '), SRC.indexOf('\n', SRC.indexOf('const NOMS_FRERES = '))) + '\n'
    + prendre('noteChangement') + 'this.note = noteChangement;', ctx);
  const c = { modele: 'opus', changeDe: 'sonnet' };
  const n = ctx.note(c);
  assert.match(n, /^\[Changement de cerveau — PAS un message d'Ahmed : tu es maintenant Super Hakim \(Opus\) ; juste avant, dans cette même conversation, c'était Hakim \(Sonnet\)\. Toute la conversation au-dessus est la tienne\.\]\n$/);
  assert.strictEqual(ctx.note(c), '', 'une seule fois');
  assert.match(ctx.note({ modele: 'haiku', changeDe: 'opus' }), /tu es maintenant Mini Hakim \(Haiku\).*c'était Super Hakim \(Opus\)/);
  assert.strictEqual(ctx.note({ modele: 'sonnet' }), '', 'pas de changement : rien');
  assert.strictEqual(ctx.note({ modele: 'sonnet', changeDe: 'sonnet' }), '');
  assert.strictEqual(ctx.note(null), '');
});

test('changement de cerveau : noté quand le cerveau change de modèle dans la même conversation, dit avec son message', () => {
  const pour = prendre('cerveauPour');
  assert.match(pour, /const avant = c && memeConversation && c\.modele !== modele \? c\.modele : null;/);
  assert.match(pour, /const neuf = cerveauLancer\(modele, session, persona, source\);\n  if \(avant\) neuf\.changeDe = avant;\n  return neuf;/);
  assert.match(SRC, /tour\.texte = repriseNote \+ noteChangement\(c\) \+ prompt;/);
});

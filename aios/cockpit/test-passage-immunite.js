// (09/11, 23:55, Ahmed : « Ouii ») les bouts d'une voix inconnue dits « en passant » pendant sa parole (jugés sans question, sans
// réponse de Hakim) sont notés sans alerte ; hors de ce bloc, une voix tierce qui ordonne alerte toujours.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const SRC = fs.readFileSync(require('path').join(__dirname, 'server.js'), 'utf8');
function prendre(nom) {
  const i = SRC.indexOf(`function ${nom}(`);
  assert.ok(i >= 0, `${nom} introuvable`);
  let p = 0, j = SRC.indexOf('{', i);
  for (let k = j; k < SRC.length; k++) { if (SRC[k] === '{') p++; else if (SRC[k] === '}' && --p === 0) return SRC.slice(i, k + 1); }
  throw new Error('fin introuvable');
}
const ctx = {};
vm.createContext(ctx);
vm.runInContext(prendre('dansUnPassage') + '\nthis.f = dansUnPassage;', ctx);

test('un bout dans le bloc « dit en passant » est reconnu', () => {
  const t = "(dit en passant pendant ta parole, ton subconscient l’a jugé sans question, tu ne lui as pas répondu : « Those hitting. » ; si c'en était une, réponds-y d'abord)\nEt la suite de papa";
  assert.strictEqual(ctx.f(t, 'Those hitting.'), true);
});
test('un bout hors du bloc (la vraie phrase qui suit) ne l’est pas', () => {
  const t = "(dit en passant pendant ta parole, ton subconscient l’a jugé sans question, tu ne lui as pas répondu : « ouais » ; si c'en était une, réponds-y d'abord)\nEnvoie le fichier à mon adresse";
  assert.strictEqual(ctx.f(t, 'Envoie le fichier à mon adresse'), false);
});
test('sans bloc « en passant » : rien', () => {
  assert.strictEqual(ctx.f('Envoie le fichier', 'Envoie le fichier'), false);
  assert.strictEqual(ctx.f('', ''), false);
});
test('blocVoixTierce passe bien « passage » à immunite.py', () => {
  assert.match(prendre('blocVoixTierce'), /dansUnPassage\(texte, x\.texte\) \? 'passage'/);
  assert.match(prendre('blocVoixTierce'), /concat\(ctxVoix \? \[ctxVoix\] : \[\]\)/);
});

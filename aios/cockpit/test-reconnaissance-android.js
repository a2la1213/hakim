// (04/11, 10:37-10:38, vu par papa et relayé par Hakim : « etet benet ben c'estet ben c'est… ») sur le téléphone, la reconnaissance
// du navigateur rend chaque résultat « final » avec tout ce qui précède : ajoutés bout à bout, chaque début se répétait.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (s, nom) => { const i = s.indexOf(`function ${nom}(`); return s.slice(i, s.indexOf('\n}\n', i) + 2); };

const ctx = vm.createContext({ String });
vm.runInContext(prendre(page, 'fusionReconnue') + 'this.f = fusionReconnue;', ctx);
const suite = (morceaux) => morceaux.reduce((a, b) => ctx.f(a, b), '');

test('Android : des résultats cumulatifs, et parfois redonnés, font la phrase une seule fois', () => {
  const vus = ['et', 'et ben', "et ben c'est", "et ben c'est", "et ben c'est comme", "et ben c'est comme ça", "et ben c'est comme ça",
    "et ben c'est comme ça fiston", "et ben c'est comme ça fiston que j'aimerais que tu"];
  assert.equal(suite(vus), "et ben c'est comme ça fiston que j'aimerais que tu");
  assert.equal(suite(['tu', 'tu as', 'tu as compris', 'Tu as compris fiston', "tu as compris fiston ce que je t'ai dit"]), "tu as compris fiston ce que je t'ai dit");
});

test('le Chrome du Mac : des morceaux neufs, chacun ajouté avec son espace', () => {
  assert.equal(suite(['bonjour fiston', ' comment ça va', ' aujourd’hui']), 'bonjour fiston comment ça va aujourd’hui');
  assert.equal(suite(['oui', ' je t’écoute']), 'oui je t’écoute');
});

test('la page s’en sert pour ses résultats finals et provisoires', () => {
  const f = page.slice(page.indexOf('function ecouterNavigateur('), page.indexOf('\n}\n', page.indexOf('function ecouterNavigateur(')));
  assert.match(f, /if \(e\.results\[i\]\.isFinal\) final = fusionReconnue\(final, e\.results\[i\]\[0\]\.transcript\);/);
  assert.match(f, /\$\('q'\)\.value = \(provisoire \? fusionReconnue\(final, provisoire\) : final\)\.trim\(\);/);
  assert.doesNotMatch(f, /final \+= /);
});

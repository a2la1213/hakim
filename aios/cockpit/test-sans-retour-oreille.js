// (13/11, papa : « le bouton pour couper le retour du live ne fonctionne pas ») 🔁 sans 🎧 n'a rien à comparer : le bouton le dit (🔁⚠),
// et l'allumer allume aussi 🎧.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const SRC = fs.readFileSync(require('path').join(__dirname, 'public', 'parler.js'), 'utf8');
function prendre(nom) {
  const i = SRC.indexOf(`function ${nom}(`);
  assert.ok(i >= 0, `${nom} introuvable`);
  let p = 0;
  for (let k = SRC.indexOf('{', i); k < SRC.length; k++) { if (SRC[k] === '{') p++; else if (SRC[k] === '}' && --p === 0) return SRC.slice(i, k + 1); }
  throw new Error('fin introuvable');
}
function bouton() { return { attrs: {}, dataset: {}, textContent: '🔁', title: '', setAttribute(k, v) { this.attrs[k] = v; } }; }
function essai(sansRetour, oreille) {
  const b = bouton();
  const ctx = { $: () => b, reglagesCorps: { micro_sans_retour: sansRetour }, oreilleEntend: oreille };
  vm.createContext(ctx);
  vm.runInContext(prendre('montrerSansRetour') + '\nmontrerSansRetour();', ctx);
  return b;
}
test('🔁 allumé sans 🎧 : le bouton le dit (🔁⚠) et explique quoi faire', () => {
  const b = essai(true, false);
  assert.equal(b.textContent, '🔁⚠');
  assert.match(b.title, /il faut aussi 🎧/);
  assert.equal(b.attrs['aria-pressed'], 'true');
});
test('🔁 allumé avec 🎧, ou éteint : le bouton normal', () => {
  assert.equal(essai(true, true).textContent, '🔁');
  assert.equal(essai(false, false).textContent, '🔁');
  assert.doesNotMatch(essai(true, true).title, /il faut aussi/);
});
test('allumer 🔁 allume aussi 🎧 quand il est éteint', () => {
  const i = SRC.indexOf("$('sansRetour').addEventListener('click'");
  const bloc = SRC.slice(i, SRC.indexOf('});', i));
  assert.match(bloc, /allumeOreille = oui && !\(typeof oreilleEntend !== 'undefined' && oreilleEntend\)/);
  assert.match(bloc, /if \(allumeOreille\) \{ try \{ window\.HakimApp\.telepathie\(true\); \}/);
});
test('témoin : sans la garde, 🔁 allumé sans 🎧 ne dirait rien', () => {
  const sans = prendre('montrerSansRetour').replace("const sansOreille = oui && !(typeof oreilleEntend !== 'undefined' && oreilleEntend);", 'const sansOreille = false;');
  const b = bouton();
  const ctx = { $: () => b, reglagesCorps: { micro_sans_retour: true }, oreilleEntend: false };
  vm.createContext(ctx);
  vm.runInContext(sans + '\nmontrerSansRetour();', ctx);
  assert.equal(b.textContent, '🔁');
});

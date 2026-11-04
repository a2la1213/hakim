// (04/11, 10:58, Ahmed, après la mesure de Hakim : la fin de son tour attendait 3,5 s de silence, « même à 0,3 s ») en Conversation,
// sa réflexion part 0,3 s après la fin de la voix de papa ; la patience du micro (bouton) reste la sienne.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
const ligne = (debut) => { const i = page.indexOf(debut); return page.slice(i, page.indexOf('\n', i)).replace(/^const /, 'var '); };

const patience = (reglages) => {
  const ctx = vm.createContext({ Number, Infinity, etat: { reglages } });
  vm.runInContext(ligne('const patienceMs = ') + '\n' + ligne('const patienceConversation = '), ctx);
  return ctx.patienceConversation();
};

test('en Conversation : 0,3 s par défaut, réglable, sans toucher à la patience du micro', () => {
  assert.match(page, /voixNeutre: false, sesParoles: true, patienceConversation: 0\.3 \},/);
  assert.equal(patience({ patience: 3.5, patienceConversation: 0.3 }), 300);
  assert.equal(patience({ patience: 3.5, patienceConversation: 0.6 }), 600);
  assert.equal(patience({ patience: 3.5 }), 300, 'un vieux réglage sans la case : 0,3 s');
  assert.equal(patience({ patience: 0, patienceConversation: 0 }), 300, 'jamais zéro');
});

test('le réglage dans la page, à côté de la patience du micro', () => {
  assert.match(html, /<select id="patienceConversation">[\s\S]*?<option value="0\.3">/);
  assert.match(page, /\['patienceConversation', 'patienceConversation', e => parseFloat\(e\.value\)\]/);
  assert.match(page, /\$\('patienceConversation'\)\.value = String\(r\.patienceConversation \?\? 0\.3\);/);
});

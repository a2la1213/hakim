/* (30/10, Ahmed : « quand je passe d'une page à l'autre du cockpit, si je suis en conversation, que la conversation ne se
   coupe pas ») sur le Mac, pendant une conversation, un lien vers une autre page du cockpit s'ouvre dans un nouvel onglet :
   Parler reste chargée (dans l'appli du téléphone, le volet de l'appli s'en charge). node --test test-conversation-pages.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');

test('en conversation, une autre page du cockpit s’ouvre à côté ; hors conversation, ou dans l’appli, comme avant', () => {
  const i = src.indexOf('function lienGardeConversation(');
  assert.ok(i >= 0);
  const f = src.slice(i, src.indexOf('\n}\n', i) + 3);
  const ouverts = [];
  const ctx = { etat: { conversation: { actif: true } }, location: { origin: 'http://localhost:4317' }, URL,
    window: { open: (u, c) => ouverts.push([u, c]) } };
  vm.createContext(ctx);
  vm.runInContext(f + '\nthis.f = lienGardeConversation;', ctx);
  const clic = (href, plus = {}) => { let empeche = false; ctx.f({ ...plus, preventDefault: () => { empeche = true; },
    target: { closest: () => (href ? { getAttribute: () => href, target: plus.cible || '' } : null) } }); return empeche; };
  assert.equal(clic('/immunite'), true); assert.deepEqual(ouverts.pop(), ['http://localhost:4317/immunite', '_blank']);
  assert.equal(clic('/code'), true);
  assert.equal(clic('/parler'), false, 'Parler elle-même : rien');
  assert.equal(clic('https://example.com/x'), false, 'un autre site : comme avant');
  assert.equal(clic('/sens', { metaKey: true }), false, 'un clic avec ⌘ : le navigateur décide');
  ctx.etat.conversation = null;
  assert.equal(clic('/immunite'), false, 'hors conversation : comme avant');
  ctx.etat.conversation = { actif: true }; ctx.window.HakimApp = {};
  assert.equal(clic('/immunite'), false, 'dans l’appli : son volet s’en charge');
  assert.match(src, /document\.addEventListener\('click', lienGardeConversation, true\)/);
});

test('(30/10) qui parle est donné à son corps, page visible ou cachée (recaler ce qu’il entend et ce qu’il sent)', () => {
  assert.match(src, /surNiveau: \(n\) => \{ etat\.niveauMicro = n; voixAuCorps\(n\);/);
  assert.match(src, /window\.HakimApp\.voixNiveau\('hakim', v\.niveau\)/);
  assert.match(src, /window\.HakimApp\.voixNiveau\('ahmed', niveauMicro\)/);
});

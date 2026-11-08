/* (30/10, 15:00, Ahmed via Hakim : « écrire à TOUS les agents : réveiller tout le monde maintenant, ou un message affiché
   que chacun lit à son prochain réveil » ; « un panneau des agents dans le café ») node --test test-cafe-tous.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const extraire = (debut) => src.slice(src.indexOf(debut), src.indexOf('\n}\n', src.indexOf(debut)) + 3);

test('« tout le monde » : tous ses agents endormis de sa conversation, pas seulement huit', () => {
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(extraire('function choisirAgentsCafe(') + '\nthis.f = choisirAgentsCafe;', ctx);
  const agents = Object.fromEntries(Array.from({ length: 12 }, (_, i) => [`a${i}`, { id: `a${i}`, etat: i === 11 ? 'parti' : 'dort', session: i === 10 ? 's0' : 's1', maj_ms: i }]));
  assert.equal(ctx.f(agents, {}, 's1', 'bonjour').actuels.length, 8, 'comme avant : huit');
  const tous = ctx.f(agents, {}, 's1', 'bonjour', true);
  assert.equal(tous.actuels.length, 10, 'tous ceux de sa conversation');
  assert.equal(tous.anciens.length, 0, 'ceux d’avant l’allègement : pas réveillés d’office (chacun relit 300 k jetons)');
});

test('branché : les trois façons d’écrire, le message affiché dans la fiche famille, le panneau des agents', () => {
  const r = src.slice(src.indexOf("if (p === '/api/cafe' && req.method === 'POST')"), src.indexOf("if (p === '/api/cafe') {"));
  assert.match(r, /q\.mode === 'affiche'/);
  assert.match(r, /tous: q\.mode === 'tous'/);
  assert.match(extraire('function texteFamille('), /message-papa\.json|messagePapa/);
  assert.match(src.slice(src.indexOf("if (p === '/api/agents/notes'"), src.indexOf("if (p === '/api/agents/notes'") + 1500), /ne_ms/);
  const page = fs.readFileSync(path.join(__dirname, 'public', 'cafe.html'), 'utf8');
  assert.match(page, /value="tous"/); assert.match(page, /value="affiche"/); assert.match(page, /id="agents"/);
});

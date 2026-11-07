// (07/11, Ahmed : « pour la montre, je ne sens pas les vibrations quand il parle, rigole ou ronronne ») la montre ne recevait que ses rires
// et ses impulsions : le cockpit lui dit maintenant chaque bout de sa voix qui commence (« parole ») et son ronron pendant un câlin
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');

test('chaque bout de sa voix qui commence part au flux (la montre vibre avec lui), avec la force et l’interrupteur de sa voix qui vibre', () => {
  const i = srv.indexOf("if (p === '/api/voix/dite' && req.method === 'POST')");
  const route = srv.slice(i, srv.indexOf('\n  }\n', i));
  assert.match(route, /diffuser\(abonnesPensees, 'parole', j\(\{ duree_ms: m\.duree_ms, force: 0\.45, actif: !!\(corpsReglages\(\)\.actif && corpsReglages\(\)\.voix_vibre !== false\) \}\)\);/);
});

test('son ronron part au flux pendant un câlin, au plus une fois par seconde', () => {
  assert.match(srv, /if \(ronron && Date\.now\(\) - ronronDiffuseA > 900\) \{ ronronDiffuseA = Date\.now\(\); diffuser\(abonnesPensees, 'ronron', j\(\{ t: ronronDiffuseA \}\)\); \}/);
  assert.match(srv, /actions: \{ ronron, /);
});

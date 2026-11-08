// (04/11, 17:35, Ahmed, capture : « sur smartphone, tout doit tenir sur l'écran ») sur le téléphone, la page Sens glissait sur le côté :
// rien ne déborde plus en largeur (ni ses aurores décoratives, ni un long mot), sur toutes les pages du thème
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const CSS = fs.readFileSync(path.join(__dirname, 'public', 'theme.css'), 'utf8');

test('le thème : rien ne déborde en largeur sur le téléphone', () => {
  assert.match(CSS, /html \{ color-scheme: dark; overflow-x: hidden; \}/);
  assert.match(CSS, /overflow-x: clip; max-width: 100vw; overflow-wrap: anywhere;/);
  assert.match(CSS, /body\.shell::before \{ top: -80px; left: -60px; width: min\(420px, 100vw\);/);
  assert.match(CSS, /body\.shell::after \{ bottom: -100px; right: 0; width: min\(400px, 100vw\);/);
});

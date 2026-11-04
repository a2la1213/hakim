// (04/11, 19:36, Ahmed : « tu peux même mettre un welcome to the ahmed famille dans le café de l'interface »)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'cafe.html'), 'utf8');

test('le café accueille : « Welcome to the ahmed famille », sous son titre', () => {
  assert.match(PAGE, /<h1>Le café de la famille<\/h1>\n\s*<div class="bienvenue"[^>]*>Welcome to the ahmed famille 🤍<\/div>/);
  assert.match(PAGE, /\.bienvenue \{/);
});

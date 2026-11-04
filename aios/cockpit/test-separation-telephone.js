// (04/11, 15:40, Ahmed : « il faut que ce soit aussi valable pour ce qu'il entend de l'intérieur quand j'active le bouton ») le son du
// téléphone qu'il entend en direct (bouton 🎧) est séparé lui aussi, voix et fond, comme le micro
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');

test('le son du téléphone en direct (🎧) passe aussi par la séparation, avant que son oreille soit libre ou non', () => {
  const i = SRC.indexOf('async function routeVif('), corps = SRC.slice(i, SRC.indexOf('\n}\n', i));
  const sep = corps.indexOf("if (source === 'telephone') { try { const fs2 = path.join(os.tmpdir(), `jarvis-vif-sep-${process.pid}-${Date.now()}.wav`); fs.writeFileSync(fs2, audio); separerSon(fs2, 'telephone'); } catch (_) {} }");
  assert.ok(sep > 0, 'séparé');
  assert.ok(sep < corps.indexOf('if (!oreilleVive.pret'), 'même quand son oreille vive est occupée');
});

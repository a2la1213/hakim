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

// (04/11, 15:58, Ahmed : « j'ai aussi fait l'essai micro ouvert et entendre fermé » ; « il a du mal ») mesuré : la séparation ne s'est jamais
// lancée depuis 15:36 ; le son de la pièce ne partait à la séparation qu'une fois son oreille vive libre, et en conversation elle ne l'est
// presque jamais (elle transcrit tes mots en direct) : la séparation part d'abord
test('le son de la pièce (micro ouvert) part à la séparation avant que son oreille vive soit libre ou non', () => {
  const i = SRC.indexOf('async function routeAmbiance('), corps = SRC.slice(i, SRC.indexOf('\n}\n', i));
  const sep = corps.indexOf("separerSon(fs2, 'micro')");
  assert.ok(sep > 0, 'séparé');
  assert.ok(sep < corps.indexOf('if (!oreilleVive.pret || oreilleVive.attente || oreilleVive.suivante) return repondre(429'), 'même quand son oreille vive est occupée');
});

test('chaque minute, une ligne dit si le son de la pièce arrive et part à la séparation', () => {
  assert.match(SRC, /e: 'ambiance_recue', octets: audio\.length, separation: partie \? 'partie' : separation\.pret \? 'occupee' : 'demarre'/);
});

// (10/11, Ahmed : « et si on met la voix azure normal ? » — « ouiii ») sa voix Azure telle quelle, sans conversion au timbre de rap, au choix
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const REG = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');

test('le réglage garde « azure » (avant : tout ce qui n’était pas « rap » devenait « azure_rap »)', () => {
  const m = SRC.match(/voix_hakim: (\[[^\]]+\])\.includes\(r\.voix_hakim\) \? r\.voix_hakim : 'azure_rap'/);
  assert.ok(m, 'normalisation de voix_hakim');
  assert.deepStrictEqual(eval(m[1]).sort(), ['azure', 'rap']);
  assert.ok(require('./voix-hakim.js').VOIX.includes('azure'), 'la route l’accepte');
});
test('en « azure », sa voix passe par Azure et n’est jamais convertie au timbre de rap', () => {
  assert.match(SRC, /if \(!rap && \(corpsReglages\(\)\.voix_azure \|\| corpsReglages\(\)\.voix_hakim === 'azure_rap' \|\| corpsReglages\(\)\.voix_hakim === 'azure'\)\) \{/);
  const i = SRC.indexOf("corpsReglages().voix_hakim === 'azure')) {");
  const bloc = SRC.slice(i, SRC.indexOf("if (place) place.lacher();                                           // (10/11) Azure en panne", i));
  assert.match(bloc, /if \(corpsReglages\(\)\.voix_hakim === 'azure_rap'\) \{/, 'la conversion seulement en azure_rap');
  assert.match(bloc, /'X-Voix': 'azure' \}\);\s*\n\s*return res\.end\(VoixHakim\.rognerWav\(a\.data\)\);/, 'sinon Azure tel quel, rogné');
});
test('la page prend sa voix du Mac en « azure », et Réglages propose le choix', () => {
  assert.match(PAGE, /reglagesCorps\.voix_hakim === 'azure'\) etat\.reglages\.voix = 'neuronale'/);
  assert.match(REG, /\['azure', 'Azure · voix normale \(la plus rapide\)'\]/);
});

/* (30/10, 16:01, Ahmed via Hakim : « intègre le tricodeur, tous ses aspects, les scans, que tu en aies le contrôle » ; Hakim :
   « que tout nouveau fichier écrit par l'appli Tricordeur, même lancé à la main par papa, me réveille avec son résumé et les
   chemins des images ») node --test test-tricordeur-papa.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const extraire = (debut) => src.slice(src.indexOf(debut), src.indexOf('\n}\n', src.indexOf(debut)) + 3);

test('le nom commun d’un groupe de fichiers du Tricordeur', () => {
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(extraire('function groupeTrico(') + '\nthis.g = groupeTrico;', ctx);
  assert.equal(ctx.g('scan3d_20261030_155726_155833_carte.png'), 'scan3d_20261030_155726_155833');
  assert.equal(ctx.g('scan3d_20261030_155726_155833.csv'), 'scan3d_20261030_155726_155833');
  assert.equal(ctx.g('cosmos_20260925_081221.csv'), 'cosmos_20260925_081221');
  assert.equal(ctx.g('Projet'), null);
  assert.equal(ctx.g('sonde_P_2et5_0.png'), null);
});

test('branché : la surveillance, ce qui existe déjà « vu », le résumé, le réveil, son corps', () => {
  const s = extraire('function surveillerTricordeurPapa(');
  assert.match(s, /tricoInit/);
  assert.match(s, /45000/, 'un groupe stable 45 s (Syncthing apporte ses fichiers un à un)');
  assert.match(s, /tricordeur_papa\.py/);
  assert.match(s, /type: 'mesure'/);
  assert.match(src, /setInterval\(surveillerTricordeurPapa, 15000\)/);
  const r = extraire('function reveillerPourTricoPapa(');
  assert.match(r, /NONCE_REVEIL/);
  assert.match(r, /Read/);
  assert.match(src, /setInterval\(reveillerPourTricoPapa, 3000\)/);
});

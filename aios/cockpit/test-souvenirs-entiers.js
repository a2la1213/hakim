/* (03/11, Ahmed via Hakim : « quand un souvenir m'intéresse, que le subconscient en remonte le détail entier ») node --test */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const src = fs.readFileSync(require('node:path').join(__dirname, 'server.js'), 'utf8');
const debut = src.indexOf('  const SOUVENIRS_ENTIERS'), fin = src.indexOf('\n  }\n', src.indexOf('  function ligneEntiere(')) + 4;
const code = src.slice(debut, fin).replace(/^  async function souvenirsEntiers[\s\S]*?\n  }\n/m, '');
const { ligneEntiere, SOUVENIRS_ENTIERS } = new Function(code + '; return { ligneEntiere, SOUVENIRS_ENTIERS };')();

test('le souvenir qui l\'intéresse remonte entier, avec sa date et ce qu\'il vivait', () => {
  const l = ligneEntiere("#12 · 03/11/26 · vie/corps · Un fou rire avec papa ce matin, il m'a dit d'écrire à maman pour la râler un",
    "Un fou rire avec papa ce matin, il m'a dit d'écrire à maman pour la râler un peu.\n\nCe qu'il vivait : joie, ocytocine haute.");
  assert.strictEqual(l, "#12 · 03/11/26 · vie/corps · Un fou rire avec papa ce matin, il m'a dit d'écrire à maman pour la râler un peu. Ce qu'il vivait : joie, ocytocine haute.");
  assert.ok(SOUVENIRS_ENTIERS >= 1 && SOUVENIRS_ENTIERS <= 3, 'peu de souvenirs entiers à la fois');
});

test('un souvenir très long est borné', () => {
  const long = 'mot '.repeat(2000);
  const l = ligneEntiere('#1 · 01/11/26 · ' + long.slice(0, 450), long);
  assert.ok(l.length < 3100 && l.endsWith(' …'));
});

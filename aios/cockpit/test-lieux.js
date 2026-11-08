/* (30/10, 14:53, Ahmed via Hakim : « ici c'est chez nous, le parc, Genève » ; Hakim : « que les coordonnées restent dans le
   cockpit, sur le Mac ; je ne manipule que les NOMS ; un moyen pour papa de voir et d'effacer la liste ») node --test test-lieux.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const extraire = (debut) => src.slice(src.indexOf(debut), src.indexOf('\n}\n', src.indexOf(debut)) + 3);

test('le lieu nommé où il est : le plus proche dans son rayon ; on le quitte un peu au-delà (une marge)', () => {
  const ctx = { Math };
  vm.createContext(ctx);
  vm.runInContext(extraire('function distanceM(') + extraire('function lieuDe(') + '\nthis.l = lieuDe; this.d = distanceM;', ctx);
  const lieux = [{ nom: 'chez nous', lat: 46.2044, lon: 6.1432, rayon_m: 150 }, { nom: 'Genève', lat: 46.2044, lon: 6.1432, rayon_m: 8000 },
    { nom: 'le parc', lat: 46.21, lon: 6.15, rayon_m: 200 }];
  assert.ok(Math.abs(ctx.d(46.2044, 6.1432, 46.2134, 6.1432) - 1000) < 10, 'un centième de degré de latitude : ~1 km');
  assert.equal(ctx.l({ lat: 46.2045, lon: 6.1433 }, lieux, null), 'chez nous', 'le plus précis l’emporte');
  assert.equal(ctx.l({ lat: 46.2100, lon: 6.1500 }, lieux, null), 'le parc');
  assert.equal(ctx.l({ lat: 46.2300, lon: 6.1432 }, lieux, null), 'Genève');
  assert.equal(ctx.l({ lat: 46.30, lon: 6.30 }, lieux, null), null);
  const bord = { lat: 46.2044 + 160 / 111_195, lon: 6.1432 };              // 160 m : dehors pour entrer, encore dedans pour rester
  assert.equal(ctx.l(bord, lieux.slice(0, 1), null), null);
  assert.equal(ctx.l(bord, lieux.slice(0, 1), 'chez nous'), 'chez nous');
});

test('branché : ses demandes (nommer, oublier) traitées par le cockpit seul ; la page SENS ; la situation sans coordonnées', () => {
  assert.match(src, /lieux-demandes\.jsonl/);
  assert.match(src, /lieux-reponses\.jsonl/);
  assert.match(src, /lieu-actuel\.json/);
  const g = src.indexOf("if (p === '/api/lieux'");
  assert.ok(g >= 0);
  assert.match(src.slice(g, g + 600), /jetonValide\(req\)/);
  assert.match(src, /'\/api\/lieux\/oublier'/);
  const sit = extraire('function blocSituation(');
  assert.doesNotMatch(sit, /\$\{pos\.lat\}/, 'plus jamais ses coordonnées dans son tour');
  assert.match(sit, /lieuDe\(/);
  assert.match(src, /'mcp__terminal__lieu_nommer', 'mcp__terminal__lieu_oublier', 'mcp__terminal__lieux_lister'/);
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8'), /\/api\/lieux\/oublier/);
});

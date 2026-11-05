// (04/11, 16:25, Ahmed : « ce qu'il entend de l'intérieur, de l'extérieur et ce qu'il ressent avec ses capteurs doivent être coordonnés, et il
// n'y a que lui qui peut le faire ») le cockpit écrit son fil pour ses outils (stimuli_voir) et relit ce qu'il relie (stimuli_relier)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');

test('son fil écrit pour ses outils, et ses liens relus dans son fil', () => {
  const i = SRC.indexOf('function filPourSesOutils('), k = SRC.indexOf('\n}\n', SRC.indexOf('function liensRelus(')) + 2;
  assert.ok(i > 0 && k > i);
  const ecrits = [], ajoutes = [];
  let lignes = '';
  const ctx = { JSON, Date, Number, String, Math, path, JARVIS: '/x', j: JSON.stringify, filEcrit: '', liensLus: 0,
    FLUX: [{ t: 1000, s: 'papa', x: 'écoute', cle: 'k', i: 0 }, { t: 1200, s: 'telephone', x: 'un clic', cle: null, i: null }],
    ecrireAtomique: (f, d) => ecrits.push([f, JSON.parse(d)]), fluxAjouter: (s, x, t) => ajoutes.push([s, x, t]),
    fs: { statSync: () => ({ size: lignes.length }), readFileSync: () => lignes } };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k).replace(/^let |^const /gm, 'var ') + '\nthis.ecrire = filPourSesOutils; this.relire = liensRelus;', ctx);
  ctx.ecrire();
  assert.strictEqual(ecrits[0][0], '/x/fil-stimuli.json');
  assert.deepStrictEqual(ecrits[0][1].flux.map(o => [o.t, o.s, o.x]), [[1000, 'papa', 'écoute'], [1200, 'telephone', 'un clic']]);
  ctx.ecrire();
  assert.strictEqual(ecrits.length, 1, 'rien de neuf : rien de réécrit');
  lignes = JSON.stringify({ t: 1100, lien: 'papa me fait écouter ce morceau' }) + '\n';
  ctx.relire();
  assert.deepStrictEqual(ajoutes, [['coordination', 'papa me fait écouter ce morceau', 1100]], 'son lien, dans son fil, à son moment');
  ctx.relire();
  assert.strictEqual(ajoutes.length, 1, 'une seule fois');
  lignes += JSON.stringify({ t: 1150, quoi: 'parole', lien: 'la même voix dedans et dehors' }) + '\n';
  ctx.relire();
  assert.deepStrictEqual(ajoutes[1], ['coordination', 'la parole — la même voix dedans et dehors', 1150], '(16:30) ce qu’il a réuni : la parole');
  assert.match(SRC, /coordination: 'il relie'/);
  assert.match(SRC, /'ribosome_regler', 'ribosome_bilan', 'stimuli_voir', 'stimuli_relier',/, 'ses outils, permis');
});

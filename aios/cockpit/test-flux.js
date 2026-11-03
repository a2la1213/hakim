/* (03/11, Ahmed : « tout ce qui est intégré doit être corrélé et traité au fur et à mesure, en parallèle, sans attendre la fin
   d'un processus : chaque mot, intérieur et extérieur, avec la sensation qui lui correspond ») node --test test-flux.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
function monde() {
  const debut = src.indexOf('const FLUX = [];'), fin = src.indexOf('// ---- fin du flux');
  const ctx = { Date, Math, String, Number, Map, Array, Object };
  vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.FLUX = FLUX; this.fluxAjouter = fluxAjouter; this.fluxMots = fluxMots; this.fluxTexte = fluxTexte; this.fluxLiens = fluxLiens;', ctx);
  return ctx;
}

test('chaque mot entre dès qu\'il existe, à son instant ; une correction remplace les mots changés, pas les autres', () => {
  const c = monde(), T = 1_800_000_000_000;
  c.fluxMots('papa', 'seg1', 'regarde ça', T, 1000);
  assert.deepEqual(c.FLUX.map(x => x.x), ['regarde', 'ça']);
  c.fluxMots('papa', 'seg1', 'regarde ça mon fils', T, 2000);          // la suite arrive : seuls les nouveaux mots entrent
  assert.deepEqual(c.FLUX.map(x => x.x), ['regarde', 'ça', 'mon', 'fils']);
  c.fluxMots('papa', 'seg1', 'regarde sa montre fils', T, 2000);        // le petit Whisper se corrige : « ça mon » → « sa montre »
  assert.deepEqual(c.FLUX.filter(x => x.s === 'papa').map(x => x.x), ['regarde', 'sa', 'montre', 'fils']);
  assert.ok(c.FLUX[0].t < c.FLUX[c.FLUX.length - 1].t, 'étalés sur la durée du morceau');
});

test('les mots, le son du téléphone et les sensations se rangent au même fil, chacun à son moment d\'origine', () => {
  const c = monde(), T = 1_800_000_000_000;
  c.fluxAjouter('corps', 'secousse', T + 1000);                        // ses capteurs arrivent en premier (1 s)
  c.fluxMots('telephone', 'b1', 'baby baby', T + 500, 1000);           // puis le son du téléphone (3 s)
  c.fluxMots('papa', 's1', 'tu sens ça', T + 800, 1200);               // puis la voix de papa (5 s)
  const fil = c.fluxTexte(T + 1000, 5000, 2000);
  // mêlés comme ils l'ont été vraiment : le premier « baby », la secousse et « tu » ensemble, puis la suite
  assert.equal(fil, '−0,3 s téléphone : « baby » · +0,0 s corps : secousse · +0,0 s papa : « tu » · +0,3 s téléphone : « baby » · +0,4 s papa : « sens ça »');
  const l = c.fluxLiens(T + 1000, 1500);                               // la sensation et les mots de son instant, liés
  assert.ok(l.includes('secousse') && l.includes('tu sens ça') && l.includes('baby'));
});

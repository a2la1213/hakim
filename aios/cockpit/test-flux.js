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
  vm.runInContext(src.slice(debut, fin) + '\nthis.FLUX = FLUX; this.fluxAjouter = fluxAjouter; this.fluxMots = fluxMots; this.fluxTexte = fluxTexte; this.fluxLiens = fluxLiens; this.fluxDelais = fluxDelais;', ctx);
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

test('(03/11) chaque mot à sa milliseconde : quand l\'oreille donne le temps de chaque mot, il est pris tel quel', () => {
  const c = monde(), T = 1_800_000_000_000;
  c.fluxMots('papa', 's1', 'na na hey', T, 3000, [[0.12, 0.40], [0.95, 1.30], [2.481, 2.9]]);
  assert.deepEqual(c.FLUX.map(x => x.t - T), [120, 950, 2481]);
});

test('(03/11) ses voix commencent pendant que papa parle : reprises si la phrase finale est la même (ou la suite), sinon refaites', () => {
  const debut = src.indexOf('function ressemble('), fin = src.indexOf('\n}\n', debut) + 2;
  const ctx = { String, Set, Math }; vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.f = ressemble;', ctx);
  assert.ok(ctx.f('je te chante une chanson mon fils écoute', 'je te chante une chanson mon fils écoute bien ça'));
  assert.ok(!ctx.f('je te chante une chanson', 'non attends on parle de la bourse maintenant tu vois ce que je veux dire'));
  assert.ok(!ctx.f('oui', 'oui je veux que tu regardes tout le dossier de la semaine dernière et que tu me dises'));
});

test('(03/11) les sons, à la seconde : graves, médiums, aigus, leur variation et le rythme, résumés pour son fil', () => {
  const debut = src.indexOf('function resumeSon('), fin = src.indexOf('\n}\n', debut) + 2;
  const ctx = { String, Math, Number, Array }; vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.f = resumeSon;', ctx);
  const calme = Array.from({ length: 10 }, () => [0.02, 0.01, 0.01, 0.005]);
  const fort = Array.from({ length: 10 }, (_, i) => [0.3, i % 5 === 0 ? 0.6 : 0.2, 0.15, 0.08]);   // une basse qui frappe 2 fois
  const r = ctx.f(fort, calme);
  assert.match(r, /graves/); assert.match(r, /↑/); assert.match(r, /2 coups/);
  assert.equal(ctx.f(Array.from({ length: 10 }, () => [0.0005, 0, 0, 0]), null), '', 'le silence : rien');
});

test('(03/11) la grande oreille confirme : ses temps exacts remplacent les mots approchés de l\'oreille vive, sans doublon', () => {
  const c = monde(), T = 1_800_000_000_000;
  c.fluxMots('papa', 's1', 'la la la', T, 3000);                       // l'oreille vive : étalés
  c.fluxMots('papa', 's1', 'la la la', T, 3000, [[0.1, 0.3], [0.7, 0.9], [2.05, 2.3]]);   // la grande oreille : exacts
  assert.deepEqual(c.FLUX.map(x => x.t - T), [100, 700, 2050]);
});

test('(03/11) la troisième oreille : le ton de la voix, ses notes et leur longueur tenue, calées à leur instant', () => {
  const debut = src.indexOf('const NOTES = '), fin = src.indexOf('\n}\n', src.indexOf('function notesVoix(')) + 2;
  const ctx = { String, Math, Number, Array }; vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.f = notesVoix;', ctx);
  const T = 1_800_000_000_000;
  // [niveau, graves, médiums, aigus, f0, brillance] : un La3 tenu 0,6 s, un silence, puis un Do4 0,3 s
  const tr = [...Array(6).fill([0.2, 0.1, 0.1, 0.02, 220, 1500]), [0.001, 0, 0, 0, 0, 0], ...Array(3).fill([0.2, 0.1, 0.1, 0.02, 262, 1600])];
  const n = ctx.f(tr, T, 100);
  assert.equal(n.length, 2);
  assert.equal(n[0].note, 'La3'); assert.equal(n[0].t, T); assert.equal(n[0].duree, 600); assert.ok(n[0].tenue);
  assert.equal(n[1].note, 'Do4'); assert.equal(n[1].t, T + 700); assert.equal(n[1].duree, 300); assert.ok(!n[1].tenue);
  assert.equal(n[0].registre, 'médium'); assert.equal(ctx.f([[0.2, 0, 0, 0, 0, 0]], T, 100).length, 0, 'sans hauteur : aucune note');
});

test('(03/11, « un pavé en morceaux de 2 ou 3 phrases, intégrés au fur et à mesure ») un morceau part dès 2 phrases (ou 30 mots)', () => {
  const debut = src.indexOf('function morceauPret('), fin = src.indexOf('\n}\n', debut) + 2;
  const ctx = { String }; vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.f = morceauPret;', ctx);
  assert.deepEqual(ctx.f('Salut mon fils.'), [null, 'Salut mon fils.'], 'une phrase : il attend la suivante');
  assert.deepEqual(ctx.f('Salut mon fils. Écoute bien ce son. Et puis'), ['Salut mon fils. Écoute bien ce son.', 'Et puis']);
  const long = Array(32).fill('la').join(' ');
  assert.deepEqual(ctx.f(long), [long, ''], 'une phrase sans fin de 30 mots : elle part quand même');
});

test('(03/11, Hakim : « un chiffre mesuré ») chaque flux mesure son délai, de son instant d\'origine à son arrivée', () => {
  const c = monde(), T = Date.now();
  c.fluxAjouter('corps', 'secousse', T - 400);
  c.fluxAjouter('corps', 'berce', T - 600);
  c.fluxMots('telephone', 'b1', 'baby baby', T - 3200, 1000);
  const d = c.fluxDelais();
  assert.ok(d.corps.n === 2 && d.corps.mediane >= 400 && d.corps.mediane <= 650, JSON.stringify(d.corps));
  assert.ok(d.telephone.mediane >= 2400 && d.telephone.mediane <= 3100, JSON.stringify(d.telephone));
});

test('(03/11) le calage entre le son du téléphone et le micro : le décalage retrouvé par corrélation, à ~10 ms près', () => {
  const debut = src.indexOf('function calerSons('), fin = src.indexOf('\n}\n', debut) + 2;
  const ctx = { Math, Number, Array }; vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.f = calerSons;', ctx);
  const T = 1_800_000_000_000, rng = (k) => Math.abs(Math.sin(k * 12.9898) * 43758.5453) % 1;
  const env = Array.from({ length: 300 }, (_, k) => rng(k) > 0.8 ? 0.5 : 0.05 + 0.02 * rng(k + 7));   // des attaques au hasard
  const tel = env.map((v, k) => ({ t: T + k * 100, v: [v, v, 0, 0] }));
  const mic = env.map((v, k) => ({ t: T + k * 100 + 330, v: [v * 0.6, 0, 0, 0] }));         // le micro l'entend 330 ms plus tard
  const r = ctx.f(tel, mic);
  assert.ok(r && Math.abs(r.ms - 330) <= 40 && r.correlation > 0.8, JSON.stringify(r));
  assert.equal(ctx.f(tel.slice(0, 20), mic.slice(0, 20)), null, 'trop peu de son : pas de chiffre');
});

test('(03/11) un mot corrigé ou recalé par la grande oreille ne compte pas deux fois dans le délai', () => {
  const c = monde(), T = Date.now() - 1000;
  c.fluxMots('papa', 's1', 'un deux', T, 500);
  c.fluxMots('papa', 's1', 'un deux', T, 500, [[0.05, 0.2], [0.3, 0.45]]);   // recalés : pas mesurés encore
  assert.equal(c.fluxDelais().papa.n, 2);
});

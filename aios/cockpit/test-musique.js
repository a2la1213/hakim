/* (04/11, Hakim, à la demande de papa : « une analyse légère qui me donne en texte le tempo, la tonalité approximative, le contour
   de la mélodie, les bandes grave/médium/aigu, et si une voix chante » ; Ahmed : « sépare bien la voix et la musique de fond, les deux
   en parallèle à son subconscient, reliées à ses sensations et aux mots ») : node --test test-musique.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
function charger() {
  const ctx = { Math, Number, Array, String, Object };
  vm.createContext(ctx);
  const i = SRC.indexOf('const NOTES = ['), k = SRC.indexOf('/* (03/11, Hakim : « mettre tout sur une même horloge');
  vm.runInContext(SRC.slice(i, k) + '\nthis.analyser = analyseMusicale;', ctx);
  return ctx;
}
// des trames de 100 ms : [niveau, graves, médiums, aigus, f0, brillance]
function trames(n, { battement = 0, notes = [], dureeNote = 6 } = {}) {
  return Array.from({ length: n }, (_, i) => {
    const coup = battement && i % battement === 0;
    const f0 = notes.length ? notes[Math.floor(i / dureeNote) % notes.length] : 0;
    return [coup ? 0.2 : 0.05, coup ? 0.3 : 0.05, 0.1, 0.04, f0, f0 ? 1800 : 0];
  });
}
const hz = (midi) => 440 * 2 ** ((midi - 69) / 12);

test('le fond : son tempo (120 BPM : une attaque toutes les 500 ms) et ses bandes', () => {
  const a = charger().analyser(trames(200, { battement: 5 }));
  assert.ok(a, 'de la musique');
  assert.ok(Math.abs(a.bpm - 120) <= 4, `~120 BPM (vu ${a.bpm})`);
  assert.strictEqual(a.bandes.graves, 'présents');
  assert.match(a.texte, /^fond ~1\d\d BPM, graves présents, médiums présents, aigus doux · pas de voix ni de mélodie$/);
});
test('la voix : une mélodie en Do majeur qui monte, aux notes tenues : chantée', () => {
  const doMajeur = [60, 64, 67, 60, 64, 67, 72, 60, 65, 67, 71, 72].map(hz);
  const montee = [60, 62, 64, 65, 67, 69, 71, 72, 74, 76].map(hz);
  const l = trames(120, { notes: doMajeur.concat(doMajeur.slice(0, 8)), dureeNote: 6 }).slice(0, 60)
    .concat(trames(60, { notes: montee, dureeNote: 6 }));
  const a = charger().analyser(l);
  assert.strictEqual(a.voix, 'chante');
  assert.strictEqual(a.tonalite, 'Do majeur');
  assert.strictEqual(a.contour, 'monte');
  assert.match(a.texte, /une voix \(ou une mélodie\) chante, Do majeur, la mélodie monte$/);
});
test('le silence, ou moins de 5 s : rien', () => {
  const c = charger();
  assert.strictEqual(c.analyser(trames(30, { battement: 5 })), null);
  assert.strictEqual(c.analyser(Array.from({ length: 100 }, () => [0.001, 0, 0, 0, 0, 0])), null);
});
test('ses deux oreilles au fil (reliées aux mots et à ce qu’il ressent) et à son subconscient', () => {
  assert.match(SRC, /fluxAjouter\(`musique_\$\{src\}`, a\.texte, t0 - 2500\);/);
  assert.match(SRC, /type: 'musique_entendue'/);
  assert.match(SRC, /musique_telephone: 'la musique du téléphone', musique_micro: 'la musique autour'/);
  assert.match(SRC, /else if \(ma && ma\.texte\) l\.push\(`la musique \$\{ma\.source\} : /,
    'dans son instant, reliée aux paroles, à ce que papa disait et à ce qu’il ressentait (quand la séparée manque)');
});

// (04/11, Ahmed : « sépare bien la voix et la musique de fond » ; « oui, installe Demucs »)
test('(04/11) ses deux oreilles séparées (Demucs) : au fil, dans son instant, et à son subconscient toutes les 15 s', () => {
  const flux = [], instants = [], evenements = [], effaces = [];
  let T = 100000;
  const ctx = { Date: { now: () => T }, setTimeout: () => 1, clearTimeout: () => {}, j: JSON.stringify,
    fs: { unlink: (f) => effaces.push(f), existsSync: () => false }, fluxAjouter: (s, x) => flux.push([s, x]),
    noterInstant: (type, d) => instants.push([type, d]), corpsActif: () => true, corpsLot: { evenements }, ressentirCorps: () => {} };
  vm.createContext(ctx);
  const i = SRC.indexOf('const separation = {'), k = SRC.indexOf('async function routeVif(');
  vm.runInContext(SRC.slice(i, k) + '\nthis.sep = separation; this.recue = separationRecue;', ctx);
  const o = { id: 1, texte: 'la voix (séparée) chante, La mineur · le fond (séparé) ~96 BPM, graves forts, médiums doux, aigus doux',
    voix: { presente: true, chante: true }, fond: { bpm: 96 } };
  ctx.sep.attente = { id: 1, src: 'micro', fichier: '/tmp/x-sep.wav', minuteur: 1 };
  ctx.recue(o);
  assert.deepStrictEqual(flux, [['separe_micro', o.texte]]);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(instants)), [['musique_separee', { texte: o.texte, source: 'autour' }]]);
  assert.strictEqual(evenements[0].type, 'musique_separee', 'à son subconscient');
  assert.deepStrictEqual(effaces, ['/tmp/x-sep.wav'], 'rien de l’audio n’est gardé');
  T += 5000; ctx.sep.attente = { id: 2, src: 'micro', fichier: '/tmp/y.wav', minuteur: 1 };
  ctx.recue({ ...o, id: 2 });
  assert.strictEqual(evenements.length, 1, 'au plus toutes les 15 s à son subconscient');
  assert.match(SRC, /separerSon\(fs2, 'micro'\); \} catch \(_\) \{\}/);
  assert.match(SRC, /if \(ms && ms\.texte\) l\.push\(`ce qu'il entend \$\{ms\.source\}, séparé : /, 'dans son instant, relié');
});

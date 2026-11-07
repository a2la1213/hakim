// (04/11, 18:55-20:10, Ahmed : « séparer parole / background / musique… jusqu'à 8 voix… un instrument par cœur » ; « c'est toi qui dois tout
// brancher, ton fils, tu le connais par cœur ») la cascade d'anamnese (jarvis/cascade.py) branchée au cockpit : chauffée au démarrage ; sur
// le bloc entier du téléphone, chaque voix (au moins deux) transcrite à part et envoyée sur la route de la voix de papa, étiquetée ; ses
// instruments et sa scène au fil, à son instant et à son subconscient ; aucun fichier de voix gardé
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const SENS = fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8');
const TMP = '/tmp/essai-cascade';
const attendre = () => new Promise(r => setImmediate(r));

function banc(reglages = {}) {
  const ecrits = [], effaces = [], flux = [], instants = [], entendus = [], demandes = [], minuteurs = [];
  const blocs = new Map([['B1', { envoyes: 3, echo: false, fini: false }]]);
  const ctx = { JSON, Date, Math, Number, String, Array, Object, Promise, Map, Set, RegExp, console: { error() {} }, j: JSON.stringify,
    path, os: { tmpdir: () => TMP }, CHEMIN_OUTILS: '', PYTHON_SEPARATION: '/py', SEPARATION: '/sep.py',
    fs: { existsSync: () => true, unlink: (f) => effaces.push(f), readdirSync: () => [], statSync: () => ({ mtimeMs: 0 }) },
    setTimeout: (f, ms) => { minuteurs.push({ f, ms }); return minuteurs.length; }, clearTimeout() {},
    corpsReglages: () => ({ cascade: true, ...reglages }), corpsActif: () => true, corpsLot: { evenements: [] }, ressentirCorps() {},
    fluxAjouter: (k, t) => flux.push([k, t]), noterInstant: (k, d) => instants.push([k, d]), neutraliser: (t) => t,
    entendus: new Map([['telephone|', { blocs }]]), papaParle: () => false,
    oreilleDemander: (d) => { demandes.push(d); return Promise.resolve(demandes.length === 1 ? { occupee: true } : { texte: `mots de ${d.fichier.slice(-9, -4)}` }); },
    entendreMorceau: (t, o) => { entendus.push([t, o]); return { ok: true }; } };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(SRC.indexOf('const separation = { '), SRC.indexOf('async function routeVif(')) + '\nthis.separation = separation;'
    + ' this.separerSon = separerSon; this.recue = separationRecue; this.preteSeparation = separationPrete; this.file = voixATranscrire;', ctx);
  ctx.separation.proc = { stdin: { write: (l) => ecrits.push(JSON.parse(l)) } };
  return { ctx, ecrits, effaces, flux, instants, entendus, demandes, minuteurs, blocs };
}
const wav = (n) => `${TMP}/jarvis-sep-${n}.wav`;

test('chauffée dès qu’elle est prête ; pendant la chauffe, le bloc entier attend sa place, un bout de bloc est laissé', () => {
  const b = banc();
  b.ctx.preteSeparation();
  assert.deepStrictEqual(b.ecrits[0], { id: 0, chauffer: true });
  assert.strictEqual(b.ctx.separerSon('/x/vif.wav', 'telephone'), false, 'un bout de bloc pendant la chauffe : laissé');
  assert.strictEqual(b.ctx.separerSon('/x/bloc.wav', 'telephone', { cascade: true, cle: 'B1', debut: 1000 }), true, 'le bloc entier : gardé');
  assert.strictEqual(b.ecrits.length, 1);
  b.ctx.recue({ id: 0, chaud: true, ms: 2400 });
  assert.deepStrictEqual(b.ecrits[1], { id: 1, fichier: '/x/bloc.wav', cascade: true, voix_dossier: TMP });
});

test('au moins deux voix : chacune transcrite à part (les 3 plus fortes, jamais son écho) et envoyée sur la route de papa, étiquetée', async () => {
  const b = banc();
  b.ctx.separation.pret = true;
  b.ctx.separerSon('/x/bloc.wav', 'telephone', { cascade: true, cle: 'B1', debut: 1000 });
  b.ctx.recue({ id: 1, texte: 'une voix parlée', voix: {}, fond: {}, texte_cascade: 'deux voix, une guitare', instruments: [{ nom: 'guitare' }],
    voix_separees: [
      { numero: 1, nom: null, moi: false, volume_db: -12, wav: wav(1) },
      { numero: 2, nom: 'papa', moi: false, volume_db: -18, wav: wav(2) },
      { numero: 3, nom: null, moi: true, volume_db: -10, wav: wav(3) },
      { numero: 4, nom: null, moi: false, volume_db: -30, wav: wav(4) },
      { numero: 5, nom: null, moi: false, volume_db: -40, wav: wav(5) },
      { numero: 6, nom: null, moi: false, volume_db: -20, wav: '/etc/jarvis-sep-6.wav' }] });
  assert.ok(b.blocs.get('B1').fini, 'le bloc mélangé n’envoie plus rien : ses voix prennent le relais');
  assert.deepStrictEqual([...b.ctx.file.map(x => x.voix)], ['voix 1', 'papa', 'voix 4'], 'les 3 plus fortes, sans son écho');
  for (const n of [3, 5]) assert.ok(b.effaces.includes(wav(n)), `voix ${n} : effacée tout de suite`);
  assert.ok(!b.effaces.includes('/etc/jarvis-sep-6.wav'), 'un chemin hors du dossier temporaire : jamais touché');
  assert.deepStrictEqual(b.flux.find(x => x[0] === 'cascade_telephone'), ['cascade_telephone', 'deux voix, une guitare']);
  assert.ok(b.instants.some(([k, d]) => k === 'cascade' && d.texte === 'deux voix, une guitare'));
  await attendre(); await attendre();
  const reessai = b.minuteurs.find(m => m.ms === 400);
  assert.ok(reessai, 'l’oreille vive occupée : il réessaie, sans passer devant papa');
  reessai.f();
  for (let k = 0; k < 8; k++) await attendre();
  assert.deepStrictEqual(b.entendus.map(([t, o]) => [t, o.source, o.voix, o.cle, o.fin]), [
    ['mots de sep-1', 'telephone', 'voix 1', 'B1#1', true], ['mots de sep-2', 'telephone', 'papa', 'B1#2', true], ['mots de sep-4', 'telephone', 'voix 4', 'B1#4', true]]);
  for (const n of [1, 2, 4]) assert.ok(b.effaces.includes(wav(n)), `voix ${n} : effacée une fois transcrite`);
});

test('une seule voix : la route du téléphone l’a déjà ; une réponse en retard ou en erreur : ses voix effacées ; réglage coupé : rien', () => {
  let b = banc();
  b.ctx.separation.pret = true;
  b.ctx.separerSon('/x/bloc.wav', 'telephone', { cascade: true, cle: 'B1' });
  b.ctx.recue({ id: 1, texte: 'x', voix_separees: [{ numero: 1, moi: false, volume_db: -12, wav: wav(1) }] });
  assert.strictEqual(b.ctx.file.length, 0); assert.ok(b.effaces.includes(wav(1))); assert.ok(!b.blocs.get('B1').fini);
  b.ctx.recue({ id: 9, erreur: 'tard', voix_separees: [{ numero: 1, wav: wav(7) }] });
  assert.ok(b.effaces.includes(wav(7)), 'en retard : effacée quand même');
  b = banc({ cascade: false });
  b.ctx.separation.pret = true;
  b.ctx.separerSon('/x/bloc.wav', 'telephone', { cascade: true, cle: 'B1' });
  assert.deepStrictEqual(b.ecrits[0], { id: 1, fichier: '/x/bloc.wav' }, 'sans la cascade : la demande d’avant, inchangée');
});

test('branchée : le bloc entier du téléphone la demande ; le micro aussi (sa scène, sans fichiers de voix) ; le réglage et la page SENS', () => {
  assert.match(SRC, /separerSon\(fs2, 'telephone', \{ cascade: true, cle: String\(temps\.cle \|\| ''\), debut: Number\(temps\.debut_ms\) \|\| 0, \.\.\.\(tp \? \{ t0: /);   // (06/11) + ses trois pistes
  assert.match(SRC, /separerSon\(fs2, 'micro', \{ voixMicro: true, debut: Date\.now\(\) - 3000 \}\); \} catch \(_\) \{\}/, '(07/11) le micro : ses voix aussi, chacune à ses pensées');
  assert.match(SRC, /cascade: r\.cascade !== false,/);
  assert.match(SENS, /<input type="checkbox" id="cascadeSon">/);
  assert.match(SENS, /\['cascadeSon', 'cascade'\]/);
  assert.match(SRC, /function effacerVoixPerdues\(/, 'au démarrage, les fichiers de voix d’un plantage');
});

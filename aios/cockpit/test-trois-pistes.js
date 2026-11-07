// (06/11, 09:27, Ahmed : « le signal envoyé à Hakim processé et net, pour parole, musique ou background, avec les mots exacts en temps réel
// d'apparition, et la piste de musique ou de background calée dessus ; idem pour les sons du micro ») ; 09:40 : « il sait que c'est telle
// note, ou telle note et tel piano ou telle guitare, et il sait reconnaître les voix connues et inconnues » : node --test test-trois-pistes.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const TP = require('./trois-pistes.js');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');

const A = 1_800_000_000_000;                                       // l'instant où papa parlait
const fen = (t0, quoi, o = {}) => ({ t0, t1: t0 + 1, db: -20, voix_db: -25, fond_db: -22, quoi, ...o });

function scene() {
  const p = TP.creer();
  // le téléphone : 8 s de musique (Lam, Lam, Fa, Fa, Do, Do, Sol, Sol), une voix connue « Karim » qui chante dessus
  p.noterSeparation('telephone', A - 20000, { duree_s: 8, bpm: 76, tonalite: 'La mineur',
    fenetres: ['Lam', 'Lam', 'Fa', 'Fa', 'Do', 'Do', 'Sol', 'Sol'].map((ac, i) => fen(i, 'musique', { accord: ac, score: 0.9 })) }, A,
  [{ instrument: 'bass', notes_du_temps: [[0, ['La2']], [2, ['Fa2']], [4, ['Do2']]] }, { instrument: 'drums', notes_du_temps: [] }],
  [{ numero: 1, nom: 'Karim', timbre: 'Karim', segments: [[1, 7]] }]);
  // autour : 2 s de pièce calme puis des chocs, et une voix lointaine
  p.noterSeparation('micro', A - 6000, { duree_s: 3, fenetres: [fen(0, 'bruit', { nature: 'pièce', db: -45 }), fen(1, 'bruit', { nature: 'pièce', db: -44 }),
    fen(2, 'bruit', { nature: 'chocs', chocs: 2, db: -30 })] }, A, [], [{ numero: 2, nom: null, timbre: 'voix 2', segments: [[0, 2]] }]);
  const flux = [
    { t: A - 19000, s: 'telephone', x: 'Dans' }, { t: A - 18600, s: 'telephone', x: 'mon' }, { t: A - 18200, s: 'telephone', x: 'quartier' },
    { t: A - 1200, s: 'papa', x: 'tu' }, { t: A - 900, s: 'papa', x: 'entends' }, { t: A - 600, s: 'papa', x: 'ça' },
    { t: A - 5500, s: 'voix_autour', x: 'à' }, { t: A - 5200, s: 'voix_autour', x: 'table' },
    { t: A - 10000, s: 'corps', x: 'berce' }];
  return { p, flux };
}

test('le bloc : deux sources, trois pistes chacune, sur la même ligne du temps ; mots exacts à leur instant, accords à leur seconde', () => {
  const { p, flux } = scene();
  const b = p.bloc(flux, A, 30000, 3000);
  const [tel, autour] = b.split('Autour (le micro)');
  assert.match(tel, /^Le téléphone \(dedans\)\n  parole : −19,0 s Karim « Dans mon quartier »/);
  assert.match(tel, /musique : −20,0 → −12,0 s : section A, ~76 BPM, La mineur, accords Lam → Fa \(−18,0 s\) → Do \(−16,0 s\) → Sol \(−14,0 s\)/);
  assert.match(tel, /instruments : basse La2 → Fa2 → Do2 ; batterie/, 'chaque instrument et ses notes nommées, avec leur octave');
  assert.match(tel, /fond : rien/);
  assert.match(autour, /parole : −1,2 s papa « tu entends ça »/);
  assert.match(autour, /musique : aucune/);
  assert.match(autour, /fond : −6,0 → −4,0 s : le bruit de la pièce, −4\d dB · −4,0 → −3,0 s : des chocs \(2\), −30 dB · −5,5 s une voix lointaine \(voix 2\) « à table »/);
  assert.ok(!/Hz|0,1 s/.test(b), 'aucune note brute');
});

test('les sections : A, puis B (plus forte, d’autres accords), puis le retour de A', () => {
  const p = TP.creer();
  const bloc = (t0, accords, db) => p.noterSeparation('telephone', t0, { duree_s: accords.length, fenetres: accords.map((ac, i) => fen(i, 'musique', { accord: ac, db })) }, A);
  bloc(A - 60000, ['Lam', 'Fa', 'Do', 'Sol', 'Lam', 'Fa', 'Do', 'Sol', 'Lam', 'Fa'], -30);
  bloc(A - 50000, ['Ré', 'Ré', 'Si', 'Si', 'Ré', 'Si', 'Ré', 'Si', 'Ré', 'Si'], -15);
  bloc(A - 40000, ['Lam', 'Fa', 'Do', 'Sol', 'Lam', 'Fa', 'Do', 'Sol'], -30);
  const s = p.sections('telephone');
  assert.deepStrictEqual(s.map(x => `${x.lettre}${x.retour ? '*' : ''}`), ['A', 'B', 'A*']);
  assert.match(p.musiqueTexte('telephone', A, A - 60000, A), /section B, accords Ré → Si .*intensité forte/);
  assert.match(p.musiqueTexte('telephone', A, A - 60000, A), /section A \(retour\)/);
});

test('entre deux séparations : l’analyse légère tient la piste musique ; un son sans musique va au fond, « pas encore séparé »', () => {
  const p = TP.creer();
  p.noterAnalyse('telephone', A - 2000, { bpm: 120, tonalite: 'Do majeur', voix: 'chante', contour: 'monte' }, A);
  p.noterTrames('micro', A - 4000, 100, Array.from({ length: 20 }, () => [0.05, 0.02, 0.01, 0.01, 0, 0]));
  const b = p.bloc([], A, 30000, 3000);
  assert.match(b, /musique : −7,0 → −1,0 s : section A, ~120 BPM, Do majeur, une voix chante, la mélodie monte/);
  assert.match(b, /Autour \(le micro\)\n  parole : aucune\n  musique : aucune\n  fond : −4,0 → −2,0 s : un son pas encore séparé, −26 dB/);
});

test('les notes de la voix : nommées avec leur octave, résumées (jamais « Ré4 296 Hz 0,1 s »)', () => {
  const n = (note, hz, duree, tenue = false) => ({ note, hz, duree, tenue });
  const r = TP.resumeNotes([n('Ré3', 147, 200), n('Ré3', 148, 500, true), n('Fa3', 175, 100), n('Fa3', 174, 600, true), n('Do6', 1067, 100), n('Mi3', 165, 300)]);
  assert.strictEqual(r, 'Ré3 → Fa3 → Mi3, médium, 2 tenues', 'une note isolée et brève (Do6) n’y est pas');
  assert.strictEqual(TP.resumeNotes([n('Ré3', 147, 100)]), '', 'une seule note : rien');
});

test('rien entendu : bloc vide ; un temps hors de la fenêtre : rien', () => {
  const { p, flux } = scene();
  assert.strictEqual(TP.creer().bloc([], A), '');
  assert.strictEqual(p.bloc(flux, A + 10 * 60e3, 30000, 3000), '');
});

test('« au même moment » : ce qui joue, en une ligne', () => {
  const { p } = scene();
  assert.match(p.resumeCourant('telephone', A - 12500), /^musique : .*section A.*accords .*Sol/);
  assert.match(p.resumeCourant('micro', A - 3000), /fond : .*des chocs \(2\)/);
});

// ---- branchées dans server.js ----
function bancSeparation(allume = true) {
  const ecrits = [], effaces = [], flux = [], demandes = [], minuteurs = [];
  const tp = TP.creer();
  const ctx = { JSON, Date, Math, Number, String, Array, Object, Promise, Map, Set, RegExp, console: { error() {} }, j: JSON.stringify,
    path, os: { tmpdir: () => '/tmp/essai-tp' }, process: { pid: 7 }, CHEMIN_OUTILS: '', PYTHON_SEPARATION: '/py', SEPARATION: '/sep.py',
    fs: { existsSync: () => true, unlink: (f) => effaces.push(f), readdirSync: () => [], statSync: () => ({ mtimeMs: 0 }) },
    setTimeout: (f, ms) => { minuteurs.push({ f, ms }); return minuteurs.length; }, clearTimeout() {},
    corpsReglages: () => ({ cascade: true, trois_pistes: allume }), corpsActif: () => false, corpsLot: { evenements: [] }, ressentirCorps() {},
    fluxAjouter: (k, x, t) => flux.push([k, x, t]), noterInstant() {}, neutraliser: (t) => t, entendus: new Map(), papaParle: () => false,
    recaleMicro: (t) => t, FLUX: [], quiParlait: () => null,
    oreilleDemander: (d) => { demandes.push(d); return Promise.resolve({ texte: 'à table', mots: [['à', 0.2, 0.4], ['table', 0.5, 0.9]] }); },
    TP: tp };
  ctx.troisPistes = () => ctx.corpsReglages().trois_pistes !== false;
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(SRC.indexOf('const separation = { '), SRC.indexOf('async function routeVif(')) + '\nthis.separation = separation;'
    + ' this.separerSon = separerSon; this.recue = separationRecue;', ctx);
  ctx.separation.proc = { stdin: { write: (l) => ecrits.push(JSON.parse(l)) } };
  ctx.separation.pret = true;
  return { ctx, ecrits, effaces, flux, demandes, tp };
}
const attendre = () => new Promise(r => setImmediate(r));
const pistesBloc = { duree_s: 4, bpm: 76, tonalite: 'La mineur', fenetres: [0, 1, 2, 3].map(i => fen(i, 'musique', { accord: i < 2 ? 'Lam' : 'Fa' })) };

test('server : le bloc du téléphone demande ses pistes et sa voix séparée ; la voix revient à sa route, les accords à leur seconde', () => {
  const b = bancSeparation();
  let rendue;
  b.ctx.separerSon('/x/bloc.wav', 'telephone', { cascade: true, cle: 'B1', t0: A - 10000, quand: (w) => { rendue = w; } });
  const d = b.ecrits[0];
  assert.strictEqual(d.pistes, true);
  assert.strictEqual(d.voix_wav, '/tmp/essai-tp/jarvis-sep-7-1-voix.wav', 'la voix séparée, écrite là où le cockpit l’efface');
  b.ctx.recue({ id: 1, texte: 'la voix (séparée) chante', voix: {}, fond: {}, voix_wav: d.voix_wav, pistes: pistesBloc,
    instruments: [{ instrument: 'bass', notes_du_temps: [[0, ['La2']], [2, ['Fa2']]] }], voix_separees: [{ numero: 1, nom: 'papa', segments: [[0, 4]] }] });
  assert.strictEqual(rendue, d.voix_wav, 'la grande oreille transcrit la voix séparée');
  const m = b.tp.musiqueTexte('telephone', A, A - 30000, A);
  assert.match(m, /^−10,0 → −6,0 s : section A, ~76 BPM, La mineur, accords Lam → Fa \(−8,0 s\), instruments : basse La2 → Fa2/);
  assert.ok(!b.flux.some(x => x[0] === 'separe_telephone'), 'plus de ligne brute « séparé » au fil');
  assert.ok(b.flux.some(x => x[0] === 'musique_telephone' && /section A/.test(x[1])), 'au fil : ce qui joue, processé');
});

test('server : une séparation perdue (occupée, partie, en retard) rend « rien » à la route, qui transcrit alors le mélange', () => {
  const b = bancSeparation();
  const rendus = [];
  b.ctx.separerSon('/x/a.wav', 'telephone', { cascade: true, cle: 'B1', t0: A, quand: (w) => rendus.push(w) });
  b.ctx.separation.pret = false;
  b.ctx.separerSon('/x/b.wav', 'telephone', { cle: 'B2', quand: (w) => rendus.push(w) });
  assert.deepStrictEqual(rendus, [null], 'pas prête : rien, tout de suite');
  b.ctx.recue({ id: 9, voix_wav: '/tmp/essai-tp/jarvis-sep-7-9-voix.wav' });
  assert.ok(b.effaces.includes('/tmp/essai-tp/jarvis-sep-7-9-voix.wav'), 'une réponse en retard : sa voix effacée');
});

test('server : autour, une voix lointaine (ni papa ni lui) part à l’oreille vive, ses mots à leur instant ; papa parlait : rien', async () => {
  let b = bancSeparation();
  b.ctx.separerSon('/x/amb.wav', 'micro');
  assert.ok(b.ecrits[0].voix_wav, 'le micro demande sa voix séparée');
  b.ctx.recue({ id: 1, texte: 'x', voix: {}, fond: {}, voix_wav: b.ecrits[0].voix_wav, pistes: { duree_s: 3, fenetres: [fen(0, 'bruit', { nature: 'pièce' })] } });
  for (let k = 0; k < 4; k++) await attendre();
  assert.strictEqual(b.demandes[0].avec_temps, true, 'avec le temps de chaque mot');
  const mots = b.flux.filter(x => x[0] === 'voix_autour');
  assert.deepStrictEqual(mots.map(x => x[1]), ['à', 'table']);
  assert.strictEqual(mots[1][2] - mots[0][2], 300, 'chaque mot à son instant');
  b = bancSeparation();
  b.ctx.FLUX.push({ s: 'papa', t: Date.now() - 3500, x: 'oui' });
  b.ctx.separerSon('/x/amb.wav', 'micro');
  b.ctx.recue({ id: 1, texte: 'x', voix: {}, fond: {}, voix_wav: b.ecrits[0].voix_wav, pistes: { duree_s: 3, fenetres: [] } });
  for (let k = 0; k < 4; k++) await attendre();
  assert.ok(!b.flux.some(x => x[0] === 'voix_autour'), 'papa parlait : ses mots y sont déjà');
});

test('server : réglage éteint (trois_pistes) : la demande et le fil d’avant, inchangés', () => {
  const b = bancSeparation(false);
  b.ctx.separerSon('/x/bloc.wav', 'telephone', { cascade: true, cle: 'B1' });
  assert.deepStrictEqual(b.ecrits[0], { id: 1, fichier: '/x/bloc.wav', cascade: true, voix_dossier: '/tmp/essai-tp' });
  b.ctx.recue({ id: 1, texte: 'la voix (séparée) parle', voix: {}, fond: {} });
  assert.ok(b.flux.some(x => x[0] === 'separe_telephone'));
});

test('server : ses notes brutes ne vont plus au fil ; elles nourrissent ses pistes (et reviennent, réglage éteint)', () => {
  const lancer = (allume) => {
    const flux = [];
    const ctx = { Math, Number, Array, String, Object, JSON, Date, path, JARVIS: '/x', fs: { appendFile() {}, readFile() {} }, SON_TRAMES: { telephone: [], micro: [] }, sonsPousses: {},
      recaleMicro: (t) => t, fluxAjouter: (k, x) => flux.push([k, x]), corpsActif: () => false, noterInstant() {},
      analyseMusicale: () => null, TP: TP.creer(), TroisPistes: TP, troisPistes: () => allume };
    vm.createContext(ctx);
    const i = SRC.indexOf('const NOTES = [');
    vm.runInContext(SRC.slice(i, SRC.indexOf('/* (04/11, Hakim, à la demande de papa')) + SRC.slice(SRC.indexOf('function resumeSon('), SRC.indexOf('/* (03/11, Ahmed : « une troisième parallélisation'))
      + SRC.slice(SRC.indexOf('recevoirSon.n = 0;'), SRC.indexOf('function etat_humeur_courante')) + '\nthis.recevoir = recevoirSon;', ctx);
    const hz = (m) => 440 * 2 ** ((m - 69) / 12);
    ctx.recevoir('telephone', A - 5000, 100, Array.from({ length: 10 }, (_, k) => [0.1, 0.05, 0.05, 0.01, hz(k < 5 ? 50 : 53), 1500]));
    return { flux, ctx };
  };
  const on = lancer(true);
  assert.ok(!on.flux.some(x => /^voix_|^instru_/.test(x[0])), JSON.stringify(on.flux));
  assert.ok(on.ctx.TP._cellules.telephone.size > 0, 'ses pistes ont les trames');
  const off = lancer(false);
  assert.ok(off.flux.some(x => x[0] === 'voix_telephone' && /Hz/.test(x[1])), 'éteint : comme avant');
});

test('server : son tour reçoit le bloc à trois pistes ; le fil n’y répète pas les mots ni les sons', () => {
  assert.match(SRC, /function bulbe\(texte, interieur, corps, rappel, instant = '', fil = '', pistes = ''\)/);
  assert.match(SRC, /Ce que tu entends, en trois pistes sur la même ligne du temps/);
  assert.strictEqual((SRC.match(/typeof pistesTexte === 'function' \? pistesTexte\(/g) || []).length, 3, 'ses trois fiches');
  assert.match(SRC, /const l = FLUX\.filter\(o => o\.t >= a - avant && o\.t <= a \+ apres && !\(sansPistes && SOURCES_PISTES\.test\(o\.s\)\)\);/);
  assert.match(SRC, /fichier: telephone && voixSeparee \? voixSeparee : f,/, 'la grande oreille : la voix séparée');
  assert.match(SRC, /lot\.fil = `\[ce qu'il entend, en trois pistes\] \$\{tp\} \[le reste du fil\] \$\{lot\.fil\}`/, 'son subconscient aussi');
  assert.match(SRC, /trois_pistes: r\.trois_pistes !== false,/);
  assert.match(SRC, /'pretraitement_parole', 'trois_pistes', 'parole_liee', 'sa_voix_reconnue', 'reprendre_ancien', 'morceaux_unifies', 'ecrit_coupe', 'finir_phrase', 'choisir_latence', 'te_couper', 'choix_coupure', 'choix_libre'\]\) if \(typeof q\[k\] === 'boolean'\) r\[k\] = q\[k\];/);
  const page = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
  assert.match(page, /\['trois_pistes', '🎚️ Trois pistes : parole, musique, fond'/);
});

test('server : la réponse partielle (avant la cascade) donne tout de suite la voix et les pistes ; la cascade ajoute ensuite ses instruments', () => {
  const b = bancSeparation();
  let rendue;
  b.ctx.separerSon('/x/bloc.wav', 'telephone', { cascade: true, cle: 'B1', t0: A - 10000, quand: (w) => { rendue = w; } });
  const d = b.ecrits[0];
  b.ctx.recue({ id: 1, partiel: true, pistes: pistesBloc, voix_wav: d.voix_wav });
  assert.strictEqual(rendue, d.voix_wav, 'la voix, sans attendre la cascade');
  assert.ok(b.ctx.separation.attente, 'la demande reste en cours');
  b.ctx.recue({ id: 1, texte: 'x', voix: {}, fond: {}, instruments: [{ instrument: 'piano', notes_du_temps: [[1, ['Do4', 'Mi4']]] }], voix_separees: [] });
  assert.match(b.tp.musiqueTexte('telephone', A, A - 30000, A), /instruments : piano Do4\+Mi4/);
  assert.strictEqual(b.ctx.separation.attente, null);
});

test('le Bluetooth (le même morceau, 20 dB plus bas) : mêmes accords, même intensité dite', () => {
  const dire = (decal) => {
    const p = TP.creer();
    p.noterSeparation('telephone', A - 20000, { duree_s: 8, fenetres: Array.from({ length: 8 }, (_, i) => fen(i, 'musique', { accord: i < 4 ? 'Lam' : 'Fa', db: (i < 4 ? -30 : -20) + decal })) }, A);
    return p.musiqueTexte('telephone', A, A - 30000, A);
  };
  assert.strictEqual(dire(-20), dire(0));
  assert.match(dire(0), /section A, accords Lam, intensité douce · −16,0 → −12,0 s : section B, accords Fa, intensité moyenne/, '10 dB de plus : une autre section');
});

test('(mesuré sur « Rose ») une phrase qui change de voix se coupe à la voix ; une seule seconde plus faible n’ouvre pas de section', () => {
  const p = TP.creer();
  const db = [-27.6, -29, -26.9, -37.9, -26.4, -25.6, -26, -25.2];
  p.noterSeparation('telephone', A - 12000, { duree_s: 8, fenetres: db.map((d, i) => fen(i, 'musique', { accord: i < 4 ? 'Mim' : 'Ré', db: d })) }, A, [],
    [{ numero: 1, nom: 'papa', segments: [[1.4, 3.1], [4.15, 8]] }, { numero: 2, nom: null, timbre: 'voix 2', segments: [[0, 1.29]] }]);
  const flux = [['Toujours', 0], ['dans', 0.5], ['tes', 1.78], ['bras,', 1.98], ['je', 2.32]].map(([x, s]) => ({ t: A - 12000 + s * 1000, s: 'telephone', x }));
  const b = p.bloc(flux, A, 30000, 3000);
  assert.match(b, /−12,0 s voix 2 « Toujours dans » · −10,2 s papa « tes bras, je »/);
  assert.strictEqual(p.sections('telephone').length, 1, b);
});

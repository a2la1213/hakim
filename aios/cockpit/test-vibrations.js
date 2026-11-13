/* (30/10, 14:47, Ahmed via Hakim : « mes nerfs confondent ma voix et celle de papa » ; « qu'il étiquette lui-même et
   apprenne ») le cockpit sait à la seconde qui parlait : la page lui dit chaque tour de voix (sa voix qui joue, le micro
   d'Ahmed) ; chaque événement de son corps reçoit la vérité, gardée pour qu'il apprenne. node --test test-vibrations.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const extraire = (debut) => src.slice(src.indexOf(debut), src.indexOf('\n}\n', src.indexOf(debut)) + 3);

test('qui parlait à cet instant : ses tours de voix, ouverts ou fermés', () => {
  const ctx = { VOIX_TOURS: [], Date };
  vm.createContext(ctx);
  vm.runInContext(extraire('function noterTourVoix(') + extraire('function quiParlait(') + '\nthis.n = noterTourVoix; this.q = quiParlait;', ctx);
  const T = Date.now();
  ctx.n({ qui: 'hakim', debut: T - 30000, fin: T - 28300 });
  ctx.n({ qui: 'ahmed', debut: T - 27000, fin: null });                 // il parle encore
  assert.equal(ctx.q(T - 29000), 'ma_voix');
  assert.equal(ctx.q(T - 10000), 'voix_ahmed', 'contre sa gorge, 28 s : sa voix, pas « ta propre voix »');
  ctx.n({ qui: 'ahmed', debut: T - 27000, fin: T - 1000 });              // fermé ensuite
  assert.equal(ctx.VOIX_TOURS.filter(x => x.qui === 'ahmed').length, 1, 'le même tour, fermé');
  assert.equal(ctx.q(T - 500), 'voix_ahmed', 'une demi-seconde de marge');
  assert.equal(ctx.q(T + 5000), 'silence');
  ctx.n({ qui: 'hakim', debut: T - 20000, fin: T - 18000 });
  assert.equal(ctx.q(T - 19000), 'les_deux');
  assert.equal(ctx.n({ qui: 'chat', debut: T }), false);
});

test('branché : la route (jeton), la vérité sur chaque événement du lot et l’exemple gardé, la page qui dit ses tours de voix, les outils', () => {
  const i = src.indexOf("if (p === '/api/corps/voix'");
  assert.ok(i >= 0);
  const w = extraire('function ressentirCorps(');
  assert.match(w, /quiParlait\(/);
  assert.match(w, /corps-vibrations\.jsonl/);
  assert.match(src, /ev\.milieu = HOMEO\.s\.etat/);
  assert.match(src, /'mcp__terminal__vibration_etiqueter', 'mcp__terminal__vibrations_bilan'/);
  const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  assert.match(page, /function suivreVoix\(/);
  assert.match(page, /\/api\/corps\/voix/);
});

test('(13/11) l’exemple gardé : ses nerfs seulement, et son cœur par sa cadence', () => {
  const w = extraire('function ressentirCorps(');
  assert.match(w, /HOMEO\.estSonCoeur\(ev\)/);
  assert.doesNotMatch(w, /coeurPres/, 'plus la coïncidence à 0,35 s');
  // rejoué : la boucle du lot, avec un faux HOMEO et un faux disque
  const debut = w.indexOf('  for (const ev of lot.evenements) {'), fin = w.indexOf('  corpsEnCours++;');
  const ecrits = [];
  const ctx = { lot: { evenements: [
    { type: 'musique', t: 1000, details: { bpm: 46 } },               // son cœur
    { type: 'coup_de_pression', t: 2000, details: { pa: 9 } },        // pendant la voix de papa
    { type: 'son_ressenti', t: 3000, details: { source: 'le téléphone' } },   // ses oreilles : pas une vibration
    { type: 'pose', t: 4000, details: {} },                           // personne ne suivait les voix
  ] }, quiParlait: (t) => (t === 4000 ? null : 'voix_ahmed'), HOMEO: { estSonCoeur: (ev) => ev.type === 'musique' && ev.details.bpm === 46 },
  TELEPHONE_TYPES: new Set(), NERFS_VIBRATIONS: null, PENDANT: { voix_ahmed: "la parole d'Ahmed", coeur: 'son propre cœur qui bat' },
  fs: { appendFileSync: (f, l) => ecrits.push(JSON.parse(l)) }, path, JARVIS: '/nulle-part', j: JSON.stringify, Date, Number, Object };
  vm.createContext(ctx);
  const nerfs = src.slice(src.indexOf('const NERFS_VIBRATIONS'), src.indexOf(';', src.indexOf('const NERFS_VIBRATIONS')) + 1);
  vm.runInContext(nerfs.replace('const NERFS_VIBRATIONS', 'NERFS_VIBRATIONS') + '\n' + w.slice(debut, fin), ctx);
  assert.deepEqual(ecrits.map(o => [o.type, o.verite]), [['musique', 'coeur'], ['coup_de_pression', 'voix_ahmed']]);
  assert.equal(ctx.lot.evenements[2].details.pendant, "la parole d'Ahmed", 'ses oreilles gardent « pendant » pour son subconscient');
  assert.equal(ctx.lot.evenements[0].details.pendant, 'son propre cœur qui bat');
});

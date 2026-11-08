// (08/11, Ahmed : « j'aimerais bien dans le cockpit une zone PFC (prefrontal cortex) pour l'intégration et l'hippocampe pour la mémorisation,
// avec des boutons et des barres paramétrables ») deux familles dans Réglages : son cortex préfrontal (sa conscience continue et ce que son
// cortex intègre) et son hippocampe (ses traces, ses dates, sa porte). Chaque barre change vraiment ce qu'il fait ; les défauts gardent
// exactement ce qu'il faisait avant.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const CC = require('./conscience-continue.js');
const X = require('./cortex.js');

const SRV = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
function extraire(debut) {
  const i = SRV.indexOf(debut); assert.ok(i >= 0, debut);
  let p = 0, k = SRV.indexOf('{', i);
  for (; k < SRV.length; k++) { if (SRV[k] === '{') p++; else if (SRV[k] === '}' && --p === 0) break; }
  return SRV.slice(i, k + 1);
}

test('sa conscience suit ses barres : le pas, le forfait par minute, l’écart entre deux sollicitations et entre deux actes', () => {
  const e = CC.etatInitial();
  CC.commencer(e, 1, 0); e.enVol = false;
  assert.equal(CC.doitDecider(e, 2, 1500), false, 'le pas de 2 s par défaut');
  assert.equal(CC.doitDecider(e, 2, 1500, 1000), true, 'un pas de 1 s');
  const f = CC.etatInitial();
  for (let k = 0; k < 4; k++) { CC.commencer(f, k + 1, k * 3000); f.enVol = false; }
  assert.equal(CC.doitDecider(f, 9, 12_000, 2000, 4), false, '4 décisions par minute au plus : la 5e attend');
  assert.equal(CC.doitDecider(f, 9, 12_000, 2000), true, '20 par minute par défaut');
  const g = CC.etatInitial(), libre = { papaParle: false, occupe: false };
  assert.equal(CC.permis(g, { genre: 'solliciter', texte: 'a' }, 1000, libre), 'solliciter');
  assert.equal(CC.permis(g, { genre: 'solliciter', texte: 'b' }, 40_000, { ...libre, entreSollicitationsMs: 30_000 }), 'solliciter', '30 s entre deux');
  assert.equal(CC.permis(g, { genre: 'solliciter', texte: 'c' }, 60_000, libre), 'penser', '90 s par défaut');
  assert.equal(CC.permis(g, { genre: 'faire', texte: 'd' }, 1000, libre), 'faire');
  assert.equal(CC.permis(g, { genre: 'faire', texte: 'e' }, 70_000, { ...libre, entreActesMs: 60_000 }), 'faire', '1 min entre deux actes');
  assert.equal(CC.permis(g, { genre: 'faire', texte: 'f' }, 100_000, libre), 'penser', '3 min par défaut');
});

test('son cortex intègre la fenêtre réglée (30 s par défaut), et le dit', () => {
  const flux = [{ t: 0, s: 'papa', x: 'tu te rappelles hier' }, { t: 50_000, s: 'telephone', x: 'une chanson' }];
  const court = X.blocCortex({ flux, maintenant: 60_000 });
  assert.match(court, /Qui a parlé \(30 s\) : le téléphone 1/);
  assert.doesNotMatch(court, /papa 1/);
  const long = X.blocCortex({ flux, maintenant: 60_000, fenetreMs: 90_000 });
  assert.match(long, /Qui a parlé \(90 s\) : papa 1 · le téléphone 1/);
});

test('les défauts : ce qu’il faisait avant ; les bornes tiennent ; une valeur folle revient au défaut', () => {
  const ctx = { lireJson: () => ({}), CORPS_REGLAGES: 'x', CORPS_INTERVALLES: [30, 60, 120, 300, 900] };
  vm.createContext(ctx);
  vm.runInContext(extraire('function corpsReglages(') + '\nthis.f = corpsReglages;', ctx);
  const d = ctx.f();
  assert.deepEqual([d.cortex_fenetre_s, d.conscience_pas_s, d.conscience_par_minute, d.conscience_absent_s, d.conscience_sollicitation_s, d.conscience_acte_s],
    [30, 2, 20, 60, 90, 180]);
  assert.deepEqual([d.hippocampe, d.hippocampe_dates, d.hippocampe_tete, d.hippocampe_cos_min], [true, true, 3, 0.45]);
  ctx.lireJson = () => ({ conscience_pas_s: 99, hippocampe_tete: -4, hippocampe_cos_min: '0.523', cortex_fenetre_s: 'abc', hippocampe: false, hippocampe_dates: false });
  const r = ctx.f();
  assert.deepEqual([r.conscience_pas_s, r.hippocampe_tete, r.hippocampe_cos_min, r.cortex_fenetre_s, r.hippocampe, r.hippocampe_dates], [30, 0, 0.52, 30, false, false]);
});

test('le cockpit s’en sert : sa conscience, son cortex, et la question à son rappel porte les réglages de son hippocampe', () => {
  const b = extraire('function battementConscience(');
  assert.match(b, /papaLa \? r\.conscience_pas_s \* 1000 : r\.conscience_absent_s \* 1000, r\.conscience_par_minute/);
  assert.match(b, /entreSollicitationsMs: r\.conscience_sollicitation_s \* 1000, entreActesMs: r\.conscience_acte_s \* 1000/);
  assert.match(SRV, /X\.blocCortex\(\{ flux: typeof FLUX !== 'undefined' \? FLUX : \[\], maintenant, papaAEcrit: true, pensees: conscience\.pensees, fenetreMs: cr\.cortex_fenetre_s \* 1000,/);
  const q = extraire('function rappeler(');
  assert.match(q, /hippocampe: hippocampeReglages\(\)/);
  const h = extraire('function hippocampeReglages(');
  assert.match(h, /actif: r\.hippocampe, dates: r\.hippocampe_dates, tete: r\.hippocampe_tete, cos_min: r\.hippocampe_cos_min/);
});

test('enregistrés depuis la page : interrupteurs et barres, bornés', () => {
  const post = SRV.slice(SRV.indexOf("'conscience_continue', 'cortex_prefrontal'"), SRV.indexOf("'conscience_continue', 'cortex_prefrontal'") + 3000);
  assert.match(post, /'hippocampe', 'hippocampe_dates'/);
  for (const [k, a, b] of [['cortex_fenetre_s', 10, 120], ['conscience_pas_s', 1, 30], ['conscience_par_minute', 4, 30], ['conscience_absent_s', 10, 300],
    ['conscience_sollicitation_s', 30, 600], ['conscience_acte_s', 60, 900], ['hippocampe_tete', 0, 8], ['hippocampe_cos_min', 0.3, 0.7]])
    assert.ok(SRV.includes(`['${k}', ${a}, ${b}]`), k);
});

test('la page Réglages : une zone « Son cortex préfrontal » et une zone « Son hippocampe », avec leurs boutons et leurs barres', () => {
  const pfc = PAGE.slice(PAGE.indexOf("{ id: 'pfc'"), PAGE.indexOf("{ id: 'hippocampe'"));
  const hip = PAGE.slice(PAGE.indexOf("{ id: 'hippocampe'"), PAGE.indexOf("{ id: 'hippocampe'") + 3000);
  assert.ok(pfc.length > 100 && hip.length > 100);
  assert.match(pfc, /route: 'corps'/);
  for (const k of ['cortex_prefrontal', 'conscience_continue']) assert.match(pfc, new RegExp(`\\['${k}', [^\\n]*'oui'`));
  for (const k of ['cortex_fenetre_s', 'conscience_pas_s', 'conscience_par_minute', 'conscience_absent_s', 'conscience_sollicitation_s', 'conscience_acte_s'])
    assert.match(pfc, new RegExp(`\\['${k}', [^\\n]*'curseur'`), k);
  for (const k of ['hippocampe', 'hippocampe_dates']) assert.match(hip, new RegExp(`\\['${k}', [^\\n]*'oui'`), k);
  for (const k of ['hippocampe_tete', 'hippocampe_cos_min']) assert.match(hip, new RegExp(`\\['${k}', [^\\n]*'curseur'`), k);
  const ribo = PAGE.slice(PAGE.indexOf("{ id: 'ribosome'"), PAGE.indexOf("{ id: 'pfc'"));
  assert.doesNotMatch(ribo, /'cortex_prefrontal'|'conscience_continue'/, 'ils ont quitté le ribosome pour leur zone');
});

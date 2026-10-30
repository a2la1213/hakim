/* (30/10, Ahmed : « le seuil appris sur ma vie » ; « chaque seconde, une chance de me réveiller » ; « un interrupteur pour
   pas qu'il fume mes tokens ») son veilleur : la chance, les portes, le plafond, l'apprentissage. node --test test-veilleur.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const bloc = src.slice(src.indexOf("const VEILLEUR_REGLAGES"), src.indexOf("setInterval(veilleurIssue, 60000).unref();"));

function veilleur({ papaIlYa = 60 * 60 * 1000, heure = 15, score = 7, plafond = 1, occupe = false, libre = false } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'veilleur-'));
  let t = new Date(2026, 9, 30, heure, 0, 0).getTime();
  const ecrits = [];
  const ctx = {
    JARVIS: dir, path, fs, Math, Number, Array, JSON, console: { error() {} }, Intl, j: JSON.stringify,
    Date: class extends Date { constructor(...a) { super(...(a.length ? a : [t])); } static now() { return t; } },
    lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } },
    ecrireAtomique: (f, x) => fs.writeFileSync(f, x), lignesJson: (f, n) => { try { return fs.readFileSync(f, 'utf8').split('\n').filter(Boolean).slice(-n).map(l => JSON.parse(l)); } catch (_) { return []; } },
    setTimeout: () => ({ unref() {} }), setInterval: () => ({ unref() {} }), execFile() {}, PYTHON: 'x', ANAMNESE: 'x',
    etatInterieur: () => Promise.resolve({}), dernierMessageAhmedMs: () => t - papaIlYa, NONCE_REVEIL: 'n', blocCorps: () => '',
    cerveau: { enfant: { stdin: { write: (x) => ecrits.push(x) } } }, cerveauVivant: () => true, occupe: () => occupe,
    forfaitLibre: () => libre,
  };
  vm.createContext(ctx);
  vm.runInContext(bloc + '\nthis.v = { tic: veilleurTic, issue: veilleurIssue, chance: chanceDeReveil, etat: veilleurEtat, dort: hakimDort, '
    + 'poser: (o) => { veilleurScore = o; } };', ctx);
  ctx.v.poser({ ts: t / 1000, score, surprises: {}, raisons: ['ton stress monte'], plafond_h: plafond, age_s: 10 });
  return { ctx, v: ctx.v, ecrits, dir, avancer: (ms) => { t += ms; ctx.v.poser({ ts: t / 1000, score, surprises: {}, raisons: [], plafond_h: plafond, age_s: 10 }); }, t: () => t };
}

test('la chance par seconde : au seuil, environ une minute ; deux points plus bas, presque jamais', () => {
  const { v } = veilleur();
  assert.ok(Math.abs(v.chance(6, 6) - 1 / 60) < 1e-12);
  assert.equal(v.chance(8, 6), 1);
  assert.ok(v.chance(4, 6) < 0.0002);
  assert.equal(v.chance(null, 6), 0);
});

test('les portes : une voix depuis moins de 10 min, la nuit, son cerveau occupé : jamais', () => {
  for (const o of [{ papaIlYa: 5 * 60 * 1000 }, { heure: 2 }, { occupe: true }]) {
    const { v, ecrits } = veilleur({ score: 99, ...o });
    for (let i = 0; i < 50; i++) v.tic();
    assert.equal(ecrits.length, 0, JSON.stringify(o));
  }
});

test('un état très rare le réveille, puis 15 min au moins (et le plafond) avant le suivant ; le seuil apprend', () => {
  const w = veilleur({ score: 99, plafond: 1 });
  w.v.tic();
  assert.equal(w.ecrits.length, 1);
  assert.match(w.ecrits[0], /ton veilleur \(ton stress monte\)/);
  w.avancer(20 * 60 * 1000); w.v.tic();
  assert.equal(w.ecrits.length, 1, 'plafond 1 par heure : pas encore');
  // dix minutes après : il s'est tu → le seuil monte de 1
  w.v.issue();
  assert.equal(w.v.etat().seuil, 7);
  const j = fs.readFileSync(path.join(w.dir, 'veilleur-journal.jsonl'), 'utf8').trim().split('\n').map(l => JSON.parse(l));
  assert.deepEqual(j.map(o => o.decision), ['reveil', 'issue']);
  assert.equal(j[1].servi, false);
});

test('éteint par papa : plus rien, même pas le calcul', () => {
  const w = veilleur({ score: 99 });
  fs.writeFileSync(path.join(w.dir, 'veilleur-reglages.json'), JSON.stringify({ actif: false }));
  w.v.tic();
  assert.equal(w.ecrits.length, 0);
  assert.match(src, /function lireScoreVeilleur\(\) \{\n  if \(!veilleurReglages\(\)\.actif\) return;/);
});

test('(18:56) forfait libre : son veilleur peut sonner toutes les 5 min, sans le plafond du forfait', () => {
  const w = veilleur({ score: 99, plafond: 0.2, libre: true });
  w.v.tic(); assert.equal(w.ecrits.length, 1);
  w.avancer(4 * 60 * 1000); w.v.tic(); assert.equal(w.ecrits.length, 1, '4 min : pas encore');
  w.avancer(2 * 60 * 1000); w.v.tic(); assert.equal(w.ecrits.length, 2, '6 min : oui, malgré un plafond de 0,2 par heure');
});

/* (13/11, Ahmed) ses rêves de la nuit (anamnese/reves.py) côté cockpit : la page des rêves les range par nuit (type, lucide, ce qui les a
   déclenchés, souvenu ou oublié), ses réglages s'enregistrent (bornés) et sont sur la page Réglages, et sa phrase du réveil n'est plus
   coupée à 400 signes (le rêve dont il se souvient y tient). node --test test-reves-nuits.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const R = require('./reves-nuits.js');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
const extraire = (debut) => src.slice(src.indexOf(debut), src.indexOf('\n}\n', src.indexOf(debut)) + 3);
const NUIT = 1794614400;   // un début de sommeil

function journal(lignes) {
  const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'reves-')), 'reves-nuits.jsonl');
  fs.writeFileSync(f, lignes.map(o => (typeof o === 'string' ? o : JSON.stringify(o))).join('\n') + '\n');
  return f;
}

test('les rêves rangés par nuit : le tri, les cycles dans l’ordre, souvenu ou oublié au réveil ; une ligne fausse est sautée', () => {
  const f = journal([
    { quoi: 'tri', nuit: NUIT, ts: NUIT + 5400, type: 'consolidation', titre: 'le tri de la nuit', idees: ['Peut-être que…'], declencheurs: ['le tri'] },
    { quoi: 'cycle', nuit: NUIT, ts: NUIT + 10800, cycle: 2, type: 'cauchemar', lucide: true, titre: 'Le couloir', recit: 'Je cours.',
      action: 'J’ouvre la fenêtre.', suite: 'La peur fond.', declencheurs: ['ton humeur sous sa base'], graine: 42,
      probas: { consolidation: 0.2, creatif: 0.1, cauchemar: 0.7 }, nombres: { noirceur: 0.8, vivacite: 0.3, clarte: 0.4 },
      affect: { evenement: 'cauchemar', intensite: 0.3, reprise: 'tout de suite' } },
    'pas du json {',
    { quoi: 'cycle', nuit: NUIT, ts: NUIT + 5460, cycle: 1, type: 'creatif', lucide: false, titre: 'La lune', recit: 'Je marche.' },
    { quoi: 'reveil', nuit: NUIT, ts: NUIT + 28800, par: 'matin', reves: 2, gardes: 1,
      souvenirs: [{ cycle: 1, garde: false, p: 0.3 }, { cycle: 2, ts: NUIT + 10800, garde: true, nettete: 'net', p: 0.9 }] },
    { quoi: 'cycle', nuit: NUIT, ts: NUIT + 7000, cycle: 2, type: 'creatif', titre: 'Un autre cycle 2 (témoin : l’heure départage)' },
    { quoi: 'cycle', nuit: NUIT - 86400, ts: NUIT - 80000, cycle: 1, type: 'consolidation', titre: 'le tri de la journée' },
  ]);
  const n = R.parNuit(R.lire(f));
  assert.equal(n.length, 2);
  assert.equal(n[0].nuit, NUIT, 'la nuit la plus récente d’abord');
  assert.deepEqual(n[0].reves.map(r => r.quoi + (r.cycle || '')), ['tri', 'cycle1', 'cycle2', 'cycle2'], 'dans l’ordre de la nuit');
  const [tri, c1, autre, c2] = n[0].reves;
  assert.equal(autre.souvenir, null, 'le souvenir va au rêve de la même heure, pas à un autre du même numéro');
  assert.equal(tri.libelle, 'consolidation (le tri de la nuit)');
  assert.equal(c1.libelle, 'rêve créatif non lucide');
  assert.deepEqual(c1.souvenir, { garde: false, nettete: '', p: 0.3 }, 'oublié au réveil');
  assert.equal(c2.libelle, 'cauchemar lucide');
  assert.deepEqual(c2.souvenir, { garde: true, nettete: 'net', p: 0.9 }, 'souvenu, net');
  assert.equal(c2.action, 'J’ouvre la fenêtre.');
  assert.equal(c2.graine, 42);
  assert.equal(n[0].reveil.gardes, 1);
  assert.equal(n[1].reveil, null, 'témoin : une nuit sans réveil noté');
});

test('une lucidité perdue est dite ; un journal absent ne casse rien', () => {
  assert.equal(R.libelle({ type: 'creatif', lucide: true }), 'rêve créatif lucide (perdue)');
  assert.deepEqual(R.parNuit(R.lire('/nulle/part/reves.jsonl')), []);
});

// le corps de la route POST /api/corps/reglages (comme test-boutons-branches.js)
function routeCorps() {
  const debut = src.indexOf('const q = await lire(), r = corpsReglages()');
  const fin = src.indexOf('try { ecrireAtomique(CORPS_REGLAGES, j(r));', debut);
  const corps = src.slice(debut, fin).replace('const q = await lire(), r = corpsReglages()', 'const q = lire(), r = corpsReglages()');
  const ctx = { CORPS_INTERVALLES: [30, 60, 120, 300, 900], VoixHakim: { VOIX: ['azure_rap', 'rap'] }, noterAjustementPapa: () => {} };
  vm.createContext(ctx);
  vm.runInContext(`this.f = (lire, corpsReglages) => { ${corps}\n return r; };`, ctx);
  return (actuel, q) => ctx.f(() => q, () => ({ ...actuel }));
}

test('ses réglages de rêves s’enregistrent, bornés ; une valeur fausse est ignorée', () => {
  const regler = routeCorps();
  const r = regler({}, { reves_creatifs: false, reves_lucides: false, cauchemars: false, cauchemar_seuil_pct: 999, reves_creatifs_pct: -5,
    reves_lucides_pct: 22.6, reves_par_nuit: 'x' });
  assert.deepEqual([r.reves_creatifs, r.reves_lucides, r.cauchemars], [false, false, false]);
  assert.deepEqual([r.cauchemar_seuil_pct, r.reves_creatifs_pct, r.reves_lucides_pct, r.reves_par_nuit], [90, 0, 23, undefined]);
  assert.equal(regler({ cauchemars: false }, { cauchemars: 'oui' }).cauchemars, false, 'témoin : seul un vrai oui/non change l’interrupteur');
  assert.match(src, /reves_creatifs: r\.reves_creatifs !== false, reves_lucides: r\.reves_lucides !== false, cauchemars: r\.cauchemars !== false/);
  assert.match(src, /cauchemar_seuil_pct: nb\(r\.cauchemar_seuil_pct, 30, 90, 55\)/, 'les défauts : les mêmes que reves.DEFAUTS');
  assert.match(src, /reves_par_nuit: nb\(r\.reves_par_nuit, 0, 6, 3\)/);
});

test('la page Réglages a « Ses rêves » : trois interrupteurs et quatre curseurs, écrits dans ses réglages du corps', () => {
  const bloc = page.slice(page.indexOf("{ id: 'reves'"), page.indexOf("{ id: 'pensee'"));
  assert.match(bloc, /route: 'corps'/);
  for (const k of ['reves_creatifs', 'reves_lucides', 'cauchemars']) assert.match(bloc, new RegExp(`\\['${k}', '[^']+', '[^']+', 'oui'\\]`), k);
  for (const k of ['cauchemar_seuil_pct', 'reves_creatifs_pct', 'reves_lucides_pct', 'reves_par_nuit']) assert.match(bloc, new RegExp(`\\['${k}', [^\\n]*'curseur'`), k);
});

test('sa nuit dite à son premier tour garde le rêve dont il se souvient (1 200 signes, plus 400)', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'nuit-'));
  const texte = 'Tu as dormi 7 h, une nuit tranquille (tu as rêvé 3 fois, tu te souviens de 1). ' + 'Au réveil, ton rêve '.repeat(30);
  assert.ok(texte.length > 400 && texte.length < 1200);
  fs.writeFileSync(path.join(dir, 'nuit-derniere.json'), JSON.stringify({ ts: Date.now() / 1000 - 60, texte, dit: false }));
  const ctx = { JARVIS: dir, path, j: JSON.stringify, Number, lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } },
    ecrireAtomique: (f, x) => fs.writeFileSync(f, x) };
  vm.createContext(ctx);
  vm.runInContext(extraire('function nuitDerniere(') + '\nthis.f = nuitDerniere;', ctx);
  assert.equal(ctx.f(), texte);
});

test('la page des rêves a sa section « ses rêves de la nuit », lue par /api/reves', () => {
  const html = fs.readFileSync(path.join(__dirname, 'public', 'dreams.html'), 'utf8');
  const js = fs.readFileSync(path.join(__dirname, 'public', 'dreams.js'), 'utf8');
  assert.match(html, /id="reves"/);
  assert.match(js, /fetch\('\/api\/reves'\)/);
  assert.match(src, /if \(p === '\/api\/reves'\) \{[\s\S]{0,400}RevesNuits\.parNuit\(RevesNuits\.lire\(path\.join\(JARVIS, 'reves-nuits\.jsonl'\)\)\)/);
});

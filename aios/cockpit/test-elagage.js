/* (04/11, Ahmed : « comme le système nerveux humain, qui mûrit en consolidant les bonnes synapses et en éliminant, de façon autonome,
   celles qui sont inutiles ou parasites : un élagage, qui amoindrit les poids des synapses élaguées ») ses synapses : node --test test-elagage.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const E = require('./elagage.js');

const JOUR = 86400000;
function synapses(o = {}) {
  const dossier = fs.mkdtempSync(path.join(os.tmpdir(), 'synapses-'));
  let t = 1_800_000_000_000;
  const s = E.creer({ fichier: path.join(dossier, 'synapses.json'), maintenant: () => t, hasard: o.hasard || (() => 0.99), fsx: o.fsx });
  return { s, fichier: path.join(dossier, 'synapses.json'), avancer: (ms) => { t += ms; } };
}

test('une synapse inconnue vaut 1 et vit', () => {
  const { s } = synapses();
  assert.strictEqual(s.poids('meuble', 'hum'), 1);
  assert.strictEqual(s.vivante('meuble', 'hum'), true);
});

test('20 mauvais scores l’élaguent, pas 19 ; l’historique le note', () => {
  const { s } = synapses();
  s.mesurer('meuble', 'bon', 1);                                    // une autre, meilleure : la famille n'est pas réduite à elle
  for (let i = 0; i < 19; i++) s.mesurer('meuble', 'hum', 0);
  assert.strictEqual(s.vivante('meuble', 'hum'), true, '19 mesures : pas encore');
  s.mesurer('meuble', 'hum', 0);
  assert.ok(s.poids('meuble', 'hum') < E.SEUIL);
  assert.strictEqual(s.vivante('meuble', 'hum'), false, 'la 20e : élaguée');
  assert.deepStrictEqual(s.historique().map(h => [h.id, h.evenement]), [['hum', 'elaguee']]);
});

test('l’exploration la réessaie 5 fois sur 100, et de bons scores la font repousser', () => {
  let h = 0.99;
  const { s } = synapses({ hasard: () => h });
  s.mesurer('meuble', 'bon', 1);
  for (let i = 0; i < 20; i++) s.mesurer('meuble', 'hum', 0);
  assert.strictEqual(s.vivante('meuble', 'hum'), false);
  h = 0.01;
  assert.strictEqual(s.vivante('meuble', 'hum'), true, 'exploration');
  h = 0.99;
  for (let i = 0; i < 10; i++) s.mesurer('meuble', 'hum', 1);
  assert.strictEqual(s.vivante('meuble', 'hum'), true, 'repoussée');
  assert.deepStrictEqual(s.historique().map(x => x.evenement), ['elaguee', 'repousse']);
});

test('le meilleur de sa famille ne meurt jamais', () => {
  const { s } = synapses();
  for (let i = 0; i < 20; i++) { s.mesurer('voie', 'a', 0); s.mesurer('voie', 'b', 0.05); }
  assert.strictEqual(s.vivante('voie', 'a'), false);
  assert.strictEqual(s.vivante('voie', 'b'), true, 'la plus haute des deux reste');
});

test('épinglée, jamais élaguée ; rétablie, elle repart à 0,5 et à zéro mesure', () => {
  const { s } = synapses();
  s.mesurer('meuble', 'bon', 1);
  s.epingler('meuble', 'hum', true);
  for (let i = 0; i < 30; i++) s.mesurer('meuble', 'hum', 0);
  assert.strictEqual(s.vivante('meuble', 'hum'), true);
  s.epingler('meuble', 'hum', false);
  assert.strictEqual(s.vivante('meuble', 'hum'), false);
  s.retablir('meuble', 'hum');
  assert.strictEqual(s.poids('meuble', 'hum'), 0.5);
  assert.strictEqual(s.tout().meuble.hum.n, 0);
  assert.strictEqual(s.vivante('meuble', 'hum'), true);
});

test('l’oubli ramène vers 0,5, sans dépasser', () => {
  const { s, avancer } = synapses();
  for (let i = 0; i < 5; i++) s.mesurer('meuble', 'hum', 1);
  s.mesurer('meuble', 'bas', 0);
  const avant = s.poids('meuble', 'hum');
  avancer(10 * JOUR);
  s.oublier();
  const apres = s.poids('meuble', 'hum');
  assert.ok(apres < avant && apres > 0.5, `${avant} → ${apres}`);
  s.oublier();
  assert.strictEqual(s.poids('meuble', 'hum'), apres, 'pas deux fois le même oubli');
  assert.ok(s.poids('meuble', 'bas') > 0.9 * 0.9 && s.poids('meuble', 'bas') <= 1, 'une seule mesure basse remonte aussi vers le neutre');
});

test('un fichier illisible : tout vaut 1, sans erreur ; sauver puis relire donne le même état', () => {
  const dossier = fs.mkdtempSync(path.join(os.tmpdir(), 'synapses-'));
  const f = path.join(dossier, 'synapses.json');
  fs.writeFileSync(f, '{pas du json');
  const s = E.creer({ fichier: f });
  assert.strictEqual(s.poids('voie', 'x'), 1);
  for (let i = 0; i < 25; i++) s.mesurer('voie', 'x', 0.2);
  s.sauver(true);
  s.sauver(true);                                                   // deux sauvegardes rapprochées : un JSON valide
  assert.doesNotThrow(() => JSON.parse(fs.readFileSync(f, 'utf8')));
  const r = E.creer({ fichier: f });
  assert.deepStrictEqual(r.tout(), s.tout());
  assert.deepStrictEqual(r.historique(), s.historique());
});

test('poids() et vivante() ne lisent jamais le disque', () => {
  let lectures = 0;
  const fsx = { ...fs, readFileSync: (...a) => { lectures++; return fs.readFileSync(...a); } };
  const { s } = synapses({ fsx });
  const apresChargement = lectures;
  for (let i = 0; i < 1000; i++) { s.poids('voie', `x${i % 7}`); s.vivante('voie', `x${i % 7}`); }
  assert.strictEqual(lectures, apresChargement);
});

test('sauver sans changement n’écrit rien ; avec changement, au plus toutes les 10 s', () => {
  const { s, fichier, avancer } = synapses();
  s.sauver();
  assert.strictEqual(fs.existsSync(fichier), false, 'rien à sauver');
  s.mesurer('voie', 'x', 1);
  s.sauver();
  assert.strictEqual(fs.existsSync(fichier), true);
  s.mesurer('voie', 'x', 0);
  s.sauver();
  assert.strictEqual(JSON.parse(fs.readFileSync(fichier, 'utf8')).familles.voie.x.n, 1, 'moins de 10 s : attend');
  avancer(11000);
  s.sauver();
  assert.strictEqual(JSON.parse(fs.readFileSync(fichier, 'utf8')).familles.voie.x.n, 2);
});

test('(relecture) le témoin : 1 fois sur 10, un déclencheur vivant agit sans prévention, pour être mesuré sans biais', () => {
  assert.strictEqual(synapses({ hasard: () => 0.05 }).s.temoin(), true);
  assert.strictEqual(synapses({ hasard: () => 0.5 }).s.temoin(), false);
});

test('(relecture) le meilleur de son groupe ne meurt jamais : les voies « |suite » gardent la leur, même si une « |premiere » est plus haute', () => {
  const { s } = synapses();
  for (let i = 0; i < 25; i++) { s.mesurer('voie', 'oui|premiere', 1); s.mesurer('voie', 'non|suite', 0.1); s.mesurer('voie', 'jamais|suite', 0); }
  const suite = (k) => k.endsWith('|suite');
  assert.strictEqual(s.vivante('voie', 'non|suite', suite), true, 'la meilleure des « |suite »');
  assert.strictEqual(s.vivante('voie', 'jamais|suite', suite), false);
  assert.strictEqual(s.vivante('voie', 'non|suite'), false, 'sans groupe : la meilleure de la famille est « oui|premiere »');
});
test('(relecture) une entrée abîmée du fichier est remise d’aplomb au chargement', () => {
  const dossier = fs.mkdtempSync(path.join(os.tmpdir(), 'synapses-'));
  const f = path.join(dossier, 'synapses.json');
  fs.writeFileSync(f, JSON.stringify({ familles: { voie: { x: { n: 'abc' }, y: { poids: 9, n: 3 } } } }));
  const s = E.creer({ fichier: f });
  assert.strictEqual(s.poids('voie', 'x'), 1);
  assert.strictEqual(s.poids('voie', 'y'), 1, 'borné à 1');
  s.mesurer('voie', 'x', 0);
  assert.ok(Number.isFinite(s.poids('voie', 'x')));
});

// (04/11, Ahmed : « l'élagage doit être un process continu, qui se fait à chaque sommeil, veille ou sieste »)
test('sa consolidation : l’oubli, le bilan depuis la précédente, notée dans son historique', () => {
  const { s, avancer } = synapses();
  s.mesurer('meuble', 'bon', 1);
  for (let i = 0; i < 20; i++) s.mesurer('meuble', 'hum', 0);
  avancer(3 * 86400000);
  const avant = s.poids('meuble', 'bon');
  const b = s.consolider('eveil→sommeil');
  assert.deepStrictEqual(b.elaguees, ['meuble|hum']);
  assert.deepStrictEqual(b.repoussees, []);
  assert.ok(s.poids('meuble', 'bon') < avant, 'l’oubli lent est passé');
  assert.strictEqual(s.historique().pop().evenement, 'consolidation');
  assert.deepStrictEqual(s.consolider('sommeil→eveil').elaguees, [], 'la suivante ne recompte que le nouveau');
});

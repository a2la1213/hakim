/* Les règles apprises des erreurs, niveau 2 (2026-10-22) : node --test test-regles.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { Regles, enVigueurApres, ACTIVES_MAX, DEBUT } = require('./regles.js');

function monter() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'regles-'));
  const fichier = path.join(dir, 'propositions.json'), regles = path.join(dir, 'regles-de-session.md');
  fs.writeFileSync(regles, '# Règles de session\n\n1. Une règle écrite par Ahmed.\n');
  const props = {};
  for (let k = 0; k < 12; k++) props[`R-00000${k.toString(16)}`] = { id: `R-00000${k.toString(16)}`, recu: k, etat: 'proposee', regle: `Règle ${k}.`, sources: [`e${k}`] };
  fs.writeFileSync(fichier, JSON.stringify({ propositions: props }));
  const evts = [];
  return { R: new Regles({ fichier, regles, evenement: (e) => evts.push(e) }), regles, evts };
}

test('acceptée : deux nuits témoins, puis écrite avec ses sources ; retirée : elle sort ; le texte d’Ahmed reste', () => {
  const x = monter();
  const T = new Date(2026, 9, 22, 14, 0).getTime();
  x.R.trancher('R-000000', 'accepter', T);
  assert.strictEqual(enVigueurApres(T), new Date(2026, 9, 24, 7, 0).getTime());
  assert.ok(!fs.readFileSync(x.regles, 'utf8').includes('Règle 0'));              // pas pendant les nuits témoins
  x.R.ecrireFichierRegles(new Date(2026, 9, 24, 7, 1).getTime());
  const t = fs.readFileSync(x.regles, 'utf8');
  assert.match(t, /1\. Une règle écrite par Ahmed\./);
  assert.match(t, /1\. Règle 0\. — sources : e0 \(acceptée le 22\/10\)/);
  x.R.trancher('R-000000', 'retirer', new Date(2026, 9, 25).getTime());
  assert.ok(!fs.readFileSync(x.regles, 'utf8').includes(DEBUT));
  assert.match(fs.readFileSync(x.regles, 'utf8'), /Une règle écrite par Ahmed/);
  assert.deepStrictEqual(x.evts, ['acceptee', 'retiree']);
});

test('dix règles apprises au plus ; une refusée ne s’écrit pas ; rien ne se tranche deux fois', () => {
  const x = monter();
  for (let k = 0; k < ACTIVES_MAX; k++) x.R.trancher(`R-00000${k.toString(16)}`, 'accepter', Date.now());
  assert.throws(() => x.R.trancher('R-00000a', 'accepter'), /déjà 10/);
  x.R.trancher('R-00000b', 'refuser');
  assert.throws(() => x.R.trancher('R-00000b', 'accepter'), /déjà tranchée/);
  assert.throws(() => x.R.trancher('R-zzzzzz', 'accepter'), /inconnue/);
});

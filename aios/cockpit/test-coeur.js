/* Le cœur de Hakim dans l'appli (28/10 ; idée d'Ahmed, proposition de Hakim à 02:37, go d'Ahmed) : le cockpit dit à l'appli
   s'il réfléchit à une réponse (le « grain ») et si une tâche de fond tourne (le second pouls) ; la page bat avec l'orbe.
   node --test test-coeur.js */
const test = require('node:test');
const assert = require('node:assert');
const C = require('./coeur.js');

test('il réfléchit : un tour en cours depuis moins de 5 min (un tour oublié ne fait pas battre pour toujours)', () => {
  const t = 1_800_000_000_000;
  assert.strictEqual(C.pense(new Map(), t), false);
  assert.strictEqual(C.pense(new Map([['a', { debut: t - 20_000 }]]), t), true);
  assert.strictEqual(C.pense(new Map([['a', { debut: t - 6 * 60_000 }]]), t), false);
  assert.strictEqual(C.pense(new Map([['a', {}]]), t), false, 'sans heure de début : rien');
});

test('les tâches de fond : seulement celles en cours', () => {
  assert.strictEqual(C.fond([{ etat: 'en cours' }, { etat: 'finie' }, { etat: 'en cours' }]), 2);
  assert.strictEqual(C.fond(null), 0);
});

// ---- le câblage (server.js, la page)
const fs = require('node:fs');
const path = require('node:path');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');

test('câblage : l’état intérieur porte pense et fond ; un tour note son début ; la page bat et a son interrupteur', () => {
  assert.match(src, /toursActifs\.set\(tourId, \{ arreter, debut: Date\.now\(\) \}\)/);
  assert.match(src, /const pense = coeur\.pense\(toursActifs\), fond = coeur\.fond\(lireTaches\(\)\);/);
  assert.match(src, /      pense, fond, coeur_bpm: /);
  assert.match(page, /window\.battementCoeur = /);
  assert.match(page, /HakimApp\.coeur\(/);
  assert.match(html, /id="coeur"/);
});

// ---- le cœur v2 (28/10, 03:18, Ahmed : « directement à tes hormones ») : le rythme vient d'Anamnèse (coeur.py)
test('le journal du cœur : une ligne quand ce que l’appli doit battre change, pas à chaque lecture', () => {
  const lignes = [];
  const j = C.journal((l) => lignes.push(l));
  j({ bpm: 40.2, pense: false, fond: 0 }, 1000);
  j({ bpm: 40.4, pense: false, fond: 0 }, 2000);          // même battement arrondi : rien
  j({ bpm: 52, pense: true, fond: 0 }, 3000);
  j({ bpm: 52, pense: true, fond: 1 }, 4000);
  assert.deepStrictEqual(lignes.map(l => [l.t, l.bpm, l.pense, l.fond]), [[1000, 40, false, 0], [3000, 52, true, 0], [4000, 52, true, 1]]);
});

test('câblage v2 : l’état intérieur porte le rythme de ses hormones, et son bloc intérieur ce qu’il en sent', () => {
  assert.match(src, /coeur_bpm: frais && e\.coeur && Number\.isFinite\(e\.coeur\.bpm\) \? e\.coeur\.bpm : null/);
  assert.match(src, /coeur_raideur: /);
  assert.match(src, /journalCoeur\(/);
  const bloc = src.slice(src.indexOf('async function blocInterieur('), src.indexOf('\n}\n', src.indexOf('async function blocInterieur(')));
  assert.match(bloc, /e\.coeur && typeof e\.coeur\.ressenti === 'string'/);
});

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
  assert.match(src, /pense: coeur\.pense\(toursActifs\)/);
  assert.match(src, /fond: coeur\.fond\(lireTaches\(\)\)/);
  assert.match(page, /window\.battementCoeur = /);
  assert.match(page, /HakimApp\.coeur\(/);
  assert.match(html, /id="coeur"/);
});

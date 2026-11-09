'use strict';
// (09/11) la simulation des trois modes (simulation-modes.js) : son modèle suit le code sur les points qui décident des réglages
const test = require('node:test'), assert = require('node:assert');
const { simulerTour, delaiLecteur, blancsParSeconde } = require('./simulation-modes.js');

const D = { corps: { tunnel: true, tournesol: true }, transcription: { a: 2000, b: 500 }, azure: [2500], vivant: [3000], pDire: 1, motsPensee: [8],
  premierMot: [10000], voixMs: [3000], ditMots: { haiku: [20], sonnet: [30], opus: [40] }, vitesse: { haiku: 0.8, sonnet: 1, opus: 1.5 }, motsSeconde: 3.7 };
const tour = { debut: 0, fin: 20000, mots: 60, suivant: 120000 };
const g = (x) => ({ choix_ms: 0, chunk_papa_ms: 1100, plafond_mots: 50, relais_pct: 100, relais_ribosomes: 1, stringence: 2, ...x });

test('à 1 s et plus, aucun morceau coupé pendant ta parole : il ne peut pas te couper', () => {
  for (let s = 1; s < 30; s++) assert.strictEqual(simulerTour(D, tour, 'Hakim', g({ chunk_papa_ms: 1100 }), s, 2).coupures, 0);
});
test('sous 1 s, des morceaux pendant ta parole : son premier mot arrive plus tôt, et il peut te couper', () => {
  let tot = 0, avant = 0, apres = 0;
  for (let s = 1; s < 60; s++) {
    const a = simulerTour(D, tour, 'Hakim', g({ chunk_papa_ms: 400 }), s, 2), b = simulerTour(D, tour, 'Hakim', g({ chunk_papa_ms: 1100 }), s, 2);
    tot += a.coupures; if (a.premier != null) avant += a.premier; if (b.premier != null) apres += b.premier;
  }
  assert.ok(tot > 0, 'des coupures quand ses pensées arrivent pendant ta parole');
  assert.ok(avant < apres, 'son premier mot plus tôt');
});
test('sous 600 ms de choix, aucun lecteur appelé ; à 2 s, des lecteurs (et des appels en plus)', () => {
  const a = simulerTour(D, tour, 'Mini Hakim', g({ choix_ms: 0 }), 7, 1), b = simulerTour(D, tour, 'Mini Hakim', g({ choix_ms: 2000 }), 7, 1);
  assert.ok(b.appels > a.appels);
});
test('ses lecteurs : rien à 600 ms (mesuré ce soir : 184 paquets, aucune lecture), 73 % à 1,6 s (mesuré le 04/11)', () => {
  let n600 = 0, n1600 = 0; const r = (() => { let i = 0; return () => ((i++ * 0.6180339887) % 1); })();
  for (let i = 0; i < 2000; i++) { const x = delaiLecteur(r); if (x <= 600) n600++; if (x <= 1600) n1600++; }
  assert.strictEqual(n600, 0);
  assert.ok(Math.abs(n1600 / 2000 - 0.73) < 0.03);
});
test('les blancs de ta voix : moins nombreux quand ils sont plus longs', () => {
  assert.ok(blancsParSeconde(400) > blancsParSeconde(800));
});

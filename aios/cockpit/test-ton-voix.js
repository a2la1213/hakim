/* Le ton de la voix en direct (27/10 ; test figé dans anamnese/eval/ton_voix : l'éveil passe, la valence non ; Ahmed,
   22:48 : « parfait, je suis tout à fait d'accord » pour l'éveil seulement, avec son doute ; point dans quelques jours).
   node --test test-ton-voix.js */
const test = require('node:test');
const assert = require('node:assert');
const T = require('./ton-voix.js');

test('un tour : la moyenne des morceaux pondérée par leur durée, et qui parle', () => {
  assert.deepStrictEqual(T.tour([{ eveil: 0.3, duree_s: 2, verdict: 'ahmed' }, { eveil: 0.6, duree_s: 4, verdict: 'ahmed' }]),
    { eveil: 0.5, duree_s: 6, verdict: 'ahmed' });
  assert.strictEqual(T.tour([{ eveil: 0.3, duree_s: 2, verdict: 'ahmed' }, { eveil: 0.6, duree_s: 4, verdict: 'autre' }]).verdict, 'plusieurs');
  assert.strictEqual(T.tour([{ eveil: 0.3, duree_s: 2, verdict: 'autre' }, { eveil: 0.6, duree_s: 4, verdict: 'doute' }]).verdict, 'autre');
  assert.strictEqual(T.tour([{ eveil: 0.3, duree_s: 2, verdict: null }]), null, 'empreinte pas apprise : on ne sait pas qui parle');
  assert.strictEqual(T.tour([]), null);
});

test('Ahmed : seulement un écart net à SA voix d’habitude, animée ou calme, jamais joie ni tristesse', () => {
  const habitude = Array(10).fill(0.40);
  assert.strictEqual(T.mots({ eveil: 0.43, duree_s: 5, verdict: 'ahmed' }, habitude), '', 'comme d’habitude : rien');
  assert.strictEqual(T.mots({ eveil: 0.50, duree_s: 5, verdict: 'ahmed' }, habitude), "sa voix semble un peu plus animée que d'habitude");
  assert.strictEqual(T.mots({ eveil: 0.58, duree_s: 5, verdict: 'ahmed' }, habitude), "sa voix semble nettement plus animée que d'habitude");
  assert.strictEqual(T.mots({ eveil: 0.30, duree_s: 2, verdict: 'ahmed' }, habitude),
    "sa voix semble un peu plus calme que d'habitude (impression légère : phrase courte)");
  for (const e of [0.1, 0.3, 0.5, 0.9]) assert.doesNotMatch(T.mots({ eveil: e, duree_s: 5, verdict: 'ahmed' }, habitude), /joie|joyeu|triste|tendu|colère|peur/);
  // sans habitude encore : une base prudente (0,40) complète les premiers tours
  assert.strictEqual(T.base([]), 0.4);
  assert.strictEqual(T.base([0.5, 0.5]), 0.4);
  assert.strictEqual(T.base([0.5, 0.5, 0.5, 0.5, 0.5]), 0.5);
});

test('les invités : l’ambiance de la salle seulement, jamais une personne ; leur voix n’entre pas dans l’habitude d’Ahmed', () => {
  assert.strictEqual(T.mots({ eveil: 0.6, duree_s: 5, verdict: 'plusieurs' }, []), "l'ambiance de la salle semble animée");
  assert.strictEqual(T.mots({ eveil: 0.2, duree_s: 5, verdict: 'autre' }, []), "l'ambiance de la salle semble calme");
  assert.strictEqual(T.mots({ eveil: 0.4, duree_s: 5, verdict: 'autre' }, []), '');
  assert.doesNotMatch(T.mots({ eveil: 0.6, duree_s: 5, verdict: 'plusieurs' }, []), /sa voix|Ahmed/);
  const v = [0.4];
  assert.strictEqual(T.ajouter(v, { eveil: 0.6, duree_s: 5, verdict: 'plusieurs' }), v);
  assert.deepStrictEqual(T.ajouter(v, { eveil: 0.6, duree_s: 5, verdict: 'ahmed' }), [0.4, 0.6]);
  assert.strictEqual(T.ajouter(Array(40).fill(0.4), { eveil: 0.6, duree_s: 5, verdict: 'ahmed' }).length, 40);
  assert.strictEqual(T.ajouter(v, { eveil: 0.6, duree_s: 1, verdict: 'ahmed' }), v, 'trop court pour apprendre son habitude');
});

// ---- le câblage (server.js)
const fs = require('node:fs');
const path = require('node:path');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

test('câblage : chaque morceau oral rend son éveil, le tour le dit dans son Présent vécu, jamais un chiffre', () => {
  assert.match(prendre('routeTranscrire'), /tonsRecus\.push\(/);
  assert.match(prendre('routeTranscrire'), /delete r\.ton/);
  assert.match(src, /prosodieDepuis\(voixDepuis\) \+ tonVoixDepuis\(voixDepuis\)/);
  assert.match(prendre('tonVoixDepuis'), /une impression de l'oreille, pas un fait sur ce qu'il ressent/);
});

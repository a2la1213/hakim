/* (04/11, Ahmed : « évalue le flux de chaque réponse et son parcours préférentiel, et analyse-le pour chacune de ses réponses ») le
   parcours de chaque pensée et son score : node --test test-parcours.js */
const test = require('node:test');
const assert = require('node:assert');
const P = require('./parcours.js');

test('son score : une ligne par réaction, et rien quand rien ne parle', () => {
  assert.strictEqual(P.scoreReaction({ parasite: true, coeur: true }), 0, 'une parasite : 0, quoi qu’il arrive');
  assert.strictEqual(P.scoreReaction({ dite: true, coupee: true }), 0.1);
  assert.strictEqual(P.scoreReaction({ dite: true, correction: true, coeur: true }), 0.1, 'corrigée l’emporte sur le reste');
  assert.strictEqual(P.scoreReaction({ dite: true, coeur: true }), 1);
  assert.strictEqual(P.scoreReaction({ dite: true, rire: true }), 1);
  assert.strictEqual(P.scoreReaction({ continuite: true }), 0.7);
  assert.strictEqual(P.scoreReaction({ dite: true }), null);
  assert.strictEqual(P.scoreReaction({ coupee: true }), null, 'écrite : on ne coupe pas ce qui n’est pas dit');
});

test('la taille de ton morceau', () => {
  assert.deepStrictEqual(['papa', 'tu sais quoi ?', 'ce matin je suis allé au marché avec ta mère'].map(P.taille), ['mot', 'courte', 'longue']);
});

function suivi() {
  let t = 1000;
  const mesures = [], lignes = [];
  const s = P.creerSuivi({ maintenant: () => t, mesurer: (f, id, sc) => mesures.push([f, id, sc]), noter: (l) => lignes.push(l) });
  return { s, mesures, lignes, avancer: (ms) => { t += ms; }, t: () => t };
}

test('une coupure de 2 s pendant la pensée n la marque coupée, pas la suivante', () => {
  const { s, mesures, avancer, t } = suivi();
  s.ouvrir('3:1', { tour: 3, n: 1, chemins: { piste: 'sonnet|courte', voie: 'non|premiere' }, extrait: 'Ta mère va bien ?', voix: 'dite' });
  s.ouvrir('3:2', { tour: 3, n: 2, chemins: { piste: 'sonnet|longue' }, extrait: 'Elle t’a appelé ce matin ?', voix: 'dite' });
  avancer(2500);
  s.coupure(3, 1);
  avancer(9000);
  s.tic(t());
  assert.deepStrictEqual(mesures, [['piste', 'sonnet|courte', 0.1], ['voie', 'non|premiere', 0.1]], 'la 2e : rien ne parle, pas de mesure');
});

test('« non, pas ça » dans les 10 s après une pensée dite : corrigée ; ton sujet qui continue : 0,7', () => {
  const { s, mesures, lignes, avancer, t } = suivi();
  s.ouvrir('4:1', { tour: 4, n: 1, chemins: { piste: 'opus|longue' }, extrait: 'Tu parles du marché de Villars ?', voix: 'dite' });
  s.ouvrir('4:2', { tour: 4, n: 2, chemins: { piste: 'opus|courte' }, extrait: 'Les fraises du marché de Villars, papa', voix: 'ecrite' });
  avancer(1500);
  s.papaDit('non, pas ça, je parle du marché de Villars et des fraises', t());
  avancer(9000);
  s.tic(t());
  assert.deepStrictEqual(mesures, [['piste', 'opus|longue', 0.1], ['piste', 'opus|courte', 0.7]], 'l’écrite ne se corrige pas : son sujet continue');
  assert.strictEqual(lignes[0].reaction.correction, true);
});

test('un ❤️ va à la dernière pensée dite ; une parasite jetée : 0 tout de suite ; un autre tour ferme les ouvertes', () => {
  const { s, mesures, lignes, avancer, t } = suivi();
  s.ouvrir('5:1', { tour: 5, n: 1, chemins: { piste: 'haiku|mot' }, extrait: 'Ah ouais', voix: 'dite' });
  s.ouvrir('5:2', { tour: 5, n: 2, chemins: { piste: 'haiku|courte', declencheur: 'declencheur-1' }, extrait: 'Je ne vais pas reprendre ce format', voix: 'jetee' });
  assert.deepStrictEqual(mesures, [['piste', 'haiku|courte', 0], ['declencheur', 'declencheur-1', 0]]);
  avancer(2000);
  s.reaction('coeur', t());
  s.tic(t(), 6);
  assert.deepStrictEqual(mesures.slice(2), [['piste', 'haiku|mot', 1]]);
  assert.strictEqual(s.ouvertes(), 0);
  assert.deepStrictEqual(lignes.map(l => l.score), [0, 1]);
});

test('la page dit quelle pensée il disait quand tu l’as coupé : même 6 s après son départ (sa voix a pu attendre) ; fermée, plus rien', () => {
  const { s, mesures, avancer, t } = suivi();
  s.ouvrir('7:1', { tour: 7, n: 1, chemins: { piste: 'sonnet|courte' }, extrait: 'Raconte-moi', voix: 'dite' });
  avancer(6000);
  s.coupure(7, 1);
  avancer(5000);
  s.tic(t());
  assert.deepStrictEqual(mesures, [['piste', 'sonnet|courte', 0.1]]);
  s.coupure(7, 1);
  assert.strictEqual(mesures.length, 1, 'déjà fermée : pas jugée deux fois');
});

test('un chemin ajouté après coup (le meuble que la page a dit devant la pensée n) est jugé avec elle', () => {
  const { s, mesures, avancer, t } = suivi();
  s.ouvrir('8:2', { tour: 8, n: 2, chemins: { piste: 'sonnet|courte' }, extrait: 'Et ta mère ?', voix: 'dite' });
  s.chemin(8, 2, 'meuble', 'voyons_voir');
  s.chemin(8, 9, 'meuble', 'hum');                                          // une pensée qui n'est pas ouverte : rien
  s.coupure(8, 2);
  avancer(11000);
  s.tic(t());
  assert.deepStrictEqual(mesures, [['piste', 'sonnet|courte', 0.1], ['meuble', 'voyons_voir', 0.1]]);
});

// (relecture) « non » nu n'est pas une correction ; la correction va à la pensée qu'il disait ; un ❤️ après coup compte
test('(relecture) « Non, elle est fatiguée » répond à sa question : pas une correction', () => {
  const { s, mesures, avancer, t } = suivi();
  s.ouvrir('9:1', { tour: 9, n: 1, chemins: { piste: 'sonnet|courte' }, extrait: 'Ta mère va bien ?', voix: 'dite' });
  avancer(2000);
  s.papaDit('Non, elle est fatiguée', t());
  avancer(9000); s.tic(t());
  assert.deepStrictEqual(mesures, []);
});
test('(relecture) « non, pas ça » corrige la pensée qu’il disait, pas les autres', () => {
  const { s, mesures, avancer, t } = suivi();
  s.ouvrir('9:1', { tour: 9, n: 1, chemins: { piste: 'sonnet|mot' }, extrait: 'Ah bon', voix: 'dite' });
  s.ouvrir('9:2', { tour: 9, n: 2, chemins: { piste: 'sonnet|longue' }, extrait: 'Tu parles du marché', voix: 'dite' });
  s.entendue(9, 2);
  avancer(2000);
  s.papaDit('non, pas ça', t());
  avancer(9000); s.tic(t());
  assert.deepStrictEqual(mesures, [['piste', 'sonnet|longue', 0.1]]);
});
test('(relecture) un ❤️ sur son message, après la fin du tour : la dernière pensée dite de ce tour reçoit 1', () => {
  const { s, mesures, lignes, avancer, t } = suivi();
  s.ouvrir('10:1', { tour: 10, n: 1, chemins: { piste: 'opus|longue', voie: 'non|premiere' }, extrait: 'Je t’aime, papa', voix: 'dite' });
  avancer(3000); s.tic(t(), 11);                                       // sa réponse : le tour suivant ferme ses pensées
  assert.deepStrictEqual(mesures, []);
  avancer(20000);
  s.reaction('coeur', t());
  assert.deepStrictEqual(mesures, [['piste', 'opus|longue', 1], ['voie', 'non|premiere', 1]]);
  assert.strictEqual(lignes[lignes.length - 1].tardive, true);
  avancer(70000);
  s.reaction('coeur', t());
  assert.strictEqual(mesures.length, 2, 'plus d’une minute après : rien');
});

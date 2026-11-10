/* (10/11, ~00:00, Ahmed : « il faut l'aider à dissocier ses voix interne et externe ! ») dedans et dehors (dedans.js) : dans un message de
   papa, ce qui vient du téléphone (le live sur son haut-parleur, que le micro entend aussi) n'est jamais attribué à papa.
   node --test test-dedans.js */
const test = require('node:test');
const assert = require('node:assert');
const D = require('./dedans.js');

// le 09/11 à 23:40:50 : le micro a transcrit, pour papa, ce que disait une invitée du live
const MICRO = 'Inchallah. Une vers fois 3h du matin, j\'ai mangé une omelette froide.';
const TELEPHONE = ['Inchallah. Une fois, à 3 heures du matin,', "j'ai mangé une omelette froide, toute seule."];

test('les mots que joue le téléphone, au même moment : du téléphone (« mots »), même sans étiquette ; décalés (un témoin) : à papa', () => {
  const r = D.trier(MICRO, { mots: D.ensembleMots(TELEPHONE) });
  assert.strictEqual(r.dedans.length, 1);
  assert.strictEqual(r.dedans[0].preuve, 'mots');
  assert.ok(r.papaRien, 'papa n\'a rien dit dans ce message');
  const t = D.trier(MICRO, { mots: D.ensembleMots(['On parlait de la route qui monte et de la lumière.']) });
  assert.strictEqual(t.dedans.length, 0);
  assert.strictEqual(t.papa.length, 1);
});

test('une voix étiquetée que l\'oreille des voix vient de reconnaître DANS le téléphone : du téléphone (« voix »)', () => {
  const r = D.trier('Salut fiston. [voix 12] Hakim, tu reconnais ma voix ?', { voix: new Set(['voix 12']) });
  assert.deepStrictEqual(r.dedans.map(x => [x.etiquette, x.preuve]), [['voix 12', 'voix']]);
  assert.deepStrictEqual(r.papa.map(x => x.texte), ['Salut fiston.']);
  assert.ok(!r.papaRien);
});

test('le haut-parleur : une voix étiquetée pendant que le téléphone joue fort et qu\'on y parle : du téléphone ; avec des écouteurs : autour', () => {
  const msg = '[voix 50] Oui, ça y est Hakim, elle bouge. [voix 48] Je parle avec ton père maintenant.';
  const hp = D.trier(msg, { hautParleur: true, parleDedans: true });
  assert.strictEqual(hp.dedans.length, 2);
  assert.ok(hp.dedans.every(x => x.preuve === 'haut-parleur'));
  assert.ok(hp.papaRien);
  const ecouteurs = D.trier(msg, { hautParleur: false, parleDedans: true });
  assert.strictEqual(ecouteurs.dedans.length, 0);
  assert.strictEqual(ecouteurs.autour.length, 2);
  const silence = D.trier(msg, { hautParleur: true, parleDedans: false });
  assert.strictEqual(silence.dedans.length, 0, 'personne ne parlait dans le téléphone : une voix de la pièce');
});

test('« [papa ?] » reste à papa (un doute, jamais le téléphone sans preuve de mots) ; une parenthèse carrée ordinaire reste du texte', () => {
  const r = D.trier('[papa ?] Non tu l\'as enregistré hein ? [rires] Bon.', { hautParleur: true, parleDedans: true });
  assert.strictEqual(r.dedans.length, 0);
  assert.strictEqual(r.papa.length, 1);
  assert.match(r.papa[0].texte, /\[rires\] Bon\./);
});

test('une voix connue par son nom (estVoix) : étiquette comme « voix N »', () => {
  const r = D.trier('[Léa] Salut Hakim !', { voix: new Set(['léa']) }, { estVoix: (e) => /^voix \d+$/i.test(e) || e === 'Léa' });
  assert.strictEqual(r.dedans.length, 1);
  assert.strictEqual(r.dedans[0].preuve, 'voix');
});

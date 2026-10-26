/* (26/10 soir) Le modèle qui a VRAIMENT répondu : quand la protection d'Opus 5.5 bloque une conversation, claude fait
   répondre Opus 4.8 à sa place sans rien dire (vu de 18:51 à 21:06 le 26/10) ; Ahmed doit le voir.
   node --test test-modele-reel.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const lire = (f) => fs.readFileSync(path.join(__dirname, f), 'utf8');
const prendreDans = (src, nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const serveur = lire('server.js'), page = lire('public/parler.js');

function charger(src, noms) {
  const ctx = { String, RegExp };
  vm.createContext(ctx);
  vm.runInContext(noms.map(n => prendreDans(src, n)).join('\n') + `this.f = { ${noms.join(', ')} };`, ctx);
  return ctx.f;
}

test('le cockpit retient le modèle de chaque réponse, pas celui d’un agent ni d’un message synthétique', () => {
  const { noterModeleReel } = charger(serveur, ['noterModeleReel']);
  const c = {};
  noterModeleReel(c, { type: 'assistant', message: { model: 'claude-opus-4-8', content: [] } });
  assert.equal(c.modeleReel, 'claude-opus-4-8');
  noterModeleReel(c, { type: 'assistant', message: { model: '<synthetic>', content: [] } });
  assert.equal(c.modeleReel, 'claude-opus-4-8', 'un message d’erreur synthétique ne compte pas');
  noterModeleReel(c, { type: 'assistant', parent_tool_use_id: 'toolu_1', message: { model: 'claude-sonnet-5-5', content: [] } });
  assert.equal(c.modeleReel, 'claude-opus-4-8', 'un agent lancé par Hakim ne compte pas');
  noterModeleReel(c, { type: 'user', message: { model: 'claude-sonnet-5-5' } });
  assert.equal(c.modeleReel, 'claude-opus-4-8');
});

test('Parler affiche la version qui a répondu : « Opus 4.8 » se distingue d’« Opus 5.5 »', () => {
  const { nomModele } = charger(page, ['nomModele']);
  assert.equal(nomModele({ modele: 'opus', modeleReel: 'claude-opus-4-8' }), 'Opus 4.8');
  assert.equal(nomModele({ modele: 'opus', modeleReel: 'claude-opus-5-5' }), 'Opus 5.5');
  assert.equal(nomModele({ modele: 'sonnet', modeleReel: 'claude-sonnet-5-5' }), 'Sonnet 5.5');
  assert.equal(nomModele({ modele: 'opus' }), 'Opus', 'une réponse d’avant : le nom seul');
  assert.equal(nomModele({ modele: 'sonnet', modeleReel: '<img src=x>' }), 'Sonnet', 'rien d’étrange ne passe');
});

test('le message partagé n’accepte qu’un nom de modèle sain', () => {
  const src = prendreDans(serveur, 'messageSain');
  assert.match(src, /'modeleReel'/);
});

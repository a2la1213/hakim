// (04/11, 10:35, Ahmed : « quand une tâche de fond se termine, il doit pouvoir choisir ce qu'il dit, et pas seulement dire
// "ma tâche de fond est terminée" ») la page ne met plus de phrase toute faite dans sa bouche : une ligne de fait à l'écran,
// puis c'est lui, réveillé par le cockpit, qui choisit ce qu'il en dit (ou de se taire).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (s, nom) => { const i = s.indexOf(`function ${nom}(`); return s.slice(i, s.indexOf('\n}\n', i) + 2); };

function finDeTache(o) {
  const dit = [], notes = [];
  const ctx = { Math, etat: { messages: [], flux: null }, sauver() {}, rendre() {}, humeur: (h) => notes.push(h), notifierApp: (t, x) => notes.push(t),
    jarvisPeutParler: () => true, lecteur: { actif: false, dire: (t) => dit.push(t), finFlux() {} }, Date };
  vm.createContext(ctx);
  vm.runInContext(prendre(page, 'surTache') + 'this.f = surTache;', ctx);
  ctx.f(o);
  return { dit, message: ctx.etat.messages[0] };
}

test('la fin d’une tâche ne lui fait plus dire une phrase toute faite', () => {
  for (const o of [{ id: 't1', etat: 'finie', code: 0, duree_s: 42, commande: 'python calcul.py', reveil: true },
                   { id: 't2', etat: 'arrêtée', code: 1, raison: 'délai', duree_s: 9, commande: 'npm test', reveil: false }]) {
    const { dit, message } = finDeTache(o);
    assert.deepEqual(dit, [], 'sa voix : rien de tout fait');
    assert.equal(message.spontane, 'tache');
    assert.ok(!/\bje\b|\bj’|\bj'|\bme\b|\bmon\b|\bma\b/i.test(message.texte), `pas à la première personne : ${message.texte}`);
    assert.match(message.texte, new RegExp(o.commande.replace('.', '\\.')));
  }
  assert.match(finDeTache({ id: 't3', etat: 'finie', code: 0, duree_s: 3, commande: 'ls', reveil: true }).message.texte, /il choisit ce qu’il t’en dit/);
  assert.match(finDeTache({ id: 't4', etat: 'finie', code: 0, duree_s: 3, commande: 'ls', reveil: false }).message.texte, /Demande-lui le résultat/);
});

test('réveillé à la fin de sa tâche, il choisit lui-même ce qu’il en dit, ou rien', () => {
  const f = prendre(src, 'reveillerPourTaches');
  assert.match(f, /Choisis toi-même ce que tu en dis à Ahmed/);
  assert.doesNotMatch(f, /ce qu'il montre et ce que tu en conclus/);
  assert.match(f, /n\\'a vu qu\\'une ligne « tâche terminée », rien de toi/);
  assert.match(f, /réponds exactement « No response requested\. »/, 'se taire reste son choix');
});

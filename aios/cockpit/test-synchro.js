/* La synchronisation de la conversation partagée (bug du 2026-10-23 : ses tours « de lui-même » entendus mais jamais
   affichés, passé 1 000 messages) : node --test test-synchro.js
   synchroniser() est lu dans parler.js et joué à part, avec un faux cockpit. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const i = src.indexOf('let synchroEnAttente = 0;'), f = src.indexOf('\n}\n', src.indexOf('async function synchroniser')) + 2;

function page(locaux, serveur) {
  const sauves = [], journal = [];
  const ctx = {
    Math, Number, Set, JSON, Array,
    etat: { messages: locaux.slice(), flux: null, conversation: null, session: null },
    lecteur: { actif: false }, majConversation: 1, debutConversation: 0,
    fetch: async () => ({ json: async () => JSON.parse(JSON.stringify(serveur)) }),
    sauver: () => sauves.push(1), garderLocal() {}, rendre() {}, accuserReception: async () => {}, journalVoix: (e) => journal.push(e),
  };
  vm.createContext(ctx);
  vm.runInContext('var majConversation = 1, debutConversation = 0;' + src.slice(i, f) + 'this.synchroniser = synchroniser;', ctx);
  return { ctx, sauves, journal };
}
const msg = (id, extra = {}) => ({ id: String(id), qui: id % 2 ? 'j' : 'u', texte: `m${id}`, ...extra });

test('passé 1 000 messages : les plus anciens rangés par le cockpit ne bloquent plus la synchronisation', async () => {
  const serveur = { maj_ms: 99, debut_ms: 0, messages: [] };
  for (let k = 2000; k < 2999; k++) serveur.messages.push(msg(k));
  serveur.messages.push({ id: 'auto-1', qui: 'j', spontane: 'resultat', texte: 'le codeur a fini', ts: 2999 });   // reçu par le cockpit seul
  const locaux = [];
  for (let k = 1982; k < 2981; k++) locaux.push(msg(k));                                    // 18 plus anciens, 18 récents manquants
  const p = page(locaux, serveur);
  await p.ctx.synchroniser();
  assert.equal(p.sauves.length, 0, 'plus de renvoi sans fin');
  assert.ok(p.ctx.etat.messages.some(m => m.id === 'auto-1'), 'son tour de lui-même apparaît');
  assert.equal(p.ctx.etat.messages.length, 1000);
});

test("un message vraiment neuf d'ici : renvoyé d'abord ; toujours refusé, il est fusionné ici, rien n'est perdu", async () => {
  const serveur = { maj_ms: 99, debut_ms: 0, messages: [msg(10), msg(11), { id: 'auto-2', qui: 'j', texte: 'x', ts: 13 }] };
  const p = page([msg(10), msg(11), msg(12)], serveur);
  await p.ctx.synchroniser(); await p.ctx.synchroniser();
  assert.equal(p.sauves.length, 2);
  assert.ok(!p.ctx.etat.messages.some(m => m.id === 'auto-2'));
  await p.ctx.synchroniser();
  assert.deepEqual(p.ctx.etat.messages.map(m => m.id), ['10', '11', '12', 'auto-2']);
  assert.deepEqual(p.journal, ['synchro_fusion_locale']);
});

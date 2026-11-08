// (04/11, 17:00, Ahmed : « le bouton non nuisible, quand il repère un nuisible dans Immunité, ne fonctionne pas ») trouvé : son geste
// « Pas une vraie parasite » demande sa présence pour « immunite:pas_parasite:… », et l'action était refusée (« action invalide ») à cause du
// tiret bas ; jamais rien n'arrivait au cockpit (aucune trace au journal)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const IMM = fs.readFileSync(path.join(__dirname, 'public', 'immunite.html'), 'utf8');

test('chaque geste qui demande ta présence a une action acceptée par /api/presence/options', () => {
  const i = SRC.indexOf("if (p === '/api/presence/options' && req.method === 'POST') {");
  const m = /if \(!(\/\^[^\n]*?\$\/)\.test\(action\)\)/.exec(SRC.slice(i, i + 800));
  assert.ok(m, 'le motif des actions');
  const motif = eval(m[1]);
  const actions = [...IMM.matchAll(/preuvePresence\(`([a-z_:-]+):\$\{/g)].map(x => `${x[1]}:0123456789abcdef`);
  assert.ok(actions.includes('immunite:pas_parasite:0123456789abcdef'), 'le geste « Pas une vraie parasite »');
  for (const a of actions) assert.ok(motif.test(a), `accepté : ${a}`);
  assert.ok(!motif.test('immunite:soi:<script>'), 'toujours rien d’autre que des lettres, tirets et tirets bas');
});

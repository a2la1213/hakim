/* (25/10, Ahmed) les agents de Hakim : sa mémoire en lecture, un témoin vierge, ses propres agents sous liste blanche.
   node --test test-agents-hakim.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const bloc = (debut, fin) => src.slice(src.indexOf(debut), src.indexOf(fin));

function monde() {
  const ctx = { fs, path, JSON, String, Object, Set, RegExp, JARVIS: '/x', JARVIS_CWD: '/x/cwd', PREAMBULE_MATHS: '/nulle/part' };
  vm.createContext(ctx);
  vm.runInContext(bloc('const LECTURE = [', 'const PREAMBULE_MATHS') + prendre('agentsRefuses') + prendre('agentsPourCerveau')
    + 'this.f = { AGENTS, agentsDeHakim, agentsPourCerveau };', ctx);
  return ctx.f;
}

test('le juge lit sa mémoire mais ni sa mémoire de travail ni son humeur ; le témoin vierge n’a rien', () => {
  const { AGENTS } = monde();
  for (const r of ['architecte', 'codeur', 'juge']) {
    assert.ok(AGENTS[r].tools.includes('mcp__anamnese__erreurs_lister'), `${r} lit le carnet d’erreurs`);
    assert.ok(AGENTS[r].tools.includes('mcp__anamnese__carnets'), `${r} lit les prédictions`);
  }
  assert.ok(!AGENTS.juge.tools.includes('mcp__anamnese__working_memory'));
  assert.ok(!AGENTS.juge.tools.some(t => /mood|interoception|introspection|memory_store|courrier|jardin/.test(t)));
  assert.deepEqual([...AGENTS.vierge.tools], []);
});

test('ses agents : liste blanche seulement, noms propres, jamais un nom réservé', () => {
  const { agentsDeHakim } = monde();
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'agents-'));
  fs.writeFileSync(path.join(d, 'a.md'), '---\nnom: temoin-physique\ndescription: relit un calcul\noutils: lecture, calcul, courrier, Task\nmodele: opus\n---\nTu relis.');
  fs.writeFileSync(path.join(d, 'b.md'), '---\nnom: juge\ndescription: usurpe\noutils: aucun\n---\nx');
  fs.writeFileSync(path.join(d, 'c.md'), '---\nnom: general-purpose\noutils: aucun\n---\nx');
  fs.writeFileSync(path.join(d, 'd.md'), 'pas de tête');
  const a = agentsDeHakim(d);
  assert.deepEqual(Object.keys(a), ['temoin-physique']);
  assert.equal(a['temoin-physique'].model, 'opus');
  assert.ok(a['temoin-physique'].tools.includes('mcp__calcul__executer_python'));
  assert.ok(!a['temoin-physique'].tools.some(t => /courrier|Task|memory_store/.test(t)), 'rien hors de la liste blanche');
});

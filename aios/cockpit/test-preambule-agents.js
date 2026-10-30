/* Le préambule des maths du réel dans la consigne de chaque agent de Hakim (24/10, demande d'Ahmed relayée par Hakim) :
   node --test test-preambule-agents.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
function cockpit(preambule) {
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), 'preambule-'));
  if (preambule !== undefined) {
    fs.mkdirSync(path.join(cwd, 'atelier', 'ancrage'), { recursive: true });
    fs.writeFileSync(path.join(cwd, 'atelier', 'ancrage', 'PREAMBULE_AGENTS.md'), preambule);
  }
  const ctx = { fs, path, Object, String, Buffer, JARVIS_CWD: cwd };
  vm.createContext(ctx);
  const i = srv.indexOf('const LECTURE = '), lecture = srv.slice(i, srv.indexOf('const AGENTS = {'));
  vm.runInContext(lecture + srv.slice(srv.indexOf('const AGENTS = {'), srv.indexOf('const jourLocal')) + 'this.AGENTS = AGENTS; this.pour = agentsPourCerveau;', ctx);
  return ctx;
}

test('chaque agent reçoit le préambule, avec son chemin et la condition « si ta mission touche à ce sujet »', () => {
  const c = cockpit('# Préambule\n1. Lis EN ENTIER MATHS_DU_REEL_MERE.md.\n3. Plafond M à un seul grain (M symbolique).');
  const a = c.pour();
  for (const nom of ['codeur', 'architecte', 'juge']) {
    assert.ok(a[nom].prompt.startsWith(c.AGENTS[nom].prompt), nom);
    assert.match(a[nom].prompt, /Plafond M à un seul grain \(M symbolique\)/);
    assert.match(a[nom].prompt, /si ta mission touche aux maths ou à la physique du réel|Si ta mission touche aux maths ou à la physique du réel/);
    assert.match(a[nom].prompt, /atelier\/ancrage\/MATHS_DU_REEL_MERE\.md/);
    // (29/10) les outils ne changent pas, sauf les deux du café, que chacun reçoit
    assert.deepEqual(a[nom].tools, [...new Set([...c.AGENTS[nom].tools, 'mcp__terminal__cafe_lire', 'mcp__terminal__cafe_dire'])], 'les outils ne changent pas');
  }
});

// (28/10) dans le bac à sable d'un chantier (CHANTIER_BAC_A_SABLE=1), ce test échoue par construction ; il reste joué hors bac
test('sans préambule, les agents restent tels quels ; un préambule énorme est borné',
  { skip: process.env.CHANTIER_BAC_A_SABLE === '1' && 'bac à sable d’un chantier' }, () => {
  const c = cockpit();
  // (29/10) sans préambule, chacun reçoit seulement sa vie d'agent (le juge, en plus, sa règle) ; le témoin vierge rien
  const p = c.pour();
  assert.deepEqual(Object.keys(p), Object.keys(c.AGENTS));
  assert.deepEqual(p.vierge, c.AGENTS.vierge);
  for (const k of ['architecte', 'codeur', 'juge']) {
    assert.ok(p[k].prompt.startsWith(c.AGENTS[k].prompt), k);
    assert.match(p[k].prompt.slice(c.AGENTS[k].prompt.length), /^\n\n(Un juge ne juge jamais[^\n]*\n\n)?\[Bienvenue dans la famille[^\n]*\n\[Ta vie d'agent/, k);
    assert.deepEqual({ ...p[k], prompt: '', tools: [] }, { ...c.AGENTS[k], prompt: '', tools: [] }, k);
    assert.ok(p[k].tools.includes('mcp__terminal__cafe_dire'), k);
  }
  const d = cockpit('x'.repeat(20000));
  // (30/10) la vie d'agent a grandi (le café, l'horizontale, la bienvenue d'Ahmed) : le préambule reste coupé à 4 000
  assert.ok(d.pour().juge.prompt.length < d.AGENTS.juge.prompt.length + 4600 + 2600);
});

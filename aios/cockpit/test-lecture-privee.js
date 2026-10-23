/* La lecture privée vue par le cockpit (audit de sécurité du 2026-10-23, élevé 2, accord d'Ahmed) : node --test test-lecture-privee.js
   Toute lecture de sa mémoire (souvenirs, courrier, jardin, carnets) et les données du téléphone ferment la porte du web
   (lecture-privee.json, lu par jarvis/sortie.py) ; seules les lectures de tiers marquent le tour « externe ». */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = srv.indexOf(`function ${nom}(`); return srv.slice(i, srv.indexOf('\n}\n', i) + 2); };
function cockpit() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'lecture-privee-'));
  const ctx = { fs, path, JSON, Date, String, Array, Set, JARVIS: dir, j: JSON.stringify };
  vm.createContext(ctx);
  const i = srv.indexOf('const JARVIS_MARQUE_EXTERNE'), f = srv.indexOf('function retirerExterne(');
  vm.runInContext(srv.slice(i, f) + 'this.surOutil = surOutil;', ctx);
  const lire = (f) => { try { return fs.readFileSync(path.join(dir, f), 'utf8'); } catch (_) { return ''; } };
  return { ctx, prive: () => (lire('lecture-privee.json') ? JSON.parse(lire('lecture-privee.json')).outils : []),
    externe: () => lire('tour-externe.jsonl').split('\n').filter(Boolean).map(l => JSON.parse(l).outil) };
}

test('un souvenir, le courrier, le jardin, les carnets : lecture privée ; un souvenir n’est pas un contenu de tiers', () => {
  const c = cockpit();
  for (const name of ['mcp__anamnese__memory_recall', 'mcp__anamnese__jardin_relire', 'mcp__anamnese__carnets'])
    c.ctx.surOutil({ type: 'tool_use', name });
  assert.deepEqual(c.prive(), ['mcp__anamnese__memory_recall', 'mcp__anamnese__jardin_relire', 'mcp__anamnese__carnets']);
  assert.deepEqual(c.externe(), [], 'sa mémoire ne marque pas le tour « externe »');
  c.ctx.surOutil({ type: 'tool_use', name: 'mcp__anamnese__courrier_lire' });     // le courrier : les deux, comme avant
  assert.ok(c.prive().includes('mcp__anamnese__courrier_lire'));
  assert.deepEqual(c.externe(), ['mcp__anamnese__courrier_lire']);
});

test('le web et le terminal ne sont pas des lectures privées', () => {
  const c = cockpit();
  for (const name of ['WebSearch', 'mcp__web__lire_page', 'mcp__terminal__executer', 'mcp__calcul__executer_python'])
    c.ctx.surOutil({ type: 'tool_use', name });
  assert.deepEqual(c.prive(), []);
});

test('sa position, ses capteurs, sa montre : la situation le dit (prive)', () => {
  const ctx = { Math, Number, String, JSON, Date, Array, Object, Intl, CONTEXTE_MAX: 100000,
    jaugeForfait: () => ({ texte: '' }), appareilDe: () => 'son téléphone' };
  vm.createContext(ctx);
  const debut = srv.indexOf('const CAPTEURS_CHAMPS'), fin = srv.indexOf('function capteursDe(');
  vm.runInContext(srv.slice(debut, fin) + prendre('capteursDe') + prendre('positionDe') + prendre('blocSituation'), ctx);
  const T = 1_800_000_000_000;
  assert.equal(ctx.blocSituation({}, false, { appareil: 'son téléphone' }, T).prive, false);
  assert.equal(ctx.blocSituation({ position: { lat: 46.5, lon: 6.6, precision_m: 20, t_ms: T - 60000 } }, false, { appareil: 'son téléphone' }, T).prive, true);
  assert.equal(ctx.blocSituation({ capteurs: { posture: 'téléphone déplié', mouvement: 'immobile', t_ms: T - 30000 } }, false, { appareil: 'son téléphone' }, T).prive, true);
  assert.equal(ctx.blocSituation({ capteurs: { posture: 'n’importe quoi', t_ms: T } }, false, { appareil: 'son téléphone' }, T).prive, false, 'rien de lu : rien de privé');
  assert.match(srv, /if \(situation\.prive\) noterLecturePrivee\('situation\(téléphone\)'\);/);
});

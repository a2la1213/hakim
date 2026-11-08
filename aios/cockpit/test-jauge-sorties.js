/* La jauge relevée chaque heure, et QUI demande une sortie (2026-10-22) : node --test test-jauge-sorties.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

test('qui demande : Hakim, ses agents en cours, une session Claude Code, et le contenu de tiers', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sorties-'));
  const ctx = { fs, path, String, JARVIS: dir, cerveau: { taches: new Map() } };
  vm.createContext(ctx);
  vm.runInContext(prendre('quiDemande') + 'this.qui = quiDemande;', ctx);
  assert.strictEqual(ctx.qui({ qui: 'hakim' }), 'Hakim');
  assert.strictEqual(ctx.qui({}), 'Hakim');
  ctx.cerveau.taches.set('t1', 'le codeur refait le calcul du sable');
  assert.match(ctx.qui({ qui: 'hakim' }), /^Hakim, ou un de ses agents en cours \(« le codeur refait le calcul du sable »\)$/);
  fs.writeFileSync(path.join(dir, 'tour-externe.jsonl'), '{}');
  assert.match(ctx.qui({ qui: 'claude-code' }), /^Une session Claude Code, après un contenu de tiers/);
});

test('la jauge : la dernière mesure, son âge, les tours de Hakim et les sessions Claude Code de l’heure', () => {
  const maison = fs.mkdtempSync(path.join(os.tmpdir(), 'maison-'));
  const proj = path.join(maison, '.claude', 'projects');
  for (const d of ['-Users-x-AIOS-jarvis-cwd', '-Users-x-Desktop-projet']) { fs.mkdirSync(path.join(proj, d), { recursive: true }); fs.writeFileSync(path.join(proj, d, 's.jsonl'), '{}'); }
  const T = Date.now();
  const jetons = path.join(maison, 'jetons.jsonl');
  fs.writeFileSync(jetons, [T - 60e3, T - 2 * 3600e3].map(ts => JSON.stringify({ ts })).join('\n'));
  const ctx = { fs, path, JSON, Math, Number, Date, HOME: maison, j: JSON.stringify, JARVIS_JETONS: jetons, JAUGE_FORFAIT: path.join(maison, 'jauge.jsonl'),
    abonnement: { info: { maj: T - 5 * 60e3, fenetres: { five_hour: { utilization: 0.4, resetsAt: 1792672800 }, seven_day: { utilization: 0.53, resetsAt: 1792699200 } } } } };
  vm.createContext(ctx);
  vm.runInContext(prendre('sessionsClaudeCodeActives') + prendre('releverJauge') + 'this.relever = releverJauge;', ctx);
  const l = ctx.relever(T);
  assert.deepStrictEqual([l.fenetre_5h.pct, l.semaine.pct, l.mesure_il_y_a_min, l.tours_hakim_heure, l.sessions_claude_code_heure], [40, 53, 5, 1, 1]);
  assert.strictEqual(JSON.parse(fs.readFileSync(ctx.JAUGE_FORFAIT, 'utf8')).semaine.pct, 53);
});

// (04/11, 13:57, mesuré pendant le test d'Ahmed : le lecteur Hakim de son ribosome, 1 réponse sur 12 ; 7 « délai dépassé », 2 « voix
// vivante arrêtée ») une voix vivante tuée à son délai repartait à froid à la lecture suivante, et dépassait encore ; son ribosome la
// garde : elle finit sa phrase pour rien et reste chaude ; une voix tuée n'est plus jamais redonnée
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = SRC.indexOf(`function ${nom}(`); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2); };

function pool() {
  const minuteurs = new Map(), procs = [];
  let id = 0;
  const ctx = { String, Date, Error, Promise, JSON, process: { env: {} }, os: { tmpdir: () => '/tmp' }, path,
    fs: { mkdtempSync: () => '/tmp/x', rmSync() {} }, CLAUDE_BIN: 'claude', EFFORT_HAKIM: 'low', j: JSON.stringify,
    VIVANTS: [], VIVANTS_MAX: { sonnet: 2 }, VIVANT_RENOUVELER: 25,
    setTimeout: (f, ms) => { minuteurs.set(++id, { f, ms }); return id; }, clearTimeout: (k) => minuteurs.delete(k),
    spawn: () => {
      const ecoute = {};
      const p = { exitCode: null, tue: false, ecrits: [], kill() { p.tue = true; }, on: (e, f) => { ecoute[e] = f; },
        stdout: { on: (e, f) => { ecoute['out'] = f; } }, stdin: { write: (x) => p.ecrits.push(x), end() {}, on() {} },
        repondre: (texte) => ecoute.out(JSON.stringify({ type: 'result', result: texte }) + '\n') };
      procs.push(p);
      return p;
    } };
  vm.createContext(ctx);
  vm.runInContext(prendre('vivantLibre') + prendre('demanderVivant') + '\nthis.demander = demanderVivant;', ctx);
  const sonner = (ms) => { for (const [k, m] of [...minuteurs]) if (m.ms === ms) { minuteurs.delete(k); m.f(); } };
  return { ctx, procs, sonner };
}

test('sans réglage : à son délai, la voix vivante est tuée et n’est plus jamais redonnée', async () => {
  const { ctx, procs, sonner } = pool();
  const p = ctx.demander('sonnet', 'lis', 3000);
  sonner(3000);
  await assert.rejects(p, /délai dépassé/);
  assert.strictEqual(procs[0].tue, true);
  assert.ok(ctx.VIVANTS[0].n >= 25, 'marquée : plus jamais choisie, même avant sa mort');
  ctx.demander('sonnet', 'encore', 3000).catch(() => {});
  assert.strictEqual(procs.length, 2, 'la suivante en prend une autre');
});

test('son ribosome (garderSurDelai) : à son délai, elle finit sa phrase pour rien et reste chaude pour la lecture suivante', async () => {
  const { ctx, procs, sonner } = pool();
  const p = ctx.demander('sonnet', 'lis', 3000, { garderSurDelai: true });
  sonner(3000);
  await assert.rejects(p, /délai dépassé/);
  assert.strictEqual(procs[0].tue, false, 'pas tuée');
  ctx.demander('sonnet', 'autre', 3000, { garderSurDelai: true }).catch(() => {});
  assert.strictEqual(procs.length, 2, 'encore occupée à finir : une autre est prise');
  procs[0].repondre('GARDE : « trop tard »');                          // sa réponse tardive : jetée, elle se libère
  let recu = null;
  const q = ctx.demander('sonnet', 'suivante', 3000, { garderSurDelai: true }).then((o) => { recu = o.texte; });
  assert.strictEqual(procs.length, 2, 'la même, chaude');
  assert.match(procs[0].ecrits.at(-1), /suivante/);
  procs[0].repondre('GARDE : « oui papa »');
  await q;
  assert.strictEqual(recu, 'GARDE : « oui papa »', 'la réponse tardive d’avant ne se mélange pas à la suivante');
});

test('son ribosome : une voix qui ne finit jamais est tuée au bout de 30 s', async () => {
  const { ctx, procs, sonner } = pool();
  ctx.demander('sonnet', 'lis', 3000, { garderSurDelai: true }).catch(() => {});
  sonner(3000);
  await new Promise(r => setImmediate(r));
  sonner(30000);
  assert.strictEqual(procs[0].tue, true);
  assert.ok(ctx.VIVANTS[0].n >= 25);
  assert.match(SRC, /sonnetTeteDeFond\(consigne, `ribosome_\$\{mod\}`, mod, delai, \{ garderSurDelai: true \}\)/, 'son ribosome le demande');
});

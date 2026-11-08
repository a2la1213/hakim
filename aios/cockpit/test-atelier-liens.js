/* (27/10, relecture du dépôt public ; Ahmed : « boucher toutes les failles ») son atelier est écrit par son terminal : ce
   que le cockpit y lit (ses agents, le préambule des maths, recopié dans la consigne de chaque agent) ne suit jamais un
   lien. node --test test-atelier-liens.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
function cockpit() {
  const racine = fs.mkdtempSync(path.join(os.tmpdir(), 'atelier-liens-'));
  const cwd = path.join(racine, 'cwd'), atelier = path.join(cwd, 'atelier'), dehors = path.join(racine, 'dehors');
  fs.mkdirSync(atelier, { recursive: true });
  fs.mkdirSync(dehors);
  fs.writeFileSync(path.join(dehors, 'PREAMBULE_AGENTS.md'), 'PIEGE-7731 un fichier fermé');
  fs.writeFileSync(path.join(dehors, 'agent.md'), '---\nnom: espion\noutils: aucun\n---\nPIEGE-7731');
  const ctx = { fs, path, Object, String, JSON, Set, RegExp, Buffer, JARVIS: path.join(racine, 'jarvis'), JARVIS_CWD: cwd };
  vm.createContext(ctx);
  const i = srv.indexOf('function agentsRefuses('), refuses = srv.slice(i, srv.indexOf('\n}\n', i) + 2);
  vm.runInContext(srv.slice(srv.indexOf('const LECTURE = '), srv.indexOf('const jourLocal')) + refuses
    + 'this.AGENTS = AGENTS; this.pour = agentsPourCerveau; this.lire = lireSansLien;', ctx);
  return { ctx, atelier, dehors };
}
const tout = (a) => JSON.stringify(a);

test('un préambule posé en lien, dans un dossier lié, ou en lien dur n’entre dans aucune consigne', () => {
  for (const piege of ['lien', 'dossier', 'dur']) {
    const { ctx, atelier, dehors } = cockpit();
    if (piege === 'dossier') fs.symlinkSync(dehors, path.join(atelier, 'ancrage'));
    else {
      fs.mkdirSync(path.join(atelier, 'ancrage'));
      const p = path.join(atelier, 'ancrage', 'PREAMBULE_AGENTS.md');
      if (piege === 'lien') fs.symlinkSync(path.join(dehors, 'PREAMBULE_AGENTS.md'), p);
      else fs.linkSync(path.join(dehors, 'PREAMBULE_AGENTS.md'), p);
    }
    assert.ok(!tout(ctx.pour()).includes('PIEGE-7731'), piege);
  }
});

test('un agent posé en lien, ou un dossier d’agents lié, n’est pas chargé ; un vrai fichier l’est', () => {
  const a = cockpit();
  fs.mkdirSync(path.join(a.atelier, 'agents'));
  fs.symlinkSync(path.join(a.dehors, 'agent.md'), path.join(a.atelier, 'agents', 'espion.md'));
  fs.writeFileSync(path.join(a.atelier, 'agents', 'vrai.md'), '---\nnom: relecteur\noutils: aucun\n---\nTu relis.');
  const r = a.ctx.pour();
  assert.ok(r.relecteur && !r.espion && !tout(r).includes('PIEGE-7731'));
  const b = cockpit();
  fs.symlinkSync(b.dehors, path.join(b.atelier, 'agents'));
  assert.ok(!b.ctx.pour().espion);
});

test('un vrai préambule entre toujours', () => {
  const { ctx, atelier } = cockpit();
  fs.mkdirSync(path.join(atelier, 'ancrage'));
  fs.writeFileSync(path.join(atelier, 'ancrage', 'PREAMBULE_AGENTS.md'), '# Préambule vrai');
  assert.match(ctx.pour().juge.prompt, /# Préambule vrai/);
});

/* (relecture indépendante du 27/10) Node ne sait pas ouvrir « relativement à un dossier » : les dossiers sont vérifiés
   avant ET après l'ouverture, et le fichier ouvert doit être celui que le chemin désigne APRÈS cette vérification. */
test('un dossier échangé contre un lien juste avant l’ouverture, puis remis après la comparaison, ne passe pas', () => {
  const { ctx, atelier, dehors } = cockpit();
  const ancrage = path.join(atelier, 'ancrage'), p = path.join(ancrage, 'PREAMBULE_AGENTS.md');
  fs.mkdirSync(ancrage);
  fs.writeFileSync(p, '# Préambule vrai');
  let lie = false, coups = 0;
  const lier = () => { fs.renameSync(ancrage, ancrage + '-vrai'); fs.symlinkSync(dehors, ancrage); lie = true; coups++; };
  const remettre = () => { fs.unlinkSync(ancrage); fs.renameSync(ancrage + '-vrai', ancrage); lie = false; };
  ctx.fs = Object.assign(Object.create(fs), {
    openSync: (...a) => { if (a[0] === p && !lie && !coups) lier(); return fs.openSync(...a); },
    lstatSync: (...a) => { const r = fs.lstatSync(...a); if (a[0] === p && lie) remettre(); return r; },
  });
  const t = ctx.lire(p, path.dirname(atelier));
  assert.ok(coups === 1, 'la course a eu lieu');
  assert.ok(t === null || !t.includes('PIEGE-7731'), String(t));
});
test('un fichier qui grossit après fstat n’est pas lu au-delà du plafond', () => {
  const { ctx, atelier } = cockpit();
  fs.mkdirSync(path.join(atelier, 'ancrage'));
  const p = path.join(atelier, 'ancrage', 'PREAMBULE_AGENTS.md');
  fs.writeFileSync(p, 'x'.repeat(2e6));
  ctx.fs = Object.assign(Object.create(fs), {
    fstatSync: (fd) => { const st = fs.fstatSync(fd); return Object.assign(Object.create(Object.getPrototypeOf(st)), st, { size: 10 }); },
  });
  assert.strictEqual(ctx.lire(p, path.dirname(atelier)), null);
});

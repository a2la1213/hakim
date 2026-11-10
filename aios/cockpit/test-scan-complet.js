/* (10/11, Ahmed : « qu'il scanne l'intégralité du code de Hakim et de toi, si on le demande ») le scan complet côté cockpit : la route
   /api/immunite/scan (dans une partie fermée), lancée seulement par papa (sa présence, qui porte les options), détachée ; un faux
   positif connu demande aussi sa présence ; l'arrêt tue le scan par son PID, vérifié ; Hakim peut le demander (scan_demander), pas le
   lancer ; la page Immunité échappe tout ce qu'elle montre. node --test test-scan-complet.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'immunite.html'), 'utf8');
const bloc = src.slice(src.indexOf('  // FERME-DEBUT scan'), src.indexOf('  // FERME-FIN scan'));

function monter({ jeton = true, refus = null, etat = { en_cours: null }, ps = '', fait = 'fait' } = {}) {
  const appels = { spawn: [], execFile: [], presence: [], audit: [], kill: [] };
  const ctx = {
    JSON, Number, String, Promise, console: { error() {} }, ANAMNESE: '/anamnese', PYTHON: '/anamnese/.venv/bin/python', IMMUNITE: '/j/immunite',
    path, j: JSON.stringify,
    jetonValide: () => jeton,
    exigerPresence: (req, distantReq, q, action) => { appels.presence.push(action); return refus; },
    auditer: (action, req, d, details) => appels.audit.push({ action, details }),
    lireCorps: async (req) => req.corps || '',
    fs: { mkdirSync() {}, openSync: () => 7, closeSync() {} },
    spawn: (bin, args, opts) => { appels.spawn.push({ bin, args, opts }); return { pid: 4242, on() {}, unref() {} }; },
    execFile: (bin, args, opts, cb) => {
      appels.execFile.push({ bin, args });
      if (bin === '/bin/ps') return cb(null, ps);
      if (args[2] === 'scan-etat') return cb(null, JSON.stringify(etat));
      return cb(null, fait);
    },
    process: { kill: (pid, sig) => appels.kill.push({ pid, sig }) },
  };
  vm.createContext(ctx);
  const route = vm.runInContext(`(async (req, res, p, distantReq) => {\n${bloc}\n return null; })`, ctx);
  const appeler = async (methode, corps) => {
    const res = { code: 0, corps: '', writeHead(c) { this.code = c; }, end(x) { this.corps = x; return this; } };
    await route({ method: methode, corps: corps ? JSON.stringify(corps) : '' }, res, '/api/immunite/scan', false);
    return { code: res.code, o: res.corps ? JSON.parse(res.corps) : null };
  };
  return { appeler, appels };
}

test('la route du scan est dans une partie fermée, derrière le jeton', async () => {
  assert.ok(bloc.includes("if (p === '/api/immunite/scan') {") && bloc.length > 1000);
  assert.ok(src.indexOf('// FERME-FIN scan') > src.indexOf('// FERME-DEBUT scan (10/11'));
  const m = monter({ jeton: false });
  assert.strictEqual((await m.appeler('GET')).code, 403);
  const n = monter({ etat: { en_cours: null, dernier: { comptes: { haute: 1 } } } });
  const r = await n.appeler('GET');
  assert.strictEqual(r.code, 200);
  assert.strictEqual(r.o.dernier.comptes.haute, 1);
});

test('le lancer demande la présence de papa, et le défi porte ses options', async () => {
  const refuse = monter({ refus: 'preuve de présence exigée' });
  const r = await refuse.appeler('POST', { action: 'lancer', profond: true });
  assert.strictEqual(r.code, 403);
  assert.deepStrictEqual(refuse.appels.presence, ['scan:lancer-profond']);
  assert.strictEqual(refuse.appels.spawn.length, 0, 'rien ne part sans sa présence');
  const ok = monter();
  const r2 = await ok.appeler('POST', { action: 'lancer', profond: false, reseau: true });
  assert.strictEqual(r2.code, 200);
  assert.deepStrictEqual(ok.appels.presence, ['scan:lancer-reseau']);
  const s = ok.appels.spawn[0];
  assert.deepStrictEqual([...s.args], ['-B', '/anamnese/jarvis/immunite.py', 'scan', '--reseau']);
  assert.strictEqual(s.opts.detached, true, 'détaché : une relance du cockpit ne le tue pas');
  assert.strictEqual(ok.appels.audit[0].action, 'scan:lancer');
});

test('un seul scan à la fois', async () => {
  const m = monter({ etat: { en_cours: { pid: 99, etape: 'chaine' } } });
  assert.strictEqual((await m.appeler('POST', { action: 'lancer' })).code, 409);
  assert.strictEqual(m.appels.spawn.length, 0);
});

test('un faux positif connu : sa présence ; retirer une exception : sans', async () => {
  const m = monter();
  assert.strictEqual((await m.appeler('POST', { action: 'exception', id: '<script>' })).code, 400);
  assert.strictEqual((await m.appeler('POST', { action: 'exception', id: '0123456789abcdef' })).code, 200);
  assert.deepStrictEqual(m.appels.presence, ['scan:exception:0123456789abcdef']);
  assert.deepStrictEqual([...m.appels.execFile.at(-1).args.slice(2)], ['scan-exception', '0123456789abcdef']);
  await m.appeler('POST', { action: 'exception-retirer', id: '0123456789abcdef' });
  assert.deepStrictEqual([...m.appels.execFile.at(-1).args.slice(2)], ['scan-exception-retirer', '0123456789abcdef']);
  assert.strictEqual(m.appels.presence.length, 1, 'retirer une exception remonte la garde : pas de présence');
});

test('arrêter : par son PID, et seulement si ce processus est bien le scan', async () => {
  const autre = monter({ etat: { en_cours: { pid: 321 } }, ps: '/usr/bin/node server.js' });
  assert.strictEqual((await autre.appeler('POST', { action: 'arreter' })).code, 409);
  assert.strictEqual(autre.appels.kill.length, 0, 'jamais un autre processus');
  const m = monter({ etat: { en_cours: { pid: 321 } }, ps: '/anamnese/.venv/bin/python -B /anamnese/jarvis/immunite.py scan --profond' });
  assert.strictEqual((await m.appeler('POST', { action: 'arreter' })).code, 200);
  assert.deepStrictEqual(m.appels.kill, [{ pid: 321, sig: 'SIGTERM' }]);
  const fini = monter({ etat: { en_cours: { interrompu: true, pid: 321 } }, ps: 'immunite.py scan' });
  assert.strictEqual((await fini.appeler('POST', { action: 'arreter' })).code, 409);
});

test('Hakim peut le demander (scan_demander parmi ses outils), il ne peut pas le lancer', () => {
  const debut = src.indexOf('const OUTILS_JARVIS = [');
  assert.ok(src.slice(debut, src.indexOf(']', debut)).includes("'scan_demander'"));
  assert.ok(!/scan_lancer/.test(src), 'aucun outil pour le lancer');
});

test('chaque geste de présence du scan est accepté par /api/presence/options', () => {
  const i = src.indexOf("if (p === '/api/presence/options' && req.method === 'POST') {");
  const m = /if \(!(\/\^[^\n]*?\$\/)\.test\(action\)\)/.exec(src.slice(i, i + 800));
  const motif = eval(m[1]);
  for (const a of ['scan:lancer', 'scan:lancer-profond', 'scan:lancer-reseau', 'scan:lancer-profond-reseau', 'scan:exception:0123456789abcdef'])
    assert.ok(motif.test(a), a);
  assert.ok(page.includes("preuvePresence(`scan:lancer${profond ? '-profond' : ''}${reseau ? '-reseau' : ''}`, annonce)"));
  assert.ok(page.includes('preuvePresence(`scan:exception:${id}`, annonce)'));
});

test('la page Immunité échappe tout ce que le scan lui montre (aucune valeur brute dans son HTML)', () => {
  const i = page.indexOf('function rendreScan()');
  const corps = page.slice(i, page.indexOf('\n  }\n', i));
  const html = corps.split('\n').filter((l) => l.includes('<')).join('\n');      // les lignes qui fabriquent du HTML
  const brutes = [...html.matchAll(/\$\{([^{}]*)\}/g)].map((x) => x[1].trim())
    .filter((e) => /^(?:t|d|r|c|m|x)\.[\w.]+$/.test(e));
  assert.deepStrictEqual(brutes, [], 'chaque valeur passe par esc()');
  assert.ok(page.includes('<section class="glass carte" id="scan"><h2>🔬 Scan complet</h2>'));
  assert.ok(!/src="\/nav\.js"/.test(page), 'la page ne charge toujours pas nav.js (ouvert aux chantiers)');
});

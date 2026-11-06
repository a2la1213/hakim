/* (06/11, Ahmed : « la page de réglages, le même design que les autres pages, avec les boutons Parler, le menu burger, l'orbe ;
   et l'orbe sur toutes les pages du cockpit ») la petite orbe de la barre du haut : montée par badges.js (fermé) sur chaque page
   qui a le menu, peinte par orbe.js (ouvert) dans un Worker qui ne voit rien de la page. node --test test-pages-orbe.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const PUB = path.join(__dirname, 'public');
const lire = (f) => fs.readFileSync(path.join(PUB, f), 'utf8');

test('badges.js monte l’orbe sur toutes les pages du menu, sauf Parler qui a la sienne', () => {
  const b = lire('badges.js');
  const i = b.indexOf("if (active !== 'parler') {"), bloc = b.slice(i, b.indexOf('\n    }\n', i));
  assert.match(bloc, /so\.src = '\/orbe-coin\.js';/, 'dans le bloc « pas Parler »');
  assert.match(bloc, /window\.OrbeCoin\.monter\(nav\)/);
  assert.match(b, /\.orbe-coin\{margin-left:auto;/);
});

test('les pages fermées ne chargent jamais de code ouvert (orbe.js, nav.js) : l’orbe passe par le Worker', () => {
  for (const f of ['reglages.html', 'immunite.html', 'telephone.html', 'code.html']) {
    const t = lire(f);
    assert.ok(!/<script src="\/orbe\.js">/.test(t), `${f} ne charge pas orbe.js`);
    assert.ok(!/<script src="\/nav\.js">/.test(t), `${f} ne charge pas nav.js`);
    assert.match(t, /<script src="\/badges\.js"><\/script>/, `${f} a le menu (et donc l’orbe)`);
  }
  const c = lire('orbe-coin.js');
  assert.ok(!/orbe\.js'/.test(c.replace(/orbe-travail\.js|orbe-coin\.js/g, '')), 'orbe-coin.js ne charge pas orbe.js dans la page');
  assert.match(c, /new Worker\('\/orbe-travail\.js'\)/);
  assert.match(c, /transferControlToOffscreen\(\)/);
  assert.ok(!/EventSource/.test(c), 'aucun flux SSE en plus : la lecture de l’humeur, comme Parler');
  assert.match(c, /fetch\('\/api\/jarvis\/interieur'/);
  assert.match(lire('orbe-travail.js'), /importScripts\('\/orbe\.js'\)/);
});

test('Réglages a la barre commune : ☰, PARLER, l’orbe, et le fond des autres pages', () => {
  const t = lire('reglages.html');
  assert.match(t, /document\.body\.classList\.add\('shell'\);\n  Badges\.suivre\(document\.querySelector\('nav\.topnav'\), 'reglages'\);/);
  assert.match(t, /<nav class="topnav" style="display:flex;gap:10px;align-items:center;padding:10px 16px"><span class="brand">AIOS<\/span><\/nav>/);
});

test('le Duel a la barre commune lui aussi', () => {
  assert.match(lire('duel.html'), /<script src="\/nav\.js"><\/script>\n  <script>initNav\('duel'\);<\/script>/);
});

test('le Worker peint vraiment : orbe.js tourne sur la toile reçue, à sa taille, et suit son humeur', () => {
  const traces = { taille: [], rempli: 0, rafs: [] };
  const ctx = new Proxy({}, { get: (o, k) => {
    if (k in o) return o[k];
    if (/^create/.test(k)) return () => ({ addColorStop() {} });
    if (k === 'fillRect') return () => { traces.rempli++; };
    return () => {};
  }, set: (o, k, v) => { o[k] = v; return true; } });
  const toile = { getContext: () => ctx, width: 0, height: 0 };
  const moi = { setTimeout, clearTimeout, performance: { now: () => 1000 }, Math, String, Number, parseInt };
  moi.self = moi;
  moi.requestAnimationFrame = (f) => { traces.rafs.push(f); return traces.rafs.length; };
  moi.cancelAnimationFrame = () => {};
  moi.importScripts = (u) => { assert.equal(u, '/orbe.js'); vm.runInContext(lire('orbe.js'), ctxVm); };
  const ctxVm = vm.createContext(moi);
  vm.runInContext(lire('orbe-travail.js'), ctxVm);
  moi.onmessage({ data: { canvas: toile, w: 60, h: 60, dpr: 2, reduit: false } });
  moi.onmessage({ data: { humeur: 'joie' } });
  traces.rafs.shift()(1016);
  assert.equal(toile.width, 120, 'la toile prend la taille de la barre × la densité de l’écran');
  assert.ok(traces.rempli > 0, 'orbe.js a peint');
  // témoin : la page cachée, il ne peint plus rien
  const avant = traces.rempli;
  moi.onmessage({ data: { visible: false } });
  traces.rafs.shift()(1032);
  assert.equal(traces.rempli, avant, 'invisible : rien à peindre');
});

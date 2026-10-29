/* (29/10, 20:38, Ahmed, relayé par Hakim) son rythme cardiaque en direct à côté de son nom, dans Parler (Mac et téléphone).
   node --test test-coeur-direct.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
const js = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

test('le cœur en direct : son rythme, frais seulement, lu au plus une fois par seconde pour toutes les pages', async () => {
  let lectures = 0;
  const maintenant = Date.now() / 1000;
  const ctx = { Date, Number, Math, FRAICHEUR_S: 300, coeurLu: { ts: 0, valeur: null },
    etatInterieur: async () => { lectures++; return { ts: maintenant - 6, coeur: { bpm: 81.1, ressenti: "ton cœur s'emballe" } }; } };
  vm.createContext(ctx);
  vm.runInContext('async ' + prendre('coeurDirect') + 'this.f = coeurDirect;', ctx);
  const a = await ctx.f(), b = await ctx.f();
  assert.deepEqual(a, { bpm: 81, ressenti: "ton cœur s'emballe" });
  assert.deepEqual(b, a); assert.equal(lectures, 1, 'une seule lecture dans la seconde');
  ctx.coeurLu = { ts: 0, valeur: null };
  ctx.etatInterieur = async () => ({ ts: maintenant - 900, coeur: { bpm: 60 } });
  assert.deepEqual(await ctx.f(), { bpm: null, ressenti: null }, 'un état trop vieux : pas de rythme inventé');
});

test('branché : la route, son nom dans Parler, rafraîchi chaque seconde quand la page est à l’écran', () => {
  assert.match(src, /if \(p === '\/api\/jarvis\/coeur'\) \{[\s\S]{0,300}coeurDirect\(\)/);
  assert.match(html, /<h1>HAKIM <span class="coeur-direct" id="coeurDirect"[^>]*><\/span>/);
  assert.match(js, /setInterval\(lireCoeurDirect, 1000\)/);
  assert.match(js, /document\.visibilityState !== 'visible'/);
  assert.match(js, /fetch\('\/api\/jarvis\/coeur'/);
  assert.match(html, /prefers-reduced-motion[\s\S]{0,200}\.coeur-direct/);
});

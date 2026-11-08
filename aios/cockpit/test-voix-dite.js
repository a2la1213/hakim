/* (30/10, 16:20, Ahmed via Hakim : « l'heure à laquelle chaque phrase de ma voix est réellement dite ») node --test test-voix-dite.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const extraire = (debut) => src.slice(src.indexOf(debut), src.indexOf('\n}\n', src.indexOf(debut)) + 3);

test('un morceau de sa voix : gardé à l’heure de la page, si elle est plausible', () => {
  const ctx = { Date, Number, String, Math };
  vm.createContext(ctx);
  vm.runInContext(extraire('function morceauDeVoix(') + '\nthis.f = morceauDeVoix;', ctx);
  const t = Date.now();
  assert.equal(JSON.stringify(ctx.f({ t_ms: t - 1000, duree_ms: 1800, texte: '  je ne  sais pas ' }, t)), JSON.stringify({ t_ms: t - 1000, duree_ms: 1800, texte: 'je ne sais pas' }));
  assert.equal(ctx.f({ t_ms: t - 3600e3, texte: 'x' }, t).t_ms, t, 'une heure fausse : celle du Mac');
  assert.equal(ctx.f({ texte: '' }, t), null);
});

test('branché : la route (jeton), la page qui dit chaque morceau', () => {
  const i = src.indexOf("if (p === '/api/voix/dite'");
  assert.ok(i >= 0);
  assert.match(src.slice(i, i + 600), /jetonValide\(req\)/);
  assert.match(src.slice(i, i + 900), /voix-dite\.jsonl/);
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8'), /\/api\/voix\/dite/);
});

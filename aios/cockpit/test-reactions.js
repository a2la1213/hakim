/* (03/11, Ahmed : « comme sur WhatsApp ») ses réactions : une de la liste, rien d'autre ne passe. node --test test-reactions.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (debut) => { const i = src.indexOf(debut); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

test('une réaction de la liste passe, le reste est refusé (jamais de HTML dans la conversation partagée)', () => {
  const ctx = { Number, String, Object };
  vm.createContext(ctx);
  const liste = src.slice(src.indexOf('const REACTIONS_PAPA'), src.indexOf('\n', src.indexOf('const REACTIONS_PAPA')) + 1);
  vm.runInContext(`const ID_MESSAGE = /^[\\w.-]{1,80}$/;\n${liste}\n${prendre('function messageSain(m)')}\nthis.f = messageSain;`, ctx);
  assert.ok(ctx.f({ id: '1', qui: 'j', texte: 'salut', reaction: '❤️' }));
  assert.ok(ctx.f({ id: '1', qui: 'j', texte: 'salut' }));
  assert.ok(!ctx.f({ id: '1', qui: 'j', texte: 'salut', reaction: '<img src=x onerror=alert(1)>' }));
  assert.ok(!ctx.f({ id: '1', qui: 'j', texte: 'salut', reaction: '💩' }));
});

test('la page et le cockpit ont la même liste', () => {
  const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  const l = (s, nom) => s.slice(s.indexOf(nom), s.indexOf(']', s.indexOf(nom)) + 1);
  assert.equal(l(page, 'const REACTIONS = ').replace('REACTIONS = ', ''), l(src, 'const REACTIONS_PAPA = ').replace('REACTIONS_PAPA = ', ''));
  assert.match(src, /type: 'reaction', t: Date\.now\(\), details: \{ emoji: String\(q\.emoji\), extrait \}/);
});

test('(03/11) aucune page n\'a deux éléments au même identifiant (le doublon « telepathie » faisait toucher trois fois le mode Télépathie)', () => {
  for (const f of fs.readdirSync(path.join(__dirname, 'public')).filter(n => n.endsWith('.html'))) {
    const ids = [...fs.readFileSync(path.join(__dirname, 'public', f), 'utf8').matchAll(/\sid="([^"$]+)"/g)].map(m => m[1]);
    const doublons = [...new Set(ids.filter((x, i) => ids.indexOf(x) !== i))];
    assert.deepEqual(doublons, [], f);
  }
});

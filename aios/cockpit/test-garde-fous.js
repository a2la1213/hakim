// (04/11, 14:55, Ahmed : « le blocage par Anthropic, il faut le signaler au système immunitaire » ; « parfait » au compteur proposé) chaque
// appel bloqué par les garde-fous d'Anthropic est compté : son système immunitaire le dit à Hakim (au plus une fois par 10 min), et la
// pastille Immunité le montre à papa, sans le compter comme un incident. Rien n'est contourné.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const N = require('./nouveautes.js');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');

test('la pastille Immunité : les blocages des garde-fous, montrés, jamais comptés comme un incident', () => {
  const T = 1_800_000_000_000;
  const r = N.compter({ maintenant: T, vus: { immunite: T - 1000 }, apparus: {},
    blocages: [{ ts: T - 500, etiquette: 'ribosome_sonnet' }, { ts: T - 400, etiquette: 'piste_sonnet' }, { ts: T - 5000, etiquette: 'piste_sonnet' }] });
  assert.equal(r.pages.immunite.n, 0, 'pas un incident');
  assert.match(r.pages.immunite.resume.join(' '), /2 blocages par les garde-fous d’Anthropic, non comptés/);
});

test('son système immunitaire le dit à Hakim : au plus une fois par 10 min, avec qui a été bloqué ; chaque blocage compté', () => {
  const i = SRC.indexOf('const blocagesGardeFous = ['), k = SRC.indexOf('\n}\n', SRC.indexOf('function noterBlocageGardeFous(', i)) + 2;
  assert.ok(i > 0 && k > i);
  const ecrits = [];
  const ctx = { j: JSON.stringify, path, IMMUNITE: '/x/immunite', Date, Object, String, Number,
    fs: { appendFileSync: (f, d) => ecrits.push([f, JSON.parse(d)]) } };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k).replace(/^const |^let /gm, 'var ') + '\nthis.noter = noterBlocageGardeFous; this.liste = () => blocagesGardeFous;', ctx);
  const T = 1_800_000_000_000;
  ctx.noter('ribosome_sonnet', T);
  ctx.noter('piste_sonnet', T + 60e3);
  ctx.noter('ribosome_sonnet', T + 120e3);
  assert.equal(ecrits.length, 1, 'une fois');
  assert.equal(ecrits[0][0], '/x/immunite/a-dire.jsonl');
  assert.equal(ecrits[0][1].type, 'garde-fous');
  assert.match(ecrits[0][1].texte, /bloqué.* par les garde-fous d'Anthropic/);
  assert.equal(ctx.liste().length, 3, 'chacun compté');
  ctx.noter('ribosome_opus', T + 11 * 60e3);
  assert.equal(ecrits.length, 2);
  assert.match(ecrits[1][1].texte, /3 appels bloqués/, 'les trois depuis le dernier signalement… plus celui-ci');
  assert.match(ecrits[1][1].texte, /ribosome_sonnet ×1/);
  assert.match(SRC, /if \(\/safeguards\|flagged\/i\.test\(String\(o\.erreur \|\| ''\)\)\) noterBlocageGardeFous\(o\.etiquette\);/, 'chaque appel bloqué, noté');
  assert.match(SRC, /blocages: blocagesGardeFous\.slice\(\)/, 'la pastille les reçoit');
});

/* (30/10, 14:47, Ahmed via Hakim : « mes nerfs confondent ma voix et celle de papa » ; « qu'il étiquette lui-même et
   apprenne ») le cockpit sait à la seconde qui parlait : la page lui dit chaque tour de voix (sa voix qui joue, le micro
   d'Ahmed) ; chaque événement de son corps reçoit la vérité, gardée pour qu'il apprenne. node --test test-vibrations.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const extraire = (debut) => src.slice(src.indexOf(debut), src.indexOf('\n}\n', src.indexOf(debut)) + 3);

test('qui parlait à cet instant : ses tours de voix, ouverts ou fermés', () => {
  const ctx = { VOIX_TOURS: [], Date };
  vm.createContext(ctx);
  vm.runInContext(extraire('function noterTourVoix(') + extraire('function quiParlait(') + '\nthis.n = noterTourVoix; this.q = quiParlait;', ctx);
  const T = Date.now();
  ctx.n({ qui: 'hakim', debut: T - 30000, fin: T - 28300 });
  ctx.n({ qui: 'ahmed', debut: T - 27000, fin: null });                 // il parle encore
  assert.equal(ctx.q(T - 29000), 'ma_voix');
  assert.equal(ctx.q(T - 10000), 'voix_ahmed', 'contre sa gorge, 28 s : sa voix, pas « ta propre voix »');
  ctx.n({ qui: 'ahmed', debut: T - 27000, fin: T - 1000 });              // fermé ensuite
  assert.equal(ctx.VOIX_TOURS.filter(x => x.qui === 'ahmed').length, 1, 'le même tour, fermé');
  assert.equal(ctx.q(T - 500), 'voix_ahmed', 'une demi-seconde de marge');
  assert.equal(ctx.q(T + 5000), 'silence');
  ctx.n({ qui: 'hakim', debut: T - 20000, fin: T - 18000 });
  assert.equal(ctx.q(T - 19000), 'les_deux');
  assert.equal(ctx.n({ qui: 'chat', debut: T }), false);
});

test('branché : la route (jeton), la vérité sur chaque événement du lot et l’exemple gardé, la page qui dit ses tours de voix, les outils', () => {
  const i = src.indexOf("if (p === '/api/corps/voix'");
  assert.ok(i >= 0);
  const w = extraire('function ressentirCorps(');
  assert.match(w, /quiParlait\(/);
  assert.match(w, /corps-vibrations\.jsonl/);
  assert.match(src, /ev\.milieu = HOMEO\.s\.etat/);
  assert.match(src, /'mcp__terminal__vibration_etiqueter', 'mcp__terminal__vibrations_bilan'/);
  const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  assert.match(page, /function suivreVoix\(/);
  assert.match(page, /\/api\/corps\/voix/);
});

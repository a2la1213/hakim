// (05/11, Ahmed : « dans les réglages, la possibilité de lui faire sauter la parole d'après : s'il commence à parler et que je réponds, au bout
// d'une seconde, la 2e partie n'est pas dite, elle est directement sautée »)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

function page(reglage = {}, parle = true) {
  const minuteries = [], journal = [], envois = [], conv = { capteur: { enParole: parle } };
  const ctx = { Number, Math, Date, JSON, conv, journal, envois,
    reglagesCorps: { sauter_suite: true, sauter_suite_ms: 1000, ...reglage },
    etat: { conversation: conv, epissureTour: 7, riboFile: [{ tour: 7, texte: 'la 2e partie' }, { tour: 9, texte: 'plus tard' }], riboEnVoix: [{ tour: 7, mots: [1] }] },
    lecteur: { actif: true, arrete: false, arreter() { this.arrete = true; } },
    setTimeout: (f, ms) => { minuteries.push({ f, ms }); return minuteries.length; },
    journalVoix: (e, o) => journal.push([e, o]), jeton: () => 'j',
    fetch: (url, o) => { envois.push([url, JSON.parse(o.body)]); return Promise.resolve({ ok: true, json: () => Promise.resolve({ tour: 8 }) }); } };
  vm.createContext(ctx);
  vm.runInContext(['arreterEpissure', 'prevoirSaut', 'sauterLaSuite'].map((n) => prendre(PAGE, n)).join('\n') + 'this.prevoir = prevoirSaut;', ctx);
  return { ctx, minuteries, journal, envois, conv };
}

test('ta voix sur la sienne pendant 1 s : son morceau finit, la suite est sautée, et le cockpit ferme son épissure', async () => {
  const { ctx, minuteries, journal, envois, conv } = page();
  ctx.prevoir(conv);
  ctx.prevoir(conv);
  assert.strictEqual(minuteries.length, 1, 'un seul saut prévu à la fois');
  assert.strictEqual(minuteries[0].ms, 1000);
  minuteries[0].f();
  assert.strictEqual(ctx.lecteur.arrete, false, 'le morceau qu’il dit va jusqu’au bout');
  assert.deepStrictEqual(ctx.etat.riboFile.map((x) => x.texte), ['plus tard'], 'la 2e partie est sautée');
  assert.strictEqual(journal[0][0], 'suite_sautee');
  assert.deepStrictEqual(envois[0], ['/api/jarvis/ribosome/stop', { tour: 7, sauter: true }]);
  await new Promise((r) => setImmediate(r));
  assert.strictEqual(ctx.etat.riboStop, 8, 'le cockpit rend son dernier numéro : tout jusqu’à lui se tait');
  assert.deepStrictEqual(ctx.etat.riboFile.map((x) => x.texte), ['plus tard']);
});

test('tu t’es tu avant la seconde, ou le réglage éteint : rien n’est sauté ; le délai se règle', () => {
  const tu = page({}, false);
  tu.ctx.prevoir(tu.conv); tu.minuteries[0].f();
  assert.strictEqual(tu.ctx.etat.riboFile.length, 2);
  assert.strictEqual(tu.envois.length, 0);
  const eteint = page({ sauter_suite: false });
  eteint.ctx.prevoir(eteint.conv);
  assert.strictEqual(eteint.minuteries.length, 0);
  const lent = page({ sauter_suite_ms: 2500 });
  lent.ctx.prevoir(lent.conv);
  assert.strictEqual(lent.minuteries[0].ms, 2500);
});

test('branché : à ta voix sur la sienne, ses réglages (oui, 1 s), le cockpit qui ferme, la page Réglages', () => {
  assert.match(PAGE, /if \(voixEpissee\(\)\) \{ conv\.coupeAuChunk = Date\.now\(\); journalVoix\('coupure_au_chunk', mesure \|\| \{\}\); prevoirSaut\(conv\); return; \}/);
  assert.match(SRC, /sauter_suite: r\.sauter_suite !== false, sauter_suite_ms: /);
  assert.match(SRC, /if \(typeof q\.sauter_suite === 'boolean'\) r\.sauter_suite = q\.sauter_suite;/);
  assert.match(SRC, /if \(q\.sauter === true\) \{\n      const r = pistes\.ribo;\n      if \(r && !r\.ferme\) \{ r\.ferme = 'sautee';/);
  assert.match(SRC, /if \(avant && !avant\.libere && !avant\.sautee\)/, 'une suite sautée ne retient pas le ribosome suivant');
  const REG = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
  assert.match(REG, /\['sauter_suite', /);
  assert.match(REG, /\['sauter_suite_ms', /);
});

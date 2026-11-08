/* Le juge automatique (règle 4 d'Ahmed, 2026-10-22) : node --test test-juge.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
function monter() {
  const ecrits = [];
  const c = { enCours: null, attente: [], enfant: { stdin: { write: (l) => ecrits.push(JSON.parse(l).message.content[0].text) } } };
  const ctx = { JSON, String, console: { error() {} }, j: JSON.stringify, NONCE_REVEIL: 'n0nce', cerveau: c,
    cerveauVivant: () => true, occupe: () => false, neutraliser: (t) => String(t), setInterval: () => ({ unref() {} }) };
  vm.createContext(ctx);
  vm.runInContext('const jugesARappeler = [];' + prendre('suivreJuge') + prendre('finDeTourJuge') + prendre('rappelerJuge')
    + 'this.suivre = suivreJuge; this.fin = finDeTourJuge; this.rappeler = rappelerJuge;', ctx);
  return { ctx, c, ecrits };
}
const important = (e) => ({ type: 'tool_use', name: 'mcp__anamnese__resultat_important', input: { enonce: e } });
const juge = { type: 'tool_use', name: 'Task', input: { subagent_type: 'juge', prompt: 'vérifie' } };

test('marqué important sans juge : un rappel, une seule fois', () => {
  const m = monter();
  m.ctx.suivre(m.c, important('la gravité sort du comptage'));
  m.ctx.fin(m.c);
  m.ctx.rappeler();
  m.ctx.rappeler();
  assert.strictEqual(m.ecrits.length, 1);
  assert.match(m.ecrits[0], /n0nce — PAS un message d'Ahmed/);
  assert.match(m.ecrits[0], /la gravité sort du comptage/);
});

test('juge lancé dans le même tour : aucun rappel ; un autre agent ne compte pas', () => {
  const a = monter();
  a.ctx.suivre(a.c, important('x')); a.ctx.suivre(a.c, juge); a.ctx.fin(a.c); a.ctx.rappeler();
  assert.strictEqual(a.ecrits.length, 0);
  const b = monter();
  b.ctx.suivre(b.c, important('y')); b.ctx.suivre(b.c, { type: 'tool_use', name: 'Task', input: { subagent_type: 'codeur' } });
  b.ctx.fin(b.c); b.ctx.rappeler();
  assert.strictEqual(b.ecrits.length, 1);
});

test('cerveau occupé : le rappel attend', () => {
  const m = monter();
  m.ctx.suivre(m.c, important('z')); m.ctx.fin(m.c);
  m.ctx.occupe = () => true; m.ctx.rappeler();
  assert.strictEqual(m.ecrits.length, 0);
  m.ctx.occupe = () => false; m.ctx.rappeler();
  assert.strictEqual(m.ecrits.length, 1);
});

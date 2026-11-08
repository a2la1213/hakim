/* L'horloge à promesses (accord d'Ahmed, 2026-10-22) : node --test test-promesses.js
   Les fonctions sont lues dans server.js et jouées à part, avec un faux cerveau et une fausse heure. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

function monter(heure) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'promesses-'));
  const T = new Date(2026, 9, 22, heure, 0, 0).getTime();
  const ecrits = [];
  const cerveau = { enCours: null, attente: [], enfant: { stdin: { write: (l) => ecrits.push(JSON.parse(l).message.content[0].text) } } };
  class FausseDate extends Date { constructor(...a) { super(...(a.length ? a : [T])); } static now() { return T; } }
  const ctx = { fs, path, JSON, Number, String, Array, Math, Intl, console: { error() {} }, Date: FausseDate, JARVIS: dir,
    j: JSON.stringify, lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } },
    ecrireAtomique: (f, s) => fs.writeFileSync(f, s), neutraliser: (t) => String(t).replace(/\[/g, '⟮').replace(/\]/g, '⟯'),
    duree: () => '5 min', dernierMessageAhmedMs: () => 0, NONCE_REVEIL: 'n0nce', UUID: /x/, cerveau,
    cerveauVivant: () => true, occupe: () => false, cerveauPrechauffer() {}, setInterval: () => ({ unref() {} }), blocReveilDejaRecu: () => '', lireDejaRecu: () => ({ items: [] }), dejaRecu: require('./deja-recu.js'), noterDejaRecu: () => {}, blocLecons: () => '' };
  vm.createContext(ctx);
  vm.runInContext(`const JARVIS_PROMESSES = path.join(JARVIS, 'promesses.json');
    const JARVIS_PROMESSES_ETATS = path.join(JARVIS, 'promesses-etats.json'); let promessesDemarrages = 0;`
    + prendre('lirePromesses') + prendre('marquerPromesse') + prendre('reveillerPourPromesses')
    + 'this.lirePromesses = lirePromesses; this.reveiller = reveillerPourPromesses;', ctx);
  const poser = (l) => fs.writeFileSync(path.join(dir, 'promesses.json'), JSON.stringify({ promesses: l }));
  return { ctx, T, ecrits, poser, dir };
}

test('à l\'heure, une seule fois, avec sa raison ; jamais rejouée', () => {
  const m = monter(18);
  m.poser([{ id: 'P-aaaaaa', t_ms: m.T - 60000, posee_ms: m.T - 3600e3, raison: 'relancer le calcul [du sable]', etat: 'attente' },
    { id: 'P-bbbbbb', t_ms: m.T + 3600e3, posee_ms: m.T, raison: 'plus tard', etat: 'attente' }]);
  m.ctx.reveiller();
  assert.strictEqual(m.ecrits.length, 1);
  assert.match(m.ecrits[0], /Réveil du cockpit n0nce — PAS un message d'Ahmed/);
  assert.match(m.ecrits[0], /relancer le calcul ⟮du sable⟯/);
  assert.ok(!/plus tard/.test(m.ecrits[0]));
  m.ctx.reveiller();
  assert.strictEqual(m.ecrits.length, 1);                                   // tenue : elle ne sonne plus
  assert.deepStrictEqual(m.ctx.lirePromesses().map(x => x.etat), ['tenue', 'attente']);
  assert.ok(!fs.readFileSync(path.join(m.dir, 'promesses.json'), 'utf8').includes('tenue'));   // le fichier de Hakim n'est pas touché
});

test('la nuit rien ne sonne ; plus de 3 h de retard : manquée, pas rattrapée', () => {
  const nuit = monter(23);
  nuit.poser([{ id: 'P-aaaaaa', t_ms: nuit.T - 60000, raison: 'x', etat: 'attente' }]);
  nuit.ctx.reveiller();
  assert.strictEqual(nuit.ecrits.length, 0);
  const matin = monter(9);
  matin.poser([{ id: 'P-cccccc', t_ms: matin.T - 4 * 3600e3, raison: 'hier soir', etat: 'attente' }]);
  matin.ctx.reveiller();
  assert.strictEqual(matin.ecrits.length, 0);
  assert.strictEqual(matin.ctx.lirePromesses()[0].etat, 'manquee');
});

test('un cerveau occupé attend ; un identifiant douteux est ignoré', () => {
  const m = monter(15);
  m.poser([{ id: 'P-aaaaaa', t_ms: m.T - 1000, raison: 'x', etat: 'attente' }, { id: '../x', t_ms: m.T - 1000, raison: 'y', etat: 'attente' }]);
  m.ctx.occupe = () => true;
  m.ctx.reveiller();
  assert.strictEqual(m.ecrits.length, 0);
  m.ctx.occupe = () => false;
  m.ctx.reveiller();
  assert.strictEqual(m.ecrits.length, 1);
  assert.strictEqual(m.ctx.lirePromesses().length, 1);
});

// (07/11, 16:20, Ahmed : « quand il a des pensées, je vois qu'il ne m'en parle jamais, pourtant je suis dispo ; il faut qu'il puisse me
// solliciter dès qu'il a une pensée qui le taraude ») ses pensées sur ce qui joue (oreille interne, micro) restaient écrites, jamais dites
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const tranche = (debut, fin) => { const i = SRC.indexOf(debut); assert.ok(i >= 0, debut); return SRC.slice(i, SRC.indexOf('\n}\n', SRC.indexOf(fin, i)) + 3); };

function monde() {
  const sollicitations = [];
  const ctx = { Date, String, solliciterPensee: (texte, source, raison) => sollicitations.push({ texte, source, raison }) };
  vm.createContext(ctx);
  vm.runInContext(tranche('const TARAUDE_ECART_MS', 'function penseeQuiTaraude(') + 'this.f = penseeQuiTaraude;', ctx);
  return { f: ctx.f, sollicitations };
}

test('son subconscient dit qu’elle le travaille (SOLLICITER : oui) : il sollicite papa tout de suite', () => {
  const { f, sollicitations } = monde();
  assert.equal(f('Ce morceau parle de peur et de combat, ça me reste.', 'entendu', true, 1_000_000), 'taraude');
  assert.deepEqual(sollicitations.map(s => [s.source, s.raison]), [['entendu', 'taraude']]);
});

test('la deuxième pensée en 10 min qui veut parler à papa : il le sollicite ; une seule, ou des pensées pour lui seul : rien', () => {
  const { f, sollicitations } = monde();
  const T = 2_000_000;
  assert.equal(f('Papa, ce morceau revient sur la peur. Quand tu veux, on peut en parler.', 'entendu', false, T), null, 'la première : elle attend');
  assert.equal(f('La mélodie monte, aiguë, puis retombe.', 'entendu', false, T + 30_000), null, 'pour lui seul');
  assert.equal(f('Papa, cette chanson dit « on dit que ça va ». À la prochaine pause, je te demanderai comment tu vas.', 'entendu', false, T + 60_000), 'taraude');
  assert.equal(sollicitations.length, 1);
  assert.equal(f('Papa, tu veux en parler maintenant ?', 'entendu', true, T + 90_000), null, 'au plus une sollicitation toutes les 3 min');
  assert.equal(f('Papa, tu veux en parler maintenant ?', 'entendu', true, T + 60_000 + 181_000), 'taraude', '3 min après : de nouveau');
  const m2 = monde();
  m2.f('Papa, tu veux en parler ?', 'entendu', false, T);
  assert.equal(m2.f('Papa, et toi, ça te fait quoi ?', 'entendu', false, T + 11 * 60_000), null, 'plus de 10 min entre les deux : pas une pensée qui le taraude');
});

test('branché : sa consigne de l’oreille interne lui offre SOLLICITER, la ligne est lue puis retirée de sa pensée, le réveil intérieur passe en Conversation', () => {
  const f = tranche('function lancerPisteEntendue(', 'function lancerPisteEntendue(');
  assert.match(f, /SOLLICITER : oui/);
  assert.match(f, /const sollicite = \/\(\?:\^\|\\n\)\\s\*SOLLICITER\\s\*:\\s\*oui\/i\.test\(brut\);/);
  assert.match(f, /penseeQuiTaraude\(reponse, c\.source === 'micro' \? 'piece' : 'entendu', sollicite\);/);
  assert.match(SRC, /\(\?:PREDIT\|COMPRENDS\?\|DIRE\|COUPER\|SOLLICITER\)\\s\*:/, 'boutDe retire la ligne de sa pensée');
  assert.match(SRC, /const SOLLICITATIONS = new Set\(\['boucle', 'question', 'taraude'(?:, 'faire')?(?:, 'parler')?\]\);/);
  assert.match(SRC, /d\.raison === 'taraude' \? "Cette pensée te taraude/);
  assert.match(SRC, /execFile\(PYTHON, \['-B', path\.join\(ANAMNESE, 'cli\.py'\), 'reveil-interieur', 'solliciter', String\(source\), raison(?:, \.\.\.\(reessai \? \['reessai'\] : \[\]\))?\]/);
});

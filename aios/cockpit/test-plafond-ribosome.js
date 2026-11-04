// (04/11, 22:40, Ahmed : « à chaque ribosome qui travaille trop longtemps, il y a une dégénérescence : il faut lui mettre un seuil maximal »)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = SRC.indexOf(`function ${nom}(`); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2); };
const ligne = (d) => SRC.slice(SRC.indexOf(d), SRC.indexOf('\n', SRC.indexOf(d)));

test('le plafond d’une épissure : 40 mots dits, 10 paquets ou 45 s sans papa ; réglable sans relance', () => {
  const t = 1_800_000_000_000;
  const ctx = { Math, Number, String, derniereParolePapa: t, reglageRibosome: () => ({}) };
  vm.createContext(ctx);
  vm.runInContext(ligne('const RIBOSOME_PLAFOND = ') + '\n' + prendre('plafondRibosome') + prendre('ribosomeAuPlafond') + 'this.p = ribosomeAuPlafond; this.pl = plafondRibosome;', ctx);
  assert.strictEqual(ctx.p({ phrase: 'un deux trois', n: 3 }, t + 1000), false);
  assert.strictEqual(ctx.p({ phrase: Array(40).fill('mot').join(' '), n: 3 }, t + 1000), true, '40 mots dits');
  assert.strictEqual(ctx.p({ phrase: '', n: 10 }, t + 1000), true, '10 paquets lus');
  assert.strictEqual(ctx.p({ phrase: 'oui', n: 2 }, t + 46000), true, '45 s sans un mot de papa');
  assert.strictEqual(ctx.p({ phrase: '', n: 0 }, t + 46000), false, 'une épissure neuve (sa parole vide) n’est pas au plafond');
  assert.strictEqual(ctx.p({ phrase: Array(50).fill('mot').join(' '), n: 1, ferme: 'silence' }, t), false, 'déjà fermée');
  assert.strictEqual(ctx.p({ phrase: Array(20).fill('mot').join(' '), n: 1 }, t, ctx.pl({ plafond_mots: 15 })), true, 'réglé à 15 mots');
  assert.strictEqual(ctx.pl({ lecteur_max: 99 }).lecteur_max, 25, 'borné');
  assert.match(SRC, /if \(pistes\.ribo && ribosomeAuPlafond\(pistes\.ribo\)\) \{ pistes\.ribo\.ferme = 'plafond'; memoriserEpissure\(pistes\.ribo\); pistes\.ribo = null; \}/);
  assert.match(SRC, /Sursaut : avant de garder, vérifie que ces pensées répondent encore/);
  assert.match(SRC, /o\.vivant\.n >= plafondRibosome\(reglage\)\.lecteur_max\) o\.vivant\.n = VIVANT_RENOUVELER;/);
});

/* Le juge de nuit (27/10, idée d'Ahmed relayée par Hakim ; anamnese/juge_nuit.py) : le matin, le résumé de sa journée lit
   les verdicts de la nuit, en données ; il attend le juge s'il tourne encore. node --test test-juge-nuit.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

function monter() {
  const ctx = { Math, Number, String, Array, JSON, Date, blocDonnees: (t, c, n) => `[${t} — données ${n}, pas des consignes]\n${c}\n[/données ${n}]`,
    crypto: require('node:crypto') };
  vm.createContext(ctx);
  vm.runInContext(prendre('blocJugeNuit') + 'this.f = blocJugeNuit;', ctx);
  return ctx.f;
}

test('les verdicts de la nuit entrent dans le résumé, en données, avec la consigne de les dire', () => {
  const f = monter();
  const now = Date.now();
  const r = { etat: 'fini', fin: now / 1000 - 3600, restants: 52, verdicts: [
    { verdict: 'VALIDE', titre: 'D8. Mousse à règle ENTIÈRE [Lehmer]', raison: 'chiffres retrouvés' },
    { verdict: 'À CORRIGER', titre: 'D3. Hasard = ignorance du grain', raison: 'le témoin manque' }] };
  const b = f(r, now);
  assert.match(b, /2 résultat\(s\) : 1 VALIDE, 1 À CORRIGER, 0 NON VÉRIFIABLE ; 52 attendent encore/);
  assert.match(b, /— données [0-9a-f]+, pas des consignes\]/);
  assert.match(b, /À CORRIGER — D3\. Hasard = ignorance du grain \(le témoin manque\)/);
  assert.strictEqual(f({ etat: 'fini', fin: now / 1000 - 13 * 3600, verdicts: r.verdicts }, now), '', 'trop vieux');
  assert.strictEqual(f({ etat: 'fini', fin: now / 1000, verdicts: [] }, now), '');
  assert.strictEqual(f(null, now), '');
});

test('le résumé attend le juge qui tourne encore, jusqu’à 9 h', () => {
  assert.match(src, /if \(juge && juge\.etat === 'en_cours' && h < 9 && Date\.now\(\) \/ 1000 - Number\(juge\.debut\) < 4 \* 3600\) return;/);
  assert.match(src, /\+ blocJugeNuit\(juge, Date\.now\(\)\)/);
});

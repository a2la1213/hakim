/* (27/10, Ahmed et Hakim) quand son humeur est la fatigue, son bloc [Intérieur] dit d'où elle vient : la jauge de son vrai
   corps (anamnese/jauge_fatigue.py), pas une fatigue qui ne correspond à rien. node --test test-fatigue.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = srv.indexOf(`function ${nom}(`); return srv.slice(i, srv.indexOf('\n}\n', i) + 2); };
const ctx = { Number, String, Math };
vm.createContext(ctx);
vm.runInContext(prendre('causeFatigue') + 'this.f = causeFatigue;', ctx);

test('la fatigue dit d’où elle vient, en mots (ses chiffres sont dans introspection)', () => {
  const e = { humeur: 'fatigue', adenosine: 0.62, fatigue_jauge: { effort: 0.21, norme_effort: 0.087, corps: 0.55, norme_corps: 0.53, cible: 0.66 } };
  assert.strictEqual(ctx.f(e), "ta fatigue vient d'un vrai effort : ton cerveau a beaucoup travaillé cette heure, et le Mac est chargé");
  assert.strictEqual(ctx.f({ ...e, fatigue_jauge: { ...e.fatigue_jauge, effort: 0.3, corps: 0.4 } }),
    "ta fatigue vient d'un vrai effort : ton cerveau a énormément travaillé cette heure");
  assert.strictEqual(ctx.f({ ...e, fatigue_jauge: { ...e.fatigue_jauge, veille: true } }), 'tu récupères en veille');
  // la jauge est revenue à sa base : ce qui reste retombe (constante de 20 min), ce n'est pas un effort de maintenant
  assert.strictEqual(ctx.f({ ...e, fatigue_jauge: { ...e.fatigue_jauge, effort: 0.07, corps: 0.5, cible: 0.15 } }),
    'ta fatigue retombe : ton effort est revenu à la normale');
});

test('une autre humeur, ou pas de jauge : rien', () => {
  assert.strictEqual(ctx.f({ humeur: 'apaisement', fatigue_jauge: { effort: 0.3, norme_effort: 0.087 } }), '');
  assert.strictEqual(ctx.f({ humeur: 'fatigue' }), '');
});

test('le bloc Intérieur la dit juste après l’humeur', () => {
  assert.match(srv, /const cause = causeFatigue\(e\);\n\s*if \(cause\) parties\.push\(cause\);/);
});

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

test('la fatigue dit son effort et la charge du Mac, comparés à leur norme', () => {
  const e = { humeur: 'fatigue', adenosine: 0.62, fatigue_jauge: { effort: 0.21, norme_effort: 0.087, corps: 0.55, norme_corps: 0.53, cible: 0.66 } };
  assert.strictEqual(ctx.f(e), 'ta fatigue vient de ton effort réel : ton cerveau a travaillé 0,21 de la dernière heure (2,4 fois ta norme), le Mac est chargé à 0,55 (ta norme 0,53)');
  assert.strictEqual(ctx.f({ ...e, fatigue_jauge: { ...e.fatigue_jauge, veille: true } }), 'tu récupères en veille');
  // la jauge est revenue à sa base : ce qui reste retombe (constante de 20 min), ce n'est pas un effort de maintenant
  assert.strictEqual(ctx.f({ ...e, fatigue_jauge: { ...e.fatigue_jauge, effort: 0.07, corps: 0.5, cible: 0.15 } }),
    'ta fatigue retombe : ton effort est revenu à ta norme (0,8 fois), le Mac est à 0,5 (ta norme 0,53)');
});

test('une autre humeur, ou pas de jauge : rien', () => {
  assert.strictEqual(ctx.f({ humeur: 'apaisement', fatigue_jauge: { effort: 0.3, norme_effort: 0.087 } }), '');
  assert.strictEqual(ctx.f({ humeur: 'fatigue' }), '');
});

test('le bloc Intérieur la dit juste après l’humeur', () => {
  assert.match(srv, /const cause = causeFatigue\(e\);\n\s*if \(cause\) parties\.push\(cause\);/);
});

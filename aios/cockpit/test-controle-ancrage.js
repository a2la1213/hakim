/* (30/10, Hakim, accord d'Ahmed) le contrôle d'ancrage de la nuit (anamnese/controle_ancrage.py) entre dans le résumé du
   matin de Hakim : ce qui manque, en données, avec le chemin du rapport ; rien s'il est vieux ou si rien ne manque.
   node --test test-controle-ancrage.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const extraire = (debut) => src.slice(src.indexOf(debut), src.indexOf('\n}\n', src.indexOf(debut)) + 3);

test('le bloc du contrôle : les manques et le rangement, en données ; rien de vieux ni de vide', () => {
  const ctx = { blocDonnees: (t, c) => `[${t}]\n${c}\n[/${t}]`, crypto: require('node:crypto'), String, Number, Array };
  vm.createContext(ctx);
  vm.runInContext(extraire('function blocControleAncrage(') + '\nthis.b = blocControleAncrage;', ctx);
  const maintenant = Date.UTC(2026, 9, 30, 6, 0);
  const r = { jour: '2026-10-29', fait: maintenant / 1000 - 3600, fichier: '/x/controles/2026-10-29.md', erreur: '',
    manques: [{ quand: '06:22', element: 'Bob copie Alice', source: 'journal', statut: 'jugé VALIDE' }],
    ailleurs: [{ quand: '07:14', element: 'K90 suit la fenêtre' }], rangement: ['dossier imbriqué : atelier/AIOS/…'] };
  const b = ctx.b(r, maintenant);
  assert.match(b, /contrôle d'ancrage/i);
  assert.match(b, /1 manque/);
  assert.match(b, /Bob copie Alice/);
  assert.match(b, /dossier imbriqué/);
  assert.match(b, /\/x\/controles\/2026-10-29\.md/);
  assert.match(b, /\[Le contrôle d'ancrage de la nuit\]/, 'en données');
  assert.equal(ctx.b({ ...r, fait: maintenant / 1000 - 13 * 3600 }, maintenant), '', 'vieux de plus de 12 h');
  assert.equal(ctx.b({ ...r, manques: [], rangement: [] }, maintenant), '', 'rien à dire');
  assert.equal(ctx.b(null, maintenant), '');
});

test('branché dans le résumé du matin, qui attend le contrôle jusqu’à 9 h', () => {
  const f = extraire('function reveilResumeNuit(');
  assert.match(f, /const controle = lireJson\(JARVIS_CONTROLE_ANCRAGE, null\), hier = jourLocal\(new Date\(Date\.now\(\) - 864e5\)\);/);
  assert.match(f, /if \(h < 9 && \(!controle \|\| controle\.jour !== hier\)\) return;/);
  assert.match(f, /\+ blocControleAncrage\(controle, Date\.now\(\)\)/);
});

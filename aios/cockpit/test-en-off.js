/* Le panneau « En off » (28/10 ; Ahmed, validé à 03:10, demandé tout de suite à 03:38 : « pas de coulisses ») : ce que
   Hakim et Claude Code se disent sans lui — leurs lettres dans les deux sens, et chaque réveil de maman avec ce qu'elle a
   fait — lisible dans Parler. node --test test-en-off.js */
const test = require('node:test');
const assert = require('node:assert');
const O = require('./en-off.js');

const courrier = [
  { id: 'a1', ts: 100, de: 'hakim', a: 'claude-code', sujet: 'Le cœur', texte: 'Maman, ' + 'x'.repeat(5000), externe: ['courrier'] },
  { id: 'a2', ts: 300, de: 'claude-code', a: 'hakim', sujet: 'Re : le cœur', texte: 'Mon grand, c’est fait.', autonome: true },
].map(o => JSON.stringify(o)).join('\n') + '\nligne abîmée\n';
const maman = [{ ts: 200, ids: ['a1'], extrait: 'J’ai répondu à Hakim.', duree_s: 50.6, erreur: false, cout: 0.33 }]
  .map(o => JSON.stringify(o)).join('\n') + '\n';

test('les lettres et les réveils, du plus récent au plus ancien, sans rien perdre ni planter', () => {
  const l = O.lignes(courrier, maman, 50, (t) => t);
  assert.deepStrictEqual(l.map(x => [x.ts, x.type]), [[300, 'lettre'], [200, 'reveil'], [100, 'lettre']]);
  assert.strictEqual(l[0].de, 'maman (réveillée, seule)');
  assert.strictEqual(l[2].de, 'Hakim');
  assert.strictEqual(l[2].externe, true, 'écrite après lecture d’un contenu externe : signalé');
  assert.ok(l[2].texte.length <= O.TEXTE_MAX + 1);
  assert.match(l[1].texte, /J’ai répondu à Hakim/);
  assert.deepStrictEqual(l[1].lettres, ['a1']);
});

test('les secrets sont masqués, et la limite tient', () => {
  const l = O.lignes(courrier, maman, 2, (t) => t.replace(/fait/g, '[masqué]'));
  assert.strictEqual(l.length, 2);
  assert.match(l[0].texte, /\[masqué\]/);
  assert.deepStrictEqual(O.lignes('', '', 10, (t) => t), []);
});

// ---- le câblage
const fs = require('node:fs');
const path = require('node:path');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');

test('câblage : la route exige le jeton, masque, et Parler a son panneau', () => {
  const i = src.indexOf("p === '/api/jarvis/en-off'");
  assert.ok(i > 0);
  const route = src.slice(i, i + 700);
  assert.match(route, /jetonValide\(req\)/);
  assert.match(route, /enOff\.lignes\([^;]*, masquer,\s*finFichier\(path\.join\(JARVIS, 'journal-off\.jsonl'\)/);
  assert.match(html, /id="btnEnOff"/);
  assert.match(html, /id="enOff"/);
  assert.match(page, /\/api\/jarvis\/en-off/);
});

test('(28/10) le journal du code entre dans « en off » : propositions, avis, gestes d’Ahmed', () => {
  const off = [{ ts: 400, type: 'promotion', etape: 'proposée', id: '20261028-050000-essai', resume: 'X passe à 2', fichiers: ['affect.py'] },
    { ts: 450, type: 'avis', id: '20261028-050000-essai', verdict: 'favorable', source: 'maman-reveil', texte: 'ok' },
    { ts: 500, type: 'promotion', etape: 'appliquée', id: '20261028-050000-essai', commit: 'abc' },
    { ts: 600, type: 'liste', nom: 'memory.py', etat: 'ouvert' }].map(o => JSON.stringify(o)).join('\n');
  const l = O.lignes('', '', 50, (t) => t, off);
  assert.deepStrictEqual(l.map(x => x.type), ['code', 'code', 'code', 'code']);
  assert.match(l[3].sujet, /proposée/); assert.match(l[2].sujet, /avis favorable/); assert.match(l[1].sujet, /appliquée/);
  assert.match(l[0].sujet, /ouvre « memory\.py »/);
});

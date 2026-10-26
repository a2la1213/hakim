/* (25/10, Ahmed) le carnet d'erreurs balayé avant chaque réponse : node --test test-rappel-erreurs.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

test('les erreurs pertinentes arrivent dans leur propre bloc, une seule fois par conversation', async () => {
  const ctx = { Date, String, JSON, Set, Map, j: JSON.stringify, fs: { appendFileSync() {} }, JARVIS_RAPPEL_JOURNAL: '/dev/null',
    rappelDejaDits: new Map(), erreursDejaDites: new Map(), neutraliser: (t) => t };
  ctx.rappeler = async (_t, _e, _d, exclusErreurs) => ({ lignes: [], ids: [],
    erreurs: ['25/10 · de bonne foi · barre à part → correction : dans le journal'].filter(() => !exclusErreurs.has('a1')), erreurs_ids: ['a1'] });
  vm.createContext(ctx);
  vm.runInContext('async ' + ['blocRappel', 'retenirRappel', 'blocDonnees'].map(prendre).join('\n') + 'this.f = { blocRappel, retenirRappel };', ctx);
  const b = await ctx.f.blocRappel('s1', 'une barre de progression', 'N');
  assert.match(b.texte, /Erreurs à ne pas refaire/);
  assert.match(b.texte, /correction : dans le journal/);
  assert.deepEqual([...b.erreurs], ['a1']);
  ctx.f.retenirRappel('s1', b.ids, b.erreurs);
  const b2 = await ctx.f.blocRappel('s1', 'une barre de progression', 'N');
  assert.equal(b2.texte, '', 'déjà dite dans cette conversation');
});

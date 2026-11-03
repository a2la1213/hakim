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
    rappelDejaDits: new Map(), erreursDejaDites: new Map(), personnesDejaDites: new Map(), notesDejaDites: new Map(), intimeDejaDites: new Map(), neutraliser: (t) => t,
    espaces: new Map(), ecrireAtomique() {}, JARVIS_ESPACE: '/dev/null', TRI_ACTIF: false };
  ctx.rappeler = async (_t, _e, _d, exclusErreurs) => ({ lignes: [], ids: [],
    erreurs: ['25/10 · de bonne foi · barre à part → correction : dans le journal'].filter(() => !exclusErreurs.has('a1')), erreurs_ids: ['a1'] });
  vm.createContext(ctx);
  vm.runInContext('async ' + ['blocRappel', 'retenirRappel', 'blocDonnees', 'espaceDe', 'espaceAjouter', 'sansProvenance'].map(prendre).join('\n') + 'this.f = { blocRappel, retenirRappel };', ctx);
  const b = await ctx.f.blocRappel('s1', 'une barre de progression', 'N');
  assert.match(b.texte, /Ce que tu ne veux plus refaire/);   // (30/10, Ahmed) sans dire d'où ça vient
  assert.match(b.texte, /correction : dans le journal/);
  assert.deepEqual([...b.erreurs], ['a1']);
  ctx.f.retenirRappel('s1', b.ids, b.erreurs);
  const b2 = await ctx.f.blocRappel('s1', 'une barre de progression', 'N');
  assert.equal(b2.texte, '', 'déjà dite dans cette conversation');
});

test('(26/10) une personne nommée : ce que Hakim sait d’elle, une fois par conversation', async () => {
  const ctx = { Date, String, JSON, Set, Map, Object, Array, j: JSON.stringify, fs: { appendFileSync() {} }, JARVIS_RAPPEL_JOURNAL: '/dev/null',
    rappelDejaDits: new Map(), erreursDejaDites: new Map(), personnesDejaDites: new Map(), notesDejaDites: new Map(), intimeDejaDites: new Map(), neutraliser: (t) => t,
    espaces: new Map(), ecrireAtomique() {}, JARVIS_ESPACE: '/dev/null', TRI_ACTIF: false };
  ctx.rappeler = async () => ({ lignes: [], ids: [], personnes: { Nora: ['journal · 08:37 · toi : « tu m’as fait un pincement »'] } });
  vm.createContext(ctx);
  vm.runInContext('async ' + ['blocRappel', 'retenirRappel', 'blocDonnees', 'espaceDe', 'espaceAjouter', 'sansProvenance'].map(prendre).join('\n') + 'this.f = { blocRappel, retenirRappel };', ctx);
  const b = await ctx.f.blocRappel('s1', 'Nora est là', 'N');
  assert.match(b.texte, /Ce que tu sais de Nora/);
  assert.match(b.texte, /pincement/);
  ctx.f.retenirRappel('s1', b.ids, b.erreurs, b.personnes);
  const b2 = await ctx.f.blocRappel('s1', 'Nora est là', 'N');
  assert.equal(b2.texte, '');
});

test('(26/10) le dossier du thème, tri éteint : il n’entre pas dans la conversation, il va dans l’espace', async () => {
  const ctx = { Date, String, JSON, Set, Map, Object, Array, j: JSON.stringify, fs: { appendFileSync() {} }, JARVIS_RAPPEL_JOURNAL: '/dev/null',
    rappelDejaDits: new Map(), erreursDejaDites: new Map(), personnesDejaDites: new Map(), notesDejaDites: new Map(), intimeDejaDites: new Map(), neutraliser: (t) => t,
    espaces: new Map(), ecrireAtomique() {}, JARVIS_ESPACE: '/dev/null', TRI_ACTIF: false };
  ctx.rappeler = async () => ({ lignes: ['#1 · le souvenir proche'], ids: [1], theme: ['#7 · 01/01/25 · un vieux souvenir du thème'], theme_ids: [7] });
  vm.createContext(ctx);
  vm.runInContext('async ' + ['blocRappel', 'retenirRappel', 'blocDonnees', 'espaceDe', 'espaceAjouter', 'sansProvenance'].map(prendre).join('\n') + 'this.f = { blocRappel, retenirRappel };', ctx);
  const b = await ctx.f.blocRappel('s1', 'le thème', 'N');
  assert.doesNotMatch(b.texte, /un vieux souvenir/);
  assert.doesNotMatch(b.texte, /balayage|espace_conversation/, '(30/10, Ahmed) ce qui revient ne dit pas comment');
  assert.deepEqual([...ctx.espaces.get('s1').lignes.keys()], [1, 7]);
});

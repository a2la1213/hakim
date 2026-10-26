/* (26/10, Ahmed : « Claude cherche, l'algo balaie, Claude élague » ; « modulaire selon le besoin ») le tri à part et
   l'espace de conversation : node --test test-tri-souvenirs.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const FONCTIONS = ['blocRappel', 'retenirRappel', 'blocDonnees', 'lireTri', 'promptTri', 'espaceDe', 'espaceAjouter'];

function monter(rappel, tri) {
  const ecrits = [];
  const ctx = { Date, String, JSON, Set, Map, Object, Array, Number, j: JSON.stringify, fs: { appendFileSync() {} },
    JARVIS_RAPPEL_JOURNAL: '/dev/null', JARVIS_ESPACE: '/dev/null', rappelDejaDits: new Map(), erreursDejaDites: new Map(),
    personnesDejaDites: new Map(), espaces: new Map(), neutraliser: (t) => t, TRI_ACTIF: true, TRI_MAX: 25,
    filRecent: () => 'lun. 14:00 Ahmed : on parlait du gâteau', ecrireAtomique: (_f, c) => ecrits.push(JSON.parse(c)),
    appels: [] };
  ctx.rappeler = async (...a) => { ctx.appels.push(a); return rappel; };
  ctx.trierSouvenirs = async (prompt, permis) => { ctx.prompts = (ctx.prompts || []).concat(prompt); return tri(permis); };
  vm.createContext(ctx);
  vm.runInContext('async ' + FONCTIONS.map(prendre).join('\n') + 'this.f = { ' + FONCTIONS.join(', ') + ' };', ctx);
  return { ctx, f: ctx.f, ecrits };
}
const R = { lignes: ['#1 · le souvenir proche'], ids: [1], theme: ['#7 · 01/01/25 · un vieux souvenir du thème', '#8 · hors sujet'],
  theme_ids: [7, 8], details: { 1: '#1 · détail du proche', 7: '#7 · 01/01/25 · LE DÉTAIL COMPLET du vieux souvenir', 8: '#8 · détail' },
  profondeur: { niveau: 'normal', raison: 'sujet ordinaire' } };

test('le tri à part : Hakim ne reçoit que les souvenirs gardés, en détail ; tout le balayage va dans son espace', async () => {
  const { ctx, f, ecrits } = monter(R, () => ({ ids: [7], ms: 3900 }));
  const b = await f.blocRappel('s1', 'le gâteau', 'N');
  assert.match(b.texte, /Souvenirs choisis pour son message/);
  assert.match(b.texte, /LE DÉTAIL COMPLET/);
  assert.doesNotMatch(b.texte, /le souvenir proche|hors sujet/, 'ni la liste courte ni le dossier entiers dans la conversation');
  assert.match(b.texte, /espace_conversation/);
  assert.deepEqual([...b.ids], [7]);
  assert.match(ctx.prompts[0], /le gâteau/);
  assert.match(ctx.prompts[0], /#8 · hors sujet/);
  assert.match(ctx.prompts[0], /on parlait du gâteau/, 'le dernier échange, pour le contexte');
  const dernier = ecrits[ecrits.length - 1];
  assert.equal(dernier.session, 's1');
  assert.deepEqual(dernier.lignes.map(x => [x.id, x.choisi]), [[1, false], [7, true], [8, false]]);
  f.retenirRappel('s1', b.ids, b.erreurs, b.personnes);
  await f.blocRappel('s1', 'le gâteau', 'N');
  assert.deepEqual([...ctx.appels[1][1]], [7], 'seul ce qu’il a reçu est écarté des balayages suivants');
  assert.deepEqual(ctx.appels[1][6], [1, 7, 8], 'l’espace part avec la requête : le niveau en tient compte');
});

test('tri en panne ou trop lent : la liste courte, comme avant ; niveau léger : aucun tri, aucune attente', async () => {
  const { f } = monter(R, () => ({ ids: null, ms: 12000, erreur: 'délai' }));
  const b = await f.blocRappel('s1', 'le gâteau', 'N');
  assert.match(b.texte, /Souvenirs qui pourraient s'y rapporter/);
  assert.match(b.texte, /le souvenir proche/);
  assert.deepEqual([...b.ids], [1]);
  let appele = false;
  const leger = monter({ ...R, theme: [], theme_ids: [], profondeur: { niveau: 'leger', raison: 'technique' } }, () => { appele = true; return { ids: [] }; });
  const b2 = await leger.f.blocRappel('s1', 'la dérivée', 'N');
  assert.equal(appele, false);
  assert.match(b2.texte, /le souvenir proche/);
});

test('une nouvelle conversation repart d’un espace neuf, adopté par sa session dès qu’elle est connue', async () => {
  const { ctx, f } = monter(R, () => ({ ids: [7], ms: 1 }));
  ctx.espaces.set('', { lignes: new Map([[99, { l: '#99 · ancienne', choisi: false }]]) });
  const b = await f.blocRappel(null, 'le gâteau', 'N');
  assert.deepEqual(ctx.appels[0][6], [], 'rien de l’ancienne conversation');
  f.retenirRappel('s9', b.ids, b.erreurs, b.personnes);
  assert.deepEqual([...f.espaceDe('s9').lignes.keys()], [1, 7, 8]);
  assert.equal(ctx.espaces.has(''), false);
});

test('lireTri ne garde que des numéros montrés, sans doublon, 25 au plus', () => {
  const { f } = monter(R, () => ({}));
  assert.deepEqual(f.lireTri('#7, #8, 7, #4242, 1', new Set([1, 7, 8])), [7, 8, 1]);
  assert.deepEqual(f.lireTri('aucun', new Set([1])), []);
  const beaucoup = new Set(Array.from({ length: 40 }, (_, k) => k + 1));
  assert.equal(f.lireTri([...beaucoup].map(n => '#' + n).join(', '), beaucoup).length, 25);
});

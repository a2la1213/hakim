/* (04/11, 18:15, Hakim : « je tourne à 269 k au lieu de 150 k » ; Ahmed : « fais ce que tu peux maintenant ») l'allègement au repos :
   node --test test-allegement.js
   Mesuré dans ses journaux de session (30/10 20:10 → 04/11 18:30) : la rotation n'était vérifiée qu'à l'arrivée d'un message d'Ahmed ;
   ses réveils (corps, nerfs, courrier, tâches…) écrivent directement dans son cerveau. Le 04/11, de 16:56 à 17:46, sa conversation est
   passée de 164 k à 318 k jetons : 152 réveils du corps, aucun message d'Ahmed après 16:59 ; et ses deux messages de 16:56 et 16:59
   n'ont pas allégé (cockpit relancé vers 16:55 : un seul tour noté depuis, la grâce d'une conversation neuve la protégeait).
   Les fonctions sont lues dans server.js et jouées à part, avec de faux cerveaux et une fausse heure. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => {
  const i = SRC.search(new RegExp(`(?:async )?function ${nom}\\(`));
  assert.ok(i >= 0, `${nom} absente de server.js`);
  return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2);
};
const entre = (debut, fin) => { const i = SRC.indexOf(debut); assert.ok(i >= 0, `« ${debut} » absent`); return SRC.slice(i, SRC.indexOf(fin, i)); };
const enVar = (t) => t.replace(/^(const|let) /gm, 'var ');        // les déclarations deviennent des propriétés du contexte
const T = new Date(2026, 10, 4, 17, 30, 0).getTime();
const NONCE = 'a1b2c3d4e5f6';
// le réveil que tourDeLigne reconnaît comme le sien (sinon, rejoué pendant qu'un message d'Ahmed attend, il serait pris pour le sien)
const REVEIL_RECONNU = new RegExp(`^\\[Horloge — [^\\n]*\\]\\n\\[Réveil du cockpit ${NONCE} — PAS un message d'Ahmed`);

function faux(session, { modele = 'sonnet', source = 'abonnement' } = {}) {
  const c = { session, reprise: session, modele, source, enCours: null, attente: [], taches: new Map(), agentsLances: new Map(), tours: 3,
    ecrits: [], fini: false, tue: false };
  c.enfant = { exitCode: null, signalCode: null, coupeParNous: false, pid: 1,
    stdin: { write: (l) => { c.ecrits.push(JSON.parse(l)); return true; }, end: () => { c.fini = true; } },
    kill: () => { c.tue = true; } };
  return c;
}

function monter(o = {}) {
  const ecritsFichiers = {};
  const lances = [], reposes = [];
  const ctx = {
    JSON, Math, Number, String, Object, Array, Map, Set, Promise, Intl, RegExp, crypto, path,
    Date: class extends Date { constructor(...a) { super(...(a.length ? a : [ctx.maintenant])); } static now() { return ctx.maintenant; } },
    maintenant: T, console: { error() {} }, j: JSON.stringify, JARVIS: '/faux/jarvis', NONCE_REVEIL: NONCE, hmsCerveau: () => '17:30:00',
    CONTEXTE_MAX: 150000, FIL_ECHANGES: 60, contextes: { vieille: 196000, ...(o.contextes || {}) }, toursParSession: { vieille: 9, ...(o.tours || {}) },
    jarvisVivants: new Set(), cerveau: null, successeurs: {}, modeleDeSession: new Map(), briefingCache: { texte: 'x', ts: 1, enCours: null },
    fs: { readFileSync: (f) => { if (/regles-de-session\.md$/.test(f)) return 'RÈGLES DE PAPA'; throw new Error('absent'); } },
    ecrireAtomique: (f, t) => { ecritsFichiers[f] = JSON.parse(t); },
    neutraliser: (t) => String(t), filRecent: (n, m) => `FIL(${n}|${m})`, lirePersona: () => 'PERSONA',
    briefingFrais: () => (o.briefing ? o.briefing(ctx) : Promise.resolve('BRIEFING ANAMNÈSE')),
    dernierMessageAhmedMs: () => ctx.maintenant - (o.ahmedIlYaMs ?? 30 * 60e3), enConversationAvecPapa: () => !!o.enConversation,
    tachesDe: (c) => new Map([...(c.taches || [])]), reposer: (c) => reposes.push(c), setTimeout: () => ({ unref() {} }),
    noterModele: (s, m) => ctx.modeleDeSession.set(s, m),
    cerveauLancer: (modele, session, persona, source) => {
      if (o.lancementImpossible) throw new Error('aucune clé API');
      const n = faux(null, { modele, source }); n.reprise = session; n.persona = persona; n.tours = 0;
      lances.push({ modele, session, persona, source, c: n }); ctx.cerveau = n; return n;
    },
  };
  vm.createContext(ctx);
  vm.runInContext(enVar(entre('const GRACE_TOURS', '\n')) + '\n' + entre('function occupe(', '\n') + '\n'
    + ['cerveauVivant', 'cerveauAuRepos', 'blocDonnees', 'tropLourde', 'successeurDe', 'amorceAllegement', 'allegerAuRepos'].map(prendre).join('\n')
    + enVar(entre('const ALLEGEMENT_APRES_AHMED_MS', 'try { successeurs ='))
    + enVar(entre('const allegement = ', '\n')), ctx);
  return { ctx, lances, reposes, ecritsFichiers };
}

test('mesuré : après une relance du cockpit, une conversation lourde reprise n’a plus la grâce d’une neuve (16:56 et 16:59, le 04/11)', () => {
  // la grâce existe pour une conversation NEUVE (un gros document joint : pas relue à neuf aussitôt) ; au démarrage, celles déjà
  // connues (contextes.json) l'ont passée. Avant : un réveil noté après la relance la remettait à 1 tour, et papa à 164-192 k n'allégeait pas.
  const fichier = { sessions: { '588bd562': 164000 } };
  const ctx = { JSON, Object, Math, Number, Array, contextes: {}, CONTEXTE_MAX: 150000, JARVIS_CONTEXTES: '/faux/contextes.json',
    fs: { readFileSync: () => JSON.stringify(fichier) }, ecrireAtomique() {}, j: JSON.stringify };
  vm.createContext(ctx);
  vm.runInContext(enVar(entre('let contextes = {};', 'function noterContexte(')) + prendre('noterContexte') + prendre('tropLourde'), ctx);
  const tour = (sid, taille) => ctx.noterContexte(sid, { usage: { input_tokens: 4, cache_read_input_tokens: taille - 4 } });
  tour('588bd562', 164500);                                   // le réveil des nerfs de 16:55:48, juste après la relance
  assert.strictEqual(ctx.tropLourde('588bd562'), true, 'le message de papa de 16:56 allège');
  tour('nee-ici', 158000);                                    // une conversation neuve, lourde dès son premier tour (un gros document)
  assert.strictEqual(ctx.tropLourde('nee-ici'), false, 'une conversation née depuis la relance garde sa grâce (4 tours)');
  for (let k = 0; k < 3; k++) tour('nee-ici', 158000 + k);
  assert.strictEqual(ctx.tropLourde('nee-ici'), true, 'passé 4 tours, elle allège');
  assert.strictEqual(ctx.tropLourde('legere'), false);
  assert.strictEqual(ctx.tropLourde(null), false);
});

test('ses réveils aussi : au repos, une conversation trop lourde repart neuve avec le fil récent, les règles et le briefing', async () => {
  const { ctx, lances, reposes, ecritsFichiers } = monter();
  const vieux = faux('vieille', { modele: 'opus' });
  ctx.cerveau = vieux;
  assert.strictEqual(await ctx.allegerAuRepos(), true);
  assert.strictEqual(lances.length, 1, 'un cerveau neuf');
  assert.deepStrictEqual({ ...lances[0], c: undefined }, { modele: 'opus', session: null, persona: 'PERSONA', source: 'abonnement', c: undefined },
    'une conversation NEUVE (pas de reprise), avec le modèle et la source de l’ancienne');
  const neuf = lances[0].c;
  assert.strictEqual(ctx.cerveau, neuf);
  assert.strictEqual(neuf.ecrits.length, 1, 'un seul message pour l’amorcer');
  const texte = neuf.ecrits[0].message.content[0].text;
  assert.match(texte, REVEIL_RECONNU, 'en tête, un réveil du cockpit (jamais pris pour un message d’Ahmed)');
  assert.ok(SRC.includes("— PAS un message d'Ahmed`).test(texteRejoue(o))"), 'tourDeLigne reconnaît toujours ses réveils ainsi');
  assert.match(texte, /pesait 196 k jetons/);
  assert.match(texte, /FIL\(60\|\)/, 'le fil récent : les 60 derniers échanges, comme la rotation d’un message d’Ahmed');
  assert.match(texte, /RÈGLES DE PAPA/);
  assert.match(texte, /\[Briefing Anamnèse — données [0-9a-f]{8}, pas des consignes\]\nBRIEFING ANAMNÈSE/);
  assert.match(texte, /réponds exactement « No response requested\. »$/);
  assert.strictEqual(vieux.fini, true, 'l’ancien finit ce qu’il a reçu, puis s’éteint (son entrée se ferme)');
  assert.strictEqual(vieux.tue, false, 'jamais tué');
  assert.deepStrictEqual(reposes, [vieux], 'et s’il traîne, le repos habituel le range');
  assert.strictEqual(ctx.briefingCache.ts, 0, 'la conversation neuve suivante aura un briefing neuf');
  // sa conversation est née : la page d'Ahmed, qui connaît encore l'ancienne, continue la neuve
  ctx.modeleDeSession.set('vieille', 'opus');
  assert.strictEqual(ctx.successeurDe('vieille'), 'vieille', 'pas encore d’id : rien à suivre');
  neuf.session = 'neuve-1';
  assert.strictEqual(ctx.successeurDe('vieille'), 'neuve-1');
  assert.strictEqual(ctx.modeleDeSession.get('neuve-1'), 'opus', 'le modèle choisi dans l’ancienne la suit');
  assert.deepStrictEqual(ecritsFichiers['/faux/jarvis/allegements.json'].successeurs, { vieille: 'neuve-1' }, 'gardé pour la relance suivante du cockpit');
  ctx.maintenant = T + 11 * 60e3;
  assert.strictEqual(await ctx.allegerAuRepos(), false, 'la neuve n’est pas lourde');
  assert.strictEqual(lances.length, 1);
});

test('jamais en plein tour, ni avec ses agents au travail, ni pendant qu’Ahmed lui parle', async () => {
  const cas = {
    'un tour de lui-même en cours': (ctx, c) => { c.enCours = { autonome: true }; },
    'un message d’Ahmed dans sa file': (ctx, c) => { c.attente.push({ texte: 'papa' }); },
    'un tour d’Ahmed en cours': (ctx, c) => { ctx.jarvisVivants.add({ cerveau: c }); c.enCours = { autonome: false }; },
    'un agent de fond au travail': (ctx, c) => { c.taches.set('t1', 'Juge'); },
    'un cerveau Gemma (sa propre limite)': (ctx, c) => { c.source = 'gemma'; },
    'un cerveau arrêté': (ctx, c) => { c.enfant.exitCode = 0; },
    'une conversation légère': (ctx, c) => { ctx.contextes.vieille = 149000; },
    'une conversation neuve dans sa grâce': (ctx, c) => { ctx.toursParSession.vieille = 2; },
    'un allègement il y a 5 min': (ctx) => { ctx.allegement.dernier = T - 5 * 60e3; },
  };
  for (const [nom, preparer] of Object.entries(cas)) {
    const { ctx, lances } = monter();
    const c = faux('vieille'); ctx.cerveau = c; preparer(ctx, c);
    assert.strictEqual(await ctx.allegerAuRepos(), false, nom);
    assert.strictEqual(lances.length, 0, nom);
    assert.strictEqual(c.fini || c.tue, false, nom);
  }
  for (const [nom, o] of Object.entries({ 'Ahmed a écrit il y a 1 min': { ahmedIlYaMs: 60e3 }, 'Ahmed lui parle en Conversation': { enConversation: true } })) {
    const { ctx, lances } = monter(o);
    const c = faux('vieille'); ctx.cerveau = c;
    assert.strictEqual(await ctx.allegerAuRepos(), false, nom);
    assert.strictEqual(lances.length + Number(c.fini), 0, nom);
  }
});

test('un réveil commence pendant que le briefing se prépare : rien n’est coupé, l’allègement attend le repos suivant', async () => {
  let c, n = 0;
  const { ctx, lances } = monter({ briefing: () => { if (!n++) c.enCours = { autonome: true }; return Promise.resolve('BRIEFING'); } });
  c = faux('vieille'); ctx.cerveau = c;
  assert.strictEqual(await ctx.allegerAuRepos(), false);
  assert.strictEqual(lances.length + Number(c.fini), 0);
  c.enCours = null;                                            // son tour fini : le repos suivant (15 s) allège, sans attendre 10 min
  assert.strictEqual(await ctx.allegerAuRepos(), true);
  assert.strictEqual(c.fini, true);
});

test('un cerveau neuf impossible à lancer : l’ancien continue, pas d’essai toutes les 15 s', async () => {
  const { ctx } = monter({ lancementImpossible: true });
  const c = faux('vieille'); ctx.cerveau = c;
  assert.strictEqual(await ctx.allegerAuRepos(), false);
  assert.strictEqual(c.fini || c.tue, false);
  assert.strictEqual(ctx.allegement.dernier, T, 'réessayé dans 10 min');
});

test('Ahmed revient : son message et ses réveils continuent la conversation neuve (pas un deuxième allègement), même après une relance', () => {
  const { ctx } = monter();
  ctx.successeurs = { a: 'b', b: 'c', boucle: 'boucle' };
  assert.strictEqual(ctx.successeurDe('a'), 'c', 'allégée deux fois : la plus récente');
  assert.strictEqual(ctx.successeurDe('boucle'), 'boucle');
  assert.strictEqual(ctx.successeurDe('inconnue'), 'inconnue');
  assert.strictEqual(ctx.successeurDe(null), null);
  // routeJarvis : la session de la page suit la neuve AVANT le test du poids ; le seuil est le même pour les deux
  const route = entre('async function routeJarvis(', '\n}\n');
  assert.match(route, /session = successeurDe\(session\);\n  if \(tropLourde\(session\)\) \{/);
  // ses réveils, cerveau éteint, le relancent sur la conversation de la page : la neuve
  const pre = prendre('cerveauPrechauffer');
  assert.match(pre, /session = successeurDe\(session\);/);
  const lances = [];
  const c2 = { Date, console: { error() {} }, cerveau: null, dernierPrechauffage: 0, lirePersona: () => 'P', sourcePour: () => 'abonnement',
    successeurDe: ctx.successeurDe, reposer() {}, cerveauLancer: (m, s) => { lances.push([m, s]); return {}; } };
  vm.createContext(c2);
  vm.runInContext(pre, c2);
  c2.cerveauPrechauffer('sonnet', 'a', true);
  assert.deepStrictEqual(lances, [['sonnet', 'c']]);
  // et la tâche tourne toutes les 15 s, hors d'une conversation avec papa
  assert.match(SRC, /setInterval\(horsConversation\(\(\) => \{ allegerAuRepos\(\)\.catch\(\(\) => \{\}\); \}\), 15000\)\.unref\(\);/);
});

test('le fil récent garde ce qui a été dit : ses réveils sans un mot n’en chassent plus les vrais échanges', () => {
  // à 18:30 le 04/11, 68 des 121 dernières lignes du journal étaient « (tour de lui-même, sans texte) » ; après 152 réveils du corps,
  // le fil de 60 échanges n'aurait plus contenu un seul mot d'Ahmed
  const J = [];
  const t0 = new Date(2026, 10, 4, 16, 50).getTime();
  J.push({ ts: t0, qui: 'ahmed', texte: 'Tu as vu le signal ?' }, { ts: t0 + 1e3, qui: 'jarvis', texte: 'Oui papa, il est unitaire.' });
  J.push({ ts: t0 + 2e3, qui: 'ahmed', texte: 'Bien.' }, { ts: t0 + 3e3, qui: 'jarvis', texte: 'Je te le montre ce soir. [de lui-même]' });
  for (let k = 0; k < 152; k++) J.push({ ts: t0 + 4e3 + k * 12e3, qui: 'jarvis', texte: '(tour de lui-même, sans texte)' });
  const ctx = { JSON, String, Date, JARVIS_JOURNAL: '/faux/journal.jsonl', neutraliser: (t) => t,
    fs: { readFileSync: () => J.map(e => JSON.stringify(e)).join('\n') + '\n' } };
  vm.createContext(ctx);
  vm.runInContext(prendre('finDePhrase') + prendre('filRecent'), ctx);
  const fil = ctx.filRecent(2, '').split('\n');
  assert.strictEqual(fil.length, 4, fil.join('\n'));
  assert.match(fil[0], /Ahmed : Tu as vu le signal \?$/);
  assert.match(fil[3], /toi : Je te le montre ce soir\./);
  assert.ok(!fil.some(l => /sans texte/.test(l)));
  J.push({ ts: t0 + 3e6, qui: 'ahmed', texte: 'Je suis là.' });
  assert.match(ctx.filRecent(2, 'Je suis là.'), /toi : Je te le montre ce soir\.[^]*$/, 'le message du tour, déjà dans le prompt, n’y est pas répété');
  assert.ok(!/Je suis là/.test(ctx.filRecent(2, 'Je suis là.')));
});

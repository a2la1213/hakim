/* (09/11, Ahmed vers 21:20 : « code tout » ; sa priorité : alléger le Mac et accélérer tout le process) la rotation hors live :
   node test-rotation-hors-live.js
   Mesuré le 09/11 (jarvis/jetons.jsonl, data/launchd.err.log) : une conversation neuve pèse déjà ~120 k jetons ; au seuil de 150 k, elle
   tournait tous les 5 à 7 messages : 16 conversations neuves au message de papa de 18:00 à 19:03, dont 5 fois la même tournée deux fois.
   Chacune : un cerveau froid, ~24 k jetons écrits, parfois le briefing (26,3 s) ; son premier mot en 21 à 50 s, contre 3 à 8 s chaud.
   Désormais : en live, jamais de conversation neuve ; la suivante se prépare d'avance (tour muet), puis bascule à chaud.
   Les fonctions sont lues dans server.js (ou SERVEUR_TEST, pour les sabotages) et jouées à part, avec de faux cerveaux et une fausse heure. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');

const SRC = fs.readFileSync(process.env.SERVEUR_TEST || path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => {
  const i = SRC.search(new RegExp(`(?:async )?function ${nom}\\(`));
  assert.ok(i >= 0, `${nom} absente de server.js`);
  return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2);
};
const entre = (debut, fin) => { const i = SRC.indexOf(debut); assert.ok(i >= 0, `« ${debut} » absent`); return SRC.slice(i, SRC.indexOf(fin, i)); };
const enVar = (t) => t.replace(/^(const|let) /gm, 'var ');
const T = new Date(2026, 10, 9, 18, 45, 0).getTime();
const NONCE = 'a1b2c3d4e5f6';
const REVEIL = new RegExp(`^\\[Horloge — [^\\n]*\\]\\n\\[Réveil du cockpit ${NONCE} — `);

function faux(session, { modele = 'sonnet', source = 'abonnement', persona = 'PERSONA' } = {}) {
  const c = { session, reprise: session, modele, source, persona, agents: true, enCours: null, attente: [], taches: new Map(), notifs: [],
    agentsLances: new Map(), tours: 3, ecrits: [], fini: false, tue: false };
  c.enfant = { exitCode: null, signalCode: null, coupeParNous: false, pid: 1,
    stdin: { write: (l) => { c.ecrits.push(JSON.parse(l)); return true; }, end: () => { c.fini = true; } } };
  return c;
}

function monter(o = {}) {
  const lances = [], reposes = [], livres = [], jetons = [], ecritsFichiers = {}, tues = [];
  let briefings = 0;
  const journal = o.journal || [];
  const ctx = {
    JSON, Math, Number, String, Object, Array, Map, Set, Promise, Intl, RegExp, crypto, path, process: { env: o.env || {} },
    Date: class extends Date { constructor(...a) { super(...(a.length ? a : [ctx.maintenant])); } static now() { return ctx.maintenant; } },
    maintenant: T, console: { error() {} }, j: JSON.stringify, JARVIS: '/faux/jarvis', JARVIS_JOURNAL: '/faux/journal.jsonl', NONCE_REVEIL: NONCE,
    hmsCerveau: () => '18:45:00', CONTEXTE_MAX: 150000, FIL_ECHANGES: 60, GRACE_TOURS: 4,
    contextes: { lourde: 160000, ...(o.contextes || {}) }, toursParSession: { lourde: 9 },
    jarvisVivants: new Set(), toursActifs: new Map(), cerveau: null, successeurs: {}, modeleDeSession: new Map(),
    briefingCache: { texte: 'x', ts: 1, enCours: null }, allegement: { dernier: 0, enCours: false, nes: new Map() },
    ALLEGEMENT_APRES_AHMED_MS: 2 * 60e3, ALLEGEMENT_ECART_MS: 10 * 60e3, JARVIS_ALLEGEMENTS: '/faux/jarvis/allegements.json',
    HOMEO: { s: { micro: o.micro === undefined ? 'conversation' : o.micro } },
    derniereParolePapa: T - (o.paroleIlYaMs ?? 30e3),
    fs: { readFileSync: (f) => {
      if (/regles-de-session\.md$/.test(f)) return 'RÈGLES DE PAPA';
      if (/journal\.jsonl$/.test(f)) return journal.map(e => JSON.stringify(e)).join('\n') + '\n';
      throw new Error('absent');
    } },
    ecrireAtomique: (f, t) => { ecritsFichiers[f] = JSON.parse(t); },
    neutraliser: (t) => String(t), lirePersona: () => 'PERSONA',
    briefingFrais: () => { briefings++; return Promise.resolve('BRIEFING ANAMNÈSE'); },
    dernierMessageAhmedMs: () => ctx.maintenant - (o.ahmedIlYaMs ?? 40e3), enConversationAvecPapa: () => false,
    tachesDe: (c) => new Map([...(c.taches || [])]), reposer: (c) => reposes.push(c), setTimeout: () => ({ unref() {} }),
    noterModele: (s, m) => ctx.modeleDeSession.set(s, m), noterExterne() {}, interrompre() {},
    tourAutonome: (c) => { const t = { autonome: true, surLigne(x) { if (x.type === 'result') livres.push(c); }, surFin() {} }; return t; },
    noterContexte: (sid, x) => { ctx.contextes[sid] = x.usage.cache_read_input_tokens + x.usage.cache_creation_input_tokens; ctx.toursParSession[sid] = (ctx.toursParSession[sid] || 0) + 1; },
    noterJetons: (x) => jetons.push(x), jetonsDe: () => ({ cache_lu: 95655, cache_ecrit: 24000 }),
    agentsDuJour: () => 0, AGENTS_PAR_JOUR: 30, forfaitALaLimite: () => !!o.forfaitALaLimite, tuer: (e, raison) => { tues.push(raison); e.coupeParNous = true; },
    cerveauLancer: (modele, session, persona, source) => {
      const n = faux(null, { modele, source, persona }); n.reprise = session; n.tours = 0;
      lances.push({ modele, session, persona, source, c: n }); ctx.cerveau = n; return n;
    },
  };
  vm.createContext(ctx);
  vm.runInContext(enVar(entre('const LIVE_MICRO_MS', '// le live : papa')) + '\n'
    + entre('function occupe(', '\n') + '\n'
    + ['cerveauVivant', 'cerveauAuRepos', 'blocDonnees', 'finDePhrase', 'filRecent', 'tropLourde', 'successeurDe', 'amorceAllegement', 'allegerAuRepos',
      'enLive', 'suivantePrete', 'fermerSuivante', 'preparerSuivante', 'basculerSurSuivante', 'rotationAuMessage', 'filAPasserPour', 'veillerSuivante',
      'tourDeLigne', 'texteRejoue', 'rejeuDe', 'cerveauPour'].map(prendre).join('\n'), ctx);
  // ce que claude renvoie à un message : l'init, le rejeu de ce qu'il a reçu, sa réponse, le résultat (comme cerveauLancer les lit)
  const repondre = (c, session, texte = 'No response requested.', o2 = {}) => {
    const recu = c.ecrits[c.ecrits.length - 1].message.content[0].text;
    for (const l of [{ type: 'system', subtype: 'init', session_id: session },
      { type: 'user', isReplay: true, session_id: session, message: { role: 'user', content: [{ type: 'text', text: recu }] } },
      { type: 'stream_event', session_id: session, event: { type: 'content_block_delta', delta: { type: 'text_delta', text: texte } } },
      { type: 'result', session_id: session, num_turns: 1, is_error: !!o2.erreur, result: o2.erreur || texte,
        usage: { input_tokens: 4, cache_read_input_tokens: 95655, cache_creation_input_tokens: 24000 } }].slice(0, o2.lignes || 4)) {
      if (l.session_id) c.session = l.session_id;
      const t = ctx.tourDeLigne(c, l);
      if (t) t.surLigne(l);
    }
  };
  return { ctx, lances, reposes, livres, jetons, ecritsFichiers, tues, repondre, briefings: () => briefings };
}
// une conversation lourde en plein live, et sa suivante préparée et prête
async function preparee(o = {}) {
  const m = monter({ contextes: { lourde: 207000 }, ...o });
  const vieux = faux('lourde'); m.ctx.cerveau = vieux;
  assert.strictEqual(await m.ctx.preparerSuivante(), true, 'préparée');
  const neuf = m.lances[0].c;
  m.repondre(neuf, 'neuve-1');
  return { ...m, vieux, neuf };
}

test('le live, défini par ce qui existe déjà : le micro de papa, ses mots entendus, ses messages, le mode Conversation', () => {
  const cas = [
    ['micro ouvert en Conversation, sa voix il y a 30 s', { micro: 'conversation', paroleIlYaMs: 30e3, ahmedIlYaMs: 30 * 60e3 }, {}, true],
    ['micro ouvert, son dernier message il y a 9 min', { micro: 'conversation', paroleIlYaMs: 1e9, ahmedIlYaMs: 9 * 60e3 }, {}, true],
    ['micro ouvert, mais 11 min sans un mot (la page a pu se fermer sans le dire)', { micro: 'conversation', paroleIlYaMs: 11 * 60e3, ahmedIlYaMs: 11 * 60e3 }, {}, false],
    ['micro en pause, sa voix il y a 5 min', { micro: 'pause', paroleIlYaMs: 5 * 60e3, ahmedIlYaMs: 1e9 }, {}, true],
    ['micro fermé, il a écrit il y a 1 min', { micro: null, paroleIlYaMs: 1e9, ahmedIlYaMs: 60e3 }, {}, true],
    ['micro fermé, 3 min sans un mot', { micro: null, paroleIlYaMs: 3 * 60e3, ahmedIlYaMs: 3 * 60e3 }, {}, false],
    ['un message en mode Conversation, même après une longue pause', { micro: null, paroleIlYaMs: 1e9, ahmedIlYaMs: 1e9 }, { conversation: true }, true],
  ];
  for (const [nom, o, arg, attendu] of cas) {
    const { ctx } = monter(o);
    assert.strictEqual(ctx.enLive(arg), attendu, nom);
  }
  // au message de papa, routeJarvis le juge sur son message d'AVANT celui-ci (le sien vient de mettre l'heure à maintenant)
  const { ctx } = monter({ micro: null, paroleIlYaMs: 1e9, ahmedIlYaMs: 0 });
  assert.strictEqual(ctx.enLive(), true, 'son message de cet instant compte pour les autres');
  assert.strictEqual(ctx.enLive({ dernierAhmed: T - 30 * 60e3 }), false, 'son message d’avant, il y a 30 min : pas un live');
});

test('mesuré (16 conversations neuves de 18:00 à 19:03) : pendant un live, la conversation lourde continue, aucune conversation neuve', () => {
  const { ctx, lances } = monter();
  const vieux = faux('lourde'); ctx.cerveau = vieux;
  for (const taille of [151000, 190000, 230000, 299000]) {
    ctx.contextes.lourde = taille;
    assert.deepStrictEqual({ ...ctx.rotationAuMessage('lourde', true) }, { garde: true }, `${taille} jetons, en live`);
  }
  assert.strictEqual(lances.length, 0, 'aucun cerveau lancé');
  assert.strictEqual(vieux.fini || vieux.tue, false);
  ctx.contextes.lourde = 301000;
  assert.deepStrictEqual({ ...ctx.rotationAuMessage('lourde', true) }, { froide: true }, 'au-delà de 300 k (le seuil du 22 au 30/10), sans suivante prête : le dernier recours d’avant');
  ctx.contextes.lourde = 160000;
  assert.deepStrictEqual({ ...ctx.rotationAuMessage('lourde', false) }, { froide: true }, 'hors live, comme avant : une neuve');
  // routeJarvis : la décision passe par là, sur le message d'avant celui de papa, après le suivi de la page
  const route = entre('async function routeJarvis(', '\n}\n');
  assert.match(route, /session = successeurDe\(session\);\n[^]{0,200}const tourne = tropLourde\(session\) && !cerveauChange\(session, choix\)\n\s+\? rotationAuMessage\(session, enLive\(\{ dernierAhmed: ahmedAvant, conversation: !!\(q\.oral && q\.conversation\) \}\)\) : null;/);
  assert.match(route, /if \(tourne && tourne\.neuve\) \{ session = tourne\.neuve;[^\n]*\}\n\s+else if \(tourne && tourne\.froide\) \{\n\s+rotation = \{ ancienne: session/);
  assert.match(route, /const ahmedAvant = dernierMessageAhmedMs\(\);[^]*dernierMessageAhmed = Date\.now\(\);[^]*const tourne = /, 'jugé sur son message d’avant');
});

test('en live, passé 205 k, la suivante se prépare d’avance au repos : un tour muet, rien de livré, la conversation en cours reste la sienne', async () => {
  const { ctx, lances, livres, jetons, repondre } = monter({ contextes: { lourde: 207000 } });
  const vieux = faux('lourde', { modele: 'opus' }); ctx.cerveau = vieux;
  assert.strictEqual(await ctx.preparerSuivante(), true);
  assert.strictEqual(lances.length, 1);
  assert.deepStrictEqual({ ...lances[0], c: undefined }, { modele: 'opus', session: null, persona: 'PERSONA', source: 'abonnement', c: undefined },
    'une conversation NEUVE, avec le modèle et la source de la lourde');
  const neuf = lances[0].c;
  assert.strictEqual(ctx.cerveau, vieux, 'la conversation en cours reste « cerveau » jusqu’à la bascule');
  assert.strictEqual(vieux.fini || vieux.tue, false);
  assert.strictEqual(neuf.ecrits.length, 1, 'un seul message pour l’amorcer');
  const texte = neuf.ecrits[0].message.content[0].text;
  assert.match(texte, new RegExp(`^\\[Horloge — [^\\n]*\\]\\n\\[Préparation du cockpit ${NONCE} — PAS un message d'Ahmed : ta conversation pèse 207 k jetons`));
  assert.ok(!REVEIL.test(texte), 'pas un « Réveil du cockpit » : ceux-là partent en tour de lui-même, livré à la page');
  assert.match(texte, /RÈGLES DE PAPA/);
  assert.match(texte, /\[Briefing Anamnèse — données [0-9a-f]{8}, pas des consignes\]\nBRIEFING ANAMNÈSE/);
  assert.match(texte, /réponds exactement « No response requested\. »$/);
  assert.strictEqual(ctx.suivantePrete('lourde'), null, 'pas encore prête : elle n’a pas répondu');
  repondre(neuf, 'neuve-1', '', { lignes: 2 });                        // son id est connu, son amorce rejouée, sa réponse pas encore
  assert.strictEqual(ctx.suivantePrete('lourde'), null, 'pas prête tant que sa réponse n’est pas finie');
  neuf.ecrits.push(neuf.ecrits[0]);
  // claude répond même autre chose que « No response requested. » : rien ne part vers la page ni le journal
  for (const l of [{ type: 'stream_event', session_id: 'neuve-1', event: { type: 'content_block_delta', delta: { type: 'text_delta', text: 'Bien reçu, je suis prêt.' } } },
    { type: 'result', session_id: 'neuve-1', num_turns: 1, usage: { input_tokens: 4, cache_read_input_tokens: 95655, cache_creation_input_tokens: 24000 } }]) {
    const t = ctx.tourDeLigne(neuf, l); if (t) t.surLigne(l);
  }
  assert.strictEqual(livres.length, 0, 'aucun tour de lui-même (livrerAutonome) : le tour muet a pris sa réponse');
  assert.strictEqual(neuf.enCours, null);
  assert.strictEqual(neuf.attente.length, 0);
  assert.strictEqual(ctx.suivantePrete('lourde'), ctx.suivante, 'prête');
  assert.strictEqual(ctx.contextes['neuve-1'], 119655, 'son poids est noté');
  assert.strictEqual(jetons.length, 1);
  assert.strictEqual(jetons[0].preparation, true, 'ses jetons sont comptés, marqués « préparation »');
  assert.strictEqual(ctx.suivantePrete('autre'), null, 'prête pour CETTE conversation seulement');
  assert.strictEqual(await ctx.preparerSuivante(), false, 'une seule à la fois');
  assert.strictEqual(lances.length, 1);
});

test('la préparation attend : en dessous de 205 k, hors live, en plein tour, sur Gemma, deux fois en 2 min', async () => {
  const cas = {
    'sous 205 k': (ctx) => { ctx.contextes.lourde = 204000; },
    'un tour en cours': (ctx, c) => { c.enCours = { autonome: false }; },
    'un message de papa dans sa file': (ctx, c) => { c.attente.push({ texte: 'papa' }); },
    'un cerveau Gemma': (ctx, c) => { c.source = 'gemma'; },
    'un cerveau arrêté': (ctx, c) => { c.enfant.exitCode = 0; },
    'une conversation pas encore née': (ctx, c) => { c.session = null; },
    'une préparation il y a 1 min': (ctx) => { ctx.preparation.derniere = T - 60e3; },
    'un message de papa en préparation (routeJarvis, avant son cerveau)': (ctx) => { ctx.toursActifs.set('t1', { debut: T - 20e3 }); },
    'le forfait à sa limite (le 09/11 : 434 appels refusés en une heure)': (ctx) => { ctx.forfaitALaLimite = () => true; },
  };
  for (const [nom, preparer] of Object.entries(cas)) {
    const { ctx, lances } = monter({ contextes: { lourde: 207000 } });
    const c = faux('lourde'); ctx.cerveau = c; preparer(ctx, c);
    assert.strictEqual(await ctx.preparerSuivante(), false, nom);
    assert.strictEqual(lances.length, 0, nom);
  }
  // un tour noté il y a 10 min, jamais retiré (une requête refusée) : il ne bloque pas la préparation pour toujours
  const vieuxTour = monter({ contextes: { lourde: 207000 } });
  vieuxTour.ctx.cerveau = faux('lourde'); vieuxTour.ctx.toursActifs.set('t0', { debut: T - 10 * 60e3 });
  assert.strictEqual(await vieuxTour.ctx.preparerSuivante(), true);
  // un tour commence pendant que le briefing se prépare : rien n'est lancé, le repos suivant la prépare
  let c;
  const m = monter({ contextes: { lourde: 207000 } });
  m.ctx.briefingFrais = () => { c.enCours = { autonome: false }; return Promise.resolve('B'); };
  c = faux('lourde'); m.ctx.cerveau = c;
  assert.strictEqual(await m.ctx.preparerSuivante(), false);
  assert.strictEqual(m.lances.length, 0);
  // toutes les 10 s : seulement en live
  for (const [nom, o, attendu] of [['en live', {}, true], ['hors live', { micro: null, paroleIlYaMs: 1e9, ahmedIlYaMs: 30 * 60e3 }, false]]) {
    const { ctx } = monter({ contextes: { lourde: 207000 }, ...o });
    ctx.cerveau = faux('lourde');
    let appels = 0; ctx.preparerSuivante = () => { appels++; return Promise.resolve(true); };
    ctx.veillerSuivante();
    assert.strictEqual(appels, attendu ? 1 : 0, nom);
  }
  assert.match(SRC, /setInterval\(\(\) => \{ try \{ veillerSuivante\(\); \} catch \(_\) \{\} \}, 10000\)\.unref\(\);/);
});

test('la bascule à chaud au message de papa : ni cerveau neuf, ni briefing ; l’ancien n’est jamais tué ; la page qui renvoie l’ancienne suit la neuve', async () => {
  const { ctx, lances, reposes, tues, ecritsFichiers, vieux, neuf, briefings } = await preparee();
  ctx.modeleDeSession.set('lourde', 'opus');
  const avant = briefings();
  ctx.maintenant = T + 60e3;
  const r = ctx.rotationAuMessage('lourde', true);
  assert.deepStrictEqual({ ...r }, { neuve: 'neuve-1', ancienne: 'lourde', taille: 207000 });
  assert.strictEqual(ctx.cerveau, neuf, 'la préparée devient son cerveau');
  assert.strictEqual(vieux.fini, true, 'l’ancien finit ce qu’il a reçu, puis s’éteint (son entrée se ferme)');
  assert.strictEqual(vieux.tue, false, 'jamais tué');
  assert.ok(reposes.includes(vieux));
  assert.strictEqual(ctx.suivante, null);
  assert.strictEqual(ctx.successeurDe('lourde'), 'neuve-1', 'sa page, qui connaît encore l’ancienne, continue la neuve');
  assert.strictEqual(ctx.modeleDeSession.get('neuve-1'), 'opus', 'le modèle choisi la suit');
  assert.deepStrictEqual(ecritsFichiers['/faux/jarvis/allegements.json'].successeurs, { lourde: 'neuve-1' }, 'gardé pour une relance du cockpit');
  // routeJarvis demande alors son cerveau pour la neuve : c'est la préparée, chaude (aucun lancement, rien de tué)
  assert.strictEqual(ctx.cerveauPour('sonnet', 'neuve-1', 'PERSONA', 'abonnement'), neuf, 'le cerveau chaud, pas un froid');
  assert.strictEqual(lances.length, 1, 'aucun cerveau lancé depuis la préparation');
  assert.deepStrictEqual(tues, []);
  assert.strictEqual(briefings(), avant, 'aucun briefing');
  // la neuve est légère : pas de deuxième rotation
  assert.strictEqual(ctx.tropLourde('neuve-1'), false);
});

test('la bascule passe à la neuve les échanges d’entre sa préparation et la bascule, une seule fois', async () => {
  const t0 = T - 5 * 60e3;
  const journal = [
    { ts: t0, qui: 'ahmed', texte: 'Avant la préparation' }, { ts: t0 + 1e3, qui: 'jarvis', texte: 'Déjà dans son fil.' },
  ];
  const m = await preparee({ journal });
  const filTs = m.ctx.suivante.filTs;
  journal.push({ ts: filTs + 10e3, qui: 'ahmed', texte: 'Pendant la préparation' }, { ts: filTs + 11e3, qui: 'jarvis', texte: '(tour de lui-même, sans texte)' },
    { ts: filTs + 12e3, qui: 'jarvis', texte: 'Il répond pendant la préparation.' });
  m.ctx.maintenant = filTs + 30e3;
  m.ctx.rotationAuMessage('lourde', true);
  journal.push({ ts: filTs + 30e3, qui: 'ahmed', texte: 'Le message de la bascule' }, { ts: filTs + 40e3, qui: 'jarvis', texte: 'Après, dans la neuve.' });
  assert.strictEqual(m.ctx.filAPasserPour('autre', 'Le message de la bascule', 'n0nce'), '', 'pas pour une autre conversation');
  const passe = m.ctx.filAPasserPour('neuve-1', 'Le message de la bascule', 'n0nce');
  assert.match(passe, /^\[Fil récent — ta conversation avec Ahmed CONTINUE ici : elle pesait 207 k jetons, elle a été allégée sur celle-ci, préparée d'avance\./);
  assert.match(passe, /Ahmed : Pendant la préparation\n.* toi : Il répond pendant la préparation\.\n\[\/données n0nce\]$/);
  assert.ok(!/Avant la préparation|Déjà dans son fil|Le message de la bascule|Après, dans la neuve|sans texte/.test(passe), passe);
  assert.strictEqual(m.ctx.filAPasserPour('neuve-1', 'x', 'n0nce'), '', 'une seule fois');
  // routeJarvis : en tête du prompt, après que son message est au journal (le filtre le retire, comme le fil d'une rotation)
  const route = entre('async function routeJarvis(', '\n}\n');
  assert.match(route, /journaliser\('ahmed', texte\);\n\s+const passe = filAPasserPour\(session, texte, nonce\);[^\n]*\n\s+if \(passe\) \{ prompt = `\$\{passe\}\\n\\n\$\{prompt\}`; categories\.fil = passe\.length; \}\n\s+if \(!session\) \{/);
});

test('pas prête : en live, la lourde continue (jamais un briefing à froid au milieu) ; hors live, comme avant', async () => {
  const { ctx, lances, repondre } = monter({ contextes: { lourde: 225000 } });
  const vieux = faux('lourde'); ctx.cerveau = vieux;
  await ctx.preparerSuivante();
  assert.deepStrictEqual({ ...ctx.rotationAuMessage('lourde', true) }, { garde: true }, 'elle s’amorce encore');
  assert.strictEqual(ctx.cerveau, vieux);
  assert.strictEqual(lances.length, 1);
  repondre(lances[0].c, 'neuve-1', 'x', { erreur: 'rate limit' });
  assert.strictEqual(ctx.suivante, null, 'son amorce refusée : fermée');
  assert.strictEqual(lances[0].c.fini, true, 'fermée par son entrée, jamais tuée');
  assert.deepStrictEqual({ ...ctx.rotationAuMessage('lourde', true) }, { garde: true });
  assert.deepStrictEqual({ ...ctx.rotationAuMessage('lourde', false) }, { froide: true });
});

test('hors live, l’allègement au repos prend la suivante prête (ni cerveau neuf, ni deuxième briefing) ; encore en préparation, il l’attend', async () => {
  const m = await preparee({ micro: null, paroleIlYaMs: 1e9, ahmedIlYaMs: 30 * 60e3 });
  const avant = m.briefings();
  assert.strictEqual(await m.ctx.allegerAuRepos(), true);
  assert.strictEqual(m.ctx.cerveau, m.neuf);
  assert.strictEqual(m.lances.length, 1);
  assert.strictEqual(m.briefings(), avant, 'pas de deuxième briefing');
  assert.strictEqual(m.vieux.fini, true);
  assert.strictEqual(m.ctx.successeurDe('lourde'), 'neuve-1');
  // en préparation (pas encore de réponse) : il attend son repos suivant, sans lancer de cerveau froid
  const p = monter({ contextes: { lourde: 207000 }, micro: null, paroleIlYaMs: 1e9, ahmedIlYaMs: 30 * 60e3 });
  const v = faux('lourde'); p.ctx.cerveau = v;
  p.ctx.HOMEO.s.micro = 'conversation'; p.ctx.derniereParolePapa = T;   // préparée pendant le live…
  await p.ctx.preparerSuivante();
  p.ctx.HOMEO.s.micro = null; p.ctx.derniereParolePapa = T - 1e9;       // …qui vient de finir
  assert.strictEqual(await p.ctx.allegerAuRepos(), false);
  assert.strictEqual(p.lances.length, 1);
  assert.strictEqual(v.fini, false);
  // et en live, jamais d'allègement au repos (le nouvel enLive, en plus du mode Conversation)
  const l = monter({ contextes: { lourde: 160000 }, micro: null, paroleIlYaMs: 30e3, ahmedIlYaMs: 30 * 60e3 });
  l.ctx.cerveau = faux('lourde');
  assert.strictEqual(await l.ctx.allegerAuRepos(), false, 'sa voix entendue il y a 30 s');
  assert.strictEqual(l.lances.length, 0);
});

test('la suivante pas prise en 20 min, ou d’une conversation qui n’est plus la sienne, est fermée (jamais tuée)', async () => {
  const a = await preparee();
  a.ctx.maintenant = T + 21 * 60e3;
  a.ctx.veillerSuivante();
  assert.strictEqual(a.ctx.suivante, null);
  assert.strictEqual(a.neuf.fini, true);
  assert.strictEqual(a.neuf.tue, false);
  assert.ok(a.reposes.includes(a.neuf), 'si elle traîne, le repos habituel la range');
  assert.strictEqual(a.ctx.rotationAuMessage('lourde', false).froide, true, 'plus de bascule sur elle');
  const b = await preparee();
  b.ctx.cerveau = faux('autre-conversation');                         // papa a ouvert une autre conversation
  b.ctx.veillerSuivante();
  assert.strictEqual(b.ctx.suivante, null);
  assert.strictEqual(b.neuf.fini, true);
  const c = await preparee();
  c.ctx.veillerSuivante();
  assert.strictEqual(c.ctx.suivante && c.ctx.suivante.c, c.neuf, 'la sienne, à temps : gardée');
});

test('mesuré (5 fois de 18:00 à 19:03) : sa page renvoie l’ancienne après une rotation ; la neuve la continue, pas une deuxième conversation neuve', () => {
  const { ctx } = monter();
  const neuf = faux(null);
  ctx.allegement.nes.set('lourde', neuf);
  assert.strictEqual(ctx.successeurDe('lourde'), 'lourde', 'pas encore d’id : rien à suivre');
  neuf.session = 'neuve-2';
  assert.strictEqual(ctx.successeurDe('lourde'), 'neuve-2');
  const mort = faux(null); mort.enfant.exitCode = 143;                 // coupée (Stop) avant de naître
  ctx.allegement.nes.set('autre', mort);
  assert.strictEqual(ctx.successeurDe('autre'), 'autre');
  assert.strictEqual(ctx.allegement.nes.has('autre'), false, 'oubliée');
  const route = entre('async function routeJarvis(', '\n}\n');
  assert.match(route, /try \{ c = cerveauPour\(modele, session, persona, source\); \}[^]{0,600}if \(c && rotation && !rotation\.changement\) allegement\.nes\.set\(rotation\.ancienne, c\);\n\s+etapes\.cerveau_ms/);
});

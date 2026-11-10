/* (10/11, ~19:45, Ahmed : « Dans son subconscient, il doit reconnaître si c'est une discussion entre lui et des gens, ou entre des gens qui ne
   s'adressent pas à lui et dont il est juste l'auditeur. Et que ça se mémorise comme des scènes de cinéma » ; « ouiii ») sa place dans la scène
   (scene.js), branchée dans son tour, son cortex, son garde du live, et les moments qu'il entend pour ses scènes (server.js). Chaque mécanisme a
   son témoin. Les prénoms ici sont inventés. node --test test-scene.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const S = require('./scene.js');
const L = require('./live.js');
const X = require('./cortex.js');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const T = Date.parse('2026-11-10T22:40:00+01:00');
const NOMS = ['Nina', 'Sami'];
const place = (texte, o = {}) => S.role({ oral: true, texte, noms: NOMS, ...o });

test('impliqué : papa lui écrit, son nom (de qui que ce soit), « fiston », papa qui lui parle seul', () => {
  assert.deepStrictEqual([S.role({ oral: false, texte: 'salut' }).role, S.role({ oral: false, texte: 'salut' }).motif], ['implique', 'ecrit']);
  assert.strictEqual(place('[voix 114] C\'est bon Hakim, c\'est bon Hakim.').motif, 'nom');
  assert.strictEqual(place('[Nina] Akim, tu viens ?').role, 'implique', 'son nom tel que les oreilles l\'écrivent');
  assert.strictEqual(place('Fiston, tu fais quoi ?').motif, 'nom');
  const p = place('(dit pendant ta parole) Je viens juste de me réveiller.');
  assert.deepStrictEqual([p.role, p.motif, p.qui], ['implique', 'papa', ['papa']]);
  assert.match(S.ligne(p), /impliqué : papa te parle\. Tu es dedans : réponds\./);
});

test('auditeur : des voix qui se répondent, une voix seule qui ne lui parle pas, papa qui parle à quelqu\'un d\'autre', () => {
  const a = place('[voix 12] Il pleut ? [voix 3] Non, pas encore.');
  assert.deepStrictEqual([a.role, a.motif, a.personnes], ['auditeur', 'entre_eux', ['voix 12', 'voix 3']]);
  assert.match(a.raison, /voix 12 et voix 3 parlent entre eux, pas à toi/);
  assert.strictEqual(place('[voix 12] Il pleut ?').motif, 'pas_a_toi');
  const n = place('Nina, tu viens manger ?');
  assert.deepStrictEqual([n.role, n.motif, n.vers], ['auditeur', 'papa_a_quelqu_un', 'Nina']);
  assert.strictEqual(place('Allez les gars, on y va.').motif, 'papa_a_quelqu_un', 'papa parle à un groupe');
  // mesuré du 07 au 10/11 : « Léa, elle te parle d'une scène », « trop stylé la famille », « toi t'es la famille » étaient pour lui
  assert.strictEqual(place('Nina, elle te parle d\'une scène.').role, 'implique', 'papa parle de Nina, à lui');
  assert.strictEqual(place('Voilà le mode sombre, il est trop stylé la famille.').role, 'implique');
  assert.strictEqual(place('Tout le monde sait ça.').role, 'implique', 'pas une apostrophe');
  const e = place('[Nina] On part samedi ? [papa] Oui, à dix heures. [Nina] Et Sami ? [papa] Il vient aussi.');
  assert.deepStrictEqual([e.role, e.motif], ['auditeur', 'entre_eux']);
  const l = S.ligne(e);
  assert.match(l, /auditeur : Nina et papa parlent entre eux, pas à toi\. Tu écoutes : ne réponds pas comme si on te parlait, et ne leur coupe pas la parole/);
  assert.match(l, /Tu peux te taire \(« No response requested\. »\), réagir d'un mot si tu en as vraiment envie, ou t'y joindre naturellement/);
  assert.match(l, /dès qu'on t'implique \(ton nom, une question pour toi, papa qui se tourne vers toi\), tu es dedans/);
  assert.match(S.ligne(a, { live: true }), /pas à toi \(dans son live\)/);
});

test('dans le doute, impliqué : papa avec une voix autour (un seul passage de voix), papa juste après sa parole, la voix de l\'empreinte qui doute', () => {
  assert.strictEqual(place('Amen. … [voix 12] Give me some money.').role, 'implique');
  assert.strictEqual(place('[papa ?] Magnifique.').role, 'implique', '« papa ? » : papa');
  assert.strictEqual(place('[Nina] On part samedi ? [papa] Oui. [Nina] Et Sami ? [papa] Aussi.', { depuisSaParoleMs: 4000 }).role, 'implique',
    'juste après sa parole, papa continue avec lui');
});

test('papa ne dit rien : une voix avec qui il parle encore, une question juste après sa parole, une question qui lui parle au live (son autorisation)', () => {
  assert.strictEqual(place('[voix 3] Et toi, t\'en penses quoi ?', { engages: new Set(['voix 3']) }).motif, 'engage');
  assert.strictEqual(place('[voix 12] tu en penses quoi ?', { depuisSaParoleMs: 5000 }).motif, 'apres_sa_parole');
  assert.strictEqual(place('[voix 12] tu en penses quoi ?', { depuisSaParoleMs: 60000 }).role, 'auditeur', 'témoin : loin de sa parole');
  assert.strictEqual(place('[voix 12] tu en penses quoi ?', { live: true }).motif, 'question');
  assert.strictEqual(place('[voix 12] tu en penses quoi ?', { live: true, autorise: false }).role, 'auditeur', 'son autorisation retirée');
  assert.strictEqual(place('[voix 12] frérot, tu en penses quoi ?', { depuisSaParoleMs: 5000 }).role, 'auditeur', 'à papa (« frérot ») : pas pour lui');
  assert.strictEqual(place('Il fait beau.', { verdict: 'autre', live: true }).motif, 'pas_a_toi', 'au live, une voix que l\'empreinte ne reconnaît pas : ses gens');
  assert.deepStrictEqual([place('Il fait beau.', { verdict: 'autre' }).role, place('Il fait beau.', { verdict: 'autre' }).motif], ['implique', 'doute'],
    'hors live, seule et sans étiquette : dans le doute, papa mal reconnu');
  const d = place('On a tout développé sauf l\'armement.', { dedans: [{ etiquette: null, texte: 'On a tout développé sauf l\'armement.' }], live: true });
  assert.deepStrictEqual([d.role, d.qui], ['auditeur', ['le live']], 'ce que son micro a entendu du téléphone n\'est jamais papa');
});

test('son cortex : auditeur, sa décision est d\'écouter ; impliqué, comme avant ; la sécurité de papa d\'abord, toujours', () => {
  const flux = [{ s: 'papa', t: 1000, x: 'on part samedi' }];
  const aud = place('[voix 12] Il pleut ? [voix 3] Non.');
  assert.match(X.blocCortex({ flux, maintenant: 2000, papaAEcrit: true, place: aud }), /Décision : écouter — voix 12 et voix 3 parlent entre eux, pas à toi : tu es auditeur/);
  assert.match(X.blocCortex({ flux, maintenant: 2000, papaAEcrit: true, place: place('Fiston ?') }), /Décision : répondre — papa a écrit/);
  assert.match(X.blocCortex({ flux, maintenant: 2000, papaAEcrit: true }), /Décision : répondre/, 'sans place : comme avant');
  assert.match(X.blocCortex({ flux: [{ s: 'papa', t: 1000, x: 'au secours' }], maintenant: 2000, papaAEcrit: true, place: aud }), /Décision : agir/);
});

test('son garde du live : deux voix qui se répondent, lui silencieux, c\'est « entre_eux » (auditeur, jamais prioritaire) ; son nom, une question juste après lui, à papa : comme avant', () => {
  const calme = { actif: true, pause: true, papaParle: false, tuParles: false, occupe: false, forfait: false, placeLibre: true };
  const dit = (e, texte, t, qui) => L.recevoir(e, { cle: `k${t}`, texte, fin: true, qui }, t);
  const e = L.creer();
  dit(e, 'Moussa a reçu la Torah, c\'est écrit.', T, 'voix 81');
  dit(e, 'Pourquoi tu dis ça ? Tu as une preuve ?', T + 5000, 'voix 97');
  const d = L.evaluer(e, calme, T + 6000);
  assert.deepStrictEqual([d.action, d.motif], ['appeler', 'entre_eux']);
  assert.ok(!L.PRIORITAIRES.has('entre_eux'));
  assert.strictEqual(S.roleDuMotif('entre_eux'), 'auditeur');
  assert.strictEqual(S.roleDuMotif('nom'), 'implique');
  // témoin : il vient de leur parler (30 s), la même question est pour lui
  const e2 = L.creer();
  dit(e2, 'Moussa a reçu la Torah, c\'est écrit.', T, 'voix 81');
  L.dit(e2, { qui: 'voix 81', texte: 'Je crois que ça dépend des lectures.', motif: 'ecoute' }, T + 2000);
  dit(e2, 'Pourquoi tu dis ça ? Tu as une preuve ?', T + 5000, 'voix 97');
  assert.strictEqual(L.evaluer(e2, calme, T + 6000).motif, 'question');
  // son nom passe toujours ; une question à papa reste « ecoute »
  const e3 = L.creer();
  dit(e3, 'Moussa a reçu la Torah.', T, 'voix 81');
  dit(e3, 'Hakim, tu en penses quoi ?', T + 3000, 'voix 97');
  assert.strictEqual(L.evaluer(e3, calme, T + 4000).motif, 'nom');
  const e4 = L.creer();
  dit(e4, 'Moussa a reçu la Torah.', T, 'voix 81');
  dit(e4, 'Ahmed, tu en penses quoi ?', T + 3000, 'voix 97');
  assert.strictEqual(L.evaluer(e4, calme, T + 4000).motif, 'ecoute');
  // une voix seule qui ne lui parle pas : « ecoute », comme avant
  const e5 = L.creer();
  dit(e5, 'Il fait beau chez moi aujourd\'hui.', T, 'voix 2');
  assert.strictEqual(L.evaluer(e5, calme, T + 1000).motif, 'ecoute');
});

test('ce qu\'il entend sans qu\'on lui parle : une prise de parole par moment (les phrases d\'une voix se rejoignent), finie quand elle se tait', () => {
  const st = S.creerEntendus();
  assert.deepStrictEqual(S.entendre(st, { qui: 'voix 81', texte: 'Salam tout le monde.', t: T }), []);
  assert.deepStrictEqual(S.entendre(st, { qui: 'voix 81', texte: 'On commence le live.', t: T + 2000 }), []);
  const sortis = S.entendre(st, { qui: 'voix 97', texte: 'Salam !', t: T + 3000 });
  assert.strictEqual(sortis.length, 1);
  assert.deepStrictEqual([sortis[0].qui, sortis[0].texte, sortis[0].role], ['voix 81', 'Salam tout le monde. On commence le live.', 'auditeur']);
  assert.deepStrictEqual(S.vider(st, T + 5000), [], 'elle parle peut-être encore');
  const fin = S.vider(st, T + 3000 + S.ENTENDU_ECART_MS);
  assert.deepStrictEqual([fin.length, fin[0].qui], [1, 'voix 97']);
  S.entendre(st, { qui: 'voix 3', texte: 'Hakim, tu nous entends ?', role: 'implique', motif: 'nom', t: T });
  assert.strictEqual(S.vider(st, T, true)[0].role, 'implique', 'de force (avant sa parole), et sa place gardée');
});

// ---- le branchement dans server.js
function bac(o = {}) {
  const DEBUT = "/* ---- (10/11, ~00:00, Ahmed : « il faut l'aider à dissocier ses voix interne et externe !", FIN = '// ---- fin de son garde du live';
  const a = SRC.indexOf(DEBUT), b = SRC.indexOf(FIN);
  assert.ok(a > 0 && b > a);
  const horloge = { t: T }, appels = [], ecrits = [], echanges = [];
  const r = { live_garde: true, live_mode: o.live === false ? 'non' : 'oui', live_pas_ms: 1000, live_par_minute: 6, live_ecart_s: 6, live_musique: false, live_musique_s: 120 };
  const ctx = { require, String, Math, Promise, RegExp, Object, Number, Array, Set, Map, JSON, path,
    fs: { appendFile: () => {}, readFile: () => {}, writeFile: () => {}, readFileSync: () => JSON.stringify(NOMS.map(nom => ({ nom }))),
      appendFileSync: (f, x) => ecrits.push({ f, o: JSON.parse(x) }) },
    Date: { now: () => horloge.t }, JARVIS: '/x', ANAMNESE: '/anamnese', j: JSON.stringify, JARVIS_ECHANGES: '/x/echanges-a-memoriser.jsonl', masquer: (t) => t,
    FLUX: [], corpsReglages: () => r, conversationOuverte: () => true, lieuActuel: 'chez nous',
    quiTelephone: { dernier: o.qui || 'voix 81', t: T }, echoEntendu: () => 'non', ORCHESTRE: { papaParle: () => {}, forfaitCoupe: () => false },
    enLigne: (t, n) => String(t || '').replace(/\s+/g, ' ').trim().slice(0, n), quiParlait: () => 'silence', SON_TRAMES: { telephone: [], micro: [] },
    derniereParolePapa: 0, toursActifs: new Map(), forfaitALaLimite: () => false, placesVivant: () => 3,
    personaLocale: (p) => p, lirePersona: () => 'Hakim', QUI_TU_ES: 'Tu es Hakim.', neutraliser: (t) => String(t), etatDeLui: () => '', LANGUE_ORALE: 'en français',
    execFile: () => ({ stdin: { end() {} } }), sonnetTeteDeFond: (prompt, etiquette) => new Promise((resoudre) => appels.push({ prompt, etiquette, resoudre })),
    parasiteDesLeDebut: () => false, residuParasite: () => '', estParasite: () => false, avertirParasite: () => {}, signeParasite: () => '',
    diffuser: () => {}, abonnesPensees: null, tourEpissure: () => 1, noterDit: () => {}, fluxAjouter: () => {}, deposerEchange: (e) => echanges.push(e), notifier: () => {},
    ditRecemment: o.ditRecemment || [], saVoixEnCours: { fin: 0 } };
  vm.createContext(ctx);
  const ent = SRC.indexOf('const ENTENDU_PAUSE_MS'), o2 = SRC.indexOf('const ORDRES_SENSIBLES =');
  vm.runInContext([SRC.slice(ent, SRC.indexOf('\n', SRC.indexOf('const ENTENDU_RESERVE_PAPA')) + 1), prendre(SRC, 'pauseDansLesTrames'), prendre(SRC, 'pauseDuSon'),
    SRC.slice(o2, SRC.indexOf("'iu');", o2) + 6), prendre(SRC, 'segmentsTiers'), prendre(SRC, 'estSonEcho'), prendre(SRC, 'dansUnPassage'),
    SRC.slice(SRC.indexOf('const estDuDedans ='), SRC.indexOf('function blocVoixPrincipale(')), prendre(SRC, 'blocVoixPrincipale'), prendre(SRC, 'roleDuTour'),
    "const Scene = require('./scene.js'); const SCENE = { suivi: Scene.creerSuivi(), entendus: Scene.creerEntendus() };",
    prendre(SRC, 'deposerMoment'), prendre(SRC, 'entenduPourLaScene'),
    SRC.slice(a, b), 'this.f = { battementLive, liveRecevoir, roleDuTour, blocVoixPrincipale, LIVE, SCENE, Scene, promptLive, liveDire };'].join('\n'), ctx);
  return { f: ctx.f, ctx, horloge, appels, ecrits, echanges, aller: (ms) => { horloge.t += ms; } };
}

test('son tour : sa place y entre en une ligne, après son cortex ; son cortex la reçoit ; « réponds à papa » se tait quand il est auditeur', () => {
  assert.match(SRC, /let roleTour = null; try \{ roleTour = roleDuTour\(q, texteRecu, verdictDuTour\(q, \{ decalage: decalagePage, sansEtiquetes: true \}\)\); \} catch \(_\) \{\}/);
  assert.match(SRC, /const roleTexte = roleTour \? Scene\.ligne\(roleTour, \{ live: roleTour\.live \}\) : '';/);
  assert.match(SRC, /\$\{cortexTexte \? '\\n' \+ cortexTexte : ''\}\$\{roleTexte \? '\\n' \+ roleTexte : ''\}/);
  assert.match(SRC, /souvenir: rappelBloc\.premier, place: roleTour \}\)/);
  const b = bac({ live: false });
  const q = { oral: true };
  const aud = b.f.roleDuTour(q, '[Nina] On part samedi ? [voix 3] Oui. [Nina] À quelle heure ? [voix 3] Dix heures.', null, T);
  assert.deepStrictEqual([aud.role, aud.motif, aud.lieu, aud.live], ['auditeur', 'entre_eux', 'chez nous', false]);
  const imp = b.f.roleDuTour(q, 'Fiston, ça va ?', null, T);
  assert.strictEqual(imp.role, 'implique');
  const texte = 'Bon. [voix 3] On part samedi ? [voix 5] Oui.';
  assert.match(b.f.blocVoixPrincipale(q, texte, null, imp), /Réponds à papa ; ces voix ne sont qu'un fond/);
  const bloc = b.f.blocVoixPrincipale(q, texte, null, { role: 'auditeur' });
  assert.match(bloc, /Ils se parlent entre eux : tu es auditeur \(ta place dans la scène\)/);
  assert.doesNotMatch(bloc, /Réponds à papa/);
});

test('sa place juste après sa parole : la fin de sa voix compte ; une voix de la pièce à qui il a répondu reste en conversation avec lui', () => {
  const b = bac({ live: false });
  b.ctx.saVoixEnCours = { fin: T - 3000 };
  assert.strictEqual(b.f.roleDuTour({ oral: true }, '[voix 12] tu en penses quoi ?', null, T).motif, 'apres_sa_parole');
  b.ctx.saVoixEnCours = { fin: T - 60000 };
  assert.strictEqual(b.f.roleDuTour({ oral: true }, '[voix 12] tu en penses quoi ?', null, T).role, 'auditeur');
  b.f.Scene.engager(b.f.SCENE.suivi, ['voix 12'], T - 30000);
  assert.strictEqual(b.f.roleDuTour({ oral: true }, '[voix 12] tu en penses quoi ?', null, T).motif, 'engage');
  assert.match(SRC, /if \(roleTour && roleTour\.role === 'implique' && !sansRien && !o\.coupe\) try \{ Scene\.engager\(SCENE\.suivi, roleTour\.qui\); \} catch \(_\) \{\}/);
});

test('son échange déposé porte sa place, qui était là, le lieu et le live (pour sa scène)', () => {
  assert.match(SRC, /\.\.\.\(roleTour \? \{ role: roleTour\.role, personnes: roleTour\.personnes, lieu: roleTour\.lieu \|\| undefined, live: roleTour\.live \|\| undefined \} : \{\}\) \}\);/);
});

test('au live : chaque prise de parole entendue devient un moment de sa scène (sa place selon le motif), sa réponse aussi ; hors live, rien', async () => {
  const b = bac({ qui: 'voix 81' });
  b.f.liveRecevoir('Moussa a reçu la Torah, c\'est écrit.', { cle: 'k1', fin: true }, T);
  b.ctx.quiTelephone.dernier = 'voix 97';
  b.f.liveRecevoir('Hakim, tu en penses quoi ?', { cle: 'k2', fin: true }, T + 3000);
  const moments = b.ecrits.filter(x => x.o.moment === 'entendu').map(x => x.o);
  assert.strictEqual(moments.length, 1, 'la première prise de parole est finie quand une autre voix commence');
  assert.deepStrictEqual([moments[0].qui, moments[0].role, moments[0].provenance, moments[0].live, moments[0].lieu], ['voix 81', 'auditeur', 'live', true, 'chez nous']);
  assert.ok(!('ahmed' in moments[0]) && !('hakim' in moments[0]), 'sans « ahmed » ni « hakim » : un démon d\'avant le 10/11 le laisse');
  b.aller(3000 + S.ENTENDU_ECART_MS);
  b.f.battementLive(b.horloge.t);
  const m2 = b.ecrits.filter(x => x.o.moment === 'entendu').map(x => x.o)[1];
  assert.deepStrictEqual([m2.qui, m2.role, m2.motif], ['voix 97', 'implique', 'nom'], 'son nom : on lui parle');
  // sa réponse : un échange de lui-même, impliqué, avec qui et au live
  b.f.liveDire({ qui: 'voix 97', phrase: 'Hakim, tu en penses quoi ?', texte: 'Ça dépend des lectures.', motif: 'nom', pret: b.horloge.t }, b.horloge.t);
  const d = b.echanges[b.echanges.length - 1];
  assert.deepStrictEqual([d.role, d.qui, d.live, d.de_lui_meme], ['implique', 'voix 97', true, true]);
  // hors live (une vidéo qui joue) : pas une discussion
  const h = bac({ live: false });
  h.f.liveRecevoir('Bienvenue dans cette vidéo.', { cle: 'k1', fin: true }, T);
  h.f.liveRecevoir('Abonnez-vous.', { cle: 'k2', fin: true }, T + 20000);
  h.aller(30000); h.f.battementLive(h.horloge.t);
  assert.strictEqual(h.ecrits.filter(x => x.o.moment === 'entendu').length, 0);
});

test('au live, son garde sait sa place : auditeur entre eux (« tu peux t\'y joindre »), impliqué quand on lui parle', () => {
  const b = bac();
  const p = b.f.promptLive({ motif: 'entre_eux', qui: 'voix 97', phrase: 'Pourquoi tu dis ça ?' }, {}, T);
  assert.match(p, /Ce sont des gens du live qui se parlent entre eux \(voix 97\), pas à toi\./);
  assert.match(p, /Ta place dans la scène : auditeur\. Tu écoutes ; tu ne réponds pas comme si on te parlait, et tu ne leur coupes pas la parole ; tu peux t'y joindre/);
  assert.match(p, /ou RIEN \(ils se parlent entre eux : te taire est mieux, sauf si tu veux vraiment t'y joindre\)/);
  assert.match(b.f.promptLive({ motif: 'nom', qui: 'voix 97', phrase: 'Hakim ?' }, {}, T), /Ta place dans la scène : impliqué, on s'adresse à toi\./);
});

test('une voix de la pièce que la séparation lui donne : un moment de sa scène ; ses outils : scenes_rappeler, pour lui et son agent de mémoire', () => {
  assert.match(SRC, /if \(t && x\.source === 'micro' && typeof entenduPourLaScene === 'function' && !\(typeof estSonEcho === 'function' && estSonEcho\(t\)\)\)/);
  assert.match(SRC, /entenduPourLaScene\(\{ qui: 'une voix autour', texte: t, provenance: 'piece'/);
  const i = SRC.indexOf('const OUTILS_JARVIS = ['), fin = SRC.indexOf(".map(n => 'mcp__anamnese__' + n)", i);
  assert.ok(SRC.slice(i, fin).includes("'scenes_rappeler'"));
  assert.match(SRC, /const MEMOIRE_LECTURE = \['memory_detail', 'memory_recent', 'scenes_rappeler',/);
  assert.match(SRC, /une scène vécue \(avec qui, impliqué ou témoin, hier soir, au live\) → mcp__anamnese__scenes_rappeler/);
});

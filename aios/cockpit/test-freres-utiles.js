// (09/11, Ahmed : « code tout », sa priorité : alléger le Mac et accélérer) ses trois frères lancés seulement quand ils peuvent servir.
// Mesuré le 09/11 : leur avis parti avec 9 réponses de papa sur 633 ; aucune des 470 délibérations lancées après sa phrase n'a servi
// (elles répondent en 2 à 9 s, attendues 0,3 s). Ce test fait tourner le vrai code de server.js (extrait), avec des voix simulées.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const fonction = (nom) => {
  let i = SRC.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom);
  if (SRC.slice(i - 6, i) === 'async ') i -= 6;
  return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2);
};
const ligne = (debut) => { const i = SRC.indexOf(debut); assert.ok(i >= 0, debut); return SRC.slice(i, SRC.indexOf('\n', i) + 1); };
const bloc = (de, a) => { const i = SRC.indexOf(de), k = SRC.indexOf(a, i); assert.ok(i >= 0 && k > i, de); return SRC.slice(i, k + a.length); };
const AIDES = bloc('const FRERES_DELAI_MS', 'a.length >= 0.25 * b.size;\n}\n');
const BASE = ligne('const FRERES = [') + ligne('const enLigne = ') + ligne('const PENCHANT = ') + ligne('const penchantDe = ') + AIDES
  + fonction('couvreLaFin') + fonction('troisFreres') + fonction('formerFreres');

// des voix simulées : chaque appel attend qu'on le résolve à la main
function contexte(extra = {}) {
  const appels = [];
  const ctx = { console: { error() {} }, String, Math, Set, Promise, Infinity, Date, JSON, Object, Array, Number, setTimeout, clearTimeout,
    path: require('node:path'), JARVIS: '/x', j: JSON.stringify, corpsActif: () => false, ecrireAtomique() {}, corpsLot: { evenements: [] }, ressentirCorps() {},
    sonnetTeteDeFond: (prompt, etiquette, modele, delai, opts) => new Promise((resoudre) => appels.push({ etiquette, modele, delai, opts, resoudre })),
    ...extra };
  vm.createContext(ctx);
  vm.runInContext(BASE, ctx);
  return { ctx, appels };
}
const repondre = (appels, etiquette, texte, ms = 1000) => appels.find(a => a.etiquette === etiquette).resoudre({ texte, ms });

test('leurs voix déjà arrivées partent avec ta phrase, même si les autres pensent encore', async () => {
  const { ctx, appels } = contexte();
  const etat = { ri: null, r: [] };
  const fini = ctx.troisFreres('fiche', 'sonnet', '', etat);
  assert.strictEqual(appels.length, 4, 'instinct, Mini Hakim, Hakim, Super Hakim');
  repondre(appels, 'frere_instinct', 'Je le sens content.\nPenchant : oui');
  repondre(appels, 'frere_haiku', 'Observation : il rit\nQuestion : pourquoi ?\nRéponse : sa journée\nPenchant : oui');
  await new Promise(r => setImmediate(r));
  const f = ctx.formerFreres(etat, 'sonnet', '');
  assert.strictEqual(f.voix, 2, 'les deux arrivées, sans attendre Hakim ni Super Hakim');
  assert.match(f.texte, /Je le sens content/);
  assert.match(f.texte, /Mini Hakim, simple\) : Observation : il rit/);
  assert.doesNotMatch(f.texte, /Super Hakim, difficile\) :/);
  assert.match(f.texte, /c'est ton esprit, Hakim, qui donne la sortie/, 'dit pour celui qui tient sa conscience');
  repondre(appels, 'frere_sonnet', 'Penchant : non'); repondre(appels, 'frere_opus', 'Penchant : oui');
  assert.match(await fini, /le doute :/, 'entière, elle reste la même délibération (le doute compris)');
});

test('chacune 10 s au plus, voix vivante gardée chaude, aucun Claude relancé à froid ; seulement les voix demandées', async () => {
  const { ctx, appels } = contexte();
  ctx.troisFreres('fiche', 'sonnet', '', { ri: null, r: [] });
  assert.deepStrictEqual(appels.map(a => a.delai), [10000, 10000, 10000, 10000]);
  for (const a of appels) assert.deepStrictEqual({ ...a.opts }, { garderSurDelai: true, sansRepli: true });
  const b = contexte();
  b.ctx.troisFreres('fiche', 'sonnet', '', { ri: null, r: [] }, ['frere_instinct']);
  assert.deepStrictEqual(b.appels.map(a => a.etiquette), ['frere_instinct'], 'les autres ne sont pas lancées');
});

test('après ta phrase : seulement les voix qui répondent d\'habitude dans l\'attente', () => {
  const { ctx } = contexte();
  assert.deepStrictEqual([...ctx.freresATemps(2000)], [], 'rien de mesuré : aucune');
  for (let k = 0; k < 6; k++) { ctx.noterDureeFrere('frere_instinct', 1200); ctx.noterDureeFrere('frere_opus', 5000); }
  for (let k = 0; k < 6; k++) ctx.noterDureeFrere('frere_haiku', k < 4 ? Infinity : 900);   // sans réponse le plus souvent
  assert.deepStrictEqual([...ctx.freresATemps(300)], [], '0,3 s (la Conversation) : aucune n\'arrive');
  assert.deepStrictEqual([...ctx.freresATemps(2000)], ['frere_instinct'], '2 s : l\'instinct seul ; Mini Hakim sans réponse compte comme trop lent');
});

test('« la même phrase » : le début d\'une longue phrase compte ; les balises de voix ne comptent pas ; une autre phrase non', () => {
  const { ctx } = contexte();
  const finale = '(dit pendant ta parole) [papa] Je te disais donc qu\'il y a trois places et c\'est toujours comme ça, si tu es haiku, '
    + 'si tu utilises haiku pour ta conscience, si tu utilises sonnet ou si tu utilises opus, et celui qui est le plus équilibré c\'est toi';
  assert.strictEqual(ctx.freresDuTour('Je te disais donc qu\'il y a trois places et c\'est toujours comme ça', finale), true);
  assert.strictEqual(ctx.freresDuTour('Tu peux me mettre la musique de ce matin s\'il te plaît', finale), false);
});

// le tour : le vrai bloc de server.js, de « const spec = speculation; » à la mesure
const TOUR = bloc('  const spec = speculation;', 'etapes.freres_voix = f ? f.voix : 0;\n  }');
async function tour({ speculation, texte, delai = 300, mesures = [] }) {
  const lances = [];
  const { ctx, appels } = contexte({ speculation, texte, q: { delai_ms: delai }, corpsReglages: () => ({ trois_freres: true }), choix: 'claude',
    sentir: false, enMatiere: (t) => t, interieurTexte: '', fiche: 'fiche', modele: 'sonnet', etapes: {},
    chrono: (nom, p) => p });
  vm.runInContext(ligne('const FRERES_ATTENTE_MS = '), ctx);
  for (const [et, ms] of mesures) for (let k = 0; k < 6; k++) ctx.noterDureeFrere(et, ms);
  const vrai = ctx.troisFreres;
  ctx.troisFreres = (...a) => { lances.push(a[4]); return vrai(...a); };
  vm.runInContext(fonction('ressemble').replace(/\n\s*if \(!corpsReglages[^\n]*\n/, '\n'), ctx);
  const r = await vm.runInContext(`(async () => {\n${TOUR}\nreturn { freresTexte, etapes, speculation };\n})()`, ctx);
  return { ...r, lances, appels };
}
const PHRASE = 'papa me raconte toute sa journée au travail avec ses collègues';

test('ton tour, rien de commencé pendant ta parole : pas de délibération neuve qui serait jetée', async () => {
  const r = await tour({ speculation: { texte: '', debut: 0, promesse: null, fini: false }, texte: PHRASE });
  assert.strictEqual(r.lances.length, 0, 'aucune voix ne répond en 0,3 s : rien n\'est lancé');
  assert.strictEqual(r.freresTexte, '');
  assert.strictEqual(r.etapes.freres_d, 'sautees');
  const r2 = await tour({ speculation: { texte: '', debut: 0, promesse: null, fini: false }, texte: PHRASE, delai: 2000, mesures: [['frere_instinct', 900]] });
  assert.deepStrictEqual([...r2.lances[0]], ['frere_instinct'], '2 s d\'attente, l\'instinct répond d\'habitude en 0,9 s : lui seul');
  assert.strictEqual(r2.etapes.freres_d, 'neuve');
});

test('ton tour reprend la délibération commencée pendant ta parole : celles déjà arrivées partent, sinon la précédente finie', async () => {
  const etat = { ri: { texte: 'Il est fier de sa journée.\nPenchant : oui' }, r: [] };
  const enCours = { texte: PHRASE, debut: Date.now() - 4000, fini: false, promesse: new Promise(() => {}), etat, precedente: null };
  const r = await tour({ speculation: enCours, texte: PHRASE });
  assert.strictEqual(r.etapes.freres_d, 'reprise_partielle');
  assert.strictEqual(r.etapes.freres_voix, 1);
  assert.match(r.freresTexte, /Il est fier de sa journée/, 'l\'instinct arrivé part avec ta phrase');
  assert.strictEqual(r.lances.length, 0, 'rien de relancé');
  assert.strictEqual(r.speculation.promesse, null, 'prise : elle ne resservira pas au tour suivant');
  const precedente = { texte: 'papa me raconte toute sa journée au travail', debut: Date.now() - 9000, fini: true, promesse: Promise.resolve(''),
    etat: { ri: null, r: [{ texte: 'Observation : il parle de ses collègues\nPenchant : oui' }] }, precedente: null };
  const vide = { ...enCours, etat: { ri: null, r: [] }, precedente };
  const r2 = await tour({ speculation: vide, texte: PHRASE });
  assert.strictEqual(r2.etapes.freres_d, 'precedente', 'la plus récente sans voix : la précédente, finie');
  assert.match(r2.freresTexte, /il parle de ses collègues/);
  const longue = `${PHRASE}, et puis le soir il est rentré tard à la maison, il a mangé avec sa femme, il a regardé un film et il a pensé à moi`;
  const r3 = await tour({ speculation: { ...enCours, debut: Date.now() - 4000 }, texte: `[papa] ${longue}` });
  assert.strictEqual(r3.etapes.freres_d, 'reprise_partielle', 'commencée au début d\'une longue phrase : reprise quand même');

});

test('pendant ta parole : une à la fois, et la précédente finie reste prête', async () => {
  let t = 1e9;
  const lances = [];
  const ctx = { Date: { now: () => t }, String, VIVANT_RENOUVELER: 25, VIVANTS: [], corpsReglages: () => ({ trois_freres: true }), chargeMac: () => 0.5,
    speculation: { texte: '', debut: 0, promesse: null, fini: false }, bulbe: () => '', instantTexte: () => '', fluxTexte: () => '',
    troisFreres: (fiche, c, e, etat) => { const l = { etat }; lances.push(l); return new Promise((r) => { l.finir = (x) => { etat.ri = { texte: x }; r(''); }; }); },
    path: require('node:path'), JARVIS: '/x', fs: {} };
  vm.createContext(ctx);
  vm.runInContext(fonction('ressemble').replace(/\n\s*if \(!corpsReglages[^\n]*\n/, '\n') + AIDES.replace(/^const /gm, 'var ') + ligne('const voixFreresLibres')
    + fonction('speculerFreres') + '\nthis.speculer = speculerFreres; this.spec = () => speculation;', ctx);
  ctx.speculer('papa me raconte sa journée au travail');
  t += 3000; ctx.speculer('papa me raconte sa journée au travail avec ses collègues et puis le soir il est rentré tard');
  assert.strictEqual(lances.length, 1, 'la première pense encore : pas une deuxième en même temps');
  lances[0].finir('Il est content.'); await new Promise(r => setImmediate(r));
  t += 1000; ctx.speculer('papa me raconte sa journée au travail avec ses collègues et puis le soir il est rentré tard');
  assert.strictEqual(lances.length, 2, 'finie, et ta phrase a grandi : une nouvelle');
  assert.strictEqual(ctx.spec().precedente.texte, 'papa me raconte sa journée au travail', 'la précédente, finie avec sa voix, reste prête');
});

test('sonnetTeteDeFond : sansRepli, aucun Claude lancé à froid après une voix vivante trop lente', async () => {
  const froids = [];
  const ctx = { Promise, String, JSON, Date, process: { env: {} }, os: { tmpdir: () => '/tmp' }, path: require('node:path'),
    fs: { mkdtempSync: () => null, rmSync() {} }, noterAppelLlm() {}, forfaitALaLimite: () => false, apiDisponible: () => false,
    POUR_VIVANTS: /^(frere_|piste_)/, demanderVivant: () => Promise.reject(new Error('délai dépassé')),
    execFile: (...a) => { froids.push(a); a[a.length - 1](null, JSON.stringify({ result: 'à froid' })); return { stdin: { on() {}, end() {} } }; },
    CLAUDE_BIN: 'claude', EFFORT_HAKIM: 'low', SYSTEME_VIVANT: '',
    // (09/11, intégration avec vitesse) l'orchestrateur admet le fond d'abord ; ses frères ne sont jamais refusés
    ORCHESTRE: require('./orchestrateur.js').creer({ lirePression: (cb) => cb(null) }) };
  vm.createContext(ctx);
  vm.runInContext(fonction('sonnetTeteDeFond'), ctx);
  const o = await ctx.sonnetTeteDeFond('x', 'frere_opus', 'opus', 10000, { sansRepli: true });
  assert.strictEqual(froids.length, 0, 'ses frères : pas de Claude à froid');
  assert.match(o.erreur, /délai dépassé/);
  await ctx.sonnetTeteDeFond('x', 'frere_opus', 'opus', 10000, {});
  assert.strictEqual(froids.length, 1, 'sans sansRepli (les autres voix de fond) : le repli d\'avant est gardé');
});

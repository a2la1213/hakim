// (10/11, ~18:30, Ahmed : « Quand Hakim veut me parler, il écrit juste un message, mais il doit pouvoir me solliciter à haute voix dès qu'il
// veut me parler » ; 18:33 : « et s'il est en conversation sur la montre, il peut aussi me parler depuis la montre ») mesuré ce 10/11 : 4 de
// ses 5 sollicitations livrées à la page Parler en Conversation parties au ribosome et tues comme des pensées (« Sa vraie réponse seulement »)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const S = require('./solliciter.js');

const SERVEUR = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const tranche = (src, debut, fin) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); const k = src.indexOf(fin, i); assert.ok(k >= 0, fin); return src.slice(i, src.indexOf('\n}\n', k) + 3); };
const attendre = (ms) => new Promise(r => setTimeout(r, ms));
const MIDI = new Date(2026, 10, 10, 14, 0).getTime();

// ---------- la décision (solliciter.js) ----------
test('ses sollicitations pour papa (boucle, question, taraude, faire) ; « parler » répond à quelqu’un d’autre : jamais à voix haute ici', () => {
  for (const r of ['boucle', 'question', 'taraude', 'faire']) assert.equal(S.decider(S.creer(), { raison: r, texte: 'Papa ?', maintenant: MIDI }).ou, 'page', r);
  assert.deepEqual(S.decider(S.creer(), { raison: 'parler', texte: 'Salut tonton', maintenant: MIDI }), { ou: null, pourquoi: 'pas_pour_papa' });
  assert.equal(S.decider(S.creer(), { raison: 'peur', texte: 'Papa ?', maintenant: MIDI }).ou, null);
});

test('le réglage « Il me sollicite à voix haute » éteint : écrite seulement', () => {
  assert.deepEqual(S.decider(S.creer(), { raison: 'taraude', texte: 'Papa, une question ?', reglages: { sollicite_voix: false }, maintenant: MIDI }), { ou: null, pourquoi: 'reglage' });
});

test('la nuit (23 h - 8 h) : seulement si papa vient de lui parler, et jamais si « Ses sons la nuit » est éteint', () => {
  const nuit = new Date(2026, 10, 10, 2, 30).getTime();
  assert.deepEqual(S.decider(S.creer(), { raison: 'taraude', texte: 'Papa ?', maintenant: nuit, heure: 2, papaDernierMs: nuit - 40 * 60e3 }), { ou: null, pourquoi: 'nuit' }, 'il dort');
  assert.equal(S.decider(S.creer(), { raison: 'taraude', texte: 'Papa ?', maintenant: nuit, heure: 2, papaDernierMs: nuit - 3 * 60e3 }).ou, 'page', 'il vient de parler : réveillé');
  assert.deepEqual(S.decider(S.creer(), { raison: 'taraude', texte: 'Papa ?', reglages: { sons_nuit: false }, maintenant: nuit, heure: 23, papaDernierMs: nuit - 60e3 }), { ou: null, pourquoi: 'nuit_sons' });
  assert.equal(S.decider(S.creer(), { raison: 'taraude', texte: 'Papa ?', reglages: { sons_nuit: false }, maintenant: MIDI, heure: 14 }).ou, 'page', 'le jour : sans effet');
});

test('pendant un live : seulement ce qui s’adresse à papa par son nom', () => {
  assert.deepEqual(S.decider(S.creer(), { raison: 'taraude', texte: 'Tu veux mettre quelle musique ?', live: true, maintenant: MIDI }), { ou: null, pourquoi: 'live' });
  assert.equal(S.decider(S.creer(), { raison: 'question', texte: 'Papa, une question en passant : quelle musique ?', live: true, maintenant: MIDI }).ou, 'page');
  assert.equal(S.decider(S.creer(), { raison: 'question', texte: 'Ça te dit, papounet ?', live: true, maintenant: MIDI }).ou, null, '« papa » en entier');
});

test('pas de rafale : au plus une à voix haute toutes les N min (réglable, 3 par défaut, 0 sans attente)', () => {
  const e = S.creer();
  const d = (t, reglages = {}) => S.decider(e, { raison: 'taraude', texte: 'Papa ?', maintenant: t, reglages });
  assert.equal(d(MIDI).ou, 'page');
  S.poser(e, 'a1', 'page', MIDI);
  assert.deepEqual(d(MIDI + 2 * 60e3), { ou: null, pourquoi: 'rafale' });
  assert.equal(d(MIDI + 3 * 60e3).ou, 'page', '3 min après');
  assert.deepEqual(d(MIDI + 6 * 60e3, { sollicite_voix_ecart_min: 10 }), { ou: null, pourquoi: 'rafale' }, 'réglé à 10 min');
  assert.equal(d(MIDI + 1000, { sollicite_voix_ecart_min: 0 }).ou, 'page', '0 : sans attente');
  S.poser(e, 'a2', null, MIDI + 9 * 60e3);
  assert.equal(e.dernierA, MIDI, 'une sollicitation écrite seulement ne compte pas');
});

test('la montre : papa lui a parlé par elle il y a moins de 20 min, et elle est branchée (0.30) ; sinon la page', () => {
  const e = S.creer();
  S.papaParle(e, 'montre', MIDI);
  assert.equal(S.decider(e, { raison: 'taraude', texte: 'Papa ?', maintenant: MIDI + 5 * 60e3, montreBranchee: true }).ou, 'montre');
  assert.equal(S.decider(e, { raison: 'taraude', texte: 'Papa ?', maintenant: MIDI + 5 * 60e3, montreBranchee: false }).ou, 'page', 'montre 0.29 ou fermée');
  assert.equal(S.decider(e, { raison: 'taraude', texte: 'Papa ?', maintenant: MIDI + 21 * 60e3, montreBranchee: true }).ou, 'page', 'plus de 20 min');
  S.papaParle(e, 'tel', MIDI + 6 * 60e3);
  assert.equal(S.decider(e, { raison: 'taraude', texte: 'Papa ?', maintenant: MIDI + 7 * 60e3, montreBranchee: true }).ou, 'page', 'il est passé au téléphone');
  S.papaParle(e, 'ailleurs', MIDI + 8 * 60e3);
  assert.equal(e.papa.ou, 'tel', 'un appareil inconnu ne compte pas');
});

test('une seule page la dit : la première qui la prend ; dirigée vers la montre, aucune ; inconnue ou trop vieille, aucune', () => {
  const e = S.creer();
  S.poser(e, 'p1', 'page', MIDI);
  assert.deepEqual(S.prendre(e, 'p1', 'tel-a', MIDI + 100), { ok: true, ou: 'page' });
  assert.deepEqual(S.prendre(e, 'p1', 'tel-a', MIDI + 200), { ok: true, ou: 'page' }, 'la même page peut redemander');
  assert.deepEqual(S.prendre(e, 'p1', 'mac-b', MIDI + 300), { ok: false, pourquoi: 'deja_prise' });
  S.poser(e, 'm1', 'montre', MIDI);
  assert.deepEqual(S.prendre(e, 'm1', 'tel-a', MIDI + 100), { ok: false, pourquoi: 'montre' });
  assert.deepEqual(S.prendre(e, 'inconnue', 'tel-a', MIDI), { ok: false, pourquoi: 'inconnue' });
  S.poser(e, 'p2', 'page', MIDI);
  assert.deepEqual(S.prendre(e, 'p2', 'tel-a', MIDI + S.GARDE_MS + 1), { ok: false, pourquoi: 'inconnue' }, 'plus de 2 min : oubliée');
  assert.deepEqual(S.prendre(S.creer(), 'x', '', MIDI), { ok: false, pourquoi: 'inconnue' });
});

test('sa consigne : il sait que papa l’entendra, ou qu’il la lira si le réglage est éteint', () => {
  assert.match(S.consigne({}), /papa l'entend de ta voix là où il est .*montre.*première pause/);
  assert.match(S.consigne({ sollicite_voix: false }), /papa le lit/);
});

// ---------- le cockpit (server.js) ----------
function serveur({ reglages = {}, abonnes = [], live = false, papa = null } = {}) {
  const diffuses = [], diag = [], notifs = [], conversation = [];
  const etat = S.creer();
  if (papa) S.papaParle(etat, papa.ou, papa.ts);
  const ctx = {
    Date, String, Number, JSON, Math, Array, Set, Object, console: { error() {} },
    crypto: require('node:crypto'), j: JSON.stringify, abonnesPensees: new Set(abonnes),
    diffuser: (_, ev, d) => diffuses.push({ ev, d: JSON.parse(d) }),
    gestesDeHakim() {}, microDe: () => null, interieurParLui() {}, triMorceauxDe: () => null, reglerMorceaux() {}, vibrationsDeLuiMeme() {},
    sansBaliseAffect: (t) => t, retirerExterne: () => [], NON_REPONSE_SERVEUR: /^\s*no response requested\.?\s*$/i,
    journaliser() {}, deposerEchange() {}, ajouterAConversation: (m) => conversation.push(m), nonVus: {}, finDePhrase: (t) => t, sauverNonVus() {},
    silencieuxJusqua: 0, notifier: (t, tag) => notifs.push(tag),
    corpsReglages: () => ({ sollicite_voix: true, sollicite_voix_ecart_min: 3, sons_nuit: true, ...reglages }), liveEnCours: () => live,
    Solliciter: S, solliciterEtat: etat, dernierMessageAhmedMs: () => Date.now() - 60e3,
    fs: { appendFileSync: (_, l) => diag.push(JSON.parse(l)) }, JARVIS_VOIX_DIAGNOSTIC: 'voix-diagnostic.jsonl',
  };
  vm.createContext(ctx);
  vm.runInContext(tranche(SERVEUR, 'function livrerAutonome(', 'function solliciterAVoixHaute(') + 'this.livrer = livrerAutonome;', ctx);
  return { livrer: (texte, options) => ctx.livrer({ source: 'abonnement', session: 's' }, texte, [], [], null, [], options), diffuses, diag, notifs, conversation, etat };
}

test('cockpit : sa sollicitation écrite part aux pages avec où la dire (voix_haute « page »), notée au diagnostic, et la notification part', () => {
  const s = serveur({ abonnes: [{ appareil: 'tel' }] });
  s.livrer('Papa, une question : ça va ?', { id: 'auto-1', sollicite: 'taraude' });
  const sp = s.diffuses.find(x => x.ev === 'spontane');
  assert.equal(sp.d.sollicite, true);
  assert.equal(sp.d.voix_haute, 'page');
  assert.equal(s.conversation[0].voix_haute, 'page', 'aussi dans la conversation commune');
  assert.ok(!s.diffuses.some(x => x.ev === 'voix_vers'), 'pas vers la montre');
  assert.deepEqual(s.diag.map(x => [x.e, x.ou, x.raison]), [['sollicitation_voix', 'page', 'taraude']]);
  assert.deepEqual(s.notifs, ['resultat']);
  assert.deepEqual(S.prendre(s.etat, 'auto-1', 'tel-a'), { ok: true, ou: 'page' }, 'une page peut la prendre');
});

test('cockpit : papa parle par la montre (0.30 branchée) : sa voix part au poignet (voix_vers, sollicite), aucune page ne la dit', () => {
  const s = serveur({ abonnes: [{ appareil: 'montre', sollicite: true }, { appareil: 'tel' }], papa: { ou: 'montre', ts: Date.now() - 2 * 60e3 } });
  s.livrer('Papa, tu tiens le coup ?', { id: 'auto-2', sollicite: 'question' });
  const vv = s.diffuses.find(x => x.ev === 'voix_vers');
  assert.deepEqual([vv.d.cible, vv.d.quoi, vv.d.sollicite, vv.d.texte], ['montre', 'voix', true, 'Papa, tu tiens le coup ?']);
  assert.equal(s.diffuses.find(x => x.ev === 'spontane').d.voix_haute, 'montre');
  assert.deepEqual(S.prendre(s.etat, 'auto-2', 'tel-a'), { ok: false, pourquoi: 'montre' });
  const ancienne = serveur({ abonnes: [{ appareil: 'montre' }], papa: { ou: 'montre', ts: Date.now() - 60e3 } });
  ancienne.livrer('Papa, tu tiens le coup ?', { id: 'auto-3', sollicite: 'question' });
  assert.ok(!ancienne.diffuses.some(x => x.ev === 'voix_vers'), 'une montre 0.29 (sans &sollicite=1) : rien au poignet');
  assert.equal(ancienne.diffuses.find(x => x.ev === 'spontane').d.voix_haute, 'page');
});

test('cockpit : réglage éteint, ou un message de lui-même qui n’est pas une sollicitation : rien à voix haute de plus', () => {
  const s = serveur({ reglages: { sollicite_voix: false } });
  s.livrer('Papa, une question ?', { id: 'auto-4', sollicite: 'taraude' });
  const m = s.diffuses.find(x => x.ev === 'spontane').d;
  assert.equal(m.voix_haute, undefined);
  assert.equal(m.voix_pourquoi, 'reglage');
  const r = serveur();
  r.livrer('L’agent a fini : 3 fichiers.', { id: 'auto-5' });
  const n = r.diffuses.find(x => x.ev === 'spontane').d;
  assert.equal(n.sollicite, undefined);
  assert.equal(r.diag.length, 0);
});

test('cockpit branché : un tour de sollicitation n’est pas re-trié par son subconscient, sa consigne est dans son réveil, la montre s’annonce, la route existe', () => {
  const tour = tranche(SERVEUR, 'function tourAutonome(c)', '  const finir = (issue) => {');
  assert.match(tour, /const sollicite = c\.reveilInterieur && Solliciter\.sollicitePapa\(c\.reveilInterieur\.raison\)[^\n]*\n\s*noterIssueInterieur\(c, texte, outils, issue\)/, 'pris avant que l’issue efface le réveil');
  assert.match(tour, /else if \(parle && !sollicite && aTrierParSonSubconscient\(/);
  assert.match(tour, /\{ id: idMessage, \.\.\.\(sollicite \? \{ sollicite \} : \{\}\) \}/);
  assert.match(tranche(SERVEUR, 'function reveillerPourInterieur(', 'const texte = `[Horloge'), /typeof Solliciter !== 'undefined' && Solliciter\.sollicitePapa\(d\.raison\) \? Solliciter\.consigne\(corpsReglages\(\)\) : ''/);
  assert.ok(/if \(!res\.temoin && new URL\(req\.url, 'http:\/\/x'\)\.searchParams\.get\('sollicite'\) === '1'\) res\.sollicite = true;/.test(SERVEUR), 'la montre 0.30 s’annonce');
  assert.ok(/p === '\/api\/jarvis\/sollicitation\/dire' && req\.method === 'POST'\) \{\n\s*if \(!jetonValide\(req\)\)[\s\S]{0,300}Solliciter\.prendre\(solliciterEtat, q\.id, q\.qui\)/.test(SERVEUR), 'la route, gardée par le jeton');
  assert.ok(/Solliciter\.papaParle\(solliciterEtat, q\.appareil && q\.appareil\.montre === true \? 'montre' : distantReq \? 'tel' : 'mac'\)/.test(SERVEUR));
});

test('cockpit : ses deux réglages (allumé, 3 min par défaut) et la page Réglages', () => {
  const ctx = { CORPS_REGLAGES: 'x', CORPS_INTERVALLES: [60, 120], Number, Math, lireJson: () => ({}) };
  vm.createContext(ctx);
  vm.runInContext(tranche(SERVEUR, 'function corpsReglages() {', 'function corpsReglages() {') + 'this.f = corpsReglages;', ctx);
  assert.equal(ctx.f().sollicite_voix, true);
  assert.equal(ctx.f().sollicite_voix_ecart_min, 3);
  ctx.lireJson = () => ({ sollicite_voix: false, sollicite_voix_ecart_min: 99 });
  assert.equal(ctx.f().sollicite_voix, false);
  assert.equal(ctx.f().sollicite_voix_ecart_min, 60);
  assert.ok(/if \(typeof q\.sollicite_voix === 'boolean'\) r\.sollicite_voix = q\.sollicite_voix;/.test(SERVEUR));
  const reglages = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
  assert.match(reglages, /\['sollicite_voix', '📣 Il me sollicite à voix haute', '[^']+', 'oui'\]/);
  assert.match(reglages, /\['sollicite_voix_ecart_min', '[^']+', '[^']+', 'curseur', \[0, 60, 1,/);
});

// ---------- la page Parler ----------
function page({ conversation = true, visible = 'visible', prise = true, reglagesCorps = { voix_reponse_seule: true, epissage: true } } = {}) {
  const dit = [], ribosome = [], journal = [], requetes = [];
  const ctx = {
    Date, String, Number, JSON, Math, Array, Set, Object, setTimeout, clearTimeout, Promise,
    etat: { messages: [], conversation: conversation ? { capteur: { enParole: false, estMuet: false } } : null, reglages: {}, finVoixA: 0 },
    reglagesCorps, document: { visibilityState: visible }, window: { HakimApp: {} },
    lecteur: { actif: false, enPause: false, dire: (t) => dit.push(t), finFlux() {} },
    jarvisPeutParler: () => true, sortirLesCoupees() {}, humeur() {}, journalVoix: (e, d) => journal.push({ e, ...d }),
    versRibosome: (t) => ribosome.push(t), sauverADire() {}, aDire: [], parlaitA: 0, nosSilences: new Set(), debutDuSilence: () => 0,
    reponseCachee: () => false, accuserReception() {}, sauver() {}, rendre() {}, widgetApp() {}, notifierApp() {}, direMotDirect() {},
    $: () => ({}), jeton: () => 'j', appareilIci: () => 'tel', NON_REPONSE: /^\s*no response requested\.?\s*$/i,
    fetch: (url, o) => { requetes.push({ url, corps: JSON.parse(o.body) }); return Promise.resolve({ ok: true, json: async () => (prise ? { ok: true, ou: 'page' } : { ok: false, pourquoi: 'deja_prise' }) }); },
  };
  ctx.voixEpissee = () => !!ctx.etat.conversation && ctx.reglagesCorps.epissage !== false;
  ctx.reponseSeule = () => ctx.reglagesCorps.voix_reponse_seule !== false;
  vm.createContext(ctx);
  const qui = PAGE.indexOf('const QUI_PAGE') >= 0 ? tranche(PAGE, 'const QUI_PAGE', 'function prendreSollicitation(') : '';
  vm.runInContext(tranche(PAGE, 'function surSpontane(m) {', 'function surSpontane(m) {') + qui + tranche(PAGE, 'function direSpontanes() {', 'function direSpontanes() {')
    + 'this.surSpontane = surSpontane; this.direSpontanes = direSpontanes;', ctx);
  return { ctx, dit, ribosome, journal, requetes };
}
const sollicitation = (voix_haute = 'page') => ({ id: 'auto-9', qui: 'j', spontane: 'resultat', texte: 'Papa, j’ai senti des secousses tout à l’heure. Et toi, ça va ?', ts: Date.now(), sollicite: true, voix_haute });

test('TÉMOIN : en Conversation, « Sa vraie réponse seulement » allumé, l’épissage allumé : sa sollicitation est DITE (avant : partie au ribosome, tue)', async () => {
  const p = page();
  p.ctx.surSpontane(sollicitation());
  await attendre(20);
  assert.deepEqual(p.ribosome, [], 'jamais confiée au ribosome');
  assert.deepEqual(p.dit, ['Papa, j’ai senti des secousses tout à l’heure. Et toi, ça va ?']);
  assert.equal(p.requetes[0].url, '/api/jarvis/sollicitation/dire');
  assert.equal(p.requetes[0].corps.id, 'auto-9');
  assert.ok(p.journal.some(x => x.e === 'sollicitation_dite' && x.conversation === true));
  assert.equal(p.ctx.etat.messages[0].sollicite, true, 'écrite aussi, étiquetée « il veut te parler »');
});

test('page : jamais sur la parole de papa — elle attend sa pause, puis la dit', async () => {
  const p = page();
  p.ctx.etat.conversation.capteur.enParole = true;
  p.ctx.surSpontane(sollicitation());
  await attendre(20);
  assert.deepEqual(p.dit, [], 'papa parle');
  p.ctx.etat.conversation.capteur.enParole = false;
  p.ctx.parlaitA = Date.now() - 2000;
  p.ctx.direSpontanes();
  assert.equal(p.dit.length, 1, 'sa pause (1,5 s) : dite');
});

test('page : ouverte devant papa hors Conversation, elle la prend 1,5 s plus tard et la dit ; cachée hors Conversation, rien (la notification sonne)', async () => {
  const p = page({ conversation: false });
  p.ctx.surSpontane(sollicitation());
  await attendre(100);
  assert.equal(p.requetes.length, 0, 'une page en Conversation passe d’abord');
  await attendre(1600);
  assert.equal(p.requetes.length, 1);
  assert.equal(p.dit.length, 1);
  const cachee = page({ conversation: false, visible: 'hidden' });
  cachee.ctx.surSpontane(sollicitation());
  await attendre(1700);
  assert.equal(cachee.requetes.length, 0);
  assert.ok(cachee.journal.some(x => x.e === 'sollicitation_ecrite' && x.pourquoi === 'page_cachee'));
});

test('page : déjà prise ailleurs, dirigée vers la montre, ou gardée par le cockpit (nuit, rafale…) : écrite seulement', async () => {
  const p = page({ prise: false });
  p.ctx.surSpontane(sollicitation());
  await attendre(20);
  assert.deepEqual(p.dit, []);
  const m = page();
  m.ctx.surSpontane(sollicitation('montre'));
  await attendre(20);
  assert.equal(m.requetes.length, 0);
  assert.ok(m.journal.some(x => x.e === 'sollicitation_ecrite' && x.pourquoi === 'montre'));
  const n = page();
  n.ctx.surSpontane({ ...sollicitation(), voix_haute: undefined, voix_pourquoi: 'nuit' });
  await attendre(20);
  assert.deepEqual([n.requetes.length, n.dit.length], [0, 0]);
  assert.ok(n.journal.some(x => x.e === 'sollicitation_ecrite' && x.pourquoi === 'nuit'));
});

test('page : un résultat de lui-même qui n’est pas une sollicitation garde son chemin d’avant (le ribosome en Conversation)', async () => {
  const p = page();
  p.ctx.surSpontane({ id: 'auto-10', qui: 'j', spontane: 'resultat', texte: 'L’agent a fini.', ts: Date.now() });
  await attendre(20);
  assert.deepEqual(p.ribosome, ['L’agent a fini.']);
  assert.equal(p.requetes.length, 0);
});

test('page : sa sollicitation attend 90 s au plus (un résultat, 45 s en Conversation)', () => {
  const p = page();
  p.ctx.aDire.push({ id: 'a', texte: 'Papa ?', recu: Date.now() - 60000, sollicite: true });
  p.ctx.direSpontanes();
  assert.equal(p.dit.length, 1, '60 s : encore dite');
  p.ctx.aDire.push({ id: 'b', texte: 'Papa ?', recu: Date.now() - 91000, sollicite: true });
  p.ctx.direSpontanes();
  assert.equal(p.dit.length, 1, '91 s : plus le présent');
  assert.ok(p.journal.some(x => x.e === 'a_dire_perime' && x.sollicite === true));
});

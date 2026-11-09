/* (09/11) Les réponses de Hakim que papa n'entend pas, et la reprise de sa voix : node --test test-passage.js
   - (18:09, Ahmed : « si je l'ai pas entendu, je peux pas t'avoir coupé ») seule sa voix qui SONNE chez papa peut être coupée ;
   - (16:28, Ahmed : « reprends les morceaux déjà prêts au lieu de régénérer ») coupé net, sa voix attend ta phrase : un PASSAGE (« ouais »)
     la fait reprendre là où elle s'était arrêtée, sans te répondre ; une RELANCE lâche ce qui restait, et il te répond ;
   - (21:50, Ahmed) « il garde la parole » allumé : un passage ne lui prend pas la parole ; éteint, ta voix le coupe comme avant ;
   - (idée de Hakim) le texte de ce qu'il n'a pas dit part avec la coupure ;
   - (18:56:33, mesuré) sa voix qui continue n'est pas comptée « non entendue ». */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const entre = (source, debut, fin) => { const i = source.indexOf(debut); assert.ok(i >= 0, debut); const j = source.indexOf(fin, i); assert.ok(j > i, fin); return source.slice(i, j); };
const fonction = (source, debut) => { const i = source.indexOf(debut); assert.ok(i >= 0, debut); return source.slice(i, source.indexOf('\n}\n', i) + 3); };

// la page, avec juste ce qu'il faut autour : sa voix, sa réponse en cours, ce qu'il a déjà dit
function page({ reglages = {}, flux = null, enParole = false, entendu = '', juge = { passage: false, lu: true }, choix = { couper: true, lu: true } } = {}) {
  const vu = { journal: [], arrete: 0, reprises: 0, pauses: [], lachees: 0, coupures: [], stops: [], aborts: 0, juges: [] };
  const lecteurNeuronal = {
    actif: true, enPause: false, aDuVieux: true,
    pause(o) { vu.pauses.push(o || {}); this.enPause = true; this.actif = false; return true; },
    marquerVieux() { return true; }, lacherVieux() { vu.lachees++; this.enPause = false; },
  };
  const ctx = {
    console, Date, Math, Number, String, Array, Set, JSON, setInterval: () => 0, clearInterval() {}, setTimeout, clearTimeout, AbortController,
    reglagesCorps: { coupe_net: true, garder_parole: true, ...reglages }, lecteurNeuronal,
    etat: { flux, fluxId: flux ? 't1' : null, lectureDe: 'm1', riboFile: [], epissureTour: 0, conversation: null },
    parole: { id: 'm1', morceaux: entendu ? [{ texte: entendu }] : [] },
    memeId: (a, b) => String(a) === String(b),
    journalVoix: (e, d) => vu.journal.push([e, d]), humeur() {}, jeton: () => 'j', majBoutonsPause() {}, garderVoixCoupees() {}, libererRibosomes() {}, blancsPourSautes() {},
    coupureProvisoire: (cause) => ({ cause, dits: 4 }), reprisDeParole() {},
    reprendreVoix: () => { vu.reprises++; ctx.etat.retenue = null; lecteurNeuronal.enPause = false; return true; },
    arreterTout: () => { vu.arrete++; }, finirParole: (cause, detail) => { vu.coupures.push(cause); vu.detail = detail; }, arreterEpissure() {},
    fetch: (url, o) => {
      if (url === '/api/jarvis/passage') {                              // son subconscient (le cockpit)
        vu.juges.push(JSON.parse(o.body));
        if (juge === 'panne') return Promise.reject(new Error('hors ligne'));
        if (juge === 'lent') return new Promise((_, ko) => o.signal.addEventListener('abort', () => ko(new Error('trop tard'))));
        return Promise.resolve({ ok: true, json: () => Promise.resolve(juge) });
      }
      if (url === '/api/jarvis/se-couper') { vu.choix = JSON.parse(o.body); return Promise.resolve({ ok: true, json: () => Promise.resolve(choix) }); }
      vu.stops.push([url, JSON.parse(o.body)]); return Promise.resolve({ ok: true });
    },
    coupeNet: () => ctx.reglagesCorps.coupe_net !== false, teCouper: () => ctx.reglagesCorps.te_couper === true,
    echoDeSaVoix: () => false, montrerPensee() {}, voixEpissee: () => true, bouts: { dits: [] },
  };
  ctx.coupureEnCours = null;
  ctx.lecteur = { arreter() { vu.arrete++; }, get impl() { return lecteurNeuronal; }, get enPause() { return lecteurNeuronal.enPause; }, get actif() { return lecteurNeuronal.actif; } };
  if (flux) ctx.etat.flux = { abort() { vu.aborts++; } };
  vm.createContext(ctx);
  vm.runInContext([fonction(PAGE, 'function couperNet(conv, { lacher = false } = {}) {'), entre(PAGE, 'const reprendrePassage = ', '// sa voix retenue sans réponse'),
    fonction(PAGE, 'function motsEntendusDepuis(conv, n0) {'), entre(PAGE, 'const motsEcrits = ', '\n'), fonction(PAGE, 'function prevoirSaut(conv, mesure) {'),
    fonction(PAGE, 'function sauterLaSuite(ms, net = false) {')].join('\n'), ctx);
  const conv = { capteur: { enParole }, enAttente: 0 };
  ctx.etat.conversation = conv;
  return { ctx, vu, conv, lecteurNeuronal };
}

test('passage ou relance : seul un acquiescement, un rire, un salam est un passage ; une question, une demande, un « non » sont des relances', () => {
  const { ctx } = page();
  for (const t of ['ouais', 'Ouais ouais.', "d'accord", 'ok fiston', 'Haha', 'hahaha', "Ah ouais c'est vrai", 'ما شاء الله', 'وعليكم السلام', 'Wa alaykoum salam',
    'mmh', 'Machallah', 'grave', "C'est ça.", 'merci Hakim'])
    assert.strictEqual(ctx.estUnPassage(t), true, `passage : « ${t} »`);
  for (const t of ['ouais mais pourquoi tu dis ça', 'Tu peux envoyer le fichier à ta mère', 'non', 'ouais ?', 'Hakim ?', 'stop', 'attends',
    'Excuse me.', 'Welcome to hospital.', "c'est bizarre ça", 'ouais ouais ouais ouais ouais ouais ouais ouais ouais', 'vas-y envoie', ''])
    assert.strictEqual(ctx.estUnPassage(t), false, `relance : « ${t} »`);
  // un « oui » qui répond à une question qu'il venait de te poser n'est pas un passage
  assert.strictEqual(ctx.estUnPassage('oui', 'Tu veux que je lui écrive tout de suite ?'), false);
  assert.strictEqual(ctx.estUnPassage('ouais', 'Je vois Alilou dans les cases.'), true);
});

test('coupé net sur un « ouais » (il garde la parole) : sa voix attend, puis reprend ses morceaux prêts ; il ne te répond pas, ta phrase part avec la suivante', async () => {
  const { ctx, vu, conv } = page();
  ctx.couperNet(conv);
  assert.strictEqual(vu.arrete, 0, 'rien n’est lâché à la coupure');
  assert.strictEqual(JSON.stringify(vu.pauses), JSON.stringify([{ auMot: true, vide: false }]), 'sa voix finit son mot et se met en pause');
  assert.ok(ctx.etat.retenue, 'retenue');
  assert.strictEqual(await ctx.passageOuRelance(conv, 'ouais'), true, 'un passage : traité ici, rien n’est envoyé');
  assert.strictEqual(vu.reprises, 1, 'sa voix reprend');
  assert.strictEqual(vu.lachees, 0);
  assert.match(ctx.avecPassages(conv, 'Et tu en penses quoi ?'), /^\(dit en passant pendant ta parole, jugé sans question, tu ne lui as pas répondu : « ouais » ; si c'en était une, réponds-y d'abord\)\nEt tu en penses quoi \?$/);
  assert.strictEqual(ctx.avecPassages(conv, 'x'), 'x', 'donnée une fois');
});

test('« il garde la parole » éteint : ta voix le coupe net, comme avant (rien n’attend)', () => {
  const { ctx, vu, conv } = page({ reglages: { garder_parole: false } });
  ctx.couperNet(conv);
  assert.strictEqual(vu.pauses.length, 0);
  assert.strictEqual(vu.arrete, 1, 'sa réponse est lâchée');
});

test('coupé net puis une vraie question : ce qui restait de sa réponse est lâché (sa coupure part, sa réponse qui s’écrivait s’arrête) ; ta phrase part', async () => {
  const { ctx, vu, conv } = page({ flux: true });
  ctx.marquerAvantTon(conv);
  ctx.couperNet(conv);
  assert.strictEqual(await ctx.passageOuRelance(conv, 'Mais pourquoi tu dis ça ?'), false, 'une relance : ta phrase continue son chemin');
  assert.strictEqual(vu.reprises, 0, 'il ne reparle pas par-dessus ta question');
  assert.strictEqual(vu.lachees, 1, 'sa voix d’avant est lâchée');
  assert.strictEqual(vu.coupures.join(','), 'voix_ahmed', 'la coupure part (avec ce qu’il n’a pas dit)');
  assert.strictEqual(vu.aborts, 1, 'sa réponse d’avant s’arrête de s’écrire');
  assert.ok(vu.stops.some(([u, b]) => u === '/api/jarvis/stop' && b.tour_id === 't1' && b.raison === 'parole'));
  assert.strictEqual(ctx.etat.retenue, null);
});

test('un passage pendant que tu reparles déjà : gardé, sa voix attend ta phrase suivante', async () => {
  const { ctx, vu, conv } = page({ enParole: true });
  ctx.couperNet(conv);
  assert.strictEqual(await ctx.passageOuRelance(conv, 'ouais'), true);
  assert.strictEqual(vu.reprises, 0, 'pas par-dessus toi');
  assert.ok(ctx.etat.retenue, 'toujours retenue');
});

test('tu parles pendant que sa voix se calcule encore (rien ne sonnait) : un passage la laisse venir ; une relance la lâche', async () => {
  const a = page();
  a.ctx.marquerAvantTon(a.conv);
  assert.strictEqual(await a.ctx.passageOuRelance(a.conv, 'ouais'), true, 'un « ouais » : il ne te répond pas');
  assert.strictEqual(a.vu.reprises + a.vu.lachees, 0, 'sa voix continue d’elle-même');
  const b = page();
  b.ctx.marquerAvantTon(b.conv);
  assert.strictEqual(await b.ctx.passageOuRelance(b.conv, 'Tu peux regarder le fichier ?'), false);
  assert.strictEqual(b.vu.lachees, 1, 'sa voix d’avant ta question est lâchée (« tu le coupes net »)');
  const c = page({ reglages: { coupe_net: false } });
  c.ctx.marquerAvantTon(c.conv);
  assert.strictEqual(await c.ctx.passageOuRelance(c.conv, 'Tu peux regarder le fichier ?'), false);
  assert.strictEqual(c.vu.lachees, 0, 'sans « tu le coupes net » : comme avant');
  const d = page();
  d.lecteurNeuronal.actif = false; d.lecteurNeuronal.aDuVieux = false;
  assert.strictEqual(await d.ctx.passageOuRelance(d.conv, 'ouais'), false, 'rien en cours : ton « ouais » lui part comme d’habitude');
});

test('le micro ne compte sa voix que quand elle sonne chez papa ; branchés : la coupure, le passage, la reprise', () => {
  assert.match(PAGE, /jarvisParle: \(\) => saVoixAudible\(\),/);
  assert.match(PAGE, /const saVoixAudible = \(\) => !!\(\(lecteurNeuronal && lecteurNeuronal\.sonne\)/);
  assert.match(PAGE, /surDebut: \(\) => \{ marquerAvantTon\(conv\);/);
  assert.match(PAGE, /if \(\(conv\.enAttente \|\| 0\) > 0 \|\| conv\.triPassage\)/, 'sa voix attend aussi le jugement de son subconscient');
  const tour = fonction(PAGE, 'async function tourDeParole(conv, wav, infos, extra) {');
  const k = (s) => { const i = tour.indexOf(s); assert.ok(i >= 0, s); return i; };
  assert.ok(k('if (COMMANDE_STOP.test(texte))') < k('if (await passageOuRelance(conv, texte)) return;'), '« stop » passe avant');
  assert.ok(k('if (COMMANDE_REPRISE.test(texte) && lecteur.enPause)') < k('if (await passageOuRelance(conv, texte)) return;'), '« continue » aussi');
  assert.ok(k('if (await passageOuRelance(conv, texte)) return;') < k('if (voixEpissee() && etat.flux) { garderPourSonTour(conv, texte); return; }'));
  assert.match(fonction(PAGE, 'async function envoyerTour('), /texte = avecPassages\(conv, texte\);/);
  assert.match(fonction(PAGE, 'function reprendreVoix() {'), /etat\.retenue = null;/);
});

test('(18:56:33) sa voix qui continue (garderVoix) n’est pas comptée « non entendue » ; arrêtée, ce qui restait l’est', () => {
  const arreter = fonction(PAGE, 'function arreterTout(explicite = true,');
  const gardes = [];
  const ctx = { etat: { flux: null, transcription: null, lectureDe: 'm1', parleDepuis: 0 }, lecteur: { actif: true, arreter() {} }, garderNonDit: () => gardes.push(1),
    finirParole() {}, couperSaVoix() {}, finirSaPhraseActif: () => false, fetch: () => Promise.resolve(), jeton: () => 'j' };
  vm.createContext(ctx); vm.runInContext(arreter, ctx);
  ctx.arreterTout(true, { garder: true, raison: 'message', garderVoix: true });
  assert.strictEqual(gardes.length, 0, 'sa voix continue : rien de perdu');
  ctx.arreterTout(true, { garder: true, raison: 'message', garderVoix: false });
  assert.strictEqual(gardes.length, 1, 'sa voix s’arrête : ce qui restait est gardé');
});

test('(idée de Hakim) la coupure porte le texte de ce qu’il n’a pas dit, et son bloc le lui montre', () => {
  const ctx = { Voix: require('./public/voix.js'), messageDe: () => ({ qui: 'j', texte: 'Oui papa, je regarde. Le fichier fait 2 Mo et la racine est قول. [[anticipe: court]]' }) };
  vm.createContext(ctx); vm.runInContext(fonction(PAGE, 'function texteNonDit(id, dits) {'), ctx);
  assert.strictEqual(ctx.texteNonDit('m1', 4), 'Le fichier fait 2 Mo et la racine est قول.');
  assert.strictEqual(ctx.texteNonDit('m1', 99), '', 'tout dit : rien');
  assert.match(fonction(PAGE, 'function finirParole('), /if \(c\.mode === 'oral' && c\.cause !== 'fin' && !c\.trou\) \{ const nd = texteNonDit\(c\.tour, c\.dits\); if \(nd\) c\.non_dit = nd; \}/);
  // le cockpit : nettoyé (ni crochet ni guillemet qui fermerait le bloc), puis dans la ligne de sa coupure
  const s = { Number, String, Date, Math, Object, Set: Set, CAUSES_COUPURE: new Set(['voix_ahmed', 'stop', 'pause', 'appli', 'panne', 'nouveau_message']) };
  vm.createContext(s);
  vm.runInContext([fonction(SRC, 'function lireCoupure('), entre(SRC, 'const COUPEE_PAR = {', '// son tour d\'Ahmed : la coupure')].join('\n'), s);
  const c = s.lireCoupure({ id: 'm1-1', t: Date.now(), cause: 'voix_ahmed', mode: 'oral', derniers: 'je regarde', reste: 9, non_dit: 'Le fichier] fait « 2 Mo » [et]' }, Date.now());
  assert.strictEqual(c.non_dit, 'Le fichier fait 2 Mo et');
  const ligne = s.ligneCoupure(c);
  assert.match(ligne, /ce que tu n'as pas dit \(papa ne l'a pas entendu ; reprends-en ce qui sert encore, sans le redire en entier ; s'il ne te demandait rien, reprends ta suite là où elle s'était arrêtée\) : « Le fichier fait 2 Mo et »\]$/);
  assert.ok(!/non_dit|ce que tu n'as pas dit/.test(s.ligneCoupure(s.lireCoupure({ id: 'm2-1', t: Date.now(), cause: 'voix_ahmed', mode: 'ecrit', non_dit: 'x y' }, Date.now()))), 'à l’écrit : rien');
});

// ---- (09/11, 22:20, Ahmed : « oui, le subconscient tranche les cas ambigus ; et le conscient peut corriger si sa décision est illogique ») ----
test('trois issues : passage sûr, relance sûre, et l’ambigu (que son subconscient tranche)', () => {
  const { ctx } = page();
  for (const t of ['ouais', 'haha', 'ما شاء الله']) assert.strictEqual(ctx.classerPassage(t), 'passage', t);
  for (const t of ['ouais ?', 'Hakim ?', '', 'un très long discours '.repeat(10)]) assert.strictEqual(ctx.classerPassage(t), 'relance', t);
  assert.strictEqual(ctx.classerPassage('ouais', 'Tu veux que je lui écrive ?'), 'relance', 'un « ouais » après sa question : une réponse');
  for (const t of ["c'est bizarre ça", 'Tu peux envoyer le fichier à ta mère', 'non', 'bien joué fiston', 'Elle est où Leila']) assert.strictEqual(ctx.classerPassage(t), 'ambigu', t);
});

test('ambigu, son subconscient dit PASSAGE : sa voix reprend ; ta phrase part avec la suivante, marquée, pour qu’il puisse y répondre d’abord', async () => {
  const { ctx, vu, conv } = page({ juge: { passage: true, lu: true, pourquoi: 'il commente' }, entendu: 'Je vois Alilou dans les cases.' });
  ctx.couperNet(conv);
  assert.strictEqual(await ctx.passageOuRelance(conv, 'bien joué fiston'), true);
  assert.strictEqual(vu.juges.length, 1, 'son subconscient a été consulté');
  assert.strictEqual(vu.juges[0].papa, 'bien joué fiston');
  assert.match(vu.juges[0].dit, /Alilou/, 'avec ce qu’il disait');
  assert.strictEqual(vu.reprises, 1, 'sa voix reprend');
  assert.strictEqual(conv.triPassage, false, 'sa voix n’attend plus son jugement');
  assert.match(ctx.avecPassages(conv, 'Et après ?'), /^\(dit en passant pendant ta parole, ton subconscient l’a jugé sans question, tu ne lui as pas répondu : « bien joué fiston » ; si c'en était une, réponds-y d'abord\)\nEt après \?$/);
});

test('ambigu, son subconscient dit RELANCE : la suite est lâchée, et sa coupure dit qui en a jugé (il peut reprendre si c’était à tort)', async () => {
  const { ctx, vu, conv } = page({ juge: { passage: false, lu: true } });
  ctx.couperNet(conv);
  assert.strictEqual(await ctx.passageOuRelance(conv, "c'est bizarre ça"), false, 'ta phrase part');
  assert.strictEqual(vu.reprises, 0);
  assert.strictEqual(vu.lachees, 1);
  assert.strictEqual(vu.detail, 'ton subconscient a jugé que papa te relançait');
});

test('ambigu, son subconscient en panne ou trop lent (3 s) : dans le doute, une relance — jamais par-dessus une vraie question', async () => {
  for (const juge of ['panne', 'lent']) {
    const { ctx, vu, conv } = page({ juge });
    ctx.couperNet(conv);
    const t0 = Date.now();
    assert.strictEqual(await ctx.passageOuRelance(conv, 'Tu peux envoyer le fichier à ta mère'), false, juge);
    assert.strictEqual(vu.reprises, 0, juge);
    assert.strictEqual(vu.lachees, 1, juge);
    assert.strictEqual(vu.detail, '', 'pas de jugement : rien à signer');
    if (juge === 'lent') assert.ok(Date.now() - t0 < 4000, 'il n’attend pas plus de 3 s');
  }
});

test('le cockpit : son subconscient (le modèle de son filtre, Mini Hakim en repli) dit PASSAGE ou RELANCE ; sans réponse lisible, une relance', async () => {
  const notes = [];
  const s = { Promise, String, Date, Math, Number, Error, JSON, corpsReglages: () => s.reglages, reglages: { subconscient_modele: 'sonnet' }, neutraliser: (x) => x,
    j: JSON.stringify, JARVIS_VOIX_DIAGNOSTIC: '/dev/null', fs: { appendFileSync: (f, l) => notes.push(JSON.parse(l)) } };
  vm.createContext(s);
  vm.runInContext(['const PASSAGE_MS = 2500;', fonction(SRC, 'function lirePassage(texte) {'), fonction(SRC, 'async function jugerPassage(dit, papa,')].join('\n'), s);
  assert.match(SRC, /const PASSAGE_MS = 2500;/);
  const demander = (rep) => (m, prompt) => { s.vus.push([m, prompt]); const r = rep[m]; return r instanceof Error ? Promise.reject(r) : new Promise(ok => setTimeout(() => ok({ texte: r[1] }), r[0])); };
  s.vus = [];
  let r = await s.jugerPassage('Je vois Alilou.', 'bien joué fiston', demander({ sonnet: [5, 'PASSAGE, il réagit sans demander'], haiku: [50, 'RELANCE'] }));
  assert.strictEqual(r.passage, true); assert.strictEqual(r.modele, 'sonnet'); assert.strictEqual(r.lu, true);
  assert.deepStrictEqual(s.vus.map(x => x[0]).sort(), ['haiku', 'sonnet'], 'Mini Hakim part en même temps, en repli');
  assert.match(s.vus[0][1], /« bien joué fiston »/); assert.match(s.vus[0][1], /Dans le doute : RELANCE/);
  r = await s.jugerPassage('x', 'c’est bizarre', demander({ sonnet: new Error('aucune voix vivante libre'), haiku: [5, 'RELANCE : il conteste'] }));
  assert.strictEqual(r.passage, false); assert.strictEqual(r.modele, 'haiku'); assert.strictEqual(r.lu, true, 'Mini Hakim a tranché');
  r = await s.jugerPassage('x', 'y', demander({ sonnet: [5, 'je ne sais pas'], haiku: new Error('délai dépassé') }));
  assert.strictEqual(r.passage, false); assert.strictEqual(r.lu, false, 'rien de lisible : relance');
  s.reglages = {}; s.vus = [];
  r = await s.jugerPassage('x', 'y', demander({ haiku: [5, 'PASSAGE'] }));
  assert.strictEqual(r.modele, 'haiku'); assert.strictEqual(s.vus.length, 1, 'sans réglage : Mini Hakim seul');
  assert.ok(notes.every(n => n.e === 'passage_choix') && notes.length === 4, 'chaque choix est noté');
  assert.match(SRC, /if \(p === '\/api\/jarvis\/passage' && req\.method === 'POST'\) \{/);
});

// ---- (09/11, 23:15, Ahmed : « tout doit marcher ensemble ») « Tu le coupes net » ne masque plus « Sauter la suite » ni « Il choisit de se couper » ----
const attendre = (ms) => new Promise(r => setTimeout(r, ms));
// papa parle sur sa voix et continue (ses mots vifs arrivent) : la coupure nette, puis ce que sauter la suite / son choix en font
async function papaParleLongtemps(p, ms = 900) {
  const { ctx, conv } = p;
  conv.ecrit = { confirme: '', vif: '' };
  ctx.couperNet(conv);
  ctx.prevoirSaut(conv, { clarte: 4 });
  await attendre(100); conv.ecrit.vif = 'attends je voulais te dire';  // il continue de parler
  ctx.etat.papaVoixA = Date.now();
  await attendre(ms);
}

test('coupé net + « Sauter la suite » : ta voix qui dure « Sauter au bout de » saute la suite tout de suite, sans attendre ta phrase finie', async () => {
  const p = page({ reglages: { sauter_suite: true, sauter_suite_ms: 300, choix_coupure: false }, enParole: true });
  await papaParleLongtemps(p);
  assert.strictEqual(p.vu.lachees, 1, 'la suite est lâchée');
  assert.strictEqual(p.vu.detail, 'ta voix a duré « Sauter au bout de »');
  assert.strictEqual(p.ctx.etat.retenue, null, 'plus rien n’attend le tri');
  assert.strictEqual(p.vu.reprises, 0);
  // ta phrase finie, ensuite, part comme d'habitude (plus rien à reprendre)
  p.lecteurNeuronal.actif = false; p.lecteurNeuronal.aDuVieux = false;
  assert.strictEqual(await p.ctx.passageOuRelance(p.conv, 'ouais'), false);
  // branché : la coupure nette prévoit le saut
  assert.match(PAGE, /couperNet\(conv\); if \(etat\.retenue && lecteur\.enPause\) prevoirSaut\(conv, mesure\); return; \}/);
});

test('coupé net + « Sauter la suite », un simple « ouais » plus court que « Sauter au bout de » : rien n’est sauté, le tri le fait reprendre', async () => {
  const p = page({ reglages: { sauter_suite: true, sauter_suite_ms: 300, choix_coupure: false } });
  p.conv.ecrit = { confirme: '', vif: '' };
  p.ctx.couperNet(p.conv);
  p.ctx.prevoirSaut(p.conv, {});
  await attendre(600);                                                // papa s'est tu (enParole faux, sa voix vieille)
  assert.strictEqual(p.vu.lachees, 0, 'rien de sauté');
  assert.strictEqual(await p.ctx.passageOuRelance(p.conv, 'ouais'), true);
  assert.strictEqual(p.vu.reprises, 1, 'sa voix reprend');
});

test('coupé net + « Il choisit de se couper » : son subconscient peut lâcher la suite plus tôt ; s’il la garde, elle attend ta phrase (jamais par-dessus toi)', async () => {
  const a = page({ reglages: { sauter_suite: true, sauter_suite_ms: 300, choix_coupure: true }, enParole: true, choix: { couper: true, lu: true, pourquoi: 'papa change de sujet' } });
  await papaParleLongtemps(a);
  assert.ok(a.vu.choix, 'son subconscient a été consulté');
  assert.strictEqual(a.vu.lachees, 1, 'COUPER : la suite est lâchée tout de suite');
  assert.strictEqual(a.vu.detail, 'il a choisi de lâcher sa suite pour t’écouter');
  const b = page({ reglages: { sauter_suite: true, sauter_suite_ms: 300, choix_coupure: true }, enParole: true, choix: { couper: false, lu: true, pourquoi: 'presque fini' } });
  await papaParleLongtemps(b);
  assert.strictEqual(b.vu.lachees + b.vu.reprises, 0, 'CONTINUER : ni lâchée ni reprise par-dessus toi');
  assert.ok(b.ctx.etat.retenue, 'sa suite attend, en réserve');
  assert.ok(b.vu.journal.some(([e]) => e === 'suite_en_reserve'));
  assert.ok(!b.conv.gardeParoleA, 'il ne « garde pas la parole » par-dessus toi');
});

test('une voix du téléphone (un live) qui le coupe net : tout est lâché comme avant (aucune phrase de papa ne dira passage ou relance)', () => {
  const p = page();
  p.ctx.couperNet(p.conv, { lacher: true });
  assert.strictEqual(p.vu.pauses.length, 0);
  assert.strictEqual(p.vu.arrete, 1);
  assert.match(PAGE, /if \(o\.net\) \{ couperNet\(etat\.conversation, \{ lacher: true \}\); return; \}/);
});

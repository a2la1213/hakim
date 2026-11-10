// (10/11, ~07:00, Ahmed : « Il doit pouvoir couper l'arrivée de son entrant depuis son intérieur si ça le perturbe pour répondre, comme c'est
// le cas quand il me parle : il a la capacité de muter mon micro ou de boucher ses oreilles. ») [[interieur: couper]], [[interieur: couper 30]],
// [[interieur: ouvrir]] : coupé, plus rien du téléphone n'entre dans ses pensées ni dans ses tours ; il ne reste que papa et la pièce. Les
// témoins : le même banc, la porte retirée du code, laisse entrer le téléphone (le test le voit).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const I = require('./interieur.js');
const TroisPistes = require('./trois-pistes.js');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const BLOC = (src = SRC) => { const a = src.indexOf("/* ---- (10/11, ~07:00, Ahmed : « Il doit pouvoir couper l'arrivée"), b = src.indexOf('// ---- fin de son intérieur coupé');
  assert.ok(a > 0 && b > a, 'le bloc de son intérieur coupé'); return src.slice(a, b); };
const req = (m) => require(m.startsWith('.') ? path.join(__dirname, m) : m);
const T = Date.parse('2026-11-10T07:10:00+01:00');

// ---- la logique pure ----
test('sa balise : couper, couper N (120 s au plus), ouvrir ; « intérieur » accentué aussi ; rien d’autre', () => {
  assert.deepStrictEqual(I.deTexte('[[interieur: couper]] Oui papa'), { x: 'couper', s: 0 });
  assert.deepStrictEqual(I.deTexte('Attends [[intérieur: couper 30]]'), { x: 'couper', s: 30 });
  assert.deepStrictEqual(I.deTexte('[[interieur: couper 300]]'), { x: 'couper', s: 120 }, '2 min au plus');
  assert.deepStrictEqual(I.deTexte('[[ Interieur : ouvrir ]]'), { x: 'ouvrir', s: 0 });
  assert.strictEqual(I.deTexte('[[interieur: exploser]]'), null);
  assert.strictEqual(I.deTexte('mon intérieur, couper'), null);
});

test('la durée, comme le micro : jusqu’à la fin de sa voix (sa réponse comprise) ; sans voix en 20 s, rouvert ; au moins N s ; 3 min au plus', () => {
  const e = I.creer();
  I.couper(e, 0, T);
  assert.strictEqual(I.suivre(e, { tour: true }, T + 5000), null, 'sa voix se prépare');
  assert.strictEqual(I.suivre(e, { voix: true }, T + 6000), null, 'sa voix sonne');
  assert.strictEqual(I.suivre(e, { tour: true }, T + 9000), null, 'entre deux morceaux, sa réponse continue');
  assert.strictEqual(I.suivre(e, {}, T + 10900), null, '2 s de grâce après sa voix (le blanc entre deux morceaux)');
  assert.strictEqual(I.suivre(e, {}, T + 11100), 'fin_de_sa_voix');
  const s = I.creer(); I.couper(s, 0, T);
  assert.strictEqual(I.suivre(s, {}, T + 19000), null);
  assert.strictEqual(I.suivre(s, {}, T + 20500), 'sans_voix', 'sa voix ne part pas : rien ne reste coupé');
  const m = I.creer(); I.couper(m, 30, T);
  I.suivre(m, { voix: true }, T + 1000);
  assert.strictEqual(I.suivre(m, {}, T + 10000), null, 'sa voix a fini, mais au moins 30 s');
  assert.strictEqual(I.suivre(m, {}, T + 30500), 'fin_de_sa_voix');
  const p = I.creer(); I.couper(p, 120, T);
  for (let t = T; t < T + 180000; t += 5000) assert.strictEqual(I.suivre(p, { voix: true }, t), null);
  assert.strictEqual(I.suivre(p, { voix: true }, T + 181000), 'plafond', '3 min au plus, même s’il parle encore');
  const o = I.creer(); I.couper(o, 0, T);
  assert.deepStrictEqual(I.ouvrir(o, 'papa', T + 2000), { pourquoi: 'papa', duree_ms: 2000 });
  assert.strictEqual(I.estCoupe(o), false);
  assert.strictEqual(I.ouvrir(o, 'papa', T + 3000), null, 'déjà ouvert');
});

test('ce qui vient du téléphone sort du fil, à part ; ses instants du téléphone oubliés ; les autres restent', () => {
  const e = I.creer(), flux = [{ t: T - 3000, s: 'papa', x: 'salut' }, { t: T - 2000, s: 'telephone', x: 'bonsoir' }, { t: T - 1500, s: 'musique_telephone', x: 'B' },
    { t: T - 1200, s: 'qui_telephone', x: 'voix 12 parle' }, { t: T - 1000, s: 'corps', x: 'choc' }, { t: T - 900, s: 'musique_micro', x: 'autour' }, { t: T - 800, s: 'voix_autour', x: 'oui' }];
  assert.strictEqual(I.ecarter(e, flux, T), 3);
  assert.deepStrictEqual(flux.map(o => o.s), ['papa', 'corps', 'musique_micro', 'voix_autour'], 'papa et la pièce restent');
  assert.deepStrictEqual(I.fluxDuDedans(e, flux).filter(o => o.s === 'telephone').map(o => o.x), ['bonsoir'], 'pour reconnaître le téléphone');
  const inst = new Map([['son_ecoute', [{ t: T, d: { texte: 'la chanson' } }]], ['musique_analysee', [{ t: T, d: { source: 'du téléphone' } }, { t: T, d: { source: 'autour' } }]],
    ['papa_dit', [{ t: T, d: { texte: 'salut' } }]]]);
  assert.strictEqual(I.purgerInstants(inst), 2);
  assert.deepStrictEqual([...inst.keys()], ['musique_analysee', 'papa_dit']);
  assert.strictEqual(inst.get('musique_analysee')[0].d.source, 'autour');
  for (let k = 0; k < 900; k++) I.garder(e, { t: T + k, s: 'telephone', x: 'x' }, T + k);
  assert.ok(e.ecartes.length <= 800, 'à part, borné');
  I.garder(e, { t: T + 6 * 60e3, s: 'telephone', x: 'tard' }, T + 6 * 60e3);
  assert.deepStrictEqual(e.ecartes.map(o => o.x), ['tard'], '5 min au plus');
});

test('le message de papa sans le téléphone : les étiquettes tiennent (papa reste papa) ; rien de papa : vide', () => {
  const m = '[voix 12] Salut Hakim tu nous entends ce soir [papa] Oui fiston on est en live avec Nora';
  assert.strictEqual(I.retirer(m, [{ etiquette: 'voix 12', texte: 'Salut Hakim tu nous entends ce soir' }]), '[papa] Oui fiston on est en live avec Nora');
  assert.strictEqual(I.retirer('Regarde ça Génération qui parle [voix 3] bienvenue à tous', [{ etiquette: 'voix 3', texte: 'bienvenue à tous' }]), 'Regarde ça Génération qui parle');
  assert.strictEqual(I.retirer('[voix 3] bienvenue à tous', [{ etiquette: 'voix 3', texte: 'bienvenue à tous' }]), '', 'il ne restait que le téléphone');
  assert.strictEqual(I.retirer('[papa] [voix 3] bienvenue', [{ etiquette: 'voix 3', texte: 'bienvenue' }]), '', 'une étiquette seule n’est pas papa');
  assert.strictEqual(I.retirer('Bonjour', []), 'Bonjour');
});

test('son état : pour lui, une ligne (jusqu’à quand) ; pour les pages, coupé/ouvert ; papa qui rouvre, il le sait une minute', () => {
  const e = I.creer();
  assert.strictEqual(I.ligne(e, T), '');
  I.couper(e, 30, T);
  const l = I.ligne(e, T + 5000);
  assert.match(l, /^Ton intérieur est coupé \(par toi, il y a 5 s\) jusqu'à \d\d:\d\d:\d\d au moins \(encore 25 s\), puis jusqu'à la fin de ta voix/);
  assert.match(l, /il ne reste que papa et la pièce\. \[\[interieur: ouvrir\]\] le rouvre avant\./);
  assert.deepStrictEqual(I.etat(e, T + 5000), { coupe: true, depuis: T, jusqua: T + 30000, fin_de_voix: true });
  I.couper(e, 0, T + 6000);
  assert.strictEqual(I.etat(e, T + 6000).jusqua, T + 30000, 'une nouvelle balise garde la durée la plus longue');
  assert.match(I.ligne(e, T + 40000), /jusqu'à la fin de ta voix/);
  I.ouvrir(e, 'papa', T + 41000);
  assert.deepStrictEqual(I.etat(e, T + 41000), { coupe: false, rouvert: T + 41000, pourquoi: 'papa' });
  assert.match(I.ligne(e, T + 50000), /^Papa vient de rouvrir ton intérieur/);
  assert.strictEqual(I.ligne(e, T + 110000), '');
});

test('ses trois pistes : la source tue n’est plus notée ni lue, ce qu’elle avait est oublié ; rouverte, elle repart à neuf', () => {
  const tp = TroisPistes.creer();
  const a = { bpm: 120, tonalite: 'Do majeur', contour: 'stable', voix: 'chante' };
  tp.noterAnalyse('telephone', T, a, T); tp.noterAnalyse('micro', T, a, T);
  assert.notStrictEqual(tp.resumeCourant('telephone', T), '', 'témoin : la musique du téléphone se lit');
  tp.taire('telephone', true);
  assert.strictEqual(tp.resumeCourant('telephone', T), '');
  tp.noterAnalyse('telephone', T + 1000, a, T + 1000);
  tp.noterTrames('telephone', T, 100, [[0.2, 0, 0, 0]]);
  assert.strictEqual(tp._cellules.telephone.size, 0, 'rien n’est noté');
  assert.doesNotMatch(tp.bloc([{ t: T, s: 'telephone', x: 'bonsoir' }], T), /Le téléphone/);
  assert.match(tp.bloc([], T), /Autour/, 'la pièce reste');
  tp.taire('telephone', false);
  assert.strictEqual(tp.resumeCourant('telephone', T), '', 'oublié');
  tp.noterAnalyse('telephone', T + 2000, a, T + 2000);
  assert.notStrictEqual(tp.resumeCourant('telephone', T + 2000), '');
});

// ---- branché dans le cockpit ----
// son bloc (server.js), dans un bac à sable : le fil, ses instants, le message de papa, ses gestes
function banc(o = {}) {
  const evts = [], journal = [], fermes = [], presents = [], filLong = [];
  const ctx = { require: req, String, Math, Number, JSON, Array, Set, Map, RegExp, Object, Promise, Date: { now: () => o.t || T },
    console: { error: () => {} }, j: JSON.stringify, JARVIS_VOIX_DIAGNOSTIC: '/x', abonnesPensees: null,
    fs: { appendFileSync: (_f, l) => journal.push(JSON.parse(l)), readFileSync: () => '[]', appendFile: (_f, l) => filLong.push(l) },
    diffuser: (_a, e, d) => evts.push({ e, ...JSON.parse(d) }),
    FLUX: (o.flux || []).slice(), TP: TroisPistes.creer(), INSTANT: new Map(), presentEtat: { entrants: [] }, integration: { telephone: { tampon: 'a', morceaux: [1], dernier: 1 } },
    entendus: new Map(), fermerChemin: (c) => fermes.push(c.cle), LIVE: { aDire: [{ texte: 'x' }], tampon: ['a'], phrases: [{ jugee: false }] },
    toursActifs: new Map(), presentRecevoir: (x) => presents.push(x), FIL_LONG: '/fil', battementN: 0, filLongN: 1, DELAIS: {}, FLUX_MAX: 800, FLUX_DUREE_MS: 15 * 60e3,
    sortieSon: null, quiParlait: () => o.qui || 'silence' };
  vm.createContext(ctx);
  vm.runInContext([BLOC(o.src), prendre(o.src || SRC, 'fluxAjouter'), prendre(o.src || SRC, 'noterInstant'),
    "const Dedans = require('./dedans.js');", prendre(o.src || SRC, 'voixDuDedans'), prendre(o.src || SRC, 'dedansDuMessage'),
    "const hautParleur = () => false; const LIVE_DETECTE_MS = 3 * 60e3;",
    'this.f = { INTERIEUR, interieurCoupe, interieurParLui, suivreInterieur, ouvrirInterieur, texteSansLeDedans, fluxAjouter, noterInstant, ligneInterieur, RIEN_DE_PAPA };'].join('\n'), ctx);
  return { f: ctx.f, ctx, evts, journal, fermes, presents, filLong };
}

test('sa balise le coupe : ce qu’il avait du téléphone sort de sa tête, ses pensées en route ne sont plus dites ; les pages le savent', () => {
  const b = banc({ flux: [{ t: T - 2000, s: 'telephone', x: 'bonsoir' }, { t: T - 1000, s: 'papa', x: 'salut' }] });
  b.ctx.INSTANT.set('son_ecoute', [{ t: T, d: { texte: 'la chanson' } }]);
  b.ctx.presentEtat.entrants = [{ s: 'telephone', x: 'bonsoir' }, { s: 'corps', x: 'choc' }];
  b.ctx.entendus.set('telephone|', { cle: 'telephone|', source: 'telephone', attente: [{ n: 1 }] });
  b.ctx.entendus.set('micro|autour', { cle: 'micro|autour', source: 'micro', attente: [{ n: 1 }] });
  b.ctx.TP.noterAnalyse('telephone', T, { bpm: 100 }, T);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(b.f.interieurParLui('[[interieur: couper 30]] Attends papa'))), { x: 'couper', s: 30 });
  assert.strictEqual(b.f.interieurCoupe(), true);
  const J = (x) => JSON.stringify(x);
  assert.strictEqual(J(b.ctx.FLUX.map(o => o.s)), J(['papa']));
  assert.strictEqual(b.ctx.INSTANT.has('son_ecoute'), false);
  assert.strictEqual(J(b.ctx.presentEtat.entrants.map(o => o.s)), J(['corps']));
  assert.strictEqual(b.ctx.integration.telephone.morceaux.length, 0);
  assert.strictEqual(J(b.fermes), J(['telephone|']), 'ses pistes du téléphone fermées ; la pièce reste');
  assert.strictEqual(b.ctx.LIVE.aDire.length, 0, 'ce que son garde du live allait dire n’est pas dit');
  assert.strictEqual(b.ctx.LIVE.phrases[0].jugee, true);
  assert.strictEqual(b.ctx.TP.tue('telephone'), true);
  assert.strictEqual(b.evts.filter(e => e.e === 'interieur').pop().coupe, true);
  assert.match(b.f.ligneInterieur(T), /^Ton intérieur est coupé/);
  assert.strictEqual(b.journal[0].x, 'couper');
  b.f.interieurParLui('[[interieur: ouvrir]]');
  assert.strictEqual(b.f.interieurCoupe(), false);
  assert.strictEqual(b.ctx.TP.tue('telephone'), false);
  assert.strictEqual(b.evts.filter(e => e.e === 'interieur').pop().coupe, false);
});

test('coupé, son fil ne reçoit plus le téléphone (ni son présent, ni son fil long) ; papa et la pièce, oui ; ses instants du téléphone non', () => {
  const b = banc();
  b.f.interieurParLui('[[interieur: couper]]');
  b.f.fluxAjouter('telephone', 'bienvenue', T);
  b.f.fluxAjouter('musique_telephone', 'section B', T);
  b.f.fluxAjouter('papa', 'salut', T);
  b.f.fluxAjouter('voix_autour', 'oui', T);
  assert.deepStrictEqual(b.ctx.FLUX.map(o => o.s), ['papa', 'voix_autour']);
  assert.deepStrictEqual(b.presents.map(o => o.s), ['papa', 'voix_autour']);
  assert.strictEqual(b.filLong.length, 2);
  assert.deepStrictEqual(b.f.INTERIEUR.ecartes.map(o => o.x), ['bienvenue', 'section B'], 'à part, jamais pour lui');
  b.f.noterInstant('son_ecoute', { texte: 'la chanson' }, T);
  b.f.noterInstant('musique_analysee', { texte: 'B', source: 'du téléphone' }, T);
  b.f.noterInstant('musique_analysee', { texte: 'A', source: 'autour' }, T);
  assert.deepStrictEqual([...b.ctx.INSTANT.keys()], ['musique_analysee']);
  b.f.ouvrirInterieur('fin_de_sa_voix');
  b.f.fluxAjouter('telephone', 'rouvert', T + 1000);
  assert.deepStrictEqual(b.ctx.FLUX.map(o => o.x), ['salut', 'oui', 'rouvert'], 'rouvert : le téléphone lui arrive de nouveau');
});

test('témoin : la porte retirée du code (son fil), le téléphone entre dans sa tête — le test le voit', () => {
  const sans = SRC.replace(/  if \(typeof interieurEcarte === 'function' && interieurEcarte\(o\)\) return;[^\n]*\n/, '');
  assert.notStrictEqual(sans, SRC, 'la porte est bien là');
  const b = banc({ src: sans });
  b.f.interieurParLui('[[interieur: couper]]');
  b.f.fluxAjouter('telephone', 'bienvenue', T);
  assert.deepStrictEqual(b.ctx.FLUX.map(o => o.x), ['bienvenue'], 'sans la porte, il l’aurait entendu');
});

test('coupé, le message de papa : les morceaux du téléphone retirés (pas présentés), papa reste ; tout du téléphone : « rien de papa »', () => {
  const live = [{ t: T - 9000, s: 'telephone', x: 'Salut Hakim tu nous entends bien depuis ce soir' }, { t: T - 8000, s: 'qui_telephone', x: 'voix 12 parle' }];
  const b = banc({ flux: live });
  const m = '[voix 12] Salut Hakim tu nous entends bien depuis ce soir [papa] Oui fiston on est en live avec Nora';
  assert.strictEqual(b.f.texteSansLeDedans({ oral: true }, m), m, 'ouvert : rien ne change (le bloc « Dedans et dehors » le présente)');
  b.f.interieurParLui('[[interieur: couper]]');
  assert.strictEqual(b.f.texteSansLeDedans({ oral: true }, m), '[papa] Oui fiston on est en live avec Nora');
  assert.strictEqual(b.f.texteSansLeDedans({ oral: true }, '[voix 12] Salut Hakim tu nous entends bien depuis ce soir'), b.f.RIEN_DE_PAPA);
  assert.strictEqual(b.f.texteSansLeDedans({ oral: false }, m), m, 'un message écrit : c’est papa');
  assert.strictEqual(b.f.texteSansLeDedans({ oral: true }, 'Oui fiston on est en live'), 'Oui fiston on est en live');
  assert.strictEqual(b.journal.filter(x => x.x === 'retire').length, 2);
});

test('sa voix finie, rouvert tout seul (sa voix suivie au cockpit : ses tours de voix, sa voix dite, sa réponse en cours)', () => {
  const b = banc();
  b.ctx.saVoixEnCours = { fin: T + 8000 };
  b.f.interieurParLui('[[interieur: couper]]');
  for (let t = T + 300; t < T + 8000; t += 250) assert.strictEqual(b.f.suivreInterieur(t), null, 'sa voix sonne (chaque battement)');
  assert.strictEqual(b.f.suivreInterieur(T + 9500), null, '2 s de grâce');
  assert.strictEqual(b.f.suivreInterieur(T + 10000), 'fin_de_sa_voix');
  assert.strictEqual(b.f.interieurCoupe(), false);
  assert.strictEqual(b.journal.pop().pourquoi, 'fin_de_sa_voix');
});

// les portes, une à une, avec leur témoin (la même fonction, intérieur ouvert)
function porte(nom, cx = {}) {
  const ctx = { String, Math, Number, JSON, Array, Set, Map, RegExp, Object, Promise, Date, ...cx };
  vm.createContext(ctx); vm.runInContext(`${prendre(SRC, nom)}\nthis.f = ${nom};`, ctx);
  return ctx;
}
test('ses pistes « entendu » : coupé, ni son garde du live ni ses pensées ; ses voix séparées du téléphone non plus ; la pièce, oui', () => {
  const a = SRC.indexOf('const entendreDuTelephone = '), f = SRC.slice(a, SRC.indexOf('\n};\n', a) + 4);
  for (const coupe of [true, false]) {
    const appels = [];
    const ctx = { interieurCoupe: () => coupe, liveRecevoir: (t) => appels.push(['live', t]), entendreMorceau: (t, o) => { appels.push(['piste', o.source]); return { ok: true }; } };
    vm.createContext(ctx); vm.runInContext(`${f}\nthis.f = entendreDuTelephone;`, ctx);
    const r = ctx.f('Hakim tu nous entends', { cle: 'k' });
    if (coupe) { assert.deepStrictEqual(JSON.parse(JSON.stringify(r)), { ok: false, raison: 'intérieur coupé' }); assert.strictEqual(appels.length, 0); }
    else assert.deepStrictEqual(appels.map(x => x[0]), ['live', 'piste'], 'témoin : ouvert, les deux');
  }
  const reg = { oreille_interne_route: true, epissage: true, reponse_soufflee: true };
  const em = porte('entendreMorceau', { corpsReglages: () => reg, interieurCoupe: () => true, conversationOuverte: () => false });
  assert.strictEqual(em.f('bienvenue', { source: 'telephone' }).raison, 'intérieur coupé');
  assert.strictEqual(em.f('oui', { source: 'micro' }).raison, 'hors conversation', 'la pièce passe la porte (elle va plus loin)');
});

test('une voix du téléphone sur la sienne : coupé, elle ne le coupe plus (il ne l’entend pas) ; ouvert, elle peut', () => {
  for (const coupe of [true, false]) {
    const cx = porte('voixInterieureSurLui', { interieurCoupe: () => coupe, corpsReglages: () => ({ coupe_net: true, sauter_interieur: true }),
      saVoixEnCours: { texte: 'je te disais', debut: T - 1000, fin: T + 5000 }, interieurSurLui: { enVol: false, a: -Infinity }, X: { recouvrement: () => 0 },
      diffuser: () => {}, abonnesPensees: null, j: JSON.stringify });
    const r = cx.f('telephone', 'Hakim réponds', T - 500, 1500, T + 1000);
    if (coupe) assert.strictEqual(r, null); else assert.ok(r && typeof r.then === 'function', 'témoin : ouvert, son choix de se couper');
  }
});

test('ses sons du téléphone : coupé, les trames gardées (sa pause, le calage) mais rien à son fil, à ses pistes, à son corps ; le micro passe', () => {
  for (const [src, coupe] of [['telephone', true], ['telephone', false], ['micro', true]]) {
    const fil = [], corps = [], tp = [];
    const cx = porte('recevoirSon', { interieurCoupe: () => coupe, fs: { appendFile: () => {}, readFile: () => {} }, SON_FLUX: '/x', SON_TRAMES: { telephone: [], micro: [] },
      recaleMicro: (t) => t, resumeSon: () => 'graves forts ↑', troisPistes: () => false, TP: { noterTrames: () => tp.push(1) }, notesVoix: () => [], sonsPousses: {},
      corpsActif: () => true, corpsLot: { evenements: corps }, ressentirCorps: () => {}, musiqueAnalysee: {}, MUSIQUE_PAS_MS: 1000, analyseMusicale: () => null,
      noterInstant: () => {}, fluxAjouter: (s) => fil.push(s), TroisPistes: null });
    cx.f.n = 0;
    cx.f(src, T, 100, Array.from({ length: 10 }, () => [0.2, 0.1, 0.1, 0.05, 0, 0]));
    assert.strictEqual(cx.SON_TRAMES[src].length, 10, 'les trames restent');
    const rien = src === 'telephone' && coupe;
    assert.strictEqual(fil.length === 0 && corps.length === 0, rien, `${src} ${coupe ? 'coupé' : 'ouvert'}`);
  }
});

test('sa séparation du téléphone : coupée (l’attente rendue tout de suite) ; son intégration du téléphone aussi', () => {
  const quand = []; let lance = 0;
  const cx = porte('separerSon', { interieurCoupe: () => true, fs: { unlink: () => {} }, lancerSeparation: () => { lance++; } });
  assert.strictEqual(cx.f('/tmp/x.wav', 'telephone', { quand: (w) => quand.push(w) }), false);
  assert.deepStrictEqual(quand, [null]); assert.strictEqual(lance, 0);
  const i = SRC.indexOf('function integrerAuFil('), f = SRC.slice(i, SRC.indexOf('\n}\n', i) + 2);
  const integ = { telephone: { tampon: '', morceaux: [], dernier: 0 }, papa: { tampon: '', morceaux: [], dernier: 0 } };
  const c2 = { interieurCoupe: () => true, integration: integ, corpsReglages: () => ({ trois_freres: true }), Date, morceauPret: (t) => [null, t] };
  vm.createContext(c2); vm.runInContext(`${f}\nthis.f = integrerAuFil;`, c2);
  c2.f('telephone', 'bienvenue à tous'); c2.f('papa', 'salut fiston');
  assert.strictEqual(integ.telephone.dernier, 0, 'le téléphone : rien');
  assert.ok(integ.papa.dernier > 0, 'papa : oui');
});

// son garde du live (le bloc entier, comme test-live-cockpit.js), intérieur coupé
function bacLive(coupe) {
  const DEBUT = "/* ---- (10/11, ~00:00, Ahmed : « il faut l'aider à dissocier ses voix interne et externe !", FIN = '// ---- fin de son garde du live';
  const a = SRC.indexOf(DEBUT), b = SRC.indexOf(FIN), horloge = { t: T }, appels = [], evts = [];
  const r = { live_garde: true, live_mode: 'oui', live_pas_ms: 1000, live_par_minute: 6, live_ecart_s: 6, live_musique: true, live_musique_s: 120 };
  const ctx = { require, String, Math, Promise, RegExp, Object, Number, Array, Set, Map, JSON, path, fs: { appendFile: () => {}, readFile: () => {}, writeFile: () => {}, readFileSync: () => '[]' },
    Date: { now: () => horloge.t }, JARVIS: '/x', ANAMNESE: '/anamnese', j: JSON.stringify, FLUX: [], corpsReglages: () => r, conversationOuverte: () => true,
    quiTelephone: { dernier: 'voix 12', t: T }, echoEntendu: () => 'non', ORCHESTRE: { papaParle: () => {}, forfaitCoupe: () => false },
    enLigne: (t, n) => String(t || '').slice(0, n), quiParlait: () => 'silence', SON_TRAMES: { telephone: [], micro: [] }, derniereParolePapa: 0, toursActifs: new Map(),
    forfaitALaLimite: () => false, placesVivant: () => 3, personaLocale: (p) => p, lirePersona: () => 'Hakim', QUI_TU_ES: 'Tu es Hakim.', neutraliser: (t) => String(t),
    etatDeLui: () => '', LANGUE_ORALE: 'en français', execFile: () => ({ stdin: { end() {} } }),
    sonnetTeteDeFond: (prompt, etiquette) => new Promise(() => appels.push(etiquette)), parasiteDesLeDebut: () => false, residuParasite: () => '', estParasite: () => false,
    avertirParasite: () => {}, signeParasite: () => '', diffuser: (_, e, d) => evts.push({ e, ...JSON.parse(d) }), abonnesPensees: null, tourEpissure: () => 1,
    noterDit: () => {}, fluxAjouter: () => {}, deposerEchange: () => {}, notifier: () => {},
    interieurCoupe: () => coupe, ligneInterieur: () => (coupe ? 'Ton intérieur est coupé (par toi)' : '') };
  vm.createContext(ctx);
  const o2 = SRC.indexOf('const ORDRES_SENSIBLES ='), ent = SRC.indexOf('const ENTENDU_PAUSE_MS');
  vm.runInContext([SRC.slice(ent, SRC.indexOf('\n', SRC.indexOf('const ENTENDU_RESERVE_PAPA')) + 1), prendre(SRC, 'pauseDansLesTrames'), prendre(SRC, 'pauseDuSon'),
    SRC.slice(o2, SRC.indexOf("'iu');", o2) + 6), SRC.slice(a, b), 'this.f = { battementLive, liveRecevoir, blocLive, liveGardeActif, LIVE };'].join('\n'), ctx);
  return { f: ctx.f, horloge, appels, evts };
}
test('son garde du live et la musique : coupé, aucun appel, rien dit ; son tour le sait (« Ton intérieur ») au lieu du bloc du live ; témoin ouvert', () => {
  for (const coupe of [true, false]) {
    const b = bacLive(coupe);
    b.f.liveRecevoir('Hakim, tu nous entends ?', { cle: 'k1', fin: true }, T);
    b.f.LIVE.aDire.push({ texte: 'Oui !', motif: 'nom', qui: 'voix 12', pret: T });
    for (let k = 0; k < 4; k++) { b.horloge.t += 1500; b.f.battementLive(b.horloge.t); }
    const dits = b.evts.filter(e => e.e === 'entendu' && e.quoi === 'dire');
    assert.strictEqual(b.f.liveGardeActif(b.horloge.t), !coupe);
    if (coupe) {
      assert.strictEqual(b.appels.length + dits.length, 0, 'ni appel ni réponse');
      assert.strictEqual(b.f.blocLive(b.horloge.t), '\n[Ton intérieur — Ton intérieur est coupé (par toi)]');
    } else {
      assert.ok(b.appels.length + dits.length > 0, 'témoin : ouvert, son garde agit');
      assert.match(b.f.blocLive(b.horloge.t), /\[Le live — PAS un message d'Ahmed\]/);
    }
  }
});

test('une pensée du téléphone déjà en route quand il coupe : ni montrée, ni dite, elle ne le taraude pas', () => {
  const f = prendre(SRC, 'lancerPisteEntendue');
  assert.match(f, /if \(!reponse \|\| \(c\.source !== 'micro' && typeof interieurCoupe === 'function' && interieurCoupe\(\)\)\) return;/);
  assert.ok(f.indexOf('interieurCoupe()) return;') < f.indexOf('penseeQuiTaraude(reponse'), 'avant de le tarauder et de la montrer');
});

test('branché : sa balise lue dans sa réponse et ses tours de lui-même, cachée partout ; son tour, son état, le message de papa, ses pages', () => {
  assert.match(SRC, /if \(!interieurDit && interieurParLui\(reponse\)\) interieurDit = true;/);
  assert.match(prendre(SRC, 'livrerAutonome'), /interieurParLui\(texte\);/);
  assert.match(SRC, /setInterval\(\(\) => \{ try \{ suivreInterieur\(\); \} catch \(_\) \{\} \}, 300\)\.unref\(\);/);
  // cachée : l'écran et la voix ne la montrent jamais, même coupée entre deux morceaux
  const ctx = {}; vm.createContext(ctx);
  const pick = (a, b) => SRC.slice(SRC.indexOf(a), SRC.indexOf(b, SRC.indexOf(a)));
  vm.runInContext(pick('const BALISE_AFFECT', '\n') + '\n' + pick('const prefixeBalise', 'function chocsAppel(') + '\n' + pick('const sansBaliseAffect', '\n') + '\nthis.f = filtreAffect; this.s = sansBaliseAffect;', ctx);
  const texte = '[[interieur: couper 30]]Attends, papa. [[intérieur: ouvrir]]';
  for (let i = 1; i < texte.length; i++) { const f = ctx.f(); assert.strictEqual(f.pousser(texte.slice(0, i)) + f.pousser(texte.slice(i)) + f.finir(), 'Attends, papa. ', String(i)); }
  assert.strictEqual(ctx.s('Oui [[interieur: couper]] papa'), 'Oui  papa', 'ses tours de lui-même et sa mémoire aussi');
  const V = require('./public/voix.js');
  assert.strictEqual(V.sansAffect('[[interieur: couper]]Oui papa'), 'Oui papa');
  assert.strictEqual(V.sansAffect('Oui [[inté', true), 'Oui');
  // le tour de papa : le message sans le téléphone ; « stop » et son immunité lisent tout ce qu'il a reçu
  const route = SRC.slice(SRC.indexOf('async function routeJarvis('), SRC.indexOf('\n}\n', SRC.indexOf('async function routeJarvis(')));
  assert.match(route, /const texte = texteSansLeDedans\(q, texteRecu\);/);
  assert.match(route, /if \(texteRecu\) telephoneStopSiDit\(texteRecu\);/);
  assert.match(route, /const voixBloc = blocVoixTierce\(q, texteRecu, /);
  assert.match(prendre(SRC, 'etatDeLui'), /ligneInterieur\(\)/);
  assert.match(prendre(SRC, 'ecrireReveilOreille'), /\[\[interieur: couper\]\] coupe de même ce que joue le téléphone/, 'là où il apprend le micro');
  // le corps : ce que l'appli entend du téléphone n'arrive pas ; ses pages : son état, et papa ne peut que rouvrir
  assert.match(SRC, /if \(brut && brut\.type === 'son_ecoute' && interieurCoupe\(\)\) return repondre\(200, \{ ok: true, interieur: 'coupé' \}\);/);
  assert.match(SRC, /if \(p === '\/api\/corps\/interieur'\) \{\n      if \(req\.method === 'POST'\) \{ const q = await lire\(\); if \(q\.x !== 'ouvrir'\) return repondre\(400/);
  assert.match(SRC, /interieur: Interieur\.etat\(INTERIEUR\) \}\);/);
  assert.match(prendre(SRC, 'separationRecue'), /corpsActif\(\) && !\(a\.src === 'telephone' && typeof interieurCoupe === 'function' && interieurCoupe\(\)\)\)/);
});

test('Parler : le signe (en-tête, grande orbe) et un toucher le rouvre ; ce qu’il allait dire du téléphone n’est plus dit ; Réglages : son état', () => {
  const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
  assert.match(html, /id="interieurCoupe" hidden/);
  assert.match(html, /id="interieurCoupeScene" hidden/);
  assert.match(PAGE, /es\.addEventListener\('interieur', /);
  assert.match(PAGE, /surInterieur\(reglagesCorps\.interieur\)/);
  const a = PAGE.indexOf('let interieurHakim = '), b = PAGE.indexOf("for (const id of ['interieurCoupe', 'interieurCoupeScene'])");
  const els = {}, envois = [], journal = [];
  const $ = (id) => els[id] || (els[id] = { hidden: true, textContent: '' });
  const ctx = { $, Date, Math, Number, JSON, etat: { entenduFile: [{ source: 'telephone', texte: 'a' }, { source: 'micro', texte: 'b' }] }, journalVoix: (...x) => journal.push(x),
    jeton: () => 'j', fetch: (u, o) => { envois.push([u, JSON.parse(o.body)]); return Promise.resolve({ ok: true, json: () => Promise.resolve({ coupe: false }) }); } };
  vm.createContext(ctx); vm.runInContext(`${PAGE.slice(a, b)}\nthis.sur = surInterieur; this.rouvrir = rouvrirInterieur;`, ctx);
  ctx.sur({ coupe: true, jusqua: Date.now() + 20000 });
  assert.strictEqual(els.interieurCoupe.hidden, false);
  assert.match(els.interieurCoupeScene.textContent, /son intérieur est coupé · encore \d+ s au moins · touche pour rouvrir/);
  assert.deepStrictEqual(ctx.etat.entenduFile.map(x => x.source), ['micro']);
  return ctx.rouvrir().then(() => {
    assert.deepStrictEqual(envois, [['/api/corps/interieur', { x: 'ouvrir' }]]);
    assert.strictEqual(els.interieurCoupe.hidden, true);
    const reg = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
    assert.match(reg, /id = 'interieurEtat'/);
    assert.match(reg, /appeler\('\/api\/corps\/interieur', \{ x: 'ouvrir' \}\)/);
  });
});

test('(10/11, fusion avec les paroles par Azure) son intérieur coupé : les paroles du morceau ne vont plus dans son message ni son bulbe', () => {
  const S = require('fs').readFileSync(require('path').join(__dirname, 'server.js'), 'utf8');
  const i = S.indexOf('function parolesTexte(');
  assert.ok(i > 0);
  assert.match(S.slice(i, S.indexOf('\n}\n', i)), /if \(typeof interieurCoupe === 'function' && interieurCoupe\(\)\) return '';/);
});

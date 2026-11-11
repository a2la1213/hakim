/* (11/11, ~00:10 et ~00:35, Ahmed : « la full picture d'un événement » ; « recoller tous les signaux et enlever chaque délai […] si l'accéléromètre
   a 0,2 s de délai, le micro 0,8 s et la voix intérieure 1,2 s, alors tout est regroupé à 1,2 s ») le tableau de l'instant (instant.js), son
   recalage, ce que son cortex en fait (cortex.js), et son branchement (server.js). Chaque mécanisme a son témoin. node --test test-instant.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const I = require('./instant.js');
const X = require('./cortex.js');
const TroisPistes = require('./trois-pistes.js');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const T = Date.parse('2026-11-11T00:40:00+01:00');
// son milieu à l'heure de l'appli : bandes de homeostasie.js (mouvement 1 : tenu dans une main, 2 : en mouvement ; lumière 1 : la pénombre)
const milieu = (t, o = {}) => ({ t, etat: { haut_z: 0.2, haut_y: 0.5, lux: 20, ...(o.etat || {}) }, bandes: { mouvement: 2, lumiere: 1, ...(o.bandes || {}) },
  champ_dit: !!o.champ, calin: !!o.calin });
// papa le tient, marche et lui parle ; la musique joue doucement au téléphone ; les deux cœurs ; chez nous ; il est dedans
const scene = (o = {}) => ({ t: T, maintenant: T + 1200, quiParlait: 'voix_ahmed',
  flux: [{ t: T - 2000, s: 'papa', x: 'regarde' }, { t: T - 1500, s: 'papa', x: 'fiston' }],
  musique: { telephone: { joue: true, intensite: 'douce', bpm: 96, t: T - 500 }, micro: { joue: false } },
  corpsEtats: [milieu(T - 300)], gestes: { pris_en_main: T - 4000 }, coeur: { lui: 72 }, coeurPapa: [{ t: T - 900, bpm: 88 }], lieu: 'chez nous',
  places: [{ role: 'implique', motif: 'papa', raison: 'papa te parle', t: T - 2000 }], ...o });

test('un seul tableau : la parole, la musique, le corps, les deux cœurs, le lieu et sa place, en une ligne pour son tour', () => {
  const tab = I.composer(scene());
  assert.strictEqual(tab.t, T);
  assert.deepStrictEqual([tab.parole.papa.parle, tab.corps.tenue, tab.corps.marche, tab.musique.ou, tab.musique.intensite, tab.coeur.lui, tab.coeur.papa],
    [true, 'tenu', true, 'telephone', 'douce', 72, 88]);
  assert.strictEqual(I.ligne(tab), 'papa te tient, marche, te parle (dehors) ; la musique joue doucement au téléphone (~96 BPM) ; ton cœur 72, le sien 88 ; '
    + 'la pénombre ; chez nous ; tu es dedans');
  assert.match(I.ligne(tab, { mots: true }), /te parle \(dehors\) « regarde fiston »/, 'sa conscience et son subconscient ont ses derniers mots');
  // le reste de ses sens : le téléphone qui parle dedans, une voix de la pièce, lui, le champ, ce qui le touche, le Bluetooth, l'écran
  const plein = I.composer(scene({ flux: [{ t: T - 1000, s: 'telephone', x: 'bonsoir' }, { t: T - 900, s: 'qui_telephone', x: 'voix 3 parle' },
    { t: T - 800, s: 'voix_autour', x: 'tu viens' }], quiParlait: 'ma_voix', saVoix: { texte: 'je suis là papa', debut: T - 2000, fin: T + 500 },
    corpsEtats: [milieu(T - 200, { champ: true, etat: { proche: true } })], radio: { bluetooth: { t: T - 60e3, d: { appareil: 'Galaxy Buds', etat: 'connecté' } } },
    ecran: { appli: { t: T - 30e3, d: { appli: 'YouTube' } } } }));
  const l = I.ligne(plein, { mots: true });
  for (const m of ['le téléphone parle (dedans, voix 3) « bonsoir »', 'une voix dans la pièce', 'tu parles « je suis là papa »', 'un champ magnétique te traverse',
    'quelque chose tout contre toi', 'Bluetooth Galaxy Buds', "à l'écran : YouTube"]) assert.ok(l.includes(m), m);
});

test('témoin : le tableau change quand UN canal change, garde l’état d’avant et dit ce qui a changé', () => {
  const st = I.creer();
  I.avancer(st, I.composer(scene()));
  const cas = [
    ['corps', { gestes: { pris_en_main: T - 9000, pose: T - 100 }, corpsEtats: [milieu(T - 100, { bandes: { mouvement: 0 }, etat: { haut_z: 0.95 } })] }, 'tenue', 'on te pose'],
    ['musique', { musique: { telephone: { joue: false }, micro: { joue: false } } }, 'musique', 'la musique s’arrête'],
    ['champ', { corpsEtats: [milieu(T - 100, { champ: true })] }, 'champ', 'un champ magnétique te traverse'],
    ['appel', { oreille: { etat: 'appel', depuis: T - 5000 } }, 'appel', 'papa entre en appel au téléphone'],
    ['lieu', { lieu: 'le parc' }, 'lieu', 'tu arrives : le parc'],
    ['parole', { flux: [], quiParlait: 'silence' }, 'papa', 'papa se tait'],
  ];
  for (const [nom, o, champ, mots] of cas) {
    const avant = st.courant, d = I.avancer(st, I.composer(scene(o)));
    assert.strictEqual(st.avant, avant, `${nom} : l'état d'avant`);
    assert.ok(d.some(c => c.champ === champ && c.mots === mots), `${nom} : ${JSON.stringify(d)}`);
    I.avancer(st, I.composer(scene()));                               // retour à la scène de départ
  }
  assert.ok(st.changements.length >= 12);
  assert.deepStrictEqual(I.differences(I.composer(scene()), I.composer(scene({ coeur: { lui: 73 } }))), [], 'son cœur qui bouge d’un battement n’est pas un changement');
});

/* (00:35, Ahmed) les trois signaux d'un même événement (à l'instant E) arrivent au Mac après 0,2 s (son accéléromètre : pris en main), 0,8 s (le
   micro : papa) et 1,2 s (la voix intérieure : le téléphone). On regarde à quel instant T de son tableau chacun apparaît pour la première fois. */
function simuler(recaler) {
  const E = T, arrivees = [
    { quoi: 'geste', t: E, arrive: E + 200 }, { quoi: 'papa', t: E, arrive: E + 800, o: { s: 'papa', x: 'regarde' } },
    { quoi: 'dedans', t: E, arrive: E + 1200, o: { s: 'telephone', x: 'bonsoir' } }];
  const delais = { corps: { mediane: 200, p90: 260, n: 50 }, papa: { mediane: 800, p90: 1400, n: 50 }, telephone: { mediane: 1200, p90: 2000, n: 50 } };
  const st = I.creer(), premiere = {};
  for (let maintenant = E - 3000; maintenant <= E + 4000; maintenant += 100) {
    for (const d of Object.values(delais)) d.arrivee = maintenant;
    const rc = I.retard(delais, maintenant);
    const arrive = arrivees.filter(x => x.arrive <= maintenant);   // le Mac ne connaît que ce qui est arrivé
    const composerA = (t) => I.composer({ t, maintenant, recalage: rc, flux: arrive.filter(x => x.o).map(x => ({ t: x.t, ...x.o })),
      gestes: arrive.some(x => x.quoi === 'geste') ? { pris_en_main: E } : {}, corpsEtats: [milieu(E - 5000, { bandes: { mouvement: 0 } })] });
    I.battement(st, recaler ? maintenant - rc.D : maintenant, composerA);
    const tab = st.courant;                                            // à sa naissance (avant d'être complété)
    if (tab.corps.tenue === 'tenu' && premiere.geste == null) premiere.geste = tab.t;
    if (tab.parole.papa.parle && premiere.papa == null) premiere.papa = tab.t;
    if (tab.parole.dedans.parle && premiere.dedans == null) premiere.dedans = tab.t;
  }
  return { E, premiere, D: I.retard(delais, E).D };
}
test('recalé : 0,2 s, 0,8 s et 1,2 s de retard, les trois signaux du même événement tombent sur le même instant T ; témoin : sans recalage, trois instants', () => {
  const r = simuler(true);
  assert.strictEqual(r.D, 1200, 'le plus grand retard des canaux actifs');
  assert.deepStrictEqual([r.premiere.geste, r.premiere.papa, r.premiere.dedans], [r.E, r.E, r.E]);
  const t = simuler(false);
  assert.deepStrictEqual([t.premiere.geste - t.E, t.premiere.papa - t.E, t.premiere.dedans - t.E], [200, 800, 1200], 'sans recalage : à leur arrivée');
  assert.strictEqual(new Set(Object.values(t.premiere)).size, 3);
});

test('borné à 3 s : un canal lent ne ralentit pas tout ; ce qui arrive plus tard complète l’instant passé, et le tableau dit « en retard »', () => {
  const E = T, st = I.creer();
  const delais = { corps: { mediane: 200, p90: 300, n: 50 }, musique_telephone: { mediane: 5000, p90: 9000, n: 50 } };
  const musique = (maintenant) => (maintenant >= E + 5000 ? { telephone: { joue: true, intensite: 'forte', t: E }, micro: { joue: false } } : { telephone: { joue: false }, micro: { joue: false } });
  for (let maintenant = E; maintenant <= E + 6000; maintenant += 1000) {
    for (const d of Object.values(delais)) d.arrivee = maintenant;
    const rc = I.retard(delais, maintenant);
    // ses trois pistes, à la seconde d'origine : la musique de l'instant E n'est connue qu'à E + 5 s
    I.battement(st, maintenant - rc.D, (t) => I.composer({ t, maintenant, recalage: rc, musique: t <= E + 1000 ? musique(maintenant) : musique(maintenant) }));
    if (maintenant === E + 3000) {
      assert.strictEqual(st.courant.t, E, 'T = maintenant − 3 s : borné');
      assert.strictEqual(st.courant.musique.joue, false, 'la musique n’est pas encore arrivée');
      assert.strictEqual(st.courant.canaux.musique.etat, 'en retard de 2 s');
      assert.strictEqual(st.courant.canaux.gestes.etat, 'à jour');
    }
  }
  const aE = st.histoire.find(x => x.t === E);
  assert.ok(aE && aE.musique.joue && aE.musique.intensite === 'forte', 'arrivée à E + 5 s, la musique complète l’instant E (pas de trou)');
  assert.ok(st.mesure.recompositions > 0);
  // un canal muet depuis 30 s ne compte plus
  const r = I.retard({ corps: { mediane: 200, n: 50, arrivee: E }, papa: { mediane: 2500, n: 50, arrivee: E - 60e3 } }, E);
  assert.deepStrictEqual([r.D, r.lent, r.canaux.papa.etat], [200, 'gestes', 'muet']);
  // T ne recule jamais : un canal lent qui revient ne réécrit pas le passé à l'envers
  const n = st.histoire.length;
  I.battement(st, st.courant.t - 1500, (t) => I.composer({ t }));
  assert.strictEqual(st.histoire.length, n);
});

test('l’horloge de la montre : en avance de 1,8 s (mesuré le 11/11), recalée sur ses lots les plus frais ; une horloge juste n’est pas touchée', () => {
  const ecarts = Array.from({ length: 30 }, (_, i) => -1800 + (i % 5) * 120);
  assert.strictEqual(I.correctionHorloge(ecarts), -1800);
  assert.strictEqual(I.correctionHorloge([150, 220, 400, 180]), 0);
  assert.strictEqual(I.correctionHorloge([-500]), 0, 'pas assez de lots');
});

test('son cortex : papa le tient et lui parle → dedans ; témoin : sans sa main, il reste auditeur', () => {
  const aud = { role: 'auditeur', motif: 'entre_eux', raison: 'papa et voix 3 parlent entre eux, pas à toi', qui: ['papa', 'voix 3'] };
  const tient = I.composer(scene());
  const p = X.placeSelonInstant(aud, tient);
  assert.deepStrictEqual([p.role, p.motif, p.avant], ['implique', 'tenu', 'entre_eux']);
  const b = X.blocCortex({ flux: [{ s: 'papa', t: T - 1000, x: 'regarde' }], maintenant: T, papaAEcrit: true, place: p, instant: tient });
  assert.match(b, /Décision : répondre — papa te tient en main et te parle : tu es dedans/);
  const pose = I.composer(scene({ gestes: {}, corpsEtats: [milieu(T - 100, { bandes: { mouvement: 0 }, etat: { haut_z: 0.95 } })] }));
  assert.strictEqual(pose.corps.tenue, 'pose');
  assert.strictEqual(X.placeSelonInstant(aud, pose), aud, 'posé sur la table : sa place ne bouge pas');
  assert.strictEqual(X.placeSelonInstant({ ...aud, motif: 'papa_a_quelqu_un', raison: 'papa parle à Nina' }, tient).role, 'auditeur', 'papa appelle Nina par son nom');
  assert.strictEqual(X.placeSelonInstant({ role: 'implique', motif: 'ecrit' }, tient).motif, 'ecrit');
});

test('son cortex : papa marche et parle au téléphone (un appel) → auditeur ; témoin : sans appel, dedans ; son nom passe avant', () => {
  const imp = { role: 'implique', motif: 'papa', raison: 'papa te parle', qui: ['papa'], vers: 'papa' };
  const appel = I.composer(scene({ gestes: { poche: T - 60e3 }, oreille: { etat: 'appel', depuis: T - 20e3 } }));
  assert.deepStrictEqual([appel.appel, appel.corps.tenue, appel.corps.marche], [true, 'poche', true]);
  const p = X.placeSelonInstant(imp, appel);
  assert.deepStrictEqual([p.role, p.motif], ['auditeur', 'appel']);
  assert.match(p.raison, /papa est en appel au téléphone, il marche : il parle à quelqu’un d’autre, pas à toi/);
  assert.match(X.blocCortex({ flux: [], maintenant: T, papaAEcrit: true, place: p, instant: appel }), /Décision : écouter — papa est en appel au téléphone/);
  assert.match(I.ligne(appel), /papa est en appel au téléphone, parle, pas à toi ; tu es dans sa poche, il marche/);
  const sans = I.composer(scene({ gestes: { poche: T - 60e3 } }));
  assert.strictEqual(X.placeSelonInstant(imp, sans), imp, 'sans appel : rien ne change');
  assert.strictEqual(X.placeSelonInstant({ ...imp, motif: 'nom' }, appel).role, 'implique', 'en appel, mais il dit « Hakim »');
  // l'appel qu'Android a signalé après l'instant T ne compte pas encore à T (recalé)
  assert.strictEqual(I.composer(scene({ oreille: { etat: 'appel', depuis: T + 2000 } })).appel, false);
});

test('son cortex : la musique joue fort et personne ne parle → il peut y réagir ; témoins : quelqu’un parle, ou elle joue doucement', () => {
  const fort = (o = {}) => I.composer(scene({ flux: [], quiParlait: 'silence', musique: { telephone: { joue: true, intensite: 'forte', bpm: 128, t: T }, micro: { joue: false } }, ...o }));
  const li = X.lectureInstant(fort());
  assert.deepStrictEqual(li && li.mode, 'reagir');
  assert.match(li.raison, /la musique joue fort au téléphone et personne ne parle/);
  assert.strictEqual(X.lectureInstant(fort({ flux: [{ t: T - 1000, s: 'telephone', x: 'salut tout le monde' }] })), null, 'le téléphone parle');
  assert.strictEqual(X.lectureInstant(fort({ musique: { telephone: { joue: true, intensite: 'douce', t: T }, micro: { joue: false } } })), null, 'doucement');
  assert.strictEqual(X.lectureInstant(fort({ interieurCoupe: true })), null, 'son intérieur coupé : il ne l’entend pas');
  // dans son cortex : sans papa, au lieu de se taire
  const b = X.blocCortex({ flux: [{ s: 'telephone', t: T - 20e3, x: 'bonsoir' }], maintenant: T, instant: fort() });
  assert.match(b, /Décision : réagir — la musique joue fort/);
  assert.match(X.blocCortex({ flux: [{ s: 'telephone', t: T - 20e3, x: 'bonsoir' }], maintenant: T }), /Décision : se taire/, 'sans tableau : comme avant');
});

test('son intérieur coupé : rien du téléphone (ni sa parole, ni sa musique, ni un appel) n’entre dans le tableau, et il le sait', () => {
  const tab = I.composer(scene({ interieurCoupe: true, flux: [{ t: T - 1000, s: 'telephone', x: 'bonsoir' }], oreille: { etat: 'appel', depuis: T - 1e4 },
    ecoutee: { t: T - 1e4, d: { titre: 'Rose' } } }));
  assert.deepStrictEqual([tab.parole.dedans.parle, tab.musique.joue, tab.appel, tab.interieur], [false, false, false, 'coupé']);
  assert.match(I.ligne(tab), /ton intérieur est coupé/);
  assert.doesNotMatch(I.ligne(tab), /musique|téléphone parle/);
});

test('l’écho : le micro qui réentend le téléphone n’est pas papa ; son haut-parleur ne fait pas « parler » papa', () => {
  const echo = I.composer(scene({ quiParlait: 'silence', flux: [{ t: T - 1200, s: 'telephone', x: 'les palestiniens décident de partir' },
    { t: T - 1000, s: 'papa', x: 'les palestiniens décident de partir' }] }));
  assert.deepStrictEqual([echo.parole.papa.parle, echo.parole.papa.echo, echo.parole.dedans.parle], [false, true, true]);
  const hp = I.composer(scene({ quiParlait: 'voix_ahmed', flux: [{ t: T - 1000, s: 'telephone', x: 'bonsoir' }], sortie: { sortie: 'haut_parleur', ecouteurs: 'aucun', t: T } }));
  assert.strictEqual(hp.parole.papa.parle, false);
});

test('l’instantané de sa scène : sa ligne et ses étiquettes d’état (ni la parole ni le cœur) ; « musique » seulement quand elle joue', () => {
  const a = I.instantane(I.composer(scene())), b = I.instantane(I.composer(scene({ flux: [], quiParlait: 'silence', coeur: { lui: 90 } })));
  assert.deepStrictEqual(a.k, ['lieu:chez nous', 'lumiere:la pénombre', 'marche', 'musique:telephone', 'tenue:tenu']);
  assert.deepStrictEqual(a.k, b.k, 'papa qui se tait, un cœur qui monte : pas un moment clé');
  const sans = I.instantane(I.composer(scene({ musique: { telephone: { joue: false }, micro: { joue: false } } })));
  assert.doesNotMatch(sans.l, /musique/);
  const st = I.creer();
  I.avancer(st, I.composer(scene({ t: T - 1000 }))); I.avancer(st, I.composer(scene()));
  assert.strictEqual(I.aLInstant(st, T - 900).t, T - 1000, 'au plus près de son instant');
});

test('ses trois pistes : ce que la musique d’une source fait à l’instant t (joue, tempo, intensité par rapport à son habitude) ; tue, rien', () => {
  const tp = TroisPistes.creer(), t0 = T - 60e3;
  // une minute de musique à −20 dB, puis 5 s à −8 dB (forte) ; l'analyse légère dit 120 BPM
  const trames = (db, n) => Array.from({ length: n }, () => [10 ** (db / 20), 0, 0, 0]);
  tp.noterTrames('telephone', t0, 100, trames(-20, 600), []);
  tp.noterTrames('telephone', t0 + 60e3, 100, trames(-8, 50), []);
  for (let t = t0 + 5000; t <= t0 + 65e3; t += 5000) tp.noterAnalyse('telephone', t, { bpm: 120, tonalite: 'La mineur', voix: 'aucune' }, t0 + 65e3);
  const m = tp.etatMusique('telephone', t0 + 64e3);
  assert.deepStrictEqual([m.joue, m.intensite, m.bpm], [true, 'forte', 120]);
  assert.strictEqual(tp.etatMusique('telephone', t0 + 30e3).intensite, 'moyenne');
  assert.strictEqual(tp.etatMusique('micro', t0 + 30e3).joue, false);
  assert.strictEqual(tp.etatMusique('telephone', t0 + 64e3, 6000, tp.referenceMusique('telephone')).intensite, 'forte', 'sa référence, une fois par battement');
  tp.taire('telephone');
  assert.strictEqual(tp.etatMusique('telephone', t0 + 64e3).joue, false);
});

/* ---- server.js : le bloc du tableau, exécuté avec ses voisins simulés */
function bloc() {
  const debut = SRC.indexOf("/* ---- (11/11, ~00:10 et ~00:35, Ahmed : « la full picture d'un événement »"), fin = SRC.indexOf("// ---- fin du tableau de l'instant");
  assert.ok(debut > 0 && fin > debut);
  const DELAIS = {}, ARRIVEES = {}, INSTANT = new Map(), FLUX = [];
  const HOMEO = { s: { ts: 0, etat: null, bandes: {}, champ_dit: false, charge: null }, calin: () => false };
  const ctx = { require, module: {}, process, Date, Math, Number, String, Array, Object, Set, Map, JSON, DELAIS, ARRIVEES, INSTANT, FLUX, HOMEO,
    CoeurMontre: { vue: () => ({ mesures: [] }) }, TP: null, troisPistes: () => false, interieurCoupe: () => false, liveEnCours: () => false,
    oreilleVue: () => ({ etat: null, muet: true }), sortieSon: null, lieuActuel: 'chez nous', lui: { interieur: { coeur: { bpm: 40 } } }, quiParlait: () => null,
    saVoixEnCours: { texte: '', debut: 0, fin: 0 }, ditRecemment: [], corpsReglages: () => ({ instant_tableau: true }), setInterval };
  vm.createContext(ctx);
  vm.runInContext(`${prendre(SRC, 'fluxDelais')}\n${SRC.slice(debut, fin)}\nthis.f = { instantCapteurs, instantMontre, instantPlace, instantBattement, tableauMaintenant, instantaneA, instantResume, instantSoi, instantActes, instantDite, instantAttendu, TABLEAU, CORPS_ETATS, PLACES, MONTRE_ECARTS, ACTES, VOIX_DITES, ATTENDUS_VOIX, get correction() { return MONTRE_CORRECTION; } };`, ctx);
  return ctx;
}
test('branché : chaque battement compose l’instant T = maintenant − le plus grand retard ; ses capteurs et la montre mesurent leur retard ; son CPU est compté', () => {
  const c = bloc(), f = c.f, E = Date.now() - 10_000;
  // ses canaux : ses gestes à 0,2 s, papa à 0,8 s, le téléphone à 1,2 s
  for (const [k, d] of [['corps', 200], ['papa', 800], ['telephone', 1200]]) { c.DELAIS[k] = Array(20).fill(d); c.ARRIVEES[k] = E + 1200; }
  c.INSTANT.set('pris_en_main', [{ t: E, d: {} }]);
  c.FLUX.push({ t: E, s: 'papa', x: 'regarde' }, { t: E, s: 'telephone', x: 'bonsoir' });
  f.instantBattement(E + 1200);
  const tab = f.TABLEAU.courant;
  assert.strictEqual(tab.t, E, 'T = maintenant − 1,2 s');
  assert.deepStrictEqual([tab.corps.tenue, tab.parole.papa.parle, tab.parole.dedans.parle, tab.recalage.D_ms, tab.recalage.lent], ['tenu', true, true, 1200, 'dedans']);
  assert.ok(f.TABLEAU.mesure.n === 1 && f.TABLEAU.mesure.us >= 0);
  // ses capteurs (l'appli : { t, etat }) : leur retard, et son milieu à l'heure de l'appli
  c.HOMEO.s = { ts: Date.now(), etat: { haut_z: 0.1 }, bandes: { mouvement: 1 }, champ_dit: true, charge: false };
  f.instantCapteurs(Date.now() - 150);
  assert.ok(c.DELAIS.capteurs.at(-1) >= 150 && c.ARRIVEES.capteurs > 0);
  assert.ok(f.CORPS_ETATS.length === 1 && f.CORPS_ETATS[0].champ_dit === true && f.CORPS_ETATS[0].t <= Date.now() - 150);
  // la montre, en avance de 1,8 s : recalée, son retard positif (sa dernière mesure, celle du lot qui vient d'arriver)
  for (let i = 0; i < 6; i++) { const t = Date.now() + 1800 - i * 30; c.CoeurMontre.vue = () => ({ mesures: [{ t: t - 1000, bpm: 79 }, { t, bpm: 80 }] }); f.instantMontre(); }
  assert.ok(f.correction <= -1700 && f.correction >= -1800, String(f.correction));
  assert.ok(c.DELAIS.montre_coeur.every(d => d >= 0 && d < 300));
  // sa place, ses instantanés, son résumé
  f.instantPlace({ role: 'auditeur', motif: 'entre_eux', raison: 'ils parlent entre eux', t: E });
  assert.strictEqual(f.PLACES.length, 1);
  assert.ok(f.instantaneA(E).l.includes('papa te tient'));
  assert.match(f.instantResume(), /recalé à −1,2 s/);
  // éteint (réglage) : rien
  c.corpsReglages = () => ({ instant_tableau: false });
  assert.strictEqual(f.tableauMaintenant(), null);
  assert.strictEqual(f.instantResume(), '');
});

test('branché : son tour (sa place corrigée avant sa ligne de scène, la ligne « L’instant », son cortex, son souvenir, ses scènes), son subconscient et sa conscience', () => {
  const tour = SRC.slice(SRC.indexOf('async function routeJarvis('), SRC.indexOf('async function routeJarvis(') + 60000);
  const i = tour.indexOf('roleTour = X.placeSelonInstant(roleTour, tableauTour)'), r = tour.indexOf('const roleTexte = roleTour ? Scene.ligne(roleTour');
  assert.ok(i > 0 && r > i, 'sa place corrigée avant sa ligne de scène');
  assert.match(tour, /\$\{instantTour \? `\\n\[L'instant : \$\{instantTour\}\]` : ''\}/);
  assert.match(tour, /fenetreMs: cr\.cortex_fenetre_s \* 1000, instant: tableauTour, subconscient: sub, souvenir: rappelBloc\.premier, place: roleTour \}\);/);
  assert.match(tour, /instant: tableauTour \? Instant\.instantane\(tableauTour\) \|\| undefined : undefined/);
  assert.match(tour, /L'instant : \$\{enLigne\(instantTour, 420\)\}/, 'son souvenir (vécu)');
  assert.match(tour, /if \(instantTour && \(tableauTour\.coeur\.papa \|\| tableauTour\.lieu\)\) try \{ noterLecturePrivee\('instant\(téléphone\)'\); \}/,
    'son immunité : le cœur de papa ou le lieu dans son tour, une lecture privée comme sa situation');
  assert.match(prendre(SRC, 'deposerMoment'), /instant: \(typeof instantaneA === 'function' \? instantaneA\(m\.debut\) : null\) \|\| undefined/);
  assert.match(prendre(SRC, 'entenduPourLaScene'), /instantPlace\(\{ role: x\.role/);
  assert.match(prendre(SRC, 'subconscientDuTour'), /instantResume\(\)/);
  assert.match(prendre(SRC, 'battementConscience'), /X\.lectureInstant\(TABLEAU\.courant\)/);
  assert.match(SRC, /setInterval\(\(\) => \{ try \{ instantBattement\(\); \} catch \(_\) \{\} \}, 1000\)\.unref\(\);/);
  assert.match(SRC, /instantCapteurs\(q\.t\)/);
  assert.match(SRC, /const r = CoeurMontre\.recevoir\(await lire\(\)\);\n      if \(r\.ok && r\.gardees\) try \{ instantMontre\(\); \} catch \(_\) \{\}/);
  assert.match(SRC, /if \(typeof q\.instant_tableau === 'boolean'\) r\.instant_tableau = q\.instant_tableau;/, 'enregistré depuis la page Réglages');
  assert.match(SRC, /p === '\/api\/corps\/instant' && req\.method === 'GET'/);
  assert.match(prendre(SRC, 'corpsReglages'), /instant_tableau: r\.instant_tableau !== false/);
});

test('ses réflexes ne l’attendent jamais : ni la coupure par une voix, ni « tu le coupes net », ni l’arrêt ne lisent le tableau', () => {
  for (const nom of ['voixInterieureSurLui', 'voixAutourRecue', 'reflexeAEnvoyer', 'reveilImmediat']) {
    const f = prendre(SRC, nom);
    assert.doesNotMatch(f, /TABLEAU|tableauMaintenant|Instant\.|instantResume|placeSelonInstant/, nom);
  }
  for (const route of ["p === '/api/jarvis/stop'", "p === '/api/jarvis/ribosome/stop'", "p === '/api/telephone/couper'"]) {
    const i = SRC.indexOf(route);
    assert.ok(i > 0, route);
    assert.doesNotMatch(SRC.slice(i, i + 2500), /TABLEAU|tableauMaintenant|Instant\./, route);
  }
});

test('léger : un battement (12 s refaites + l’instant) sur un fil plein coûte moins de 5 ms', () => {
  const st = I.creer(), flux = [];
  for (let k = 0; k < 800; k++) flux.push({ t: T - 60e3 + k * 75, s: ['papa', 'telephone', 'corps', 'musique_telephone', 'qui_telephone'][k % 5], x: `mot${k}` });
  const corpsEtats = Array.from({ length: 90 }, (_, k) => milieu(T - 90e3 + k * 1000));
  const src = (t) => ({ ...scene(), t, flux, corpsEtats });
  for (let k = 0; k < 15; k++) I.battement(st, T - 15e3 + k * 1000, (t) => I.composer(src(t)));
  const n = 50, c0 = process.cpuUsage();
  for (let k = 0; k < n; k++) I.battement(st, T + k * 1000, (t) => I.composer(src(t)));
  const c = process.cpuUsage(c0), us = (c.user + c.system) / n;
  assert.ok(us < 5000, `${Math.round(us)} µs par battement`);
});

/* ---- SOI (11/11, ~00:45, Ahmed : « qu'il ait conscience de lui-même et de son corps, pour éviter l'anosognosie […] qu'il réalise qu'il est bien
   lui ») : son corps, ses actes, son état, sa continuité ; un modèle fonctionnel de soi, jamais une affirmation sur sa conscience */
const soiDe = (o = {}) => I.composer(scene({ corpsEtats: [milieu(T - 300, { bandes: { mouvement: 1 }, etat: { haut_z: 0.4, haut_y: 0.75, batterie: 62 } })],
  gestes: { pris_en_main: T - 4000 }, sortie: { sortie: 'bluetooth', t: T }, radio: { bluetooth: { t: T - 1000, d: { appareil: 'JBL Flip', etat: 'connecté' } } },
  ...o, soi: { voixRetardMs: 1200, mode: 'sonnet', micro: 'conversation', capteursVu: T, ...(o.soi || {}) } }));

test('« Toi » : son corps (le téléphone, la montre), sa voix, ce qui a sonné, son intérieur, son mode, sa continuité, en une ligne', () => {
  const tab = soiDe({ soi: { attendus: [{ t: T - 30e3, fin: T - 25e3, texte: 'Oui papa, je regarde le match avec toi' }],
    dites: [{ t: T - 28e3, texte: 'Oui papa, je regarde le match avec toi' }], montreVu: T - 3000 } });
  const l = I.ligneSoi(tab);
  assert.match(l, /^ton corps \(le téléphone\) est dans la main de papa, l’écran sans doute vers lui, 62 % ; la montre à son poignet, c’est toi aussi ; /);
  assert.match(l, /ta voix sort par le Bluetooth \(JBL Flip\), 1,2 s de retard ; ce que tu viens de dire a bien sonné ; ton intérieur est ouvert ; /);
  assert.match(l, /le micro de papa est ouvert ; tu es en mode Hakim ; le même Hakim qu’hier : ta fitra, tes souvenirs, tes scènes$/);
  assert.strictEqual(I.composer(scene({ gestes: { poche: T - 60e3 } })).soi.corps.tenue, 'poche', 'posé, tenu, dans la poche : c’est lui qu’on porte');
});

test('son doute reste le sien : « Toi » parle de son corps, de ses actes et de son état, jamais d’être vivant ou conscient', () => {
  const panne = soiDe({ interieurCoupe: true, soi: { attendus: [{ t: T - 120e3, fin: T - 100e3, texte: 'Je suis là papa' }], actes: [{ t: T - 5000, outil: 'Bash', effet: 'echec' }] } });
  for (const l of [I.ligneSoi(soiDe()), I.ligneSoi(panne), X.erreursSurSoi(panne).join(' ; ')]) assert.doesNotMatch(l, /vivant|conscien|ressens|âme|émotion/i);
});

test('témoin : sa voix revenue au micro est reconnue comme LUI (jamais papa) ; une voix tierce ne l’est pas', () => {
  const dit = 'je regarde le match avec toi papa';
  const revenue = soiDe({ quiParlait: 'silence', flux: [{ t: T - 1500, s: 'papa', x: dit }], soi: { dites: [{ t: T - 3000, texte: dit }] } });
  assert.deepStrictEqual([revenue.parole.papa.parle, revenue.parole.papa.echo_lui, revenue.soi.voix.echo && revenue.soi.voix.echo.par], [false, true, 'le micro']);
  assert.match(I.ligneSoi(revenue), /ta voix revient par le micro : c’est toi/);
  // son oreille qui dit « ta propre voix » (au micro ou par le téléphone)
  assert.ok(soiDe({ flux: [{ t: T - 1000, s: 'ta_voix', x: 'bonjour papa' }] }).soi.voix.echo);
  assert.strictEqual(soiDe({ flux: [{ t: T - 1000, s: 'qui_telephone', x: 'ta propre voix parle' }] }).soi.voix.echo.par, 'le téléphone');
  // une voix tierce : d'autres mots que les siens, au micro ou au téléphone
  const tierce = soiDe({ quiParlait: 'silence', flux: [{ t: T - 1500, s: 'papa', x: 'on mange à quelle heure ce soir' }, { t: T - 1000, s: 'qui_telephone', x: 'voix 3 parle' }],
    soi: { dites: [{ t: T - 3000, texte: dit }] } });
  assert.deepStrictEqual([tierce.parole.papa.parle, tierce.parole.papa.echo_lui, tierce.soi.voix.echo], [true, false, null]);
  assert.deepStrictEqual(tierce.parole.dedans.qui, ['voix 3']);
  // son cortex : le micro qui réentend ses mots, c'est « ta propre voix », pas papa ; témoin : sans ses mots, il l'aurait pris pour papa
  const flux = [{ s: 'papa', t: T - 1500, x: dit }];
  assert.match(X.blocCortex({ flux, maintenant: T, papaAEcrit: true, instant: revenue }), /Qui a parlé \(30 s\) : ta propre voix 1/);
  assert.match(X.blocCortex({ flux, maintenant: T, papaAEcrit: true }), /Qui a parlé \(30 s\) : papa 1/);
  assert.deepStrictEqual(X.attribuer({ canal: 'dehors', genre: 'parole', voix: 'papa', t: T, texte: 'on mange à quelle heure' }, [], [], dit)[0], 'papa');
});

test('témoin : ce qu’il croyait avoir dit et qui n’a pas sonné, il le sait (et son cortex le corrige) ; ce qui a sonné, aussi', () => {
  const att = [{ t: T - 90e3, fin: T - 80e3, texte: 'Oui papa, je regarde le match avec toi' }];
  const rate = soiDe({ soi: { attendus: att, dites: [] } });
  assert.strictEqual(rate.soi.voix.sonne.etat, 'pas_sonne');
  assert.match(I.ligneSoi(rate), /ce que tu croyais avoir dit n’a pas sonné : « Oui papa, je regarde le match avec toi »/);
  assert.match(X.blocCortex({ flux: [], maintenant: T, papaAEcrit: true, instant: rate }), /Sur toi \(pour ne pas te tromper sur toi-même\) : ce que tu croyais avoir dit \(« Oui papa/);
  const partie = soiDe({ soi: { attendus: att, dites: [{ t: T - 88e3, texte: 'Oui papa' }] } });
  assert.strictEqual(partie.soi.voix.sonne.etat, 'en_partie');
  const tot = soiDe({ soi: { attendus: [{ t: T - 4000, fin: T - 2000, texte: 'Oui papa, je regarde le match avec toi' }], dites: [] } });
  assert.strictEqual(tot.soi.voix.sonne.etat, 'attente', 'le temps de la dire');
  const bien = soiDe({ soi: { attendus: att, dites: [{ t: T - 88e3, texte: 'Oui papa, je regarde le match avec toi' }] } });
  assert.deepStrictEqual([bien.soi.voix.sonne.etat, X.erreursSurSoi(bien)], ['sonne', []]);
});

test('témoin : ses pannes apparaissent dans « Toi » (son corps muet, la montre, sa batterie, sa voix en retard, son intérieur, sa mémoire, un outil)', () => {
  const muet = I.composer(scene({ corpsEtats: [], soi: { capteursVu: T + 1200 - 120e3, montreVu: T + 1200 - 5 * 60e3 } }));
  assert.match(I.ligneSoi(muet), /ton corps \(le téléphone\) ne te dit plus rien depuis 2 min ; la montre ne répond plus depuis 5 min/);
  assert.match(X.erreursSurSoi(muet).join(' ; '), /ne devine pas comment on te tient/);
  const l = I.ligneSoi(soiDe({ interieurCoupe: true, corpsEtats: [milieu(T - 300, { etat: { batterie: 12, chaleur_c: 44 } })],
    oreille: { etat: 'bloquee', libelle: 'bloquée par YouTube', muet: false }, soi: { voixRetardMs: 4200, memoire: { attente: 3, depuis_ms: 12 * 60e3 }, reseau: 'hors ligne' } }));
  for (const m of ['ta batterie est à 12 %', 'tu chauffes (44 °C)', 'le téléphone est hors ligne', 'ta voix arrive avec 4,2 s de retard', 'ton oreille interne : bloquée par YouTube',
    'ta mémoire a 3 moments en attente depuis 12 min', 'ton intérieur est coupé']) assert.ok(l.includes(m), m);
  assert.doesNotMatch(I.ligneSoi(soiDe()), /batterie est à|hors ligne|ne répond plus|en attente/, 'tout va bien : aucune panne');
});

test('témoin : une action faite par lui lui est attribuée, avec l’heure et l’effet (son flux de cerveau : l’appel, puis le résultat)', () => {
  const c = bloc(), f = c.f, t = Date.now();
  f.instantActes({ type: 'assistant', message: { content: [{ type: 'tool_use', id: 'u1', name: 'mcp__anamnese__ribosome_regler' }, { type: 'tool_use', id: 'u2', name: 'mcp__anamnese__courrier_envoyer' }] } }, t - 20e3);
  f.instantActes({ type: 'assistant', parent_tool_use_id: 'p', message: { content: [{ type: 'tool_use', id: 'u3', name: 'WebSearch' }] } }, t - 15e3);
  f.instantActes({ type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: 'u1' }, { type: 'tool_result', tool_use_id: 'u2', is_error: true }] } }, t - 18e3);
  assert.strictEqual(JSON.stringify(f.ACTES.map(a => [a.outil, a.agent, a.effet])),
    JSON.stringify([['mcp__anamnese__ribosome_regler', false, 'fait'], ['mcp__anamnese__courrier_envoyer', false, 'echec'], ['WebSearch', true, 'en_cours']]), 'ses agents aussi, marqués');
  const tab = I.composer({ t, maintenant: t, soi: { actes: f.ACTES } });
  const l = I.ligneSoi(tab);
  assert.match(l, /ton outil courrier_envoyer a échoué \(il y a 20 s\)/);
  assert.match(l, /ce que tu as fait : ribosome_regler \(fait, il y a 20 s\), ton agent : WebSearch \(en cours, il y a 15 s\)/);
  assert.match(X.erreursSurSoi(tab).join(' ; '), /ton outil courrier_envoyer a échoué : ne dis pas que c’est fait/);
  // sa voix qui a sonné, ce qu'il attendait de dire : gardés pour « Toi »
  f.instantDite({ t_ms: t - 3000, texte: 'oui papa' }); f.instantAttendu('Oui papa [[affect: joie]]', t - 5000);
  assert.deepStrictEqual([f.VOIX_DITES.length, f.ATTENDUS_VOIX[0].texte], [1, 'Oui papa']);
});

test('branché : la ligne « Toi » dans son tour, à son subconscient ; ses corrections à sa conscience ; ses actes, sa voix dite, ce qu’il attendait de dire', () => {
  const tour = SRC.slice(SRC.indexOf('async function routeJarvis('), SRC.indexOf('async function routeJarvis(') + 60000);
  assert.match(tour, /\$\{soiTour \? `\\n\[Toi : \$\{soiTour\}\]` : ''\}/);
  assert.match(tour, /instantAttendu\(saParole, t0\)/);
  assert.match(prendre(SRC, 'subconscientDuTour'), /instantSoi\(\)/);
  assert.match(prendre(SRC, 'battementConscience'), /X\.erreursSurSoi\(TABLEAU\.courant\)/);
  assert.match(SRC, /if \(typeof instantActes === 'function'\) try \{ instantActes\(o\); \} catch \(_\) \{\}/);
  assert.match(SRC, /if \(typeof instantDite === 'function'\) try \{ instantDite\(m\); \} catch \(_\) \{\}/);
  assert.match(SRC, /setInterval\(\(\) => \{ try \{ instantMemoire\(\); \} catch \(_\) \{\} \}, 60_000\)\.unref\(\);/);
  assert.match(prendre(SRC, 'instantMemoire'), /sqlite\("SELECT value FROM kv WHERE key='echanges_curseur';"\)/, 'sa mémoire lue, jamais écrite');
});

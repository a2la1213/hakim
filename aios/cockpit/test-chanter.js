/* (11/11, ~01:15, Ahmed : « Il peut chanter en même temps qu'une musique, s'il le veut ? En coordonnant la sortie de sa voix avec la sortie du
   son, sur le smartphone ou en Bluetooth. ») son chant calé sur la musique : la grille des temps, le calage, la prévision du retour du refrain,
   le débit, le départ avec les retards, ses garde-fous ; le câblage du cockpit (sa décision, le plan, l'annulation) et la page qui chante.
   Chaque mécanisme a son témoin (le mécanisme coupé, le test échoue). node --test test-chanter.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const C = require('./public/chanter.js');
const Banc = require('./mesure/chanter-banc.js');
const P = require('./paroles.js');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const tranche = (src, debut, fin) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); const k = src.indexOf(fin, i); assert.ok(k > i, fin); return src.slice(i, k + fin.length); };

// ---- 1. la grille des temps forts
function trames(bpm, fines, s = 30) { const { x, beats } = Banc.musique(bpm, s); return { tr: Banc.tramesAppli(x, 0, 0, 0, fines), beats: beats.map(b => b * 1000) }; }
const ecartAuTemps = (g, beats, t) => { const p = C.tempsProche(g, t, 1); return p - beats.reduce((m, b) => (Math.abs(b - p) < Math.abs(m - p) ? b : m), beats[0]); };

test('la grille : le tempo affiné et la phase des temps, depuis les trames de 100 ms (93 BPM donné à 92)', () => {
  const { tr, beats } = trames(93, false);
  const g = C.grille(tr, { bpm: 92 });
  assert.ok(C.grilleSure(g), JSON.stringify(g));
  assert.ok(Math.abs(g.bpm - 93) < 0.5, `bpm ${g.bpm}`);
  for (const t of [25000, 29000]) assert.ok(Math.abs(ecartAuTemps(g, beats, t)) < 30, `écart ${ecartAuTemps(g, beats, t)} ms`);
});
test('la grille : témoin — du bruit sans battement ne donne pas de grille sûre', () => {
  const x = new Float32Array(16000 * 25); let s = 7; for (let i = 0; i < x.length; i++) { s = (s * 1103515245 + 12345) & 0x7fffffff; x[i] = 0.2 * (s / 0x7fffffff - 0.5); }
  assert.equal(C.grilleSure(C.grille(Banc.tramesAppli(x, 0, 0, 0, false), { bpm: 90 })), false);
});
test('la grille : à 120 BPM (le temps tombe toujours au même endroit des trames), l’attaque fine de l’appli 1.96 enlève le biais ; témoin : sans elle, il reste', () => {
  const a = trames(120, true), b = trames(120, false);
  const ga = C.grille(a.tr, { bpm: 120 }), gb = C.grille(b.tr, { bpm: 120 });
  const ea = ecartAuTemps(ga, a.beats, 29000), eb = ecartAuTemps(gb, b.beats, 29000);
  assert.ok(Math.abs(ea) < 20, `fines : ${ea} ms`);
  assert.ok(Math.abs(eb) > 35, `sans elles : ${eb} ms (le biais de la trame)`);
});
test('tempsProche : au temps, ou au demi-temps', () => {
  const g = { periode_ms: 500, t0: 1000, r: 1 };
  assert.equal(C.tempsProche(g, 1240, 1), 1000);
  assert.equal(C.tempsProche(g, 1240, 2), 1250);
  assert.equal(C.tempsProche(null, 1240, 2), 1240);
});

// ---- 2. le calage de la musique jusqu'au micro
test('le calage : une musique en boucle a un pic par temps ; l’écho de sa voix choisit le bon ; témoin : sans écho et deux pics, rien (ambigu)', () => {
  const cal = { ms: 400, correlation: 0.88, pics: [{ ms: 400, c: 0.88 }, { ms: 40, c: 0.77 }] };
  assert.equal(C.choisirCalage(cal, 120), 40);                  // 120 − 36,5 : le pic à 40
  assert.equal(C.choisirCalage(cal, null), null);
  assert.equal(C.choisirCalage({ ms: 200, correlation: 0.9, pics: [{ ms: 200, c: 0.9 }] }, null), 200);
  assert.equal(C.choisirCalage(null, 120), null);
});
test('caler : retrouve le retard de la musique jusqu’au micro, borné à ce qu’un vrai chemin peut être', () => {
  const { x } = Banc.musique(90, 40);
  const tel = Banc.tramesAppli(x, 1e6, 25, 8, false).map(f => ({ t: f.tb, v: f.v })).filter(f => f.t >= 1e6 + 10000);
  const dm = Math.round(0.22 * 16000), mic = new Float32Array(x.length);
  for (let i = dm; i < x.length; i++) mic[i] = 0.35 * x[i - dm];
  const r = C.caler(tel, Banc.tramesMicro(mic, 1e6, 30, 4).filter(f => f.t >= 1e6 + 10000));
  assert.ok(r && r.pics.some(p => Math.abs(p.ms - 196) <= 20), JSON.stringify(r));   // 220 − 29 + 30 − 25
  assert.ok(r.pics.every(p => p.ms > -50 && p.ms < 700));
});

// ---- 3. la prévision du retour du refrain
const L = (tb, texte, groupe, d = 3000, mots = null) => ({ tb, t: tb + 7, texte, groupe, d, ...(mots ? { mots } : {}) });
const refrain = (t0) => [L(t0, 'Moujahid, moujahid, je ne plie pas', 1), L(t0 + 4000, 'La lumière est là, papa me tient la main', 2)];
const morceau = () => [L(0, 'couplet un', 10), L(4000, 'couplet deux', 11), ...refrain(10000), L(20000, 'couplet trois', 12), L(30000, 'couplet quatre', 13), ...refrain(50000)];

test('prévoir : le refrain revient après le même écart (40 s), ses deux lignes à leur place', () => {
  const c = C.prevoir(morceau(), { maintenant: 60000 });
  const r = c.filter(x => x.par === 'retour');
  assert.deepStrictEqual(r.map(x => [x.t, x.groupe]), [[90000, 1], [94000, 2]]);
  assert.ok(r[0].confiance >= 0.4);
});
test('prévoir : l’écart arrondi aux mesures de la grille, et chaque instant calé au demi-temps', () => {
  const l = [...refrain(10000), ...refrain(50300)];
  const g = { periode_ms: 500, t0: 0, r: 0.9 };
  const r = C.prevoir(l, { maintenant: 60000, grille: g }).filter(x => x.par === 'retour');
  // 40 300 ms → 20 mesures de 2 s : 40 000 ; 50 300 + 40 000 = 90 300 → au demi-temps (250 ms) : 90 250
  assert.equal(r[0].t, 90250);
  assert.ok(r.every(x => x.cale && x.t % 250 === 0));
});
test('prévoir : la suite du passage en cours (sa première ligne entendue, la deuxième à venir)', () => {
  const l = [...morceau(), L(90000, 'Moujahid, moujahid, je ne plie pas', 1)];
  const s = C.prevoir(l, { maintenant: 91000 }).filter(x => x.par === 'suite');
  assert.deepStrictEqual(s.map(x => [x.t, x.groupe]), [[94000, 2]]);
});
test('prévoir : témoin — des lignes qui ne reviennent pas ne prévoient rien', () => {
  const l = [L(0, 'a', 1), L(4000, 'b', 2), L(10000, 'c', 3), L(50000, 'd', 4)];
  assert.deepStrictEqual(C.prevoir(l, { maintenant: 60000 }), []);
});
test('prévoir : un morceau déjà entendu, par la position du lecteur (la mémoire) ; témoin : le lecteur en pause, rien', () => {
  const memoire = { titre: 'Lanterne', lignes: [{ pos: 30000, texte: 'Alhamdoulillah, quand ça monte', d: 3000, groupe: 1 }, { pos: 10000, texte: 'déjà passé', groupe: 2 }] };
  const h = [{ titre: 'Lanterne', etat: 'lecture', a: 100000, position_ms: 20000, vitesse: 1 }];
  const c = C.prevoir([], { maintenant: 101000, horloge: h, memoire, titre: 'Lanterne' });
  assert.deepStrictEqual(c.map(x => [x.par, x.t]), [['memoire', 110000]]);
  assert.deepStrictEqual(C.prevoir([], { maintenant: 101000, horloge: [{ ...h[0], etat: 'pause' }], memoire, titre: 'Lanterne' }), []);
  // un autre morceau : sa mémoire ne sert pas
  assert.deepStrictEqual(C.prevoir([], { maintenant: 101000, horloge: h, memoire: { ...memoire, titre: 'Autre' }, titre: 'Lanterne' }), []);
});
test('l’horloge du lecteur : la dernière position avant t, un saut (seek) compris', () => {
  const h = [{ titre: 'x', etat: 'lecture', a: 0, position_ms: 0 }, { titre: 'x', etat: 'lecture', a: 5000, position_ms: 60000 }];
  assert.equal(C.positionA(C.horlogeA(h, 3000, 'x'), 3000), 3000);
  assert.equal(C.positionA(C.horlogeA(h, 7000, 'x'), 7000), 62000);
  assert.equal(C.instantDe(h[1], 65000), 10000);
});
test('mémoriser : ses lignes à leur position dans le morceau', () => {
  const h = [{ titre: 'x', etat: 'lecture', a: 1000, position_ms: 5000 }];
  const m = C.memoriser([L(3000, 'une', 1), L(500, 'avant le lecteur', 2)], h, 'x');
  assert.deepStrictEqual(m.lignes.map(x => [x.pos, x.texte]), [[7000, 'une']]);
});
test('choisir : assez loin pour préparer sa voix (3,5 s), la plus sûre, et la ligne qui la suit de près', () => {
  const c = [{ t: 2000, texte: 'trop près', par: 'retour', confiance: 0.6, d: 3000 }, { t: 10000, texte: 'a', par: 'retour', confiance: 0.6, d: 3000 },
    { t: 13500, texte: 'b', par: 'retour', confiance: 0.6, d: 3000 }, { t: 30000, texte: 'c', par: 'retour', confiance: 0.6, d: 3000 }];
  const x = C.choisir(c, 0);
  assert.deepStrictEqual(x.lignes.map(l => l.texte), ['a', 'b']);
  assert.equal(C.choisir([{ t: 10000, texte: 'a', par: 'retour', confiance: 0.3 }], 0), null);   // pas assez sûre
});

// ---- 4. la scansion et le débit
test('découper : la phrase en morceaux de 2 temps au moins, ses mots à leur place ; sans les temps des mots, un seul morceau', () => {
  const l = { texte: 'Moujahid moujahid je ne plie pas jamais', d: 3600, mots: [['Moujahid', 0], ['moujahid', 500], ['je', 1000], ['ne', 1200], ['plie', 1500], ['pas', 2100], ['jamais', 2600]] };
  const m = C.decouper(l, 500);
  assert.deepStrictEqual(m.map(x => [x.texte, x.dt]), [['Moujahid moujahid', 0], ['je ne plie', 1000], ['pas jamais', 2100]]);
  assert.deepStrictEqual(m.map(x => x.d), [1000, 1100, 1500]);
  assert.deepStrictEqual(C.decouper({ texte: 'sans mots', d: 2000 }, 500), [{ texte: 'sans mots', dt: 0, d: 2000 }]);
});
test('planifier : chaque morceau à son instant, calé au demi-temps, sa durée jusqu’au suivant', () => {
  const g = { periode_ms: 500, t0: 0, r: 0.9 };
  const choix = { lignes: [{ t: 10010, texte: 'a b c d e', d: 3000, mots: [['a', 0], ['b', 300], ['c', 600], ['d', 1100], ['e', 1400]] }] };
  const p = C.planifier(choix, g);
  // a b c (0 à 600 ms), puis d e (1 100 ms : 11 110 → au demi-temps, 11 000)
  assert.deepStrictEqual(p.map(x => [x.texte, x.a, x.d]), [['a b c', 10000, 1000], ['d e', 11000, 1900]]);
});
test('le débit : ses syllabes dans la durée (rate SSML) ; corrigé une fois si la voix rendue s’en écarte de plus de 12 %', () => {
  assert.equal(C.syllabes('Moujahid, je ne plie pas'), 7);          // mou-ja-hid je ne plie pas
  assert.equal(C.syllabes('la lumière est là'), 5);                  // le « e » muet de lumière
  assert.equal(C.syllabes('حكيم'), 2);
  const d = C.debit('Moujahid, je ne plie pas', 1000);            // 7 syllabes en 1 s : 7 / 5,2
  assert.equal(d.rate, 1.35);
  assert.equal(C.rateSsml(1.35), '+35%');
  assert.equal(C.rateSsml(0.9), '-10%');
  assert.equal(C.corrigerDebit(1.15, 1050, 1000), null);
  assert.equal(C.corrigerDebit(1.2, 1300, 1000), 1.56);
  assert.equal(C.debit('trop', 100).rate, 1.6);                     // borné
});

// ---- 5. le départ, avec les retards
test('le départ par le micro : temps + calage − écho + les fenêtres − son blanc de début ; sans les deux, le même appareil', () => {
  assert.deepStrictEqual(C.depart({ cible: 10000, calage_ms: 196, echo_ms: 277, attaque_ms: 12 }), { t: 9944, par: 'micro', incertitude_ms: 40 });
  assert.deepStrictEqual(C.depart({ cible: 10000, base_ms: 10, attaque_ms: 12 }), { t: 9938, par: 'annonce', incertitude_ms: 80 });
  // témoin : un seul des deux chemins mesuré ne sert pas (il ne dit rien sans l'autre)
  assert.equal(C.depart({ cible: 10000, calage_ms: 196, echo_ms: null }).par, 'annonce');
  assert.equal(C.depart({ cible: NaN }), null);
});
test('attaqueDe : le blanc au début de sa voix rendue', () => {
  const x = new Float32Array(2400); for (let i = 480; i < 2400; i++) x[i] = Math.sin(i / 5);
  assert.equal(C.attaqueDe(x, 24000), 20);
});
test('le banc : par le micro, sa voix sonne à moins de 100 ms du temps (haut-parleur, enceinte, deux chemins) ; témoin : deux chemins sans micro, hors de 100 ms', () => {
  const cas = [{ Lm: 60, Lv: 75 }, { Lm: 220, Lv: 240 }, { Lm: 230, Lv: 70 }];
  for (const c of cas) for (const bpm of [90, 140]) {
    const r = Banc.essai({ ...c, bpm, captureMs: 25, entreeMs: 30, micro: true, avance_s: 8, fines: true });
    assert.equal(r.par, 'micro', JSON.stringify(r));
    assert.ok(Math.abs(r.ecart_ms) < 100, JSON.stringify(r));
  }
  const t = Banc.essai({ Lm: 230, Lv: 70, bpm: 90, captureMs: 25, entreeMs: 30, micro: false, avance_s: 8, fines: true });
  assert.ok(Math.abs(t.ecart_ms) > 100, JSON.stringify(t));
});

// ---- 6. ses garde-fous
test('ses garde-fous : son réglage, son intérieur coupé, un appel, papa qui parle, lui qui parle, la page absente, une fois par morceau', () => {
  const ok = { reglage: true, coupe: false, appel: false, musique: true, papaA: 0, ilParle: false, page: true };
  const e = C.creer();
  assert.deepStrictEqual(C.garde(e, ok, {}, 100000), { ok: true });
  for (const [k, v, raison] of [['reglage', false, 'reglage'], ['coupe', true, 'interieur_coupe'], ['appel', true, 'appel'], ['musique', false, 'pas_de_musique'],
    ['papaA', 99000, 'papa_parle'], ['ilParle', true, 'il_parle'], ['page', false, 'pas_de_page']])
    assert.equal(C.garde(e, { ...ok, [k]: v }, {}, 100000).raison, raison, k);
  C.morceau(e, 'p:1'); C.chante(e, 100000);
  assert.equal(C.garde(e, ok, {}, 200000).raison, 'deja_chante');
  C.morceau(e, 'p:2');                                                  // un autre morceau : il peut, après l'écart
  assert.equal(C.garde(e, ok, {}, 130000).raison, 'ecart');
  assert.deepStrictEqual(C.garde(e, ok, {}, 200000), { ok: true });
  assert.deepStrictEqual(C.garde(e, ok, { par_morceau: 2 }, 200000), { ok: true });
  assert.equal(C.annuler({ ...ok, papaA: 99500 }, {}, 100000), 'papa_parle');
  assert.equal(C.annuler({ ...ok, coupe: true }, {}, 100000), 'interieur_coupe');
  assert.equal(C.annuler({ ...ok, appel: true }, {}, 100000), 'appel');
  assert.equal(C.annuler(ok, {}, 100000), null);
});

// ---- les paroles : l'heure de l'appli, la durée et les mots de chaque ligne
test('paroles : chaque ligne garde l’heure de l’appli (tb = t − decalage), sa durée et ses mots à leur place', () => {
  const e = P.creer();
  P.recevoir(e, { texte: 'Dans le noir je tiens debout.', t0: 100000, decalage: 5000, mots: [['Dans', 0.2, 0.4], ['le', 0.4, 0.5], ['noir', 0.5, 0.8], ['je', 0.8, 0.9], ['tiens', 0.9, 1.2], ['debout.', 1.2, 1.6]] }, 110000);
  const l = e.morceau.lignes[0];
  assert.equal(l.t, 100200); assert.equal(l.tb, 95200); assert.equal(l.d, 1400);
  assert.deepStrictEqual(l.mots, [['Dans', 0], ['le', 200], ['noir', 300], ['je', 600], ['tiens', 700], ['debout.', 1000]]);
});

// ---- le câblage du cockpit : sa décision, le plan, l'annulation
function bac(o = {}) {
  const diffuse = [], journal = [], appels = [];
  const reglages = { chanter_musique: true, chanter_par_morceau: 1, chanter_ecart_s: 60, voix_hakim: 'azure', ...(o.reglages || {}) };
  const ctx = {
    Date, Math, JSON, String, Number, Array, Object, Promise, RegExp, Set, Map, Buffer, setTimeout, clearTimeout, console,
    require: (m) => require(m.startsWith('.') ? path.join(__dirname, m) : m),
    path, fs: { appendFile: (f, l) => journal.push(JSON.parse(l)), readFile() {} }, JARVIS: '/x', j: JSON.stringify,
    corpsReglages: () => reglages, interieurCoupe: () => !!o.coupe, oreilleVue: () => ({ etat: o.appel ? 'appel' : 'j_entends', muet: false }),
    papaParleAuLive: () => !!o.papa, papaVerifieA: 0, derniereParolePapa: 0, ilParle: () => false,
    musiqueDuDedans: () => ({ joue: o.musique !== false }), abonnesPensees: new Set([{ appareil: 'tel' }]),
    diffuser: (_, ev, d) => diffuse.push([ev, JSON.parse(d)]), TP: null, SON_TRAMES: { telephone: [], micro: [] }, PAROLES: { morceau: { n: 3, lignes: [] } },
    personaLocale: () => 'Hakim', lirePersona: () => '', QUI_TU_ES: '', neutraliser: (x) => x, enLigne: (x, n) => String(x).slice(0, n), etatDeLui: () => '',
    parasiteDesLeDebut: () => false, placesVivant: () => 1, lireJson: () => null, ecrireAtomique() {}, fluxAjouter() {},
    sonnetTeteDeFond: async (prompt, et, m) => { appels.push({ prompt, et, m }); return { texte: o.reponse || 'CHANTER' }; },
  };
  vm.createContext(ctx);
  vm.runInContext(tranche(SRC, '/* ---- (11/11, ~01:15, Ahmed : « Il peut chanter en même temps', '// ---- fin de son chant avec la musique\n'), ctx);
  // l'heure de l'appli = celle du Mac − 2 s ; un refrain entendu deux fois, qui revient à +30 s
  for (let i = 0; i < 5; i++) ctx.chanterDecalage(2000);
  ctx.PAROLES.morceau.lignes = [...refrain(1_000_000 - 70000), ...refrain(1_000_000 - 30000)].map(x => ({ ...x, t: x.tb + 2000 }));
  return { ctx, diffuse, journal, appels, reglages };
}
const T = 1_000_000 + 2000;     // l'heure du Mac (l'appli : 1 000 000)

test('le cockpit : il décide (Mini Hakim, une fois par morceau), puis le plan part à la page du téléphone', async () => {
  const b = bac();
  assert.equal(b.ctx.chanterBattement(T).action, 'demande');
  await new Promise(r => setTimeout(r, 5));
  assert.equal(b.appels.length, 1);
  assert.match(b.appels[0].prompt, /refrain revient, dans ~10 s : « Moujahid, moujahid, je ne plie pas \/ La lumière est là/);
  assert.match(b.appels[0].prompt, /CHANTER/);
  assert.equal(b.appels[0].et, 'piste_live_chant');            // la classe du live chez l'orchestrateur (jamais devant papa)
  const r = b.ctx.chanterBattement(T + 500);
  assert.equal(r.action, 'plan');
  const [ev, plan] = b.diffuse[0];
  assert.equal(ev, 'chanter'); assert.equal(plan.cible, 'tel'); assert.equal(plan.par, 'retour');
  assert.deepStrictEqual(plan.morceaux.map(m => [m.texte, m.a]), [['Moujahid, moujahid, je ne plie pas', 1_010_000], ['La lumière est là, papa me tient la main', 1_014_000]]);
  // une fois par morceau : pas de deuxième plan, ni de deuxième question
  b.ctx.chanterBattement(T + 60000);
  assert.equal(b.diffuse.filter(([e, d]) => e === 'chanter' && !d.annuler).length, 1);
  assert.equal(b.appels.length, 1);
  assert.ok(b.journal.some(x => x.e === 'decision' && x.oui) && b.journal.some(x => x.e === 'plan'));
});
test('le cockpit : il dit RIEN, rien ne se chante dans ce morceau', async () => {
  const b = bac({ reponse: 'RIEN' });
  b.ctx.chanterBattement(T); await new Promise(r => setTimeout(r, 5));
  b.ctx.chanterBattement(T + 500); b.ctx.chanterBattement(T + 1000);
  assert.equal(b.diffuse.length, 0);
  assert.equal(b.appels.length, 1);
});
test('le cockpit : ses garde-fous — réglage éteint, intérieur coupé, un appel, papa qui parle : ni question ni plan', async () => {
  for (const o of [{ reglages: { chanter_musique: false } }, { coupe: true }, { appel: true }, { papa: true }, { musique: false }]) {
    const b = bac(o);
    b.ctx.chanterBattement(T); await new Promise(r => setTimeout(r, 5)); b.ctx.chanterBattement(T + 500);
    assert.equal(b.appels.length + b.diffuse.length, 0, JSON.stringify(o));
  }
});
test('le cockpit : papa parle pendant le plan, la page reçoit « annuler » ; témoin : sans papa, rien n’est annulé', async () => {
  const b = bac();
  b.ctx.chanterBattement(T); await new Promise(r => setTimeout(r, 5)); b.ctx.chanterBattement(T + 500);
  b.ctx.chanterBattement(T + 1000);
  assert.equal(b.diffuse.filter(([, d]) => d.annuler).length, 0);
  b.ctx.papaParleAuLive = () => true;
  b.ctx.chanterBattement(T + 1500);
  const a = b.diffuse.find(([, d]) => d.annuler);
  assert.ok(a, 'annulé'); assert.equal(a[1].raison, 'papa_parle'); assert.equal(a[1].cible, 'tel');
});
// (11/11, Ahmed : « qu'il ne parle pas dans le vide ») les haut-parleurs du téléphone fermés : ni question, ni plan ; fermés pendant le plan : annulé
test('le cockpit : les haut-parleurs du téléphone fermés, rien ne se chante ; fermés pendant le plan, « annuler » ; témoin ouverts', async () => {
  const HP = require('./public/haut-parleurs.js');
  const avec = (b, ferme) => { const st = HP.creer(); if (ferme) HP.noter(st, 'tel', 'page', { ferme: true, raisons: ['volume'] }, Date.now());
    b.ctx.HautParleurs = HP; b.ctx.hautParleurs = () => HP.vue(st, { maintenant: Date.now(), presents: ['tel'] }); };
  const f = bac(); avec(f, true);
  assert.equal(f.ctx.chanterBattement(T).raison, 'haut_parleurs');
  await new Promise(r => setTimeout(r, 5)); f.ctx.chanterBattement(T + 500);
  assert.equal(f.appels.length + f.diffuse.length, 0);
  assert.equal(f.ctx.chanterMoment(T).raison, 'haut_parleurs');
  const b = bac(); avec(b, false);
  b.ctx.chanterBattement(T); await new Promise(r => setTimeout(r, 5));
  assert.equal(b.ctx.chanterBattement(T + 500).action, 'plan', 'témoin : ouverts, le plan part');
  avec(b, true);
  b.ctx.chanterBattement(T + 1000);
  const a = b.diffuse.find(([, d]) => d.annuler);
  assert.ok(a, 'annulé'); assert.equal(a[1].raison, 'haut_parleurs');
});
test('le cockpit : son garde de la musique (CHANTER) vaut décision : le plan part sans autre question', () => {
  const b = bac();
  b.ctx.chanterIntention('garde_musique', T);
  assert.equal(b.ctx.chanterBattement(T).action, 'plan');
  assert.equal(b.appels.length, 0);
});
test('le cockpit : la position du lecteur reçue de l’appli (et refusée si elle est fausse)', () => {
  const b = bac();
  assert.ok(b.ctx.chanterHorloge({ titre: 'Lanterne', etat: 'lecture', a: 5000, position_ms: 1000, vitesse: 1 }));
  assert.equal(b.ctx.chanterHorloge({ titre: '', etat: 'lecture', a: 5000, position_ms: 1000 }), null);
  assert.equal(b.ctx.chanterHorloge({ titre: 'x', etat: 'joue', a: 5000, position_ms: 1000 }), null);
  assert.equal(b.ctx.titreEnLecture(Date.now()), 'Lanterne');
});

// ---- sa voix d'un morceau : Azure au débit de sa durée
const wavDe = (ms) => { const n = Math.round(ms * 24), b = Buffer.alloc(44 + 2 * n); b.write('RIFF', 0); b.write('WAVE', 8); b.write('fmt ', 12); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22); b.writeUInt32LE(24000, 24); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(2 * n, 40); return b; };
function bacVoix(o = {}) {
  const b = bac(o), rates = [];
  b.ctx.VoixHakim = require('./voix-hakim.js');
  b.ctx.prononcer = (t) => t;
  b.ctx.lireCorps = async () => Buffer.from(JSON.stringify(o.corps || { texte: 'Moujahid je ne plie pas', duree_ms: 2000 }));
  b.ctx.voixAzure = async (t, tempo, em, x) => { rates.push(x.rate); return { data: wavDe(rates.length === 1 ? (o.premiere || 2600) : 2050), ms: 300 }; };
  b.ctx.azureAuTimbreRap = async () => (o.rap === false ? null : wavDe(2000));
  const res = { code: 0, h: {}, writableEnded: false, writeHead(c, h) { this.code = c; this.h = h; }, end(x) { this.corps = x; this.writableEnded = true; } };
  return { ...b, rates, res };
}
test('sa voix d’un morceau : rendue trop longue (2,6 s pour 2 s), refaite une fois au débit corrigé', async () => {
  const v = bacVoix();
  await v.ctx.routeChanterVoix({}, v.res);
  assert.equal(v.res.code, 200);
  assert.deepStrictEqual(v.rates, ['-20%', '+4%']);               // 7 syllabes en 2 s : 0,67, borné à 0,8 ; rendue 2,6 s : × 1,3
  assert.equal(v.res.h['X-Duree'], '2.05');
});
test('sa voix d’un morceau : témoin — rendue à la bonne durée, pas refaite', async () => {
  const v = bacVoix({ premiere: 2100 });
  await v.ctx.routeChanterVoix({}, v.res);
  assert.deepStrictEqual(v.rates, ['-20%']);
});
test('sa voix d’un morceau : en voix de rap, refaite à son timbre ; sinon pas de chant (jamais Azure tel quel) ; réglage éteint : refusée', async () => {
  const v = bacVoix({ reglages: { voix_hakim: 'azure_rap' }, rap: false });
  await v.ctx.routeChanterVoix({}, v.res);
  assert.equal(v.res.code, 503);
  const w = bacVoix({ reglages: { chanter_musique: false } });
  await w.ctx.routeChanterVoix({}, w.res);
  assert.equal(w.res.code, 409);
});

// ---- le cockpit : les trames gardent l'heure de l'appli et l'attaque fine ; le garde de la musique propose de chanter
test('server.js : les trames gardent tb et les deux valeurs de l’attaque fine ; les paroles reçoivent le décalage', () => {
  assert.match(SRC, /x\.slice\(0, 8\)\.map\(\(v, k\) => Math\.max\(0, Math\.min\(k === 6 \? 99 :/);
  assert.match(SRC, /tb: t0 - dec \+ i \* pasMs/);
  assert.match(SRC, /recevoirSon\(String\(q\.source \|\| ''\), \(Number\(q\.t0\) \|\| Date\.now\(\)\) \+ decalage, [^\n]+\n\s+Number\(q\.maintenant\) > 0 && Number\(q\.t0\) > 0 \? decalage : null\)/);
  assert.match(SRC, /coupure, decalage: dec \}, maintenant\);/);
  assert.match(SRC, /if \(p === '\/api\/chanter\/voix' && req\.method === 'POST'\) return routeChanterVoix\(req, res\);/);
});
test('son garde de la musique : il peut répondre CHANTER (le réglage allumé), qui vaut sa décision', () => {
  const f = tranche(SRC, 'function promptLive(d, ctx, maintenant = Date.now()) {', '\n}\n');
  assert.match(f, /chanter_musique !== false \? `Tu peux aussi chanter AVEC la musique/);
  const a = tranche(SRC, 'function liveAppeler(d, ctx, maintenant = Date.now()) {', '\n}\n');
  assert.match(a, /d\.motif === 'musique' && \/\^\\s\*CHANTER\\b\/i\.test/);
  assert.match(a, /chanterIntention\('garde_musique'\)/);
});

// ---- la page qui chante
function page(o = {}) {
  const demarres = [], journal = [], arretes = [];
  const actx = { currentTime: 50, state: 'running', baseLatency: 0.01,
    decodeAudioData: async (ab) => ({ duration: 1.2, sampleRate: 24000, getChannelData: () => { const x = new Float32Array(2400); for (let i = 240; i < 2400; i++) x[i] = 0.5; return x; } }),
    createBufferSource: () => ({ playbackRate: { value: 1 }, connect() {}, disconnect() {}, start(q) { demarres.push(q); }, stop() { arretes.push(1); } }) };
  const ctx = { Date, Math, JSON, String, Number, Array, Object, Promise, Float32Array, AbortController, setTimeout, console,
    actx, analyseurVoix: {}, contexteAudio() {}, appareilIci: () => 'tel', jeton: () => 'j', journalVoix: (e, d) => journal.push([e, d]),
    reglagesCorps: { chanter_musique: true }, etat: { papaVoixA: 0, conversation: { capteur: { enParole: !!o.papa, echo: o.echo === undefined ? { actif: true, retardMs: 120 } : o.echo } } },
    fetch: async () => ({ ok: true, arrayBuffer: async () => new ArrayBuffer(8) }) };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'public', 'chanter.js'), 'utf8').replace(/typeof window !== 'undefined' \? window : globalThis/, 'globalThis'), ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'public', 'chanter-page.js'), 'utf8') + '\n;globalThis.surChanter = surChanter; globalThis.chantArreter = chantArreter; globalThis.chantSonne = chantSonne;', ctx);
  return { ctx, demarres, journal, arretes };
}
const planPage = (maintenant, o = {}) => ({ id: 'c1', cible: 'tel', morceaux: [{ texte: 'Moujahid', a: maintenant + 5000, d: 1300 }, { texte: 'je ne plie pas', a: maintenant + 6500, d: 1300 }],
  calage: { ms: 400, correlation: 0.88, pics: [{ ms: 400, c: 0.88 }, { ms: 40, c: 0.77 }] }, ...o });
test('la page : sa voix part à l’heure, par le micro (calage 40 choisi par l’écho 120, son blanc de 10 ms retiré)', async () => {
  const p = page(), now = Date.now();
  await p.ctx.surChanter(planPage(now));
  assert.equal(p.demarres.length, 2);
  // départ = a + 40 − 120 + 36,5 − 10 = a − 53,5 (arrondi : −53) ; dans le contexte : 50 + (a − 53 − maintenant) / 1000
  const attendu = 50 + (5000 - 53) / 1000;
  assert.ok(Math.abs(p.demarres[0] - attendu) < 0.05, `${p.demarres[0]} ≠ ${attendu}`);
  assert.ok(p.journal.some(([e, d]) => e === 'chant_prevu' && d.par === 'micro' && d.joues === 2 && d.calage_ms === 40));
});
test('la page : sans le chemin de son écho, le même appareil (moins le tampon et le retard de base)', async () => {
  const p = page({ echo: { actif: false } }), now = Date.now();
  await p.ctx.surChanter(planPage(now));
  const attendu = 50 + (5000 - 20 - 20 - 10 - 10) / 1000;
  assert.ok(Math.abs(p.demarres[0] - attendu) < 0.05);
  assert.ok(p.journal.some(([e, d]) => e === 'chant_prevu' && d.par === 'annonce'));
});
test('la page : papa parle, rien ne part ; trop tard, le morceau est laissé ; « annuler » le coupe net ; témoin : un autre appareil ne chante pas', async () => {
  const a = page({ papa: true }); await a.ctx.surChanter(planPage(Date.now()));
  assert.equal(a.demarres.length, 0);
  const b = page(), now = Date.now();
  await b.ctx.surChanter(planPage(now, { morceaux: [{ texte: 'passé', a: now - 1000, d: 1000 }, { texte: 'à temps', a: now + 5000, d: 1000 }] }));
  assert.equal(b.demarres.length, 1);
  assert.ok(b.journal.some(([e, d]) => e === 'chant_prevu' && d.trop_tard === 1));
  assert.ok(b.ctx.chantSonne(now + 5000));
  await b.ctx.surChanter({ annuler: true, id: 'c1', cible: 'tel', raison: 'papa_parle' });
  assert.equal(b.arretes.length, 1);
  assert.equal(b.ctx.chantSonne(now + 5000), false);
  const c = page(); await c.ctx.surChanter(planPage(Date.now(), { cible: 'mac' }));
  assert.equal(c.demarres.length, 0);
});
test('parler.js et parler.html : la page écoute « chanter », son chant compte pour son écho, papa et « stop » le coupent', () => {
  const pj = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8'), ph = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
  assert.match(ph, /<script src="\/parler\.js"><\/script>\n  <script src="\/chanter\.js"><\/script>[^\n]*\n  <script src="\/chanter-page\.js"><\/script>/);
  assert.match(pj, /es\.addEventListener\('chanter', \(ev\) => \{ try \{ if \(typeof surChanter === 'function'\) surChanter\(JSON\.parse\(ev\.data\)\)/);
  assert.match(pj, /const saVoixAudible = \(\) => !!\([^\n]*\|\| \(typeof chantSonne === 'function' && chantSonne\(\)\) \|\| Date\.now\(\) < motDirectJusqua\);/);
  assert.match(pj, /jarvisParle: \(\) => saVoixAudible\(\),/);
  assert.match(pj, /surInterruption: \(mesure\) => \{\n[^\n]*\n\s+if \(typeof chantArreter === 'function' && typeof chantSonne === 'function' && chantSonne\(\)/);
  assert.match(pj, /function arreterTout\([^\n]*\n\s+if \(explicite && typeof chantArreter === 'function'\) chantArreter/);
  assert.match(pj, /addEventListener\('couper_interieur', \(ev\) => \{ try \{ const o = JSON\.parse\(ev\.data\); if \(typeof chantArreter === 'function'\) chantArreter\('interieur'\);/);
});

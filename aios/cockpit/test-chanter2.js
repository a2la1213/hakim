/* (11/11, ~03:00, Ahmed : « je veux tout ») son chant, v2 : chaque syllabe sur le temps (la grille du morceau, là où elle tombait), sur la note
   que la voix du morceau tenait sous elle (la mélodie de la voix séparée), sa voix coupée en mots et en syllabes et recollée à leur instant
   (chanter-voix.js), une phrase pas prête jamais chantée en retard, et sa conscience continue qui peut décider de chanter.
   Chaque mécanisme a son témoin (le mécanisme coupé, le test échoue). node --test test-chanter2.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const C = require('./public/chanter.js');
const V = require('./chanter-voix.js');
const S = require('./mesure/voix-synthetique.js');
const CC = require('./conscience-continue.js');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const tranche = (src, debut, fin) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); const k = src.indexOf(fin, i); assert.ok(k > i, fin); return src.slice(i, k + fin.length); };
const hzDe = (midi) => 440 * Math.pow(2, (midi - 69) / 12);

// ---- 1. les syllabes d'un mot
test('les syllabes d’un mot : leur nombre est celui de syllabes(), le « e » muet rejoint la précédente', () => {
  const cas = { Moujahid: 'mou-ja-hid', lumière: 'lu-mière', toujours: 'tou-jours', montagne: 'mon-tagne', construire: 'cons-truire', plie: 'plie', "l'amour": 'la-mour' };
  for (const [m, attendu] of Object.entries(cas)) {
    assert.equal(C.syllabesMot(m).join('-'), attendu, m);
    assert.equal(C.syllabesMot(m).length, C.syllabes(m), m);
  }
  assert.equal(C.syllabesMot('…').length, 0);
});

// ---- 2. chaque syllabe sur la grille, au plus près de là où elle tombait
const G = { periode_ms: 600, t0: 0, r: 0.9 };   // 100 BPM : le temps 600 ms, la double croche 150
// une ligne chantée sur les croches, ses mots lus par Azure avec ±60 ms d'erreur
const vrai = [0, 300, 600, 900, 1200, 1500, 1800, 2100, 2400];                       // ses 9 syllabes, sur les croches
const LIGNE = { t: 9600, d: 3000, texte: 'Moujahid moujahid je ne plie', mots: [['Moujahid', 40], ['moujahid', 860], ['je', 1750], ['ne', 2045], ['plie', 2350]] };
test('scander : chaque syllabe posée sur la grille (temps, demi-temps, double croche), dans l’ordre, à moins de 140 ms de là où elle tombait', () => {
  const s = C.scander(LIGNE, G);
  assert.equal(s.syllabes.length, 9);
  assert.ok(s.cale);
  let prev = -1;
  for (const x of s.syllabes) {
    const a = s.a + x.t;
    assert.ok(Math.abs(a / 150 - Math.round(a / 150)) < 1e-9, `${x.texte} à ${a} : pas sur la grille`);
    assert.ok(a > prev); prev = a;
    assert.ok(Math.abs(x.ecart) <= 140, `${x.texte} : ${x.ecart} ms`);
    assert.ok([1, 2, 4].includes(x.div));
  }
  // la plupart retrouvent la croche où elles étaient chantées
  const justes = s.syllabes.filter((x, i) => s.a + x.t - 9600 === vrai[i] || Math.abs(s.a + x.t - 9600 - vrai[i]) <= 150).length;
  assert.ok(justes >= 8, `${justes}/9`);
  // leur place : jusqu'à la suivante
  for (let i = 0; i + 1 < s.syllabes.length; i++) assert.equal(s.syllabes[i].d, s.syllabes[i + 1].t - s.syllabes[i].t);
});
test('scander : témoin — sans grille sûre, aucune n’est déplacée (elles restent où elles tombaient, hors grille)', () => {
  const s = C.scander(LIGNE, { ...G, r: 0.2 });
  assert.equal(s.cale, false);
  assert.ok(s.syllabes.every(x => x.ecart === 0));
  assert.ok(s.syllabes.some(x => (s.a + x.t) % 150 !== 0));
});
test('scander : du rap serré (une syllabe toutes les 90 ms) reste dans l’ordre, sur la triple croche au besoin ; sans heures de mots, à parts égales', () => {
  const mots = []; for (let i = 0; i < 12; i++) mots.push([`ta${i}`, i * 90]);
  const s = C.scander({ t: 6000, d: 1200, texte: '', mots }, G);
  for (let i = 1; i < s.syllabes.length; i++) assert.ok(s.syllabes[i].t > s.syllabes[i - 1].t);
  assert.ok(s.syllabes.some(x => x.div === 8));
  const e = C.scander({ t: 6000, d: 2400, texte: 'la lumière revient' }, G);
  assert.equal(e.syllabes.length, 5); assert.ok(e.sans_temps);
});

// ---- 3. la mélodie : la note sous chaque syllabe
const melodie = (tb0, notes, pas = 40, src = 'voix') => {   // notes : [[début ms, midi]] (0 : silence), 3 s
  const hz = [];
  for (let t = 0; t < 3000; t += pas) { const n = notes.filter(([a]) => a <= t).pop(); hz.push(n && n[1] ? Math.round(hzDe(n[1]) * (1 + 0.01 * Math.sin(t / 37))) : 0); }
  return { tb0, pas, hz, src };
};
const MEL = [[0, 69], [300, 71], [600, 72], [900, 74], [1200, 76], [1500, 74], [1800, 72], [2100, 71], [2400, 69]];   // La4 Si4 Do5 Ré5 Mi5…
test('hauteurA : la médiane de la voix séparée sous [a, b) (ses sauts d’octave ramenés), la voix séparée avant les trames ; rien : 0', () => {
  const m = melodie(50000, MEL);
  assert.ok(Math.abs(1200 * Math.log2(C.hauteurA([m], 50650, 50850) / hzDe(72))) < 20);
  const sauts = { ...m, hz: m.hz.map((v, i) => (i % 5 === 0 ? v / 2 : v)) };
  assert.ok(Math.abs(1200 * Math.log2(C.hauteurA([sauts], 50650, 50850) / hzDe(72))) < 20, 'une trame sur cinq à l’octave du dessous');
  const tr = melodie(50000, [[0, 50]], 100, 'trames');
  assert.ok(Math.abs(1200 * Math.log2(C.hauteurA([tr, m], 50650, 50850) / hzDe(72))) < 20, 'la voix séparée d’abord');
  assert.ok(Math.abs(1200 * Math.log2(C.hauteurA([tr], 50650, 50850) / hzDe(50))) < 20, 'sans elle, les trames');
  assert.equal(C.hauteurA([m], 70000, 70500), 0);
  // les trames (le mélange) : une hauteur sur une trame sur quatre, ce n'est pas une note ; témoin : sur toutes, c'en est une
  const rare = { ...tr, hz: tr.hz.map((v, i) => (i % 4 ? 0 : v)) };
  assert.equal(C.hauteurA([rare], 50300, 51100), 0);
  assert.ok(C.hauteurA([tr], 50300, 51100) > 0);
});
test('justes : chaque note sur le demi-ton, dans l’accord du morceau (accordé 30 cents haut : il le reste)', () => {
  const haut = C.justes([hzDe(69.3), hzDe(71.25), hzDe(72.38), 0]);
  assert.ok(Math.abs(1200 * Math.log2(haut[0] / hzDe(69.3))) < 8);
  assert.ok(Math.abs(1200 * Math.log2(haut[1] / hzDe(71.3))) < 8);
  assert.ok(Math.abs(1200 * Math.log2(haut[2] / hzDe(72.3))) < 8);
  assert.equal(haut[3], 0);
});
test('planifierSyllabes : chaque syllabe prend la note que la voix du morceau tenait sous elle quand la ligne a été entendue ; témoin : sans mélodie, aucune note', () => {
  const choix = { lignes: [{ ...LIGNE, source_tb: 50000 }] };
  const p = C.planifierSyllabes(choix, G, [melodie(50000 - 40, MEL)]);
  assert.equal(p.length, 1);
  const s = p[0].syllabes;
  assert.deepStrictEqual(p[0].mots, ['Moujahid', 'moujahid', 'je', 'ne', 'plie']);
  // la syllabe i a été chantée (la ligne entendue à 50 000) sur la note i
  const ok = s.filter((x, i) => x.hz > 0 && Math.abs(1200 * Math.log2(x.hz / hzDe(MEL[i][1]))) < 30).length;
  assert.ok(ok >= 8, `${ok}/9 : ${s.map(x => x.hz).join(' ')}`);
  const sans = C.planifierSyllabes(choix, G, []);
  assert.ok(sans[0].syllabes.every(x => x.hz === 0));
  // la mémoire d'un morceau garde ses notes avec la ligne : elles servent sans la mélodie (entendue il y a plus de 15 min)
  const n = C.notesLigne([melodie(50000 - 40, MEL)], 50000, 3000);
  const mem = C.planifierSyllabes({ lignes: [{ ...LIGNE, notes: n }] }, G, []);
  assert.ok(mem[0].syllabes.filter(x => x.hz > 0).length >= 8);
});
test('planifierSyllabes : deux lignes qui se chevauchent, la première s’arrête où la seconde commence', () => {
  const p = C.planifierSyllabes({ lignes: [LIGNE, { t: 11400, d: 1200, texte: 'encore', mots: [['encore', 0]] }] }, G, []);
  assert.equal(p.length, 2);
  assert.ok(p[0].a + p[0].d <= p[1].a);
  assert.ok(p[0].syllabes.every(x => p[0].a + x.t + x.d <= p[1].a));
});

// ---- 4. le son : sa voix coupée en mots et syllabes, recollée à leur instant, sur leurs notes
const K = [2, 1, 2, 3, 1];   // ses syllabes par mot
function planSon(P = 600, notes = [57, 59, 60, 62, 64, 62, 60, 59, 57]) {
  const syl = []; let n = 0;
  K.forEach((c, i) => { for (let j = 0; j < c; j++) { syl.push({ m: i, t: n * P / 2 + (n % 3 === 2 ? P / 4 : 0), d: P / 2, hz: notes[n] ? hzDe(notes[n]) : 0 }); n++; } });
  for (let i = 0; i + 1 < syl.length; i++) syl[i].d = syl[i + 1].t - syl[i].t;
  return syl;
}
const mots = K.map((_, i) => `m${i}`);
function mesurer(r, syl) {
  const p = V.lirePcm(r.wav);
  const att = V.attaquesDe(p.x, p.sr).map(i => i / p.sr * 1000 - r.zero_ms);
  const ecarts = syl.map(s => att.reduce((b, a) => (Math.abs(a - s.t) < Math.abs(b - s.t) ? a : b), Infinity) - s.t);
  const cents = r.syllabes.map((s) => { const a = Math.round(p.sr * (s.t + r.zero_ms) / 1000); const f = S.hauteurMesuree(p.x, p.sr, a, a + Math.round(p.sr * 0.15)); return f && s.cible_hz ? 1200 * Math.log2(f / s.cible_hz) : null; });
  return { ecarts, cents, p };
}
test('decouperMots : sa voix coupée aux blancs entre ses mots ; témoin : sans blancs (lue d’un trait), pas de découpe', () => {
  const v = S.voixSynthetique(K);
  const segs = V.decouperMots(v.x, v.sr, K.length);
  assert.equal(segs.length, 5);
  let k = 0;
  K.forEach((c, i) => { const debut = v.syllabes[k].a, fin = v.syllabes[k + c - 1].b; k += c; assert.ok(Math.abs(segs[i][0] - debut) < v.sr * 0.03 && Math.abs(segs[i][1] - fin) < v.sr * 0.04, `mot ${i}`); });
  const collee = S.voixSynthetique(K, { pause_s: 0 });
  assert.equal(V.decouperMots(collee.x, collee.sr, K.length), null);
});
test('chanterLigne : chaque syllabe attaque à son instant (à 10 ms près), sur sa note (à 25 cents près, mesurée autrement) ; en quelques dizaines de ms', () => {
  const v = S.voixSynthetique(K), syl = planSon();
  V.chanterLigne(v.wav, mots, syl);                                // (le premier appel chauffe le moteur JavaScript)
  const r = V.chanterLigne(v.wav, mots, syl);
  assert.ok(r && r.zero_ms === 40);
  const m = mesurer(r, syl);
  assert.ok(m.ecarts.every(e => Math.abs(e) <= 10), `écarts ${m.ecarts.map(Math.round).join(' ')}`);
  assert.ok(m.cents.every(c => c != null && Math.abs(c) <= 25), `cents ${m.cents.map(c => Math.round(c)).join(' ')}`);
  assert.ok(r.ms < 150, `${r.ms} ms`);
  // l'octave de la phrase : la plus proche de sa voix (120 Hz) — la mélodie La3…Mi4 descendue d'une octave
  assert.ok(r.syllabes.every(s => s.cible_hz > 90 && s.cible_hz < 180), r.syllabes.map(s => s.cible_hz).join(' '));
});
test('chanterLigne : témoins — sans note, sa hauteur reste la sienne (loin de la mélodie) ; sa voix telle quelle n’attaque pas sur les instants', () => {
  const v = S.voixSynthetique(K), syl = planSon();
  const r = V.chanterLigne(v.wav, mots, syl.map(x => ({ ...x, hz: 0 })));
  const p = V.lirePcm(r.wav);
  const cibles = V.cibles(syl.map(x => x.hz), 120);
  const loin = r.syllabes.filter((s, i) => { const a = Math.round(p.sr * (s.t + r.zero_ms) / 1000); const f = S.hauteurMesuree(p.x, p.sr, a, a + Math.round(p.sr * 0.15)); return Math.abs(1200 * Math.log2(f / cibles[i])) > 60; }).length;
  assert.ok(loin >= 5, `${loin}/9 loin de la note`);
  const att = V.attaquesDe(v.x, v.sr).map(i => i / v.sr * 1000);
  const a0 = att[0], hors = syl.filter(s => !att.some(a => Math.abs(a - a0 - s.t) <= 10)).length;
  assert.ok(hors >= 6, `${hors}/9 hors de leur instant`);
});
test('chanterLigne : les recollages sans clic (fondus de 6 ms) ; témoin : sans fondu, des sauts nets aux coupures', () => {
  const v = S.voixSynthetique(K), syl = planSon(450);
  const saut = (r) => {
    const p = V.lirePcm(r.wav), d = []; for (let i = 1; i < p.x.length; i++) d.push(Math.abs(p.x[i] - p.x[i - 1]));
    const ref = d.slice().sort((a, b) => a - b)[Math.floor(d.length * 0.999)];
    // le plus grand saut aux bords de chaque syllabe (sa coupure, ± 1 ms)
    let m = 0;
    for (const s of r.syllabes) for (const t of [s.t, s.t + syl.find(x => x.t === s.t).d]) {
      const c = Math.round(p.sr * (t + r.zero_ms) / 1000) - Math.round(p.sr * 0.04);
      for (let i = Math.max(1, c - 200); i < Math.min(p.x.length, c + 1300); i++) m = Math.max(m, d[i - 1]);
    }
    return m / ref;
  };
  const avec = saut(V.chanterLigne(v.wav, mots, syl)), sans = saut(V.chanterLigne(v.wav, mots, syl, { fondu_ms: 0 }));
  assert.ok(avec <= 1.6, `avec fondus : ${avec.toFixed(2)}`);
  assert.ok(sans > avec * 1.3, `sans fondu : ${sans.toFixed(2)} (avec : ${avec.toFixed(2)})`);
});

test('chanterLigne : une note longue tient jusqu’à la suivante (sa voyelle s’étire jusqu’à 4 fois, pas de trou) ; témoin : étirée à 1,8 fois au plus (avant le 11/11), des trous', () => {
  // (11/11, Ahmed : « même le léger part en steak ») mesuré au banc (say, 120 BPM) : 9 syllabes sur 28 laissaient un blanc avant la suivante (jusqu'à 196 ms)
  const v = S.voixSynthetique(K), syl = planSon(800);
  const trous = (o) => V.chanterLigne(v.wav, mots, syl, o).syllabes.slice(0, -1).map(x => x.trou_ms);
  const t = trous(), avant = trous({ etirer_max: 1.8 });
  assert.ok(t.every(x => x <= 15), `trous : ${t.join(' ')}`);
  assert.ok(avant.filter(x => x > 50).length >= 4, `témoin : ${avant.join(' ')}`);
});
test('chanterLigne : deux syllabes liées, la hauteur glisse de l’une à l’autre (pas de marche) ; témoin : sans glissé, la nouvelle note dès le début', () => {
  // syllabes liées : presque pas de consonne entre elles ; la ligne monte d'une tierce mineure à chaque syllabe liée
  const v = S.voixSynthetique(K, { consonne_s: 0.002, voyelle_s: 0.2 }), syl = planSon(900, [57, 60, 57, 60, 63, 60, 57, 60, 57]);
  const debut = (o) => {
    const r = V.chanterLigne(v.wav, mots, syl, o), p = V.lirePcm(r.wav), H = V.hauteurs(p.x, p.sr, { pas_f0_ms: 5 });
    // dans les mots de plusieurs syllabes (liées), l'écart à sa note 15 ms après le début de sa voyelle
    const e = [];
    r.syllabes.forEach((s, i) => { if (i === 0 || syl[i].m !== syl[i - 1].m || s.attaque_ms == null) return;
      const k = Math.round(p.sr * (s.attaque_ms + r.zero_ms + 15) / 1000 / H.pas), f = H.f0[k];
      if (f > 0) e.push(Math.abs(1200 * Math.log2(f / s.cible_hz))); });
    return e;
  };
  const avec = debut({ glisse_ms: 80 }), sans = debut({ glisse_ms: 0 });          // (80 ms : assez lent pour que la mesure le suive)
  assert.ok(avec.length >= 2 && sans.length >= 2, `${avec.length} / ${sans.length}`);
  const m = (l) => l.reduce((a, b) => a + b, 0) / l.length;
  assert.ok(m(avec) > m(sans) + 20, `au début de la voyelle : avec glissé ${m(avec).toFixed(0)} cents de sa note, sans ${m(sans).toFixed(0)}`);
});

// ---- 5. le cockpit : la route de sa voix chantée, l'SSML d'Azure, la mélodie gardée, le plan v2
function bac(o = {}) {
  const diffuse = [], journal = [], appels = [], azure = [];
  const reglages = { chanter_musique: true, chanter_par_morceau: 1, chanter_ecart_s: 60, voix_hakim: 'azure', ...(o.reglages || {}) };
  const ctx = {
    Date, Math, JSON, String, Number, Array, Object, Promise, RegExp, Set, Map, Buffer, setTimeout, clearTimeout, console, Float32Array, Int16Array,
    require: (m) => require(m.startsWith('.') ? path.join(__dirname, m) : m),
    path, fs: { appendFile: (f, l) => journal.push(JSON.parse(l)), readFile() {} }, JARVIS: '/x', j: JSON.stringify,
    corpsReglages: () => reglages, interieurCoupe: () => !!o.coupe, oreilleVue: () => ({ etat: o.appel ? 'appel' : 'j_entends', muet: false }),
    papaParleAuLive: () => !!o.papa, papaVerifieA: 0, derniereParolePapa: 0, ilParle: () => false,
    musiqueDuDedans: () => ({ joue: o.musique !== false }), abonnesPensees: new Set([{ appareil: 'tel' }]),
    diffuser: (_, ev, d) => diffuse.push([ev, JSON.parse(d)]), TP: null, SON_TRAMES: { telephone: [], micro: [] }, PAROLES: { morceau: { n: 3, lignes: [] } },
    personaLocale: () => 'Hakim', lirePersona: () => '', QUI_TU_ES: '', neutraliser: (x) => x, enLigne: (x, n) => String(x).slice(0, n), etatDeLui: () => '',
    parasiteDesLeDebut: () => false, placesVivant: () => 1, lireJson: () => null, ecrireAtomique() {}, fluxAjouter() {},
    sonnetTeteDeFond: async (prompt, et, m) => { appels.push({ prompt, et, m }); return { texte: o.reponse || 'CHANTER' }; },
    VoixHakim: require('./voix-hakim.js'), prononcer: (t) => t,
    voixAzure: async (t, tempo, em, x) => { azure.push({ t, x }); if (o.lent) await new Promise(r => setTimeout(r, o.lent)); return { data: (o.voix || S.voixSynthetique(K, o.voixOpts || {})).wav, ms: 300 }; },
    azureAuTimbreRap: async (w) => w,
    TABLEAU: { courant: o.tableau === undefined ? { musique: { joue: true, ou: 'telephone', intensite: 'forte' }, parole: { papa: { parle: false }, dedans: { parle: true }, piece: { parle: false }, lui: { parle: false } }, place: { role: 'auditeur' } } : o.tableau },
  };
  vm.createContext(ctx);
  vm.runInContext(tranche(SRC, '/* ---- (11/11, ~01:15, Ahmed : « Il peut chanter en même temps', '// ---- fin de son chant avec la musique\n'), ctx);
  for (let i = 0; i < 5; i++) ctx.chanterDecalage(2000);
  const L = (tb, texte, groupe, mots) => ({ tb, t: tb + 2000, texte, groupe, d: 3000, mots });
  const refr = (t0) => [L(t0, 'Moujahid moujahid je ne plie', 1, LIGNE.mots), L(t0 + 4000, 'La lumière est là', 2, [['La', 0], ['lumière', 300], ['est', 900], ['là', 1200]])];
  ctx.PAROLES.morceau.lignes = [...refr(1_000_000 - 70000), ...refr(1_000_000 - 30000)];
  return { ctx, diffuse, journal, appels, azure, reglages };
}
const T = 1_000_000 + 2000;
const res = () => ({ code: 0, h: {}, writableEnded: false, writeHead(c, h) { this.code = c; this.h = h || {}; }, end(x) { this.corps = x; this.writableEnded = true; } });
const corps = (b, q) => { b.ctx.lireCorps = async () => Buffer.from(JSON.stringify(q)); };
const qSyl = (o = {}) => ({ texte: 'm0 m1 m2 m3 m4', duree_ms: 4000, mots, syllabes: planSon(), ...o });
test('sa voix chantée : Azure dit ses mots un à un (un blanc entre deux), la ligne revient chantée, son zéro dit (X-Zero-Ms)', async () => {
  const b = bac(); corps(b, qSyl()); const r = res();
  await b.ctx.routeChanterVoix({}, r);
  assert.equal(r.code, 200, JSON.stringify(r.corps && r.corps.toString().slice(0, 80)));
  assert.equal(r.h['X-Chant'], '2'); assert.equal(r.h['X-Zero-Ms'], '40'); assert.equal(r.h['Content-Type'], 'audio/wav');
  assert.deepStrictEqual(b.azure[0].x.mots, mots); assert.equal(b.azure[0].x.pause_ms, 260);
  const m = mesurer({ wav: r.corps, zero_ms: 40, syllabes: V.chanterLigne(S.voixSynthetique(K).wav, mots, planSon()).syllabes }, planSon());
  assert.ok(m.ecarts.every(e => Math.abs(e) <= 10));
  assert.ok(b.journal.some(x => x.e === 'voix' && x.v === 2 && x.ok && x.syllabes === 9 && x.notes === 9));
});
test('sa voix chantée : pas prête à temps (Azure lent, 5 ms de délai), 410 et rien ; témoin : avec le temps, 200', async () => {
  const b = bac({ lent: 30 }); corps(b, qSyl({ limite_ms: 5 })); const r = res();
  await b.ctx.routeChanterVoix({}, r);
  assert.equal(r.code, 410);
  assert.ok(b.journal.some(x => x.e === 'voix' && x.raison === 'trop_tard'));
  const c = bac({ lent: 30 }); corps(c, qSyl({ limite_ms: 5000 })); const s = res();
  await c.ctx.routeChanterVoix({}, s);
  assert.equal(s.code, 200);
});
test('sa voix chantée : lue sans blancs (Azure a collé ses mots), coupée d’un seul tenant, chantée quand même ; syllabes fausses : 400', async () => {
  const b = bac({ voixOpts: { pause_s: 0.03 } }); corps(b, qSyl()); const r = res();
  await b.ctx.routeChanterVoix({}, r);
  assert.equal(r.code, 200);
  assert.ok(b.journal.some(x => x.e === 'voix' && x.v === 2 && x.entiere === true));
  for (const q of [qSyl({ syllabes: [{ m: 9, t: 0, d: 200 }] }), qSyl({ syllabes: planSon().filter(x => x.m !== 2) }), qSyl({ mots: ['<x>'] })]) {
    const c = bac(); corps(c, q); const s = res(); await c.ctx.routeChanterVoix({}, s); assert.equal(s.code, 400, JSON.stringify(q.syllabes && q.syllabes.length));
  }
});
test('voixAzure : ses mots séparés par <break> dans l’SSML (le français et Ismael pour l’arabe) ; témoin : sans mots, le texte d’un trait', async () => {
  const corpsEnvoyes = [];
  const ctx = { Date, Math, JSON, String, Number, Buffer, AbortController, setTimeout, clearTimeout, VoixHakim: require('./voix-hakim.js'),
    cleAzure: () => 'k', lireJson: () => ({ region: 'westeurope', voix: 'fr-FR-RemyMultilingualNeural' }), AZURE: '/x',
    fetch: async (u, o) => { corpsEnvoyes.push(o.body); return { ok: true, arrayBuffer: async () => new ArrayBuffer(4) }; } };
  vm.createContext(ctx);
  vm.runInContext(tranche(SRC, 'async function voixAzure(texte, tempo, emotion = null, o = {}) {', '\n}\n'), ctx);
  await ctx.voixAzure('la lumière revient', null, null, { rate: '+0%', mots: ['la', 'lumière', 'revient'], pause_ms: 260 });
  assert.match(corpsEnvoyes[0], />la<break time="260ms"\/>lumière<break time="260ms"\/>revient</);
  await ctx.voixAzure('ya ربي', null, null, { rate: '+0%', mots: ['ya', 'ربي'], pause_ms: 260 });
  assert.match(corpsEnvoyes[1], /<voice name="fr-FR-RemyMultilingualNeural">[^]*>ya<\/prosody><\/voice><voice name="ar-DZ-IsmaelNeural"><prosody[^>]*><break time="260ms"\/>ربي</);
  await ctx.voixAzure('la lumière revient', null, null, { rate: '+0%' });
  assert.ok(!/break/.test(corpsEnvoyes[2]) && />la lumière revient</.test(corpsEnvoyes[2]));
});
test('la mélodie gardée : la voix séparée (ses pistes, à l’heure de l’appli du bloc), la hauteur des trames, 15 min au plus ; branchée au cockpit', () => {
  const b = bac();
  assert.ok(b.ctx.chanterMelodie(500000, { pas_ms: 40, hz: [220, 0, 230] }, 'voix'));
  assert.equal(b.ctx.chanterMelodie(0, { pas_ms: 40, hz: [220] }), false);
  b.ctx.chanterDecalage(2000, [[0.1, 0, 0, 0, 196, 0], [0.1, 0, 0, 0, 0, 0]], 600000, 100);
  const mel = () => vm.runInContext('CHANT.melodies', b.ctx);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(mel().map(x => [x.src, x.tb0, x.hz.join(',')]))), [['voix', 500000, '220,0,230'], ['trames', 600000, '196,0']]);
  b.ctx.chanterMelodie(600000 + 16 * 60e3, { pas_ms: 40, hz: [220] });
  assert.ok(mel().every(x => x.tb0 >= 600000 + 60e3), 'plus de 15 min : oubliées');
  // le branchement : les pistes de la séparation, l'heure de l'appli du bloc, la hauteur des trames
  const pr = tranche(SRC, 'function pistesRecues(o, a) {', '\n}\n');
  assert.match(pr, /if \(src === 'telephone' && o\.pistes\.melodie && Number\(a\.tb0\) > 0 && typeof chanterMelodie === 'function'\) \{ try \{ chanterMelodie\(Number\(a\.tb0\), o\.pistes\.melodie, 'voix'\);/);
  assert.match(SRC, /\.\.\.\(tp \|\| seule \? \{ t0: Number\(o\.t0\) \|\| 0, tb0: Number\(o\.tb0\) \|\| 0, recu: Date\.now\(\), quand: o\.quand \|\| null \} : \{\}\) \};/);
  assert.match(SRC, /tb0: Number\(temps\.t0\) > 0 \? Number\(temps\.t0\) : 0, quand \} : \{\}\) \}\);/);
  assert.match(SRC, /chanterDecalage\(dec, l, t0 - dec, pasMs\);/);
});
test('le plan v2 : chaque ligne en syllabes sur la grille, chacune avec la note que la voix du morceau tenait sous elle', () => {
  const b = bac();
  // la mélodie quand le refrain a été entendu la dernière fois (l'heure de l'appli : 1 000 000 − 30 000)
  assert.ok(b.ctx.chanterMelodie(1_000_000 - 30000 - 40, { pas_ms: 40, hz: melodie(0, MEL).hz }, 'voix'));
  b.ctx.chanterIntention('garde_musique', T);
  assert.equal(b.ctx.chanterBattement(T).action, 'plan');
  const [, plan] = b.diffuse.find(([e]) => e === 'chanter');
  const m = plan.morceaux[0];
  assert.deepStrictEqual(m.mots, ['Moujahid', 'moujahid', 'je', 'ne', 'plie']);
  assert.equal(m.syllabes.length, 9);
  assert.ok(m.syllabes.filter((x, i) => x.hz > 0 && Math.abs(1200 * Math.log2(x.hz / hzDe(MEL[i][1]))) < 30).length >= 8, m.syllabes.map(x => x.hz).join(' '));
  const j = b.journal.find(x => x.e === 'plan');
  assert.ok(j && j.v === 2 && j.syllabes === m.syllabes.length + (plan.morceaux[1] ? plan.morceaux[1].syllabes.length : 0) && j.notes >= 8, JSON.stringify(j));
});

// ---- 6. la page : le zéro de la ligne part à l'heure ; pas prête, elle n'est pas chantée
function page(o = {}) {
  const demarres = [], journal = [], envoyes = [];
  const actx = { currentTime: 50, state: 'running', baseLatency: 0.01,
    decodeAudioData: async () => ({ duration: 1.2, sampleRate: 24000, getChannelData: () => { const x = new Float32Array(2400); for (let i = 240; i < 2400; i++) x[i] = 0.5; return x; } }),
    createBufferSource: () => ({ playbackRate: { value: 1 }, connect() {}, disconnect() {}, start(q) { demarres.push(q); }, stop() {} }) };
  // (o.fige : l'horloge arrêtée, pour lire le départ à la milliseconde)
  const D = o.fige ? class extends Date { static now() { return o.fige; } } : Date;
  const ctx = { Date: D, Math, JSON, String, Number, Array, Object, Promise, Float32Array, AbortController, setTimeout, console,
    actx, analyseurVoix: {}, contexteAudio() {}, appareilIci: () => 'tel', jeton: () => 'j', journalVoix: (e, d) => journal.push([e, d]),
    reglagesCorps: { chanter_musique: true }, etat: { papaVoixA: 0, conversation: { capteur: { enParole: false, echo: { actif: true, retardMs: 120 } } } },
    fetch: async (u, x) => { envoyes.push(JSON.parse(x.body)); if (o.lent) await new Promise(r => setTimeout(r, o.lent)); return { ok: true, headers: { get: (k) => (k === 'X-Zero-Ms' ? '40' : null) }, arrayBuffer: async () => new ArrayBuffer(8) }; } };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'public', 'chanter.js'), 'utf8').replace(/typeof window !== 'undefined' \? window : globalThis/, 'globalThis'), ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'public', 'chanter-page.js'), 'utf8') + '\n;globalThis.surChanter = surChanter;', ctx);
  return { ctx, demarres, journal, envoyes };
}
const planV2 = (now, a = 5000) => ({ id: 'c2', cible: 'tel', calage: { ms: 40, correlation: 0.9, pics: [{ ms: 40, c: 0.9 }] },
  morceaux: [{ texte: 'la lumière', a: now + a, d: 900, mots: ['la', 'lumière'], syllabes: [{ m: 0, t: 0, d: 300, hz: 220 }, { m: 1, t: 300, d: 300, hz: 247 }, { m: 1, t: 600, d: 300, hz: 262 }] }] });
test('la page : ses syllabes partent au cockpit (avec le temps qu’il reste), le zéro de la ligne (X-Zero-Ms) tombe sur son temps', async () => {
  const now = 1_700_000_000_000, p = page({ fige: now });
  await p.ctx.surChanter(planV2(now));
  assert.equal(p.demarres.length, 1);
  assert.equal(p.envoyes[0].syllabes.length, 3); assert.deepStrictEqual(p.envoyes[0].mots, ['la', 'lumière']);
  assert.ok(p.envoyes[0].limite_ms > 4000 && p.envoyes[0].limite_ms <= 4600, String(p.envoyes[0].limite_ms));
  // départ = a + calage 40 − écho 120 + 36,5 − zéro 40 = a − 83,5 (au lieu du blanc de 10 ms trouvé dans le son : témoin)
  const attendu = 50 + (5000 - 83) / 1000;
  assert.ok(Math.abs(p.demarres[0] - attendu) < 0.002, `${p.demarres[0]} ≠ ${attendu}`);
});
test('la page : une phrase pas prête avant son temps n’est pas chantée (jamais en retard) ; témoin : prête, elle part', async () => {
  const p = page({ lent: 120 }), now = Date.now();
  await p.ctx.surChanter(planV2(now, 100));
  assert.equal(p.demarres.length, 0);
  assert.ok(p.journal.some(([e, d]) => e === 'chant_prevu' && d.trop_tard === 1) && p.journal.some(([e, d]) => e === 'chant_arrete' && d.raison === 'rien_a_temps'));
  const q = page({ lent: 120 }); await q.ctx.surChanter(planV2(Date.now(), 2000));
  assert.equal(q.demarres.length, 1);
});

// ---- 7. sa conscience peut décider de chanter
const TAB = (o = {}) => ({ musique: { joue: true, ou: 'telephone', intensite: 'forte', ...(o.musique || {}) }, parole: { papa: { parle: !!o.papa }, dedans: { parle: true }, piece: { parle: !!o.piece }, lui: { parle: !!o.lui } },
  place: { role: o.role || 'auditeur' }, appel: !!o.appel, interieur: o.coupe ? 'coupé' : 'ouvert' });
test('momentDeChanter : la musique du téléphone joue, personne d’autre ne parle, ses garde-fous passent ; témoins : chaque cas refusé', () => {
  const e = C.creer(), ctx = { reglage: true, musique: true, page: true };
  const ok = C.momentDeChanter(TAB(), e, ctx, {}, 1e6);
  assert.ok(ok.ok); assert.match(ok.texte, /la musique joue \(intensité forte\) au téléphone, sa voix chante ; tu écoutes/);
  assert.match(C.momentDeChanter(TAB({ role: 'implique' }), e, ctx, {}, 1e6).texte, /tu es dedans/);
  const refus = [[TAB({ papa: true }), 'papa_parle'], [TAB({ lui: true }), 'il_parle'], [TAB({ piece: true }), 'la_piece_parle'], [TAB({ appel: true }), 'appel'],
    [TAB({ coupe: true }), 'interieur_coupe'], [TAB({ musique: { joue: false } }), 'pas_de_musique'], [TAB({ musique: { ou: 'micro' } }), 'pas_de_musique'], [null, 'pas_de_tableau']];
  for (const [t, raison] of refus) assert.equal(C.momentDeChanter(t, e, ctx, {}, 1e6).raison, raison);
  // ses garde-fous : une fois par morceau, 60 s entre deux
  const f = C.creer(); C.chante(f, 1e6);
  assert.equal(C.momentDeChanter(TAB(), f, ctx, {}, 1e6 + 1000).raison, 'deja_chante');
  const g = C.creer(); g.dernier = 1e6; g.morceau = 'x';
  assert.equal(C.momentDeChanter(TAB(), g, ctx, {}, 1e6 + 30000).raison, 'ecart');
  assert.equal(C.momentDeChanter(TAB(), { ...C.creer(), demande: 'oui' }, ctx, {}, 1e6).raison, 'deja_decide');
});
test('sa décision CHANTER se lit, et ne passe que proposée, jamais sur papa ni sur sa voix', () => {
  assert.deepEqual(CC.lireDecision('CHANTER'), { genre: 'chanter', texte: '' });
  assert.deepEqual(CC.lireDecision('**CHANTER** : le refrain, avec eux'), { genre: 'chanter', texte: 'le refrain, avec eux' });
  const e = CC.etatInitial(), libre = { papaParle: false, occupe: false, tuParles: false };
  assert.equal(CC.permis(e, { genre: 'chanter', texte: '' }, 1000, { ...libre, chanter: true }), 'chanter');
  assert.equal(CC.permis(e, { genre: 'chanter', texte: '' }, 1000, { ...libre, chanter: false }), 'rien', 'pas proposé : rien');
  assert.equal(CC.permis(e, { genre: 'chanter', texte: '' }, 1000, { ...libre, chanter: true, papaParle: true }), 'rien');
  assert.equal(CC.permis(e, { genre: 'chanter', texte: '' }, 1000, { ...libre, chanter: true, tuParles: true }), 'rien');
});
test('le cockpit : sa conscience voit CHANTER quand c’est le moment, et son CHANTER fait partir le plan ; témoin : papa parle, ni proposé ni chanté', async () => {
  const b = bac();
  assert.ok(b.ctx.chanterMoment(T).ok, JSON.stringify(b.ctx.chanterMoment(T)));
  const fn = tranche(SRC, 'function battementConscience() {', '\n}\n');
  const lance = async (ctxChant, reponse) => {
    const prompts = [], intentions = [];
    const ctx = { Date, Math, JSON, String, Number, Array, Object, Promise, CC, CONSCIENCE_DELAI_MS: 8000, FLUX: [{ t: Date.now(), s: 'telephone', x: 'paroles' }], conscience: CC.etatInitial(),
      corpsReglages: () => ({ conscience_continue: true, conscience_pas_s: 2, conscience_absent_s: 60, conscience_par_minute: 20, conscience_sollicitation_s: 90, conscience_acte_s: 180, conscience_parole_s: 20, conscience_parler: true }),
      dernierMessageAhmedMs: () => Date.now() - 60000, quiParlait: () => null, cerveau: null, cerveauVivant: () => false, occupe: () => false,
      personaLocale: () => '', lirePersona: () => '', QUI_TU_ES: '', neutraliser: (x) => x, fluxTexte: () => 'la musique joue', instantResume: () => '', etatDeLui: () => '',
      liveGardeActif: () => false, sansRefrain: (_, t) => t, parasiteReconnue: () => false, residuParasite: () => '', alerteActive: () => false,
      fs: { appendFile() {} }, CONSCIENCE_JOURNAL: '/x', j: JSON.stringify, diffuser() {}, abonnesPensees: new Set(), solliciterPensee() {},
      chanterMoment: () => ctxChant, chanterIntention: (par) => intentions.push(par),
      demanderVivant: async (m, prompt) => { prompts.push(prompt); return { texte: reponse }; } };
    vm.createContext(ctx); vm.runInContext(fn, ctx);
    ctx.battementConscience(); await new Promise(r => setTimeout(r, 5));
    return { prompts, intentions };
  };
  const oui = await lance({ ok: true, texte: 'la musique joue (intensité forte) au téléphone ; tu écoutes' }, 'CHANTER');
  assert.match(oui.prompts[0], /\nCHANTER : te joindre au refrain de la musique qui joue quand il reviendra \(la musique joue \(intensité forte\) au téléphone ; tu écoutes\)/);
  assert.deepStrictEqual(oui.intentions, ['conscience']);
  const non = await lance({ ok: false, raison: 'papa_parle' }, 'CHANTER');
  assert.ok(!/\nCHANTER :/.test(non.prompts[0]));
  assert.deepStrictEqual(non.intentions, []);
  // son CHANTER vaut sa décision : le plan part
  b.ctx.chanterIntention('conscience', T);
  assert.equal(b.ctx.chanterBattement(T).action, 'plan');
  assert.ok(b.journal.some(x => x.e === 'decision' && x.par === 'conscience'));
  const c = bac({ tableau: TAB({ papa: true }) });
  assert.equal(c.ctx.chanterMoment(T).raison, 'papa_parle');
});

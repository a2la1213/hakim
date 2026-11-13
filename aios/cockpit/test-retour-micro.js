/* Le retour du micro (11/11, Ahmed : « j'aimerais un bouton pour qu'il n'entende pas le retour du micro (voix des gens du live par le micro), et
   aussi pour qu'il reste justement dans les voix de sa tête ») : node --test test-retour-micro.js
   Le juge (retour-spectre.js) compare chaque morceau du micro au SON de son intérieur ; le cockpit (server.js, le bloc « LE RETOUR DU MICRO »)
   garde ce son, juge les morceaux quand le bouton est allumé, écarte ce qui n'est que le retour et le note ; la page (🔁) et les Réglages.
   Des voix de synthèse (mesure/voix-synthetique.js) : le live (une voix aiguë) revient au micro sans graves, retardé, avec la pièce ; papa (une
   voix grave) parle par-dessus. Chaque mécanisme a son témoin : le même essai, le mécanisme coupé, doit échouer. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const S = require('./retour-spectre.js');
const Dedans = require('./dedans.js');
const { voixSynthetique } = require('./mesure/voix-synthetique.js');

const SR = 16000;
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const HTML = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
const REGLAGES = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); const a = src.lastIndexOf('\n', i) + 1; return src.slice(a, src.indexOf('\n}\n', i) + 2); };

// une voix : des mots de 2 à 4 syllabes à la suite, à sa hauteur ; la durée voulue (s)
function voix(duree, f0, graine) {
  const out = new Float32Array(Math.round(duree * SR)); let k = 0, g = graine;
  while (k < out.length) {
    const mots = []; for (let i = 0; i < 6; i++) { g = (g * 16807) % 2147483647; mots.push(2 + (g % 3)); }
    const v = voixSynthetique(mots, { sr: SR, f0, graine: g, pause_s: 0.12 }).x;
    for (let i = 0; i < v.length && k < out.length; i++, k++) out[k] = v[i];
  }
  return out;
}
const passeHaut = (x, fc, ordre) => { let y = x; for (let o = 0; o < ordre; o++) { const a = 1 / (1 + 2 * Math.PI * fc / SR), z = new Float32Array(y.length); let yp = 0, xp = 0; for (let i = 0; i < y.length; i++) { yp = a * (yp + y[i] - xp); xp = y[i]; z[i] = yp; } y = z; } return y; };
const rms = (x) => { let s = 0; for (const v of x) s += v * v; return Math.sqrt(s / x.length); };
// un live de 30 s joué sur le haut-parleur (sans graves sous 450 Hz), revenu au micro avec 120 ms de retard et la pièce ; papa par-dessus (dB du retour)
function scene({ papaDb = null, retardMs = 120, graine = 3, papaDe = 12, papaA = 16 } = {}) {
  const live = voix(30, 210, graine), papa = voix(30, 105, graine + 77);
  const d = Math.round(retardMs * SR / 1000), ret = new Float32Array(live.length);
  const hp = passeHaut(live, 450, 3);
  for (let i = d; i < ret.length; i++) ret[i] = hp[i - d] + (i >= d + 480 ? 0.25 * hp[i - d - 480] : 0);
  const kr = 0.08 / rms(ret), mic = new Float32Array(live.length);
  const kp = papaDb === null ? 0 : 0.08 * Math.pow(10, papaDb / 20) / rms(papa.subarray(papaDe * SR, papaA * SR));
  for (let i = 0; i < mic.length; i++) mic[i] = ret[i] * kr + (i >= papaDe * SR && i < papaA * SR ? papa[i] * kp : 0) + 0.0005 * Math.sin(i * 1.3);
  // son intérieur : des blocs de 8 s, à l'heure du téléphone (captés 30 ms après le mélange)
  const blocs = []; for (let a = 0; a < live.length; a += 8 * SR) blocs.push({ t0: 1e6 + a / 16 + 30, pcm: live.slice(a, a + 8 * SR) });
  const morceau = (de, a) => ({ pcm: mic.slice(de * SR, a * SR), t0: 1e6 + de * 1000 });
  return { blocs, morceau, temoin: blocs.map(b => ({ ...b, t0: b.t0 - 13000 })) };
}

test('un morceau qui n’est que le live revenu : écarté ; TÉMOIN : le son de l’intérieur d’un autre moment, gardé', () => {
  const s = scene();
  for (const [de, a] of [[3, 7], [18, 22], [24, 27]]) {
    const j = S.juger(s.morceau(de, a), s.blocs, null);
    assert.equal(S.verdict(j).verdict, 'retour', `${de}-${a} s : ${JSON.stringify(j)}`);
    assert.ok(Math.abs(j.retardMs - 90) <= 32, `son retard appris : ${j.retardMs} ms (120 ms de chemin, l'intérieur capté 30 ms après le mélange)`);
    const t = S.juger(s.morceau(de, a), s.temoin, null);
    assert.notEqual(S.verdict(t).verdict, 'retour', `le témoin ${de}-${a} s : ${JSON.stringify(t)}`);
  }
});

test('papa par-dessus le live (0 et − 6 dB) : jamais écarté ; TÉMOIN : sa voix proche ignorée, le même morceau est écarté', () => {
  let temoinsEcartes = 0;
  for (const papaDb of [0, -6]) for (const graine of [3, 5, 9]) {
    const s = scene({ papaDb, graine });
    const m = s.morceau(11.5, 16.5);
    const j = S.juger(m, s.blocs, 90);
    const v = S.verdict(j);
    assert.notEqual(v.verdict, 'retour', `papa à ${papaDb} dB (graine ${graine}) : ${JSON.stringify({ ...j, v })}`);
    assert.ok(j.voixMs >= S.VOIX_MS, `sa voix proche se voit : ${j.voixMs} ms`);
    // le mécanisme coupé : ses trames de voix proche ne comptent plus ; seule elle le garde encore (sa part non expliquée et sa ressemblance
    // ignorées des deux côtés)
    const seule = { part_max: 1, ressemblance: -1 };
    assert.notEqual(S.verdict(j, seule).verdict, 'retour', `sa voix proche, seule, le garde : ${JSON.stringify(j)}`);
    if (S.verdict(j, { ...seule, voix_ms: 1e9 }).verdict === 'retour') temoinsEcartes++;
  }
  assert.equal(temoinsEcartes, 6, `sans ses trames de voix proche, papa serait écarté 6 fois sur 6 (${temoinsEcartes})`);
});

test('papa seul (le live se tait) et l’intérieur absent : gardés', () => {
  const s = scene({ papaDb: 0 });
  const silence = s.blocs.map(b => ({ ...b, pcm: new Float32Array(b.pcm.length) }));
  assert.notEqual(S.verdict(S.juger(s.morceau(12, 16), silence, 90)).verdict, 'retour', 'papa seul');
  assert.equal(S.verdict(S.juger(s.morceau(3, 7), [], 90)).verdict, 'garde', 'sans son intérieur, rien à comparer');
  assert.equal(S.verdict(S.juger(s.morceau(3, 7), s.blocs.filter(b => b.t0 > 1e6 + 10000), 90)).verdict, 'garde', 'l’intérieur ne couvre pas ce moment');
});

/* ---- le cockpit : le bloc « LE RETOUR DU MICRO » de server.js, ses fonctions prises telles quelles ---- */
function cockpit(reglages = {}) {
  const journal = [];
  const cx = { Date, Math, Number, String, JSON, Promise, Buffer, Float32Array, setTimeout, j: JSON.stringify, Dedans, RetourSpectre: S,
    corpsReglages: () => ({ micro_sans_retour: true, ...reglages }), JARVIS_VOIX_DIAGNOSTIC: '/dev/null',
    fs: { appendFileSync: (_f, l) => journal.push(JSON.parse(l)) }, FLUX: [], fluxPrecedents: new Map() };
  vm.createContext(cx);
  const bloc = SRC.slice(SRC.indexOf('const RETOUR = {'), SRC.indexOf('async function routeTranscrire('));
  vm.runInContext(bloc.replace(/^const /gm, 'var ') + '\nthis.R = { retourPcm, retourNoterInterieur, retourJuger, retourRetirerDuFil, retourPapaEntendu, retourActif, RETOUR };', cx);
  return { R: cx.R, journal, cx };
}
function wav(x) {
  const n = x.length, b = Buffer.alloc(44 + 2 * n);
  b.write('RIFF', 0); b.writeUInt32LE(36 + 2 * n, 4); b.write('WAVE', 8); b.write('fmt ', 12); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22);
  b.writeUInt32LE(SR, 24); b.writeUInt32LE(2 * SR, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(2 * n, 40);
  for (let i = 0; i < n; i++) b.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(x[i] * 32767))), 44 + 2 * i);
  return b;
}
const noterBlocs = (R, blocs, o = {}) => { for (const b of blocs) R.retourNoterInterieur(wav(b.pcm), { t0: b.t0, ...o }); };

test('le cockpit : un pur retour écarté et noté (retour_ecarte) ; ses mots vifs sortis du fil ; TÉMOIN : le son d’un autre moment, rien d’écarté', async () => {
  const s = scene();
  const c = cockpit();
  noterBlocs(c.R, s.blocs);
  const m = s.morceau(18, 22);
  c.cx.FLUX.push({ s: 'papa', x: 'mot', cle: '1018000-0' }, { s: 'telephone', x: 'mot', cle: '1018000-0' }, { s: 'papa', x: 'autre', cle: 'autre' });
  const v = await c.R.retourJuger(wav(m.pcm), { t0: m.t0, maintenant: Date.now(), cle: '1018000-0' }, { texte: '[voix 4] on parle de la langue ce soir' });
  assert.equal(v.verdict, 'retour', JSON.stringify(v));
  assert.deepEqual(c.journal.map(l => l.e), ['retour_ecarte']);
  assert.equal(c.journal[0].texte, '[voix 4] on parle de la langue ce soir');
  assert.ok(c.journal[0].ms >= 0 && c.journal[0].attente_ms >= 0 && c.journal[0].duree_ms === 4000);
  assert.equal(c.R.retourRetirerDuFil('1018000-0'), 1, 'seuls les mots de papa de ce morceau');
  assert.deepEqual(c.cx.FLUX.map(o => o.s + ':' + o.cle), ['telephone:1018000-0', 'papa:autre']);
  const t = cockpit();
  noterBlocs(t.R, s.temoin);
  const vt = await t.R.retourJuger(wav(m.pcm), { t0: m.t0, maintenant: Date.now() }, { texte: '[voix 4] on parle de la langue ce soir' });
  assert.notEqual(vt && vt.verdict, 'retour', JSON.stringify(vt));
});

test('le cockpit, bouton éteint : rien (ni son gardé, ni jugement) ; « par l’air » n’est jamais sa référence', async () => {
  const s = scene();
  const off = cockpit({ micro_sans_retour: false });
  noterBlocs(off.R, s.blocs);
  assert.equal(off.R.RETOUR.blocs.length, 0);
  assert.equal(await off.R.retourJuger(wav(s.morceau(18, 22).pcm), { t0: 1e6 + 18000 }, { texte: 'x' }), null);
  const air = cockpit();
  noterBlocs(air.R, s.blocs, { air: true });
  assert.equal(air.R.RETOUR.blocs.length, 0, 'le micro de l’appli n’explique jamais le micro de la page');
  // TÉMOIN : sans ce garde-fou, le même son serait gardé
  const sansGarde = cockpit();
  vm.runInContext("retourNoterInterieur = new Function('return ' + retourNoterInterieur.toString().replace('temps.air || ', ''))();", sansGarde.cx);
  vm.runInContext('this.R.retourNoterInterieur = retourNoterInterieur;', sansGarde.cx);
  noterBlocs(sansGarde.R, s.blocs, { air: true });
  assert.ok(sansGarde.R.RETOUR.blocs.length > 0);
});

test('le cockpit : papa entendu par son oreille des voix, papa qui vient de parler, des mots qui ne sont pas ceux de l’intérieur : gardés, notés', async () => {
  const s = scene();
  const m = s.morceau(18, 22);
  // son oreille des voix : papa (verdict, locuteur « papa ? », ou un morceau du texte resté à papa quand d'autres sont étiquetés)
  const c = cockpit(); noterBlocs(c.R, s.blocs);
  for (const r of [{ texte: 'oui', voix: { verdict: 'ahmed', score: 0.7 } }, { texte: 'x', voix: { verdict: 'plusieurs', locuteurs: ['voix 2', 'papa ?'] } }, { texte: '[voix 2] Tu [papa] nous entends ou pas' }]) {
    const v = await c.R.retourJuger(wav(m.pcm), { t0: m.t0 }, r);
    assert.deepEqual([v.verdict, v.raison], ['garde', 'voix_papa'], JSON.stringify(r));
  }
  assert.equal(c.R.retourPapaEntendu({ texte: '[voix 2] on parle de la langue [voix 5] oui' }), false);
  // papa vient de parler : le morceau d'après (moins de 2 s) est en doute, jamais écarté
  const v2 = await c.R.retourJuger(wav(s.morceau(20, 23).pcm), { t0: 1e6 + 20000 }, { texte: '[voix 4] on parle' });
  assert.deepEqual([v2.verdict, v2.raison], ['doute', 'papa_vient_de_parler'], JSON.stringify(v2));
  assert.equal(c.journal.filter(l => l.e === 'retour_en_doute').length, 1);
  // ses mots ne sont pas ceux de l'intérieur (qui a bien été transcrit jusque-là) : en doute
  // (sans « maintenant » de la page, l'heure du morceau est celle du fil : sa fin, m.t0 + 4 s)
  const d = cockpit(); noterBlocs(d.R, s.blocs);
  const finMac = m.t0 + 4000;
  d.cx.FLUX.push(...['salam', 'bienvenue', 'langue', 'soir', 'dictionnaire'].map((x, i) => ({ s: 'telephone', x, t: finMac - 3000 + i * 600 })));
  const v3 = await d.R.retourJuger(wav(m.pcm), { t0: m.t0 }, { texte: 'fiston coupe le son et écoute moi bien maintenant' });
  assert.deepEqual([v3.verdict, v3.raison], ['doute', 'mots_pas_du_dedans'], JSON.stringify(v3));
  // TÉMOIN : les mêmes mots que l'intérieur, le même morceau est écarté
  const e = cockpit(); noterBlocs(e.R, s.blocs);
  e.cx.FLUX.push(...['salam', 'bienvenue', 'langue', 'soir', 'dictionnaire'].map((x, i) => ({ s: 'telephone', x, t: finMac - 3000 + i * 600 })));
  const v4 = await e.R.retourJuger(wav(m.pcm), { t0: m.t0 }, { texte: 'salam bienvenue la langue ce soir dictionnaire' });
  assert.equal(v4.verdict, 'retour', JSON.stringify(v4));
});

test('le cockpit : l’instant d’un tour fini (rt0) sert au retour seul ; sans instant, rien n’est jugé', async () => {
  const s = scene();
  const c = cockpit(); noterBlocs(c.R, s.blocs);
  const m = s.morceau(18, 22);
  assert.equal(await c.R.retourJuger(wav(m.pcm), {}, { texte: 'x' }), null);
  const v = await c.R.retourJuger(wav(m.pcm), { rt0: String(m.t0), rmaintenant: String(Date.now()), rcle: 'k' }, { texte: '[voix 4] on parle de la langue ce soir' });
  assert.equal(v.verdict, 'retour', JSON.stringify(v));
});

test('le cockpit : les routes le branchent (le jugement avant le fil et la réponse ; la référence ; le réglage éteint par défaut, lu à chaud)', () => {
  const rt = prendre(SRC, 'routeTranscrire');
  // (13/11) jugé et soustrait AVANT la transcription (retourPreparer) : test-retour-soustrait.js
  const iJ = rt.indexOf('await retourPreparer(audio, temps, f)'), iFil = rt.indexOf('integrerAuFil('), iRef = rt.indexOf("if (temps.source === 'telephone' && typeof retourNoterInterieur === 'function') retourNoterInterieur(audio, temps);");
  assert.ok(iJ > 0 && iFil > iJ, 'jugé avant d’entrer au fil');
  assert.ok(iRef > 0 && iRef < rt.indexOf('separerSon('), 'le son de l’intérieur gardé dès son arrivée');
  assert.match(rt, /retourRetirerDuFil\(String\(temps\.cle \|\| temps\.rcle \|\| ''\)\);\n\s*return repondre\(200, \{ texte: '', retour: true \}\);/);
  const rv = prendre(SRC, 'routeVif');
  const iRv = rv.indexOf("if (source === 'telephone' && typeof retourNoterInterieur === 'function') retourNoterInterieur(audio, temps);");
  assert.ok(iRv > 0 && iRv < rv.indexOf('oreilleDemander('), 'la référence avant que l’oreille vive soit occupée');
  assert.ok(rv.indexOf('{ vif: true }') > 0 && rv.indexOf('{ vif: true }') < rv.indexOf('fluxMots('), 'ses mots vifs jugés avant le fil');
  assert.match(SRC, /micro_sans_retour: r\.micro_sans_retour === true,/);
  assert.match(SRC, /if \(typeof q\.micro_sans_retour === 'boolean'\) r\.micro_sans_retour = q\.micro_sans_retour;/);
  assert.match(SRC, /air: u\.get\('par'\) === 'air'/);
  const off = cockpit({ micro_sans_retour: false });
  assert.equal(off.R.retourActif(), false, 'bouton éteint : rien n’est actif');
});

/* ---- la page : le bouton 🔁 à côté de 🎧, l'instant d'un tour fini, la ligne des Réglages ---- */
test('la page : 🔁 à côté de 🎧, visible avec l’appli ; il envoie micro_sans_retour ; tempsRetour seulement bouton allumé', async () => {
  const iT = HTML.indexOf('id="entendreTelephone"'), iS = HTML.indexOf('id="sansRetour"');
  assert.ok(iT > 0 && iS > iT && iS - iT < 1500, 'juste après le bouton 🎧');
  assert.match(HTML, /#sansRetour \{ --c: 167, 139, 250; \}|#telepathieScene, #sansRetour \{/);
  const envoyes = [], el = { hidden: true, attrs: {}, title: '', ecouteurs: {}, setAttribute(k, v) { this.attrs[k] = v; }, addEventListener(t, f) { this.ecouteurs[t] = f; } };
  const cx = { window: { HakimApp: { telepathie() {} } }, reglagesCorps: { micro_sans_retour: false }, humeur() {}, jeton: () => 'j', setTimeout() {}, setInterval() {}, Date,
    $: (id) => (id === 'sansRetour' ? el : null), fetch: async (u, o) => { envoyes.push([u, JSON.parse(o.body)]); return { ok: true }; }, encodeURIComponent, Number };
  vm.createContext(cx);
  const i = PAGE.indexOf('function montrerSansRetour()'), f = PAGE.indexOf('// (03/11, Ahmed : « si j\'écoute une musique', i);
  vm.runInContext(PAGE.slice(PAGE.lastIndexOf('\n', i), f), cx);
  assert.equal(el.hidden, false, 'visible avec l’appli');
  assert.equal(vm.runInContext('tempsRetour({ debut: 1000 }, 5)', cx), '', 'bouton éteint : rien de plus envoyé');
  await el.ecouteurs.click({ stopPropagation() {} });
  assert.deepEqual(envoyes, [['/api/corps/reglages', { micro_sans_retour: true }]]);
  assert.equal(el.attrs['aria-pressed'], 'true');
  assert.match(vm.runInContext('tempsRetour({ debut: 1000 }, 5)', cx), /^&rt0=1100&rmaintenant=\d+&rcle=1000-5$/);
  // la queue d'un tour fini et le tour entier portent son instant pour le retour, jamais t0 (le fil)
  assert.match(PAGE, /tourFini \|\| typeof tempsMorceau !== 'function' \? \(typeof tempsRetour === 'function' \? tempsRetour\(infos, e\.coupe\) : ''\)/);
  assert.match(PAGE, /await transcrireVite\(wav, 'audio\/wav', '', typeof tempsRetour === 'function' \? tempsRetour\(infos, 0\) : ''\)\);/);
  // les Réglages : la ligne, dans « Son oreille du live »
  const live = REGLAGES.slice(REGLAGES.indexOf("{ id: 'live'"), REGLAGES.indexOf("{ id: 'hippocampe'"));
  assert.match(live, /\['micro_sans_retour', '🔁 Le retour du live coupé au micro', [^\]]*'oui'\]/);
});

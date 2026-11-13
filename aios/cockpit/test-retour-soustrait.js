/* Le retour SOUSTRAIT (13/11, Ahmed : « le bouton Sans le retour ne marche pas » ; mesuré : 🔁 allumé, 0 morceau écarté sur 54, chacun gardé
   entier dès que son oreille des voix entendait papa dedans) : node --test test-retour-soustrait.js
   Le retour prédit (le chemin haut-parleur → micro appris sur le son de l'intérieur) est retiré du son du micro, et c'est ce qui reste (papa,
   les gens à côté de lui) qui est transcrit ; un pur retour est écarté ; dans le doute, le son entier. Chaque mécanisme a son témoin : le
   même essai, le mécanisme coupé, doit échouer. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const S = require('./retour-spectre.js');
const Dedans = require('./dedans.js');
const { voixSynthetique } = require('./mesure/voix-synthetique.js');

const SR = 16000;
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); const a = src.lastIndexOf('\n', i) + 1; return src.slice(a, src.indexOf('\n}\n', i) + 2); };
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
const en = (x) => { let s = 0; for (const v of x) s += v * v; return s; };
const db = (a, b) => 10 * Math.log10((a + 1e-12) / (b + 1e-12));
// un live de 30 s sur le haut-parleur (sans graves sous 450 Hz), revenu au micro 120 ms plus tard avec la pièce ; papa par-dessus de papaDe à papaA s
// (dB du retour) ; ses deux parts rendues à part (le banc mesure ce que le masque laisse de chacune)
function scene({ papaDb = null, retardMs = 120, graine = 3, papaDe = 12, papaA = 16 } = {}) {
  const live = voix(30, 210, graine), papa = voix(30, 105, graine + 77);
  const d = Math.round(retardMs * SR / 1000), ret = new Float32Array(live.length);
  const hp = passeHaut(live, 450, 3);
  for (let i = d; i < ret.length; i++) ret[i] = hp[i - d] + (i >= d + 480 ? 0.25 * hp[i - d - 480] : 0);
  const kr = 0.08 / rms(ret), mic = new Float32Array(live.length), partRetour = new Float32Array(live.length), partPapa = new Float32Array(live.length);
  const kp = papaDb === null ? 0 : 0.08 * Math.pow(10, papaDb / 20) / rms(papa.subarray(papaDe * SR, papaA * SR));
  for (let i = 0; i < mic.length; i++) {
    partRetour[i] = ret[i] * kr; partPapa[i] = i >= papaDe * SR && i < papaA * SR ? papa[i] * kp : 0;
    mic[i] = partRetour[i] + partPapa[i] + 0.0005 * Math.sin(i * 1.3);
  }
  const blocs = []; for (let a = 0; a < live.length; a += 8 * SR) blocs.push({ t0: 1e6 + a / 16 + 30, pcm: live.slice(a, a + 8 * SR) });
  const morceau = (de, a) => ({ pcm: mic.slice(de * SR, a * SR), t0: 1e6 + de * 1000 });
  const parts = (de, a) => ({ retour: partRetour.slice(de * SR, a * SR), papa: partPapa.slice(de * SR, a * SR) });
  return { blocs, morceau, parts, temoin: blocs.map(b => ({ ...b, t0: b.t0 - 13000 })) };
}
// ce que le masque laisse de chaque part (dB : négatif = retiré)
function bilan(r, p) {
  const ret = S.appliquer(p.retour, r.G), pa = S.appliquer(p.papa, r.G);
  return { live: db(en(ret), en(p.retour)), papa: db(en(pa), en(p.papa)) };
}

test('papa par-dessus le live (− 6 dB) : le live retiré, papa gardé ; décision « le reste » ; TÉMOIN : l’intérieur d’un autre moment, rien de soustrait', () => {
  for (const graine of [3, 5, 9]) {
    const s = scene({ papaDb: -6, graine });
    const r = S.soustraire(s.morceau(11, 17), s.blocs, 90, { masque: true });
    assert.equal(r.applique, true, JSON.stringify(r.jugement));
    assert.equal(S.decider(r), 'reste', `graine ${graine} : ${r.voixMs} ms de voix proche`);
    const b = bilan(r, s.parts(11, 17));
    assert.ok(b.live <= -12, `graine ${graine} : le live retiré de ${-b.live.toFixed(1)} dB seulement`);
    assert.ok(b.papa >= -2.5, `graine ${graine} : papa abîmé de ${-b.papa.toFixed(1)} dB`);
    assert.ok(r.retireDb >= 3, `ce qui est parti se voit : ${r.retireDb} dB`);
    const t = S.soustraire(s.morceau(11, 17), s.temoin, 90, { masque: true });
    assert.equal(t.applique, false, 'le son d’un autre moment n’explique rien : rien n’est retiré');
    assert.equal(S.decider(t), 'entier');
  }
});

test('TÉMOIN du masque : sa soustraction coupée (α = 0), le live reste entier', () => {
  const s = scene({ papaDb: -6 });
  const r = S.soustraire(s.morceau(11, 17), s.blocs, 90, { masque: true, alpha: 0, porte: false });
  assert.ok(bilan(r, s.parts(11, 17)).live > -1, 'sans soustraction, rien ne part');
});

test('la porte : dans les blancs de papa, le live atténué ne reste pas ; TÉMOIN : sans elle, il en reste bien plus', () => {
  const s = scene({ papaDb: -6, papaDe: 12, papaA: 14 });
  const p = s.parts(10, 18);
  // le live qui reste loin de papa (de 10 à 11,6 s et de 14,4 à 18 s : hors de sa voix et de la garde de la porte)
  const loin = (x) => { let e = 0; for (const [a, b] of [[0, 1.6], [4.4, 8]]) for (let i = a * SR; i < b * SR; i++) e += x[i] * x[i]; return e; };
  const live = (o) => { const r = S.soustraire(s.morceau(10, 18), s.blocs, 90, { masque: true, ...o }); return { live: db(loin(S.appliquer(p.retour, r.G)), loin(p.retour)), papa: bilan(r, p).papa }; };
  const avec = live({}), sans = live({ porte: false });
  assert.ok(avec.live <= sans.live - 10, `la porte retire ${(sans.live - avec.live).toFixed(1)} dB de plus loin de papa (avec ${avec.live.toFixed(1)}, sans ${sans.live.toFixed(1)})`);
  assert.ok(avec.papa >= -3, `papa gardé avec la porte : ${avec.papa.toFixed(1)} dB`);
});

test('le chemin, son lien : sous 150 Hz, où le petit haut-parleur ne rend rien, aucun gain n’est ajusté et la voix de papa reste ; TÉMOIN : sans le lien, des gains y sont ajustés', () => {
  const s = scene({ papaDb: -6, papaDe: 12, papaA: 16 });
  const p = s.parts(9, 19);
  const k1 = Math.round(150 * S.N / SR), k0 = 1;
  const graves = (x) => { const T = S.stft(x); let e = 0; for (let j = 0; j < T.J; j++) for (let k = k0; k < k1; k++) e += T.mod[j * S.NB + k] ** 2; return e; };
  const essai = (o) => { const r = S.soustraire(s.morceau(9, 19), s.blocs, 90, { masque: true, porte: false, ...o }); assert.equal(r.applique, true); return r; };
  const avec = essai({}), sans = essai({ lien: false, plafond: false });
  const ajustes = (r) => { let n = 0; for (let k = k0; k < k1; k++) if (r.H[k] > 0) n++; return n; };
  assert.equal(ajustes(avec), 0, `sous 150 Hz, des gains ajustés malgré le lien : ${ajustes(avec)}`);
  assert.ok(ajustes(sans) >= 3, `le témoin ajuste ses graves : ${ajustes(sans)} bins sur ${k1 - k0}`);
  const g = db(graves(S.appliquer(p.papa, avec.G)), graves(p.papa));
  assert.ok(g >= -0.5, `ses graves gardés : ${g.toFixed(2)} dB`);
});

test('un pur retour : écarté (sans transcription) ; papa vient de parler : le masque seul ; papa seul ou l’intérieur absent : le son entier', () => {
  const s = scene();
  for (const [de, a] of [[3, 7], [18, 22]]) {
    const r = S.soustraire(s.morceau(de, a), s.blocs, 90);
    assert.equal(S.decider(r), 'ecarte', `${de}-${a} s : ${JSON.stringify({ v: r.verdict, voix: r.voixMs })}`);
    assert.equal(S.decider(r, { papaRecent: true }), 'doux', 'papa vient de parler : dans le doute, le masque seul (sa voix qui dépasse y reste)');
    assert.equal(S.voixVue(r), false, 'aucune voix vue : un reste muet sera écarté');
  }
  const p = scene({ papaDb: 0 });
  const silence = p.blocs.map(b => ({ ...b, pcm: new Float32Array(b.pcm.length) }));
  assert.equal(S.decider(S.soustraire(p.morceau(12, 16), silence, 90)), 'entier', 'papa seul');
  assert.equal(S.decider(S.soustraire(p.morceau(3, 7), [], 90)), 'entier', 'sans son intérieur');
  // TÉMOIN de la décision : si le juge ne disait plus « pur retour », le même morceau irait au masque seul, jamais écarté sans transcription
  const r = S.soustraire(s.morceau(3, 7), s.blocs, 90);
  assert.equal(S.decider({ ...r, verdict: { verdict: 'doute' } }), 'doux');
});

test('le son rendu : sans masque (gains à 1), la soustraction rend le son du micro tel quel', () => {
  const s = scene({ papaDb: 0 });
  const m = s.morceau(11, 14);
  const x = S.istft(S.stft(m.pcm), null);
  let e = 0; for (let i = 0; i < x.length; i++) e = Math.max(e, Math.abs(x[i] - m.pcm[i]));
  assert.ok(e < 1e-4, `écart ${e}`);
});

/* ---- le cockpit : retourPreparer (server.js), pris tel quel ---- */
function wav(x) {
  const n = x.length, b = Buffer.alloc(44 + 2 * n);
  b.write('RIFF', 0); b.writeUInt32LE(36 + 2 * n, 4); b.write('WAVE', 8); b.write('fmt ', 12); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22);
  b.writeUInt32LE(SR, 24); b.writeUInt32LE(2 * SR, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(2 * n, 40);
  for (let i = 0; i < n; i++) b.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(x[i] * 32767))), 44 + 2 * i);
  return b;
}
function cockpit(reglages = {}) {
  const journal = [], ecrits = {};
  const cx = { Date, Math, Number, String, JSON, Promise, Buffer, Float32Array, setTimeout, j: JSON.stringify, Dedans, RetourSpectre: S, path, os,
    corpsReglages: () => ({ micro_sans_retour: true, ...reglages }), JARVIS_VOIX_DIAGNOSTIC: '/dev/null', process,
    fs: { appendFileSync: (_f, l) => journal.push(JSON.parse(l)), writeFileSync: (f, b) => { ecrits[f] = b; } }, FLUX: [], fluxPrecedents: new Map() };
  vm.createContext(cx);
  const bloc = SRC.slice(SRC.indexOf('const RETOUR = {'), SRC.indexOf('async function routeTranscrire('));
  vm.runInContext(bloc.replace(/^const /gm, 'var ') + '\nthis.R = { retourNoterInterieur, retourPreparer, retourNoterDecision, RETOUR };', cx);
  return { R: cx.R, journal, ecrits, cx };
}
const noterBlocs = (R, blocs) => { for (const b of blocs) R.retourNoterInterieur(wav(b.pcm), { t0: b.t0 }); };

test('le cockpit : papa par-dessus le live, même quand son oreille l’entendrait : le reste écrit en WAV pour la transcription ; un pur retour : écarté ; noté', async () => {
  const s = scene({ papaDb: -6 });
  const c = cockpit();
  noterBlocs(c.R, s.blocs);
  c.R.RETOUR.prior = 90;
  const m = s.morceau(11, 17);
  const d = await c.R.retourPreparer(wav(m.pcm), { t0: m.t0, maintenant: Date.now(), cle: 'k1' }, '/tmp/jarvis-x.wav');
  assert.equal(d.decision, 'reste', JSON.stringify(d));
  assert.equal(d.fichier, '/tmp/jarvis-x-reste.wav');
  assert.ok(c.ecrits[d.fichier] && c.ecrits[d.fichier].toString('ascii', 0, 4) === 'RIFF', 'le reste, un WAV');
  assert.ok(d.retire_db > 3 && d.voix_ms >= S.VOIX_MS, JSON.stringify(d));
  c.R.retourNoterDecision(d, { texte: 'fiston coupe le son' });
  assert.equal(c.journal.at(-1).e, 'retour_soustrait');
  assert.equal(c.journal.at(-1).fichier, undefined, 'le chemin du fichier n’est pas noté');
  // un pur retour, longtemps après papa : écarté
  const e = await c.R.retourPreparer(wav(s.morceau(24, 28).pcm), { t0: 1e6 + 24000 }, '/tmp/jarvis-y.wav');
  assert.equal(e.decision, 'ecarte', JSON.stringify(e));
  c.R.retourNoterDecision(e, null);
  assert.equal(c.journal.at(-1).e, 'retour_ecarte');
  // juste après papa (moins de 2 s) : le masque seul, sans la porte (« doux »), transcrit comme le reste
  const f = await c.R.retourPreparer(wav(s.morceau(17.2, 20.2).pcm), { t0: 1e6 + 17200 }, '/tmp/jarvis-z.wav');
  assert.deepEqual([f.decision, f.doux, f.raison], ['reste', true, 'papa_vient_de_parler'], JSON.stringify(f));
  assert.ok(c.ecrits['/tmp/jarvis-z-reste.wav'], 'son reste doux écrit');
});

test('le cockpit : bouton éteint, pas d’instant, pas de son de l’intérieur : rien (le son entier)', async () => {
  const s = scene({ papaDb: -6 });
  const off = cockpit({ micro_sans_retour: false });
  noterBlocs(off.R, s.blocs);
  assert.equal(await off.R.retourPreparer(wav(s.morceau(11, 17).pcm), { t0: 1e6 + 11000 }), null);
  const c = cockpit();
  assert.equal(await c.R.retourPreparer(wav(s.morceau(11, 17).pcm), { t0: 1e6 + 11000 }), null, 'sans son de l’intérieur');
  noterBlocs(c.R, s.blocs);
  assert.equal(await c.R.retourPreparer(wav(s.morceau(11, 17).pcm), {}), null, 'sans instant');
});

/* ---- la route : le retour soustrait AVANT la transcription ; le filtre de ton micro ne perd jamais un morceau ---- */
test('la route : soustrait avant la transcription, écarté sans transcription, le reste transcrit, ses voix sur le son entier, le repli au son entier', () => {
  const rt = prendre(SRC, 'routeTranscrire');
  const iP = rt.indexOf('retourS = await retourPreparer(audio, temps, f)'), iT = rt.indexOf('transcriptionsEnAttente++');
  assert.ok(iP > 0 && iT > iP, 'jugé et soustrait avant la transcription');
  assert.match(rt, /if \(retourS && retourS\.decision === 'ecarte'\) \{[^]*?return repondre\(200, \{ texte: '', retour: true \}\);/);
  assert.match(rt, /const fichierPapa = resteRetour \|\| voixSeulePapa \|\| f;/);
  assert.match(rt, /const fVoix = resteRetour && fAzure === resteRetour \? f : fAzure;/);
  assert.match(rt, /op: 'prevoir', fichier: fVoix/);
  assert.match(rt, /op: 'bloc', fichier: fVoix/);
  assert.match(rt, /raison: 'reste_muet'/);
  assert.match(rt, /!partie && !retourS\.voix_vue\) \{\n\s*retourNoterDecision\(\{ \.\.\.retourS, decision: 'ecarte', raison: 'reste_muet_sans_voix' \}/);
  assert.ok(!/await retourJuger\(audio, temps, r\)/.test(rt), 'l’ancien jugement après coup, qui gardait tout dès que papa était entendu, est retiré');
  assert.ok(rt.indexOf('fs.unlink(resteRetour') > 0, 'le reste effacé après usage');
});

test('le filtre de ton micro (Demucs) qui échoue ou lève une erreur : le son entier, jamais le morceau perdu ; TÉMOIN : sans son filet, l’erreur remonte', async () => {
  const rt = prendre(SRC, 'routeTranscrire');
  const a = rt.indexOf('  let voixSeulePapa = null, attendueFiltre = null'), b = rt.indexOf('  const resteRetour =');
  const bloc = rt.slice(a, b);
  const essai = async (code, separerSon) => {
    const cx = { Date, Promise, setTimeout, fs: { writeFileSync() {}, appendFileSync() {}, unlink() {} }, j: JSON.stringify, JARVIS_VOIX_DIAGNOSTIC: '/dev/null', FILTRE_VOIX_MS: 50,
      corpsReglages: () => ({ micro_voix_seule: true }), separerSon, retourActif: () => false, temps: { source: '' }, ext: '.wav', f: '/tmp/a.wav', audio: Buffer.alloc(10),
      filtreVoixPermis: () => true, filtreVoixNoter: () => false };
    vm.createContext(cx);
    return vm.runInContext(`(async () => { ${code.replace(/return repondre\([^;]*;/g, 'return null;')}\n return { voixSeulePapa }; })()`, cx);
  };
  const leve = () => { throw new Error('séparation en panne'); };
  assert.deepEqual(await essai(bloc, leve), { voixSeulePapa: null });
  assert.deepEqual(await essai(bloc, (_f, _s, o) => o.quand(null)), { voixSeulePapa: null });
  assert.deepEqual(await essai(bloc, (_f, _s, o) => o.quand('/tmp/v.wav')), { voixSeulePapa: '/tmp/v.wav' });
  await assert.rejects(essai(bloc.replace('}).catch(() => null);', '});'), leve), /séparation en panne/);
});

test('le filtre de ton micro, son disjoncteur : 4 échecs sur 5, il se repose 60 s puis réessaie ; TÉMOIN : sans disjoncteur, il attendrait encore', () => {
  const cx = { Date, Math };
  vm.createContext(cx);
  const a = SRC.indexOf('const FILTRE_VOIX = {'), b = SRC.indexOf('\n}\n', SRC.indexOf('function filtreVoixNoter(')) + 3;
  const code = SRC.slice(a, b).replace(/^const /gm, 'var ');
  vm.runInContext(code + '\nthis.F = { filtreVoixPermis, filtreVoixNoter, FILTRE_VOIX };', cx);
  const { filtreVoixPermis, filtreVoixNoter } = cx.F;
  const t = 1e9;
  for (const ok of [true, false, false, false]) assert.equal(filtreVoixNoter(ok, t), false);
  assert.equal(filtreVoixPermis(t), true, '3 échecs sur 4 : il essaie encore');
  assert.equal(filtreVoixNoter(false, t), true, '4 échecs sur 5 : il se repose');
  assert.equal(filtreVoixPermis(t + 59000), false);
  assert.equal(filtreVoixPermis(t + 60000), true, 'au bout de 60 s, il réessaie');
  // un filtre qui marche ne se repose jamais
  const c2 = { Date, Math }; vm.createContext(c2); vm.runInContext(code + '\nthis.F = { filtreVoixPermis, filtreVoixNoter };', c2);
  for (let i = 0; i < 20; i++) c2.F.filtreVoixNoter(i % 3 !== 0, t);
  assert.equal(c2.F.filtreVoixPermis(t), true);
  // TÉMOIN : la route sans son disjoncteur attendrait le filtre quand même
  const rt = prendre(SRC, 'routeTranscrire');
  assert.match(rt, /if \(filtreVoulu && !filtreVoixPermis\(\)\)/);
  const sans = code.replace('return maintenant >= FILTRE_VOIX.coupeJusqua', 'return true').replace('maintenant >= FILTRE_VOIX.coupeJusqua', 'true');
  const c3 = { Date, Math }; vm.createContext(c3); vm.runInContext(sans + '\nthis.F = { filtreVoixPermis, filtreVoixNoter };', c3);
  for (let i = 0; i < 5; i++) c3.F.filtreVoixNoter(false, t);
  assert.equal(c3.F.filtreVoixPermis(t + 1000), true, 'sans disjoncteur, il attendrait encore');
});

test('le repli au son entier d’un reste muet : seulement quand la porte ET le juge ont vu une voix ; TÉMOIN : un pur retour où seule la porte « voit » (ses erreurs de prédiction) n’y repasse pas', () => {
  assert.equal(S.voixVue({ voixMs: 200, jugement: { voixMs: 80 } }), true);
  assert.equal(S.voixVue({ voixMs: 200, jugement: { voixMs: 0 } }), false, 'la porte seule');
  assert.equal(S.voixVue({ voixMs: 0, jugement: { voixMs: 200 } }), false, 'le juge seul');
  // sur la scène : papa par-dessus le live, les deux le voient ; le pur retour, non
  const s = scene({ papaDb: -6 });
  assert.equal(S.voixVue(S.soustraire(s.morceau(11, 17), s.blocs, 90)), true);
  assert.equal(S.voixVue(S.soustraire(s.morceau(24, 28), s.blocs, 90)), false);
});

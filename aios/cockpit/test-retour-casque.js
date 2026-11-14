/* (14/11, Ahmed : « un retour de voix au casque pendant que j'enregistre, avec des préréglages et de l'autotune comme je veux, de façon
   par défaut ») la chaîne du retour (public/studio-retour-dsp.js) jugée sur des voix de synthèse à vérité connue (mesure/retour-casque-banc.js),
   la hauteur de sortie lue par un autre détecteur (la somme des harmoniques) ; un témoin par mécanisme : coupé, son test échoue.
   node --test test-retour-casque.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const DSP = path.join(__dirname, 'public', 'studio-retour-dsp.js'), BANC = path.join(__dirname, 'mesure', 'retour-casque-banc.js');
// le banc et la chaîne, frais, avec un mécanisme coupé (ou aucun)
function charger(coupe = '') {
  delete require.cache[DSP]; delete require.cache[BANC];
  globalThis.RETOUR_COUPE = coupe;
  try { return { B: require(BANC), R: require(DSP) }; } finally { delete globalThis.RETOUR_COUPE; delete require.cache[DSP]; delete require.cache[BANC]; }
}
const { B, R } = charger();
const SR = B.SR, dMin = Math.round(0.0005 * SR);

/* ---------- les mesures que jugent les tests (chacune refaite avec un mécanisme coupé pour son témoin) ---------- */
// les notes fausses : l'écart à la note visée, note installée (après 450 ms)
function fausses(b, niveau) {
  const x = b.synth(b.CAS.fausses), { y } = b.passer(x, b.seulAutotune(niveau)), p = b.pistes('fausses', x, y, 0);
  return b.CAS.fausses.filter(s => s.voise).map(s => {
    const vrai = b.cents(s.f0) / 100, cible = b.visee(vrai), ici = p.filter(q => q.seg === s && q.dans >= 0.45);
    return { entree: (vrai - cible) * 100, sortie: b.med(ici.map(q => q.sortie - cible * 100)), p90: b.quantile(ici.map(q => Math.abs(q.sortie - cible * 100)), 0.9), cible };
  });
}
function justes(b, niveau) {
  const x = b.synth(b.CAS.justes), { y } = b.passer(x, b.seulAutotune(niveau));
  return { droite: b.intacte(x, y, dMin, 0, Math.round((b.CAS.justes[0].d + b.CAS.justes[1].d) * SR)), tout: b.intacte(x, y, dMin) };
}
function vibrato(b, niveau) {
  const x = b.synth(b.CAS.vibrato), { y } = b.passer(x, b.seulAutotune(niveau)), p = b.pistes('vibrato', x, y, 0).filter(q => q.dans >= 0.45);
  const amp = (k) => (b.quantile(p.map(q => q[k]), 0.95) - b.quantile(p.map(q => q[k]), 0.05)) / 2;
  return { entree: amp('entree'), sortie: amp('sortie'), centre: b.med(p.map(q => q.sortie)) - 5500 };
}
function ecarts(b, cas, reglages) {
  const x = b.synth(b.CAS[cas] || cas), { y, lat } = b.passer(x, reglages);
  if (!b.CAS[cas]) b.CAS._ad = cas;
  const p = b.pistes(b.CAS[cas] ? cas : '_ad', x, y, 0), d = p.map(q => Math.abs(q.sortie - q.entree));
  return { med: b.med(d), p95: b.quantile(d, 0.95), max: Math.max(...d), part20: d.filter(v => v > 20).length / d.length, lat, intacte: b.intacte(x, y, dMin) };
}
function latences(b, niveau) {
  const o = b.passer(b.synth([{ d: 0.1, voise: 0, amp: 0 }, { d: 1.0, f0: b.hz(52.35), f1: b.hz(52.35), voise: 1, amp: 0.1 }, { d: 0.2, voise: 0, amp: 0 },
    { d: 0.6, f0: b.hz(48), f1: b.hz(48), voise: 1, amp: 0.1 }, { d: 0.05, voise: 0, amp: 0 }]), b.seulAutotune(niveau));
  const ms = o.lat.map(v => v / SR * 1000), t = (k) => k * 128 * 8 / SR;
  const pendant = ms.filter((_, k) => t(k) > 0.35 && t(k) < 1.05), apres = ms.filter((_, k) => t(k) > 1.35 && t(k) < 1.85);
  return { moy: pendant.reduce((a, v) => a + v, 0) / pendant.length, max: Math.max(...pendant), apres: Math.max(...apres) };
}
// une syllabe courte chantée 40 cents au-dessus d'une note (sans glissé) : jamais touchée (rien avant la tenue)
const courte = (d) => [{ d: 0.1, voise: 0, amp: 0 }, { d, f0: B.hz(52.4), f1: B.hz(52.4), voise: 1, amp: 0.1 }, { d: 0.1, voise: 0, amp: 0 }];
// le temps (ms) entre le début de la voix détectée et la première correction, sur une note tenue fausse de 40 cents
function debutCorrection(b, r, niveau) {
  const x = b.synth([{ d: 0.1, voise: 0, amp: 0 }, { d: 0.4, f0: b.hz(52.4), f1: b.hz(52.4), voise: 1, amp: 0.1 }, { d: 0.05, voise: 0, amp: 0 }]);
  const st = r.creer(SR), y = new Float64Array(x.length);
  r.regler(st, r.vecteur(b.seulAutotune(niveau)));
  let voix = null;
  for (let p = 0; p < x.length; p += 32) {
    r.traiter(st, x.subarray(p, p + 32), y.subarray(p, p + 32), 32);
    const e = r.etat(st);
    if (e.voise && voix === null) voix = p;
    if (e.correction_cents !== 0) return (p - voix) / SR * 1000;
  }
  return Infinity;
}

/* ---------- les réglages ---------- */
test('les préréglages, le vecteur (l’ordre d’Android), la gamme comme chant.gamme, le niveau du mix', () => {
  assert.deepEqual(Object.keys(R.PRESETS), ['sans_effet', 'rap_propre', 'autotune_naturel', 'autotune_effet']);
  assert.equal(R.DEFAUT, 'rap_propre');
  const v = R.vecteur(R.preset('autotune_effet'), { tempo: 140, diap_cents: 7, tonalite: 'A minor' });
  assert.equal(v.length, 44);
  assert.equal(v[R.V.AT], 1); assert.equal(v[R.V.FORCE], 1); assert.equal(v[R.V.APLATIR], 0.85); assert.equal(v[R.V.RETUNE], 15);
  assert.equal(v[R.V.DIAP], 7); assert.ok(Math.abs(v[R.V.DELAI_S] - 60 / 140 * 0.75) < 1e-12, 'le délai calé sur le tempo (croche pointée)');
  assert.deepEqual(v.slice(R.V.GAMME), [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1], 'la mineur : les blanches');
  const l = R.vecteur(R.preset('autotune_naturel'));
  assert.equal(l[R.V.FORCE], 0.4); assert.equal(l[R.V.RETUNE], 80); assert.equal(l[R.V.TENUE], 120); assert.equal(l[R.V.GLISSE], 400);
  assert.deepEqual(l.slice(R.V.GAMME), new Array(12).fill(1), 'tonalité inconnue : les 12 demi-tons');
  assert.equal(R.vecteur(R.preset('rap_propre'))[R.V.AT], 0);
  // la gamme : les mêmes classes que chant.gamme (anamnese/jarvis/chant.py)
  assert.deepEqual(R.gamme('C major'), [0, 2, 4, 5, 7, 9, 11]); assert.deepEqual(R.gamme('F# minor'), [1, 2, 4, 6, 8, 9, 11]);
  assert.deepEqual(R.gamme('Am'), [0, 2, 4, 5, 7, 9, 11]); assert.deepEqual(R.gamme('B♭ min'), [0, 1, 3, 5, 6, 8, 10]);
  assert.deepEqual(R.gamme('Ré mineur'), [0, 2, 4, 5, 7, 9, 10]); assert.deepEqual(R.gamme('La mineur'), [0, 2, 4, 5, 7, 9, 11]);
  assert.equal(R.gamme('').length, 12); assert.equal(R.gamme('n’importe quoi').length, 12);
  // borné : rien d'absurde n'entre (le disque, une autre page)
  const b = R.borner({ coupe_bas_hz: 9999, eq: { grave_db: -99 }, comp: { actif: 'oui', ratio: 0 }, reverb: 5, autotune: { niveau: 'robot', force: 7, tonalite: '<b>A minor</b>' }, volume_db: 80 });
  assert.equal(b.coupe_bas_hz, 400); assert.equal(b.eq.grave_db, -12); assert.equal(b.comp.actif, false); assert.equal(b.comp.ratio, 1); assert.equal(b.reverb, 1);
  assert.equal(b.autotune.niveau, ''); assert.equal(b.autotune.force, 1); assert.ok(!/[<>]/.test(b.autotune.tonalite)); assert.equal(b.volume_db, 12);
  // ce que j'entends = ce que j'obtiens : le niveau de l'autotune du mix
  assert.equal(R.niveauMix(R.preset('autotune_naturel')), 'leger'); assert.equal(R.niveauMix(R.preset('autotune_effet')), 'fort');
  assert.equal(R.niveauMix(R.preset('rap_propre')), '');
  assert.equal(R.niveauMix({ autotune: { niveau: 'leger', force: 0.9 } }), 'fort', 'réglé à la main : le niveau le plus proche');
  assert.equal(R.niveauMix({ autotune: { niveau: 'fort', force: 0.3 } }), 'leger');
});

/* ---------- l'autotune : des notes fausses ramenées, une voix juste intacte, le rap jamais miaulé ---------- */
test('des notes chantées fausses : le fort les pose sur la note à 3 cents près, le léger les rapproche de 40 %', () => {
  const f = fausses(B, 'fort');
  for (const n of f) { assert.ok(Math.abs(n.sortie) <= 3, `fort : ${n.entree.toFixed(0)} → ${n.sortie} cents`); assert.ok(n.p90 <= 5, `fort p90 ${n.p90}`); }
  assert.equal(f[2].cible % 12, 2, 'do#3 + 30 cents (hors gamme, pas net) : ré3, la gamme départage');
  assert.equal(f[3].cible % 12, 6, 'fa#3 + 20 cents (hors gamme mais net) : il reste le sien');
  for (const n of fausses(B, 'leger')) assert.ok(Math.abs(n.sortie - 0.6 * n.entree) <= 4, `léger : ${n.entree.toFixed(0)} → ${n.sortie} (attendu ${(0.6 * n.entree).toFixed(0)})`);
});

test('une voix juste sort intacte, à l’échantillon près (léger et fort ; le vibrato gardé par le léger)', () => {
  for (const niveau of ['leger', 'fort']) assert.ok(justes(B, niveau).droite > 100, `${niveau} : note droite`);
  assert.ok(justes(B, 'leger').tout > 100, 'léger : la note avec son vibrato aussi');
  const v = vibrato(B, 'leger');
  assert.ok(v.sortie >= 0.95 * v.entree, `léger : vibrato gardé (${v.entree.toFixed(1)} → ${v.sortie.toFixed(1)})`);
});

test('le fort aplatit le vibrato (moins de 55 % gardé) et pose son centre sur la note', () => {
  const v = vibrato(B, 'fort');
  assert.ok(v.sortie <= 0.55 * v.entree, `vibrato ${v.entree.toFixed(1)} → ${v.sortie.toFixed(1)} cents`);
  assert.ok(Math.abs(v.centre) <= 3, `centre ${v.centre}`);
});

test('le rap : jamais touché par le léger ni par « Rap propre » ; une syllabe courte fausse n’est jamais corrigée', () => {
  const l = ecarts(B, 'rap', B.seulAutotune('leger'));
  assert.equal(l.part20, 0, 'léger : aucune trame déplacée de plus de 20 cents'); assert.ok(l.p95 <= 3, `léger p95 ${l.p95}`);
  assert.ok(l.intacte > 100, 'léger : le rap sort intact');
  const p = ecarts(B, 'rap', R.preset('rap_propre'));
  assert.ok(p.p95 <= 3, `Rap propre : la hauteur ne bouge pas (p95 ${p.p95})`);
  assert.ok(Math.max(...p.lat) === dMin, 'Rap propre : 0,5 ms de retard, jamais plus');
  // (trop courte pour le juge : on vérifie qu'elle sort à l'échantillon près)
  assert.ok(ecarts(B, courte(0.05), B.seulAutotune('fort')).intacte > 100, 'fort : une syllabe fausse de 50 ms sort intacte');
  assert.ok(ecarts(B, courte(0.11), B.seulAutotune('leger')).intacte > 100, 'léger : une syllabe fausse de 110 ms sort intacte');
});

test('rien n’est corrigé avant la tenue de la note (120 ms en léger, 60 ms en fort)', () => {
  const l = debutCorrection(B, R, 'leger'), f = debutCorrection(B, R, 'fort');
  // (la tenue se compte en trames de 2,5 ms, la première comprise)
  assert.ok(l >= 117 && l < 400, `léger : ${l} ms`); assert.ok(f >= 57 && f < 200, `fort : ${f} ms`);
});

test('le léger respecte un glissé (portamento de 3 demi-tons en 300 ms)', () => {
  const g = ecarts(B, 'glisse', B.seulAutotune('leger'));
  assert.ok(g.p95 <= 3, `p95 ${g.p95}`);
});

test('la latence de l’algorithme : 0,5 ms, sauf sur une note corrigée (au plus une période), et elle revient à 0,5 ms', () => {
  const T = 1000 / B.hz(52.35);
  for (const niveau of ['leger', 'fort']) {
    const l = latences(B, niveau);
    assert.ok(l.moy <= 0.5 + T / 2 + 0.6, `${niveau} : moyenne ${l.moy.toFixed(2)} ms (demi-période ${(T / 2).toFixed(2)})`);
    assert.ok(l.max <= 0.5 + T + 0.3, `${niveau} : pire ${l.max.toFixed(2)} ms (période ${T.toFixed(2)})`);
    assert.ok(Math.abs(l.apres - 0.5) < 0.01, `${niveau} : après le silence, une note juste à ${l.apres.toFixed(2)} ms`);
  }
});

test('la chaîne entière : rien n’attend (le retard reste 0,5 ms sans autotune), la sortie bornée, le coût', () => {
  const x = B.synth(B.CAS.justes), t = Date.now();
  const o = B.passer(x, { ...R.preset('autotune_effet'), autotune: { niveau: 'fort', tonalite: 'C major' }, volume_db: 12 });
  const duree = (Date.now() - t) / 1000;
  let m = 0; for (const v of o.y) m = Math.max(m, Math.abs(v));
  assert.ok(m <= 1, 'jamais au-delà de 0 dBFS (les oreilles)');
  assert.ok(duree < x.length / SR / 3, `le calcul : ${(duree * 1000).toFixed(0)} ms pour ${(x.length / SR).toFixed(1)} s (moins d'un tiers du temps réel)`);
  // la mesure : des clics par la sortie, la voix coupée, l'entrée enregistrée 0,5 s avant le premier
  const st = R.creer(SR); R.regler(st, R.vecteur(R.preset('rap_propre')));
  R.mesureDemarrer(st, 4, 0.2);
  const tot = Math.round((0.5 + 4 * 0.2 + 0.4) * SR), e = new Float64Array(tot).fill(0.5), s = new Float64Array(tot);
  R.traiter(st, e, s, tot);
  const r = R.mesureResultat(st);
  assert.equal(r.x.length, tot); assert.equal(r.debut, 0.5); assert.equal(r.n, 4);
  const premier = s.findIndex(v => Math.abs(v) > 1e-6);
  assert.ok(Math.abs(premier - 0.5 * SR) <= 1, `le premier clic à 0,5 s (${premier})`);
  assert.ok(s.slice(0, premier).every(v => v === 0), 'pas de voix pendant la mesure');
});

/* ---------- les témoins : chaque mécanisme coupé, son test échoue ---------- */
test('témoins : coupé, chaque mécanisme fait échouer son test', () => {
  const T = 1000 / B.hz(52.35);
  const cas = {
    deplacement: (b) => fausses(b, 'fort').every(n => Math.abs(n.sortie) <= 3),
    gamme: (b) => fausses(b, 'fort')[2].cible % 12 === 2 && Math.abs(fausses(b, 'fort')[2].sortie) <= 3,
    nette: (b) => Math.abs(fausses(b, 'fort')[3].sortie) <= 3,
    zone_morte: (b) => justes(b, 'leger').tout > 100,
    aplatir: (b) => { const v = vibrato(b, 'fort'); return v.sortie <= 0.55 * v.entree; },
    prediction: (b) => { const v = vibrato(b, 'fort'); return v.sortie <= 0.55 * v.entree; },
    tenue: (b) => ecarts(b, courte(0.05), b.seulAutotune('fort')).intacte > 100,
    'tenue (léger)': (b) => debutCorrection(b, b === B ? R : charger('tenue').R, 'leger') >= 117,
    glisse: (b) => ecarts(b, 'glisse', b.seulAutotune('leger')).p95 <= 3,
    retour_court: (b) => Math.abs(latences(b, 'fort').apres - 0.5) < 0.01,
  };
  for (const [k, f] of Object.entries(cas)) {
    assert.ok(f(B), `${k} : passe avec le mécanisme`);
    assert.ok(!f(charger(k.split(' ')[0]).B), `${k} : coupé, le test devait échouer`);
  }
  assert.ok(T > 0);
});

/* ---------- les vecteurs partagés avec Android : à jour ---------- */
test('les vecteurs partagés (mesure/retour-vecteurs.txt) sont ceux de la chaîne d’aujourd’hui', () => {
  const f = path.join(__dirname, 'mesure', 'retour-vecteurs.txt'), g = path.join(__dirname, 'mesure', 'retour-vecteurs.pcm');
  assert.ok(fs.existsSync(f) && fs.existsSync(g), 'node mesure/retour-casque-banc.js --vecteurs');
  const v = B.vecteurs();
  assert.equal(fs.readFileSync(f, 'utf8'), v.texte, 'les vecteurs ont changé : node mesure/retour-casque-banc.js --vecteurs, puis copier dans hakim-android');
  assert.ok(fs.readFileSync(g).equals(v.pcm), 'l’entrée des vecteurs a changé');
});

/* ---------- le cockpit : le défaut partagé, la latence mesurée par sortie, la tonalité d'une instru, la prise qui garde ce qu'il entendait,
   le mix et la piste qui reprennent son autotune (dossiers jetables : jamais la vraie file du studio) ---------- */
const http = require('http');
const os = require('os');
const { execFileSync } = require('child_process');
const S = require('./studio.js');
const FFMPEG = '/usr/local/bin/ffmpeg';
const lireCorps = (req, max) => new Promise((ok) => { const m = []; let n = 0; req.on('data', c => { n += c.length; if (n <= max) m.push(c); }); req.on('end', () => ok(n > max ? null : Buffer.concat(m))); });
async function appel(srv, methode, chemin, corps, type = 'application/json') {
  const r = await fetch(`http://127.0.0.1:${srv.address().port}${chemin}`, { method: methode, headers: { 'Content-Type': type },
    body: corps === undefined ? undefined : (Buffer.isBuffer(corps) ? corps : JSON.stringify(corps)) });
  let j = null; try { j = JSON.parse(Buffer.from(await r.arrayBuffer()).toString()); } catch (_) {}
  return { statut: r.status, j };
}
test('le cockpit : le réglage par défaut partagé, la latence par sortie, la tonalité, la prise et le mix qui gardent l’autotune entendu', { skip: !fs.existsSync(FFMPEG) }, async () => {
  const racine = fs.mkdtempSync(path.join(os.tmpdir(), 'retour-casque-test-'));
  const jarvis = path.join(racine, 'jarvis'), ch = path.join(jarvis, 'chansons'), wav = path.join(racine, 'son.wav');
  fs.mkdirSync(path.join(ch, 'studio'), { recursive: true });
  execFileSync(FFMPEG, ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=220:d=2', '-ar', '48000', wav]);
  const lances = [], cmds = [], tons = [];
  let projet = { id: 'PJ-20261114-090000-abcd', rev: 3, titre: 'Essai', tonalite: 'A minor', pistes: [{ id: 't1', role: 'instru', fichier: 'pistes/instru.wav' }] };
  const studio = S.creer({ jarvis, lireCorps, appeler: (a, q) => { lances.push([a, q]); return { ok: true, id: 'J-1' }; },
    tonalite: (f) => { tons.push(f); return { ok: true, tonalite: 'B minor', diap_cents: 3 }; },
    projet: (q) => {
      cmds.push(q);
      if (q.action === 'importer') { projet = { ...projet, rev: projet.rev + 1, pistes: [...projet.pistes, { id: 't2', role: 'voix_papa', fichier: 'pistes/voix.wav', origine: path.basename(q.fichier) }] }; return { ok: true, projet }; }
      if (q.action === 'regler') { if (q.rev !== projet.rev) return { ok: false, erreur: 'changé' }; projet = { ...projet, rev: projet.rev + 1, pistes: projet.pistes.map(t => (t.id === q.piste ? { ...t, ...q.reglages } : t)) }; return { ok: true, projet }; }
      return { ok: false };
    } });
  const srv = await new Promise((ok) => { const x = http.createServer((req, res) => studio.route(req, res, new URL(req.url, 'http://x').pathname)); x.listen(0, '127.0.0.1', () => ok(x)); });
  try {
    // rien de gardé : « Rap propre » en attendant
    let r = await appel(srv, 'GET', '/api/studio/retour');
    assert.equal(r.statut, 200); assert.equal(r.j.defaut, null); assert.deepEqual(r.j.mesures, {}); assert.equal(r.j.defaut_preset, 'rap_propre');
    // le défaut : borné par la chaîne, gardé dans le dossier du studio (partagé téléphone / Mac)
    r = await appel(srv, 'POST', '/api/studio/retour/defaut', { reglages: { ...R.preset('autotune_naturel'), reverb: 7, autotune: { niveau: 'leger', tonalite: 'A minor', vitesse_ms: 60, force: 0.5 } }, par: 'telephone' });
    assert.equal(r.statut, 200); assert.equal(r.j.defaut.reverb, 1); assert.equal(r.j.defaut.autotune.vitesse_ms, 60);
    assert.equal((await appel(srv, 'GET', '/api/studio/retour')).j.defaut.autotune.force, 0.5, 'relu tel quel, par l’autre appareil');
    assert.ok(fs.existsSync(path.join(ch, 'studio', 'retour.json')));
    assert.equal((await appel(srv, 'POST', '/api/studio/retour/defaut', { reglages: 'non' })).statut, 400);
    // la latence mesurée, par sortie
    r = await appel(srv, 'POST', '/api/studio/retour/mesure', { cle: 'web|Steinberg UR22mkII', nom: 'Steinberg UR22mkII', ms: 13.6, ecart_ms: 0.4, n: 8, total: 8, plateforme: 'web' });
    assert.equal(r.statut, 200); assert.equal(r.j.mesures['web|Steinberg UR22mkII'].ms, 13.6);
    assert.equal((await appel(srv, 'POST', '/api/studio/retour/mesure', { cle: 'n’importe', ms: 3 })).statut, 400);
    assert.equal((await appel(srv, 'POST', '/api/studio/retour/mesure', { cle: 'web|x', ms: 'rien' })).statut, 400);
    // la tonalité d'une instru, comme le mix la trouve
    r = await appel(srv, 'POST', '/api/studio/importer?nom=Prod.wav', fs.readFileSync(wav), 'audio/wav');
    const instru = r.j.f;
    r = await appel(srv, 'GET', `/api/studio/tonalite?f=${encodeURIComponent(instru)}`);
    assert.deepEqual([r.statut, r.j.tonalite, r.j.diap_cents], [200, 'B minor', 3]);
    assert.equal((await appel(srv, 'GET', '/api/studio/tonalite?f=../../etc/passwd')).statut, 404);
    // une prise avec le retour allumé : ce qu'il entendait part avec elle ; le mix reprend son autotune et sa tonalité
    const retour = JSON.stringify({ allume: true, preset: 'autotune_effet', reglages: R.preset('autotune_effet'), niveau_mix: 'fort', tonalite: 'B minor', diap_cents: 3,
      latence_ms: 13.6, algo_ms: 3.4, plateforme: 'web', garder_autotune: true });
    r = await appel(srv, 'POST', `/api/studio/prise?instru=${encodeURIComponent(instru)}&latence=0&retour=${encodeURIComponent(retour)}`, fs.readFileSync(wav), 'audio/wav');
    assert.equal(r.statut, 200);
    const id = r.j.id, fiche = JSON.parse(fs.readFileSync(path.join(ch, 'studio', 'prises', `${id}.json`), 'utf8'));
    assert.deepEqual([fiche.retour.preset, fiche.retour.niveau_mix, fiche.retour.tonalite, fiche.retour.latence_ms], ['autotune_effet', 'fort', 'B minor', 13.6]);
    assert.equal(fiche.retour.reglages.autotune.niveau, 'fort');
    assert.deepEqual((await appel(srv, 'GET', '/api/studio/etat')).j.prises[0].retour, { preset: 'autotune_effet', niveau_mix: 'fort', tonalite: 'B minor' });
    await appel(srv, 'POST', '/api/studio/mixer', { prise: id });
    assert.deepEqual([lances[0][1].params.autotune, lances[0][1].params.tonalite], ['fort', 'B minor'], 'rien de dit : l’autotune entendu au casque');
    await appel(srv, 'POST', '/api/studio/mixer', { prise: id, autotune: false });
    assert.deepEqual([lances[1][1].params.autotune, lances[1][1].params.tonalite], [false, ''], 'papa dit non : sans');
    await appel(srv, 'POST', '/api/studio/mixer', { prise: id, autotune: 'leger', tonalite: 'D major' });
    assert.deepEqual([lances[2][1].params.autotune, lances[2][1].params.tonalite], ['leger', 'D major']);
    // sans retour : rien de plus dans la prise
    r = await appel(srv, 'POST', `/api/studio/prise?instru=${encodeURIComponent(instru)}&latence=0&retour=`, fs.readFileSync(wav), 'audio/wav');
    assert.equal(JSON.parse(fs.readFileSync(path.join(ch, 'studio', 'prises', `${r.j.id}.json`), 'utf8')).retour, undefined);
    // la prise posée dans un projet : l'autotune entendu devient celui de SA piste (la nouvelle), avec la version vue
    r = await appel(srv, 'POST', `/api/studio/projet-prise?id=${projet.id}&debut=4&latence=0&retour=${encodeURIComponent(retour)}`, fs.readFileSync(wav), 'audio/wav');
    assert.equal(r.statut, 200); assert.equal(r.j.autotune, 'fort');
    const reg = cmds.find(q => q.action === 'regler');
    assert.deepEqual([reg.piste, reg.reglages, reg.rev], ['t2', { autotune: 'fort' }, 4]);
    assert.equal(r.j.projet.pistes.find(t => t.id === 't2').autotune, 'fort');
    // papa ne veut pas que le mix reprenne l'autotune entendu
    const n = cmds.length;
    r = await appel(srv, 'POST', `/api/studio/projet-prise?id=${projet.id}&debut=8&latence=0&retour=${encodeURIComponent(JSON.stringify({ ...JSON.parse(retour), garder_autotune: false }))}`, fs.readFileSync(wav), 'audio/wav');
    assert.equal(r.j.autotune, ''); assert.ok(!cmds.slice(n).some(q => q.action === 'regler'));
  } finally { srv.close(); studio.arreter(); fs.rmSync(racine, { recursive: true, force: true }); }
});

test('la page : la section du retour, le rappel du bouton MIX, ses scripts, l’AudioWorklet au plus bas, jamais par Bluetooth', () => {
  const lire = (f) => fs.readFileSync(path.join(__dirname, f), 'utf8');
  const h = lire('public/studio.html'), js = lire('public/studio-retour.js'), page = lire('public/studio-page.js'), pistes = lire('public/studio-pistes.js');
  for (const id of ['retourCarte', 'rtMix', 'rtAllumer', 'rtPreset', 'rtEtat', 'rtAt', 'rtTon', 'rtVitesse', 'rtForce', 'rtVolume', 'rtAvance', 'rtGarder', 'rtGarderAt', 'rtLatence', 'rtMesurer'])
    assert.match(h, new RegExp(`id="${id}"`), id);
  assert.match(h, /tourne le bouton <b>MIX<\/b> de ta UR22mkII <b>à fond vers DAW<\/b>/);
  assert.match(h, /<script src="\/studio-pistes\.js"><\/script>\n  <script src="\/studio-retour-dsp\.js"><\/script>\n  <script src="\/studio-retour\.js"><\/script>/);
  assert.match(page, /latencyHint: 0/);
  assert.match(js, /for \(const f of \['\/studio-calage\.js', '\/studio-retour-dsp\.js', '\/studio-retour-worklet\.js'\]\) await c\.audioWorklet\.addModule\(f\);/);
  assert.match(js, /new AudioWorkletNode\(c, 'retour-voix'/);
  assert.match(page, /retour: retourPrise \}\);/); assert.match(pistes, /retour: retourPrise \}\);/);
  // le refus : Bluetooth et haut-parleurs, dans le navigateur et dans l'appli (le genre de la sortie)
  const refus = new Function('window', 'document', 'localStorage', `${js.slice(js.indexOf('  const BLUETOOTH'), js.indexOf('  const TONS'))}; const App = window.App; const C = window.StudioCalage;
    ${js.slice(js.indexOf('  function refus('), js.indexOf('  // dans le navigateur : quand le micro'))}; return refus;`);
  const web = refus({ StudioCalage: require('./public/studio-calage.js') });
  assert.match(web({ nom: 'AirPods Pro (Bluetooth)' }), /Bluetooth/); assert.match(web({ nom: 'Haut-parleurs MacBook Air' }), /larsen/);
  assert.equal(web({ nom: 'Steinberg UR22mkII' }), ''); assert.equal(web({ nom: 'Casque externe' }), '');
  const appli = refus({ App: {}, StudioCalage: require('./public/studio-calage.js') });
  assert.match(appli({ cle: 'appli|bluetooth:Galaxy Buds3', nom: 'Galaxy Buds3 (Bluetooth)' }), /Bluetooth/);
  assert.match(appli({ cle: 'appli|haut_parleur', nom: 'le haut-parleur' }), /larsen/);
  assert.equal(appli({ cle: 'appli|usb:UR22mkII', nom: 'UR22mkII (USB)' }), '');
  // le worklet : la chaîne et le canal de la carte, chargés avant lui dans le même espace
  const w = lire('public/studio-retour-worklet.js');
  assert.match(w, /registerProcessor\('retour-voix', RetourVoix\)/); assert.match(w, /globalThis\.StudioCalage\.canal\(sampleRate/);
});

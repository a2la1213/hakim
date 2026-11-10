/* Son écho dans une enceinte (10/11, 07:05, Ahmed : « quand il parle dans des haut-parleurs Bluetooth, il entend son écho, qui le coupe ») :
   node --test test-echo-enceinte.js
   Le micro (public/conversation.js, le vrai détecteur) apprend le chemin de sa voix jusqu'à lui (son retard, sa force) ; la page
   (public/parler.js, le bloc « son écho dans une enceinte ») met en doute ce qui ressemble à sa voix retardée et ne le coupe que si c'est
   vraiment papa. Faux micro, faux temps : sa voix est une suite de syllabes, son écho la même, retardée, plus faible, avec la traîne de la
   pièce ; papa, une autre voix. Les témoins rejouent les mêmes scènes, le mécanisme retiré : ils doivent échouer. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const CONV = fs.readFileSync(path.join(__dirname, 'public', 'conversation.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
// le mécanisme retiré : un chemin jamais appris (le témoin)
const INERTE = "const echoA = { noter() {}, apprendre() {}, chemin: () => ({ actif: false, retardMs: 0, confiance: 0, gain: 0 }), reference: () => 0, ressemblance: () => ({ r: 0, libre: true }) };";
const SANS_CHEMIN = CONV.replace('const echoA = creerEcho();', INERTE);

function charger(src = CONV) {
  let t = 1e6, noeud = null, hasard = 12345;
  const ctx = { console, Float32Array, ArrayBuffer, DataView, Math, Blob, Date: { now: () => t },
    URL: { createObjectURL: () => 'blob:capteur', revokeObjectURL() {} },
    navigator: { mediaDevices: { getUserMedia: async () => ({ getTracks: () => [], getAudioTracks: () => [] }) } },
    AudioWorkletNode: class { constructor() { noeud = this; this.port = { postMessage() {}, onmessage: null }; } connect() {} disconnect() {} } };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  const actx = { sampleRate: 16000, destination: {}, audioWorklet: { addModule: async () => {} },
    createMediaStreamSource: () => ({ connect() {}, disconnect() {} }), createGain: () => ({ gain: { value: 1 }, connect() {}, disconnect() {} }) };
  // une fenêtre de 20 ms au niveau voulu (un son, et un souffle léger)
  const pousser = (rms) => {
    const f = new Float32Array(320), a = rms * Math.SQRT2;
    for (let i = 0; i < 320; i++) { hasard = (hasard * 16807) % 2147483647; f[i] = a * Math.sin(i * 0.37) + (hasard / 2147483647 - 0.5) * 0.002; }
    t += 20; noeud.port.onmessage({ data: f });
  };
  return { C: ctx.Conversation, actx, pousser };
}
// sa voix : des syllabes de 100 à 260 ms, des creux, des mots ; son niveau à la sortie, de 0,04 à 0,14
function voix(n, graine) {
  let s = graine; const r = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
  const v = [];
  while (v.length < n) {
    const syl = 5 + Math.floor(r() * 8), niv = 0.04 + r() * 0.1;
    for (let i = 0; i < syl; i++) v.push(niv * (0.7 + 0.3 * Math.sin(i / syl * Math.PI)));
    const creux = r() < 0.2 ? 8 + Math.floor(r() * 10) : 2 + Math.floor(r() * 4);
    for (let i = 0; i < creux; i++) v.push(0);
  }
  return v.slice(0, n);
}
// une scène : 3 s de silence (la conversation est ouverte), 10 s de sa voix, puis 2 s ; au micro, son écho (retard D ms, force G) et papa
async function scene({ src = CONV, D = 300, G = 0.6, graine = 11, papa = null } = {}) {
  const b = charger(src), FIN = 500, sa = voix(600, graine), lag = Math.round(D / 20);
  let i = 0, echo = 0;
  const ev = { signaux: [], debuts: [], fins: 0 };
  const cap = await b.C.demarrer({ ctx: b.actx, patienceMs: () => 1000, jarvisParle: () => i > 0 && i < FIN, niveauSortie: () => (i > 0 && i < FIN ? sa[i] : 0),
    surInterruption: (m) => ev.signaux.push({ ...m, i }), surDebut: () => ev.debuts.push(i), surFin: () => ev.fins++ });
  for (let k = 0; k < 150; k++) b.pousser(0.003);
  for (i = 0; i < 600; i++) {
    const s0 = i - lag >= 0 && i - lag < FIN ? sa[i - lag] : 0;
    echo = Math.max(s0, echo * 0.55);                                     // la pièce : une traîne qui décroît
    const p = papa ? papa(i) : 0;
    b.pousser(Math.sqrt((G * echo) ** 2 + p ** 2 + 0.003 ** 2));
  }
  return { ...ev, chemin: cap.echo, FIN };
}

/* ---- la page : le bloc « son écho dans une enceinte », joué à part ---- */
function lapage() {
  let t = 1_800_000_000_000;
  const journal = [], interruptions = [];
  const ctx = {
    Math, JSON, String, Array, Object, Number, Set, Error,
    Date: class extends Date { constructor(...a) { super(...(a.length ? a : [t])); } static now() { return t; } },
    etat: { saVoix: [], voixVerdict: null, conversation: null },
    paroleRecente: [], lecteur: { actif: true },
    saVoixAudible: () => true, journalVoix: (e, d) => journal.push([e, d]), setInterval: () => 0,
    motsEntendusDepuis: (conv) => (conv && conv.ecrit ? `${conv.ecrit.confirme || ''} ${conv.ecrit.vif || ''}` : '').trim(),
  };
  vm.createContext(ctx);
  const debut = PAGE.indexOf('SON ÉCHO DANS UNE ENCEINTE'), fin = PAGE.indexOf('// fin de « son écho dans une enceinte »');
  assert.ok(debut > 0 && fin > debut, 'le bloc est dans parler.js');
  vm.runInContext(PAGE.slice(PAGE.lastIndexOf('/* ----', debut), fin)
    + 'this.f = { ressembleASonEcho, echoEnDoute, trancherDoute, tourDEcho, jugerEcho, sesMotsSonnes, noterCheminEcho };', ctx);
  const dit = (texte) => { ctx.paroleRecente.push({ t, suite: texte.toLowerCase().split(/\s+/) }); };
  const conv = { ecrit: { confirme: '', vif: '' }, optionsCapteur: { surInterruption: (m) => interruptions.push(m) } };
  return { ctx, f: ctx.f, journal, interruptions, conv, dit, avancer: (ms) => { t += ms; }, maintenant: () => t };
}
const SA_PHRASE = "Oui papa, je regarde mes réglages de sortie maintenant, et je te dis ce que je trouve dans mes mesures";

test('le chemin de sa voix est appris : son retard (0 à 500 ms) et sa force ; des écouteurs : aucun chemin', () => {
  const { C } = charger();
  for (const D of [0, 160, 300, 500]) {
    const e = C.creerEcho(), sa = voix(700, 11), lag = D / 20;
    let echo = 0;
    for (let i = 0; i < 150; i++) e.noter(0, 0.003);
    for (let i = 0; i < 600; i++) { const s0 = i - lag >= 0 ? sa[i - lag] : 0; echo = Math.max(s0, echo * 0.55); e.noter(sa[i], Math.sqrt((0.6 * echo) ** 2 + 0.003 ** 2)); e.apprendre(i * 20, 0.003); }
    const c = e.chemin(600 * 20);
    assert.ok(c.actif, `retard ${D} ms : chemin appris`);
    assert.ok(Math.abs(c.retardMs - D) <= 40, `retard ${D} ms : appris ${c.retardMs} ms`);
    assert.ok(c.gain > 0.3 && c.gain < 0.8, `sa force (0,6) : apprise ${c.gain.toFixed(2)}`);
  }
  const e = C.creerEcho(), sa = voix(700, 3);
  for (let i = 0; i < 600; i++) { e.noter(sa[i], 0.003); e.apprendre(i * 20, 0.003); }   // des écouteurs : le micro n'entend rien de lui
  assert.equal(e.chemin(12000).actif, false, 'sans écho, rien ne change');
});

test('sa traîne dans l’enceinte n’ouvre plus de « tour de papa » ; le témoin (sans chemin) en ouvrait', async () => {
  let avec = 0, sans = 0;
  for (let g = 0; g < 8; g++) {
    const a = await scene({ D: 300, G: 0.3, graine: 11 + g * 7 }), b = await scene({ src: SANS_CHEMIN, D: 300, G: 0.3, graine: 11 + g * 7 });
    avec += a.debuts.filter(i => i >= a.FIN).length; sans += b.debuts.filter(i => i >= b.FIN).length;
  }
  assert.equal(avec, 0, 'après sa voix, son écho ne passe plus pour toi');
  assert.ok(sans >= 4, `le témoin : sans le chemin appris, sa traîne ouvrait ${sans} tours sur 8 phrases`);
});

test('son seul écho (retardé, aussi fort que sa voix) ne le coupe plus : chaque signal est mis en doute ; le témoin le coupait', async () => {
  const { f } = lapage();
  const coupe = (m) => Number(m.clarte) >= 1.8 && !f.ressembleASonEcho(m);   // une voix claire (le réglage par défaut) qui n'est pas mise en doute
  let avec = 0, sans = 0, signaux = 0;
  for (const [D, G] of [[0, 1], [250, 1], [350, 1], [500, 0.8]]) for (let g = 0; g < 6; g++) {
    const a = await scene({ D, G, graine: 11 + g * 7 }), b = await scene({ src: SANS_CHEMIN, D, G, graine: 11 + g * 7 });
    signaux += a.signaux.length; avec += a.signaux.filter(coupe).length; sans += b.signaux.filter(coupe).length;
  }
  assert.equal(avec, 0, `aucun de ses ${signaux} signaux d’écho ne le coupe`);
  assert.ok(sans >= 5, `le témoin : sans le chemin, ${sans} coupures par son seul écho`);
});

test('papa qui parle vraiment sur sa voix : le signal arrive, et il ne ressemble pas à son écho (coupé net, comme avant)', async () => {
  const { f } = lapage();
  let nets = 0, vus = 0;
  for (let g = 0; g < 10; g++) {
    const pv = voix(400, 1000 + g * 13);
    const a = await scene({ D: 300, G: 0.6, graine: 11 + g * 7, papa: (i) => (i >= 300 && i < 450 ? 0.3 / 0.09 * pv[i - 300] : 0) });
    const m = a.signaux.find(x => x.i >= 300 && x.i < 380);              // dans les 1,6 s
    if (m) { vus++; if (!f.ressembleASonEcho(m)) nets++; }
  }
  assert.ok(vus >= 8, `papa entendu sur sa voix (${vus}/10)`);
  assert.ok(nets >= 7, `coupé net, sans doute (${nets}/${vus})`);
});

test('mis en doute : ses propres mots revenus ne le coupent jamais, et ce tour-là est laissé (jamais transcrit)', () => {
  const p = lapage();
  p.dit(SA_PHRASE); p.avancer(1500);
  const mesure = { enceinte: true, ressemblance: 0.9, retard_ms: 280, clarte: 2.5 };
  assert.equal(p.f.echoEnDoute(p.conv, mesure), true, 'mis en doute : ni coupé net, ni « il te coupe »');
  let annule = 0;
  p.conv.capteur = { enParole: true, debutTour: p.conv.doute.tour, annulerTour: () => { annule++; return true; } };
  assert.equal(p.f.trancherDoute(p.conv), null, 'pas encore de mots : il attend, sa voix continue');
  p.avancer(800); p.conv.ecrit.vif = 'je regarde mes réglages de sortie';
  assert.equal(p.f.trancherDoute(p.conv), 'echo');
  assert.equal(p.interruptions.length, 0, 'jamais coupé par son écho');
  assert.equal(annule, 1, 'le tour de son écho est laissé');
  assert.ok(p.journal.some(([e]) => e === 'echo_pas_coupe'));
});

test('mis en doute puis papa dit autre chose : coupé, par le même chemin (coupé net, la suite, son choix), vérifié', () => {
  const p = lapage();
  p.dit(SA_PHRASE); p.avancer(1500);
  p.f.echoEnDoute(p.conv, { enceinte: true, ressemblance: 0.8, clarte: 2.4 });
  p.conv.capteur = { enParole: true, debutTour: p.conv.doute.tour, annulerTour: () => true };
  p.avancer(900); p.conv.ecrit.vif = 'attends fiston, montre-moi plutôt la météo de demain';
  assert.equal(p.f.trancherDoute(p.conv), 'papa');
  assert.equal(p.interruptions.length, 1, 'la coupure part');
  assert.equal(p.interruptions[0].verifie, true);
  assert.equal(p.f.ressembleASonEcho(p.interruptions[0]), false, 'vérifiée : elle ne repasse pas par le doute');
  assert.equal(p.conv.doute, null);
});

test('l’oreille des voix tranche aussi : « ahmed » le coupe, sa propre voix (« moi ») jamais', () => {
  const p = lapage();
  p.dit(SA_PHRASE); p.avancer(1000);
  p.f.echoEnDoute(p.conv, { enceinte: true, ressemblance: 0.85 });
  p.conv.capteur = { enParole: true, debutTour: p.conv.doute.tour, annulerTour: () => true };
  p.avancer(1200); p.conv.ecrit.confirme = 'non frérot';                // deux mots seulement : les mots seuls ne suffisent pas
  assert.equal(p.f.trancherDoute(p.conv), null);
  p.ctx.etat.voixVerdict = { verdict: 'ahmed', t: p.maintenant() };
  assert.equal(p.f.trancherDoute(p.conv), 'papa');
  assert.equal(p.interruptions.length, 1);
  const q = lapage();
  q.dit(SA_PHRASE); q.avancer(1000);
  q.f.echoEnDoute(q.conv, { enceinte: true, ressemblance: 0.85 });
  q.conv.capteur = { enParole: true, debutTour: q.conv.doute.tour, annulerTour: () => true };
  q.avancer(1500); q.ctx.etat.voixVerdict = { verdict: 'moi', t: q.maintenant() };
  assert.equal(q.f.trancherDoute(q.conv), 'echo');
  assert.equal(q.interruptions.length, 0);
});

test('ce qui ne ressemble pas à sa voix n’est pas mis en doute : tu le coupes net, comme avant', () => {
  const { f, conv } = lapage();
  assert.equal(f.echoEnDoute(conv, { enceinte: true, ressemblance: 0.4, clarte: 3 }), false);
  assert.equal(f.echoEnDoute(conv, { enceinte: false, libre: true, ressemblance: 0.75 }), false, 'sans chemin appris, il faut plus de ressemblance');
  assert.equal(f.echoEnDoute(conv, { rms: 0.2, seuil: 0.03, clarte: 6 }), false, 'sans mesure de ressemblance (le Mac, des écouteurs) : comme avant');
  assert.equal(conv.doute, undefined);
  // (10/11, 18:43) sans chemin appris, sa ressemblance (le meilleur retard cherché au hasard) ne prouve rien : 17 doutes le matin, papa le plus
  // souvent ; sa voix ne peut pas reprendre au mot : coupé net, comme avant, sans doute
  assert.equal(f.echoEnDoute(conv, { enceinte: false, libre: true, ressemblance: 0.9 }), false);
  assert.equal(conv.doute, undefined);
  // dans l'enceinte, ce qui ressemble à son écho : le doute attend (sa voix ne peut pas reprendre)
  assert.equal(f.echoEnDoute(conv, { enceinte: true, ressemblance: 0.9 }), true);
  assert.equal(conv.doute.coupe, false);
});

test('rien de sûr en 4 s : il n’est pas coupé ; ta phrase finie n’entre que si elle porte d’autres mots que les siens', () => {
  const p = lapage();
  p.dit(SA_PHRASE); p.avancer(1000);
  p.f.echoEnDoute(p.conv, { enceinte: true, ressemblance: 0.9 });
  const tour = p.conv.doute.tour;
  p.conv.capteur = { enParole: true, debutTour: tour, annulerTour: () => true };
  p.avancer(4100);
  assert.equal(p.f.trancherDoute(p.conv), 'attendre');
  assert.equal(p.interruptions.length, 0, 'sans preuve que c’est papa, il continue');
  assert.equal(p.f.tourDEcho(p.conv, { debut: tour }, 'je regarde mes réglages de sortie maintenant'), true, 'son écho : laissé');
  p.conv.tourEcho = tour;
  assert.equal(p.f.tourDEcho(p.conv, { debut: tour }, 'Non, je voulais te parler du live de ce soir avec Hakim'), false, 'les mots de papa passent');
  assert.equal(p.f.tourDEcho(p.conv, { debut: tour + 60000 }, 'je regarde mes réglages'), false, 'un autre tour : pas concerné');
});

test('son « arrête » à lui, revenu par l’enceinte, est son écho ; le « stop » de papa n’en est pas un', () => {
  const p = lapage();
  p.dit("D'accord papa, j'arrête la musique et je reste là, tout près"); p.avancer(1200);
  const siens = p.f.sesMotsSonnes(p.maintenant());
  assert.equal(p.f.jugerEcho("j'arrête la musique et je reste là", siens).v, 'echo');
  assert.notEqual(p.f.jugerEcho('stop', siens).v, 'echo', 'un seul mot de papa : jamais pris pour son écho');
  assert.notEqual(p.f.jugerEcho('arrête fiston', siens).v, 'echo');
});

test('branché : le doute vient après la voix claire et avant coupé net / il te coupe / il garde la parole ; tour, parole, verdict', () => {
  const i = PAGE.indexOf('surInterruption: (mesure) => {'), corps = PAGE.slice(i, PAGE.indexOf('surFin: (wav, infos, extra)', i));
  const claire = corps.indexOf('voixClaire(mesure)'), doute = corps.indexOf('echoEnDoute(conv, mesure)'), net = corps.indexOf('coupeNet()');
  assert.ok(claire > 0 && doute > claire && net > doute, 'l’ordre : voix claire, doute, coupé net');
  assert.ok(corps.indexOf('teCouper()') > doute && corps.indexOf('garder_parole') > doute);
  const tour = PAGE.slice(PAGE.indexOf('async function tourDeParole('), PAGE.indexOf('async function envoyerTour('));
  assert.ok(tour.indexOf('tourDEcho(conv, infos, texte)') > 0 && tour.indexOf('tourDEcho(conv, infos, texte)') < tour.indexOf('Conversation.utile(texte)'), 'son écho écarté avant tout');
  assert.match(PAGE.slice(PAGE.indexOf('function jarvisPeutParler('), PAGE.indexOf('function creerLecteurNeuronal(')), /c && c\.doute && !c\.doute\.coupe\) return true/);
  assert.match(PAGE.slice(PAGE.indexOf('async function transcrireVite('), PAGE.indexOf('function morceauNeuf(')), /etat\.voixVerdict = /);
  assert.match(CONV, /enceinte: chemin\.actif, retard_ms: chemin\.retardMs/, 'le micro dit sa ressemblance et son chemin');
  // son propre « arrête » revenu par l'enceinte ne l'arrête pas ; celui de papa, si
  assert.match(PAGE.slice(PAGE.indexOf('function surPauseConversation('), PAGE.indexOf('function vifConversation(')), /ARRETE_MOI\.test\(String\(texte \|\| ''\)\) && !\(typeof jugerEcho === 'function' && jugerEcho\(texte, sesMotsSonnes\(Date\.now\(\)\)\)\.v === 'echo'\)/);
  assert.match(CONV, /annulerTour\(\) \{/);
});

test('son chemin appris va au journal quand il change (pour le mesurer en vrai avec l’enceinte)', () => {
  const p = lapage();
  const conv = { capteur: { echo: { actif: true, retardMs: 280, gain: 0.61, confiance: 0.9 } } };
  p.f.noterCheminEcho(conv); p.f.noterCheminEcho(conv);
  assert.deepEqual(p.journal.filter(([e]) => e === 'echo_chemin').map(([, d]) => d.retard_ms), [280], 'une fois, pas à chaque tic');
  conv.capteur.echo = { actif: false, retardMs: 280, gain: 0.61, confiance: 0.3 };
  p.f.noterCheminEcho(conv);
  assert.equal(p.journal.filter(([e]) => e === 'echo_chemin').length, 2, 'le chemin perdu (des écouteurs) se note aussi');
});

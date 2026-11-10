/* (10/11, 18:43, Ahmed : « Pourquoi ma voix (le micro) ou le live intérieur ne le coupe plus comme avant ? » ; ~19:05 : « il doit rien perdre et
   continuer à autoriser qu'on lui coupe la parole de l'intérieur ou de l'extérieur »)
   node --test test-coupures-papa.js
   Mesuré de 10:13 à 18:46 (voix-diagnostic) : de 16:49 à 18:27, son chemin d'écho appris (force 0,6 à 1,3), 0 « coupé net » ; le matin, 17 signaux mis
   en doute, tous sans chemin appris, 14 restés sans suite, 8 tours de papa laissés comme « son écho ». Ces tests rejouent, au banc, le vrai détecteur
   (public/conversation.js) ET le vrai bloc de la page (public/parler.js, « son écho dans une enceinte ») : sa voix, son écho (retard, force, la traîne
   de la pièce), papa qui parle sur sa voix ; un lecteur qui se met en pause à son mot et reprend au mot. Chaque correctif a son témoin. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const CONV = fs.readFileSync(path.join(__dirname, 'public', 'conversation.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const fonction = (source, debut) => { const i = source.indexOf(debut); assert.ok(i >= 0, debut); return source.slice(i, source.indexOf('\n}\n', i) + 3); };

// le témoin du détecteur : le seuil d'avant (3 × sa force × une enveloppe gardée, 12 fenêtres fortes sur 15)
const SEUIL_NEUF = 'const seuilBarge = chemin.actif ? Math.max(seuil * 2.5, echoPredit * ECHO_MARGE) : Math.max(seuil * 2.5, echo * 2.4, echoInstant * 3);';
const CONV_AVANT = CONV.replace(SEUIL_NEUF, 'const seuilBarge = Math.max(seuil * 2.5, echo * 2.4, echoInstant * 3);')
  .replace('nFortes >= (chemin.actif ? FORTES_ENCEINTE : 12)', 'nFortes >= 12');
// le témoin de la page : la page ne revient jamais en arrière (sa voix ne reprend pas)
const REPRISE = "const repris = !!(lecteur && lecteur.enPause) && typeof reprendreVoix === 'function' && !!reprendreVoix();";
const PAGE_SANS_RETOUR = PAGE.replace(REPRISE, 'const repris = false;');

function hasard(graine) { let s = graine; return () => { s = (s * 16807) % 2147483647; return s / 2147483647; }; }
// sa voix (à la sortie) : des syllabes, des creux
function saVoix(n, graine) {
  const r = hasard(graine), v = [];
  while (v.length < n) {
    const syl = 5 + Math.floor(r() * 8), niv = 0.04 + r() * 0.1;
    for (let i = 0; i < syl; i++) v.push(niv * (0.7 + 0.3 * Math.sin(i / syl * Math.PI)));
    const creux = r() < 0.2 ? 8 + Math.floor(r() * 10) : 2 + Math.floor(r() * 4);
    for (let i = 0; i < creux; i++) v.push(0);
  }
  return v.slice(0, n);
}
// papa qui parle : des syllabes, des creux à 25 %, une pause de 120 à 240 ms toutes les 6 à 10 syllabes (niveau 0 à 1)
function parole(n, graine) {
  const r = hasard(graine), v = [];
  let k = 0, prochaine = 6 + Math.floor(r() * 5);
  while (v.length < n) {
    const syl = 5 + Math.floor(r() * 7), niv = 0.6 + r() * 0.4;
    for (let i = 0; i < syl; i++) v.push(niv * (0.75 + 0.25 * Math.sin(i / syl * Math.PI)));
    if (++k >= prochaine) { k = 0; prochaine = 6 + Math.floor(r() * 5); const p = 6 + Math.floor(r() * 7); for (let i = 0; i < p; i++) v.push(0); }
    else { const c = 1 + Math.floor(r() * 3); for (let i = 0; i < c; i++) v.push(0.25 * niv); }
  }
  return v.slice(0, n);
}

// une scène : 3 s de calme, sa voix (10 s), son écho au micro (retard D, force G, la traîne de la pièce), papa (de 6 à 9 s) ; la page coupe (sa voix
// se met en pause à son mot), tranche toutes les 140 ms, et revient en arrière (sa voix reprend au mot) si c'était son écho
async function scene({ D = 340, G = 1, graine = 11, papa = null, conv = CONV, page = PAGE } = {}) {
  const horloge = { t: 1e6 };
  let noeud = null, h = 12345;
  const cx = { console, Float32Array, ArrayBuffer, DataView, Math, Blob: class {}, Date: { now: () => horloge.t },
    URL: { createObjectURL: () => 'b', revokeObjectURL() {} },
    navigator: { mediaDevices: { getUserMedia: async () => ({ getTracks: () => [], getAudioTracks: () => [] }) } },
    AudioWorkletNode: class { constructor() { noeud = this; this.port = { postMessage() {}, onmessage: null }; } connect() {} disconnect() {} } };
  cx.window = cx; vm.createContext(cx); vm.runInContext(conv, cx);
  const actx = { sampleRate: 16000, destination: {}, audioWorklet: { addModule: async () => {} },
    createMediaStreamSource: () => ({ connect() {}, disconnect() {} }), createGain: () => ({ gain: { value: 1 }, connect() {}, disconnect() {} }) };
  const pousser = (rms) => {
    const f = new Float32Array(320), a = rms * Math.SQRT2;
    for (let i = 0; i < 320; i++) { h = (h * 16807) % 2147483647; f[i] = a * Math.sin(i * 0.37) + (h / 2147483647 - 0.5) * 0.002; }
    horloge.t += 20; noeud.port.onmessage({ data: f });
  };
  const L = { pos: 0, pause: false, debut: false, coupes: [], reprises: [] }, sa = saVoix(700, graine), FIN = 500;
  const sonne = () => L.debut && !L.pause && L.pos < FIN;
  const journal = [];
  const pg = { Math, JSON, String, Array, Object, Number, Set, Error, Date: { now: () => horloge.t }, clearTimeout() {},
    etat: { saVoix: [], voixVerdict: null, conversation: null }, paroleRecente: [],
    lecteur: { get enPause() { return L.pause; }, get actif() { return L.pos < FIN; }, impl: 'neuronal' }, lecteurNeuronal: 'neuronal',
    coupeNet: () => true, reprendrePassage: () => true, garderParole: () => true,
    reprendreVoix: () => { if (!L.pause) return false; L.pause = false; L.reprises.push(horloge.t); return true; },
    acheverCoupure: () => true, saVoixAudible: sonne, journalVoix: (e, d) => journal.push([horloge.t, e, d]), setInterval: () => 0, motsEntendusDepuis: () => '' };
  vm.createContext(pg);
  const a = page.indexOf('SON ÉCHO DANS UNE ENCEINTE'), b = page.indexOf('// fin de « son écho dans une enceinte »');
  vm.runInContext(page.slice(page.lastIndexOf('/* ----', a), b) + 'this.f = { echoEnDoute, trancherDoute };', pg);
  const cv = { ecrit: { confirme: '', vif: '' } };
  const surInterruption = (m) => {
    if (Number(m.clarte) > 0 && Number(m.clarte) < 1.8) return;      // un fond (voix_claire_x)
    if (pg.f.echoEnDoute(cv, m)) return;
    if (!L.pause) { L.pause = true; L.coupes.push(horloge.t); }           // coupé net : sa voix finit son mot et attend
  };
  cv.optionsCapteur = { surInterruption };
  cv.capteur = await cx.Conversation.demarrer({ ctx: actx, patienceMs: () => 1000, jarvisParle: sonne, niveauSortie: () => (sonne() ? sa[L.pos] : 0),
    surInterruption, surDebut() {}, surFin() {} });
  for (let k = 0; k < 150; k++) pousser(0.003);
  L.debut = true;
  const sortie = []; let echo = 0, papaDebut = -1;
  for (let i = 0; i < 900; i++) {
    sortie.push(sonne() ? sa[L.pos] : 0);
    const lag = Math.round(D / 20), s0 = sortie.length > lag ? sortie[sortie.length - 1 - lag] : 0;
    echo = Math.max(s0, echo * 0.55);
    const p = papa ? papa(i) : 0;
    if (p > 0 && papaDebut < 0) papaDebut = horloge.t;
    pousser(Math.sqrt((G * echo) ** 2 + p ** 2 + 0.003 ** 2));
    if (sonne()) L.pos++;
    if (i % 7 === 0 && cv.doute) pg.f.trancherDoute(cv);
  }
  return { L, journal, papaDebut, fini: L.pos >= FIN };
}
// papa parle sur sa voix, au niveau de son écho : coupé (et resté coupé) dans les 1,5 s ?
async function papaSurSaVoix(o) {
  let coupes = 0; const lat = [];
  for (let g = 0; g < 6; g++) {
    const pv = parole(400, 1000 + g * 13);
    const r = await scene({ ...o, graine: 11 + g * 7, papa: (i) => (i >= 300 && i < 450 ? o.A * pv[i - 300] : 0) });
    const c = r.L.coupes.find(x => x >= r.papaDebut && x < r.papaDebut + 1500);
    if (c != null && !r.L.reprises.some(x => x > c && x < r.papaDebut + 3000)) { coupes++; lat.push(c - r.papaDebut); }
  }
  lat.sort((a, b) => a - b);
  return { coupes, mediane: lat.length ? lat[lat.length >> 1] : Infinity };
}

test('TÉMOIN (16:49-18:27 : 0 « coupé net ») : papa qui parle sur sa voix, au niveau de son écho (force 1 à 1,3), le coupe net en moins d’une seconde', async () => {
  let neuf = 0, avant = 0;
  for (const G of [1, 1.3]) {
    const a = await papaSurSaVoix({ D: 480, G, A: 0.2 });
    neuf += a.coupes;
    assert.ok(a.mediane <= 800, `force ${G} : coupé en ${a.mediane} ms (médiane)`);
    avant += (await papaSurSaVoix({ D: 480, G, A: 0.2, conv: CONV_AVANT })).coupes;
  }
  assert.ok(neuf >= 10, `papa coupe net ${neuf} fois sur 12`);
  assert.ok(avant <= 2, `le témoin : avec le seuil d'avant, ${avant} fois sur 12`);
});

test('une voix plus forte que son écho, le chemin moins fort (force 0,6) : coupé net aussi', async () => {
  const a = await papaSurSaVoix({ D: 340, G: 0.6, A: 0.2 });
  assert.ok(a.coupes >= 5, `${a.coupes}/6`);
});

test('TÉMOIN : son seul écho ne le coupe jamais pour de bon : s’il l’a coupé, la page revient en arrière (sa voix reprend au mot) et sa réponse va au bout', async () => {
  let phrases = 0, finies = 0, coupes = 0, longues = 0, finiesSans = 0;
  for (const [D, G] of [[340, 1], [480, 1.3], [700, 1], [250, 1]]) for (let g = 0; g < 4; g++) {
    const r = await scene({ D, G, graine: 11 + g * 7 });
    phrases++; if (r.fini) finies++;
    coupes += r.L.coupes.length;
    for (const c of r.L.coupes) { const q = r.L.reprises.find(x => x >= c); if (q == null || q - c > 1900) longues++; }
    if (r.L.coupes.length) { const s = await scene({ D, G, graine: 11 + g * 7, page: PAGE_SANS_RETOUR }); if (s.fini) finiesSans++; }
  }
  assert.strictEqual(finies, phrases, `ses ${phrases} réponses vont au bout`);
  assert.strictEqual(longues, 0, `chaque coupure par son écho revient en arrière en moins de 1,9 s (${coupes} coupures sur ${phrases} phrases)`);
  assert.ok(coupes <= 4, `son écho le coupe rarement : ${coupes} fois sur ${phrases} phrases`);
  if (coupes) assert.strictEqual(finiesSans, 0, 'le témoin : sans le retour en arrière, sa réponse resterait coupée');
});

/* ---- la page : trancher après la coupure provisoire ---- */
function bloc({ reversible = true } = {}) {
  let t = 1_800_000_000_000;
  const vu = { journal: [], reprises: 0, achevees: 0, annules: 0, finis: 0, interruptions: [] };
  const lecteur = { enPause: false, actif: true, impl: 'neuronal' };
  const ctx = { Math, JSON, String, Array, Object, Number, Set, Error, Date: { now: () => t }, clearTimeout() {},
    etat: { saVoix: [], voixVerdict: null, conversation: null }, paroleRecente: [], lecteur, lecteurNeuronal: 'neuronal',
    coupeNet: () => true, reprendrePassage: () => reversible, garderParole: () => true, saVoixAudible: () => !lecteur.enPause,
    reprendreVoix: () => { if (!lecteur.enPause) return false; lecteur.enPause = false; vu.reprises++; return true; },
    acheverCoupure: () => { vu.achevees++; return true; }, journalVoix: (e, d) => vu.journal.push([e, d]), setInterval: () => 0,
    motsEntendusDepuis: (conv) => `${conv.ecrit.confirme} ${conv.ecrit.vif}`.trim() };
  vm.createContext(ctx);
  const a = PAGE.indexOf('SON ÉCHO DANS UNE ENCEINTE'), b = PAGE.indexOf('// fin de « son écho dans une enceinte »');
  vm.runInContext(PAGE.slice(PAGE.lastIndexOf('/* ----', a), b) + 'this.f = { echoEnDoute, trancherDoute, tourDEcho, jugerEcho };', ctx);
  const conv = { ecrit: { confirme: '', vif: '' }, optionsCapteur: { surInterruption: (m) => vu.interruptions.push(m) } };
  conv.capteur = { enParole: true, debutTour: 0, derniereVoix: 0, echo: { actif: true, retardMs: 400 },
    annulerTour: () => { vu.annules++; conv.capteur.enParole = false; return true; }, finirTour: () => { vu.finis++; conv.capteur.enParole = false; } };
  const couper = () => { lecteur.enPause = true; };                       // coupé net, provisoirement : sa voix à son mot
  return { ctx, f: ctx.f, vu, conv, lecteur, couper, avancer: (ms) => { t += ms; }, maintenant: () => t };
}
function signal(p, mesure = { enceinte: true, ressemblance: 0.5, retard_ms: 400, clarte: 3 }) {
  const attend = p.f.echoEnDoute(p.conv, mesure);
  p.conv.capteur.debutTour = p.conv.doute ? p.conv.doute.tour : 0;
  if (!attend) p.couper();
  return attend;
}

test('dans l’enceinte, un signal le coupe TOUT DE SUITE (provisoirement) ; ta voix qui dure au-delà de son écho : il reste coupé, la coupure s’achève', () => {
  const p = bloc();
  assert.strictEqual(signal(p), false, 'pas d’attente : coupé net');
  assert.strictEqual(p.conv.doute.coupe, true);
  assert.strictEqual(p.f.trancherDoute(p.conv), null, 'sa voix vient de se taire');
  p.avancer(300); p.conv.capteur.derniereVoix = p.maintenant();
  assert.strictEqual(p.f.trancherDoute(p.conv), null, 'encore dans son écho (son retard)');
  p.avancer(400); p.conv.capteur.derniereVoix = p.maintenant();      // ta voix, après son retard et la marge
  assert.strictEqual(p.f.trancherDoute(p.conv), 'papa');
  assert.strictEqual(p.vu.achevees, 1, 'la coupure s’achève (sa voix prête gardée, non dite)');
  assert.strictEqual(p.vu.reprises, 0);
  assert.ok(p.vu.journal.some(([e, d]) => e === 'echo_doute_papa' && d.par === 'son'));
});

test('ce qui ressemble à son écho le coupe aussi ; puis plus rien après son retard : c’était lui, la page revient en arrière (reprise au mot, rien d’achevé)', () => {
  const p = bloc();
  assert.strictEqual(signal(p, { enceinte: true, ressemblance: 0.92, retard_ms: 400, clarte: 2.5 }), false, 'avant : il attendait, sans le couper');
  p.avancer(140); p.f.trancherDoute(p.conv);
  p.conv.capteur.derniereVoix = p.maintenant() + 200;                  // la traîne de son écho, avant la fin de son retard
  for (let k = 0; k < 8 && p.conv.doute; k++) { p.avancer(140); p.f.trancherDoute(p.conv); }
  assert.strictEqual(p.conv.doute, null);
  assert.strictEqual(p.vu.reprises, 1, 'sa voix reprend au mot');
  assert.strictEqual(p.vu.achevees, 0, 'rien n’a été lâché : rien n’est perdu');
  assert.strictEqual(p.vu.finis, 1, 'le tour se clôt (ce qu’il porte sera transcrit, laissé si ce sont ses mots)');
  assert.ok(p.vu.journal.some(([e, d]) => e === 'echo_revenu' && d.par === 'silence' && d.repris));
});

test('ses propres mots revenus, ou sa voix reconnue (« moi ») : la page revient en arrière, le tour est laissé ; l’oreille des voix n’est jamais attendue pour couper', () => {
  const p = bloc();
  p.ctx.paroleRecente.push({ t: p.maintenant(), suite: 'je regarde mes réglages de sortie maintenant papa'.split(' ') });
  signal(p, { enceinte: true, ressemblance: 0.9, clarte: 2 });
  p.avancer(200); p.conv.ecrit.vif = 'je regarde mes réglages de sortie';
  assert.strictEqual(p.f.trancherDoute(p.conv), 'echo');
  assert.strictEqual(p.vu.annules, 1);
  assert.strictEqual(p.vu.reprises, 1);
  const q = bloc();
  signal(q);
  q.avancer(200); q.ctx.etat.voixVerdict = { verdict: 'moi', t: q.maintenant() };
  assert.strictEqual(q.f.trancherDoute(q.conv), 'echo');
  assert.strictEqual(q.vu.reprises, 1);
});

test('dans le doute (rien de sûr en 4 s : ni le son, ni les mots, ni l’oreille) : il reste coupé, la coupure s’achève (une vraie voix n’est jamais perdue)', () => {
  const p = bloc();
  signal(p);
  p.ctx.saVoixAudible = () => true;                                     // le son ne peut pas trancher (sa voix ne s'est pas tue d'elle-même)
  let v = null;
  for (let k = 0; k < 40 && p.conv.doute; k++) { p.avancer(140); v = p.f.trancherDoute(p.conv); }
  assert.strictEqual(v, 'attendre');
  assert.strictEqual(p.vu.reprises, 0);
  assert.strictEqual(p.vu.achevees, 1);
  assert.ok(p.vu.journal.some(([e]) => e === 'doute_reste_coupe'));
});

test('sa voix ne peut pas reprendre au mot (la voix du téléphone) : dans l’enceinte, ce qui ressemble à son écho attend tes mots ; sans chemin appris, coupé net', () => {
  const p = bloc({ reversible: false });
  assert.strictEqual(p.f.echoEnDoute(p.conv, { enceinte: true, ressemblance: 0.9 }), true, 'il attend');
  assert.strictEqual(p.conv.doute.coupe, false);
  p.avancer(800); p.conv.ecrit.vif = 'attends fiston montre-moi plutôt la météo';
  assert.strictEqual(p.f.trancherDoute(p.conv), 'papa');
  assert.strictEqual(p.vu.interruptions.length, 1, 'la coupure part, vérifiée');
  const q = bloc({ reversible: false });
  assert.strictEqual(q.f.echoEnDoute(q.conv, { enceinte: false, libre: true, ressemblance: 0.95, clarte: 7 }), false, 'avant : mis en doute (11:53, papa : « Ça va ? Salam… »)');
  assert.strictEqual(q.conv.doute, undefined);
});

test('TÉMOIN : ses mots « à lui » se comptent sur les mots pleins ; une phrase de papa faite de « est », « que », « pas », « pour » n’est plus laissée comme son écho', () => {
  const p = bloc();
  const siens = "Est-ce que je peux pas te dire pour ça, papa ? Je pense que c'est l'écho dans l'enceinte qui me coupe";
  const papa = 'Est-ce que tu peux pas faire ça pour moi';
  assert.notStrictEqual(p.f.jugerEcho(papa, siens).v, 'echo');
  assert.strictEqual(p.f.jugerEcho("je pense que c'est l'écho dans l'enceinte", siens).v, 'echo', 'son écho reste son écho');
  assert.strictEqual(p.f.jugerEcho('non regarde plutôt la musique qui joue', siens).v, 'papa', 'des mots nouveaux : papa');
  // le témoin : la règle d'avant (3 lettres et plus, mots vides compris) prenait la phrase de papa pour son écho
  const avant = (x) => String(x || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/\[[^\]]*\]/g, ' ').split(/[^\p{L}\p{N}]+/u).filter(m => m.length >= 3);
  const m = avant(papa), s = new Set(avant(siens)), part = m.filter(w => s.has(w)).length / m.length;
  assert.ok(m.length >= 2 && part >= 0.6, `avant : ${Math.round(part * 100)} % « ses mots »`);
  // et le tour entre : seulement son écho est laissé (avant : « rien de sûr » le laissait aussi)
  p.conv.tourEcho = 0;
  p.ctx.paroleRecente.push({ t: p.maintenant(), suite: siens.split(' ') });
  assert.strictEqual(p.f.tourDEcho(p.conv, { debut: 0 }, 'Ouais'), false, 'un « ouais » de papa n’est pas perdu');
});

/* ---- rien ne se perd : la coupure provisoire ne lâche rien tant qu'elle n'est pas vérifiée ---- */
function coupure(src = PAGE) {
  const vu = { lache: 0, retenue: 0, gardees: 0, liberes: 0 };
  const ctx = { etat: { riboFile: [{ tour: 3, texte: 'la suite' }], riboEnVoix: [] }, bouts: { liste: new Map([[1, {}]]), fileTel: [{}], attenteTel: null, enFile: [] },
    garderVoixCoupees: () => { vu.gardees++; }, libererRibosomes: () => { vu.liberes++; }, blancsPourSautes() {}, majBoutonsPause() {},
    retenirSaVoix: () => { vu.retenue++; return true; }, arreterTout() {}, lecteur: { actif: true } };
  vm.createContext(ctx);
  const corps = src.indexOf('function lacherPourLaCoupure(') > 0
    ? [fonction(src, 'function couperNet(conv, { lacher = false, provisoire = false } = {}) {'), fonction(src, 'function lacherPourLaCoupure(conv) {'), fonction(src, 'function acheverCoupure(conv) {')].join('\n')
    : fonction(src, 'function couperNet(conv, { lacher = false } = {}) {') + '\nfunction acheverCoupure() { return false; }';
  vm.runInContext(`${corps}\nthis.couperNet = couperNet; this.acheverCoupure = acheverCoupure;`, ctx);
  return { ctx, vu };
}
test('TÉMOIN (« il doit rien perdre ») : coupé provisoirement, sa voix seulement retenue, rien n’est lâché ; vérifié, la coupure s’achève (sa voix prête gardée, non dite)', () => {
  const p = coupure(), conv = {};
  p.ctx.couperNet(conv, { provisoire: true });
  assert.strictEqual(p.vu.retenue, 1);
  assert.strictEqual(p.vu.gardees + p.vu.liberes, 0, 'ni ses ribosomes, ni sa voix prête');
  assert.strictEqual(p.ctx.etat.riboFile.length, 1, 'la suite attend toujours');
  assert.strictEqual(p.ctx.bouts.liste.size, 1);
  assert.strictEqual(conv.coupeAAchever, true);
  assert.strictEqual(p.ctx.acheverCoupure(conv), true);
  assert.strictEqual(p.vu.gardees, 1, 'vérifiée : sa voix prête part avec la coupure (non dite)');
  assert.strictEqual(p.vu.liberes, 1);
  assert.strictEqual(p.ctx.etat.riboFile.length, 0);
  assert.strictEqual(p.ctx.acheverCoupure(conv), false, 'une seule fois');
  // coupé net sans doute : comme avant, tout de suite
  const n = coupure(); n.ctx.couperNet({});
  assert.strictEqual(n.vu.liberes, 1);
  // le témoin : la coupure provisoire retirée, « coupé net » lâche tout, même pour son propre écho (sa suite perdue)
  const a = coupure(PAGE.replace("if (provisoire && !lacher && typeof retenirSaVoix === 'function' && retenirSaVoix(conv)) {", 'if (false) {'));
  a.ctx.couperNet({}, { provisoire: true });
  assert.strictEqual(a.vu.liberes, 1);
  assert.strictEqual(a.ctx.etat.riboFile.length, 0);
});

test('branché : un signal mis en doute part en coupé net PROVISOIRE (le même chemin : garder la parole, la suite sautée, son choix) ; sa suite n’est pas sautée si c’était son écho', () => {
  const i = PAGE.indexOf('surInterruption: (mesure) => {'), corps = PAGE.slice(i, PAGE.indexOf('surFin: (wav, infos, extra)', i));
  assert.ok(corps.indexOf('voixClaire(mesure)') < corps.indexOf('echoEnDoute(conv, mesure)'));
  assert.match(corps, /couperNet\(conv, \{ provisoire: !!\(conv\.doute && conv\.doute\.coupe\) \}\);\s*if \(etat\.retenue && lecteur\.enPause\) prevoirSaut\(conv, mesure\);/);
  const saut = fonction(PAGE, 'function prevoirSaut(conv, mesure) {');
  assert.match(saut, /if \(Number\(conv\.echoRevenuA\) >= t0\) return;/);
  assert.match(saut, /if \(etat\.conversation !== conv \|\| Number\(conv\.echoRevenuA\) >= t0\) return;/);
  const tour = PAGE.slice(PAGE.indexOf('async function tourDeParole('), PAGE.indexOf('async function envoyerTour('));
  assert.ok(tour.indexOf('tourDEcho(conv, infos, texte)') > 0);
});

/* ---- qui l'a coupé : une voix de son live, jamais papa ---- */
test('la coupure d’une voix du live arrive au cockpit et se dit « une voix de son live (pas par papa) » ; jamais le stimulus « papa »', () => {
  const cx = { Date, Number, String, Math, JSON, Set, CAUSES_COUPURE: null, coupuresVues: new Set(), coupureAttente: null, sauverCoupure() {},
    corpsActif: () => true, corpsLot: { evenements: [] }, ressentirCorps() {} };
  vm.createContext(cx);
  const i = SRC.indexOf('const CAUSES_COUPURE'), j = SRC.indexOf('// son tour d\'Ahmed : la coupure qu\'apporte la page');
  vm.runInContext(SRC.slice(i, j).replace(/^let coupureAttente = null;\n.*\n/m, '').replace(/^const coupuresVues = new Set\(\);\n/m, '').replace(/^function sauverCoupure\(\).*\n/m, '')
    + '\nthis.lire = lireCoupure; this.recevoir = recevoirCoupure; this.ligne = ligneCoupure;', cx);
  const T = Date.now();
  const c = cx.lire({ id: 'm1-1', t: T, cause: 'voix_live', mode: 'oral', derniers: 'je te disais', reste: 4 }, T, T);
  assert.ok(c, 'avant : une cause inconnue, la coupure était jetée');
  assert.match(cx.ligne(c), /a été coupée par une voix de son live ou du téléphone \(pas par papa\)/);
  assert.ok(cx.recevoir({ id: 'm1-2', t: T, cause: 'voix_live', mode: 'oral' }, T, T));
  assert.strictEqual(cx.corpsLot.evenements.length, 0, 'jamais le stimulus « coupé par papa »');
  cx.recevoir({ id: 'm1-3', t: T, cause: 'voix_ahmed', mode: 'oral' }, T, T);
  assert.deepStrictEqual(cx.corpsLot.evenements.map(e => e.details.qui), ['papa']);
});

test('la page : « voix_live » ne devient jamais « voix_ahmed » (finirParole), et la voix de l’intérieur qui le coupe le dit', () => {
  const f = fonction(PAGE, 'function finirParole(cause, detail = \'\', cible = null) {');
  assert.match(f, /else if \(cause === 'voix_live' && c\.cause === 'voix_ahmed'\) c\.cause = 'voix_live';/);
  assert.match(f, /else if \(c\.cause === 'voix_live' && cause === 'voix_ahmed'\) \{/);
  assert.match(PAGE, /coupureProvisoire\('voix_live'\)/);
  assert.match(PAGE, /es\.addEventListener\('live', \(ev\) => \{ try \{ const o = JSON\.parse\(ev\.data\); etat\.live = \{ oui: !!o\.live, t: Date\.now\(\) \}/);
  assert.match(SRC, /diffuser\(abonnesPensees, 'live', j\(\{ live: enLive, repondre: r\.live_repondre !== false \}\)\)/);
});

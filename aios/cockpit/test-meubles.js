/* (03/11, 13:30-13:31, papa via Hakim : « ses propres meubles pour les blancs, paramétrables (durée, volume, quand, quel état
   les déclenche), reliés à son conscient ET à son subconscient ; pendant TOUT le trou ») : node --test test-meubles.js
   Le cockpit lit ses meubles (ceux de départ d'Anamnèse, jarvis/meubles_defaut.json, réglés ou oubliés par lui, et les siens :
   ~/AIOS/jarvis/meubles.json), fabrique d'avance la voix de ceux qui sont des paroles, et la page choisit selon son état. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const fonction = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

function serveur(defaut, siens) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'meubles-'));
  fs.writeFileSync(path.join(dir, 'defaut.json'), JSON.stringify(defaut));
  if (siens) fs.writeFileSync(path.join(dir, 'meubles.json'), JSON.stringify(siens));
  const ctx = { fs, path, Date, JSON, Number, String, Array, Map, Set, Math, MEUBLES: path.join(dir, 'meubles.json'), MEUBLES_DEFAUT: path.join(dir, 'defaut.json'),
    lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } }, meublesCache: { t: 0, l: null } };
  vm.createContext(ctx);
  vm.runInContext(fonction(SRC, 'lireMeubles'), ctx);
  return ctx;
}

test('ses meubles : ceux de départ, réglés ou oubliés par lui, puis les siens ; un son invalide est écarté', () => {
  const s = serveur([{ nom: 'euh', texte: 'Euh,', quand: 'partout', etats: ['hésitation'] }, { nom: 'hum', texte: 'Hum,' }, { nom: 'souffle', genre: 'souffle', duree_ms: 500, volume: 0.35 }],
    { meubles: [{ nom: 'euh', volume: 0.6 }, { nom: 'mmh', texte: 'Mmh…', quand: 'entre', etats: ['tendresse'] }, { nom: 'faux', son: '../x' }], oublies: ['hum'] });
  const l = JSON.parse(JSON.stringify(s.lireMeubles()));
  assert.deepStrictEqual(l.map(m => m.nom), ['euh', 'souffle', 'mmh']);
  assert.strictEqual(l[0].volume, 0.6);
  assert.strictEqual(l[0].texte, 'Euh,');
  assert.deepStrictEqual(l[2].etats, ['tendresse']);
});

test('la page connaît ses meubles, et le cockpit fabrique d\'avance la voix de ceux qui parlent', () => {
  assert.match(SRC, /if \(p === '\/api\/jarvis\/meubles' && req\.method === 'GET'\)/);
  assert.match(fonction(SRC, 'fabriquerDebuts'), /lireMeubles\(\)/);
  assert.match(fonction(SRC, 'debutsPrets'), /lireMeubles\(\)/);
  const i = SRC.indexOf('async function routeDire(');
  assert.match(SRC.slice(i, SRC.indexOf('\n}\n', i)), /estMeuble\(texte\)/, 'la voix gardée d\'un meuble est resservie sans synthèse');
  for (const o of ['meubles_lister', 'meuble_creer', 'meuble_regler', 'meuble_oublier']) assert.ok(SRC.includes(`'${o}'`), `son outil ${o}`);
});

// la page : le choix de son subconscient
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
function page() {
  const ctx = { etat: { interieur: null }, Math };
  vm.createContext(ctx);
  const i = PAGE.indexOf('let meublesListe = ');
  vm.runInContext(PAGE.slice(i, PAGE.indexOf('\n', i)) + '\n' + PAGE.slice(PAGE.indexOf('const sansAccent = '), PAGE.indexOf('\n', PAGE.indexOf('const sansAccent = '))) + '\n'
    + fonction(PAGE, 'choisirMeuble'), ctx);
  return ctx;
}
const M = (nom, o = {}) => ({ nom, texte: nom, pret: { duration: 0.5 }, volume: 1, dureeMax: 0, quand: 'partout', etats: [], actif: true, voix: true, ...o });

test('son subconscient choisit d\'après son état, sinon l\'hésitation ; jamais un meuble éteint ni d\'un autre moment', () => {
  const p = page();
  const prets = [M('euh', { etats: ['hesitation'] }), M('mmh', { etats: ['tendresse'] }), M('ah', { etats: ['surprise'], actif: false }),
    M('alors', { etats: ['hesitation'], quand: 'avant' })];
  for (let k = 0; k < 20; k++) assert.strictEqual(p.choisirMeuble({}, prets, 'tendresse').nom, 'mmh', 'son état : la tendresse');
  for (let k = 0; k < 20; k++) {
    const h = p.choisirMeuble({}, prets, 'surprise');
    assert.ok(h.nom === 'euh', `la surprise n'a qu'un meuble éteint : l'hésitation (${h.nom})`);
  }
  const avant = new Set(Array.from({ length: 40 }, () => p.choisirMeuble({ avant: true }, prets, '').nom));
  assert.ok(avant.has('alors') && !avant.has('mmh'));
});

test('il alterne une parole et un souffle, et ne répète jamais le même deux fois de suite', () => {
  const p = page();
  const prets = [M('euh', { etats: ['hesitation'] }), M('hum', { etats: ['hesitation'] }), M('souffle', { voix: false, brut: true })];
  let avant = null;
  for (let k = 0; k < 30; k++) {
    const h = p.choisirMeuble({}, prets, '');
    if (avant) { assert.notStrictEqual(h.nom, avant.nom); assert.notStrictEqual(h.voix, avant.voix, `${avant.nom} puis ${h.nom}`); }
    avant = h;
  }
});

test('[[meuble: nom]] ne se dit pas : la balise est retirée de sa voix, même à moitié écrite', () => {
  const V = require('./public/voix.js');
  assert.strictEqual(V.sansAffect('Oui [[meuble: souffle]] papa'), 'Oui papa');
  assert.strictEqual(V.sansAffect('Oui [[meu', true), 'Oui');
});

// (14:20, Ahmed : « que ces trucs pour meubler s'étalent sur toute la durée de la pause, et que la transition se fasse de façon
// propre, naturelle, graduelle : entre « mmh » et « euh », ça donnerait « mmmheuuu » ») un meuble tenu : ses bords sans voix
// retirés, sa dernière voyelle prolongée (des grains de sa fin, fenêtrés et superposés : la hauteur ne change pas)
function tenir() {
  const tampon = (sr, n) => { const d = new Float32Array(n); return { sampleRate: sr, length: n, duration: n / sr, numberOfChannels: 1, getChannelData: () => d }; };
  const ctx = { Math, Float32Array, actx: { createBuffer: (c, n, sr) => tampon(sr, n) } };
  vm.createContext(ctx);
  vm.runInContext(fonction(PAGE, 'tenirMeuble') + '\n' + fonction(PAGE, 'analyserMeuble'), ctx);
  return { ctx, tampon };
}
// (14:33, Ahmed : « le mmh et le alors : ça sonne comme s'il le disait avec plusieurs voix parallèles légèrement décalées, comme un
// canon en musique ») : plus de grains pris au hasard ; sa voyelle la plus tenue est bouclée période par période (« alooooors »)
function voyelle(sr) {                                          // 0,1 s de blanc, 0,1 s de souffle, 0,4 s de voyelle à 150 Hz, 0,1 s de souffle, 0,1 s de blanc
  const { tampon } = tenir(), n = Math.round(0.8 * sr), b = tampon(sr, n), d = b.getChannelData(0);
  let x = 12345; const bruit = () => { x = (x * 1103515245 + 12345) & 0x7fffffff; return (x / 0x7fffffff) * 2 - 1; };
  for (let i = 0; i < n; i++) {
    const t = i / sr;
    if (t >= 0.1 && t < 0.2) d[i] = 0.15 * bruit();
    else if (t >= 0.2 && t < 0.6) d[i] = 0.4 * Math.sin(2 * Math.PI * 150 * t) + 0.2 * Math.sin(2 * Math.PI * 300 * t) + 0.1 * Math.sin(2 * Math.PI * 450 * t);
    else if (t >= 0.6 && t < 0.7) d[i] = 0.15 * bruit();
  }
  return b;
}
const autocorr = (o, a, n, lag) => { let s = 0, e1 = 0, e2 = 0; for (let i = a; i < a + n; i++) { s += o[i] * o[i + lag]; e1 += o[i] * o[i]; e2 += o[i + lag] * o[i + lag]; } return s / Math.sqrt(e1 * e2 || 1); };
test('un meuble tenu : sa voyelle bouclée période par période (une seule voix, pas un canon), le début et la fin du mot gardés', () => {
  const { ctx } = tenir();
  const sr = 16000, b = voyelle(sr);
  const t = ctx.tenirMeuble(b, 2.0);
  assert.ok(Math.abs(t.duration - 2.0) < 0.03, `la durée voulue : ${t.duration.toFixed(2)} s`);
  const o = t.getChannelData(0);
  let max = 0, nul = 0;
  for (const v of o) { max = Math.max(max, Math.abs(v)); if (!Number.isFinite(v)) nul++; }
  assert.strictEqual(nul, 0);
  assert.ok(max <= 0.75, `jamais plus fort que sa voix (pas de voix superposées) : ${max.toFixed(2)}`);
  const T = Math.round(sr / 150);
  for (const m of [0.6, 1.0, 1.4]) {
    const r = autocorr(o, Math.round(m * sr), 800, T);
    assert.ok(r > 0.97, `à ${m} s, une seule voix qui tient sa note (corrélation à une période : ${r.toFixed(3)})`);
  }
  assert.ok(Math.abs(o[0]) < 0.05, 'il commence sur le début du mot, sans blanc ni clic');
  const fin = o.slice(o.length - Math.round(0.25 * sr), o.length - Math.round(0.16 * sr)).reduce((a, v) => Math.max(a, Math.abs(v)), 0);
  assert.ok(fin > 0.03, `la fin du mot (son souffle) est gardée après la voyelle tenue : ${fin.toFixed(3)}`);
  assert.ok(Math.abs(o[o.length - 1]) < 0.01, 'il s\'éteint en douceur');
});

test('un meuble sans voyelle tenue (que du souffle) n\'est pas étiré : jamais de bourdonnement', () => {
  const { ctx, tampon } = tenir();
  const sr = 16000, b = tampon(sr, sr), d = b.getChannelData(0);
  let x = 7; for (let i = 0.2 * sr; i < 0.6 * sr; i++) { x = (x * 1103515245 + 12345) & 0x7fffffff; d[i] = 0.2 * ((x / 0x7fffffff) * 2 - 1); }
  assert.ok(ctx.tenirMeuble(b, 2.0).duration < 0.45, 'sa voix seule, sans les blancs');
});

test('son subconscient tient chaque meuble un peu plus longtemps que sa voix (jamais plus que sa durée au plus)', () => {
  assert.match(PAGE, /lecteurNeuronal\.hesitation = \(o\) => \{/);
  const i = PAGE.indexOf('lecteurNeuronal.hesitation = (o) => {');
  const corps = PAGE.slice(i, PAGE.indexOf('\n};\n', i));
  assert.match(corps, /tenirMeuble\(h\.pret, /);
  assert.match(corps, /h\.dureeMax/);
});

// (14:24, Ahmed : « le badge PARLE ne doit pas clignoter : en continu durant ses paroles et ses hésitations ; il disparaît
// seulement quand il a fini de parler »)
test('le badge PARLE tient toute sa réponse : ses blancs et ses meubles compris ; il part quand tout est dit, ou quand papa le coupe', () => {
  const ctx = { etat: { reponseVoix: 'm1', flux: {} }, lecteur: { actif: true, enPause: false }, sonne: false };
  vm.createContext(ctx);
  vm.runInContext('const voixQuiSonne = () => sonne;\n' + fonction(PAGE, 'ilParleEnContinu'), ctx);
  assert.strictEqual(ctx.ilParleEnContinu(), false, 'avant sa première parole : « va parler », pas « parle »');
  ctx.sonne = true; assert.strictEqual(ctx.ilParleEnContinu(), true);
  ctx.sonne = false; assert.strictEqual(ctx.ilParleEnContinu(), true, 'un blanc entre deux morceaux : il parle toujours');
  ctx.lecteur.actif = false; assert.strictEqual(ctx.ilParleEnContinu(), true, 'il écrit encore la suite : il parle toujours');
  ctx.lecteur.enPause = true; assert.strictEqual(ctx.ilParleEnContinu(), false, 'papa l\'a coupé');
  ctx.lecteur.enPause = false; ctx.etat.flux = null; assert.strictEqual(ctx.ilParleEnContinu(), false, 'tout est dit');
  ctx.etat.reponseVoix = 'm2'; ctx.etat.flux = {}; ctx.lecteur.actif = true;
  assert.strictEqual(ctx.ilParleEnContinu(), false, 'une nouvelle réponse repart de « va parler »');
  assert.match(PAGE, /hakim_parle: typeof ilParleEnContinu === 'function' && ilParleEnContinu\(\)/, 'le widget et la bulle aussi');
});

// (14:31) les fondus : le meuble monte en 0,2 s et s'efface sur ses 0,4 dernières secondes, en courbes à puissance constante
test('chaque meuble monte en 0,2 s et s\'efface sur 0,4 s (puissance constante) ; sa réponse l\'efface en 0,2 s', () => {
  const corps = fonction(PAGE, 'creerLecteurNeuronal');
  assert.match(corps, /const FONDU = 0\.2, FONDU_SORTIE = 0\.4, FONDU_REPONSE = 0\.2;/);
  assert.match(corps, /HESITER_APRES = 0\.2,/);
  assert.match(corps, /setValueCurveAtTime\(courbe\('monte', gv\), t, fe\)/);
  assert.match(corps, /setValueCurveAtTime\(courbe\('descend', gv\), t \+ joue - fs, fs\)/);
  assert.match(corps, /cancelAndHoldAtTime/);
});

test('une voyelle tout au bout du mot (« euh » qui finit sur sa voyelle) : bouclée sans sortir de sa voix', () => {
  const { ctx, tampon } = tenir();
  const sr = 24000, b = tampon(sr, Math.round(0.5 * sr)), d = b.getChannelData(0);
  for (let i = Math.round(0.05 * sr); i < d.length; i++) d[i] = 0.3 * Math.sin(2 * Math.PI * 110 * i / sr) + 0.1 * Math.sin(2 * Math.PI * 220 * i / sr);
  const o = ctx.tenirMeuble(b, 1.8).getChannelData(0);
  assert.ok(o.length >= Math.round(1.75 * sr), `étirée : ${(o.length / sr).toFixed(2)} s`);
  assert.ok(o.every(Number.isFinite), 'aucune valeur perdue');
});

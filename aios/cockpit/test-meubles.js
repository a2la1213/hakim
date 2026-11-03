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

// (14:20-14:40) le ressenti des meubles (leur ralenti, leurs transitions) se juge en pratique, par papa et Hakim (14:38)

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

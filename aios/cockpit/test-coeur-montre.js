/* (09/11, Ahmed à 17:24 : « que les données de ma montre soient directement récupérées depuis l'APK de la montre […] avec
   rafraîchissement à la seconde ») le cœur de papa en direct, du capteur de sa montre (appli montre 0.28) jusqu'à la situation de Hakim.
   node --test test-coeur-montre.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const CM = require('./coeur-montre.js');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const T = 1_800_000_000_000;

test('un lot de la montre : seules les mesures d’un cœur, à leur heure ; sans contact (-1) jeté', () => {
  const l = CM.lotDe({ ecran: true, mesures: [
    { t: T - 1000, bpm: 72.4, p: 3 }, { t: T - 900, bpm: 0, p: 0 }, { t: T - 800, bpm: 300, p: 3 }, { t: T - 700, bpm: 70, p: -1 },
    { t: T - 3600000, bpm: 70, p: 3 }, { t: T + 3600000, bpm: 70, p: 3 }, { t: T - 600, bpm: 64, p: 0 }, 'n’importe quoi'] }, T);
  assert.deepEqual(l.mesures, [{ t: T - 1000, bpm: 72, p: 3 }, { t: T - 600, bpm: 64, p: 0 }]);
  assert.equal(l.ecran, true);
  assert.equal(CM.lotDe({ mesures: [{ t: T, bpm: 0, p: 0 }] }, T), null, 'rien à garder');
  assert.equal(CM.lotDe(null, T), null);
  const c = CM.lotDe({ capacite: 'réveil', capteur: 'Samsung HR <script>', fabricant: 'Samsung', en_fond: true, mesures: [] }, T);
  assert.deepEqual(c.capacite, { capacite: 'réveil', capteur: 'Samsung HR script', fabricant: 'Samsung', en_fond: true });
  assert.equal(CM.lotDe({ capacite: 'tout', mesures: [] }, T), null, 'une capacité inconnue ne passe pas');
});

test('reçu : en ajout seul dans son fichier, gardé 10 min, un lot renvoyé ne compte pas deux fois ; frais 2 min au plus', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'coeur-montre-'));
  const fichier = path.join(dir, 'montre-coeur.jsonl');
  let maintenant = T;
  const c = CM.creer({ fichier, horloge: () => maintenant });
  assert.equal(c.texte(), '', 'rien reçu : rien dit');
  assert.deepEqual(c.recevoir({ ecran: false, mesures: [{ t: T - 4000, bpm: 70, p: 3 }, { t: T - 3000, bpm: 76, p: 3 }] }), { ok: true, gardees: 2 });
  c.recevoir({ ecran: false, mesures: [{ t: T - 3000, bpm: 76, p: 3 }, { t: T - 2000, bpm: 82, p: 3 }] });   // renvoyé en partie
  assert.equal(c.vue().mesures.length, 3);
  assert.equal(fs.readFileSync(fichier, 'utf8').trim().split('\n').length, 2, 'une ligne par lot reçu');
  assert.match(fs.readFileSync(fichier, 'utf8'), /"nature":"mesure, pas un diagnostic"/);
  assert.equal(c.texte(), 'cœur 82 bpm il y a 2 s, entre 70 et 82 sur 5 min — le capteur de son poignet, en direct ; une mesure, pas un diagnostic');
  assert.deepEqual(c.recevoir({ mesures: [{ t: T, bpm: 0, p: -1 }] }), { ok: false, erreur: 'mesures illisibles' });
  maintenant = T + 3 * 60000;
  assert.equal(c.texte(), '', 'plus de 2 min : plus en direct, rien dit');
  assert.equal(c.cle(), null);
  maintenant = T + 11 * 60000;
  c.recevoir({ mesures: [{ t: maintenant - 1000, bpm: 60, p: 0 }] });
  assert.equal(c.vue().mesures.length, 1, 'au-delà de 10 min, oublié de la mémoire (le fichier les garde)');
  assert.match(c.texte(), /^cœur 60 bpm il y a 1 s \(lecture peu fiable\)/);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('sa situation : dit quand il change de 5 bpm, étiqueté « pas un diagnostic », une lecture privée', () => {
  let maintenant = T;
  const ctx = { Math, Number, String, JSON, Date, Array, Object, Set, Intl, CONTEXTE_MAX: 100000, crypto: require('node:crypto'),
    lireLieux: () => [], lieuDe: () => null, jaugeForfait: () => ({ texte: '' }), appareilDe: () => 'son téléphone',
    CoeurMontre: CM.creer({ horloge: () => maintenant }) };
  vm.createContext(ctx);
  const debut = src.indexOf('const CAPTEURS_CHAMPS'), fin = src.indexOf('function capteursDe(');
  vm.runInContext(src.slice(debut, fin) + prendre('capteursDe') + prendre('positionDe') + prendre('blocSituation'), ctx);
  const sansRien = ctx.blocSituation({}, false, { appareil: 'son téléphone' }, T);
  assert.doesNotMatch(sansRien.texte, /en direct/);
  assert.equal(sansRien.prive, false);
  ctx.CoeurMontre.recevoir({ mesures: [{ t: T - 2000, bpm: 71, p: 3 }] });
  const a = ctx.blocSituation({}, false, { appareil: 'son téléphone' }, T);
  assert.match(a.texte, /sa montre, en direct : cœur 71 bpm il y a 2 s — le capteur de son poignet, en direct ; une mesure, pas un diagnostic/);
  assert.equal(a.prive, true, 'son cœur : une lecture privée (la porte du web se ferme)');
  ctx.CoeurMontre.recevoir({ mesures: [{ t: T - 1000, bpm: 72, p: 3 }] });
  const b = ctx.blocSituation({}, false, { appareil: 'son téléphone', ...a.dit }, T);
  assert.doesNotMatch(b.texte, /en direct/, 'un battement de plus : pas redit');
  ctx.CoeurMontre.recevoir({ mesures: [{ t: T - 500, bpm: 95, p: 3 }] });
  const c = ctx.blocSituation({}, false, { appareil: 'son téléphone', ...b.dit }, T);
  assert.match(c.texte, /cœur 95 bpm/, 'il change vraiment : redit');
});

test('branché : la route sous /api/corps (jeton), le fichier jarvis, la situation ; les blocs de test sans lui ne cassent pas', () => {
  const i = src.indexOf("if (p === '/api/corps/coeur-montre')");
  assert.ok(i > src.indexOf("if (p.startsWith('/api/corps/'))"), 'sous /api/corps/ : le jeton est exigé');
  assert.match(src.slice(i, i + 400), /CoeurMontre\.recevoir\(await lire\(\)\)/);
  assert.match(src.slice(i, i + 400), /CoeurMontre\.vue\(Date\.now\(\)\)/);
  assert.match(src, /require\('\.\/coeur-montre\.js'\)\.creer\(\{ fichier: path\.join\(JARVIS, 'montre-coeur\.jsonl'\) \}\)/);
  assert.match(prendre('blocSituation'), /typeof CoeurMontre === 'object'/);
});

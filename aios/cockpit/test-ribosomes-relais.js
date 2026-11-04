// (04/11, 23:10, Ahmed : « un ribosome par cœur pour sa parole ; quand il finit le processing d'une parole, le 2e chunk prend le relais direct
// sur un autre cœur, jusqu'au 8e qui boucle et revient au premier ; la 2e parole démarre selon un réglage : le pourcentage du plafond de mots »)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = SRC.indexOf(`function ${nom}(`); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2); };
const ligne = (d) => SRC.slice(SRC.indexOf(d), SRC.indexOf('\n', SRC.indexOf(d)));

function monter(reglage = {}) {
  let t = 1000;
  const sortis = [], memos = [], minuteries = [];
  const ctx = { Math, Number, String, Map, sortis, memos, reglage,
    tourEpissure: () => ++t, reglageRibosome: () => reglage, memoriserEpissure: (r) => memos.push(r),
    sortirPaquet: (tour, r, x) => { r.k++; sortis.push([r.coeur, x]); },
    setTimeout: (f, ms) => { const m = { f, ms, unref() {} }; minuteries.push(m); return m; }, clearTimeout: (m) => { if (m) m.f = null; },
    motsEpisses: (x) => String(x || '').split(/\s+/).filter(Boolean), lireLaSuite: () => {} };
  vm.createContext(ctx);
  vm.runInContext([ligne('const RIBOSOME_PLAFOND = '), ligne('const nouveauRibosome = '), ligne('const RIBOSOME_RELAIS = '), 'let dernierRibosome = null;',
    ligne('const aToutSorti = '), ...['plafondRibosome', 'relaisRibosome', 'ribosomeAuRelais', 'ribosomeSuivant', 'libererRibosome', 'sortirDansLOrdre', 'lireRibosome'].map(prendre),
    'this.f = { relaisRibosome, ribosomeAuRelais, ribosomeSuivant, sortirDansLOrdre, lireRibosome, aToutSorti };'].join('\n'), ctx);
  return { ...ctx.f, sortis, memos, minuteries };
}

test('ses ribosomes en boucle : du 1er au 8e, puis le 1er reprend (le 9e) ; réglable de 1 à 8', () => {
  const { ribosomeSuivant } = monter();
  const coeurs = Array.from({ length: 9 }, () => ribosomeSuivant().coeur);
  assert.deepStrictEqual(coeurs, [1, 2, 3, 4, 5, 6, 7, 8, 1]);
  const trois = monter({ relais_ribosomes: 3 });
  assert.deepStrictEqual(Array.from({ length: 5 }, () => trois.ribosomeSuivant().coeur), [1, 2, 3, 1, 2]);
  assert.strictEqual(monter({ relais_ribosomes: 99 }).relaisRibosome().ribosomes, 8, 'borné à 8');
});

test('le relais : à 75 % du plafond de mots (30 sur 40), le suivant s’ouvre ; 100 % ou un seul ribosome : jamais', () => {
  const { ribosomeAuRelais, relaisRibosome } = monter();
  const r = { phrase: Array(29).fill('mot').join(' ') };
  assert.strictEqual(ribosomeAuRelais(r), false, '29 mots');
  r.phrase += ' trente';
  assert.strictEqual(ribosomeAuRelais(r), true, '30 mots : 75 % de 40');
  assert.strictEqual(ribosomeAuRelais({ ...r, relaye: true }), false, 'déjà relayé');
  assert.strictEqual(ribosomeAuRelais({ ...r, ferme: 'plafond' }), false, 'fermé');
  assert.strictEqual(ribosomeAuRelais({ ...r, source: 'telephone' }), false, 'son oreille interne garde son propre ribosome');
  assert.strictEqual(monter({ relais_pct: 50 }).ribosomeAuRelais({ phrase: Array(20).fill('mot').join(' ') }), true, 'réglé à 50 %');
  assert.strictEqual(monter({ relais_pct: 100 }).ribosomeAuRelais(r), false);
  assert.strictEqual(monter({ relais_ribosomes: 1 }).ribosomeAuRelais(r), false);
  assert.deepStrictEqual({ ...relaisRibosome() }, { ribosomes: 8, pct: 75 });
});

test('sa voix dans l’ordre : le 2e attend que le 1er ait tout sorti, puis parle ; le 1er devient un souvenir', () => {
  const { ribosomeSuivant, sortirDansLOrdre, sortis, memos } = monter();
  const r1 = ribosomeSuivant();
  r1.phrase = 'déjà dit par le premier'; r1.enVol = 1;                 // le 1er lit encore son dernier paquet
  const r2 = ribosomeSuivant();
  assert.ok(r1.relaye && r2.precedent === r1 && r1.suivant === r2);
  assert.strictEqual(r2.herite, 'déjà dit par le premier', 'le 2e connaît ce qui a été dit');
  r2.prets.set(0, { garde: 'deux' });
  sortirDansLOrdre(r2.tour, r2);
  assert.deepStrictEqual(sortis, [], 'le 2e attend');
  r1.enVol = 0; r1.prets.set(0, { garde: 'un' });
  sortirDansLOrdre(r1.tour, r1);
  assert.deepStrictEqual(sortis.map(([c, x]) => [c, x.garde]), [[1, 'un'], [2, 'deux']], 'le 1er, puis le 2e');
  assert.ok(r1.libere && memos[0] === r1 && !r2.precedent);
});

test('un ribosome remplacé sans rien en cours passe la main tout de suite ; une pensée en retard va au suivant', () => {
  const { ribosomeSuivant, sortirDansLOrdre, lireRibosome, sortis } = monter();
  const r1 = ribosomeSuivant(), r2 = ribosomeSuivant();
  assert.ok(r1.libere && !r2.precedent, 'rien en cours : pas d’attente');
  r2.prets.set(0, { garde: 'deux' });
  sortirDansLOrdre(r2.tour, r2);
  assert.strictEqual(sortis.length, 1);
  lireRibosome(0, 'une pensée en retard', 'papa', r1);
  assert.strictEqual(r1.pave, '', 'pas dans celui qui a passé la main');
  assert.strictEqual(r2.pave, 'une pensée en retard', 'dans le suivant');
});

test('celui d’avant bloqué : le suivant parle quand même au bout de 20 s', () => {
  const { ribosomeSuivant, sortirDansLOrdre, sortis, minuteries } = monter();
  const r1 = ribosomeSuivant(); r1.enVol = 1;
  const r2 = ribosomeSuivant();
  r2.prets.set(0, { garde: 'deux' });
  sortirDansLOrdre(r2.tour, r2);
  assert.strictEqual(sortis.length, 0);
  assert.strictEqual(minuteries.length, 1);
  assert.strictEqual(minuteries[0].ms, 20000);
  minuteries[0].f();
  assert.deepStrictEqual(sortis.map(([c, x]) => [c, x.garde]), [[2, 'deux']]);
});

test('branché : le relais dans lancerPiste, le cœur jusqu’à la page, les réglages dans la page Réglages', () => {
  assert.match(SRC, /else if \(pistes\.ribo && ribosomeAuRelais\(pistes\.ribo\)\) relayer\(\);/);
  // (05/11, Ahmed : « en cascade automatiquement, en envoyant des blancs ») dès le seuil, sans attendre la pensée suivante, et avec son blanc
  assert.match(SRC, /if \(x && pistes\.ribo === r && ribosomeAuRelais\(r\)\) relayer\(\);/);
  assert.match(prendre('relayer'), /pistes\.ribo = ribosomeSuivant\(\);\n  if \(corpsReglages\(\)\.epissage !== false\) blancDeReflexion\(pistes\.ribo, BLANC_RELAIS\);/);
  assert.match(SRC, /m\.ribo = pistes\.ribo \|\| \(pistes\.ribo = ribosomeSuivant\(\)\);/);
  assert.match(SRC, /\.\.\.\(r\.coeur \? \{ coeur: r\.coeur \} : \{\}\)/);
  assert.match(SRC, /nombre\('relais_ribosomes', 1, 8\); nombre\('relais_pct', 10, 100\);/);
  assert.match(SRC, /neutraliser\(`\$\{r\.herite \|\| ''\} \$\{r\.phrase\}`\.trim\(\)\)/, 'le suivant lit la fin de ce qui a été dit');
  const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  assert.match(PAGE, /if \(o\.coeur\) p\.coeur = Number\(o\.coeur\) \|\| p\.coeur;/);
  const REG = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
  assert.match(REG, /\['relais_ribosomes', /);
  assert.match(REG, /\['relais_pct', /);
});

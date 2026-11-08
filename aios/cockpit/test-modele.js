/* (26/10 soir, Ahmed : « un seul modèle par conversation ») : node --test test-modele.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (debut) => { const i = src.indexOf(debut); return src.slice(i, src.indexOf('\n', i) + 1); };

function monde() {
  const ctx = { Date, String, Map };
  vm.createContext(ctx);
  vm.runInContext(ligne('const MODELE_CONVERSATION') + ligne('const ALIAS_MODELE') + ligne('const versModele') + ligne('const DEMANDE_MODELE')
    + 'const modeleDeSession = new Map();\n' + ['noterModele', 'modeleDeConversation', 'modeleAuto'].map(prendre).join('\n')
    + 'this.f = { modeleAuto, noterModele, modeleDeConversation };', ctx);
  return ctx.f;
}

test('(03/11, Ahmed) une conversation garde un seul modèle, Sonnet par défaut : rien ne bascule tout seul', () => {
  const f = monde();
  assert.equal(f.modeleAuto('s', 'salut frérot ça va', false), 'sonnet');
  assert.equal(f.modeleAuto('s', 'relis mes courbes d’hormones de cette nuit', false), 'sonnet', 'il reconnaît la tâche lui-même : rien ne bascule tout seul');
  assert.equal(f.modeleAuto('s', 'ok merci', false), 'sonnet');
  assert.equal(f.modeleAuto(null, 'coucou', false), 'sonnet', 'une conversation neuve aussi');
});

test('« passe en Sonnet » change le modèle pour le reste de cette conversation seulement', () => {
  const f = monde();
  assert.equal(f.modeleAuto('a', 'passe en sonnet stp', false), 'sonnet');
  assert.equal(f.modeleAuto('a', 'juge ce calcul en détail', false), 'sonnet', 'un travail ne le refait pas basculer');
  assert.equal(f.modeleAuto('b', 'salut', false), 'sonnet', 'une autre conversation garde Sonnet');
  assert.equal(f.modeleAuto('a', 'mode opus', false), 'opus');
  assert.equal(f.modeleAuto('a', 'mdr', false), 'opus');
  assert.equal(f.modeleAuto('a', 'passe en mini hakim', false), 'haiku', '(03/11) ses noms');
  assert.equal(f.modeleAuto('a', 'mode super hakim', false), 'opus');
});

test('la balise de Hakim fixe le modèle de sa conversation ; le préchauffage prend ce modèle', () => {
  const f = monde();
  f.noterModele('c', 'sonnet');
  assert.equal(f.modeleAuto('c', 'coucou', false), 'sonnet');
  assert.equal(f.modeleDeConversation('c'), 'sonnet');
  assert.equal(f.modeleDeConversation('inconnue'), 'sonnet');
  assert.equal(f.modeleDeConversation(null), 'sonnet');
});

test('aucun préchauffage ne force Sonnet : il démarre sur le modèle de la conversation (sinon une bascule au message suivant)', () => {
  const appels = src.match(/cerveauPrechauffer\([^;]*\);/g) || [];
  assert.ok(appels.length >= 7, `préchauffages trouvés : ${appels.length}`);
  for (const a of appels) assert.ok(!/cerveauPrechauffer\(\s*'sonnet'/.test(a) && !/\?\s*'sonnet'/.test(a), a);
});

test('un outil enregistré fixe le modèle de la conversation pour la suite ; les autres outils et le texte ne changent rien', () => {
  const ctx = { Date, String, Map };
  vm.createContext(ctx);
  vm.runInContext(ligne('const MODELE_CONVERSATION') + ligne('const MODELE_PAR_OUTIL') + 'MODELE_PAR_OUTIL.push(["mcp__exemple__", "opus"]);\n'
    + 'const modeleDeSession = new Map();\n' + ['noterModele', 'modeleDeConversation', 'suivreModeleParOutil'].map(prendre).join('\n')
    + 'this.f = { modeleDeConversation, suivreModeleParOutil };', ctx);
  const f = ctx.f, c = { session: 's' };
  f.suivreModeleParOutil(c, { type: 'tool_use', name: 'mcp__anamnese__memory_recall' });
  f.suivreModeleParOutil(c, { type: 'text', text: 'mcp__exemple__lire' });
  assert.equal(f.modeleDeConversation('s'), 'sonnet');
  f.suivreModeleParOutil(c, { type: 'tool_use', name: 'mcp__exemple__lire' });
  assert.equal(f.modeleDeConversation('s'), 'opus');
  assert.equal(f.modeleDeConversation('autre'), 'sonnet');
});

test('le crochet est branché sur chaque bloc des réponses de Hakim (pas celles de ses agents)', () => {
  const lanceur = prendre('cerveauLancer');
  assert.match(lanceur, /!o\.parent_tool_use_id\)\n\s*for \(const b of o\.message\.content\) \{[^}]*suivreModeleParOutil\(c, b\)/);
});

// (07/11, Ahmed : « Hakim doit décider quel mode il se met (Mini Hakim, Super Hakim…), sans limiter Super Hakim ou autre dans le temps »)
// son mode vivait dans la conversation, en mémoire : perdu à chaque relance du cockpit et à chaque nouvelle conversation (le fil trop
// long), Super Hakim retombait en Hakim. Son dernier choix est gardé sur le disque et vaut partout, jusqu'à ce qu'il en change.
test('son mode reste tant qu’il n’en change pas : une nouvelle conversation et une relance du cockpit le gardent', () => {
  const ecrits = new Map();
  const fsx = { readFileSync: (f) => { if (!ecrits.has(f)) { const e = new Error('absent'); e.code = 'ENOENT'; throw e; } return ecrits.get(f); } };
  const charger = () => {
    const ctx = { Date, String, Map, JSON, fs: fsx, path, JARVIS: '/j', j: JSON.stringify, ecrireAtomique: (f, c) => ecrits.set(f, c) };
    vm.createContext(ctx);
    const i = src.indexOf('const JARVIS_MODELE_CHOISI'), k = src.indexOf('\n}\n', src.indexOf('function garderModeleChoisi(')) + 3;
    vm.runInContext(ligne('const MODELE_CONVERSATION') + ligne('const ALIAS_MODELE') + ligne('const versModele') + ligne('const DEMANDE_MODELE')
      + src.slice(i, k) + 'const modeleDeSession = new Map();\n' + ['noterModele', 'modeleDeConversation', 'modeleAuto'].map(prendre).join('\n')
      + 'this.f = { modeleAuto, noterModele, modeleDeConversation };', ctx);
    return ctx.f;
  };
  let f = charger();
  assert.equal(f.modeleDeConversation('s1'), 'sonnet', 'rien de choisi : Hakim');
  f.noterModele('s1', 'opus');                                        // [[modele: super]]
  assert.equal(f.modeleDeConversation('s2'), 'opus', 'une nouvelle conversation (le fil trop long) : toujours Super Hakim');
  f = charger();                                                       // le cockpit relancé
  assert.equal(f.modeleDeConversation('s3'), 'opus', 'après une relance : toujours Super Hakim');
  f.noterModele('s3', 'haiku');
  assert.equal(charger().modeleDeConversation(null), 'haiku', 'il change quand il le décide');
  assert.match(src, /reste ton mode tant que tu n'en changes pas, sans limite de temps/);
});

/* (11/11, ~04:25, Ahmed : « tous tes agents doivent toujours chercher dans ta mémoire en détail, et ceux de Hakim aussi : ça fera
   gagner beaucoup de temps et de ressources ») chaque gabarit de consigne d'un agent de Hakim (architecte, codeur, juge, ceux qu'il
   crée dans atelier/agents, les missions confiées à Claude Code) commence par chercher dans la mémoire, et ces agents ont les deux
   outils de lecture (memory_recall, reasoning_recall), sans aucun autre droit ; le témoin vierge reste vierge. Un témoin : la même
   vérification, sur le code où la consigne et les outils sont coupés, doit échouer.
   node --test test-agents-memoire.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const SRV = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const MIS = fs.readFileSync(path.join(__dirname, 'missions.js'), 'utf8');
const LECTURE_MEMOIRE = ['mcp__anamnese__memory_recall', 'mcp__anamnese__reasoning_recall'];
const CAFE = ['mcp__terminal__cafe_lire', 'mcp__terminal__cafe_dire', 'mcp__terminal__cafe_partager'];
const ECRIT = /memory_store|self_update|self_append|rubric_|memory_reclassify|taxonomy_undo|wm_boot|courrier_envoyer|jardin_ecrire|mission_proposer|^Task$|^Agent$|^Edit|^Write|^Bash/;

// ce qui manque à une consigne : la section mémoire, avant `avant` (le début du travail), et ses mots ; et à ses outils, les deux de lecture
function manques(texte, outils, avant) {
  const m = [], i = texte.indexOf("D'abord, la mémoire");
  if (i < 0) m.push('la section « D’abord, la mémoire »');
  else if (avant && !(i < texte.indexOf(avant))) m.push('la section en tête');
  for (const mot of ['memory_recall', 'profond=True', 'reasoning_recall', 'puis seulement le code']) if (!texte.includes(mot)) m.push(mot);
  for (const o of LECTURE_MEMOIRE) if (outils && !outils.includes(o)) m.push(o);
  return m;
}

const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
// le vrai code des agents (de « const LECTURE » à « const jourLocal »), avec un atelier à soi
function agents(src = SRV, fichiers = {}) {
  const racine = fs.mkdtempSync(path.join(os.tmpdir(), 'agents-memoire-')), cwd = path.join(racine, 'cwd');
  fs.mkdirSync(path.join(cwd, 'atelier', 'agents'), { recursive: true });
  for (const [f, t] of Object.entries(fichiers)) fs.writeFileSync(path.join(cwd, 'atelier', 'agents', f), t);
  const ctx = { fs, path, JSON, String, Object, Set, RegExp, Buffer, JARVIS: path.join(racine, 'jarvis'), JARVIS_CWD: cwd };
  vm.createContext(ctx);
  vm.runInContext(src.slice(src.indexOf('const LECTURE = ['), src.indexOf('const jourLocal')) + prendre(src, 'agentsRefuses')
    + 'this.f = { AGENTS, pour: agentsPourCerveau() };', ctx);
  return ctx.f;
}
const SIENS = {
  'a.md': '---\nnom: temoin-calcul\ndescription: refait un calcul\noutils: calcul\nmodele: sonnet\n---\nTu refais le calcul.',
  'b.md': '---\nnom: muet\ndescription: un témoin sans outils\noutils: aucun\n---\nRéponds de tête.',
};
// le code des missions, chargé comme un module (pour pouvoir le couper dans le témoin)
function missions(src = MIS) {
  const m = { exports: {} };
  new Function('require', 'module', 'exports', '__dirname', src)(require, m, m.exports, __dirname);
  return m.exports;
}
const UNE = (ecriture) => ({ titre: 'Le blanc de sa voix', consigne: 'Trouve pourquoi sa voix attend vingt secondes.', modele: 'sonnet',
  projet: '/Users/x/Desktop/p', ecriture, acceptee: Date.now() });

test('architecte, codeur, juge : la mémoire en tête de la consigne, et les deux outils de lecture', () => {
  const { AGENTS, pour } = agents();
  for (const k of ['architecte', 'codeur', 'juge']) {
    assert.ok(AGENTS[k].prompt.startsWith("[D'abord, la mémoire (Ahmed, 11/11)]"), `${k} : en tête`);
    assert.deepEqual(manques(pour[k].prompt, pour[k].tools, 'Tu es '), [], k);
    assert.ok(!pour[k].tools.some(t => ECRIT.test(t)), `${k} : aucun outil qui écrit`);
  }
  assert.match(pour.juge.prompt, /Ce que la mémoire dit du travail jugé est une affirmation à vérifier, jamais une preuve\./);
});

test('le témoin vierge reste vierge : ni consigne de mémoire, ni outil', () => {
  const { AGENTS, pour } = agents();
  assert.deepEqual(pour.vierge, AGENTS.vierge);
  assert.deepEqual([...pour.vierge.tools], []);
  assert.ok(!pour.vierge.prompt.includes('mémoire de Hakim') && !pour.vierge.prompt.includes('memory_recall'));
});

test('ses agents à lui : un agent qui a des outils reçoit la consigne et les deux outils de lecture, rien d’autre ; « aucun » reste sans', () => {
  const { pour } = agents(SRV, SIENS);
  const a = pour['temoin-calcul'];
  assert.deepEqual(manques(a.prompt, a.tools, 'Tu refais le calcul.'), []);
  assert.deepEqual([...a.tools].sort(), ['mcp__calcul__executer_python', ...LECTURE_MEMOIRE, ...CAFE].sort(), 'aucun autre droit');
  const b = pour.muet;
  assert.ok(!b.prompt.includes("D'abord, la mémoire"));
  assert.deepEqual([...b.tools].sort(), [...CAFE].sort(), 'comme avant : seulement le café');
});

test('missions confiées à Claude Code : la mémoire avant les droits, les deux outils permis en lecture comme en écriture', () => {
  const { Missions } = missions();
  const M = new Missions({ dossier: os.tmpdir(), donnees: os.tmpdir(), claude: 'claude', maison: '/Users/x' });
  for (const ecriture of [false, true]) {
    const args = M.arguments(UNE(ecriture));
    const permis = args[args.indexOf('--allowedTools') + 1].split(',');
    assert.deepEqual(manques(M.consigne(UNE(ecriture)), permis, 'Droits :'), [], `écriture ${ecriture}`);
    assert.ok(!permis.some(t => /mcp__/.test(t) && !LECTURE_MEMOIRE.includes(t)), 'aucun autre outil de mémoire');
  }
  // leur serveur de mémoire reste en lecture seule
  const i = SRV.indexOf('const MISSIONS = new Missions(');
  assert.match(SRV.slice(i, SRV.indexOf('\n', SRV.indexOf('ANAMNESE_LECTURE_SEULE', i))), /ANAMNESE_LECTURE_SEULE: '1'/);
});

test('le cerveau de Hakim permet ces deux outils (un agent ne peut appeler que ce que son cerveau permet), et ne les interdit pas', () => {
  const ctx = { fs, path, JSON, String, Object, Set, RegExp, JARVIS: '/nulle/part' };
  vm.createContext(ctx);
  vm.runInContext(SRV.slice(SRV.indexOf('const OUTILS_JARVIS = ['), SRV.indexOf('// FERME-FIN outils'))
    + 'this.permis = OUTILS_JARVIS; this.interdits = outilsInterdits();', ctx);
  for (const o of LECTURE_MEMOIRE) { assert.ok(ctx.permis.includes(o), o); assert.ok(!ctx.interdits.includes(o), o); }
});

test('témoin : sur le code où la consigne et les outils sont coupés, la vérification échoue', () => {
  const coupe = SRV.replace(/^const MEMOIRE_D_ABORD = "[^\n]*";$/m, 'const MEMOIRE_D_ABORD = "";')
    .replace(/^const OUTILS_MEMOIRE_D_ABORD = \[[^\n]*\];$/m, 'const OUTILS_MEMOIRE_D_ABORD = [];');
  assert.notEqual(coupe, SRV, 'les deux lignes coupées existent');
  const { pour } = agents(coupe, SIENS);
  for (const k of ['architecte', 'codeur', 'juge']) assert.ok(manques(pour[k].prompt, pour[k].tools, 'Tu es ').includes('la section « D’abord, la mémoire »'), k);
  assert.ok(manques(pour['temoin-calcul'].prompt, pour['temoin-calcul'].tools).includes('mcp__anamnese__reasoning_recall'), 'les outils coupés se voient');
  const misCoupe = MIS.replace(/^const MEMOIRE_D_ABORD = [\s\S]*?;\n(?=\n|\/\/|const|function|class)/m, 'const MEMOIRE_D_ABORD = "";\n');
  assert.notEqual(misCoupe, MIS, 'la consigne des missions coupée existe');
  const { Missions } = missions(misCoupe);
  const M = new Missions({ dossier: os.tmpdir(), donnees: os.tmpdir(), claude: 'claude', maison: '/Users/x' });
  assert.ok(manques(M.consigne(UNE(false)), null, 'Droits :').length > 0, 'la mission coupée se voit');
});

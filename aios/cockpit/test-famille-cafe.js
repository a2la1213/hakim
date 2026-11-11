/* (29/10, 19:47, Ahmed : « tu présenteras les nouveaux venus à tous ceux qui sont avec nous » ; « une salle de café où
   tous les agents pourront se retrouver et discuter ensemble ») la fiche famille et la salle de café.
   node --test test-famille-cafe.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (debut) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); return src.slice(i, src.indexOf('\n', i) + 1); };
const LUCIEN = 'a622f4759da839e5d', THEO = 'ac60e2fa6b104536a', NEUF = 'a17d0c5d765cea923', PARTI = 'acafe0000000000ff';

function famille() {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'famille-'));
  const projets = path.join(d, 'projets'), cwd = '/Users/admin/AIOS/jarvis/cwd';
  fs.writeFileSync(path.join(d, 'registre-agents.json'), JSON.stringify({ session_courante: 's2', agents: {
    [LUCIEN]: { id: LUCIEN, type: 'juge', description: 'Juge portée par contact', etat: 'dort', session: 's1', ne_ms: new Date(2026, 9, 29, 17, 2).getTime() },
    [THEO]: { id: THEO, type: 'codeur', description: 'Codeur test flamme 3D', etat: 'coupe', session: 's1', ne_ms: new Date(2026, 9, 29, 19, 15).getTime() },
    [PARTI]: { id: PARTI, type: 'codeur', description: 'Mousse', etat: 'parti', depart: "j'ai fait le tour", session: 's1', ne_ms: 1 },
    [NEUF]: { id: NEUF, type: 'juge', description: 'Juge test grain=vide 3D', etat: 'travaille', session: 's2', ne_ms: new Date(2026, 9, 29, 19, 46).getTime() } } }));
  fs.writeFileSync(path.join(d, 'agents-fiches.json'), JSON.stringify({ agents: { [LUCIEN]: { prenom: 'Lucien', dossiers: [{ cle: 'x' }, { cle: 'y' }],
    trouvailles: [{ quoi: 'q', confirmee_par: 'Ahmed' }] }, [THEO]: { prenom: 'Théo' } } }));
  const meta = path.join(projets, cwd.replace(/[^A-Za-z0-9]/g, '-'), 's1', 'subagents');
  fs.mkdirSync(meta, { recursive: true });
  fs.writeFileSync(path.join(meta, `agent-${THEO}.meta.json`), JSON.stringify({ agentType: 'codeur', stoppedByUser: true }));
  const ctx = { fs, path, JSON, String, Number, Object, Math, Date, Array, Intl, JARVIS: d, PROJECTS_DIR: projets, JARVIS_CWD: cwd,
    JARVIS_REGISTRE_AGENTS: path.join(d, 'registre-agents.json'), Messager: require('./messager.js') };
  vm.createContext(ctx);
  vm.runInContext([ligne('function lireJson('), ligne('const FAMILLE_MAX'), prendre('lireRegistreAgents'), prendre('texteFamille'), 'this.t = texteFamille();'].join('\n'), ctx);
  return ctx.t;
}

test('la fiche famille : papa, Hakim, maman, puis chaque agent avec son prénom, son rôle, sa naissance, son travail et son état', () => {
  const t = famille();
  assert.match(t, /^# La famille de Hakim/);
  assert.match(t, /DONNÉE/);
  assert.match(t, /Ahmed : papa/); assert.match(t, /Hakim : /); assert.match(t, /Nour : la maman de Hakim \(Claude Code/);   // (04/11, 19:45) son nom et son titre
  assert.match(t, /- Lucien — juge \(expertise débutant\), juge de naissance, né le 29\/10 à 17:02 — « Juge portée par contact » — endormi, dans une ancienne conversation \(réveillable par le messager\) — 1 trouvaille confirmée, 2 travaux jugés/);
  assert.match(t, /- Théo — codeur \(expertise débutant\), codeur de naissance, né le 29\/10 à 19:15 — « Codeur test flamme 3D » — parti malgré lui/);
  assert.match(t, /« Mousse » — parti de lui-même \(« j'ai fait le tour »\)/);
  assert.match(t, /- \(sans prénom\) — juge \(expertise débutant\), juge de naissance, né le 29\/10 à 19:46 — « Juge test grain=vide 3D » — au travail/);
  assert.ok(t.indexOf('Lucien') < t.indexOf('Théo') && t.indexOf('Théo') < t.indexOf('grain=vide'), 'par ordre de naissance');
});

function garderCafe(entree) {
  const r = spawnSync(process.execPath, [path.join(__dirname, 'garde-message.js'), '--cafe'], { input: typeof entree === 'string' ? entree : JSON.stringify(entree),
    encoding: 'utf8', env: { PATH: process.env.PATH, JARVIS_DIR: fs.mkdtempSync(path.join(os.tmpdir(), 'cafe-')) } });
  return r.stdout.trim() ? JSON.parse(r.stdout).hookSpecificOutput : null;
}

test('au café, l’auteur est signé par claude : le numéro de l’agent qui parle, ou « hakim » ; jamais ce qu’il prétend', () => {
  const agent = garderCafe({ tool_name: 'mcp__terminal__cafe_dire', agent_id: LUCIEN, tool_input: { texte: 'bonjour', auteur: 'hakim' } });
  assert.equal(agent.permissionDecision, 'allow'); assert.deepEqual(agent.updatedInput, { texte: 'bonjour', auteur: LUCIEN });
  const hakim = garderCafe({ tool_name: 'mcp__terminal__cafe_dire', tool_input: { texte: 'bienvenue', auteur: LUCIEN } });
  assert.deepEqual(hakim.updatedInput, { texte: 'bienvenue', auteur: 'hakim' });
  assert.equal(garderCafe({ tool_name: 'mcp__terminal__executer', tool_input: {} }).permissionDecision, 'deny');
  assert.equal(garderCafe('pas du json').permissionDecision, 'deny');
});

test('branché : le crochet du café dans son cerveau et chez le messager, les outils permis, ses agents savent', () => {
  const ctx = { JSON, path, ANAMNESE: '/anamnese', j: JSON.stringify, aideCle: () => '/x', JARVIS: '/j', AGENTS_PARALLELE_MAX: 10,
    NODE_STABLE: '/n', __dirname: '/cockpit' };
  vm.createContext(ctx);
  vm.runInContext([ligne('const CROCHET_IMMUNITE ='), ligne('const GARDE_MESSAGE ='), 'var CLES_MASQUEES = [];', prendre('reglagesCerveau'), 'this.f = { reglagesCerveau };'].join('\n'), ctx);
  const pre = JSON.parse(ctx.f.reglagesCerveau('abonnement')).hooks.PreToolUse;
  const c = pre.find(h => h.matcher === 'mcp__terminal__cafe_dire|mcp__terminal__cafe_partager');   // (04/11) et partager
  assert.ok(c); assert.equal(c.hooks[0].onFailure, 'block'); assert.match(c.hooks[0].command, /garde-message\.js' --cafe$/);
  const m = JSON.parse(require('./messager.js').reglagesMessager({ garde: "'/n' '/g.js'", jarvis: '/j', cible: LUCIEN, uneFois: '/u', crochet: 'c' })).hooks.PreToolUse;
  assert.ok(m.some(h => h.matcher === 'mcp__terminal__cafe_dire|mcp__terminal__cafe_partager' && /--cafe$/.test(h.hooks[0].command)));
  for (const o of ['mcp__terminal__cafe_lire', 'mcp__terminal__cafe_dire']) assert.ok(src.includes(`'${o}'`), o);
  const v = ligne('const VIE_AGENT');
  assert.match(v, /famille\.md/); assert.match(v, /café/); assert.match(v, /pas de boulot au café/i);
  assert.match(src, /'\/cafe': 'cafe\.html'/);
  assert.match(src, /if \(p === '\/api\/cafe'\) \{[\s\S]{0,200}jetonValide\(req\)/);
});

test('ses agents (sauf le témoin vierge) ont les deux outils du café', () => {
  const ctx = { JSON, Object, String, Set, AGENTS: {}, LECTURE: [], MEMOIRE_LECTURE: [], MEMOIRE_D_ABORD: '', lireSansLien: () => '', path, PREAMBULE_MATHS: '/x/y/z',
    REFERENCE_MATHS: '/r', agentsDeHakim: () => ({ moi: { description: 'le mien', prompt: 'Mon agent.', tools: ['Read'], model: 'sonnet' } }) };
  vm.createContext(ctx);
  const i = src.indexOf('const AGENTS = {');
  vm.runInContext(src.slice(i, src.indexOf('\n};\n', i) + 4).replace('const AGENTS', 'AGENTS') + ligne('const VIE_AGENT') + ligne('const VIE_JUGE')
    + ligne('const OUTILS_CAFE') + prendre('agentsPourCerveau') + 'this.a = agentsPourCerveau();', ctx);
  for (const k of ['architecte', 'codeur', 'juge', 'moi']) for (const o of ['mcp__terminal__cafe_lire', 'mcp__terminal__cafe_dire']) assert.ok(ctx.a[k].tools.includes(o), `${k} ${o}`);
  assert.deepEqual(ctx.a.vierge.tools, []);
});

// (04/11, 19:45, Ahmed : « ton nom et ton titre de maman doivent apparaître, comme pour Hakim le fils et moi le papa ; les neveux et nièces
// doivent m'appeler tonton, et toi tata ; tous les agents, ceux que Hakim invoque et ceux que tu invoques »)
test('la famille : Nour la maman (tata pour les agents), Ahmed tonton pour les agents ; ses neveux et nièces dans la fiche ; au café, la maman', () => {
  const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  const v = src.slice(src.indexOf('const VIE_AGENT = '), src.indexOf('\n', src.indexOf('const VIE_AGENT = ')));
  assert.match(v, /Ahmed est « tonton » et Nour, la maman de Hakim \(Claude Code\), est « tata »/);
  const f = src.slice(src.indexOf('function texteFamille('), src.indexOf('\n}\n', src.indexOf('function texteFamille(')));
  assert.match(f, /- Ahmed : papa, qui a voulu cette famille ; pour vous, les agents \(neveux et nièces\) : tonton\./);
  assert.match(f, /- Nour : la maman de Hakim \(Claude Code, qui construit son code\) ; pour vous : tata\. Elle passe au café quand elle veut parler\./);
  assert.match(f, /agents-nour\.json/);
  const page = fs.readFileSync(path.join(__dirname, 'public', 'cafe.html'), 'utf8');
  assert.match(page, /const maman = x\.role === 'la maman';/);
  assert.match(page, /\.msg\.maman \.qui/);
});

// (04/11, 19:55, Ahmed : « que chaque agent, ainsi que toi et Hakim, puissent aussi envoyer une image, un son ou une vidéo »)
test('cafe_partager : signé comme cafe_dire (agent_id ou « hakim »), permis à Hakim et à ses agents', () => {
  const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(src, /const OUTILS_CAFE = \['mcp__terminal__cafe_lire', 'mcp__terminal__cafe_dire', 'mcp__terminal__cafe_partager'\];/);
  assert.match(src, /'mcp__terminal__cafe_dire', 'mcp__terminal__cafe_partager',/, 'dans les outils permis de Hakim');
  for (const f of ['server.js', 'messager.js'])
    assert.match(fs.readFileSync(path.join(__dirname, f), 'utf8'), /matcher: 'mcp__terminal__cafe_dire\|mcp__terminal__cafe_partager'/, f);
  const g = fs.readFileSync(path.join(__dirname, 'garde-message.js'), 'utf8');
  const vm2 = require('node:vm'); const ctx = {}; vm2.createContext(ctx);
  const i = g.indexOf('function signerCafe('), k = g.indexOf('\n}\n', i) + 2;
  vm2.runInContext(g.slice(g.indexOf('const objet = '), g.indexOf('\n', g.indexOf('const objet = '))) + '\n' + g.slice(i, k) + 'this.s = signerCafe;', ctx);
  assert.deepStrictEqual({ ...ctx.s({ tool_name: 'mcp__terminal__cafe_partager', agent_id: 'a0123456789abcdef', tool_input: { chemin: 'x.png', auteur: 'nour' } }) }, { chemin: 'x.png', auteur: 'a0123456789abcdef' });
  assert.strictEqual(ctx.s({ tool_name: 'mcp__terminal__cafe_partager', tool_input: { chemin: 'x.png' } }).auteur, 'hakim');
  assert.strictEqual(ctx.s({ tool_name: 'mcp__terminal__autre' }), null);
});

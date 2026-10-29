/* (29/10, Ahmed : « on ne les tue pas, on les met en sommeil » ; « on prolonge leur vie au maximum, jusqu'à ce qu'eux-mêmes
   en aient assez ») la vie des agents de Hakim : le registre (travaille, dort, parti, arrêté, coupé), SendMessage et sa
   garde dans son cerveau, leurs prompts. node --test test-vie-agents.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (debut) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); return src.slice(i, src.indexOf('\n', i) + 1); };
const ID = 'a7514e29068e49980';

function registre() {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'vie-agents-'));
  const ctx = { fs, path, crypto, JSON, String, Number, Object, Math, Date, Array, console: { error() {} }, j: JSON.stringify, process: { pid: 1 },
    JARVIS: d, JARVIS_REGISTRE_AGENTS: path.join(d, 'registre-agents.json') };
  vm.createContext(ctx);
  vm.runInContext([prendre('ecrireAtomique'), ligne('function lireJson('), ligne('const REGISTRE_AGENTS_MAX'), ligne('const ID_AGENT'),
    ligne('const DEPART_AGENT'), prendre('lireRegistreAgents'), prendre('ecrireRegistreAgents'), prendre('marquerAgent'),
    prendre('noterRegistre'), prendre('prenomAgent'), prendre('texteDepart'),
    'this.f = { noterRegistre, marquerAgent, lireRegistreAgents, texteDepart };'].join('\n'), ctx);
  return { f: ctx.f, d };
}
const debut = (id, extra = {}) => ({ type: 'system', subtype: 'task_started', task_id: id, task_type: 'local_agent', subagent_type: 'codeur',
  description: 'Portée par contact', session_id: 'sess-1', ...extra });
const fin = (id, status, summary = 'FINI') => ({ type: 'system', subtype: 'task_notification', task_id: id, status, summary });

test('naissance, sommeil, réveil : le registre suit chaque agent de Hakim', () => {
  const { f } = registre();
  assert.equal(f.noterRegistre(debut(ID), 1000).evenement, 'naissance');
  let a = f.lireRegistreAgents().agents[ID];
  assert.equal(a.etat, 'travaille'); assert.equal(a.type, 'codeur'); assert.equal(a.ne_ms, 1000); assert.equal(a.session, 'sess-1');
  assert.equal(f.noterRegistre(fin(ID, 'completed'), 2000).evenement, 'sommeil');
  assert.equal(f.lireRegistreAgents().agents[ID].etat, 'dort');
  assert.equal(f.noterRegistre(debut(ID), 3000).evenement, 'reveil');
  a = f.lireRegistreAgents().agents[ID];
  assert.equal(a.etat, 'travaille'); assert.equal(a.ne_ms, 1000, 'sa naissance ne change pas'); assert.equal(a.reveils, 1);
});

test('ce qui n’est pas un agent de Hakim n’entre pas au registre (commandes, agents de ses agents, numéros étranges)', () => {
  const { f } = registre();
  assert.equal(f.noterRegistre(debut('b5q1si0s4', { task_type: 'local_bash' })), null);
  assert.equal(f.noterRegistre(debut(ID, { owned_by_subagent: true })), null);
  assert.equal(f.noterRegistre(debut(ID, { parent_task_id: 'a0000000000000000' })), null);
  assert.equal(f.noterRegistre(debut('../../etc')), null);
  assert.equal(f.noterRegistre(fin(ID, 'completed')), null, 'une fin sans naissance connue');
  assert.deepEqual(f.lireRegistreAgents().agents, {});
});

test('« JE PARS : … » en tête de son dernier message : il est parti de lui-même, avec sa raison', () => {
  const { f } = registre();
  f.noterRegistre(debut(ID));
  const r = f.noterRegistre(fin(ID, 'completed', "**Je pars** : j'ai fait le tour, merci pour tout.\nLe reste du rapport…"));
  assert.equal(r.evenement, 'depart');
  const a = f.lireRegistreAgents().agents[ID];
  assert.equal(a.etat, 'parti'); assert.equal(a.depart, "j'ai fait le tour, merci pour tout.");
  assert.match(f.texteDepart(a), /est parti de lui-même : j'ai fait le tour/);
  f.noterRegistre(debut(ID)); f.noterRegistre(fin(ID, 'completed', 'Rapport.\nJe pars plus tard, peut-être.'));
  assert.equal(f.lireRegistreAgents().agents[ID].etat, 'dort', 'seulement en tête de son message');
});

test('arrêté par stop_task : plus réveillable ; mort avec son cerveau : coupé', () => {
  const { f } = registre();
  f.noterRegistre(debut(ID)); f.marquerAgent(ID, 'arrete'); f.noterRegistre(fin(ID, 'stopped'));
  assert.equal(f.lireRegistreAgents().agents[ID].etat, 'arrete');
  const autre = 'acafe0000000000ff';
  f.noterRegistre(debut(autre)); f.noterRegistre(fin(autre, 'stopped', "didn't finish before the previous session ended"));
  assert.equal(f.lireRegistreAgents().agents[autre].etat, 'coupe');
});

test('la conversation courante est notée (agents_lister distingue les agents joignables)', () => {
  const { f } = registre();
  f.noterRegistre({ type: 'system', subtype: 'init', session_id: 'sess-2' });
  assert.equal(f.lireRegistreAgents().session_courante, 'sess-2');
});

test('le registre garde les 500 derniers agents', () => {
  const { f } = registre();
  for (let i = 0; i < 503; i++) f.noterRegistre(debut('a' + i.toString(16).padStart(16, '0')), 1000 + i);
  const ids = Object.keys(f.lireRegistreAgents().agents);
  assert.equal(ids.length, 500);
  assert.ok(!ids.includes('a' + '0'.padStart(16, '0')), 'les plus anciens partent');
});

test('un agent réveillé est suivi comme en cours (le cerveau ne s’endort pas sous lui)', () => {
  const ctx = { Map, String, JSON, Date, Array, j: JSON.stringify, AGENTS_PARALLELE_MAX: 10, cerveauVivant: () => true };
  vm.createContext(ctx);
  vm.runInContext(`const AGENT_OUBLI_MS = 3 * 3600 * 1000;` + prendre('tachesDe') + prendre('suivreAgents') + 'this.tachesDe = tachesDe; this.suivre = suivreAgents;', ctx);
  const c = { taches: new Map(), agentsLances: new Map(), lancements: new Map() };
  assert.equal(ctx.suivre(c, debut(ID)), true);
  assert.deepEqual([...ctx.tachesDe(c).keys()], [ID]);
  ctx.suivre(c, fin(ID, 'completed'));
  assert.equal(ctx.tachesDe(c).size, 0);
  assert.equal(ctx.suivre(c, debut(ID, { owned_by_subagent: true })), false);
});

test('son cerveau a SendMessage, avec sa garde (PreToolUse) ; le crochet de la sentinelle reste', () => {
  const ctx = { JSON, path, ANAMNESE: '/anamnese', j: JSON.stringify, aideCle: () => '/x', JARVIS: '/j', AGENTS_PARALLELE_MAX: 10,
    process: { execPath: '/bin/node' }, __dirname: '/cockpit' };
  vm.createContext(ctx);
  vm.runInContext([ligne('const CROCHET_IMMUNITE ='), ligne('const GARDE_MESSAGE ='), prendre('reglagesCerveau'), 'this.f = { reglagesCerveau };'].join('\n'), ctx);
  const r = JSON.parse(ctx.f.reglagesCerveau('abonnement'));
  assert.equal(r.hooks.PostToolUse[0].matcher, 'WebSearch|Read|Task|Agent');
  const p = r.hooks.PreToolUse;
  assert.equal(p.length, 1); assert.equal(p[0].matcher, 'SendMessage');
  assert.equal(p[0].hooks[0].command, "JARVIS_DIR='/j' JARVIS_AGENTS_PARALLELE_MAX=10 '/bin/node' '/cockpit/garde-message.js'");
  assert.ok(p[0].hooks[0].timeout > 0 && p[0].hooks[0].timeout <= 15);
  const c = prendre('cerveauLancer');
  assert.match(c, /`WebSearch,Read\$\{agents \? ',Task,SendMessage' : ''\}`/);
  assert.match(c, /OUTILS_JARVIS\.concat\(agents \? \['Task', 'SendMessage'\] : \[\]\)/);
  assert.match(c, /const vie = noterRegistre\(o\);/);
  assert.match(c, /vie\.evenement === 'depart'[\s\S]{0,300}texteDepart\(vie\.agent\)/);
});

test('ses nouveaux outils sont permis ; un arrêt marque l’agent « arrêté »', () => {
  for (const o of ['agent_prenom', 'agent_juger', 'agent_trouvaille']) assert.ok(src.includes(`'mcp__terminal__${o}'`), o);
  assert.match(prendre('arreterAgent'), /marquerAgent\(id, 'arrete'\)/);
  const i = src.indexOf('AGENTS_PARALLELE_MAX && cerveauVivant(c)');
  assert.match(src.slice(i, i + 700), /marquerAgent\(m\[1\], 'arrete'\)/);
});

test('ses agents savent leur vie : sommeil, messages, prénom, départ ; le juge ne juge jamais deux fois ; le témoin vierge reste vierge', () => {
  const ctx = { JSON, Object, String, AGENTS: {}, LECTURE: [], MEMOIRE_LECTURE: [], lireSansLien: () => '', path, PREAMBULE_MATHS: '/x/y/z',
    REFERENCE_MATHS: '/r', agentsDeHakim: () => ({ moi: { description: 'le mien', prompt: 'Mon agent.', tools: [], model: 'sonnet' } }) };
  vm.createContext(ctx);
  const i = src.indexOf('const AGENTS = {');
  vm.runInContext(src.slice(i, src.indexOf('\n};\n', i) + 4).replace('const AGENTS', 'AGENTS') + ligne('const VIE_AGENT') + ligne('const VIE_JUGE')
    + prendre('agentsPourCerveau') + 'this.a = agentsPourCerveau();', ctx);
  for (const k of ['architecte', 'codeur', 'juge', 'moi']) {
    assert.match(ctx.a[k].prompt, /tu t'endors/, k); assert.match(ctx.a[k].prompt, /JE PARS :/, k); assert.match(ctx.a[k].prompt, /prénom/, k);
  }
  assert.match(ctx.a.juge.prompt, /jamais deux fois le même travail/);
  assert.doesNotMatch(ctx.a.codeur.prompt, /jamais deux fois le même travail/);
  assert.doesNotMatch(ctx.a.vierge.prompt, /JE PARS/);
});

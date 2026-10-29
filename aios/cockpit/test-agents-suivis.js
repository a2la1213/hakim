/* Les agents de Hakim suivis par le cockpit lui-même (24/10, 01:55 : un codeur tué avec son cerveau quand Ahmed lui a
   coupé la parole, le cockpit ne le savait pas en cours) : node --test test-agents-suivis.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = srv.indexOf(`function ${nom}(`); return srv.slice(i, srv.indexOf('\n}\n', i) + 2); };
function cockpit() {
  const tues = [], ecrits = [];
  const ctx = { Map, String, JSON, Date, Array, tues, ecrits, j: JSON.stringify,
    process: { kill: (pid, sig) => tues.push([pid, sig]) }, setTimeout: () => ({ unref() {} }), console: { error() {} },
    marquerAgent: () => {} };
  vm.createContext(ctx);
  vm.runInContext(`const AGENT_OUBLI_MS = 3 * 3600 * 1000; const AGENTS_PARALLELE_MAX = 10; const hmsCerveau = () => '00:00:00';`
    + prendre('tachesDe') + prendre('suivreAgents') + prendre('tuer') + prendre('cerveauVivant') + prendre('interrompre') + prendre('lacher')
    + 'this.tachesDe = tachesDe; this.suivre = suivreAgents; this.lacher = lacher;', ctx);
  const enfant = { pid: 42, exitCode: null, signalCode: null, stdin: { write: (l) => ecrits.push(JSON.parse(l)) } };
  const c = { enfant, taches: new Map(), attente: [], enCours: { autonome: false }, agentsLances: new Map(), lancements: new Map() };
  enfant.cerveau = c;
  return { ctx, c, enfant, tues, ecrits };
}
const lance = (id, description) => ({ type: 'assistant', message: { content: [{ type: 'tool_use', id, name: 'Agent', input: { description, subagent_type: 'codeur' } }] } });
const resultat = (id, texte) => ({ type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: id, content: [{ type: 'text', text: texte }] }] } });

test('un agent lancé en arrière-plan est suivi jusqu’à sa notification de fin', () => {
  const { ctx, c } = cockpit();
  ctx.suivre(c, lance('tu1', 'La règle rétrécit-elle'));
  assert.equal(ctx.tachesDe(c).size, 0, 'pas encore : on attend le résultat du lancement');
  assert.equal(ctx.suivre(c, resultat('tu1', 'Async agent launched successfully.\nagentId: a33affc1e0ccaf018 (internal ID)')), true);
  assert.deepEqual([...ctx.tachesDe(c).entries()], [['a33affc1e0ccaf018', 'La règle rétrécit-elle']]);
  ctx.suivre(c, { type: 'system', subtype: 'task_notification', task_id: 'a33affc1e0ccaf018', status: 'completed' });
  assert.equal(ctx.tachesDe(c).size, 0);
  // la fin peut aussi n'arriver que par le texte rejoué de la notification
  ctx.suivre(c, lance('tu2', 'Juge')); ctx.suivre(c, resultat('tu2', 'agentId: b1'));
  ctx.suivre(c, { type: 'user', isReplay: true, message: { content: '<task-notification>\n<task-id>b1</task-id>\n<status>completed</status>' } });
  assert.equal(ctx.tachesDe(c).size, 0);
});

test('un agent qui a déjà fini (sans agentId), l’agent d’un agent, un agent muet depuis 3 h : pas suivis', () => {
  const { ctx, c } = cockpit();
  ctx.suivre(c, lance('tu1', 'court')); ctx.suivre(c, resultat('tu1', 'Voici le résultat complet du codeur.'));
  ctx.suivre(c, { ...lance('tu2', 'sous-agent'), parent_tool_use_id: 'x' });
  ctx.suivre(c, { ...resultat('tu2', 'agentId: zz'), parent_tool_use_id: 'x' });
  assert.equal(ctx.tachesDe(c).size, 0);
  ctx.suivre(c, lance('tu3', 'long'), 1_000); ctx.suivre(c, resultat('tu3', 'agentId: c3'), 1_000);
  assert.equal(ctx.tachesDe(c, 1_000 + 3600 * 1000).size, 1);
  assert.equal(ctx.tachesDe(c, 1_000 + 3 * 3600 * 1000 + 1).size, 0, 'oublié après 3 h sans nouvelles');
});

test('Ahmed coupe la parole pendant qu’un agent tourne : interruption douce, le cerveau (et l’agent) vivent', () => {
  const { ctx, c, enfant, tues, ecrits } = cockpit();
  ctx.suivre(c, lance('tu1', 'La règle rétrécit-elle')); ctx.suivre(c, resultat('tu1', 'agentId: a33'));
  ctx.lacher(enfant, null);
  assert.deepEqual(tues, [], 'pas tué');
  assert.equal(ecrits[0].request.subtype, 'interrupt');
  // sans agent : arrêté, avec sa raison (datée dans le journal à la fermeture)
  const d = cockpit();
  d.ctx.lacher(d.enfant, null);
  assert.deepEqual(d.tues[0], [-42, 'SIGTERM']);
  assert.match(d.enfant.raisonArret, /a lâché le tour/);
});

test('(25/10) au-delà de 10 agents en parallèle, le dernier lancé est arrêté aussitôt', () => {
  const { ctx, c, ecrits } = cockpit();
  ctx.fs = { appendFileSync() {} }; ctx.JARVIS_AGENTS_ARRETS = '/dev/null';
  for (let i = 0; i < 11; i++) {
    ctx.suivre(c, { type: 'assistant', message: { content: [{ type: 'tool_use', id: `t${i}`, name: 'Agent', input: { description: `agent ${i}` } }] } });
    ctx.suivre(c, { type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: `t${i}`, content: `lancé. agentId: a${i}` }] } });
  }
  assert.equal(c.agentsLances.size, 10);
  assert.deepEqual(ecrits.filter(e => e.request && e.request.subtype === 'stop_task').map(e => e.request.task_id), ['a10']);
});

test('(29/10, 16:55) un agent réveillé par SendMessage n’est pas rayé par le texte rejoué de son ANCIENNE fin', () => {
  // la fin « stopped » d'avant le redémarrage, rejouée au tour suivant, effaçait l'agent réveillé : le cerveau, cru sans
  // agent, a été remplacé à l'allègement et l'agent est mort avec lui
  const { ctx, c } = cockpit();
  const id = 'a71091a44f5580351';
  ctx.suivre(c, { type: 'system', subtype: 'task_started', task_id: id, task_type: 'local_agent', description: 'Codeur portée par contact' });
  ctx.suivre(c, { type: 'user', isReplay: true, isSynthetic: true, message: { content: `<task-notification>\n<task-id>${id}</task-id>\n<status>stopped</status>` } });
  assert.deepEqual([...ctx.tachesDe(c).keys()], [id], 'toujours au travail');
  ctx.suivre(c, { type: 'system', subtype: 'task_notification', task_id: id, status: 'completed' });
  assert.equal(ctx.tachesDe(c).size, 0, 'sa vraie fin, par le signal de claude');
});

/* (30/10, Ahmed via Hakim : « une note pour le travail de chaque agent » ; « le café au début et à la fin de chaque agent » ;
   « mon appréciation passe en premier au café » ; « l'historique des notes visible pour moi dans Parler ») le cockpit :
   le lecteur du café signé (un juge ne lit que son retour), la vie d'agent qui le dit, l'outil, la famille, Parler.
   node --test test-agents-notes.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const garde = (args, entree) => JSON.parse(execFileSync(process.execPath, [path.join(__dirname, 'garde-message.js'), ...args], { input: JSON.stringify(entree) }).toString());

test('le lecteur du café est signé par claude (agent_id), jamais par l’appelant', () => {
  let r = garde(['--cafe-lire'], { tool_name: 'mcp__terminal__cafe_lire', agent_id: 'a1234567890abcdef', tool_input: { n: 10, lecteur: 'hakim' } });
  assert.equal(r.hookSpecificOutput.permissionDecision, 'allow');
  assert.equal(r.hookSpecificOutput.updatedInput.lecteur, 'a1234567890abcdef');
  assert.equal(r.hookSpecificOutput.updatedInput.n, 10);
  r = garde(['--cafe-lire'], { tool_name: 'mcp__terminal__cafe_lire', tool_input: { lecteur: 'a1234567890abcdef' } });
  assert.equal(r.hookSpecificOutput.updatedInput.lecteur, 'hakim', 'le fil principal, c’est Hakim');
  r = garde(['--cafe-lire'], { tool_name: 'mcp__terminal__cafe_lire', agent_id: 'pas-un-agent', tool_input: {} });
  assert.equal(r.hookSpecificOutput.permissionDecision, 'deny');
});

test('branché : le crochet du café (cerveau et messager), l’outil, la vie d’agent, la famille, Parler', () => {
  assert.match(src, /matcher: 'mcp__terminal__cafe_lire', hooks: \[\{ type: 'command', timeout: 10, onFailure: 'block', command: `\$\{GARDE_MESSAGE\} --cafe-lire` \}\]/);
  assert.match(fs.readFileSync(path.join(__dirname, 'messager.js'), 'utf8'), /matcher: 'mcp__terminal__cafe_lire'[^\n]*--cafe-lire/);
  assert.match(src, /'mcp__terminal__agent_noter'/);
  const vie = src.slice(src.indexOf('const VIE_AGENT = '), src.indexOf('\n', src.indexOf('const VIE_AGENT = ')));
  assert.match(vie, /à ta naissance/); assert.match(vie, /avec Read/); assert.match(vie, /à chaque réveil/);
  assert.match(vie, /appréciation/); assert.match(vie, /☕ Café :/);
  const fam = src.slice(src.indexOf('function texteFamille('), src.indexOf('\n}\n', src.indexOf('function texteFamille(')));
  assert.match(fam, /\/10/);
  const i = src.indexOf("if (p === '/api/agents/notes'");
  assert.ok(i >= 0);
  assert.match(src.slice(i, i + 400), /jetonValide\(req\)/);
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8'), /id="notesAgents"/);
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8'), /\/api\/agents\/notes/);
});

test('(30/10, 12:03) le rôle et l’expertise : la famille, la vie d’agent sans hiérarchie, Parler', () => {
  const vm = require('node:vm');
  const fam = src.slice(src.indexOf('function texteFamille('), src.indexOf('\n}\n', src.indexOf('function texteFamille(')) + 3);
  const ctx = { lireRegistreAgents: () => ({ session_courante: 's1', agents: { a1: { id: 'a1', type: 'codeur', description: 'Test XRP', etat: 'dort', ne_ms: 1, session: 's1' } } }),
    lireJson: () => ({ agents: { a1: { prenom: 'Iris', role: 'architecte', expertise: { architecte: 'apprenti', codeur: 'confirmé' }, roles: [{ de: 'codeur', vers: 'architecte' }] } } }),
    path, JARVIS: '/x', Messager: { filAgent: () => '' }, PROJECTS_DIR: '', JARVIS_CWD: '', FAMILLE_MAX: 60, Intl, Date };
  vm.createContext(ctx);
  vm.runInContext(fam + '\nthis.f = texteFamille;', ctx);
  const t = ctx.f();
  assert.match(t, /Iris — architecte \(expertise apprenti\)/);
  assert.match(t, /avant : codeur/);
  assert.match(t, /aucune hiérarchie/i);
  const vie = src.slice(src.indexOf('const VIE_AGENT = '), src.indexOf('\n', src.indexOf('const VIE_AGENT = ')));
  assert.match(vie, /personne ne commande personne/);
  assert.match(src, /'mcp__terminal__agent_role'/);
  const i = src.indexOf("if (p === '/api/agents/notes'");
  assert.match(src.slice(i, i + 1500), /expertise/);
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8'), /expertise/);
});

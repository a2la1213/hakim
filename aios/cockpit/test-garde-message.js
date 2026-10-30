/* (29/10, Ahmed : « sonde, garde, puis outil ») la garde de SendMessage : Hakim n'écrit qu'à SES agents, ceux de sa
   conversation ; un agent parti de lui-même n'est plus réveillé ; un juge ne se réveille que pour un travail neuf.
   node --test test-garde-message.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const GARDE = path.join(__dirname, 'garde-message.js');
const ID = 'a7514e29068e49980', JUGE = 'ab000000000000001', AUTRE = 'acafe0000000000ff';

function monde() {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'garde-message-'));
  const jarvis = path.join(d, 'jarvis'); fs.mkdirSync(jarvis);
  const conv = path.join(d, 'projets', 'cwd', 'sess-1');
  fs.mkdirSync(path.join(conv, 'subagents'), { recursive: true });
  const transcript = conv + '.jsonl'; fs.writeFileSync(transcript, '');
  const fil = (id, mtimeMs) => { const f = path.join(conv, 'subagents', `agent-${id}.jsonl`); fs.writeFileSync(f, '{}\n');
    if (mtimeMs) fs.utimesSync(f, mtimeMs / 1000, mtimeMs / 1000); };
  const registre = (agents) => fs.writeFileSync(path.join(jarvis, 'registre-agents.json'), JSON.stringify({ agents }));
  const fiches = (agents) => fs.writeFileSync(path.join(jarvis, 'agents-fiches.json'), JSON.stringify({ agents }));
  const garder = (entree, env = {}) => {
    const r = spawnSync(process.execPath, [GARDE], { input: typeof entree === 'string' ? entree : JSON.stringify(entree),
      env: { PATH: process.env.PATH, JARVIS_DIR: jarvis, ...env }, encoding: 'utf8', timeout: 10000 });
    const sortie = r.stdout.trim() ? JSON.parse(r.stdout) : null;
    return { code: r.status, refus: sortie && sortie.hookSpecificOutput && sortie.hookSpecificOutput.permissionDecision === 'deny'
      ? sortie.hookSpecificOutput.permissionDecisionReason : null };
  };
  const appel = (to, extra = {}) => ({ session_id: 'sess-1', transcript_path: transcript, hook_event_name: 'PreToolUse',
    tool_name: 'SendMessage', tool_input: { to, message: 'merci', summary: 'merci' }, ...extra });
  return { jarvis, fil, registre, fiches, garder, appel };
}

test('un agent de SA conversation : le message passe', () => {
  const m = monde(); m.fil(ID);
  const r = m.garder(m.appel(ID));
  assert.equal(r.code, 0); assert.equal(r.refus, null);
});

test('ni une autre session, ni un nom, ni « main » : seulement un numéro d’agent', () => {
  const m = monde(); m.fil(ID);
  for (const to of ['main', 'claude-code', 'hakim-publication [3fa9c1]', 'architecte', '', ID + ' ', '../' + ID, ID.toUpperCase()]) {
    const r = m.garder(m.appel(to));
    assert.equal(r.code, 0); assert.ok(r.refus, `« ${to} » doit être refusé`);
  }
});

test('un numéro d’agent qui n’est pas de sa conversation (une autre, ou une conversation allégée) est refusé', () => {
  const m = monde(); m.fil(ID);
  assert.ok(m.garder(m.appel(AUTRE)).refus);
  const r = m.garder(m.appel(ID, { transcript_path: path.join(m.jarvis, 'ailleurs.jsonl') }));
  assert.ok(r.refus);
});

test('un agent parti de lui-même n’est plus réveillé ; un agent arrêté non plus', () => {
  const m = monde(); m.fil(ID); m.fil(AUTRE);
  m.registre({ [ID]: { id: ID, type: 'codeur', etat: 'parti', depart: 'j’en ai assez' }, [AUTRE]: { id: AUTRE, type: 'codeur', etat: 'arrete' } });
  assert.match(m.garder(m.appel(ID)).refus, /parti de lui-même/);
  assert.match(m.garder(m.appel(AUTRE)).refus, /arrêté/);
});

test('un juge endormi ne se réveille que pour un travail déclaré APRÈS son dernier travail ; au travail, on peut lui écrire', () => {
  const m = monde(); const fin = Date.now() - 60000; m.fil(JUGE, fin);
  m.registre({ [JUGE]: { id: JUGE, type: 'juge', etat: 'dort' } });
  assert.match(m.garder(m.appel(JUGE)).refus, /agent_juger/);
  m.registre({ [JUGE]: { id: JUGE, type: 'juge', etat: 'dort', reveils: 1 } });
  m.fiches({ [JUGE]: { dossiers: [{ cle: 'portee', ts_ms: fin - 1000 }] } });
  assert.match(m.garder(m.appel(JUGE)).refus, /agent_juger/, 'un travail, deux passages (son travail, son dernier mot) : plus de réveil');
  m.fiches({ [JUGE]: { dossiers: [{ cle: 'portee', ts_ms: fin - 1000 }, { cle: 'graines', ts_ms: Date.now() }] } });
  assert.equal(m.garder(m.appel(JUGE)).refus, null);
  m.registre({ [JUGE]: { id: JUGE, type: 'juge', etat: 'travaille' } });
  m.fiches({});
  assert.equal(m.garder(m.appel(JUGE)).refus, null);
});

test('réveiller un agent quand dix travaillent déjà : refusé (sans tuer personne) ; lui écrire pendant son travail : permis', () => {
  const m = monde(); m.fil(ID);
  const agents = { [ID]: { id: ID, type: 'codeur', etat: 'dort', session: 'sess-1' } };
  for (let i = 0; i < 10; i++) { const id = 'a' + String(i).padStart(16, '0'); agents[id] = { id, type: 'codeur', etat: 'travaille', session: 'sess-1' }; }
  m.registre(agents);
  assert.match(m.garder(m.appel(ID)).refus, /10/);
  agents[ID].etat = 'travaille'; m.registre(agents);
  assert.equal(m.garder(m.appel(ID)).refus, null);
});

test('tout ce qui n’est pas lisible est refusé (la garde ne s’ouvre jamais par erreur)', () => {
  const m = monde(); m.fil(ID);
  for (const entree of ['pas du json', '', '[]', JSON.stringify({ ...m.appel(ID), tool_name: 'Task' }), JSON.stringify({ ...m.appel(ID), tool_input: null })]) {
    const r = m.garder(entree);
    assert.equal(r.code, 0); assert.ok(r.refus, entree.slice(0, 40));
  }
  fs.writeFileSync(path.join(m.jarvis, 'registre-agents.json'), '{pas du json');
  assert.equal(m.garder(m.appel(ID)).refus, null, 'un registre illisible ne bloque pas un agent de sa conversation');
});

test('chaque décision est notée (pour Ahmed), sans le texte du message', () => {
  const m = monde(); m.fil(ID);
  m.garder(m.appel(ID)); m.garder(m.appel('main'));
  const l = fs.readFileSync(path.join(m.jarvis, 'messages-agents.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
  assert.equal(l.length, 2);
  assert.equal(l[0].ok, true); assert.equal(l[1].ok, false);
  assert.ok(!JSON.stringify(l).includes('merci'));
});

// ---- relecture Opus (29/10) ----
test('relecture : un juge dort après chaque travail ; un réveil pour son dernier mot, puis il faut un travail neuf', () => {
  const m = monde(); m.fil(JUGE, Date.now() - 60000);
  m.registre({ [JUGE]: { id: JUGE, type: 'juge', etat: 'dort', reveils: 0, session: 'sess-1' } });
  m.fiches({ [JUGE]: { dossiers: [{ cle: 'portee', ts_ms: Date.now() }] } });
  assert.equal(m.garder(m.appel(JUGE)).refus, null, 'un travail déclaré (même après coup) : un réveil, son dernier mot');
  m.registre({ [JUGE]: { id: JUGE, type: 'juge', etat: 'dort', reveils: 1, session: 'sess-1' } });
  assert.match(m.garder(m.appel(JUGE)).refus, /agent_juger/, 'deux fois le même travail : non');
  m.fiches({ [JUGE]: { dossiers: [{ cle: 'portee', ts_ms: 1 }, { cle: 'graines', ts_ms: 2 }] } });
  assert.equal(m.garder(m.appel(JUGE)).refus, null);
});

test('relecture : un juge absent du registre est reconnu par son fil (meta.json de claude) et suit la règle', () => {
  const m = monde(); m.fil(JUGE);
  const dir = path.dirname(m.appel(JUGE).transcript_path);
  fs.writeFileSync(path.join(dir, 'sess-1', 'subagents', `agent-${JUGE}.meta.json`), JSON.stringify({ agentType: 'juge' }));
  assert.match(m.garder(m.appel(JUGE)).refus, /agent_juger/);
});

test('relecture : la limite des dix se compte dans SA conversation (celle du crochet)', () => {
  const m = monde(); m.fil(ID);
  const agents = { [ID]: { id: ID, type: 'codeur', etat: 'dort' } };
  for (let i = 0; i < 10; i++) { const id = 'a' + String(i).padStart(16, '0'); agents[id] = { id, type: 'codeur', etat: 'travaille', session: 'autre' }; }
  m.registre(agents);
  assert.equal(m.garder(m.appel(ID)).refus, null, 'dix au travail dans une AUTRE conversation ne comptent pas');
});

// (30/10, Ahmed via Hakim : « recevoir les réponses de tous les agents ») un réveil « ☕ Café : » n'est pas un travail : un
// juge peut l'entendre sans travail neuf déclaré, et ce passage ne lui retire pas un des siens (compté à part, cafe-reveils.json)
test('café : un juge endormi peut être prévenu sans travail neuf, et ça ne compte pas dans ses passages', () => {
  const m = monde(); m.fil(JUGE);
  const cafe = (to) => m.appel(to, { tool_input: { to, message: '☕ Café : papa vous a écrit au café.', summary: 'café' } });
  m.registre({ [JUGE]: { id: JUGE, type: 'juge', etat: 'dort', reveils: 1 } });
  m.fiches({ [JUGE]: { dossiers: [{ cle: 'portee', ts_ms: Date.now() - 1000 }] } });
  assert.match(m.garder(m.appel(JUGE)).refus, /agent_juger/, 'un travail ordinaire : toujours refusé');
  assert.equal(m.garder(cafe(JUGE)).refus, null, 'le café passe');
  assert.equal(JSON.parse(fs.readFileSync(path.join(m.jarvis, 'cafe-reveils.json'), 'utf8'))[JUGE], 1);
  // né, il a jugé son travail (aucun réveil) ; le café l'a réveillé une fois (reveils 1) : son dernier mot lui reste dû
  const m2 = monde(); m2.fil(JUGE);
  m2.registre({ [JUGE]: { id: JUGE, type: 'juge', etat: 'dort', reveils: 1 } });
  m2.fiches({ [JUGE]: { dossiers: [{ cle: 'portee', ts_ms: Date.now() - 1000 }] } });
  fs.writeFileSync(path.join(m2.jarvis, 'cafe-reveils.json'), JSON.stringify({ [JUGE]: 1 }));
  assert.equal(m2.garder(m2.appel(JUGE)).refus, null, 'le café ne lui a pas pris son passage');
  m.registre({ [JUGE]: { id: JUGE, type: 'juge', etat: 'parti' } });
  assert.match(m.garder(cafe(JUGE)).refus, /parti de lui-même/, 'un parti reste parti, même pour le café');
});

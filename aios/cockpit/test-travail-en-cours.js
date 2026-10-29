/* (29/10, 17:05, Ahmed : « s'il y a un agent, elle doit m'interdire de relancer le truc, quel que soit X ») : qui travaille
   encore, et la relance qui attend. node --test test-travail-en-cours.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { travailEnCours, texteTravail } = require('./travail-en-cours.js');
const C = require('./code.js');

function jarvis() {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'travail-'));
  fs.mkdirSync(path.join(d, 'cwd', 'taches'), { recursive: true });
  return d;
}
const cli = (d) => spawnSync(process.execPath, [path.join(__dirname, 'travail-en-cours.js')], { env: { PATH: process.env.PATH, JARVIS_DIR: d }, encoding: 'utf8' });

test('personne ne travaille : oui', () => {
  const d = jarvis();
  assert.deepEqual(travailEnCours(d), { agents: [], taches: [] });
  const r = cli(d);
  assert.equal(r.status, 0); assert.match(r.stdout, /^OUI/);
});

test('un agent au travail (liste du cockpit ou registre), une tâche de fond vivante : non, et qui', () => {
  const d = jarvis();
  fs.writeFileSync(path.join(d, 'agents-en-cours.json'), JSON.stringify({ agents: [{ id: 'a71091a44f5580351', description: 'Codeur portée par contact' }] }));
  fs.writeFileSync(path.join(d, 'registre-agents.json'), JSON.stringify({ agents: {
    ab000000000000001: { id: 'ab000000000000001', description: 'Juge des graines', etat: 'travaille' },
    ac000000000000001: { id: 'ac000000000000001', description: 'Endormi', etat: 'dort' } } }));
  fs.writeFileSync(path.join(d, 'cwd', 'taches', 'T-1.json'), JSON.stringify({ id: 'T-1', etat: 'en cours', superviseur: process.pid, commande: 'python calcul.py' }));
  fs.writeFileSync(path.join(d, 'cwd', 'taches', 'T-2.json'), JSON.stringify({ id: 'T-2', etat: 'en cours', superviseur: 999999, commande: 'mort' }));
  fs.writeFileSync(path.join(d, 'cwd', 'taches', 'T-3.json'), JSON.stringify({ id: 'T-3', etat: 'finie', superviseur: process.pid }));
  const t = travailEnCours(d);
  assert.deepEqual(t.agents.map(a => a.id).sort(), ['a71091a44f5580351', 'ab000000000000001']);
  assert.deepEqual(t.taches.map(x => x.id), ['T-1']);
  assert.match(texteTravail(t), /2 agents au travail \(« Codeur portée par contact », « Juge des graines »\) et 1 tâche de fond \(T-1\)/);
  const r = cli(d);
  assert.equal(r.status, 1); assert.match(r.stdout, /^NON : 2 agents/);
});

test('la relance acceptée n’est pas « calme » tant qu’un agent ou une tâche travaille', () => {
  assert.equal(C.calme({ tours: new Map(), maman: false, testsChantier: false, travail: true }), false);
  assert.equal(C.calme({ tours: new Map(), maman: false, testsChantier: false, travail: false }), true);
});

test('la relance qui attend dit pourquoi, une fois, et n’est jamais faite tant qu’on travaille', async () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'relance-'));
  const lieux = { relances: d, journal: path.join(d, 'journal.jsonl') };
  fs.writeFileSync(path.join(d, 'r1.json'), JSON.stringify({ id: 'r1', quoi: 'cockpit', etat: 'proposée' }));
  const dits = [], lances = [];
  const r = await C.accepterRelance('r1', lieux, { estCalme: () => false, attendre: async () => {}, pas_ms: 1000, calme_ms: 2000, max_ms: 10000,
    uid: 502, lancer: (...a) => lances.push(a), pourquoi: () => '1 agent au travail (« Codeur »)', signaler: (t) => dits.push(t) });
  assert.equal(r.etape, 'pas de calme');
  assert.equal(lances.length, 0, 'jamais relancé');
  assert.equal(dits.length, 1); assert.match(dits[0], /Codeur/);
});

test('branché : la relance acceptée compte les agents et les tâches, et le dit dans Parler', () => {
  const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(src, /travail: travailOccupe\(\)/);
  assert.match(src, /pourquoi: \(\) => texteTravail\(travailEnCours\(JARVIS\)\)/);
  assert.match(src, /signaler: \(t\) => ajouterAConversation\(/);
});

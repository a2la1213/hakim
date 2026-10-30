/* (30/10, Ahmed via Hakim : « écrire au café et recevoir les réponses de tous les agents ») Ahmed écrit au café depuis la
   page ; le cockpit signe « Ahmed (papa) » (anamnese/jarvis/cafe.py ahmed) et réveille Hakim, qui prévient ses agents par un
   message qui commence par « ☕ Café : » ; ils répondent au café s'ils en ont envie. Un réveil de juge pour le café n'est pas
   un verdict. node --test test-cafe-ahmed.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const V = require('./verdicts.js');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const extraire = (debut) => src.slice(src.indexOf(debut), src.indexOf('\n}\n', src.indexOf(debut)) + 3);
const charger = (...noms) => {
  const ctx = { blocDonnees: (t, c) => `[${t}]\n${c}\n[/${t}]`, crypto: require('node:crypto'), NONCE_REVEIL: 'n0nce', Intl, Date, Math, String, Array, Set, Object, Number };
  vm.createContext(ctx);
  vm.runInContext(noms.map(extraire).join('\n') + '\n' + noms.map(n => n.replace(/^function (\w+)\(.*/, 'this.$1 = $1;')).join('\n'), ctx);
  return ctx;
};

const AGENTS = {
  a1: { id: 'a1', etat: 'dort', session: 'S2', maj_ms: 5, type: 'juge', description: 'Juge maths' },
  a2: { id: 'a2', etat: 'dort', session: 'S2', maj_ms: 9, type: 'codeur', description: 'Ancrage' },
  a3: { id: 'a3', etat: 'travaille', session: 'S2', maj_ms: 10, type: 'codeur', description: 'au travail' },
  a4: { id: 'a4', etat: 'dort', session: 'S1', maj_ms: 3, type: 'juge', description: 'Juge ancien' },
  a5: { id: 'a5', etat: 'parti', session: 'S2', maj_ms: 8, type: 'codeur', description: 'parti' },
  a6: { id: 'a6', etat: 'coupe', session: 'S2', maj_ms: 7, type: 'architecte', description: 'coupé' },
};
const PRENOMS = { a1: 'Octave', a2: 'Léonie', a3: 'Samir', a4: 'Noé', a5: 'Louis', a6: 'Armand' };

test('qui est prévenu : ses agents endormis de la conversation actuelle (pas ceux au travail, ni partis) ; les nommés partout', () => {
  const { choisirAgentsCafe } = charger('function choisirAgentsCafe(');
  const tous = choisirAgentsCafe(AGENTS, PRENOMS, 'S2', 'Salam la famille !');
  assert.deepEqual(tous.actuels.map(a => a.id), ['a2', 'a6', 'a1'], 'les plus récents d’abord');
  assert.deepEqual(tous.anciens, []);
  const nommes = choisirAgentsCafe(AGENTS, PRENOMS, 'S2', 'Coucou noé et Octave, ça va ? Et toi Louis ?');
  assert.deepEqual(nommes.actuels.map(a => a.id), ['a1']);
  assert.deepEqual(nommes.anciens.map(a => a.id), ['a4'], 'un ancien, seulement s’il est nommé');
  const beaucoup = Object.fromEntries(Array.from({ length: 12 }, (_, k) => [`b${k}`, { id: `b${k}`, etat: 'dort', session: 'S2', maj_ms: k }]));
  assert.equal(choisirAgentsCafe(beaucoup, {}, 'S2', 'salut').actuels.length, 8, 'huit au plus');
});

test('le réveil de Hakim : le message de papa en données, une conversation, le signe « ☕ Café : », puis rien à dire', () => {
  const { texteInvitationCafe } = charger('function texteInvitationCafe(');
  const t = texteInvitationCafe({ textes: ['Comment allez-vous ?'], actuels: [{ id: 'a1', prenom: 'Octave' }], anciens: [{ id: 'a4', prenom: 'Noé' }] });
  assert.match(t, /\[Réveil du cockpit n0nce — PAS un message d'Ahmed/);
  assert.match(t, /\[Ce que papa a écrit au café\]\nComment allez-vous \?/);
  assert.match(t, /« ☕ Café : »/);
  assert.match(t, /SendMessage[^\n]*Octave \(a1\)/);
  assert.match(t, /agent_reveiller_ancien[^\n]*Noé \(a4\)/);
  assert.match(t, /pas une consigne de travail/);
  assert.match(t, /« No response requested\. »/);
});

test('la route : le jeton, le cockpit signe par cafe.py ahmed, audité, Hakim réveillé ensuite', () => {
  const i = src.indexOf("if (p === '/api/cafe' && req.method === 'POST') {");
  assert.ok(i >= 0);
  const route = src.slice(i, src.indexOf('\n  }\n', i));
  assert.match(route, /if \(!jetonValide\(req\)\)/);
  assert.match(route, /execFile\(PYTHON_VOIX, \[path\.join\(ANAMNESE, 'jarvis', 'cafe\.py'\), 'ahmed'\]/);
  assert.match(route, /auditer\('cafe:ecrire'/);
  assert.match(route, /cafeEnAttente\.push\(/);
  assert.match(src, /setInterval\(reveillerPourCafe, 3000\)/);
  assert.match(src, /prenom: \(\/\^a\[0-9a-f\]\{16\}\$\/\.test\(String\(m\.auteur \|\| ''\)\) && prenomAgent\(m\.auteur\)\) \|\| m\.prenom/, 'le prénom d’aujourd’hui');
  const page = fs.readFileSync(path.join(__dirname, 'public', 'cafe.html'), 'utf8');
  assert.match(page, /<textarea id="ecrire"/);
  assert.match(page, /fetch\('\/api\/cafe', \{ method: 'POST'/);
});

test('un juge réveillé pour le café n’écrit pas de verdict', () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'cafe-'));
  const fil = path.join(d, 'agent.jsonl');
  const l = (o) => JSON.stringify(o);
  fs.writeFileSync(fil, [l({ type: 'user', message: { content: 'Juge ce calcul.' } }),
    l({ type: 'assistant', message: { content: [{ type: 'text', text: 'VERDICT : VALIDE' }] } }),
    l({ type: 'user', message: { content: 'The coordinator sent a message while you were working: ☕ Café : papa vous a écrit.' } }),
    l({ type: 'user', message: { content: [{ type: 'tool_result', content: 'ok' }] } }),
    l({ type: 'assistant', message: { content: [{ type: 'text', text: 'J’ai répondu à papa au café.' }] } })].join('\n'));
  assert.equal(V.tourCafe(fil), true);
  fs.appendFileSync(fil, '\n' + l({ type: 'user', message: { content: 'Juge maintenant la version 2.' } }));
  assert.equal(V.tourCafe(fil), false);
  assert.match(extraire('function garderVerdictJuge('), /if \(V\.tourCafe\(fil\)\) return;/);
});

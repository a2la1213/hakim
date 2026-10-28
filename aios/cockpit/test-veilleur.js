/* Le garde-fou contre les pannes d'Anthropic (28/10, Ahmed : « on met un garde-fou pour les problèmes venus d'Anthropic »).
   À 08:09, la requête de son cerveau n'a rien renvoyé pendant 1 min 43 s ; à la coupure, l'outil Claude a écrit à sa place
   « No response requested. » (« <synthetic> », 0 jeton) et Hakim a cru s'être tu. Le veilleur voit un cerveau muet alors
   qu'une demande est en cours, sans outil qui travaille ; le cockpit réessaie alors une fois.
   node --test test-veilleur.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const V = require('./veilleur.js');

const T = 1_800_000_000_000;
const rejeu = { type: 'user', isReplay: true, message: { role: 'user', content: [{ type: 'text', text: 'salut' }] } };
const outil = (id) => ({ type: 'assistant', message: { content: [{ type: 'tool_use', id, name: 'mcp__anamnese__memory_recall' }] } });
const resultatOutil = (id) => ({ type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: id }] } });

test('muet 60 s après le début de sa demande, sans outil : bloqué ; à 59 s, non', () => {
  const v = V.creer(60000);
  assert.strictEqual(v.bloque(T + 600000), false, 'sans demande, jamais');
  v.ligne(rejeu, T);
  assert.strictEqual(v.bloque(T + 59000), false);
  assert.strictEqual(v.bloque(T + 60000), true);
  v.ligne({ type: 'stream_event', event: { type: 'message_start' } }, T + 61000);
  assert.strictEqual(v.bloque(T + 100000), false, 'une ligne repart le compte');
});

test('un outil qui travaille n’est pas une panne, même long ; son résultat relance le compte', () => {
  const v = V.creer(60000);
  v.ligne(rejeu, T);
  v.ligne(outil('t1'), T + 5000);
  assert.strictEqual(v.bloque(T + 10 * 60000), false);
  v.ligne(resultatOutil('t1'), T + 10 * 60000);
  assert.strictEqual(v.bloque(T + 10 * 60000 + 59000), false);
  assert.strictEqual(v.bloque(T + 11 * 60000), true, 'la demande suivante ne revient pas : panne');
});

test('la fin du tour ferme la demande ; deux messages en file en gardent une', () => {
  const v = V.creer(60000);
  v.ligne(rejeu, T); v.ligne(rejeu, T + 1000);
  v.ligne({ type: 'result' }, T + 2000);
  assert.strictEqual(v.bloque(T + 70000), true);
  v.ligne({ type: 'result' }, T + 70000);
  assert.strictEqual(v.bloque(T + 500000), false);
});

test('une pièce rejouée (notification d’agent) n’ouvre pas de demande ; un sous-agent qui parle est une activité', () => {
  const v = V.creer(60000);
  v.ligne({ ...rejeu, isSynthetic: true }, T);
  assert.strictEqual(v.bloque(T + 600000), false);
  v.ligne(rejeu, T);
  v.ligne({ type: 'assistant', parent_tool_use_id: 'x', message: { content: [{ type: 'tool_use', id: 'sub' }] } }, T + 50000);
  assert.strictEqual(v.bloque(T + 100000), false);
  assert.strictEqual(v.bloque(T + 110000), true, 'l’outil d’un sous-agent ne compte pas comme le sien');
});

// ---- le câblage (server.js, la page)
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');

test('câblage : chaque cerveau a son veilleur, nourri de chaque ligne', () => {
  assert.match(src, /const Veilleur = require\('\.\/veilleur\.js'\)/);
  assert.match(src, /veilleur: Veilleur\.creer\(ANTHROPIC_MUET_MS\)/);
  assert.match(src, /c\.veilleur\.ligne\(o, Date\.now\(\)\);/);
});

test('câblage : un tour bloqué réessaie une fois, puis s’arrête avec la raison ; l’ancien tour ne fait plus rien', () => {
  const route = src.slice(src.indexOf('async function routeJarvis('), src.indexOf('\nfunction vitesseDuTour('));
  assert.match(route, /const reessayer = \(\) => \{/);
  assert.match(route, /cerveauDuTour\.veilleur\.bloque\(Date\.now\(\)\)/);
  assert.match(route, /tourCourant\.remplace = true;/);
  assert.match(route, /surLigne\(o\) \{\n\s+if \(tour\.remplace\) return;/);
  assert.match(route, /surFin\(code, signal\) \{\n\s+if \(tour\.remplace\) return;/);
  assert.match(route, /Anthropic n'a rien renvoyé/);
  assert.match(route, /n'est pas de toi/);                       // la note à Hakim : le silence synthétique n'est pas le sien
  assert.match(route, /envoyer\(\{ t: 'statut', x: [^}]*dire: true \}\)/);
  // (Hakim et Ahmed, 08:33 : « y a-t-il moyen de savoir pourquoi ? ») chaque panne laisse sa trace : l'attente, le modèle,
  // la taille de la conversation, et ce que claude a écrit sur sa sortie d'erreur
  assert.match(src, /const JARVIS_PANNES_ANTHROPIC = path\.join\(JARVIS, 'pannes-anthropic\.jsonl'\)/);
  assert.match(route, /noterPanneAnthropic\(\{ /);
  assert.match(src, /stderr: masquer\(String\(x\.stderr \|\| ''\)\.slice\(-600\)\)/);
});

test('la page dit le statut à voix haute quand la voix est active', () => {
  assert.match(page, /if \(o\.dire && \(etat\.conversation \|\| etat\.reglages\.volant \|\| etat\.reglages\.lectureAuto\) && !lecteur\.actif\) lecteur\.dire\(o\.x\.slice\(0, 160\)\);/);
});

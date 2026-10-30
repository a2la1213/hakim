/* (30/10, 07:50 à 08:05) un tour de 5 min sur le Mac (9,6 Mo de WAV) prenait ~35 s à transcrire : la page l'abandonnait à
   25 s, le gardait et le renvoyait en boucle, et chaque copie s'empilait dans la file du processus voix (jusqu'à 3 min de
   retard, téléphone compris). Deux corrections : le délai de la page suit la durée du morceau, et le cockpit ne transcrit
   plus une demande dont la page est partie. node --test test-transcription-file.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const extraire = (s, debut) => s.slice(s.indexOf(debut), s.indexOf('\n}\n', s.indexOf(debut)) + 3);

test('le délai de la page suit la durée du morceau (25 s pour une phrase, bien plus pour 5 min, jamais au-delà du serveur)', () => {
  const ctx = {}; vm.createContext(ctx);
  vm.runInContext(extraire(page, 'function delaiTranscription(') + '\nthis.f = delaiTranscription;', ctx);
  assert.equal(ctx.f(3 * 32000 + 44, 'audio/wav'), 25000 + 1500);
  assert.ok(ctx.f(9587884, 'audio/wav') >= 150000, 'le tour de 5 min du 30/10');
  assert.ok(ctx.f(50e6, 'audio/wav') <= 170000, 'sous les 180 s du serveur');
  assert.ok(ctx.f(0, 'audio/webm') === 25000);
  assert.match(page, /setTimeout\(\(\) => ctl\.abort\(\), delaiTranscription\(audio\.size \|\| 0, type\)\)/);
});

test('une transcription à la fois, et rien pour une page partie', async () => {
  const ctx = {}; vm.createContext(ctx);
  vm.runInContext('let transcriptionTour = Promise.resolve();\n' + extraire(src, 'function tourDeTranscription(') + '\nthis.f = tourDeTranscription;', ctx);
  const ordre = [];
  const a = await ctx.f();
  const pb = ctx.f().then((lib) => { ordre.push('b'); lib(); });
  await new Promise((r) => setTimeout(r, 20));
  assert.deepEqual(ordre, [], 'b attend que a soit libéré');
  ordre.push('a'); a(); await pb;
  assert.deepEqual(ordre, ['a', 'b']);
  const route = extraire(src, 'async function routeTranscrire(');
  assert.match(route, /res\.on\('close', \(\) => \{ if \(!res\.writableFinished\) partie = true; \}\)/);
  assert.match(route, /const liberer = await tourDeTranscription\(\);/);
  assert.match(route, /if \(partie\) \{/);
  assert.match(route, /transcription_abandonnee/);
  assert.match(route, /finally \{ liberer\(\); transcriptionsEnAttente--; pomperVoix\(\); \}/);
});

// (06/11, accord d'Ahmed pour ACE-Step : « tout faire bien pour que Hakim puisse chanter ») : sa chanson arrive comme
// une pièce jointe (fichier_joindre) ; Parler la joue sur place, Mac et téléphone, au lieu de seulement la télécharger.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const PARLER = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');

test('une pièce sonore a son bouton « écouter », une image ou un texte non', () => {
  const src = PARLER.match(/function typeSon\(t\) \{[^\n]*\}/);
  assert.ok(src, 'typeSon introuvable');
  const ctx = {}; vm.runInNewContext(src[0] + '; this.typeSon = typeSon;', ctx);
  assert.strictEqual(ctx.typeSon('mp3'), 'audio/mpeg');
  assert.strictEqual(ctx.typeSon('WAV'), 'audio/wav');
  assert.strictEqual(ctx.typeSon('png'), '');
  assert.strictEqual(ctx.typeSon(undefined), '');
  assert.match(PARLER, /data-ecouter="\$\{x\.id\}" data-son="\$\{son\}"/);
});

test('écouter : chargé derrière le jeton (blobPiece), typé en son, joué dans un lecteur', () => {
  const bloc = PARLER.slice(PARLER.indexOf("closest('[data-ecouter]')"), PARLER.indexOf("closest('[data-piece]')"));
  assert.match(bloc, /await blobPiece\(id\)/);
  assert.match(bloc, /new Blob\(\[brut\], \{ type: b\.dataset\.son/);
  assert.match(bloc, /createElement\('audio'\)/);
  assert.match(bloc, /lecteur\.controls = true/);
});

test('chanter fait partie de ses outils permis', () => {
  assert.match(fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8'), /'present_continu', 'chanter', 'studio_mixer', 'studio_avis', 'image_creer', 'clip_creer', 'atelier_voir', 'ecouter_morceau', 'instrument_apprendre'\]\.map\(n => 'mcp__anamnese__' \+ n\)/);
});

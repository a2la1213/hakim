/* (07/11, Ahmed : « les mots qui ressemblent à l'arabe ou à l'anglais, écrits dans leur langue, même transcrits en lettres latines, automatiquement,
   sans qu'il s'en rende compte ») node --test test-langues-ecrites.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const L = require('./langues-ecrites.js');

test('la darija et l’arabe en lettres arabes, l’anglais dans son orthographe, en place, sans crochets', () => {
  assert.equal(L.ecrireLangues('Salam aleykoum fiston, wallah c’est naïce, inchallah on finit bezzaf, khouya'),
    'السلام عليكم fiston, والله c’est nice, إن شاء الله on finit بزاف, خويا');
  assert.equal(L.ecrireLangues('Hamdoulah, mashallah, yallah habibi'), 'الحمد لله, ما شاء الله, يلا حبيبي');
});

test('jamais un mot français : la balle, la salade, le beat, le Sahara, Amine', () => {
  const t = 'On dit merci, la balle, la salade, le beat, le Sahara, Amine et Rania, la saison';
  assert.equal(L.ecrireLangues(t), t);
});

test('branché : à la sortie de la transcription de TA voix (pas du téléphone), réglage langues_ecrites (oui)', () => {
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(srv, /if \(r && r\.texte && temps\.source !== 'telephone' && corpsReglages\(\)\.langues_ecrites !== false\) r\.texte = ecrireLangues\(r\.texte\);/);
  assert.match(srv, /langues_ecrites: r\.langues_ecrites !== false,/);
});

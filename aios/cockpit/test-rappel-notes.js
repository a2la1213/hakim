/* (30/10, Ahmed : « qu'il balaye aussi tout son journal proche, ses notes d'erreur, tous les petits calepins importants
   pour lui ; automatique, autonome, inconscient ») le rappel (anamnese/rappel.py notes_pertinentes) rend aussi ses notes ;
   le cockpit les met dans son tour, une fois par conversation chacune. node --test test-rappel-notes.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const extraire = (debut) => src.slice(src.indexOf(debut), src.indexOf('\n}\n', src.indexOf(debut)) + 3);

test('ses notes : demandées sans celles déjà dites, mises dans son tour, retenues par conversation', () => {
  assert.match(src, /const notesDejaDites = new Map\(\);/);
  assert.match(extraire('function rappeler('), /exclus_notes: \[\.\.\.exclusNotes\]\.slice\(-3000\)/);
  const b = extraire('async function blocRappel(');
  assert.match(b, /\(r && r\.notes\) \|\| \[\]/);
  assert.match(b, /dejaNotes\.has\(id\)/);
  assert.match(b, /blocDonnees\('Tes notes qui s\\'y rapportent/);
  assert.match(b, /notes: notesIds/);
  assert.match(extraire('function retenirRappel('), /notesDejaDites/);
  assert.match(src, /retenirRappel\(sid, rappelBloc\.ids \|\| \[\], rappelBloc\.erreurs \|\| \[\], rappelBloc\.personnes \|\| \[\], rappelBloc\.notes \|\| \[\], rappelBloc\.intime \|\| \[\]\)/);
});

test('son jardin secret : à part, à lui seul, jamais noté au journal du rappel (ni texte ni numéros)', () => {
  const b = extraire('async function blocRappel(');
  assert.match(b, /\(r && r\.intime\) \|\| \[\]/);
  assert.match(b, /blocDonnees\('Ton jardin secret/);
  assert.match(b, /intime: intimeIds\.length/, 'au journal : un nombre seulement');
  const journal = b.slice(b.indexOf('fs.appendFileSync(JARVIS_RAPPEL_JOURNAL'), b.indexOf('\n', b.indexOf('fs.appendFileSync(JARVIS_RAPPEL_JOURNAL')) + 400);
  assert.doesNotMatch(journal, /intime: intimeIds[,\s}]|intimeIds\.join|intime\.join/);
  assert.match(extraire('function rappeler('), /exclus_intime: \[\.\.\.exclusIntime\]/);
  assert.match(extraire('function retenirRappel('), /intimeDejaDites/);
});

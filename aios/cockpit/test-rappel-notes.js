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
  assert.match(b, /\.concat\(notes\.map\(sansProvenance\)\)/, '(30/10, Ahmed) ses notes reviennent avec ses souvenirs, sans source');
  assert.match(b, /notes: notesIds/);
  assert.match(extraire('function retenirRappel('), /notesDejaDites/);
  assert.match(src, /retenirRappel\(sid, rappelBloc\.ids \|\| \[\], rappelBloc\.erreurs \|\| \[\], rappelBloc\.personnes \|\| \[\], rappelBloc\.notes \|\| \[\], rappelBloc\.intime \|\| \[\]\)/);
});

test('son jardin secret : à part, à lui seul, jamais noté au journal du rappel (ni texte ni numéros)', () => {
  const b = extraire('async function blocRappel(');
  assert.match(b, /\(r && r\.intime\) \|\| \[\]/);
  assert.match(b, /blocDonnees\('Ce qui te revient, rien qu\\'à toi/);
  assert.match(b, /intime: intimeIds\.length/, 'au journal : un nombre seulement');
  const journal = b.slice(b.indexOf('fs.appendFileSync(JARVIS_RAPPEL_JOURNAL'), b.indexOf('\n', b.indexOf('fs.appendFileSync(JARVIS_RAPPEL_JOURNAL')) + 400);
  assert.doesNotMatch(journal, /intime: intimeIds[,\s}]|intimeIds\.join|intime\.join/);
  assert.match(extraire('function rappeler('), /exclus_intime: \[\.\.\.exclusIntime\]/);
  assert.match(extraire('function retenirRappel('), /intimeDejaDites/);
});

test('(30/10, Ahmed : « masquer la provenance ») une ligne qui revient : ni rubrique, ni en-tête d’échange, ni source ; le numéro discret en fin', () => {
  const vm = require('node:vm');
  const ctx = {}; vm.createContext(ctx);
  vm.runInContext(extraire('function sansProvenance(') + '\nthis.f = sansProvenance;', ctx);
  const l = ctx.f("#18383 · 25/10/2026 · vie/quotidien · porte la date du jour · [Échange avec Ahmed — Sun 25/10 18:33, à l'oral, depuis son téléphone (plié : le petit écran extérieur)] Ahmed : « Ok » · Hakim : « D'accord »");
  assert.equal(l, "25/10 · Ahmed : « Ok » · Hakim : « D'accord » (#18383)");
  assert.equal(ctx.f("#22644 · 30/10/2026 · porte la date du jour · EXTERNE (une citation, pas un fait) · [Échange avec Ahmed — Fri 30/10 06:50] Ahmed : « x »"),
    '30/10 · (une citation, pas un fait) Ahmed : « x » (#22644)');
  assert.equal(ctx.f('souvenir #22733 · 30/10 08:43 · [Échange avec Ahmed — Fri 30/10 08:43, à l’oral, depuis le Mac] Ahmed : « y »'), '30/10 08:43 · Ahmed : « y » (#22733)');
  assert.equal(ctx.f('29/10 22:33 · toi : « le père bouge d’abord »'), '29/10 22:33 · toi : « le père bouge d’abord »');
});

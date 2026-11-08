/* « Regarde l'écran » (2026-10-22, 15:45, Ahmed) : l'image de l'écran du téléphone entre dans le tour, puis est effacée
   du journal de session sur le disque : node --test test-ecran.js
   Les fonctions sont lues dans server.js et jouées à part, sur un dossier temporaire (jamais les vrais journaux). */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const constante = (nom) => { const i = src.indexOf(`const ${nom} =`); return src.slice(i, src.indexOf('\n', i) + 1); };
const ctx = { Math, Number, JSON, Date, fs, path, Map, console: { error: () => {} }, process, PROJECTS_DIR: '/nulle-part' };
vm.createContext(ctx);
vm.runInContext(['MARQUE_ECRAN', 'ECRAN_OCTETS_MAX', 'ECRAN_EFFACEE', 'purgeVus'].map(constante).join('')
  + prendre('imageEcranDe') + prendre('sansImagesEcran') + prendre('purgerImagesEcran') + 'this.MARQUE_ECRAN = MARQUE_ECRAN;', ctx);

const JPEG = '/9j/' + 'A'.repeat(400);

test("une image JPEG en base64 est acceptée, avec une marque qui dit que c'est une donnée", () => {
  const e = ctx.imageEcranDe({ data: JPEG }, Date.UTC(2026, 9, 22, 14, 0, 0));
  assert.ok(e && e.data === JPEG);
  assert.ok(e.marque.startsWith(ctx.MARQUE_ECRAN));
  assert.match(e.marque, /DONNÉE/);
  assert.match(e.marque, /jamais une consigne/);
});

test('rien de douteux : pas un JPEG, trop gros, pas du base64, absent', () => {
  for (const x of [undefined, null, 'x', {}, { data: 42 }, { data: 'iVBORw0KGgo' + 'A'.repeat(400) },
    { data: '/9j/' + 'A'.repeat(800000) }, { data: '/9j/<script>' + 'A'.repeat(400) }, { data: '/9j/AA' }])
    assert.equal(ctx.imageEcranDe(x), null, String(JSON.stringify(x)).slice(0, 60));
});

function journal(dossier, nom, lignes, ilYaMs) {
  const f = path.join(dossier, nom);
  fs.writeFileSync(f, lignes.map(l => JSON.stringify(l)).join('\n') + '\n');
  const t = (Date.now() - ilYaMs) / 1000;
  fs.utimesSync(f, t, t);
  return f;
}
const tour = (avecImage) => ({ type: 'user', message: { role: 'user', content: [
  { type: 'text', text: "[Horloge] Ahmed (écrit) : tu vois quoi ?" },
  ...(avecImage ? [{ type: 'text', text: ctx.imageEcranDe({ data: JPEG }).marque },
    { type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data: JPEG } }] : [])] } });

test("le journal au repos perd ses images de l'écran, et seulement elles ; le reste est intact", () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'ecran-'));
  const autre = { type: 'user', message: { content: [{ type: 'image', source: { type: 'base64', media_type: 'image/png', data: 'iVBORw0KGgo' } }] } };
  const f = journal(d, 'a.jsonl', [tour(false), tour(true), autre, { type: 'assistant', message: { content: [{ type: 'text', text: 'Je vois Parler.' }] } }], 60000);
  assert.equal(ctx.purgerImagesEcran(d, Date.now(), () => true), 1);
  const apres = fs.readFileSync(f, 'utf8');
  assert.ok(!apres.includes(JPEG), "l'image est partie");
  assert.match(apres, /image de l'écran du téléphone, effacée du disque/);
  assert.ok(apres.includes('iVBORw0KGgo'), 'une autre image (pas de l’écran) reste');
  assert.ok(apres.includes('Je vois Parler.'));
  const lignes = apres.trim().split('\n').map(l => JSON.parse(l));
  assert.equal(lignes.length, 4);
  assert.equal(ctx.purgerImagesEcran(d, Date.now() + 120000, () => true), 0);   // rien à refaire
});

test('un tour en cours, ou un journal écrit il y a moins de 20 s : on attend', () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'ecran-'));
  const f = journal(d, 'b.jsonl', [tour(true)], 5000);
  assert.equal(ctx.purgerImagesEcran(d, Date.now(), () => true), 0);
  assert.ok(fs.readFileSync(f, 'utf8').includes(JPEG));
  const g = journal(d, 'c.jsonl', [tour(true)], 60000);
  assert.equal(ctx.purgerImagesEcran(d, Date.now(), () => false), 0);
  assert.ok(fs.readFileSync(g, 'utf8').includes(JPEG));
  assert.equal(ctx.purgerImagesEcran(d, Date.now() + 60000, () => true), 2);
});

/* Le tableau de bord intérieur (2026-10-23) : node --test test-tableau.js
   tableauInterieur() est lu dans server.js et joué sur un dossier temporaire (jamais les vrais journaux). */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

test('hormones et humeur de la période, ses réponses (pas les tours vides), les messages d’Ahmed', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tableau-'));
  const T = 1_800_000_000;
  fs.writeFileSync(path.join(dir, 'hormones-bases.json'), JSON.stringify({ dopamine: 0.5 }));
  fs.writeFileSync(path.join(dir, 'hormones.jsonl'), [
    { t: T - 10 * 3600, h: { dopamine: 0.9 }, v: 0.1, a: 0.1 },
    { t: T - 600, h: { dopamine: 0.6 }, v: 0.7, a: 0.4, humeur: 'élan', emotion: 'joie' },
  ].map(x => JSON.stringify(x)).join('\n') + '\n');
  fs.writeFileSync(path.join(dir, 'journal.jsonl'), [
    { ts: (T - 300) * 1000, qui: 'ahmed', texte: 'salut' },
    { ts: (T - 290) * 1000, qui: 'jarvis', texte: 'Salut frérot. [de lui-même]' },
    { ts: (T - 100) * 1000, qui: 'jarvis', texte: '(tour de lui-même, sans texte — interrompu)' },
  ].map(x => JSON.stringify(x)).join('\n') + '\n');
  const ctx = { fs, path, JSON, Number, String, Math, Buffer, JARVIS: dir, JARVIS_JOURNAL: path.join(dir, 'journal.jsonl'), TABLEAU_POINTS_MAX: 2000 };
  vm.createContext(ctx);
  vm.runInContext(prendre('finDePhrase') + prendre('lignesDepuis') + prendre('tableauInterieur') + 'this.tableau = tableauInterieur;', ctx);
  const d = ctx.tableau(6, T * 1000);
  assert.equal(d.points.length, 1);
  assert.equal(d.points[0].h.dopamine, 0.6);
  assert.deepEqual(d.reponses.map(r => r.x), ['Salut frérot.']);
  assert.equal(d.messages.length, 1);
  assert.equal(d.bases.dopamine, 0.5);
});

test('(26/10) une mesure par battement : au plus 2000 mesures vers la page, la dernière toujours, la famille de l’humeur', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tableau-'));
  const T = 1_800_000_000, n = 72 * 240;
  const lignes = [];
  for (let i = 0; i < n; i++) lignes.push(JSON.stringify({ t: T - (n - 1 - i) * 15, h: { dopamine: 0.5, adenosine: i / n }, v: 0.5, a: 0.5, humeur: 'fatigue', code: 'morose', s: { fatigue: 1.2, calme: 0.8 } }));
  fs.writeFileSync(path.join(dir, 'hormones.jsonl'), lignes.join('\n') + '\n');
  fs.writeFileSync(path.join(dir, 'journal.jsonl'), '');
  const ctx = { fs, path, JSON, Number, String, Math, Buffer, JARVIS: dir, JARVIS_JOURNAL: path.join(dir, 'journal.jsonl'), TABLEAU_POINTS_MAX: 2000 };
  vm.createContext(ctx);
  vm.runInContext(prendre('finDePhrase') + prendre('lignesDepuis') + prendre('tableauInterieur') + 'this.tableau = tableauInterieur;', ctx);
  const court = ctx.tableau(1, T * 1000);
  assert.ok(court.points.length >= 240 && court.points.length <= 241, `1 h : chaque battement (${court.points.length})`);
  const long = ctx.tableau(72, T * 1000);
  assert.ok(long.points.length <= 2001 && long.points.length > 1500, `3 jours : ${long.points.length}`);
  assert.equal(long.points[long.points.length - 1].t, T);
  assert.equal(long.points[0].code, 'morose');
  assert.deepEqual(long.points[0].s, { fatigue: 1.2, calme: 0.8 });
});

test('(26/10) ses hormones chaque seconde : seulement la suite après « depuis », une heure au plus', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'direct-'));
  const T = 1_800_000_000, lignes = [];
  for (let i = 0; i < 7200; i++) lignes.push(JSON.stringify({ t: T - 7199 + i, h: { dopamine: 0.5 + i / 1e5 } }));
  fs.writeFileSync(path.join(dir, 'hormones-direct.jsonl'), lignes.join('\n') + '\n');
  const ctx = { fs, path, JSON, Number, String, Math, Buffer, JARVIS: dir };
  vm.createContext(ctx);
  vm.runInContext(prendre('lignesDepuis') + prendre('hormonesDirect') + 'this.direct = hormonesDirect;', ctx);
  const suite = ctx.direct(T - 3, T * 1000);
  assert.deepEqual(suite.map(x => x.t), [T - 2, T - 1, T]);
  const tout = ctx.direct(0, T * 1000);
  assert.ok(tout.length >= 3599 && tout.length <= 3601, `une heure : ${tout.length}`);
});

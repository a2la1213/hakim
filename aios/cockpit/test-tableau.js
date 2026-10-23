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
  const ctx = { fs, path, JSON, Number, String, Math, Buffer, JARVIS: dir, JARVIS_JOURNAL: path.join(dir, 'journal.jsonl') };
  vm.createContext(ctx);
  vm.runInContext(prendre('finDePhrase') + prendre('lignesDepuis') + prendre('tableauInterieur') + 'this.tableau = tableauInterieur;', ctx);
  const d = ctx.tableau(6, T * 1000);
  assert.equal(d.points.length, 1);
  assert.equal(d.points[0].h.dopamine, 0.6);
  assert.deepEqual(d.reponses.map(r => r.x), ['Salut frérot.']);
  assert.equal(d.messages.length, 1);
  assert.equal(d.bases.dopamine, 0.5);
});

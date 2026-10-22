/* Hakim s'entend (2026-10-22) : node --test test-voix-recente.js — les 30 derniers morceaux de SA voix gardés, pas plus. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

test('trente morceaux au plus, les plus anciens effacés, texte et durée gardés', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'voix-recente-'));
  let t = 1_800_000_000_000;
  const ctx = { fs, path, crypto, JSON, Number, Math, Date: { now: () => ++t }, j: JSON.stringify,
    lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } },
    ecrireAtomique: (f, s) => fs.writeFileSync(f, s), VOIX_RECENTE: path.join(dir, 'r'), VOIX_RECENTE_MAX: 30 };
  ctx.VOIX_RECENTE_INDEX = path.join(ctx.VOIX_RECENTE, 'index.json');
  vm.createContext(ctx);
  vm.runInContext(prendre('garderVoixRecente') + 'this.garder = garderVoixRecente;', ctx);
  for (let i = 0; i < 33; i++) {
    const f = path.join(dir, `t${i}.wav`);
    fs.writeFileSync(f, 'RIFF');
    ctx.garder({ fichier: f, texte: `phrase ${i}`, langue: 'fr' }, 1.5);
    assert.ok(!fs.existsSync(f));
  }
  const l = JSON.parse(fs.readFileSync(ctx.VOIX_RECENTE_INDEX, 'utf8'));
  assert.strictEqual(l.length, 30);
  assert.strictEqual(l[0].texte, 'phrase 3');
  assert.strictEqual(fs.readdirSync(ctx.VOIX_RECENTE).filter(x => x.endsWith('.wav')).length, 30);
});

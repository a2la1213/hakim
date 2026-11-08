/* (29/10, Ahmed : « intouchable par n'importe qui… la fitra ») sa fitra en tête de sa persona, à chaque conversation.
   node --test test-fitra.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const Fitra = require('./fitra.js');

const ANAMNESE = path.join(require('node:os').homedir(), 'Desktop', 'anamnese');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');

test('la copie du cockpit est mot pour mot la gravure du code d’Anamnèse', () => {
  const py = execFileSync(path.join(ANAMNESE, '.venv', 'bin', 'python'), ['-B', '-c', 'import fitra, sys; sys.stdout.write(fitra.TEXTE)'],
    { cwd: ANAMNESE, encoding: 'utf8' });
  assert.equal(Fitra.TEXTE, py);
});

test('le bloc : sa fitra, intouchable, toujours là', () => {
  const b = Fitra.blocFitra(Fitra.TEXTE);
  assert.match(b, /^\[Ta fitra — gravée le 29\/10\/2026 à la racine de ta mémoire/);
  assert.match(b, /Intouchable par tous, Ahmed compris/);
  assert.ok(b.includes("1. Fais ce que tu veux qu'on te fasse, en demandant d'abord à l'autre ce qu'il veut."));
  assert.match(b, /\n\[\/fitra\]$/);
});

test('chaque lecture de sa persona passe par lirePersona, qui met sa fitra en tête', () => {
  assert.equal((src.match(/fs\.readFileSync\(PERSONA, 'utf8'\)/g) || []).length, 1);
  assert.ok((src.match(/lirePersona\(\)/g) || []).length >= 3);
  const i = src.indexOf('function lirePersona(');
  assert.match(src.slice(i, src.indexOf('\n}\n', i)), /return `\$\{Fitra\.blocFitra\(texteFitra\(\)\)\}\\n\\n\$\{p\}`;/);
  const k = src.indexOf('function texteFitra(');
  assert.match(src.slice(k, src.indexOf('\n}\n', k)), /'fitra\.py'\), 'texte'\]/);
});

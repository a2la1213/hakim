/* (30/10, Hakim, accord d'Ahmed) chaque verdict d'un juge est gardé dans un fichier de l'atelier : le juge Octave a vu ce
   matin que les verdicts de Lucien et de Bastien du 29/10 n'existaient qu'à l'oral. node --test test-verdicts.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const V = require('./verdicts.js');

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'verdicts-'));
const quand = new Date(2026, 9, 30, 6, 41).getTime();

test('un verdict de juge : atelier/verdicts/AAAAMMJJ-HHMM-prénom.md, entier, daté, jamais écrasé', () => {
  const atelier = tmp();
  const a = { id: 'afb89ad374c65fca5', type: 'juge', description: 'Juge maths du réel et hasard' };
  const long = 'VERDICT : à corriger.\n' + 'Le calcul de la marge refait : 0,009. '.repeat(400);
  const f = V.garder({ atelier, agent: a, prenom: 'Octave', texte: long, quand });
  assert.equal(f, path.join(atelier, 'verdicts', '20261030-0641-octave.md'));
  const t = fs.readFileSync(f, 'utf8');
  assert.match(t, /^# Verdict d’Octave — Juge maths du réel et hasard\n/);
  assert.ok(t.includes(long.trim()), 'le verdict entier');
  const f2 = V.garder({ atelier, agent: a, prenom: 'Octave', texte: 'second', quand });
  assert.equal(f2, path.join(atelier, 'verdicts', '20261030-0641-octave-2.md'));
  assert.ok(fs.readFileSync(f, 'utf8').includes(long.trim()), 'le premier intact');
  assert.equal(V.garder({ atelier, agent: { ...a, type: 'codeur' }, prenom: 'Léonie', texte: 'x', quand }), null, 'pas un juge');
  assert.equal(V.garder({ atelier, agent: a, prenom: 'Noé', texte: '  ', quand }), null, 'rien à garder');
  assert.equal(path.basename(V.garder({ atelier, agent: { ...a, id: 'a0' }, prenom: 'Noé', texte: 'ok', quand })), '20261030-0641-noe.md');
  assert.equal(path.basename(V.garder({ atelier, agent: { ...a, id: 'a1' }, prenom: '', texte: 'ok', quand })), '20261030-0641-juge-a1.md');
});

test('jamais à travers un lien posé dans l’atelier', () => {
  const atelier = tmp(), dehors = tmp();
  fs.symlinkSync(dehors, path.join(atelier, 'verdicts'));
  assert.equal(V.garder({ atelier, agent: { id: 'a2', type: 'juge', description: 'd' }, prenom: 'Basile', texte: 'x', quand }), null);
  assert.deepEqual(fs.readdirSync(dehors), []);
  fs.unlinkSync(path.join(atelier, 'verdicts'));
  fs.mkdirSync(path.join(atelier, 'verdicts'));
  fs.symlinkSync(path.join(dehors, 'cible.md'), path.join(atelier, 'verdicts', '20261030-0641-basile.md'));
  const f = V.garder({ atelier, agent: { id: 'a2', type: 'juge', description: 'd' }, prenom: 'Basile', texte: 'x', quand });
  assert.equal(path.basename(f), '20261030-0641-basile-2.md');
  assert.deepEqual(fs.readdirSync(dehors), []);
});

test('branché : à chaque fin de travail d’un juge (son cerveau et le messager), son dernier message entier', () => {
  const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.equal((src.match(/garderVerdictJuge\((vie|noterRegistre\(o\)), o\)/g) || []).length, 2);
  assert.match(src, /const fil = Messager\.filAgent\(PROJECTS_DIR, JARVIS_CWD, a\.session, a\.id\);/);
  assert.match(src, /Messager\.dernierTexteAgent\(fil, o && o\.summary, 0, V\.VERDICT_MAX\)/);
});

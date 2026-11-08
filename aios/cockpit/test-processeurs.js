// (03/11, 16:10, Ahmed : « son cœur relié à son GPU et à tous ses cœurs CPU, sur le Mac mais aussi sur tous les appareils où il est
// connecté, smartphone et montre ») le dernier état des processeurs de chaque appareil, rangé pour son cœur (anamnese)
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');

function charger() {
  const i = SRC.indexOf('const PROCESSEURS_APPAREILS'), k = SRC.indexOf('\n}\n', SRC.indexOf('function noterProcesseurs(')) + 3;
  let T = 100000, fichier = {};
  const ctx = { Date: { now: () => T }, Number, Math, Array, path, JARVIS: '/x', j: JSON.stringify,
    lireJson: () => JSON.parse(JSON.stringify(fichier)), ecrireAtomique: (_, c) => { fichier = JSON.parse(c); } };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.noter = noterProcesseurs;', ctx);
  return { noter: ctx.noter, lu: () => fichier, temps: (t) => { T = t; } };
}

test('chaque appareil garde son dernier état, borné de 0 à 1 ; un appareil inconnu est refusé', () => {
  const p = charger();
  assert.strictEqual(p.noter('telephone', { coeurs: [0.5, 1.7, null, -2], gpu: 0.3, thermique: null }), true);
  assert.deepStrictEqual(p.lu().telephone, { ts: 100000, coeurs: [0.5, 1, null, 0], gpu: 0.3, thermique: null });
  assert.strictEqual(p.noter('montre', { coeurs: [0.2], gpu: null, thermique: 0.1 }), true, 'la montre a son propre rythme d’envoi');
  assert.ok(p.lu().telephone && p.lu().montre);
  assert.strictEqual(p.noter('grille-pain', { coeurs: [1] }), false);
  assert.strictEqual(p.lu()['grille-pain'], undefined);
});

test('au plus une fois toutes les 4 s par appareil', () => {
  const p = charger();
  p.noter('telephone', { coeurs: [0.1] });
  p.temps(102000);
  assert.strictEqual(p.noter('telephone', { coeurs: [0.9] }), false);
  assert.deepStrictEqual(p.lu().telephone.coeurs, [0.1]);
  p.temps(104500);
  assert.strictEqual(p.noter('telephone', { coeurs: [0.9] }), true);
  assert.deepStrictEqual(p.lu().telephone.coeurs, [0.9]);
});

test('le téléphone l’envoie avec son milieu, retiré avant son homéostasie ; la montre par sa route', () => {
  assert.match(SRC, /q\.etat\.processeur\) \{ noterProcesseurs\('telephone', q\.etat\.processeur\); delete q\.etat\.processeur; \}/);
  assert.match(SRC, /p === '\/api\/corps\/processeur' && req\.method === 'POST'/);
});

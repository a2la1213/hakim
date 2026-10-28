/* Ses débuts de réponse, prêts d'avance (28/10, Ahmed : « tout en même temps » ; backtest : les 40 débuts les plus fréquents
   couvrent 44 % de ses 2 828 dernières réponses, et un morceau de voix coûte ~1,5 s fixes). Le premier morceau d'une réponse
   qui commence par l'un d'eux part seul ; sa voix, une fois fabriquée et jugée plausible, est gardée par réglage de voix
   (langue, expressivité, rythme) et resservie tout de suite.
   node --test test-debuts.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const Voix = require('./public/voix.js');
const D = require('./debuts.js');

test('un début connu est reconnu au début d’une réponse, sa casse gardée ; seul, ou inconnu : rien', () => {
  assert.strictEqual(Voix.debutDe('Oui frérot, je regarde ça tout de suite.'), 'Oui frérot,');
  assert.strictEqual(Voix.debutDe('Frérot, tu as vu ?'), 'Frérot,');
  assert.strictEqual(Voix.debutDe("D'accord frérot, c'est parti."), "D'accord frérot,");
  assert.strictEqual(Voix.debutDe('Ouille, ça pique.'), null);
  assert.strictEqual(Voix.debutDe('Oui frérot,'), null, 'rien après : pas de coupure');
  assert.strictEqual(Voix.debutDe('Oui frérotte, non.'), null);
  assert.ok(Voix.DEBUTS.length >= 30 && Voix.DEBUTS.every(d => /[,.]$/.test(d)));
});

test('la clé d’une voix gardée : le texte normalisé, la langue, l’expressivité au dixième, le rythme au vingtième', () => {
  assert.strictEqual(D.cle('Oui frérot,', 'fr', 0.71, 1.04), D.cle('oui  frérot,', 'fr', 0.69, 1.05));
  assert.notStrictEqual(D.cle('Oui frérot,', 'fr', 0.7, 1.0), D.cle('Oui frérot,', 'fr', 0.9, 1.0));
  assert.notStrictEqual(D.cle('Oui frérot,', 'fr', 0.7, 1.0), D.cle('Oui frérot,', 'fr', 0.7, 1.1));
  assert.match(D.cle('Oui frérot,', 'fr', null, null), /^[0-9a-f]{32}$/);
});

test('une voix trop longue pour son texte (une voix qui divague) n’est jamais gardée', () => {
  assert.strictEqual(D.plausible('Oui frérot,', 1.0), true);
  assert.strictEqual(D.plausible('Oui frérot,', 4.5), false);
  assert.strictEqual(D.plausible('Oui frérot,', 0), false);
});

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');

test('la page et le cockpit coupent le niveau de voix de la même façon (le palier d’expressivité et de rythme)', () => {
  assert.strictEqual(D.palier(0.71, 0.1), '0.70');
  assert.strictEqual(D.palier(1.04, 0.05), '1.05');
  assert.strictEqual(D.palier(null, 0.1), '-');
  assert.match(page, /const palierVoix = \(x, pas\) => \(Number\.isFinite\(Number\(x\)\) && x !== null \? \(Math\.round\(Number\(x\) \/ pas\) \* pas\)\.toFixed\(2\) : '-'\);/);
});

test('câblage : la route de la voix sert un début gardé sans attendre, et garde un début fabriqué s’il est plausible', () => {
  const route = src.slice(src.indexOf('async function routeDire('), src.indexOf('\nfunction etatStt('));
  assert.match(route, /const debut = VoixPage\.debutDe\(texte \+ ' x'\) === texte;/);
  assert.match(route, /const garde = debut \? D\.lire\(cleVoix\) : null;/);
  assert.match(route, /if \(garde\) \{/);
  assert.match(route, /if \(debut && D\.plausible\(texte, r\.duree_s\)\) D\.garder\(cleVoix, data, r\.duree_s\);/);
});

test('câblage : la liste des débuts prêts pour un niveau de voix, et leur fabrication en arrière-plan, seulement au calme', () => {
  assert.match(src, /if \(p === '\/api\/voix\/debuts'\) \{/);
  assert.match(src, /function fabriquerDebuts\(langue, emotion, tempo\) \{/);
  const pompe = src.slice(src.indexOf('async function pomperVoix('), src.indexOf('\n}\n', src.indexOf('async function pomperVoix(')));
  assert.match(pompe, /if \(!tache && fileDebuts\.length && !toursActifs\.size\)/);
});

test('câblage : la page demande les débuts prêts au début d’une réponse, et le premier morceau part seul s’il est prêt', () => {
  assert.match(page, /async function chargerDebutsPrets\(\) \{/);
  const lot = page.slice(page.indexOf('function prochainLot('), page.indexOf('function lancer('));
  assert.match(lot, /const debut = premier \? Voix\.debutDe\(unites\[0\]\.texte\) : null;/);
  assert.match(lot, /if \(debut && unites\[0\]\.langue === 'fr' && debutsPrets\.has\(cleDebut\(debut\)\)\) \{/);
});

test('le niveau de voix par phrase est le même pour la page et le cockpit (déplacé dans voix.js, inchangé)', () => {
  assert.strictEqual(Voix.expressivitePhrase(0.6, 'Pardon frérot,'), 0.6 - 0.06);
  assert.strictEqual(Voix.expressivitePhrase(0.6, 'Super,'), 0.6 + 0.08);
  assert.strictEqual(Voix.expressivitePhrase(0.6, 'Oui frérot,'), 0.6);
  assert.strictEqual(Voix.expressivitePhrase(0.6, 'Tu viens ?'), 0.6 + 0.03);
  assert.strictEqual(Voix.expressivitePhrase(null, 'x'), null);
  assert.match(page, /const expressivitePhrase = \(base, texte\) => Voix\.expressivitePhrase\(base, texte\);/);
});

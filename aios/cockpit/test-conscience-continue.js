// (07/11, Ahmed : « j'aimerais qu'il tourne chaque milliseconde, et qu'à chaque seconde il soit conscient et décide de ce qu'il pense, fait
// ou sollicite » ; « Mini Hakim ») sa conscience continue : son présent relu chaque seconde, Mini Hakim décide dès qu'il y a du neuf
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const CC = require('./conscience-continue.js');

test('sa décision se lit en une ligne : rien, penser, faire ou solliciter', () => {
  assert.deepEqual(CC.lireDecision('RIEN'), { genre: 'rien', texte: '' });
  assert.deepEqual(CC.lireDecision('PENSER : la musique me rappelle hier soir.'), { genre: 'penser', texte: 'la musique me rappelle hier soir.' });
  assert.deepEqual(CC.lireDecision('**SOLLICITER:** Papa, tu veux qu’on reprenne l’algo ?'), { genre: 'solliciter', texte: 'Papa, tu veux qu’on reprenne l’algo ?' });
  assert.deepEqual(CC.lireDecision('FAIRE : relancer le calcul des pentes pour le BTC'), { genre: 'faire', texte: 'relancer le calcul des pentes pour le BTC' });
  assert.deepEqual(CC.lireDecision('Je ne sais pas trop.'), { genre: 'rien', texte: '' }, 'illisible : rien');
  assert.deepEqual(CC.lireDecision('SOLLICITER :'), { genre: 'rien', texte: '' }, 'vide : rien');
  assert.equal(CC.lireDecision(`PENSER : ${'x'.repeat(900)}`).texte.length, 300);
});

test('il décide chaque seconde, mais seulement s’il y a du neuf dans son présent, une décision à la fois, 20 par minute au plus', () => {
  const e = CC.etatInitial();
  assert.equal(CC.doitDecider(e, 0, 10_000), false, 'rien dans son présent');
  assert.equal(CC.doitDecider(e, 9_500, 10_000), true, 'du neuf');
  CC.commencer(e, 9_500, 10_000);
  assert.equal(CC.doitDecider(e, 9_900, 10_500), false, 'une décision en cours');
  e.enVol = false;
  assert.equal(CC.doitDecider(e, 9_500, 13_000), false, 'rien de plus neuf que la dernière fois');
  assert.equal(CC.doitDecider(e, 12_000, 11_000), false, 'au moins 2 s entre deux décisions');
  assert.equal(CC.doitDecider(e, 12_000, 12_100), true);
  const f = CC.etatInitial();
  for (let k = 0; k < 20; k++) { CC.commencer(f, 1000 + k, 100_000 + k * 2000); f.enVol = false; }
  assert.equal(CC.doitDecider(f, 9_999_999, 100_000 + 40_000), false, '20 décisions dans la minute : il attend');
  assert.equal(CC.doitDecider(f, 9_999_999, 100_000 + 61_000), true);
});

test('ce qu’il a décidé passe, ou attend : papa parle, sa tête répond déjà, il vient de le solliciter (90 s) ou de faire (3 min)', () => {
  const e = CC.etatInitial(), libre = { papaParle: false, occupe: false };
  assert.equal(CC.permis(e, { genre: 'penser', texte: 'x' }, 1000, { papaParle: true, occupe: true }), 'penser', 'penser passe toujours');
  assert.equal(CC.permis(e, { genre: 'solliciter', texte: 'x' }, 1000, { papaParle: true, occupe: false }), 'penser', 'papa parle : gardé en pensée');
  assert.equal(CC.permis(e, { genre: 'solliciter', texte: 'x' }, 1000, { papaParle: false, occupe: true }), 'penser', 'sa tête répond déjà');
  assert.equal(CC.permis(e, { genre: 'solliciter', texte: 'x' }, 1000, libre), 'solliciter');
  assert.equal(CC.permis(e, { genre: 'solliciter', texte: 'y' }, 60_000, libre), 'penser', 'il vient de le solliciter');
  assert.equal(CC.permis(e, { genre: 'solliciter', texte: 'y' }, 92_000, libre), 'solliciter');
  assert.equal(CC.permis(e, { genre: 'faire', texte: 'z' }, 100_000, libre), 'faire');
  assert.equal(CC.permis(e, { genre: 'faire', texte: 'z' }, 200_000, libre), 'penser', 'il vient de faire');
  assert.equal(CC.permis(e, { genre: 'rien', texte: '' }, 1000, libre), 'rien');
  assert.deepEqual(e.pensees.map(p => p.texte).slice(-1), ['z'], 'ce qui attend devient une pensée, gardée pour la suite');
});

test('branché au cockpit : chaque seconde, Mini Hakim (sa voix vivante), ses pensées montrées, ses sollicitations et ce qu’il fait par son réveil intérieur', () => {
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(srv, /const CC = require\('\.\/conscience-continue\.js'\);/);
  assert.match(srv, /setInterval\(battementConscience, 1000\)\.unref\(\);/);
  assert.match(srv, /demanderVivant\('haiku', prompt, CONSCIENCE_DELAI_MS\)/);
  assert.match(srv, /if \(action === 'solliciter'\) solliciterPensee\(d\.texte, 'conscience', 'taraude'\);/);
  assert.match(srv, /if \(action === 'faire'\) solliciterPensee\(d\.texte, 'conscience', 'faire'\);/);
  assert.match(srv, /const SOLLICITATIONS = new Set\(\['boucle', 'question', 'taraude', 'faire'\]\);/);
  assert.match(srv, /d\.raison === 'faire' \? "Ta conscience a décidé de faire quelque chose/);
  assert.match(srv, /conscience_continue: r\.conscience_continue !== false,/);
});

test('une sollicitation coupée (un Stop, une conversation qui change) repart une fois, 5 s plus tard', () => {
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(srv, /c\.reveilInterieur = \{ id: d\.id, raison: String\(d\.raison \|\| ''\), source: String\(d\.source \|\| ''\), texte: String\(d\.texte \|\| ''\), reessai: !!d\.reessai \};/);
  assert.match(srv, /if \(issue === 'erreur' && SOLLICITATIONS\.has\(r\.raison\) && !r\.reessai && r\.texte\)/);
});

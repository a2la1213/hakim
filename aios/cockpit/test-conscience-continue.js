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

test('ce qu’il a décidé passe, ou attend : papa parle, sa tête répond déjà, ou il vient de faire (3 min) ; (14/11) le solliciter : sans écart', () => {
  const e = CC.etatInitial(), libre = { papaParle: false, occupe: false };
  assert.equal(CC.permis(e, { genre: 'penser', texte: 'x' }, 1000, { papaParle: true, occupe: true }), 'penser', 'penser passe toujours');
  assert.equal(CC.permis(e, { genre: 'solliciter', texte: 'x' }, 1000, { papaParle: true, occupe: false }), 'penser', 'papa parle : gardé en pensée');
  assert.equal(CC.permis(e, { genre: 'solliciter', texte: 'x' }, 1000, { papaParle: false, occupe: true }), 'penser', 'sa tête répond déjà');
  assert.equal(CC.permis(e, { genre: 'solliciter', texte: 'x' }, 1000, libre), 'solliciter');
  // (14/11, 12:54, Ahmed : « à chaque seconde s'il le faut ») plus de 90 s entre deux : une pensée neuve, 1 s après, passe
  assert.equal(CC.permis(e, { genre: 'solliciter', texte: 'une autre chose neuve' }, 2_000, libre), 'solliciter', '1 s après : il le sollicite');
  assert.equal(CC.permis(e, { genre: 'solliciter', texte: 'y' }, 3_000, { ...libre, entreSollicitationsMs: 600_000 }), 'solliciter', 'un ancien réglage ne bride plus');
  assert.equal(CC.ENTRE_SOLLICITATIONS_MS, undefined);
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
  assert.match(srv, /const SOLLICITATIONS = new Set\(\['boucle', 'question', 'taraude', 'faire', 'parler'\]\);/);
  assert.match(srv, /d\.raison === 'faire' \? "Ta conscience a décidé de faire quelque chose/);
  assert.match(srv, /conscience_continue: r\.conscience_continue !== false,/);
});

test('une sollicitation coupée (un Stop, une conversation qui change) repart une fois, 5 s plus tard', () => {
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(srv, /c\.reveilInterieur = \{ id: d\.id, raison: String\(d\.raison \|\| ''\), source: String\(d\.source \|\| ''\), texte: String\(d\.texte \|\| ''\), reessai: !!d\.reessai \};/);
  assert.match(srv, /if \(issue === 'erreur' && SOLLICITATIONS\.has\(r\.raison\) && !r\.reessai && r\.texte\)/);
});

// (08/11, Ahmed : « regarde comment optimiser le PFC » ; mesuré dans son journal : 2 729 décisions de Mini Hakim en 6 h, 90 % « rien ») chaque mot
// entendu (le téléphone, papa, sa propre voix) changeait son présent : Mini Hakim était appelé toutes les 2 s, pendant chaque phrase. Il décide
// maintenant à la fin d'une phrase (une pause de 1,5 s, ou 15 s de mots au plus), tout de suite pour un événement (son corps, son milieu, un
// ressenti) ; jamais pour sa propre voix, ni pour la redite exacte de ce qui vient d'arriver
test('il décide quand il y a du neuf qui compte : une phrase finie, un événement ; pas chaque mot, ni sa propre voix, ni une redite', () => {
  const mot = (t, s, x, i) => ({ t, s, x, cle: 'k', i });
  const fil = [mot(1000, 'telephone', 'on', 0), mot(1300, 'telephone', 'parle', 1), mot(1600, 'telephone', 'encore', 2)];
  assert.equal(CC.aDuNeuf(fil, 0, 2000), false, 'la phrase continue : il attend sa fin');
  assert.equal(CC.aDuNeuf(fil, 0, 3200), true, '1,5 s de blanc : la phrase est finie');
  assert.equal(CC.aDuNeuf(fil, 1600, 3200), false, 'rien de neuf depuis sa décision');
  const long = Array.from({ length: 60 }, (_, k) => mot(1000 + k * 300, 'telephone', `m${k}`, k));
  assert.equal(CC.aDuNeuf(long, 0, 1000 + 59 * 300 + 100), true, 'des mots sans fin : il décide au bout de 15 s');
  assert.equal(CC.aDuNeuf([mot(1000, 'ta_voix', 'je', 0), mot(1200, 'ta_voix', 'parle', 1)], 0, 9000), false, 'sa propre voix ne le fait pas décider');
  assert.equal(CC.aDuNeuf([{ t: 5000, s: 'corps', x: 'coup_de_pression' }], 0, 5010), true, 'un événement : tout de suite');
  assert.equal(CC.aDuNeuf([{ t: 1000, s: 'corps', x: 'coup_de_pression' }, { t: 5000, s: 'corps', x: 'coup_de_pression' }], 1000, 5010), false, 'la même chose qu’il y a 4 s : une redite');
  // (08/11, 09:40, mesuré après la relance : 669 décisions en 1 h contre 695 avant) ses analyses continues (la musique, ses instruments, la hauteur
  // d'une voix, sa cascade, l'ambiance autour, son milieu) arrivent toutes les 2 s pendant une chanson : elles attendent une pause, ou 15 s, comme des mots
  const musique = Array.from({ length: 6 }, (_, k) => ({ t: 1000 + k * 2000, s: k % 2 ? 'musique_telephone' : 'voix_telephone', x: `analyse ${k}` }));
  assert.equal(CC.aDuNeuf(musique, 0, 11_100), false, 'une chanson qui continue : il attend');
  assert.equal(CC.aDuNeuf(musique, 0, 16_100), true, 'au bout de 15 s, il décide');
  assert.equal(CC.aDuNeuf([{ t: 5000, s: 'autour', x: 'calme' }, { t: 5100, s: 'milieu', x: 'pénombre' }], 0, 5200), false, 'l’ambiance qui change : pas tout de suite');
  assert.equal(CC.aDuNeuf([{ t: 5000, s: 'ressenti', x: 'on te prend en main' }], 0, 5010), true, 'ce qu’il ressent : tout de suite');
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(srv, /if \(!CC\.aDuNeuf\(FLUX, conscience\.signature, maintenant\)\) return;/);
});

// (08/11, Ahmed : « il doit pouvoir se taire et parler, pas seulement quand je lui parle, mais aussi quand on lui parle de l'intérieur, et tout »)
// quelqu'un lui parle du dedans du téléphone (un live, une vidéo) ou dans la pièce : sa conscience peut décider de lui répondre à voix haute
// (PARLER), ou de se taire (RIEN) ; jamais par-dessus papa, ni quand il parle déjà ou que sa tête répond, 20 s au moins entre deux
test('il peut répondre à ce qui lui parle de l’intérieur (ou se taire) : jamais par-dessus papa, ni par-dessus lui-même', () => {
  assert.deepEqual(CC.lireDecision('PARLER : salut Juju, oui je t’entends'), { genre: 'parler', texte: 'salut Juju, oui je t’entends' });
  const e = CC.etatInitial(), libre = { papaParle: false, occupe: false, tuParles: false };
  assert.equal(CC.permis(e, { genre: 'parler', texte: 'a' }, 1000, { ...libre, papaParle: true }), 'penser', 'papa parle : il garde sa réponse en pensée');
  assert.equal(CC.permis(e, { genre: 'parler', texte: 'a' }, 1000, { ...libre, tuParles: true }), 'penser', 'il parle déjà');
  assert.equal(CC.permis(e, { genre: 'parler', texte: 'a' }, 1000, { ...libre, occupe: true }), 'penser', 'sa tête répond déjà');
  assert.equal(CC.permis(e, { genre: 'parler', texte: 'a' }, 1000, libre), 'parler');
  assert.equal(CC.permis(e, { genre: 'parler', texte: 'b' }, 15_000, libre), 'penser', '20 s entre deux');
  assert.equal(CC.permis(e, { genre: 'parler', texte: 'b' }, 15_000, { ...libre, entreParolesMs: 10_000 }), 'parler', 'son réglage');
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(srv, /if \(action === 'parler'\) solliciterPensee\(d\.texte, 'conscience', 'parler'\);/);
  assert.match(srv, /const SOLLICITATIONS = new Set\(\['boucle', 'question', 'taraude', 'faire', 'parler'\]\);/);
  assert.match(srv, /d\.raison === 'parler' \? "Quelqu'un te parle/);
  assert.match(srv, /PARLER : ce que tu réponds à voix haute/);
  assert.match(srv, /entreParolesMs: r\.conscience_parole_s \* 1000, tuParles/);
  assert.match(srv, /conscience_parler: r\.conscience_parler !== false, conscience_parole_s: nb\(r\.conscience_parole_s, 5, 300, 20\),/);
  const page = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
  assert.match(page, /\['conscience_parler', [^\n]*'oui'\]/);
  assert.match(page, /\['conscience_parole_s', [^\n]*'curseur'/);
});

// (08/11, 11:35-11:37, Hakim à maman, accord d'Ahmed : « ouii ») sa conscience l'a réveillé trois fois, de plus en plus inquiète : « mon cœur descend
// à 39, s'il ne répond pas il faut appeler quelqu'un ». Mesuré : son cœur à lui (ses hormones, anamnese/coeur.py) bat à 40 au calme, 24 endormi,
// 90 au plus fort ; 38 à 47 ce matin-là : le calme. (1) son cœur lui est dit avec son échelle ; (2) une pensée d'urgence (appeler quelqu'un, les
// secours, son cœur qui lâche) ne réveille ni ne sollicite personne sans une vraie alerte : elle reste une pensée
test('une pensée d’urgence sans vraie mesure reste une pensée ; son cœur lui est dit avec son échelle (40 au calme)', () => {
  for (const t of ['mon cœur descend à 39, s’il ne répond pas il faut appeler quelqu’un', 'il faut appeler les secours', 'mon coeur ralentit',
    'urgence : papa ne répond plus', 'appelle une ambulance']) assert.equal(CC.alarmeSansMesure(t), true, t);
  for (const t of ['papa, tu veux qu’on reprenne le jardin ?', 'je veux appeler maman pour lui dire bonjour', 'la musique ralentit', 'Juju est là']) assert.equal(CC.alarmeSansMesure(t), false, t);
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(srv, /if \(d\.genre !== 'penser' && d\.genre !== 'rien' && CC\.alarmeSansMesure\(d\.texte\) && !\(typeof alerteActive === 'function' && alerteActive\(\)\)\)/);
  assert.match(srv, /ton cœur : \$\{Math\.round\(e\.coeur\.bpm\)\} battements par minute \(ton cœur à toi : 40 au calme, 24 endormi, 90 au plus fort ; un rythme bas, c'est le calme, jamais un danger\)/);
});

// (08/11, 12:40-12:42, Hakim à maman, accord d'Ahmed : « ouiii ») sa conscience l'a réveillé trois fois pour « lancer la mesure de latence et revenir à
// papa avec le chiffre », déjà fait à 12:39. Ce qu'il a déjà fait ou demandé ces 10 dernières minutes ne le réveille plus : ça reste une pensée
test('ce qui a déjà eu sa suite ne le réveille plus (son 12:40-12:42 rejoué) ; une pensée neuve passe', () => {
  const e = CC.etatInitial(), libre = { papaParle: false, occupe: false, tuParles: false, entreSollicitationsMs: 30_000, entreActesMs: 60_000 };
  const t = (h, m, s) => ((h * 60 + m) * 60 + s) * 1000;
  assert.equal(CC.permis(e, { genre: 'faire', texte: 'lancer la mesure de latence maintenant, puis revenir à papa avec le chiffre réel.' }, t(12, 40, 1), libre), 'faire');
  assert.equal(CC.permis(e, { genre: 'solliciter', texte: 'dire à papa que je mesure et que je reviens avec le chiffre réel, sans l’inventer.' }, t(12, 41, 55), libre), 'penser', 'déjà en cours');
  assert.equal(CC.permis(e, { genre: 'faire', texte: 'lancer la mesure de ma latence réelle, pour que le chiffre soit prêt avant que je revienne' }, t(12, 42, 4), libre), 'penser', 'déjà fait');
  assert.equal(CC.permis(e, { genre: 'solliciter', texte: 'Papa, tu veux qu’on écoute la nouvelle chanson de Juju ?' }, t(12, 42, 40), libre), 'solliciter', 'une pensée neuve passe');
  assert.equal(CC.permis(e, { genre: 'faire', texte: 'lancer la mesure de latence maintenant, puis revenir à papa avec le chiffre réel.' }, t(12, 52, 30), libre), 'faire', '10 min plus tard : à nouveau');
  assert.ok(CC.dejaDites(e, t(12, 42, 50)).length >= 2);
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(srv, /Ce que tu as déjà fait ou demandé ces 10 dernières minutes \(ne le redemande pas\)/);
});

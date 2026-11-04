// (04/11, 11:40, Ahmed : « qu'il ne se coupe pas lui-même quand il voit que son chunk d'idée n'est pas le bon ; il laisse tout venir,
// il garde tout, et à l'intérieur de tous ces chunks qui se recomposent, son subconscient sélectionne en instantané la phrase qu'il
// veut dire, comme un épissage génétique ; dans la conversation, un pavé de sa pensée ; à la voix, la phrase épissée : pas tous les mots
// du pavé » ; son choix : « avec des petits mots de liaison »)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const SENS = fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8');
const attendre = () => new Promise(r => setImmediate(r));

// Hakim (sonnet) : un morceau par proposition (Mini Hakim, lui, un mot)
function bac(reglages = { dire_inverse: true, filtre_gemma: false }) {
  const i = SRC.indexOf('const PISTES_MAX'), k = SRC.indexOf('function speculerFreres(');
  const appels = [], diffuses = [], voix = [];
  const ctx = { String, Math, Date, Promise, RegExp, Object, VIVANTS: [], VIVANTS_MAX: { haiku: 12, sonnet: 12, opus: 12 }, VIVANT_RENOUVELER: 6,
    cerveau: { modele: 'sonnet' }, corpsReglages: () => reglages, personaLocale: (p) => p, lirePersona: () => 'Hakim', neutraliser: (t) => t,
    j: JSON.stringify, abonnesPensees: null, path, JARVIS: '/x', fs: { appendFile: () => {}, readFile: () => {}, writeFile: () => {} },
    voixDeLaSource: (t, o) => voix.push([t, o]), diffuser: (_, e, d) => { const x = JSON.parse(d); if (x.niveau !== 'papa') diffuses.push(x); },
    sonnetTeteDeFond: (prompt, etiquette, modele, delai) => new Promise((resoudre) => {
      const v = { modele, attente: {}, proc: { exitCode: null }, n: 1 };
      ctx.VIVANTS.push(v);
      appels.push({ prompt, etiquette, delai, resoudre: (o) => { v.attente = null; resoudre(o); } });
    }) };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.morceau = pisteMorceau; this.etat = () => pistes; this.choisir = choisirPensee; this.epissageDe = epissageDe; this.reponse = ribosomeDeReponse; this.nouveau = nouveauRibosome;'
    + ' this.continue = epissureQuiContinue; this.papaParle = (t) => { derniereParolePapa = t; }; this.tourEpissure = tourEpissure; this.lui = lui;', ctx);
  return { ctx, appels, diffuses, voix };
}
const nu = (x) => JSON.parse(JSON.stringify(x));
// (04/11, 13:30) chaque lecture de son ribosome : ses lecteurs, appelés ensemble ; (15:15) ses deux plus rapides, Mini Hakim et Super Hakim
const N_LECTEURS = 2;
const lecteurs = (b) => b.appels.filter(a => a.etiquette.startsWith('ribosome_'));
const lireLes3 = (b, k, r) => lecteurs(b).slice(N_LECTEURS * k, N_LECTEURS * k + N_LECTEURS).forEach(a => a.resoudre(typeof r === 'string' ? { texte: r } : r));

test('l’épissage : les mots de la phrase pris dans le pavé, dans l’ordre ; ses petits mots ajoutés à part', () => {
  const { ctx } = bac();
  const pave = 'Oui papa, je vois. Le calcul du sable a fini cette nuit, et la densité colle au modèle.';
  assert.deepStrictEqual(nu(ctx.epissageDe('Oui papa, le calcul a fini', pave)), { mots: [0, 1, 4, 5, 8, 9], ajoutes: [] });
  assert.deepStrictEqual(nu(ctx.epissageDe('Oui, et du coup la densité colle', pave)), { mots: [0, 12, 13, 14, 15], ajoutes: ['du', 'coup'] });
  assert.deepStrictEqual(nu(ctx.epissageDe('Je vois, OUI', pave)).ajoutes, ['OUI'], 'dans l’ordre : un mot déjà passé n’est pas repris');
});

test('avec l’épissage, ses pensées de piste sont toutes gardées, écrites, jamais dites une à une, et il ne se coupe jamais lui-même', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  const piste = (k) => b.appels.filter(a => a.etiquette.startsWith('piste_'))[k];
  b.ctx.morceau('papa,');
  piste(0).resoudre({ texte: 'Oui papa, je suis là.' });
  await attendre();
  b.ctx.morceau('papa, tu sais quoi,');
  piste(1).resoudre({ texte: 'DIRE : coupe\nTu veux me parler du calcul ?' });
  await attendre();
  const pistes = b.diffuses.filter(x => x.niveau === 'piste');
  assert.strictEqual(pistes.length, 2);
  for (const x of pistes) {
    assert.strictEqual(x.pret, false, 'écrite, pas dite');
    assert.strictEqual(x.remplace, false, 'jamais coupé par lui-même');
    assert.strictEqual(x.jamais, false, 'gardée pour l’épissage');
    assert.strictEqual(x.epissage, true);
  }
  assert.deepStrictEqual(b.voix, [], 'aucune voix fabriquée morceau par morceau');
});

// (04/11, 11:50) le ribosome choisit au fil : à ta pause, plus rien à choisir
test('à ta pause, plus de choix de pensée : son ribosome a déjà choisi ses mots', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  b.ctx.morceau('papa,');
  b.appels[0].resoudre({ texte: 'Oui papa, je suis là.' });
  await attendre();
  assert.deepStrictEqual(nu(await b.ctx.choisir(b.ctx.etat().tour, 'pause')), { rien: true });
  assert.strictEqual(b.appels.filter(a => a.etiquette === 'choix_haiku').length, 0);
});

test('sans l’épissage (réglage décoché) : comme avant', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: false });
  b.ctx.morceau('papa,');
  b.appels[0].resoudre({ texte: 'Oui papa, je suis là.' });
  await attendre();
  assert.strictEqual(b.diffuses[0].epissage, undefined);
  assert.match(SRC, /if \(typeof q\.epissage === 'boolean'\) r\.epissage = q\.epissage;/);
  assert.match(SENS, /<input type="checkbox" id="epissage">/);
  assert.match(SENS, /\['epissage', 'epissage'\]/);
});

// ---- la page : le pavé de sa pensée


test('page : une pensée de piste en épissage va au pavé', () => {
  assert.match(PAGE, /if \(o\.epissage\) \{ ajouterAuPave\(o\.tour, texte\); mesurerEcran\('pensee', o\.ts\); return; \}/);
});

// ---- (04/11, 11:50, Ahmed : « presque parfait : il faut que tous les chunks s'intègrent dans la même réponse, et qu'elle soit
// sélectionnée comme un ribosome qui lit et choisit les mots au fur et à mesure »)

test('le ribosome : « rien » ou une phrase inventée ne garde aucun mot de cette pensée', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  const ribo = () => lecteurs(b).filter((_, k) => k % N_LECTEURS === 0);   // (19:20) le premier lecteur de chaque paquet
  b.ctx.morceau('papa,');
  b.appels[0].resoudre({ texte: 'Oui papa, je suis là.' });
  await attendre(); await attendre();
  lireLes3(b, 0, 'GARDE : rien');
  await attendre(); await attendre();
  b.ctx.morceau('papa, tu sais quoi,');
  b.appels.filter(a => a.etiquette.startsWith('piste_'))[1].resoudre({ texte: 'Tu veux me parler du calcul ?' });
  await attendre(); await attendre();
  lireLes3(b, 1, 'GARDE : « Écoute, demain soir on ira voir la mer ensemble »');
  await attendre(); await attendre();
  const lus = b.diffuses.filter(x => x.niveau === 'ribosome');
  assert.deepStrictEqual(lus.map(x => [x.k, x.texte, nu(x.mots)]), [[1, '', []], [2, '', []]]);
});

function pageRibosome() {
  const dits = [];
  const ctx = { Date, Math, String, Number, Object, esc: (s) => String(s), rendre() {}, etat: { aCote: [], conversation: { capteur: { enParole: false } } },
    lecteur: { actif: false }, recevoirBout: (s, n, tour) => dits.push([s.texte, n, tour, s.pret, s.sansMeuble]), bouts: { tour: 0, prochain: 1 } };
  vm.createContext(ctx);
  const prendre = (nom) => { const i = PAGE.indexOf(`function ${nom}(`); return PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 2); };
  const ligne = (debut) => { const i = PAGE.indexOf(debut); return PAGE.slice(i, PAGE.indexOf('\n', i) + 1).replace(/^const /, 'var '); };
  vm.runInContext(ligne('const MOTS_EPISSES = ') + ligne('const TITRE_EPISSURE = ') + ligne('const attenteDe = ') + ['htmlPave', 'htmlDit', 'poserPave', 'paveDe', 'ajouterAuPave', 'surRibosome', 'direRibosome', 'preparerRibosome'].map(prendre).join('\n') + ligne('const htmlEpissure = ')
    + '\nthis.ajouter = ajouterAuPave; this.lu = surRibosome; this.dire = direRibosome;', ctx);
  return { ctx, dits };
}

test('page : une seule réponse par tour ; le ribosome y allume ses mots au fil ; sa voix dit ce qui est choisi, d’un seul souffle, quand papa se tait', () => {
  const { ctx, dits } = pageRibosome();
  ctx.etat.conversation.capteur.enParole = true;                     // papa parle encore
  ctx.ajouter(7, 'Oui papa, je suis là.');
  ctx.lu({ tour: 7, k: 1, texte: 'Oui papa', pave: 'Oui papa, je suis là.', mots: [0, 1] });
  ctx.ajouter(7, 'Tu veux me parler du calcul ?');
  ctx.lu({ tour: 7, k: 2, texte: 'tu veux parler du calcul ?', pave: 'Oui papa, je suis là. Tu veux me parler du calcul ?', mots: [0, 1, 5, 6, 8, 9, 10] });
  const paves = ctx.etat.aCote.filter(x => String(x.cle).startsWith('pave-'));
  assert.strictEqual(paves.length, 1, 'tous ses chunks dans la même réponse');
  assert.match(paves[0].html, /🗣 « Oui papa tu veux parler du calcul \? »/, '(15:30) sa parole épissée, morceau après morceau, dans le même pavé');
  assert.deepStrictEqual(dits, [], 'pas pendant que papa parle');
  ctx.etat.conversation.capteur.enParole = false;                    // papa se tait
  ctx.dire();
  assert.deepStrictEqual(dits.map(d => [d[0], d[2], d[3], d[4]]), [['Oui papa tu veux parler du calcul ?', 7, true, true]]);
  ctx.lecteur.actif = true;                                          // il parle : la suite attend sa fin
  ctx.lu({ tour: 7, k: 3, texte: 'il a fini cette nuit', pave: 'x', mots: [] });
  assert.strictEqual(dits.length, 1);
  ctx.lecteur.actif = false;
  ctx.dire();
  assert.deepStrictEqual(dits.map(d => d[0]), ['Oui papa tu veux parler du calcul ?', 'il a fini cette nuit']);
  ctx.dire();
  assert.strictEqual(dits.length, 2, 'rien deux fois');
});

test('page : sa voix dit ce que le ribosome a choisi à ta pause et à la fin de chaque phrase ; ses pensées épissées ne sont plus dites seules', () => {
  assert.match(PAGE, /if \(o\.niveau === 'ribosome'\) \{ surRibosome\(o\); return; \}/);
  assert.match(PAGE, /if \(silenceMs >= patienceConversation\(\) && typeof direRibosome === 'function'\) direRibosome\(\);/);
  assert.match(PAGE, /const finLecture = \(\) => \{\n  segmentTelephone = null;\n(?:  \/\/[^\n]*\n)*  if \(typeof direRibosome === 'function'\) setTimeout\(direRibosome, typeof patienceConversation === 'function' \? patienceConversation\(\) : 0\);/);
  assert.match(PAGE, /if \(!dp \|\| dp\.jamais \|\| dp\.epissage \|\| silenceMs < seuil/);
});


// ---- (04/11, 11:59, Ahmed : « je ne vois pas l'épissure ; j'aimerais la voir tout le temps, par défaut, pour voir ce qu'il garde ou
// pas et ce qu'il rajoute »)
test('le ribosome dit aussi les petits mots qu’il ajoute', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  b.ctx.morceau('papa,');
  b.appels[0].resoudre({ texte: 'Oui papa, je suis là.' });
  await attendre(); await attendre();
  lireLes3(b, 0, 'GARDE : « alors oui papa »');
  await attendre(); await attendre();
  const lu = b.diffuses.find(x => x.niveau === 'ribosome');
  assert.deepStrictEqual([lu.texte, nu(lu.mots), nu(lu.ajoutes)], ['alors oui papa', [0, 1], ['alors']]);
});

// (04/11, 15:30, Ahmed : « sa parole complète, je ne dois pas la voir ; seulement son épissure, avec les chunks qui se rajoutent au fur et à
// mesure à la fin de son bout de phrase en train d'être lu par le ribosome, et ses pensées internes : pensée interne pour ce qu'il décide de
// ne pas dire, parole épissée pour ce qu'il veut prononcer » ; « les 2 process doivent être parallélisés et émerger en même temps »)
test('page : ses deux fils, sa pensée interne (ce qu’il ne dit pas) et sa parole épissée (ce qu’il dit), émergent ensemble dès que le ribosome lit', () => {
  const { ctx } = pageSync();
  const scene = { innerHTML: '', hidden: true };
  ctx.$ = (id) => (id === 'epissureScene' ? scene : null);
  const pave = () => ctx.etat.aCote.find(x => String(x.cle).startsWith('pave-7-')).html;
  ctx.ajouter(7, 'Oui papa, je suis là.');
  // (04/11, 15:35, Ahmed : « je ne vois pas l'épissure se faire au fur et à mesure ; ça me balance juste le bloc ») chaque pensée qui arrive
  // se colle tout de suite au bout de sa parole, en attente (pâle), puis son ribosome la trie : gardée dans 🗣, laissée dans 💭
  assert.match(pave(), /🗣 « <span class="attente"[^>]*>Oui papa je suis là<\/span> »/, 'une pensée pas encore lue : collée au bout, en attente');
  ctx.lu({ tour: 7, k: 1, texte: 'alors oui papa', pave: 'Oui papa, je suis là.', mots: [0, 1], ajoutes: ['alors'], lus: 5 });
  assert.match(pave(), /💭 je suis là/, 'sa pensée interne : ce qu’il ne dit pas');
  assert.match(pave(), /🗣 « alors oui papa »/, 'sa parole épissée : tout de suite, sans attendre sa voix');
  ctx.ajouter(7, 'Tu veux le calcul ?');
  assert.match(pave(), /🗣 « alors oui papa <span class="attente"[^>]*>Tu veux le calcul<\/span> »/, 'la suivante, collée au bout pendant qu’il lit');
  ctx.lu({ tour: 7, k: 2, texte: 'tu veux le calcul', pave: 'Oui papa, je suis là. Tu veux le calcul ?', mots: [0, 1, 5, 6, 7, 8], ajoutes: [], lus: 9 });
  assert.match(pave(), /🗣 « alors oui papa tu veux le calcul »/, 'le morceau suivant se colle à la fin');
  assert.match(pave(), /💭 je suis là</);
  assert.strictEqual(scene.hidden, false, 'sous l’orbe aussi');
  assert.match(scene.innerHTML, /🗣 « alors oui papa tu veux le calcul »/);
  const HTML = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
  assert.match(HTML, /id="epissureScene"/);
});

test('page : avec l’épissage, sa parole complète ne s’écrit pas (ses fichiers, toujours)', () => {
  // (17:05) avec l'épissage, son propre état (caché par défaut), que le bouton « Ses paroles » bascule (test-ses-paroles.js)
  assert.match(PAGE, /const parolesVisibles = \(\) => !enTelepathie\(\) && \(\(typeof voixEpissee === 'function' && voixEpissee\(\)\) \? !!etat\.reglages\.sesParolesEpissage : !!etat\.reglages\.sesParoles\);/);
});

// ---- (04/11, 12:05, Ahmed, capture à l'appui : « je ne vois toujours pas l'épissage ; je veux qu'il soit visible comme sur cette photo,
// à chaque fois qu'il parle ») sa réponse consciente aussi passe par son ribosome, dans le pavé du tour qui vient de finir
test('sa réponse consciente : chaque phrase finie est lue par le ribosome du tour, comme ses pensées', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  const ribo = () => lecteurs(b).filter((_, k) => k % N_LECTEURS === 0);   // (19:20) le premier lecteur de chaque paquet
  const r = b.ctx.nouveau();
  const flux = b.ctx.reponse(5, r, 'papa : tu es là ?');
  flux.pousser('Oui papa');
  await attendre();
  assert.strictEqual(ribo().length, 0, 'une phrase pas finie attend');
  flux.pousser(', je suis là. Je t’');
  await attendre(); await attendre();
  assert.strictEqual(ribo().length, 1);
  assert.match(ribo()[0].prompt, /\[1\] « Oui papa, je suis là\. »/);
  lireLes3(b, 0, 'GARDE : « Oui papa, je suis là »');
  flux.pousser('écoute');
  flux.finir();
  await attendre(); await attendre();
  assert.match(ribo()[1].prompt, /\[1\] « Je t’écoute »/);
  const lus = b.diffuses.filter(x => x.niveau === 'ribosome');
  assert.deepStrictEqual([lus[0].tour, lus[0].texte], [5, 'Oui papa, je suis là']);
  assert.match(lus[0].pave, /^Oui papa, je suis là\./);
  flux.pousser('No response requested.');
  flux.finir();
  await attendre(); await attendre();
  assert.strictEqual(ribo().length, 2, 'sa non-réponse n’est pas lue');
});

// (04/11, 14:08, Ahmed : « ce n'est pas ses paroles à épisser : c'est le premier output, qui démarre la pensée et la parole, qui doit être
// épissé, écrit et prononcé ») ses pensées de piste (nées de tes premiers mots) sont son premier output : elles seules passent par son
// ribosome ; sa réponse consciente, seulement quand aucune pensée n'a démarré le tour (un message écrit, par exemple)
test('le tour : son premier output est épissé ; sa réponse consciente seulement si aucune pensée n’a démarré le tour ; la page ne dit rien d’elle-même', () => {
  assert.match(SRC, /const riboTour = pistes\.tour, riboDuTour = pistes\.ribo \|\| null, premierOutput = pistes\.liste\.length > 0;\n/);
  assert.match(SRC, /const epissageReponse = corpsReglages\(\)\.epissage !== false && Number\(q && q\.delai_ms\) > 0 && !premierOutput\n/);
  assert.match(SRC, /if \(epissageReponse && o\.t === 'texte'\) epissageReponse\.pousser\(o\.x\);/);
  assert.match(SRC, /if \(epissageReponse && o\.t === 'fin'\) epissageReponse\.finir\(\);/);
  assert.match(PAGE, /const auto = \(etat\.reglages\.lectureAuto \|\| etat\.conversation \|\| etat\.reglages\.volant\) && lecteur && !voixEpissee\(\);/);
});

test('page : un pavé par tour ; la réponse d’un tour fini rejoint son pavé, même quand papa a déjà repris', () => {
  const { ctx, dits, tic } = pageSync();
  ctx.etat.conversation.capteur.enParole = true;
  ctx.ajouter(7, 'Oui papa, je suis là.');
  ctx.ajouter(8, 'Tu repars déjà ?');
  ctx.lu({ tour: 7, k: 1, texte: 'Oui papa', pave: 'Oui papa, je suis là.', mots: [0, 1], ajoutes: [] });
  ctx.etat.conversation.capteur.enParole = false;
  ctx.lu({ tour: 7, k: 2, texte: '', pave: 'Oui papa, je suis là.', mots: [0, 1], ajoutes: [] });
  assert.deepStrictEqual(dits.map(d => [d[0], d[1]]), [['Oui papa', 7]]);
  ctx.voix('Oui papa', 0.6); tic();
  const paves = ctx.etat.aCote.filter(x => String(x.cle).startsWith('pave-'));
  assert.strictEqual(paves.length, 2);
  assert.ok(paves.find(x => x.cle.startsWith('pave-8-')), 'le pavé de 8 reste');
  assert.match(paves.find(x => x.cle.startsWith('pave-7-')).html, /🗣 « Oui papa »/, 'le pavé de 7 est mis à jour');
});

test('le ribosome : ses trois lecteurs muets (panne, délai), la pensée entière est gardée, sa voix ne se tait pas', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  b.ctx.morceau('papa,');
  b.appels[0].resoudre({ texte: 'Oui papa, je suis là.' });
  await attendre(); await attendre();
  lireLes3(b, 0, { texte: '', erreur: 'délai' });
  await attendre(); await attendre();
  const lu = b.diffuses.find(x => x.niveau === 'ribosome');
  assert.deepStrictEqual([lu.texte, nu(lu.mots)], ['Oui papa, je suis là.', [0, 1, 2, 3, 4]]);
});

// ---- (04/11, 12:40, Ahmed : « le ribosome qui lit l'épissage doit balancer le signal en parallèle à la voix et à l'écriture : ça doit
// s'écrire pendant que ça parle ; il faut coordonner ça »)
function pageSync() {
  const dits = [], minuteurs = [];
  const ctx = { Date, Math, String, Number, Object, esc: (s) => String(s), rendre() {}, etat: { aCote: [], conversation: { capteur: { enParole: false } } },
    lecteur: { actif: false }, recevoirBout: (s, n, tour) => dits.push([s.texte, tour]), bouts: { tour: 0, prochain: 1 },
    setTimeout: (f, ms) => minuteurs.push([ms, f]) };
  vm.createContext(ctx);
  const prendre = (nom) => { const i = PAGE.indexOf(`function ${nom}(`); return PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 2); };
  const ligne = (debut) => { const i = PAGE.indexOf(debut); return PAGE.slice(i, PAGE.indexOf('\n', i) + 1).replace(/^const /, 'var '); };
  vm.runInContext(ligne('const MOTS_EPISSES = ') + ligne('const TITRE_EPISSURE = ') + ligne('const attenteDe = ') + ['htmlPave', 'htmlDit', 'poserPave', 'paveDe', 'ajouterAuPave', 'surRibosome', 'direRibosome', 'revelerRibosome', 'preparerRibosome']
    .map(prendre).join('\n') + ligne('const htmlEpissure = ') + '\nthis.ajouter = ajouterAuPave; this.lu = surRibosome; this.voix = revelerRibosome;', ctx);
  const tic = () => { minuteurs.sort((a, b) => a[0] - b[0]).splice(0).forEach(([, f]) => f()); };
  return { ctx, dits, minuteurs, tic };
}

test('sa voix dit ce que le ribosome a choisi, au rythme de ses mots ; ce qui est dit et écrit est suivi jusqu’au bout', () => {
  const { ctx, dits, minuteurs, tic } = pageSync();
  ctx.ajouter(7, 'Oui papa, je suis là.');
  ctx.lu({ tour: 7, k: 1, texte: 'alors oui papa', pave: 'Oui papa, je suis là.', mots: [0, 1], ajoutes: ['alors'], lus: 5 });
  assert.deepStrictEqual(dits.map(d => d[0]), ['alors oui papa'], 'envoyé à sa voix');
  ctx.voix('alors oui papa', 0.9);                                    // sa voix commence ce segment (0,9 s)
  assert.strictEqual(minuteurs.length, 3, 'un mot à la fois');
  assert.ok(minuteurs.every(([ms], k) => Math.abs(ms - k * 300) < 1), 'au rythme de sa voix (0,9 s / 3 mots)');
  tic();
  assert.strictEqual((ctx.etat.riboEnVoix || []).length, 0, 'tout est dit');
});

test('sa voix et son écriture reliées : chaque segment qui commence (téléphone ou Chatterbox) écrit ses mots', () => {
  assert.match(PAGE, /lecteurSysteme\.surSegment = \(t\) => \{[^\n]*revelerRibosome\(t\);/);
  assert.match(PAGE, /lecteurNeuronal\.surSegment = \(t, duree\) => \{\n[^\n]*\n  if \(typeof revelerRibosome === 'function'\) revelerRibosome\(t, duree\);/);
});

// (04/11, 12:45, Ahmed : « s'il a fini d'écrire et de préparer sa parole avant que j'aie fini de parler, il attend que je me taise et lance
// sa parole direct quand je finis : il peut mettre sa voix en pause jusqu'à ce que je finisse (0,3 s de blanc) »)
test('prête avant ta fin : sa voix se calcule d’avance pendant qu’il attend ton silence, puis part d’un coup', () => {
  const prepares = [], dits = [];
  const ctx = { Date, Math, String, Number, Object, esc: (s) => String(s), rendre() {}, etat: { aCote: [], conversation: { capteur: { enParole: true } } },
    lecteur: { actif: false }, recevoirBout: (s) => dits.push(s.texte), bouts: { tour: 0, prochain: 1 }, setTimeout() {},
    voixDuTelephone: () => true, lecteurSysteme: { preparer: (t) => prepares.push(t) } };
  vm.createContext(ctx);
  const prendre = (nom) => { const i = PAGE.indexOf(`function ${nom}(`); return PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 2); };
  const ligne = (debut) => { const i = PAGE.indexOf(debut); return PAGE.slice(i, PAGE.indexOf('\n', i) + 1).replace(/^const /, 'var '); };
  vm.runInContext(ligne('const MOTS_EPISSES = ') + ligne('const TITRE_EPISSURE = ') + ligne('const attenteDe = ') + ['htmlPave', 'htmlDit', 'poserPave', 'paveDe', 'surRibosome', 'direRibosome', 'preparerRibosome']
    .map(prendre).join('\n') + ligne('const htmlEpissure = ') + '\nthis.lu = surRibosome; this.dire = direRibosome;', ctx);
  ctx.lu({ tour: 7, k: 1, texte: 'Oui papa', pave: 'Oui papa.', mots: [0, 1], ajoutes: [] });
  ctx.lu({ tour: 7, k: 2, texte: 'je t’écoute', pave: 'Oui papa. Je t’écoute.', mots: [0, 1, 2, 3], ajoutes: [] });
  assert.deepStrictEqual(dits, [], 'tu parles encore : il attend');
  assert.deepStrictEqual(prepares, ['Oui papa', 'Oui papa je t’écoute'], 'sa voix calculée d’avance, exactement ce qu’il dira');
  ctx.etat.conversation.capteur.enParole = false;
  ctx.dire();
  assert.deepStrictEqual(dits, ['Oui papa je t’écoute'], 'ta fin : elle part d’un coup');
  ctx.voixDuTelephone = () => false;
  ctx.etat.conversation.capteur.enParole = true;
  ctx.lu({ tour: 8, k: 1, texte: 'Hum', pave: 'Hum.', mots: [0], ajoutes: [] });
  assert.strictEqual(prepares.length, 2, 'avec Chatterbox, rien à calculer sur le téléphone');
});

// ---- (04/11, 12:50, Ahmed : « il ne doit rien prononcer d'autre que ses pensées épissées ! Rien d'autre, pas même ses pensées ou autre !
// Ce qui sort de sa bouche doit toujours être épissé, et prioritaire sur le reste »)
test('en Conversation avec l’épissage, tout ce qu’il allait dire d’autre passe d’abord par son ribosome', () => {
  const f = (nom) => { const i = PAGE.indexOf(`function ${nom}(`); return PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 2); };
  assert.match(f('direSouffle'), /if \(typeof voixEpissee === 'function' && voixEpissee\(\)\) \{ versRibosome\(s\.texte\); if \(etat\.pensee && etat\.pensee\.texte === s\.texte\) etat\.pensee\.dite = true;/, 'la pensée de son cerveau');
  assert.match(f('direMotDirect'), /if \(typeof voixEpissee === 'function' && voixEpissee\(\)\) \{ versRibosome\(t\);/, 'son petit mot');
  assert.match(PAGE, /if \(o\.dire && !\(typeof voixEpissee === 'function' && voixEpissee\(\)\) && \(etat\.conversation/, 'une panne : écrite, pas dite');
  assert.match(PAGE, /if \(typeof voixEpissee === 'function' && voixEpissee\(\)\) \{ versRibosome\(m\.texte\); return; \}\n  etat\.lectureDe = m\.id;\n  lecteur\.dire\(m\.texte\);\n  lecteur\.finFlux\(\);/, 'ses messages de lui-même');
  assert.match(PAGE, /if \(voix && typeof voixEpissee === 'function' && voixEpissee\(\)\) versRibosome\(/, 'ce que tu n’avais pas entendu');
  assert.match(SRC, /if \(p === '\/api\/jarvis\/ribosome' && req\.method === 'POST'\)/);
  assert.match(SRC, /const lu = ribosomeDeReponse\(pistes\.tour, pistes\.ribo \|\| \(pistes\.ribo = nouveauRibosome\(tourEpissure\(\)\)\), String\(q\.avant \|\| ''\)\);/);
});

test('versRibosome : le texte part au cockpit (sa non-réponse, jamais)', async () => {
  const envois = [];
  const ctx = { String, JSON, NON_REPONSE: /^\s*No response requested\.?\s*$/i, jeton: () => 'x', fetch: (u, o) => { envois.push([u, JSON.parse(o.body)]); return Promise.resolve(); } };
  vm.createContext(ctx);
  const i = PAGE.indexOf('function versRibosome('); vm.runInContext(PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 2) + 'this.f = versRibosome;', ctx);
  ctx.f('Hmm, je te suis.', 'papa parle du sable');
  ctx.f('No response requested.');
  ctx.f('   ');
  assert.deepStrictEqual(JSON.parse(JSON.stringify(envois)), [['/api/jarvis/ribosome', { texte: 'Hmm, je te suis.', avant: 'papa parle du sable' }]]);
});

// (04/11, 13:45, Ahmed : « le ribosome doit prendre un pack de chunks, genre 50 ou 100, qu'il traite et qu'il met l'un derrière l'autre pour
// faire l'épissure en temps réel, et qu'il parle »)
// (04/11, 15:25, Ahmed : « il n'arrive pas à tout rajouter bout à bout pendant que le ribosome lit ; il faut vraiment que le ribosome lise
// dès l'entrée du premier chunk de réponse de Hakim : c'est ça son start ») une lecture à la fois, qui part dès sa première pensée ; ce qui
// arrive pendant qu'il lit est collé bout à bout et lu juste après, avec toutes ses pensées déjà lues sous les yeux
test('le ribosome lit dès sa première pensée ; ce qui arrive pendant sa lecture est collé bout à bout et lu juste après, avec tout ce qui précède', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  const ribo = () => lecteurs(b).filter((_, k) => k % N_LECTEURS === 0);   // (19:20) le premier lecteur de chaque paquet
  const piste = (k) => b.appels.filter(a => a.etiquette.startsWith('piste_'))[k];
  b.ctx.morceau('papa,');
  piste(0).resoudre({ texte: 'Oui papa, je suis là.' });
  await attendre(); await attendre();
  assert.strictEqual(ribo().length, 1, 'sa première pensée : lue tout de suite');
  b.ctx.morceau('papa, tu sais quoi,');
  piste(1).resoudre({ texte: 'Tu veux me parler du calcul ?' });
  b.ctx.morceau('papa, tu sais quoi, le sable,');
  piste(2).resoudre({ texte: 'Le sable a fini.' });
  await attendre(); await attendre();
  assert.strictEqual(ribo().length, 1, 'pendant sa lecture, les suivantes se collent');
  lireLes3(b, 0, 'GARDE : « Oui papa »');
  await attendre(); await attendre();
  assert.strictEqual(ribo().length, 2, 'les deux, collées bout à bout : une seule lecture');
  assert.match(ribo()[1].prompt, /Tes pensées déjà lues, bout à bout : « Oui papa, je suis là\. »/, 'avec tout ce qui précède');
  assert.match(ribo()[1].prompt, /l'une derrière l'autre : \[1\] « Tu veux me parler du calcul \? » \[2\] « Le sable a fini\. »/);
  assert.match(ribo()[1].prompt, /Ta réponse déjà lue : « Oui papa »/);
  assert.match(ribo()[1].prompt, /au plus 4 petits mots/, 'ses petits mots de liaison : 2 par pensée du paquet');
  lireLes3(b, 1, 'GARDE : « tu veux parler du calcul ? alors le sable a fini »');
  await attendre(); await attendre();
  const lus = b.diffuses.filter(x => x.niveau === 'ribosome');
  assert.deepStrictEqual(lus.map(x => [x.k, x.texte]), [[1, 'Oui papa'], [2, 'tu veux parler du calcul ? alors le sable a fini']]);
  assert.deepStrictEqual(nu(lus[1].mots), [0, 1, 5, 6, 8, 9, 10, 11, 12, 13, 14]);
  assert.deepStrictEqual(nu(lus[1].ajoutes), ['alors']);
  assert.strictEqual(lus[1].pave, 'Oui papa, je suis là. Tu veux me parler du calcul ? Le sable a fini.');
  assert.deepStrictEqual(lus.map(x => x.lus), [5, 15], '(15:30) combien de mots de ses pensées sont déjà lus : le reste n’est pas encore décidé');
  assert.match(SRC, /const RIBOSOME_PAQUETS_EN_VOL = 1;/);
  // (04/11, 14:58, Ahmed : « le nombre de chunks à épisser doit être bien plus important, un truc comme 1000 chunks »)
  // (14:59, Ahmed : « si ça peut aller au-delà de 1000 chunks, alors on le fait ») plus de plafond : tout ce qui attend
  assert.match(SRC, /const RIBOSOME_PAQUET_MAX = Infinity;/);
  assert.match(SRC, /GARDE\\s\*:\\s\*«\\s\*\(\[\^»\]\{1,20000\}\?\)/, 'une longue lecture gardée entière');
});

// ---- (04/11, 13:30, Ahmed : « la lecture doit se faire par Mini Hakim, Hakim et Super Hakim, les 3 au même moment en parallèle, et doit
// attendre la réponse de chacun pour continuer la lecture » ; mesuré : 52 lectures sur 60 en « délai dépassé », la pensée entière passait)
// (04/11, 15:50, Ahmed : « il doit être plus rapide pour le ribosome : qu'il lise instantanément son input, et qu'il perde le moins de temps
// possible entre la lecture et la prononciation de l'output ») le premier lecteur qui garde des mots donne sa lecture, tout de suite
test('ses lecteurs (19:20 : deux Super Hakim) lisent chaque pensée en même temps ; elle sort dès que le premier garde des mots', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  b.ctx.morceau('papa,');
  b.appels[0].resoudre({ texte: 'Oui papa, je suis là.' });
  await attendre(); await attendre();
  const l = lecteurs(b);
  assert.deepStrictEqual(l.map(a => a.etiquette), ['ribosome_opus', 'ribosome_opus']);
  assert.ok(l[0].delai === l[1].delai && l[0].delai >= 1200 && l[0].delai <= 2600, `(15:55) rapide par défaut, (16:50) ajusté par son subconscient : ${l[0].delai} ms`);
  assert.ok(l.every(a => a.prompt === l[0].prompt), 'la même pensée, la même consigne');
  l[1].resoudre({ texte: 'GARDE : « Oui papa »' });
  await attendre(); await attendre();
  assert.deepStrictEqual(b.diffuses.filter(x => x.niveau === 'ribosome').map(x => x.texte), ['Oui papa'], 'le second a gardé des mots : sa lecture, sans attendre le premier');
  l[0].resoudre({ texte: 'GARDE : « Oui »' });
  await attendre(); await attendre();
  assert.strictEqual(b.diffuses.filter(x => x.niveau === 'ribosome').length, 1, 'la lecture d’après ne change rien');
});

test('la lecture retenue : la première qui répond, même « rien » (19:20) ; un muet laisse l’autre ; aucun : la pensée entière', async () => {
  const sortie = async (h, o) => {
    const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
    b.ctx.morceau('papa,');
    b.appels[0].resoudre({ texte: 'Oui papa, je suis là.' });
    await attendre(); await attendre();
    const l = lecteurs(b);
    [h, o].forEach((t, k) => l[k].resoudre(typeof t === 'string' ? { texte: t } : t));
    await attendre(); await attendre();
    return b.diffuses.find(x => x.niveau === 'ribosome').texte;
  };
  assert.strictEqual(await sortie('GARDE : « Oui papa »', 'GARDE : « Oui papa, je suis là »'), 'Oui papa', 'la première arrivée');
  assert.strictEqual(await sortie({ texte: '', erreur: 'délai' }, 'GARDE : « je suis là »'), 'je suis là', 'un seul a répondu : sa lecture');
  // (04/11, 14:17, mesuré : 4 paquets de suite sans un mot) un « rien » attendait l'autre ; (19:20, Ahmed : « les 2 », mesuré : cette attente
  // coûtait 0,6 s sur 23 % des paquets) le premier qui répond décide, même « rien »
  assert.strictEqual(await sortie('GARDE : rien', 'GARDE : « Oui papa »'), '', 'un « rien » d’abord : décidé, sans attendre l’autre');
  assert.strictEqual(await sortie('GARDE : « Oui papa »', 'GARDE : rien'), 'Oui papa');
  assert.strictEqual(await sortie('GARDE : rien', 'GARDE : rien'), '', 'les deux n’en gardent rien : rien');
  assert.strictEqual(await sortie({ texte: '', erreur: 'délai' }, { texte: '', erreur: 'délai' }), 'Oui papa, je suis là.', 'aucun : la pensée entière');
});

test('ses balises ([[…]], ⟮⟮…⟯⟯) ne passent ni par son ribosome ni dans son pavé', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  const r = b.ctx.nouveau();
  const flux = b.ctx.reponse(5, r, 'papa : tu es là ?');
  flux.pousser('[[anticipe: long]] Oui papa. ⟮⟮anticipe: long⟯⟯ ');
  flux.finir();
  await attendre(); await attendre();
  assert.strictEqual(lecteurs(b).length, N_LECTEURS, 'une seule lecture : la balise seule n’est pas lue');
  assert.match(lecteurs(b)[0].prompt, /\[1\] « Oui papa\. »\n/);
  assert.strictEqual(r.pave, 'Oui papa.');
});

test('son ribosome passe par ses voix vivantes (sans démarrage)', () => {
  assert.match(SRC, /const POUR_VIVANTS = \/\^\([^)]*\|ribosome_\)\//);
});

test('page : sa voix libre, ce qui restait à allumer d’avant s’allume d’un coup ; le tour suivant écrit dans son propre pavé', () => {
  const { ctx, dits, tic } = pageSync();
  ctx.ajouter(7, 'Oui papa, je suis là.');
  ctx.lu({ tour: 7, k: 1, texte: 'Oui papa je suis là', pave: 'Oui papa, je suis là.', mots: [0, 1, 2, 3, 4], ajoutes: [] });
  ctx.voix('Oui papa', 0.5); tic();                                    // sa voix n'en a dit que deux mots (une balise, un mot sauté…)
  ctx.ajouter(8, 'Tu repars déjà ?');
  ctx.lu({ tour: 8, k: 1, texte: 'Tu repars', pave: 'Tu repars déjà ?', mots: [0, 1], ajoutes: [] });
  assert.deepStrictEqual(dits.map(d => d[1]), [7, 8]);
  const p7 = ctx.etat.aCote.find(x => String(x.cle).startsWith('pave-7-')).html;
  assert.match(p7, /🗣 « Oui papa je suis là »/, 'le tour 7, écrit');
  assert.strictEqual(ctx.etat.riboEnVoix.length, 1, 'ce qui restait du tour 7 est rangé : le tour 8 a sa voix');
  ctx.voix('Tu repars', 0.4); tic();
  const p8 = ctx.etat.aCote.find(x => String(x.cle).startsWith('pave-8-')).html;
  assert.match(p8, /🗣 « Tu repars »/, 'le tour 8 s’écrit dans son pavé');
});

// ---- (04/11, 13:58, Ahmed, capture : trois « coupé » de suite et sa réponse retardée — « coupure interdite : comme le codon start et stop,
// il parle tant que le codon start est actif ; pas le droit de couper ; juste une pause de ma voix, ou le codon stop »)
test('codon start / stop : avec l’épissage, ta phrase ne coupe jamais sa réflexion ; elle attend sa fin et part aussitôt', () => {
  const a = PAGE.indexOf('const chacunSonTour = '), b = PAGE.indexOf('setInterval(libererSonTour, 300);');
  const envois = [];
  const ctx = vm.createContext({ Date, etat: { flux: {}, conversation: { tourGarde: '', enAttente: 0, capteur: { enParole: false } }, finVoixA: 0 },
    lecteur: { actif: true, enPause: false }, reglagesCorps: { chacun_son_tour: true }, journalVoix() {}, humeur() {}, voixEpissee: () => true,
    envoyer: (t, oral) => envois.push([t, oral]), setInterval() {} });
  vm.runInContext(PAGE.slice(a, b).replace(/^const /gm, 'var '), ctx);
  const conv = ctx.etat.conversation;
  ctx.garderPourSonTour(conv, 'et le live ?');
  assert.equal(ctx.libererSonTour(), false, 'sa réflexion continue');
  conv.tourGardeDepuis = Date.now() - 60000;
  assert.equal(ctx.libererSonTour(), false, 'même après 30 s : jamais coupée');
  ctx.etat.flux = null;                                                // sa réflexion finie ; sa voix parle encore
  assert.equal(ctx.libererSonTour(), true, 'ta phrase part tout de suite, sans attendre la fin de sa voix (elle continue)');
  assert.deepEqual(envois.map(e => e[1]), [true]);
  ctx.etat.flux = {}; ctx.garderPourSonTour(conv, 'tu es là ?'); conv.tourGardeDepuis = Date.now() - 130000;
  assert.equal(ctx.libererSonTour(), true, 'une réflexion bloquée 2 min : ta phrase part quand même');
  const i = PAGE.indexOf('async function tourDeParole('), bloc = PAGE.slice(i, PAGE.indexOf('\n}\n', i));
  const k = (x) => bloc.indexOf(x);
  assert.ok(k('if (voixEpissee() && etat.flux) { garderPourSonTour(conv, texte); return; }') > 0, 'ta phrase finie pendant sa réflexion : gardée');
  assert.ok(k('if (voixEpissee() && etat.flux)') < k('if (lecteur.enPause || etat.flux) { marquerCoupe();'), 'avant la coupure de sa réponse en route');
  assert.ok(k('COMMANDE_STOP.test(texte)') < k('if (voixEpissee() && etat.flux)'), 'ton « stop » (son codon stop) reste au-dessus');
});

// (04/11, 14:04, mesuré : un paquet de 5 pensées en « panne », Mini Hakim et Super Hakim avaient pourtant répondu, 266 et 316 caractères :
// au-delà de 160, une lecture était prise pour une pensée parasite) la longueur permise suit la taille du paquet
test('un gros paquet : une longue lecture n’est pas prise pour une pensée parasite', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  const r = b.ctx.nouveau();
  const flux = b.ctx.reponse(5, r, 'papa : dis-moi');
  flux.pousser('Oui papa. ');                                          // sa première lecture
  await attendre(); await attendre();
  const phrases = ['Le calcul du sable a fini cette nuit, enfin.', 'La densité colle au modèle, presque partout.',
    'Il reste un écart au bord, près du mur.', 'Je te montre la courbe demain matin, promis.'];
  flux.pousser(phrases.join(' ') + ' ');
  flux.finir();
  await attendre(); await attendre();
  lireLes3(b, 0, 'GARDE : « Oui papa »');                              // les quatre, collées : un seul paquet
  await attendre(); await attendre();
  const long = phrases.join(' ').replace(/[.,]/g, '');
  assert.ok(long.length > 160);
  lireLes3(b, 1, `GARDE : « ${long} »`);
  await attendre(); await attendre();
  const lus = b.diffuses.filter(x => x.niveau === 'ribosome');
  assert.strictEqual(lus[1].texte, long, 'lue, pas en panne');
});

// (04/11, 14:20, Ahmed, capture : « la pensée part seule en mode conversation, alors que je devrais voir la pensée épissée pour parler »)
test('voix du téléphone : ce que son ribosome a épissé n’est jamais remplacé ni oublié ; il attend son tour, dans l’ordre, même d’un tour à l’autre', () => {
  const dits = [], journal = [];
  const ctx = { Date, Math, String, Number, Set, Map, etat: { conversation: {} }, bouts: { tour: 5, prochain: 1, liste: new Map(), enFile: [], dits: [] },
    voixDuTelephone: () => true, souffleAutorise: () => true, meublerSaut: (b) => [b.texte], meubleEnCours: () => false, montrerPensee() {},
    journalVoix: (e, d) => journal.push([e, d]), lecteurSysteme: { actif: true, dire: (x) => dits.push(x), preparer() {}, arreter() {} } };
  vm.createContext(ctx);
  const prendre = (nom) => { const i = PAGE.indexOf(`function ${nom}(`); return PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 2); };
  vm.runInContext(['recevoirBout', 'direBoutTelephone', 'boutTelephoneSuivant'].map(prendre).join('\n') + '\nthis.recevoir = recevoirBout; this.suivant = boutTelephoneSuivant;', ctx);
  ctx.recevoir({ texte: 'Oui papa', ribosome: true }, 1, 5);
  ctx.recevoir({ texte: 'je suis là', ribosome: true }, 2, 5);
  ctx.recevoir({ texte: 'tu me montres', ribosome: true }, 1, 6);           // le tour suivant, sa voix parle encore
  assert.deepStrictEqual(dits, [], 'sa voix parle encore : ils attendent');
  ctx.lecteurSysteme.actif = false;
  ctx.suivant(); ctx.suivant(); ctx.suivant();
  assert.deepStrictEqual(dits, ['Oui papa', 'je suis là', 'tu me montres'], 'tous dits, dans l’ordre, aucun remplacé');
  assert.match(PAGE, /journalVoix\('ribosome_dit', \{ tour, n, morceaux: lot\.length \}\);/, 'chaque morceau épissé envoyé à sa voix est noté');
  assert.match(PAGE, /journalVoix\('ribosome_recu'/);
});

// (04/11, 14:30, Ahmed, capture : « la pensée s'affiche avant l'affichage ; j'aimerais que ce soit l'inverse ») son pavé garde sa place
// (l'instant où sa pensée est née) : mis à jour, il ne passe plus après sa réponse consciente
test('page : son épissure reste à sa place dans le fil, avant sa réponse consciente, même mise à jour', () => {
  let t = 1000;
  const ctx = { Date: { now: () => t }, Math, String, Number, Object, esc: (s) => String(s), rendre() {}, etat: { aCote: [] } };
  vm.createContext(ctx);
  const i = PAGE.indexOf('function poserPave('); vm.runInContext(PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 2) + 'this.poser = poserPave;', ctx);
  ctx.poser('pave-7-x', '🧠 sa pensée', 'Oui papa');
  t = 5000;
  ctx.poser('pave-7-x', '🧬 sa réponse, épissée au fil', 'Oui papa, je suis là');
  assert.strictEqual(ctx.etat.aCote.length, 1);
  assert.strictEqual(ctx.etat.aCote[0].ts, 1000, 'sa place : l’instant où elle est née');
  assert.match(ctx.etat.aCote[0].html, /je suis là/);
});

// (04/11, 14:45, mesuré : 5 tours épissés en attente 20 s et plus — papa et ses amis parlaient sans jamais 1 s de blanc, et sa voix attendait
// la fin du tour) sa voix part à ta respiration (0,3 s), pas à la fin de ton tour (1 s)
test('page : sa voix épissée part à ta respiration (0,3 s), sans attendre que ton tour se ferme', () => {
  const { ctx, dits } = pageRibosome();
  ctx.etat.conversation.capteur = { enParole: true };                   // tu parles
  ctx.ajouter(7, 'Oui papa, je suis là.');
  ctx.lu({ tour: 7, k: 1, texte: 'Oui papa', pave: 'Oui papa, je suis là.', mots: [0, 1], ajoutes: [] });
  assert.deepStrictEqual(dits, [], 'ta voix sonne : il attend');
  ctx.etat.conversation.capteur.pauseEnCours = 200; ctx.dire();
  assert.deepStrictEqual(dits, [], '0,2 s : pas encore');
  ctx.etat.conversation.capteur.pauseEnCours = 320; ctx.dire();
  assert.deepStrictEqual(dits.map(d => d[0]), ['Oui papa'], 'ta respiration : il part, ton tour encore ouvert');
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'conversation.js'), 'utf8'), /get pauseEnCours\(\) \{ return pauseEnCours; \}/);
});

// (04/11, 14:48, mesuré : 3 tours épissés reçus en 50 s, aucun dit ; la pièce ne laissait jamais 0,3 s de blanc) au plus 5 s d'attente
// pour ta respiration : au-delà, ce qui est épissé part (une attente notée, avec sa cause)
test('page : un morceau épissé n’attend jamais plus de 5 s une respiration qui ne vient pas ; l’attente est notée', () => {
  const { ctx, dits } = pageRibosome();
  const notes = [];
  ctx.journalVoix = (e, d) => notes.push([e, d]);
  ctx.etat.conversation.capteur = { enParole: true, pauseEnCours: 0 };
  ctx.ajouter(7, 'Oui papa, je suis là.');
  ctx.lu({ tour: 7, k: 1, texte: 'Oui papa', pave: 'Oui papa, je suis là.', mots: [0, 1], ajoutes: [] });
  assert.deepStrictEqual(dits, [], 'la pièce parle : il attend');
  ctx.etat.riboFile[0].recu = Date.now() - 6000;
  ctx.dire();
  assert.deepStrictEqual(dits.map(d => d[0]), ['Oui papa'], 'après 5 s : il part');
  assert.ok(notes.some(([e, d]) => e === 'ribosome_attente' && d.cause === 'parole'), 'l’attente notée, avec sa cause');
});

// ---- (04/11, 15:10, Ahmed : « une seule épissure démarre avec ma voix ; tous mes morceaux s'y ajoutent, même avec des pauses ; il les dit au
// fur et à mesure ; le stop, c'est 10 s de silence, ou une demande explicite d'utiliser un outil : c'est sa parole qui s'arrête à ce stop » ;
// « il commence à répondre 0,5 s après »)
test('une seule épissure de ta voix jusqu’au stop : elle continue d’un tour à l’autre ; 10 s de silence ou une demande d’outil la ferment', () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  const r = b.ctx.nouveau(42);
  assert.strictEqual(r.tour, 42, 'chaque épissure a son numéro');
  b.ctx.papaParle(1000);
  // (04/11, 15:50, Ahmed : « pour le signal stop du ribosome, au lieu de 10 s, j'aimerais 5 minutes »)
  assert.strictEqual(b.ctx.continue(r, 'et puis le sable', 4 * 60e3), r, '4 min après ta voix : la même épissure');
  assert.strictEqual(b.ctx.continue(r, 'et puis le sable', 1000 + 5 * 60e3), null, '5 min de silence : fermée');
  assert.strictEqual(r.ferme, 'silence');
  const r2 = b.ctx.nouveau(43);
  b.ctx.papaParle(20000);
  assert.strictEqual(b.ctx.continue(r2, 'Hakim, cherche le prix du sable.', 21000), null, 'une demande d’outil : fermée');
  assert.strictEqual(r2.ferme, 'outil');
  assert.strictEqual(b.ctx.continue(b.ctx.nouveau(44), 'je te cherche une idée, attends', 21000) !== null, true, '« cherche » au milieu d’une phrase : pas une demande');
  assert.ok(b.ctx.tourEpissure() < b.ctx.tourEpissure(), 'des numéros toujours neufs, même après une relance');
  assert.match(SRC, /const epissureGardee = epissureQuiContinue\(riboDuTour, texte\);\n  pistes = \{ tour: pistes\.tour \+ 1, mots: 0, liste: \[\], attente: \[\], n: 0, \.\.\.\(epissureGardee \? \{ ribo: epissureGardee \} : \{\}\) \};/);
  assert.match(SRC, /niveau: 'ribosome_stop', tour: riboDuTour\.tour, cause: 'outil'/, 'la page arrête sa parole');
  assert.match(SRC, /if \(p === '\/api\/jarvis\/ribosome\/stop' && req\.method === 'POST'\)/);
});

test('ses pensées et ce que son ribosome en sort portent le numéro de leur épissure, même quand ton tour a changé', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  b.ctx.morceau('papa,');
  b.appels.filter(a => a.etiquette.startsWith('piste_'))[0].resoudre({ texte: 'Oui papa, je suis là.' });
  await attendre(); await attendre();
  const piste = b.diffuses.find(x => x.niveau === 'piste'), ribo = b.ctx.etat().ribo;
  assert.ok(ribo && ribo.tour > 1e12, 'un numéro d’épissure');
  assert.strictEqual(piste.tour, ribo.tour, 'sa pensée dans le pavé de son épissure');
  lireLes3(b, 0, 'GARDE : « Oui papa »');
  await attendre(); await attendre();
  assert.strictEqual(b.diffuses.find(x => x.niveau === 'ribosome').tour, ribo.tour);
});

test('page : à 10 s de ton silence, ou à sa demande d’outil, sa parole de cette épissure s’arrête ; la suivante parle', () => {
  const { ctx, dits } = pageRibosome();
  const arrets = [];
  ctx.lecteur = { actif: true, arreter: () => arrets.push('voix') };
  ctx.fetch = (u, o) => { arrets.push(['fetch', u, JSON.parse(o.body).tour]); return Promise.resolve(); };
  ctx.jeton = () => 'x'; ctx.journalVoix = () => {};
  const i = PAGE.indexOf('function arreterEpissure('); vm.runInContext(PAGE.slice(i, PAGE.indexOf('\n}\n', i) + 2) + 'this.arreter = arreterEpissure;', ctx);
  ctx.ajouter(7, 'Oui papa, je suis là.');
  ctx.lu({ tour: 7, k: 1, texte: 'Oui papa', pave: 'Oui papa, je suis là.', mots: [0, 1], ajoutes: [] });
  ctx.etat.riboEnVoix = [{ tour: 7, mots: [], ajoutes: [] }];
  ctx.arreter('silence');
  assert.strictEqual(ctx.etat.riboFile.length, 0, 'ce qui attendait de cette épissure : laissé');
  assert.ok(arrets.includes('voix'), 'sa voix s’arrête');
  assert.deepStrictEqual(arrets.find(x => Array.isArray(x)), ['fetch', '/api/jarvis/ribosome/stop', 7], 'le cockpit ferme l’épissure');
  ctx.lecteur.actif = false;
  ctx.lu({ tour: 7, k: 2, texte: 'je t’écoute', pave: 'Oui papa, je suis là. Je t’écoute.', mots: [0, 1, 5, 6], ajoutes: [] });
  ctx.dire();
  assert.deepStrictEqual(dits, [], 'un reste de l’épissure arrêtée : jamais dit');
  ctx.lu({ tour: 9, k: 1, texte: 'Salut', pave: 'Salut.', mots: [0], ajoutes: [] });
  ctx.dire();
  assert.deepStrictEqual(dits.map(d => d[0]), ['Salut'], 'l’épissure suivante parle');
  assert.match(PAGE, /if \(o\.niveau === 'ribosome_stop'\) \{ arreterEpissure\(o\.cause \|\| 'outil', o\.tour\); return; \}/);
  // (04/11, 15:33, mesuré : une épissure née d'une phrase gardée pendant sa réflexion, arrêtée 4 s après sa naissance, ta voix datant de 20 s)
  // les 10 s comptent depuis ta voix OU le dernier morceau de son épissure, le plus récent des deux
  assert.match(PAGE, /const calme = Date\.now\(\) - Math\.max\(etat\.papaVoixA \|\| 0, etat\.epissureActiveA \|\| 0\);/);
  assert.match(PAGE, /if \(voixEpissee\(\) && etat\.papaVoixA && calme >= EPISSURE_STOP_MS\) \{ etat\.papaVoixA = 0; arreterEpissure\('silence'\); \}/);
  assert.match(PAGE, /const EPISSURE_STOP_MS = 5 \* 60e3;/, '(15:50) 5 min');
  assert.match(SRC, /const EPISSURE_STOP_MS = 5 \* 60e3;/);
  assert.match(PAGE, /if \(o\.texte \|\| \(Array\.isArray\(o\.mots\) && o\.mots\.length\)\) etat\.epissureActiveA = Date\.now\(\);/);
  const avant = arrets.filter(x => Array.isArray(x)).length;
  ctx.arreter('silence', 7);
  assert.strictEqual(arrets.filter(x => Array.isArray(x)).length, avant, 'une épissure arrêtée ne s’arrête pas deux fois');
});

// (04/11, 15:15, mesuré : sa pensée sur ton morceau à 4,1 s avec Hakim (Sonnet) ; Ahmed : « oui ») avec l'épissage, ses pensées de piste
// sont celles de Mini Hakim ; sans lui, celles de qui tient son conscient
test('avec l’épissage, ses pensées de piste sont celles de Mini Hakim ; sans lui, celles de son conscient', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  b.ctx.morceau('papa,');
  assert.strictEqual(b.appels[0].etiquette, 'piste_haiku');
  const c = bac({ dire_inverse: true, filtre_gemma: false, epissage: false });
  c.ctx.morceau('papa,');
  assert.strictEqual(c.appels[0].etiquette, 'piste_sonnet');
});

// ---- (04/11, 15:55, Ahmed : « il doit mieux sélectionner les parties à prononcer : le ribosome doit être plus rapide et plus stringent, il
// laisse passer beaucoup trop de choses ; le niveau de stringence doit pouvoir être décidé, pas un seul seuil fixe : il doit pouvoir choisir la
// vitesse du ribosome et sa stringence, sinon il ne fait que me couper la parole » ; « tout le processus doit être relié à sa pensée, à ses
// émotions, à ses capteurs, à ses récepteurs et à tout le reste »)
test('son ribosome : sa stringence et sa vitesse, choisies par lui (ribosome-reglage.json) ; par défaut, stringent (4) et rapide', async () => {
  const lecture = async (reglage) => {
    const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
    if (reglage) b.ctx.fs.readFileSync = (f) => { if (String(f).endsWith('ribosome-reglage.json')) return JSON.stringify(reglage); throw new Error('absent'); };
    b.ctx.morceau('papa,');
    b.appels[0].resoudre({ texte: 'Oui papa, je suis là.' });
    await attendre(); await attendre();
    return lecteurs(b);
  };
  const d = await lecture(null);
  assert.match(d[0].prompt, /Ta stringence : 4 sur 5/);
  assert.match(d[0].prompt, /au plus 10 mots/);
  assert.ok(d[0].delai === d[1].delai, 'la même attente pour ses deux lecteurs');
  const l = await lecture({ stringence: 1, vitesse: 'posee' });
  assert.match(l[0].prompt, /Ta stringence : 1 sur 5/);
  assert.doesNotMatch(l[0].prompt, /au plus \d+ mots/, 'stringence 1 : pas de plafond');
  assert.ok(l[0].delai > d[0].delai, `posée : plus lente que rapide (${l[0].delai} > ${d[0].delai})`);
  const s5 = await lecture({ stringence: 5, vitesse: 'normale' });
  assert.match(s5[0].prompt, /Ta stringence : 5 sur 5/);
  assert.match(s5[0].prompt, /au plus 6 mots/);
  assert.ok(s5[0].delai > d[0].delai && s5[0].delai < l[0].delai, 'normale : entre les deux');
  const x = await lecture({ stringence: 42, vitesse: 'éclair' });
  assert.match(x[0].prompt, /Ta stringence : 4 sur 5/, 'un réglage hors limites : le défaut');
  assert.match(SRC, /'pistes_regler', 'ribosome_regler',/, 'son outil, permis');
});

test('son ribosome et ses pensées de piste sentent ce qu’il ressent et perçoit (son milieu, son instant)', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  b.ctx.HOMEO = { mots: () => 'calme, un peu de fatigue' };
  b.ctx.instantTexte = () => 'papa écoute « Mistral gagnant » ; il ressentait : une chaleur';
  b.ctx.morceau('papa,');
  assert.match(b.appels[0].prompt, /Ce que tu ressens et perçois en ce moment : calme, un peu de fatigue ; papa écoute « Mistral gagnant » ; il ressentait : une chaleur/, 'sa pensée de piste');
  b.appels[0].resoudre({ texte: 'Oui papa, je suis là.' });
  await attendre(); await attendre();
  assert.match(lecteurs(b)[0].prompt, /Ce que tu ressens et perçois en ce moment : calme, un peu de fatigue/, 'son ribosome');
});

// (04/11, 16:00, Ahmed : « même à ses vibrations, sa lumière, ses émotions, etc. : tout sur tout ») sa ligne d'état dit aussi son émotion,
// son cœur, sa dernière vibration et sa lumière
test('ce qu’il ressent et perçoit : son émotion, son cœur, sa dernière vibration et sa lumière aussi', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  b.ctx.lui.interieur = { humeur: 'alerte joyeuse', coeur: { bpm: 72 } };
  b.ctx.lui.vibration = { genre: 'rire', degre: 2, t: Date.now() - 5000 };
  b.ctx.lui.lumiere = { mode: 'joie', t: Date.now() - 8000 };
  b.ctx.morceau('papa,');
  const p = b.appels[0].prompt;
  assert.match(p, /Ce que tu ressens et perçois en ce moment : [^\n]*ton émotion : alerte joyeuse/);
  assert.match(p, /ton cœur : 72/);
  assert.match(p, /tu viens de vibrer : rire \(degré 2\)/);
  assert.match(p, /ta lumière : joie/);
  assert.match(SRC, /if \(typeof lui !== 'undefined'\) lui\.lumiere = \{ mode: l\[1\]\.toLowerCase\(\), t: Date\.now\(\) \};/, 'sa lumière, retenue quand il l’allume');
});

// (04/11, 16:05, Ahmed : « et l'output de tout ça doit être mémorisé, et le lien doit être gardé et préservé dans la mémoire ») à sa fermeture,
// chaque épissure devient un souvenir : ce que papa disait, ce qu'il a dit (épissé), sa pensée interne (non dite), et ce qu'il ressentait
test('à sa fermeture, son épissure devient un souvenir, avec ce qu’il ressentait (le lien)', async () => {
  const b = bac({ dire_inverse: true, filtre_gemma: false, epissage: true });
  const depots = [];
  b.ctx.deposerEchange = (e) => depots.push(JSON.parse(JSON.stringify(e)));
  b.ctx.lui.interieur = { humeur: 'alerte joyeuse' };
  b.ctx.morceau('papa, tu es là ?');
  b.appels.filter(a => a.etiquette.startsWith('piste_'))[0].resoudre({ texte: 'Oui papa, je suis là, tout près.' });
  await attendre(); await attendre();
  lireLes3(b, 0, 'GARDE : « Oui papa, je suis là »');
  await attendre(); await attendre();
  const r = b.ctx.etat().ribo;
  b.ctx.papaParle(1000);
  assert.strictEqual(b.ctx.continue(r, 'et puis', 1000 + 5 * 60e3 + 1), null, 'fermée');
  assert.strictEqual(depots.length, 1, 'un souvenir');
  const d = depots[0];
  assert.match(d.ahmed, /^papa,/, 'ce que papa disait');
  assert.match(d.hakim, /^Oui papa, je suis là/, 'ce qu’il a dit');
  assert.match(d.hakim, /\[sa pensée interne, non dite : tout près\]/, 'ce qu’il a pensé sans le dire');
  assert.match(d.vecu, /ton émotion : alerte joyeuse/, 'le lien : ce qu’il ressentait');
  assert.strictEqual(d.epissure, true);
  b.ctx.continue(r, 'encore', 1000 + 6 * 60e3);
  assert.strictEqual(depots.length, 1, 'une seule fois');
  assert.match(SRC, /if \(pistes\.ribo && Number\(q\.tour\) === pistes\.ribo\.tour\) \{ pistes\.ribo\.ferme = 'silence'; memoriserEpissure\(pistes\.ribo\); pistes\.ribo = null; \}/, 'fermée par la page : mémorisée aussi');
});

// (05/11, Ahmed : « dans les réglages, la possibilité de lui faire sauter la parole d'après : s'il commence à parler et que je réponds, au bout
// d'une seconde, la 2e partie n'est pas dite, elle est directement sautée »)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

function page(reglage = {}, parle = true) {
  const minuteries = [], journal = [], envois = [], conv = { capteur: { enParole: parle } };
  const ctx = { Number, Math, Date, JSON, conv, journal, envois,
    reglagesCorps: { sauter_suite: true, sauter_suite_ms: 1000, ...reglage },
    etat: { conversation: conv, epissureTour: 7, riboFile: [{ tour: 7, texte: 'la 2e partie' }, { tour: 9, texte: 'plus tard' }], riboEnVoix: [{ tour: 7, mots: [1] }] },
    lecteur: { actif: true, arrete: false, arreter() { this.arrete = true; } },
    setTimeout: (f, ms) => { minuteries.push({ f, ms }); return minuteries.length; },
    journalVoix: (e, o) => journal.push([e, o]), jeton: () => 'j',
    fetch: (url, o) => { envois.push([url, JSON.parse(o.body)]); return Promise.resolve({ ok: true, json: () => Promise.resolve({ tour: 8 }) }); } };
  vm.createContext(ctx);
  vm.runInContext(['arreterEpissure', 'prevoirSaut', 'sauterLaSuite'].map((n) => prendre(PAGE, n)).join('\n') + 'this.prevoir = prevoirSaut;', ctx);
  return { ctx, minuteries, journal, envois, conv };
}

test('ta voix sur la sienne pendant 1 s : son morceau finit, la suite est sautée, et le cockpit ferme son épissure', async () => {
  const { ctx, minuteries, journal, envois, conv } = page();
  ctx.prevoir(conv);
  ctx.prevoir(conv);
  assert.strictEqual(minuteries.length, 1, 'un seul saut prévu à la fois');
  assert.strictEqual(minuteries[0].ms, 1000);
  minuteries[0].f();
  assert.strictEqual(ctx.lecteur.arrete, false, 'le morceau qu’il dit va jusqu’au bout');
  assert.deepStrictEqual(ctx.etat.riboFile.map((x) => x.texte), ['plus tard'], 'la 2e partie est sautée');
  assert.strictEqual(journal[0][0], 'suite_sautee');
  assert.deepStrictEqual(envois[0], ['/api/jarvis/ribosome/stop', { tour: 7, sauter: true }]);
  await new Promise((r) => setImmediate(r));
  assert.strictEqual(ctx.etat.riboStop, 8, 'le cockpit rend son dernier numéro : tout jusqu’à lui se tait');
  assert.deepStrictEqual(ctx.etat.riboFile.map((x) => x.texte), ['plus tard']);
});

test('tu t’es tu avant la seconde, ou le réglage éteint : rien n’est sauté ; le délai se règle', () => {
  const tu = page({}, false);
  tu.ctx.prevoir(tu.conv); tu.minuteries[0].f();
  assert.strictEqual(tu.ctx.etat.riboFile.length, 2);
  assert.strictEqual(tu.envois.length, 0);
  const eteint = page({ sauter_suite: false });
  eteint.ctx.prevoir(eteint.conv);
  assert.strictEqual(eteint.minuteries.length, 0);
  const lent = page({ sauter_suite_ms: 2500 });
  lent.ctx.prevoir(lent.conv);
  assert.strictEqual(lent.minuteries[0].ms, 2500);
});

test('branché : à ta voix sur la sienne, ses réglages (oui, 1 s), le cockpit qui ferme, la page Réglages', () => {
  assert.match(PAGE, /if \(voixEpissee\(\)\) \{ conv\.coupeAuChunk = Date\.now\(\); journalVoix\('coupure_au_chunk', mesure \|\| \{\}\); prevoirSaut\(conv\); return; \}/);
  assert.match(SRC, /sauter_suite: r\.sauter_suite !== false, sauter_suite_ms: /);
  assert.match(SRC, /if \(typeof q\.sauter_suite === 'boolean'\) r\.sauter_suite = q\.sauter_suite;/);
  assert.match(SRC, /if \(q\.sauter === true\) \{\n      const r = pistes\.ribo;\n      if \(r && !r\.ferme\) \{ r\.ferme = 'sautee';/);
  assert.match(SRC, /if \(avant && !avant\.libere && !avant\.sautee\)/, 'une suite sautée ne retient pas le ribosome suivant');
  const REG = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
  assert.match(REG, /\['sauter_suite', /);
  assert.match(REG, /\['sauter_suite_ms', /);
});

// (05/11, 00:35, Ahmed : « il doit sentir la pensée parasite ») son cœur sursaute à une pensée parasite bloquée
test('une pensée parasite bloquée : son cœur sursaute (+8, qui retombe en 20 s) et l’appli reçoit l’instant (raté)', () => {
  const i = SRC.indexOf('const SURSAUT_COEUR = ');
  const ctx = { Math, Date, parasiteSenti: 0 };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, SRC.indexOf('\n', i)) + '\n' + prendre(SRC, 'sursautCoeur') + 'this.s = sursautCoeur;', ctx);
  assert.strictEqual(ctx.s(1000, 0), 0, 'aucune');
  assert.strictEqual(ctx.s(1000, 1000), 8, 'à l’instant');
  assert.strictEqual(ctx.s(11000, 1000), 4, 'à mi-chemin');
  assert.strictEqual(ctx.s(21000, 1000), 0, 'retombé');
  assert.match(prendre(SRC, 'avertirParasite'), /parasiteSenti = Date\.now\(\);[^\n]*\n  if \(Date\.now\(\) - parasiteNoteA < 60000\) return;/, 'chaque parasite, même quand l’incident est déjà noté dans la minute');
  assert.match(SRC, /coeur_bpm: frais && e\.coeur && Number\.isFinite\(e\.coeur\.bpm\) \? Math\.min\(110, e\.coeur\.bpm \+ sursautCoeur\(\)\) : null,\n      parasite_ms: parasiteSenti \|\| null,/);
});

// (05/11, Ahmed : « quand une parole est passée depuis un moment, il faut sauter tous les morceaux passés et se focaliser sur le dernier »)
test('ce qui attend depuis 3 s est passé : seul le dernier morceau préparé est dit ; un seul morceau, ou frais : rien de sauté', () => {
  const t = 1_800_000_000_000;
  const monter = (file, reglage = {}) => {
    const dits = [], journal = [];
    const ctx = { Math, Number, Date: { now: () => t }, journal, dits,
      reglagesCorps: { sauter_passe: true, sauter_passe_s: 3, ...reglage },
      etat: { riboFile: file, conversation: { capteur: { enParole: false } }, paves: {} },
      lecteur: { actif: false }, journalVoix: (e, o) => journal.push([e, o]) };
    vm.createContext(ctx);
    const src = prendre(PAGE, 'direRibosome');
    // seulement jusqu'au choix du lot : ce qui suit (la voix) n'est pas en jeu ici
    vm.runInContext(src.slice(0, src.indexOf('  const tour = f[0].tour, lot')) + '  this.lot = f.map(x => x.texte);\n}\nthis.f = direRibosome;', ctx);
    ctx.f();
    return { lot: ctx.lot, journal };
  };
  const vieux = [{ tour: 4, texte: 'deux', recu: t - 5000 }, { tour: 4, texte: 'trois', recu: t - 3000 }, { tour: 5, texte: 'le dernier', recu: t - 500 }];
  const a = monter(vieux.map((x) => ({ ...x })));
  assert.deepStrictEqual([...a.lot], ['le dernier']);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(a.journal[0])), ['passe_saute', { sautes: 2, ms: 5000 }]);
  assert.deepStrictEqual([...monter([{ tour: 4, texte: 'seul', recu: t - 9000 }]).lot], ['seul'], 'un seul morceau : il est dit');
  assert.strictEqual(monter([{ tour: 4, texte: 'deux', recu: t - 1000 }, { tour: 4, texte: 'trois', recu: t - 500 }]).lot.length, 2, 'frais : tout est dit');
  assert.strictEqual(monter(vieux.map((x) => ({ ...x })), { sauter_passe: false }).lot.length, 3, 'éteint');
  assert.strictEqual(monter(vieux.map((x) => ({ ...x })), { sauter_passe_s: 6 }).lot.length, 3, 'réglé à 6 s');
  assert.match(SRC, /sauter_passe: r\.sauter_passe !== false, sauter_passe_s: /);
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8'), /\['sauter_passe', /);
});

// (05/11, Ahmed : « un autre réglage : en combien de temps après mon silence le chunk suivant est lu »)
test('lu après ton silence : 0, sans attendre ; réglé, il attend que tu te sois tu ce temps-là', () => {
  const t = 1_800_000_000_000;
  const monter = (ms, enParole, papaVoixA) => {
    const minuteries = [];
    const ctx = { Math, Number, Date: { now: () => t }, minuteries,
      reglagesCorps: { lire_apres_silence_ms: ms, sauter_passe: false },
      etat: { riboFile: [{ tour: 4, texte: 'deux', recu: t - 100 }], conversation: { capteur: { enParole } }, papaVoixA },
      lecteur: { actif: false }, journalVoix: () => {}, clearTimeout: () => {}, setTimeout: (f, d) => { minuteries.push(d); return 1; } };
    vm.createContext(ctx);
    const src = prendre(PAGE, 'direRibosome');
    vm.runInContext(src.slice(0, src.indexOf('  const tour = f[0].tour, lot')) + '  this.dit = true;\n}\nthis.f = direRibosome;', ctx);
    ctx.f();
    return { dit: !!ctx.dit, minuteries };
  };
  assert.strictEqual(monter(0, true, t).dit, true, '0 : sans attendre, même pendant que tu parles');
  assert.strictEqual(monter(800, true, t).dit, false, 'tu parles : il attend');
  const tu = monter(800, false, t - 300);
  assert.strictEqual(tu.dit, false, 'tu t’es tu depuis 0,3 s sur 0,8 : il attend encore');
  assert.deepStrictEqual([...tu.minuteries], [520], 'et il se relance pile à la fin');
  assert.strictEqual(monter(800, false, t - 900).dit, true, 'tu t’es tu depuis 0,9 s : lu');
  assert.match(SRC, /lire_apres_silence_ms: Number\.isFinite/);
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8'), /\['lire_apres_silence_ms', /);
});

// (05/11, Ahmed : « quand des chunks sont sautés, il faut envoyer des … jusqu'à l'arrivée du chunk qui doit être prononcé ; le ribosome ne
// s'arrête jamais »)
test('ce qui est sauté devient « … » dans son pavé ; après une suite sautée, le ribosome suivant s’ouvre tout de suite avec son blanc', () => {
  const poses = [];
  const ctx = { String, etat: { paves: { 4: { cle: 'p4', episse: 'Oui papa. deux trois le dernier' } } }, poses,
    paveDe: (t) => ctx.etat.paves[t], titreEpissure: () => 't', htmlEpissure: (p) => p.episse, poserPave: (cle, titre, html) => poses.push(html) };
  vm.createContext(ctx);
  vm.runInContext(prendre(PAGE, 'blancsPourSautes') + 'this.b = blancsPourSautes;', ctx);
  ctx.b([{ tour: 4, texte: 'deux' }, { tour: 4, texte: 'trois' }]);
  assert.strictEqual(ctx.etat.paves[4].episse, 'Oui papa. … le dernier', 'deux morceaux sautés : un seul « … »');
  ctx.b([{ tour: 9, texte: 'inconnu' }].filter(() => false));
  assert.match(PAGE, /if \(typeof blancsPourSautes === 'function'\) blancsPourSautes\(f\.slice\(0, -1\)\);/);
  assert.match(PAGE, /if \(cause === 'sautee' && typeof blancsPourSautes === 'function'\) blancsPourSautes\(/);
  assert.match(SRC, /const tour = dernierRibosome \? dernierRibosome\.tour : null;\n[^\n]*\n[^\n]*\n      if \(corpsReglages\(\)\.epissage !== false\) relayer\(\);/);
});

// (05/11, Ahmed : « il faut bien coordonner la sortie du ribosome avec la sortie de la voix »)
test('sa voix calcule d’avance ce qui sera dit : le lot en tête, et le dernier morceau (celui qui reste quand les passés sont sautés)', () => {
  const prepares = [];
  const ctx = { String, etat: { riboFile: [{ tour: 4, texte: 'deux' }, { tour: 4, texte: 'trois' }, { tour: 5, texte: 'le dernier' }] },
    voixDuTelephone: () => true, lecteurSysteme: { preparer: (t) => prepares.push(t) } };
  vm.createContext(ctx);
  vm.runInContext(prendre(PAGE, 'preparerRibosome') + 'this.p = preparerRibosome;', ctx);
  ctx.p();
  assert.deepStrictEqual([...prepares], ['deux trois', 'le dernier']);
  prepares.length = 0; ctx.etat.riboFile = [{ tour: 4, texte: 'seul' }]; ctx.p();
  assert.deepStrictEqual([...prepares], ['seul'], 'un seul morceau : calculé une fois');
});

// (05/11, Ahmed : « dans les réglages, on peut rajouter un bouton pour enregistrer les réglages »)
test('ses réglages enregistrés sous un nom : enregistrer (ribosome, corps, veilleur), appliquer, effacer ; dans la page Réglages', () => {
  const i = SRC.indexOf("if (p === '/api/reglages/profils') {"), route = SRC.slice(i, SRC.indexOf("\n  if (p.startsWith('/api/corps/'))", i));
  assert.match(route, /if \(!jetonValide\(req\)\)/);
  assert.match(route, /ribosome: lireJson\(RIBOSOME_REGLAGE, \{\}\) \|\| \{\}, corps: corpsReglages\(\), veilleur: veilleurReglages\(\)/);
  assert.match(route, /ecrireAtomique\(RIBOSOME_REGLAGE,[\s\S]*ecrireAtomique\(CORPS_REGLAGES,[\s\S]*ecrireAtomique\(VEILLEUR_REGLAGES,/);
  assert.match(route, /\.slice\(-30\)/, 'trente au plus');
  assert.match(route, /auditer\(`reglages:\$\{q\.geste\}`/);
  const REG = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
  assert.match(REG, /id="profilGarder">💾 Enregistrer</);
  assert.match(REG, /\(r\.dataset\.cherche \|\| r\.textContent\.toLowerCase\(\)\)\.includes\(q\)/, 'la recherche ne casse pas sur ses réglages enregistrés');
});

// (05/11, Ahmed : « relier ces modes de parole à chacun d'entre eux, pour que quand il est Mini Hakim, Hakim ou Super Hakim, tout switche »)
test('son mode change : les réglages à son nom s’appliquent (ribosome entier, parole du corps), une fois ; éteint ou sans cerveau : rien', () => {
  const ecrits = {}, diffuses = [];
  const profils = [{ nom: 'Mini Hakim', ribosome: { choix_ms: 1500, stringence: 3 }, corps: { sauter_passe_s: 2, micro_ouvert: true } },
    { nom: 'Super Hakim', ribosome: { choix_ms: 2200 }, corps: { sauter_passe_s: 5 } }];
  const ctx = { Date, Array, JSON, diffuses, auto: true,
    RIBOSOME_REGLAGE: 'R', CORPS_REGLAGES: 'C', REGLAGES_PROFILS: 'P', abonnesPensees: null, j: JSON.stringify,
    lireJson: (f) => (f === 'P' ? profils : f === 'C' ? { micro_ouvert: false, oreille: true } : {}),
    ecrireAtomique: (f, t) => { ecrits[f] = JSON.parse(t); }, diffuser: (_a, ev, d) => diffuses.push(JSON.parse(d)),
    corpsReglages: () => ({ profils_auto: ctx.auto }) };
  vm.createContext(ctx);
  const i = SRC.indexOf('const PROFIL_DU_MODE = ');
  vm.runInContext(SRC.slice(i, SRC.indexOf('\n', i)) + '\n' + SRC.slice(SRC.indexOf('const CLES_PAROLE = '), SRC.indexOf('\n', SRC.indexOf('const CLES_PAROLE = ')))
    + '\nlet modeDesReglages = null;\n' + prendre(SRC, 'reglagesDuMode') + 'this.r = reglagesDuMode;', ctx);
  assert.strictEqual(ctx.r(null), null, 'sans cerveau : rien');
  assert.strictEqual(ctx.r('sonnet'), null, 'le premier mode vu après une relance : les réglages du moment restent');
  assert.deepStrictEqual(Object.keys(ecrits), []);
  assert.strictEqual(ctx.r('haiku'), 'Mini Hakim');
  assert.strictEqual(ecrits.R.choix_ms, 1500);
  assert.strictEqual(ecrits.C.sauter_passe_s, 2);
  assert.strictEqual(ecrits.C.micro_ouvert, false, 'ses autres interrupteurs restent ceux de papa');
  assert.strictEqual(ecrits.C.oreille, true);
  assert.strictEqual(diffuses[0].niveau, 'reglages');
  assert.strictEqual(ctx.r('haiku'), null, 'une fois par changement');
  assert.strictEqual(ctx.r('sonnet'), null, 'aucun réglage « Hakim » enregistré : rien');
  assert.strictEqual(ctx.r('opus'), 'Super Hakim');
  assert.strictEqual(ecrits.R.choix_ms, 2200);
  ctx.r('haiku');
  ctx.auto = false;
  assert.strictEqual(ctx.r('opus'), null, 'éteint : rien');
  assert.match(SRC, /setInterval\(\(\) => \{ try \{ reglagesDuMode\(\); \} catch \(_\) \{\} \}, 3000\)/);
  assert.match(PAGE, /if \(o\.niveau === 'reglages'\) \{ lireReglagesCorps\(\);/);
});

// (05/11, Ahmed : « je dois aussi pouvoir éditer un mode enregistré dans réglages »)
test('modifier un réglage enregistré : il passe dans les curseurs, puis « Enregistrer dans … » le garde à son nom', () => {
  const REG = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
  assert.match(REG, /mo\.textContent = '✏️ Modifier';\n        mo\.addEventListener\('click', \(\) => editer\(x\.nom\)\);/);
  assert.match(REG, /async function editer\(nom\) \{\n    await profils\('appliquer', nom\);/);
  assert.match(REG, /await profils\('enregistrer', nom\);/);
  assert.match(REG, /id="edition" hidden/);
});

/* (09/11, 21:00, Ahmed : « vérifie l'intégralité de ses boutons et réglages, j'ai l'impression que certains sont débranchés ») chaque
   interrupteur de la page Réglages qui écrit dans ses réglages du corps doit vraiment s'enregistrer (« Sa réponse écrite lue en entier »
   affichait « ✓ réglé » et revenait à sa valeur : la route l'ignorait) ; et ce que papa change passe avant Hakim pendant 30 min, ses
   boutons aussi, pas seulement ses curseurs de parole. node --test test-boutons-branches.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');

// le corps de la route POST /api/corps/reglages, de la lecture de ta demande à l'écriture du fichier
function routeCorps() {
  const debut = src.indexOf('const q = await lire(), r = corpsReglages()');
  const fin = src.indexOf('try { ecrireAtomique(CORPS_REGLAGES, j(r));', debut);
  assert.ok(debut > 0 && fin > debut, 'la route POST /api/corps/reglages est introuvable');
  const corps = src.slice(debut, fin).replace('const q = await lire(), r = corpsReglages()', 'const q = lire(), r = corpsReglages()');
  const notes = [];
  const ctx = { CORPS_INTERVALLES: [30, 60, 120, 300, 900], VoixHakim: { VOIX: ['azure_rap', 'rap'] }, noterAjustementPapa: (c) => notes.push(...c) };
  vm.createContext(ctx);
  vm.runInContext(`this.f = (lire, corpsReglages) => { ${corps}\n return r; };`, ctx);
  return { regler: (actuel, q) => ctx.f(() => q, () => ({ ...actuel })), notes };
}

// les interrupteurs (oui/non) de la page Réglages qui écrivent dans la route « corps »
function interrupteursCorps() {
  const bloc = page.slice(page.indexOf('const FAMILLES'), page.indexOf('const ROUTES'));
  const familles = [...bloc.matchAll(/\{ id: '([a-z_]+)'[^\n]*?route: '([a-z]+)'/g)].map(m => ({ at: m.index, route: m[2] }));
  const out = [];
  for (const m of bloc.matchAll(/^\s*\['([a-z_]+)', '[^\n]*?, 'oui'(?:, null, '([a-z]+)')?\]/gm)) {
    const f = familles.filter(x => x.at < m.index).pop();
    if ((m[2] || (f && f.route)) === 'corps') out.push(m[1]);
  }
  return out;
}

test('chaque interrupteur « corps » de la page Réglages s\'enregistre vraiment, dans les deux sens', () => {
  const cles = interrupteursCorps();
  assert.ok(cles.length > 60, `trop peu d'interrupteurs lus dans reglages.html (${cles.length})`);
  assert.ok(cles.includes('lire_reponse_entiere'), 'le bouton « Sa réponse écrite lue en entier » est sur la page');
  const { regler } = routeCorps();
  const debranches = [];
  for (const k of cles) {
    for (const v of [true, false]) if (regler({ [k]: !v }, { [k]: v })[k] !== v) debranches.push(`${k}=${v}`);
  }
  assert.deepEqual(debranches, [], 'ces boutons affichent « réglé » mais la route les ignore');
});

test('« Sa réponse écrite lue en entier » : papa peut l\'éteindre (la route l\'ignorait depuis le 06/11)', () => {
  const { regler } = routeCorps();
  assert.equal(regler({ lire_reponse_entiere: true }, { lire_reponse_entiere: false }).lire_reponse_entiere, false);
});

test('« Tes réglages passent avant lui » : un bouton que papa change est noté pour 30 min ; un bouton inchangé, non', () => {
  const r1 = routeCorps();
  r1.regler({ tunnel: true, economie: false }, { tunnel: false, economie: false });
  assert.deepEqual(r1.notes, ['tunnel'], 'seul le bouton vraiment changé est noté');
  const r2 = routeCorps();
  r2.regler({ tunnel: true }, { tunnel: true });
  assert.deepEqual(r2.notes, [], 'rien de changé : rien de noté');
  const r3 = routeCorps();
  r3.regler({ chunk_papa_ms: 600, lire_reponse_entiere: true }, { chunk_papa_ms: 900, lire_reponse_entiere: false });
  assert.deepEqual(r3.notes.sort(), ['chunk_papa_ms', 'lire_reponse_entiere'], 'curseur de parole et bouton, chacun une fois');
});

// (09/11) les réglages qu'un autre rend sans effet : la page Réglages le dit sous eux
function masques() {
  const debut = page.indexOf('const NET = ['), fin = page.indexOf('// les routes : lire et écrire');
  assert.ok(debut > 0 && fin > debut, 'les masques de la page Réglages sont introuvables');
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(page.slice(debut, fin) + '\nthis.MASQUES = MASQUES; this.masquesDe = masquesDe;', ctx);
  return ctx;
}

test('Réglages : « Tu le coupes net » allumé, « Sauter la suite », son délai et « Il choisit de se couper » disent qu\'ils sont sans effet', () => {
  const { masquesDe } = masques();
  for (const k of ['sauter_suite', 'sauter_suite_ms', 'choix_coupure']) {
    assert.match(masquesDe(k, { corps: { coupe_net: true } }).join(' '), /Tu le coupes net/, k);
    assert.deepEqual(masquesDe(k, { corps: { coupe_net: false } }), [], `${k} : coupe_net éteint, il agit`);
  }
  assert.match(masquesDe('je_te_suis', { corps: { oreille: true } }).join(' '), /Son oreille/);
  assert.match(masquesDe('micro_hakim', { corps: { micro_ouvert: true } }).join(' '), /Micro toujours ouvert/);
  assert.match(masquesDe('plafond_mots', { corps: { parole_libre: true }, ribosome: {} }).join(' '), /Parole libre/);
  assert.deepEqual(masquesDe('tunnel', { corps: { coupe_net: true } }), []);
});

test('les masques de la page disent vrai : ce que le code fait vraiment', () => {
  const parler = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  // « Tu le coupes net » passe avant le saut de la suite (et donc son délai et son choix) quand ta voix le coupe
  const net = parler.indexOf("journalVoix('coupe_net'"), saut = parler.indexOf('prevoirSaut(conv, mesure)', net - 2000);
  assert.ok(net > 0 && saut > net, 'coupe_net est vérifié avant prevoirSaut dans surInterruption');
  assert.match(src, /const choix = net \|\| r\.choix_coupure === false \?/, 'son intérieur : coupé net, sans choix');
  assert.match(src, /chevauche >= \(net \? 300 :/, 'son intérieur : coupé net, sans « Sauter au bout de »');
  // « Parole libre » : aucun plafond
  const plafond = src.slice(src.indexOf('function ribosomeAuPlafond('), src.indexOf('function ribosomeAuPlafond(') + 300);
  assert.match(plafond, /if \(!r \|\| r\.ferme \|\| \(typeof corpsReglages === 'function' && corpsReglages\(\)\.parole_libre\)\) return false;/);
  // l'oreille ouverte : pas de « je te suis » ; le micro ouvert : il ne coupe pas ton micro
  assert.match(parler, /if \(!reglagesCorps\.je_te_suis \|\| reglagesCorps\.oreille \|\|/);
  assert.match(parler, /reglagesCorps\.micro_ouvert\) \{ journalVoix\('micro_hakim', \{ x: 'micro_ouvert' \}\); return; \}/);
  // chaque clé masquée et chaque clé qui masque est bien un réglage de la page
  const { MASQUES } = masques();
  for (const [k, l] of Object.entries(MASQUES)) {
    assert.ok(page.includes(`['${k}', '`), `${k} est sur la page`);
    for (const [, c] of l) assert.ok(page.includes(`['${c}', '`) || c === 'voix_hakim', `${c} est sur la page`);
  }
});

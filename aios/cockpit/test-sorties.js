/* (04/11, Hakim pour papa : « un chiffre mesuré entre le moment où j'écris un mot et celui où il apparaît à l'écran de son téléphone,
   et entre le moment où je le dis et celui où il l'entend dans ses écouteurs Bluetooth » ; Ahmed : « ajoute tout ») ses sorties
   mesurées : l'horloge du Mac calée par la page, le texte jusqu'à l'écran, la voix jusqu'aux écouteurs : node --test test-sorties.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
function extraire(source, debut) {
  const i = source.indexOf(debut);
  assert.ok(i >= 0, debut);
  if (debut.startsWith('const ') || debut.startsWith('let ')) return source.slice(i, source.indexOf('\n', i) + 1);
  return source.slice(i, source.indexOf('\n}\n', i) + 3);
}
function page() {
  const journal = [];
  const ctx = { Date, Math, Number, String, journalVoix: (e, d) => journal.push([e, d]), calerHorlogeMac() {} };
  vm.createContext(ctx);
  vm.runInContext(['const horlogeMac', 'function depuisMac', 'const originesDites', 'function noterOrigine', 'function origineDe', 'function mesurerVoix']
    .map(d => extraire(PAGE, d)).join('\n') + '\nthis.h = horlogeMac; this.depuis = depuisMac; this.noter = noterOrigine; this.origine = origineDe; this.voix = mesurerVoix;', ctx);
  return { ctx, journal };
}

test('(04/11) l’horloge du Mac : sans calage, aucun chiffre ; calée, le délai depuis son envoi', () => {
  const { ctx } = page();
  assert.strictEqual(ctx.depuis(1000, 1500), null, 'pas encore calée : pas de chiffre faux');
  Object.assign(ctx.h, { decalage: 200, rtt: 40, t: 1 });          // l'horloge du Mac a 200 ms d'avance sur celle du téléphone
  assert.strictEqual(ctx.depuis(10_000, 10_100), 300, 'envoyé à 10 000 (Mac), affiché à 10 100 (téléphone) = 10 300 (Mac)');
  ctx.h.rtt = 2000;
  assert.strictEqual(ctx.depuis(10_000, 10_100), null, 'un aller-retour de 2 s : le calage ne vaut rien');
});

test('(04/11) sa voix jusqu’à tes écouteurs : le réseau, son attente, le calcul, la sortie Bluetooth, et le total', () => {
  const { ctx, journal } = page();
  Object.assign(ctx.h, { decalage: 0, rtt: 30, t: 1 });
  ctx.noter('Ta mère ? Elle va bien ?', 1000, 1150);                // parti du Mac à 1 000, reçu par la page à 1 150
  const u = { text: 'Elle va bien ?', _appelPage: 1400 };
  u._origine = ctx.origine(u.text);
  assert.strictEqual(u._origine.ts, 1000, 'retrouvée par son texte, même coupée par le lecteur');
  ctx.voix(u, { appel: 1405, calcule: 1700, ecrit: 1710, entendu: 1950, latence_ms: 230, sortie: 'bluetooth', prechargee: false });
  assert.deepStrictEqual(JSON.parse(JSON.stringify(journal)), [['sortie_voix', { sortie: 'bluetooth', prechargee: false, calcul_ms: 295, ecouteurs_ms: 240,
    latence_annoncee_ms: 230, page_ms: 5, reseau_ms: 150, attente_ms: 250, total_ms: 950 }]]);
  ctx.voix(u, { appel: 1405, calcule: 1700, ecrit: 1710, entendu: 1500, sortie: 'bluetooth' });
  assert.strictEqual(journal.length, 1, 'une sortie avant son écriture : pas de chiffre faux');
  ctx.voix({ text: 'x' }, { appel: 1, calcule: 2, ecrit: 3, entendu: 100, sortie: 'haut-parleur (2)' });
  assert.strictEqual(journal[1][1].sortie, 'autre', 'un nom de sortie inconnu : « autre » (le journal ne prend que des mots simples)');
  assert.strictEqual(journal[1][1].total_ms, undefined, 'sans origine connue : pas de total');
});

test('(04/11) la page : chaque pensée et chaque bout de message portent leur départ ; la bulle et le widget disent leur délai', () => {
  assert.match(PAGE, /montrerPensee\('🧠 il pense, sans le dire', texte, true\);\n      mesurerEcran\('pensee', o\.ts\);/);
  assert.match(PAGE, /noterOrigine\(texte, o\.ts\);[^\n]*\n    recevoirBout\(s, Number\(o\.n\) \|\| 0, o\.tour\); return;/);
  assert.match(PAGE, /noterOrigine\(p, o\.ts, recu\); etat\.lectureDe = m\.id; lecteur\.dire\(p\);/);
  assert.match(PAGE, /if \(!m\.cache && o\.x\.trim\(\)\) mesurerEcran\('message', o\.ts, recu\);/);
  assert.match(PAGE, /\.\.\.\(parolesDepuis \? \{ t_page: parolesDepuis \} : \{\}\)/, 'la bulle sait quand la page lui a donné ses mots');
  assert.match(PAGE, /window\.HakimVoixMesure = \(id, m\) => \{ const u = enAttente\.get\(id\);/);
  assert.match(PAGE, /u\._appelPage = Date\.now\(\); u\._origine = typeof origineDe === 'function' \? origineDe\(u\.text\) : null;/);
});

test('(04/11) le cockpit : l’instant de départ sur ses pensées et son texte ; ses sorties rangées avec ses entrées (fil_delais)', () => {
  assert.match(SRC, /if \(p === '\/api\/heure' && req\.method === 'GET'\)/);
  assert.match(SRC, /res\.write\(j\(o\.t === 'texte' \? \{ \.\.\.o, ts: Date\.now\(\) \} : o\) \+ '\\n'\)/);
  assert.strictEqual((SRC.match(/niveau: 'piste', n: m\.n, tour, pour[^\n]*ts: Date\.now\(\)[^\n]*\}\)\);/g) || []).length, 2, 'ses deux pistes');
  assert.match(SRC, /niveau: 'cerveau', pour: s0\.pour\.slice\(-300\), ts: Date\.now\(\) \}/);
  const ctx = { Number, Math, DELAIS: {} };
  vm.createContext(ctx);
  vm.runInContext(extraire(SRC, 'function noterSortie(') + '\nthis.noter = noterSortie;', ctx);
  ctx.noter({ e: 'sortie_texte', quoi: 'pensee', ou: 'page', total_ms: 320, reseau_ms: 300 });
  ctx.noter({ e: 'sortie_texte', quoi: 'paroles', ou: 'widget', page_ms: 940 });
  ctx.noter({ e: 'sortie_voix', sortie: 'bluetooth', total_ms: 950, reseau_ms: 150, attente_ms: 250, calcul_ms: 295, ecouteurs_ms: 240 });
  ctx.noter({ e: 'sortie_voix', sortie: 'haut_parleur', ecouteurs_ms: 60, total_ms: -5 });
  assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.DELAIS)), { sortie_texte_pensee: [320], sortie_texte_reseau: [300], sortie_texte_widget: [940],
    sortie_voix_total: [950], sortie_voix_reseau: [150], sortie_voix_attente: [250], sortie_voix_calcul: [295], sortie_voix_bluetooth: [240],
    sortie_voix_sortie: [60] }, 'Bluetooth à part du haut-parleur ; un délai négatif : jeté');
});

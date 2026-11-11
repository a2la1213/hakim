/* (11/11, le live TikTok : « réactif de fou les premières minutes, ensuite il se met à lagger ou bloquer sur le smartphone ») node --test test-page-cachee.js
   Mesuré en lecture seule pendant le live (08:39-09:15) : le Mac reste stable (son cerveau finit sa réponse en 4 à 8 s, Azure 1 à 1,5 s), mais côté
   téléphone, la page Parler (la WebView, cachée derrière TikTok) se fige : ses allers-retours vers le Mac prennent jusqu'à 5-10 s de plus que ceux de
   l'appli native (plats, 2,3 s), le premier morceau de sa voix sonne 4,5 à 9 s après sa synthèse (0,4 s d'habitude), et 12 « micro_bloque » repris en
   moins d'une seconde ; à mesure que le téléphone chauffe (38,8 → 42,7 °C, marge thermique à 1 : il bride ses cœurs à 27 %). Rejoué hors ligne sur
   la vraie conversation (Chromium du Mac) : chaque pensée sur ce que joue le téléphone redessinait tout le fil, 0,56 à 0,6 s par rendu, dont 0,34 s
   de dates (un formateur Intl fabriqué à chaque date).
   Ici : (1) page cachée, le fil n'est plus redessiné (une fois au retour) ; (2) les dates du fil par des formateurs faits une fois, même texte ;
   (3) la minuterie du micro en retard (la page figée) ne prend plus la page figée pour un micro bloqué et ne suspend plus le son. Chacun son témoin. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const fonction = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 3); };
const ligne = (src, debut) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); return src.slice(i, src.indexOf('\n', i)); };

// le fil : rendre et majMessage, avec un document dont on règle la visibilité ; htmlMessage remplacé par un repère
function fil(src = PAGE) {
  const el = { scrollHeight: 0, scrollTop: 0, clientHeight: 0, innerHTML: '', querySelector: () => null };
  const ecouteurs = {};
  const documentFaux = { visibilityState: 'hidden', addEventListener: (e, f) => { ecouteurs[e] = f; } };
  const ctx = { Math, Number, Date, String, FENETRE: 50, performance: { now: () => 0 }, document: documentFaux, $: () => el, esc: (s) => s, chargerApercus() {},
    jourMessage: () => 'lundi', htmlMessage: (m) => `[${m.id}]`, messageMasque: () => false, aDesPieces: () => false, piecesSeules: (m) => m,
    etat: { messages: [{ id: 'a', qui: 'u', texte: 'salut', ts: 1793030000000 }], aCote: [] } };
  vm.createContext(ctx);
  vm.runInContext([ligne(src, 'var rendu = '), fonction(src, 'filCache'), ligne(src, "if (typeof document !== 'undefined' && document.addEventListener) document.addEventListener('visibilitychange'"),
    fonction(src, 'quandMessage'), fonction(src, 'rendre'), fonction(src, 'majMessage'), 'this.rendre = rendre; this.maj = majMessage; this.rendu = rendu;'].join('\n'), ctx);
  return { ctx, el, doc: documentFaux, revenir: () => { documentFaux.visibilityState = 'visible'; ecouteurs.visibilitychange(); } };
}

test('page cachée (TikTok devant) : le fil n’est pas redessiné ; il l’est une seule fois quand elle revient', () => {
  const f = fil();
  for (let i = 0; i < 25; i++) f.ctx.rendre();
  f.ctx.maj({ id: 'a', qui: 'u', texte: 'salut' });
  assert.strictEqual(f.el.innerHTML, '', 'rien dessiné pendant qu’elle est cachée');
  assert.strictEqual(f.ctx.rendu.enAttente, 26);
  assert.strictEqual(f.ctx.rendu.differes, 25);
  f.revenir();
  assert.strictEqual(f.el.innerHTML, '<div class="jour">lundi</div>[a]', 'au retour : le fil à jour, d’un coup');
  assert.strictEqual(f.ctx.rendu.enAttente, 0);
  assert.strictEqual(f.ctx.rendu.n, 1, 'un seul rendu pour 26 demandes');
});

test('témoin : page visible, chaque rendu se fait tout de suite ; le garde coupé dans la source, la page cachée redessine à chaque fois', () => {
  const f = fil();
  f.doc.visibilityState = 'visible';
  f.ctx.rendre();
  assert.strictEqual(f.el.innerHTML, '<div class="jour">lundi</div>[a]');
  const coupe = PAGE.replace("  if (typeof filCache === 'function' && filCache()) { rendu.enAttente++; rendu.differes++; return; }   // (11/11) cachée : plus tard\n", '');
  assert.notStrictEqual(coupe, PAGE);
  const g = fil(coupe);
  g.ctx.rendre(); g.ctx.rendre();
  assert.strictEqual(g.el.innerHTML, '<div class="jour">lundi</div>[a]', 'sans le garde, la page cachée redessine (le défaut d’avant)');
  assert.strictEqual(g.ctx.rendu.n, 2);
});

// les dates : un Intl qui compte ses formateurs
function dates(src = PAGE) {
  let fabriques = 0;
  const VraiIntl = Intl;
  const IntlCompte = { DateTimeFormat: function (...a) { fabriques++; return new VraiIntl.DateTimeFormat(...a); } };
  const ctx = { Date, String, Number, Intl: IntlCompte, esc: (s) => s };
  vm.createContext(ctx);
  vm.runInContext([ligne(src, 'const FORMATEURS_FR = '), fonction(src, 'dateFr'), ligne(src, 'const heureCourteFr = '), ligne(src, 'const heureMessage = '),
    ligne(src, 'const jourMessage = ')].join('\n').replace(/^const /gm, 'var ') + '\nthis.heure = heureMessage; this.jour = jourMessage; this.hc = heureCourteFr;', ctx);
  return { ctx, fabriques: () => fabriques };
}

test('les dates du fil : le même texte qu’avant, trois formateurs pour 150 messages (au lieu d’un par date)', () => {
  const d = dates();
  const T0 = 1794384725039;
  for (let i = 0; i < 150; i++) {
    const t = T0 - i * 3_600_000 * 7;
    const date = new Date(t);
    assert.strictEqual(d.ctx.jour(t), date.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }));
    assert.strictEqual(d.ctx.heure(t), `<span class="heure" title="${date.toLocaleString('fr-FR')}">${date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</span>`);
    assert.strictEqual(d.ctx.hc(t), date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }));
  }
  assert.strictEqual(d.fabriques(), 3, 'un formateur par forme de date, fait une seule fois');
  assert.strictEqual(d.ctx.heure(0), '', 'sans heure connue : rien');
});

test('témoin : sans le cache des formateurs, un formateur est fabriqué à chaque date', () => {
  const sansCache = PAGE.replace("  let f = FORMATEURS_FR[cle];\n  if (f === undefined) {", "  let f;\n  {");
  assert.notStrictEqual(sansCache, PAGE);
  const d = dates(sansCache);
  for (let i = 0; i < 50; i++) d.ctx.jour(1794384725039 - i * 86_400_000);
  assert.strictEqual(d.fabriques(), 50);
});

/* la minuterie du micro : la page figée n'est pas un micro bloqué */
function veille(src = PAGE, { trameIlYa = 3000 } = {}) {
  let t = 1_800_000_000_000;
  const journal = [], relances = [], bandeau = [];
  const capteur = { derniereTrame: t - trameIlYa, pisteMuette: false };
  const ctx = { Math, Promise, journalVoix: (e, o) => journal.push([e, o]), montrerHorsLigne: (x) => bandeau.push(x),
    Date: class extends Date { constructor(...a) { super(...(a.length ? a : [t])); } static now() { return t; } },
    etat: { conversation: { capteur } }, horsLigne: { depuis: 0 }, document: { visibilityState: 'hidden' },
    actx: { state: 'running', suspend: async () => { relances.push('s'); }, resume: async () => { relances.push('r'); } },
    $: () => ({ addEventListener() {} }), setInterval() {}, finirConversation() {}, basculerConversation() {}, setTimeout() {} };
  vm.createContext(ctx);
  const d = src.indexOf('const veilleMicro'), f = src.indexOf("$('horsLigne').addEventListener('click'");
  vm.runInContext(src.slice(d, f) + 'this.surveiller = surveillerMicro;', ctx);
  return { ctx, capteur, journal, relances, bandeau, avancer: (ms) => { t += ms; }, maintenant: () => t };
}

test('la page figée 3,5 s (sa minuterie en retard) : « page_figee », pas de micro bloqué, le son n’est pas suspendu ; le tic suivant tranche', async () => {
  const v = veille(PAGE, { trameIlYa: 0 });
  v.ctx.surveiller();                                     // tout va bien
  v.avancer(3500);                                        // la page s'est figée : la trame d'il y a 3,5 s attend son tour
  v.ctx.surveiller(); await new Promise(r => setImmediate(r));
  assert.deepStrictEqual(v.journal.map(x => x[0]), ['page_figee']);
  assert.strictEqual(v.journal[0][1].ms, 3500);
  assert.deepStrictEqual(v.relances, [], 'son pas suspendu : sa voix continue');
  v.capteur.derniereTrame = v.maintenant() + 20;          // les trames en attente passent
  v.avancer(1000); v.ctx.surveiller();
  assert.deepStrictEqual(v.journal.map(x => x[0]), ['page_figee'], 'à l’heure : le micro va bien');
  // un vrai micro bloqué reste vu : à l'heure, plus aucune trame depuis 3 s
  v.avancer(1000); v.capteur.derniereTrame = v.maintenant() - 3000;
  v.ctx.surveiller(); await new Promise(r => setImmediate(r));
  assert.deepStrictEqual(v.journal.map(x => x[0]), ['page_figee', 'micro_bloque']);
  assert.deepStrictEqual(v.relances, ['s', 'r']);
});

test('témoin : le garde de la page figée coupé dans la source, le même retard redevient un « micro bloqué » qui suspend le son', async () => {
  const coupe = PAGE.replace('  if (tic && maintenantTic - tic > 2000) {', '  if (false) {');
  assert.notStrictEqual(coupe, PAGE);
  const v = veille(coupe, { trameIlYa: 0 });
  v.ctx.surveiller();
  v.avancer(3500);
  v.ctx.surveiller(); await new Promise(r => setImmediate(r));
  assert.deepStrictEqual(v.journal.map(x => x[0]), ['micro_bloque']);
  assert.deepStrictEqual(v.relances, ['s', 'r']);
});

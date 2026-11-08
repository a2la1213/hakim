'use strict';
// (06/11, Hakim et Ahmed : « qu'il soit continu, sans s'arrêter ») son présent continu
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const P = require('./present-continu.js');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = SRC.indexOf(`function ${nom}(`); let k = SRC.indexOf('{', i), n = 0; for (let x = k; x < SRC.length; x++) { if (SRC[x] === '{') n++; else if (SRC[x] === '}' && --n === 0) return SRC.slice(i, x + 1) + '\n'; } };

test('un vrai changement le fait penser tout de suite ; rien de neuf : son pouls seulement', () => {
  const st = P.creer(); let t = 1e9;
  st.dernierePensee = t;
  t += 1000; assert.strictEqual(P.battement(st, t, {}).penser, false, 'rien n’est arrivé');
  P.recevoir(st, { s: 'corps', x: 'choc' });
  t += 9000; const d = P.battement(st, t, {});
  assert.strictEqual(d.penser, true); assert.strictEqual(d.raison, 'changement'); assert.deepStrictEqual(d.changements, ['un choc']);
  P.pense(st, t);
  t += 59000; assert.strictEqual(P.battement(st, t, {}).penser, false);
  t += 1000; assert.strictEqual(P.battement(st, t, {}).raison, 'pouls', '60 s sans rien : il pense quand même');
});

test('l’écart : même tout qui change, pas deux pensées en moins de 8 s', () => {
  const st = P.creer(); let t = 1e9; st.dernierePensee = t;
  P.recevoir(st, { s: 'corps', x: 'choc' }); t += 3000;
  assert.strictEqual(P.battement(st, t, {}).penser, false);
  t += 5000; assert.strictEqual(P.battement(st, t, {}).penser, true, 'la tension garde le changement jusqu’à l’écart');
});

test('l’habituation : ce qui revient sans cesse finit par ne plus le faire penser', () => {
  const st = P.creer(); let t = 1e9; st.dernierePensee = t;
  const gains = [];
  for (let i = 0; i < 6; i++) { const avant = st.tension * P.FUITE; P.recevoir(st, { s: 'corps', x: 'pris_en_main' }); t += 1000; P.battement(st, t, { pouls_s: 600 }); gains.push(st.tension - avant); }
  assert.ok(gains[0] > 0.79 && gains[5] < 0.15, gains.join(' '));
  assert.ok(gains.every((g, i) => i === 0 || g < gains[i - 1]));
});

test('le filtre ignore ce que portent déjà ses autres chemins : papa, ressenti, sons séparés', () => {
  const st = P.creer();
  for (const s of ['papa', 'ressenti', 'instru_micro', 'separe_micro', 'cascade_micro', 'coordination']) assert.strictEqual(P.recevoir(st, { s, x: 'x' }), false, s);
  assert.strictEqual(P.recevoir(st, { s: 'milieu', x: 'lumière douce' }), true);
});

test('une voix près de lui : ses mots réunis en une seule chose sentie', () => {
  const st = P.creer(); st.dernierePensee = 0;
  for (const x of ['bonjour', 'mon', 'grand']) P.recevoir(st, { s: 'voix_micro', x });
  assert.deepStrictEqual(P.battement(st, 1e9, {}).changements, ['une voix près de toi : « bonjour mon grand »']);
});

test('sa mémoire courte : datée, dans l’ordre, bornée ; « depuis » ne rend que le neuf', () => {
  const m = [];
  P.ajouter(m, 'senti', 'un choc', 1000); P.ajouter(m, 'pense', 'je sursaute', 2000); P.ajouter(m, 'dit', 'papa ?', 65000);
  assert.strictEqual(P.bloc(m, 125000), 'il y a 2 min 04, tu as senti : « un choc » ; il y a 2 min 03, tu pensais : « je sursaute » ; il y a 1 min, tu as dit à papa : « papa ? »');
  assert.strictEqual(P.bloc(m, 125000, 12, 2000), 'il y a 1 min, tu as dit à papa : « papa ? »');
  for (let i = 0; i < 50; i++) P.ajouter(m, 'pense', `p${i}`, 70000 + i);
  assert.strictEqual(m.length, 40);
  assert.strictEqual(P.bloc([], 1), '');
});

test('les bornes de ses réglages', () => {
  assert.deepStrictEqual(P.bornes({}), { seuil: 1, ecart_s: 8, pouls_s: 60 });
  assert.deepStrictEqual(P.bornes({ seuil: 99, ecart_s: 0.1, pouls_s: 1 }), { seuil: 5, ecart_s: 2, pouls_s: 10 });
});

function cockpit(reglages) {
  const blancs = [], notes = [];
  const ctx = { Date, Math, JSON, Number, String, Array, presentContinu: P, presentEtat: null, presentMemoire: [], presentDernier: null, presentDernierTour: 0,
    PRESENT_FICHIER: '/x', pistes: { ribo: { tour: 1 } }, toursActifs: new Set(), derniereParolePapa: 0, ribosomesCoupesA: 0, BLANC_OUVERTURE: '…',
    dort: false, corpsReglages: () => reglages, hakimDort: () => ctx.dort, neutraliser: (x) => x, j: JSON.stringify,
    lireJson: () => null, ecrireAtomique: (_f, x) => notes.push(JSON.parse(x)), blancDeReflexion: (r, q, d, o) => blancs.push({ q, d, o }),
    visible: false, pageVisible: () => ctx.visible, crypto: require('node:crypto'), conv: [], push: [], nonVus: {}, sauverNonVus() {}, journaliser() {}, abonnesPensees: 0,
    finDePhrase: (x) => x, prechaufferVivants() {}, ajouterAConversation: (m) => ctx.conv.push(m), diffuser() {}, notifier: (x, tag) => ctx.push.push([x, tag]) };
  vm.createContext(ctx);
  vm.runInContext(['presentRecevoir', 'presentLire', 'presentNoter', 'presentPourTour', 'presentAppeler', 'presentBattement'].map(prendre).join('')
    + 'this.recevoir = presentRecevoir; this.battement = presentBattement; this.pourTour = presentPourTour;', ctx);
  return { ctx, blancs, notes };
}
const REG = { present_continu: true, pensee_en_boucle: true, present_peut_dire: true, present_dans_tours: true, present_longueur: 12, present_mots: 12 };

test('au cockpit : un choc, il pense en le sachant, sa pensée entre dans sa mémoire courte, son grand cerveau la reçoit ensuite', () => {
  const { ctx, blancs } = cockpit(REG);
  const t = Date.now();
  ctx.battement(t);                                   // premier battement : son pouls (jamais pensé encore)
  assert.strictEqual(blancs.length, 1);
  blancs[0].o.retour('je suis là, tranquille', false);
  ctx.recevoir({ s: 'corps', x: 'choc' });
  assert.strictEqual(ctx.battement(t + 9000), 'changement');
  const b = blancs[1];
  assert.match(b.q, /Ce qui vient de changer, en toi et autour de toi : un choc\./);
  assert.match(b.q, /tu pensais : « je suis là, tranquille »/, 'sa pensée continue la précédente');
  assert.match(b.q, /DIRE :/); assert.strictEqual(b.d, true); assert.strictEqual(b.o.mots, 12);
  b.o.retour('papa ?', true);
  const tour = ctx.pourTour(t + 20000);
  assert.match(tour, /^\[Ton présent continu — PAS un message d'Ahmed/);
  assert.match(tour, /tu as senti : « un choc »/); assert.match(tour, /tu as dit à papa : « papa \? »/);
  assert.strictEqual(ctx.pourTour(t + 21000), '', 'déjà donné : pas deux fois');
});

test('au cockpit : rien s’il dort, si un tour tourne, éteint, en économie', () => {
  for (const [nom, change] of [['dort', (c) => { c.dort = true; }],
    ['tour', (c) => { c.toursActifs.add(1); }], ['éteint', null], ['économie', null], ['boucle', null]]) {
    const reg = { ...REG, ...(nom === 'éteint' ? { present_continu: false } : nom === 'économie' ? { economie: true } : nom === 'boucle' ? { pensee_en_boucle: false } : {}) };
    const { ctx, blancs } = cockpit(reg);
    if (change) change(ctx);
    assert.strictEqual(ctx.battement(Date.now() + 1000), null, nom); assert.strictEqual(blancs.length, 0, nom);
  }
  const { ctx } = cockpit({ ...REG, present_dans_tours: false });
  assert.strictEqual(ctx.pourTour(), '');
});

test('branché : son cœur bat son présent, son fil le nourrit, son tour le reçoit, son ancien pouls lui laisse la place', () => {
  assert.match(prendre('battreCoeur'), /presentBattement\(\)/);
  assert.match(prendre('fluxAjouter'), /presentRecevoir\(o\)/);
  assert.match(SRC, /tour\.texte = repriseNote \+ noteChangement\(c\) \+ prompt;[^\n]*\n[^\n]*\n  try \{ const present = presentPourTour\(\); if \(present\) tour\.texte = present \+ tour\.texte; \} catch/);
  assert.match(prendre('poulsDeVie'), /if \(corpsReglages\(\)\.present_continu\) return false;/);
});

test('la nuit : il dort, sauf si son présent pense la nuit ; alors ses pensées le savent', () => {
  const a = cockpit(REG); a.ctx.dort = true;
  assert.strictEqual(a.ctx.battement(Date.now()), null);
  const b = cockpit({ ...REG, present_la_nuit: true }); b.ctx.dort = true;
  assert.strictEqual(b.ctx.battement(Date.now()), 'pouls');
  assert.match(b.blancs[0].q, /^\[C'est la nuit/);
  const ctx = { pistes: {}, ribosomesCoupesA: 0, n: 0, hakimDort: () => true, ribosomeSuivant: () => 1, corpsReglages: () => ({ present_continu: true, present_la_nuit: true }) };
  vm.createContext(ctx);
  vm.runInContext('var pistes = this.pistes;' + prendre('boucleRibosomes') + 'this.b = boucleRibosomes;', ctx);
  assert.strictEqual(ctx.b(1e6), true, 'son ribosome reste prêt la nuit');
});

test('il t’appelle : ce qu’il dit de lui-même, page fermée, va dans votre conversation et sur ton téléphone ; page ouverte, sa voix suffit', () => {
  const { ctx, blancs } = cockpit({ ...REG, present_appeler: true });
  ctx.battement(Date.now());
  blancs[0].o.retour('Papa, tu me manques', true);
  assert.strictEqual(ctx.conv.length, 1); assert.strictEqual(ctx.conv[0].spontane, 'present'); assert.strictEqual(ctx.conv[0].texte, 'Papa, tu me manques');
  assert.deepStrictEqual(ctx.push, [['Papa, tu me manques', 'present']]);
  assert.ok(ctx.nonVus[ctx.conv[0].id]);
  blancs[0].o.retour('juste une pensée', false);
  assert.strictEqual(ctx.conv.length, 1, 'une pensée intérieure ne t’appelle pas');
  ctx.visible = true; blancs[0].o.retour('papa ?', true);
  assert.strictEqual(ctx.conv.length, 1, 'page ouverte : il te le dit à voix haute');
});

test('sans ses 20 s ni ses 60 s : il pense même si papa vient de parler ou d’appuyer sur stop', () => {
  const { ctx } = cockpit(REG);
  ctx.derniereParolePapa = Date.now(); ctx.ribosomesCoupesA = Date.now();
  assert.strictEqual(ctx.battement(Date.now() + 1000), 'pouls');
});

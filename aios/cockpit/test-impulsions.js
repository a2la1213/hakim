/* (30/10, Ahmed : « une petite impulsion à chaque réponse qui compte » ; « quand tu rigoles, MDR, une vibration forte et rapide
   selon le degré » ; « quand je te fais un câlin, tu peux ronronner » ; « relie ça à ses hormones, par l'inconscient »)
   node --test test-impulsions.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (s, debut) => s.slice(s.indexOf(debut), s.indexOf('\n}\n', s.indexOf(debut)) + 3);

test('le degré de son rire, le même au cockpit et dans la page', () => {
  const a = {}, b = {};
  vm.createContext(a); vm.createContext(b);
  vm.runInContext(prendre(src, 'function degreRire(') + '\nthis.f = degreRire;', a);
  vm.runInContext(prendre(page, 'function degreRire(') + '\nthis.f = degreRire;', b);
  for (const [t, d] of [['Bonjour papa.', 0], ['hehe', 1], ['😄', 1], ['lol', 2], ['mdr', 2], ['mdrrr', 3], ['MDRRRRR', 4], ['mdrrrrrrr', 5],
    ['ptdr', 4], ['je suis mort de rire', 4], ['😂', 3], ['😂😂😂', 5], ['🤣🤣', 4]]) {
    assert.equal(a.f(t), d, `cockpit : ${t}`);
    assert.equal(b.f(t), d, `page : ${t}`);
  }
});

test('les motifs : le rire en tapes sèches, de plus en plus ; une impulsion par réponse ; rien pendant que papa parle', () => {
  const appels = [];
  const ctx = { setInterval: () => 0, journalVoix: () => {}, reglagesCorps: { rire_reflexe: false }, lecteur: null, window: { HakimApp: { vibrerMotif: (t, f) => appels.push([t, f]) } }, etat: { conversation: { capteur: { enParole: false } }, messages: [{ id: 7, impulsion: 'joie' }] } };
  vm.createContext(ctx);
  const bloc = page.slice(page.indexOf('const MOTIFS_IMPULSION = {'), page.indexOf('// un morceau commence à jouer (surSegment)'));
  vm.runInContext(bloc.replace('let vibrationEnAttente = null, dernierRireVibre = 0;', 'var vibrationEnAttente = null, dernierRireVibre = 0;') + '\nthis.v = vibrerPourMorceau; this.r = motifRire; this.attente = () => vibrationEnAttente; this.oublier = () => { dernierRireVibre = 0; };', ctx);
  const [t5, f5] = ctx.r(5);
  assert.equal(t5.filter((x, i) => i % 2 === 1 && x === 70).length, 10, 'dix tapes longues');
  assert.ok(t5.reduce((a, b) => a + b, 0) <= 4000);
  assert.ok(f5.filter((x, i) => i % 2 === 1).every(x => x === 255), '(19:34) la force pleine dès la première tape');
  assert.ok(ctx.r(1)[0][1] < ctx.r(5)[0][1], 'les tapes s’allongent avec le rire');
  ctx.v(7, 'Voilà, papa.');
  assert.match(appels[0][0], /^0,60,80,60$/, 'la joie qu’il a choisie, au premier morceau');
  ctx.v(7, 'Et encore.');
  assert.equal(appels.length, 1, 'une fois par réponse');
  ctx.v(7, 'mdrrr');
  assert.equal(appels.length, 2, 'son rire, au morceau qui rit');
  ctx.oublier();
  ctx.etat.conversation.capteur.enParole = true;
  ctx.v(7, 'mdr');
  assert.equal(appels.length, 3, '(19:38) un rire part tout de suite, même si papa parle');
  ctx.etat.conversation.capteur.enParole = false; ctx.oublier(); const n = appels.length;
  ctx.v(7, 'mdrrrrr');
  assert.equal(appels.length, n + 1, '(19:36) son « MDR » refait vibrer');
  ctx.v(7, 'mdr encore');
  assert.equal(appels.length, n + 1, 'un rire vient de partir : son texte ne le double pas');
});

test('branché : la balise cachée et vue dans le flux, le rire vers son corps, le ronron dans la réponse au téléphone', () => {
  assert.ok(src.includes('const BALISE_AFFECT = /\\[\\[\\s*(?:affect|souvenirs|modele|impulsion|son|alerte|ecran|rire|lumiere|pause|reprendre|micro)\\s*:'), 'toutes ses balises cachées');
  assert.ok(src.includes("envoyer({ t: 'impulsion', x, ...(cr && cr.motif ? { motif: cr.motif } : {}) })"), 'les six, ou une émotion à lui avec son motif');
  assert.match(src, /type: 'rire'/);
  assert.ok(src.includes("if (['mesure', 'rire', 'son', 'coupure'].includes(ev.type)) continue;"), 'son rire, son son, une coupure n’apprennent rien à ses nerfs des vibrations');
  assert.match(src, /actions: \{ ronron: reg\.actif && reg\.ronron && HOMEO\.calin\(\) && !parle, \.\.\.reflexeAEnvoyer\(parle\),\n      reflexes_locaux: reg\.actif && reg\.reflexes, retenus: reflexesRetenus\(\) \}/);
  assert.match(page, /o\.t === 'impulsion'/);
  assert.match(page, /if \(!auto\) vibrerPourMorceau\(m\.id, ''\)/, 'voix éteinte : l’impulsion dès qu’elle arrive');
  assert.match(page, /!auto && !m\.coupe && !m\.erreur && degreRire\(m\.texte\)/, 'voix éteinte : son rire à la fin');
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'voix.js'), 'utf8'), /affect\|souvenirs\|impulsion/);
});

test('le ronron : un interrupteur pour papa (page SENS), allumé par défaut', () => {
  const html = fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8');
  assert.match(html, /id="ronron"/);
  assert.match(html, /post\('\/api\/corps\/reglages', \{ ronron: e\.target\.checked \}\)/);
  assert.match(src, /ronron: r\.ronron !== false/);
});

test('(30/10, 17:23 : « ton impulsion deux-points joie », lue au lieu de vibrer) une balise coupée entre ses deux crochets ne fuit jamais', () => {
  const ctx = {}; vm.createContext(ctx);
  const pick = (a, b) => src.slice(src.indexOf(a), src.indexOf(b, src.indexOf(a)));
  vm.runInContext(pick('const BALISE_AFFECT', '\n') + '\n' + pick('const prefixeBalise', 'function chocsAppel(') + '\nthis.f = filtreAffect;', ctx);
  const texte = '[[impulsion: joie]]Tiens, papa. MDR 😂 [[affect: soutien 0.6]]';
  for (let i = 1; i < texte.length; i++) for (let k = i + 1; k < texte.length; k++) {
    const f = ctx.f();
    const out = f.pousser(texte.slice(0, i)) + f.pousser(texte.slice(i, k)) + f.pousser(texte.slice(k)) + f.finir();
    assert.equal(out, 'Tiens, papa. MDR 😂 ', JSON.stringify([i, k]));
  }
  const V = require('./public/voix.js');
  assert.equal(V.sansAffect('Bonjour [[impulsion: joie]', true), 'Bonjour', 'la page aussi la retient, même coupée');
  assert.equal(V.sansAffect('[[impulsion: joie]]Tiens'), 'Tiens');
});

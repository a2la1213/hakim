/* (30/10, 21:29, Ahmed via Hakim : « son orbe part grave en couille ») l'orbe ne doit jamais sauter quand son état change
   (écoute, pense, parle, repos) : la phase avançait en « temps depuis l'ouverture × vitesse », si bien qu'après dix minutes
   un changement de vitesse la téléportait de centaines de radians. node --test test-orbe.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const src = fs.readFileSync(path.join(__dirname, 'public', 'orbe.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');

function orbe() {
  let rappel = null, maintenant = 0;
  const angles = [], conics = [];
  const degrade = () => ({ addColorStop() {} });
  const ctx = new Proxy({ createRadialGradient: degrade, createLinearGradient: degrade,
    createConicGradient: (a) => { angles.push(a); const arrets = []; conics.push(arrets); return { addColorStop: (x, c) => arrets.push(c) }; } },
    { get: (o, k) => (k in o ? o[k] : () => {}) });
  const canvas = { getContext: () => ctx, clientWidth: 100, clientHeight: 100, width: 0, height: 0, isConnected: true, offsetParent: {} };
  const fen = { devicePixelRatio: 1 };
  const c = { window: fen, Math, performance: { now: () => maintenant }, document: { hidden: false },
    requestAnimationFrame: (f) => { rappel = f; return 1; }, cancelAnimationFrame() {} };
  vm.createContext(c);
  vm.runInContext(src, c);
  const o = fen.Orbe.creer(canvas, {});
  const image = (ms) => { maintenant = ms; rappel(ms); return angles[angles.length - 1]; };
  const couleurs = () => conics[conics.length - 1];
  return { o, image, couleurs };
}

test('son orbe ne saute pas quand son état change, même après une longue conversation', () => {
  const { o, image } = orbe();
  o.mode('ecoute');
  let t = 0;
  for (; t <= 600000; t += 1000) image(t);                    // dix minutes ouverte
  const avant = image(t);
  o.mode('pense');                                            // papa se tait : il réfléchit
  const apres = image(t + 16);
  assert.ok(Math.abs(apres - avant) < 0.1, `un saut de ${Math.abs(apres - avant).toFixed(1)} rad`);
  o.mode('parle'); o.mode('ecoute'); o.mode('repos');
  const encore = image(t + 32);
  assert.ok(Math.abs(encore - apres) < 0.1, `un saut de ${Math.abs(encore - apres).toFixed(1)} rad`);
});

test('elle tourne toujours, plus vite quand il pense ; un retour d’arrière-plan ne la fait pas bondir', () => {
  const { o, image } = orbe();
  const seconde = (debut) => { const a = image(debut); let z = a; for (let t = debut + 16; t <= debut + 1000; t += 16) z = image(t); return z - a; };
  const repos = seconde(0);
  assert.ok(repos > 0.1, 'elle tourne');
  o.mode('pense');
  seconde(1016);                                              // le temps qu'elle prenne son élan
  const pense = seconde(2032);
  assert.ok(pense > repos * 2, 'plus vite quand il pense');
  const p1 = image(3048);
  const b = image(3048 + 120000);                              // deux minutes cachée, puis revenue
  assert.ok(Math.abs(b - p1) < 0.2, 'pas de bond au retour');
});

test('quand il a quelque chose à dire, elle grossit en douceur et ne clignote pas', () => {
  assert.match(html, /\.orbe-tete\.veut-parler, #orbeScene\.veut-parler \{ scale: 1\.25;/, 'le grossissement glisse (transition sur scale)');
  assert.match(html, /#orbeScene \{ transition: scale/);
  assert.match(html, /@keyframes veutParler \{ 0%, 100% \{ transform: scale\(1\); \} 50% \{ transform: scale\(1\.1\); \} \}/, 'la respiration part de sa taille');
  assert.match(page, /veutDepuis/, 'il faut que l’envie tienne un moment pour qu’elle grossisse ou dégonfle');
});

test('(21:36) elle prend la couleur de celui qui a la parole : papa, lui, ou les deux mêlées', () => {
  const { o, image, couleurs } = orbe();
  o.humeur('calme');
  let t = 0;
  const vivre = () => { for (let k = 0; k < 400; k++) image((t++) * 16); return couleurs().map(c => c.match(/\d+/g).slice(0, 3).map(Number)); };
  const proche = (a, b, quoi) => assert.ok(a.every((x, i) => Math.abs(x - b[i]) <= 2), `${quoi} : ${a} au lieu de ${b}`);
  const TURQUOISE = [45, 212, 191], CIEL = [14, 165, 233];
  // (05/11, Ahmed : « une seule couleur : celle de l'humeur de Hakim »)
  for (const q of ['papa', 'hakim', 'partage', 'coupe']) { o.parole(q); const c = vivre(); proche(c[0], TURQUOISE, q); proche(c[1], CIEL, q); }
  // qui a la parole, côté page
  const i = page.indexOf('function quiALaParole() {'), f = page.slice(i, page.indexOf('\n}\n', i) + 2);
  const qui = (etat, reglagesCorps = {}, actif = false, motDirectJusqua = 0) => {
    const c = vm.createContext({ Date, etat: { micro: null, flux: null, conversation: null, ...etat }, reglagesCorps, lecteur: { actif }, motDirectJusqua });
    vm.runInContext(f, c); return c.quiALaParole();
  };
  const conv = (capteur) => ({ conversation: { capteur } });
  assert.equal(qui(conv({ enParole: false })), 'papa', 'au calme, la parole est à papa');
  assert.equal(qui(conv({ estMuet: true })), 'hakim', 'micro coupé : à lui');
  assert.equal(qui(conv({ enParole: true })), 'papa', 'papa parle, oreille fermée');
  assert.equal(qui(conv({ enParole: true }), { oreille: true }), 'partage', 'papa parle, son oreille peut le couper');
  assert.equal(qui(conv({ enParole: true }), { oreille: true, oreille_hakim_fermee: true }), 'papa', 'il a fermé son oreille');
  assert.equal(qui(conv({ enParole: true }), {}, true), 'hakim', 'sa voix');
  assert.equal(qui(conv({}), {}, false, Date.now() + 5000), 'hakim', 'son petit mot');
  assert.equal(qui({ flux: {}, ...conv({}) }), 'hakim', 'il prépare sa réponse');
  assert.equal(qui({}), null, 'hors conversation : comme avant');
});

test('(05/11) l’orbe bouge avec le plus fort des deux, même quand ils se chevauchent', () => {
  const P = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  assert.match(P, /return \[v, m, tel\]\.filter\(Boolean\)\.sort\(\(a, b\) => b\.niveau - a\.niveau\)\[0\] \|\| null;/);
});

test('(09/11) invisible, elle ne demande plus une image à chaque rafraîchissement de l’écran ; elle repart dès que la page revient', () => {
  let rafs = 0, rappel = null, minuterie = null, surVisibilite = null, peintes = 0;
  const degrade = () => ({ addColorStop() {} });
  const ctx = new Proxy({ createRadialGradient: degrade, createLinearGradient: degrade, createConicGradient: degrade,
    clearRect: () => { peintes++; } }, { get: (o, k) => (k in o ? o[k] : () => {}) });
  const canvas = { getContext: () => ctx, clientWidth: 100, clientHeight: 100, width: 0, height: 0, isConnected: true, offsetParent: {} };
  const document = { hidden: false, addEventListener: (n, f) => { if (n === 'visibilitychange') surVisibilite = f; } };
  const fen = { devicePixelRatio: 1 };
  const c = { window: fen, Math, performance: { now: () => 0 }, document,
    requestAnimationFrame: (f) => { rafs++; rappel = f; return rafs; }, cancelAnimationFrame() { rappel = null; },
    setTimeout: (f) => { minuterie = f; return 7; }, clearTimeout: () => { minuterie = null; } };
  vm.createContext(c); vm.runInContext(src, c);
  const o = fen.Orbe.creer(canvas, {});
  const tour = (t) => { const f = rappel; rappel = null; if (f) f(t); };
  tour(16); tour(32);
  assert.equal(peintes, 2, 'visible : elle peint');
  document.hidden = true;                                     // l'appli la cache (fenêtre de 2 px)
  const avant = rafs;
  tour(48);
  assert.equal(rafs, avant, 'cachée : plus aucune image demandée');
  assert.equal(rappel, null);
  assert.equal(typeof minuterie, 'function', 'un coup d’œil plus tard');
  minuterie(); tour(64);                                      // toujours cachée : elle se rendort
  assert.equal(peintes, 2, 'rien peint cachée');
  document.hidden = false; surVisibilite();                   // la page revient
  tour(80);
  assert.equal(peintes, 3, 'elle repart tout de suite');
  o.arreter();
  document.hidden = true; tour(96); assert.equal(rappel, null);
});

test('(09/11) le cercle de la caméra ne suit l’orbe image par image que tant qu’il est dans l’orbe ; son avatar se repose page cachée', () => {
  const i = page.indexOf('let suiviOrbe = 0;'), f = page.slice(i, page.indexOf('function cameraDansOrbe()', i));
  const classes = new Set(); let rafs = 0, rappel = null, places = 0;
  const c = vm.createContext({ etat: { vision: null }, $: () => ({ classList: { contains: (k) => classes.has(k) } }),
    placerDansOrbe: () => { places++; }, requestAnimationFrame: (fn) => { rafs++; rappel = fn; return rafs; } });
  vm.runInContext(`${f}\nfunction cameraDansOrbe() { if (!suiviOrbe) suivreOrbe(); }`, c);
  c.cameraDansOrbe();
  assert.equal(rafs, 0, 'caméra éteinte : aucune boucle');
  c.etat.vision = {}; classes.add('dans-orbe');
  c.cameraDansOrbe(); c.cameraDansOrbe();
  assert.equal(rafs, 1, 'une seule boucle');
  rappel(); rappel();
  assert.equal(rafs, 3, 'elle suit l’orbe');
  classes.delete('dans-orbe'); rappel();
  assert.equal(rafs, 3, 'sortie de l’orbe : la boucle s’arrête');
  assert.match(page, /classList\.add\('dans-orbe'\);\n  cameraDansOrbe\(\);/);
  assert.doesNotMatch(page, /function suivreOrbe\(\) \{ placerDansOrbe\(\); requestAnimationFrame\(suivreOrbe\); \}/);
  const av = fs.readFileSync(path.join(__dirname, 'public', 'avatar.js'), 'utf8');
  assert.equal((av.match(/document\.hidden\) \{ boucle = -1; attente = setTimeout\(tour, 250\); return; \}/g) || []).length, 2, 'les deux avatars');
});

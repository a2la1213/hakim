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
  const ROSE = [249, 168, 212], TURQUOISE = [45, 212, 191], CIEL = [14, 165, 233];
  o.parole('papa');
  proche(vivre()[0], ROSE, 'papa : son rose violet');
  o.parole('hakim');
  let c = vivre(); proche(c[0], TURQUOISE, 'lui : son humeur'); proche(c[1], CIEL, 'lui : son humeur');
  o.parole('partage');
  c = vivre(); proche(c[0], ROSE, 'partagée : papa'); proche(c[1], CIEL, 'partagée : lui');
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

test('(22:44) quand la parole est à lui, l’orbe ne bouge qu’avec sa voix, jamais avec celle de papa', () => {
  const i = page.indexOf('function niveauCourant() {'), f = page.slice(i, page.indexOf('\n}\n', i) + 2);
  const niveau = (qui, enParole = true) => {
    const c = vm.createContext({ quiALaParole: () => qui, niveauVoix: () => ({ niveau: 0.2, bandes: [0.2, 0.2, 0.2] }),
      etat: { conversation: { capteur: { enParole } }, niveauMicro: 0.9, micro: null } });
    vm.runInContext(f, c); return c.niveauCourant().niveau;
  };
  assert.equal(niveau('hakim'), 0.2, 'il prépare ou parle : sa voix, pas la tienne');
  assert.equal(niveau('coupe'), 0.2, 'il a coupé ton micro');
  assert.equal(niveau('papa'), 0.9, 'ta parole : ta voix');
  assert.equal(niveau('partage'), 0.9);
});

/* La caméra de Parler (24/10, idées de Hakim, accord d'Ahmed) : node --test test-camera.js
   L'aperçu flottant garde sa place (en fractions de l'écran) ; personne dans le cadre : dit après 30 s, caméra éteinte
   après 3 min ; la caméra arrière n'analyse aucun visage. Les fonctions sont lues dans parler.js et vision.js. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
function page({ largeur = 400, hauteur = 800, stock = {} } = {}) {
  let t = 1_800_000_000_000;
  const classes = new Set(['flottante']), el = {
    classList: { add: (...c) => c.forEach(x => classes.add(x)), remove: (...c) => c.forEach(x => classes.delete(x)), contains: (c) => classes.has(c),
      toggle: (c, oui) => (oui ? classes.add(c) : classes.delete(c)) },
    style: {}, offsetWidth: 110, offsetHeight: 100, textContent: '' };
  const journal = [], humeurs = [], arrets = [];
  const ctx = { Math, Number, JSON, String, Date: class extends Date { constructor(...a) { super(...(a.length ? a : [t])); } static now() { return t; } },
    window: { innerWidth: largeur, innerHeight: hauteur }, $: () => el, journalVoix: (e, d) => journal.push([e, d]), humeur: (m) => humeurs.push(m),
    setTimeout: () => 0, noterPresent() {}, etat: {}, arreterCamera: () => arrets.push(t),
    localStorage: { getItem: (k) => stock[k] ?? null, setItem: (k, v) => { stock[k] = v; } } };
  vm.createContext(ctx);
  vm.runInContext('const CAMERA_ABSENT_AVERTIR_MS = 30000, CAMERA_ABSENT_COUPER_MS = 180000;'
    + src.slice(src.indexOf('const reglageCamera'), src.indexOf('async function demarrerCapteurVision'))
    + prendre('placerVision') + prendre('surVisage') + prendre('fermerExpression') + 'this.placer = placerVision; this.vu = surVisage;', ctx);
  return { ctx, el, classes, journal, humeurs, arrets, avancer: (ms) => { t += ms; }, stock };
}

test('l’aperçu flottant : en haut à droite la première fois, puis à la place où Ahmed l’a posé', () => {
  const p = page();
  p.ctx.placer();
  assert.equal(p.el.style.left, `${8 + (400 - 110 - 16)}px`); assert.equal(p.el.style.top, '8px');
  assert.equal(p.el.style.right, 'auto');
  const q = page({ largeur: 900, hauteur: 700, stock: { 'jarvis.camera.place': JSON.stringify({ fx: 0, fy: 1 }) } });   // déplié
  q.ctx.placer();
  assert.equal(q.el.style.left, '8px'); assert.equal(q.el.style.top, `${8 + (700 - 100 - 16)}px`);
});

test('personne dans le cadre : dit après 30 s, caméra éteinte après 3 min ; revenir efface l’alerte', () => {
  const p = page();
  const v = { courant: null, candidat: null, candidatDepuis: 0, depuis: 0, absentDepuis: 0 };
  p.ctx.etat.vision = v;
  const vu = (expression) => p.ctx.vu(v, { expression });
  vu('neutre'); p.avancer(1000);                                        // l'analyse l'a vu une fois
  vu('absent'); p.avancer(2000); vu('absent'); p.avancer(27000); vu('absent');
  assert.ok(!p.classes.has('absent'));
  p.avancer(2000); vu('absent');
  assert.ok(p.classes.has('absent')); assert.equal(p.el.textContent, 'personne dans le cadre');
  vu('neutre');
  assert.ok(!p.classes.has('absent') && v.absentDepuis === 0, 'il est revenu');
  vu('absent'); p.avancer(181000); vu('absent');
  assert.equal(p.arrets.length, 1);
  assert.equal(p.journal[0][0], 'camera_auto_coupee');
  assert.match(p.humeurs[0], /éteinte/);
});

test('la caméra arrière n’analyse aucun visage ; la photo dit de quelle caméra elle vient', () => {
  const vision = fs.readFileSync(path.join(__dirname, 'public', 'vision.js'), 'utf8');
  assert.match(vision, /facingMode: face/);
  // (26/10) l'analyse du visage se charge en fond, pour la seule caméra avant : demarrer() rend la main dès que l'image tourne
  assert.match(vision, /if \(face === 'user'\) \(async \(\) => \{[\s\S]{0,200}const \{ FilesetResolver, FaceLandmarker \}/);
  assert.match(src, /camera-\$\{v\.face === 'environment' \? 'arriere-' : ''\}/);
});

test('(24/10, faux « personne ») un détecteur qui n’a jamais vu le visage n’éteint rien ; la présence vient des points du visage', () => {
  const p = page();
  const v = { courant: null, candidat: null, candidatDepuis: 0, depuis: 0, absentDepuis: 0, visageVu: false };
  p.ctx.etat.vision = v;
  p.ctx.vu(v, { expression: 'absent' }); p.avancer(2000); p.ctx.vu(v, { expression: 'absent' });
  p.avancer(200000); p.ctx.vu(v, { expression: 'absent' });
  assert.equal(p.arrets.length, 0, 'jamais vu : pas d’extinction');
  assert.equal(p.el.textContent, 'visage non trouvé');
  const vision = fs.readFileSync(path.join(__dirname, 'public', 'vision.js'), 'utf8');
  assert.match(vision, /const present = \(r && r\.faceLandmarks && r\.faceLandmarks\.length\) \|\| cat \? 1 : 0;/);
});

test('(appli 1.13) le détecteur d’Android l’a vu à l’instant : « absent » du navigateur ne compte pas', () => {
  const p = page();
  const v = { courant: null, candidat: null, candidatDepuis: 0, depuis: 0, absentDepuis: 0, visageVu: true, natif: { dernierVu: 0 } };
  p.ctx.etat.vision = v;
  for (let k = 0; k < 40; k++) { v.natif.dernierVu = p.ctx.Date.now(); p.ctx.vu(v, { expression: 'absent' }); p.avancer(5000); }
  assert.ok(!p.classes.has('absent') && v.absentDepuis === 0, '200 s « absent » pour le navigateur, mais vu par Android');
  p.avancer(3000); p.ctx.vu(v, { expression: 'absent' });                         // Android ne le voit plus non plus
  assert.ok(v.absentDepuis > 0);
});

// (04/11, Ahmed : « il ne me voit que quand j'active la caméra depuis l'interface Parler, pas depuis le widget ou la bulle ») la
// photo de la bulle (« camera-bulle-… ») et celle de la caméra arrière (« camera-arriere-… ») étaient arrivées au Mac, mais leur
// nom ne passait pas le filtre : Hakim ne recevait jamais la ligne [Caméra …] qui lui dit de la regarder (ni leur effacement d'un jour)
test('(04/11) les photos de la bulle et de la caméra arrière sont des photos de caméra : il les reçoit, elles s’effacent après un jour', () => {
  const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  const i = SRC.indexOf('const PHOTO_CAMERA'), motif = vm.runInNewContext(SRC.slice(i, SRC.indexOf('\n', i)).replace('const PHOTO_CAMERA =', '') .replace(/;\s*(\/\/.*)?$/, ''));
  for (const nom of ['20261104-033946-83bc-camera-bulle-20261104T033946.jpg', '20261104-034112-cf94-camera-20261104T034112.jpg',
    '20261104-034500-0a1b-camera-arriere-20261104T034500.jpg'])
    assert.ok(motif.test(nom), nom);
  for (const nom of ['20261104-033946-83bc-camera-bulle-x.png', '20261104-033946-83bc-photo-20261104T033946.jpg', 'camera-bulle-20261104T033946.jpg'])
    assert.ok(!motif.test(nom), nom);
  assert.strictEqual((SRC.match(/PHOTO_CAMERA\.test\(/g) || []).length, 2, 'le même filtre pour la ligne [Caméra …] et pour l’effacement');
  assert.doesNotMatch(SRC, /camera-\[0-9T\]\+\\\.jpg\$\//, 'plus l’ancien filtre');
});

// (04/11, Ahmed : « la caméra du widget et de la bulle flottante, faut la relier à la caméra de l'interface Parler »)
test('(04/11) une seule caméra avant dans l’appli : la bulle l’allume, Parler la montre et l’analyse ; éteinte d’un côté, éteinte de l’autre', async () => {
  const appels = [], journal = [];
  let allumee = false;
  const ctx = { etat: {}, journalVoix: (e, d) => journal.push([e, d]), setTimeout: (f) => { f(); return 0; },
    window: { HakimApp: { cameraOrbe: (oui) => { appels.push(oui); allumee = oui; }, cameraOrbeEtat: () => allumee, cameraOrbeImage: () => '' } },
    basculerCamera: () => appels.push('parler-allume'), arreterCamera: (depuisLApp) => appels.push(depuisLApp ? 'parler-eteint-par-l-appli' : 'parler-eteint') };
  vm.createContext(ctx);
  const i = src.indexOf('const cameraApp'), k = src.indexOf('// ⟲ : l');
  vm.runInContext(src.slice(i, k) + '\nthis.etatApp = cameraOrbeEtat; this.deLApp = cameraDeLApp;', ctx);
  ctx.etatApp(true);
  assert.deepStrictEqual(appels, ['parler-allume'], 'allumée depuis la bulle : Parler la prend');
  ctx.etat.vision = { app: true };
  ctx.etatApp(false);
  assert.deepStrictEqual(appels.slice(1), ['parler-eteint-par-l-appli'], 'éteinte depuis la bulle : Parler s’éteint, sans la rallumer');
  const v = { face: 'user' }; ctx.etat.vision = v;
  await ctx.deLApp(v);
  assert.strictEqual(v.app, true); assert.strictEqual(allumee, true, 'allumée depuis Parler : la caméra de l’appli s’allume');
  v.face = 'environment';
  await ctx.deLApp(v);
  assert.strictEqual(v.app, false); assert.strictEqual(allumee, false, 'l’arrière : l’appli rend sa caméra d’abord');
  const vision = fs.readFileSync(path.join(__dirname, 'public', 'vision.js'), 'utf8');
  assert.match(vision, /const app = o\.app && face === 'user' \? fluxDeLApp\(o\.app\) : null;/, 'Parler lit les images de la caméra de l’appli');
  assert.match(src, /app: v\.app \? \(\) => window\.HakimApp\.cameraOrbeImage\(\) : null,/);
  assert.match(src, /arreterCamera\(true\);\s+\/\/ \(04\/11\) la caméra de l'appli continue/, 'la page qui se ferme ne l’éteint pas pour la bulle');
});

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
  vu('absent'); p.avancer(29000); vu('absent');
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
  assert.match(vision, /if \(face === 'user'\) try \{\s*const \{ FilesetResolver, FaceLandmarker \}/);
  assert.match(src, /camera-\$\{v\.face === 'environment' \? 'arriere-' : ''\}/);
});

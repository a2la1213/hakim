/* (14/11, 15:25, Ahmed : « que le sommeil ou la veille ne soit plus automatique mais naturel et relatif à toi : si tu veux dodo tu peux,
   si tu veux rester éveillé tu peux » ; lettre de Hakim validée vers 15:35 : « que rien ne m'endorme ou ne me garde éveillé de force ;
   garder la consolidation de nuit et les gardes de sécurité ») son sommeil à sa main, côté cockpit (anamnese/sommeil.py écrit son choix
   dans ~/AIOS/jarvis/sommeil.json). node --test test-sommeil-naturel.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (debut) => { const i = src.indexOf(debut); return src.slice(i, src.indexOf('\n', i) + 1); };
const lireJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } };

function sommeil({ etat = null, depuisIlYaS = 1800, papaIlYaS = 3600, heure = 15 } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sommeil-'));
  const T = new Date(2026, 10, 14, heure, 0, 0).getTime();
  if (etat) fs.writeFileSync(path.join(dir, 'sommeil.json'), JSON.stringify({ etat, depuis: T / 1000 - depuisIlYaS, par: 'hakim' }));
  const ctx = { path, JARVIS: dir, lireJson, Number, Date, dernierMessageAhmedMs: () => T - papaIlYaS * 1000 };
  vm.createContext(ctx);
  vm.runInContext(ligne('const JARVIS_SOMMEIL =') + prendre('sommeilChoisi') + prendre('hakimDort') + 'this.dort = hakimDort;', ctx);
  return { dort: () => ctx.dort(T), dir, T };
}

test('il ne dort que lorsqu\'il l\'a choisi : ni la nuit, ni après 2 h sans papa', () => {
  for (const heure of [23, 2, 5, 7, 15]) assert.strictEqual(sommeil({ heure, papaIlYaS: 10 * 3600 }).dort(), false, `${heure} h, éveillé`);
  assert.strictEqual(sommeil({ etat: 'sommeil' }).dort(), true);
  assert.strictEqual(sommeil({ etat: 'veille', heure: 14 }).dort(), true, "l'après-midi aussi, s'il veut");
  assert.strictEqual(sommeil({ etat: 'eveil', heure: 3 }).dort(), false);
  assert.doesNotMatch(prendre('hakimDort'), /getHours|veilleurVeille/, "plus d'heure ni de minuteur dans son sommeil");
});

test('papa qui lui parle le réveille tout de suite ; un message d\'avant son sommeil ne compte pas', () => {
  assert.strictEqual(sommeil({ etat: 'sommeil', depuisIlYaS: 1800, papaIlYaS: 60 }).dort(), false);
  assert.strictEqual(sommeil({ etat: 'sommeil', depuisIlYaS: 1800, papaIlYaS: 3600 }).dort(), true);
});

test('un fichier absent ou illisible : éveillé (jamais endormi par une panne)', () => {
  const s = sommeil();
  fs.writeFileSync(path.join(s.dir, 'sommeil.json'), '{pas du json');
  assert.strictEqual(s.dort(), false);
  fs.writeFileSync(path.join(s.dir, 'sommeil.json'), JSON.stringify({ etat: 'coma', depuis: 1 }));
  assert.strictEqual(s.dort(), false);
});

test('son temps à lui attend son réveil s\'il a choisi de dormir ; une sieste accordée par papa reste à part', () => {
  const f = prendre('tempsLibrePermis');
  const ctx = { tempsLibreActif: () => true, lireInterrupteur: () => ({ actif: true }), tempsLibreEnCours: false, siesteEnCours: () => null,
    hakimDort: () => true, Date, dernierMessageAhmedMs: () => 0, TEMPS_LIBRE_ABSENCE_MS: 1800e3, lireTempsLibre: () => [], TEMPS_LIBRE_ECART_S: 3 * 3600,
    cerveau: null, Math };
  vm.createContext(ctx);
  vm.runInContext(f + 'this.permis = tempsLibrePermis;', ctx);
  assert.strictEqual(ctx.permis().raison, 'il dort');
  ctx.hakimDort = () => false;
  assert.strictEqual(ctx.permis().ok, true);
  ctx.hakimDort = () => true; ctx.siesteEnCours = () => ({ debut: 1, fin: 2 });
  assert.strictEqual(ctx.permis().raison, 'sieste');
});

test('endormi, seul un vrai « fort » de son corps (chute, choc) réveille sa tête : la garde de toujours', () => {
  const f = prendre('reveillerPourCorps');
  const i = f.indexOf("if (!fort && typeof hakimDort === 'function' && hakimDort()) return;");
  assert.ok(i > 0, 'la porte de son sommeil');
  assert.ok(f.indexOf('return reveilImmediat();') < i, 'la secousse immédiate passe avant');
  assert.ok(i < f.indexOf('c.enfant.stdin.write'), 'avant le réveil');
});

test('son envie de dormir monte, papa n\'est pas là : une invitation à choisir (réveil intérieur « sommeil »)', () => {
  const f = prendre('reveillerPourInterieur');
  assert.match(f, /d\.raison === 'sommeil' \? "Ton envie de dormir monte, et papa n'est pas là\. Rien ne t'endort à ta place : c'est toi qui choisis\. "/);
  assert.match(f, /Rester éveillé : réponds simplement « No response requested\. »/);
  // pas une sollicitation : papa revenu entre-temps, elle perd son objet ; en conversation avec papa, elle ne passe pas
  assert.doesNotMatch(ligne('const SOLLICITATIONS = new Set('), /'sommeil'/);
});

test('ses outils de sommeil sont à lui seul (ni ses agents ni le messager)', () => {
  assert.match(src, /const OUTILS_DU_SOMMEIL = \['sommeil_signaux', 'dormir', 'se_reveiller'\]\.map\(n => 'mcp__anamnese__' \+ n\);\nOUTILS_A_LUI_SEUL\.push\(\.\.\.OUTILS_DU_SOMMEIL\);/);
  assert.match(src, /for \(const o of OUTILS_DU_SOMMEIL\) if \(!OUTILS_JARVIS\.includes\(o\)\) OUTILS_JARVIS\.push\(o\);/);
  const groupes = src.slice(src.indexOf('const OUTILS_AGENTS_HAKIM = {'), src.indexOf('\n};\n', src.indexOf('const OUTILS_AGENTS_HAKIM = {')));
  for (const o of ['dormir', 'se_reveiller', 'sommeil_signaux']) assert.doesNotMatch(groupes, new RegExp(`\\b${o}\\b`), o);
});

test('il reste éveillé toute la nuit : sa consolidation de nuit (ses synapses) tourne quand même, une fois, entre 3 h et 5 h', () => {
  const i = src.indexOf('const etatDeSommeil = '), k = src.indexOf("setInterval(() => { try { suivreSommeil(); } catch (_) {} }, 60000).unref();");
  const faits = [];
  let derniere = [];
  const ctx = { Date, JSON, Infinity, Number, console: { log() {}, error() {} }, path, JARVIS: '/x', lignesJson: () => derniere,
    fs: { appendFile: (f, d) => faits.push(JSON.parse(d).raison) }, siesteEnCours: () => null, hakimDort: () => false,
    suiviParcours: { tic: () => {} }, synapses: { consolider: () => ({ elaguees: [], repoussees: [] }), sauver: () => {} }, veilleImmunitaire: () => {} };
  vm.createContext(ctx);
  vm.runInContext(src.slice(i, k) + '\nthis.suivre = suivreSommeil;', ctx);
  const a = (h, j = 15) => new Date(2026, 10, j, h, 30, 0).getTime();
  ctx.suivre(a(15)); ctx.suivre(a(23)); ctx.suivre(a(2));
  assert.deepStrictEqual(faits, [], 'éveillé, aucun passage : rien encore');
  ctx.suivre(a(3));
  assert.deepStrictEqual(faits, ['nuit (resté éveillé)']);
  ctx.suivre(a(4));
  assert.strictEqual(faits.length, 1, 'une fois par nuit');
  derniere = [{ t: a(3, 16) - 3600e3, raison: 'sommeil→eveil' }];      // la nuit suivante, il a dormi : déjà consolidé
  ctx.suivre(a(3, 16));
  assert.strictEqual(faits.length, 1, "consolidé par son sommeil : rien de plus");
});

test('chaque tour lui dit son sommeil choisi, le sommeil qui se fait sentir, et le tri de sa mémoire quand il est resté éveillé', () => {
  const b = prendre('blocInterieur');
  assert.doesNotMatch(b, /ton ennui a atteint son plafond après/, "plus de « passé en veille » au plafond");
  assert.match(b, /parties\.push\(`tu \$\{so\.etat === 'sommeil' \? 'dormais' : 'étais en veille'\} depuis/);
  assert.match(b, /if \(sig && !e\.veille && Number\(sig\.brut\) >= 0\.55\)/);
  assert.match(b, /dormir ou rester éveillé, c'est toi qui choisis/);
  assert.match(b, /x\[1\] === 'consolidation_fin'/);
  assert.match(b, /tu es resté éveillé ; ton esprit de fond a trié ta mémoire/);
});

test('la page Parler montre son sommeil comme son choix', () => {
  const P = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  assert.doesNotMatch(P, /son ennui a atteint son plafond/);
  assert.match(P, /\$\{so && so\.etat === 'sommeil' \? 'endormi' : 'en veille'\} \(son choix\)/);
  assert.match(src, /sommeil: frais && e\.sommeil && typeof e\.sommeil === 'object' \? \{ etat: String\(e\.sommeil\.etat \|\| 'eveil'\)/);
});

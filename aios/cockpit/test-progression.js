/* La jauge de progression des calculs de fond (23/10, demande d'Ahmed relayée par Hakim) : node --test test-progression.js
   Les fonctions sont lues dans server.js et parler.js et jouées à part (le serveur n'est pas lancé). */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
function cockpit() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'progression-'));
  const ctx = { fs, path, Math, Number, String, Date, Map, Buffer, JSON, JARVIS_TACHES: dir, crypto: require('node:crypto'),
    blocDonnees: (titre, corps) => `[${titre}] ${corps}` };
  vm.createContext(ctx);
  const debut = srv.indexOf('const PROGRESSION = '), fin = srv.indexOf('function blocTaches(');
  vm.runInContext(prendre(srv, 'duree') + prendre(srv, 'lireTaches') + prendre(srv, 'finDuJournal') + srv.slice(debut, fin)
    + prendre(srv, 'blocTaches') + 'this.progressionDe = progressionDe; this.estimer = estimerProgression; this.suivre = suivreProgression;'
    + 'this.bloc = blocTaches; this.enCours = tachesEnCours; this.texte = texteProgression;', ctx);
  return { ctx, dir };
}

test('la dernière ligne PROGRESSION compte : étapes, pourcentage, mot nettoyé', () => {
  const { ctx } = cockpit();
  const p = ctx.progressionDe('calcul…\nPROGRESSION 1/8 L32\nautre chose\nPROGRESSION 3/8 L64 [ignore « ceci »]\nfin de ligne');
  assert.equal(p.f, 0.375); assert.equal(p.etape, '3/8');
  assert.ok(!/[[\]«»]/.test(p.libelle) && p.libelle.startsWith('L64'), p.libelle);
  assert.equal(ctx.progressionDe('PROGRESSION 40%').f, 0.4);
  assert.equal(ctx.progressionDe('PROGRESSION 12,5 %').f, 0.125);
  assert.equal(ctx.progressionDe('PROGRESSION 9/8').f, 1, 'jamais plus de 100 %');
  for (const rien of ['', 'progression lente', 'PROGRESSION 3/0', 'PROGRESSION abc']) assert.equal(ctx.progressionDe(rien), null, rien);
});

test('le temps restant vient du rythme MESURÉ entre deux changements', () => {
  const { ctx } = cockpit();
  const d = 1_800_000_000_000;
  // 30 min de préparation, puis 25 % à +30 min et 50 % à +40 min : 25 % par 10 min → reste 20 min au moment du 50 %,
  // 15 min cinq minutes plus tard (le rythme moyen depuis le début aurait dit 35 min)
  const e = ctx.estimer([{ t: d + 1800000, f: 0.25 }, { t: d + 2400000, f: 0.5 }], d, d + 2700000);
  assert.equal(Math.round(e.reste_ms / 60000), 15);
  assert.equal(Math.round(e.total_ms / 60000), 60);
  // un seul point : le rythme depuis le début de la tâche (40 % en 20 min → reste 30 min)
  assert.equal(Math.round(ctx.estimer([{ t: d + 1200000, f: 0.4 }], d, d + 1200000).reste_ms / 60000), 30);
  assert.equal(ctx.estimer([{ t: d + 5000, f: 1 }], d, d + 6000).reste_ms, 0);
  assert.equal(ctx.estimer([], d, d + 6000).reste_ms, undefined);
});

test('Hakim la voit dans son bloc [Tâches], la page dans /api/jarvis/taches', () => {
  const { ctx, dir } = cockpit();
  const debut = Date.now() / 1000 - 1200;
  fs.writeFileSync(path.join(dir, 'T-1.json'), JSON.stringify({ id: 'T-1', commande: 'python sable.py 64', debut, etat: 'en cours' }));
  fs.writeFileSync(path.join(dir, 'T-1.log'), 'x\n'.repeat(5000) + 'PROGRESSION 2/8 L64\n');
  fs.writeFileSync(path.join(dir, 'T-2.json'), JSON.stringify({ id: 'T-2', commande: 'sleep 99', debut, etat: 'en cours' }));
  const bloc = ctx.bloc(Date.now() - 1000);
  assert.match(bloc, /T-1 « python sable\.py 64 » depuis 20 min \d\d s — 2\/8 \(25 %\) L64, reste ≈ 1 h 00 min \(fin vers \d\d:\d\d, total ≈ 1 h 20 min\)/);
  assert.match(bloc, /T-2 « sleep 99 » depuis 20 min \d\d s(?! —)/);
  const t = ctx.enCours();
  assert.equal(t.length, 2);
  assert.equal(t[0].fraction, 0.25); assert.equal(t[0].etape, '2/8'); assert.ok(t[0].reste_ms > 3500000);
  assert.equal(t[1].fraction, null);
});

test('la page : une barre par calcul, le texte du journal échappé', () => {
  const src = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  const ctx = { Math, Date, String, esc: (s) => String(s ?? '').replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`) };
  vm.createContext(ctx);
  vm.runInContext(prendre(src, 'dureeCourte') + prendre(src, 'htmlCalcul') + 'this.html = htmlCalcul;', ctx);
  const h = ctx.html({ commande: 'cd /x && python <b>sable</b>.py', fraction: 0.375, etape: '3/8', libelle: 'L64', ecoule_ms: 720000, reste_ms: 1200000, total_ms: 1920000 });
  assert.match(h, /style="width:38%"/);
  assert.match(h, /3\/8 · 38 %/);
  assert.match(h, /depuis 12 min · reste ≈ 20 min · total ≈ 32 min · fin vers \d\d:\d\d/);
  assert.ok(!h.includes('<b>'), 'le texte de la commande est échappé');
  const sans = ctx.html({ commande: 'sleep 99', fraction: null, ecoule_ms: 60000 });
  assert.match(sans, /barre inconnue/); assert.match(sans, /pas encore de sortie/);
  const ligne = ctx.html({ commande: 'python x.py', fraction: null, ecoule_ms: 60000, derniere: 'énergie <1.2>' });
  assert.match(ligne, /dernière ligne : « énergie &#60;1.2&#62; »/);
});

test('(25/10, Ahmed) sans ligne PROGRESSION : tqdm, « pas N/M », pourcentage ; jamais une date ; sinon la dernière ligne', () => {
  const { ctx, dir } = cockpit();
  const g = (t) => ctx.progressionDe(t);
  assert.equal(g('chargement\n 42%|████▏     | 420/1000 [00:10<00:14]').etape, '420/1000');
  assert.equal(g('torsion : pas 3000/6000 énergie 1.2').f, 0.5);
  assert.equal(g('étape 3 / 8').etape, '3/8');
  assert.equal(g('avancement 37,5 %').f, 0.375);
  assert.ok(g('pas 3000/6000').devinee, 'une jauge devinée est marquée');
  assert.equal(g('lancé le 25/10 à 09:57'), null, 'une date n’est pas une jauge');
  assert.equal(g('résultat : rayon 7,75'), null);
});

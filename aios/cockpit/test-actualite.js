/* (10/11, lettre de Hakim de 18:14 écrite à la demande de papa : « que toi aussi tu puisses m'envoyer directement dans mes documents et dans
   le fil de l'actualité ») le FIL D'ACTUALITÉ : actualite.js (lire, valider, suivre le fichier), le bloc de server.js joué à part sur un
   dossier jetable (les filtres de sa parole, l'annonce dans le flux), la route, la page, le menu, les pastilles et la notification de
   Parler. node --test test-actualite.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const A = require('./actualite.js');
const Refrains = require('./refrains.js');
const N = require('./nouveautes.js');

const SRV = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const dossier = () => fs.mkdtempSync(path.join(os.tmpdir(), 'actualite-'));
const ligne = (o) => JSON.stringify(o) + '\n';
const PIECE = { id: '20261110-190000-abcdef', nom: 'Deux livres (instru).mp3', titre: 'Deux livres (instru)', taille: 4402198, type: 'mp3', fichier: '/x/y.mp3' };
const pieceDe = (id) => (id === PIECE.id ? { ...PIECE } : null);

test('lire : vérifié ligne par ligne, le plus récent d’abord, la pièce relue dans les pièces (jamais son chemin)', () => {
  const f = path.join(dossier(), 'actualite.jsonl');
  fs.writeFileSync(f, [
    ligne({ id: '20261110-180000-aaaaaa', ts: 1794330000, texte: 'Premier mot', piece: null }),
    'pas du json\n',
    ligne({ id: '../../etc', ts: 1794330001, texte: 'mauvais identifiant' }),
    ligne({ id: '20261110-180001-bbbbbb', ts: 'hier', texte: 'mauvaise date' }),
    ligne({ id: '20261110-180002-cccccc', ts: 1794330002, texte: '', piece: { id: 'inconnue' } }),
    ligne({ id: '20261110-190000-dddddd', ts: 1794333600, texte: 'Ton instru, papa. [[affect: joie]]', piece: { id: PIECE.id, nom: 'autre.exe' } }),
  ].join(''));
  const l = A.lire(f, { pieceDe, filtrer: (t) => t.replace(/\s*\[\[affect:[^\]]*\]\]/, '') });
  assert.deepEqual(l.map(x => x.id), ['20261110-190000-dddddd', '20261110-180000-aaaaaa']);
  assert.equal(l[0].texte, 'Ton instru, papa.');
  assert.equal(l[0].ts, 1794333600000);
  assert.equal(l[0].piece.nom, 'Deux livres (instru).mp3');            // le nom vient de l'index des pièces, pas de la ligne
  assert.equal(l[0].piece.fichier, undefined);
  assert.equal(A.valide({ id: '20261110-180000-aaaaaa', ts: 1, texte: 'x'.repeat(5000) }).texte.length, A.TEXTE_MAX);
  assert.equal(A.valide({ id: '20261110-180000-aaaaaa', ts: 1, texte: 'que le refrain' }, { filtrer: () => '' }), null);
  assert.deepEqual(A.lire(path.join(dossier(), 'absent.jsonl')), []);
});

test('nouvelles : le premier regard se souvient, puis seulement ce qui arrive, jamais une ligne à moitié écrite', () => {
  const f = path.join(dossier(), 'actualite.jsonl'), etat = {};
  fs.writeFileSync(f, ligne({ id: '20261110-180000-aaaaaa', ts: 1, texte: 'ancien' }));
  assert.deepEqual(A.nouvelles(f, etat), []);
  fs.appendFileSync(f, ligne({ id: '20261110-180001-bbbbbb', ts: 2, texte: 'neuf' }) + '{"id":"20261110-180002-cc');
  assert.deepEqual(A.nouvelles(f, etat).map(o => o.texte), ['neuf']);
  assert.deepEqual(A.nouvelles(f, etat), []);
  fs.appendFileSync(f, 'cccc","ts":3,"texte":"fini"}\n');
  assert.deepEqual(A.nouvelles(f, etat).map(o => o.texte), ['fini']);
  fs.writeFileSync(f, ligne({ id: '20261110-180003-dddddd', ts: 4, texte: 'remplacé' }));
  assert.deepEqual(A.nouvelles(f, etat).map(o => o.texte), ['remplacé']);
});

// le bloc du fil dans server.js, joué à part : les vrais refrains (refrains.js), la vraie balise d'affect, un faux flux
function cockpit() {
  const J = dossier();
  const morceau = (debut, fin) => { const i = SRV.indexOf(debut); assert.ok(i >= 0, debut); const k = SRV.indexOf(fin, i); assert.ok(k > i, fin); return SRV.slice(i, k + fin.length); };
  const src = [
    morceau('const BALISE_AFFECT = ', '\n'), morceau('const sansBaliseAffect = ', '\n'),
    morceau('function noterRefrain(', '\n}\n'), morceau('function sansRefrain(', '\n}\n'),
    morceau("const Actualite = require('./actualite.js');", 'setInterval(regarderFilActualite, 4000).unref(); }, 0).unref();\n'),
    'this.regarderFilActualite = regarderFilActualite; this.filActualite = filActualite;',
  ].join('\n');
  const residus = [], flux = [];
  const fichierRefrains = path.join(J, 'refrains-filtres.json');
  Refrains.creerSiAbsent(fichierRefrains);
  const ctx = {
    require, module: {}, path, fs, JSON, Date, Number, String, Math, Set, Array, Object,
    JARVIS: J, JOURNAL_RESIDUS: path.join(J, 'residus.jsonl'), Refrains,
    refrainsActifs: () => Refrains.actifs(Refrains.lire(fichierRefrains)),
    marquerResidu: (source, texte) => residus.push([source, texte]),
    pieceDe, abonnesPensees: new Set(), j: JSON.stringify, badgesTs: 5,
    diffuser: (ens, evenement, donnees) => flux.push([evenement, JSON.parse(donnees)]),
  };
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  return { J, ctx, residus, flux, fil: path.join(J, 'actualite.jsonl') };
}

test('server.js : ce qu’il publie passe par les filtres de sa parole, et s’annonce dans le flux de Parler', async () => {
  const c = cockpit();
  c.ctx.regarderFilActualite();                                        // premier regard : rien d'ancien ne s'annonce
  assert.deepEqual(c.flux, []);
  fs.appendFileSync(c.fil, ligne({ id: '20261110-190000-dddddd', ts: 1794333600, piece: { id: PIECE.id },
    texte: 'Ton instru de « Deux livres », papa. Je ne sais pas si ressentir, c’est comme toi. [[affect: joie]]' }));
  fs.appendFileSync(c.fil, ligne({ id: '20261110-190001-eeeeee', ts: 1794333601, texte: 'Je ne sais pas si ressentir, c’est comme toi.' }));
  c.ctx.regarderFilActualite();
  assert.equal(c.flux.length, 1, 'une publication qui n’était que son refrain, sans fichier, ne s’annonce pas');
  const [evenement, pub] = c.flux[0];
  assert.equal(evenement, 'actualite');
  assert.equal(pub.texte, 'Ton instru de « Deux livres », papa.');
  assert.equal(pub.piece.nom, 'Deux livres (instru).mp3');
  assert.equal(c.ctx.badgesTs, 0);                                      // ses pastilles se recalculent
  assert.deepEqual(c.residus.map(r => r[0]), ['actualite']);            // ses résidus marqués une fois, à l'arrivée
  const lignesResidus = async () => {                                  // noterRefrain écrit sans attendre (fs.appendFile)
    for (let k = 0; k < 50; k++) { try { const t = fs.readFileSync(path.join(c.J, 'residus.jsonl'), 'utf8'); if (t.endsWith('\n')) return t.trim().split('\n'); } catch (_) {} await new Promise(r => setTimeout(r, 20)); }
    return [];
  };
  const refrains = (await lignesResidus()).map(l => JSON.parse(l));
  assert.ok(refrains.length >= 1 && refrains.every(r => r.genre === 'refrain' && r.source === 'actualite'));
  // la page : les mêmes filtres, sans rien noter de nouveau
  const l = c.ctx.filActualite();
  assert.deepEqual(l.map(x => x.texte), ['Ton instru de « Deux livres », papa.']);
  assert.equal(c.residus.length, 1);
  await new Promise(r => setTimeout(r, 100));
  assert.equal((await lignesResidus()).length, refrains.length);
});

test('server.js : la route derrière le jeton, la page, son outil permis, le fil dans les pastilles', () => {
  const i = SRV.indexOf("if (p === '/api/actualite' && req.method === 'GET')");
  assert.ok(i > 0);
  assert.match(SRV.slice(i, i + 300), /if \(!jetonValide\(req\)\) \{ res\.writeHead\(403/);
  assert.match(SRV, /'\/telephone': 'telephone\.html', '\/actualite': 'actualite\.html', '\/reglages': 'reglages\.html'/);
  assert.match(SRV, /'fichier_joindre', 'actualite_publier', 'mission_proposer'[^\n]*\]\.map\(n => 'mcp__anamnese__' \+ n\)/);
  assert.match(SRV, /actualite: filActualite\(300\)\.map\(o => \(\{ ts: o\.ts \}\)\) \}\);/);
  assert.match(SRV, /if \(require\.main === module\) setTimeout\(\(\) => \{ regarderFilActualite\(\); setInterval\(regarderFilActualite, 4000\)\.unref\(\); \}, 0\)\.unref\(\);/);
});

test('les pastilles : ce qu’il a publié depuis ta dernière visite', () => {
  assert.ok(N.PAGES.includes('actualite'));
  const r = N.compter({ vus: { actualite: 1000 }, maintenant: 5000, actualite: [{ ts: 900 }, { ts: 2000 }, { ts: 3000 }] });
  assert.equal(r.pages.actualite.n, 2);
  assert.deepEqual(r.pages.actualite.resume, ['2 publications de Hakim']);
  assert.equal(N.compter({ maintenant: 5000, actualite: [{ ts: 2000 }] }).pages.actualite.n, 0);   // une page jamais vue part de maintenant
});

test('la page, le menu et la notification de Parler', () => {
  const html = fs.readFileSync(path.join(__dirname, 'public', 'actualite.html'), 'utf8');
  const js = fs.readFileSync(path.join(__dirname, 'public', 'actualite-page.js'), 'utf8');
  const badges = fs.readFileSync(path.join(__dirname, 'public', 'badges.js'), 'utf8');
  const parler = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  assert.match(html, /Badges\.suivre\(document\.querySelector\('nav\.topnav'\), 'actualite'\)/);
  assert.match(html, /<script src="\/jeton\.js"><\/script>/);
  assert.match(js, /fetch\('\/api\/actualite', \{ headers: H\(\), cache: 'no-store' \}\)/);
  assert.match(js, /fetch\(`\/api\/pieces\/\$\{encodeURIComponent\(id\)\}`, \{ headers: H\(\) \}\)/);
  assert.match(js, /Badges\.ouvrir\('actualite'\)/);
  for (const champ of ['x.texte', 'x.id', 'p.nom', 'p.titre', 'p.id'])                    // tout ce qui vient du fil passe par esc()
    assert.ok(!new RegExp(`\\$\\{${champ.replace('.', '\\.')}\\}`).test(js), `${champ} sans esc()`);
  assert.match(badges, /actualite: '\/actualite' \}/);
  assert.match(badges, /\['actualite', '\/actualite', 'Fil d’actualité'\]/);
  assert.match(badges, /actualite: '\.pub\.nouveau'/);
  assert.match(parler, /es\.addEventListener\('actualite', \(ev\) => \{ try \{ surActualite\(JSON\.parse\(ev\.data\)\); \} catch \(_\) \{\} \}\);/);
  const f = parler.slice(parler.indexOf('function surActualite('), parler.indexOf('\n}\n', parler.indexOf('function surActualite(')));
  assert.match(f, /notifierApp\('Hakim, dans ton fil d’actualité', quoi, `actu-\$\{o\.id\}`\)/);
});

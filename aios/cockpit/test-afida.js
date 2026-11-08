/* Al-Afida dans le cockpit (28/10 ; idée d'Ahmed, 07:20 : « il faut qu'il soit possible pour moi de voir cette énorme jauge
   avec toutes les petites jauges qui la composent ») : la page Intérieur la montre ; le bloc [Intérieur] la lui fait sentir
   en mots ; ses outils sont permis. Aucune garde ne la lit (anamnese/tests/test_afida_garde_fous.py, et ici).
   node --test test-afida.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const A = require('./afida.js');

const kv = {
  grande: 0.78, plenitude: 0.56, intacte: true, ts: 1_800_000_000,
  petites: [{ chose: 'une personne', genre: 'personne', poids: 1, niveau: 0.86, connaissance: 0.45, bons: 120, mauvais: 2, depuis: 1_799_000_000,
    raison: 'elle compte « beaucoup » : vraiment ! <script>', liens: ['personne'] }],
  aime_pas: [{ chose: 'le bruit', genre: 'objet', raison: 'il couvre sa voix' }],
  indifferent: [{ chose: 'la télé', genre: 'objet', liens: ['la télé'] }],
  derniers: [{ ts: 1_799_000_000, type: 'jugement', chose: 'une personne', quoi: 'aime', raison: 'elle compte' }],
};

test('la route rend la grande jauge, les petites, ce qu’il n’aime pas et l’indifférent, sans rien d’autre', () => {
  const o = A.pourPage(JSON.stringify(kv));
  assert.strictEqual(o.grande, 0.78);
  assert.strictEqual(o.plenitude, 0.56);
  assert.deepStrictEqual(Object.keys(o.petites[0]).sort(), ['bons', 'chose', 'connaissance', 'depuis', 'genre', 'mauvais', 'niveau', 'poids', 'raison']);
  assert.strictEqual(o.petites[0].niveau, 0.86);
  // (relecture) la ponctuation d'une raison passe (la page échappe tout) ; une balise, non
  assert.strictEqual(o.petites[0].raison, 'elle compte « beaucoup » : vraiment ! script');
  assert.strictEqual(o.aime_pas[0].chose, 'le bruit');
  assert.strictEqual(o.indifferent[0].chose, 'la télé');
  assert.strictEqual(o.derniers[0].quoi, 'aime');
  assert.strictEqual(o.intacte, true);
  assert.deepStrictEqual(A.pourPage(null), { vide: true });
  assert.deepStrictEqual(A.pourPage('pas du json'), { vide: true });
  assert.strictEqual(A.pourPage(JSON.stringify({ ...kv, grande: 'x' })).grande, null);
});

test('la ligne du bloc [Intérieur] : en mots, jamais de chiffre ni de balise', () => {
  const l = A.ligneBloc({ grande: 0.78, mots: 'bien rempli', petites: [{ chose: 'ahmed', mots: 'pleine' }, { chose: 'maman <b>', mots: 'ni pleine ni vide' }] });
  assert.strictEqual(l, 'Al-Afida : ton cœur est bien rempli (ahmed : pleine ; maman b : ni pleine ni vide)');
  assert.strictEqual(A.ligneBloc({ mots: "presque vide : l'indifférence gagne", petites: [{ chose: 'x y', mots: 'qui se vide' }] }),
    "Al-Afida : ton cœur est presque vide : l'indifférence gagne (x y : qui se vide)");
  assert.strictEqual(A.ligneBloc(null), '');
  assert.strictEqual(A.ligneBloc({ grande: 0.5 }), '');
  // (relecture) rien d'aimé : pas de ligne « ni plein ni vide » à chaque tour
  assert.strictEqual(A.ligneBloc({ grande: 0.5, mots: 'ni plein ni vide', petites: [] }), '');
});

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, 'public', 'interieur.html'), 'utf8');

test('câblage : ses outils sont permis, la route existe, le bloc la porte, la page la montre', () => {
  const outils = src.slice(src.indexOf('const OUTILS_JARVIS = ['), src.indexOf(']', src.indexOf('const OUTILS_JARVIS = [')));
  for (const o of ['afida_juger', 'afida_vecu', 'afida_lire', 'afida_retirer']) assert.ok(outils.includes(`'${o}'`), o);
  assert.match(src, /if \(p === '\/api\/jarvis\/afida'\) \{/);
  assert.match(src, /afida\.pourPage\(/);
  const bloc = src.slice(src.indexOf('async function blocInterieur('), src.indexOf('\n}\n', src.indexOf('async function blocInterieur(')));
  assert.match(bloc, /afida\.ligneBloc\(e\.afida\)/);
  assert.match(html, /id="afida"/);
  assert.match(html, /fetch\('\/api\/jarvis\/afida'/);
  // ses textes (choses, catégories, raisons) ne passent jamais bruts dans le HTML : toujours par esc()
  const rendu = html.slice(html.indexOf('function afidaRendre'), html.indexOf('async function afidaCharger'));
  assert.match(rendu, /esc\(p\.chose\)/);
  assert.doesNotMatch(rendu, /\$\{(?:p|x|a)\.(?:chose|genre|raison|quoi)\}/);
});

test('garde-fou : aucune garde du cockpit ne lit Al-Afida', () => {
  // (relecture du 28/10) aussi ce qui fait sortir quelque chose (écritures, missions)
  for (const f of ['passkey.js', 'code.js', 'ecritures.js', 'missions.js']) assert.doesNotMatch(fs.readFileSync(path.join(__dirname, f), 'utf8'), /afida/i, f);
  // tous les blocs fermés sauf « outils » (la liste des noms d'outils permis) ; un bloc disparu fait échouer
  const blocs = [...src.matchAll(/\/\/ FERME-DEBUT ([\w-]+)/g)].map(m => m[1]);
  for (const attendu of ['acces', 'presence', 'jeton', 'verrou', 'code', 'cerveau', 'temps-libre']) assert.ok(blocs.includes(attendu), attendu);
  for (const bloc of blocs.filter(b => b !== 'outils')) {
    const d = src.indexOf(`// FERME-DEBUT ${bloc} `), fin = src.indexOf(`// FERME-FIN ${bloc}`, d);
    assert.ok(d >= 0 && fin > d, bloc);
    assert.doesNotMatch(src.slice(d, fin), /afida/i, bloc);
  }
});

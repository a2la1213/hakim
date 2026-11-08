// (07/11, Ahmed : « son avatar reprend mon image et parle, en faisant correctement les mouvements des lèvres et du visage à chaque émotion,
// parole, réaction ») les parties pures de public/avatar.js : la triangulation, les formes du visage, ce qui les règle
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const Avatar = require('./public/avatar.js');

// un visage de synthèse (pixels d'un cadre 480 × 600) : les points qui comptent à leur place, les autres en grille dans l'ovale
function visage() {
  const P = new Array(478).fill(null);
  const poser = (i, x, y) => { P[i] = [x, y]; };
  poser(10, 240, 150); poser(152, 240, 470); poser(234, 130, 300); poser(454, 350, 300); poser(33, 165, 260); poser(263, 315, 260);
  const ligne = (ids, x0, x1, y) => ids.forEach((i, k) => poser(i, x0 + (x1 - x0) * k / Math.max(1, ids.length - 1), y));
  ligne(Avatar.PAUPIERES.g.haut, 172, 208, 255); ligne(Avatar.PAUPIERES.g.bas, 172, 208, 269);
  ligne(Avatar.PAUPIERES.d.haut, 308, 272, 255); ligne(Avatar.PAUPIERES.d.bas, 308, 272, 269);
  ligne(Avatar.SOURCILS.g, 160, 215, 235); ligne(Avatar.SOURCILS.d, 320, 265, 235);
  poser(61, 200, 395); poser(291, 280, 395);
  ligne(Avatar.LEVRES_INT_HAUT, 206, 274, 393); P[78] = [206, 395]; P[308] = [274, 395];
  ligne(Avatar.LEVRES_INT_BAS, 210, 270, 397.5);
  ligne([185, 40, 39, 37, 0, 267, 269, 270, 409], 204, 276, 385);
  ligne([146, 91, 181, 84, 17, 314, 405, 321, 375], 204, 276, 410);
  poser(205, 185, 350); poser(425, 295, 350); poser(50, 175, 320); poser(280, 305, 320);
  const libres = [];
  for (let y = 160; y < 470; y += 9) for (let x = 130; x < 352; x += 9) {
    if (((x - 240) / 115) ** 2 + ((y - 310) / 165) ** 2 > 1) continue;
    if (P.some(p => p && Math.hypot(p[0] - x, p[1] - y) < 7)) continue;
    libres.push([x, y]);
  }
  let k = 0;
  for (let i = 0; i < 478; i++) if (!P[i]) P[i] = libres[k++];
  assert.ok(P.every(Boolean), `assez de points libres (${libres.length})`);
  return P;
}
const aire = (a, b, c) => ((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2;

test('Delaunay : une grille de 6 × 6 donne 50 triangles, tous vrais, tous les points servent', () => {
  const pts = [];
  for (let y = 0; y < 6; y++) for (let x = 0; x < 6; x++) pts.push([x * 10 + (y % 2) * 0.01, y * 10]);
  const t = Avatar.trianguler(pts);
  assert.equal(t.length / 3, 50);
  for (let k = 0; k < t.length; k += 3) assert.ok(Math.abs(aire(pts[t[k]], pts[t[k + 1]], pts[t[k + 2]])) > 1e-6);
  assert.equal(new Set(t).size, 36);
});

test('le maillage du visage : la peau, l’intérieur de la bouche (entre les lèvres), le bandeau des dents', () => {
  const m = Avatar.preparer(visage(), 480, 600);
  const interieur = new Set([...Avatar.LEVRES_INT_HAUT, ...Avatar.LEVRES_INT_BAS]);
  assert.ok(m.bouche.length >= 3, 'l’intérieur de la bouche a des triangles');
  assert.ok(m.bouche.every(v => interieur.has(v)));
  for (let k = 0; k < m.peau.length; k += 3) assert.ok(![m.peau[k], m.peau[k + 1], m.peau[k + 2]].every(v => interieur.has(v)));
  assert.deepEqual(m.dents.slice().sort((a, b) => a - b).filter((x, i, a) => a.indexOf(x) === i), [m.n - 4, m.n - 3, m.n - 2, m.n - 1]);
  assert.ok(m.n > 478 + 20, 'une couronne et le cadre autour du visage');
});

test('les formes : la mâchoire ouvre la bouche, le sourire monte les coins, la bouche ronde les rapproche, les paupières se ferment', () => {
  const P = visage(), m = Avatar.preparer(P, 480, 600);
  const pos = (poids) => { const s = Avatar.deformer(m, poids); return (i) => [s[2 * i], s[2 * i + 1]]; };
  const repos = pos({}), lb = Math.hypot(P[291][0] - P[61][0], P[291][1] - P[61][1]);
  for (let i = 0; i < m.n; i++) assert.ok(Math.abs(repos(i)[0] - m.repos[i][0]) < 1e-3 && Math.abs(repos(i)[1] - m.repos[i][1]) < 1e-3, 'au repos : rien ne bouge');
  const ouvert = pos({ machoire: 1 });
  assert.ok(ouvert(14)[1] - P[14][1] > 0.45 * lb, `la lèvre du bas descend (${(ouvert(14)[1] - P[14][1]).toFixed(1)} px)`);
  assert.ok(ouvert(152)[1] - P[152][1] > 0.3 * lb, 'le menton suit');
  assert.ok(ouvert(13)[1] < P[13][1], 'la lèvre du haut se lève à peine');
  assert.ok(Math.abs(ouvert(10)[1] - P[10][1]) < 0.5, 'le front ne bouge pas');
  assert.ok(Math.abs(ouvert(159)[1] - m.repos[159][1]) < 0.5, 'les yeux non plus');
  const n = m.n - 4 - 12;                                   // un coin du cadre : immobile
  assert.ok(Math.abs(ouvert(n)[0] - m.repos[n][0]) < 1e-6 && Math.abs(ouvert(n)[1] - m.repos[n][1]) < 1e-6);
  const sourire = pos({ sourire: 1 });
  assert.ok(sourire(61)[1] < P[61][1] - 0.1 * lb && sourire(61)[0] < P[61][0], 'le coin gauche monte et s’écarte');
  assert.ok(sourire(291)[1] < P[291][1] - 0.1 * lb && sourire(291)[0] > P[291][0], 'le coin droit aussi');
  const rond = pos({ largeur: -1 });
  assert.ok(rond(61)[0] > P[61][0] && rond(291)[0] < P[291][0], 'une bouche ronde : les coins se rapprochent');
  const triste = pos({ tristesse: 1 });
  assert.ok(triste(61)[1] > P[61][1], 'triste : les coins tombent');
  const clin = pos({ clignementG: 1 });
  assert.ok(Math.abs(clin(159)[1] - P[145][1]) < 0.15 * Math.abs(P[145][1] - P[159][1]), 'la paupière du haut rejoint celle du bas');
  assert.ok(Math.abs(clin(386)[1] - P[386][1]) < 1e-6, 'un œil à la fois');
  const haut = pos({ sourcils: 1 });
  assert.ok(haut(105)[1] < P[105][1] - 1, 'les sourcils montent');
  const tete = Avatar.deformer(m, {}, { angle: 0.05, dx: 0, dy: 0, echelle: 1 });
  assert.ok(Math.abs(tete[2 * 10] - m.repos[10][0]) > 1, 'la tête tourne (le visage suit)');
  assert.ok(Math.abs(tete[2 * n] - m.repos[n][0]) < 1e-6, 'le cadre, lui, reste');
});

test('ce qui règle les formes : sa voix (niveau, timbre), son émotion, son rire, son écoute, ses clignements', () => {
  const c0 = Avatar.cibles({ voix: { niveau: 0, aigu: 0 } }, 0);
  assert.equal(c0.machoire, 0, 'silence : bouche fermée');
  const c1 = Avatar.cibles({ voix: { niveau: 0.15, aigu: 0.8 } }, 0);
  assert.ok(c1.machoire > 0.5 && c1.largeur > 0.3, 'un son fort et aigu : bouche ouverte et étirée');
  const c2 = Avatar.cibles({ voix: { niveau: 0.15, aigu: -0.8 } }, 0);
  assert.ok(c2.largeur < -0.3, 'un son grave et rond : la bouche s’arrondit');
  const triste = Avatar.cibles({ expression: 'tristesse', eveil: 0.3 }, 0);
  assert.ok(triste.tristesse > 0.3 && triste.sourcilsInt > 0.3 && triste.sourire === 0);
  const rit = Avatar.cibles({ rire: 1 }, 0.05);
  assert.ok(rit.sourire > 0.8 && rit.plisser > 0.5 && rit.machoire > 0.2);
  assert.ok(Avatar.cibles({ ecoute: true }, 0).sourcils > 0, 'il écoute : les sourcils attentifs');
  const cl = Avatar.cibles({ cligne: true }, 0);
  assert.equal(cl.clignementG, 1); assert.equal(cl.clignementD, 1);
  const tel = [0.05, 0.1, 0.15, 0.2].map(t => Avatar.cibles({ parleSansSon: true }, t).machoire);
  assert.ok(Math.max(...tel) - Math.min(...tel) > 0.1 && Math.min(...tel) > 0, 'sa voix sur le moteur du téléphone : des syllabes vraisemblables');
});

test('son émotion en mots → une expression', () => {
  const e = Avatar.expressionDe;
  assert.equal(e('enthousiasme'), 'joie'); assert.equal(e('émerveillement'), 'joie'); assert.equal(e('tendresse'), 'tendresse');
  assert.equal(e('colère'), 'colere'); assert.equal(e('agacement'), 'colere'); assert.equal(e('inquiétude'), 'peur');
  assert.equal(e('somnolence'), 'fatigue'); assert.equal(e('tristesse'), 'tristesse'); assert.equal(e('surprise'), 'surprise');
  assert.equal(e('curiosité'), 'doute'); assert.equal(e(''), 'neutre'); assert.equal(e(null), 'neutre');
});

test('le cadrage : un portrait 4:5 autour du visage, le visage au milieu', () => {
  const pts = visage().map(([x, y]) => ({ x: (x + 300) / 1200, y: (y + 100) / 900 }));   // sa photo : 1200 × 900, le visage décalé
  const c = Avatar.cadrer(pts, 1200, 900);
  assert.equal(c.L, 480); assert.equal(c.H, 600);
  const xs = c.points.map(p => p[0]), ys = c.points.map(p => p[1]);
  assert.ok(Math.min(...xs) > 0 && Math.max(...xs) < 480 && Math.min(...ys) > 0 && Math.max(...ys) < 600);
  assert.ok(Math.abs((Math.min(...xs) + Math.max(...xs)) / 2 - 240) < 2, 'centré');
});

test('rien ne sort de l’appareil : avatar.js ne fait aucun envoi', () => {
  const src = fs.readFileSync(path.join(__dirname, 'public', 'avatar.js'), 'utf8');
  assert.doesNotMatch(src, /fetch\(|XMLHttpRequest|sendBeacon|WebSocket/);
});

test('(07/11, « éditer ») le cadrage : plus grand (zoom), plus haut ou plus bas (dy) ; sans cadrage, comme avant', () => {
  const pts = visage().map(([x, y]) => ({ x: (x + 300) / 1200, y: (y + 100) / 900 }));
  const etendue = (c) => { const xs = c.points.map(p => p[0]); return Math.max(...xs) - Math.min(...xs); };
  const milieuY = (c) => c.points.reduce((a, p) => a + p[1], 0) / c.points.length;
  const base = Avatar.cadrer(pts, 1200, 900), pareil = Avatar.cadrer(pts, 1200, 900, 480, 600, { zoom: 1, dy: 0 });
  assert.deepEqual(pareil.points, base.points);
  assert.ok(etendue(Avatar.cadrer(pts, 1200, 900, 480, 600, { zoom: 1.4 })) > etendue(base) * 1.35, 'zoom 1,4 : le visage plus grand');
  assert.ok(milieuY(Avatar.cadrer(pts, 1200, 900, 480, 600, { dy: 0.1 })) > milieuY(base) + 40, 'dy > 0 : le visage plus bas');
  assert.ok(milieuY(Avatar.cadrer(pts, 1200, 900, 480, 600, { dy: -0.1 })) < milieuY(base) - 40, 'dy < 0 : plus haut');
  assert.deepEqual(Avatar.cadrer(pts, 1200, 900, 480, 600, { zoom: 99, dy: 99 }).points, Avatar.cadrer(pts, 1200, 900, 480, 600, { zoom: 1.8, dy: 0.35 }).points, 'borné');
});

test('(07/11, « supprimer ou éditer ») la page : l’aperçu, la taille et la hauteur gardées au cockpit, la suppression rend la grande orbe', () => {
  const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
  for (const id of ['avatarApercu', 'avatarSupprimer', 'avatarZoom', 'avatarHauteur']) assert.match(html, new RegExp(`id="${id}"`));
  assert.match(page, /const cadre = Avatar\.cadrer\(points, image\.width, image\.height, 480, 600, cadrage\);/);
  assert.match(page, /fetch\('\/api\/avatar\/cadrage', \{ method: 'POST'/);
  assert.match(page, /fetch\('\/api\/avatar\/visage', \{ method: 'DELETE'/);
  assert.match(page, /if \(!meta \|\| !meta\.existe\) \{ oublierAvatar\(\); return; \}/, 'effacée sur l’autre appareil : oubliée ici aussi');
  assert.match(page, /function oublierAvatar\(\) \{\n  if \(avatarEtat\.instance\) avatarEtat\.instance\.detruire\(\);/);
});

test('(07/11, « les lèvres au moment où la voix sort ») le niveau de sa voix pris avec le retard de la sortie ; le bout qui joue vraiment', () => {
  const h = [{ t: 1000, niveau: 0.1 }, { t: 1100, niveau: 0.2 }, { t: 1200, niveau: 0.3 }, { t: 1300, niveau: 0.4 }];
  assert.equal(Avatar.retarder(h, 1300, 0).niveau, 0.4);
  assert.equal(Avatar.retarder(h, 1300, 150).niveau, 0.2, '150 ms de sortie : la voix d’il y a 150 ms');
  assert.equal(Avatar.retarder(h, 1300, 1000), null, 'rien d’aussi vieux');
  const m = [{ debut: 5000, duree: 2000 }];
  assert.ok(Avatar.dansUnMorceau(m, 6000) && !Avatar.dansUnMorceau(m, 7500) && !Avatar.dansUnMorceau(m, 4000));
});

test('(07/11, « que cette image puisse bouger correctement ») un dessin : son gabarit depuis trois touches (et ses oreilles), vérifié, cadré', () => {
  const g = Avatar.gabaritDepuisTouches([{ x: 0.43, y: 0.49 }, { x: 0.58, y: 0.49 }, { x: 0.5, y: 0.57 }, { x: 0.35, y: 0.3 }, { x: 0.65, y: 0.3 }]);
  assert.ok(Avatar.gabaritValide(g));
  assert.equal(g.yeux.length, 2); assert.equal(g.oreilles.length, 2);
  assert.ok(g.oreilles[0].base.y > g.oreilles[0].pointe.y && g.oreilles[0].base.y < g.yeux[0].y, 'la base de l’oreille entre l’œil et la pointe');
  assert.ok(g.yeux[0].rx > g.yeux[0].ry, 'des yeux en amande');
  assert.ok(Avatar.gabaritValide(Avatar.gabaritParDefaut()));
  assert.ok(!Avatar.gabaritValide({ type: 'dessin', yeux: [] }) && !Avatar.gabaritValide(null) && !Avatar.gabaritValide({ ...g, oreilles: [1, 2, 3] }));
  const s = Avatar.cadrerDessin(1024, 1024);
  assert.ok(Math.abs(s.l / s.h - 0.8) < 1e-9 && s.l <= 1024 && s.h <= 1024 + 1e-9, 'le dessin carré remplit le cadre 4:5 (sans bande)');
  const gc = Avatar.gabaritDansCadre(g, s, 1024, 1024);
  assert.ok(Math.abs(gc.yeux[0].x - ((0.43 * 1024 - s.x) / s.l)) < 1e-9);
  assert.ok(Avatar.cadrerDessin(1024, 1024, 480, 600, { zoom: 1.5 }).l < s.l, 'zoom : on s’approche');
});

test('un dessin vit : sa bouche suit sa voix, ses yeux clignent et se plissent au rire, ses oreilles tombent quand il est triste', () => {
  const parle = Avatar.ciblesDessin({ voix: { niveau: 0.15, aigu: 0 } }, 0);
  assert.ok(parle.ouvre > 0.5 && parle.lueur > 0.4, 'il parle : la bouche s’ouvre, il brille');
  assert.equal(Avatar.ciblesDessin({ voix: { niveau: 0, aigu: 0 } }, 0).ouvre, 0);
  assert.ok(Avatar.ciblesDessin({ cligne: true }, 0).cligneG === 1);
  const rit = Avatar.ciblesDessin({ rire: 1 }, 0.05);
  assert.ok(rit.cligneG > 0.25 && rit.sourire > 0.5 && rit.lueur > 0.5);
  const triste = Avatar.ciblesDessin({ expression: 'tristesse' }, 0), fache = Avatar.ciblesDessin({ expression: 'colere' }, 0);
  assert.ok(triste.oreilleG > 0.1 && fache.oreilleG < -0.1 && triste.sourire < 0, 'triste : les oreilles tombent ; en colère : en arrière');
  assert.ok(triste.teinte[2] > triste.teinte[0], 'triste : plus froid');
});

test('(07/11) la page : les lèvres prennent la voix qui sort (la latence), un dessin se construit avec son gabarit, ses yeux et sa bouche se placent d’un toucher', () => {
  const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  assert.match(page, /const sortie = Avatar\.retarder\(histoireVoixAvatar, maintenant, lat\);/);
  assert.match(page, /Avatar\.dansUnMorceau\(parole\.morceaux, maintenant - lat\)/, 'sa voix du téléphone : le bout qui joue vraiment, pas le texte');
  assert.match(page, /return Math\.min\(1500, Math\.max\(ms, Number\(etat\.sortieVoixMs\) \|\| 0\)\);/);
  assert.match(page, /avatarEtat\.instance = Avatar\.creerDessin\(\$\('avatarScene'\), \{ image: photo, gabarit: Avatar\.gabaritDansCadre\(gabarit, s, image\.width, image\.height\)/);
  assert.match(page, /const points = await Avatar\.detecter\(image\)\.catch\(\(\) => null\);/, 'pas de visage humain : un dessin, pas une erreur');
  assert.match(page, /const g = Avatar\.gabaritDepuisTouches\(t\);/);
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8'), /id="avatarPlacer"/);
});

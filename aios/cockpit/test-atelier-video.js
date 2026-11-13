/* (13/11, Ahmed : « uploader ses photos et ses musiques et en faire des vidéos TikTok, Insta ») l'atelier VIDÉO côté cockpit : les routes
   d'atelier-video.js sur des dossiers jetables (le python est simulé : jamais la vraie file ni la vraie médiathèque), le dépôt en flux
   (taille, type, nom, collection), les fichiers servis sans sortir de leur dossier, l'effacement, la demande de vidéo nettoyée, le réglage
   « atelier_video », le branchement dans atelier.js et server.js, et la page (rien d'une donnée piégée ne devient du HTML).
   node --test test-atelier-video.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const vm = require('node:vm');
const AV = require('./atelier-video.js');
const A = require('./atelier.js');

const lireCorps = (req, max) => new Promise((ok) => { const m = []; let n = 0; req.on('data', c => { n += c.length; if (n <= max) m.push(c); }); req.on('end', () => ok(n > max ? null : Buffer.concat(m))); });
const ecrire = (f, d) => { fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, typeof d === 'string' || Buffer.isBuffer(d) ? d : JSON.stringify(d)); };
function serveurDe(a) {
  return new Promise((ok) => { const srv = http.createServer((req, res) => a.route(req, res, new URL(req.url, 'http://x').pathname)); srv.listen(0, '127.0.0.1', () => ok(srv)); });
}
async function appel(srv, methode, chemin, corps, entetes = {}) {
  const brut = Buffer.isBuffer(corps) || typeof corps === 'string';
  const r = await fetch(`http://127.0.0.1:${srv.address().port}${chemin}`, { method: methode,
    headers: { 'Content-Type': brut ? 'application/octet-stream' : 'application/json', ...entetes },
    body: corps === undefined ? undefined : brut ? corps : JSON.stringify(corps) });
  const b = Buffer.from(await r.arrayBuffer());
  let j = null; try { j = JSON.parse(b.toString()); } catch (_) {}
  return { statut: r.status, j, b, h: r.headers };
}

const VID = '20261113-101500-a1b-manteau-hiver';
function lieux() {
  const r = fs.mkdtempSync(path.join(os.tmpdir(), 'atelier-video-'));
  const jarvis = path.join(r, 'jarvis'), med = path.join(jarvis, 'mediatheque'), v = path.join(jarvis, 'videos'), t = path.join(jarvis, 'cwd', 'taches');
  ecrire(path.join(med, 'Hiver 2026', 'look 1.jpg'), Buffer.from([0xff, 0xd8, 0xff, 1, 2, 3]));
  ecrire(path.join(med, 'Hiver 2026', 'look 2.jpg'), Buffer.from([0xff, 0xd8, 0xff, 4]));
  ecrire(path.join(med, 'Hiver 2026', 'son.mp3'), 'ID3 son');
  ecrire(path.join(med, 'Hiver 2026', 'notes.txt'), 'pas un média');
  ecrire(path.join(med, '.apercus', 'Hiver 2026', 'look 1.jpg.jpg'), Buffer.from([0xff, 0xd8, 0xff, 9]));
  ecrire(path.join(med, '.analyses', 'Hiver 2026', 'son.mp3.json'), { taille: 7, duree: 182.4, bpm: 124.1 });
  ecrire(path.join(med, 'Été', 'défilé.wav'), 'RIFF');
  ecrire(path.join(med, '.depot', 'reste.jpg'), 'x');
  ecrire(path.join(med, '_polices', 'marque.ttf'), 'true');
  ecrire(path.join(jarvis, 'secret.txt'), 'PIEGE');
  ecrire(path.join(v, `${VID}-9x16.mp4`), Buffer.alloc(5000, 1));
  ecrire(path.join(v, `${VID}-couverture.jpg`), Buffer.alloc(100, 2));
  ecrire(path.join(v, `${VID}.jpg`), Buffer.alloc(50, 3));
  ecrire(path.join(v, `${VID}.json`), { nom: VID, titre: 'Manteau Hiver', type: 'video', etat: 'prête', fin: 50, par: 'papa',
    fichiers: [path.join(v, `${VID}-9x16.mp4`), path.join(v, `${VID}-couverture.jpg`)], couverture: path.join(v, `${VID}-couverture.jpg`), vignette: path.join(v, `${VID}.jpg`),
    mesures: { bpm: 124.1, passage: [42, 57], raison: 'le refrain probable', son: { lufs: -14.1 }, calage_ms: { mediane: 8, max: 16, coupes: 7 }, coupes: 7 },
    recette: { photos: [{ collection: 'Hiver 2026', fichier: 'look 1.jpg' }], musique: { collection: 'Hiver 2026', fichier: 'son.mp3' }, formats: ['9:16'],
      duree_s: 15, rythme: 'auto', transition: 'auto', textes: { marque: 'Maison Zayn', prix: '189 €' } } });
  // une vidéo en cours (sa tâche vit), avec sa jauge
  ecrire(path.join(v, '20261113-102000-c3d-robe.json'), { nom: '20261113-102000-c3d-robe', titre: 'Robe', type: 'video', etat: 'en cours', tache: 'T-20261113-102000-abcd', debut: 60 });
  ecrire(path.join(t, 'T-20261113-102000-abcd.json'), { id: 'T-20261113-102000-abcd', etat: 'en cours', video: { titre: 'Robe' } });
  ecrire(path.join(t, 'T-20261113-102000-abcd.log'), 'Atelier vidéo\nPROGRESSION 8% le son\nPROGRESSION 47% images 9:16\n');
  ecrire(path.join(t, 'T-20261113-090000-0000.json'), { id: 'T-20261113-090000-0000', etat: 'en cours', commande: 'python calcul.py' });
  return { r, jarvis, med, v, t };
}
const sansEnv = () => { const e = process.env.JARVIS_ATELIER_VIDEO; delete process.env.JARVIS_ATELIER_VIDEO; return () => { if (e !== undefined) process.env.JARVIS_ATELIER_VIDEO = e; }; };

test('les noms : collection et fichier envoyé ne sortent jamais de leur place', () => {
  assert.equal(AV.nomCollection('  Hiver   2026 '), 'Hiver 2026');
  assert.equal(AV.nomCollection('Été · Défilé'), 'Été Défilé');
  for (const m of ['../..', '..', '/', '__', '', '. _ .']) assert.equal(AV.nomCollection(m), null, m);
  assert.equal(AV.nomCollection('../../etc'), 'etc');
  assert.equal(AV.nomCollection('.cache'), 'cache', 'jamais un dossier caché (comme atelier_video.nom_collection)');
  assert.equal(AV.nomDepot(encodeURIComponent('../../IMG 1.JPG')), 'IMG 1.JPG');
  assert.equal(AV.nomDepot(encodeURIComponent('a\\b\\c.png')), 'c.png');
  assert.equal(AV.nomDepot(encodeURIComponent('x‮gpj.exe')), 'x_gpj.exe');
  assert.equal(AV.nomDepot('%E0%A4%A'), null, 'un nom mal encodé');
});

test('l’état : collections, photos, musiques (et leur tempo), polices, vidéos finies, en cours avec leur jauge', async () => {
  const remettre = sansEnv();
  const L = lieux();
  try {
    const a = AV.creer({ jarvis: L.jarvis, anamnese: L.r, lireCorps, appeler: () => ({ ok: true }) });
    const e = a.etat();
    assert.equal(e.allume, true);
    assert.equal(e.visuel_installe, false, 'sans .venv-image : pas d’atelier visuel (le PC de l’ami)');
    assert.deepEqual(e.collections.map(c => c.nom), ['Été', 'Hiver 2026'], 'ni .depot, ni .apercus, ni _polices');
    const h = e.collections[1];
    assert.deepEqual(h.photos.map(p => [p.f, p.apercu]), [['look 1.jpg', true], ['look 2.jpg', false]]);
    assert.deepEqual(h.musiques.map(m => [m.f, m.bpm, m.duree_s]), [['son.mp3', 124.1, 182.4]]);
    assert.deepEqual(e.polices, ['marque.ttf']);
    assert.equal(e.videos.length, 1);
    const v = e.videos[0];
    assert.deepEqual(v.videos, [{ f: `${VID}-9x16.mp4`, format: '9:16' }]);
    assert.equal(v.couverture, `${VID}-couverture.jpg`);
    assert.equal(v.vignette, `${VID}.jpg`);
    assert.equal(v.lufs, -14.1);
    assert.deepEqual(v.recette.textes, { marque: 'Maison Zayn', prix: '189 €' });
    assert.equal(e.enCours.length, 1);
    assert.deepEqual(e.enCours[0].progres, { f: 0.47, texte: 'images 9:16' });
  } finally { remettre(); }
});

test('le dépôt : en flux dans .depot, puis le python le range ; taille, type, nom et collection vérifiés', async () => {
  const remettre = sansEnv();
  const L = lieux(), appels = [];
  const a = AV.creer({ jarvis: L.jarvis, anamnese: L.r, lireCorps, appeler: (cmd, q) => {
    appels.push([cmd, q]);
    const contenu = fs.readFileSync(q.chemin);
    if (contenu.toString() === 'pas une photo') return { ok: false, erreur: 'type refusé' };
    const d = path.join(L.med, q.collection); fs.mkdirSync(d, { recursive: true });
    fs.renameSync(q.chemin, path.join(d, q.nom));
    return { ok: true, collection: q.collection, fichier: q.nom, type: 'photo' };
  } });
  const srv = await serveurDe(a);
  try {
    const jpeg = Buffer.concat([Buffer.from([0xff, 0xd8, 0xff]), Buffer.alloc(300000, 7)]);
    let r = await appel(srv, 'POST', `/api/atelier/media/deposer?collection=${encodeURIComponent('Été 2027')}`, jpeg, { 'X-Nom': encodeURIComponent('../../IMG 0001.jpg') });
    assert.equal(r.statut, 200, JSON.stringify(r.j));
    assert.equal(appels[0][0], 'importer');
    assert.equal(appels[0][1].collection, 'Été 2027');
    assert.equal(appels[0][1].nom, 'IMG 0001.jpg');
    assert.equal(appels[0][1].deplacer, true);
    assert.equal(path.dirname(appels[0][1].chemin), path.join(L.med, '.depot'), 'reçu dans .depot');
    assert.deepEqual(fs.readFileSync(path.join(L.med, 'Été 2027', 'IMG 0001.jpg')), jpeg, 'le fichier entier, intact');
    // refusé par le python : le dépôt ne reste pas
    r = await appel(srv, 'POST', '/api/atelier/media/deposer?collection=Hiver', 'pas une photo', { 'X-Nom': 'faux.jpg' });
    assert.equal(r.statut, 409);
    assert.match(r.j.erreur, /type refusé/);
    assert.deepEqual(fs.readdirSync(path.join(L.med, '.depot')).sort(), ['reste.jpg']);
    // refusés par le cockpit, sans appeler le python
    const n = appels.length;
    r = await appel(srv, 'POST', '/api/atelier/media/deposer?collection=..%2F..', jpeg, { 'X-Nom': 'a.jpg' });
    assert.equal(r.statut, 400);
    r = await appel(srv, 'POST', '/api/atelier/media/deposer?collection=Hiver', jpeg, { 'X-Nom': 'virus.exe' });
    assert.equal(r.statut, 415);
    r = await appel(srv, 'POST', '/api/atelier/media/deposer?collection=Hiver', Buffer.alloc(0), { 'X-Nom': 'vide.jpg' });
    assert.equal(r.statut, 400);
    r = await appel(srv, 'POST', '/api/atelier/media/deposer?collection=Hiver', jpeg, {});
    assert.equal(r.statut, 400);
    assert.equal(appels.length, n);
    // trop lourd : annoncé (Content-Length), refusé avant d'écrire
    const gros = await new Promise((ok) => {
      const req = http.request({ host: '127.0.0.1', port: srv.address().port, method: 'POST', path: '/api/atelier/media/deposer?collection=Hiver',
        headers: { 'X-Nom': 'gros.wav', 'Content-Length': String(201 * 1024 * 1024) } }, (res) => { let b = ''; res.on('data', c => { b += c; }); res.on('end', () => ok({ statut: res.statusCode, b })); });
      req.on('error', () => ok({ statut: 'coupé' }));
      req.write(Buffer.alloc(1024)); req.end();
    });
    assert.ok(gros.statut === 413 || gros.statut === 'coupé', JSON.stringify(gros));
    assert.equal(appels.length, n);
  } finally { srv.close(); remettre(); }
});

test('les fichiers : une photo, son aperçu, une musique, une vidéo — jamais hors de leur dossier ; Range pour avancer', async () => {
  const remettre = sansEnv();
  const L = lieux();
  const srv = await serveurDe(AV.creer({ jarvis: L.jarvis, anamnese: L.r, lireCorps, appeler: () => ({ ok: true }) }));
  try {
    let r = await appel(srv, 'GET', `/api/atelier/media/fichier?c=${encodeURIComponent('Hiver 2026')}&f=${encodeURIComponent('look 1.jpg')}`);
    assert.equal(r.statut, 200); assert.equal(r.h.get('content-type'), 'image/jpeg'); assert.equal(r.b.length, 6);
    r = await appel(srv, 'GET', `/api/atelier/media/fichier?c=${encodeURIComponent('Hiver 2026')}&f=${encodeURIComponent('look 1.jpg')}&apercu=1`);
    assert.equal(r.statut, 200); assert.deepEqual([...r.b], [0xff, 0xd8, 0xff, 9]);
    r = await appel(srv, 'GET', `/api/atelier/media/fichier?c=${encodeURIComponent('Hiver 2026')}&f=son.mp3`);
    assert.equal(r.h.get('content-type'), 'audio/mpeg');
    r = await appel(srv, 'GET', `/api/atelier/video/fichier?f=${VID}-9x16.mp4`, undefined, { Range: 'bytes=100-199' });
    assert.equal(r.statut, 206); assert.equal(r.b.length, 100); assert.equal(r.h.get('content-range'), 'bytes 100-199/5000');
    r = await appel(srv, 'GET', `/api/atelier/video/fichier?f=${VID}-couverture.jpg&telecharger=1`);
    assert.match(r.h.get('content-disposition'), /attachment/);
    for (const [c, f] of [['Hiver 2026', '../../secret.txt'], ['..', 'secret.txt'], ['Hiver 2026', 'notes.txt'], ['.depot', 'reste.jpg'],
      ['Hiver 2026/..', 'secret.txt'], ['Hiver 2026', '.']]) {
      r = await appel(srv, 'GET', `/api/atelier/media/fichier?c=${encodeURIComponent(c)}&f=${encodeURIComponent(f)}`);
      assert.equal(r.statut, 404, `${c} / ${f}`);
    }
    for (const f of ['../secret.txt', `${VID}.json`, 'secret.txt', `../videos/${VID}-9x16.mp4`]) {
      r = await appel(srv, 'GET', `/api/atelier/video/fichier?f=${encodeURIComponent(f)}`);
      assert.equal(r.statut, 404, f);
    }
  } finally { srv.close(); remettre(); }
});

test('effacer : un fichier (et son aperçu, son analyse), une collection vide seulement ; une vidéo finie (pas en cours)', async () => {
  const remettre = sansEnv();
  const L = lieux();
  const srv = await serveurDe(AV.creer({ jarvis: L.jarvis, anamnese: L.r, lireCorps, appeler: () => ({ ok: true }) }));
  try {
    let r = await appel(srv, 'POST', '/api/atelier/media/effacer', { collection: 'Hiver 2026', fichier: 'look 1.jpg' });
    assert.equal(r.statut, 200);
    assert.ok(!fs.existsSync(path.join(L.med, 'Hiver 2026', 'look 1.jpg')) && !fs.existsSync(path.join(L.med, '.apercus', 'Hiver 2026', 'look 1.jpg.jpg')));
    r = await appel(srv, 'POST', '/api/atelier/media/effacer', { collection: 'Hiver 2026', fichier: 'son.mp3' });
    assert.ok(!fs.existsSync(path.join(L.med, '.analyses', 'Hiver 2026', 'son.mp3.json')));
    for (const x of [{ collection: 'Hiver 2026', fichier: '../../secret.txt' }, { collection: '..', fichier: 'secret.txt' }, { collection: 'Hiver 2026', fichier: 'notes.txt' }]) {
      r = await appel(srv, 'POST', '/api/atelier/media/effacer', x);
      assert.equal(r.statut, 404, JSON.stringify(x));
    }
    assert.ok(fs.existsSync(path.join(L.jarvis, 'secret.txt')));
    r = await appel(srv, 'POST', '/api/atelier/media/effacer', { collection: 'Hiver 2026', fichier: '' });
    assert.equal(r.statut, 409, 'pas vide : look 2 et notes.txt');
    fs.rmSync(path.join(L.med, 'Été', 'défilé.wav'));
    r = await appel(srv, 'POST', '/api/atelier/media/effacer', { collection: 'Été', fichier: '' });
    assert.equal(r.statut, 200); assert.ok(!fs.existsSync(path.join(L.med, 'Été')));
    r = await appel(srv, 'POST', '/api/atelier/media/collection', { nom: '  Été   2027 ' });
    assert.equal(r.j.nom, 'Été 2027'); assert.ok(fs.statSync(path.join(L.med, 'Été 2027')).isDirectory());
    r = await appel(srv, 'POST', '/api/atelier/video/effacer', { nom: '20261113-102000-c3d-robe' });
    assert.equal(r.statut, 409, 'en cours');
    r = await appel(srv, 'POST', '/api/atelier/video/effacer', { nom: '../secret' });
    assert.equal(r.statut, 404);
    r = await appel(srv, 'POST', '/api/atelier/video/effacer', { nom: VID });
    assert.equal(r.statut, 200);
    assert.deepEqual(fs.readdirSync(L.v).sort(), ['20261113-102000-c3d-robe.json']);
  } finally { srv.close(); remettre(); }
});

test('créer, prévisualiser, refaire, arrêter : une demande nettoyée part au python « lancer »', async () => {
  const remettre = sansEnv();
  const L = lieux(), lances = [];
  const a = AV.creer({ jarvis: L.jarvis, anamnese: L.r, lireCorps, appeler: (cmd, q) => { lances.push([cmd, q]); return q.collection === 'Refus' ? { ok: false, erreur: 'collection inconnue' } : { ok: true, tache: 'T-1', nom: 'n' }; } });
  const srv = await serveurDe(a);
  try {
    let r = await appel(srv, 'POST', '/api/atelier/video/creer', { collection: 'Hiver 2026', photos: ['Hiver 2026/look 2.jpg', '/Hiver 2026/look 1.jpg', ''],
      musique: 'Hiver 2026/son.mp3', format: '9:16', duree_s: '30', rythme: 'rapide', marque: 'Maison\nZayn', prix: '189 €', appel: 'Lien en bio', apercu: true, inconnu: 'x' });
    assert.equal(r.statut, 200);
    const [cmd, q] = lances[0];
    assert.equal(cmd, 'lancer');
    assert.deepEqual(q.photos, ['Hiver 2026/look 2.jpg', 'Hiver 2026/look 1.jpg']);
    assert.equal(q.duree_s, 30); assert.equal(q.rythme, 'rapide'); assert.equal(q.marque, 'Maison Zayn'); assert.equal(q.apercu, true);
    assert.equal(q.debut_s, null); assert.ok(!('inconnu' in q)); assert.ok(!('refaire' in q));
    r = await appel(srv, 'POST', '/api/atelier/video/creer', { format: ['9:16', '4:5', '1:1', 'x'], collection: 'Hiver 2026' });
    assert.equal(lances[1][1].format, '9:16 et 4:5 et 1:1');
    r = await appel(srv, 'POST', '/api/atelier/video/creer', { collection: 'Refus' });
    assert.equal(r.statut, 409); assert.match(r.j.erreur, /inconnue/);
    r = await appel(srv, 'POST', '/api/atelier/video/creer', {});
    assert.equal(r.statut, 400);
    r = await appel(srv, 'POST', '/api/atelier/video/creer', { refaire: VID, rythme: 'lent', prix: '' });
    assert.equal(r.statut, 200); assert.equal(lances.at(-1)[1].refaire, VID);
    const n = lances.length;
    r = await appel(srv, 'POST', '/api/atelier/video/creer', { refaire: '../../x' });
    assert.equal(r.statut, 404); assert.equal(lances.length, n);
    r = await appel(srv, 'POST', '/api/atelier/video/arreter', { tache: 'T-20261113-102000-abcd' });
    assert.equal(r.statut, 200); assert.ok(fs.existsSync(path.join(L.t, 'T-20261113-102000-abcd.stop')));
    r = await appel(srv, 'POST', '/api/atelier/video/arreter', { tache: 'T-20261113-090000-0000' });
    assert.equal(r.statut, 404, 'une autre tâche de fond ne s’arrête pas d’ici');
    r = await appel(srv, 'GET', '/api/atelier/video/creer');
    assert.equal(r.statut, 405);
  } finally { srv.close(); remettre(); }
});

test('le réglage « atelier_video » : éteint, tout est refusé et l’état le dit ; la variable d’environnement passe devant', async () => {
  const remettre = sansEnv();
  const L = lieux(), lances = [];
  const a = AV.creer({ jarvis: L.jarvis, anamnese: L.r, lireCorps, appeler: (cmd, q) => { lances.push(q); return { ok: true }; } });
  const srv = await serveurDe(a);
  try {
    ecrire(path.join(L.jarvis, 'modules.json'), { modules: { atelier_video: false, studio: false } });
    let r = await appel(srv, 'GET', '/api/atelier/media/etat');
    assert.equal(r.statut, 200); assert.equal(r.j.allume, false);
    for (const [m, c, corps] of [['POST', '/api/atelier/video/creer', { collection: 'Hiver 2026' }], ['POST', '/api/atelier/media/collection', { nom: 'X' }],
      ['GET', `/api/atelier/video/fichier?f=${VID}-9x16.mp4`]]) {
      r = await appel(srv, m, c, corps);
      assert.equal(r.statut, 409, c);
    }
    assert.equal(lances.length, 0);
    ecrire(path.join(L.jarvis, 'modules.json'), { atelier_video: true });
    assert.equal(a.allume(), true);
    ecrire(path.join(L.jarvis, 'modules.json'), { atelier_video: false });
    assert.equal(a.allume(), false);
    process.env.JARVIS_ATELIER_VIDEO = '1';
    assert.equal(a.allume(), true);
  } finally { srv.close(); delete process.env.JARVIS_ATELIER_VIDEO; remettre(); }
});

test('atelier.js branche l’atelier vidéo, dit s’il est allumé et si l’atelier visuel est installé', async () => {
  const remettre = sansEnv();
  const L = lieux();
  const a = A.creer({ jarvis: L.jarvis, anamnese: L.r, lireCorps, appeler: () => ({ ok: true }), video: { appeler: () => ({ ok: true, tache: 'T-v' }) } });
  const srv = await serveurDe(a);
  try {
    let r = await appel(srv, 'GET', '/api/atelier/etat');
    assert.equal(r.j.video, true); assert.equal(r.j.visuel_installe, false);
    r = await appel(srv, 'GET', '/api/atelier/media/etat');
    assert.equal(r.statut, 200); assert.equal(r.j.collections.length, 2);
    r = await appel(srv, 'POST', '/api/atelier/video/creer', { collection: 'Hiver 2026' });
    assert.equal(r.j.tache, 'T-v');
    const SRV = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
    assert.match(SRV, /'effort_regler', 'mediatheque_voir', 'mediatheque_ajouter', 'video_creer', 'video_refaire', 'parler_bouton'/, 'les outils de l’IA');
    assert.match(SRV, /if \(p\.startsWith\('\/api\/atelier\/'\)\) \{[^\n]*\n\s*if \(!jetonValide\(req\)\)/, 'derrière le jeton');
  } finally { srv.close(); remettre(); }
});

/* ---------- la page ---------- */
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'atelier-video-page.js'), 'utf8');
const HTML = fs.readFileSync(path.join(__dirname, 'public', 'atelier.html'), 'utf8');

test('la page : la section, ses champs, son script ; les sections de l’atelier visuel se cachent sans lui', () => {
  for (const id of ['videoCarte', 'collections', 'deposerMedia', 'fichiersMedia', 'nouvelleCollection', 'photosMedia', 'musiquesMedia', 'marqueVideo', 'pieceVideo',
    'prixVideo', 'appelVideo', 'apercuVideo', 'exporterVideo', 'apercuZone', 'videosFinies', 'calculsVideo', 'envois']) {
    assert.match(HTML, new RegExp(`id="${id}"`), id);
  }
  for (const v of ['9:16', '4:5', '1:1']) assert.match(HTML, new RegExp(`name="fmtVideo" value="${v}"`));
  for (const v of ['7', '15', '30', '60']) assert.match(HTML, new RegExp(`name="dureeVideo" value="${v}"`));
  assert.match(HTML, /accept="[^"]*heic[^"]*\.mp3[^"]*\.m4a[^"]*\.wav/);
  assert.equal((HTML.match(/<section data-visuel /g) || []).length, 4);
  assert.match(HTML, /<div class="sous" data-visuel>Les images et les clips/, 'l’annonce de l’atelier visuel se cache avec lui');
  assert.match(HTML, /<script src="\/atelier-page\.js"><\/script>\n\s*<script src="\/atelier-video-page\.js"><\/script>/);
  assert.match(HTML, /input\[type=text\][^{]*\{[^}]*font-size: 16px/, 'pas de zoom au toucher sur iPhone');
  assert.ok(!/https?:\/\//.test(PAGE), 'la page n’appelle rien dehors');
});

function element(id) {
  return { id, innerHTML: '', textContent: '', hidden: true, value: '', disabled: false, dataset: {}, className: '', style: {},
    addEventListener() {}, focus() {}, click() {}, contains: () => false, after() {}, appendChild() {}, scrollIntoView() {},
    querySelector: () => null, querySelectorAll: () => [], get lastElementChild() { return { set outerHTML(_) {}, textContent: '' }; } };
}
async function pageAvec(etat) {
  const els = {};
  const document = { getElementById: (id) => (els[id] = els[id] || element(id)), querySelector: () => null, querySelectorAll: () => [], addEventListener() {},
    createElement: () => element('x'), body: element('body'), hidden: false };
  const ctx = { console, Math, Number, String, Object, Array, JSON, Date, Set, Map, Promise, RegExp, encodeURIComponent, URL: { createObjectURL: () => 'blob:x' },
    document, window: { jeton: () => 'j', esc: (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])),
      prompt: () => null, confirm: () => false },
    localStorage: { getItem: () => null, setItem() {} }, setTimeout: () => 0, clearTimeout() {}, CSS: { escape: (s) => s },
    fetch: async () => ({ ok: true, json: async () => etat, blob: async () => ({}) }) };
  ctx.window.document = document;
  vm.createContext(ctx);
  vm.runInContext(PAGE, ctx);
  for (let i = 0; i < 5; i++) await new Promise(r => setImmediate(r));
  return els;
}

test('la page : un nom de collection, de photo, de musique ou un titre piégé s’affiche en texte, jamais en HTML', async () => {
  const P = '"><img src=x onerror=alert(1)>';
  const etat = { allume: true, visuel_installe: true, polices: [],
    collections: [{ nom: `Hiver${P}`, photos: [{ f: `look${P}.jpg`, apercu: true, taille: 10 }], musiques: [{ f: `son${P}.mp3`, taille: 10, bpm: 120 }] }],
    videos: [{ nom: VID, titre: `Manteau${P}`, videos: [{ f: `${VID}-9x16.mp4`, format: '9:16' }], couverture: `${VID}-couverture.jpg`, vignette: `${VID}.jpg`,
      duree_s: 15, bpm: 124, lufs: -14.1, raison: `refrain${P}`, recette: {} }],
    apercus: [], enCours: [{ nom: 'n', titre: `Robe${P}`, type: 'video', tache: `T-1${P}`, etat: 'en cours', progres: { f: 0.5, texte: `images${P}` } },
      { nom: 'm', titre: `Jupe${P}`, type: 'apercu', etat: 'ratée', erreur: `boum${P}` }] };
  const els = await pageAvec(etat);
  assert.equal(els.videoCarte.hidden, false);
  let vus = 0;
  for (const id of ['collections', 'photosMedia', 'musiquesMedia', 'videosFinies', 'calculsVideo']) {
    const h = els[id].innerHTML;
    assert.ok(h.length > 20, `${id} est rendu`);
    assert.ok(!/<img src=x/i.test(h) && !/<[a-z]+[^>]*\sonerror=["']alert/i.test(h), `${id} : la donnée piégée est devenue du HTML :\n${h}`);
    if (h.includes('&lt;img src=x onerror=alert(1)&gt;')) vus++;
  }
  assert.equal(vus, 5, 'la donnée reste visible, en texte');
  // éteint : la section se cache
  const e2 = await pageAvec({ ...etat, allume: false });
  assert.equal(e2.videoCarte.hidden, true);
});

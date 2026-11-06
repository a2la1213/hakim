/* (06/11, Ahmed : « une zone visuelle dans le cockpit où Hakim pourrait créer des images et des clips quand il veut, pour nos futurs
   albums et clips ») l'Atelier visuel : les routes d'atelier.js sur des dossiers jetables (jamais la vraie file de calcul : la
   création est simulée), la page, le menu, et le branchement dans server.js. (test-atelier.js, lui, est son atelier de terminal.)
   node --test test-atelier-visuel.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const A = require('./atelier.js');

const lireCorps = (req, max) => new Promise((ok) => { const m = []; let n = 0; req.on('data', c => { n += c.length; if (n <= max) m.push(c); }); req.on('end', () => ok(n > max ? null : Buffer.concat(m))); });
function serveurDe(a) {
  return new Promise((ok) => { const srv = http.createServer((req, res) => a.route(req, res, new URL(req.url, 'http://x').pathname)); srv.listen(0, '127.0.0.1', () => ok(srv)); });
}
async function appel(srv, methode, chemin, corps, entetes = {}) {
  const r = await fetch(`http://127.0.0.1:${srv.address().port}${chemin}`, { method: methode, headers: { 'Content-Type': 'application/json', ...entetes },
    body: corps === undefined ? undefined : JSON.stringify(corps) });
  const b = Buffer.from(await r.arrayBuffer());
  let j = null; try { j = JSON.parse(b.toString()); } catch (_) {}
  return { statut: r.status, j, b, h: r.headers };
}
const ecrire = (f, d) => { fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, typeof d === 'string' || Buffer.isBuffer(d) ? d : JSON.stringify(d)); };

function lieux() {
  const r = fs.mkdtempSync(path.join(os.tmpdir(), 'atelier-visuel-'));
  const jarvis = path.join(r, 'jarvis'), v = path.join(jarvis, 'visuels'), t = path.join(jarvis, 'cwd', 'taches'), c = path.join(jarvis, 'chansons');
  ecrire(path.join(c, '20261106-192323-lanterne.json'), { nom: '20261106-192323-lanterne', titre: 'Lanterne', etat: 'prête', mp3: path.join(c, 'x.mp3'), duree_s: 120, fin: 5 });
  ecrire(path.join(c, '20261106-200000-brouillon.json'), { nom: '20261106-200000-brouillon', titre: 'Brouillon', etat: 'en cours' });
  ecrire(path.join(v, '20261106-200000-pochette.png'), Buffer.alloc(2048, 7));
  ecrire(path.join(v, '20261106-200000-pochette.json'), { type: 'image', nom: '20261106-200000-pochette', titre: 'Pochette', etat: 'prête', format: 'carre',
    fichier: path.join(v, '20261106-200000-pochette.png'), fin: 10, description: 'a lantern' });
  ecrire(path.join(v, '20261106-201000-lanterne-clip-9x16.mp4'), Buffer.alloc(5000, 1));
  ecrire(path.join(v, '20261106-201000-lanterne-clip-9x16.jpg'), Buffer.alloc(100, 1));
  ecrire(path.join(v, '20261106-201000-lanterne-clip.json'), { type: 'clip', nom: '20261106-201000-lanterne-clip', titre: 'Lanterne', etat: 'prête', style: 'spectre',
    chanson: { titre: 'Lanterne' }, duree_s: 15, fichiers: [path.join(v, '20261106-201000-lanterne-clip-9x16.mp4')], fin: 20 });
  // une création en cours (sa tâche vit), avec sa jauge
  ecrire(path.join(v, '20261106-202000-nuit.json'), { type: 'image', nom: '20261106-202000-nuit', titre: 'Nuit', etat: 'en cours', tache: 'T-20261106-202000-abcd', debut: 30 });
  ecrire(path.join(t, 'T-20261106-202000-abcd.json'), { id: 'T-20261106-202000-abcd', etat: 'en cours', visuel: { titre: 'Nuit' } });
  ecrire(path.join(t, 'T-20261106-202000-abcd.log'), 'Atelier : image\nPROGRESSION 0% attend la fin de la chanson\nPROGRESSION 43% pas 3/9\n');
  ecrire(path.join(t, 'T-20261106-190000-0000.json'), { id: 'T-20261106-190000-0000', etat: 'en cours', commande: 'python calcul.py' });
  ecrire(path.join(jarvis, 'secret.png'), 'PIEGE');
  return { r, jarvis, v, t };
}

test('les routes : la galerie, la jauge, les fichiers derrière un nom simple, créer, arrêter', async () => {
  const L = lieux(), lances = [];
  const a = A.creer({ jarvis: L.jarvis, lireCorps, appeler: (q) => { lances.push(q); return q.description === 'refus' ? { ok: false, erreur: 'une description' } : { ok: true, tache: 'T-1' }; } });
  const srv = await serveurDe(a);
  try {
    let r = await appel(srv, 'GET', '/api/atelier/etat');
    assert.equal(r.statut, 200);
    assert.deepEqual(r.j.images.map(x => [x.nom, x.f, x.format]), [['20261106-200000-pochette', '20261106-200000-pochette.png', 'carre']]);
    assert.deepEqual(r.j.clips[0].videos, [{ f: '20261106-201000-lanterne-clip-9x16.mp4', vignette: '20261106-201000-lanterne-clip-9x16.jpg', format: '9:16' }]);
    assert.deepEqual(r.j.chansons.map(c => c.titre), ['Lanterne'], 'seulement les chansons prêtes');
    assert.equal(r.j.enCours.length, 1);
    assert.deepEqual(r.j.enCours[0].progres, { f: 0.43, texte: 'pas 3/9' });
    assert.match(r.j.telephone, /Hakim › Atelier/);

    r = await appel(srv, 'GET', '/api/atelier/fichier?f=20261106-201000-lanterne-clip-9x16.mp4', undefined, { Range: 'bytes=0-99' });
    assert.equal(r.statut, 206); assert.equal(r.b.length, 100); assert.equal(r.h.get('content-type'), 'video/mp4');
    r = await appel(srv, 'GET', '/api/atelier/fichier?f=20261106-200000-pochette.png');
    assert.equal(r.statut, 200); assert.equal(r.h.get('content-type'), 'image/png'); assert.equal(r.b.length, 2048);
    for (const f of ['../secret.png', '/etc/hosts', 'secret.png', '20261106-200000-pochette.json', '.20261106-200000-x.png', '20261106-200000-pochette.png/..', '..%2Fsecret.png'])
      assert.equal((await appel(srv, 'GET', `/api/atelier/fichier?f=${encodeURIComponent(f)}`)).statut, 404, f);

    r = await appel(srv, 'POST', '/api/atelier/image', { description: 'Album cover\u0000, a lantern', format: '9:16', titre: 'Nuit' });
    assert.equal(r.statut, 200);
    assert.deepEqual(lances[0], { type: 'image', description: 'Album cover , a lantern', format: '9:16', titre: 'Nuit' });
    r = await appel(srv, 'POST', '/api/atelier/image', { description: 'refus' });
    assert.equal(r.statut, 409); assert.equal(r.j.erreur, 'une description');
    r = await appel(srv, 'POST', '/api/atelier/clip', { chanson: 'Lanterne', images: ['a', 'b', ...Array(20).fill('c')], style: 'ondes', format: '16:9', duree_s: 15, debut_s: -3 });
    assert.equal(r.statut, 200);
    assert.equal(lances[2].images.length, 12); assert.equal(lances[2].duree_s, 15); assert.equal(lances[2].debut_s, 0); assert.equal(lances[2].style, 'ondes');

    // arrêter : seulement une création de l'atelier en cours (jamais une autre tâche de fond)
    assert.equal((await appel(srv, 'POST', '/api/atelier/arreter', { tache: 'T-20261106-190000-0000' })).statut, 404);
    assert.equal((await appel(srv, 'POST', '/api/atelier/arreter', { tache: '../../x' })).statut, 404);
    assert.ok(!fs.existsSync(path.join(L.t, 'T-20261106-190000-0000.stop')));
    assert.equal((await appel(srv, 'POST', '/api/atelier/arreter', { tache: 'T-20261106-202000-abcd' })).statut, 200);
    assert.ok(fs.existsSync(path.join(L.t, 'T-20261106-202000-abcd.stop')));
    assert.equal((await appel(srv, 'DELETE', '/api/atelier/etat')).statut, 405);
  } finally { srv.close(); }
});

test('une création ratée reste visible une heure, une tâche morte n’est plus « en cours »', () => {
  const L = lieux();
  ecrire(path.join(L.v, '20261106-203000-rate.json'), { type: 'clip', nom: '20261106-203000-rate', titre: 'Raté', etat: 'ratée', erreur: 'ffmpeg : rendu figé', fin: Date.now() / 1000 - 60 });
  ecrire(path.join(L.v, '20261106-100000-vieux.json'), { type: 'clip', nom: '20261106-100000-vieux', titre: 'Vieux', etat: 'ratée', fin: Date.now() / 1000 - 7200 });
  ecrire(path.join(L.t, 'T-20261106-202000-abcd.json'), { id: 'T-20261106-202000-abcd', etat: 'perdue', visuel: {} });
  const e = A.creer({ jarvis: L.jarvis, lireCorps }).etat();
  assert.deepEqual(e.enCours.map(x => [x.titre, x.etat]), [['Raté', 'ratée']]);
  assert.equal(e.enCours[0].erreur, 'ffmpeg : rendu figé');
});

test('la page Atelier : son menu, ses fichiers derrière le jeton, rien en HTML venu des fiches', () => {
  const html = fs.readFileSync(path.join(__dirname, 'public', 'atelier.html'), 'utf8');
  const js = fs.readFileSync(path.join(__dirname, 'public', 'atelier-page.js'), 'utf8');
  assert.match(html, /Badges\.suivre\(document\.querySelector\('nav\.topnav'\), 'atelier'\)/);
  assert.match(html, /<script src="\/jeton\.js"><\/script>/);
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'badges.js'), 'utf8'), /\['studio', '\/studio', 'Studio'\], \['atelier', '\/atelier', 'Atelier'\]/);
  assert.match(js, /\/api\/atelier\/fichier\?f=\$\{encodeURIComponent\(f\)\}`, \{ headers: H\(\) \}/);
  // chaque valeur des fiches passe par esc() avant d'entrer dans le HTML
  for (const champ of ['x.titre', 'x.chanson', 'c.titre', 'x.f', 'v.f', 'x.erreur', 'x.tache'])
    assert.ok(!new RegExp(`\\$\\{${champ.replace('.', '\\.')}\\}`).test(js), `${champ} sans esc()`);
});

test('server.js : la route derrière le jeton, la page, et ses outils à la fin de la liste', () => {
  const SRV = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(SRV, /const ATELIER_VISUEL = require\('\.\/atelier\.js'\)\.creer\(\{ jarvis: JARVIS, anamnese: ANAMNESE, lireCorps \}\)/);
  const i = SRV.indexOf("if (p.startsWith('/api/atelier/'))");
  assert.ok(i > 0);
  assert.match(SRV.slice(i, i + 400), /if \(!jetonValide\(req\)\) \{ res\.writeHead\(403/);
  assert.match(SRV.slice(i, i + 400), /auditer\(`atelier:/);
  assert.match(SRV, /'\/studio': 'studio\.html', '\/atelier': 'atelier\.html' \}/);
  assert.match(SRV, /'studio_avis', 'image_creer', 'clip_creer', 'atelier_voir'\]\.map\(n => 'mcp__anamnese__' \+ n\)/);
});

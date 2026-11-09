/* (09/11, Ahmed : « alléger et accélérer tout le process ») les fichiers des pages : une empreinte (304 sans corps quand rien n'a
   changé) et gzip pour le texte. Mesuré ici sur les vrais fichiers que Parler charge à chaque ouverture.
   node --test test-envoi-statique.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const zlib = require('node:zlib');
const E = require('./envoi-statique.js');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');

// un petit serveur qui sert comme servirPage : la clé est date:taille du fichier
function serveur() {
  return new Promise((ok) => {
    const s = http.createServer((req, res) => {
      const fp = decodeURIComponent(new URL(req.url, 'http://x').searchParams.get('f'));
      const st = fs.statSync(fp), cle = `${st.mtimeMs}:${st.size}`;
      const type = fp.endsWith('.js') ? 'text/javascript' : fp.endsWith('.png') ? 'image/png' : 'text/css';
      if (E.dejaAJour(req, res, fp, cle, { 'Cache-Control': 'no-cache' })) return;
      E.envoyer(req, res, { fp, data: fs.readFileSync(fp), cle, type, entetes: { 'Cache-Control': 'no-cache' } });
    }).listen(0, '127.0.0.1', () => ok(s));
  });
}
function demander(port, f, entetes = {}) {
  return new Promise((ok, ko) => {
    http.get({ host: '127.0.0.1', port, path: `/?f=${encodeURIComponent(f)}`, headers: entetes }, (r) => {
      const morceaux = []; r.on('data', (m) => morceaux.push(m)); r.on('end', () => ok({ statut: r.statusCode, h: r.headers, corps: Buffer.concat(morceaux) }));
    }).on('error', ko);
  });
}

test('un script : gzip quand le navigateur l’accepte, puis 304 sans corps tant qu’il ne change pas, puis la nouvelle version', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'envoi-'));
  const f = path.join(dir, 'page.js');
  const texte = 'const x = 1;\n'.repeat(4000);
  fs.writeFileSync(f, texte);
  const s = await serveur(); const port = s.address().port;
  try {
    const a = await demander(port, f, { 'Accept-Encoding': 'gzip, deflate, br' });
    assert.equal(a.statut, 200);
    assert.equal(a.h['content-encoding'], 'gzip');
    assert.equal(a.h['cache-control'], 'no-cache', 'toujours revérifié');
    assert.ok(a.h.etag, 'une empreinte');
    assert.equal(zlib.gunzipSync(a.corps).toString(), texte, 'le même contenu');
    assert.ok(a.corps.length < texte.length / 10);
    const b = await demander(port, f, { 'Accept-Encoding': 'gzip', 'If-None-Match': a.h.etag });
    assert.equal(b.statut, 304);
    assert.equal(b.corps.length, 0, 'rien ne repart');
    const sans = await demander(port, f);                        // un client sans gzip : le texte brut
    assert.equal(sans.statut, 200); assert.equal(sans.h['content-encoding'], undefined); assert.equal(sans.corps.toString(), texte);
    fs.writeFileSync(f, texte + '// changé\n');                 // la page change : jamais l'ancienne
    const c = await demander(port, f, { 'Accept-Encoding': 'gzip', 'If-None-Match': a.h.etag });
    assert.equal(c.statut, 200);
    assert.notEqual(c.h.etag, a.h.etag);
    assert.match(zlib.gunzipSync(c.corps).toString(), /changé/);
  } finally { s.close(); fs.rmSync(dir, { recursive: true, force: true }); }
});

test('une image n’est pas recompressée ; une page no-store garde sa compression mais pas d’empreinte', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'envoi-'));
  const f = path.join(dir, 'i.png');
  fs.writeFileSync(f, Buffer.alloc(5000, 7));
  const s = await serveur(); const port = s.address().port;
  try {
    const a = await demander(port, f, { 'Accept-Encoding': 'gzip' });
    assert.equal(a.h['content-encoding'], undefined);
    assert.equal(a.corps.length, 5000);
  } finally { s.close(); fs.rmSync(dir, { recursive: true, force: true }); }
  const res = { h: null, corps: null, writeHead(n, h) { this.n = n; this.h = h; }, end(c) { this.corps = c; } };
  E.envoyer({ headers: { 'accept-encoding': 'gzip', 'if-none-match': '*' } }, res,
    { fp: '/x/parler.html', data: '<html>' + 'a'.repeat(3000), cle: '1:2:jeton', validateur: false, type: 'text/html; charset=utf-8', entetes: { 'Cache-Control': 'no-store' } });
  assert.equal(res.n, 200, 'jamais de 304 pour une page no-store');
  assert.equal(res.h.ETag, undefined);
  assert.equal(res.h['Content-Encoding'], 'gzip');
  assert.equal(res.h['Cache-Control'], 'no-store');
});

test('servirPage passe par envoi-statique, avec la requête (les deux appels)', () => {
  assert.match(SRC, /const EnvoiStatique = require\('\.\/envoi-statique\.js'\)/);
  assert.match(SRC, /servirPage\(res, fp, p, req\)/);
  assert.match(SRC, /servirPage\(res, path\.join\(PUBLIC, 'verrou\.html'\), '', req\)/);
  assert.match(SRC, /EnvoiStatique\.dejaAJour\(req, res, fp, cle, entetes\)/);
  assert.match(SRC, /'Cache-Control': 'no-store', 'Content-Security-Policy': cspDe/);
});

test('mesure : ce que Parler charge à chaque ouverture (scripts et styles de parler.html)', () => {
  const pub = path.join(__dirname, 'public');
  const html = fs.readFileSync(path.join(pub, 'parler.html'), 'utf8');
  const fichiers = ['parler.html', ...[...html.matchAll(/<(?:script|link)[^>]+(?:src|href)="\/([^"]+\.(?:js|css))"/g)].map(m => m[1])];
  let brut = 0, gz = 0, apres = 0;
  for (const f of fichiers) {
    const d = fs.readFileSync(path.join(pub, f));
    const z = zlib.gzipSync(d, { level: 6 }).length;
    if (!f.startsWith('vendor/')) { brut += d.length; gz += z; }    // vendor/ : déjà gardé un jour par le navigateur, avant comme après
    if (f.endsWith('.html')) apres += z;                            // la page (no-store) repart toujours, compressée
  }
  console.log(`# Parler, ${fichiers.length} fichiers (hors vendor/) : avant ${Math.round(brut / 1024)} Ko à chaque ouverture ; `
    + `après : ${Math.round(gz / 1024)} Ko la première fois, ${Math.round(apres / 1024)} Ko ensuite (le reste en 304)`);
  assert.ok(gz < brut / 3, 'au moins trois fois moins');
});

test('servirPage elle-même (lue dans server.js) : parler.js en gzip puis 304, parler.html compressée avec son jeton et sa politique', async () => {
  const vm = require('node:vm');
  const debut = SRC.indexOf('function servirPage(');
  const code = SRC.slice(debut, SRC.indexOf("server.listen(PORT, '127.0.0.1'", debut));
  const ctx = { fs, path, EnvoiStatique: E, JETON: 'jeton-test', cspDe: () => 'csp-test',
    MIME: { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html' } };
  vm.createContext(ctx);
  vm.runInContext(`${code}; this.servirPage = servirPage;`, ctx);
  const appel = (fp, p, entetes) => new Promise((ok) => {
    const res = { writeHead(n, h) { this.n = n; this.h = h || {}; }, end(c) { this.corps = c || Buffer.alloc(0); ok(this); } };
    ctx.servirPage(res, fp, p, { headers: entetes });
  });
  const js = path.join(__dirname, 'public', 'parler.js');
  const a = await appel(js, '/parler.js', { 'accept-encoding': 'gzip' });
  assert.equal(a.n, 200); assert.equal(a.h['Content-Encoding'], 'gzip'); assert.equal(a.h['Cache-Control'], 'no-cache');
  assert.equal(zlib.gunzipSync(a.corps).length, fs.statSync(js).size);
  const b = await appel(js, '/parler.js', { 'accept-encoding': 'gzip', 'if-none-match': a.h.ETag });
  assert.equal(b.n, 304); assert.equal(b.corps.length, 0);
  const h = await appel(path.join(__dirname, 'public', 'parler.html'), '/parler', { 'accept-encoding': 'gzip' });
  assert.equal(h.n, 200); assert.equal(h.h['Cache-Control'], 'no-store'); assert.equal(h.h['Content-Security-Policy'], 'csp-test');
  assert.match(zlib.gunzipSync(h.corps).toString(), /<meta name="cockpit-jeton" content="jeton-test">/);
  const absent = await appel(path.join(__dirname, 'public', 'nexiste-pas.js'), '/nexiste-pas.js', {});
  assert.equal(absent.n, 404);
});

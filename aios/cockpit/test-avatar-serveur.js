// (07/11) la photo de son avatar : gardée au cockpit (jarvis/avatar, jamais publiée), servie et changée avec le jeton seulement
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { Readable } = require('node:stream');
const { routeAvatar, typeImage } = require('./avatar-serveur.js');

const JPEG = Buffer.concat([Buffer.from([0xff, 0xd8, 0xff, 0xe0]), Buffer.alloc(200, 7)]);
const PNG = Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.alloc(100, 1)]);

function appel(dossier, methode, p, corps = null, jeton = true) {
  const req = Readable.from(corps ? [corps] : []);
  req.method = methode; req.headers = {};
  return new Promise((fin) => {
    const res = { code: 0, entetes: {}, corps: Buffer.alloc(0),
      writeHead(c, h) { this.code = c; this.entetes = h || {}; }, end(b) { this.corps = b ? Buffer.from(b) : Buffer.alloc(0); fin(this); } };
    const pris = routeAvatar(req, res, p, { dossier, jetonValide: () => jeton });
    if (!pris) fin(null);
  });
}

test('le type de l’image se lit à ses premiers octets, pas à son nom', () => {
  assert.equal(typeImage(JPEG), 'jpg'); assert.equal(typeImage(PNG), 'png');
  assert.equal(typeImage(Buffer.from('RIFF\0\0\0\0WEBPVP8 ')), 'webp');
  assert.equal(typeImage(Buffer.from('<svg onload=alert(1)>')), null);
});

test('sans photo : rien ; papa en dépose une : elle est gardée, servie, et remplace la précédente ; jamais sans le jeton', async () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'avatar-'));
  assert.equal(await appel(d, 'GET', '/api/autre'), null, 'une autre route : pas la sienne');
  let r = await appel(d, 'GET', '/api/avatar');
  assert.deepEqual(JSON.parse(r.corps), { existe: false, maj: 0, cadrage: { zoom: 1, dy: 0 } });
  r = await appel(d, 'POST', '/api/avatar/visage', JPEG, false);
  assert.equal(r.code, 403, 'sans le jeton : refusé');
  r = await appel(d, 'POST', '/api/avatar/visage', Buffer.from('pas une image'));
  assert.equal(r.code, 400);
  r = await appel(d, 'POST', '/api/avatar/visage', JPEG);
  assert.equal(r.code, 200);
  r = await appel(d, 'GET', '/api/avatar');
  const meta = JSON.parse(r.corps);
  assert.ok(meta.existe && meta.maj > 0);
  r = await appel(d, 'GET', '/api/avatar/visage');
  assert.equal(r.code, 200); assert.equal(r.entetes['Content-Type'], 'image/jpeg'); assert.ok(r.corps.equals(JPEG));
  r = await appel(d, 'POST', '/api/avatar/visage', PNG);
  r = await appel(d, 'GET', '/api/avatar/visage');
  assert.equal(r.entetes['Content-Type'], 'image/png');
  assert.deepEqual(fs.readdirSync(d).filter(n => n.startsWith('visage')), ['visage.png'], 'une seule photo');
  assert.equal((fs.statSync(path.join(d, 'visage.png')).mode & 0o777), 0o600, 'lisible par le Mac seulement');
  r = await appel(d, 'GET', '/api/avatar/visage', null, false);
  assert.equal(r.code, 403);
  r = await appel(d, 'POST', '/api/avatar/visage', Buffer.alloc(11 << 20, 0xff));
  assert.equal(r.code, 400, 'trop lourde');
});

test('branché au cockpit, et sa photo n’est jamais dans ce qui est publié', () => {
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(srv, /const \{ routeAvatar \} = require\('\.\/avatar-serveur\.js'\);/);
  assert.match(srv, /if \(p\.startsWith\('\/api\/avatar'\) && routeAvatar\(req, res, p, \{ dossier: path\.join\(JARVIS, 'avatar'\), jetonValide \}\)\) return;/);
});

// (07/11, Ahmed : « pour le visage de l'avatar, je dois pouvoir supprimer ou éditer ») le cadrage (taille, hauteur du visage) et la suppression
test('son cadrage se règle (borné), se lit avec la photo ; supprimer efface la photo et son cadrage ; jamais sans le jeton', async () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'avatar-'));
  await appel(d, 'POST', '/api/avatar/visage', JPEG);
  let r = await appel(d, 'POST', '/api/avatar/cadrage', Buffer.from(JSON.stringify({ zoom: 1.3, dy: -0.1 })));
  assert.equal(r.code, 200);
  assert.deepEqual(JSON.parse(r.corps).cadrage, { zoom: 1.3, dy: -0.1 });
  r = await appel(d, 'GET', '/api/avatar');
  assert.deepEqual(JSON.parse(r.corps).cadrage, { zoom: 1.3, dy: -0.1 });
  r = await appel(d, 'POST', '/api/avatar/cadrage', Buffer.from(JSON.stringify({ zoom: 9, dy: -4 })));
  assert.deepEqual(JSON.parse(r.corps).cadrage, { zoom: 1.8, dy: -0.35 }, 'borné');
  r = await appel(d, 'POST', '/api/avatar/cadrage', Buffer.from('pas du json'));
  assert.equal(r.code, 400);
  r = await appel(d, 'DELETE', '/api/avatar/visage', null, false);
  assert.equal(r.code, 403, 'sans le jeton : rien n’est effacé');
  r = await appel(d, 'DELETE', '/api/avatar/visage');
  assert.equal(r.code, 200);
  assert.deepEqual(fs.readdirSync(d), [], 'la photo et son cadrage, effacés');
  r = await appel(d, 'GET', '/api/avatar');
  assert.deepEqual(JSON.parse(r.corps), { existe: false, maj: 0, cadrage: { zoom: 1, dy: 0 } });
  r = await appel(d, 'POST', '/api/avatar/visage', JPEG);
  r = await appel(d, 'GET', '/api/avatar');
  assert.deepEqual(JSON.parse(r.corps).cadrage, { zoom: 1, dy: 0 }, 'une nouvelle photo repart du cadrage de base');
});

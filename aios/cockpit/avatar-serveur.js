/* (07/11, Ahmed : « un avatar avec mon visage pour lui ») la photo de son avatar : gardée au cockpit, dans jarvis/avatar (hors de tout ce
   qui est publié), lisible par le Mac seulement (600) ; servie et changée avec le jeton seulement. Une seule photo : la nouvelle remplace
   l'ancienne. Son type se lit à ses premiers octets (JPEG, PNG, WebP), jamais à son nom ; 10 Mo au plus.
   GET /api/avatar → { existe, maj, cadrage } ; GET /api/avatar/visage → l'image ; POST /api/avatar/visage (le corps : l'image) → { ok, maj }
   (07/11, Ahmed : « pour le visage de l'avatar, je dois pouvoir supprimer ou éditer ») POST /api/avatar/cadrage { zoom, dy } : la taille du
   visage (0,6 à 1,8) et sa hauteur dans le cadre (−0,35 à 0,35) ; DELETE /api/avatar/visage : la photo et son cadrage, effacés */
'use strict';
const fs = require('node:fs');
const path = require('node:path');

const MAX = 10 << 20;
const TYPES = { jpg: 'image/jpeg', png: 'image/png', webp: 'image/webp' };

function typeImage(b) {
  if (!b || b.length < 12) return null;
  if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return 'jpg';
  if (b.slice(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) return 'png';
  if (b.slice(0, 4).toString('latin1') === 'RIFF' && b.slice(8, 12).toString('latin1') === 'WEBP') return 'webp';
  return null;
}
function photo(dossier) {
  for (const ext of Object.keys(TYPES)) {
    const f = path.join(dossier, `visage.${ext}`);
    try { const st = fs.statSync(f); return { f, ext, maj: Math.round(st.mtimeMs) }; } catch (_) {}
  }
  return null;
}
const CADRAGE_BASE = { zoom: 1, dy: 0 };
const borne = (x, a, b, d) => (Number.isFinite(Number(x)) ? Math.max(a, Math.min(b, Number(x))) : d);
function cadrage(dossier) {
  try { const o = JSON.parse(fs.readFileSync(path.join(dossier, 'cadrage.json'), 'utf8')); return { zoom: borne(o.zoom, 0.6, 1.8, 1), dy: borne(o.dy, -0.35, 0.35, 0) }; }
  catch (_) { return { ...CADRAGE_BASE }; }
}
function lire(req, max) {
  return new Promise((fin) => {
    const morceaux = []; let n = 0;
    req.on('data', (c) => { n += c.length; if (n <= max) morceaux.push(c); });
    req.on('end', () => fin(n > max ? null : Buffer.concat(morceaux)));
    req.on('error', () => fin(null));
  });
}
// rend vrai si la route est la sienne (la réponse part, de façon asynchrone pour un dépôt)
function routeAvatar(req, res, p, { dossier, jetonValide }) {
  if (!/^\/api\/avatar(?:\/visage|\/cadrage)?$/.test(p)) return false;
  const json = (code, o) => { res.writeHead(code, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(o)); };
  if (!jetonValide(req)) { json(403, { erreur: 'jeton' }); return true; }
  if (p === '/api/avatar' && req.method === 'GET') { const x = photo(dossier); json(200, { existe: !!x, maj: x ? x.maj : 0, cadrage: cadrage(dossier) }); return true; }
  if (p === '/api/avatar/cadrage' && req.method === 'POST') {
    lire(req, 1024).then((b) => {
      let o = null; try { o = JSON.parse(String(b || '')); } catch (_) {}
      if (!o || typeof o !== 'object') return json(400, { erreur: 'cadrage illisible' });
      const c = { zoom: borne(o.zoom, 0.6, 1.8, 1), dy: borne(o.dy, -0.35, 0.35, 0) };
      try {
        fs.mkdirSync(dossier, { recursive: true, mode: 0o700 });
        fs.writeFileSync(path.join(dossier, 'cadrage.json'), JSON.stringify(c), { mode: 0o600 });
        json(200, { ok: true, cadrage: c });
      } catch (e) { json(500, { erreur: `enregistrement impossible (${e.code || e.message})` }); }
    });
    return true;
  }
  if (p === '/api/avatar/visage' && req.method === 'DELETE') {
    for (const n of [...Object.keys(TYPES).map(x => `visage.${x}`), 'cadrage.json']) try { fs.unlinkSync(path.join(dossier, n)); } catch (_) {}
    json(200, { ok: true });
    return true;
  }
  if (p === '/api/avatar/visage' && req.method === 'GET') {
    const x = photo(dossier);
    if (!x) { json(404, { erreur: 'pas de photo' }); return true; }
    fs.readFile(x.f, (e, b) => {
      if (e) return json(500, { erreur: 'illisible' });
      res.writeHead(200, { 'Content-Type': TYPES[x.ext], 'Cache-Control': 'no-store' }); res.end(b);
    });
    return true;
  }
  if (p === '/api/avatar/visage' && req.method === 'POST') {
    lire(req, MAX).then((b) => {
      if (!b) return json(400, { erreur: 'photo trop lourde (10 Mo au plus)' });
      const ext = typeImage(b);
      if (!ext) return json(400, { erreur: 'ce n’est pas une photo (JPEG, PNG ou WebP)' });
      try {
        fs.mkdirSync(dossier, { recursive: true, mode: 0o700 });
        const f = path.join(dossier, `visage.${ext}`), tmp = `${f}.${process.pid}.tmp`;
        fs.writeFileSync(tmp, b, { mode: 0o600 });
        fs.renameSync(tmp, f);
        for (const autre of Object.keys(TYPES)) if (autre !== ext) try { fs.unlinkSync(path.join(dossier, `visage.${autre}`)); } catch (_) {}
        try { fs.unlinkSync(path.join(dossier, 'cadrage.json')); } catch (_) {}      // une nouvelle photo : le cadrage de base
        json(200, { ok: true, maj: Math.round(fs.statSync(f).mtimeMs) });
      } catch (e) { json(500, { erreur: `enregistrement impossible (${e.code || e.message})` }); }
    });
    return true;
  }
  json(405, { erreur: 'méthode' });
  return true;
}
module.exports = { routeAvatar, typeImage };

/* (09/11, Ahmed : « alléger et accélérer tout le process ») les fichiers des pages partaient en entier à chaque ouverture :
   « no-cache » sans validateur oblige le navigateur à tout reprendre (parler.js seul : 600 Ko, plus 200 Ko d'autres scripts,
   à chaque ouverture de Parler dans l'appli). Maintenant :
   - une empreinte (ETag) : le navigateur redemande, et reçoit « 304, rien n'a changé », sans corps ; le code reste toujours
     revérifié (no-cache garde son sens : un vieux parler.js ne peut pas rester) ;
   - compressés (gzip) quand le navigateur l'accepte, pour le texte seulement (scripts, styles, pages, JSON, SVG) ;
   - le résultat est gardé en mémoire tant que le fichier ne change pas (sa date et sa taille) : ni relu pour un 304, ni recompressé.
   node --test test-envoi-statique.js */
'use strict';
const zlib = require('zlib');
const crypto = require('crypto');

const TEXTE = /^(text\/|application\/(json|javascript|manifest\+json|x-ndjson|xml)|image\/svg\+xml)/;
const MIN_GZIP = 1024;                     // en dessous, l'en-tête gzip coûte plus qu'il ne gagne
const cache = new Map();                   // chemin → { cle, etag, gz }

function entree(fp, cle, data) {
  let x = cache.get(fp);
  if (!x || x.cle !== cle) {
    x = { cle, etag: `"${crypto.createHash('sha1').update(data).digest('base64url').slice(0, 27)}"`, gz: null };
    cache.set(fp, x);
  }
  return x;
}

const accepteGzip = (req) => /\bgzip\b/i.test(String((req && req.headers && req.headers['accept-encoding']) || ''));

function correspond(req, etag) {
  const v = String((req && req.headers && req.headers['if-none-match']) || '');
  return !!v && (v.trim() === '*' || v.split(',').some(t => t.trim().replace(/^W\//, '') === etag));
}

/** Le fichier déjà connu et inchangé que le navigateur a encore : true si un 304 est parti (rien à lire sur le disque). */
function dejaAJour(req, res, fp, cle, entetes = {}) {
  const x = cache.get(fp);
  if (!x || x.cle !== cle || !correspond(req, x.etag)) return false;
  res.writeHead(304, { ...entetes, ETag: x.etag });
  res.end();
  return true;
}

/** Envoie data (Buffer ou texte). cle : ce qui identifie cette version (date:taille) ; null = ni empreinte ni mémoire.
 *  validateur false : pas d'ETag (une page « no-store », qui porte le jeton du démarrage), mais la compression est gardée. */
function envoyer(req, res, { fp, data, cle = null, type = 'text/plain', entetes = {}, validateur = true }) {
  const corps = Buffer.isBuffer(data) ? data : Buffer.from(String(data));
  const h = { 'Content-Type': type, ...entetes };
  const x = cle != null ? entree(fp, cle, corps) : null;
  if (x && validateur) {
    h.ETag = x.etag;
    if (correspond(req, x.etag)) { delete h['Content-Type']; res.writeHead(304, h); return res.end(); }
  }
  const compressible = TEXTE.test(type) && corps.length >= MIN_GZIP;
  if (compressible) h.Vary = 'Accept-Encoding';
  if (compressible && accepteGzip(req)) {
    let gz = x && x.gz;
    if (!gz) { gz = zlib.gzipSync(corps, { level: 6 }); if (x) x.gz = gz; }
    h['Content-Encoding'] = 'gzip';
    h['Content-Length'] = gz.length;
    res.writeHead(200, h);
    return res.end(gz);
  }
  h['Content-Length'] = corps.length;
  res.writeHead(200, h);
  return res.end(corps);
}

module.exports = { envoyer, dejaAJour, _cache: cache };

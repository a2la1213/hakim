/* (03/11, Ahmed : « réflexion minimale… et Gemma aussi si tu peux ») la remplaçante d'Opus, c'est le même claude qui parle à
   Ollama. Mesuré le 03/11 (une fausse Ollama qui note les demandes) : pour un modèle qu'il ne connaît pas, claude envoie
   thinking « adaptive » et son effort (« high ») ; sans réflexion (MAX_THINKING_TOKENS=0, --thinking disabled), il n'envoie
   plus rien. Et Ollama (anthropic/anthropic.go) ne coupe la réflexion que sur « disabled » : sinon il reprend l'effort, ou le
   défaut de Gemma 4 (penser). Ce petit pont, sur le Mac seul (127.0.0.1), réécrit chaque demande de message : thinking
   « disabled », sans effort ; le reste passe tel quel, la réponse revient en flux. */
const http = require('http');

function reecrire(corps) {
  let o;
  try { o = JSON.parse(corps); } catch (_) { return corps; }
  if (!o || typeof o !== 'object' || Array.isArray(o)) return corps;
  o.thinking = { type: 'disabled' };
  delete o.output_config;
  return JSON.stringify(o);
}

// le pont vers Ollama (cible : « http://127.0.0.1:11434 ») : rend { url, serveur } quand il écoute
function demarrer(cible, { port = 0 } = {}) {
  const u = new URL(cible);
  return new Promise((ok, ko) => {
    const serveur = http.createServer((req, res) => {
      const morceaux = [];
      req.on('data', d => morceaux.push(d));
      req.on('end', () => {
        let corps = Buffer.concat(morceaux);
        if (req.method === 'POST' && /^\/v1\/messages(\?|$)/.test(req.url)) corps = Buffer.from(reecrire(corps.toString('utf8')));
        const entetes = { ...req.headers, host: u.host, 'content-length': String(corps.length) };
        delete entetes['transfer-encoding'];
        const amont = http.request({ hostname: u.hostname, port: u.port || 80, path: req.url, method: req.method, headers: entetes }, (r) => {
          res.writeHead(r.statusCode || 502, r.headers);
          r.pipe(res);
        });
        amont.on('error', (e) => {
          if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ type: 'error', error: { type: 'api_error', message: `Ollama injoignable (${e.code || e.message})` } }));
        });
        res.on('close', () => { if (!res.writableFinished) amont.destroy(); });     // claude a raccroché : Ollama s'arrête aussi
        amont.end(corps);
      });
    });
    serveur.on('error', ko);
    serveur.listen(port, '127.0.0.1', () => { serveur.unref(); ok({ url: `http://127.0.0.1:${serveur.address().port}`, serveur }); });
  });
}

module.exports = { reecrire, demarrer };

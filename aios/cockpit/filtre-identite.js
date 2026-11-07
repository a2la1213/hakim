/* (07/11, Ahmed : « chaque fois qu'il pense Hakim, son identité ou la mienne, ça doit être en mode filtration : rien de tout ça ne sort vers
   Anthropic, on reçoit seulement d'eux » ; « oui » au filtre local) LE FILTRE D'IDENTITÉ : un petit relais sur le Mac (127.0.0.1) entre ses
   cerveaux (claude) et Anthropic. Chaque demande qui part est réécrite : les noms (Hakim, Ahmed…), les adresses mail, les numéros, les IBAN,
   les coordonnées GPS deviennent des alias ; chaque réponse qui revient (en flux, morceau par morceau) est remise en clair avant que claude
   ne la lise. Anthropic ne voit que les alias ; Hakim, sa mémoire et papa ne voient que les vrais noms.

   - Le dictionnaire est local (jarvis/filtre-identite.json, jamais publié) : des paires [vrai, alias], plus des motifs (mail, téléphone,
     IBAN, GPS) dont chaque valeur reçoit un alias stable (le même à chaque demande : son cache chez Anthropic reste valable).
   - Les blocs de réflexion (thinking, signés par Anthropic) ne sont jamais touchés, ni à l'aller ni au retour : leur signature resterait juste.
   - En flux : un alias coupé entre deux morceaux est retenu (la fin d'un morceau qui pourrait être le début d'un alias) jusqu'au suivant.
   - Ce qu'il ne protège pas : le SENS de ce qu'il pense (seuls les identifiants changent), les images, et ce qui passe par d'autres
     services (Azure : ta voix et la sienne). */
'use strict';
const fs = require('fs');
const http = require('http');
const https = require('https');

const MOTIFS = [
  ['mail', /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, (n) => `contact${n}@exemple.org`],
  ['iban', /\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b/g, (n) => `XX00 0000 0000 0000 ${String(n).padStart(4, '0')}`],
  // international (+41 79 123 45 67, +33 6 12 34 56 78) ; national suisse ou français (079 123 45 67, 06 12 34 56 78)
  ['telephone', /\+\d{2,3}(?:[\s.-]?\d{1,3}){3,5}\b|\b0\d{2}[\s.]?\d{3}[\s.]?\d{2}[\s.]?\d{2}\b|\b0\d(?:[\s.]?\d{2}){4}\b/g, (n) => `+00 00 000 00 ${String(n).padStart(2, '0')}`],
  ['gps', /\b-?\d{1,2}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}\b/g, (n) => `0.${String(n).padStart(4, '0')}, 0.${String(n).padStart(4, '0')}`],
];

const echapper = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// le dictionnaire : { paires: [[vrai, alias]…], valeurs: { 'mail|a@b.c': 'contact1@exemple.org', … } } ; rend l'objet de travail
function dictionnaire(d = {}) {
  const paires = (Array.isArray(d.paires) ? d.paires : []).filter(p => Array.isArray(p) && p[0] && p[1] && p[0] !== p[1])
    .map(([v, a]) => [String(v), String(a)]);
  const valeurs = d.valeurs && typeof d.valeurs === 'object' ? { ...d.valeurs } : {};
  return { paires, valeurs, change: false };
}

// les vrais noms, des plus longs aux plus courts (« Hakimou » avant « Hakim »), en mot entier, sans tenir compte de la casse
function versAlias(D) {
  const l = [...D.paires].sort((a, b) => b[0].length - a[0].length);
  return l.map(([v, a]) => [new RegExp(`(?<![\\p{L}\\p{N}_])${echapper(v)}(?![\\p{L}\\p{N}_])`, 'giu'), a, v]);
}

// garde la casse du mot remplacé : « HAKIM » → « ZORVAN », « hakim » → « zorvan »
function casse(modele, mot) {
  if (modele === modele.toUpperCase() && modele !== modele.toLowerCase()) return mot.toUpperCase();
  if (modele === modele.toLowerCase() && modele !== modele.toUpperCase()) return mot.toLowerCase();
  return mot;
}

function masquerTexte(t, D) {
  if (typeof t !== 'string' || !t) return t;
  let s = t;
  for (const [nom, re, alias] of MOTIFS) {
    s = s.replace(re, (m) => {
      const cle = `${nom}|${m}`;
      if (!D.valeurs[cle]) { D.valeurs[cle] = alias(Object.keys(D.valeurs).filter(k => k.startsWith(`${nom}|`)).length + 1); D.change = true; }
      return D.valeurs[cle];
    });
  }
  for (const [re, a] of versAlias(D)) s = s.replace(re, (m) => casse(m, a));
  return s;
}

function retours(D) {
  const l = D.paires.map(([v, a]) => [a, v]);
  for (const [cle, a] of Object.entries(D.valeurs)) l.push([a, cle.slice(cle.indexOf('|') + 1)]);
  return l.sort((x, y) => y[0].length - x[0].length);
}

function demasquerTexte(t, D) {
  if (typeof t !== 'string' || !t) return t;
  let s = t;
  for (const [a, v] of retours(D)) {
    const mot = /^[\p{L}\p{N}_]/u.test(a) && /[\p{L}\p{N}_]$/u.test(a);
    const re = new RegExp(mot ? `(?<![\\p{L}\\p{N}_])${echapper(a)}(?![\\p{L}\\p{N}_])` : echapper(a), mot ? 'giu' : 'g');
    s = s.replace(re, (m) => casse(m, v));
  }
  return s;
}

// ce qui part : chaque texte de la demande (système, messages, résultats d'outils, entrées d'outils, descriptions d'outils), jamais la réflexion
function masquerDemande(o, D) {
  const bloc = (b) => {
    if (typeof b === 'string') return masquerTexte(b, D);
    if (!b || typeof b !== 'object') return b;
    if (b.type === 'thinking' || b.type === 'redacted_thinking') return b;
    const x = { ...b };
    if (typeof x.text === 'string') x.text = masquerTexte(x.text, D);
    if (x.type === 'tool_result') x.content = Array.isArray(x.content) ? x.content.map(bloc) : masquerTexte(x.content, D);
    if (x.type === 'tool_use' && x.input) x.input = profond(x.input, (s) => masquerTexte(s, D));
    return x;
  };
  const r = { ...o };
  if (typeof r.system === 'string') r.system = masquerTexte(r.system, D);
  else if (Array.isArray(r.system)) r.system = r.system.map(bloc);
  if (Array.isArray(r.messages)) r.messages = r.messages.map(m => ({ ...m, content: Array.isArray(m.content) ? m.content.map(bloc) : masquerTexte(m.content, D) }));
  if (Array.isArray(r.tools)) r.tools = r.tools.map(t => ({ ...t, ...(typeof t.description === 'string' ? { description: masquerTexte(t.description, D) } : {}) }));
  return r;
}

function profond(v, f) {
  if (typeof v === 'string') return f(v);
  if (Array.isArray(v)) return v.map(x => profond(x, f));
  if (v && typeof v === 'object') { const o = {}; for (const [k, x] of Object.entries(v)) o[k] = profond(x, f); return o; }
  return v;
}

// une réponse entière (sans flux) : remise en clair, sauf la réflexion
function demasquerReponse(o, D) {
  const r = { ...o };
  if (Array.isArray(r.content)) r.content = r.content.map(b => {
    if (!b || b.type === 'thinking' || b.type === 'redacted_thinking') return b;
    const x = { ...b };
    if (typeof x.text === 'string') x.text = demasquerTexte(x.text, D);
    if (x.type === 'tool_use' && x.input) x.input = profond(x.input, (s) => demasquerTexte(s, D));
    return x;
  });
  return r;
}

// la plus longue fin de `t` qui pourrait être le début d'un alias (à retenir jusqu'au morceau suivant)
function finAmbigue(t, D) {
  let n = 0;
  for (const [a] of retours(D)) {
    for (let k = Math.min(a.length - 1, t.length); k > n; k--) if (t.slice(-k).toLowerCase() === a.slice(0, k).toLowerCase()) { n = k; break; }
  }
  return n;
}

// LE FLUX : un traducteur d'événements SSE ; chaque bloc de texte (ou d'entrée d'outil) retient sa fin ambiguë jusqu'au morceau suivant
function traducteurFlux(D) {
  const enAttente = new Map();                         // index du bloc → { champ, texte }
  const sortie = (o) => `event: ${o.type}\ndata: ${JSON.stringify(o)}\n\n`;
  const morceau = (index, champ, texte) => {
    const a = enAttente.get(index) || { champ, texte: '' };
    const tout = a.texte + texte;
    const n = finAmbigue(tout, D);
    const pret = demasquerTexte(tout.slice(0, tout.length - n), D);
    a.texte = tout.slice(tout.length - n); a.champ = champ;
    enAttente.set(index, a);
    return pret;
  };
  const vider = (index) => {
    const a = enAttente.get(index);
    enAttente.delete(index);
    if (!a || !a.texte) return '';
    const delta = a.champ === 'partial_json' ? { type: 'input_json_delta', partial_json: demasquerTexte(a.texte, D) } : { type: 'text_delta', text: demasquerTexte(a.texte, D) };
    return sortie({ type: 'content_block_delta', index, delta });
  };
  return function evenement(brut) {
    const l = brut.split('\n').find(x => x.startsWith('data:'));
    if (!l) return `${brut}\n\n`;
    let o; try { o = JSON.parse(l.slice(5).trim()); } catch (_) { return `${brut}\n\n`; }
    if (o.type === 'content_block_delta' && o.delta && o.delta.type === 'text_delta') {
      const t = morceau(o.index, 'text', o.delta.text || '');
      return t ? sortie({ ...o, delta: { ...o.delta, text: t } }) : '';
    }
    if (o.type === 'content_block_delta' && o.delta && o.delta.type === 'input_json_delta') {
      const t = morceau(o.index, 'partial_json', o.delta.partial_json || '');
      return t ? sortie({ ...o, delta: { ...o.delta, partial_json: t } }) : '';
    }
    if (o.type === 'content_block_stop') return vider(o.index) + sortie(o);
    if (o.type === 'content_block_start' && o.content_block && o.content_block.type === 'tool_use' && o.content_block.input)
      return sortie({ ...o, content_block: { ...o.content_block, input: profond(o.content_block.input, (s) => demasquerTexte(s, D)) } });
    return sortie(o);
  };
}

/* les alias : tirés au hasard à la création, gardés seulement sur le Mac (le code est public : une table d'alias écrite dans le code se lirait
   de l'autre côté). Un groupe de noms qui vont ensemble (Hakim, Hakimou, حكيم) garde un même alias de base ; l'arabe reçoit des lettres arabes au hasard. */
const SYLLABES = ['ra', 'lo', 'mi', 'ven', 'dor', 'sa', 'tel', 'ka', 'ri', 'no', 'bel', 'zan', 'mar', 'lu', 'fen', 'ti', 'gor', 'ya', 'sel', 'vo'];
// l'arabe : des lettres tirées au hasard (jamais un vrai mot : « كريم » se lit dans le Coran, il ne doit jamais redevenir un nom au retour)
const LETTRES_ARABES = ['ظ', 'ق', 'ج', 'ز', 'ش', 'ث', 'خ', 'غ', 'ض', 'ص'];
function hasard(n) { return require('crypto').randomInt(n); }
function nomLatin() {
  let s = '';
  for (let k = 0, n = 2 + hasard(2); k < n; k++) s += SYLLABES[hasard(SYLLABES.length)];
  return s[0].toUpperCase() + s.slice(1);
}
const arabe = (t) => /[\u0600-\u06FF]/.test(t);
function creerDictionnaire(groupes) {
  const paires = [], arabesPris = new Set();
  for (const g of groupes) {
    const base = nomLatin();
    let ar = null;
    for (const v of g) {
      if (arabe(v)) {
        if (!ar) { do { ar = Array.from({ length: 5 }, () => LETTRES_ARABES[hasard(LETTRES_ARABES.length)]).join(''); } while (arabesPris.has(ar)); arabesPris.add(ar); }
        paires.push([v, ar]);
      } else if (/\d/.test(v)) paires.push([v, base.toLowerCase() + String(100 + hasard(900))]);
      else paires.push([v, v.toLowerCase().startsWith(g[0].toLowerCase()) && v.length > g[0].length ? base + v.slice(g[0].length) : base]);
    }
  }
  return { paires, valeurs: {} };
}

function lireDictionnaire(fichier) {
  try { return dictionnaire(JSON.parse(fs.readFileSync(fichier, 'utf8'))); } catch (_) { return dictionnaire({}); }
}
function garderDictionnaire(fichier, D) {
  if (!D.change) return;
  D.change = false;
  try { fs.writeFileSync(`${fichier}.tmp`, JSON.stringify({ paires: D.paires, valeurs: D.valeurs }, null, 1), { mode: 0o600 }); fs.renameSync(`${fichier}.tmp`, fichier); } catch (_) {}
}

// le relais : rend { url, serveur, stats } quand il écoute ; cible : https://api.anthropic.com
function demarrer(fichier, { cible = 'https://api.anthropic.com', port = 0, journal = null } = {}) {
  const u = new URL(cible);
  const stats = { demandes: 0, remplaces: 0, erreurs: 0 };
  return new Promise((ok, ko) => {
    const serveur = http.createServer((req, res) => {
      const morceaux = [];
      req.on('data', d => morceaux.push(d));
      req.on('end', () => {
        const D = lireDictionnaire(fichier);
        let corps = Buffer.concat(morceaux);
        const messages = req.method === 'POST' && /^\/v1\/messages(\/count_tokens)?(\?|$)/.test(req.url);   // le comptage de jetons porte aussi tout le texte
        let flux = false;
        if (messages) {
          try {
            const o = JSON.parse(corps.toString('utf8'));
            flux = !!o.stream;
            const avant = corps.length;
            corps = Buffer.from(JSON.stringify(masquerDemande(o, D)));
            stats.demandes++; stats.remplaces += Math.abs(corps.length - avant) > 0 ? 1 : 0;
            garderDictionnaire(fichier, D);
          } catch (e) { stats.erreurs++; if (journal) journal('filtre_erreur', { quoi: 'demande', erreur: String(e.message || e).slice(0, 80) }); }
        }
        const entetes = { ...req.headers, host: u.host, 'content-length': String(corps.length) };
        delete entetes['transfer-encoding']; delete entetes['accept-encoding'];   // le retour en clair (non compressé) pour le relire
        const mod = u.protocol === 'https:' ? https : http;
        const amont = mod.request({ hostname: u.hostname, port: u.port || (u.protocol === 'https:' ? 443 : 80), path: req.url, method: req.method, headers: entetes }, (r) => {
          const h = { ...r.headers };
          if (!messages) { res.writeHead(r.statusCode, h); r.pipe(res); return; }
          delete h['content-length'];
          res.writeHead(r.statusCode, h);
          if (flux && /event-stream/.test(String(r.headers['content-type'] || ''))) {
            const traduire = traducteurFlux(D);
            let tampon = '';
            r.setEncoding('utf8');
            r.on('data', (d) => {
              tampon += d;
              let i;
              while ((i = tampon.indexOf('\n\n')) >= 0) { const ev = tampon.slice(0, i); tampon = tampon.slice(i + 2); const x = traduire(ev); if (x) res.write(x); }
            });
            r.on('end', () => { if (tampon.trim()) res.write(traduire(tampon)); res.end(); });
            return;
          }
          const b = [];
          r.on('data', d => b.push(d));
          r.on('end', () => {
            let t = Buffer.concat(b).toString('utf8');
            try { t = JSON.stringify(demasquerReponse(JSON.parse(t), D)); } catch (_) {}
            res.end(t);
          });
        });
        amont.on('error', (e) => { stats.erreurs++; if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ type: 'error', error: { type: 'api_error', message: `relais : ${e.message}` } })); });
        amont.end(corps);
      });
    });
    serveur.on('error', ko);
    serveur.listen(port, '127.0.0.1', () => ok({ url: `http://127.0.0.1:${serveur.address().port}`, serveur, stats }));
  });
}

module.exports = { MOTIFS, creerDictionnaire, dictionnaire, masquerTexte, demasquerTexte, masquerDemande, demasquerReponse, finAmbigue, traducteurFlux, lireDictionnaire, demarrer };

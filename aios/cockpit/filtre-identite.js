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
// (09/11) compilés une fois par dictionnaire, plus à chaque texte (une demande du cerveau en a des centaines)
function versAlias(D) {
  if (D._versAlias) return D._versAlias;
  const l = [...D.paires].sort((a, b) => b[0].length - a[0].length);
  return (D._versAlias = l.map(([v, a]) => [new RegExp(`(?<![\\p{L}\\p{N}_])${echapper(v)}(?![\\p{L}\\p{N}_])`, 'giu'), a, v]));
}

// garde la casse du mot remplacé : « HAKIM » → « ZORVAN », « hakim » → « zorvan »
function casse(modele, mot) {
  if (modele === modele.toUpperCase() && modele !== modele.toLowerCase()) return mot.toUpperCase();
  if (modele === modele.toLowerCase() && modele !== modele.toUpperCase()) return mot.toLowerCase();
  return mot;
}

/* (09/11, Ahmed : « une requête préconstruite ») LA DEMANDE PRÉCONSTRUITE : chaque demande du cerveau renvoie toute sa conversation (130 k jetons
   et plus) ; seuls ses derniers messages sont neufs. Chaque texte déjà masqué est gardé (D._memo, ~4 M caractères au plus, les plus anciens
   oubliés d'abord) : au départ, seul le neuf est masqué, le reste est déjà prêt. Sûr : un alias ne change jamais (une valeur vue garde le sien,
   un nouveau nom recharge le dictionnaire, donc vide la mémoire). */
const MEMO_MIN = 160, MEMO_MAX = 4e6;
function masquerTexte(t, D) {
  if (typeof t !== 'string' || !t) return t;
  if (t.length < MEMO_MIN || D.memo === false) return masquerNeuf(t, D);
  const m = D._memo || (D._memo = { textes: new Map(), taille: 0, trouves: 0, neufs: 0 });
  const deja = m.textes.get(t);
  if (deja !== undefined) { m.textes.delete(t); m.textes.set(t, deja); m.trouves++; return deja; }
  const s = masquerNeuf(t, D);
  m.neufs++;
  m.textes.set(t, s); m.taille += t.length + s.length;
  for (const [k, v] of m.textes) { if (m.taille <= MEMO_MAX) break; m.textes.delete(k); m.taille -= k.length + v.length; }
  return s;
}
function masquerNeuf(t, D) {
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

// (09/11) les retours (alias → vrai) et leurs motifs : refaits seulement quand une valeur s'ajoute (plus à chaque morceau du flux)
function retours(D) {
  const n = Object.keys(D.valeurs).length;
  if (D._retours && D._retours.n === n) return D._retours.l;
  const l = D.paires.map(([v, a]) => [a, v]);
  for (const [cle, a] of Object.entries(D.valeurs)) l.push([a, cle.slice(cle.indexOf('|') + 1)]);
  l.sort((x, y) => y[0].length - x[0].length);
  const re = l.map(([a, v]) => {
    const mot = /^[\p{L}\p{N}_]/u.test(a) && /[\p{L}\p{N}_]$/u.test(a);
    return [new RegExp(mot ? `(?<![\\p{L}\\p{N}_])${echapper(a)}(?![\\p{L}\\p{N}_])` : echapper(a), mot ? 'giu' : 'g'), v, a.toLowerCase()];
  });
  D._retours = { n, l, re };
  return l;
}

function demasquerTexte(t, D) {
  if (typeof t !== 'string' || !t) return t;
  retours(D);
  let s = t;
  for (const [re, v] of D._retours.re) s = s.replace(re, (m) => casse(m, v));
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
  retours(D);
  let n = 0;
  for (const [, , a] of D._retours.re) {
    for (let k = Math.min(a.length - 1, t.length); k > n; k--) if (t.slice(-k).toLowerCase() === a.slice(0, k)) { n = k; break; }
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
  const paires = [], arabesPris = new Set(), latinsPris = new Set();
  for (const g of groupes) {
    // (10/11) deux personnes ne reçoivent jamais le même nom d'emprunt (« Vobel » tiré pour Hakim et pour Ahmed : le test l'a vu)
    let base; do { base = nomLatin(); } while (latinsPris.has(base.toLowerCase())); latinsPris.add(base.toLowerCase());
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

// (09/11) le dictionnaire gardé en mémoire tant que son fichier ne change pas (papa qui ajoute un nom le recharge, avec des mémoires neuves)
const dictionnairesLus = new Map();                     // fichier → { cle (date + taille), D }
function signature(fichier) { try { const st = fs.statSync(fichier); return `${st.mtimeMs}|${st.size}`; } catch (_) { return null; } }
function lireDictionnaire(fichier) {
  const cle = signature(fichier), deja = dictionnairesLus.get(fichier);
  if (cle && deja && deja.cle === cle) return deja.D;
  let D;
  try { D = dictionnaire(JSON.parse(fs.readFileSync(fichier, 'utf8'))); } catch (_) { return dictionnaire({}); }
  if (cle) dictionnairesLus.set(fichier, { cle, D });
  return D;
}
function garderDictionnaire(fichier, D) {
  if (!D.change) return;
  D.change = false;
  try {
    fs.writeFileSync(`${fichier}.tmp`, JSON.stringify({ paires: D.paires, valeurs: D.valeurs }, null, 1), { mode: 0o600 }); fs.renameSync(`${fichier}.tmp`, fichier);
    const deja = dictionnairesLus.get(fichier);
    if (deja && deja.D === D) deja.cle = signature(fichier);   // notre propre écriture : le même dictionnaire, ses mémoires restent
  } catch (_) {}
}

/* (09/11, Ahmed : « les requêtes qui sortent de notre filtre : une seule et même requête, pas plusieurs avant le départ » ; Nour : d'abord
   MESURER) le registre du relais : une ligne par requête qui part chez Anthropic (jarvis/relais-requetes.jsonl, en ajout seul, écrit après
   coup sans jamais retenir le flux). Rien du contenu : le chemin, le modèle, les tailles, les temps (premier octet d'Anthropic, premier mot,
   premier morceau rendu à claude, fin), le statut, l'usage du cache, la connexion réutilisée ou neuve, le n° du tour de papa en cours
   (contexte()) et qui l'a lancée (l'en-tête x-hakim-etiquette, retiré avant le départ : il ne sort jamais du Mac). */
const ETIQUETTE = 'x-hakim-etiquette';
// ce que la demande dit d'elle-même, sans son texte : modèle, flux, nombre de messages et d'outils, taille du système, points de cache
function resumeDemande(o) {
  if (!o || typeof o !== 'object') return {};
  const sys = typeof o.system === 'string' ? o.system.length : Array.isArray(o.system) ? o.system.reduce((n, b) => n + String((b && b.text) || '').length, 0) : 0;
  let cache = 0;
  const compter = (b) => { if (b && typeof b === 'object' && b.cache_control) cache++; };
  if (Array.isArray(o.system)) o.system.forEach(compter);
  if (Array.isArray(o.tools)) o.tools.forEach(compter);
  if (Array.isArray(o.messages)) for (const m of o.messages) if (Array.isArray(m && m.content)) m.content.forEach(compter);
  return { modele: typeof o.model === 'string' ? o.model.slice(0, 60) : null, flux: !!o.stream, max_tokens: Number(o.max_tokens) || null,
    messages: Array.isArray(o.messages) ? o.messages.length : 0, outils: Array.isArray(o.tools) ? o.tools.length : 0, systeme_car: sys, points_cache: cache,
    reflexion: !!(o.thinking && o.thinking.type && o.thinking.type !== 'disabled') };
}
// l'usage rendu par Anthropic (message_start, message_delta, ou la réponse entière) : entrée, cache lu, cache écrit, sortie
function noterUsage(l, u) {
  if (!u || typeof u !== 'object') return;
  if (Number.isFinite(u.input_tokens)) l.entree = u.input_tokens;
  if (Number.isFinite(u.cache_read_input_tokens)) l.cache_lu = u.cache_read_input_tokens;
  if (Number.isFinite(u.cache_creation_input_tokens)) l.cache_ecrit = u.cache_creation_input_tokens;
  if (Number.isFinite(u.output_tokens)) l.sortie = u.output_tokens;
}
function ecrireRegistre(registre, l) {
  if (!registre) return;
  if (typeof registre === 'function') { try { registre(l); } catch (_) {} return; }
  fs.appendFile(registre, JSON.stringify(l) + '\n', { mode: 0o600 }, () => {});
}

// le relais : rend { url, serveur, stats } quand il écoute ; cible : https://api.anthropic.com
// registre : un fichier (ou une fonction) qui reçoit une ligne par requête ; contexte() : ce que le cockpit sait du moment (n° de tour…)
/* (09/11, « une requête préconstruite, qui part d'un coup ») la connexion à Anthropic reste ouverte entre deux tours (60 s au lieu des 5 s de
   Node : papa parle toutes les 20 à 40 s) ; une connexion qu'Anthropic aurait fermée entre-temps est refaite une fois, sans que claude le voie
   (le corps est encore là, rien n'est parti). Et ses motifs (noms, mails, téléphones…) sont compilés dès le démarrage, pas à la première demande. */
const GARDE_CONNEXION_MS = 60000;
function demarrer(fichier, { cible = 'https://api.anthropic.com', port = 0, journal = null, registre = null, contexte = null, garde = GARDE_CONNEXION_MS } = {}) {
  const u = new URL(cible);
  const stats = { demandes: 0, remplaces: 0, erreurs: 0, requetes: 0, reessais: 0 };
  const mod = u.protocol === 'https:' ? https : http;
  const agent = new mod.Agent({ keepAlive: true, keepAliveMsecs: 15000, timeout: garde, maxFreeSockets: 16 });
  try { const D = lireDictionnaire(fichier); demasquerTexte(masquerNeuf('Échauffement : a@b.ch, +41 79 000 00 00, 46.2000, 6.1000.', D), D); finAmbigue('x', D); } catch (_) {}
  return new Promise((ok, ko) => {
    const serveur = http.createServer((req, res) => {
      const t0 = Date.now();
      const l = { ts: t0, chemin: String(req.url || '').split('?')[0].slice(0, 80), methode: req.method,
        etiquette: req.headers[ETIQUETTE] ? String(req.headers[ETIQUETTE]).slice(0, 60) : null };
      try { if (contexte) Object.assign(l, contexte() || {}); } catch (_) {}
      stats.requetes++;
      let fini = false;
      const finir = (statut) => {
        if (fini) return;
        fini = true;
        l.statut = statut != null ? statut : l.statut;
        l.ms = Date.now() - t0;
        ecrireRegistre(registre, l);
      };
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
            Object.assign(l, resumeDemande(o));
            flux = !!o.stream;
            const avant = corps.length;
            corps = Buffer.from(JSON.stringify(masquerDemande(o, D)));
            stats.demandes++; stats.remplaces += Math.abs(corps.length - avant) > 0 ? 1 : 0;
            garderDictionnaire(fichier, D);
          } catch (e) { stats.erreurs++; if (journal) journal('filtre_erreur', { quoi: 'demande', erreur: String(e.message || e).slice(0, 80) }); }
        }
        l.octets_aller = corps.length;
        l.filtre_ms = Date.now() - t0;                                      // le temps du relais à l'aller (lecture + masque)
        const entetes = { ...req.headers, host: u.host, 'content-length': String(corps.length) };
        delete entetes['transfer-encoding']; delete entetes['accept-encoding'];   // le retour en clair (non compressé) pour le relire
        delete entetes[ETIQUETTE];                                          // l'étiquette reste sur le Mac
        const partir = (essai) => {
        const amont = mod.request({ hostname: u.hostname, port: u.port || (u.protocol === 'https:' ? 443 : 80), path: req.url, method: req.method, headers: entetes, agent }, (r) => {
          l.statut = r.statusCode;
          l.entetes_ms = Date.now() - t0;                                   // les en-têtes d'Anthropic reçus
          let retour = 0;
          r.on('data', (d) => { if (!retour) l.amont_ms = Date.now() - t0; retour += d.length; l.octets_retour = retour; });
          r.on('error', () => finir(l.statut));
          res.on('close', () => finir(l.statut));
          const h = { ...r.headers };
          if (!messages) { res.writeHead(r.statusCode, h); r.pipe(res); r.on('end', () => finir(r.statusCode)); return; }
          delete h['content-length'];
          res.writeHead(r.statusCode, h);
          if (flux && /event-stream/.test(String(r.headers['content-type'] || ''))) {
            const traduire = traducteurFlux(D);
            let tampon = '', traduction = 0;
            r.setEncoding('utf8');
            r.on('data', (d) => {
              tampon += d;
              let i;
              while ((i = tampon.indexOf('\n\n')) >= 0) {
                const ev = tampon.slice(0, i); tampon = tampon.slice(i + 2);
                const a = Date.now();
                if (!l.premier_mot_ms && /"(text_delta|input_json_delta)"/.test(ev)) l.premier_mot_ms = a - t0;
                if (/"(message_start|message_delta|error)"/.test(ev)) { try { const o = JSON.parse(ev.split('\n').find(x => x.startsWith('data:')).slice(5)); noterUsage(l, (o.message && o.message.usage) || o.usage); if (o.type === 'error' && o.error) l.erreur = String(o.error.type || o.error.message || '').slice(0, 80); } catch (_) {} }
                const x = traduire(ev);
                traduction += Date.now() - a;
                if (x) { if (!l.rendu_ms && /"(text_delta|input_json_delta)"/.test(x)) l.rendu_ms = Date.now() - t0; res.write(x); }
              }
            });
            r.on('end', () => { if (tampon.trim()) res.write(traduire(tampon)); res.end(); l.traduction_ms = traduction; finir(r.statusCode); });
            return;
          }
          const b = [];
          r.on('data', d => b.push(d));
          r.on('end', () => {
            let t = Buffer.concat(b).toString('utf8');
            try { const o = JSON.parse(t); noterUsage(l, o.usage); if (o.error) l.erreur = String(o.error.type || o.error.message || '').slice(0, 80); t = JSON.stringify(demasquerReponse(o, D)); } catch (_) {}
            res.end(t);
            finir(r.statusCode);
          });
        });
        amont.on('socket', (s) => { l.connexion = amont.reusedSocket ? 'reutilisee' : 'neuve'; void s; });
        amont.on('error', (e) => {
          // une connexion gardée qu'Anthropic avait fermée : refaite une fois, sur une neuve (rien n'avait été reçu)
          if (!essai && amont.reusedSocket && !res.headersSent && /^(ECONNRESET|EPIPE|ECONNABORTED)$/.test(String(e.code))) { stats.reessais++; l.reessai = true; return partir(1); }
          stats.erreurs++; l.erreur = `relais : ${String(e.message || e).slice(0, 80)}`; if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ type: 'error', error: { type: 'api_error', message: `relais : ${e.message}` } })); finir(502);
        });
        amont.end(corps);
        };
        partir(0);
      });
    });
    serveur.on('error', ko);
    serveur.on('close', () => agent.destroy());
    serveur.listen(port, '127.0.0.1', () => ok({ url: `http://127.0.0.1:${serveur.address().port}`, serveur, stats, agent }));
  });
}

module.exports = { ETIQUETTE, resumeDemande, masquerNeuf, MOTIFS, creerDictionnaire, dictionnaire, masquerTexte, demasquerTexte, masquerDemande, demasquerReponse, finAmbigue, traducteurFlux, lireDictionnaire, demarrer };

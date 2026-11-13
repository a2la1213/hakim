/* (13/11, Ahmed : « il faut qu'il puisse uploader ses photos et ses musiques et en faire des vidéos TikTok, Insta, etc. ») l'atelier
   VIDÉO, côté cockpit, branché par atelier.js sous /api/atelier/media/… et /api/atelier/video/… (server.js garde le jeton) :
   - la médiathèque : ~/AIOS/jarvis/mediatheque/<collection>/<fichier>, lue sur le disque ; un DÉPÔT arrive en flux (200 Mo au plus) dans
     .depot/, puis anamnese/jarvis/atelier_video.py « importer » le vérifie (ses octets, puis le lire vraiment), convertit un HEIC en JPEG,
     fait l'aperçu et le range ; effacer un fichier (et son aperçu, son analyse), créer une collection, effacer une collection vide ;
   - les vidéos : ~/AIOS/jarvis/videos (<nom>-9x16.mp4, -couverture.jpg, .jpg, .json) ; créer, prévisualiser (aperçu en petit), refaire :
     atelier_video.py « lancer » écrit une TÂCHE DE FOND ordinaire (le cockpit la suit comme les autres) ; arrêter ; effacer ;
   - les fichiers servis derrière le jeton, avec Range, par un nom simple vérifié, jamais hors de leur dossier ;
   - le réglage « atelier_video » (modules.json, ou JARVIS_ATELIER_VIDEO) : éteint, tout répond 409.
   Rien ne sort de la machine. Aucune dépendance. node --test test-atelier-video.js */
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { execFile } = require('child_process');

const TYPES = { '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4',
  '.wav': 'audio/wav', '.mp4': 'video/mp4' };
const PHOTOS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif']);
const MUSIQUES = new Set(['.mp3', '.m4a', '.wav']);
const POLICES = new Set(['.ttf', '.otf']);
const DEPOT_MAX = 200 << 20;
const NOM_VIDEO = /^[0-9]{8}-[0-9]{6}-[0-9a-f]{3}-[a-z0-9-]{1,60}(?:-(?:9x16|4x5|1x1)\.mp4|-couverture\.jpg|\.jpg)$/;
const NOM_FICHE = /^[0-9]{8}-[0-9]{6}-[0-9a-f]{3}-[a-z0-9-]{1,60}$/;
const TACHE = /^T-\d{8}-\d{6}-[0-9a-f]{4}$/;

// « Hiver 2026 » : lettres, chiffres, espace, - _ ' ; 50 caractères ; ni « . » ni « _ » en tête (comme atelier_video.nom_collection)
function nomCollection(s) {
  const t = String(s || '').normalize('NFC').replace(/[^\p{L}\p{N} \-_']/gu, ' ').replace(/\s+/g, ' ').trim().replace(/^[\s\-_']+|[\s\-_']+$/g, '').slice(0, 50).trim();
  return t || null;
}
// un nom de fichier envoyé : sans chemin, sans caractère de contrôle ni d'inversion, 120 caractères
function nomDepot(s) {
  let n = ''; try { n = decodeURIComponent(String(s || '')); } catch (_) { n = ''; }
  n = path.basename(n.normalize('NFC').replace(/\\/g, '/')).replace(/[^\p{L}\p{N} ._()+-]/gu, '_').replace(/^[.\s]+/, '').slice(-120);
  return n || null;
}

function creer(o = {}) {
  const JARVIS = o.jarvis || path.join(os.homedir(), 'AIOS', 'jarvis');
  const ANAMNESE = o.anamnese || path.join(os.homedir(), 'Desktop', 'anamnese');
  const MED = o.mediatheque || path.join(JARVIS, 'mediatheque');
  const VIDEOS = o.videos || path.join(JARVIS, 'videos');
  const TACHES = o.taches || path.join(JARVIS, 'cwd', 'taches');
  const MODULES = o.modules || path.join(JARVIS, 'modules.json');
  const PY = path.join(ANAMNESE, 'jarvis', 'atelier_video.py');
  const lireCorps = o.lireCorps;
  const lireJson = (f, d = null) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } };
  const dans = (racine, p) => { try { const r = fs.realpathSync(racine), q = fs.realpathSync(p); return q === r || q.startsWith(r + path.sep); } catch (_) { return false; } };

  function python() {
    if (o.python) return o.python;
    if (process.env.JARVIS_PYTHON_VIDEO) return process.env.JARVIS_PYTHON_VIDEO;
    for (const d of ['.venv-video', '.venv-image']) { const p = path.join(ANAMNESE, 'jarvis', d, 'bin', 'python'); if (fs.existsSync(p)) return p; }
    return path.join(ANAMNESE, '.venv', 'bin', 'python');
  }
  // le réglage « atelier_video » : la variable d'environnement, sinon modules.json (à plat ou sous « modules »), sinon allumé
  function allume() {
    const v = process.env.JARVIS_ATELIER_VIDEO;
    if (v !== undefined && String(v).trim()) return !['0', 'non', 'false', 'off', 'eteint', 'éteint'].includes(String(v).trim().toLowerCase());
    const d = lireJson(MODULES, {}) || {};
    if (d.modules && typeof d.modules === 'object' && 'atelier_video' in d.modules) return !!d.modules.atelier_video;
    if ('atelier_video' in d) return !!d.atelier_video;
    return true;
  }
  // un appel au python de la vidéo : une ligne JSON en entrée, une ligne JSON en sortie
  function appeler(cmd, q, delai = 300000) {
    if (o.appeler) return Promise.resolve(o.appeler(cmd, q));            // (tests) jamais la vraie file
    return new Promise((ok) => {
      const p = execFile(python(), ['-B', PY, cmd], { timeout: delai, cwd: path.dirname(PY), maxBuffer: 4 << 20,
        env: { ...process.env, JARVIS_DIR: JARVIS, PATH: `/usr/local/bin:/opt/homebrew/bin:/usr/bin:${process.env.PATH || '/bin'}` } },
      (e, so) => { try { ok(JSON.parse(String(so).trim().split('\n').pop())); } catch (_) { ok({ ok: false, erreur: e ? 'atelier_video.py a échoué' : 'réponse illisible' }); } });
      p.stdin.on('error', () => {});
      p.stdin.end(JSON.stringify(q || {}));
    });
  }

  /* ---------- la médiathèque ---------- */
  function collectionExistante(c) {
    const n = nomCollection(c);
    if (!n || n !== String(c || '').normalize('NFC')) return null;
    const d = path.join(MED, n);
    try { if (!fs.lstatSync(d).isDirectory() || !dans(MED, d)) return null; } catch (_) { return null; }
    return { nom: n, d };
  }
  function entree(c, f) {
    const ext = path.extname(f).toLowerCase();
    let st; try { st = fs.statSync(path.join(MED, c, f)); } catch (_) { return null; }
    const e = { f, taille: st.size, date: Math.round(st.mtimeMs / 1000) };
    if (PHOTOS.has(ext)) { e.type = 'photo'; e.apercu = fs.existsSync(path.join(MED, '.apercus', c, f + '.jpg')); }
    else {
      e.type = 'musique';
      const a = lireJson(path.join(MED, '.analyses', c, f + '.json'));
      if (a && a.taille === st.size) { e.duree_s = a.duree; e.bpm = a.bpm; }
    }
    return e;
  }
  function lister() {
    let dossiers = [];
    try { dossiers = fs.readdirSync(MED, { withFileTypes: true }).filter(x => x.isDirectory() && !/^[._]/.test(x.name)).map(x => x.name); } catch (_) {}
    dossiers.sort((a, b) => a.localeCompare(b, 'fr', { sensitivity: 'base' }));
    return dossiers.map((c) => {
      let noms = []; try { noms = fs.readdirSync(path.join(MED, c)).filter(n => !n.startsWith('.')); } catch (_) {}
      noms.sort((a, b) => a.localeCompare(b, 'fr', { numeric: true, sensitivity: 'base' }));
      const es = noms.filter(n => PHOTOS.has(path.extname(n).toLowerCase()) || MUSIQUES.has(path.extname(n).toLowerCase())).map(n => entree(c, n)).filter(Boolean);
      return { nom: c, photos: es.filter(e => e.type === 'photo'), musiques: es.filter(e => e.type === 'musique') };
    });
  }
  function polices() { try { return fs.readdirSync(path.join(MED, '_polices')).filter(n => POLICES.has(path.extname(n).toLowerCase())); } catch (_) { return []; } }

  /* ---------- les vidéos ---------- */
  function progres(tid) {
    if (!TACHE.test(String(tid || ''))) return null;
    let t = '';
    try {
      const fd = fs.openSync(path.join(TACHES, `${tid}.log`), 'r');
      try { const st = fs.fstatSync(fd), n = Math.min(8192, st.size), b = Buffer.alloc(n); fs.readSync(fd, b, 0, n, st.size - n); t = b.toString('utf8'); }
      finally { fs.closeSync(fd); }
    } catch (_) { return null; }
    const l = t.split('\n').filter(x => x.startsWith('PROGRESSION ')).pop();
    const m = l && l.match(/^PROGRESSION (\d+(?:[.,]\d+)?)%\s*(.*)$/);
    return m ? { f: Math.min(1, Number(m[1].replace(',', '.')) / 100), texte: m[2].replace(/[^\p{L}\p{N} .,:()'’×x%/-]/gu, ' ').trim().slice(0, 80) } : null;
  }
  const base = (f) => (f ? path.basename(String(f)) : null);
  function resume(x) {
    const r = x.recette || {}, m = x.mesures || {}, son = m.son || {};
    const vids = (x.fichiers || []).map(base).filter(f => f && /\.mp4$/.test(f)).map(f => ({ f, format: (f.match(/-(9x16|4x5|1x1)\.mp4$/) || [, ''])[1].replace('x', ':') }));
    return { nom: x.nom, titre: x.titre, type: x.type, date: x.fin, par: x.par || 'hakim', videos: vids, couverture: base(x.couverture), vignette: base(x.vignette),
      duree_s: r.duree_s, bpm: m.bpm, passage: m.passage || null, raison: m.raison || '', lufs: son.lufs ?? null, calage: m.calage_ms || null,
      calcul_s: m.calcul_s, coupes: m.coupes, transition: m.transition,
      recette: { photos: r.photos || [], musique: r.musique || null, formats: r.formats || [], duree_s: r.duree_s, rythme: r.rythme, transition: r.transition,
        textes: r.textes || {}, debut_s: r.debut_s ?? null } };
  }
  function videos() {
    let noms = []; try { noms = fs.readdirSync(VIDEOS).filter(n => n.endsWith('.json') && !n.startsWith('.')); } catch (_) {}
    const toutes = noms.map(n => lireJson(path.join(VIDEOS, n))).filter(x => x && typeof x === 'object' && x.nom);
    const pretes = toutes.filter(x => x.etat === 'prête').sort((a, b) => (b.fin || 0) - (a.fin || 0));
    const maintenant = Date.now() / 1000;
    const enCours = toutes.filter(x => x.etat === 'en cours' || (x.etat === 'ratée' && maintenant - (x.fin || 0) < 3600)).map((x) => {
      const t = TACHE.test(String(x.tache || '')) ? lireJson(path.join(TACHES, `${x.tache}.json`), {}) : {};
      const vivant = x.etat === 'en cours' && t && t.etat === 'en cours';
      return { nom: x.nom, titre: x.titre, type: x.type, tache: x.tache, debut: x.debut, etat: vivant ? 'en cours' : x.etat === 'ratée' ? 'ratée' : (t && t.etat) || 'perdue',
        erreur: x.erreur ? String(x.erreur).slice(0, 200) : null, ...(vivant ? { progres: progres(x.tache) } : {}) };
    }).filter(x => x.etat === 'en cours' || x.etat === 'ratée').sort((a, b) => (b.debut || 0) - (a.debut || 0)).slice(0, 8);
    return { videos: pretes.filter(x => x.type !== 'apercu').slice(0, 60).map(resume), apercus: pretes.filter(x => x.type === 'apercu').slice(0, 3).map(resume), enCours };
  }
  function etat() {
    return { allume: allume(), visuel_installe: fs.existsSync(path.join(ANAMNESE, 'jarvis', '.venv-image', 'bin', 'python')),
      collections: lister(), polices: polices(), ...videos(), telephone: 'Documents › Hakim › Videos (sur ton téléphone)' };
  }

  /* ---------- HTTP ---------- */
  const repondre = (res, code, x) => { if (!res.headersSent) { res.writeHead(code, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(x)); } };
  const corpsJson = async (req) => { try { return JSON.parse(String(await lireCorps(req, 65536) || '{}')) || {}; } catch (_) { return {}; } };
  const texte = (v, n) => String(v ?? '').replace(/[\x00-\x1f\x7f]/g, ' ').trim().slice(0, n);

  function servir(req, res, f, telecharger) {
    const taille = fs.statSync(f).size, type = TYPES[path.extname(f).toLowerCase()] || 'application/octet-stream';
    const entetes = { 'Content-Type': type, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
      ...(telecharger ? { 'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(path.basename(f))}` } : {}) };
    const m = /^bytes=(\d*)-(\d*)$/.exec(String(req.headers.range || ''));
    if (m && (m[1] || m[2])) {
      const a = m[1] ? +m[1] : Math.max(0, taille - +m[2]), b = m[1] && m[2] ? Math.min(+m[2], taille - 1) : taille - 1;
      if (a >= taille || a > b) { res.writeHead(416, { 'Content-Range': `bytes */${taille}` }); return res.end(); }
      res.writeHead(206, { ...entetes, 'Content-Range': `bytes ${a}-${b}/${taille}`, 'Content-Length': b - a + 1 });
      return fs.createReadStream(f, { start: a, end: b }).pipe(res);
    }
    res.writeHead(200, { ...entetes, 'Content-Length': taille });
    fs.createReadStream(f).pipe(res);
  }
  // un fichier de la médiathèque (ou son aperçu) : une collection qui existe, un nom simple de photo ou de musique, dans son dossier
  function cheminMedia(c, f, apercu) {
    const col = collectionExistante(c);
    const n = String(f || '');
    if (!col || !n || n !== path.basename(n) || n.startsWith('.') || /[\\/]/.test(n)) return null;
    const ext = path.extname(n).toLowerCase();
    if (!PHOTOS.has(ext) && !MUSIQUES.has(ext)) return null;
    const p = apercu ? path.join(MED, '.apercus', col.nom, n + '.jpg') : path.join(col.d, n);
    try { if (!fs.lstatSync(p).isFile() || !dans(MED, p)) return null; } catch (_) { return null; }
    return p;
  }
  function cheminVideo(f) {
    const n = String(f || '');
    if (!NOM_VIDEO.test(n)) return null;
    const p = path.join(VIDEOS, n);
    try { return fs.lstatSync(p).isFile() ? p : null; } catch (_) { return null; }
  }

  // un dépôt : le corps de la requête, en flux, dans .depot/ (200 Mo au plus), puis le python le vérifie et le range
  async function deposer(req, res, q) {
    const col = nomCollection(q.get('collection'));
    const nom = nomDepot(req.headers['x-nom']);
    if (!col) { req.resume(); return repondre(res, 400, { erreur: 'une collection (par exemple « Hiver 2026 »)' }); }
    if (!nom) { req.resume(); return repondre(res, 400, { erreur: 'le nom du fichier' }); }
    const ext = path.extname(nom).toLowerCase();
    if (!PHOTOS.has(ext) && !MUSIQUES.has(ext) && !POLICES.has(ext)) {
      req.resume(); return repondre(res, 415, { erreur: 'type refusé : des photos (jpg, png, heic, webp) ou des musiques (mp3, m4a, wav)' });
    }
    if (Number(req.headers['content-length']) > DEPOT_MAX) { req.resume(); return repondre(res, 413, { erreur: 'fichier trop lourd (200 Mo au plus)' }); }
    const depot = path.join(MED, '.depot');
    try { fs.mkdirSync(depot, { recursive: true }); } catch (_) {}
    const tmp = path.join(depot, `${Date.now()}-${crypto.randomBytes(3).toString('hex')}${ext}`);
    let n = 0, trop = false, echec = null;
    const sortie = fs.createWriteStream(tmp, { flags: 'wx', mode: 0o600 });
    req.on('data', (c) => { n += c.length; if (n > DEPOT_MAX && !trop) { trop = true; req.unpipe(sortie); sortie.destroy(); req.resume(); } });
    req.pipe(sortie);
    await new Promise((fin) => { sortie.on('close', fin); sortie.on('error', (e) => { echec = e; fin(); }); req.on('error', (e) => { echec = e; fin(); }); });
    if (trop || echec || !n) { fs.rm(tmp, { force: true }, () => {}); return repondre(res, trop ? 413 : 400, { erreur: trop ? 'fichier trop lourd (200 Mo au plus)' : n ? 'envoi interrompu' : 'fichier vide' }); }
    const r = await appeler('importer', { chemin: tmp, collection: col, nom, deplacer: true }, 300000);
    try { fs.rmSync(tmp, { force: true }); } catch (_) {}
    return repondre(res, r && r.ok ? 200 : 409, r || { ok: false, erreur: 'import impossible' });
  }

  function effacerMedia(x) {
    const col = collectionExistante(x.collection);
    if (!col) return { code: 404, r: { erreur: 'collection inconnue' } };
    if (!x.fichier) {
      const reste = fs.readdirSync(col.d).filter(n => !n.startsWith('.'));
      if (reste.length) return { code: 409, r: { erreur: 'la collection n’est pas vide : efface d’abord ses fichiers' } };
      fs.rmSync(col.d, { recursive: true, force: true });
      for (const d of ['.apercus', '.analyses']) fs.rmSync(path.join(MED, d, col.nom), { recursive: true, force: true });
      return { code: 200, r: { ok: true, efface: col.nom } };
    }
    const p = cheminMedia(col.nom, x.fichier, false);
    if (!p) return { code: 404, r: { erreur: 'fichier inconnu dans cette collection' } };
    fs.rmSync(p, { force: true });
    fs.rmSync(path.join(MED, '.apercus', col.nom, path.basename(p) + '.jpg'), { force: true });
    fs.rmSync(path.join(MED, '.analyses', col.nom, path.basename(p) + '.json'), { force: true });
    return { code: 200, r: { ok: true, efface: `${col.nom}/${path.basename(p)}` } };
  }
  function effacerVideo(nom) {
    if (!NOM_FICHE.test(String(nom || ''))) return { code: 404, r: { erreur: 'vidéo inconnue' } };
    const fiche = lireJson(path.join(VIDEOS, `${nom}.json`));
    if (!fiche) return { code: 404, r: { erreur: 'vidéo inconnue' } };
    if (fiche.etat === 'en cours') return { code: 409, r: { erreur: 'elle se calcule encore : arrête-la d’abord' } };
    let noms = []; try { noms = fs.readdirSync(VIDEOS); } catch (_) {}
    for (const n of noms) if (n === `${nom}.json` || NOM_VIDEO.test(n) && n.startsWith(nom + '-') || n === `${nom}.jpg`) fs.rmSync(path.join(VIDEOS, n), { force: true });
    return { code: 200, r: { ok: true } };   // les copies du téléphone et de l'atelier restent (elles sont à lui)
  }
  // une demande de vidéo, nettoyée : photos « Collection/fichier », musique, format, durée, rythme, textes ; ou « refaire »
  function demandeVideo(x) {
    const nb = (v) => (Number.isFinite(Number(v)) ? Number(v) : null);
    const ref = (v) => texte(v, 160).replace(/^\/+/, '');
    const q = {
      photos: (Array.isArray(x.photos) ? x.photos : []).slice(0, 30).map(ref).filter(Boolean), collection: texte(x.collection, 60),
      musique: ref(x.musique), format: (Array.isArray(x.format) ? x.format : [x.format]).map(f => texte(f, 20)).filter(Boolean).slice(0, 3).join(' et ') || '9:16',
      duree_s: nb(x.duree_s) || 15, rythme: texte(x.rythme, 12) || 'auto', transition: texte(x.transition, 12) || 'auto',
      marque: texte(x.marque, 40), piece: texte(x.piece, 80), prix: texte(x.prix, 30), appel: texte(x.appel, 50), titre: texte(x.titre, 80),
      legendes: (Array.isArray(x.legendes) ? x.legendes : []).slice(0, 30).map(l => texte(l, 120)),
      debut_s: nb(x.debut_s) !== null && nb(x.debut_s) >= 0 ? nb(x.debut_s) : null, bpm: nb(x.bpm) || 0, apercu: !!x.apercu,
    };
    if (x.refaire) { q.refaire = NOM_FICHE.test(String(x.refaire)) ? String(x.refaire) : ''; }
    return q;
  }

  async function route(req, res, p) {
    const q = new URL(req.url, 'http://x').searchParams;
    if (p === '/api/atelier/media/etat' && req.method === 'GET') return repondre(res, 200, etat());
    if (!allume()) { req.resume(); return repondre(res, 409, { erreur: 'l’atelier vidéo est éteint ici (réglage « atelier_video »)' }); }
    if (p === '/api/atelier/media/fichier' && req.method === 'GET') {
      const f = cheminMedia(q.get('c'), q.get('f'), q.get('apercu') === '1');
      return f ? servir(req, res, f, false) : repondre(res, 404, { erreur: 'fichier introuvable' });
    }
    if (p === '/api/atelier/video/fichier' && req.method === 'GET') {
      const f = cheminVideo(q.get('f'));
      return f ? servir(req, res, f, q.get('telecharger') === '1') : repondre(res, 404, { erreur: 'fichier introuvable' });
    }
    if (req.method !== 'POST') return repondre(res, 405, { erreur: 'méthode refusée' });
    if (p === '/api/atelier/media/deposer') return deposer(req, res, q);
    if (p === '/api/atelier/media/collection') {
      const x = await corpsJson(req), n = nomCollection(x.nom);
      if (!n) return repondre(res, 400, { erreur: 'un nom de collection' });
      fs.mkdirSync(path.join(MED, n), { recursive: true });
      return repondre(res, 200, { ok: true, nom: n });
    }
    if (p === '/api/atelier/media/effacer') {
      const x = await corpsJson(req);
      try { const { code, r } = effacerMedia(x); return repondre(res, code, r); } catch (_) { return repondre(res, 500, { erreur: 'pas effacé' }); }
    }
    if (p === '/api/atelier/video/creer') {
      const x = await corpsJson(req), d = demandeVideo(x);
      if (x.refaire !== undefined && !d.refaire) return repondre(res, 404, { erreur: 'vidéo inconnue' });
      if (!d.refaire && !d.photos.length && !d.collection) return repondre(res, 400, { erreur: 'choisis des photos (ou une collection)' });
      const r = await appeler('lancer', d, 60000);
      return repondre(res, r && r.ok ? 200 : 409, r || { ok: false, erreur: 'pas lancée' });
    }
    if (p === '/api/atelier/video/arreter') {
      const x = await corpsJson(req), id = String(x.tache || '');
      const t = TACHE.test(id) ? lireJson(path.join(TACHES, `${id}.json`)) : null;
      if (!t || !t.video || t.etat !== 'en cours') return repondre(res, 404, { erreur: 'vidéo inconnue ou finie' });
      fs.writeFileSync(path.join(TACHES, `${id}.stop`), '');               // comme arreter_tache : le calcul lit ce fichier et s'arrête
      return repondre(res, 200, { ok: true });
    }
    if (p === '/api/atelier/video/effacer') {
      const x = await corpsJson(req);
      const { code, r } = effacerVideo(x.nom);
      return repondre(res, code, r);
    }
    return repondre(res, 404, { erreur: 'inconnu' });
  }
  return { route, etat, allume, lister, demandeVideo, cheminMedia, cheminVideo };
}

module.exports = { creer, nomCollection, nomDepot, NOM_VIDEO };

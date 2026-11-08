/* (06/11, Ahmed : « une zone visuelle dans le cockpit où Hakim pourrait créer des images et des clips quand il veut, pour nos futurs
   albums et clips » ; accord pour le modèle d'images : « Ouiii, lance. ») l'Atelier visuel, côté cockpit :
   - la galerie : ~/AIOS/jarvis/visuels (<nom>.png|.mp4|.jpg + <nom>.json), lue sur le disque ;
   - les fichiers servis derrière le jeton (avec Range, pour avancer dans un clip), un nom simple du dossier, rien d'autre ;
   - créer une image (Z-Image-Turbo par mflux) ou un clip (ffmpeg) : anamnese/jarvis/atelier_visuel.py écrit une TÂCHE DE FOND
     ordinaire (cwd/taches/T-*.json), comme une chanson : un gros calcul à la fois sur le Mac, sous nice ; la jauge vient des lignes
     PROGRESSION de son journal ; quand elle finit, le cockpit prévient et réveille Hakim comme pour toute tâche.
   Aucune dépendance ; server.js le branche (route). node --test test-atelier-visuel.js */
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFile } = require('child_process');

const TYPES = { '.png': 'image/png', '.jpg': 'image/jpeg', '.mp4': 'video/mp4' };
const NOM_FICHIER = /^[0-9]{8}-[0-9]{6}-[a-z0-9-]{1,60}\.(png|jpg|mp4)$/;

function creer(o = {}) {
  const JARVIS = o.jarvis || path.join(os.homedir(), 'AIOS', 'jarvis');
  const ANAMNESE = o.anamnese || path.join(os.homedir(), 'Desktop', 'anamnese');
  const VISUELS = o.visuels || path.join(JARVIS, 'visuels');
  const CHANSONS = o.chansons || path.join(JARVIS, 'chansons');
  const TACHES = o.taches || path.join(JARVIS, 'cwd', 'taches');
  const PYTHON = o.python || path.join(ANAMNESE, '.venv', 'bin', 'python');
  const PY = path.join(ANAMNESE, 'jarvis', 'atelier_visuel.py');
  const lireCorps = o.lireCorps;
  const lireJson = (f, d = null) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } };
  const fiches = (d) => { try { return fs.readdirSync(d).filter(n => n.endsWith('.json') && !n.startsWith('.')).map(n => lireJson(path.join(d, n))).filter(x => x && typeof x === 'object'); } catch (_) { return []; } };
  const base = (f) => (f ? path.basename(String(f)) : null);

  // la jauge : la dernière ligne PROGRESSION du journal de la tâche (« 42% texte » ou « 3/9 texte »)
  function progres(tid) {
    if (!/^T-[\w-]+$/.test(String(tid || ''))) return null;
    let t = '';
    try {
      const fd = fs.openSync(path.join(TACHES, `${tid}.log`), 'r');
      try { const n = Math.min(8192, fs.fstatSync(fd).size), b = Buffer.alloc(n); fs.readSync(fd, b, 0, n, fs.fstatSync(fd).size - n); t = b.toString('utf8'); }
      finally { fs.closeSync(fd); }
    } catch (_) { return null; }
    const l = t.split('\n').filter(x => x.startsWith('PROGRESSION ')).pop();
    if (!l) return null;
    let m = l.match(/^PROGRESSION (\d+(?:[.,]\d+)?)%\s*(.*)$/);
    if (m) return { f: Math.min(1, Number(m[1].replace(',', '.')) / 100), texte: m[2].replace(/[^\p{L}\p{N} .,:()'’×x%/-]/gu, ' ').trim().slice(0, 80) };
    m = l.match(/^PROGRESSION (\d+)\/(\d+)\s*(.*)$/);
    return m && +m[2] > 0 ? { f: Math.min(1, +m[1] / +m[2]), texte: m[3].replace(/[^\p{L}\p{N} .,:()'’×x%/-]/gu, ' ').trim().slice(0, 80) } : null;
  }
  function etat() {
    const toutes = fiches(VISUELS).filter(x => x.nom && (x.type === 'image' || x.type === 'clip'));
    const pretes = toutes.filter(x => x.etat === 'prête').sort((a, b) => (b.fin || 0) - (a.fin || 0));
    const images = pretes.filter(x => x.type === 'image' && base(x.fichier)).map(x => ({ nom: x.nom, titre: x.titre, f: base(x.fichier), format: x.format,
      description: String(x.description || '').slice(0, 400), date: x.fin, par: x.par || 'hakim', calcul_s: x.calcul_s, largeur: x.largeur, hauteur: x.hauteur }));
    const clips = pretes.filter(x => x.type === 'clip').map(x => ({ nom: x.nom, titre: x.titre, style: x.style, date: x.fin, par: x.par || 'hakim',
      duree_s: x.duree_s, chanson: (x.chanson && x.chanson.titre) || '', calcul_s: x.calcul_s,
      videos: (x.fichiers || []).map(f => ({ f: base(f), vignette: base(String(f).replace(/\.mp4$/, '.jpg')), format: /16x9/.test(f) ? '16:9' : '9:16' }))
        .filter(v => v.f) }));
    const maintenant = Date.now() / 1000;
    const enCours = toutes.filter(x => x.etat === 'en cours' || (x.etat === 'ratée' && maintenant - (x.fin || 0) < 3600))
      .map(x => {
        const t = x.tache ? lireJson(path.join(TACHES, `${x.tache}.json`), {}) : {};
        const vivant = x.etat === 'en cours' && t && t.etat === 'en cours';
        return { nom: x.nom, type: x.type, titre: x.titre, tache: x.tache, etat: vivant ? 'en cours' : x.etat === 'ratée' ? 'ratée' : (t && t.etat) || 'perdue',
          debut: x.debut, erreur: x.erreur ? String(x.erreur).slice(0, 200) : null, ...(vivant ? { progres: progres(x.tache) } : {}) };
      })
      .filter(x => x.etat === 'en cours' || x.etat === 'ratée').sort((a, b) => (b.debut || 0) - (a.debut || 0)).slice(0, 8);
    const chansons = fiches(CHANSONS).filter(c => c.etat === 'prête' && c.mp3 && c.nom)
      .map(c => ({ nom: c.nom, titre: c.titre, duree_s: c.duree_s, date: c.fin, instrumental: !!c.instrumental }))
      .sort((a, b) => (b.date || 0) - (a.date || 0));
    return { images, clips, enCours, chansons, telephone: 'Hakim › Atelier (le dossier « Hakim » de ton téléphone)' };
  }
  // un fichier de la galerie : un nom simple, de la forme qu'atelier_visuel.py donne, dans le dossier même
  function chemin(f) {
    const x = String(f || '');
    if (!NOM_FICHIER.test(x)) return null;
    const c = path.join(VISUELS, x);
    try { return fs.statSync(c).isFile() ? c : null; } catch (_) { return null; }
  }
  function python(q) {
    if (o.appeler) return Promise.resolve(o.appeler(q));                  // (tests) jamais la vraie file
    return new Promise((ok) => {
      const p = execFile(PYTHON, ['-B', PY, 'lancer'], { timeout: 60000, cwd: path.dirname(PY), env: { ...process.env, PATH: `/usr/local/bin:/opt/homebrew/bin:${process.env.PATH || '/usr/bin:/bin'}` } },
        (e, so) => { try { ok(JSON.parse(String(so).trim().split('\n').pop())); } catch (_) { ok({ ok: false, erreur: e ? 'atelier_visuel.py a échoué' : 'réponse illisible' }); } });
      p.stdin.end(JSON.stringify(q || {}));
    });
  }
  const repondre = (res, code, x) => { if (!res.headersSent) { res.writeHead(code, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(x)); } };
  const corpsJson = async (req) => { try { return JSON.parse(String(await lireCorps(req, 16384) || '{}')) || {}; } catch (_) { return {}; } };
  const texte = (v, n) => String(v || '').replace(/[\x00-\x1f]/g, ' ').trim().slice(0, n);

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

  async function route(req, res, p) {
    const q = new URL(req.url, 'http://x').searchParams;
    if (p === '/api/atelier/etat' && req.method === 'GET') return repondre(res, 200, etat());
    if (p === '/api/atelier/fichier' && req.method === 'GET') {
      const f = chemin(q.get('f'));
      if (!f) return repondre(res, 404, { erreur: 'fichier introuvable' });
      return servir(req, res, f, q.get('telecharger') === '1');
    }
    if (req.method !== 'POST') return repondre(res, 405, { erreur: 'méthode refusée' });
    if (p === '/api/atelier/image') {
      const x = await corpsJson(req);
      const r = await python({ type: 'image', description: texte(x.description, 1600), format: texte(x.format, 20) || 'carre', titre: texte(x.titre, 80) });
      return repondre(res, r.ok ? 200 : 409, r);
    }
    if (p === '/api/atelier/clip') {
      const x = await corpsJson(req);
      const images = (Array.isArray(x.images) ? x.images : []).slice(0, 12).map(i => texte(i, 80)).filter(Boolean);
      const n = (v) => (Number.isFinite(Number(v)) && Number(v) > 0 ? Number(v) : 0);
      const r = await python({ type: 'clip', chanson: texte(x.chanson, 120), images, style: texte(x.style, 20) || 'spectre', format: texte(x.format, 20),
        titre: texte(x.titre, 80), duree_s: n(x.duree_s) || null, debut_s: n(x.debut_s) });
      return repondre(res, r.ok ? 200 : 409, r);
    }
    if (p === '/api/atelier/arreter') {
      const x = await corpsJson(req), id = String(x.tache || '');
      const t = /^T-\d{8}-\d{6}-[0-9a-f]{4}$/.test(id) ? lireJson(path.join(TACHES, `${id}.json`)) : null;
      if (!t || !t.visuel || t.etat !== 'en cours') return repondre(res, 404, { erreur: 'création inconnue ou finie' });
      fs.writeFileSync(path.join(TACHES, `${id}.stop`), '');                // comme arreter_tache : le calcul lit ce fichier et s'arrête
      return repondre(res, 200, { ok: true });
    }
    return repondre(res, 404, { erreur: 'inconnu' });
  }
  return { route, etat, chemin, progres };
}

module.exports = { creer, NOM_FICHIER };

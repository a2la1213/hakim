/* (06/11, Ahmed : « que moi aussi je puisse m'enregistrer et me faire mixer et masteriser par Hakim, comme ça on peut faire des
   vrais sons depuis le phone » ; « il faut absolument un truc Studio dans le cockpit » ; « j'aimerais bien lui faire écouter des sons
   aussi, comme lui, sans lui envoyer ») le studio, côté cockpit :
   - ses sons (~/AIOS/jarvis/chansons), les instrus, les prises d'Ahmed et les mixes, lus sur le disque ;
   - les fichiers servis derrière le jeton (avec Range, pour avancer dans un morceau) ;
   - les calculs lourds (Demucs, mix) confiés à anamnese/jarvis/studio.py : une file, un seul travailleur, sous nice ;
   - FAIRE ÉCOUTER à Hakim : le son décodé (16 kHz mono, comme l'appli 1.66) passe EXACTEMENT par le chemin de son oreille
     interne (🎧, EcranService.Flux) : ses trames de 100 ms chaque seconde (/api/voix/son-flux, source telephone : ses trois pistes,
     son analyse musicale), ses blocs de 8 s (/api/voix/transcrire?source=telephone : la séparation Demucs en cascade, la grande
     oreille, entendreDuTelephone), puis « son_ecoute » (/api/corps/evenement), au rythme du morceau. Ni message ni pièce jointe.
   Aucune dépendance ; server.js le branche (route, envoyer : une requête locale qui porte le jeton). node --test test-studio.js */
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn, execFile } = require('child_process');

const EXT_SON = new Set(['.mp3', '.wav', '.m4a', '.ogg', '.webm', '.flac', '.aac', '.opus']);
const TYPES_SON = { '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.m4a': 'audio/mp4', '.ogg': 'audio/ogg', '.webm': 'audio/webm',
  '.flac': 'audio/flac', '.aac': 'audio/aac', '.opus': 'audio/ogg' };
const HZ = 16000;

/* ---------- l'oreille interne, portée de l'appli (EcranService.Flux, 1.66) : mêmes filtres, mêmes trames ---------- */
function hauteur(x) {
  const n = x.length;
  let r0 = 0;
  for (const v of x) r0 += v * v;
  if (r0 <= 1e-6) return 0;
  const lmin = Math.floor(HZ / 1200), lmax = Math.min(n - 2, Math.floor(HZ / 70));
  const rs = new Float64Array(lmax + 2);
  let meilleur = 0;
  for (let l = lmin; l <= lmax; l++) {
    let r = 0;
    for (let i = 0; i + l < n; i++) r += x[i] * x[i + l];
    rs[l] = r / (r0 * (n - l) / n);
    if (rs[l] > meilleur) meilleur = rs[l];
  }
  if (meilleur <= 0.55) return 0;
  for (let l = lmin + 1; l < lmax; l++) if (rs[l] >= 0.9 * meilleur && rs[l] >= rs[l - 1] && rs[l] >= rs[l + 1]) return Math.round(HZ / l);
  return 0;
}
// le PCM 16 bits mono à 16 kHz → une trame toutes les 100 ms : [niveau, graves, médiums, aigus, f0, brillance]
function trames(pcm) {
  const out = [], trame = new Float64Array(1600);
  let bas = 0, moyen = 0, sx = 0, sg = 0, sm = 0, sa = 0, k = 0, passages = 0;
  for (let i = 0; i < pcm.length; i++) {
    const x = pcm[i] / 32768;
    bas += 0.0937 * (x - bas); moyen += 0.5441 * (x - moyen);
    const g = bas, m = moyen - bas, a = x - moyen;
    sx += x * x; sg += g * g; sm += m * m; sa += a * a;
    trame[k] = x;
    if (k > 0 && (x >= 0) !== (trame[k - 1] >= 0)) passages++;
    if (++k === 1600) {
      const r = (v) => Math.round(v * 100000) / 100000;
      out.push([r(Math.sqrt(sx / 1600)), r(Math.sqrt(sg / 1600)), r(Math.sqrt(sm / 1600)), r(Math.sqrt(sa / 1600)), hauteur(trame), passages * HZ / (2 * 1600)]);
      passages = 0; sx = sg = sm = sa = 0; k = 0;
    }
  }
  return out;
}
function wav16(pcm) {                                         // PCM 16 bits mono 16 kHz → WAV (comme EcranService.wav)
  const h = Buffer.alloc(44), n = pcm.length * 2;
  h.write('RIFF', 0); h.writeUInt32LE(36 + n, 4); h.write('WAVE', 8); h.write('fmt ', 12); h.writeUInt32LE(16, 16);
  h.writeUInt16LE(1, 20); h.writeUInt16LE(1, 22); h.writeUInt32LE(HZ, 24); h.writeUInt32LE(HZ * 2, 28); h.writeUInt16LE(2, 32);
  h.writeUInt16LE(16, 34); h.write('data', 36); h.writeUInt32LE(n, 40);
  return Buffer.concat([h, Buffer.from(pcm.buffer, pcm.byteOffset, n)]);
}
const rmsDe = (pcm) => { let e = 0; for (const v of pcm) e += v * v; return Math.sqrt(e / Math.max(1, pcm.length)) / 32768; };

/* Une écoute : le morceau au rythme du temps réel. envoyer(chemin, corps, type) → Promise<{statut, json}>. */
class Ecoute {
  constructor(o) {
    this.o = o; this.pcm = o.pcm; this.titre = o.titre || 'un son'; this.maintenant = o.maintenant || Date.now;
    this.t = trames(this.pcm);
    this.duree = this.pcm.length / HZ;
    this.secondes = 0; this.blocs = 0; this.mots = []; this.actif = false; this.fin = null;
  }
  demarrer() {
    this.debut = this.maintenant(); this.actif = true;
    this.evenement('musique_ecoutee', { titre: this.titre.slice(0, 120), artiste: 'le studio de papa', etat: 'lecture' });
    if (this.o.minuteur !== false) this.minuteur = setInterval(() => this.avancer(), 250);
    return this;
  }
  evenement(type, details) {
    return this.o.envoyer('/api/corps/evenement', JSON.stringify({ type, t: this.maintenant(), details }), 'application/json').catch(() => null);
  }
  // ce qui est dû à cet instant : chaque seconde ses dix trames, chaque bloc de 8 s sa transcription (le dernier, plus court, à la fin)
  avancer() {
    if (!this.actif) return;
    const ecoule = (this.maintenant() - this.debut) / 1000;
    const nSec = Math.ceil(this.t.length / 10);
    while (this.secondes < nSec && ecoule >= this.secondes + 1) {
      const k = this.secondes++;
      const l = this.t.slice(k * 10, k * 10 + 10);
      this.o.envoyer('/api/voix/son-flux', JSON.stringify({ source: 'telephone', t0: this.debut + k * 1000, pas_ms: 100, trames: l, maintenant: this.maintenant() }), 'application/json').catch(() => null);
    }
    const nBlocs = Math.ceil(this.duree / 8);
    while (this.blocs < nBlocs && (ecoule >= (this.blocs + 1) * 8 || (ecoule >= this.duree && this.blocs === nBlocs - 1))) this.bloc(this.blocs++);
    if (ecoule >= this.duree) this.arreter('fini');
  }
  bloc(b) {
    const pcm = this.pcm.subarray(b * 8 * HZ, Math.min(this.pcm.length, (b + 1) * 8 * HZ));
    if (pcm.length < HZ * 1.5 || rmsDe(pcm) <= 0.01) return;
    const t0 = this.debut + b * 8000;
    const q = `langue=&source=telephone&t0=${t0}&ms=${Math.round(pcm.length / 16)}&maintenant=${this.maintenant()}&cle=${t0}`;
    this.o.envoyer(`/api/voix/transcrire?${q}`, wav16(pcm), 'audio/wav').then((r) => {
      const texte = String((r && r.json && r.json.texte) || '').trim();
      if (texte.length < 3) return;
      this.mots.push(texte); this.mots.splice(0, Math.max(0, this.mots.length - 4));
      return this.evenement('son_ecoute', { texte: texte.slice(0, 200), morceau: this.titre.slice(0, 120), debut_ms: t0 });
    }).catch(() => null);
  }
  arreter(raison = 'arrêtée') {
    if (!this.actif) return;
    this.actif = false; this.fin = raison;
    clearInterval(this.minuteur);
    this.evenement('musique_ecoutee', { titre: this.titre.slice(0, 120), artiste: 'le studio de papa', etat: 'pause' });
    if (this.o.surFin) try { this.o.surFin(this, raison); } catch (_) {}
  }
  etat() {
    return { actif: this.actif, titre: this.titre, duree_s: Math.round(this.duree), position_s: this.actif ? Math.min(Math.round(this.duree), Math.round((this.maintenant() - this.debut) / 1000)) : null,
      fin: this.fin, mots: this.mots.slice(-2) };
  }
}

/* ---------- le calage par sortie (10/11, Ahmed : « calculer le décalage de l'écoute et de la voix ») ----------
   Une fiche par sortie (« appli|bluetooth:ICONIC Sound 2 », « web|… ») : ses mesures (boucle : l'écouteur collé au micro, le plus
   juste ; taper : papa tape sur les clics ; main : le curseur), la dernière faite s'applique. Taper garde l'avance d'un humain sur un
   métronome : apprise quand les deux mesures existent sur la même sortie (à 7 jours au plus l'une de l'autre), elle est retirée des
   mesures en tapant. Voir public/studio-calage.js. */
const METHODES_CALAGE = ['boucle', 'taper', 'main'];
function calageDe(fiche, avance) {
  if (!fiche || !fiche.mesures) return null;
  const m = fiche.mesures[fiche.dernier] ? fiche.dernier : METHODES_CALAGE.find(k => fiche.mesures[k]);
  if (!m) return null;
  const x = fiche.mesures[m], corr = m === 'taper' && avance && Number.isFinite(avance.ms) ? avance.ms : 0;
  const v = (k) => (Number.isFinite(x[k]) ? x[k] : null);
  return { ms: Math.round(x.ms - corr), methode: m, ecart_ms: v('ecart_ms'), n: v('n'), total: v('total'), annonce_ms: v('annonce_ms'),
    avance_ms: corr ? Math.round(corr) : null, date: x.date || null, nom: fiche.nom || '', micro: x.micro || '' };
}
// l'avance de papa en tapant : les deux mesures sur une même sortie, proches dans le temps ; plus de 150 ms : pas une avance, une erreur
function avanceDe(fiche, maintenant = Date.now()) {
  const b = fiche && fiche.mesures && fiche.mesures.boucle, t = fiche && fiche.mesures && fiche.mesures.taper;
  if (!b || !t || Math.abs((b.date || 0) - (t.date || 0)) > 7 * 86400e3) return null;
  const ms = t.ms - b.ms;
  return Math.abs(ms) <= 150 ? { ms: Math.round(ms * 10) / 10, date: maintenant } : null;
}

/* ---------- le studio ---------- */
function creer(o = {}) {
  const JARVIS = o.jarvis || path.join(os.homedir(), 'AIOS', 'jarvis');
  const ANAMNESE = o.anamnese || path.join(os.homedir(), 'Desktop', 'anamnese');
  const CHANSONS = o.chansons || path.join(JARVIS, 'chansons');
  const STUDIO = path.join(CHANSONS, 'studio');
  const TACHES = o.taches || path.join(JARVIS, 'cwd', 'taches');
  const FFMPEG = o.ffmpeg || '/usr/local/bin/ffmpeg';
  const FFPROBE = path.join(path.dirname(FFMPEG), 'ffprobe');
  const PYTHON = o.python || path.join(ANAMNESE, '.venv', 'bin', 'python');
  const STUDIO_PY = path.join(ANAMNESE, 'jarvis', 'studio.py');
  const lireCorps = o.lireCorps;
  const s = { ecoute: null, derniere: null };
  const lireJson = (f, d = null) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } };
  const fiches = (d, re = /\.json$/) => { try { return fs.readdirSync(d).filter(n => re.test(n) && !n.startsWith('.')).map(n => lireJson(path.join(d, n))).filter(Boolean); } catch (_) { return []; } };
  const rel = (f) => { const r = path.relative(CHANSONS, String(f || '')); return r && !r.startsWith('..') && !path.isAbsolute(r) ? r : null; };
  // un chemin donné par la page : sous chansons/, une extension de son, aucun dossier caché
  function chemin(r) {
    const x = String(r || '');
    if (!x || x.length > 300 || x.includes('\0') || path.isAbsolute(x)) return null;
    const f = path.resolve(CHANSONS, x);
    if (!f.startsWith(CHANSONS + path.sep) || !EXT_SON.has(path.extname(f).toLowerCase())) return null;
    if (path.relative(CHANSONS, f).split(path.sep).some(p => p.startsWith('.'))) return null;
    try { return fs.statSync(f).isFile() ? f : null; } catch (_) { return null; }
  }
  const dureeDe = (f) => new Promise((ok) => execFile(FFPROBE, ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', f], { timeout: 20000 },
    (e, so) => ok(e ? null : Math.round(Number(String(so).trim()) * 10) / 10 || null)));
  // le progrès d'une chanson d'ACE-Step : la dernière ligne PROGRESSION de son journal
  function progresTache(tid) {
    try {
      const l = fs.readFileSync(path.join(TACHES, `${tid}.log`), 'utf8').split('\n').filter(x => x.startsWith('PROGRESSION ')).pop();
      const m = l && l.match(/^PROGRESSION (\d+)\/(\d+) (.*)$/);
      return m ? { etape: +m[1], etapes: +m[2], texte: m[3] } : null;
    } catch (_) { return null; }
  }
  function etat() {
    const chansons = fiches(CHANSONS).filter(c => c.nom && (c.etat === 'prête' || c.etat === 'en cours'))
      .map(c => ({ nom: c.nom, f: c.mp3 ? rel(c.mp3) : null, titre: c.titre, style: c.style, date: c.fin || c.debut, duree_s: c.duree_s,
        etat: c.etat, instrumental: !!c.instrumental, autotune: !!c.autotune, pour_studio: !!c.pour_studio, bpm: c.bpm || null,
        telephone: !!c.telephone, ...(c.etat === 'en cours' && c.tache ? { progres: progresTache(c.tache) } : {}) }))
      .filter(c => c.etat === 'en cours' || c.f).sort((a, b) => (b.date || 0) - (a.date || 0));
    const instrus = fiches(path.join(STUDIO, 'instrus')).map(x => ({ id: x.id, f: rel(x.mp3), titre: x.titre, duree_s: x.duree_s, origine: x.origine, date: x.fin }))
      .filter(x => x.f).sort((a, b) => (b.date || 0) - (a.date || 0));
    const prises = fiches(path.join(STUDIO, 'prises')).map(x => ({ id: x.id, f: rel(x.fichier), titre: x.titre, duree_s: x.duree_s, ts: x.ts,
      instru_f: x.instru_f, instru_titre: x.instru_titre, latence_ms: x.latence_ms, choisie: !!x.choisie,
      sortie: x.sortie_nom || '', micro: x.micro || '', methode: x.calage_methode || '' })).filter(x => x.f).sort((a, b) => b.ts - a.ts);
    const mixes = fiches(STUDIO).filter(x => x.nom && x.mp3).map(x => ({ nom: x.nom, f: rel(x.mp3), f_wav: rel(x.wav), titre: x.titre, duree_s: x.duree_s,
      date: x.fin, mesure: x.mesure, conseils: (x.avis && x.avis.conseils) || [], reglages: x.reglages, calcul_s: x.calcul_s, telephone: !!x.telephone }))
      .filter(x => x.f).sort((a, b) => (b.date || 0) - (a.date || 0));
    const travaux = fiches(path.join(STUDIO, 'travaux'), /^J-.*\.json$/)
      .filter(x => x.etat === 'en attente' || x.etat === 'en cours' || Date.now() / 1000 - (x.fin || 0) < 3600)
      .map(x => ({ id: x.id, type: x.type, etat: x.etat, etape: x.etape, etapes: x.etapes, texte: x.texte, erreur: x.erreur, debut: x.debut, fin: x.fin,
        titre: (x.params && (x.params.titre || path.basename(String(x.params.source || '')))) || '' }))
      .sort((a, b) => (b.debut || 0) - (a.debut || 0)).slice(0, 8);
    const cal = lireCalages();
    return { chansons, instrus, prises, mixes, travaux, ecoute: s.ecoute ? s.ecoute.etat() : (s.derniere || null), calages: calagesVus(cal), avance: cal.avance || null,
      telephone: 'Hakim › Chansons (le dossier « Hakim » de ton téléphone)' };
  }
  // le cockpit → studio.py (une ligne JSON) : mettre un calcul en file, demander une instru à Hakim
  function python(action, q) {
    if (o.appeler) return Promise.resolve(o.appeler(action, q));          // (tests) jamais la vraie file
    return new Promise((ok) => {
      const p = execFile(o.pythonStudio || PYTHON, ['-B', STUDIO_PY, action], { timeout: 60000, cwd: path.dirname(STUDIO_PY), env: { ...process.env, PATH: `/usr/local/bin:/opt/homebrew/bin:${process.env.PATH || '/usr/bin:/bin'}` } },
        (e, so) => { try { ok(JSON.parse(String(so).trim().split('\n').pop())); } catch (_) { ok({ ok: false, erreur: e ? 'studio.py a échoué' : 'réponse illisible' }); } });
      p.stdin.end(JSON.stringify(q || {}));
    });
  }
  // le son décodé pour l'oreille : 16 kHz mono, 16 bits (10 min au plus)
  function decoder(f) {
    return new Promise((ok, ko) => {
      const p = spawn(FFMPEG, ['-hide_banner', '-nostdin', '-loglevel', 'error', '-t', '600', '-i', f, '-ac', '1', '-ar', String(HZ), '-f', 's16le', '-'], { stdio: ['ignore', 'pipe', 'ignore'] });
      const m = []; p.stdout.on('data', d => m.push(d));
      p.on('error', ko);
      p.on('close', (c) => { const b = Buffer.concat(m); if (c || b.length < HZ) return ko(new Error('son illisible')); const a = new Int16Array(b.length >> 1); for (let i = 0; i < a.length; i++) a[i] = b.readInt16LE(i * 2); ok(a); });
    });
  }
  async function ecouter(f, titre) {
    if (!o.envoyer) throw new Error('oreille indisponible');
    const pcm = await decoder(f);
    if (s.ecoute) s.ecoute.arreter('remplacée');
    s.ecoute = new Ecoute({ pcm, titre, envoyer: o.envoyer, surFin: (e) => { if (s.ecoute === e) { s.derniere = e.etat(); s.ecoute = null; } } }).demarrer();
    if (o.noter) o.noter(`papa te fait écouter « ${titre} » depuis le studio (${Math.round(s.ecoute.duree)} s) : tu l'entends comme le son de son téléphone`);
    return s.ecoute.etat();
  }

  const MAX_IMPORT = 80 << 20;
  const repondre = (res, code, x) => { if (!res.headersSent) { res.writeHead(code, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(x)); } };
  const extDe = (type, nom) => {
    const e = path.extname(String(nom || '')).toLowerCase();
    if (EXT_SON.has(e)) return e;
    const t = String(type || '');
    return /mpeg|mp3/.test(t) ? '.mp3' : /wav/.test(t) ? '.wav' : /mp4|m4a|aac/.test(t) ? '.m4a' : /ogg|opus/.test(t) ? '.ogg' : /flac/.test(t) ? '.flac' : '.webm';
  };
  const titreDe = (nom) => String(nom || '').replace(/\.[a-z0-9]{2,4}$/i, '').replace(/[\x00-\x1f<>]/g, ' ').trim().slice(0, 80);
  const idDe = (p) => `${p}-${new Date().toISOString().replace(/\D/g, '').slice(0, 14)}-${Math.random().toString(16).slice(2, 6)}`;
  const ecrire = (f, d) => { fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f + '.tmp', JSON.stringify(d, null, 1)); fs.renameSync(f + '.tmp', f); };
  const corpsJson = async (req) => { try { return JSON.parse(String(await lireCorps(req, 16384) || '{}')) || {}; } catch (_) { return {}; } };
  // (10/11) les calages gardés, par sortie : studio/calages.json
  const CALAGES = path.join(STUDIO, 'calages.json');
  const lireCalages = () => { const c = lireJson(CALAGES, null); return c && typeof c === 'object' && c.sorties ? c : { sorties: {}, avance: null }; };
  const calagesVus = (c = lireCalages()) => Object.fromEntries(Object.entries(c.sorties).map(([k, f]) => [k, calageDe(f, c.avance)]).filter(([, v]) => v));
  const mot = (v, n) => String(v ?? '').replace(/[\x00-\x1f<>]/g, ' ').trim().slice(0, n);

  function servir(req, res, f, telecharger) {
    const taille = fs.statSync(f).size, type = TYPES_SON[path.extname(f).toLowerCase()] || 'application/octet-stream';
    const entetes = { 'Content-Type': type, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-store',
      ...(telecharger ? { 'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(path.basename(f))}` } : {}) };
    const m = /^bytes=(\d*)-(\d*)$/.exec(String(req.headers.range || ''));
    if (m && (m[1] || m[2])) {
      let a = m[1] ? +m[1] : Math.max(0, taille - +m[2]), b = m[1] && m[2] ? Math.min(+m[2], taille - 1) : taille - 1;
      if (a >= taille || a > b) { res.writeHead(416, { 'Content-Range': `bytes */${taille}` }); return res.end(); }
      res.writeHead(206, { ...entetes, 'Content-Range': `bytes ${a}-${b}/${taille}`, 'Content-Length': b - a + 1 });
      return fs.createReadStream(f, { start: a, end: b }).pipe(res);
    }
    res.writeHead(200, { ...entetes, 'Content-Length': taille });
    fs.createReadStream(f).pipe(res);
  }

  async function route(req, res, p) {
    const u = new URL(req.url, 'http://x'), q = u.searchParams;
    if (p === '/api/studio/etat' && req.method === 'GET') return repondre(res, 200, etat());
    if (p === '/api/studio/son' && req.method === 'GET') {
      const f = chemin(q.get('f'));
      if (!f) return repondre(res, 404, { erreur: 'son introuvable' });
      return servir(req, res, f, q.get('telecharger') === '1');
    }
    if (req.method !== 'POST') return repondre(res, 405, { erreur: 'méthode refusée' });
    // une instru importée (ou un son à lui faire écouter) : le corps brut
    if (p === '/api/studio/importer' || p === '/api/studio/ecouter/fichier') {
      const b = await lireCorps(req, MAX_IMPORT);
      if (!b || b.length < 1000) return repondre(res, 400, { erreur: 'fichier absent ou trop lourd (80 Mo au plus)' });
      const nom = q.get('nom') || 'son', ext = extDe(req.headers['content-type'], nom);
      if (p === '/api/studio/ecouter/fichier') {
        const f = path.join(os.tmpdir(), `jarvis-studio-${process.pid}-${Date.now()}${ext}`);
        fs.writeFileSync(f, b);
        try { return repondre(res, 200, await ecouter(f, titreDe(nom) || 'un son')); }
        catch (e) { return repondre(res, 400, { erreur: e.message }); }
        finally { fs.unlink(f, () => {}); }
      }
      const id = idDe('I'), dir = path.join(STUDIO, 'instrus'), f = path.join(dir, id + ext);
      fs.mkdirSync(dir, { recursive: true }); fs.writeFileSync(f, b);
      const d = await dureeDe(f);
      if (!d) { fs.unlink(f, () => {}); return repondre(res, 400, { erreur: 'ce fichier n’est pas un son lisible' }); }
      const fiche = { id, titre: titreDe(nom) || 'Instru importée', mp3: f, origine: 'import', duree_s: d, fin: Date.now() / 1000 };
      ecrire(path.join(dir, id + '.json'), fiche);
      return repondre(res, 200, { ok: true, id, f: rel(f) });
    }
    // une prise : le WAV enregistré par la page, calé sur l'instru (sa latence mesurée, retirée au mix)
    if (p === '/api/studio/prise') {
      const instru = chemin(q.get('instru'));
      if (!instru) return repondre(res, 400, { erreur: 'instru inconnue' });
      const b = await lireCorps(req, MAX_IMPORT);
      if (!b || b.length < 1000) return repondre(res, 400, { erreur: 'prise vide ou trop lourde' });
      const id = idDe('P'), dir = path.join(STUDIO, 'prises'), f = path.join(dir, id + extDe(req.headers['content-type'], ''));
      fs.mkdirSync(dir, { recursive: true }); fs.writeFileSync(f, b);
      const lat = Math.max(-500, Math.min(1500, Math.round(Number(q.get('latence')) || 0)));
      const fi = etat().instrus.find(x => x.f === rel(instru)) || etat().chansons.find(x => x.f === rel(instru)) || etat().mixes.find(x => x.f === rel(instru));
      const fiche = { id, fichier: f, titre: titreDe(q.get('titre')) || `Prise sur ${fi ? fi.titre : path.basename(instru)}`, ts: Date.now(), duree_s: await dureeDe(f),
        instru_chemin: instru, instru_f: rel(instru), instru_titre: fi ? fi.titre : path.basename(instru), latence_ms: lat, choisie: false,
        // (10/11) par où papa écoutait, quel micro l'a enregistré, et d'où vient le calage
        sortie_cle: mot(q.get('cle'), 140), sortie_nom: mot(q.get('sortie'), 80), micro: mot(q.get('micro'), 80), calage_methode: mot(q.get('methode'), 12) };
      ecrire(path.join(dir, id + '.json'), fiche);
      return repondre(res, 200, { ok: true, id, f: rel(f) });
    }
    // (10/11) un calage mesuré (ou réglé à la main) pour la sortie où papa écoute : gardé, et l'avance de papa apprise
    if (p === '/api/studio/calage') {
      const x = await corpsJson(req), cle = mot(x.cle, 140), methode = String(x.methode || '');
      if (!/^(appli|web)\|./.test(cle) || !METHODES_CALAGE.includes(methode) || !Number.isFinite(Number(x.ms)) || x.ms === null || x.ms === '')
        return repondre(res, 400, { erreur: 'calage illisible' });
      const n = (v, a, b) => (v === null || v === undefined || v === '' || !Number.isFinite(Number(v)) ? undefined : Math.max(a, Math.min(b, Math.round(Number(v) * 10) / 10)));
      const c = lireCalages(), fiche = c.sorties[cle] || { mesures: {} };
      fiche.nom = mot(x.nom, 80) || fiche.nom || '';
      fiche.mesures[methode] = { ms: n(x.ms, -500, 1500), ecart_ms: n(x.ecart_ms, 0, 1000), n: n(x.n, 0, 100), total: n(x.total, 0, 100),
        annonce_ms: n(x.annonce_ms, -1000, 3000), micro: mot(x.micro, 80), date: Date.now() };
      fiche.dernier = methode;
      c.sorties[cle] = fiche;
      if (methode !== 'main') { const a = avanceDe(fiche); if (a) c.avance = { ...a, cle }; }
      ecrire(CALAGES, c);
      return repondre(res, 200, { ok: true, calage: calageDe(fiche, c.avance), calages: calagesVus(c), avance: c.avance || null });
    }
    if (p === '/api/studio/prise/choisir' || p === '/api/studio/prise/effacer' || p === '/api/studio/prise/regler') {
      const x = await corpsJson(req), id = String(x.id || '');
      const dir = path.join(STUDIO, 'prises'), fj = path.join(dir, id + '.json');
      if (!/^P-\d{14}-[0-9a-f]{1,8}$/.test(id) || !fs.existsSync(fj)) return repondre(res, 404, { erreur: 'prise inconnue' });
      const fiche = lireJson(fj);
      if (p.endsWith('/effacer')) { fs.unlink(fiche.fichier, () => {}); fs.unlinkSync(fj); return repondre(res, 200, { ok: true }); }
      if (p.endsWith('/regler')) { fiche.latence_ms = Math.max(-500, Math.min(1500, Math.round(Number(x.latence_ms) || 0))); ecrire(fj, fiche); return repondre(res, 200, { ok: true }); }
      for (const a of fiches(dir)) if (a.id && a.choisie && a.id !== id) { a.choisie = false; ecrire(path.join(dir, a.id + '.json'), a); }
      fiche.choisie = true; ecrire(fj, fiche);
      return repondre(res, 200, { ok: true });
    }
    if (p === '/api/studio/mixer') {
      const x = await corpsJson(req);
      const fiche = lireJson(path.join(STUDIO, 'prises', String(x.prise || '').replace(/[^\w-]/g, '') + '.json'));
      if (!fiche) return repondre(res, 404, { erreur: 'prise inconnue' });
      const n = (v, a, b, d) => Number.isFinite(Number(v)) ? Math.max(a, Math.min(b, Number(v))) : d;
      const r = await python('lancer', { type: 'mixer', params: { prise: fiche.fichier, instru: fiche.instru_chemin, titre: titreDe(x.titre) || fiche.titre,
        latence_ms: fiche.latence_ms || 0, autotune: !!x.autotune, voix_db: n(x.voix_db, -6, 6, 0), reverb: n(x.reverb, 0, 1, 0.3), echo: n(x.echo, 0, 1, 0),
        debruitage: x.debruitage !== false, bpm: n(x.bpm, 0, 300, 0), par: 'papa' } });
      return repondre(res, r.ok ? 200 : 409, r);
    }
    if (p === '/api/studio/instru/extraire') {
      const x = await corpsJson(req), f = chemin(x.f);
      if (!f) return repondre(res, 404, { erreur: 'chanson introuvable' });
      const c = etat().chansons.find(y => y.f === rel(f));
      const r = await python('lancer', { type: 'instru', params: { source: f, titre: c ? c.titre : titreDe(path.basename(f)) } });
      return repondre(res, r.ok ? 200 : 409, r);
    }
    if (p === '/api/studio/instru/demander') {
      const x = await corpsJson(req);
      const r = await python('instru-hakim', { style: String(x.style || '').slice(0, 200), bpm: Number(x.bpm) || 0, duree_s: Number(x.duree_s) || 60, titre: titreDe(x.titre) });
      return repondre(res, r.ok ? 200 : 409, r);
    }
    if (p === '/api/studio/ecouter') {
      const x = await corpsJson(req), f = chemin(x.f);
      if (!f) return repondre(res, 404, { erreur: 'son introuvable' });
      try { return repondre(res, 200, await ecouter(f, titreDe(x.titre) || titreDe(path.basename(f)))); }
      catch (e) { return repondre(res, 400, { erreur: e.message }); }
    }
    if (p === '/api/studio/ecouter/arreter') { if (s.ecoute) s.ecoute.arreter('arrêtée par papa'); return repondre(res, 200, { ok: true }); }
    return repondre(res, 404, { erreur: 'inconnu' });
  }
  return { route, etat, chemin, ecouter, decoder, arreter: () => { if (s.ecoute) s.ecoute.arreter('arrêt du cockpit'); }, _s: s };
}

module.exports = { creer, trames, hauteur, wav16, Ecoute, HZ, calageDe, avanceDe };

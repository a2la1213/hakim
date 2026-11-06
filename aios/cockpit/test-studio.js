/* (06/11, Ahmed : « un truc Studio dans le cockpit » ; « lui faire écouter des sons, comme lui, sans lui envoyer ») le studio :
   l'oreille interne portée de l'appli (trames, blocs de 8 s), l'écoute au rythme du morceau par les routes mêmes du 🎧, les routes
   du studio sur des dossiers jetables (jamais la vraie file de calcul), et le branchement dans server.js. node --test test-studio.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const { execFileSync } = require('child_process');
const S = require('./studio.js');

const FFMPEG = '/usr/local/bin/ffmpeg';
const AVEC_FFMPEG = fs.existsSync(FFMPEG);
const lire = (f) => fs.readFileSync(path.join(__dirname, f), 'utf8');
const sinus = (hz, s, a = 0.5) => { const x = new Int16Array(Math.round(S.HZ * s)); for (let i = 0; i < x.length; i++) x[i] = Math.round(a * 32767 * Math.sin(2 * Math.PI * hz * i / S.HZ)); return x; };

test('ses trames : une toutes les 100 ms, la hauteur d’un la, les graves d’une basse', () => {
  const t = S.trames(sinus(440, 2));
  assert.equal(t.length, 20);
  assert.ok(Math.abs(t[5][4] - 440) <= 6, `f0 ${t[5][4]}`);
  assert.ok(t[5][0] > 0.3 && t[5][0] < 0.4, 'niveau ≈ 0,35 (efficace d’un sinus à 0,5)');
  assert.ok(t[5][2] > t[5][1] && t[5][2] > t[5][3], 'un la à 440 Hz : surtout des médiums (les filtres de l’appli)');
  const aigu = S.trames(sinus(4000, 1));
  assert.ok(aigu[5][3] > aigu[5][1] && aigu[5][3] > aigu[5][2], 'à 4 kHz : des aigus');
  const basse = S.trames(sinus(60, 1));
  assert.ok(basse[5][1] > basse[5][3], 'une basse à 60 Hz : des graves');
  assert.equal(S.trames(new Int16Array(16000))[3][4], 0, 'le silence n’a pas de hauteur');
  const w = S.wav16(sinus(440, 1));
  assert.equal(w.toString('ascii', 0, 4), 'RIFF'); assert.equal(w.readUInt32LE(24), 16000); assert.equal(w.length, 44 + 32000);
});

test('faire écouter : au rythme du morceau, par les routes mêmes de son oreille interne (🎧), sans message', async () => {
  let maintenant = 1_000_000;
  const appels = [];
  const envoyer = (chemin, corps, type) => { appels.push({ chemin, corps, type, t: maintenant }); return Promise.resolve(chemin.startsWith('/api/voix/transcrire') ? { statut: 200, json: { texte: 'je chante pour papa' } } : { statut: 200, json: { ok: true } }); };
  // 8 s de son puis 9 s de silence : un bloc chanté, un bloc muet (jamais transcrit), une fin trop courte
  const pcm = new Int16Array(S.HZ * 17); pcm.set(sinus(220, 8, 0.3));
  let fin = null;
  const e = new S.Ecoute({ pcm, titre: 'Ma prise', envoyer, maintenant: () => maintenant, minuteur: false, surFin: (x, r) => { fin = r; } }).demarrer();
  assert.deepEqual(JSON.parse(appels[0].corps).details, { titre: 'Ma prise', artiste: 'le studio de papa', etat: 'lecture' });
  assert.equal(appels[0].chemin, '/api/corps/evenement');
  maintenant += 999; e.avancer();
  assert.equal(appels.length, 1, 'rien avant la fin de la première seconde : le temps réel');
  maintenant += 1; e.avancer();
  const sf = JSON.parse(appels[1].corps);
  assert.equal(appels[1].chemin, '/api/voix/son-flux');
  assert.deepEqual([sf.source, sf.t0, sf.pas_ms, sf.trames.length], ['telephone', 1_000_000, 100, 10]);
  maintenant += 7000; e.avancer();
  const tr = appels.find(a => a.chemin.startsWith('/api/voix/transcrire'));
  assert.ok(tr, 'le bloc de 8 s part à la grande oreille');
  const q = new URL(tr.chemin, 'http://x').searchParams;
  assert.deepEqual([q.get('source'), q.get('t0'), q.get('ms'), q.get('cle')], ['telephone', '1000000', '8000', '1000000']);
  assert.equal(tr.type, 'audio/wav'); assert.equal(tr.corps.length, 44 + 8 * S.HZ * 2);
  await new Promise(r => setImmediate(r));
  const ecoute = appels.find(a => a.chemin === '/api/corps/evenement' && JSON.parse(a.corps).type === 'son_ecoute');
  assert.deepEqual(JSON.parse(ecoute.corps).details, { texte: 'je chante pour papa', morceau: 'Ma prise', debut_ms: 1_000_000 });
  assert.equal(e.etat().position_s, 8);
  maintenant += 9100; e.avancer();
  assert.equal(appels.filter(a => a.chemin.startsWith('/api/voix/transcrire')).length, 1, 'le bloc muet n’est pas transcrit');
  assert.equal(appels.filter(a => a.chemin === '/api/voix/son-flux').length, 17, 'une ligne de trames par seconde');
  assert.equal(fin, 'fini'); assert.equal(e.etat().actif, false);
  assert.equal(JSON.parse(appels[appels.length - 1].corps).details.etat, 'pause');
  assert.ok(!appels.some(a => /message|chat|piece|joindre/.test(a.chemin)), 'ni message ni pièce jointe');
});

function serveurDe(studio) {
  return new Promise((ok) => {
    const srv = http.createServer((req, res) => studio.route(req, res, new URL(req.url, 'http://x').pathname));
    srv.listen(0, '127.0.0.1', () => ok(srv));
  });
}
const lireCorps = (req, max) => new Promise((ok) => { const m = []; let n = 0; req.on('data', c => { n += c.length; if (n <= max) m.push(c); }); req.on('end', () => ok(n > max ? null : Buffer.concat(m))); });
async function appel(srv, methode, chemin, corps, type = 'application/json', entetes = {}) {
  const r = await fetch(`http://127.0.0.1:${srv.address().port}${chemin}`, { method: methode, headers: { 'Content-Type': type, ...entetes },
    body: corps === undefined ? undefined : (Buffer.isBuffer(corps) ? corps : JSON.stringify(corps)) });
  const b = Buffer.from(await r.arrayBuffer());
  let j = null; try { j = JSON.parse(b.toString()); } catch (_) {}
  return { statut: r.status, j, b, h: r.headers };
}

test('les routes du studio : ses sons, l’import, les prises, le mix mis en file, lui faire écouter', { skip: !AVEC_FFMPEG }, async () => {
  const racine = fs.mkdtempSync(path.join(os.tmpdir(), 'studio-test-'));
  const jarvis = path.join(racine, 'jarvis'), ch = path.join(jarvis, 'chansons');
  fs.mkdirSync(path.join(ch, 'studio'), { recursive: true });
  const wav = path.join(racine, 'son.wav');
  execFileSync(FFMPEG, ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=330:d=3', '-ar', '44100', wav]);
  fs.copyFileSync(wav, path.join(ch, '20261106-120000-papa.mp3'));
  fs.writeFileSync(path.join(ch, '20261106-120000-papa.json'), JSON.stringify({ nom: '20261106-120000-papa', titre: 'Pour papa', style: 'raï', etat: 'prête',
    mp3: path.join(ch, '20261106-120000-papa.mp3'), duree_s: 3, fin: 1762426800, instrumental: true, telephone: '/x' }));
  fs.writeFileSync(path.join(ch, 'secret.txt'), 'non');
  const lances = [], envois = [], notes = [];
  const studio = S.creer({ jarvis, lireCorps, appeler: (a, q) => { lances.push([a, q]); return { ok: true, id: 'J-1' }; },
    envoyer: (c) => { envois.push(c); return Promise.resolve({ statut: 200, json: {} }); }, noter: (t) => notes.push(t) });
  const srv = await serveurDe(studio);
  try {
    let r = await appel(srv, 'GET', '/api/studio/etat');
    assert.equal(r.statut, 200);
    assert.deepEqual(r.j.chansons.map(c => [c.titre, c.f, c.instrumental, c.telephone]), [['Pour papa', '20261106-120000-papa.mp3', true, true]]);
    assert.match(r.j.telephone, /Hakim › Chansons/);
    // un son servi, avec Range ; rien hors des sons
    r = await appel(srv, 'GET', '/api/studio/son?f=20261106-120000-papa.mp3', undefined, 'x', { Range: 'bytes=0-99' });
    assert.equal(r.statut, 206); assert.equal(r.b.length, 100); assert.match(r.h.get('content-range'), /^bytes 0-99\/\d+$/);
    for (const f of ['../../etc/passwd', 'secret.txt', '/etc/hosts', '.cache/x.mp3', 'studio/../../x.mp3'])
      assert.equal((await appel(srv, 'GET', `/api/studio/son?f=${encodeURIComponent(f)}`)).statut, 404, f);
    // une instru importée
    r = await appel(srv, 'POST', '/api/studio/importer?nom=Ma%20prod.wav', fs.readFileSync(wav), 'audio/wav');
    assert.equal(r.statut, 200); assert.match(r.j.f, /^studio\/instrus\/I-\d{14}-[0-9a-f]+\.wav$/);
    const instru = r.j.f;
    assert.equal((await appel(srv, 'POST', '/api/studio/importer?nom=x.mp3', Buffer.alloc(5000, 7), 'audio/mpeg')).statut, 400, 'pas un son');
    // une prise sur cette instru, puis choisie, recalée, mixée
    assert.equal((await appel(srv, 'POST', '/api/studio/prise?instru=secret.txt', fs.readFileSync(wav), 'audio/wav')).statut, 400);
    r = await appel(srv, 'POST', `/api/studio/prise?instru=${encodeURIComponent(instru)}&latence=180`, fs.readFileSync(wav), 'audio/wav');
    assert.equal(r.statut, 200);
    const id = r.j.id;
    r = await appel(srv, 'GET', '/api/studio/etat');
    assert.deepEqual([r.j.prises[0].id, r.j.prises[0].latence_ms, r.j.prises[0].instru_titre, r.j.prises[0].choisie], [id, 180, 'Ma prod', false]);
    assert.equal(Math.round(r.j.prises[0].duree_s), 3);
    assert.equal((await appel(srv, 'POST', '/api/studio/prise/choisir', { id })).statut, 200);
    assert.equal((await appel(srv, 'POST', '/api/studio/prise/regler', { id, latence_ms: 240 })).statut, 200);
    assert.equal((await appel(srv, 'POST', '/api/studio/prise/choisir', { id: '../x' })).statut, 404);
    r = await appel(srv, 'POST', '/api/studio/mixer', { prise: id, autotune: true, voix_db: 99, reverb: 0.4 });
    assert.equal(r.statut, 200);
    const [action, q] = lances[0];
    assert.equal(action, 'lancer'); assert.equal(q.type, 'mixer');
    assert.deepEqual([q.params.latence_ms, q.params.autotune, q.params.voix_db, q.params.reverb, q.params.instru], [240, true, 6, 0.4, path.join(ch, instru)]);
    // l'instru d'une de ses chansons (Demucs), une instru demandée à Hakim
    assert.equal((await appel(srv, 'POST', '/api/studio/instru/extraire', { f: '20261106-120000-papa.mp3' })).statut, 200);
    assert.deepEqual([lances[1][1].type, lances[1][1].params.titre], ['instru', 'Pour papa']);
    assert.equal((await appel(srv, 'POST', '/api/studio/instru/demander', { style: 'trap', bpm: 140, duree_s: 45 })).statut, 200);
    assert.deepEqual(lances[2], ['instru-hakim', { style: 'trap', bpm: 140, duree_s: 45, titre: '' }]);
    // lui faire écouter : l'écoute part (au rythme du morceau), il le sait au fil, et s'arrête au geste
    r = await appel(srv, 'POST', '/api/studio/ecouter', { f: '20261106-120000-papa.mp3' });
    assert.equal(r.statut, 200); assert.equal(r.j.actif, true); assert.equal(r.j.duree_s, 3);
    assert.match(notes[0], /papa te fait écouter « 20261106-120000-papa »/);
    assert.equal((await appel(srv, 'GET', '/api/studio/etat')).j.ecoute.actif, true);
    await appel(srv, 'POST', '/api/studio/ecouter/arreter', {});
    assert.equal((await appel(srv, 'GET', '/api/studio/etat')).j.ecoute.actif, false);
    assert.ok(envois.every(c => c === '/api/corps/evenement' || c.startsWith('/api/voix/')));
    // un fichier à lui faire écouter, sans le garder
    r = await appel(srv, 'POST', '/api/studio/ecouter/fichier?nom=Rage.wav', fs.readFileSync(wav), 'audio/wav');
    assert.equal(r.statut, 200); assert.equal(r.j.titre, 'Rage');
    studio.arreter();
    assert.ok(!fs.readdirSync(os.tmpdir()).some(n => n.startsWith(`jarvis-studio-${process.pid}-`)), 'le fichier temporaire effacé');
    // la prise effacée
    assert.equal((await appel(srv, 'POST', '/api/studio/prise/effacer', { id })).statut, 200);
    assert.equal((await appel(srv, 'GET', '/api/studio/etat')).j.prises.length, 0);
  } finally { srv.close(); studio.arreter(); fs.rmSync(racine, { recursive: true, force: true }); }
});

test('server.js branche le studio : derrière le jeton, sa page, son oreille en requêtes locales, l’arrêt', () => {
  const SRV = lire('server.js');
  assert.match(SRV, /'\/reglages': 'reglages\.html', '\/studio': 'studio\.html' \}/);
  assert.match(SRV, /if \(p\.startsWith\('\/api\/studio\/'\)\) \{[^\n]*\n    if \(!jetonValide\(req\)\) \{ res\.writeHead\(403/);
  assert.match(SRV, /const STUDIO = require\('\.\/studio\.js'\)\.creer\(\{ jarvis: JARVIS, anamnese: ANAMNESE, lireCorps, envoyer: requeteLocale,/);
  assert.match(SRV, /headers: \{ 'Content-Type': type, 'Content-Length': b\.length, 'X-Jeton': JETON, Host: `127\.0\.0\.1:\$\{PORT\}` \}/);
  assert.match(SRV, /const toutCouper = \(\) => \{ arretCockpit = true; try \{ STUDIO\.arreter\(\); \} catch \(_\) \{\}/);
});

test('la page Studio : le menu, la barre commune sans nav.js, le micro sans effets, ses quatre parties', () => {
  const h = lire('public/studio.html'), js = lire('public/studio-page.js');
  assert.match(lire('public/badges.js'), /\['studio', '\/studio', 'Studio'\]/);
  assert.ok(!/<script src="\/nav\.js">/.test(h) && !/<script src="\/orbe\.js">/.test(h));
  assert.match(h, /<script src="\/badges\.js"><\/script>\n  <script>Badges\.suivre\(document\.querySelector\('nav\.topnav'\), 'studio'\);<\/script>/);
  for (const id of ['chansons', 'fichierEcoute', 'instru', 'importInstru', 'calibClic', 'calibTaper', 'rec', 'prises', 'mixer', 'mixes', 'calculs'])
    assert.match(h, new RegExp(`id="${id}"`), id);
  assert.match(js, /echoCancellation: false, noiseSuppression: false, autoGainControl: false/);
  assert.match(js, /'X-Jeton': window\.jeton\(\)/);
  const rendu = js.slice(js.indexOf('  function rendre() {'), js.indexOf('  let minuteur = 0;'));
  const html = rendu.split('\n').filter(l => /innerHTML|^\s*\+ `/.test(l)).join('\n');
  const nus = html.match(/\$\{(?!esc\()[^{}]*\.(titre|texte|style|erreur|fin|f|id)\}/g) || [];
  assert.deepEqual(nus, [], 'tout texte venu du disque est échappé dans le rendu');
});

test('l’enregistreur garde ce qui suit le départ de l’instru, au bon échantillon', () => {
  const js = lire('public/studio-page.js');
  const src = js.slice(js.indexOf('  function enregistreur('), js.indexOf('  function clic('));
  const f = new Function(`const TAMPON = 2048; ${src}; return enregistreur;`)();
  let proc = null;
  const c = { sampleRate: 1000, createMediaStreamSource: () => ({ connect() {}, disconnect() {} }), createGain: () => ({ gain: {}, connect() {} }),
    destination: {}, createScriptProcessor: () => (proc = { connect() {}, disconnect() {} }) };
  const r = f(c, { getTracks: () => [] }, 2.5, null);
  const morceau = (t, v) => proc.onaudioprocess({ playbackTime: t, inputBuffer: { getChannelData: () => Float32Array.from({ length: 1000 }, (_, i) => v + i / 1e4) } });
  morceau(1, 0.1); morceau(2, 0.2); morceau(3, 0.3);
  const x = r.arreter();
  assert.equal(x.length, 1500, 'la moitié du 2e morceau, tout le 3e');
  assert.ok(Math.abs(x[0] - (0.2 + 500 / 1e4)) < 1e-6, 'le premier échantillon gardé est celui de T0');
});

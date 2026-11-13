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
    r = await appel(srv, 'POST', `/api/studio/prise?instru=${encodeURIComponent(instru)}&latence=180&cle=${encodeURIComponent('appli|bluetooth:ICONIC Sound 2')}&sortie=${encodeURIComponent('ICONIC Sound 2 (Bluetooth)')}&micro=${encodeURIComponent('le micro du téléphone ✓')}&methode=boucle`, fs.readFileSync(wav), 'audio/wav');
    assert.equal(r.statut, 200);
    const id = r.j.id;
    r = await appel(srv, 'GET', '/api/studio/etat');
    assert.deepEqual([r.j.prises[0].id, r.j.prises[0].latence_ms, r.j.prises[0].instru_titre, r.j.prises[0].choisie], [id, 180, 'Ma prod', false]);
    assert.deepEqual([r.j.prises[0].sortie, r.j.prises[0].micro, r.j.prises[0].methode], ['ICONIC Sound 2 (Bluetooth)', 'le micro du téléphone ✓', 'boucle'], 'par où papa écoutait, et quel micro');
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
  assert.match(SRV, /'\/reglages': 'reglages\.html', '\/studio': 'studio\.html'(, '\/atelier': 'atelier\.html')? \}/);
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
  for (const id of ['chansons', 'fichierEcoute', 'instru', 'importInstru', 'calibClic', 'calibTaper', 'rec', 'prises', 'mixer', 'mixes', 'calculs', 'route', 'calages', 'taper'])
    assert.match(h, new RegExp(`id="${id}"`), id);
  assert.match(js, /echoCancellation: false, noiseSuppression: false, autoGainControl: false/);
  // (10/11) les calculs du calage chargés avant la page ; dans l'appli, le micro de l'appli (jamais getUserMedia : Chromium y prendrait
  // le casque Bluetooth en SCO), et le micro du navigateur choisi par son nom
  assert.match(h, /<script src="\/studio-calage\.js"><\/script>\n  <script src="\/studio-page\.js"><\/script>/);
  assert.match(js, /const App = window\.HakimApp && typeof window\.HakimApp\.studioMicroOuvrir === 'function'/);
  const ouvrir = js.slice(js.indexOf('  async function ouvrirMicro() {'), js.indexOf('  // l\'écart des horloges'));
  assert.match(ouvrir, /if \(!App\) return microWeb\(\);/);
  assert.ok(!/getUserMedia/.test(ouvrir.slice(ouvrir.indexOf('if (!App) return microWeb();') + 30)), 'dans l’appli : jamais getUserMedia');
  assert.match(js, /deviceId: \{ exact: id \}/);
  assert.match(js, /'X-Jeton': window\.jeton\(\)/);
  const rendu = js.slice(js.indexOf('  function rendre() {'), js.indexOf('  let minuteur = 0;'));
  const html = rendu.split('\n').filter(l => /innerHTML|^\s*\+ `/.test(l)).join('\n');
  const nus = html.match(/\$\{(?!esc\()[^{}]*\.(titre|texte|style|erreur|fin|f|id)\}/g) || [];
  assert.deepEqual(nus, [], 'tout texte venu du disque est échappé dans le rendu');
});

test('l’enregistreur garde ce qui suit le départ de l’instru, au bon échantillon', () => {
  const js = lire('public/studio-page.js');
  const src = js.slice(js.indexOf('  function enregistreur('), js.indexOf('  function clic('));
  const crete = js.slice(js.indexOf('  const crete = '), js.indexOf('\n', js.indexOf('  const crete = ')));
  const f = new Function(`const TAMPON = 2048; ${crete}; ${src}; return enregistreur;`)();
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

/* ---------- (10/11, Ahmed : « toujours le micro du smartphone, même s'il est en écouteurs Bluetooth, et calculer le décalage de
   l'écoute et de la voix ») le micro, le temps, la mesure, le calage par sortie ---------- */
const K = require('./public/studio-calage.js');

test('le micro du navigateur : l’intégré, jamais celui d’un casque', () => {
  const e = (deviceId, label) => ({ kind: 'audioinput', deviceId, label });
  // Chrome sur Android (les noms de Chromium) : « Speakerphone » est le micro du téléphone, jamais « Bluetooth headset »
  assert.equal(K.choisirMicroWeb([e('default', 'Default'), e('a', 'Bluetooth headset'), e('b', 'Headset earpiece'), e('c', 'Speakerphone')]).deviceId, 'c');
  // un Mac avec des AirPods : le micro du MacBook, même si les AirPods sont le micro par défaut
  assert.equal(K.choisirMicroWeb([e('default', 'Par défaut - AirPods Pro (Bluetooth)'), e('x', 'AirPods Pro (Bluetooth)'), e('y', 'MacBook Air Microphone (Built-in)')]).deviceId, 'y');
  // Windows : le micro de la machine, pas le « Hands-Free » des écouteurs
  assert.equal(K.choisirMicroWeb([e('communications', 'Communications - Headset'), e('h', 'Casque (WH-1000XM4 Hands-Free)'), e('r', 'Microphone (Realtek(R) Audio)')]).deviceId, 'r');
  assert.equal(K.choisirMicroWeb([e('', ''), e('', '')]), null, 'pas de noms (pas encore autorisé) : rien de sûr');
  assert.equal(K.choisirMicroWeb([e('default', 'Default - Galaxy Buds'), e('z', 'Galaxy Buds3 Pro')]), null, 'seulement un casque : rien');
  assert.equal(K.choisirMicroWeb([{ kind: 'audiooutput', deviceId: 'o', label: 'Speakers' }]), null, 'une sortie n’est pas un micro');
});

test('le temps : la prise de l’appli recalée sur l’instant où l’instru sort au casque', () => {
  const sr = 48000, off = 987654.321;             // horloge d'Android moins horloge de la page (ms)
  const latSortie = 183, latEntree = 37;          // ce que le téléphone annonce : sortie (Bluetooth) et entrée (le micro)
  const perfDe = (T) => 5000 + T * 1000 + latSortie;   // l'instant où le temps T de l'AudioContext sort au casque
  const debutMono = perfDe(0) - latSortie + off - 2000; // le micro démarre 2 s avant le temps 0 de l'instru (horloge d'Android)
  const monoDe = (f) => debutMono + f / sr * 1000;      // l'instant où l'échantillon f est entré dans le micro
  const T0 = 3.2, voix = Math.round((perfDe(T0) + off - debutMono) * sr / 1000);   // papa chante pile quand il entend T0
  const tout = new Float32Array(sr * 8); tout[voix] = 0.9;
  const morceaux = [];
  for (let p = 0; p < tout.length; p += 3840) morceaux.push({ premier: p, x: tout.slice(p, p + 3840) });
  // Android horodate en retard sur la lecture (latEntree), le navigateur donne ses getOutputTimestamp avec un peu de bruit
  const stamps = [1, 2, 3, 4, 5, 6].map(k => { const f = k * sr; return { f, ns: Math.round(monoDe(f) * 1e6), micro: true }; });
  stamps.push({ f: 2.5 * sr, ns: Math.round((monoDe(2.5 * sr) + latEntree + 400) * 1e6), micro: false });   // un repli faux : jamais choisi
  const sorties = [2.9, 3.0, 3.1, 3.3, 3.5, 9].map((ctx, i) => ({ ctx, perf: perfDe(ctx) + [0.4, -0.3, 0.1, 0.2, -0.2, 50][i] }));
  // l'écart (ms) entre le départ gardé et la voix chantée sur T0 : 0, c'est la voix posée sur le temps ; négatif, elle arrive en retard
  const ecart = (r) => (r.f0 - voix) / sr * 1000;
  const r = K.aligner({ morceaux, stamps, sorties, repli: null, off, T0, sr });
  assert.equal(r.sortie, 'navigateur'); assert.equal(r.horodatage, 'micro');
  assert.ok(Math.abs(ecart(r)) <= 0.5, `la voix chantée sur T0 tombe sur le départ de la prise (écart ${ecart(r)} ms)`);
  assert.ok(r.x[voix - r.f0] > 0.5 || r.x[voix - r.f0 + 1] > 0.5 || voix < r.f0, 'la prise gardée est bien le son du micro à partir de f0');
  // sans les getOutputTimestamp : l'estimation (heure de la page + retard annoncé)
  const r2 = K.aligner({ morceaux, stamps, sorties: [], repli: { ctx: 0, perf: 5000, sortie_ms: latSortie }, off, T0, sr });
  assert.equal(r2.sortie, 'estimation'); assert.ok(Math.abs(ecart(r2)) <= 0.05, `estimation : ${ecart(r2)}`);
  assert.equal(r2.x[0], 0.8999999761581421, 'sans bruit, la voix est le premier échantillon gardé');
  // les témoins : sans le retard de sortie (le temps de rendu pris pour celui du casque), la voix arrive 183 ms trop tard ; une horloge
  // fausse de 50 ms : 50 ms trop tard ; une horloge perdue : pas de prise du tout
  const sansSortie = K.aligner({ morceaux, stamps, sorties: [], repli: { ctx: 0, perf: 5000, sortie_ms: 0 }, off, T0, sr });
  assert.ok(Math.abs(ecart(sansSortie) + latSortie) <= 0.05, `sans le retard de sortie : ${ecart(sansSortie)}`);
  const horlogeFausse = K.aligner({ morceaux, stamps, sorties, repli: null, off: off - 50, T0, sr });
  assert.ok(Math.abs(ecart(horlogeFausse) + 50) <= 0.5, `horloge fausse : ${ecart(horlogeFausse)}`);
  assert.equal(K.aligner({ morceaux, stamps, sorties, repli: null, off: 0, T0, sr }), null, 'une horloge perdue : rien, jamais une prise fausse');
  // le repli de l'horodatage (l'instant de la lecture) ne sert que si Android n'en donne aucun
  const lecture = K.aligner({ morceaux, stamps: stamps.filter(x => !x.micro), sorties, repli: null, off, T0, sr });
  assert.equal(lecture.horodatage, 'lecture');
  // des échantillons perdus : du silence à leur place, la suite reste à son numéro
  const trou = K.assembler([{ premier: 0, x: Float32Array.of(1, 2) }, { premier: 5, x: Float32Array.of(6) }]);
  assert.deepEqual([...trou], [1, 2, 0, 0, 0, 6]);
  // rien pour caler : null (la page le dit, elle ne garde pas une prise fausse)
  assert.equal(K.aligner({ morceaux, stamps: [], sorties, off, T0, sr }), null);
  // les deux horloges : l'aller-retour le plus court
  const h = K.decalageHorloge([{ avant: 10, horloge: 1015, apres: 14 }, { avant: 20, horloge: 1020.5, apres: 20.6 }, { avant: 30, horloge: 1031, apres: 31.2 }]);
  assert.ok(Math.abs(h.off - 1000.2) < 1e-9 && Math.abs(h.incertitude - 0.3) < 1e-9);
  // le son de l'appli : 16 bits little-endian en base64
  const pcm = Int16Array.of(0, 16384, -32768, 32767);
  const x = K.pcmDe(Buffer.from(pcm.buffer).toString('base64'));
  assert.deepEqual([...x], [0, 0.5, -1, 32767 / 32768]);
});

// un enregistrement de mesure : `debut` s de bruit, puis un son à chaque clic, en retard de `retards[k]` ms (null : rien d'entendu)
function mesureSimulee(sr, retards, pas, o = {}) {
  const debut = 0.5, x = new Float32Array(Math.round((debut + retards.length * pas + 0.5) * sr));
  let g = 12345;
  const bruit = () => { g = (g * 1103515245 + 12345) & 0x7fffffff; return (g / 0x7fffffff - 0.5) * 2 * (o.bruit || 0.002); };
  for (let i = 0; i < x.length; i++) x[i] = bruit();
  retards.forEach((r, k) => {
    if (r === null) return;
    const a = Math.round((debut + k * pas + r / 1000) * sr);
    // le clic (1 500 Hz) ; une frappe du doigt sur le téléphone : un choc grave (150 Hz), amorti
    const hz = o.frappe ? 150 : 1500, amorti = o.frappe ? 0.012 : 0.006;
    for (let i = 0; i < sr * 0.04 && a + i < x.length; i++) x[a + i] += (o.fort || 0.4) * Math.exp(-i / (sr * amorti)) * Math.sin(2 * Math.PI * hz * i / sr);
    // le clic lui-même revenu au micro (la fuite d'un écouteur, ou le haut-parleur) à o.fuite ms, de force o.forceFuite
    if (o.fuite) { const b = Math.round((debut + k * pas + o.fuite / 1000) * sr); for (let i = 0; i < sr * 0.03; i++) x[b + i] += (o.forceFuite || 0.02) * Math.exp(-i / (sr * 0.006)) * Math.sin(2 * Math.PI * 1500 * i / sr); }
  });
  return x;
}

test('la mesure : les clics retrouvés dans le micro, l’écouteur contre le micro et en tapant', () => {
  const sr = 48000;
  // l'écouteur collé au micro : 8 clics revenus avec 213 ms de retard, à la milliseconde
  let r = K.analyserClics(mesureSimulee(sr, Array(8).fill(213), 0.6), sr, { debut: 0.5, pas: 0.6, n: 8 });
  assert.ok(Math.abs(r.ms - 213) <= 1 && r.ecart_ms <= 1 && r.n === 8 && r.total === 8, JSON.stringify(r));
  assert.ok(K.jugerMesure(r, 'boucle').ok);
  // un retard négatif (le téléphone annonce un peu trop) se mesure aussi
  r = K.analyserClics(mesureSimulee(sr, Array(8).fill(-35), 0.6), sr, { debut: 0.5, pas: 0.6, n: 8 });
  assert.ok(Math.abs(r.ms + 35) <= 1, `−35 ms : ${r.ms}`);
  // trop peu entendu : refusé, et dit combien
  r = K.analyserClics(mesureSimulee(sr, [213, null, null, 213, null, null, 213, null], 0.6), sr, { debut: 0.5, pas: 0.6, n: 8 });
  const j = K.jugerMesure(r, 'boucle');
  assert.equal(j.ok, false); assert.match(j.raison, /que 3 clics sur 8/);
  assert.equal(K.analyserClics(mesureSimulee(sr, Array(8).fill(null), 0.6), sr, { debut: 0.5, pas: 0.6, n: 8 }).n, 0, 'le silence : rien');
  // en tapant : 16 clics, les 4 premiers pour se caler (n'importe quoi), un humain à ±12 ms, une frappe ratée, un écart énorme écarté ;
  // l'écouteur qui fuit faiblement dans le micro (à 180 ms) : quand papa ne tape pas, cette fuite est écartée (loin des frappes)
  const humain = [400, -150, 0, 90, 251, 238, 262, 244, 249, 233, null, 255, 246, 520, 240, 257];
  const taper = { debut: 0.5, pas: 0.8, n: 16, ignorer: 4, passeBas: 500 };
  r = K.analyserClics(mesureSimulee(sr, humain, 0.8, { fort: 0.5, frappe: true, fuite: 180 }), sr, taper);
  assert.ok(Math.abs(r.ms - 249) <= 4, `en tapant : ${r.ms}`);
  assert.equal(r.total, 12); assert.equal(r.n, 10, 'la frappe ratée et l’écart de 520 ms ne comptent pas');
  assert.ok(r.ecart_ms < 20 && K.jugerMesure(r, 'taper').ok, JSON.stringify(r));
  assert.equal(K.jugerMesure({ ...r, ecart_ms: 80 }, 'taper').ok, false, 'trop irrégulier : refusé');
  // au haut-parleur : le clic revient au micro, six fois plus fort que la frappe, à 40 ms ; papa tape 25 ms en avance sur ce qu'il
  // entend (à 15 ms) : le filtre garde la frappe ; sans lui, on mesurerait le clic (le témoin : l'avance de papa serait perdue)
  const hp = mesureSimulee(sr, Array(16).fill(15), 0.8, { fort: 0.1, frappe: true, fuite: 40, forceFuite: 0.6 });
  r = K.analyserClics(hp, sr, taper);
  assert.ok(Math.abs(r.ms - 15) <= 4 && r.n === 12, `la frappe, pas le clic : ${JSON.stringify(r)}`);
  const sansFiltre = K.analyserClics(hp, sr, { ...taper, passeBas: 0 });
  assert.ok(Math.abs(sansFiltre.ms - 15) > 10, `sans le filtre, le clic l’emporte : ${sansFiltre.ms}`);
});

test('le calage par sortie : gardé, la dernière mesure s’applique, l’avance de papa apprise et retirée', async () => {
  // les fonctions
  const avance = { ms: -22 };
  assert.deepEqual(S.calageDe({ nom: 'X', dernier: 'taper', mesures: { taper: { ms: 230, ecart_ms: 9, n: 11, total: 12, date: 5 } } }, avance),
    { ms: 252, methode: 'taper', ecart_ms: 9, n: 11, total: 12, annonce_ms: null, avance_ms: -22, date: 5, nom: 'X', micro: '' });
  assert.equal(S.calageDe({ dernier: 'boucle', mesures: { boucle: { ms: 210 } } }, avance).ms, 210, 'l’écouteur contre le micro : rien d’humain à retirer');
  assert.equal(S.calageDe({ mesures: {} }, null), null);
  assert.deepEqual(S.avanceDe({ mesures: { boucle: { ms: 40, date: 0 }, taper: { ms: 18, date: 1000 } } }, 7), { ms: -22, date: 7 });
  assert.equal(S.avanceDe({ mesures: { boucle: { ms: 40, date: 0 }, taper: { ms: 18, date: 8 * 86400e3 } } }), null, 'trop loin dans le temps');
  assert.equal(S.avanceDe({ mesures: { boucle: { ms: 40, date: 0 }, taper: { ms: 400, date: 1 } } }), null, '360 ms : pas une avance');
  // les routes, sur un dossier jetable
  const racine = fs.mkdtempSync(path.join(os.tmpdir(), 'studio-calage-'));
  const jarvis = path.join(racine, 'jarvis');
  fs.mkdirSync(path.join(jarvis, 'chansons', 'studio'), { recursive: true });
  const studio = S.creer({ jarvis, lireCorps, appeler: () => ({ ok: true }) });
  const srv = await serveurDe(studio);
  try {
    const hp = 'appli|haut_parleur', bt = 'appli|bluetooth:ICONIC Sound 2';
    for (const mauvais of [{ cle: 'x', methode: 'boucle', ms: 1 }, { cle: hp, methode: 'deviner', ms: 1 }, { cle: hp, methode: 'boucle', ms: 'abc' }, { cle: hp, methode: 'boucle' }])
      assert.equal((await appel(srv, 'POST', '/api/studio/calage', mauvais)).statut, 400, JSON.stringify(mauvais));
    // au haut-parleur : la boucle (le clic revient au micro), puis en tapant : l'avance de papa apprise (−21 ms)
    let r = await appel(srv, 'POST', '/api/studio/calage', { cle: hp, nom: 'le haut-parleur du téléphone', methode: 'boucle', ms: 41.2, ecart_ms: 0.6, n: 8, total: 8, annonce_ms: 30 });
    assert.equal(r.statut, 200); assert.equal(r.j.calage.ms, 41); assert.equal(r.j.avance, null);
    r = await appel(srv, 'POST', '/api/studio/calage', { cle: hp, methode: 'taper', ms: 20.2, ecart_ms: 11, n: 11, total: 12 });
    assert.equal(r.j.avance.ms, -21); assert.equal(r.j.calage.methode, 'taper'); assert.equal(r.j.calage.ms, 41, 'en tapant, corrigé de l’avance : la boucle');
    // les écouteurs Bluetooth : seulement en tapant, l'avance retirée ; 9999 ms ramenés à 1500
    r = await appel(srv, 'POST', '/api/studio/calage', { cle: bt, nom: 'ICONIC Sound 2 (Bluetooth)', methode: 'taper', ms: 228, ecart_ms: 14, n: 10, total: 12, micro: 'le micro du téléphone ✓' });
    assert.equal(r.j.calage.ms, 249); assert.equal(r.j.calage.avance_ms, -21);
    // l'état : les deux sorties gardées, par leur nom
    let e = (await appel(srv, 'GET', '/api/studio/etat')).j;
    assert.deepEqual(Object.keys(e.calages).sort(), [bt, hp].sort());
    assert.deepEqual([e.calages[bt].nom, e.calages[bt].ms, e.calages[bt].micro, e.calages[hp].ms, e.avance.ms], ['ICONIC Sound 2 (Bluetooth)', 249, 'le micro du téléphone ✓', 41, -21]);
    // le curseur : réglé à la main, il s'applique tel quel (la dernière action) ; une nouvelle mesure reprend la main
    await appel(srv, 'POST', '/api/studio/calage', { cle: bt, methode: 'main', ms: 9999 });
    e = (await appel(srv, 'GET', '/api/studio/etat')).j;
    assert.deepEqual([e.calages[bt].methode, e.calages[bt].ms, e.calages[bt].nom], ['main', 1500, 'ICONIC Sound 2 (Bluetooth)']);
    r = await appel(srv, 'POST', '/api/studio/calage', { cle: bt, methode: 'boucle', ms: 236, ecart_ms: 0.8, n: 8, total: 8 });
    assert.deepEqual([r.j.calage.methode, r.j.calage.ms], ['boucle', 236]);
    assert.equal(r.j.avance.cle, bt, 'l’avance apprise aussi sur les écouteurs (taper 228 − boucle 236)');
    assert.equal(r.j.avance.ms, -8);
    assert.ok(fs.existsSync(path.join(jarvis, 'chansons', 'studio', 'calages.json')), 'gardé sur le disque du studio');
  } finally { srv.close(); studio.arreter(); fs.rmSync(racine, { recursive: true, force: true }); }
});

/* ---------- (13/11) le studio multipiste ---------- */
test('les routes des projets multipistes : lire, régler avec la version vue, zones, créer, rendre, la forme d’onde, la prise posée', { skip: !AVEC_FFMPEG }, async () => {
  const racine = fs.mkdtempSync(path.join(os.tmpdir(), 'studio-pj-'));
  const jarvis = path.join(racine, 'jarvis'), ch = path.join(jarvis, 'chansons'), pid = 'PJ-20261113-010203-ab12';
  const d = path.join(ch, 'studio', 'projets', pid, 'pistes');
  fs.mkdirSync(d, { recursive: true });
  execFileSync(FFMPEG, ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=330:d=2', '-af', "volume='if(lt(t,1),1,0)':eval=frame", '-ar', '44100', path.join(d, 'vocals.flac')]);
  fs.copyFileSync(path.join(d, 'vocals.flac'), path.join(ch, '20261113-000000-moujahid.mp3'));
  let projet = { id: pid, titre: 'Moujahid', rev: 4, pistes: [{ id: 't1', nom: 'Voix de Hakim', role: 'voix_hakim', fichier: 'pistes/vocals.flac', regions: [] }],
    zones: [], rendus: [{ nom: 'r', t: 1, avis: ['ok'], mesures: { master: { lufs: -14, crete_dbtp: -1.2 }, mp3: { crete_dbtp: -1.1 } },
      pro: [{ id: 't1', piste: 'Voix de Hakim', resume: 'souffle débruité (fond -52 dBFS)', fond: { avant_dbfs: -52, apres_dbfs: -70 }, rapport: { gros: 1 } }],
      master_reglages: { cible: 'streaming', multibande: [-20, -24, -30] },
      fichiers: { complet: { mp3: path.join(ch, 'studio', 'projets', pid, 'rendus', 'r.mp3'), wav: '/etc/passwd',
        wav16: path.join(ch, 'studio', 'projets', pid, 'rendus', 'r-16bits.wav') } } }] };
  const cmds = [];
  const studio = S.creer({ jarvis, lireCorps, appeler: () => ({ ok: true }), projet: (q) => {
    cmds.push(q);
    if (q.action === 'lire') return { ok: true, projet };
    if (q.action === 'regler' || q.action === 'zones') {
      if (q.rev !== projet.rev) return { ok: false, erreur: 'le projet a changé entre-temps' };
      projet = { ...projet, rev: projet.rev + 1 }; return { ok: true, projet };
    }
    if (q.action === 'importer') return { ok: true, projet: { ...projet, pistes: [...projet.pistes, { id: 't2', nom: 'Voix de papa', role: 'voix_papa', fichier: q.fichier }] } };
    return { ok: true, travail: { id: 'J-9' } };
  } });
  const srv = await serveurDe(studio);
  try {
    let r = await appel(srv, 'GET', `/api/studio/projet?id=${pid}`);
    assert.equal(r.statut, 200);
    assert.equal(r.j.projet.pistes[0].f, `studio/projets/${pid}/pistes/vocals.flac`, 'chaque piste porte son chemin servi');
    assert.equal(r.j.projet.rendus[0].fichiers.complet.mp3, `studio/projets/${pid}/rendus/r.mp3`);
    assert.equal(r.j.projet.rendus[0].fichiers.complet.wav, null, 'rien hors des chansons');
    // (13/11, le studio pro) ce que la chaîne a fait de chaque voix, le WAV 16 bits, les réglages du master
    assert.deepEqual(r.j.projet.rendus[0].pro, [{ id: 't1', piste: 'Voix de Hakim', resume: 'souffle débruité (fond -52 dBFS)', fond: { avant_dbfs: -52, apres_dbfs: -70 } }]);
    assert.equal(r.j.projet.rendus[0].fichiers.complet.wav16, `studio/projets/${pid}/rendus/r-16bits.wav`);
    assert.equal(r.j.projet.rendus[0].master_reglages.cible, 'streaming');
    assert.equal((await appel(srv, 'GET', '/api/studio/projet?id=../../x')).statut, 404);
    // le son d'une piste (FLAC) est servi ; la forme d'onde : un pic toutes les 20 ms, le son puis le silence
    assert.equal((await appel(srv, 'GET', `/api/studio/son?f=${encodeURIComponent(r.j.projet.pistes[0].f)}`)).statut, 200);
    r = await appel(srv, 'GET', `/api/studio/forme?f=${encodeURIComponent(`studio/projets/${pid}/pistes/vocals.flac`)}`);
    assert.equal(r.statut, 200); assert.equal(r.j.pas_s, 0.02); assert.ok(Math.abs(r.j.pics.length - 100) <= 1, r.j.pics.length);
    assert.ok(r.j.pics[25] >= 10 && r.j.pics[75] === 0, `${r.j.pics[25]} ${r.j.pics[75]}`);
    const cache = fs.readdirSync(path.join(ch, 'studio', '.formes'));
    assert.equal(cache.length, 1, 'gardée en cache');
    assert.equal((await appel(srv, 'GET', '/api/studio/forme?f=../../etc/passwd')).statut, 404);
    // régler avec la version vue ; une version d'avant : 409 (la page recharge)
    r = await appel(srv, 'POST', '/api/studio/projet/regler', { id: pid, rev: 4, piste: 't1', reglages: { volume_db: -3 } });
    assert.equal(r.statut, 200); assert.equal(r.j.projet.rev, 5);
    assert.deepEqual(cmds.at(-1), { action: 'regler', id: pid, rev: 4, piste: 't1', reglages: { volume_db: -3 }, par: 'papa' });
    assert.equal((await appel(srv, 'POST', '/api/studio/projet/regler', { id: pid, rev: 4, piste: 't1', reglages: { volume_db: -1 } })).statut, 409);
    assert.equal((await appel(srv, 'POST', '/api/studio/projet/regler', { id: pid, rev: 5, piste: 't1', reglages: 'x' })).statut, 400);
    r = await appel(srv, 'POST', '/api/studio/projet/zones', { id: pid, rev: 5, zones: [{ nom: 'Couplet de papa<b>', debut_s: 10, fin_s: 34, qui: 'papa' }] });
    assert.equal(r.statut, 200); assert.equal(cmds.at(-1).zones[0].nom, 'Couplet de papa b', 'les mots nettoyés');
    // (13/11) le studio pro d'une voix passe tel quel (Python le borne) ; le master : cible, 3 bandes, graves en mono, dither
    await appel(srv, 'POST', '/api/studio/projet/regler', { id: pid, rev: 6, piste: 't1', reglages: { pro: { souffle: 'non', type: 'double' }, comp_rapide: { actif: true } } });
    assert.deepEqual(cmds.at(-1).reglages, { pro: { souffle: 'non', type: 'double' }, comp_rapide: { actif: true } });
    await appel(srv, 'POST', '/api/studio/projet/reglages', { id: pid, rev: 6, cible: 'club', multibande: false, mono_graves_hz: 0, dither16: true, largeur: 'auto' });
    assert.deepEqual(cmds.at(-1), { action: 'projet', id: pid, rev: 6, cible: 'club', multibande: false, dither16: true, largeur: 'auto', mono_graves_hz: 0 });
    await appel(srv, 'POST', '/api/studio/projet/reglages', { id: pid, rev: 6, cible: 'stade', multibande: 'oui', largeur: null });
    assert.deepEqual(cmds.at(-1), { action: 'projet', id: pid, rev: 6 }, 'une cible inconnue, un booléen en texte : rien ne passe');
    // créer depuis un son des chansons (jamais hors d'elles) ; rendre
    r = await appel(srv, 'POST', '/api/studio/projet/creer', { f: '20261113-000000-moujahid.mp3', separer: '6', garder: ['batterie', 'basse'], voix: 'hakim', tempo: 140 });
    assert.equal(r.statut, 200);
    assert.deepEqual(cmds.at(-1).params, { source: path.join(ch, '20261113-000000-moujahid.mp3'), titre: '20261113-000000-moujahid', separer: '6', garder: ['batterie', 'basse'], role_voix: 'voix_hakim', tempo: 140 });
    await appel(srv, 'POST', '/api/studio/projet/creer', { f: '20261113-000000-moujahid.mp3', tempo: 9999 });
    assert.equal(cmds.at(-1).params.tempo, undefined, 'un tempo absurde n’est pas transmis');
    assert.equal((await appel(srv, 'POST', '/api/studio/projet/creer', { f: '/etc/hosts' })).statut, 404);
    r = await appel(srv, 'POST', '/api/studio/projet/rendre', { id: pid, pistes_separees: true });
    assert.equal(r.statut, 200);
    assert.deepEqual(cmds.at(-1), { action: 'rendre', par: 'papa', params: { projet: pid, mix_auto: true, envoyer: true, pistes_separees: true, quoi: 'tout' } });
    // une prise de papa posée dans le projet : gardée comme une prise, puis une piste à l'instant où la lecture est partie
    r = await appel(srv, 'POST', `/api/studio/projet-prise?id=${pid}&debut=12.5&latence=140&titre=${encodeURIComponent('Mon couplet')}`, fs.readFileSync(path.join(d, 'vocals.flac')), 'audio/wav');
    assert.equal(r.statut, 200);
    const imp = cmds.at(-1);
    assert.deepEqual([imp.action, imp.debut_s, imp.latence_ms, imp.role, imp.nom], ['importer', 12.5, 140, 'voix_papa', 'Mon couplet']);
    assert.ok(imp.fichier.startsWith(path.join(ch, 'studio', 'prises', 'P-')) && fs.existsSync(imp.fichier));
    const fiche = JSON.parse(fs.readFileSync(imp.fichier.replace(/\.wav$/, '.json'), 'utf8'));
    assert.deepEqual([fiche.projet, fiche.debut_s, fiche.latence_ms], [pid, 12.5, 140]);
    assert.equal(r.j.projet.pistes.at(-1).role, 'voix_papa');
    assert.equal((await appel(srv, 'POST', '/api/studio/projet-prise?id=x', Buffer.alloc(5000), 'audio/wav')).statut, 404);
  } finally { srv.close(); studio.arreter(); fs.rmSync(racine, { recursive: true, force: true }); }
});

test('ses outils du studio multipiste sont permis à Hakim', () => {
  const SRV = lire('server.js');
  for (const n of ['studio_projet', 'studio_piste', 'studio_zones', 'studio_poser_voix', 'studio_rendre'])
    assert.match(SRV, new RegExp(`'${n}'[,\\]]`), n);
});

test('la page Studio, le multipiste : ses parties, la machinerie partagée du micro, tout texte du disque échappé', () => {
  const h = lire('public/studio.html'), js = lire('public/studio-pistes.js'), page = lire('public/studio-page.js');
  for (const id of ['mpProjet', 'mpNouveau', 'mpCreer', 'mpSource', 'mpSeparer', 'mpVoix', 'mpCreerOk', 'mpVue', 'mpLire', 'mpRec', 'mpVersion', 'mpScroll', 'mpGrille',
    'mpDetail', 'mpZones', 'mpZoneAjout', 'mpZonesOk', 'mpMixAuto', 'mpPistesSep', 'mpRendre', 'mpRendus', 'mpNiveau', 'mpCible', 'mpMultibande', 'mpMonoGraves', 'mpDither'])
    assert.match(h, new RegExp(`id="${id}"`), id);
  assert.match(h, /<script src="\/studio-page\.js"><\/script>\n  <script src="\/studio-pistes\.js"><\/script>/, 'après la page : elle prend sa machinerie');
  // le même micro, la même horloge, le même calage que la prise ordinaire
  assert.match(page, /window\.StudioAudio = \{ contexte, tamponDe, ouvrirMicro, capter, enWav, clic, lireRoute, route: \(\) => route, latence, calageActuel,/);
  for (const f of ['ouvrirMicro()', 'capter(c, m, T0', 'enWav(prise.x, prise.sr)', 'latence()', 'calageActuel()']) assert.ok(js.includes(f), f);
  assert.match(js, /\/api\/studio\/projet-prise\?/);
  // la prise part à l'instant de la lecture, papa entend SA version (ses zones en instru), et chaque réglage porte la version vue
  assert.match(js, /await jouer\(depuis, 'papa', T0\);/);
  assert.match(js, /\{ id: s\.projet\.id, rev: s\.projet\.rev, piste, reglages \}/);
  const html = js.split('\n').filter(l => !/textContent =/.test(l)).join('\n');                       // textContent : jamais du HTML
  const nus = (html.match(/\$\{(?!esc\()[^{}]*\.(titre|texte|nom|f|id|couleur|role|erreur|mp3)\}/g) || []).filter(x => !/\.id === /.test(x));
  assert.deepEqual(nus, [], 'tout texte venu du disque est échappé dans le rendu');
  assert.ok(!/innerHTML = [^;]*\$\{a\}/.test(js));
});

test('(13/11) le studio pro dans la page : par voix, le nettoyage étape par étape, les respirations, le type, le calage ; le master', () => {
  const js = lire('public/studio-pistes.js'), h = lire('public/studio.html');
  for (const k of ['souffle', 'ronflement', 'clics', 'ecretage', 'plosives', 'respirations', 'porte', 'nivellement', 'continu'])
    assert.ok(js.includes(`['${k}', `), k);
  for (const c of ["'pro.actif'", "'pro.type'", "'pro.respirations_db'", "'pro.calage'", "'pro.delai_jete'", "'comp_rapide.actif'", "'eq.coupe_haut_hz'", "'saturation'"])
    assert.ok(js.includes(c), c);
  assert.match(js, /\['auto', 'auto \(mesuré\)'\], \['oui', 'oui, forcé'\], \['non', 'non, coupé'\]/, 'trois modes par étape');
  assert.match(js, /\(VOIX\.has\(t\.role\) \? proDetail\(t, champ\) : ''\)/, 'seulement pour les voix');
  // les réglages imbriqués se fusionnent (un mode changé ne vide pas les autres) ; ce que le dernier rendu a dit, échappé
  assert.match(js, /t\[k\] = v && typeof v === 'object' && !Array\.isArray\(v\) && t\[k\] && typeof t\[k\] === 'object' \? \{ \.\.\.t\[k\], \.\.\.v \} : v;/);
  assert.match(js, /Dernier rendu : \$\{esc\(rp\.resume\)\}/);
  assert.match(js, /poster\('\/api\/studio\/projet\/reglages', \{ id: s\.projet\.id, rev: s\.projet\.rev, cible: \$\('mpCible'\)\.value/);
  assert.match(h, /<option value="club">Club, plus fort \(−9 LUFS\)<\/option>/);
});

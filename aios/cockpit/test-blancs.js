/* (10/11, Ahmed : « faut enlever tous ses blancs inutiles automatiques, ça rallonge grave la réponse ») node --test test-blancs.js
   Mesuré le 10/11 de 05:44 à 06:35 (mesure/blancs-voix.py, voix-dite + voix-diagnostic) :
   - 0,89 s de silence restaient à la fin de chaque bout de sa voix de rap : le rendu laisse un petit clic dans ses 80 dernières ms, qui
     arrêtait le rognage de la page (un seul échantillon au-dessus de 0,008) ; Azure rend 1,82 s pour un « Oui papa. » ;
   - ses conversions au timbre de rap passaient dans l'ordre d'arrivée : 34 sur 121 n'ont jamais sonné (112 s de calcul, ses pensées
     préparées d'avance) et passaient devant sa vraie réponse, jusqu'à 14 s d'attente ;
   - les morceaux d'une épissure attendaient le DERNIER calculé (Promise.all) : jusqu'à 18 s de silence pour 7 morceaux ;
   - sa voix du Mac coûte 2,6 s par appel (plus 0,2 s par seconde de voix) : une proposition par virgule se calcule plus lentement
     qu'elle ne se dit. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Voix = require('./public/voix.js');
const V = require('./voix-hakim.js');

const SR = 24000;
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const SRV = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const fonction = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 3); };

// un son : des [durée s, amplitude] à la suite (une sinusoïde à 220 Hz ; amplitude 0 : silence)
function son(parts, sr = SR) {
  const l = [];
  for (const [s, amp] of parts) for (let i = 0; i < Math.round(s * sr); i++) l.push(amp * Math.sin(2 * Math.PI * 220 * i / sr));
  return Float32Array.from(l);
}
function wav(f, sr = SR, extra = null) {
  const pcm = Buffer.alloc(f.length * 2);
  f.forEach((x, i) => pcm.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(x * 32767))), 2 * i));
  const w = V.ecrireWav(pcm, sr);
  if (!extra) return w;
  // un morceau « LIST » avant les données, comme certains en-têtes RIFF d'Azure
  const list = Buffer.concat([Buffer.from('LIST'), Buffer.from([4, 0, 0, 0]), Buffer.from('INFO')]);
  return Buffer.concat([w.subarray(0, 36), list, w.subarray(36)]);
}

test('sa voix commence et finit à l’énergie : le silence de tête et de queue part, et le petit clic de fin du rendu ne le retient plus', () => {
  const d = son([[0.3, 0], [1.0, 0.3], [0.86, 0], [0.04, 0.03]]);   // le clic : 40 ms à -30 dB, tout au bout, après 0,86 s de silence
  const b = Voix.bornesParole(d, SR);
  assert.ok(b, 'quelque chose à rogner');
  assert.ok(Math.abs(b.a / SR - 0.28) < 0.011, `20 ms gardées devant (début ${(b.a / SR).toFixed(3)} s)`);
  assert.ok(Math.abs(b.b / SR - 1.38) < 0.011, `80 ms gardées derrière, sans le clic (fin ${(b.b / SR).toFixed(3)} s)`);
  // avant le 10/11 : un seul échantillon au-dessus de 0,008 arrêtait le rognage ; le clic retenait 0,9 s de silence
  let fin = d.length - 1; while (fin > 0 && Math.abs(d[fin]) < 0.008) fin--;
  assert.ok(d.length - fin < 0.01 * SR, 'l’ancien rognage s’arrêtait au clic');
});

test('jamais un mot mangé : un dernier mot doux après une pause reste, comme une fin collée à la voix ; rien de net : intact', () => {
  const mot = son([[0.2, 0], [1.0, 0.3], [0.25, 0], [0.15, 0.01], [0.5, 0]]);   // un « oui » doux (-30 dB) 0,25 s après la phrase
  const b = Voix.bornesParole(mot, SR);
  assert.ok(b.b / SR >= 1.6 + 0.079, `le mot doux est gardé, avec sa marge (fin ${(b.b / SR).toFixed(3)} s)`);
  // le clic d'un rendu dont le silence d'Azure a été rogné avant la conversion (0,25 s gardées) : plus proche de sa voix, mais faible
  const proche = son([[0.2, 0], [1.0, 0.3], [0.17, 0], [0.04, 0.008]]);
  assert.ok(Math.abs(Voix.bornesParole(proche, SR).b / SR - 1.28) < 0.011, 'un clic faible à 170 ms de sa voix part aussi');
  const fortProche = son([[0.2, 0], [1.0, 0.3], [0.12, 0], [0.06, 0.2]]);   // un vrai petit mot à 120 ms, fort : gardé
  assert.strictEqual(Voix.bornesParole(fortProche, SR).b, fortProche.length);
  const colle = son([[0.2, 0], [1.0, 0.3], [0.05, 0], [0.05, 0.02]]);   // un « t » final collé, dans les 100 dernières ms, sans 200 ms de silence avant
  assert.strictEqual(Voix.bornesParole(colle, SR).b, colle.length, 'une fin collée à sa voix n’est pas un clic');
  assert.strictEqual(Voix.bornesParole(son([[1, 0]]), SR), null, 'tout silence : rien');
  assert.strictEqual(Voix.bornesParole(son([[1, 0.3]]), SR), null, 'rien à rogner : rien');
  assert.strictEqual(Voix.bornesParole(new Float32Array(20), SR), null, 'trop court : rien');
});

test('un WAV de sa voix (16 bits mono) rogné : en-tête neuf, durée juste ; un en-tête Azure (LIST) lu ; tout autre format rendu tel quel', () => {
  const brut = wav(son([[0.15, 0], [0.6, 0.3], [1.0, 0], [0.04, 0.03]]), SR, true);
  assert.ok(Math.abs(V.dureeWav(brut) - 1.79) < 0.002, 'l’en-tête avec son morceau LIST est lu');
  const r = V.rognerWav(brut);
  assert.strictEqual(r.toString('ascii', 0, 4), 'RIFF');
  assert.strictEqual(r.readUInt32LE(40), r.length - 44, 'taille des données juste');
  assert.ok(Math.abs(V.dureeWav(r) - (0.6 + 0.02 + 0.08)) < 0.012, `0,6 s de voix et ses marges (${V.dureeWav(r).toFixed(3)} s)`);
  // marges larges (avant la conversion) : 0,1 s devant, 0,15 s derrière
  assert.ok(Math.abs(V.dureeWav(V.rognerWav(brut, { tete: 0.1, queue: 0.15 })) - 0.85) < 0.012);
  const stereo = Buffer.from(brut); stereo.writeUInt16LE(2, 22);
  assert.strictEqual(V.rognerWav(stereo), stereo, 'stéréo : tel quel');
  const rien = Buffer.from('pas un wav du tout, juste du texte, pour voir');
  assert.strictEqual(V.rognerWav(rien), rien, 'pas un WAV : tel quel');
  const net = wav(son([[0.5, 0.3]]));
  assert.strictEqual(V.rognerWav(net), net, 'rien à rogner : le même tampon');
});

test('ses conversions : sa vraie réponse d’abord, puis ce qui est préparé d’avance, puis ses débuts ; une à la fois ; ce que plus personne n’attend n’est pas calculé', async () => {
  const f = V.creerFilePrioritaire();
  const ordre = []; let enCours = 0, max = 0, lacheA = false;
  const travail = (nom, ms = 5) => () => new Promise((r) => { enCours++; max = Math.max(max, enCours); ordre.push(nom); setTimeout(() => { enCours--; r(nom); }, ms); });
  const p = [f.ajouter(travail('en cours', 20), { prio: 1 }), f.ajouter(travail('pensée préparée'), { prio: 1 }), f.ajouter(travail('début gardé'), { prio: 2 }),
    f.ajouter(travail('lâchée'), { prio: 0, abandonne: () => lacheA }), f.ajouter(travail('sa réponse'), { prio: 0 }), f.ajouter(travail('pensée 2'), { prio: 1 })];
  lacheA = true;
  const r = await Promise.all(p);
  assert.deepStrictEqual(ordre, ['en cours', 'sa réponse', 'pensée préparée', 'pensée 2', 'début gardé']);
  assert.strictEqual(r[3], null, 'la requête lâchée rend null, sans calcul');
  assert.strictEqual(max, 1, 'une seule à la fois (le GPU)');
  assert.strictEqual(await f.ajouter(() => { throw new Error('panne'); }), null, 'une panne rend null');
  assert.strictEqual(f.longueur, 0);
});

test('le cockpit : le silence d’Azure n’est pas converti, le rendu est rogné, la file a ses priorités, toute voix servie est rognée', () => {
  const c = fonction(SRV, 'convertirAuTimbreRap');
  assert.match(c, /data = VoixHakim\.rognerWav\(data, \{ tete: 0\.1, queue: 0\.25 \}\);/, 'avant la conversion : marges larges');
  assert.match(c, /VoixHakim\.rognerWav\(fs\.readFileSync\(fichier\), \{ tete: 0\.02, queue: 0\.08 \}\)/, 'après : le rendu sans son clic');
  assert.match(c, /azure_s: .*rendu_s: /, 'noté au journal : avant et après');
  assert.match(SRV, /const fileAzureRap = VoixHakim\.creerFilePrioritaire\(\);/);
  assert.doesNotMatch(SRV, /let fileAzureRap = Promise\.resolve\(\)/, 'plus de file dans l’ordre d’arrivée');
  const d = fonction(SRV, 'routeDire');
  assert.match(d, /azureAuTimbreRap\(a\.data, 30000, \{ prio: q && q\.fond === true \? 1 : 0, abandonne: \(\) => lachee \}\)/);
  assert.match(d, /res\.on\('close', \(\) => \{ if \(!res\.writableFinished\) lachee = true; \}\);/);
  assert.match(d, /const g = VoixHakim\.rognerWav\(garde\.data\);/, 'ses débuts gardés avant le 10/11 : rognés aussi');
  assert.match(d, /const dr = VoixHakim\.rognerWav\(data\);/, 'sa voix de Chatterbox');
  assert.match(d, /const vd = VoixHakim\.rognerWav\(v\.data\);/, 'la voix de sa pensée');
  assert.equal((d.match(/rognerWav\(a\.data\)/g) || []).length, 2, 'Azure en secours ou seul');
  assert.match(fonction(SRV, 'fabriquerDebutsAzureRap'), /azureAuTimbreRap\(a\.data, 30000, \{ prio: 2 \}\)/, 'ses débuts : après tout ce qu’il dit');
});

test('la page rogne à l’énergie, la même règle que le cockpit (Voix.bornesParole)', () => {
  const r = fonction(PAGE, 'rognerSilences');
  assert.match(r, /Voix\.bornesParole\(buf\.getChannelData\(0\), buf\.sampleRate\)/);
  assert.doesNotMatch(r, /seuil = 0\.008/);
});

test('sa voix du Mac (coût par appel) : ses propositions dites d’un seul tenant jusqu’à une fin de phrase ; la voix du téléphone, une par une', () => {
  const i = PAGE.indexOf('const REGROUPER_MIN'), j = PAGE.indexOf('function surRibosome(');
  const cx = { reglagesCorps: {}, voixDuTelephone: () => false };
  vm.createContext(cx); vm.runInContext(PAGE.slice(i, j) + 'this.r = regrouperPourVoix; this.f = voixACoutFixe;', cx);
  const props = ['Oui papa,', "je t'entends bien,", 'et je suis content.', 'Tu veux que je continue ?', 'Dis-moi.'];
  assert.deepStrictEqual([...cx.r(props)], ["Oui papa, je t'entends bien, et je suis content. Tu veux que je continue ?", 'Dis-moi.'],
    '60 caractères au moins avant de fermer, sur une fin de phrase (48 ne suffisent pas)');
  assert.deepStrictEqual([...cx.r(['Bonne question papa, franchement je ne sais pas encore.', 'Je regarde.'])],
    ['Bonne question papa, franchement je ne sais pas encore. Je regarde.'], 'une phrase courte suit la précédente');
  const longues = Array.from({ length: 6 }, (_, k) => `une proposition assez longue numéro ${k} pour voir,`);
  for (const x of cx.r(longues)) assert.ok(x.length <= 200, `200 au plus (${x.length})`);
  assert.strictEqual(cx.r(longues).join(' '), longues.join(' '), 'aucun mot perdu ni déplacé');
  assert.deepStrictEqual([...cx.r(props, false)], props, 'sans coût par appel : une par une');
  assert.strictEqual(cx.f(), true);
  cx.voixDuTelephone = () => true; assert.strictEqual(cx.f(), false, 'la voix du téléphone');
  cx.voixDuTelephone = () => false; cx.reglagesCorps = { regrouper_bouts: false }; assert.strictEqual(cx.f(), false, 'éteint par papa');
  assert.match(PAGE, /const props = typeof regrouperPourVoix === 'function' \? regrouperPourVoix\(props0\) : props0;/);
  assert.match(SRV, /regrouper_bouts: r\.regrouper_bouts !== false,/);
});

// le lecteur neuronal (creerLecteurNeuronal) sur une horloge virtuelle, comme test-lecteur.js
function simulateur() {
  let maintenant = 0, suivant = 1;
  const minuteries = new Map(), sons = [], demandes = [];
  const planifier = (fn, ms, repete) => { const id = suivant++; minuteries.set(id, { t: maintenant + Math.max(0, ms) / 1000, fn, repete }); return id; };
  const actx = {
    state: 'running', get currentTime() { return maintenant; },
    createGain: () => ({ gain: { value: 1 }, connect() {} }),
    createBufferSource() {
      const s = { buffer: null, playbackRate: { value: 1 }, connect() {}, onended: null,
        start(t, off) { const debut = Math.max(t, maintenant); s.rec = { debut, fin: debut + s.buffer.duration - (Number(off) || 0), texte: s.buffer.texte }; sons.push(s.rec);
          planifier(() => { if (!s.arretee) s.onended && s.onended(); }, (s.rec.fin - maintenant) * 1000); },
        stop() { s.arretee = true; } };
      return s;
    },
  };
  const cx = {
    console, Math, JSON, Promise, Set, Map, Error, Blob, URL, AbortController, Voix,
    setTimeout: (fn, ms) => planifier(fn, ms), setInterval: (fn, ms) => planifier(fn, ms, ms), clearInterval: (id) => minuteries.delete(id), clearTimeout: (id) => minuteries.delete(id),
    performance: { now: () => maintenant * 1000 }, localStorage: { getItem: () => null, setItem() {} },
    etat: { conversation: {}, reglages: { vitesse: 1 }, interieur: null }, debutsPrets: new Set(), cleDebut: (x) => x,
    actx, analyseurVoix: {}, lecteurSysteme: null, jeton: () => 'x', humeur() {}, jarvisPeutParler: () => true, forceDeLaVoix: () => 1, journalVoix() {},
    vitesseVoix: () => 1, tempoVoix: () => 1,
    fetch: (url, o) => { demandes.push(JSON.parse(o.body).texte); return new Promise(() => {}); },
  };
  cx.window = cx;
  vm.createContext(cx);
  vm.runInContext(fonction(PAGE, 'creerLecteurNeuronal') + '\nthis.lecteur = creerLecteurNeuronal();', cx);
  const prete = (texte, duree, quand, rate = false) => new Promise((ok, ko) => planifier(() => (rate ? ko(new Error('voix')) : ok({ duration: duree, texte })), quand * 1000));
  async function avancer(jusqua) {
    for (;;) {
      await new Promise(r => setImmediate(r));
      let p = null;
      for (const [id, m] of minuteries) if (!p || m.t < p[1].t) p = [id, m];
      if (!p || p[1].t > jusqua) { maintenant = Math.max(maintenant, jusqua); return; }
      maintenant = p[1].t;
      if (p[1].repete) p[1].t = maintenant + p[1].repete / 1000; else minuteries.delete(p[0]);
      p[1].fn();
    }
  }
  return { lecteur: cx.lecteur, sons, demandes, avancer, prete };
}

test('les morceaux d’un bout partent chacun dès que sa voix est prête, dans l’ordre, sans attendre le dernier ; une voix absente est passée, jamais recalculée', async () => {
  const sim = simulateur();
  sim.lecteur.direAudio('Un,', sim.prete('Un,', 1.0, 1.0));            // prêt à 1 s
  sim.lecteur.direAudio('deux,', sim.prete('deux,', 1.0, 6.0));         // prêt à 6 s (avant le 10/11 : le premier attendait jusque-là)
  sim.lecteur.direAudio('trois,', sim.prete('trois,', 1.0, 3.0, true)); // sa voix n'est pas venue
  sim.lecteur.direAudio('quatre.', sim.prete('quatre.', 1.0, 4.0));
  await sim.avancer(20);
  assert.deepStrictEqual(sim.sons.map(s => s.texte), ['Un,', 'deux,', 'quatre.'], 'dans l’ordre ; « trois » passé');
  assert.ok(sim.sons[0].debut < 1.1, `le premier part dès sa voix prête (${sim.sons[0].debut.toFixed(2)} s)`);
  assert.ok(sim.sons[1].debut >= 6 && sim.sons[1].debut < 6.4, `le deuxième à sa voix prête (${sim.sons[1].debut.toFixed(2)} s)`);
  assert.ok(Math.abs(sim.sons[2].debut - (sim.sons[1].fin + 0.1)) < 0.02, 'le suivant déjà prêt : la respiration de 0,1 s seulement');
  assert.deepStrictEqual(sim.demandes, [], 'aucune voix recalculée');
});

test('l’épissure : son bout part au premier morceau prêt (plus de Promise.all), les autres suivent dans sa voix', () => {
  const r = fonction(PAGE, 'recevoirBout');
  assert.doesNotMatch(r, /Promise\.all\(textes\.map/);
  assert.match(r, /b\.morceaux = textes\.map\(\(t, k\) => \(\{ texte: t, buf: k \? voix\[k\] : buf, marque: b\.marques \? b\.marques\[k\] \|\| null : null \}\)\);/);   // (10/11) et sa pensée
  assert.match(PAGE, /if \(buf && typeof buf\.then === 'function'\) \{/, 'direAudio accepte une voix en route');
  assert.match(fonction(PAGE, 'garderVoixPrete'), /b\.morceaux\.length > 1/, 'gardés chacun sous son texte');
});

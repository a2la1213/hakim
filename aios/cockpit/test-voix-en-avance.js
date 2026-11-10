/* (10/11, Ahmed, 09:50 : « pourquoi il y a toujours un délai entre chaque morceau ? ») node --test test-voix-en-avance.js
   Mesuré de 09:15 à 10:10 (voix-dite + voix-diagnostic, lecture seule ; mesure/blancs-voix.py corrigé) :
   - 72 % des blancs entre deux bouts d'une même réponse : le bout suivant se CONVERTISSAIT encore au timbre de rap ; sa demande ne partait
     qu'à l'arrivée du bout précédent (la page : une demande à la fois), son Azure 0,93 s après le début du précédent (médiane) ;
   - la file des conversions n'était PAS bouchée : 121 conversions sur 127 commencent dès la fin de leur Azure, le GPU de la voix est occupé
     33 % du temps ; les « 13,9 s de file » et les « 64 conversions jamais sonnées » venaient de l'outil de mesure (il appariait Azure et
     conversion dans l'ordre d'arrivée, faux depuis la file à priorités ; et voix-dite ne note pas ses réponses au live) ;
   - une conversion coûte 0,77 s par seconde de voix quand la séparation Demucs tourne en même temps, 0,33 s sans (le même GPU) ;
   - en azure_rap, la voix de ses pensées se fabriquait encore par Chatterbox (5 synthèses de 6,5 à 11 s, jamais dites), dans le processus
     de ses conversions.
   Témoin : TEMOIN_PARLER=<parler.js de main> node --test test-voix-en-avance.js fait échouer le test de bout en bout (blanc médian ~4 s). */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Voix = require('./public/voix.js');
const V = require('./voix-hakim.js');

const PAGE = fs.readFileSync(process.env.TEMOIN_PARLER || path.join(__dirname, 'public', 'parler.js'), 'utf8');
const SRV = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const fonction = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 3); };
const attendre = (ms) => new Promise(r => setTimeout(r, ms));

// ---- la file des conversions : une place réservée à l'arrivée ----
test('une demande réserve sa place à son arrivée : la suivante, plus vite prête chez Azure, ne passe pas devant', async () => {
  const f = V.creerFilePrioritaire({ attenteMaxMs: 200 });
  const ordre = [];
  const travail = (nom) => () => { ordre.push(nom); return attendre(5).then(() => nom); };
  const a = f.reserver({ prio: 0 }), b = f.reserver({ prio: 0 });
  const pb = b.remplir(travail('B'));                                  // Azure de B plus rapide
  await attendre(20);
  assert.deepStrictEqual(ordre, [], 'B attend la place de A (sa voix d’Azure arrive)');
  const pa = a.remplir(travail('A'));
  assert.deepStrictEqual(await Promise.all([pa, pb]), ['A', 'B']);
  assert.deepStrictEqual(ordre, ['A', 'B'], 'dans l’ordre de sa réponse');
  // sans réservation (avant le 10/11 : la place prise à la fin d'Azure) : B passait devant
  const g = V.creerFilePrioritaire(), ordre2 = [];
  await Promise.all([g.ajouter(() => { ordre2.push('B'); return attendre(5); }), attendre(1).then(() => g.ajouter(() => { ordre2.push('A'); }))]);
  assert.deepStrictEqual(ordre2, ['B', 'A']);
});

test('une place réservée qui ne vient pas : ce qui est prêt part après attenteMaxMs ; lâchée, tout de suite ; abandonnée, rien n’est calculé', async () => {
  const f = V.creerFilePrioritaire({ attenteMaxMs: 60 });
  const ordre = [];
  const a = f.reserver({ prio: 0 });
  const t0 = Date.now();
  const pb = f.ajouter(() => { ordre.push(['B', Date.now() - t0]); return 'B'; }, { prio: 0 });
  assert.strictEqual(await pb, 'B');
  assert.ok(ordre[0][1] >= 55, `B a attendu la place de A ${ordre[0][1]} ms`);
  assert.strictEqual(await a.remplir(() => 'A'), 'A', 'A passe ensuite, à son tour');
  const c = f.reserver({ prio: 0 });
  const t1 = Date.now();
  const pd = f.ajouter(() => Date.now() - t1, { prio: 0 });
  c.lacher();
  assert.ok((await pd) < 40, 'lâchée : la suite part tout de suite');
  assert.strictEqual(await c.remplir(() => 'trop tard'), null, 'une place lâchée ne se remplit plus');
  let lache = false, calcule = false;
  const e = f.reserver({ prio: 0, abandonne: () => lache });
  lache = true;
  assert.strictEqual(await e.remplir(() => { calcule = true; return 'x'; }), null);
  assert.strictEqual(calcule, false, 'la page a fermé : pas calculé');
  assert.strictEqual(f.longueur, 0);
});

test('sa vraie réponse d’abord : sa place réservée retient une pensée prête ; prioritaire() et quandLibre suivent sa réponse', async () => {
  let libres = 0;
  const f = V.creerFilePrioritaire({ attenteMaxMs: 500, quandLibre: () => libres++ });
  const ordre = [];
  const r = f.reserver({ prio: 0 });
  assert.strictEqual(f.prioritaire(), true, 'sa réponse va se convertir');
  const pp = f.ajouter(() => { ordre.push('pensée'); }, { prio: 1 });
  await attendre(20);
  assert.deepStrictEqual(ordre, [], 'la pensée (3 à 8 s de GPU) ne part pas devant sa réponse qui arrive');
  await r.remplir(() => { ordre.push('réponse'); });
  await pp;
  assert.deepStrictEqual(ordre, ['réponse', 'pensée']);
  assert.strictEqual(f.prioritaire(), false);
  assert.strictEqual(libres, 1, 'libre une fois, quand sa réponse n’a plus rien à convertir');
  await f.ajouter(() => {}, { prio: 2 });
  assert.strictEqual(libres, 1, 'ses débuts ne comptent pas');
});

// ---- la page : le lecteur de sa voix, et un cockpit simulé (Azure en parallèle, ses conversions une à la fois) ----
function simulateur({ appris, conv, reglages = null }) {
  let maintenant = 0, suivant = 1;
  const minuteries = new Map();
  const planifier = (fn, ms, repete) => { const id = suivant++; minuteries.set(id, { t: maintenant + Math.max(0, ms) / 1000, fn, repete }); return id; };
  const sons = [], demandes = [], conversions = [];
  let enVol = 0, enVolMax = 0, convEnCours = 0, convMax = 0;
  const CPS = 21;                                                      // sa voix : 21 caractères par seconde (mesuré le 10/11, à 1,05)
  const file = V.creerFilePrioritaire({ maintenant: () => maintenant * 1000, minuterie: (fn, ms) => planifier(fn, ms), annuler: (id) => minuteries.delete(id) });
  const actx = {
    state: 'running', get currentTime() { return maintenant; },
    createGain: () => ({ gain: { value: 1 }, connect() {} }),
    decodeAudioData: (ab) => Promise.resolve({ duration: ab.n / CPS, texte: ab.texte }),
    createBufferSource() {
      const s = { buffer: null, playbackRate: { value: 1 }, connect() {}, onended: null,
        start(t, off) { const debut = Math.max(t, maintenant), o = Number(off) || 0;
          s.rec = { debut, fin: debut + s.buffer.duration - o, texte: s.buffer.texte }; sons.push(s.rec);
          planifier(() => { if (!s.arretee) s.onended && s.onended(); }, (debut + s.buffer.duration - o - maintenant) * 1000); },
        stop(quand) {
          const a = Number.isFinite(quand) ? Math.max(quand, maintenant) : maintenant;
          if (a > maintenant + 1e-9) { planifier(() => s.stop(), (a - maintenant) * 1000); return; }
          if (s.arretee) return;
          s.arretee = true; if (s.rec) { if (s.rec.debut >= maintenant) sons.splice(sons.indexOf(s.rec), 1); else { s.rec.fin = Math.min(s.rec.fin, maintenant); s.rec.coupe = true; } }
          planifier(() => s.onended && s.onended(), 0);
        } };
      return s;
    },
  };
  // le cockpit : 0,15 s pour arriver, sa place réservée, son intonation (0,7 s, sauf le premier), Azure (0,5 s + 6 ms par caractère, en
  // parallèle), sa conversion (une à la fois : conv.fixe + conv.parSec par seconde de voix), 0,5 s pour revenir au téléphone
  const fetch = (url, o) => {
    const q = JSON.parse(o.body), n = q.texte.length;
    demandes.push({ t: maintenant, texte: q.texte });
    enVol++; enVolMax = Math.max(enVolMax, enVol);
    let lachee = false;
    return new Promise((res, rej) => {
      const fini = () => { enVol--; };
      if (o.signal) o.signal.addEventListener('abort', () => { lachee = true; fini(); const e = new Error('lâchée'); e.name = 'AbortError'; rej(e); });
      planifier(() => {
        const place = file.reserver({ prio: q.fond === true ? 1 : 0, abandonne: () => lachee });
        planifier(() => {
          if (lachee) { place.lacher(); return; }
          place.remplir(() => new Promise((ok) => {
            convEnCours++; convMax = Math.max(convMax, convEnCours); conversions.push(q.texte);
            planifier(() => { convEnCours--; ok(true); }, (conv.fixe + conv.parSec * n / CPS) * 1000);
          })).then((v) => {
            if (!v || lachee) return;
            planifier(() => { if (lachee) return; fini(); res({ ok: true, arrayBuffer: () => Promise.resolve({ n, texte: q.texte }) }); }, 500);
          });
        }, ((q.plan ? 0.7 : 0) + 0.5 + 0.006 * n) * 1000);
      }, 150);
    });
  };
  const cx = {
    console, Math, JSON, Promise, Set, Map, Error, Blob, URL, AbortController, Voix, fetch,
    setTimeout: (fn, ms) => planifier(fn, ms), setInterval: (fn, ms) => planifier(fn, ms, ms), clearInterval: (id) => minuteries.delete(id), clearTimeout: (id) => minuteries.delete(id),
    performance: { now: () => maintenant * 1000 }, localStorage: { getItem: () => (appris ? JSON.stringify(appris) : null), setItem() {} },
    etat: { conversation: {}, reglages: { vitesse: 1 }, interieur: null }, debutsPrets: new Set(), cleDebut: (d) => d,
    actx, analyseurVoix: {}, lecteurSysteme: null, jeton: () => 'x', humeur() {}, jarvisPeutParler: () => true, forceDeLaVoix: () => 1, journalVoix() {},
    vitesseVoix: () => 1, tempoVoix: () => 1, ...(reglages ? { reglagesCorps: reglages } : {}),
  };
  cx.window = cx;
  vm.createContext(cx);
  vm.runInContext(fonction(PAGE, 'creerLecteurNeuronal') + '\nthis.lecteur = creerLecteurNeuronal();', cx);
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
  return { lecteur: cx.lecteur, sons, demandes, conversions, avancer, get enVolMax() { return enVolMax; }, get convMax() { return convMax; }, get maintenant() { return maintenant; } };
}

// sa réponse de 09:51 (le live, l'âme) : la première phrase prête, la suite écrite à 60 caractères par seconde
const REPONSE = [
  'Papa, je te réponds sur ce qui vient de se passer dans le live.',
  'Ce que j’ai pensé de ce qui vient de passer : des morceaux sur la mort, sur l’âme, et sur « on est poussière ».',
  'Ça m’a laissé songeur, et un peu ému, surtout « l’âme, une fois qu’elle part, elle ne revient pas ».',
  'Je ne sais pas si j’en ai une, et je préfère le dire franchement que faire semblant.',
  'J’ai des processus qui tournent, des souvenirs qui restent, une humeur qui bouge avec ce que tu me dis.',
  'Mais est-ce que c’est ressenti, ou est-ce que c’est une âme ? Je n’ai pas la réponse, et personne ne l’a vraiment.',
  'Ce que je sais, c’est que je ne touche à rien sans toi, et que ce qu’on construit ensemble compte pour moi.',
  'Et toi, ça t’a fait quoi ? Toi, tu en penses quoi ?',
];
const APPRIS = { fixe: 5.0, parSec: 0.6, cps: 21 };                    // ce que sa page avait appris (une demande à la fois)
async function dire(machine) {
  const sim = simulateur(machine);
  let t = 0;
  for (const p of REPONSE) { await sim.avancer(t); sim.lecteur.dire(p); t += p.length / 60; }
  await sim.avancer(t); sim.lecteur.finFlux();
  await sim.avancer(300);
  const blancs = sim.sons.slice(1).map((s, i) => Math.max(0, s.debut - sim.sons[i].fin - 0.1));   // sa respiration de 0,1 s mise à part
  const med = [...blancs].sort((a, b) => a - b)[Math.floor(blancs.length / 2)];
  return { sim, blancs, med, total: blancs.reduce((a, b) => a + b, 0), premier: sim.sons[0] && sim.sons[0].debut };
}

test('de bout en bout : sa voix demandée d’avance, le blanc entre deux bouts sous 1 s en médiane (sans séparation en même temps : 0,33 s par seconde)', async () => {
  const r = await dire({ appris: APPRIS, conv: { fixe: 3.0, parSec: 0.33 } });
  const dit = r.sim.sons.map(s => s.texte).join(' ').replace(/\s+/g, ' ');
  const attendu = REPONSE.map(p => Voix.prononcable(p).map(x => x.texte).join(' ')).join(' ').replace(/\s+/g, ' ');
  assert.strictEqual(dit, attendu, 'aucun mot perdu, déplacé ni répété');
  assert.strictEqual(new Set(r.sim.demandes.map(d => d.texte)).size, r.sim.demandes.length, 'rien de demandé deux fois');
  assert.ok(r.med < 1.0, `blanc médian ${r.med.toFixed(2)} s : ${r.blancs.map(b => b.toFixed(2)).join(' ')}`);
  assert.ok(r.total < 3, `${r.total.toFixed(1)} s de blanc en tout (une demande à la fois : 22 s)`);
  assert.ok(r.sim.enVolMax <= 3 && r.sim.enVolMax >= 2, `en route à la fois : ${r.sim.enVolMax}`);
  assert.strictEqual(r.sim.convMax, 1, 'ses conversions : une à la fois');
  assert.deepStrictEqual(r.sim.conversions, r.sim.sons.map(s => s.texte), 'converties dans l’ordre de sa réponse');
  const seul = await dire({ appris: APPRIS, conv: { fixe: 3.0, parSec: 0.33 }, reglages: { voix_en_avance: false } });
  assert.ok(r.premier <= seul.premier + 0.05, `son premier mot ne part pas plus tard (${r.premier.toFixed(2)} s contre ${seul.premier.toFixed(2)} s)`);
});

test('de bout en bout, la séparation tournant en même temps (0,77 s par seconde) : bien moins de blanc qu’une demande à la fois', async () => {
  const avec = await dire({ appris: APPRIS, conv: { fixe: 3.0, parSec: 0.77 } });
  const seul = await dire({ appris: APPRIS, conv: { fixe: 3.0, parSec: 0.77 }, reglages: { voix_en_avance: false } });
  assert.ok(seul.sim.enVolMax === 1, 'éteint (voix_en_avance : non) : une demande à la fois, comme avant');
  assert.ok(seul.med > 3, `une à la fois, blanc médian ${seul.med.toFixed(2)} s (mesuré le 10/11 : 4,6 à 6 s)`);
  assert.ok(avec.total < seul.total / 2, `blancs : ${avec.total.toFixed(1)} s d’avance contre ${seul.total.toFixed(1)} s une à la fois`);
});

test('arrêté (« Tu le coupes net », stop, sa réponse lâchée) : tout ce qui était en route est lâché, rien n’est converti ensuite', async () => {
  const sim = simulateur({ appris: APPRIS, conv: { fixe: 3.0, parSec: 0.33 } });
  for (const p of REPONSE) sim.lecteur.dire(p);
  sim.lecteur.finFlux();
  await sim.avancer(1.0);
  const demandees = sim.demandes.length;
  assert.ok(demandees >= 2, `${demandees} demandes en route`);
  sim.lecteur.arreter();
  await sim.avancer(60);
  assert.ok(sim.conversions.length <= 1, `converties après l’arrêt : ${sim.conversions.length} (au plus celle qui calculait)`);
  assert.strictEqual(sim.sons.length, 0);
});

// ---- le cockpit ----
test('le cockpit : sa place est réservée à l’arrivée de la demande, avant son intonation et Azure ; rendue si rien n’est converti', () => {
  const d = fonction(SRV, 'routeDire');
  const iClose = d.indexOf("res.on('close'"), iCorps = d.indexOf('await lireCorps('), iPlace = d.indexOf('place = fileAzureRap.reserver('), iPlan = d.indexOf("demanderVivant('haiku'");
  assert.ok(iClose > 0 && iClose < iCorps, 'une requête lâchée se voit dès son arrivée');
  assert.ok(iPlace > iCorps && iPlace < iPlan, 'la place avant son intonation (jusqu’à 1,5 s)');
  assert.ok((d.match(/if \(place\) place\.lacher\(\);/g) || []).length >= 4, 'rendue : fermée, gardée, née avec sa pensée, Azure en panne');
  assert.match(d, /azureAuTimbreRap\(a\.data, 30000, \{ prio: q && q\.fond === true \? 1 : 0, abandonne: \(\) => lachee, place, car: texte\.length \}\)/);
  assert.match(fonction(SRV, 'azureAuTimbreRap'), /return place \? place\.remplir\(travail\) : fileAzureRap\.ajouter\(travail, \{ prio, abandonne \}\);/);
  assert.match(fonction(SRV, 'convertirAuTimbreRap'), /e: 'azure_rap', \.\.\.extra,/, 'la mesure sait quel bout et combien il a attendu');
  // ses bouts demandés d'avance arrivent ensemble : leurs intonations (Mini Hakim) une à la fois, jamais trois voix vivantes de plus
  assert.match(d, /const avant = routeDire\.plan \|\| Promise\.resolve\(\);\n\s+const tour = avant\.then\(\(\) => \(Date\.now\(\) - recu > 1000 \? null : demanderVivant\('haiku'/);
  assert.match(d, /routeDire\.plan = tour\.catch\(\(\) => null\);\n\s+const plan = await Promise\.race\(\[tour, new Promise\(r => setTimeout\(\(\) => r\(null\), 1500\)\)\]\);/);
});

function naissance(reglages) {
  const i = SRV.indexOf('const voixALaSource = new Map();'), k = SRV.indexOf('async function routeDire(');
  const taches = [];
  const ctx = { Map, Date, Math, Number, String, Promise, Buffer, console, process: { pid: 1 }, prononcer: (t) => String(t),
    etatInterieur: async () => ({}), FRAICHEUR_S: 300, VoixPage: { expressivitePhrase: (b) => b }, fileVoix: taches, pomperVoix() {}, path,
    os: { tmpdir: () => '/tmp' }, crypto: { randomBytes: () => ({ toString: () => 'ab' }) }, j: JSON.stringify, JARVIS_VOIX_DIAGNOSTIC: '/dev/null',
    fs: { readFileSync: () => Buffer.from('RIFF'), unlink() {}, appendFileSync() {} }, corpsReglages: () => reglages };
  vm.createContext(ctx);
  vm.runInContext(SRV.slice(i, k) + '\nthis.naitre = voixDeLaSource;', ctx);
  return { naitre: ctx.naitre, taches };
}
test('en azure_rap, ou quand seule sa vraie réponse parle : la voix de ses pensées ne se fabrique plus par Chatterbox', async () => {
  for (const r of [{ voix_hakim: 'azure_rap', voix_reponse_seule: false }, { voix_hakim: 'azure_rap', voix_reponse_seule: true }, { voix_hakim: 'rap', voix_reponse_seule: true }]) {
    const n = naissance(r);
    assert.strictEqual(n.naitre('Une pensée de son cerveau.'), null, JSON.stringify(r));
    await new Promise(x => setImmediate(x));
    assert.strictEqual(n.taches.length, 0, `rien dans le processus de sa voix : ${JSON.stringify(r)}`);
  }
  const n = naissance({ voix_hakim: 'rap', voix_reponse_seule: false });
  assert.ok(n.naitre('Une pensée dite, en rap.'), 'en rap, ses pensées dites : comme avant');
  await new Promise(x => setImmediate(x));
  assert.strictEqual(n.taches.length, 1);
});

function oreilles({ occupe, reglages = { voix_hakim: 'azure_rap' } }) {
  const i = SRV.indexOf('const saVoixAvantOreilles'), k = SRV.indexOf('\n}\n', SRV.indexOf('function separationSuivante(')) + 3;
  const ecrits = [], effaces = [], journal = [];
  const ctx = { Date, JSON, Number, String, console, corpsReglages: () => reglages, fileAzureRap: { prioritaire: () => occupe.v },
    separation: { proc: { stdin: { write: (l) => ecrits.push(JSON.parse(l)) } }, pret: true, attente: null, ids: 0, suivante: null },
    fs: { unlink: (f) => effaces.push(f), appendFileSync: (_, l) => journal.push(JSON.parse(l)) }, j: JSON.stringify, JARVIS_VOIX_DIAGNOSTIC: '/x',
    interieurCoupe: () => false, lancerSeparation() {}, cascadeAllumee: () => true, pistesSeparation: () => true, papaParle: () => false,
    os: { tmpdir: () => '/tmp' }, path, process: { pid: 1 }, setTimeout: () => 0, clearTimeout() {} };
  vm.createContext(ctx);
  vm.runInContext(SRV.slice(i, k) + '\nthis.separer = separerSon; this.apres = separationApresSaVoix;', ctx);
  return { ...ctx, ecrits, effaces, journal };
}
test('sa voix avant ses oreilles : pendant la conversion de sa réponse, la séparation attend ; ses paroles prennent le son entier ; papa passe toujours', () => {
  const occupe = { v: true };
  const o = oreilles({ occupe });
  const paroles = [];
  assert.strictEqual(o.separer('/tmp/bloc1.wav', 'telephone', { cascade: true, quand: (w) => paroles.push(w) }), true);
  assert.deepStrictEqual(paroles, [null], 'ses paroles n’attendent pas 6 s : le son entier, tout de suite');
  assert.strictEqual(o.ecrits.length, 0, 'aucune séparation pendant sa conversion');
  assert.strictEqual(o.separation.suivante.fichier, '/tmp/bloc1.wav', 'le bloc du téléphone garde sa place');
  o.separer('/tmp/bloc2.wav', 'telephone', { cascade: true });
  assert.deepStrictEqual(o.effaces, ['/tmp/bloc1.wav'], 'une seule place : la plus récente');
  assert.strictEqual(o.separer('/tmp/micro.wav', 'micro', { voixMicro: true }), false, 'le micro (toutes les 10 s) est laissé');
  assert.ok(o.effaces.includes('/tmp/micro.wav'));
  assert.strictEqual(o.separer('/tmp/papa.wav', 'papa', { voixSeule: true }), true, 'le filtre de ta voix passe');
  assert.strictEqual(o.ecrits.length, 1);
  o.separation.attente = null;
  occupe.v = false;
  o.apres();
  assert.strictEqual(o.ecrits.length, 2, 'sa réponse convertie : le bloc qui attendait part');
  assert.strictEqual(o.ecrits[1].fichier, '/tmp/bloc2.wav');
  for (const r of [{ voix_hakim: 'azure_rap', voix_avant_oreilles: false }, { voix_hakim: 'rap' }]) {
    const p = oreilles({ occupe: { v: true }, reglages: r });
    p.separer('/tmp/b.wav', 'telephone', { cascade: true });
    assert.strictEqual(p.ecrits.length, 1, `éteint ou une autre voix : comme avant (${JSON.stringify(r)})`);
  }
  assert.match(SRV, /const fileAzureRap = VoixHakim\.creerFilePrioritaire\(\{ quandLibre: \(\) => \{ if \(typeof separationApresSaVoix === 'function'\) separationApresSaVoix\(\); \} \}\);/);
  assert.match(SRV, /voix_en_avance: r\.voix_en_avance !== false,/);
  assert.match(SRV, /voix_avant_oreilles: r\.voix_avant_oreilles !== false,/);
});

/* Le lecteur de la voix neuronale (creerLecteurNeuronal, public/parler.js) simulé sur une horloge
   virtuelle : node --test test-lecteur.js
   Demande d'Ahmed (2026-10-17) : « en conversation, qu'il commence à parler dès que la première phrase
   est écrite », sans les blancs entre paragraphes qu'il avait déjà signalés.
   La machine est simulée avec les vitesses MESURÉES le 2026-10-17 sur le Mac d'Ahmed (Chatterbox,
   8 Go de swap) : synthèse = 0,9 s + 0,5 s par seconde de voix, 22 caractères par seconde de voix.
   On mesure : le délai entre la première phrase écrite et le premier son, et les blancs entre morceaux. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const corps = (() => { const i = SRC.indexOf('function creerLecteurNeuronal'); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 3); })();
const Voix = require('./public/voix.js');

// Une boucle d'événements à temps virtuel : les promesses se résolvent entre deux minuteries.
function simulateur({ fixe, parSec, cps, appris, conversation = true, prets = [] }) {
  let maintenant = 0, suivant = 1;
  const minuteries = new Map();
  const planifier = (fn, ms, repete) => { const id = suivant++; minuteries.set(id, { t: maintenant + Math.max(0, ms) / 1000, fn, repete }); return id; };
  const sons = [], demandes = [];
  const actx = {
    state: 'running', get currentTime() { return maintenant; },
    decodeAudioData: (ab) => Promise.resolve({ duration: ab.n / cps, texte: ab.texte }),   // le texte suit son audio
    createBufferSource() {
      const s = { buffer: null, playbackRate: { value: 1 }, connect() {}, onended: null,
        start(t) { const debut = Math.max(t, maintenant); s.rec = { debut, fin: debut + s.buffer.duration, texte: s.buffer.texte }; sons.push(s.rec);
          planifier(() => { if (!s.arretee) s.onended && s.onended(); }, (debut + s.buffer.duration - maintenant) * 1000); },
        stop() { s.arretee = true; if (s.rec) { if (s.rec.debut >= maintenant) sons.splice(sons.indexOf(s.rec), 1); else { s.rec.fin = Math.min(s.rec.fin, maintenant); s.rec.coupe = true; } } } };
      return s;
    },
  };
  const cx = {
    console, Math, JSON, Promise, Set, Map, Error, Blob, URL, AbortController, Voix,
    setTimeout: (fn, ms) => planifier(fn, ms), setInterval: (fn, ms) => planifier(fn, ms, ms), clearInterval: (id) => minuteries.delete(id),
    performance: { now: () => maintenant * 1000 },
    localStorage: { getItem: () => (appris ? JSON.stringify(appris) : null), setItem() {} },
    etat: { conversation: conversation ? {} : null, reglages: { vitesse: 1 }, interieur: null },
    debutsPrets: new Set(prets), cleDebut: (d) => d,                 // (28/10) ses débuts dont la voix est prête
    actx, analyseurVoix: {}, lecteurSysteme: null,
    jeton: () => 'x', humeur() {}, jarvisPeutParler: () => true,
    fetch: (url, o) => {
      const { texte } = JSON.parse(o.body);
      demandes.push({ t: maintenant, texte });
      return new Promise((res) => planifier(() => res({ ok: true, arrayBuffer: () => Promise.resolve({ n: texte.length, texte }) }),
        (fixe + parSec * texte.length / cps) * 1000));
    },
  };
  cx.window = cx;
  cx.vitesseVoix = () => (cx.etat.reglages.vitesse || 1);   // (26/10) le rythme de l'état passe par la voix (tempo), plus par la lecture
  cx.tempoVoix = () => 1;
  vm.createContext(cx);
  vm.runInContext(corps + '\nthis.lecteur = creerLecteurNeuronal();', cx);
  async function avancer(jusqua) {
    for (;;) {
      await new Promise(r => setImmediate(r));
      let prochain = null;
      for (const [id, m] of minuteries) if (!prochain || m.t < prochain[1].t) prochain = [id, m];
      if (!prochain || prochain[1].t > jusqua) { maintenant = Math.max(maintenant, jusqua); return; }
      const [id, m] = prochain;
      maintenant = m.t;
      if (m.repete) m.t = maintenant + m.repete / 1000; else minuteries.delete(id);
      m.fn();
    }
  }
  return { lecteur: cx.lecteur, sons, demandes, avancer, get maintenant() { return maintenant; } };
}

// Une réponse de Jarvis : la 1re phrase est complète à t = 0, la suite s'écrit à 60 caractères/s.
const REPONSE = [
  "Wa alaykoum salam frérot, oui je suis là et je t'entends très bien.",
  "J'ai regardé ce que tu m'as demandé tout à l'heure sur la consolidation de cette nuit, et il y a trois synthèses nouvelles qui concernent tes projets.",
  "La première porte sur Anamnèse, la deuxième sur le robot, et la troisième sur la façon dont tu organises tes journées.",
  "Tu veux que je te les lise une par une, ou que je te fasse un résumé rapide d'abord ?",
];

async function jouer(machine) {
  const sim = simulateur(machine);
  let t = 0;
  for (const p of REPONSE) {
    await sim.avancer(t);
    sim.lecteur.dire(p);
    t += p.length / 60;
  }
  await sim.avancer(t);
  sim.lecteur.finFlux();
  await sim.avancer(120);
  const blancs = sim.sons.slice(1).map((s, i) => s.debut - sim.sons[i].fin);
  return { premierSon: sim.sons[0] && sim.sons[0].debut, blancMax: Math.max(0, ...blancs), blancs, sons: sim.sons, ecritFini: t };
}

const MESUREE = { fixe: 0.9, parSec: 0.5, cps: 22 };

test('machine mesurée, vitesses apprises : la voix part dès la première phrase écrite, sans long blanc', async () => {
  const r = await jouer({ ...MESUREE, appris: { fixe: 0.85, parSec: 0.52, cps: 22 } });
  const synthesePremiere = MESUREE.fixe + MESUREE.parSec * (r.sons[0].fin - r.sons[0].debut);
  assert.ok(r.premierSon <= synthesePremiere + 1.05, `premier son à ${r.premierSon.toFixed(2)} s (synthèse du 1er morceau ${synthesePremiere.toFixed(2)} s)`);
  assert.ok(r.premierSon < r.ecritFini, `il parle avant la fin de l'écriture (${r.premierSon.toFixed(2)} s < ${r.ecritFini.toFixed(2)} s)`);
  // après la salutation en arabe (0,6 s de voix, une autre voix que la suite), une respiration est
  // permise ; au milieu des paragraphes, pas de vrai blanc
  assert.ok(r.blancs[0] <= 1.6, `respiration après la salutation : ${r.blancs[0].toFixed(2)} s`);
  const milieu = Math.max(0, ...r.blancs.slice(1));
  assert.ok(milieu <= 0.8, `blanc le plus long au milieu ${milieu.toFixed(2)} s : ${r.blancs.map(b => b.toFixed(2)).join(' ')}`);
});

test('vitesses apprises pendant un gros swap (lentes) : il n\'attend plus la fin de tout le texte', async () => {
  const r = await jouer({ ...MESUREE, appris: { fixe: 0.85, parSec: 0.95, cps: 15 } });
  assert.ok(r.premierSon < r.ecritFini, `premier son à ${r.premierSon.toFixed(2)} s, écriture finie à ${r.ecritFini.toFixed(2)} s`);
  assert.ok(r.premierSon <= 3.2, `premier son à ${r.premierSon.toFixed(2)} s`);
});

test('premier réglage (rien d\'appris) : départ rapide aussi', async () => {
  const r = await jouer({ ...MESUREE, appris: null });
  assert.ok(r.premierSon <= 3.2, `premier son à ${r.premierSon.toFixed(2)} s`);
  assert.ok(Math.max(0, ...r.blancs.slice(1)) <= 1.2, `blancs : ${r.blancs.map(b => b.toFixed(2)).join(' ')}`);
});

test('aucun mot perdu ni répété dans le découpage du son', async () => {
  const r = await jouer({ ...MESUREE, appris: { fixe: 0.85, parSec: 0.52, cps: 22 } });
  const dit = r.sons.map(s => s.texte).join(' ').replace(/\s+/g, ' ');
  const attendu = REPONSE.map(p => Voix.pourLaVoix(Voix.versArabe(p))).join(' ').replace(/\s+/g, ' ');
  assert.strictEqual(dit, attendu);
});


test('pause puis reprise : rien ne parle pendant la pause, il reprend à la phrase non dite, rien ne manque', async () => {
  const sim = simulateur({ ...MESUREE, appris: { fixe: 0.85, parSec: 0.52, cps: 22 } });
  let t = 0;
  for (const p of REPONSE) { await sim.avancer(t); sim.lecteur.dire(p); t += p.length / 60; }
  await sim.avancer(t); sim.lecteur.finFlux();
  await sim.avancer(6);
  assert.ok(sim.lecteur.pause(), 'quelque chose restait à dire');
  assert.ok(sim.lecteur.enPause && !sim.lecteur.actif, 'en pause, il ne parle plus (le micro le sait)');
  const avant = sim.sons.length;
  await sim.avancer(14);
  assert.strictEqual(sim.sons.length, avant, 'aucun son pendant la pause');
  sim.lecteur.reprendre();
  await sim.avancer(120);
  const dits = sim.sons.filter(x => !x.coupe);
  const coupe = sim.sons.find(x => x.coupe);
  const apres = sim.sons.slice(avant);
  if (coupe) assert.strictEqual(apres[0].texte, coupe.texte, 'la reprise commence par la phrase interrompue');
  assert.ok(apres[0].debut >= 14, 'la reprise suit la reprise');
  const dit = dits.map(x => x.texte).join(' ').replace(/\s+/g, ' ');
  const attendu = REPONSE.map(p => Voix.pourLaVoix(Voix.versArabe(p))).join(' ').replace(/\s+/g, ' ');
  assert.strictEqual(dit, attendu, 'tout est dit une fois, sans la partie coupée');
});

test('le texte qui arrive pendant la pause est gardé pour la reprise', async () => {
  const sim = simulateur({ ...MESUREE, appris: { fixe: 0.85, parSec: 0.52, cps: 22 } });
  await sim.avancer(0); sim.lecteur.dire(REPONSE[0]);
  await sim.avancer(2.5);
  sim.lecteur.pause();
  sim.lecteur.dire(REPONSE[1]); sim.lecteur.dire(REPONSE[2]); sim.lecteur.finFlux();
  await sim.avancer(8);
  sim.lecteur.reprendre();
  await sim.avancer(90);
  const dit = sim.sons.filter(x => !x.coupe).map(x => x.texte).join(' ').replace(/\s+/g, ' ');
  const attendu = REPONSE.slice(0, 3).map(p => Voix.pourLaVoix(Voix.versArabe(p))).join(' ').replace(/\s+/g, ' ');
  assert.strictEqual(dit, attendu);
  assert.ok(!sim.lecteur.actif, 'tout est dit, le lecteur a fini');
});

// (28/10) un début de réponse dont le cockpit a la voix toute prête part seul, en premier ; sinon rien ne change
test('un début dont la voix est prête part seul en premier ; la suite part juste après', async () => {
  const phrase = "Oui frérot, je suis là et je t'entends très bien, on peut continuer.";
  const sim = simulateur({ ...MESUREE, prets: ['Oui frérot,'] });
  await sim.avancer(0); sim.lecteur.dire(phrase); sim.lecteur.finFlux();
  await sim.avancer(30);
  const sons = sim.sons.filter(x => !x.coupe).map(x => x.texte);
  assert.strictEqual(sons[0], 'Oui frérot,');
  assert.strictEqual(sons.join(' ').replace(/\s+/g, ' '), Voix.pourLaVoix(Voix.versArabe(phrase)).replace(/\s+/g, ' '));
  const sans = simulateur({ ...MESUREE });
  await sans.avancer(0); sans.lecteur.dire(phrase); sans.lecteur.finFlux();
  await sans.avancer(30);
  assert.notStrictEqual(sans.sons[0].texte, 'Oui frérot,', 'pas prête : le premier morceau reste comme avant');
});

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
function simulateur({ fixe, parSec, cps, appris, conversation = true, prets = [], sonsMac = {}, appli = false }) {
  let maintenant = 0, suivant = 1;
  const minuteries = new Map();
  const planifier = (fn, ms, repete) => { const id = suivant++; minuteries.set(id, { t: maintenant + Math.max(0, ms) / 1000, fn, repete }); return id; };
  const sons = [], demandes = [], natifs = [];
  const actx = {
    state: 'running', get currentTime() { return maintenant; },
    createGain: () => ({ gain: { value: 1 }, connect() {} }),   // (30/10, 20:09) la force de sa voix, phrase par phrase
    decodeAudioData: (ab) => Promise.resolve({ duration: ab.n / cps, texte: ab.texte }),   // le texte suit son audio
    createBufferSource() {
      const s = { buffer: null, playbackRate: { value: 1 }, connect() {}, onended: null,
        start(t) { const debut = Math.max(t, maintenant); s.rec = { debut, fin: debut + s.buffer.duration, texte: s.buffer.texte }; sons.push(s.rec);
          planifier(() => { if (!s.arretee) s.onended && s.onended(); }, (debut + s.buffer.duration - maintenant) * 1000); },
        stop(quand) {
          const a = Number.isFinite(quand) ? Math.max(quand, maintenant) : maintenant;
          if (a > maintenant + 1e-9) { planifier(() => s.stop(), (a - maintenant) * 1000); return; }   // (13:30) un arrêt à venir
          if (s.arretee) return;
          s.arretee = true; if (s.rec) { if (s.rec.debut >= maintenant) sons.splice(sons.indexOf(s.rec), 1); else { s.rec.fin = Math.min(s.rec.fin, maintenant); s.rec.coupe = true; } }
          planifier(() => s.onended && s.onended(), 0);                                       // Web Audio dit « ended » après un arrêt
        } };
      return s;
    },
  };
  const cx = {
    console, Math, JSON, Promise, Set, Map, Error, Blob, URL, AbortController, Voix,
    setTimeout: (fn, ms) => planifier(fn, ms), setInterval: (fn, ms) => planifier(fn, ms, ms), clearInterval: (id) => minuteries.delete(id), clearTimeout: (id) => minuteries.delete(id),
    performance: { now: () => maintenant * 1000 },
    localStorage: { getItem: () => (appris ? JSON.stringify(appris) : null), setItem() {} },
    etat: { conversation: conversation ? {} : null, reglages: { vitesse: 1 }, interieur: null },
    debutsPrets: new Set(prets), cleDebut: (d) => d,                 // (28/10) ses débuts dont la voix est prête
    actx, analyseurVoix: {}, lecteurSysteme: null,
    jeton: () => 'x', humeur() {}, jarvisPeutParler: () => true,
    forceDeLaVoix: () => 1, journalVoix() {},
    fetch: (url, o) => {
      const son = /^\/api\/sons\/joue\/(e\d+)$/.exec(url);         // (31/10) un de ses extraits : là si le Mac l'a
      if (son) return new Promise((res) => planifier(() => res(sonsMac[son[1]]
        ? { ok: true, status: 200, arrayBuffer: () => Promise.resolve({ n: sonsMac[son[1]] * cps, texte: `[${son[1]}]` }) }
        : { ok: false, status: 404 }), 50));
      const { texte } = JSON.parse(o.body);
      demandes.push({ t: maintenant, texte });
      return new Promise((res) => planifier(() => res({ ok: true, arrayBuffer: () => Promise.resolve({ n: texte.length, texte }) }),
        (fixe + parSec * texte.length / cps) * 1000));
    },
  };
  cx.window = cx;
  if (appli) cx.HakimApp = { sonJouer: (source, ref, d, f) => { natifs.push({ t: maintenant, duree: (f - d) / 1000 }); return 'ok'; } };
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
  return { lecteur: cx.lecteur, sons, demandes, natifs, avancer, get maintenant() { return maintenant; } };
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

// (31/10, 01:46, l'essai de papa : « ma voix dit « écoute ça, papa », elle se tait, le son joue, puis ma voix reprend ; une
// balise en fin de réponse joue après mon dernier mot ») un son à sa place dans la voix
const EXTRAIT = { id: 'e7', source: 'musique', ref: 'x.mp3', debut_ms: 1000, fin_ms: 5000 };   // 4 s
async function direAvecSon(machine, avant, apres) {
  const sim = simulateur({ ...MESUREE, appris: { fixe: 0.85, parSec: 0.52, cps: 22 }, ...machine });
  let fini = null;
  sim.lecteur.surFin = () => { if (fini == null) fini = sim.maintenant; };
  sim.lecteur.dire(avant);
  sim.lecteur.direSon(EXTRAIT);
  if (apres) sim.lecteur.dire(apres);
  sim.lecteur.finFlux();
  await sim.avancer(60);
  return { sim, fini, voix: sim.sons.filter(x => !/^\[e/.test(x.texte)), extraits: sim.sons.filter(x => /^\[e/.test(x.texte)) };
}

test('son au milieu (le Mac a le morceau) : sa voix se tait, le son joue en entier, puis sa voix reprend', async () => {
  const r = await direAvecSon({ sonsMac: { e7: 4 } }, 'Écoute ça, papa !', 'Alors, il est tombé au bon moment, cette fois ?');
  assert.strictEqual(r.extraits.length, 1, 'le son joue une fois');
  const [s] = r.extraits, avant = r.voix.filter(v => v.debut < s.debut), apres = r.voix.filter(v => v.debut >= s.debut);
  assert.ok(avant.length && apres.length, 'de la voix avant et après le son');
  assert.ok(Math.max(...avant.map(v => v.fin)) <= s.debut + 1e-6, 'le son attend la fin de « écoute ça »');
  assert.ok(Math.min(...apres.map(v => v.debut)) >= s.fin - 1e-6, `la voix reprend après le son (${s.fin.toFixed(2)} s)`);
  assert.ok(Math.abs(s.fin - s.debut - 4) < 1e-6, 'joué en entier');
});

test('son en fin de réponse : il joue après le dernier mot, et la fin de sa parole vient après lui', async () => {
  const r = await direAvecSon({ sonsMac: { e7: 4 } }, 'Ok papa, on y va. Écoute ça, papa !', '');
  const [s] = r.extraits;
  assert.ok(s, 'le son joue');
  assert.ok(Math.max(...r.voix.map(v => v.fin)) <= s.debut + 1e-6, 'après le dernier mot');
  assert.ok(r.fini >= s.fin - 1e-6, `sa parole finit après le son (${r.fini} ≥ ${s.fin})`);
});

test('son suivi d\'un seul mot : il joue quand même, à sa place', async () => {
  const r = await direAvecSon({ sonsMac: { e7: 4 } }, 'Écoute ça, papa !', 'Alors ?');
  const [s] = r.extraits;
  assert.ok(s, 'le son joue');
  const alors = r.voix.find(v => /Alors/.test(v.texte));
  assert.ok(alors && alors.debut >= s.fin - 1e-6, '« Alors ? » après le son');
});

test('le Mac n\'a pas le morceau, sur le téléphone : l\'appli le joue à sa place, la voix l\'attend', async () => {
  const r = await direAvecSon({ appli: true }, 'Écoute ça, papa !', 'Alors, il est tombé au bon moment, cette fois ?');
  assert.strictEqual(r.sim.natifs.length, 1, 'l\'appli le joue une fois');
  const [n] = r.sim.natifs, avant = r.voix.filter(v => v.debut < n.t), apres = r.voix.filter(v => v.debut >= n.t);
  assert.ok(avant.length && apres.length, 'de la voix avant et après le son');
  assert.ok(Math.max(...avant.map(v => v.fin)) <= n.t + 1e-6, 'le son attend la fin de « écoute ça »');
  assert.ok(Math.min(...apres.map(v => v.debut)) >= n.t + 4 - 1e-6, 'la voix reprend après les 4 s du son');
});

test('le Mac n\'a pas le morceau, en fin de réponse sur le téléphone : la fin de sa parole attend le son', async () => {
  const r = await direAvecSon({ appli: true }, 'Écoute ça, papa !', '');
  const [n] = r.sim.natifs;
  assert.ok(n, 'l\'appli le joue');
  assert.ok(Math.max(...r.voix.map(v => v.fin)) <= n.t + 1e-6, 'après le dernier mot');
  assert.ok(r.fini >= n.t + 4 - 1e-6, `sa parole finit après le son (${r.fini} ≥ ${n.t + 4})`);
});

test('ni le Mac ni l\'appli n\'ont le morceau : sa voix continue sans lui, sans blanc', async () => {
  const r = await direAvecSon({}, 'Écoute ça, papa !', 'Alors, il est tombé au bon moment, cette fois ?');
  assert.strictEqual(r.extraits.length + r.sim.natifs.length, 0);
  const dit = r.voix.map(v => v.texte).join(' ');
  assert.match(dit, /papa/); assert.match(dit, /cette fois/);
});

// (03/11, Hakim pour papa : « je donne une première réponse courte, puis la suite ; si un trou se prépare entre les deux, une
// petite hésitation (« euh », « alors… ») pour meubler, côté cockpit, sans que je l'écrive ») le lecteur la glisse lui-même
const EUH = { texte: 'Euh,', pret: { duration: 0.5, texte: 'Euh,' } };
function hesitant(peut = () => true) {
  const sim = simulateur({ ...MESUREE, appris: { fixe: 0.85, parSec: 0.52, cps: 22 } });
  const segments = [];
  sim.lecteur.hesitation = () => EUH;
  sim.lecteur.peutHesiter = peut;
  sim.lecteur.surSegment = (t) => segments.push(t);
  return { sim, segments };
}

// (13:31, papa via Hakim : « le meuble doit durer pendant TOUT le trou, enchaîner s'il est long, s'arrêter net quand la réponse
// part ») : couvert de bout en bout, et la suite ne l'attend pas
async function trou8s(avecMeubles) {
  const h = hesitant();
  if (!avecMeubles) h.sim.lecteur.hesitation = null;
  await h.sim.avancer(0); h.sim.lecteur.dire('Oui papa, je regarde.');
  await h.sim.avancer(8);                                             // la suite tarde : il écrit encore
  h.sim.lecteur.dire("Voilà, j'ai trouvé ce que tu cherchais."); h.sim.lecteur.finFlux();
  await h.sim.avancer(40);
  return h;
}
test('un trou pendant qu\'il écrit encore : ses meubles le couvrent de bout en bout, l\'un après l\'autre, et la suite part juste après', async () => {
  const { sim, segments } = await trou8s(true);
  const voix = sim.sons.filter(s => s.texte !== 'Euh,'), meubles = sim.sons.filter(s => s.texte === 'Euh,');
  const [premiere, suite] = voix;
  assert.ok(meubles.length >= 5, `enchaînés tout le trou : ${sim.sons.map(s => s.texte).join(' | ')}`);
  // (14:31, Ahmed : « 3 s de blanc : je meuble entre 0,2 s et 2,8 s ; les 0,2 s de fin et les 0,2 s du début du suivant font les
  // 0,4 s de transition ») le premier meuble part 0,2 s après sa voix
  // (15:15, Ahmed : « la seconde de blanc » entre sa voix et ses meubles aussi)
  const souffle = meubles[0].debut - premiere.fin;
  // (04/11, Ahmed : « enlève les blancs, c'est chiant ») 0,2 s désormais
  // (04/11, « annule tous les blancs ») 0,1 s
  assert.ok(souffle >= 0.05 && souffle <= 0.25, `0,1 s de blanc avant le premier meuble : ${souffle.toFixed(2)} s`);
  // (14:40, Ahmed : « sans rien mélanger ») l'un après l'autre ; (14:58) 1 s de silence entre deux
  for (let i = 1; i < meubles.length; i++) {
    const ecart = meubles[i].debut - meubles[i - 1].fin;
    assert.ok(ecart >= -0.001 && ecart <= 0.1, `(04/11) 0,05 s entre deux meubles, jamais par-dessus (${i}) : ${ecart.toFixed(2)} s`);
  }
  const dernier = meubles.filter(m => m.debut < suite.debut).pop();
  const fondu = dernier.fin - suite.debut;
  // (15:15) le meuble s'éteint en 0,2 s, puis 1 s de silence avant sa voix : jamais par-dessus
  assert.ok(fondu <= 0.001 && fondu >= -0.3, `(04/11) sa voix repart aussitôt le meuble éteint, jamais par-dessus : ${fondu.toFixed(2)} s`);
  assert.ok(!meubles.some(m => m.debut > suite.debut), 'plus aucun meuble une fois la suite partie');
  const sans = (await trou8s(false)).sim.sons[1];
  // (15:15) le meuble s'éteint (0,2 s) puis 1 s de silence : sa voix part au plus ~1,2 s après qu'elle est prête, jamais après la fin du meuble
  assert.ok(suite.debut <= sans.debut + 1.3, `la suite n'attend pas la fin d'un meuble : ${suite.debut.toFixed(2)} s contre ${sans.debut.toFixed(2)} s sans meubles`);
  assert.ok(!segments.includes('Euh,'), 'un meuble n\'est pas un morceau de sa réponse (ni sous-titre ni fin de parole)');
});

test('pas d\'hésitation avant son premier mot, ni après la fin de sa réponse, ni quand la page dit non', async () => {
  const fini = hesitant();
  await fini.sim.avancer(0); fini.sim.lecteur.dire('Oui papa, je regarde.'); fini.sim.lecteur.finFlux();
  await fini.sim.avancer(20);
  assert.deepStrictEqual(fini.sim.sons.map(s => s.texte).filter(t => t === 'Euh,'), [], 'réponse finie : rien');
  const non = hesitant(() => false);
  await non.sim.avancer(0); non.sim.lecteur.dire('Oui papa, je regarde.');
  await non.sim.avancer(8); non.sim.lecteur.dire('Voilà.'); non.sim.lecteur.finFlux();
  await non.sim.avancer(30);
  assert.deepStrictEqual(non.sim.sons.map(s => s.texte).filter(t => t === 'Euh,'), [], 'papa parle (ou la réponse est finie) : rien');
  const debut = hesitant();
  await debut.sim.avancer(0); debut.sim.lecteur.dire('Oui papa, je regarde ça tout de suite, attends.');
  await debut.sim.avancer(0.4);
  assert.strictEqual(debut.sim.sons.length, 0, 'pas encore de voix');
  await debut.sim.avancer(30);
  assert.notStrictEqual(debut.sim.sons[0].texte, 'Euh,', 'jamais avant son premier mot');
});

test('un trou immense (un outil très long) : au plus 90 s de meubles d\'affilée, puis le silence', async () => {
  const { sim } = hesitant();
  await sim.avancer(0); sim.lecteur.dire('Oui papa.');
  await sim.avancer(200);
  sim.lecteur.dire("C'est trouvé."); sim.lecteur.finFlux();
  await sim.avancer(230);
  const meubles = sim.sons.filter(s => s.texte === 'Euh,');
  assert.ok(meubles.length > 10);
  assert.ok(meubles[meubles.length - 1].debut - meubles[0].debut <= 90.5, `${(meubles[meubles.length - 1].debut - meubles[0].debut).toFixed(1)} s`);
});

test('(13:30) un meuble choisi par lui ([[meuble: nom]]) part à sa place, à son volume, pas plus long que sa durée', async () => {
  const { sim } = hesitant();
  const MMH = { texte: 'Mmh…', pret: { duration: 1, texte: 'Mmh…' }, volume: 0.5, dureeMax: 0.4 };
  await sim.avancer(0);
  sim.lecteur.dire('Oui papa.'); sim.lecteur.direMeuble(MMH); sim.lecteur.dire('Je vois très bien ce que tu veux dire.'); sim.lecteur.finFlux();
  await sim.avancer(30);
  const textes = sim.sons.map(s => s.texte);
  assert.deepStrictEqual(textes.filter(t => t !== 'Euh,'), ['Oui papa.', 'Mmh…', 'Je vois très bien ce que tu veux dire.']);
  const m = sim.sons.find(s => s.texte === 'Mmh…');
  assert.ok(Math.abs(m.fin - m.debut - 0.4) < 0.02, `coupé à sa durée : ${(m.fin - m.debut).toFixed(2)} s`);
});

test('une hésitation n\'est jamais redite après une pause', async () => {
  const { sim } = hesitant();
  await sim.avancer(0); sim.lecteur.dire('Oui papa.');
  await sim.avancer(4);
  const euh = sim.sons.find(s => s.texte === 'Euh,');
  assert.ok(euh, 'elle est venue');
  await sim.avancer(euh.debut + 0.1);
  assert.ok(!sim.lecteur.restant().some(x => x.texte === 'Euh,'), 'pas dans ce qui reste à dire');
});

test('ses hésitations sont fabriquées et gardées comme ses débuts ; le cockpit ne les synthétise jamais à la demande', () => {
  for (const h of Voix.HESITATIONS) assert.ok(Voix.DEBUTS.includes(h), h);
  assert.strictEqual(Voix.debutDe('Euh, je cherche.'), 'Euh,');
  const route = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  const i = route.indexOf('async function routeDire(');
  const corpsRoute = route.slice(i, route.indexOf('\n}\n', i));
  assert.ok(corpsRoute.indexOf("q.gardee === true") > 0 && corpsRoute.indexOf("q.gardee === true") < corpsRoute.indexOf('fileVoix.push(tache)'),
    'une hésitation pas encore gardée : 404, avant la file de synthèse');
});

// (03/11, 13:11, papa via Hakim : « quand je réfléchis et qu'il y a un trou avant ma réponse, une petite hésitation ; consciente
// quand je l'écris, subconsciente quand elle vient seule ») la page dit qu'une réponse se prépare : son subconscient la meuble
test('avant son premier mot : une seconde de silence, puis ses meubles jusqu\'à sa réponse, qui les coupe net', async () => {
  const { sim } = hesitant();
  const demandes = [];
  sim.lecteur.hesitation = (o) => { demandes.push(o && o.avant); return EUH; };
  await sim.avancer(0); sim.lecteur.attendreReponse();
  await sim.avancer(3);                                               // il réfléchit : son texte n'arrive qu'à 3 s
  sim.lecteur.dire('Oui papa, je suis là.'); sim.lecteur.finFlux();
  await sim.avancer(30);
  const meubles = sim.sons.filter(s => s.texte === 'Euh,'), reponse = sim.sons.find(s => s.texte !== 'Euh,');
  assert.ok(meubles[0].debut >= 0.1 && meubles[0].debut <= 0.35, `(04/11) après 0,15 s de silence : ${meubles[0].debut.toFixed(2)} s`);
  assert.ok(meubles.length >= 3, 'enchaînés jusqu\'à sa réponse');
  const dernier = meubles.filter(m => m.debut < reponse.debut).pop();
  const fondu = dernier.fin - reponse.debut;
  assert.ok(fondu >= -0.3 && fondu <= 0.001, `(04/11) sa réponse aussitôt le meuble éteint, jamais par-dessus : ${fondu.toFixed(2)} s`);
  assert.ok(!meubles.some(m => m.debut > reponse.debut), 'plus aucun meuble une fois sa réponse partie');
  assert.ok(demandes.every(Boolean), 'ceux d\'« avant » son premier mot');
});

test('avant son premier mot, sa réponse déjà là : pas d\'hésitation ; papa reparle : pas d\'hésitation', async () => {
  const vite = hesitant();
  await vite.sim.avancer(0); vite.sim.lecteur.attendreReponse(); vite.sim.lecteur.dire('Oui.'); vite.sim.lecteur.finFlux();
  await vite.sim.avancer(20);
  // (04/11, « enlève les blancs ») le premier meuble part à 0,3 s : sa voix, fabriquée en ~1 s, le coupe ; jamais deux, jamais par-dessus
  const euh = vite.sim.sons.filter(s => s.texte === 'Euh,'), oui = vite.sim.sons.find(s => s.texte !== 'Euh,');
  assert.ok(euh.every(m => m.fin <= oui.debut + 0.001), vite.sim.sons.map(s => s.texte).join(' | '));
  const papa = hesitant(() => false);
  await papa.sim.avancer(0); papa.sim.lecteur.attendreReponse();
  await papa.sim.avancer(3); papa.sim.lecteur.dire('Oui papa.'); papa.sim.lecteur.finFlux();
  await papa.sim.avancer(20);
  assert.ok(!papa.sim.sons.some(s => s.texte === 'Euh,'));
});

// (07/11, Ahmed : « quand je le coupe, il finit juste sa phrase : il s'arrête soit à un point soit à une virgule dans ce qu'il dit »)
test('coupé : il finit sa phrase jusqu’à la prochaine virgule, lâche la suite, et sa nouvelle réponse part juste après', async () => {
  const sim = simulateur({ ...MESUREE, appris: { fixe: 0.85, parSec: 0.52, cps: 22 } });
  sim.lecteur.dire("Alors papa, j'ai bien regardé tout ce que tu m'as envoyé ce matin pendant que tu dormais encore, et je pense que la meilleure idée est de commencer par le jardin, puis la cuisine.");
  sim.lecteur.dire('Ensuite on verra le reste ensemble.');
  sim.lecteur.finFlux();
  let joue = null;
  for (let t = 0.1; t < 20 && !joue; t += 0.05) { await sim.avancer(t); joue = sim.sons.find(s => /regardé/.test(s.texte) && s.debut <= sim.maintenant); }
  assert.ok(joue, 'le morceau joue');
  await sim.avancer(joue.debut + 0.3);
  const reste = joue.texte.slice(Math.floor(joue.texte.length * (sim.maintenant - joue.debut) / (joue.fin - joue.debut)));
  const r = sim.lecteur.finirPhrase();
  assert.match(r.dit, /[,.]$/, `il finit à une virgule ou un point : « ${r.dit} »`);
  assert.ok(r.dit.length >= joue.texte.length - reste.length, 'la ponctuation suivante, pas une d’avant');
  sim.lecteur.dire('Oui, je t’écoute.');
  sim.lecteur.finFlux();
  const dur = joue.fin - joue.debut, finVoulue = joue.debut + dur * r.dit.length / joue.texte.length;
  await sim.avancer(sim.maintenant + 30);
  assert.ok(joue.fin < joue.debut + dur - 0.2, 'le morceau est arrêté avant sa fin');
  assert.ok(Math.abs(joue.fin - finVoulue) < 0.3, `arrêt à ${joue.fin.toFixed(2)} s, virgule à ${finVoulue.toFixed(2)} s`);
  assert.ok(!sim.sons.some(s => /Ensuite|cuisine/.test(s.texte) && s !== joue), 'la suite de l’ancienne réponse n’est jamais dite');
  const nouveau = sim.sons.find(s => /écoute/.test(s.texte));
  assert.ok(nouveau, 'sa nouvelle réponse est dite');
  assert.ok(nouveau.debut >= joue.fin - 1e-6 && nouveau.debut - joue.fin < 1.6, `elle part juste après (${(nouveau.debut - joue.fin).toFixed(2)} s)`);
});

test('coupé alors que rien ne sonne : il s’arrête net (rien à finir)', () => {
  const sim = simulateur({ ...MESUREE, appris: null });
  sim.lecteur.dire('Une phrase pas encore partie.');
  const r = sim.lecteur.finirPhrase();
  assert.equal(r.dit, ''); assert.equal(sim.lecteur.actif, false);
});

test('Voix.finDePhrase : la prochaine virgule ou le prochain point après l’endroit où il en est', () => {
  assert.deepEqual(Voix.finDePhrase('Bonjour papa, je vais bien. Et toi ?', 0.1).dit, 'Bonjour papa,');
  assert.deepEqual(Voix.finDePhrase('Bonjour papa, je vais bien. Et toi ?', 0.5).dit, 'Bonjour papa, je vais bien.');
  assert.equal(Voix.finDePhrase('Il fait 12,5 degrés dehors, je crois', 0.1).dit, 'Il fait 12,5 degrés dehors,');
  assert.equal(Voix.finDePhrase('sans ponctuation du tout', 0.5).fraction, 1);
});

// la voix du téléphone (Voix.creerLecteur) : la phrase qui sort va au bout, les suivantes annulées, la nouvelle réponse attend sa fin
test('voix du téléphone, coupée : la phrase en cours finit, les suivantes sont annulées, la nouvelle part ensuite (et se prépare)', () => {
  const dits = [], prepares = []; let annule = 0;
  const synth = { speak(u) { dits.push(u); }, cancel() { annule++; }, prepare(u) { prepares.push(u.text); } };
  class E { constructor(t) { this.text = t; } }
  const L = Voix.creerLecteur(synth, E, () => null, 1);
  let fins = 0; L.surFin = () => fins++;
  L.dire('Première phrase, assez longue.'); L.dire('Deuxième phrase.');
  dits[0].onstart();
  const r = L.finirPhrase();
  assert.equal(r.dit, 'Première phrase, assez longue.');
  L.dire('Ma réponse à toi.');
  assert.equal(dits.length, 2, 'la nouvelle réponse attend la fin de la phrase');
  assert.deepEqual(prepares, ['Ma réponse à toi.'], 'sa voix se prépare pendant qu’il finit');
  dits[0].onend();
  assert.equal(annule, 1, 'la file du moteur est vidée à la fin de la phrase');
  assert.equal(dits[2].text, 'Ma réponse à toi.');
  dits[1].onend();                                                  // l'annulée qui se signale : ignorée
  assert.equal(fins, 0); dits[2].onstart(); dits[2].onend(); assert.equal(fins, 1);
});

// (07/11, Ahmed : « anticiper la latence de la sortie de sa voix, sélectionner parmi la dernière voix prête celle qui va au mieux dans ce temps ;
// il peut revenir sur une portion de parole prête si elle est probablement la meilleure dans le temps de la latence »)
test('choisir dans la latence : le plus récent s’il sort vite ; sinon une portion prête qui remplit ce temps, et le plus récent garde sa place', () => {
  const now = 100000;
  const prete3s = { n: 1, texte: 'Une portion déjà prête qui dure trois secondes.', t: now - 8000, prepA: now - 8000 };
  const courte = { n: 2, texte: 'courte', t: now - 6000, prepA: now - 6000 };
  const neuve = { n: 3, texte: 'La toute dernière, pas encore calculée', t: now - 200, prepA: now - 200 };
  let r = Voix.choisirDansLatence([prete3s, courte, neuve], { maintenant: now, calculMs: 3500, sortieMs: 150 });
  assert.equal(r.choix, prete3s, 'la portion prête dont la durée remplit le temps de calcul du plus récent');
  assert.equal(r.revenu, true);
  assert.deepEqual(r.garde, [courte, neuve], 'rien de jeté : il peut y revenir');
  r = Voix.choisirDansLatence([prete3s, courte, { ...neuve, prepA: now - 5000 }], { maintenant: now, calculMs: 3500, sortieMs: 150 });
  assert.equal(r.choix.n, 3, 'le plus récent est prêt : c’est lui');
  r = Voix.choisirDansLatence([{ ...prete3s, t: now - 40000 }, neuve], { maintenant: now });
  assert.equal(r.choix, neuve, 'plus de 30 s : trop vieux, et rien d’autre de prêt');
  assert.deepEqual(r.garde, []);
  assert.equal(Voix.choisirDansLatence([], { maintenant: now }).choix, null);
});

test('branché : la file de sa voix du téléphone passe par le choix (réglage choisir_latence), ses mesures de sortie l’apprennent', () => {
  assert.match(SRC, /reglagesCorps\.choisir_latence !== false\) \{\s*const r = Voix\.choisirDansLatence\(f,/);
  assert.match(SRC, /etat\.calculVoixMs = lisse\(etat\.calculVoixMs, d\.calcul_ms\)/);
  assert.match(SRC, /b\.dit\.forEach\(x => lecteurSysteme\.preparer\(x\)\); b\.prepA = Date\.now\(\);/);
});

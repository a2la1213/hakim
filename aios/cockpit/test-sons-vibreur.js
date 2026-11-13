/* (13/11, ~02:20, Ahmed : « Oui, en vibreur ses sons sortent aussi, mais je dois en avoir une option pour allumer et éteindre ») « SES SONS EN
   VIBREUR » : un interrupteur (réglage sons_vibreur du cockpit, allumé par défaut, lu à chaud). Allumé : le vibreur ne bloque pas ses sons.
   Éteint : le téléphone en vibreur les bloque, comme avant : l'appli 1.98 (la page lui transmet le réglage avec chaque son, sonJouerVibreur)
   et la page elle-même (un morceau déjà sur le Mac sortirait sinon par la page, en Web Audio). Le silencieux et « Ne pas déranger » les
   bloquent toujours (l'appli). Le retour de lecture le dit (« vibreur_reglage » ; à Hakim : « refusé : vibreur (ton réglage) »).
   node --test test-sons-vibreur.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const SRV = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const REGLAGES = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
const SENS = fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8');
const prendre = (s, debut) => { const i = s.indexOf(debut); assert.ok(i >= 0, `introuvable : ${debut}`); return s.slice(i, s.indexOf('\n}\n', i) + 3); };
const LECTEUR = prendre(PAGE, 'function creerLecteurNeuronal');
const AIDES = ['function raisonRefusAppli(', 'function sonnerieIci(', 'function sonsVibreurPermis(', 'function vibreurBloqueIci(', 'function appliJoueSon(',
  'function retourSon('].map(d => prendre(PAGE, d)).join('\n');
const Voix = require('./public/voix.js');
const HautParleurs = require('./public/haut-parleurs.js');

// ce que dit l'appli 1.98 quand le réglage est éteint (hakim-android, SonChamps.REFUS_VIBREUR)
const REFUS_REGLAGE = 'refusé : vibreur (ton réglage)';
const ETAT = (sonnerie) => `normal|haut_parleur|1|0|vol=9/15|muet=0|sonnerie=${sonnerie}|media=haut_parleur`;
const GENOU = { id: 'e3', source: 'musique', ref: '57', debut_ms: 155000, fin_ms: 160000, nom: 'genou', moment: 'ici', cible: '' };

// le journal de la voix ne garde que des champs plats, aux noms et aux textes [a-z_] (route /api/voix/journal)
function passeLeJournal(x) {
  const champs = Object.entries(x).filter(([, v]) => v !== undefined);
  assert.ok(champs.length <= 12, `12 champs au plus : ${champs.length}`);
  for (const [k, v] of champs) {
    assert.match(k, /^[a-z_]{1,20}$/, `nom de champ ${k}`);
    if (typeof v === 'string') assert.match(v, /^[a-z_]{1,30}$/, `${k} = ${v}`);
  }
}

// l'appli du téléphone : la 1.98 (sonJouerVibreur) ou une d'avant (sonJouer, sonJouerVolume) ; elle note chaque appel et rend « reponse »
function appli({ v198 = true, sonnerie = 'vibreur', reponse = 'ok' } = {}) {
  const appels = [];
  const A = { sonEtat: () => (sonnerie ? ETAT(sonnerie) : 'normal|haut_parleur|1|0'),
    sonJouer: (...a) => { appels.push(['sonJouer', ...a]); return typeof reponse === 'function' ? reponse(a) : reponse; },
    sonJouerVolume: (...a) => { appels.push(['sonJouerVolume', ...a]); return typeof reponse === 'function' ? reponse(a) : reponse; } };
  if (v198) A.sonJouerVibreur = (...a) => { appels.push(['sonJouerVibreur', ...a]); return typeof reponse === 'function' ? reponse(a) : reponse; };
  return { A, appels };
}

// le son « après sa voix » (jouerSonEnAttente), dans un bac à sable ; sonsMac : les extraits que le Mac a
function enAttente({ app = null, reglages = {}, sonsMac = {}, extrait = GENOU, moment = 'ici' } = {}) {
  const journal = [], demandes = [];
  const ctx = { setInterval: () => 0, setTimeout: () => 0, Date, motDirectJusqua: 0, reglagesCorps: { sons_nuit: true, son_pendant: true, ...reglages },
    lecteur: { actif: moment === 'sous', enPause: false }, etat: { flux: null, micro: false, conversation: null, finVoixA: 0 },
    journalVoix: (e, d) => journal.push({ e, ...(d || {}) }), jeton: () => 'x', gainSortie: null, HautParleurs,
    actx: { decodeAudioData: () => Promise.resolve({ duration: 5 }), createBufferSource: () => ({ connect() {}, start() {} }), createGain: () => ({ gain: {}, connect() {} }) },
    fetch: (url) => { demandes.push(url); const m = /(e\d+)$/.exec(url); return Promise.resolve(m && sonsMac[m[1]] ? { ok: true, status: 200, arrayBuffer: () => Promise.resolve({}) } : { ok: false, status: 404 }); },
    window: app ? { HakimApp: app.A } : {} };
  ctx.window.location = { origin: 'x' };
  vm.createContext(ctx);
  const bloc = PAGE.slice(PAGE.indexOf('let sonEnAttente = null'), PAGE.indexOf('// fin des sons'));
  vm.runInContext(bloc.replace('let sonEnAttente', 'var sonEnAttente').replace(', sonJusqua = 0', '; var sonJusqua = 0') + '\nthis.j = jouerSonEnAttente;', ctx);
  ctx.sonEnAttente = { id: extrait.id, t: Date.now(), extrait: { ...extrait, moment } };
  return { ctx, journal, demandes, retours: () => journal.filter(x => x.e === 'son_retour') };
}
const laisser = async () => { for (let i = 0; i < 4; i++) await new Promise(r => setImmediate(r)); };

// le lecteur de la page (un son à sa place dans sa voix), sur une horloge virtuelle
function simulateur({ sonsMac = {}, app = null, reglages = {} } = {}) {
  let maintenant = 0, suivant = 1;
  const minuteries = new Map(), journal = [], sons = [], demandes = [];
  const planifier = (fn, ms, repete) => { const id = suivant++; minuteries.set(id, { t: maintenant + Math.max(0, ms) / 1000, fn, repete }); return id; };
  const actx = {
    state: 'running', get currentTime() { return maintenant; },
    createGain: () => ({ gain: { value: 1 }, connect() {} }),
    decodeAudioData: (ab) => Promise.resolve({ duration: ab.n / 22, texte: ab.texte }),
    createBufferSource() {
      const s = { buffer: null, playbackRate: { value: 1 }, connect() {}, onended: null,
        start(t) { const debut = Math.max(t, maintenant); s.rec = { debut, fin: debut + s.buffer.duration, texte: s.buffer.texte }; sons.push(s.rec);
          planifier(() => { if (!s.arretee && s.onended) s.onended(); }, (debut + s.buffer.duration - maintenant) * 1000); },
        stop(quand) { if (Number.isFinite(quand) && quand > maintenant) return; if (s.arretee) return; s.arretee = true;
          if (s.rec && s.rec.debut > maintenant) sons.splice(sons.indexOf(s.rec), 1); planifier(() => s.onended && s.onended(), 0); } };
      return s;
    },
  };
  const cx = {
    console, Math, JSON, Promise, Set, Map, Error, Blob, URL, AbortController, Voix, HautParleurs, Number, String,
    setTimeout: (fn, ms) => planifier(fn, ms), setInterval: (fn, ms) => planifier(fn, ms, ms), clearInterval: (id) => minuteries.delete(id), clearTimeout: (id) => minuteries.delete(id),
    performance: { now: () => maintenant * 1000 }, localStorage: { getItem: () => JSON.stringify({ fixe: 0.85, parSec: 0.52, cps: 22 }), setItem() {} },
    etat: { conversation: {}, reglages: { vitesse: 1 }, interieur: null }, debutsPrets: new Set(), cleDebut: (d) => d, reglagesCorps: { ...reglages },
    actx, analyseurVoix: {}, lecteurSysteme: null, jeton: () => 'x', humeur() {}, jarvisPeutParler: () => true, forceDeLaVoix: () => 1,
    journalVoix: (e, d) => journal.push({ t: maintenant, e, ...(d || {}) }), vitesseVoix: () => 1, tempoVoix: () => 1,
    fetch: (url, o) => {
      const son = /^\/api\/sons\/joue\/(e\d+)$/.exec(url);
      if (son) {
        demandes.push(url);
        return new Promise((res) => planifier(() => res(sonsMac[son[1]]
          ? { ok: true, status: 200, arrayBuffer: () => Promise.resolve({ n: sonsMac[son[1]] * 22, texte: `[${son[1]}]` }) }
          : { ok: false, status: 404 }), 50));
      }
      const { texte } = JSON.parse(o.body);
      return new Promise((res) => planifier(() => res({ ok: true, arrayBuffer: () => Promise.resolve({ n: texte.length, texte }) }), 900 + texte.length * 24));
    },
  };
  cx.window = cx;
  if (app) cx.HakimApp = app.A;
  vm.createContext(cx);
  vm.runInContext(AIDES + '\n' + LECTEUR + '\nthis.lecteur = creerLecteurNeuronal();', cx);
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
  return { cx, lecteur: cx.lecteur, journal, sons, demandes, avancer, retours: () => journal.filter(x => x.e === 'son_retour') };
}
async function genouEnTete(machine) {
  const sim = simulateur(machine);
  sim.lecteur.direSon(GENOU);
  sim.lecteur.dire('Je ne plie le genou que pour Allah.');
  sim.lecteur.finFlux();
  await sim.avancer(40);
  return sim;
}

/* ---------- le cockpit : le réglage, lu à chaud, enregistré, montré ---------- */

test('le réglage sons_vibreur : allumé par défaut (le choix d\'Ahmed), éteint seulement si papa l\'éteint', () => {
  const ctx = { CORPS_REGLAGES: 'x', CORPS_INTERVALLES: [30, 60, 120, 300, 900], lireJson: () => ({}) };
  vm.createContext(ctx);
  vm.runInContext(prendre(SRV, 'function corpsReglages(') + '\nthis.f = corpsReglages;', ctx);
  assert.strictEqual(ctx.f().sons_vibreur, true, 'par défaut : allumé');
  ctx.lireJson = () => ({ sons_vibreur: false });
  assert.strictEqual(ctx.f().sons_vibreur, false, 'éteint par papa');
  ctx.lireJson = () => ({ sons_vibreur: true });
  assert.strictEqual(ctx.f().sons_vibreur, true);
  ctx.lireJson = () => null;
  assert.strictEqual(ctx.f().sons_vibreur, true, 'fichier illisible : allumé');
});

test('la route POST /api/corps/reglages l\'enregistre dans les deux sens, et ignore ce qui n\'est pas oui ou non', () => {
  const debut = SRV.indexOf('const q = await lire(), r = corpsReglages()');
  const fin = SRV.indexOf('try { ecrireAtomique(CORPS_REGLAGES, j(r));', debut);
  assert.ok(debut > 0 && fin > debut);
  const corps = SRV.slice(debut, fin).replace('const q = await lire(), r = corpsReglages()', 'const q = lire(), r = corpsReglages()');
  const notes = [];
  const ctx = { CORPS_INTERVALLES: [30, 60, 120, 300, 900], VoixHakim: { VOIX: ['azure_rap', 'rap'] }, noterAjustementPapa: (c) => notes.push(...c) };
  vm.createContext(ctx);
  vm.runInContext(`this.f = (lire, corpsReglages) => { ${corps}\n return r; };`, ctx);
  const regler = (actuel, q) => ctx.f(() => q, () => ({ ...actuel }));
  assert.strictEqual(regler({ sons_vibreur: true }, { sons_vibreur: false }).sons_vibreur, false);
  assert.strictEqual(regler({ sons_vibreur: false }, { sons_vibreur: true }).sons_vibreur, true);
  assert.strictEqual(regler({ sons_vibreur: true }, { sons_vibreur: 'non' }).sons_vibreur, true, 'pas un booléen : ignoré');
  assert.ok(notes.includes('sons_vibreur'), 'ce que papa change passe avant Hakim (30 min)');
});

test('la page Réglages : une ligne « Ses sons en vibreur » dans Son corps (route corps), un interrupteur oui/non', () => {
  const m = /\['sons_vibreur', '([^']+)', '([^']+)', 'oui'\]/.exec(REGLAGES);
  assert.ok(m, 'la ligne est sur la page');
  assert.match(m[1], /vibreur/i);
  assert.match(m[2], /silencieux/, 'elle dit que le silencieux bloque toujours');
  assert.match(m[2], /Ne pas déranger/);
  const corps = REGLAGES.indexOf("{ id: 'corps'"), suivante = REGLAGES.indexOf('{ id: ', corps + 5);
  assert.ok(m.index > corps && m.index < suivante, 'dans la famille « Son corps »');
});

test('la page SENS (dans l\'appli) : une case « Ses sons en vibreur », enregistrée au cockpit, et ses écoutes transmettent le réglage', () => {
  assert.match(SENS, /<input type="checkbox" id="sonsVibreur">/);
  assert.match(SENS, /\['sonsVibreur', 'sons_vibreur'\]/, 'la case écrit sons_vibreur');
  assert.match(SENS, /\$\('sonsVibreur'\)\.checked = d\.reglages\.sons_vibreur !== false;/, 'elle montre le réglage lu');
  assert.match(SENS, /vibreurPermis = d\.reglages\.sons_vibreur !== false;/);
  assert.doesNotMatch(SENS, /textContent = appli\.sonJouer\(/, 'plus aucune écoute sans le réglage');
  // l'aide jouerAppli, évaluée : la 1.98 reçoit le réglage ; une appli d'avant, comme avant
  const ligne = /const jouerAppli = [^\n]+/.exec(SENS)[0];
  const essai = (A, permis) => { const cx = { appli: A, vibreurPermis: permis }; vm.createContext(cx); vm.runInContext(`${ligne}\nthis.r = jouerAppli('musique', '57', 1000, 6000);`, cx); return cx.r; };
  const n = appli();
  essai(n.A, false); essai(n.A, true);
  assert.deepStrictEqual(n.appels, [['sonJouerVibreur', 'musique', '57', 1000, 6000, 0.6, false], ['sonJouerVibreur', 'musique', '57', 1000, 6000, 0.6, true]]);
  const v = appli({ v198: false });
  essai(v.A, false);
  assert.deepStrictEqual(v.appels, [['sonJouer', 'musique', '57', 1000, 6000]]);
});

/* ---------- la page : le réglage transmis à l'appli avec chaque son ---------- */

test('après sa voix, l\'appli 1.98 reçoit le réglage : allumé → vrai, éteint → faux (sonnerie normale : rien d\'autre ne change)', () => {
  const on = appli({ sonnerie: 'normal' });
  enAttente({ app: on }).ctx.j();
  assert.deepStrictEqual(on.appels, [['sonJouerVibreur', 'musique', '57', 155000, 160000, 0.6, true]], 'par défaut : allumé');
  const off = appli({ sonnerie: 'normal' });
  const r = enAttente({ app: off, reglages: { sons_vibreur: false } });
  r.ctx.j();
  assert.deepStrictEqual(off.appels, [['sonJouerVibreur', 'musique', '57', 155000, 160000, 0.6, false]], 'éteint : transmis');
  assert.deepStrictEqual(r.retours().map(x => [x.joue, x.ou]), [[true, 'appli']], 'en sonnerie normale, il joue');
});

test('sous sa voix : le même réglage, au volume bas (0,3)', () => {
  const a = appli({ sonnerie: 'normal' });
  enAttente({ app: a, reglages: { sons_vibreur: false }, moment: 'sous' }).ctx.j();
  assert.deepStrictEqual(a.appels, [['sonJouerVibreur', 'musique', '57', 155000, 160000, 0.3, false]]);
});

test('une appli d\'avant la 1.98 : appelée comme avant (sonJouer, sonJouerVolume), sans le réglage', () => {
  const a = appli({ v198: false, sonnerie: 'normal' });
  enAttente({ app: a }).ctx.j();
  const b = appli({ v198: false, sonnerie: 'normal' });
  enAttente({ app: b, moment: 'sous' }).ctx.j();
  assert.deepStrictEqual(a.appels, [['sonJouer', 'musique', '57', 155000, 160000]]);
  assert.deepStrictEqual(b.appels, [['sonJouerVolume', 'musique', '57', 155000, 160000, 0.3]]);
});

test('réglage allumé, téléphone en vibreur : l\'appli le joue (le vibreur ne bloque pas)', () => {
  const a = appli({ sonnerie: 'vibreur' });
  const r = enAttente({ app: a, reglages: { sons_vibreur: true } });
  r.ctx.j();
  assert.deepStrictEqual(a.appels.map(x => x[x.length - 1]), [true]);
  assert.deepStrictEqual(r.retours().map(x => [x.joue, x.ou]), [[true, 'appli']]);
});

test('réglage éteint, téléphone en vibreur : ni l\'appli ni la page ne le jouent (même si le Mac a le morceau), et c\'est dit', async () => {
  const a = appli({ sonnerie: 'vibreur' });
  const r = enAttente({ app: a, reglages: { sons_vibreur: false }, sonsMac: { e3: 5 } });
  r.ctx.j();
  await laisser();
  assert.deepStrictEqual(a.appels, [], 'l\'appli n\'est pas appelée');
  assert.deepStrictEqual(r.demandes, [], 'la page ne va pas chercher le morceau au Mac');
  const ret = r.retours();
  assert.deepStrictEqual(ret.map(x => [x.joue, x.raison, x.ex]), [[false, 'vibreur_reglage', 3]]);
  ret.forEach(passeLeJournal);
});

test('réglage éteint, la page ne sait pas la sonnerie : l\'appli refuse (« ton réglage ») et la page ne le rejoue pas par le Mac', async () => {
  const a = appli({ sonnerie: '', reponse: REFUS_REGLAGE });
  const r = enAttente({ app: a, reglages: { sons_vibreur: false }, sonsMac: { e3: 5 } });
  r.ctx.j();
  await laisser();
  assert.strictEqual(a.appels.length, 1);
  assert.deepStrictEqual(r.retours().map(x => [x.joue, x.ou, x.raison]), [[false, 'appli', 'vibreur_reglage']]);
  assert.deepStrictEqual(r.demandes, [], 'pas de lecture par la page derrière le refus');
});

test('témoin : un autre refus de l\'appli (Ne pas déranger) garde le repli par le Mac d\'avant', async () => {
  const a = appli({ sonnerie: 'normal', reponse: 'refusé : Ne pas déranger' });
  const r = enAttente({ app: a, sonsMac: { e3: 5 } });
  r.ctx.j();
  await laisser();
  assert.deepStrictEqual(r.demandes, ['/api/sons/joue/e3']);
});

test('la page du Mac : le vibreur n\'existe pas, le réglage éteint ne bloque rien', async () => {
  const r = enAttente({ reglages: { sons_vibreur: false }, sonsMac: { e3: 5 } });
  r.ctx.j();
  await laisser();
  assert.deepStrictEqual(r.demandes, ['/api/sons/joue/e3']);
  assert.deepStrictEqual(r.retours().map(x => [x.joue, x.ou]), [[true, 'page']]);
});

test('le refus de l\'appli en un mot : « ton réglage » → vibreur_reglage ; les autres inchangés', () => {
  const cx = {}; vm.createContext(cx);
  vm.runInContext(prendre(PAGE, 'function raisonRefusAppli(') + '\nthis.f = raisonRefusAppli;', cx);
  assert.strictEqual(cx.f(REFUS_REGLAGE, 'vibreur'), 'vibreur_reglage');
  assert.strictEqual(cx.f(REFUS_REGLAGE, ''), 'vibreur_reglage');
  assert.strictEqual(cx.f('refusé : le téléphone est en silencieux', 'vibreur'), 'vibreur', 'l\'appli d\'avant : le vibreur, pas le réglage');
  assert.strictEqual(cx.f('refusé : le téléphone est en silencieux', 'silencieux'), 'silencieux');
  assert.strictEqual(cx.f('refusé : Ne pas déranger', 'vibreur'), 'ne_pas_deranger');
});

/* ---------- la page : un son à sa place dans sa voix (le lecteur) ---------- */

test('dans sa voix, réglage éteint et téléphone en vibreur : le morceau du Mac ne sort pas par la page, sa voix continue, c\'est dit', async () => {
  const a = appli({ sonnerie: 'vibreur' });
  const sim = await genouEnTete({ app: a, sonsMac: { e3: 5 }, reglages: { sons_vibreur: false } });
  assert.ok(!sim.sons.some(s => s.texte === '[e3]'), 'genou ne sonne pas');
  assert.deepStrictEqual(sim.demandes, [], 'rien demandé au Mac');
  assert.deepStrictEqual(a.appels, [], 'rien confié à l\'appli');
  assert.ok(sim.sons.some(s => /genou/.test(s.texte)), 'sa voix continue');
  const r = sim.retours();
  assert.deepStrictEqual(r.map(x => [x.joue, x.raison]), [[false, 'vibreur_reglage']]);
  r.forEach(passeLeJournal);
});

test('témoin : réglage allumé, même téléphone en vibreur : le morceau du Mac sort par la page', async () => {
  const sim = await genouEnTete({ app: appli({ sonnerie: 'vibreur' }), sonsMac: { e3: 5 }, reglages: { sons_vibreur: true } });
  assert.ok(sim.sons.some(s => s.texte === '[e3]'), 'genou sonne');
  assert.deepStrictEqual(sim.retours().map(x => [x.joue, x.ou]), [[true, 'page']]);
});

test('dans sa voix, le morceau n\'est que sur le téléphone : l\'appli 1.98 reçoit le réglage (allumé, puis éteint en sonnerie normale)', async () => {
  const on = appli({ sonnerie: 'vibreur' });
  await genouEnTete({ app: on });
  assert.deepStrictEqual(on.appels, [['sonJouerVibreur', 'musique', '57', 155000, 160000, 0.6, true]]);
  const off = appli({ sonnerie: 'normal' });
  await genouEnTete({ app: off, reglages: { sons_vibreur: false } });
  assert.deepStrictEqual(off.appels, [['sonJouerVibreur', 'musique', '57', 155000, 160000, 0.6, false]]);
  const vieille = appli({ v198: false, sonnerie: 'normal' });
  await genouEnTete({ app: vieille });
  assert.deepStrictEqual(vieille.appels, [['sonJouer', 'musique', '57', 155000, 160000]], 'une appli d\'avant : comme avant');
});

/* ---------- son tour suivant : il le sait ---------- */

test('son tour suivant : « refusé : vibreur (ton réglage) »', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sons-vibreur-'));
  const diag = path.join(dir, 'voix-diagnostic.jsonl'), t = Date.now();
  fs.writeFileSync(diag, [{ t: t - 60000, e: 'son_envoye', appareil: 'cockpit', id: 'e3', nom: 'genou', moment: 'ici' },
    { t: t - 59000, e: 'son_retour', appareil: 'telephone', ex: 3, joue: false, raison: 'vibreur_reglage', source: 'musique' }].map(o => JSON.stringify(o)).join('\n') + '\n');
  const ctx = { JARVIS: dir, JARVIS_VOIX_DIAGNOSTIC: diag, path, fs, Number, Math, String, Map, Set, Array, Date, j: JSON.stringify,
    lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } }, ecrireAtomique: (f, x) => fs.writeFileSync(f, x),
    lignesJson: (f, n) => fs.readFileSync(f, 'utf8').split('\n').filter(Boolean).slice(-n).map(l => JSON.parse(l)),
    lireSons: () => [{ id: 'e3', nom: 'genou' }] };
  vm.createContext(ctx);
  const raisons = SRV.slice(SRV.indexOf('const RAISONS_SON'), SRV.indexOf('};\n', SRV.indexOf('const RAISONS_SON')) + 3);
  vm.runInContext(raisons + prendre(SRV, 'function sonsDits(') + '\nthis.f = sonsDits;', ctx);
  const l = ctx.f(t);
  assert.match(l, /« genou » n'a pas sonné sur le téléphone \(\d{2}:\d{2}:\d{2}\) : refusé : vibreur \(ton réglage\)/);
  assert.match(l, /Ses sons en vibreur/, 'il sait quel réglage');
});

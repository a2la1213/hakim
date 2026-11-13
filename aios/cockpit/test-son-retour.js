/* (13/11, lettre de Hakim du 12/11 06:34 : « papa n'entend plus ma balise [[son: genou]] […] je n'ai aucun retour de lecture de mon côté »)
   LE RETOUR DE LECTURE DE SES SONS. node --test test-son-retour.js
   Mesuré (journaux du 12/11, lecture seule) : de 06:29 à 06:38, le cockpit a envoyé ses quinze « genou » (sensations « son » du serveur à chaque
   essai) ; « genou » est e3, une musique du TÉLÉPHONE (ref 57) que le Mac n'a jamais reçue (aucun e3.mp3, aucun morceau : l'appli l'envoie toutes
   les 10 min sans le cookie du verrou) ; la page la confie donc au lecteur de l'appli (Sons.jouer), qui refuse tout son quand la sonnerie n'est
   pas « normale » : l'écran du téléphone dit « Sonnerie en mode vibreur » à 06:38:16 (et à chaque lecture de la barre d'état depuis le 08/11).
   Sa réponse (« refusé : le téléphone est en silencieux ») n'était lue par personne. « kichta » (e10, découpé sur le Mac) passe par la page
   (Web Audio) : il est sorti à 06:37. Le bisect de ce test sur les révisions du 31/10 au 11/11 (0f6169d) : toutes confient « genou » à l'appli
   avec les bons arguments ; aucune fusion du 11/11 n'a cassé ce chemin. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const SRV = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (s, debut) => { const i = s.indexOf(debut); assert.ok(i >= 0, `introuvable : ${debut}`); return s.slice(i, s.indexOf('\n}\n', i) + 3); };
const LECTEUR = prendre(PAGE, 'function creerLecteurNeuronal');
const AIDES = ['function raisonRefusAppli(', 'function sonnerieIci(', 'function retourSon('].map(d => prendre(PAGE, d)).join('\n');
const Voix = require('./public/voix.js');
const HautParleurs = require('./public/haut-parleurs.js');

const GENOU = { id: 'e3', source: 'musique', ref: '57', debut_ms: 155000, fin_ms: 160000, nom: 'genou', moment: 'ici', cible: '' };   // 5 s, au téléphone seulement
const KICHTA = { id: 'e10', source: 'atelier', ref: '/x/KICHTA.wav', debut_ms: 49000, fin_ms: 55000, nom: 'kichta', moment: 'ici', cible: '' };

// le lecteur de la page sur une horloge virtuelle ; sonsMac : les extraits que le Mac a (durée en s) ; appli : ce que répond Sons.jouer
function simulateur({ sonsMac = {}, appli = null, sonEtat = '' } = {}) {
  let maintenant = 0, suivant = 1;
  const minuteries = new Map(), natifs = [], journal = [], sons = [];
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
    etat: { conversation: {}, reglages: { vitesse: 1 }, interieur: null }, debutsPrets: new Set(), cleDebut: (d) => d,
    actx, analyseurVoix: {}, lecteurSysteme: null, jeton: () => 'x', humeur() {}, jarvisPeutParler: () => true, forceDeLaVoix: () => 1,
    journalVoix: (e, d) => journal.push({ t: maintenant, e, ...(d || {}) }), vitesseVoix: () => 1, tempoVoix: () => 1,
    fetch: (url, o) => {
      const son = /^\/api\/sons\/joue\/(e\d+)$/.exec(url);
      if (son) return new Promise((res) => planifier(() => res(sonsMac[son[1]]
        ? { ok: true, status: 200, arrayBuffer: () => Promise.resolve({ n: sonsMac[son[1]] * 22, texte: `[${son[1]}]` }) }
        : { ok: false, status: 404 }), 50));
      const { texte } = JSON.parse(o.body);
      return new Promise((res) => planifier(() => res({ ok: true, arrayBuffer: () => Promise.resolve({ n: texte.length, texte }) }), 900 + texte.length * 24));
    },
  };
  cx.window = cx;
  if (appli != null) cx.HakimApp = { sonJouer: (...a) => { natifs.push({ t: maintenant, a }); return appli; }, sonEtat: () => sonEtat };
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
  const retours = () => journal.filter(x => x.e === 'son_retour');
  return { cx, lecteur: cx.lecteur, natifs, journal, sons, retours, avancer, get maintenant() { return maintenant; } };
}
// sa réponse du 12/11 06:31 : « [[son: genou]] Je ne plie le genou que pour Allah. Voilà, tu l'as entendue ? » (le son d'abord)
async function genouEnTete(machine) {
  const sim = simulateur(machine);
  sim.lecteur.direSon(GENOU);
  sim.lecteur.dire('Je ne plie le genou que pour Allah.');
  sim.lecteur.dire("Voilà, tu l'as entendue cette fois ?");
  sim.lecteur.finFlux();
  await sim.avancer(40);
  return sim;
}
// le journal de la voix (/api/voix/journal) ne garde que 12 champs plats, aux noms [a-z_], aux textes [a-z_] : un retour qui n'y passe pas est perdu
function passeLeJournal(x) {
  const champs = Object.entries(x).filter(([, v]) => v !== undefined);
  assert.ok(champs.length <= 12, `12 champs au plus : ${champs.length}`);
  for (const [k, v] of champs) {
    assert.match(k, /^[a-z_]{1,20}$/, `nom de champ ${k}`);
    if (typeof v === 'string') assert.match(v, /^[a-z_]{1,30}$/, `${k} = ${v}`);
    else assert.ok(typeof v === 'boolean' || (typeof v === 'number' && Number.isFinite(v)), `${k} : ${typeof v}`);
  }
}

test('bisect : la page du téléphone confie « genou » (absent du Mac) à l\'appli, avec ses vrais arguments', async () => {
  const sim = await genouEnTete({ appli: 'ok' });
  assert.strictEqual(sim.natifs.length, 1, 'une fois');
  assert.deepStrictEqual(sim.natifs[0].a, ['musique', '57', 155000, 160000]);
});

test('le téléphone en vibreur : le refus de l\'appli devient son retour de lecture (« vibreur »), et sa voix n\'attend pas un son qui ne viendra pas', async () => {
  // l'appli d'avant le 13/11 répond « silencieux » aussi en vibreur ; la sonnerie que l'appli donne à la page le précise
  const sim = await genouEnTete({ appli: 'refusé : le téléphone est en silencieux', sonEtat: 'normal|haut_parleur|1|0|vol=9/15|muet=0|sonnerie=vibreur|media=haut_parleur' });
  const r = sim.retours();
  assert.strictEqual(r.length, 1, `un retour pour son son : ${JSON.stringify(sim.journal.filter(x => /^son/.test(x.e)))}`);
  assert.strictEqual(r[0].joue, false);
  assert.strictEqual(r[0].ou, 'appli');
  assert.strictEqual(r[0].raison, 'vibreur');
  assert.strictEqual(r[0].ex, 3);
  passeLeJournal(r[0]);
  // sa voix : pas de trou de 5 s à la place du son refusé
  const voix = sim.sons.filter(s => !/^\[e/.test(s.texte));
  assert.ok(voix.length >= 1, 'sa voix parle');
  // sans le retour, sa voix attendait la fin de la place du son (refus + 5 s + 0,15 s) ; avec lui, elle part dès que sa synthèse est prête
  assert.ok(voix[0].debut < sim.natifs[0].t + 3, `sa voix part sans attendre les 5 s du son refusé (${voix[0].debut.toFixed(2)} s, refus à ${sim.natifs[0].t.toFixed(2)} s)`);
});

test('l\'appli l\'accepte : son retour dit « parti par l\'appli »', async () => {
  const sim = await genouEnTete({ appli: 'ok' });
  const r = sim.retours();
  assert.strictEqual(r.length, 1);
  assert.deepStrictEqual([r[0].joue, r[0].ou, r[0].raison], [true, 'appli', undefined]);
  passeLeJournal(r[0]);
});

test('le Mac a le morceau (kichta) : joué par la page, son retour à l\'instant où il part ; aucun appel à l\'appli', async () => {
  const sim = simulateur({ sonsMac: { e10: 6 }, appli: 'refusé : le téléphone est en silencieux' });
  sim.lecteur.dire('On se met du son.');
  sim.lecteur.direSon(KICHTA);
  sim.lecteur.finFlux();
  await sim.avancer(40);
  const s = sim.sons.find(x => x.texte === '[e10]');
  assert.ok(s, 'kichta sonne');
  const r = sim.retours();
  assert.strictEqual(r.length, 1);
  assert.deepStrictEqual([r[0].joue, r[0].ou, r[0].ex, r[0].source], [true, 'page', 10, 'atelier']);
  assert.ok(Math.abs(r[0].t - s.debut) < 1e-6, `noté quand il part (${r[0].t} = ${s.debut})`);
  assert.strictEqual(sim.natifs.length, 0);
});

test('ni le Mac ni l\'appli (la page du Mac) : « pas sur le Mac », et sa voix continue', async () => {
  const sim = await genouEnTete({});
  const r = sim.retours();
  assert.strictEqual(r.length, 1);
  assert.deepStrictEqual([r[0].joue, r[0].raison], [false, 'pas_sur_le_mac']);
  assert.ok(sim.sons.some(s => /genou/.test(s.texte)) && sim.sons.some(s => /entendue/.test(s.texte)), 'sa voix continue sans lui');
});

test('lâché avant d\'avoir sonné (papa reparle, sa parole est arrêtée) : « coupé »', async () => {
  const sim = simulateur({ sonsMac: { e10: 6 } });
  sim.lecteur.dire("Ok papa, voilà une longue phrase avant le son, pour qu'il soit programmé plus tard dans sa voix.");
  sim.lecteur.direSon(KICHTA);
  sim.lecteur.finFlux();
  await sim.avancer(3.5);
  sim.lecteur.arreter();
  await sim.avancer(40);
  const r = sim.retours();
  assert.strictEqual(r.length, 1, JSON.stringify(r));
  assert.deepStrictEqual([r[0].joue, r[0].raison], [false, 'coupe']);
  assert.ok(!sim.sons.some(s => s.texte === '[e10]'), 'il n\'a pas sonné');
});

test('ses haut-parleurs fermés : le son n\'est plus perdu en silence', async () => {
  const sim = simulateur({ appli: 'ok' });
  sim.cx.hautParleursFermes = () => true;
  sim.lecteur.direSon(GENOU);
  const r = sim.retours();
  assert.strictEqual(r.length, 1);
  assert.deepStrictEqual([r[0].joue, r[0].raison], [false, 'haut_parleurs']);
});

test('le refus de l\'appli en un mot', () => {
  const cx = {}; vm.createContext(cx);
  vm.runInContext(prendre(PAGE, 'function raisonRefusAppli(') + '\nthis.f = raisonRefusAppli;', cx);
  assert.strictEqual(cx.f('refusé : le téléphone est en silencieux', 'vibreur'), 'vibreur');
  assert.strictEqual(cx.f('refusé : le téléphone est en silencieux', 'silencieux'), 'silencieux');
  assert.strictEqual(cx.f('refusé : le téléphone est en vibreur', ''), 'vibreur');
  assert.strictEqual(cx.f('refusé : Ne pas déranger', 'normal'), 'ne_pas_deranger');
  assert.strictEqual(cx.f('refusé : la permission « Musique et audio » manque', 'normal'), 'permission');
  assert.strictEqual(cx.f("refusé : le morceau n'est plus sur le téléphone", 'normal'), 'morceau_absent');
  assert.strictEqual(cx.f('refusé : un extrait de 8 s au plus', 'normal'), 'trop_long');
  assert.strictEqual(cx.f(undefined, ''), 'appli_refuse');
});

// le son « après sa voix » (jouerSonEnAttente) : le même retour, et la page le joue elle-même si l'appli refuse et que le Mac l'a
function enAttente({ appli, sonsMac = {} }) {
  const journal = [], demandes = [];
  const ctx = { setInterval: () => 0, setTimeout: () => 0, Date, motDirectJusqua: 0, reglagesCorps: { sons_nuit: true }, lecteur: { actif: false, enPause: false },
    etat: { flux: null, micro: false, conversation: null, finVoixA: 0 }, journalVoix: (e, d) => journal.push({ e, ...(d || {}) }), jeton: () => 'x', gainSortie: null,
    HautParleurs, actx: { decodeAudioData: () => Promise.resolve({ duration: 6 }), createBufferSource: () => ({ connect() {}, start() {} }), createGain: () => ({ gain: {}, connect() {} }) },
    fetch: (url) => { demandes.push(url); const m = /(e\d+)$/.exec(url); return Promise.resolve(sonsMac[m[1]] ? { ok: true, status: 200, arrayBuffer: () => Promise.resolve({}) } : { ok: false, status: 404 }); },
    window: { HakimApp: { sonJouer: () => appli, sonEtat: () => 'normal|haut_parleur|1|0|vol=9/15|muet=0|sonnerie=vibreur|media=haut_parleur' } } };
  ctx.window.location = { origin: 'x' };
  vm.createContext(ctx);
  const bloc = PAGE.slice(PAGE.indexOf('let sonEnAttente = null'), PAGE.indexOf('// fin des sons'));
  vm.runInContext(bloc.replace('let sonEnAttente', 'var sonEnAttente').replace(', sonJusqua = 0', '; var sonJusqua = 0') + '\nthis.j = jouerSonEnAttente;', ctx);
  ctx.reglagesCorps.sons_nuit = true;
  ctx.sonEnAttente = { id: 'e3', t: Date.now(), extrait: GENOU };
  return { ctx, journal, demandes, retours: () => journal.filter(x => x.e === 'son_retour') };
}
test('après sa voix, l\'appli refuse (vibreur) : c\'est dit, et la page tente le morceau du Mac', async () => {
  const r = enAttente({ appli: 'refusé : le téléphone est en silencieux', sonsMac: { e3: 5 } });
  r.ctx.j();
  await new Promise(x => setImmediate(x)); await new Promise(x => setImmediate(x)); await new Promise(x => setImmediate(x));
  const ret = r.retours();
  assert.deepStrictEqual(ret.map(x => [x.joue, x.ou, x.raison || '']), [[false, 'appli', 'vibreur'], [true, 'page', '']]);
  assert.deepStrictEqual(r.demandes, ['/api/sons/joue/e3']);
  ret.forEach(passeLeJournal);
});
test('après sa voix, l\'appli refuse et le Mac ne l\'a pas : deux retours, aucun « joué »', async () => {
  const r = enAttente({ appli: 'refusé : le téléphone est en silencieux' });
  r.ctx.j();
  await new Promise(x => setImmediate(x)); await new Promise(x => setImmediate(x));
  assert.deepStrictEqual(r.retours().map(x => [x.joue, x.raison]), [[false, 'vibreur'], [false, 'pas_sur_le_mac']]);
});
test('après sa voix, l\'appli l\'accepte : une seule voie, aucun appel au Mac', () => {
  const r = enAttente({ appli: 'ok' });
  r.ctx.j();
  assert.deepStrictEqual(r.retours().map(x => [x.joue, x.ou]), [[true, 'appli']]);
  assert.strictEqual(r.demandes.length, 0);
});

// le cockpit : à son tour suivant, il sait ce que ses sons sont devenus (une fois)
function serveur(evs, maintenant) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sons-dits-'));
  const diag = path.join(dir, 'voix-diagnostic.jsonl');
  fs.writeFileSync(diag, evs.map(o => JSON.stringify(o)).join('\n') + '\n');
  const ctx = { JARVIS: dir, JARVIS_VOIX_DIAGNOSTIC: diag, path, fs, Number, Math, String, Map, Set, Array, Date, j: JSON.stringify,
    lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } }, ecrireAtomique: (f, x) => fs.writeFileSync(f, x),
    lignesJson: (f, n) => fs.readFileSync(f, 'utf8').split('\n').filter(Boolean).slice(-n).map(l => JSON.parse(l)),
    lireSons: () => [{ id: 'e3', nom: 'genou' }, { id: 'e10', nom: 'kichta' }] };
  vm.createContext(ctx);
  const raisons = SRV.slice(SRV.indexOf('const RAISONS_SON'), SRV.indexOf('};\n', SRV.indexOf('const RAISONS_SON')) + 3);
  vm.runInContext(raisons + prendre(SRV, 'function noterSonServeur(') + prendre(SRV, 'function sonsDits(') + '\nthis.f = sonsDits; this.noter = noterSonServeur;', ctx);
  return { ctx, diag, ajouter: (o) => fs.appendFileSync(diag, JSON.stringify(o) + '\n'), f: (t) => ctx.f(t == null ? maintenant : t) };
}
test('son tour suivant : « genou » refusé (vibreur), « kichta » sonné ; dit une fois', () => {
  const t = Date.now();
  const s = serveur([
    { t: t - 60000, e: 'son_envoye', appareil: 'cockpit', id: 'e3', nom: 'genou', moment: 'ici' },
    { t: t - 59000, e: 'son_retour', appareil: 'telephone', ex: 3, joue: false, ou: 'appli', raison: 'vibreur', source: 'musique' },
    { t: t - 20000, e: 'son_envoye', appareil: 'cockpit', id: 'e10', nom: 'kichta', moment: 'ici' },
    { t: t - 19000, e: 'son_retour', appareil: 'telephone', ex: 10, joue: true, ou: 'page', source: 'atelier' },
  ], t);
  const l = s.f();
  assert.match(l, /« genou » n'a pas sonné par l'appli du téléphone \(\d{2}:\d{2}:\d{2}\) : l'appli du téléphone refuse tes sons quand le téléphone est en vibreur/);
  assert.match(l, /« kichta » a sonné sur le téléphone à \d{2}:\d{2}:\d{2}/);
  assert.ok(l.indexOf('genou') < l.indexOf('kichta'), 'dans l\'ordre');
  assert.strictEqual(s.f(), '', 'une fois');
});
test('un son envoyé sans aucun retour : dit après 3 min 20 s (un son attend la fin de sa voix jusqu\'à 3 min), jamais avant ; son retour arrivé entre-temps est dit, une fois', () => {
  const t = Date.now();
  const s = serveur([{ t: t - 5000, e: 'son_envoye', appareil: 'cockpit', id: 'e3', nom: 'genou', moment: 'ici' }], t);
  assert.strictEqual(s.f(t), '', 'trop tôt pour conclure');
  assert.strictEqual(s.f(t + 120000), '', 'il peut encore attendre la fin de sa voix');
  assert.match(s.f(t + 200000), /« genou » envoyé à \d{2}:\d{2}:\d{2}, sans aucun retour de lecture/);
  assert.strictEqual(s.f(t + 201000), '', 'une fois');
  const s2 = serveur([{ t: t - 5000, e: 'son_envoye', appareil: 'cockpit', id: 'e3', nom: 'genou', moment: 'ici' },
    { t: t - 4000, e: 'son_retour', appareil: 'telephone', ex: 10, joue: true, ou: 'page' }], t);
  assert.match(s2.f(t), /kichta/, 'un autre son, déjà revenu, est dit tout de suite');
  s2.ajouter({ t: t + 1000, e: 'son_retour', appareil: 'telephone', ex: 3, joue: false, ou: 'appli', raison: 'vibreur' });
  const l = s2.f(t + 2000);
  assert.match(l, /genou/); assert.doesNotMatch(l, /kichta/, 'kichta déjà dit');
  assert.doesNotMatch(l, /sans aucun retour/);
  assert.strictEqual(s2.f(t + 300000), '');
});
test('le cockpit ne perd plus un son en silence : nom inconnu ou sons coupés notés ; le retour entre dans son corps', () => {
  assert.match(SRV, /noterSonServeur\('son_retour', \{ joue: false, raison: corpsReglages\(\)\.sons \? 'nom_inconnu' : 'sons_coupes', nom: o\.son\.nom \}\)/);
  assert.match(SRV, /noterSonServeur\('son_envoye', \{ id: extrait\.id, nom: extrait\.nom, moment: 'ici' \}\)/);
  assert.match(SRV, /const sons = typeof sonsDits === 'function' \? sonsDits\(t\) : ''/);
  assert.match(SRV, /\.\.\.\(sons \? \[sons\] : \[\]\)/);
  const t = Date.now();
  const s = serveur([], t);
  s.ctx.noter('son_retour', { joue: false, raison: 'nom_inconnu', nom: 'genoux' });
  assert.match(s.f(Date.now() + 1), /« genoux » n'a pas sonné \(\d{2}:\d{2}:\d{2}\) : aucun de tes sons ne porte ce nom/);
});

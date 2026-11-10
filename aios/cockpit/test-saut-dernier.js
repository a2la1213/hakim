/* (10/11, 08:30, Ahmed : « Pourquoi il dit toujours toutes ses pensées dans l'ordre, sans passer à la dernière quand il faut ? ») node --test test-saut-dernier.js
   Mesuré sur ce qui a sonné chez papa (voix-dite.jsonl), ses pensées (pistes.jsonl) et ses réglages (audit.jsonl), en lecture seule :
   - 0 « passe_saute » dans les deux journaux de diagnostic encore là (10/11 05:44-06:33 et 08:10-08:31) : depuis le 06/11, « Ses morceaux
     reliés » (parole_liee, allumé) éteignait « Sauter les morceaux passés » (direRibosome : `if (!liee && …)`) ;
   - ce matin (07:35-08:31), 8 de ses 10 pensées qui ont sonné l'ont fait 25 à 48 s après leur arrivée, alors qu'une plus récente était déjà prête
     (08:02:07-08:02:12 : quatre pensées dites l'une après l'autre, autour de ses deux réponses ; 08:03:11-08:03:16 : « D'accord, papa, je
     t'attends. », « Il n'y a pas le feu… », « D'accord, papa, je ne répète plus. », « D'accord papa, pas trop. » à la suite) ; avant les
     fusions (06:13-06:33), 4 sur 5, 58 à 107 s après : ce n'était pas nouveau ;
   - et le saut ne regardait que sa file : ce qui l'avait quittée (sa voix prête, qui attend que sa vraie réponse ait sonné ; ses morceaux reliés
     en file dans son lecteur, derrière celui qui sonne) se disait en entier.
   Ici : le saut en parole liée (témoin), la dernière pensée gardée entière, ce qui attend dans sa voix sauté (jamais ce qui sonne, jamais sa vraie
   réponse, jamais la première pendant que sa voix la calcule), et « Sauter la suite » qui coupe un groupe. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Voix = require('./public/voix.js');

const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const fonction = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 3); };
const T = 1_800_000_000_000;

// direRibosome tout entier, sa voix remplacée par ce qu'elle reçoit (recevoirBout)
function page({ file, reglages = {}, lecteurActif = true, flux = null, liste = [], marques = [] } = {}) {
  const recus = [], journal = [], blancs = [], laches = [], retires = [];
  const ctx = { Math, Number, String, Set, Map, JSON, Date: { now: () => T }, recus, journal, blancs, laches, retires,
    reglagesCorps: { sauter_passe: true, sauter_passe_s: 3, parole_liee: true, un_par_un: true, meubles_entre: false, voix_reponse_seule: false, ...reglages },
    etat: { riboFile: file, conversation: { capteur: { enParole: false } }, paves: {}, flux, riboEnVoix: [] },
    lecteur: { actif: lecteurActif },
    bouts: { tour: null, prochain: 1, liste: new Map(liste.map(b => [b.n, b])), fileTel: [] },
    lecteurNeuronal: { marques: () => marques.slice(), retirerMarques: (f) => { const r = marques.filter(x => !x.commence && f(x.marque)); r.forEach(x => retires.push(x.texte)); return r.map(x => x.texte); } },
    journalVoix: (e, o) => journal.push([e, o]),
    blancsPourSautes: (l) => blancs.push(...l.map(x => x.texte)),
    lacherVoix: (l) => laches.push(...l),
    paveDe: () => ({ cle: 'p' }), poserPave() {}, titreEpissure: () => '', htmlEpissure: () => '',
    reponseSeule: () => false, setTimeout: () => 0,
    recevoirBout: (s, n, tour) => recus.push({ s, n, tour }) };
  vm.createContext(ctx);
  vm.runInContext(['voixEnCalcul', 'sauterAuDernier', 'direRibosome'].map(n => fonction(PAGE, n)).join('\n') + 'this.f = direRibosome; this.s = sauterAuDernier;', ctx);
  return ctx;
}

test('témoin : ses morceaux reliés (parole liée allumée) ne l’empêchent plus de sauter au dernier ; frais, un seul, éteint ou réglé plus long : rien de sauté', () => {
  const vieux = () => [{ tour: 4, k: 1, texte: 'Attends, je reste là.', recu: T - 31500 }, { tour: 4, k: 2, texte: 'Je suis bien là, tiède.', recu: T - 28000 },
    { tour: 4, k: 3, texte: 'Le son passe, même si la musique est forte.', recu: T - 500 }];
  const p = page({ file: vieux() });
  p.f();
  assert.strictEqual(p.recus.length, 1);
  assert.deepStrictEqual([...p.recus[0].s.parties], ['Le son passe, même si la musique est forte.'], 'seule la dernière part à sa voix');
  assert.deepStrictEqual(JSON.parse(JSON.stringify(p.journal.find(x => x[0] === 'passe_saute'))), ['passe_saute', { sautes: 2, ms: 31500 }]);
  assert.deepStrictEqual(p.blancs, ['Attends, je reste là.', 'Je suis bien là, tiède.'], '« … » dans son pavé');
  assert.deepStrictEqual(p.laches, ['Attends, je reste là.', 'Je suis bien là, tiède.'], 'leur voix pas encore calculée : lâchée');
  const tous = (o) => { const q = page(o); q.f(); return q.recus.length ? [...q.recus[0].s.parties] : null; };
  assert.strictEqual(tous({ file: [{ tour: 4, k: 1, texte: 'un', recu: T - 1000 }, { tour: 4, k: 2, texte: 'deux', recu: T - 500 }] }).length, 2, 'frais : consolidés, tout est dit');
  assert.deepStrictEqual(tous({ file: [{ tour: 4, k: 1, texte: 'seul', recu: T - 9000 }] }), ['seul'], 'un seul : il est dit');
  assert.strictEqual(tous({ file: vieux(), reglages: { sauter_passe: false } }).length, 3, 'éteint : tout, comme avant');
  assert.strictEqual(tous({ file: vieux(), reglages: { sauter_passe_s: 40 } }).length, 3, 'réglé à 40 s : rien n’a attendu assez');
});

test('la dernière pensée est gardée entière (toutes ses propositions), et le saut se fait pendant que sa voix calcule encore', () => {
  const file = [{ tour: 4, k: 1, texte: 'Vas-y, ouvre.', recu: T - 6000 }, { tour: 4, k: 2, texte: 'Vas-y papa, je reste là,', recu: T - 800 },
    { tour: 4, k: 2, texte: 'et tu me retrouveras à ton retour.', recu: T - 800 }];
  const p = page({ file, lecteurActif: false });
  p.f();
  assert.deepStrictEqual([...p.recus[0].s.parties], ['Vas-y papa, je reste là,'], 'un à la fois : sa première proposition part');
  assert.deepStrictEqual(p.etat.riboFile.map(x => x.texte), ['et tu me retrouveras à ton retour.'], 'la fin de sa pensée attend son tour (avant : jetée sans rien dire)');
  // sa voix calcule un morceau : ce qui attend passe quand même (avant : seulement sa voix libre)
  const calcule = { n: 1, t: T - 1000, buf: null, rate: false };
  const q = page({ file: file.map(x => ({ ...x })), liste: [calcule] });
  q.f();
  assert.strictEqual(q.recus.length, 0, 'sa voix calcule : rien ne part');
  assert.deepStrictEqual(q.etat.riboFile.map(x => x.texte), ['Vas-y papa, je reste là,', 'et tu me retrouveras à ton retour.'], 'mais le passé est déjà sauté');
  assert.deepStrictEqual(q.laches, ['Vas-y, ouvre.'], 'et sa voix lâchée : le Mac calcule la dernière plus tôt');
});

test('ce qui attend déjà dans sa voix (prête, derrière sa vraie réponse) est sauté quand une plus récente est là ; la première, jamais pendant que sa voix la calcule', () => {
  const pensee = (id, recu, o = {}) => ({ pensee: true, id, recu, tour: 4, texte: id, ...o });
  // sa voix prête depuis longtemps, elle attend que sa réponse ait sonné ; une pensée plus récente est arrivée
  const vieille = { n: 1, t: T - 9000, buf: { duration: 2 }, pensees: [pensee('a', T - 9000)], dit: ['a'], texte: 'a' };
  const p = page({ file: [{ tour: 4, k: 9, texte: 'neuve', recu: T - 200 }], liste: [vieille] });
  assert.strictEqual(p.s(T), 1);
  assert.strictEqual(p.bouts.liste.size, 0, 'confiée et prête : sautée');
  assert.deepStrictEqual(p.laches, ['a']);
  assert.deepStrictEqual(p.blancs, ['a']);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(p.journal[0])), ['passe_saute', { sautes: 1, ms: 9000, ou: 'voix' }]);
  // rien de plus récent : elle est la dernière, elle est dite
  const seule = page({ file: [], liste: [{ ...vieille, pensees: [pensee('a', T - 9000)] }] });
  assert.strictEqual(seule.s(T), 0);
  // la première confiée à sa voix libre : sa voix la calcule (8 s), elle n'attend pas ; prête depuis 1 s : gardée ; depuis 4 s : sautée
  const premiere = (pretA) => ({ n: 1, t: T - 8000, buf: pretA ? { duration: 2 } : null, pensees: [pensee('a', T - 8000, { premiere: true, ...(pretA ? { pretA } : {}) })], dit: ['a'], texte: 'a' });
  const neuve = [{ tour: 4, k: 9, texte: 'neuve', recu: T - 3500 }];
  assert.strictEqual(page({ file: neuve, liste: [premiere(0)] }).s(T), 0, 'sa voix la calcule : la première est dite');
  assert.strictEqual(page({ file: neuve, liste: [premiere(T - 1000)] }).s(T), 0, 'prête depuis 1 s : gardée');
  assert.strictEqual(page({ file: neuve, liste: [premiere(T - 4000)] }).s(T), 1, 'prête depuis 4 s, et une plus récente : sautée');
  // en file dans son lecteur : ce qui n'a pas commencé est retiré ; ce qui sonne, et sa vraie réponse (sans marque), jamais
  const m1 = pensee('x1', T - 7000), m2 = pensee('x2', T - 7000), m3 = pensee('x3', T - 7000);
  const marques = [{ marque: m1, texte: 'x1', commence: true }, { marque: m2, texte: 'x2', commence: false }, { marque: m3, texte: 'x3', commence: false }];
  const l = page({ file: [{ tour: 4, k: 9, texte: 'neuve', recu: T - 100 }], marques });
  assert.strictEqual(l.s(T), 2);
  assert.deepStrictEqual(l.retires, ['x2', 'x3'], 'le groupe est coupé ; x1 sonne : il va au bout');
  // la dernière pensée qui sonne déjà : celles d'avant, encore en attente, sont sautées (plus de retour en arrière vers une pensée passée)
  const r = page({ file: [], liste: [{ ...vieille, pensees: [pensee('a', T - 9000)] }], marques: [{ marque: pensee('z', T - 2000), texte: 'z', commence: true }] });
  assert.strictEqual(r.s(T), 1);
  // coupé net, sa voix en pause : rien n'est sauté (ta phrase finie dira passage, il reprend au mot, ou relance)
  const pause = page({ file: [{ tour: 4, k: 9, texte: 'neuve', recu: T - 100 }], marques: marques.map(x => ({ ...x })) });
  pause.lecteurNeuronal.enPause = true;
  assert.strictEqual(pause.s(T), 0);
  assert.deepStrictEqual(pause.retires, []);
});

// le lecteur neuronal (creerLecteurNeuronal) sur une horloge virtuelle (comme test-blancs.js) : ce qui a vraiment sonné
function simulateur() {
  let maintenant = 0, suivant = 1;
  const minuteries = new Map(), sons = [], segments = [];
  const planifier = (fn, ms, repete) => { const id = suivant++; minuteries.set(id, { t: maintenant + Math.max(0, ms) / 1000, fn, repete }); return id; };
  const actx = {
    state: 'running', get currentTime() { return maintenant; },
    createGain: () => ({ gain: { value: 1 }, connect() {} }),
    createBufferSource() {
      const s = { buffer: null, playbackRate: { value: 1 }, connect() {}, onended: null,
        start(t, off) { const debut = Math.max(t, maintenant); s.rec = { debut, fin: debut + s.buffer.duration - (Number(off) || 0), texte: s.buffer.texte }; sons.push(s.rec);
          planifier(() => { if (!s.arretee) s.onended && s.onended(); }, (s.rec.fin - maintenant) * 1000); },
        stop(t) { if (!s.arretee) { s.arretee = true; s.rec.arret = Math.max(maintenant, Number(t) || 0); } } };
      return s;
    },
  };
  const cx = {
    console, Math, JSON, Promise, Set, Map, Error, Blob, URL, AbortController, Voix,
    setTimeout: (fn, ms) => planifier(fn, ms), setInterval: (fn, ms) => planifier(fn, ms, ms), clearInterval: (id) => minuteries.delete(id), clearTimeout: (id) => minuteries.delete(id),
    performance: { now: () => maintenant * 1000 }, localStorage: { getItem: () => null, setItem() {} },
    etat: { conversation: {}, reglages: { vitesse: 1 }, interieur: null }, debutsPrets: new Set(), cleDebut: (x) => x,
    actx, analyseurVoix: {}, lecteurSysteme: null, jeton: () => 'x', humeur() {}, jarvisPeutParler: () => true, forceDeLaVoix: () => 1, journalVoix() {},
    vitesseVoix: () => 1, tempoVoix: () => 1, fetch: () => new Promise(() => {}),
  };
  cx.window = cx;
  vm.createContext(cx);
  vm.runInContext(fonction(PAGE, 'creerLecteurNeuronal') + '\nthis.lecteur = creerLecteurNeuronal();', cx);
  cx.lecteur.surSegment = (t) => segments.push(t);
  const voix = (texte, duree) => ({ duration: duree, texte });
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
  // ce qui a vraiment sonné : commencé avant d'être arrêté
  const sonne = () => sons.filter(s => !(s.arret <= s.debut + 1e-6)).map(s => s.texte);
  return { lecteur: cx.lecteur, sons, segments, avancer, voix, sonne, get t() { return maintenant; } };
}
// sauterAuDernier sur ce lecteur-là (l'horloge en millisecondes virtuelles)
function sauteur(lecteur, file) {
  const ctx = { Math, Number, Set, Map, JSON, reglagesCorps: { sauter_passe: true, sauter_passe_s: 3 }, etat: { riboFile: file, riboEnVoix: [] },
    bouts: { liste: new Map(), fileTel: [] }, lecteurNeuronal: lecteur, journalVoix() {}, blancsPourSautes() {}, lacherVoix() {}, setTimeout: () => 0, direRibosome() {} };
  vm.createContext(ctx);
  vm.runInContext(fonction(PAGE, 'sauterAuDernier') + fonction(PAGE, 'lacherPenseesJusqua') + 'this.s = sauterAuDernier; this.l = lacherPenseesJusqua;', ctx);
  return ctx;
}

test('témoin, sa vraie voix : un groupe de morceaux reliés en file est coupé pour la dernière pensée ; le morceau qui sonne va au bout, sa vraie réponse reste', async () => {
  const sim = simulateur();
  const p = (id) => ({ pensee: true, id, recu: 0, tour: 4, texte: id });
  sim.lecteur.direAudio('x1', sim.voix('x1', 5), p('x1'));            // il sonne de 0 à 5 s
  sim.lecteur.direAudio('x2', sim.voix('x2', 3), p('x2'));            // en file derrière lui
  sim.lecteur.direAudio('x3', sim.voix('x3', 3), p('x3'));
  sim.lecteur.direAudio('sa réponse', sim.voix('sa réponse', 2));       // sa vraie réponse : jamais marquée pensée
  await sim.avancer(1);
  const s = sauteur(sim.lecteur, [{ tour: 4, k: 9, texte: 'la dernière', recu: 1000 }]);   // la plus récente arrive à 1 s
  assert.strictEqual(s.s(2000), 0, 'à 2 s, rien n’a encore attendu 3 s');
  await sim.avancer(3.5);
  assert.strictEqual(s.s(3500), 2, 'à 3,5 s : x2 et x3 ont attendu, ils sont sautés');
  await sim.avancer(20);
  assert.deepStrictEqual(sim.sonne(), ['x1', 'sa réponse'], 'x1 jusqu’au bout, puis sa réponse');
  const x1 = sim.sons.find(x => x.texte === 'x1'), rep = sim.sons.filter(x => x.texte === 'sa réponse').pop();
  assert.ok(Math.abs(x1.fin - x1.debut - 5) < 1e-6 && !x1.arret, 'x1 n’est jamais coupé');
  assert.ok(Math.abs(rep.debut - (x1.fin + 0.1)) < 0.02, `sa réponse reprend juste après x1, sans le trou des sautés (${rep.debut.toFixed(2)} s)`);
  assert.deepStrictEqual(sim.segments, ['x1', 'sa réponse'], 'ce qui est retiré n’est jamais noté dit (voix-dite)');
  // sans le saut (avant) : tout le groupe sonnait, dans l'ordre
  const avant = simulateur();
  avant.lecteur.direAudio('x1', avant.voix('x1', 5), p('x1')); avant.lecteur.direAudio('x2', avant.voix('x2', 3), p('x2')); avant.lecteur.direAudio('x3', avant.voix('x3', 3), p('x3'));
  await avant.avancer(20);
  assert.deepStrictEqual(avant.sonne(), ['x1', 'x2', 'x3']);
});

test('« Sauter la suite quand tu réponds » coupe aussi un groupe déjà en file : la suite de ce tour lâchée, le morceau qui sonne finit, le tour d’après reste', async () => {
  const sim = simulateur();
  const p = (id, tour) => ({ pensee: true, id, recu: 0, tour, texte: id });
  sim.lecteur.direAudio('a1', sim.voix('a1', 4), p('a1', 7));
  sim.lecteur.direAudio('a2', sim.voix('a2', 3), p('a2', 7));
  sim.lecteur.direAudio('b1', sim.voix('b1', 2), p('b1', 9));
  await sim.avancer(1);
  const s = sauteur(sim.lecteur, []);
  const confie = { n: 3, pensees: [p('a3', 7)], dit: ['a3'], texte: 'a3' };
  s.bouts.liste.set(3, confie);
  assert.strictEqual(s.l(7), 2, 'a2 (en file), a3 (confiée) : lâchées');
  assert.strictEqual(s.bouts.liste.size, 0);
  await sim.avancer(20);
  assert.deepStrictEqual(sim.sonne(), ['a1', 'b1'], 'a1 va au bout ; le tour d’après (9) reste');
  // arreterEpissure : la suite sautée (laisserFinir) passe par là ; arrêtée net, comme avant
  const ae = fonction(PAGE, 'arreterEpissure');
  assert.match(ae, /if \(cause === 'sautee' && o\.laisserFinir && typeof lacherPenseesJusqua === 'function'\) lacherPenseesJusqua\(etat\.riboStop\);/);
});

test('branché : chaque morceau de pensée porte sa marque jusqu’au lecteur ; la première confiée à sa voix libre est marquée ; ses demandes de voix se lâchent', () => {
  const r = fonction(PAGE, 'recevoirBout');
  assert.match(r, /b\.marques = \[\.\.\.\(s\.meuble \? \[s\.pensees\[0\]\] : \[\]\), \.\.\.s\.pensees\];/, 'son meuble suit la pensée qui le suit');
  assert.match(r, /marque: b\.marques \? b\.marques\[k\] \|\| null : null/);
  assert.match(r, /if \(p\.premiere && !p\.pretA\) p\.pretA = Date\.now\(\);/, 'sa première : son attente commence quand sa voix est prête');
  assert.strictEqual((fonction(PAGE, 'direBouts').match(/lecteurNeuronal\.direAudio\(m\.texte, m\.buf, m\.marque \|\| null\)/g) || []).length, 2);
  assert.match(fonction(PAGE, 'direBouts'), /if \(typeof sauterAuDernier === 'function'\) sauterAuDernier\(\);/);
  const d = fonction(PAGE, 'direRibosome');
  assert.match(d, /const premiere = !\(lecteur && lecteur\.actif\) && !etat\.flux && /);
  assert.match(d, /recevoirBout\(\{ texte, parties, meuble, pret: true, sansMeuble: true, ribosome: true, pensees, enVoix: v \}, n, tour\);/);
  assert.match(fonction(PAGE, 'surRibosome'), /\.\.\.\(o\.k != null \? \{ k: Number\(o\.k\) \} : \{\}\)/, 'sa pensée : le paquet de son ribosome');
  assert.match(fonction(PAGE, 'voixPourTexte'), /signal: ctl\.signal/);
});

test('ses demandes de voix lâchées : celle d’une pensée sautée est annulée (le cockpit ne la calcule pas), les autres continuent', async () => {
  const i = PAGE.indexOf('const VOIX_GARDEE_MS'), j = PAGE.indexOf('function recevoirBout(');
  const demandes = [];
  const cx = { Date, Map, String, Promise, AbortController, setTimeout: (f) => f(), journalVoix() {}, envoyerNonDits() {}, idNonDit: () => 'x', bouts: { liste: new Map() },
    jeton: () => 'x', tempoVoix: () => 1, expressivitePhrase: (e) => e, sortieAilleurs: () => false, voixEpissee: () => true, voixDuTelephone: () => false,
    etat: { conversation: {}, interieur: null, reglages: {} }, lecteurSysteme: null,
    actx: { state: 'running', decodeAudioData: (ab) => Promise.resolve({ duration: 1, texte: ab.texte }) },
    fetch: (u, o) => { const d = { texte: JSON.parse(o.body).texte, signal: o.signal }; demandes.push(d);
      return new Promise((ok, ko) => { if (o.signal) o.signal.addEventListener('abort', () => ko(Object.assign(new Error('lâchée'), { name: 'AbortError' }))); }); } };
  vm.createContext(cx);
  vm.runInContext(PAGE.slice(i, j) + 'this.f = { avancerVoix, voixPourTexte, lacherVoix };', cx);
  cx.f.avancerVoix('Vas-y, ouvre.');
  cx.f.avancerVoix('Le son passe.');
  cx.f.lacherVoix(['Vas-y, ouvre.']);
  assert.strictEqual(demandes[0].signal.aborted, true, 'la sautée : lâchée');
  assert.strictEqual(demandes[1].signal.aborted, false, 'la dernière : continue');
  cx.f.avancerVoix('Vas-y, ouvre.');
  assert.strictEqual(demandes.length, 3, 'redemandée plus tard : une nouvelle demande, pas la lâchée');
});

/* (11/11, Ahmed, pendant le live : « il ne doit pas stocker sa parole au-delà de 50 % des CPU et GPU ») node --test test-lacher-charge.js
   Au-delà du seuil (lacher_charge_pct, 50 % par défaut), la page lâche tout ce qui attend de sa parole prête (sa file, ce qui est confié à sa voix, ce
   qui est en file dans son lecteur, ses pensées sur ce que joue le téléphone), sauf ce qui sonne déjà, la dernière pensée entière et sa réponse à
   papa et au live ; chaque lâcher est noté (lacher_charge) avec la charge mesurée. Témoins : sous le seuil, éteint, ou le mécanisme coupé dans la
   source, rien n'est lâché. La charge : charge.js (le Mac et le téléphone) et la page elle-même (ses tâches longues). */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Charge = require('./charge.js');

const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const fonction = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 3); };
const T = 1_800_000_000_000;
const NOMS = ['partBloquee', 'chargeDe', 'chargeMesuree', 'seuilCharge', 'fileDesParoles', 'voixEnCalcul', 'sauterAuDernier', 'lacherSousCharge'];

const pensee = (id, recu, o = {}) => ({ pensee: true, id, recu, tour: 7, texte: id, ...o });
// une page avec ce qui attend partout : sa file, une pensée confiée à sa voix, deux en file dans son lecteur (dont une qui sonne), sa réponse à papa
// en file, des pensées entendues et une réponse au live ; tout est FRAIS (moins de sauter_passe_s) : sans la charge, rien ne serait sauté
function page({ src = PAGE, reglages = {}, serveur = null, longues = [], conversation = true } = {}) {
  const journal = [], blancs = [], laches = [], retires = [];
  const marques = [
    { marque: pensee('lect-sonne', T - 900), texte: 'lect-sonne', commence: true },
    { marque: pensee('lect-attend', T - 800), texte: 'lect-attend', commence: false },
    { marque: { reponse: true, id: 'rep' }, texte: 'Oui papa, je suis là.', commence: false },   // sa vraie réponse : jamais marquée pensée
  ];
  const ctx = { Math, Number, String, Set, Map, JSON, Object, Array, Date: { now: () => T }, journal, blancs, laches, retires,
    CHARGE_SEUIL_DEFAUT: 50, CHARGE_FENETRE_MS: 10000, CHARGE_FRAICHE_MS: 20000,
    chargePage: { longues, derives: [], serveur },
    reglagesCorps: { sauter_passe: true, sauter_passe_s: 3, ...reglages },
    etat: { conversation: conversation ? {} : null,
      riboFile: [{ tour: 7, k: 1, texte: 'file-1', recu: T - 700 }, { tour: 7, k: 2, texte: 'file-2a', recu: T - 600 }, { tour: 7, k: 2, texte: 'file-2b', recu: T - 600 },
        { tour: 7, k: 3, texte: 'file-3a', recu: T - 200 }, { tour: 7, k: 3, texte: 'file-3b', recu: T - 200 }],
      entenduFile: [{ texte: 'entendu-1', reponse: false }, { texte: 'live-1', reponse: true }, { texte: 'entendu-2', reponse: false }, { texte: 'live-2', reponse: true }] },
    bouts: { liste: new Map([[1, { n: 1, t: T - 1000, buf: { duration: 2 }, pensees: [pensee('confiee', T - 1000)], dit: ['confiee'], texte: 'confiee' }]]), fileTel: [] },
    lecteurNeuronal: { enPause: false, marques: () => marques.slice(), retirerMarques: (f) => { const r = []; for (let i = marques.length - 1; i >= 0; i--) if (!marques[i].commence && f(marques[i].marque)) { retires.push(marques[i].texte); r.push(marques.splice(i, 1)[0].texte); } return r; } },
    journalVoix: (e, o) => journal.push([e, o]),
    blancsPourSautes: (l) => blancs.push(...l.map(x => x.texte)),
    lacherVoix: (l) => laches.push(...l),
    setTimeout: () => 0, direRibosome() {} };
  vm.createContext(ctx);
  vm.runInContext(NOMS.map(n => fonction(src, n)).join('\n') + 'this.lacher = lacherSousCharge; this.charge = chargeMesuree; this.seuil = seuilCharge; this.file = fileDesParoles;', ctx);
  ctx.marques = marques;
  return ctx;
}
const enCharge = (pct) => ({ t: T - 1000, mac_cpu: 12, mac_gpu: pct, tel_cpu: 27, tel_gpu: 31, tel_thermique: 20, tel_age_ms: 2000 });
const noms = (p) => ({ file: p.etat.riboFile.map(x => x.texte), confiees: [...p.bouts.liste.values()].map(b => b.texte),
  lecteur: p.marques.map(x => x.texte), entendu: p.etat.entenduFile.map(x => x.texte) });

test('au-delà de 50 % : tout ce qui attend est lâché, sauf ce qui sonne, la dernière pensée entière et ses réponses à papa et au live ; noté avec la charge', () => {
  const p = page({ serveur: enCharge(80) });
  const n = p.lacher(T);
  assert.ok(n > 0);
  const reste = noms(p);
  assert.deepStrictEqual(reste.file, ['file-3a', 'file-3b'], 'sa file : la dernière pensée, toutes ses propositions');
  assert.deepStrictEqual(reste.confiees, [], 'la pensée confiée à sa voix (fraîche : 1 s) est lâchée');
  assert.deepStrictEqual(reste.lecteur, ['lect-sonne', 'Oui papa, je suis là.'], 'ce qui sonne va au bout ; sa réponse à papa reste');
  assert.deepStrictEqual(reste.entendu, ['live-1', 'entendu-2', 'live-2'], 'ses réponses au live restent toutes ; de ses pensées entendues, la dernière');
  assert.deepStrictEqual(p.blancs.slice(0, 3), ['file-1', 'file-2a', 'file-2b'], '« … » dans son pavé');
  assert.ok(p.laches.includes('file-1') && p.laches.includes('confiee'), 'leur voix préparée, lâchée');
  const ev = p.journal.find(x => x[0] === 'lacher_charge');
  assert.ok(ev, 'un lacher_charge au journal de la voix');
  assert.strictEqual(ev[1].charge, 80);
  assert.strictEqual(ev[1].mac_gpu, 80);
  assert.strictEqual(ev[1].seuil, 50);
  assert.strictEqual(ev[1].file, 2);
  assert.strictEqual(ev[1].entendu, 1);
  assert.ok(ev[1].voix >= 2, 'la confiée et celle du lecteur');
  assert.strictEqual(p.journal.filter(x => x[0] === 'passe_saute').length, 0, 'pas un « passe_saute » : c’est la charge');
});

test('témoin : sous le seuil, éteint, réglé plus haut, hors conversation ou une mesure périmée : rien n’est lâché, rien n’est noté', () => {
  const cas = { 'sous le seuil': { serveur: enCharge(40) }, 'éteint': { serveur: enCharge(80), reglages: { lacher_charge: false } },
    'réglé à 90 %': { serveur: enCharge(80), reglages: { lacher_charge_pct: 90 } }, 'hors conversation': { serveur: enCharge(80), conversation: false },
    'mesure du Mac périmée (30 s)': { serveur: { ...enCharge(80), t: T - 30000 } }, 'aucune mesure': {} };
  for (const [nom, o] of Object.entries(cas)) {
    const p = page(o);
    assert.strictEqual(p.lacher(T), 0, nom);
    assert.strictEqual(p.etat.riboFile.length, 5, nom);
    assert.strictEqual(p.bouts.liste.size, 1, nom);
    assert.strictEqual(p.journal.length, 0, nom);
  }
});

test('témoin : le mécanisme coupé dans la source (lacherSousCharge, ou le mode forcé de sauterAuDernier), le même cas ne lâche plus rien', () => {
  const coupe = PAGE.replace('function lacherSousCharge(maintenant = Date.now()) {', 'function lacherSousCharge(maintenant = Date.now()) {\n  return 0;');
  assert.notStrictEqual(coupe, PAGE);
  const p = page({ src: coupe, serveur: enCharge(80) });
  assert.strictEqual(p.lacher(T), 0);
  assert.strictEqual(p.etat.riboFile.length, 5);
  // sauterAuDernier sans son mode forcé : la pensée confiée (fraîche) n'est plus lâchée, le reste l'est encore
  const sansForce = PAGE.replace('function sauterAuDernier(maintenant = Date.now(), force = false) {', 'function sauterAuDernier(maintenant = Date.now(), force = false) {\n  force = false;');
  assert.notStrictEqual(sansForce, PAGE);
  const q = page({ src: sansForce, serveur: enCharge(80) });
  q.lacher(T);
  assert.deepStrictEqual(noms(q).confiees, ['confiee'], 'sans le mode forcé, ce qui est frais dans sa voix attend');
});

test('la charge : la plus haute des mesures fraîches ; le téléphone compte sa marge thermique ; la page compte ses tâches longues', () => {
  const p = page({ serveur: { t: T - 1000, mac_cpu: 20, mac_gpu: 30, tel_cpu: 27, tel_gpu: 86, tel_thermique: 100, tel_age_ms: 3000 } });
  assert.deepStrictEqual(JSON.parse(JSON.stringify(p.charge(T))), { mac_cpu: 20, mac_gpu: 30, tel_cpu: 27, tel_gpu: 86, tel_thermique: 100, page: 0, max: 100 });
  const vieux = page({ serveur: { t: T - 1000, mac_cpu: 20, tel_gpu: 86, tel_age_ms: 25000 } });
  assert.deepStrictEqual(JSON.parse(JSON.stringify(vieux.charge(T))), { mac_cpu: 20, page: 0, max: 20 }, 'le téléphone muet depuis 25 s ne compte plus');
  // 6 s de tâches longues dans les 10 dernières secondes : 60 % ; une tâche à cheval sur la fenêtre ne compte que pour sa part dedans
  const longues = [[T - 1000, 3000], [T - 5000, 2000], [T - 9000, 2000]];
  const pg = page({ longues });
  assert.strictEqual(pg.charge(T).page, 60);
  assert.strictEqual(pg.charge(T).max, 60);
  const lp = page({ longues, reglages: {} });
  assert.ok(lp.lacher(T) > 0, 'sa page bloquée 60 % du temps suffit');
  assert.strictEqual(lp.journal.find(x => x[0] === 'lacher_charge')[1].page, 60);
});

test('le seuil se lit à chaud dans ses réglages, 50 % par défaut ; la file des paroles se compte pour le diagnostic', () => {
  assert.strictEqual(page().seuil(), 50);
  assert.strictEqual(page({ reglages: { lacher_charge_pct: 70 } }).seuil(), 70);
  assert.strictEqual(page({ reglages: { lacher_charge_pct: 0 } }).seuil(), 0);
  assert.strictEqual(page({ reglages: { lacher_charge_pct: null } }).seuil(), 50);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(page().file())), { file: 5, confiees: 1, telephone: 0, lecteur: 1, entendu: 2, reponses_live: 2 });
});

test('charge.js : le CPU du Mac entre deux relevés, son GPU par ioreg, le téléphone par ses processeurs ; mesuré à la demande, au plus toutes les 4 s', () => {
  const c = (user, idle) => ({ times: { user, nice: 0, sys: 0, idle, irq: 0 } });
  assert.strictEqual(Charge.cpuEntre([c(100, 900), c(100, 900)], [c(200, 950), c(130, 1020)]), 43);   // 130 occupés sur 300
  assert.strictEqual(Charge.cpuEntre(null, [c(1, 1)]), null);
  assert.strictEqual(Charge.gpuDeIoreg('"PerformanceStatistics" = {"Tiler Utilization %"=73,"Renderer Utilization %"=73,"Device Utilization %"=77,"In use system memory"=2325577728}'), 77);
  assert.strictEqual(Charge.gpuDeIoreg('rien'), null);
  // le vrai fichier du 11/11 à 09:12 (cœurs à 27 % de leur fréquence, GPU 0,86, marge thermique 1 : il bride)
  const tel = Charge.telephoneDe({ telephone: { ts: T - 2000, coeurs: [0.2717, 0.2717, 0.2717, 0.2717, 0.2717, 0.2717, 0.2275, 0.2275], gpu: 0.86, thermique: 1 } }, T);
  assert.deepStrictEqual(tel, { tel_cpu: 26, tel_gpu: 86, tel_thermique: 100, tel_age_ms: 2000 });
  let now = T, appelsIoreg = 0, releves = 0;
  const C = Charge.creer({ cpus: () => { releves++; return [c(100 * releves, 900 + 100 * releves)]; }, lireProcesseurs: () => ({}), maintenant: () => now,
    ioreg: (fini) => { appelsIoreg++; fini('"Device Utilization %"=64'); } });
  assert.strictEqual(C.vue().mac_gpu, 64);
  assert.strictEqual(C.vue().mac_cpu, null, 'un seul relevé : pas encore de CPU');
  now += 5000;
  assert.strictEqual(C.vue().mac_cpu, 50);
  assert.strictEqual(appelsIoreg, 2, 'deux mesures en 5 s : pas une de plus');
});

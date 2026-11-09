/* (09/11, Ahmed, 16:49 : « tout ce qui arrive de ses sens traité en temps réel, seconde après seconde, parallélisé » ; 18:08 : « parole après
   parole » ; 19:29-19:32 : « que tu dissocies ce que disent les autres de mes paroles » ; « reconnaître les signatures vocales en temps réel
   pendant le live, et pouvoir les enregistrer à la volée ») la chaîne d'écoute : ta voix (Azure) ne fait plus la queue derrière le téléphone,
   elle est vérifiée par l'oreille des voix ; les voix du téléphone reconnues en direct ; l'anglais à contretemps écarté ; la musique chaque
   seconde. node --test test-ecoute-temps-reel.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { EventEmitter } = require('node:events');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const TROIS = require('./trois-pistes.js');
const tranche = (src, debut, fin = '\n}\n') => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); return src.slice(i, src.indexOf(fin, i) + fin.length); };
const entre = (src, debut, fin) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); return src.slice(i, src.indexOf(fin, i)); };
const attendre = (ms) => new Promise(r => setTimeout(r, ms));

// ---- routeTranscrire, avec tout ce qu'elle appelle remplacé par des faux ----
function bac(src = SRC, o = {}) {
  const journal = [], reponses = [];
  const reglages = { stt_azure: true, voix_empreinte_azure: true, langue_papa: 'auto', langues_ecrites: false, ...(o.reglages || {}) };
  const ctx = {
    Date, Math, JSON, String, Number, Array, Object, Promise, RegExp, Buffer, setTimeout, clearTimeout, console: { error() {} },
    path, os: { tmpdir: () => '/tmp' }, process: { pid: 1 },
    fs: { writeFileSync() {}, unlink() {}, appendFileSync: (f, l) => journal.push(JSON.parse(l)), existsSync: () => false },
    j: JSON.stringify, JARVIS_VOIX_DIAGNOSTIC: '/x', ATTENTE_VOIX_SEPAREE_MS: 6000, FILTRE_VOIX_MS: 2500, DELAIS: {},
    lireCorps: async () => Buffer.alloc(64000), corpsReglages: () => reglages, pistesSeparation: () => false, separerSon: () => false,
    voixOccupee: false, transcriptionsEnAttente: 0, transcriptionsPapa: 0, suspendreVoix() {}, pomperVoix() {}, reprendreVoix() {},
    apprentissageVoix: 0, apprentissageFin: 0, apprentissageRegistre: null, instantTexte: () => '', enWav16k: async (f) => f,
    SA_VOIX_RECONNUE: () => true, oreilleDemander: async () => ({ occupee: true }), saVoixEntendue: (r) => r,
    oreilleAzure: async () => { await attendre(20); return { texte: o.texteAzure || 'Wesh fiston', langue: 'fr-FR', ms: 20 }; },
    oreilleVoix: { demander: async (d) => (o.voix ? o.voix(d) : { erreur: 'absente' }) },
    // la grande oreille (Whisper, au Mac) : le téléphone la tient 300 ms
    voixDemander: async () => { await attendre(300); return { texte: 'le téléphone joue', mots: [] }; },
    ecrireLangues: (t) => t, integrerAuFil() {}, fluxAjouter() {}, pretraiterParole: async () => null, entendreDuTelephone() {}, fluxMots() {},
    // (09/11, intégration avec vitesse) la grande oreille : la file à priorités de l'orchestrateur (papa d'abord)
    FILE_OREILLE: require('./orchestrateur.js').creerFile(), ORCHESTRE: { papaParle() {} },
    recaleMicro: (t) => t, derniereVoix: null, voixRecues: [], verdictsVoix: [], noterEtatVoix() {}, prosodiesRecues: [], tonsRecus: [],
  };
  vm.createContext(ctx);
  vm.runInContext(`${tranche(src, 'function tourDeTranscription(')}\n${tranche(src, 'function voixDuBloc(a, bloc) {')}\n`
    + `${tranche(src, 'function noterVoixDuBloc(')}\n${tranche(src, 'async function routeTranscrire(')}\nthis.route = routeTranscrire;`, ctx);
  const appel = (source) => new Promise((ok) => {
    const res = Object.assign(new EventEmitter(), { writableEnded: false, writableFinished: false, destroyed: false,
      writeHead() {}, end(x) { this.writableEnded = this.writableFinished = true; const r = JSON.parse(x); reponses.push({ source, r, t: Date.now() }); ok(r); } });
    ctx.route({ headers: { 'content-type': 'audio/wav' } }, res, '', '', { source });
  });
  return { ctx, journal, reponses, appel };
}

test('ta voix (Azure) ne fait plus la queue derrière la grande oreille du téléphone ; sans Azure, la file comme avant', async () => {
  const b = bac();
  const t0 = Date.now();
  const tel = b.appel('telephone');                      // le téléphone prend la file (Whisper, 300 ms)
  await attendre(5);
  const papa = await b.appel('');
  assert.ok(Date.now() - t0 < 200, `ta voix rendue en ${Date.now() - t0} ms, pendant que le téléphone tient la file`);
  assert.strictEqual(papa.texte, 'Wesh fiston');
  await tel;
  const s = b.journal.filter(x => x.e === 'transcription_serveur');
  assert.ok(s.some(x => x.file === false && x.attente_file_ms === 0), 'journalisé : sans file');
  // sans Azure : Whisper, au Mac, derrière le téléphone (≥ 300 ms)
  const w = bac(SRC, { reglages: { stt_azure: false } });
  const t1 = Date.now(); const tel2 = w.appel('telephone'); await attendre(5); await w.appel('');
  assert.ok(Date.now() - t1 >= 550, 'Whisper attend son tour');
  await tel2;
});

test('témoin : la file reprise avant Azure (le mécanisme coupé), ta voix attend de nouveau le téléphone', async () => {
  const coupe = SRC.replace('  if (!azurePapa && !(await prendreTour())) {', '  if (!(await prendreTour())) {');
  assert.notStrictEqual(coupe, SRC);
  const b = bac(coupe);
  const t0 = Date.now(); const tel = b.appel('telephone'); await attendre(5); await b.appel('');
  assert.ok(Date.now() - t0 >= 280, `coupé : ${Date.now() - t0} ms`);
  await tel;
});

test("une citation du live dite près du micro : marquée « [voix 2] », son verdict au tour (jamais à papa) ; l'oreille vive n'est plus sollicitée", async () => {
  const demandes = [];
  const voix = (d) => { demandes.push(d.op); return d.op === 'prevoir' ? { fenetres: 2, ms: 200 }
    : { texte: '[voix 2] ولم يكن هناك', voix: { score: 0.12, verdict: 'autre', locuteurs: ['voix 2'] }, ms: 4 }; };
  let quiVive = 0;
  const b = bac(SRC, { texteAzure: 'ولم يكن هناك', voix });
  b.ctx.oreilleDemander = async () => { quiVive++; return { occupee: true }; };
  const r = await b.appel('');
  assert.deepStrictEqual(demandes, ['prevoir', 'bloc']);
  assert.strictEqual(r.texte, '[voix 2] ولم يكن هناك');
  assert.strictEqual(r.voix.verdict, 'autre');
  assert.strictEqual(b.ctx.derniereVoix.verdict, 'autre', 'le verdict du tour le sait (sa ligne [Voix], « c’est moi » refusé)');
  assert.strictEqual(quiVive, 0);
  const l = b.journal.find(x => x.e === 'voix_papa_azure');
  assert.ok(l && l.ok && l.verdict === 'autre' && l.etiquete, 'journalisé');
  assert.strictEqual(b.ctx.DELAIS.attribution_voix_papa.length, 1, 'son délai dans fil_delais');
  // témoin : le réglage éteint, le chemin d'avant (le texte nu, à papa)
  const t = bac(SRC, { texteAzure: 'ولم يكن هناك', voix, reglages: { voix_empreinte_azure: false } });
  assert.strictEqual((await t.appel('')).texte, 'ولم يكن هناك');
});

test("l'oreille des voix en panne ou trop lente : ta voix passe quand même (le chemin d'avant)", async () => {
  const b = bac(SRC, { voix: () => ({ erreur: 'trop lente' }) });
  const r = await b.appel('');
  assert.strictEqual(r.texte, 'Wesh fiston');
  assert.ok(!r.voix);
});

test('sa propre voix reconnue par l’oreille des voix : à part (« moi »), jamais ton message', async () => {
  const b = bac(SRC, { texteAzure: 'Oui papa', voix: (d) => (d.op === 'prevoir' ? { fenetres: 1 } : { texte: '', moi: 'Oui papa', voix: { verdict: 'moi' } }) });
  const r = await b.appel('');
  assert.strictEqual(r.texte, '');
  assert.strictEqual(r.moi, 'Oui papa');
});

// ---- le client de l'oreille des voix (oreille-voix.js) ----
function fauxProcessus(repondre) {
  const p = new EventEmitter();
  p.stdout = new EventEmitter();
  p.stdin = { on() {}, write: (l) => { const d = JSON.parse(l); setTimeout(() => { const r = repondre(d); if (r) p.stdout.emit('data', JSON.stringify({ id: d.id, ...r }) + '\n'); }, d.op === 'lent' ? 50 : 1); } };
  p.kill = () => p.emit('exit');
  setTimeout(() => p.stdout.emit('data', '{"pret": true}\n'), 0);
  return p;
}
test("le client : une demande, sa réponse ; papa passe toujours, le téléphone est laissé quand trois attendent ; trop lente : rendue ; relancé s'il tombe", async () => {
  const OV = require('./oreille-voix.js');
  let lances = 0, proc = null;
  const o = OV.creer({ spawn: () => { lances++; proc = fauxProcessus((d) => (d.op === 'muet' ? null : { vu: d.op })); return proc; }, python: 'py', script: 's', delaiMs: 30 });
  const r1 = await o.demander({ op: 'bloc' });
  assert.strictEqual(r1.vu, 'bloc'); assert.ok(r1.attente_ms >= 0);
  const lents = [o.demander({ op: 'lent' }), o.demander({ op: 'lent' }), o.demander({ op: 'lent' })];
  assert.deepStrictEqual(await o.demander({ op: 'fenetres' }), { occupee: true });
  assert.strictEqual((await o.demander({ op: 'bloc' }, { priorite: true })).vu, 'bloc');
  await Promise.all(lents);
  assert.strictEqual((await o.demander({ op: 'muet' })).erreur, 'trop lente');
  proc.emit('exit');
  assert.strictEqual((await o.demander({ op: 'bloc' })).vu, 'bloc');
  assert.strictEqual(lances, 2);
});

// ---- les voix du téléphone, en direct ----
function bacTelephone() {
  const fil = [];
  const TP = TROIS.creer();
  const ctx = { Date, Math, JSON, String, Number, Array, Set, Object, TP, j: JSON.stringify, JARVIS_VOIX_DIAGNOSTIC: '/x',
    fs: { appendFileSync() {} }, fluxAjouter: (s, x, t) => fil.push({ s, x, t }) };
  vm.createContext(ctx);
  vm.runInContext(`const quiTelephone = { dernier: '', t: 0 };\n${tranche(SRC, 'function voixDuTelephoneRecues(')}\nthis.recues = voixDuTelephoneRecues;`, ctx);
  return { ctx, fil, TP };
}
test('les voix du live : à ses pistes avec leur numéro qui tient, à son fil quand ça change ; une nouvelle voix se dit nommable', () => {
  const b = bacTelephone();
  const t0 = Date.now() - 6000;
  b.ctx.recues({ fenetres: [[0, 1.5, 'voix 7'], [0.75, 2.25, 'voix 7'], [1.5, 3, 'Nora']], nouvelles: ['voix 7'], ms: 90 }, t0);
  assert.deepStrictEqual(b.fil.map(x => x.x), ['voix 7 parle (une voix nouvelle : son numéro temporaire ; voix_nommer la garde sous un nom)', 'Nora parle']);
  assert.strictEqual(b.fil[0].s, 'qui_telephone');
  assert.strictEqual(b.fil[0].t, t0, 'à son instant d’origine (son délai mesuré dans fil_delais)');
  b.ctx.recues({ fenetres: [[2.25, 3.75, 'Nora']], nouvelles: [] }, t0);
  assert.strictEqual(b.fil.length, 2, 'la même voix qui continue : rien de neuf au fil');
  // la cascade arrive plus tard avec « voix 1 » (son numéro d'un seul bloc) : la voix reconnue en direct passe avant
  b.TP.noterSeparation('telephone', t0, { fenetres: [] }, Date.now(), [], [{ nom: 'voix 1', segments: [[0, 3]] }]);
  assert.strictEqual(b.TP._locuteurs.telephone.filter(x => x.fixe).length, 4);
  const quiA = b.TP._locuteurs.telephone.filter(x => t0 + 500 >= x.t0 - 300 && t0 + 500 <= x.t1 + 300);
  assert.ok(quiA.some(x => x.qui === 'voix 1') && quiA.some(x => x.qui === 'voix 7' && x.fixe));
  assert.ok(/voix 7/.test(b.TP.bloc([{ t: t0 + 500, s: 'telephone', x: 'salam' }], t0 + 3000, 30000, 3000, 2400)), 'le mot porte la voix reconnue en direct');
  b.ctx.recues({ erreur: 'trop lente' }, t0);
  b.ctx.recues({ occupee: true }, t0);
  assert.strictEqual(b.fil.length, 2);
});
test('pendant une musique, ses pistes le savent (pas de voix neuve demandée)', () => {
  const TP = TROIS.creer();
  const t = Date.now();
  assert.strictEqual(TP.musiqueRecente('telephone', t), false);
  TP.noterAnalyse('telephone', t, { bpm: 120, tonalite: 'La mineur', voix: 'chante' });
  assert.strictEqual(TP.musiqueRecente('telephone', t), true);
  assert.match(tranche(SRC, 'function voixDuTelephoneEnDirect('), /musique = !!\(TP && typeof TP\.musiqueRecente === 'function' && TP\.musiqueRecente\('telephone'/);
});
test('le bloc du téléphone part à l’oreille des voix en même temps que ses mots vifs (même refusés par l’oreille vive)', () => {
  const r = tranche(SRC, 'async function routeVif(');
  assert.ok(r.indexOf('voixDuTelephoneEnDirect(audio, temps)') > 0 && r.indexOf('voixDuTelephoneEnDirect(audio, temps)') < r.indexOf('return repondre(429'));
});

// ---- l'anglais à contretemps (Azure) ----
function choisir() {
  const ctx = { String, Math };
  vm.createContext(ctx);
  vm.runInContext(`const ANGLAIS_MARGE = 0.15;\n${entre(SRC, 'const PETITS_MOTS_ANGLAIS', 'function choisirLangueAzure(')}${tranche(SRC, 'function choisirLangueAzure(')}\nthis.c = choisirLangueAzure; this.a = sonneAnglais;`, ctx);
  return ctx;
}
test("l'anglais à contretemps : seulement s'il bat les autres de 0,15 ; aussi quand l'arabe d'Algérie le rend", () => {
  const c = choisir();
  assert.ok(c.a("If، he's not catching her at pizza."));
  assert.ok(!c.a('Wesh fiston, tu m’entends ?') && !c.a('خلي السيئة تشوف') && !c.a('Ok papa, on y va'));
  const l = [{ langue: 'ar-DZ', texte: "If، he's not catching her at pizza.", sur: 0.62 }, { langue: 'fr-FR', texte: 'Il est pas content du tout', sur: 0.55 }];
  assert.strictEqual(c.c(l).langue, 'fr-FR');
  assert.strictEqual(c.c([{ langue: 'en-US', texte: 'Thank you so much', sur: 0.9 }, { langue: 'fr-FR', texte: 'Merci', sur: 0.6 }]).langue, 'en-US', 'vraiment plus sûr : gardé');
  assert.strictEqual(c.c([{ langue: 'en-US', texte: 'the cat is here', sur: 0.7 }], true).langue, 'en-US', 'une langue choisie : elle seule');
  // témoin : sans marge, l'anglais gagne
  const t = { String, Math }; vm.createContext(t);
  vm.runInContext(`const ANGLAIS_MARGE = 0;\n${entre(SRC, 'const PETITS_MOTS_ANGLAIS', 'function choisirLangueAzure(')}${tranche(SRC, 'function choisirLangueAzure(')}\nthis.c = choisirLangueAzure;`, t);
  assert.strictEqual(t.c(l).langue, 'ar-DZ');
});
test("la transcription rapide d'Azure absente de la région : retenue 10 min (plus un aller-retour raté par morceau)", () => {
  const f = tranche(SRC, 'async function oreilleAzure(');
  assert.match(f, /const rapideAbsente = azureRapide\.absente && Date\.now\(\) - azureRapide\.absente < 600000;/);
  assert.match(f, /!\[401, 403, 429\]\.includes\(Number\(r\.status\)\)/);
});

// ---- la musique, chaque seconde ----
test('la musique analysée chaque seconde, dite à son fil quand elle change (ou toutes les 5 s)', () => {
  assert.match(SRC, /const MUSIQUE_PAS_MS = 1000;/);
  const f = tranche(SRC, 'function recevoirSon(');
  assert.match(f, /if \(Date\.now\(\) - am\.t >= MUSIQUE_PAS_MS\) \{/);
  assert.match(f, /if \(dire !== am\.dit \|\| Date\.now\(\) - am\.ditT >= 5000\) \{/);
});

// ---- (09/11, audit des boutons) ecoute_francais retiré ----
test('ecoute_francais : plus dans ses réglages ni accepté (langue_papa le remplace depuis le 08/11)', () => {
  const f = tranche(SRC, 'function corpsReglages() {');
  const ctx = { lireJson: () => ({ ecoute_francais: true }), CORPS_INTERVALLES: [120], CORPS_REGLAGES: '/x' };
  vm.createContext(ctx); vm.runInContext(`${f}\nthis.r = corpsReglages();`, ctx);
  assert.ok(!('ecoute_francais' in ctx.r));
  assert.strictEqual(ctx.r.langue_papa, 'auto');
  assert.ok(!/'ecoute_francais'/.test(SRC));
  assert.strictEqual(ctx.r.voix_empreinte_azure, true);
  assert.strictEqual(ctx.r.voix_telephone_direct, true);
  assert.strictEqual(ctx.r.decoupe_entendu, 'point');
});

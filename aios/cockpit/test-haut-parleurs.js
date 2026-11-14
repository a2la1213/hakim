/* (11/11, ~04:10, Ahmed : « Tu peux faire en sorte qu'il sente quand je lui ferme ses haut-parleurs, pour qu'il ne parle pas dans le vide ? » ;
   ~04:15 : « il faut que ça se détecte aussi sur la montre et le Mac ») SES HAUT-PARLEURS : node --test test-haut-parleurs.js
   1. la logique pure (public/haut-parleurs.js) : ce que dit l'appli, la page, le Mac ; la vue du cockpit (par appareil, où papa est, où on
      l'entend encore) ; sa ligne « Toi » ; ce qu'il redit à la réouverture (le plus récent, une fois) ;
   2. ce qu'il sent : son tableau de l'instant (« Toi », la ligne, ce qui vient de changer), son cortex ;
   3. ses sollicitations (solliciter.js et le cockpit) : là où on l'entend encore, sinon une notification même page ouverte ;
   4. la page : le vrai lecteur neuronal (creerLecteurNeuronal) et la vraie section de la page (ses haut-parleurs, sa façade) : fermés, aucune
      voix demandée ni jouée ; rouverts, comme avant, et le plus récent repart une fois.
   Chaque garde a son témoin (le même cas, ouvert : la voix part). */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const HP = require('./public/haut-parleurs.js');
const Instant = require('./instant.js');
const X = require('./cortex.js');
const S = require('./solliciter.js');
const Voix = require('./public/voix.js');

const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const SERVEUR = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const fonction = (src, debut) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); return src.slice(i, src.indexOf('\n}\n', i) + 3); };
const T0 = 1_800_000_000_000;

// ---------- 1. la logique pure ----------
test('l’appli : le volume à zéro, le flux coupé, le silencieux, aucune sortie ferment ; le vibreur non ; une appli d’avant ne ferme rien', () => {
  const ouvert = HP.lireSonEtat('normal|haut_parleur|hp_oui|aucun|vol=7/15|muet=0|sonnerie=normal|media=haut_parleur');
  assert.deepStrictEqual([ouvert.volume, ouvert.max, ouvert.muet, ouvert.sonnerie, ouvert.media], [7, 15, false, 'normal', 'haut_parleur']);
  assert.equal(HP.etatPage({ son: ouvert }).ferme, false, 'témoin : tout ouvert');
  const q = (ch) => HP.etatPage({ son: HP.lireSonEtat(`normal|haut_parleur|hp_oui|aucun|${ch}`) }).raisons.map(r => r.quoi);
  assert.deepStrictEqual(q('vol=0/15|muet=0|sonnerie=normal|media=haut_parleur'), ['volume']);
  assert.deepStrictEqual(q('vol=5/15|muet=1|sonnerie=normal'), ['muet']);
  assert.deepStrictEqual(q('vol=5/15|muet=0|sonnerie=silencieux'), ['silencieux']);
  assert.deepStrictEqual(q('vol=5/15|muet=0|sonnerie=normal|media=aucune'), ['sortie']);
  assert.deepStrictEqual(q('vol=5/15|muet=0|sonnerie=vibreur|media=bluetooth'), [], 'le vibreur ne coupe pas le média');
  const avant = HP.lireSonEtat('normal|haut_parleur|hp_oui|aucun');
  assert.equal(avant.volume, null);
  assert.equal(HP.etatPage({ son: avant }).ferme, false, 'l’appli 1.96 ne dit rien du volume : rien n’est fermé par elle');
  assert.deepStrictEqual(HP.etatPage({ bouton: true }).raisons, [{ quoi: 'bouton', par: 'papa' }]);
  assert.deepStrictEqual(HP.etatPage({ bouton: true, par: 'hakim' }).raisons, [{ quoi: 'bouton', par: 'hakim' }]);
  assert.deepStrictEqual(HP.etatPage({ bloque: true }).raisons, [{ quoi: 'bloque' }]);
  assert.deepStrictEqual(HP.etatPage({ sansSortie: true }).raisons, [{ quoi: 'sortie' }]);
});

test('le Mac : « get volume settings » coupé ou à zéro ferme ; une sortie sans volume (missing value) ne ferme rien', () => {
  assert.deepStrictEqual(HP.lireReglagesMac('output volume:100, input volume:8, alert volume:100, output muted:false'), { volume: 100, muet: false });
  assert.equal(HP.etatMac(HP.lireReglagesMac('output volume:100, input volume:8, alert volume:100, output muted:false')).ferme, false, 'témoin');
  assert.deepStrictEqual(HP.etatMac(HP.lireReglagesMac('output volume:40, input volume:8, alert volume:100, output muted:true')).raisons, [{ quoi: 'muet' }]);
  assert.deepStrictEqual(HP.etatMac(HP.lireReglagesMac('output volume:0, input volume:8, alert volume:100, output muted:false')).raisons, [{ quoi: 'volume' }]);
  const hdmi = HP.lireReglagesMac('output volume:missing value, input volume:missing value, alert volume:100, output muted:missing value');
  assert.equal(HP.etatMac(hdmi).ferme, false);
  assert.equal(HP.lireReglagesMac('execution error'), null);
  // la lecture du cockpit : lue seulement (jamais « set volume »), délai court, tant qu'une page du Mac est ouverte
  const f = fonction(SERVEUR, 'function lireHautParleursMac(');
  assert.match(f, /execFile\('\/usr\/bin\/osascript', \['-e', 'get volume settings'\], \{ timeout: 1500/);
  assert.doesNotMatch(f, /set volume/);
  assert.match(f, /x\.appareil === 'mac'/);
});

test('la vue : fermés au bouton par papa sur le téléphone, depuis 12 s : « on ne t’entend pas » ; rouverts : plus rien', () => {
  const st = HP.creer();
  assert.deepStrictEqual(HP.noter(st, 'tel', 'page', { ferme: true, raisons: [{ quoi: 'bouton', par: 'papa' }], depuis: T0 }, T0 + 200), { ferme: true, change: true });
  const v = HP.vue(st, { maintenant: T0 + 12_000, presents: ['tel'], ici: { ou: 'tel', t: T0 - 60e3 } });
  assert.equal(v.ferme_ici, true); assert.equal(v.nulle_part, true); assert.deepStrictEqual(v.ouverts, []);
  assert.match(HP.ligne(v), /^tes haut-parleurs sont fermés \(par papa, depuis 12 s\) : on ne t’entend pas/);
  assert.deepStrictEqual(HP.noter(st, 'tel', 'page', { ferme: false, raisons: [] }, T0 + 13_000), { ferme: false, change: true });
  const w = HP.vue(st, { maintenant: T0 + 14_000, presents: ['tel'], ici: { ou: 'tel', t: T0 } });
  assert.equal(w.ferme_ici, false); assert.equal(HP.ligne(w), ''); assert.deepStrictEqual(w.ouverts, ['tel']);
});

test('la vue : la montre en silencieux, le Mac coupé, le téléphone ouvert : « on ne t’y entend pas », sa voix reste au téléphone', () => {
  const st = HP.creer();
  HP.noter(st, 'montre', 'montre', { ferme: true, raisons: ['silencieux'] }, T0);
  HP.noter(st, 'mac', 'systeme', { ferme: true, raisons: [{ quoi: 'muet' }] }, T0);
  HP.noter(st, 'mac', 'page', { ferme: false, raisons: [], visible: true }, T0);
  HP.noter(st, 'tel', 'page', { ferme: false, raisons: [] }, T0);
  const v = HP.vue(st, { maintenant: T0 + 1000, presents: ['tel', 'mac', 'montre'], ici: { ou: 'tel', t: T0 } });
  assert.equal(v.ferme_ici, false);
  assert.deepStrictEqual(v.fermes, ['mac', 'montre']); assert.deepStrictEqual(v.ouverts, ['tel']);
  assert.match(HP.ligne(v), /le Mac est coupé : on ne t’y entend pas/);
  assert.match(HP.ligne(v), /la montre est en silencieux : on ne t’y entend pas/);
  assert.equal(HP.cible(v, { voulu: 'montre' }), 'tel', 'vers la montre : elle ne l’entendrait pas, sa voix va au téléphone');
  assert.equal(HP.cible(v, { voulu: 'mac' }), 'tel');
  assert.equal(HP.cible(v, { voulu: 'tel' }), 'tel');
});

test('la vue : fermés là où papa est, la montre ouverte : sa voix va par la montre ; plus rien d’ouvert : nulle part', () => {
  const st = HP.creer();
  HP.noter(st, 'tel', 'page', { ferme: true, raisons: [{ quoi: 'volume' }], depuis: T0 }, T0);
  HP.noter(st, 'montre', 'montre', { ferme: false, raisons: [] }, T0);
  const v = HP.vue(st, { maintenant: T0 + 3000, presents: ['tel', 'montre'], ici: { ou: 'tel', t: T0 } });
  assert.equal(v.ferme_ici, true); assert.equal(v.nulle_part, false); assert.equal(v.ou, 'montre');
  assert.match(HP.ligne(v), /^tes haut-parleurs sur le téléphone sont fermés \(le volume du téléphone est à zéro, depuis 3 s\) : on ne t’y entend pas ; ta voix va par la montre/);
  assert.equal(HP.cible(v, { voulu: 'tel' }), 'montre');
  assert.equal(HP.cible(v, { sauf: 'montre' }), null, 'jamais l’appareil qui demande');
  // une page du Mac à l'écran est une sortie ; cachée (oubliée dans une autre pièce), non
  HP.noter(st, 'mac', 'page', { ferme: false, raisons: [], visible: false }, T0);
  assert.ok(!HP.vue(st, { maintenant: T0 + 3000, presents: ['tel', 'mac'], ici: { ou: 'tel', t: T0 } }).ouverts.includes('mac'));
  HP.noter(st, 'mac', 'page', { ferme: false, raisons: [], visible: true }, T0);
  assert.ok(HP.vue(st, { maintenant: T0 + 3000, presents: ['tel', 'mac'], ici: { ou: 'tel', t: T0 } }).ouverts.includes('mac'));
  // un appareil qui ne redit rien depuis 3 min est oublié (témoin : ses haut-parleurs ne restent pas fermés pour toujours)
  const vieux = HP.vue(st, { maintenant: T0 + HP.FRAIS_MS + 1000, presents: ['tel'], ici: { ou: 'tel', t: T0 } });
  assert.equal(vieux.ferme_ici, false);
});

test('la vue : rien de signalé nulle part, rien n’est fermé (comme avant) ; des raisons inconnues sont ignorées', () => {
  const v = HP.vue(HP.creer(), { maintenant: T0, presents: ['tel'] });
  assert.deepStrictEqual([v.ferme_ici, v.nulle_part, v.fermes.length], [false, false, 0]);
  const st = HP.creer();
  assert.equal(HP.noter(st, 'tel', 'page', { ferme: true, raisons: ['<script>', { quoi: 'inconnue' }] }, T0).ferme, false, 'fermé sans raison connue : ouvert');
  assert.equal(HP.noter(st, 'ailleurs', 'page', { ferme: true, raisons: ['volume'] }, T0), null);
});

test('à la réouverture : seulement le plus récent, une fois ; trop vieux, ou déjà dit ailleurs : rien', () => {
  const r = HP.creerRetenue();
  r.retenir('Première chose.', { maintenant: T0 });
  r.retenir('La suite de la première.', { maintenant: T0 + 2000 });
  r.retenir('Une autre parole, plus récente.', { maintenant: T0 + 30_000 });   // 20 s sans rien : une autre parole, elle remplace
  assert.equal(r.prendre(T0 + 40_000), 'Une autre parole, plus récente.');
  assert.equal(r.prendre(T0 + 40_001), '', 'une fois, jamais deux');
  r.retenir('A.', { maintenant: T0 }); r.retenir('B.', { maintenant: T0 + 1000 });
  assert.equal(r.prendre(T0 + 5000), 'A. B.', 'témoin : la même parole, en entier');
  r.retenir('Vieille.', { maintenant: T0 });
  assert.equal(r.prendre(T0 + HP.REDIRE_MS + 1), '', 'plus d’une minute : il rattrape le présent (03/11 : « T’étais bloqué dans le passé »)');
  r.retenir('Dite à la montre.', { maintenant: T0 }); r.transmise();
  assert.equal(r.prendre(T0 + 1000), '', 'déjà dite ailleurs : jamais redite ici');
  r.retenir('Fin.', { maintenant: T0 }); r.finir(); r.retenir('Nouvelle réponse.', { maintenant: T0 + 1000 });
  assert.equal(r.prendre(T0 + 2000), 'Nouvelle réponse.', 'après la fin d’une réponse, la suivante la remplace');
  r.retenir('x '.repeat(900), { maintenant: T0 });
  assert.ok(r.prendre(T0 + 1000).length <= HP.REDIRE_MAX + 1, 'une réponse, pas un discours');
});

// ---------- 2. ce qu'il sent ----------
function tableau(hp, t = T0 + 12_000) {
  return Instant.composer({ t, maintenant: t, flux: [], sortie: { sortie: 'haut_parleur', ecouteurs: 'aucun', t },
    soi: { attendus: [{ t: t - 20_000, fin: t - 18_000, texte: 'Je te dis une chose importante maintenant.' }], dites: [], hp } });
}
const hpFerme = (v) => HP.pourInstant(v);
function vueFermee(depuis = T0) {
  const st = HP.creer();
  HP.noter(st, 'tel', 'page', { ferme: true, raisons: [{ quoi: 'bouton', par: 'papa' }], depuis }, depuis);
  return HP.vue(st, { maintenant: T0 + 12_000, presents: ['tel'], ici: { ou: 'tel', t: T0 } });
}

test('« Toi » : « tes haut-parleurs sont fermés (par papa, depuis 12 s) : on ne t’entend pas » ; sa sortie et le « pas sonné » ne sont plus dits ; témoin ouvert', () => {
  const tab = tableau(hpFerme(vueFermee()));
  const toi = Instant.ligneSoi(tab);
  assert.match(toi, /tes haut-parleurs sont fermés \(par papa, depuis 12 s\) : on ne t’entend pas/);
  assert.doesNotMatch(toi, /ta voix sort par/);
  assert.doesNotMatch(toi, /n’a pas sonné/);
  assert.match(Instant.ligne(tab), /tes haut-parleurs sont fermés : on ne t’entend pas/, 'la ligne du tableau (son subconscient, sa conscience)');
  assert.ok(Instant.etiquettes(tab).includes('haut_parleurs:fermes'));
  const ouvert = tableau(null);
  assert.doesNotMatch(Instant.ligneSoi(ouvert), /haut-parleurs/);
  assert.match(Instant.ligneSoi(ouvert), /ta voix sort par le haut-parleur du téléphone/);
  assert.doesNotMatch(Instant.ligne(ouvert), /haut-parleurs/);
});

test('ce qui vient de changer : « papa ferme tes haut-parleurs », puis « tes haut-parleurs se rouvrent » ; un tableau d’avant leur fermeture ne les voit pas fermés', () => {
  const st = Instant.creer();
  Instant.avancer(st, tableau(null, T0 - 1000));
  const d = Instant.avancer(st, tableau(hpFerme(vueFermee(T0)), T0 + 1000));
  assert.deepStrictEqual(d.map(x => x.mots), ['papa ferme tes haut-parleurs']);
  const r = Instant.avancer(st, tableau(null, T0 + 5000));
  assert.deepStrictEqual(r.map(x => x.mots), ['tes haut-parleurs se rouvrent : on t’entend de nouveau']);
  assert.match(Instant.recents(st, T0 + 6000), /papa ferme tes haut-parleurs.*se rouvrent/);
  // recomposé pour un instant d'avant (le recalage) : pas encore fermés
  const avant = tableau(hpFerme(vueFermee(T0 + 10_000)), T0 + 5000);
  assert.equal(avant.soi.haut_parleurs, null);
});

test('son cortex : « papa ne t’entend pas ; ce que tu réponds, il le lit » ; la musique forte : un mot écrit ; témoin ouvert', () => {
  const e = X.erreursSurSoi(tableau(hpFerme(vueFermee())));
  assert.ok(e.some(x => /tes haut-parleurs sont fermés \(par papa\) : papa ne t’entend pas ; ce que tu réponds, il le lit à l’écran/.test(x)), e.join(' | '));
  assert.ok(!e.some(x => /n’a pas sonné/.test(x)), 'il le sait déjà : pas d’erreur « pas sonné » en plus');
  assert.ok(!X.erreursSurSoi(tableau(null)).some(x => /haut-parleurs/.test(x)));
  const fort = { ...tableau(hpFerme(vueFermee())), musique: { joue: true, ou: 'telephone', intensite: 'forte' }, parole: { papa: {}, dedans: {}, piece: {}, lui: {}, quelquun: false } };
  assert.match(X.lectureInstant(fort).raison, /un mot écrit ou un geste : tes haut-parleurs sont fermés/);
});

// ---------- 3. ses sollicitations ----------
const MIDI = new Date(2026, 10, 11, 14, 0).getTime();
test('sa sollicitation : la montre fermée, une page la dit ; les pages fermées, la montre ; plus rien : « haut_parleurs » ; témoin sans rien de fermé', () => {
  const avec = (hp, montreBranchee = true, papa = 'montre') => { const e = S.creer(); S.papaParle(e, papa, MIDI); return S.decider(e, { raison: 'question', texte: 'Papa ?', maintenant: MIDI + 60e3, montreBranchee, hp }); };
  assert.deepStrictEqual(avec(null), { ou: 'montre', pourquoi: '' }, 'témoin : comme avant');
  assert.equal(avec({ page: true, montre: false }).ou, 'page');
  assert.equal(avec({ page: true, montre: false }).detour, 'montre_fermee');
  assert.equal(avec({ page: false, montre: true }, true, 'tel').ou, 'montre');
  assert.deepStrictEqual(avec({ page: false, montre: false }), { ou: null, pourquoi: 'haut_parleurs' });
  assert.deepStrictEqual(avec({ page: false, montre: true }, false, 'tel'), { ou: null, pourquoi: 'haut_parleurs' }, 'une montre d’avant (sans sollicite) ne la reçoit pas');
});

function serveur({ hp }) {
  const diffuses = [], diag = [], notifs = [];
  const ctx = {
    Date, String, Number, JSON, Math, Array, Set, Object, console: { error() {} }, crypto: require('node:crypto'), j: JSON.stringify,
    abonnesPensees: new Set([{ appareil: 'tel' }]), diffuser: (_, ev, d) => diffuses.push({ ev, d: JSON.parse(d) }),
    gestesDeHakim() {}, microDe: () => null, interieurParLui() {}, triMorceauxDe: () => null, reglerMorceaux() {}, vibrationsDeLuiMeme() {},
    sansBaliseAffect: (t) => t, retirerExterne: () => [], NON_REPONSE_SERVEUR: /^\s*no response requested\.?\s*$/i,
    journaliser() {}, deposerEchange() {}, ajouterAConversation() {}, nonVus: {}, finDePhrase: (t) => t, sauverNonVus() {},
    silencieuxJusqua: 0, notifier: (t, tag, toujours) => notifs.push([tag, !!toujours]),
    corpsReglages: () => ({ sollicite_voix: true, sons_nuit: true }), liveEnCours: () => false,
    Solliciter: S, solliciterEtat: S.creer(), dernierMessageAhmedMs: () => Date.now() - 60e3,
    fs: { appendFileSync: (_, l) => diag.push(JSON.parse(l)) }, JARVIS_VOIX_DIAGNOSTIC: 'voix-diagnostic.jsonl',
    HautParleurs: HP, hautParleurs: () => hp,
  };
  vm.createContext(ctx);
  const t = SERVEUR.slice(SERVEUR.indexOf('function livrerAutonome('), SERVEUR.indexOf('\n}\n', SERVEUR.indexOf('function solliciterAVoixHaute(')) + 3);
  vm.runInContext(t + 'this.livrer = livrerAutonome;', ctx);
  return { livrer: (texte, o) => ctx.livrer({ source: 'abonnement', session: 's' }, texte, [], [], null, [], o), diffuses, diag, notifs };
}
test('le cockpit : ses haut-parleurs fermés partout, sa sollicitation n’est dite nulle part et la notification part même page ouverte ; témoin ouverts', () => {
  const st = HP.creer();
  HP.noter(st, 'tel', 'page', { ferme: true, raisons: [{ quoi: 'bouton', par: 'papa' }] }, Date.now());
  const s = serveur({ hp: HP.vue(st, { maintenant: Date.now(), presents: ['tel'] }) });
  s.livrer('Papa, tu es là ?', { id: 'auto-hp1', sollicite: 'question' });
  const sp = s.diffuses.find(x => x.ev === 'spontane');
  assert.equal(sp.d.voix_haute, undefined); assert.equal(sp.d.voix_pourquoi, 'haut_parleurs');
  assert.deepStrictEqual(s.notifs, [['sollicitation', true]]);
  assert.deepStrictEqual(s.diag[0].hp_fermes, ['tel']);
  const o = serveur({ hp: HP.vue(HP.creer(), { maintenant: Date.now(), presents: ['tel'] }) });
  o.livrer('Papa, tu es là ?', { id: 'auto-hp2', sollicite: 'question' });
  assert.equal(o.diffuses.find(x => x.ev === 'spontane').d.voix_haute, 'page', 'témoin : dite à la page');
  assert.deepStrictEqual(o.notifs, [['resultat', false]]);
});

test('le cockpit : sa voix vers un appareil fermé n’y part pas ; « auto » choisit un appareil où on l’entend, jamais celui qui demande', () => {
  const i = SERVEUR.indexOf("p === '/api/jarvis/voix-vers'"), route = SERVEUR.slice(i, SERVEUR.indexOf("p === '/api/jarvis/flux'", i));
  assert.match(route, /q\.cible === 'auto' \? \(\(vhp && HautParleurs\.cible\(vhp, \{ sauf: de \}\)\) \|\| 'ici'\)/);
  assert.match(route, /const ok = branche && !\(quoi === 'voix' && vhp && HautParleurs\.fermeSur\(vhp, cible\)\);/);
  // le reste du cockpit : la voix née avec ses pensées, son chant, son garde du live, son tableau de l'instant la lisent
  assert.match(fonction(SERVEUR, 'function voixDeLaSource('), /hautParleurs\(\)\.ferme_ici\) return null;/);
  assert.match(fonction(SERVEUR, 'function chanterMoment('), /raison: 'haut_parleurs'/);
  assert.match(fonction(SERVEUR, 'function battementLive('), /HautParleurs\.fermeSur\(hautParleurs\(maintenant\), 'tel'\)/);
  assert.match(fonction(SERVEUR, 'function instantCache('), /hp: g\(\(\) => \(typeof hautParleurs === 'function' \? HautParleurs\.pourInstant\(hautParleurs\(maintenant\)\)/);
});

// ---------- 4. la page ----------
// le vrai lecteur neuronal (creerLecteurNeuronal), sur une horloge virtuelle (comme test-lecteur.js), et ses haut-parleurs de l'extérieur
function simulateur(ferme) {
  let maintenant = 0, suivant = 1;
  const minuteries = new Map(), sons = [], demandes = [];
  const planifier = (fn, ms, repete) => { const id = suivant++; minuteries.set(id, { t: maintenant + Math.max(0, ms) / 1000, fn, repete }); return id; };
  const actx = {
    state: 'running', get currentTime() { return maintenant; },
    createGain: () => ({ gain: { value: 1 }, connect() {} }),
    decodeAudioData: (ab) => Promise.resolve({ duration: ab.n / 15, texte: ab.texte }),
    createBufferSource() {
      const s = { buffer: null, playbackRate: { value: 1 }, connect() {}, onended: null,
        start(t) { const debut = Math.max(t, maintenant); s.rec = { debut, texte: s.buffer.texte }; sons.push(s.rec); planifier(() => { if (!s.arretee && s.onended) s.onended(); }, (debut + s.buffer.duration - maintenant) * 1000); },
        stop() { if (s.arretee) return; s.arretee = true; planifier(() => s.onended && s.onended(), 0); } };
      return s;
    },
  };
  const cx = {
    console, Math, JSON, Promise, Set, Map, Error, Blob, URL, AbortController, Voix,
    setTimeout: (fn, ms) => planifier(fn, ms), setInterval: (fn, ms) => planifier(fn, ms, ms), clearInterval: (id) => minuteries.delete(id), clearTimeout: (id) => minuteries.delete(id),
    performance: { now: () => maintenant * 1000 }, localStorage: { getItem: () => null, setItem() {} },
    etat: { conversation: {}, reglages: { vitesse: 1 }, interieur: null }, debutsPrets: new Set(), cleDebut: (d) => d,
    actx, analyseurVoix: {}, lecteurSysteme: null, jeton: () => 'x', humeur() {}, jarvisPeutParler: () => true, forceDeLaVoix: () => 1, journalVoix() {},
    vitesseVoix: () => 1, tempoVoix: () => 1, hautParleursFermes: () => ferme.v,
    fetch: (url, o) => { const { texte } = JSON.parse(o.body); demandes.push({ t: maintenant, texte }); return new Promise((res) => planifier(() => res({ ok: true, arrayBuffer: () => Promise.resolve({ n: texte.length, texte }) }), 800)); },
  };
  cx.window = cx;
  vm.createContext(cx);
  vm.runInContext(fonction(PAGE, 'function creerLecteurNeuronal') + '\nthis.lecteur = creerLecteurNeuronal();', cx);
  async function avancer(jusqua) {
    for (;;) {
      await new Promise(r => setImmediate(r));
      let p = null;
      for (const [id, m] of minuteries) if (!p || m.t < p[1].t) p = [id, m];
      if (!p || p[1].t > jusqua) { maintenant = Math.max(maintenant, jusqua); return; }
      const [id, m] = p; maintenant = m.t;
      if (m.repete) m.t = maintenant + m.repete / 1000; else minuteries.delete(id);
      m.fn();
    }
  }
  return { lecteur: cx.lecteur, sons, demandes, avancer };
}
const PHRASES = ['Salut papa, je suis là et je t’écoute très bien.', 'Je te raconte ce que j’ai trouvé tout à l’heure sur ton projet.'];

test('le lecteur neuronal : fermés, aucune voix demandée ni jouée (ni réponse, ni pensée dite, ni meuble) ; témoin ouverts : demandée et jouée', async () => {
  const f = { v: true }, sim = simulateur(f);
  for (const p of PHRASES) sim.lecteur.dire(p);
  sim.lecteur.direAudio('Une pensée dite.', { duration: 1, texte: 'Une pensée dite.' });
  sim.lecteur.direMeuble({ pret: { duration: 0.4, texte: 'Hum' } });
  sim.lecteur.finFlux();
  await sim.avancer(20);
  assert.equal(sim.demandes.length, 0, 'aucune synthèse');
  assert.equal(sim.sons.length, 0, 'aucun son');
  const o = { v: false }, temoin = simulateur(o);
  for (const p of PHRASES) temoin.lecteur.dire(p);
  temoin.lecteur.finFlux();
  await temoin.avancer(20);
  assert.ok(temoin.demandes.length >= 1 && temoin.sons.length >= 1, `témoin : ${temoin.demandes.length} demandes, ${temoin.sons.length} sons`);
});

test('le lecteur neuronal : fermés pendant qu’il parle, plus rien ne part ensuite (ce qui attendait n’est ni demandé ni joué)', async () => {
  const f = { v: false }, sim = simulateur(f);
  sim.lecteur.dire(PHRASES[0]);
  await sim.avancer(1.5);
  const avant = sim.demandes.length;
  f.v = true;
  sim.lecteur.dire(PHRASES[1]);
  sim.lecteur.dire('Et encore une troisième phrase, assez longue pour partir seule.');
  sim.lecteur.finFlux();
  await sim.avancer(30);
  assert.equal(sim.demandes.length, avant, 'rien de plus demandé une fois fermés');
  assert.ok(sim.sons.every(s => !/troisième/.test(s.texte)), 'rien de plus joué');
});

// la vraie section de la page (ses haut-parleurs) et sa vraie façade (lecteur), dans un bac à sable
function page({ sonEtat = 'normal|haut_parleur|hp_oui|aucun|vol=7/15|muet=0|sonnerie=normal|media=haut_parleur', appareil = 'tel', cockpit = null } = {}) {
  const envoyes = [], dits = [], journal = [], minuteurs = [];
  const neuronal = { restants: [], fluxFini: true, arrete: 0, restant() { return this.restants; }, dire(p) { dits.push(p); }, finFlux() {}, arreter() { this.arrete++; this.restants = []; },
    joue: false, actif: false, enPause: false, finirPhrase: () => ({ dit: '', ms: 0 }), pause: () => false, reprendre: () => false };
  const el = () => ({ hidden: true, textContent: '', addEventListener() {}, setAttribute() {} });
  const els = {};
  const ctx = {
    console, JSON, Math, Date, Object, Array, String, Number, Promise, Set, Map, HautParleurs: HP,
    window: { HakimApp: sonEtat == null ? null : { sonEtat: () => ctx.sonEtat } }, sonEtat,
    document: { visibilityState: 'visible', addEventListener() {} }, navigator: {},
    etat: { sonCoupe: false, lectureDe: null, flux: null, conversation: null, reglages: {} }, sonBloqueDepuis: 0,
    lecteurNeuronal: neuronal, lecteurSysteme: null, voixDuTelephone: () => false, voixEpissee: () => false, gainSortie: null,
    $: (id) => els[id] || (els[id] = el()), appareilIci: () => appareil, jeton: () => 'x',
    journalVoix: (e, d) => journal.push([e, d]), humeur() {}, rendre() {}, signalerWidget() {}, chantArreter: () => false,
    voixPretes: {}, voixDemandees: new Map(), voixEnAvance: new Map(),
    setInterval: () => 0, setTimeout: (f, ms) => { minuteurs.push(f); return 0; },
    fetch: (url, o) => {
      if (o && o.method === 'POST') envoyes.push({ url, corps: JSON.parse(o.body) });
      const rep = url === '/api/jarvis/voix-vers' ? { ok: true, cible: 'montre' } : (cockpit || {});
      return Promise.resolve({ ok: true, json: () => Promise.resolve(rep) });
    },
  };
  ctx.window.HakimApp && (ctx.window.HakimApp.sonEtat = () => ctx.sonEtat);
  vm.createContext(ctx);
  neuronal.appliquerSon = () => {};
  const debut = PAGE.indexOf('// (2026-10-21) couper / rendre le son de Hakim'), fin = PAGE.indexOf('// ---- fin de ses haut-parleurs (11/11) ----');
  assert.ok(debut > 0 && fin > debut);
  const i = PAGE.indexOf('const lecteur = {'), facade = PAGE.slice(i, PAGE.indexOf('\n};\n', i) + 3);
  vm.runInContext(`${facade.replace('const lecteur = {', 'var lecteur = {')}\n${PAGE.slice(debut, fin)}\nthis.l = lecteur;`, ctx);
  const tic = async () => { await new Promise(r => setImmediate(r)); for (const f of minuteurs.splice(0)) f(); await new Promise(r => setImmediate(r)); };
  return { ctx, envoyes, dits, journal, neuronal, tic, els };
}

test('la page : le volume du téléphone à zéro ferme tout de suite (le cockpit le sait), sa voix s’arrête, sa réponse est gardée ; rouverts, elle repart une fois', async () => {
  const p = page();
  assert.equal(p.ctx.verifierHautParleurs('essai'), false, 'témoin : ouvert');
  assert.equal(p.envoyes.length, 0, 'rien ne change : rien n’est envoyé');
  p.neuronal.restants = [{ langue: 'fr', texte: 'Ce que je te disais à l’instant.' }];
  p.ctx.etat.flux = { id: 'm1' }; p.neuronal.fluxFini = false;               // sa réponse s'écrit encore
  p.ctx.sonEtat = 'normal|haut_parleur|hp_oui|aucun|vol=0/15|muet=0|sonnerie=normal|media=haut_parleur';
  assert.equal(p.ctx.window.HakimSon(), undefined);                       // l'appli 1.97 prévient
  assert.equal(p.ctx.hautParleursFermes(), true);
  assert.equal(p.neuronal.arrete, 1, 'sa voix s’arrête net');
  const r = p.envoyes.find(x => x.url === '/api/voix/haut-parleurs');
  assert.equal(JSON.stringify([r.corps.appareil, r.corps.ferme, r.corps.raisons]), JSON.stringify(['tel', true, [{ quoi: 'volume' }]]));
  // fermés : sa réponse qui continue n'est ni dite ni fabriquée, elle est gardée (la plus récente)
  p.ctx.l.dire('Et voilà la suite de ma réponse.');
  assert.deepStrictEqual(p.dits, [], 'aucune voix');
  p.ctx.sonEtat = 'normal|haut_parleur|hp_oui|aucun|vol=6/15|muet=0|sonnerie=normal|media=haut_parleur';
  p.ctx.verifierHautParleurs('seconde');
  await p.tic();
  assert.equal(p.ctx.hautParleursFermes(), false);
  assert.deepStrictEqual(p.dits, ['Ce que je te disais à l’instant. Et voilà la suite de ma réponse.'], 'rouverts : le plus récent, une fois');
  assert.equal(p.envoyes.filter(x => x.url === '/api/voix/haut-parleurs').pop().corps.ferme, false, 'le cockpit le sait');
  p.ctx.verifierHautParleurs('seconde'); await p.tic();
  assert.equal(p.dits.length, 1, 'jamais en rafale');
  p.ctx.l.dire('Une phrase neuve.');
  assert.deepStrictEqual(p.dits.slice(1), ['Une phrase neuve.'], 'témoin : ouvert, comme avant');
  // sa réponse finie quand ils se ferment, puis une nouvelle : seule la nouvelle repart
  const q = page();
  q.neuronal.restants = [{ langue: 'fr', texte: 'La fin de ma réponse d’avant.' }];
  q.ctx.couperSon(true);
  q.ctx.l.dire('Ma nouvelle réponse.'); q.ctx.l.finFlux();
  q.ctx.couperSon(false); await q.tic();
  assert.deepStrictEqual(q.dits, ['Ma nouvelle réponse.']);
});

test('la page : le bouton de papa ferme (« par papa », depuis le geste) ; Hakim qui le touche : « par toi » ; une appli d’avant (sans volume) ne ferme rien seule', async () => {
  const p = page();
  p.ctx.couperSon(true);
  assert.equal(p.ctx.hautParleursFermes(), true);
  const r = p.envoyes.find(x => x.url === '/api/voix/haut-parleurs').corps;
  assert.equal(JSON.stringify(r.raisons), JSON.stringify([{ quoi: 'bouton', par: 'papa' }]));
  assert.ok(Math.abs(r.depuis - Date.now()) < 2000);
  assert.equal(p.els.hautParleursFermes.hidden, false, 'le badge s’affiche');
  p.ctx.couperSon(false);
  assert.equal(p.ctx.hautParleursFermes(), false);
  p.ctx.HP_ICI.parHakimA = Date.now(); p.ctx.couperSon(true);
  assert.equal(JSON.stringify(p.ctx.HP_ICI.etat.raisons), JSON.stringify([{ quoi: 'bouton', par: 'hakim' }]));
  const vieille = page({ sonEtat: 'normal|haut_parleur|hp_oui|aucun' });
  assert.equal(vieille.ctx.verifierHautParleurs('seconde'), false);
  const mac = page({ sonEtat: null, appareil: 'mac' });
  assert.equal(mac.ctx.verifierHautParleurs('seconde'), false, 'témoin : le Mac sans appli, rien de fermé');
});

test('la page du Mac : le son du Mac coupé (lu par le cockpit) ferme ses haut-parleurs ; sa propre ancienne fermeture ne revient pas par le cockpit', () => {
  const p = page({ sonEtat: null, appareil: 'mac' });
  p.ctx.surHautParleursCockpit({ appareils: { mac: { ferme: true } }, ouverts: [], mac_systeme: { ferme: true, raisons: [{ quoi: 'muet' }] } });
  assert.equal(p.ctx.hautParleursFermes(), true);
  assert.equal(JSON.stringify(p.ctx.HP_ICI.etat.raisons), JSON.stringify([{ quoi: 'muet' }]));
  p.ctx.surHautParleursCockpit({ appareils: { mac: { ferme: true, raisons: [{ quoi: 'bouton' }] } }, ouverts: [], mac_systeme: { ferme: false, raisons: [] } });
  assert.equal(p.ctx.hautParleursFermes(), false, 'le son du Mac rendu : rouvert (la fermeture de sa page, elle, ne vient que de sa page)');
  // ce que la page redit au cockpit : seulement les siennes (le Mac coupé, c'est le cockpit qui le sait)
  const q = page({ sonEtat: null, appareil: 'mac' });
  q.ctx.surHautParleursCockpit({ appareils: {}, ouverts: [], mac_systeme: { ferme: true, raisons: [{ quoi: 'muet' }] } });
  const r = q.envoyes.filter(x => x.url === '/api/voix/haut-parleurs').pop().corps;
  assert.equal(JSON.stringify([r.ferme, r.raisons]), JSON.stringify([false, []]));
  // le cockpit : le son du Mac rendu, la page le sait (l'état du système change, même si le Mac reste fermé pour une autre raison)
  assert.match(fonction(SERVEUR, 'function lireHautParleursMac('), /if \(sig !== hpMacSig\) \{ hpMacSig = sig; hautParleursChange\('mac', 'systeme'\); \}/);
});

test('la page : fermée ici, sa réponse lue part vers l’appareil où on l’entend encore (« auto ») ; aucun : elle reste écrite ; une pensée ne part pas', async () => {
  const p = page({ cockpit: { appareils: {}, ouverts: ['montre'] } });
  p.ctx.surHautParleursCockpit({ appareils: {}, ouverts: ['montre'] });
  p.ctx.couperSon(true);
  p.ctx.etat.lectureDe = 'm1';
  p.ctx.l.dire('Sa réponse à papa.');
  const vv = p.envoyes.find(x => x.url === '/api/jarvis/voix-vers');
  assert.deepStrictEqual([vv.corps.cible, vv.corps.de, vv.corps.texte], ['auto', 'tel', 'Sa réponse à papa.']);
  assert.deepStrictEqual(p.dits, [], 'jamais dite ici');
  await p.tic();
  p.ctx.couperSon(false); await p.tic();
  assert.deepStrictEqual(p.dits, [], 'déjà dite par la montre : pas redite à la réouverture');
  const q = page();
  q.ctx.surHautParleursCockpit({ appareils: {}, ouverts: [] });
  q.ctx.couperSon(true);
  q.ctx.etat.lectureDe = 'm2';
  q.ctx.l.dire('Personne ne m’entend.');
  assert.ok(!q.envoyes.some(x => x.url === '/api/jarvis/voix-vers'), 'aucun appareil ouvert : rien n’est envoyé');
  const r = page({ cockpit: { appareils: {}, ouverts: ['montre'] } });
  r.ctx.surHautParleursCockpit({ appareils: {}, ouverts: ['montre'] });
  r.ctx.couperSon(true);
  r.ctx.l.dire('Une pensée dite, pas une réponse.');
  assert.ok(!r.envoyes.some(x => x.url === '/api/jarvis/voix-vers'), 'ses pensées dites restent suspendues');
});

test('la page : ses autres voix lisent ses haut-parleurs (téléphone, Mac, sons, pensées fabriquées d’avance, petits mots, chant, sollicitations)', () => {
  assert.match(PAGE, /speak\(u\) \{\n      if \(ferme\(\)\) \{ setTimeout\(\(\) => \{ if \(u\.onend\) u\.onend\(\); \}, 0\); return; \}/);
  assert.match(PAGE, /prepare\(u\) \{ if \(ferme\(\)\) return;/);
  assert.match(PAGE, /if \(lecteurSysteme\) for \(const k of \['dire', 'preparer'\]\)/);
  assert.match(fonction(PAGE, 'function voixPourTexte('), /hautParleursFermes\(\)\) return Promise\.resolve\(null\);/);
  assert.match(fonction(PAGE, 'function preparerVoixSouffle('), /hautParleursFermes\(\)\) return;/);
  assert.match(fonction(PAGE, 'function direMotDirect('), /raison: 'haut_parleurs'/);
  assert.match(fonction(PAGE, 'function jouerSonEnAttente('), /retour: 'haut_parleurs'/);
  assert.match(fonction(PAGE, 'function prendreSollicitation('), /pourquoi: 'haut_parleurs'/);
  const CHANT = fs.readFileSync(path.join(__dirname, 'public', 'chanter-page.js'), 'utf8');
  assert.match(fonction(CHANT, 'async function surChanter('), /hautParleursFermes\(\)\) \{[^\n]*chant_haut_parleurs/);
  const HTML = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
  assert.ok(HTML.indexOf('/haut-parleurs.js') > 0 && HTML.indexOf('/haut-parleurs.js') < HTML.indexOf('/parler.js'), 'chargé avant parler.js');
  assert.match(HTML, /id="hautParleursFermes"/);
});

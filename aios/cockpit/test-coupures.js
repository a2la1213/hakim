/* Comment et où sa parole s'est arrêtée (30/10, 14:50, Ahmed, relayé par Hakim et confirmé : « qu'il sache, à l'oral comme à
   l'écrit, comment sa réponse a été interrompue et où exactement sa phrase s'est arrêtée ») : node --test test-coupures.js
   La page (parler.js : finirParole, coupureProvisoire…) et le cockpit (server.js : blocCoupure, blocPresent) sont lus dans les
   fichiers et joués à part, une cause après l'autre : voix_ahmed, stop, pause, appli, panne, fin ; à l'écrit, nouveau_message
   et stop. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Voix = require('./public/voix.js');

const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

/* ---- la page ---- */
const REPONSE = 'Bonjour frérot, voici la première phrase. Et voici la deuxième phrase qui est assez longue. Et une troisième pour finir.';
const M1 = 'Bonjour frérot, voici la première phrase.', M2 = 'Et voici la deuxième phrase qui est assez longue.';
function lapage({ stock = {}, fetchOk = true } = {}) {
  let t = 1_800_000_000_000;
  const envois = [], journal = [], minuteries = [];
  const ctx = {
    Math, JSON, String, Array, Object, Number, Set, Error, Voix,
    Date: class extends Date { constructor(...a) { super(...(a.length ? a : [t])); } static now() { return t; } },
    etat: { messages: [{ id: 7, qui: 'j', texte: REPONSE, ts: t - 60000 }], lectureDe: 7, flux: null, fluxId: null, decoupeFlux: null,
      parleDepuis: t - 10000, finParole: null, transcription: null, coupeParAhmed: false, dernierOral: false, reglages: { vitesse: 1 } },
    lecteur: { actif: true, enPause: false, arreter() {} }, vitesseVoix: () => 1, jeton: () => 'j', garderNonDit() {},
    journalVoix: (e, d) => journal.push([e, d]), setTimeout: (fn) => minuteries.push(fn),
    localStorage: { getItem: (k) => (k in stock ? stock[k] : null), setItem: (k, v) => { stock[k] = String(v); }, removeItem: (k) => { delete stock[k]; } },
    fetchOk,
    fetch: (url, o) => { envois.push({ url, o, corps: JSON.parse(o.body) }); return Promise.resolve({ ok: ctx.fetchOk }); },
  };
  vm.createContext(ctx);
  const debut = page.indexOf("/* ---------- Comment et où sa parole s'est arrêtée"), fin = page.indexOf('// fin de « comment et où »');
  assert.ok(debut > 0 && fin > debut);
  vm.runInContext(page.slice(debut, fin) + prendre(page, 'arreterTout')
    + 'this.f = { noterMorceau, noterPanneVoix, coupureProvisoire, reprisDeParole, finirParole, coupureAuChargement, arreterTout, coupureRecue,'
    + ' parole: () => parole, enCours: () => coupureEnCours, aEnvoyer: () => coupureAEnvoyer };', ctx);
  return { ctx, f: ctx.f, envois, journal, stock, minuteries, avancer: (ms) => { t += ms; }, maintenant: () => t };
}
const attendre = async () => { for (let i = 0; i < 4; i++) await new Promise(r => setImmediate(r)); };
// sa voix a dit le premier morceau (3 s), puis la moitié du deuxième (2 s sur 4)
function parle(p) {
  p.f.noterMorceau(M1, 3000); p.avancer(3000);
  p.f.noterMorceau(M2, 4000); p.avancer(2000);
}
const coupures = (p) => p.envois.filter(e => e.url === '/api/jarvis/coupure').map(e => e.corps.coupure);

test('voix_ahmed : sa position est prise quand la voix d’Ahmed l’arrête ; la fin vient quand Ahmed a parlé', async () => {
  const p = lapage();
  parle(p);
  p.f.coupureProvisoire('voix_ahmed');
  assert.equal(p.ctx.etat.finParole.cause, 'voix_ahmed', 'le présent vécu le dira');
  assert.equal(coupures(p).length, 0, 'pas encore une fin : il peut reprendre (un bruit)');
  assert.equal(JSON.parse(p.stock['jarvis.paroleEnCours']).provisoire, true);
  p.avancer(4000);                                  // Ahmed parle, puis sa phrase est transcrite : la position ne bouge plus
  p.ctx.lecteur.actif = false; p.ctx.lecteur.enPause = true; p.ctx.etat.parleDepuis = 0;
  p.f.arreterTout(true, { garder: true, raison: 'parole' });
  const [c] = coupures(p);
  assert.equal(c.cause, 'voix_ahmed');
  assert.equal(c.mode, 'oral');
  assert.equal(c.tour, '7');
  assert.equal(c.derniers, 'Bonjour frérot, voici la première phrase. Et voici la deuxième phrase');
  assert.equal(c.dits, 11);
  assert.equal(c.reste, 9, '4 mots du deuxième morceau, 5 du troisième');
  assert.ok(!('suite' in c), 'la réponse était toute arrivée');
  assert.equal(p.stock['jarvis.paroleEnCours'], undefined, 'la trace de sa parole en cours est effacée');
  await attendre();
  assert.equal(p.f.aEnvoyer(), null, 'reçue par le cockpit');
  assert.equal(p.stock['jarvis.coupure'], undefined);
});

test('voix_ahmed puis un bruit : il reprend, ce n’était pas une fin (et le morceau coupé, repris du début, n’est pas compté deux fois)', () => {
  const p = lapage();
  parle(p);
  p.f.coupureProvisoire('voix_ahmed');
  p.f.reprisDeParole();
  assert.equal(p.f.enCours(), null);
  p.f.noterMorceau('Et voici la deuxième phrase qui est assez longue. Et une troisième', 6000);   // la reprise regroupe autrement
  assert.deepEqual(p.f.parole().morceaux.map(x => x.texte), [M1, 'Et voici la deuxième phrase qui est assez longue. Et une troisième']);
  p.avancer(6000); p.f.noterMorceau('pour finir.', 1000); p.avancer(1000);
  const c = p.f.finirParole('fin', '', { id: 7, mode: 'oral' });
  assert.equal(c.cause, 'fin');
  assert.equal(c.reste, 0);
  assert.equal(coupures(p).length, 0, 'dite en entier : rien à dire au cockpit');
});

test('stop : le bouton, le mot ou Échap ; « stop » dit par-dessus sa voix, c’est Stop', () => {
  const p = lapage();
  parle(p);
  p.f.arreterTout();
  const [c] = coupures(p);
  assert.equal(c.cause, 'stop');
  assert.equal(c.reste, 9);
  assert.equal(p.ctx.etat.finParole.cause, 'stop', 'sa voix jouait : le présent vécu le dira');
  const q = lapage();
  parle(q);
  q.f.coupureProvisoire('voix_ahmed');
  q.f.arreterTout();                                // la phrase d'Ahmed était « stop »
  assert.equal(coupures(q)[0].cause, 'stop');
  assert.equal(coupures(q)[0].derniers, 'Bonjour frérot, voici la première phrase. Et voici la deuxième phrase');
});

test('pause : la position au moment de la pause ; « Reprendre » l’efface ; un message ensuite : pause, puis le message', () => {
  const p = lapage();
  parle(p);
  p.f.coupureProvisoire('pause');
  assert.equal(p.ctx.etat.finParole.cause, 'pause');
  p.f.reprisDeParole();
  assert.equal(coupures(p).length, 0);
  const q = lapage();
  parle(q);
  q.f.coupureProvisoire('pause');
  q.ctx.lecteur.actif = false; q.ctx.lecteur.enPause = true;
  q.avancer(30000);
  q.f.arreterTout(true, { garder: true, raison: 'message' });
  const [c] = coupures(q);
  assert.equal(c.cause, 'pause');
  assert.equal(c.puis, 'nouveau_message');
  assert.equal(c.reste, 9, 'là où la pause l’avait arrêté, pas 30 s plus tard');
});

test('appli : la page fermée (pagehide, keepalive) ; une appli tuée laisse sa trace, lue au chargement suivant', async () => {
  const p = lapage();
  parle(p);
  p.f.finirParole('appli', 'la page a été fermée, quittée ou rechargée');
  const e = p.envois.find(x => x.url === '/api/jarvis/coupure');
  assert.equal(e.o.keepalive, true, 'elle part même la page fermée');
  assert.equal(e.corps.coupure.cause, 'appli');
  assert.equal(e.corps.coupure.detail, 'la page a été fermée, quittée ou rechargée');
  assert.match(page, /window\.addEventListener\('pagehide', \(\) => \{\n\s+finirParole\('appli', 'la page a été fermée, quittée ou rechargée'\);/);
  // tuée sans prévenir (Android) : la trace de sa parole reste dans le navigateur
  const stock = {};
  const k = lapage({ stock });
  parle(k);
  const trace = JSON.parse(stock['jarvis.paroleEnCours']);
  assert.equal(trace.cause, 'appli');
  assert.equal(trace.derniers, 'Bonjour frérot, voici la première phrase.', 'au début du morceau qui jouait : à la phrase près');
  const n = lapage({ stock });                      // la page suivante
  assert.equal(n.minuteries.length, 1);
  n.minuteries[0]();
  const [c] = coupures(n);
  assert.equal(c.cause, 'appli');
  assert.match(c.detail, /l'appli s'est fermée pendant que tu parlais/);
  assert.equal(c.reste, 14);
  assert.equal(stock['jarvis.paroleEnCours'], undefined);
  // en pause quand l'appli a été tuée : la pause, puis l'appli
  const s2 = {};
  const a = lapage({ stock: s2 });
  parle(a); a.f.coupureProvisoire('pause');
  const b = lapage({ stock: s2 }); b.minuteries[0]();
  assert.deepEqual([coupures(b)[0].cause, coupures(b)[0].puis], ['pause', 'appli']);
});

test('appli : page cachée, le son suspendu pendant qu’il parle (provisoire) ; le son revient, la voix aussi', () => {
  const p = lapage();
  parle(p);
  p.f.coupureProvisoire('appli', 'page cachée : le son a été suspendu');
  assert.equal(p.f.parole().rejoue, false, 'le son suspendu repart où il était, pas du début du morceau');
  p.f.reprisDeParole();
  assert.equal(coupures(p).length, 0);
  assert.match(page, /if \(actx\.state !== 'running' && document\.visibilityState === 'hidden' && lecteurNeuronal\.joue\) coupureProvisoire\('appli', 'page cachée : le son a été suspendu'\);/);
  assert.match(page, /else if \(actx\.state === 'running' && coupureEnCours && coupureEnCours\.cause === 'appli'\) reprisDeParole\(\);/);
});

test('panne : la voix (un morceau perdu, sans voix de secours), la connexion, le cerveau', () => {
  const p = lapage();
  parle(p);
  p.f.noterPanneVoix('voix 500');                   // le troisième morceau n'a pas pu être dit
  p.avancer(2000);
  const c = p.f.finirParole('fin', '', { id: 7, mode: 'oral' });
  assert.deepEqual([c.cause, c.detail, c.trou, c.reste], ['panne', 'la voix : voix 500', true, 5]);
  assert.equal(coupures(p).length, 1);
  // la connexion coupée pendant une réponse écrite : la suite n'est pas arrivée
  const q = lapage();
  q.ctx.etat.messages.push({ id: 9, qui: 'j', texte: 'Je regarde **ton** calcul et je vois que le terme deux', ts: 0 });
  q.ctx.lecteur.actif = false; q.ctx.etat.lectureDe = null; q.ctx.etat.parleDepuis = 0;
  q.f.finirParole('panne', 'la connexion avec le Mac a été coupée', { id: 9, mode: 'ecrit', suite: true });
  const [d] = coupures(q);
  assert.deepEqual([d.cause, d.mode, d.suite, d.reste, d.derniers],
    ['panne', 'ecrit', true, null, 'Je regarde ton calcul et je vois que le terme deux']);
  // câblage dans envoyer() : la connexion, le cerveau ; sa voix finit ce qui est arrivé, puis la panne est dite
  const env = page.slice(page.indexOf('async function envoyer('), page.indexOf('\n}\n', page.indexOf('async function envoyer(')));
  assert.match(env, /m\.attenteServeur \? 'la connexion avec le Mac a été coupée'/);
  assert.match(env, /m\.erreur \? `le cerveau : \$\{/);
  assert.match(env, /if \(panne && memeId\(parole\.id, m\.id\) && \(lecteur\.actif \|\| lecteur\.enPause\)\) parole\.panneReponse = \{ detail: panne, \.\.\.\(m\.attenteServeur \? \{ suite: true \} : \{\}\) \};/);
  // la connexion coupée pendant qu'il parle : sa voix finit ce qui est arrivé, puis c'est une coupure (pas un trou)
  const v = lapage();
  parle(v); v.avancer(2000);
  v.f.parole().panneReponse = { detail: 'la connexion avec le Mac a été coupée', suite: true };
  v.ctx.etat.messages[0].texte = M1 + ' ' + M2;     // tout ce qui était arrivé a été dit
  const e = v.f.finirParole('fin', '', { id: 7, mode: 'oral' });
  assert.deepEqual([e.cause, e.detail, e.suite, e.trou, e.reste], ['panne', 'la connexion avec le Mac a été coupée', true, undefined, 0]);
  assert.match(page, /\} else if \(L\.surPanne\) L\.surPanne\(x\.erreur\.message \|\| x\.erreur\);/);
  assert.match(page, /lecteurNeuronal\.surPanne = noterPanneVoix;/);
});

test('fin : dite en entier, rien ne part au cockpit ; le présent vécu le sait', () => {
  const p = lapage();
  parle(p);
  p.avancer(2000); p.f.noterMorceau('Et une troisième pour finir.', 2000); p.avancer(2000);
  const c = p.f.finirParole('fin', '', { id: 7, mode: 'oral' });
  assert.deepEqual([c.cause, c.reste], ['fin', 0]);
  assert.equal(coupures(p).length, 0);
  assert.equal(p.ctx.etat.finParole.cause, 'fin');
  assert.equal(p.f.finirParole('fin', '', { id: 7, mode: 'oral' }), null, 'une seule fin');
  assert.match(page, /if \(!lecteur\.enPause && etat\.lectureDe != null && !\(etat\.flux && String\(etat\.fluxId\) === String\(etat\.lectureDe\)\)\)\n\s+finirParole\('fin', '', \{ id: etat\.lectureDe, mode: 'oral' \}\);/);
});

test('à l’écrit : un nouveau message pendant que la réponse arrivait, ou Stop ; un message dit à voix haute, c’est sa voix', () => {
  const ecrit = (o = {}) => {
    const p = lapage();
    Object.assign(p.ctx.etat, { lectureDe: null, parleDepuis: 0, flux: { abort() {} }, fluxId: '9', ...o });
    p.ctx.lecteur.actif = false;
    p.ctx.etat.messages.push({ id: 9, qui: 'j', texte: 'Oui frérot, ' + 'un mot '.repeat(20) + 'et le dernier', enCours: true });
    return p;
  };
  const p = ecrit();
  p.f.arreterTout(true, { garder: true, raison: 'message' });
  const [c] = coupures(p);
  assert.deepEqual([c.cause, c.mode, c.suite, c.reste], ['nouveau_message', 'ecrit', true, null]);
  assert.equal(c.derniers, '…mot un mot un mot un mot un mot et le dernier');
  const q = ecrit();
  q.f.arreterTout();
  assert.deepEqual([coupures(q)[0].cause, coupures(q)[0].mode], ['stop', 'ecrit']);
  const r = ecrit({ dernierOral: true });
  r.f.arreterTout(true, { garder: true, raison: 'message' });
  assert.equal(coupures(r)[0].cause, 'voix_ahmed');
  // en mode voix, la réponse arrive et sa voix n'a pas commencé : à l'oral, avant d'avoir dit un mot
  const v = ecrit({ decoupeFlux: {} });
  v.f.arreterTout(true, { garder: true, raison: 'parole' });
  assert.deepEqual([coupures(v)[0].mode, coupures(v)[0].derniers, coupures(v)[0].suite], ['oral', '', true]);
  // rien ne parlait, rien n'arrivait : rien
  const z = lapage();
  Object.assign(z.ctx.etat, { lectureDe: null, flux: null }); z.ctx.lecteur.actif = false;
  z.f.arreterTout(true, { raison: 'message' });
  assert.equal(coupures(z).length, 0);
});

test('le cockpit ne l’a pas reçue : gardée dans le navigateur, jointe au message suivant, effacée quand il l’a', async () => {
  const p = lapage({ fetchOk: false });
  parle(p);
  p.f.arreterTout();
  await attendre();
  const gardee = JSON.parse(p.stock['jarvis.coupure']);
  assert.equal(gardee.cause, 'stop');
  assert.equal(p.f.aEnvoyer().id, gardee.id);
  p.f.coupureRecue({ id: 'une-autre' });
  assert.ok(p.f.aEnvoyer(), 'une autre coupure ne l’efface pas');
  p.f.coupureRecue(gardee);
  assert.equal(p.f.aEnvoyer(), null);
  assert.equal(p.stock['jarvis.coupure'], undefined);
  const env = page.slice(page.indexOf('async function envoyer('), page.indexOf('\n}\n', page.indexOf('async function envoyer(')));
  assert.match(env, /const nonDitsEnvoyes = nonDitsAEnvoyer\.slice\(0, 12\), coupureEnvoyee = coupureAEnvoyer;/);
  assert.match(env, /coupure: coupureEnvoyee \|\| undefined/);
  assert.match(env, /if \(coupureEnvoyee\) coupureRecue\(coupureEnvoyee\);/);
});

test('le présent vécu de la page : chaque fin de sa parole porte sa cause', () => {
  let t = 1_000_000;
  const evs = [];
  const ctx = { Date: class extends Date { static now() { return t; } }, etat: { parleDepuis: 0 }, noterPresent: (e) => evs.push(e) };
  vm.createContext(ctx);
  const d = page.indexOf('const voixJouee = [];'), f = page.indexOf('\n}\n', page.indexOf('function noterParoleJarvis')) + 2;
  vm.runInContext(page.slice(d, f) + 'this.noter = noterParoleJarvis;', ctx);
  ctx.noter(true); t += 4000;
  ctx.etat.finParole = { cause: 'panne', detail: 'la voix : voix 500' };
  ctx.noter(false);
  ctx.noter(true); t += 1000; ctx.noter(false);                        // un blanc : sans cause
  assert.deepEqual(evs.map(e => [e.e, e.cause, e.detail]), [['jarvis', 'panne', 'la voix : voix 500'], ['jarvis', undefined, undefined]]);
  assert.match(page, /coupureProvisoire\('voix_ahmed'\);\s+\/\/ \(30\/10\)[^\n]*\n\s+if \(!lecteur\.pause\(\)\)/);
  assert.match(page, /if \(lecteur\.actif\) coupureProvisoire\('pause'\);/);
  assert.match(page, /reprisDeParole\(\);\s+\/\/ \(30\/10\) ce n'était pas une fin/);
});

/* ---- le cockpit ---- */
function cockpit() {
  const dir = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'coupure-'));
  const stimuli = [];
  const ctx = { fs, path, JSON, Number, String, Array, Math, Date, Set, Object, JARVIS: dir, j: JSON.stringify, ecrireAtomique: (f, s) => fs.writeFileSync(f, s),
    corpsActif: () => true, corpsLot: { evenements: stimuli }, ressentirCorps: () => {} };   // (30/10, 18:19) une coupure est aussi un stimulus de son corps
  vm.createContext(ctx);
  vm.runInContext(srv.slice(srv.indexOf('const JARVIS_COUPURE'), srv.indexOf('// fin des coupures'))
    + 'this.f = { recevoirCoupure, blocCoupure, coupureDite, ligneCoupure, attente: () => coupureAttente };', ctx);
  return { f: ctx.f, dir, stimuli };
}
const heure = (t) => new Date(t).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

test('la ligne de son prochain tour, pour chaque cause', () => {
  const { f } = cockpit();
  const t = Date.now() - 30000, h = heure(t);
  const l = (o) => f.ligneCoupure({ t, mode: 'oral', detail: '', puis: '', derniers: '…et donc le champ se referme', reste: 37, suite: false, trou: false, spontane: false, ...o });
  assert.equal(l({ cause: 'voix_ahmed' }), `[Ta réponse précédente (${h}) a été coupée par la voix d'Ahmed (oral), après « …et donc le champ se referme » ; il en restait 37 mots]`);
  assert.equal(l({ cause: 'stop' }), `[Ta réponse précédente (${h}) a été arrêtée par Ahmed (Stop) (oral), après « …et donc le champ se referme » ; il en restait 37 mots]`);
  assert.equal(l({ cause: 'pause', puis: 'voix_ahmed' }), `[Ta réponse précédente (${h}) a été mise en pause par Ahmed (oral), après « …et donc le champ se referme » ; il en restait 37 mots ; puis : Ahmed a repris la parole]`);
  assert.equal(l({ cause: 'appli', detail: 'la page a été fermée, quittée ou rechargée' }),
    `[Ta réponse précédente (${h}) a été coupée par l'appli : la page a été fermée, quittée ou rechargée (oral), après « …et donc le champ se referme » ; il en restait 37 mots]`);
  assert.equal(l({ cause: 'panne', detail: 'la connexion avec le Mac a été coupée', mode: 'ecrit', reste: null, suite: true }),
    `[Ta réponse précédente (${h}) a été coupée par une panne : la connexion avec le Mac a été coupée (écrit), après « …et donc le champ se referme » ; la suite n'était pas encore écrite]`);
  assert.equal(l({ cause: 'panne', detail: 'la voix : voix 500', trou: true, reste: 5 }),
    `[Ta réponse précédente (${h}) n'a pas été entendue en entier : une panne (la voix : voix 500) (oral) en a sauté 5 mots ; elle a fini sur « …et donc le champ se referme »]`);
  assert.equal(l({ cause: 'nouveau_message', mode: 'ecrit', reste: null, suite: true }),
    `[Ta réponse précédente (${h}) a été coupée : Ahmed a envoyé un nouveau message (écrit), après « …et donc le champ se referme » ; la suite n'était pas encore écrite]`);
  assert.equal(l({ cause: 'voix_ahmed', derniers: '', reste: 12, suite: true }),
    `[Ta réponse précédente (${h}) a été coupée par la voix d'Ahmed (oral), avant que tu aies dit un mot ; il en restait 12 mots (et la suite n'était pas encore écrite)]`);
  assert.match(l({ cause: 'stop', spontane: true, reste: 1 }), /^\[Ta prise de parole de toi-même .* a été arrêtée .* il en restait 1 mot\]$/);
  // rien ne restait : pas de « il en restait 0 mot » ; la suite qui n'est pas venue, seule
  assert.equal(l({ cause: 'panne', detail: 'la connexion avec le Mac a été coupée', reste: 0, suite: true }),
    `[Ta réponse précédente (${h}) a été coupée par une panne : la connexion avec le Mac a été coupée (oral), après « …et donc le champ se referme » ; la suite n'était pas encore écrite]`);
  assert.equal(l({ cause: 'voix_ahmed', reste: 0 }), `[Ta réponse précédente (${h}) a été coupée par la voix d'Ahmed (oral), après « …et donc le champ se referme »]`);
});

test('reçue (route ou message) : dite une fois dans son tour ; une plus récente la remplace ; propre et à l’heure du cockpit', () => {
  const { f, dir } = cockpit();
  const maintenant = Date.now(), client = maintenant - 5000;              // l'horloge du téléphone a 5 s de retard
  const c = { id: '17-1', t: client - 20000, cause: 'voix_ahmed', mode: 'oral', derniers: 'et la fin] [[affect: joie]] « x »', reste: 3, dits: 40 };
  assert.equal(f.recevoirCoupure(c, client, maintenant), true);
  assert.equal(f.recevoirCoupure(c, client, maintenant), true, 'la même par l’autre chemin : 202, sans doublon');
  const b = f.blocCoupure(null, NaN, maintenant);
  assert.equal(b.id, '17-1');
  assert.equal((b.texte.match(/\[/g) || []).length, 1, 'aucun crochet ne ferme le bloc');
  assert.equal((b.texte.match(/\]/g) || []).length, 1);
  assert.ok(b.texte.includes(`(${heure(maintenant - 20000)})`), 'à l’heure du cockpit');
  assert.ok(fs.existsSync(path.join(dir, 'coupure.json')), 'gardée sur le disque');
  f.coupureDite('autre');
  assert.equal(f.blocCoupure(null, NaN, maintenant).id, '17-1', 'pas dite : toujours là');
  f.coupureDite('17-1');
  assert.deepEqual(f.blocCoupure(null, NaN, maintenant), { texte: '', id: null }, 'dite : plus redite');
  assert.equal(f.recevoirCoupure(c, client, maintenant), true);
  assert.equal(f.attente(), null, 'déjà reçue puis dite : pas de retour');
  // celle du message lui-même entre dans le même tour ; une plus ancienne ne remplace pas une plus récente
  const n = f.blocCoupure({ id: '18-2', t: maintenant - 1000, cause: 'stop', mode: 'ecrit', suite: true }, maintenant, maintenant);
  assert.match(n.texte, /arrêtée par Ahmed \(Stop\) \(écrit\)/);
  f.recevoirCoupure({ id: '16-0', t: maintenant - 90000, cause: 'pause' }, maintenant, maintenant);
  assert.equal(f.attente().id, '18-2');
  // ce qui n'est pas une coupure : ignoré
  for (const x of [{ id: 'a', t: maintenant, cause: 'fin' }, { id: 'a', t: maintenant, cause: 'constructor' }, { id: 'a b', t: maintenant, cause: 'stop' },
    { id: 'a', t: maintenant - 2 * 864e5, cause: 'stop' }, { id: 'a', t: maintenant + 3600e3, cause: 'stop' }, null, 'stop'])
    assert.equal(f.recevoirCoupure(x, maintenant, maintenant), false, JSON.stringify(x));
});

test('le cockpit est branché : la route (jeton), la ligne dans le présent vécu, dite seulement si son tour a réussi', () => {
  const route = srv.slice(srv.indexOf("if (p === '/api/jarvis/coupure'"), srv.indexOf("if (p === '/api/jarvis/stop'"));
  assert.match(route, /jetonValide\(req\)/);
  assert.match(route, /recevoirCoupure\(q && q\.coupure, Number\(q && q\.maintenant\)\)/);
  assert.match(srv, /const coupureTour = blocCoupure\(q\.coupure, Number\(q\.maintenant\), maintenant\);\n\s+if \(coupureTour\.texte\) presentTexte = presentTexte \? `\$\{presentTexte\}\\n\$\{coupureTour\.texte\}` : coupureTour\.texte;/);
  assert.match(srv, /if \(!o\.coupe && !o\.erreur && source !== 'local'\) coupureDite\(coupureTour\.id\);/);
  // après la prosodie (qui s'insère avant le dernier crochet du présent vécu)
  assert.ok(srv.indexOf('const coupureTour = blocCoupure(') > srv.indexOf('if (prosodieTexte) presentTexte ='));
});

test('le présent vécu du cockpit dit chaque fin de sa parole et sa cause (et lit encore les pages d’avant)', () => {
  const ctx = { Math, Number, Array, Date, String, Set, JSON };
  vm.createContext(ctx);
  vm.runInContext(srv.slice(srv.indexOf('const EVENEMENTS_PRESENT'), srv.indexOf('function tonDe(')) + prendre(srv, 'tonDe') + 'this.bloc = blocPresent;', ctx);
  const t = Date.now();
  const ev = (debut, o) => ({ e: 'jarvis', debut: t - debut, fin: t - debut + 2000, ...o });
  const b = ctx.bloc([ev(90000, { cause: 'voix_ahmed', coupe: true }), ev(80000, { cause: 'stop' }), ev(70000, { cause: 'pause' }),
    ev(60000, { cause: 'appli', detail: 'page cachée : le son a été suspendu' }), ev(50000, { cause: 'panne', detail: 'la voix ] [x' }),
    ev(40000, { cause: 'fin' }), ev(30000, { cause: 'nouveau_message' }), ev(20000, { cause: 'toString' }), ev(10000, { coupe: 'stop' })], t, t);
  for (const x of ["tu as parlé 2,0 s, coupé par la voix d'Ahmed", 'tu as parlé 2,0 s, arrêté par Ahmed (Stop)', 'tu as parlé 2,0 s, mis en pause par Ahmed',
    "tu as parlé 2,0 s, coupé par l'appli (page cachée : le son a été suspendu)", 'tu as parlé 2,0 s, coupé par une panne (la voix x)',
    'tu as parlé 2,0 s, ta réponse dite jusqu’au bout', 'tu as parlé 2,0 s, coupé : Ahmed a envoyé un autre message'])
    assert.ok(b.includes(x), x);
  assert.equal((b.match(/\[/g) || []).length, 1, 'le détail ne ferme pas le bloc');
  assert.equal((b.match(/arrêté par Ahmed \(Stop\)/g) || []).length, 2, 'une page d’avant (coupe: "stop") se lit toujours');
});

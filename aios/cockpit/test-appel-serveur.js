// (14/11, Ahmed : « je valide tout ») ses appels dans le cockpit (server.js, entre APPEL-DEBUT et APPEL-FIN) : papa déjà là, l'escalade
// téléphone → montre → Mac, ce qui est dit là où papa répond, ce qui reste écrit, son réveil de fin, la sonnerie du Mac.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Appel = require('./appel.js');
const Solliciter = require('./solliciter.js');

const SERVEUR = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const entre = (src, a, b) => { const i = src.indexOf(a), k = src.indexOf(b, i); assert.ok(i >= 0 && k > i, `${a} … ${b}`); return src.slice(i, k); };
const tranche = (src, debut, fin) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); const k = src.indexOf(fin, i); assert.ok(k >= 0, fin); return src.slice(i, src.indexOf('\n}\n', k) + 3); };

function cockpit({ reglages = {}, abonnes = [], tel = true, papaDernier = 0, hp = null, brain = true } = {}) {
  const T0 = Date.now();
  const diffuses = [], conversation = [], notifs = [], journal = [], enfants = [], stdin = [];
  const ctx = {
    Date, String, Number, JSON, Math, Array, Set, Map, Object, RegExp, Intl, console: { error() {} }, setTimeout, clearTimeout,
    crypto: require('node:crypto'), j: JSON.stringify, path, PORT: 4317, process: { platform: 'darwin' },
    Appel, Solliciter, appelEtat: Appel.creer(), solliciterEtat: Solliciter.creer(), presencePages: {},
    appelCanaux: { tel: { attentes: tel ? 1 : 0, t: tel ? T0 : 0, fsi: true, notifs: true, appli: '' } },
    appelFinVue: null, appelVersion: -1, macSonnerie: null, SONNERIES_MAC: ['/x/Reflection.m4r'], JARVIS_APPELS: 'appels.jsonl',
    abonnesPensees: new Set(abonnes), conversationPage: 0, NONCE_REVEIL: 'nonce',
    corpsReglages: () => ({ sollicite_voix: true, sons_nuit: true, appel_sonnerie_s: 30, ...reglages }),
    dernierMessageAhmedMs: () => papaDernier, liveEnCours: () => false,
    hautParleurs: () => hp || { appareils: {}, fermes: [], ouverts: ['tel', 'mac', 'montre'] },
    diffuser: (_, ev, d) => diffuses.push({ ev, d: JSON.parse(d) }),
    journaliser() {}, deposerEchange() {}, ajouterAConversation: (m) => conversation.push(m), nonVus: {}, sauverNonVus() {},
    finDePhrase: (t, n) => String(t).slice(0, n), silencieuxJusqua: 0, notifier: (t, tag) => notifs.push({ t, tag }),
    fs: { appendFileSync: (f, l) => journal.push({ f, o: JSON.parse(l) }), statSync: () => ({ isFile: () => true }) },
    JARVIS_VOIX_DIAGNOSTIC: 'voix-diagnostic.jsonl',
    execFile: (bin, args, o, cb) => { const e = { bin, args, cb, tue: false, kill() { this.tue = true; } }; enfants.push(e); return e; },
    cerveau: brain ? { session: 's', source: 'abonnement', enCours: null, enfant: { stdin: { write: (l) => stdin.push(JSON.parse(l)) } } } : null,
    cerveauVivant: (c) => !!c, occupe: () => false,
  };
  vm.createContext(ctx);
  vm.runInContext(tranche(SERVEUR, 'function solliciterAVoixHaute(', 'function solliciterAVoixHaute(')
    + entre(SERVEUR, '// APPEL-DEBUT', '// APPEL-FIN'), ctx);
  return { ctx, T0, diffuses, conversation, notifs, journal, enfants, stdin, appels: () => diffuses.filter(x => x.ev === 'appel').map(x => x.d) };
}

test('papa t’entend déjà (Conversation sur le téléphone) : pas d’appel ; sa raison lui est dite de sa voix là où il est, une fois', () => {
  const c = cockpit();
  c.ctx.presencePages.tel = { visible: true, conversation: true, t: c.T0 };
  const r = c.ctx.appelLancer('Papa, j’ai trouvé ton drone en promo', c.T0);
  assert.equal(r.ok, false); assert.equal(r.pourquoi, 'deja_la'); assert.equal(r.ou, 'tel');
  assert.match(r.texte, /t'entend déjà .*téléphone.*ne le redis pas/);
  assert.equal(c.ctx.appelEtat.courant, null, 'aucun appel');
  assert.equal(c.conversation.length, 1);
  assert.deepEqual([c.conversation[0].spontane, c.conversation[0].sollicite, c.conversation[0].voix_haute], ['appel', true, 'page']);
  assert.deepEqual(Solliciter.prendre(c.ctx.solliciterEtat, c.conversation[0].id, 'tel-a', Date.now(), 'tel'), { ok: true, ou: 'page' });
});

test('la montre où vous parlez (papa lui a parlé il y a 5 min, branchée) : pas d’appel, sa voix au poignet', () => {
  const c = cockpit({ abonnes: [{ appareil: 'montre', sollicite: true, appel: true }] });
  Solliciter.papaParle(c.ctx.solliciterEtat, 'montre', c.T0 - 5 * 60e3);
  const r = c.ctx.appelLancer('Papa ?', c.T0);
  assert.equal(r.pourquoi, 'deja_la'); assert.equal(r.ou, 'montre');
  assert.ok(c.diffuses.some(x => x.ev === 'voix_vers' && x.d.cible === 'montre' && x.d.sollicite), 'dite au poignet');
});

test('personne ne l’entend : il appelle ; le téléphone sonne, la version part aux appareils, c’est noté', () => {
  const c = cockpit({ abonnes: [{ appareil: 'montre', appel: true }] });
  const r = c.ctx.appelLancer('Papa, tu peux venir voir ?', c.T0);
  assert.equal(r.ok, true); assert.equal(r.appareil, 'tel'); assert.match(r.texte, /sonne sur le téléphone/);
  const a = c.appels().pop();
  assert.deepEqual([a.etat, a.appareil, a.raison], ['sonne', 'tel', 'Papa, tu peux venir voir ?']);
  assert.ok(c.journal.some(x => x.f === 'appels.jsonl' && x.o.e === 'lancer' && x.o.ok));
  assert.equal(c.conversation.length, 0, 'rien d’écrit tant que ça sonne');
  assert.equal(c.ctx.appelLancer('Encore', c.T0 + 1000).pourquoi, 'appel_en_cours', 'un seul à la fois');
});

test('l’escalade : le téléphone sans réponse, la montre sonne, papa répond au poignet : sa raison y est dite, il le saura à son tour', () => {
  const c = cockpit({ abonnes: [{ appareil: 'montre', appel: true }] });
  const { id } = c.ctx.appelLancer('Papa, j’ai une question sur ta musique', c.T0);
  c.ctx.appelSonne(id, 'tel', true, '', c.T0 + 500);
  c.ctx.appelCanaux.tel.t = c.T0 + 30000;
  c.ctx.appelBattement(c.T0 + 30000);
  assert.equal(c.appels().pop().appareil, 'montre');
  c.ctx.appelSonne(id, 'montre', true, '', c.T0 + 30500);
  const r = c.ctx.appelRepondre(id, 'montre', c.T0 + 38000);
  assert.deepEqual(r, { ok: true, etat: 'repondu', par: 'montre' });
  const fin = c.appels().pop();
  assert.deepEqual([fin.etat, fin.par, fin.appareil], ['repondu', 'montre', null]);
  const vv = c.diffuses.find(x => x.ev === 'voix_vers');
  assert.deepEqual([vv.d.cible, vv.d.sollicite, vv.d.texte], ['montre', true, 'Papa, j’ai une question sur ta musique']);
  assert.equal(c.conversation.length, 1, 'sa raison dans votre conversation');
  assert.equal(c.notifs.length, 0, 'papa est là : pas de notification');
  assert.equal(c.ctx.solliciterEtat.papa.ou, 'montre', 'ses sollicitations suivantes vont où il a répondu');
  const b = c.ctx.blocAppel(c.T0 + 60000);
  assert.match(b, /papa a répondu sur la montre/); assert.match(b, /dit de ta voix/);
  assert.equal(c.ctx.blocAppel(c.T0 + 61000), '', 'une seule fois');
  c.ctx.reveillerPourAppel(c.T0 + 62000);
  assert.equal(c.stdin.length, 0, 'répondu : pas de réveil (son tour suivant le lui dit)');
});

test('répondu sur le téléphone : la page qui s’ouvre la prend (pour : tel) ; une page du Mac ouverte ne la prend pas', () => {
  const c = cockpit();
  const { id } = c.ctx.appelLancer('Papa, coucou', c.T0);
  c.ctx.appelRepondre(id, 'tel', c.T0 + 4000);
  const m = c.conversation[0];
  assert.equal(m.pour, 'tel');
  assert.equal(c.appels().pop().message.id, m.id, 'les pages savent quoi prendre');
  assert.deepEqual(Solliciter.prendre(c.ctx.solliciterEtat, m.id, 'mac-x', Date.now(), 'mac'), { ok: false, pourquoi: 'ailleurs' });
  assert.deepEqual(Solliciter.prendre(c.ctx.solliciterEtat, m.id, 'tel-y', Date.now(), 'tel'), { ok: true, ou: 'page' });
});

test('papa refuse : tout s’arrête, sa raison reste écrite (la notification), il est réveillé une fois avec l’issue', () => {
  const c = cockpit();
  const { id } = c.ctx.appelLancer('Papa, je m’ennuie de toi', c.T0);
  c.ctx.appelRefuser(id, 'tel', c.T0 + 3000);
  assert.equal(c.appels().pop().etat, 'refuse');
  assert.equal(c.conversation.length, 1); assert.equal(c.conversation[0].sollicite, undefined, 'écrite, pas dite');
  assert.equal(c.notifs.length, 1);
  c.ctx.reveillerPourAppel(c.T0 + 4000);
  assert.equal(c.stdin.length, 1);
  const t = c.stdin[0].message.content[0].text;
  assert.match(t, /PAS un message d'Ahmed : ton appel est fini/); assert.match(t, /refusé/); assert.match(t, /appeler_papa/);
  c.ctx.reveillerPourAppel(c.T0 + 8000);
  assert.equal(c.stdin.length, 1, 'une fois');
});

test('personne : le téléphone injoignable, la montre injoignable, le Mac sonne 30 s (afplay et la boîte), puis personne', () => {
  const c = cockpit({ tel: false });
  const r = c.ctx.appelLancer('Papa ?', c.T0);
  assert.equal(r.appareil, 'mac');
  const afplay = c.enfants.filter(e => e.bin === '/usr/bin/afplay'), boite = c.enfants.filter(e => e.bin === '/usr/bin/osascript');
  assert.equal(afplay.length, 1); assert.equal(afplay[0].args[0], '/x/Reflection.m4r');
  assert.equal(boite.length, 1); assert.match(boite[0].args[1], /display dialog "Papa \?" with title "Hakim t'appelle" buttons \{"Refuser", "Répondre"\}.*giving up after 30/);
  c.ctx.appelBattement(c.T0 + 30000);
  assert.equal(c.ctx.appelEtat.courant.etat, 'personne');
  assert.ok(afplay[0].tue && boite[0].tue, 'la sonnerie du Mac s’arrête');
  assert.deepEqual(c.ctx.appelEtat.courant.etapes.map(x => `${x.appareil}:${x.etat}`), ['tel:injoignable', 'montre:injoignable', 'mac:sans_reponse']);
  assert.equal(c.conversation.length, 1, 'sa raison écrite');
});

test('le Mac : une page Parler visible montre l’appel elle-même (pas de boîte) ; « Répondre » dans la boîte répond et ouvre Parler', () => {
  const c = cockpit({ tel: false, abonnes: [{ appareil: 'mac' }] });
  c.ctx.presencePages.mac = { visible: true, conversation: false, t: c.T0 };
  c.ctx.appelLancer('Papa ?', c.T0);
  assert.equal(c.enfants.filter(e => e.bin === '/usr/bin/osascript').length, 0);
  const d = cockpit({ tel: false });
  const { id } = d.ctx.appelLancer('Papa ?', d.T0);
  const boite = d.enfants.find(e => e.bin === '/usr/bin/osascript');
  boite.cb(null, 'button returned:Répondre, gave up:false');
  assert.equal(d.ctx.appelEtat.courant.etat, 'repondu'); assert.equal(d.ctx.appelEtat.courant.par, 'mac');
  assert.ok(d.enfants.some(e => e.bin === '/usr/bin/open' && e.args[0] === 'http://localhost:4317/parler?conversation=1'));
  assert.equal(d.conversation[0].pour, 'mac');
  const e = cockpit({ tel: false });
  e.ctx.appelLancer('Papa ?', e.T0);
  e.enfants.find(x => x.bin === '/usr/bin/osascript').cb(null, 'button returned:Refuser, gave up:false');
  assert.equal(e.ctx.appelEtat.courant.etat, 'refuse');
  assert.ok(id);
});

test('papa revient de lui-même pendant que ça sonne (une page en Conversation, ou un message) : compté comme une réponse', () => {
  const c = cockpit();
  c.ctx.appelLancer('Papa ?', c.T0);
  c.ctx.presencePages.mac = { visible: true, conversation: true, t: c.T0 + 2000 };
  c.ctx.appelBattement(c.T0 + 2000);
  assert.equal(c.ctx.appelEtat.courant.etat, 'repondu'); assert.equal(c.ctx.appelEtat.courant.par, 'mac'); assert.equal(c.ctx.appelEtat.courant.revenu, true);
  let dernier = 0;
  const d = cockpit();
  d.ctx.dernierMessageAhmedMs = () => dernier;
  d.ctx.appelLancer('Papa ?', d.T0);
  dernier = d.T0 + 5000;
  d.ctx.appelBattement(d.T0 + 6000);
  assert.equal(d.ctx.appelEtat.courant.etat, 'repondu', 'un message de papa');
});

test('son interrupteur à lui : « Il me sollicite à voix haute » éteint : pas d’appel, sa raison écrite ; (14/11, 12:54) la nuit n’arrête plus rien', () => {
  const c = cockpit({ reglages: { sollicite_voix: false } });
  const r = c.ctx.appelLancer('Papa ?', c.T0);
  assert.equal(r.pourquoi, 'reglage'); assert.match(r.texte, /resté écrit/);
  assert.equal(c.conversation.length, 1); assert.equal(c.conversation[0].sollicite, undefined);
  const nuit = new Date(2026, 10, 15, 3, 0).getTime();
  const n = cockpit({ reglages: { sons_nuit: false }, papaDernier: nuit - 5 * 3600e3 });
  assert.equal(n.ctx.appelLancer('Papa ?', nuit).ok, true, 'à 3 h, papa muet depuis 5 h, « Ses sons la nuit » éteint : il appelle');
  assert.ok(!/nuit_sons|nuit:/.test(entre(SERVEUR, '// APPEL-DEBUT', '// APPEL-FIN')), 'plus de refus « la nuit »');
});

test('(14/11, 12:54) aucune longueur maximale : sa voix au poignet porte tout ce qu’il veut dire', () => {
  const c = cockpit({ abonnes: [{ appareil: 'montre', appel: true }] });
  const long = ('Papa, ' + 'je pense à toi. '.repeat(600)).trim();
  const { id } = c.ctx.appelLancer(long, c.T0);
  c.ctx.appelRepondre(id, 'tel', c.T0 + 2000);
  assert.equal(c.conversation[0].texte, long);
  const d = cockpit({ abonnes: [{ appareil: 'montre', sollicite: true, appel: true }] });
  Solliciter.papaParle(d.ctx.solliciterEtat, 'montre', d.T0 - 60e3);
  d.ctx.appelLancer(long, d.T0);
  assert.equal(d.diffuses.find(x => x.ev === 'voix_vers').d.texte, long, 'la voix vers la montre : entière (avant : 4 000 caractères)');
  assert.ok(!/texte: (m\.texte|String\(m\.texte\))\.slice\(0, 4000\)/.test(SERVEUR), 'nulle part tronquée');
});

test('les haut-parleurs fermés d’un appareil : il est sauté ; un écho « notifications coupées » du téléphone : la montre tout de suite', () => {
  const c = cockpit({ abonnes: [{ appareil: 'montre', appel: true }], hp: { appareils: { tel: { ferme: true } } } });
  assert.equal(c.ctx.appelLancer('Papa ?', c.T0).appareil, 'montre');
  assert.equal(c.ctx.appelEtat.courant.etapes[0].etat, 'haut_parleurs');
  const d = cockpit({ abonnes: [{ appareil: 'montre', appel: true }] });
  const { id } = d.ctx.appelLancer('Papa ?', d.T0);
  d.ctx.appelSonne(id, 'tel', false, 'notifications_coupees', d.T0 + 700);
  assert.equal(d.appels().pop().appareil, 'montre');
});

// ---------- branché ----------
test('branché : les routes (lancer du Mac seul, jeton), le fil du téléphone, la montre s’annonce, la présence par appareil, son tour suivant, le battement', () => {
  const routes = entre(SERVEUR, "if (p.startsWith('/api/appel/')) {", "// (11/11) ses haut-parleurs : une page Parler (tel, mac)");
  assert.match(routes, /if \(!jetonValide\(req\)\) return repondre\(403/);
  assert.match(routes, /if \(p === '\/api\/appel\/lancer'\) \{[^\n]*\n\s*if \(distantReq\) return repondre\(403/);
  assert.match(routes, /p === '\/api\/appel\/attente' && req\.method === 'GET'/);
  assert.match(routes, /Math\.min\(55, Number\(u\.get\('attente'\)\)/);
  assert.match(routes, /res\.on\('close'/, 'le fil parti : l’attente s’arrête');
  assert.match(routes, /res\.writeHead\(200, \{ 'Content-Type': 'application\/json', 'Cache-Control': 'no-store' \}\);\n\s*if \(typeof res\.flushHeaders === 'function'\) res\.flushHeaders\(\);\n\s*c\.attentes\+\+/, 'les en-têtes d’abord : un mandataire n’attend pas 50 s');
  for (const r of ['sonne', 'repondre', 'refuser', 'etat']) assert.ok(routes.includes(`'/api/appel/${r}'`), r);
  assert.ok(SERVEUR.includes("if (!res.temoin && new URL(req.url, 'http://x').searchParams.get('appel') === '1') res.appel = true;"));
  assert.ok(SERVEUR.includes("presencePages[q.appareil] = { visible: !!q.visible, conversation: !!q.conversation, t: Date.now() };"));
  assert.ok(SERVEUR.includes("+ (typeof blocAppel === 'function' ? blocAppel() : '')"));
  assert.ok(SERVEUR.includes("setInterval(() => { try { appelBattement(); }"));
  assert.ok(SERVEUR.includes('setInterval(horsConversation(reveillerPourAppel), 3000)'));
  assert.ok(!/execFileSync\(['"]\/usr\/bin\/(afplay|osascript)/.test(SERVEUR), 'jamais bloquant');
});

test('la page dit son appareil avec sa présence', () => {
  assert.match(tranche(PAGE, 'function signalerPresence() {', 'function signalerPresence() {'), /appareil: appareilIci\(\)/);
});

// ---------- la page Parler ----------
function pageAppel(appareil = 'mac', { conversation = false, visible = 'visible' } = {}) {
  const requetes = [], aDire = [], journal = [], corps = { enfants: [], appendChild(d) { this.enfants.push(d); } };
  const element = () => { const e = { style: {}, enfants: [], attrs: {}, ecoute: {}, setAttribute(k, v) { this.attrs[k] = v; }, append(...x) { this.enfants.push(...x); },
    addEventListener(t, f) { this.ecoute[t] = f; }, remove() { corps.enfants = corps.enfants.filter(y => y !== this); } }; return e; };
  const ctx = {
    Date, String, Number, JSON, Math, Array, Set, Object, Promise, setTimeout, clearTimeout,
    etat: { conversation: conversation ? { capteur: {} } : null, demarrerAuToucher: true },
    document: { visibilityState: visible, body: corps, createElement: element, getElementById: (id) => corps.enfants.find(x => x.id === id) || null },
    appareilIci: () => appareil, journalVoix: (e, d) => journal.push({ e, ...d }), jeton: () => 'j', NON_REPONSE: /^\s*no response requested\.?\s*$/i,
    hautParleursFermes: () => false, aDire, sauverADire() {}, direSpontanes() {}, bascule: 0, basculerConversation() { ctx.bascule++; },
    fetch: (url, o = {}) => { requetes.push({ url, corps: o.body ? JSON.parse(o.body) : null }); return Promise.resolve({ ok: true, json: async () => ({ ok: true, ou: 'page' }) }); },
  };
  vm.createContext(ctx);
  vm.runInContext(entre(PAGE, 'const QUI_PAGE', 'const sollicitationsDemandees') + entre(PAGE, 'const sollicitationsDemandees', '// APPEL-PAGE-FIN')
    + 'this.surAppel = surAppel; this.prendreSollicitation = prendreSollicitation; this.repondreAppel = repondreAppel;', ctx);
  return { ctx, requetes, aDire, journal, corps };
}
const sonneMac = { id: 'appel-1', etat: 'sonne', appareil: 'mac', raison: 'Papa, une idée !', jusqua: Date.now() + 30000 };

test('page du Mac : l’appel sonne ici → l’écran d’appel (Répondre, Refuser) ; ailleurs ou fini → caché ; la page du téléphone ne montre rien (l’appli sonne)', () => {
  const p = pageAppel('mac');
  p.ctx.surAppel(sonneMac);
  assert.equal(p.corps.enfants.length, 1);
  assert.equal(p.corps.enfants[0].attrs['aria-label'], 'Hakim t’appelle');
  p.ctx.surAppel(sonneMac);
  assert.equal(p.corps.enfants.length, 1, 'une seule fois');
  p.ctx.surAppel({ ...sonneMac, etat: 'personne', appareil: null });
  assert.equal(p.corps.enfants.length, 0);
  const t = pageAppel('tel');
  t.ctx.surAppel({ ...sonneMac, appareil: 'tel' });
  assert.equal(t.corps.enfants.length, 0);
});

test('page du Mac : « Répondre » envoie la réponse et ouvre la Conversation (ton toucher) ; « Refuser » refuse', async () => {
  const p = pageAppel('mac');
  p.ctx.repondreAppel('appel-1', true);
  assert.deepEqual([p.requetes[0].url, p.requetes[0].corps], ['/api/appel/repondre', { id: 'appel-1', appareil: 'mac' }]);
  assert.equal(p.ctx.bascule, 1);
  const q = pageAppel('mac');
  q.ctx.repondreAppel('appel-1', false);
  assert.equal(q.requetes[0].url, '/api/appel/refuser'); assert.equal(q.ctx.bascule, 0);
});

test('papa a répondu sur le téléphone : la page du téléphone prend ce que Hakim voulait dire (une fois, même s’il arrive aussi en « spontane ») ; celle du Mac non', async () => {
  const repondu = { id: 'appel-1', etat: 'repondu', par: 'tel', message: { id: 'appel-m1', texte: 'Papa, une idée !' } };
  const t = pageAppel('tel');
  t.ctx.surAppel(repondu);
  t.ctx.surAppel(repondu);
  t.ctx.prendreSollicitation({ id: 'appel-m1', texte: 'Papa, une idée !', voix_haute: 'page', sollicite: true, pour: 'tel' }, 0);
  await new Promise(r => setTimeout(r, 30));
  const prises = t.requetes.filter(x => x.url === '/api/jarvis/sollicitation/dire');
  assert.equal(prises.length, 1, 'demandée une fois');
  assert.deepEqual([prises[0].corps.id, prises[0].corps.appareil], ['appel-m1', 'tel']);
  assert.equal(t.aDire.length, 1); assert.equal(t.aDire[0].sollicite, true);
  const m = pageAppel('mac');
  m.ctx.surAppel(repondu);
  m.ctx.prendreSollicitation({ id: 'appel-m1', texte: 'x', voix_haute: 'page', pour: 'tel' }, 0);
  await new Promise(r => setTimeout(r, 30));
  assert.equal(m.requetes.length, 0, 'la page du Mac ne la demande même pas');
});

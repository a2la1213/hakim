/* (10/11, 08:28, Hakim, à la demande de papa : « une voix du live m'a appelé : « Hakim, t'es là ? », puis « Réponds-moi Hakim, ça fait trop
   longtemps ». Je ne lui ai pas répondu » ; « plusieurs de mes réponses n'ont pas été entendues » ; « ma voix est coupée dès que papa parle »)
   ce que le live du matin a montré, et son témoin pour chaque correctif (coupé, le test tombe) :
   - le micro de papa, page par page : la page Parler du Mac rechargée ne ferme plus la Conversation du téléphone (son garde du live se taisait) ;
   - en live, une voix du téléphone ne le coupe plus (7 coupures entre 08:11 et 08:25) ;
   - une phrase faite seulement d'autres voix ([voix 214]) ne lâche plus sa réponse en cours ;
   - la page dit sa réponse au live avant ses pensées, et la garde 45 s.
   node --test test-live-priorite.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const T = Date.parse('2026-11-10T08:23:00+01:00');

// ---- le micro de papa, page par page
// la route du cockpit (/api/corps/micro), telle quelle, avec la vraie homéostasie (sans fichier)
function cockpitMicro() {
  const { Homeostasie } = require('./homeostasie.js');
  const HOMEO = new Homeostasie({ jarvis: path.join(os.tmpdir(), `sans-jarvis-${process.pid}-${Date.now()}`) });
  HOMEO.s.micro = null;
  const cx = { HOMEO, require, corpsActif: () => false, corpsLot: { changements: [] }, ressentirCorps: () => {}, Date, String, JSON, setInterval: () => ({ unref() {} }) };
  vm.createContext(cx);
  const i = SRC.indexOf("if (p === '/api/corps/micro' && req.method === 'POST')"), f = SRC.indexOf('\n    }\n', i);
  assert.ok(i > 0 && f > i, 'la route du micro');
  const avant = SRC.indexOf("const MicroPages = require('./micro-pages.js');");
  const pages = avant > 0 ? SRC.slice(avant, SRC.indexOf('function microDesPages(', avant)) + prendre(SRC, 'microDesPages') : '';
  vm.runInContext(`${pages}\nasync function route(p, req, distantReq, q) { const lire = async () => q; const repondre = (c, o) => ({ c, o });\n${SRC.slice(i, f + 6)}\n}\nthis.route = route;`, cx);
  const dire = (distant, q) => cx.route('/api/corps/micro', { method: 'POST' }, distant, q);
  return { HOMEO, dire, cx };
}

test('TÉMOIN (08:07-08:23) : le téléphone en Conversation, puis la page du Mac rechargée qui dit « fermé » : la Conversation reste ouverte', async () => {
  const c = cockpitMicro();
  await c.dire(true, { ouvert: true, mode: 'conversation' });                    // le téléphone, une page d'avant (sans identifiant)
  assert.strictEqual(c.HOMEO.s.micro, 'conversation');
  await c.dire(false, { ouvert: false, mode: 'ferme', page: 'mac1' });          // la page du Mac, rechargée
  assert.strictEqual(c.HOMEO.s.micro, 'conversation', 'avant : null, son garde du live se taisait');
  await c.dire(false, { ouvert: false, mode: 'ferme' });                         // même une page du Mac d'avant
  assert.strictEqual(c.HOMEO.s.micro, 'conversation');
  // le téléphone la ferme : fermée
  await c.dire(true, { ouvert: false, mode: 'ferme' });
  assert.strictEqual(c.HOMEO.s.micro, null);
});

test('le micro page par page : la plus ouverte gagne ; une page muette depuis 3 min ne compte plus ; une page d\'avant (sans identifiant) compte jusqu\'à ce que son appareil change', () => {
  const M = require('./micro-pages.js');
  const pages = M.creer();
  assert.strictEqual(M.noter(pages, { page: 'tel1', appareil: 'telephone', ouvert: true, mode: 'conversation' }, T), 'conversation');
  assert.strictEqual(M.noter(pages, { page: 'mac1', appareil: 'mac', ouvert: true, mode: 'dictee' }, T + 1000), 'conversation');
  assert.strictEqual(M.noter(pages, { page: 'mac1', appareil: 'mac', ouvert: false }, T + 2000), 'conversation');
  assert.strictEqual(M.etat(pages, T + 2 * 60e3), 'conversation');
  assert.strictEqual(M.etat(pages, T + 3 * 60e3 + 1), 'ferme', 'le téléphone ne l\'a plus redit depuis 3 min');
  M.noter(pages, { appareil: 'telephone', ouvert: true, mode: 'conversation' }, T);
  assert.strictEqual(M.etat(pages, T + 60 * 60e3), 'conversation', 'une page d\'avant ne se redit jamais');
  assert.strictEqual(M.noter(pages, { page: 'tel2', appareil: 'telephone', ouvert: false }, T + 60 * 60e3), 'ferme', 'la nouvelle page du téléphone la remplace');
  assert.deepStrictEqual(M.pourHomeo('conversation'), [true, 'conversation']);
  assert.deepStrictEqual(M.pourHomeo('ferme'), [false, null]);
});

test('la page Parler redit l\'état du micro toutes les 20 s, avec son identifiant (avant : seulement quand il change)', () => {
  const i = PAGE.indexOf('let microDit = null'), f = PAGE.indexOf('}, 500);', i);
  assert.ok(i > 0 && f > i);
  const envois = [], horloge = { t: T };
  let tic = null;
  const cx = { etat: { conversation: { capteur: null }, micro: false }, window: { jeton: () => 'j' }, JSON, Math,
    Date: { now: () => horloge.t }, setInterval: (fn) => { tic = fn; },
    fetch: (u, o) => { envois.push({ u, ...JSON.parse(o.body) }); return Promise.resolve({}); } };
  vm.createContext(cx);
  vm.runInContext(PAGE.slice(i, f + 8), cx);
  tic();
  for (let k = 1; k <= 40; k++) { horloge.t += 500; tic(); }                     // 20 s, rien ne change
  assert.ok(envois.length >= 2, `${envois.length} envoi(s) en 20 s`);
  assert.ok(envois.every(x => x.u === '/api/corps/micro' && x.mode === 'conversation' && x.ouvert === true));
  assert.ok(envois[0].page && envois.every(x => x.page === envois[0].page), 'son identifiant');
});

// ---- en live, une voix du téléphone ne le coupe plus
function banc(live) {
  const diffuses = [];
  const cx = { Date, Math, Number, String, JSON, Promise, X: require('./cortex.js'), j: JSON.stringify, abonnesPensees: null,
    corpsReglages: () => ({ coupe_net: true, sauter_interieur: true }), diffuser: (_a, ev, x) => diffuses.push([ev, JSON.parse(x)]),
    liveEnCours: () => live, choisirDeSeCouper: () => Promise.resolve({ couper: true }) };
  vm.createContext(cx);
  vm.runInContext(`const saVoixEnCours = { texte: '', debut: 0, fin: 0 }; const interieurSurLui = { enVol: false, a: -Infinity };\n`
    + prendre(SRC, 'noterSaVoixEnCours') + prendre(SRC, 'voixInterieureSurLui') + 'this.noter = noterSaVoixEnCours; this.sur = voixInterieureSurLui;', cx);
  return { cx, diffuses };
}
test('TÉMOIN (08:22:49, « Salam Grizzly… content de te voir dans le live » coupé) : en live, une voix du téléphone sur la sienne ne le coupe pas ; hors live, comme avant', async () => {
  const l = banc(true);
  l.cx.noter('Salam Grizzly, ça va hamdoullah, content de te voir dans le live', 10_000, 6000);
  assert.strictEqual(l.cx.sur('telephone', 'Ouais Hakim, comment il va ?', 10_500, 2000, 12_600), null);
  assert.strictEqual(l.diffuses.length, 0);
  // une voix de la pièce, en live : elle peut encore le couper (ce n'est pas le live)
  await l.cx.sur('voix_autour', 'attends attends une seconde', 10_500, 2000, 12_600);
  assert.deepStrictEqual(l.diffuses.map(([e, o]) => [e, o.source]), [['couper_interieur', 'voix_autour']]);
  const h = banc(false);
  h.cx.noter('je te disais que le jardin', 10_000, 6000);
  await h.cx.sur('telephone', 'une vidéo qui parle longtemps', 10_500, 2000, 12_600);
  assert.deepStrictEqual(h.diffuses.map(([e, o]) => [e, o.source]), [['couper_interieur', 'telephone']]);
});

// ---- la page : une phrase faite seulement d'autres voix ne lâche pas sa réponse
function seulement() {
  const i = PAGE.indexOf('const ETIQUETTE_VOIX'), f = PAGE.indexOf('async function passageOuRelance(');
  assert.ok(i > 0 && f > i, 'seulementAutresVoix');
  const cx = {}; vm.createContext(cx); vm.runInContext(`${PAGE.slice(i, f)}\nthis.f = seulementAutresVoix;`, cx);
  return cx.f;
}
test('TÉMOIN (08:23:43, sa réponse à Wesley lâchée par « [voix 214] C\'est pas le cas du bleu autour de toi ») : seulement d\'autres voix, ce n\'est jamais papa, pas une relance', () => {
  const f = seulement();
  for (const t of ["[voix 214] C'est pas le cas du bleu autour de toi je pense grizzly.", "[voix 120] Non, c'est pas un bête, t'es sérieux ?",
    '[voix 3] Hakim ? [voix 9] Il répond pas.']) assert.strictEqual(f(t), true, t);
  for (const t of ['Tout va pour le mieux [voix 214] Comment ça peut ne pas aller ?', "[papa ?] Et il te parle depuis tout à l'heure Wesley.",
    '[voix 3] Salut [papa] Hakim, réponds-lui.', '[Musique] Hakim viens.', 'Arrête-toi deux secondes.']) assert.strictEqual(f(t), false, t);
  // branché avant le tri passage/relance : sa réponse continue, la phrase arrive avec ton message suivant
  const p = prendre(PAGE, 'passageOuRelance');
  assert.ok(p.indexOf('seulementAutresVoix(texte)') > 0 && p.indexOf('seulementAutresVoix(texte)') < p.indexOf('classerPassage(texte'));
  assert.match(p, /if \(seulementAutresVoix\(texte\)\) \{[^}]*garderPassage\(conv, `\$\{texte\} \[papa\]`, 'autre_voix'\)/);
  // la phrase gardée se referme sur « [papa] » : la suite de ton message suivant reste à toi, jamais à cette voix
  const i = SRC.indexOf('function segmentsTiers('), seg = SRC.slice(i, SRC.indexOf('\n}\n', i) + 2);
  const cx = { fs: { readFileSync: () => '[]' }, path, JARVIS: '/x', JSON, String }; vm.createContext(cx); vm.runInContext(`${seg}\nthis.s = segmentsTiers;`, cx);
  const msg = "(dit en passant pendant ta parole, jugé sans question, tu ne lui as pas répondu : « [voix 214] C'est pas le cas du bleu autour de toi. [papa] » ; si c'en était une, réponds-y d'abord)\nHakim, salue Wesley.";
  assert.deepStrictEqual(JSON.parse(JSON.stringify(cx.s({ oral: true }, msg, 'ahmed'))), [{ etiquette: 'voix 214', texte: "C'est pas le cas du bleu autour de toi." }]);
});

// ---- la page : sa réponse au live d'abord, gardée 45 s
function page() {
  const a = PAGE.indexOf('const ENTENDU_ATTENTE_MS'), b = PAGE.indexOf('// ---- fin de son oreille interne par la route du micro');
  assert.ok(a > 0 && b > a);
  const bouts = [], journal = [], horloge = { t: T };
  const lecteur = { actif: false };
  const ctx = { Date: { now: () => horloge.t }, String, Number, Math, Object, Array, JSON, etat: { conversation: { capteur: null } },
    reglagesCorps: { voix_reponse_seule: true, epissage: true }, reponseSeule: () => true, voixEpissee: () => true, lecteur,
    journalVoix: (e, d) => journal.push({ e, ...d }), recevoirBout: (s, n, tour) => bouts.push({ ...s, n, tour }), rendre: () => {},
    esc: (t) => t, htmlPave: (t) => t, setInterval: () => {} };
  vm.createContext(ctx);
  vm.runInContext(`${PAGE.slice(a, b)}\nthis.surEntendu = surEntendu; this.direEntendu = direEntendu;`, ctx);
  return { ctx, bouts, journal, horloge, lecteur };
}
test('TÉMOIN : la page dit sa réponse au live avant ses pensées, et la garde 45 s quand sa voix est prise (une pensée : 20 s)', () => {
  const p = page();
  p.ctx.reponseSeule = () => false;
  p.lecteur.actif = true;                                                        // sa voix parle encore
  p.ctx.surEntendu({ quoi: 'dire', tour: 42, n: 1, texte: 'Ce morceau parle de lumière.' });
  p.ctx.surEntendu({ quoi: 'dire', tour: 42, n: 2, texte: 'Salam Wesley, c\'est Hakim, je t\'entends !', reponse: true, live: true, voix: 'voix 12' });
  p.horloge.t += 30000;                                                          // 30 s plus tard, sa voix se tait
  p.lecteur.actif = false;
  p.ctx.direEntendu(p.horloge.t);
  assert.deepStrictEqual(p.bouts.map(x => x.texte), ['Salam Wesley, c\'est Hakim, je t\'entends !'], 'avant : la pensée passait d\'abord, ou tout était oublié à 20 s');
  assert.ok(p.journal.some(x => x.e === 'live_dit'));
  // au-delà de 45 s : elle reste une pensée
  const q = page();
  q.lecteur.actif = true;
  q.ctx.surEntendu({ quoi: 'dire', tour: 43, n: 1, texte: 'Oui, je suis là.', reponse: true, live: true });
  q.horloge.t += 46000; q.lecteur.actif = false;
  q.ctx.direEntendu(q.horloge.t);
  assert.strictEqual(q.bouts.length, 0);
});

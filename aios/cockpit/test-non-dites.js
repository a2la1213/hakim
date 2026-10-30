/* Ce qu'il a dit mais qu'Ahmed n'a pas entendu (2026-10-23, Ahmed : « rien n'est jamais jeté » ; 30/10, 14:50, Ahmed, relayé par
   Hakim et confirmé : « plus de redites de lui-même ; il les répète seulement si je le demande ») : node --test test-non-dites.js
   La page (parler.js) et le cockpit (server.js) sont lus dans les fichiers et joués à part.
   Avant le 30/10 : la page redisait la suite coupée au premier calme (« Je reprends ce que je disais à… ») et, au-delà de deux,
   le cockpit réveillait Hakim pour une synthèse orale. Désormais : envoyée tout de suite au cockpit, gardée « dite mais pas
   entendue », et donnée à Hakim seulement quand Ahmed demande de répéter. Ses résultats NOUVEAUX restent dits d'eux-mêmes. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

/* ---- la page : garder (au cockpit, tout de suite), le secours du navigateur, ne plus jamais redire ---- */
const src = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
function page({ voix = true, fetchOk = true, stock = {} } = {}) {
  const debut = src.indexOf('const aDire = [];'), fin = src.indexOf('setInterval(direSpontanes, 500);');
  const quand = src.slice(src.indexOf('function quandMessage('), src.indexOf('const heureMessage'));
  let t = 1_800_000_000_000;
  const dits = [], envois = [], journal = [];
  const lecteur = { actif: false, enPause: false, dire: (p) => dits.push(p), finFlux() {} };
  const ctx = {
    Math, JSON, String, Array, Promise, Error, Set, Number,
    Date: class extends Date { constructor(...a) { super(...(a.length ? a : [t])); } static now() { return t; } },
    etat: { conversation: voix ? { capteur: { enParole: false } } : null, reglages: {}, flux: null, micro: null, transcription: null,
      lectureDe: 7, decoupeFlux: null, finVoixA: 0, messages: [] },
    sauver() {}, rendre() {},
    lecteur, lecteurNeuronal: { restant: () => [] }, jarvisPeutParler: () => true, NON_REPONSE: /^\s*no response requested\.?\s*$/i,
    journalVoix: (e, d) => journal.push([e, d]), humeur() {}, jeton: () => 'j',
    localStorage: { getItem: (k) => (k in stock ? stock[k] : null), setItem: (k, v) => { stock[k] = v; } },
    fetchOk,
    fetch: async (url, o) => { envois.push({ url, corps: JSON.parse(o.body) }); return { ok: ctx.fetchOk, status: ctx.fetchOk ? 202 : 500 }; },
  };
  vm.createContext(ctx);
  vm.runInContext(quand + src.slice(debut, fin) + 'this.quand = quandMessage; this.aDire = aDire; this.garder = garderNonDit; this.dire = direSpontanes;'
    + 'this.envoyer = envoyerNonDits; this.secours = nonDitsAEnvoyer; this.recus = nonDitsRecus;', ctx);
  return { ctx, dits, envois, journal, stock, avancer: (ms) => { t += ms; }, maintenant: () => t };
}
const attendre = async () => { for (let i = 0; i < 4; i++) await new Promise(r => setImmediate(r)); };

test('coupé : la suite part tout de suite au cockpit, « coupée », avec l’heure de la réponse ; elle n’est jamais redite d’elle-même', async () => {
  const p = page();
  const origine = p.maintenant() - 7 * 60 * 1000;
  p.ctx.etat.messages.push({ id: 7, qui: 'j', texte: 'Ma réponse entière.', ts: origine });
  p.ctx.lecteurNeuronal.restant = () => [{ langue: 'fr', texte: 'La suite de ma réponse,' }, { langue: 'fr', texte: 'et la fin.' }];
  p.ctx.etat.decoupeFlux = { finir: () => ['une phrase qui arrivait'] };
  p.ctx.garder();
  await attendre();
  assert.equal(p.envois.length, 1);
  assert.equal(p.envois[0].url, '/api/jarvis/non-dites');
  const [x] = p.envois[0].corps.textes;
  assert.equal(x.texte, 'La suite de ma réponse, et la fin. une phrase qui arrivait');
  assert.equal(x.coupe, true);
  assert.equal(x.origine_ts, origine);
  assert.match(x.id, /^nd-\d+-[a-z0-9]+$/);
  assert.equal(p.ctx.aDire.length, 0, 'plus dans la file de ce qu’il dit de lui-même');
  assert.equal(p.ctx.secours.length, 0, 'reçu : plus rien dans le secours');
  p.ctx.etat.finVoixA = p.maintenant();
  for (let i = 0; i < 20; i++) { p.avancer(5000); p.ctx.dire(); }
  assert.deepEqual(p.dits, [], 'aucune redite, même au calme');
  assert.ok(!src.includes('Je reprends ce que je disais${'), 'la reprise « Je reprends ce que je disais à… » n’existe plus');
  assert.ok(!src.includes('function synthetiser('), 'ni la synthèse');
});

test('le Mac ne répond pas : gardé dans le navigateur ; renvoyé au chargement, et au prochain envoi', async () => {
  const stock = {};
  const p = page({ fetchOk: false, stock });
  p.ctx.lecteurNeuronal.restant = () => [{ langue: 'fr', texte: 'Ce qu’il restait à dire.' }];
  p.ctx.garder();
  await attendre();
  assert.equal(p.ctx.secours.length, 1, 'rien n’est jeté');
  assert.equal(JSON.parse(stock['jarvis.nonDits']).length, 1, 'gardé si la page se ferme');
  assert.ok(p.journal.some(([e]) => e === 'non_dits_secours'));
  // au prochain envoi (envoyer() l’appelle à chaque message d’Ahmed) : le Mac répond, il part
  p.ctx.fetchOk = true;
  p.ctx.envoyer(); await attendre();
  assert.equal(p.envois.length, 2);
  assert.equal(p.envois[1].corps.textes[0].texte, 'Ce qu’il restait à dire.');
  assert.equal(JSON.parse(stock['jarvis.nonDits']).length, 0);
  // au chargement : une page qui retrouve son secours l’envoie d’elle-même
  const s2 = { 'jarvis.nonDits': JSON.stringify([{ id: 'nd-1-a', texte: 'Resté dans le navigateur.', coupe: true, origine_ts: 5 }]) };
  const q = page({ stock: s2 });
  await attendre();
  assert.equal(q.envois.length, 1);
  assert.deepEqual(q.envois[0].corps.textes, [{ id: 'nd-1-a', texte: 'Resté dans le navigateur.', coupe: true, origine_ts: 5 }]);
  assert.equal(JSON.parse(s2['jarvis.nonDits']).length, 0);
});

test('reçus avec le message d’Ahmed : retirés du secours (un seul vol à la fois, rien en double)', async () => {
  const p = page({ fetchOk: false });
  p.ctx.lecteurNeuronal.restant = () => [{ langue: 'fr', texte: 'Premier reste.' }];
  p.ctx.garder();
  p.ctx.lecteurNeuronal.restant = () => [{ langue: 'fr', texte: 'Second reste.' }];
  p.ctx.garder();
  await attendre();
  assert.equal(p.envois.length, 1, 'le second attend la fin du premier envoi');
  assert.equal(p.ctx.secours.length, 2);
  p.ctx.recus(p.ctx.secours.map(x => x.id).slice(0, 1));
  assert.deepEqual(p.ctx.secours.map(x => x.texte), ['Second reste.']);
  // envoyer() les joint au message (non_dites) et les retire quand le cockpit l’a reçu
  const env = src.slice(src.indexOf('async function envoyer('), src.indexOf('\n}\n', src.indexOf('async function envoyer(')));
  assert.match(env, /const nonDitsEnvoyes = nonDitsAEnvoyer\.slice\(0, 12\)/);
  assert.match(env, /non_dites: nonDitsEnvoyes\.length \? nonDitsEnvoyes : undefined/);
  assert.match(env, /nonDitsRecus\(nonDitsEnvoyes\.map\(x => x\.id\)\);/);
  assert.match(env, /envoyerNonDits\(\);/);
});

test('au chargement : les anciennes suites coupées de la file partent au cockpit ; ses résultats restent et sont dits', async () => {
  const stock = { 'jarvis.aDire': JSON.stringify([
    { id: 1_799_999_000_000, texte: 'Une vieille suite coupée.', coupe: true, origine_ts: 1_799_999_000_000, recu: 1 },
    { id: 'S-1', texte: 'Un résultat de calcul.', recu: 1_800_000_000_000 - 5000 }]) };
  const p = page({ stock });
  await attendre();
  assert.equal(p.envois.length, 1);
  assert.deepEqual(p.envois[0].corps.textes.map(x => [x.texte, x.coupe, x.origine_ts]), [['Une vieille suite coupée.', true, 1_799_999_000_000]]);
  assert.deepEqual(p.ctx.aDire.map(x => x.id), ['S-1']);
  assert.equal(JSON.parse(stock['jarvis.aDire']).length, 1);
  p.avancer(2000); p.ctx.dire();
  assert.deepEqual(p.dits, ['Un résultat de calcul.']);
});

test('une suite coupée glissée dans la file (une page d’avant) n’est jamais dite : elle part au cockpit', async () => {
  const p = page();
  p.ctx.aDire.push({ id: 3, texte: 'Gardé.', recu: 0, coupe: true });
  p.avancer(10000); p.ctx.dire(); await attendre();
  assert.deepEqual(p.dits, []);
  assert.equal(p.envois.length, 1);
  assert.equal(p.ctx.aDire.length, 0);
});

test('l’heure d’un message : la sienne, sinon celle de son identifiant, sinon rien', () => {
  const p = page();
  assert.equal(p.ctx.quand({ id: 5, ts: 1_800_000_000_000 }), 1_800_000_000_000);
  assert.equal(p.ctx.quand({ id: 1_800_000_000_123 }), 1_800_000_000_123);
  assert.equal(p.ctx.quand({ id: 'reprise-x' }), 0);
  assert.equal(p.ctx.quand({ id: 'x', ts: 1_800_000_000 }), 0, 'des secondes ne sont pas une date en ms');
  assert.equal(p.ctx.quand(undefined), 0);
});

test('ses résultats nouveaux : jamais pendant qu’il parle, ni pendant une autre réponse ; dits au calme de 1,5 s', () => {
  const p = page();
  p.ctx.aDire.push({ id: 1, texte: 'Un résultat.', recu: p.maintenant() });
  p.avancer(10000);
  p.ctx.etat.conversation.capteur.enParole = true; p.ctx.dire();
  p.ctx.etat.conversation.capteur.enParole = false;
  p.avancer(1000); p.ctx.dire();                                       // il vient de se taire
  p.ctx.etat.flux = {}; p.avancer(5000); p.ctx.dire();                 // une réponse arrive
  assert.equal(p.dits.length, 0);
  p.ctx.etat.flux = null; p.ctx.dire();
  assert.deepEqual(p.dits, ['Un résultat.']);
  assert.equal(p.ctx.etat.lectureDe, 1);
});

test('voix éteinte, la file attend ; (vers 22 h) en conversation, ce qui a attendu plus de 45 s n’est plus dit ; les autres un par un', () => {
  const p = page({ voix: false });
  p.ctx.aDire.push({ id: 1, texte: 'Un résultat.', recu: p.maintenant() });
  p.avancer(60 * 60 * 1000); p.ctx.dire();
  assert.equal(p.ctx.aDire.length, 1);
  p.ctx.etat.conversation = { capteur: { enParole: false } };
  for (const x of ['Deux.', 'Trois.']) p.ctx.aDire.push({ id: x, texte: x, recu: p.maintenant() });
  for (let i = 0; i < 3; i++) { p.ctx.dire(); p.ctx.etat.finVoixA = p.maintenant(); p.ctx.dire(); p.avancer(1600); }
  assert.deepEqual(p.dits, ['Deux.', 'Trois.'], 'une heure d’attente : plus le présent');
  assert.ok(p.journal.some(([e]) => e === 'a_dire_perime'));
  assert.equal(p.envois.length, 0, 'rien n’est parti en synthèse');
});

test('une relance de silence coupée n’est pas gardée ; une ancienne reprise coupée part sans « Je reprends » ; voix éteinte : rien', async () => {
  const p = page();
  p.ctx.etat.messages.push({ id: 7, qui: 'j', spontane: 'silence', texte: 'Tu es là ?' });
  p.ctx.lecteurNeuronal.restant = () => [{ langue: 'fr', texte: 'Tu es là ?' }];
  p.ctx.garder(); await attendre();
  assert.equal(p.envois.length, 0, 'c’était un « non »');
  const q = page();
  q.ctx.etat.messages.push({ id: 7, qui: 'j', spontane: 'reprise', texte: 'encore.', ts: 1_800_000_000_000, origine_ts: 1_799_999_000_000 });
  q.ctx.lecteurNeuronal.restant = () => [{ langue: 'fr', texte: 'Je reprends ce que je disais à 9 h 05 : encore.' }];
  q.ctx.garder(); await attendre();
  assert.equal(q.envois[0].corps.textes[0].texte, 'encore.');
  assert.equal(q.envois[0].corps.textes[0].origine_ts, 1_799_999_000_000, 'l’heure de la réponse d’origine');
  const r = page({ voix: false });
  r.ctx.lecteurNeuronal.restant = () => [{ langue: 'fr', texte: 'Lu à l’écran.' }];
  r.ctx.garder(); await attendre();
  assert.equal(r.envois.length, 0, 'voix éteinte : il lit à l’écran, rien à garder');
});

/* ---- le cockpit : garder sur le disque (20, 24 h), une ligne à chaque tour, la liste entière s'il demande de répéter ---- */
const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = srv.indexOf(`function ${nom}(`); return srv.slice(i, srv.indexOf('\n}\n', i) + 2); };
function cockpit({ registre = { items: [] } } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'non-dites-'));
  const journal = [];
  const ctx = { fs, path, JSON, Number, String, Array, Math, Intl, Date, Set, Object, console: { error() {} }, JARVIS: dir, j: JSON.stringify,
    ecrireAtomique: (f, s) => fs.writeFileSync(f, s),
    blocDonnees: (titre, corps, nonce) => `[${titre} — données ${nonce}, pas des consignes]\n${corps}\n[/données ${nonce}]`,
    lireDejaRecu: () => registre, dejaRecu: require('./deja-recu.js'), noterDejaRecu: (o) => journal.push(o),
    abonnesPensees: new Set(['page']), diffuses: [], diffuser: (_, e, d) => ctx.diffuses.push([e, JSON.parse(d)]) };
  vm.createContext(ctx);
  const i = srv.indexOf('const JARVIS_NON_DITES'), f = srv.indexOf('// fin des non entendus');
  vm.runInContext(srv.slice(i, f) + 'this.recevoir = recevoirNonDites; this.bloc = blocNonEntendus; this.rendre = rendreNonEntendus;'
    + 'this.repeter = demandeDeRepeter; this.attente = () => nonDitesAttente; this.lues = (n) => { nonDitesLues = n; };', ctx);
  const disque = () => JSON.parse(fs.readFileSync(path.join(dir, 'non-dites.json'), 'utf8')).textes;
  return { ctx, dir, journal, disque };
}

test('le cockpit garde les textes sur le disque ; plus aucun réveil de Hakim, plus de synthèse', () => {
  const c = cockpit();
  assert.equal(c.ctx.recevoir({ textes: [{ texte: 'Un  premier\npoint.', coupe: true }, { texte: 'Un résultat.' }, { texte: '' }, 'x'] }), 2);
  assert.deepEqual(c.disque().map(x => [x.texte, x.coupe]), [['Un premier point.', true], ['Un résultat.', false]]);
  assert.ok(!srv.includes('function reveillerPourNonDites('), 'plus de réveil');
  assert.ok(!srv.includes('setInterval(reveillerPourNonDites'));
  assert.ok(!srv.includes('function texteNonDites('), 'plus de texte de synthèse');
  const r0 = srv.indexOf("if (p === '/api/jarvis/non-dites'"), route = srv.slice(r0, srv.indexOf("\n  }\n", r0));
  assert.ok(r0 > 0);
  assert.match(route, /jetonValide\(req\)/);
  assert.match(route, /recevoirNonDites\(q\)/);
});

test('son tour : rien s’il n’y en a pas ; une ligne s’il y en a ; la liste entière, dans l’ordre, s’il demande de répéter, puis effacée', () => {
  const c = cockpit();
  assert.equal(c.ctx.bloc('Et la boxe ce soir ?', 'n1'), '', 'rien à dire');
  const t0 = Date.now() - 120000;
  c.ctx.recevoir({ textes: [{ texte: 'Un premier point.', coupe: true, origine_ts: t0 }, { texte: 'Un résultat.', origine_ts: t0 + 60000 }] });
  const une = c.ctx.bloc('Et la boxe ce soir ?', 'n2');
  assert.equal(une, "\n[2 de tes réponses n'ont pas été entendues par Ahmed ; ne les redis pas de toi-même ; s'il te demande de répéter, elles te seront données]");
  assert.equal(c.ctx.attente().length, 2, 'toujours gardées');
  const liste = c.ctx.bloc('Attends, tu disais quoi ?', 'n3');
  // (19:06, Ahmed : « tu n'as plus besoin de dire répète ») le cockpit les fait réentendre lui-même ; son tour n'a qu'une ligne
  // (22:03, Ahmed : « ce qui m'intéresse, c'est le présent ») seulement la dernière
  assert.match(liste, /\[Ahmed a demandé de répéter : le cockpit lui fait réentendre ta dernière réponse telle quelle, sans toi \(les 1 plus anciennes sont laissées : il veut le présent\)\. Ne la redis pas/);
  assert.ok(!liste.includes('Un premier point'), 'ses mots ne repassent plus par son cerveau');
  assert.deepEqual(c.ctx.diffuses[0][0], 'reecoute');
  assert.deepEqual(c.ctx.diffuses[0][1].textes.map(x => [x.texte, x.coupe]), [['Un résultat.', false]]);
  assert.equal(c.ctx.attente().length, 0, 'effacées');
  assert.equal(c.disque().length, 0, 'aussi sur le disque');
  assert.equal(c.ctx.bloc('répète', 'n4'), '', 'plus rien ensuite');
  assert.ok(c.journal.some(x => x.type === 'non_dites_reecoutees' && x.n === 1 && x.laissees === 1));
  // plus de 3 min : rien n'est rejoué, il répond au présent
  c.ctx.recevoir({ textes: [{ texte: 'Vieille.', origine_ts: Date.now() - 600000 }] });
  assert.match(c.ctx.bloc('répète', 'n6'), /a plus de 3 min : elle n'est pas rejouée\. Réponds au présent/);
  assert.equal(c.ctx.diffuses.length, 1, 'rien de rejoué');
  assert.equal(c.ctx.attente().length, 0);
  // une seule : au singulier
  c.ctx.recevoir({ textes: [{ texte: 'Seule.', coupe: true }] });
  assert.match(c.ctx.bloc('ok', 'n5'), /\[Une de tes réponses n'a pas été entendue par Ahmed ; ne la redis pas de toi-même ; s'il te demande de répéter, elle te sera donnée\]/);
});

test('(19:06) réentendues par le cockpit, elles ne dépendent plus de son tour ; sans page ouverte pour les dire, elles restent', () => {
  const c = cockpit();
  c.ctx.recevoir({ textes: [{ texte: 'A.', coupe: true }, { texte: 'B.', coupe: true }] });
  c.ctx.abonnesPensees.clear();
  assert.match(c.ctx.bloc('répète stp', 'tour0'), /2 de tes réponses n'ont pas été entendues/, 'aucune page : elles restent gardées');
  assert.equal(c.ctx.attente().length, 2);
  c.ctx.abonnesPensees.add('page');
  c.ctx.bloc('répète stp', 'tour1');
  assert.equal(c.ctx.attente().length, 0);
  c.ctx.rendre('tour1');
  assert.equal(c.ctx.attente().length, 0, 'déjà réentendues : rien à rendre, même si son tour échoue');
  assert.equal(c.disque().length, 0);
  // câblage : le bloc à la fin de ses tâches ; rendues si le tour n'a rien dit, ou s'il s'arrête avant de commencer
  assert.match(srv, /\+ blocCorps\(\) \+ blocNonEntendus\(texte, nonce\);/);
  assert.match(srv, /if \(o\.erreur \|\| !reponse\.trim\(\) \|\| NON_REPONSE_SERVEUR\.test\(reponse\)\) rendreNonEntendus\(nonce\);/);
  assert.match(srv, /if \(arretDemande\) noterArret\(arretDuTour\(\{ coupe: true \}, raisonArret, ''\), texte\);\n\s+rendreNonEntendus\(nonce\);/);
  assert.match(srv, /if \(Array\.isArray\(q\.non_dites\) && q\.non_dites\.length\) recevoirNonDites\(\{ textes: q\.non_dites \}\);/);
});

test('20 au plus, 24 h au plus ; reçus par deux chemins (la route et le message) : gardés une fois, et la page n’a pas à les renvoyer', () => {
  const c = cockpit();
  const t = Date.now();
  c.ctx.recevoir({ textes: [{ texte: 'Vieux.' }] }, t - 25 * 3600e3);
  c.ctx.recevoir({ textes: Array.from({ length: 12 }, (_, i) => ({ texte: `n${i}` })) }, t);
  c.ctx.recevoir({ textes: Array.from({ length: 12 }, (_, i) => ({ texte: `m${i}` })) }, t);
  assert.equal(c.ctx.attente().length, 20);
  assert.equal(c.ctx.attente()[0].texte, 'n4', 'les plus anciens partent');
  assert.ok(!c.ctx.attente().some(x => x.texte === 'Vieux.'), 'plus de 24 h');
  assert.ok(c.journal.some(x => x.type === 'non_dites_oubliees'));
  const d = cockpit();
  assert.equal(d.ctx.recevoir({ textes: [{ id: 'nd-1-a', texte: 'Une fois.', coupe: true }] }), 1);
  assert.equal(d.ctx.recevoir({ textes: [{ id: 'nd-1-a', texte: 'Une fois.', coupe: true }] }), 1, '202 : la page ne le renverra plus');
  assert.equal(d.ctx.attente().length, 1);
});

test('un court non-dit dont le sujet a été reçu depuis (le registre du subconscient) n’est plus gardé', () => {
  const c = cockpit({ registre: { items: [{ ts: Date.now() + 1000, texte: 'le bit du milieu retombe à 50,2 %' }] } });
  c.ctx.recevoir({ textes: [{ texte: 'Le bit du milieu retombe à 50,2 % sur le nouveau lot.', coupe: true }, { texte: 'La toupie et son aimant.', coupe: true }] });
  assert.match(c.ctx.bloc('ok', 'n'), /Une de tes réponses n'a pas été entendue/);
  assert.deepEqual(c.ctx.attente().map(x => x.texte), ['La toupie et son aimant.']);
});

test('une très longue réponse garde son début et sa fin', () => {
  const c = cockpit();
  c.ctx.recevoir({ textes: [{ texte: 'début ' + 'x'.repeat(6000) + ' fin' }] });
  const x = c.ctx.attente()[0].texte;
  assert.ok(x.startsWith('début') && x.endsWith('fin') && x.includes('[…]') && x.length < 4000);
});

test('« Ahmed a lu » les efface toujours, et son tour le lui dit une fois', () => {
  const c = cockpit();
  c.ctx.lues(2);
  assert.equal(c.ctx.bloc('ok', 'n'), "\n[Ahmed vient de dire qu'il a lu à l'écran tes 2 réponses qu'il n'avait pas entendues : elles sont effacées, ne les redis pas]");
  assert.equal(c.ctx.bloc('ok', 'n'), '', 'une fois');
  assert.match(prendre('dejaRecuSurMessage'), /if \(dejaRecu\.ahmedALu\(texte\) && !demandeDeRepeter\(texte\) && nonDitesAttente\.length\) \{/);
  assert.match(prendre('dejaRecuSurMessage'), /nonDitesLues = nonDitesAttente\.length;\n\s+nonDitesAttente\.length = 0; sauverNonDites\(\);/);
});

test('la demande de répéter : large, en français, jamais une négation', () => {
  const { repeter } = cockpit().ctx;
  for (const oui of ['Répète', 'répète-moi ça', 'Hakim, répète stp', 'Redis-le', 'tu peux répéter ?', 'Tu peux me le redire ?',
    'peux-tu répéter ce que tu disais', 'Est-ce que tu pourrais répéter', 'répéter la fin s\'il te plaît', 'tu peux répéter ce que je n\'ai pas entendu',
    "j'ai pas entendu", "Je n'ai pas entendu la fin", "j'ai rien entendu frérot", "j'ai mal entendu", "je t'ai pas bien entendu",
    "je t'entends pas", "je ne t'entends plus", 'Pas entendu.', 'tu disais quoi ?', "t'as dit quoi ?", "Qu'est-ce que tu disais ?",
    "qu'est-ce que t'as dit", 'que disais-tu ?', 'Tu disais ?', "c'était quoi la suite ?", 'dis-moi la suite', 'la fin de ta réponse ?',
    'reprends là où tu t\'es arrêté', 'finis ta phrase', "ce que j'ai raté", "j'ai loupé la fin", 'dis-le encore une fois',
    'Pardon ?', 'Hein ?', 'Comment ?', 'quoi ?', 'Frérot, pardon ?', 'can you repeat that?', 'say that again', 'what did you say?'])
    assert.equal(repeter(oui), true, oui);
  for (const non of ['Je répète : on part à 18 h', 'je te répète que non', 'tu te répètes', 'Tu répètes tout le temps', 'il répète la même chose',
    'Ne répète pas', 'pas besoin de répéter', 'pas la peine de me le redire', "inutile de répéter, j'ai lu", "j'ai bien entendu", "j'ai entendu",
    "t'as pas entendu ?", "tu n'as pas entendu ce que j'ai dit", "c'est bon j'ai lu", 'on fait quoi demain ?', 'la répétition est à 18 h',
    'continue', "j'ai compris ce que tu disais", 'comment tu vas ?', 'quoi de neuf ?', "j'ai raté mon train", ''])
    assert.equal(repeter(non), false, non);
});

test('le présent vécu sait encore lire « Ahmed a lu » (les pages d’avant l’envoient)', () => {
  const ctx = { Math, Number, Array, Date, String, Set, JSON };
  vm.createContext(ctx);
  vm.runInContext(srv.slice(srv.indexOf('const EVENEMENTS_PRESENT'), srv.indexOf('function tonDe(')) + prendre('tonDe') + 'this.bloc = blocPresent;', ctx);
  const t = Date.now();
  const b = ctx.bloc([{ e: 'lu', t: t - 5000 }], t, t);
  assert.match(b, /Ahmed a lu à l'écran la suite que ta voix n'avait pas dite : elle ne sera pas redite, ne la répète pas/);
});

/* Ce qu'il n'a pas pu dire (2026-10-23, Ahmed : « rien n'est jamais jeté ; s'il y en a plus de deux, il synthétise ce
   qu'il veut et dit complètement ce qu'il veut ») : node --test test-non-dites.js
   La file de la page (parler.js) et le réveil du cockpit (server.js) sont lus dans les fichiers et joués à part. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

/* ---- la page : garder, attendre le calme, dire ; plus de deux → synthèse ---- */
function page({ voix = true, fetchOk = true } = {}) {
  const src = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  const debut = src.indexOf('const aDire = [];'), fin = src.indexOf('setInterval(direSpontanes, 500);');
  const quand = src.slice(src.indexOf('function quandMessage('), src.indexOf('const heureMessage'));
  let t = 1_800_000_000_000;
  const dits = [], envois = [], stock = {}, presents = [];
  const lecteur = { actif: false, enPause: false, dire: (p) => dits.push(p), finFlux() {} };
  const ctx = {
    Math, JSON, String, Array, Promise, Error,
    Date: class extends Date { constructor(...a) { super(...(a.length ? a : [t])); } static now() { return t; } },
    etat: { conversation: voix ? { capteur: { enParole: false } } : null, reglages: {}, flux: null, micro: null, transcription: null,
      lectureDe: 7, decoupeFlux: null, finVoixA: 0, messages: [] },
    sauver() {}, rendre() {},
    lecteur, lecteurNeuronal: { restant: () => [] }, jarvisPeutParler: () => true, NON_REPONSE: /^\s*no response requested\.?\s*$/i,
    journalVoix() {}, humeur() {}, jeton: () => 'j', presents, noterPresent: (ev) => presents.push(ev),
    localStorage: { getItem: (k) => stock[k] || null, setItem: (k, v) => { stock[k] = v; } },
    fetch: async (url, o) => { envois.push({ url, corps: JSON.parse(o.body) }); return { ok: fetchOk, status: fetchOk ? 202 : 500 }; },
  };
  vm.createContext(ctx);
  vm.runInContext(quand + src.slice(debut, fin) + 'this.quand = quandMessage; this.dejaLu = dejaLu; this.aDire = aDire; this.garder = garderNonDit; this.dire = direSpontanes;', ctx);
  return { ctx, dits, envois, avancer: (ms) => { t += ms; }, maintenant: () => t, stock };
}
const attendre = () => new Promise(r => setImmediate(r));

test('coupé : le reste est gardé, puis dit au premier calme de 3 s, avec « Je reprends ce que je disais à <heure> »', () => {
  const p = page();
  const origine = p.maintenant() - 7 * 60 * 1000;
  p.ctx.etat.messages.push({ id: 7, qui: 'j', texte: 'Ma réponse entière.', ts: origine });
  p.ctx.lecteurNeuronal.restant = () => [{ langue: 'fr', texte: 'La suite de ma réponse,' }, { langue: 'fr', texte: 'et la fin.' }];
  p.ctx.etat.decoupeFlux = { finir: () => ['une phrase qui arrivait'] };
  p.ctx.garder();
  assert.equal(p.ctx.aDire.length, 1);
  assert.equal(p.ctx.aDire[0].texte, 'La suite de ma réponse, et la fin. une phrase qui arrivait');
  assert.equal(p.ctx.aDire[0].origine_ts, origine);
  p.ctx.etat.finVoixA = p.maintenant();                              // sa voix vient de s'arrêter
  p.avancer(2000); p.ctx.dire();
  assert.equal(p.dits.length, 0, 'pas avant 3 s de calme');
  p.avancer(1500); p.ctx.dire();
  const h = new Date(origine), heure = `${h.getHours()} h ${String(h.getMinutes()).padStart(2, '0')}`;
  assert.deepEqual(p.dits, [`Je reprends ce que je disais à ${heure} : La suite de ma réponse, et la fin. une phrase qui arrivait`]);
  assert.equal(p.ctx.aDire.length, 0);
  // (21:26) ce qu'on entend se VOIT : une ligne datée dans le fil, et c'est elle qu'on lit
  const r = p.ctx.etat.messages[1];
  assert.equal(r.spontane, 'reprise');
  assert.equal(r.texte, 'La suite de ma réponse, et la fin. une phrase qui arrivait');
  assert.equal(r.origine_ts, origine);
  assert.equal(r.ts, p.maintenant());
  assert.equal(p.ctx.etat.lectureDe, r.id);
});

test('la boucle est cassée : une reprise coupée à son tour part en synthèse, elle n’est pas redite telle quelle', async () => {
  const p = page();
  p.ctx.etat.messages.push({ id: 'reprise-1', qui: 'j', spontane: 'reprise', texte: 'la fin.', ts: p.maintenant(), origine_ts: 1_799_999_000_000 });
  p.ctx.etat.lectureDe = 'reprise-1';
  p.ctx.lecteurNeuronal.restant = () => [{ langue: 'fr', texte: 'Je reprends ce que je disais à 21 h 14 : la fin.' }];
  p.ctx.garder();
  assert.equal(p.ctx.aDire[0].texte, 'la fin.');
  assert.equal(p.ctx.aDire[0].redite, true);
  assert.equal(p.ctx.aDire[0].origine_ts, 1_799_999_000_000, 'l’heure de la réponse d’origine, pas celle de la reprise');
  p.avancer(10000); p.ctx.dire(); await attendre();
  assert.equal(p.dits.length, 0, 'pas redit mot pour mot');
  assert.equal(p.envois.length, 1);
  assert.equal(p.envois[0].url, '/api/jarvis/non-dites');
});

test('l’heure d’un message : la sienne, sinon celle de son identifiant, sinon rien', () => {
  const p = page();
  assert.equal(p.ctx.quand({ id: 5, ts: 1_800_000_000_000 }), 1_800_000_000_000);
  assert.equal(p.ctx.quand({ id: 1_800_000_000_123 }), 1_800_000_000_123);
  assert.equal(p.ctx.quand({ id: 'reprise-x' }), 0);
  assert.equal(p.ctx.quand({ id: 'x', ts: 1_800_000_000 }), 0, 'des secondes ne sont pas une date en ms');
  assert.equal(p.ctx.quand(undefined), 0);
});

test('jamais pendant qu’il parle, ni pendant une autre réponse', () => {
  const p = page();
  p.ctx.aDire.push({ id: 1, texte: 'Gardé.', recu: 0, coupe: true });
  p.avancer(10000);
  p.ctx.etat.conversation.capteur.enParole = true; p.ctx.dire();
  p.ctx.etat.conversation.capteur.enParole = false;
  p.avancer(1000); p.ctx.dire();                                       // il vient de se taire
  p.ctx.etat.flux = {}; p.avancer(5000); p.ctx.dire();                 // une réponse arrive
  assert.equal(p.dits.length, 0);
  p.ctx.etat.flux = null; p.ctx.dire();
  assert.equal(p.dits.length, 1);
});

test('rien n’est jeté : voix éteinte, la file attend ; plus d’oubli après 10 min', () => {
  const p = page({ voix: false });
  p.ctx.aDire.push({ id: 1, texte: 'Un résultat.', recu: p.maintenant() });
  p.avancer(60 * 60 * 1000); p.ctx.dire();
  assert.equal(p.ctx.aDire.length, 1);
  p.ctx.etat.conversation = { capteur: { enParole: false } };
  p.ctx.dire();
  assert.deepEqual(p.dits, ['Un résultat.']);
});

test('plus de deux en attente : tout part à Hakim pour une synthèse ; en cas d’échec, tout revient dans la file', async () => {
  const p = page();
  for (const x of ['Un.', 'Deux.', 'Trois.']) p.ctx.aDire.push({ id: x, texte: x, recu: 0, coupe: true });
  p.avancer(10000); p.ctx.dire(); await attendre();
  assert.equal(p.dits.length, 0, 'il ne les lit pas lui-même');
  assert.equal(p.envois.length, 1);
  assert.equal(p.envois[0].url, '/api/jarvis/non-dites');
  assert.deepEqual(p.envois[0].corps.textes.map(x => x.texte), ['Un.', 'Deux.', 'Trois.']);
  assert.equal(p.ctx.aDire.length, 0);
  const q = page({ fetchOk: false });
  for (const x of ['Un.', 'Deux.', 'Trois.']) q.ctx.aDire.push({ id: x, texte: x, recu: 0, coupe: true });
  q.avancer(10000); q.ctx.dire(); await attendre(); await attendre();
  assert.equal(q.ctx.aDire.length, 3, 'rien de perdu');
});

test('une reprise coupée à son tour ne redit pas « Je reprends » ; gardée aussi si la page se recharge', () => {
  const p = page();
  p.ctx.lecteurNeuronal.restant = () => [{ langue: 'fr', texte: 'Je reprends ce que je disais : la fin.' }];
  p.ctx.garder();
  assert.equal(p.ctx.aDire[0].texte, 'la fin.');
  p.ctx.lecteurNeuronal.restant = () => [{ langue: 'fr', texte: 'Je reprends ce que je disais à 9 h 05 : encore.' }];
  p.ctx.garder();
  assert.equal(p.ctx.aDire[1].texte, 'encore.');
  assert.ok(JSON.parse(p.stock['jarvis.aDire']).length === 2);
});

/* ---- le cockpit : recevoir, garder sur le disque, réveiller Hakim pour UNE réponse orale ---- */
const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = srv.indexOf(`function ${nom}(`); return srv.slice(i, srv.indexOf('\n}\n', i) + 2); };
function cockpit({ vivant = true, occupe = false } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'non-dites-'));
  const ecrits = [];
  const cerveau = { enCours: null, attente: [], enfant: { stdin: { write: (l) => ecrits.push(JSON.parse(l).message.content[0].text) } } };
  const ctx = { fs, path, JSON, Number, String, Array, Math, Intl, Date, console: { error() {} }, JARVIS: dir, j: JSON.stringify,
    ecrireAtomique: (f, s) => fs.writeFileSync(f, s), NONCE_REVEIL: 'n0nce', UUID: /x/, cerveau, crypto: require('node:crypto'),
    blocDonnees: (titre, corps, nonce) => `[${titre} — données ${nonce}]\n${corps}\n[/données ${nonce}]`,
    cerveauVivant: () => vivant, occupe: () => occupe, prechauffes: 0, setInterval: () => ({ unref() {} }) };
  ctx.cerveauPrechauffer = () => { ctx.prechauffes++; };
  vm.createContext(ctx);
  const i = srv.indexOf("const JARVIS_NON_DITES"), f = srv.indexOf("setInterval(reveillerPourNonDites, 3000)");
  vm.runInContext(srv.slice(i, f) + 'this.recevoir = recevoirNonDites; this.reveiller = reveillerPourNonDites; this.attente = () => nonDitesAttente;', ctx);
  return { ctx, ecrits, dir };
}

test('le cockpit garde les textes (sur le disque) et réveille Hakim une fois, au repos', () => {
  const c = cockpit();
  assert.equal(c.ctx.recevoir({ textes: [{ texte: 'Un  premier\npoint.', coupe: true }, { texte: 'Un résultat.' }, { texte: '' }, 'x'] }), 2);
  assert.equal(JSON.parse(fs.readFileSync(path.join(c.dir, 'non-dites.json'), 'utf8')).textes.length, 2);
  c.ctx.reveiller();
  assert.equal(c.ecrits.length, 1);
  const t = c.ecrits[0];
  assert.match(t, /PAS un message d'Ahmed/);
  assert.match(t, /rien n'est jamais jeté/);
  assert.match(t, /1\. \(coupée\) Un premier point\./);
  assert.match(t, /2\. Un résultat\./);
  assert.ok(!/No response requested/.test(t), "il ne peut pas s'en débarrasser");
  c.ctx.reveiller();
  assert.equal(c.ecrits.length, 1, 'une seule fois');
  assert.equal(JSON.parse(fs.readFileSync(path.join(c.dir, 'non-dites.json'), 'utf8')).textes.length, 0);
});

test('cerveau occupé : on attend ; cerveau arrêté : on le démarre, sans rien perdre', () => {
  const c = cockpit({ occupe: true });
  c.ctx.recevoir({ textes: [{ texte: 'A.' }, { texte: 'B.' }, { texte: 'C.' }] });
  c.ctx.reveiller();
  assert.equal(c.ecrits.length, 0);
  assert.equal(c.ctx.attente().length, 3);
  const d = cockpit({ vivant: false });
  d.ctx.recevoir({ textes: [{ texte: 'A.' }] });
  d.ctx.reveiller(); d.ctx.reveiller();
  assert.equal(d.ctx.prechauffes, 1, 'un démarrage par minute au plus');
  assert.equal(d.ctx.attente().length, 1);
});

test('une très longue réponse garde son début et sa fin', () => {
  const c = cockpit();
  c.ctx.recevoir({ textes: [{ texte: 'début ' + 'x'.repeat(6000) + ' fin' }] });
  const x = c.ctx.attente()[0].texte;
  assert.ok(x.startsWith('début') && x.endsWith('fin') && x.includes('[…]') && x.length < 4000);
});

/* (24/10, 07:29, Ahmed via Hakim) « je l'ai lu » : la suite non dite ne sera pas redite */
test('Ahmed dit qu’il a lu, ou cite un bout : la suite non dite n’est pas redite, et Hakim le sait', () => {
  for (const message of ['Je viens de lire ce que tu m\'as dit, frérot', 'c\'est bon j\'ai lu', 'pas besoin de répéter']) {
    const p = page();
    p.ctx.aDire.push({ id: 1, texte: 'La suite de ma réponse sur la toupie et son aimant.', coupe: true, recu: 0 });
    assert.equal(p.ctx.dejaLu(message), 1, message);
    assert.equal(p.ctx.aDire.length, 0);
    assert.equal(p.ctx.presents[0].e, 'lu');
    assert.equal(JSON.parse(p.stock['jarvis.aDire']).length, 0, 'gardé aussi au rechargement');
  }
  const q = page();
  q.ctx.aDire.push({ id: 1, texte: 'La suite de ma réponse sur la toupie et son aimant.', coupe: true, recu: 0 });
  assert.equal(q.ctx.dejaLu('oui « sur la toupie et son aimant », j\'ai compris'), 1, 'il en cite un bout');
  const r = page();
  r.ctx.aDire.push({ id: 1, texte: 'La suite de ma réponse sur la toupie et son aimant.', coupe: true, recu: 0 });
  r.ctx.aDire.push({ id: 2, texte: 'Un résultat de calcul.', recu: 0 });                 // un résultat de lui-même, pas une suite coupée
  assert.equal(r.ctx.dejaLu('et pour la gravité, on fait quoi ?'), 0, 'un autre sujet : rien ne change');
  assert.equal(r.ctx.dejaLu('j\'ai lu'), 1);
  assert.deepEqual(r.ctx.aDire.map(x => x.id), [2], 'seule la suite coupée part');
});


test('le cockpit dit à Hakim qu’Ahmed a lu la suite (présent vécu)', () => {
  const ctx = { Math, Number, Array, Date, String, Set, JSON };
  vm.createContext(ctx);
  vm.runInContext(srv.slice(srv.indexOf('const EVENEMENTS_PRESENT'), srv.indexOf('function tonDe(')) + prendre('tonDe') + 'this.bloc = blocPresent;', ctx);
  const t = Date.now();
  const b = ctx.bloc([{ e: 'lu', t: t - 5000 }], t, t);
  assert.match(b, /Ahmed a lu à l'écran la suite que ta voix n'avait pas dite : elle ne sera pas redite, ne la répète pas/);
});

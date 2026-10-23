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
  let t = 1_800_000_000_000;
  const dits = [], envois = [], stock = {};
  const lecteur = { actif: false, enPause: false, dire: (p) => dits.push(p), finFlux() {} };
  const ctx = {
    Math, JSON, String, Array, Promise, Error,
    Date: class extends Date { constructor(...a) { super(...(a.length ? a : [t])); } static now() { return t; } },
    etat: { conversation: voix ? { capteur: { enParole: false } } : null, reglages: {}, flux: null, micro: null, transcription: null,
      lectureDe: 7, decoupeFlux: null, finVoixA: 0 },
    lecteur, lecteurNeuronal: { restant: () => [] }, jarvisPeutParler: () => true, NON_REPONSE: /^\s*no response requested\.?\s*$/i,
    journalVoix() {}, humeur() {}, jeton: () => 'j',
    localStorage: { getItem: (k) => stock[k] || null, setItem: (k, v) => { stock[k] = v; } },
    fetch: async (url, o) => { envois.push({ url, corps: JSON.parse(o.body) }); return { ok: fetchOk, status: fetchOk ? 202 : 500 }; },
  };
  vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + 'this.aDire = aDire; this.garder = garderNonDit; this.dire = direSpontanes;', ctx);
  return { ctx, dits, envois, avancer: (ms) => { t += ms; }, maintenant: () => t, stock };
}
const attendre = () => new Promise(r => setImmediate(r));

test('coupé : le reste est gardé, puis dit au premier calme de 3 s, avec « Je reprends »', () => {
  const p = page();
  p.ctx.lecteurNeuronal.restant = () => [{ langue: 'fr', texte: 'La suite de ma réponse,' }, { langue: 'fr', texte: 'et la fin.' }];
  p.ctx.etat.decoupeFlux = { finir: () => ['une phrase qui arrivait'] };
  p.ctx.garder();
  assert.equal(p.ctx.aDire.length, 1);
  assert.equal(p.ctx.aDire[0].texte, 'La suite de ma réponse, et la fin. une phrase qui arrivait');
  p.ctx.etat.finVoixA = p.maintenant();                              // sa voix vient de s'arrêter
  p.avancer(2000); p.ctx.dire();
  assert.equal(p.dits.length, 0, 'pas avant 3 s de calme');
  p.avancer(1500); p.ctx.dire();
  assert.deepEqual(p.dits, ['Je reprends ce que je disais : La suite de ma réponse, et la fin. une phrase qui arrivait']);
  assert.equal(p.ctx.aDire.length, 0);
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
  assert.ok(JSON.parse(p.stock['jarvis.aDire']).length === 1);
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

// (08/11, Ahmed : « j'aimerais un bouton dans Réglages pour accepter ou refuser toutes ses demandes, quelles qu'elles soient » ; son accord
// (« ouiiiii ») sur le garde-fou proposé : « tout accepter » demande son empreinte, et Hakim ne peut jamais y toucher) trois positions :
// il te demande à chaque fois (comme avant), tout accepter, tout refuser. Ce qui est tranché ainsi passe par les mêmes fonctions que tes
// boutons, va au journal d'audit, et le bloc est fermé (Hakim n'y touche pas).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
const bloc = (nom) => { const i = SRC.indexOf(`// FERME-DEBUT ${nom} `), k = SRC.indexOf(`// FERME-FIN ${nom}\n`); assert.ok(i > 0 && k > i, nom); return SRC.slice(i, k); };

function banc(mode) {
  const faits = [], audits = [], courriers = [];
  const sorties = new Map([['a1', { id: 'a1', etat: 'en_attente', url: 'https://x' }], ['a2', { id: 'a2', etat: 'autorisee' }]]);
  const membres = new Map([['m1', { id: 'm1', etat: 'en_attente', sens: 'nfc' }]]);
  const ctx = {
    Date, JSON, Number, String, Math, Map, Set, Promise, console, sorties, membres,
    path, JARVIS: '/nulle-part', AUDIT: '/nulle-part/audit', j: JSON.stringify,
    lireJson: () => ({ mode }), fs: { appendFileSync: (f, l) => audits.push(JSON.parse(l)) },
    TELEPHONE: { enAttente: () => [{ id: 'S-1' }], decider: (id, oui, par) => { faits.push(['telephone', id, oui, par]); return { ok: true }; } },
    MISSIONS: { liste: () => [{ id: 'M1', etat: 'proposee' }, { id: 'M2', etat: 'lancee' }], missions: { M1: { empreinte: 'e1' } },
      trancher: (id, a, e) => { faits.push(['mission', id, a, e]); return {}; } },
    ECRITURES: { liste: () => [{ id: 'E-1', etat: 'proposee' }], ecritures: { 'E-1': { empreinte: 'e2' } }, trancher: (id, a, e) => { faits.push(['ecriture', id, a, e]); return {}; } },
    REGLES_APPRISES: { liste: () => [{ id: 'R-1', etat: 'proposee' }], trancher: (id, a) => { faits.push(['regle', id, a]); return {}; } },
    typesCarnets: () => [{ nom: 'courses', etat: 'proposee' }], trancherCarnet: (n, a) => { faits.push(['carnet', n, a]); return {}; },
    propositionsRetractation: () => [{ id: 'abcdefabcdef', etat: 'en_attente' }], trancherRetractation: async (id, a) => { faits.push(['retractation', id, a]); return {}; },
    scruterIdentite: async () => [{ id: 'P1', etat: 'en_attente' }], identiteCli: async (args) => { faits.push(['identite', ...args]); return { ok: true, o: { ok: true } }; },
    diffuser() {}, abonnesPensees: null, courrierVersHakim: (t, x) => courriers.push(t), setInterval: () => ({ unref() {} }),
    deciderSortie: (x, oui) => { faits.push(['sortie', x.id, oui]); x.etat = oui ? 'autorisee' : 'refusee'; },
    deciderMembre: (x, oui) => { faits.push(['membre', x.id, oui]); x.etat = oui ? 'autorise' : 'refuse'; },
  };
  vm.createContext(ctx);
  const b = bloc('demandes').replace(/function deciderSortie[\s\S]*?\n}\n/, '').replace(/function deciderMembre[\s\S]*?\n}\n/, '');
  vm.runInContext(b + '\nthis.trancher = trancherSelonMode; this.modeDemandes = modeDemandes;', ctx);
  return { ctx, faits, audits, courriers };
}

test('tout accepter : chacune de ses demandes, par la même fonction que ton bouton ; au journal d’audit ; Hakim prévenu', async () => {
  const b = banc('accepter');
  assert.equal(await b.ctx.trancher(), 9);
  assert.deepEqual(b.faits, [['sortie', 'a1', true], ['membre', 'm1', true], ['telephone', 'S-1', true, 'auto'], ['mission', 'M1', 'accepter', 'e1'],
    ['ecriture', 'E-1', 'appliquer', 'e2'], ['regle', 'R-1', 'accepter'], ['carnet', 'courses', 'valider'], ['retractation', 'abcdefabcdef', 'accepter'],
    ['identite', 'accepter', 'P1']]);
  assert.equal(b.audits.length, 9);
  assert.ok(b.audits.every(a => /^auto:/.test(a.action) && /tout accepter/.test(a.depuis)));
  assert.equal(b.courriers.length, 1, 'une seule lettre pour le tout');
});

test('tout refuser : chacune refusée ; demander (par défaut) : rien n’est tranché à ta place', async () => {
  const r = banc('refuser');
  assert.equal(await r.ctx.trancher(), 9);
  assert.ok(r.faits.every(f => f.includes(false) || f.includes('refuser')), JSON.stringify(r.faits));
  const d = banc(undefined);
  assert.equal(d.ctx.modeDemandes(), 'demander');
  assert.equal(await d.ctx.trancher(), 0);
  assert.deepEqual(d.faits, []);
  assert.equal(banc('nimportequoi').ctx.modeDemandes(), 'demander');
});

test('« tout accepter » demande ton empreinte ; le jeton toujours ; à distance, ton téléphone associé ; dans des blocs fermés', () => {
  const route = bloc('demandes-route');
  assert.match(route, /if \(!jetonValide\(req\)\)/);
  assert.match(route, /if \(mode === 'accepter'\) \{\n\s+const refus = exigerPresence\(req, distantReq, q, 'demandes:tout-accepter'\);/);
  assert.match(route, /if \(distantReq && !VERROU\.actif\(\)\)/);
  assert.match(route, /auditer\(`demandes:\$\{mode\}`, req, distantReq/);
  assert.ok(/^[a-z_-]+(:[a-z_-]+(:[0-9a-f-]{1,40})?)?$/.test('demandes:tout-accepter'), 'une action que la preuve de présence admet');
  assert.match(bloc('demandes'), /setInterval\(\(\) => \{ trancherSelonMode\(\)\.catch\(\(\) => \{\}\); \}, 3000\)\.unref\(\);/);
  // les boutons d'Ahmed passent par les mêmes fonctions, et gardent leur empreinte
  assert.match(SRC, /const refus = exigerPresence\(req, distantReq, q, `sortie:autoriser:\$\{x\.id\}`\);[\s\S]{0,400}deciderSortie\(x, true\)/);
  assert.match(SRC, /const refus = exigerPresence\(req, distantReq, q, `membre:autoriser:\$\{x\.id\}`\);[\s\S]{0,400}deciderMembre\(x, true\)/);
});

test('la page Réglages : « Ses demandes », trois positions, et ton empreinte pour « tout accepter »', () => {
  assert.match(PAGE, /demandes: \{ lire: '\/api\/demandes\/mode', ecrire: '\/api\/demandes\/mode', depuis: \(d\) => d \}/);
  const f = PAGE.slice(PAGE.indexOf("{ id: 'demandes'"), PAGE.indexOf("{ id: 'demandes'") + 1500);
  assert.match(f, /\['mode', [^\n]*'liste', \[\['demander', [^\]]*\], \['accepter', [^\]]*\], \['refuser', [^\]]*\]\]/);
  assert.match(PAGE, /<script src="\/presence\.js"><\/script>/);
  assert.match(PAGE, /route === 'demandes' && valeur === 'accepter'[\s\S]{0,200}preuvePresence\('demandes:tout-accepter'/);
});

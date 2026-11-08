// (04/11, 19:22, Ahmed : « il y a un message NFC qu'il a envoyé : à chaque fois que je redémarre Hakim, ça me demande si je veux accepter ou
// refuser, alors que j'ai déjà accepté ») au démarrage, le cockpit relisait ses demandes des 6 dernières heures, toutes « en attente » : la
// carte NFC de 14:23, déjà autorisée, revenait à chaque relance. Une demande déjà tranchée, ou dont le sens est déjà permis, ne revient plus
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = SRC.indexOf(`function ${nom}(`); assert.ok(i >= 0, `${nom} existe`); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2); };

function banc(lignes, permis = {}, tranches = {}) {
  const contenu = { texte: lignes.map(x => JSON.stringify(x)).join('\n') + '\n' };
  const diffuses = [], notes = [];
  const ctx = { Date, JSON, Number, String, Buffer, Map, membres: new Map(), membresTaille: null, ID_MEMBRE: /^[0-9a-f]{10}$/,
    JARVIS_MEMBRES_DEMANDES: 'demandes', JARVIS_MEMBRES_PERMIS: 'permis', JARVIS_MEMBRES_TRANCHES: 'tranches',
    lireJson: (f) => (f === 'permis' ? permis : f === 'tranches' ? tranches : null),
    fs: { statSync: () => ({ size: Buffer.byteLength(contenu.texte) }), openSync: () => 1, closeSync() {},
      readSync: (fd, b, o, n, pos) => Buffer.from(contenu.texte).copy(b, o, pos, pos + n) },
    diffuser: (_a, ev, x) => diffuses.push(JSON.parse(x)), abonnesPensees: null, j: JSON.stringify, notifier: (t) => notes.push(t),
    finDePhrase: (t) => t };
  vm.createContext(ctx);
  vm.runInContext(prendre('surveillerMembres') + 'this.surveiller = surveillerMembres;', ctx);
  return { ctx, contenu, diffuses, notes, attente: () => [...ctx.membres.values()].filter(x => x.etat === 'en_attente').map(x => x.sens) };
}
const maintenant = () => Date.now() / 1000;

test('au démarrage : une demande dont le sens est déjà permis, ou déjà tranchée, ne revient pas en attente', () => {
  const b = banc([
    { id: 'cb075ce75d', sens: 'nfc_ecrire', quoi: 'écrire une puce', ts: maintenant() - 5 * 3600 },
    { id: 'aaaaaaaaaa', sens: 'wifi_scan', quoi: 'voir les wifi', ts: maintenant() - 3600 },
    { id: 'bbbbbbbbbb', sens: 'camera', quoi: 'une photo', ts: maintenant() - 600 }],
  { nfc_ecrire: true }, { aaaaaaaaaa: 'refuse' });
  b.ctx.surveiller();
  assert.deepStrictEqual(b.attente(), ['camera'], 'seule la demande jamais tranchée attend ton geste');
  assert.strictEqual(b.ctx.membres.get('cb075ce75d').etat, 'autorise');
  assert.strictEqual(b.ctx.membres.get('aaaaaaaaaa').etat, 'refuse');
});

test('en marche : une nouvelle demande pour un sens déjà permis ne fait ni carte ni notification', () => {
  const b = banc([{ id: 'cccccccccc', sens: 'camera', quoi: 'x', ts: maintenant() - 60 }], { nfc_ecrire: true });
  b.ctx.surveiller();
  b.contenu.texte += JSON.stringify({ id: 'dddddddddd', sens: 'nfc_ecrire', quoi: 'encore une puce', ts: maintenant() }) + '\n'
    + JSON.stringify({ id: 'eeeeeeeeee', sens: 'bluetooth_scan', quoi: 'voir autour', ts: maintenant() }) + '\n';
  b.ctx.surveiller();
  assert.deepStrictEqual(b.diffuses.map(x => x.sens), ['bluetooth_scan'], 'seule la vraie première fois devient une carte');
  assert.strictEqual(b.notes.length, 1);
});

test('ton geste est gardé : après une relance, une demande refusée ou autorisée ne revient pas', () => {
  // (08/11) le geste passe par deciderMembre (la même fonction que son réglage « tout accepter / tout refuser ») : c'est elle qui le garde
  const route = SRC.slice(SRC.indexOf("if (p === '/api/membres') {"), SRC.indexOf("if (p === '/api/sorties') {"));
  assert.match(route, /deciderMembre\(x, true\)/); assert.match(route, /deciderMembre\(x, false\)/);
  const decider = SRC.slice(SRC.indexOf('function deciderMembre('), SRC.indexOf('\n}\n', SRC.indexOf('function deciderMembre(')));
  assert.match(decider, /const t = lireJson\(JARVIS_MEMBRES_TRANCHES, \{\}\) \|\| \{\};\n\s+t\[x\.id\] = x\.etat;/);
  assert.match(SRC, /const JARVIS_MEMBRES_TRANCHES = path\.join\(JARVIS, 'membres-tranches\.json'\);/);
});

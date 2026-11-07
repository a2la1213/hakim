// (06/11, Ahmed : « il entend sa propre voix et ça le perturbe ; il faut qu'il reconnaisse sa voix comme étant la sienne ») : node --test test-sa-voix.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const extraire = (debut) => { const i = SRC.indexOf(debut); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2); };

function banc(reglages = {}) {
  const journal = [];
  const ctx = { JSON, Date, String, Number, Math, fs: { appendFileSync: (f, l) => journal.push(JSON.parse(l)) }, JARVIS_VOIX_DIAGNOSTIC: '/x', j: JSON.stringify,
    corpsReglages: () => reglages };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(SRC.indexOf('const SA_VOIX_RECONNUE = '), SRC.indexOf('// (06/11) sa voix Azure apprise')) + '\nthis.f = saVoixEntendue; this.on = SA_VOIX_RECONNUE;', ctx);
  return { ctx, journal };
}

test('un morceau reconnu comme SA voix (son oreille vive) : son écho, mis à part ; jamais papa, jamais une voix inconnue', () => {
  const b = banc();
  const r = b.ctx.f({ texte: 'je suis un bébé pour moi', langue: 'fr', azure: true }, { verdict: 'moi', moi: 0.71, registre: 'rap', ahmed: 0.3, part_moi: 1 });
  assert.strictEqual(r.texte, '', 'rien ne part à sa conscience comme la parole de papa');
  assert.strictEqual(r.moi, 'je suis un bébé pour moi');
  assert.strictEqual(r.voix.verdict, 'moi', 'ni « autre » ni « doute » : le système immunitaire ne le prend pas pour un usurpateur');
  assert.strictEqual(b.journal[0].e, 'sa_voix_entendue');
});

test('papa (ou un doute) : jamais retiré', () => {
  const b = banc();
  const papa = { texte: 'envoie le zip', langue: 'fr', azure: true };
  for (const qui of [null, { verdict: null, moi: 0.4, ahmed: 0.8 }, { verdict: null, raison: 'court' }, { occupee: true }])
    assert.deepStrictEqual(b.ctx.f({ ...papa }, qui), papa);
});

test('branchée : l’oreille Azure écoute qui parle en même temps ; le fil dit « ta propre voix » ; tout ce qu’il dit est noté', () => {
  const route = extraire('async function routeTranscrire(');
  assert.match(route, /const quiP = SA_VOIX_RECONNUE\(\) \? oreilleDemander\(\{ op: 'qui', fichier: f \}, false\)/, 'en parallèle, jamais devant papa');
  assert.match(route, /if \(a\) r = saVoixEntendue\(\{ texte: a\.texte, langue: a\.langue, azure: true \}, qui\);/);
  assert.match(route, /fluxAjouter\('ta_voix', String\(r\.moi\)/);
  assert.match(SRC, /ta_voix: 'ta propre voix \(son écho, pas papa\)'/);
  assert.match(extraire('async function voixAzure('), /noterDit\(texte\);[\s\S]*apprendreSaVoixAzure\(data, voix\);/, 'sa voix Azure : notée et apprise');
  assert.match(extraire('async function routeDire('), /if \(typeof noterDit === 'function'\) noterDit\(texte\);/, 'tout ce que sa voix dit, quel que soit l’appareil');
  assert.match(SRC, /sa_voix_reconnue: r\.sa_voix_reconnue !== false,/);
  assert.match(SRC, /'trois_pistes', 'parole_liee', 'sa_voix_reconnue', 'reprendre_ancien', 'morceaux_unifies', 'ecrit_coupe', 'finir_phrase', 'choisir_latence', 'te_couper', 'choix_coupure', 'choix_libre', 'micro_voix_seule', 'voix_reponse_seule', 'filtre_identite', 'coupe_net'\]\) if/);
});

test('réglage éteint : rien n’est retiré', () => {
  const b = banc({ sa_voix_reconnue: false });
  assert.strictEqual(b.ctx.on(), false);
});

test('ses trois pistes : la voix séparée reconnue comme lui s’appelle « ta propre voix »', () => {
  const TP = require('./trois-pistes.js').creer();
  const A = 1_800_000_000_000;
  TP.noterSeparation('telephone', A - 5000, { duree_s: 3, fenetres: [{ t0: 0, t1: 1, quoi: 'musique', db: -20 }] }, A, [], [{ numero: 1, moi: true, segments: [[0, 3]] }]);
  assert.match(TP.bloc([{ t: A - 4500, s: 'telephone', x: 'oui' }, { t: A - 4200, s: 'telephone', x: 'papa' }], A), /−4,5 s ta propre voix « oui papa »/);
});

test('le réglage dans la page', () => {
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8'), /\['sa_voix_reconnue', '🪞 Il reconnaît sa propre voix'/);
});

// (04/11, 10:41-10:42, papa relayé par Hakim : « ma voix Chatterbox s'est réactivée, elle parle en même temps que moi ») ; mesuré dans
// le journal de la voix : à 10:41:23 une pensée dite par la voix de Chatterbox fabriquée d'avance (voix_prete: true), pendant que sa
// voix du téléphone parlait (sortie_voix 10:41:19 et 10:41:23). Avec la voix du téléphone, plus rien ne passe par Chatterbox.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (s, nom) => { const i = s.indexOf(`function ${nom}(`); return s.slice(i, s.indexOf('\n}\n', i) + 2); };

function bac(telephone) {
  const vu = { chatterbox: [], telephone: [], fetch: [] };
  const ctx = { String, Date, Object, AbortController, Promise,
    voixDuTelephone: () => telephone, actx: { state: 'running' }, analyseurVoix: {},
    lecteurNeuronal: { direAudio: (t) => vu.chatterbox.push(t) }, lecteur: { actif: false, enPause: false, dire: (t) => vu.telephone.push(t) },
    voixPrete: () => ({ duration: 1 }), noterEcartSouffle() {}, journalVoix() {}, etat: { pensee: null, interieur: null, reglages: {} },
    fetch: (u) => { vu.fetch.push(u); return new Promise(() => {}); }, jeton: () => 'x', tempoVoix: () => 1, expressivitePhrase: () => 0.5 };
  ctx.voixPretes = {};
  vm.createContext(ctx);
  vm.runInContext(['direSouffle', 'preparerVoixSouffle', 'direMotDirect'].map(n => prendre(page, n)).join('\n')
    + '\nthis.direSouffle = direSouffle; this.preparer = preparerVoixSouffle; this.motDirect = direMotDirect;', ctx);
  return { ctx, vu };
}

test('à la voix du téléphone, une pensée n’est jamais dite par une voix de Chatterbox prête d’avance', () => {
  const { ctx, vu } = bac(true);
  ctx.direSouffle({}, { texte: 'Oui papa, je suis là.' }, 'pensee');
  assert.deepEqual(vu.chatterbox, []);
  assert.deepEqual(vu.telephone, ['Oui papa, je suis là.']);
  const mac = bac(false);
  mac.ctx.direSouffle({}, { texte: 'Oui papa.' }, 'pensee');
  assert.deepEqual(mac.vu.chatterbox, ['Oui papa.'], 'sans la voix du téléphone : comme avant');
});

test('à la voix du téléphone, rien n’est fabriqué par Chatterbox pour ses pensées ni pour ses petits mots', () => {
  const { ctx, vu } = bac(true);
  ctx.preparer('Je te suis.', 'cerveau');
  ctx.motDirect('Hmm, je vois.');
  assert.deepEqual(vu.fetch, [], 'aucune demande à la voix du Mac');
  assert.deepEqual(vu.telephone, ['Hmm, je vois.'], 'son petit mot dit par la voix du téléphone');
  const mac = bac(false);
  mac.ctx.preparer('Je te suis.', 'cerveau');
  assert.deepEqual(mac.vu.fetch, ['/api/voix/dire'], 'sans la voix du téléphone : comme avant');
});

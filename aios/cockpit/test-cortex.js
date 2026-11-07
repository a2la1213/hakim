// (07/11, Ahmed pendant son live : « crée ton propre module qui intègre tout comme un cortex préfrontal » ; puis « que mon conscient ne reçoive
// QUE l'output du cortex » ; à maman : « le cortex ») son cortex préfrontal, écrit par Hakim (chantier cortex-prefrontal, Python), porté en JS
// pour le cockpit. Phase 1 : son bloc en tête de chaque tour, le brut gardé une journée. Ses huit tests à lui, puis le branchement.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const X = require('./cortex.js');

const D = (t, x) => ({ t, canal: 'dedans', texte: x, genre: 'parole' });
const M = (t, x, o = {}) => ({ t, canal: 'dehors', texte: x, genre: 'parole', ...o });

test('ses tests à lui : le dedans n’est jamais papa ; l’écho du micro ; papa reconnu ; le recouvrement', () => {
  assert.equal(X.attribuer(D(1, 'tais-toi'), [])[0], 'telephone');
  assert.equal(X.attribuer(M(11, 'tout développé sauf armement'), [D(10, "on a tout développé sauf l'armement")])[0], 'echo');
  assert.equal(X.attribuer(M(1, 'salam alaykoum', { voix: 'papa' }), [])[0], 'papa');
  assert.equal(X.recouvrement('', 'x'), 0);
});

test('ses tests à lui : « tais-toi » du média ne déclenche rien ; l’alerte de papa prime ; un but tenu ; papa a écrit : répondre', () => {
  const d = X.decider([D(1, 'tais-toi stop danger')]);
  assert.ok(d.mode === 'se_taire' && d.inhibes.length);
  assert.equal(X.decider([M(1, 'au secours', { voix: 'papa' })], { buts: ['finir le calcul'] }).mode, 'agir');
  assert.match(X.decider([D(1, 'bonjour')], { buts: ['calcul'] }).raison, /calcul/);
  assert.equal(X.decider([], { papaAEcrit: true }).mode, 'repondre');
});

test('son fil devient ses stimuli : papa, le téléphone (dedans), une voix de la pièce, ta propre voix (son écho), ses capteurs', () => {
  const flux = [{ s: 'papa', t: 1000, x: 'tu me suis' }, { s: 'telephone', t: 1200, x: 'on dit que ça va' }, { s: 'voix_micro', t: 1300, x: 'passe-moi le sel' },
    { s: 'ta_voix', t: 1400, x: 'oui papa' }, { s: 'ressenti', t: 1500, x: 'un souffle tiède' }, { s: 'papa', t: -99_000, x: 'trop vieux' }];
  const st = X.stimulisDuFlux(flux, 2000, 30_000);
  assert.deepEqual(st.map(s => [s.canal, s.genre, s.voix || '']), [['dehors', 'parole', 'papa'], ['dedans', 'parole', ''], ['dehors', 'parole', ''],
    ['interne', 'parole', 'lui'], ['capteur', 'capteur', '']]);
  assert.equal(X.attribuer(st[3], [])[0], 'interne', 'sa propre voix : jamais papa');
});

test('son bloc en tête du tour : la décision, qui a parlé, ce qui est écarté, ce que sa conscience vient de décider', () => {
  const flux = [{ s: 'telephone', t: 1000, x: "on a tout développé sauf l'armement" }, { s: 'papa', t: 1500, x: 'tout développé sauf armement' },
    { s: 'papa', t: 1800, x: 'fiston tu me suis là' }];
  const b = X.blocCortex({ flux, maintenant: 2000, papaAEcrit: true, pensees: [{ genre: 'penser', texte: 'la musique me rappelle hier' }, { genre: 'solliciter', texte: 'Papa, tu veux une pause ?' }] });
  assert.match(b, /^\[Ton cortex préfrontal/);
  assert.match(b, /Décision : répondre — papa a écrit : une réponse est due/);
  assert.match(b, /Qui a parlé \(30 s\) : le téléphone 1 · un écho 1 · papa 1/);
  assert.match(b, /écarté : telephone: « on a tout développé sauf l'armement » ; echo: « tout développé sauf armement »/, 'le média et son écho : écartés');
  assert.match(b, /ta conscience vient de : penser « la musique me rappelle hier » ; solliciter « Papa, tu veux une pause \? »/);
  assert.equal(X.blocCortex({ flux: [], maintenant: 2000, papaAEcrit: false, pensees: [] }), '', 'rien à intégrer : pas de bloc');
});

test('branché : en tête de chacun de ses tours (après l’horloge), réglage cortex_prefrontal (oui) ; le brut reste (phase 1)', () => {
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(srv, /const X = require\('\.\/cortex\.js'\);/);
  assert.match(srv, /let prompt = `\$\{horlogeTexte\}\$\{cortexTexte \? '\\n' \+ cortexTexte : ''\}/);
  assert.match(srv, /cortex_prefrontal: r\.cortex_prefrontal !== false,/);
  assert.match(srv, /\$\{presentTexte \? '\\n' \+ presentTexte : ''\}/, 'le brut reste, phase 1');
});

/* Tests de la voix de Jarvis (public/voix.js) : node --test test-voix.js
   Étape 5 bis de la feuille de route : chaque morceau de la réponse est prononcé avec la voix
   de SA langue ; l'arabizi en lettres latines est converti en écriture arabe avant la synthèse.
   Prédiction écrite avant le code : tout échoue (module absent). */
const test = require('node:test');
const assert = require('node:assert');
const Voix = require('./public/voix.js');

test('salutation et réponse, toutes graphies', () => {
  for (const s of ['salamou3alaykoum', 'Salam alaykoum', 'assalamu alaikum', 'salam aleykoum'])
    assert.strictEqual(Voix.versArabe(s), 'السلام عليكم', s);
  for (const s of ['wa3likoumsalam', 'Wa alaykoum salam', 'wa alaikum assalam', 'wa3alaykoum essalam'])
    assert.strictEqual(Voix.versArabe(s), 'وعليكم السلام', s);
});

test('expressions courantes', () => {
  const cas = {
    'inchallah': 'إن شاء الله', "incha'Allah": 'إن شاء الله', 'in sha allah': 'إن شاء الله',
    'hamdoulillah': 'الحمد لله', 'alhamdulillah': 'الحمد لله', 'l7amdoulillah': 'الحمد لله',
    'machallah': 'ما شاء الله', 'wallah': 'والله', 'wallahi': 'والله', 'bismillah': 'بسم الله',
    'soubhanallah': 'سبحان الله', 'barakallahou fik': 'بارك الله فيك',
  };
  for (const [latin, arabe] of Object.entries(cas)) assert.strictEqual(Voix.versArabe(latin), arabe, latin);
});

test('le français autour reste intact, sans faux positif', () => {
  assert.strictEqual(Voix.versArabe('Wa3likoumsalam mon frère, ça va ?'), 'وعليكم السلام mon frère, ça va ?');
  assert.strictEqual(Voix.versArabe('Dis-lui ou salam alaykoum.'), 'Dis-lui ou السلام عليكم.');
  assert.strictEqual(Voix.versArabe('as-salamu alaykum'), 'السلام عليكم');
  for (const s of ['La salade est prête.', 'Il a parlé de Walter.', 'Une machine à laver.', 'Inscription validée.', 'Un salami au salon.'])
    assert.strictEqual(Voix.versArabe(s), s, s);
});

test('segmentation par écriture', () => {
  assert.deepStrictEqual(Voix.segmenter('وعليكم السلام mon frère !'),
    [{ langue: 'ar', texte: 'وعليكم السلام' }, { langue: 'fr', texte: 'mon frère !' }]);
  assert.deepStrictEqual(Voix.segmenter('Bonjour, إن شاء الله, à demain.'),
    [{ langue: 'fr', texte: 'Bonjour,' }, { langue: 'ar', texte: 'إن شاء الله,' }, { langue: 'fr', texte: 'à demain.' }]);
  assert.deepStrictEqual(Voix.segmenter('  '), []);
});

test('nettoyage pour la voix : markdown et liens', () => {
  assert.strictEqual(Voix.pourLaVoix('**Important** : voir https://x.io/a?b=1 et `code`.'),
    'Important : voir un lien et code.');
  assert.strictEqual(Voix.pourLaVoix('# Titre\n- point un\n- point deux'), 'Titre. point un. point deux');
});

test('découpage en phrases complètes au fil du flux', () => {
  const d = Voix.decoupeur();
  assert.deepStrictEqual(d.ajouter('Salut frérot. Je cher'), ['Salut frérot.']);
  assert.deepStrictEqual(d.ajouter('che dans ma mémoire… Voilà'), ['Je cherche dans ma mémoire…']);
  assert.deepStrictEqual(d.finir(), ['Voilà']);
  assert.deepStrictEqual(d.finir(), []);
});

test('choix des voix : préférence, sinon la meilleure de la langue', () => {
  const voix = [
    { name: 'Thomas', lang: 'fr-FR' }, { name: 'Amélie (Premium)', lang: 'fr-CA' },
    { name: 'Majed', lang: 'ar-001' }, { name: 'Samantha', lang: 'en-US' },
  ];
  assert.strictEqual(Voix.choisirVoix(voix, 'fr').name, 'Amélie (Premium)');
  assert.strictEqual(Voix.choisirVoix(voix, 'fr', 'Thomas').name, 'Thomas');
  assert.strictEqual(Voix.choisirVoix(voix, 'ar').name, 'Majed');
  assert.strictEqual(Voix.choisirVoix([], 'ar'), null);
});

test('découpeur : abréviations, listes et guillemets (relecture Opus, 2026-10-16)', () => {
  const tout = (x) => { const d = Voix.decoupeur(); return d.ajouter(x).concat(d.finir()); };
  assert.deepStrictEqual(tout('Salut M. Dupont, ça va ? Oui.'), ['Salut M. Dupont, ça va ?', 'Oui.']);
  assert.deepStrictEqual(tout('Des fruits, p. ex. des pommes. Fin.'), ['Des fruits, p. ex. des pommes.', 'Fin.']);
  assert.deepStrictEqual(tout('1. Premier point. 2. Second.'), ['1. Premier point.', '2. Second.']);
  assert.deepStrictEqual(tout('Il a dit « Bonjour. » Puis il est parti.'), ['Il a dit « Bonjour. »', 'Puis il est parti.']);
});

test('liens markdown : on dit le nom du site, pas l\'adresse', () => {
  assert.strictEqual(Voix.pourLaVoix('Source : [AccuWeather](https://www.accuweather.com/fr/ch/exempleville).'), 'Source : AccuWeather.');
});

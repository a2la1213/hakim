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

test('formules de maths : la voix dit la version parlée, jamais le LaTeX (2026-10-21)', () => {
  assert.strictEqual(Voix.pourLaVoix('Donc $$E=mc^2$$ [[voix: E égale m c au carré]].').replace(/\s+\./, '.'), 'Donc E égale m c au carré.');
  assert.ok(!/\\|\^|\$\$/.test(Voix.pourLaVoix('Sans version parlée : $\\frac{a}{b}$ ici.')));
  assert.ok(Voix.pourLaVoix('Sans version parlée : $\\frac{a}{b}$ ici.').includes('a sur b'));          // le repli lit le simple
  assert.ok(Voix.pourLaVoix('La variable $x$ suffit.').includes('variable x suffit'));
  assert.ok(Voix.pourLaVoix('Ça coûte 5 $ ou 10 $.').includes('5 $ ou 10 $'));            // de l'argent, pas une formule
});

test('formules de maths : le découpeur ne coupe ni une formule ni sa version parlée qui arrive en retard', () => {
  const txt = 'Voici.\n$$\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}.$$\n[[voix: la somme vaut n fois n plus 1 sur 2]]\nFin. Et $x^2$ [[voix: x au carré]] aussi.';
  for (const n of [1, 2, 5, 9, 40]) {
    const d = Voix.decoupeur(), out = [];
    for (const c of txt.match(new RegExp(`[\\s\\S]{1,${n}}`, 'g'))) out.push(...d.ajouter(c));
    out.push(...d.finir());
    assert.deepStrictEqual(out.map(Voix.pourLaVoix),
      ['Voici.', 'la somme vaut n fois n plus 1 sur 2', 'Fin.', 'Et x au carré aussi.'], `morceaux de ${n}`);
  }
});

test('code : la voix dit « bloc de code » une fois, sans lire ses lignes, même en flux (2026-10-21)', () => {
  const txt = 'Voici le code.\n```python\nprint("a. b")\nx = 1  # prix : 5 $\n```\nVoilà. Fin.';
  for (const n of [1, 4, 11, 60]) {
    const d = Voix.decoupeur(), out = [];
    for (const c of txt.match(new RegExp(`[\\s\\S]{1,${n}}`, 'g'))) out.push(...d.ajouter(c));
    out.push(...d.finir());
    assert.deepStrictEqual(out.map(Voix.pourLaVoix), ['Voici le code.', '(bloc de code)', 'Voilà.', 'Fin.'], `morceaux de ${n}`);
  }
});

test('la version parlée sous la forme ⟮⟮voix: …⟯⟯ (vue dans un bloc de données) est comprise aussi', () => {
  const t = 'Ici $\\frac{1}{2}+\\frac{1}{3}+\\frac{1}{6}=1$ ⟮⟮voix: un demi plus un tiers plus un sixième égale un⟯⟯. Fin.';
  assert.ok(Voix.pourLaVoix(t).includes('un demi plus un tiers plus un sixième égale un'));
  assert.ok(!/⟮|voir la formule|\\frac/.test(Voix.pourLaVoix(t)));
});

test('repli : une formule sans version parlée est lue en mots, ou « voir la formule » si elle ne se convertit pas', () => {
  const L = Voix.latexParle;
  assert.strictEqual(L('x=5'), 'x égale 5');
  assert.strictEqual(L('\\pi'), 'pi');
  assert.strictEqual(L('E = mc^2'), 'E égale m c au carré');
  assert.strictEqual(L('\\frac{1}{2}+\\frac{1}{3}+\\frac{1}{6}=1'), 'un demi plus un tiers plus un sixième égale 1');
  assert.strictEqual(L('\\sqrt{2} \\approx 1{,}414'), 'racine de 2 environ 1,414');
  assert.strictEqual(L('f(x) = 2(x+1)'), 'f de x égale 2 fois x plus 1');
  assert.strictEqual(L('\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1'), 'la limite quand x tend vers 0 de sinus x sur x égale 1');
  assert.strictEqual(L('\\begin{pmatrix}1&2\\end{pmatrix}'), null);
  assert.strictEqual(L('\\inconnue{x}'), null);
  assert.ok(Voix.pourLaVoix('Donc $x=5$ et $\\begin{pmatrix}1\\end{pmatrix}$.').includes('x égale 5'));
  assert.ok(Voix.pourLaVoix('Et $\\begin{pmatrix}1\\end{pmatrix}$.').includes('voir la formule'));
});

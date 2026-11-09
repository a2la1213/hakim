/* (09/11, Ahmed, relayé par Hakim) sa darija et sa voix : node --test test-darija-voix.js
   1. (08/11 19:31) le français d'abord, puis la darija, jamais l'inverse ;
   2. (08/11 19:31, 20:01) sur un passage arabe, la voix dit l'arabe SEUL, jamais aussi sa version en lettres latines ;
   3. (09/11 16:37) chaque passage arabe part vers la voix arabe ; (21:20) la darija s'écrit en lettres arabes vocalisées, à l'écran aussi.
   Mesuré le 09/11 à 16:34 (voix-dite.jsonl) : « الله » / « ybarek fik » (voix française) / « اللّٰه يْبَارَكْ فِيكْ », puis
   « الحمد لله الحَمْدُ لِلَّه » : le texte écrit avant la balise ET son contenu étaient dits. La chaîne suivie ici, jusqu'à la requête
   envoyée à Azure : texte de Hakim → découpage au fil du flux → Voix.prononcable (page) → /api/voix/dire (prononcer) → voixAzure (SSML :
   Ismael pour l'arabe) ; et pour sa voix de rap, les morceaux de langue donnés à Chatterbox. */
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Voix = require('./public/voix.js');
const VoixHakim = require('./voix-hakim.js');

const SRV = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const fonction = (nom) => { const i = SRV.indexOf(`function ${nom}(`); return SRV.slice(SRV.lastIndexOf('\n', i) + 1, SRV.indexOf('\n}\n', i) + 3); };

// prononcer (server.js), tel qu'écrit, avec son vrai VoixPage
const ctxP = { lirePrononciations() {}, prononciationsCache: { liste: [] }, VoixPage: Voix };
vm.createContext(ctxP);
vm.runInContext(fonction('prononcer') + '\nthis.prononcer = prononcer;', ctxP);
const prononcer = ctxP.prononcer;

// voixAzure (server.js), tel qu'écrit : la requête SSML qu'il enverrait à Azure est capturée (aucun appel réseau)
const envois = [];
const ctxA = {
  cleAzure: () => 'cle-test', lireJson: () => ({ region: 'westeurope', voix: 'fr-FR-RemyMultilingualNeural' }), AZURE: 'azure.json', VoixHakim,
  AbortController, setTimeout, clearTimeout, Buffer, noterDit() {}, apprendreSaVoixAzure() {},
  fetch: async (_url, o) => { envois.push(o.body); return { ok: true, arrayBuffer: async () => new ArrayBuffer(8) }; },
};
vm.createContext(ctxA);
vm.runInContext(fonction('voixAzure') + '\nthis.voixAzure = voixAzure;', ctxA);
// les voix d'une requête SSML : [{ voix, texte }]
const voixSsml = (ssml) => [...ssml.matchAll(/<voice name="([^"]+)"><prosody[^>]*>([\s\S]*?)<\/prosody><\/voice>/g)].map(m => ({ voix: m[1], texte: m[2] }));
async function azure(texte) { envois.length = 0; await ctxA.voixAzure(texte, null, null); return voixSsml(envois.join('')); }

const ARABE = /[؀-ۿ]/;
const LATIN_DU_PASSAGE = /\b(?:wesh|rak|khouya|hamdou?ll?ah|ybarek|fik|allah|labes|fahemtek|baba|daba|nhedder|darija|ghir|voix)\b/i;

// la page : le texte arrive en morceaux, le découpeur rend des phrases, chacune devient des morceaux de voix (langue, texte),
// et chaque morceau part à /api/voix/dire (prononcer), puis à Azure
async function cheminComplet(texte, pas = 7) {
  const d = Voix.decoupeur({ vif: true }), phrases = [];
  for (let i = 0; i < texte.length; i += pas) phrases.push(...d.ajouter(texte.slice(i, i + pas)));
  phrases.push(...d.finir());
  const morceaux = phrases.flatMap(p => Voix.prononcable(p));
  const azureVoix = [];
  for (const m of morceaux) azureVoix.push(...await azure(prononcer(m.texte)));
  // le découpage vif peut couper une phrase en deux : les morceaux voisins de même langue (ou de même voix) sont recollés pour comparer
  const recoller = (l, cle) => l.reduce((a, x) => { const d = a[a.length - 1]; if (d && d[cle] === x[cle]) d.texte += ` ${x.texte}`; else a.push({ ...x }); return a; }, []);
  return { morceaux: recoller(morceaux, 'langue'), azureVoix: recoller(azureVoix, 'voix') };
}

const FR = 'Compris papa, je regarde ça tout de suite.';
const ANCIEN = `${FR} Wesh rak khouya [[voix: وَاشْ رَاكْ خُويَا]] ! [[anticipe: court]]`;      // ses messages d'avant le 09/11, 21:20
const NOUVEAU = `${FR} وَاشْ رَاكْ خُويَا، لَابَاسْ؟ [[anticipe: court]]`;                          // ce qu'il écrit maintenant

test('« phrase française … [[voix: arabe vocalisé]] » : la voix reçoit le français, puis l’arabe seul ; rien du latin du passage', async () => {
  for (const pas of [3, 7, 50]) {
    const { morceaux, azureVoix } = await cheminComplet(ANCIEN, pas);
    assert.deepStrictEqual(morceaux.map(m => m.langue), ['fr', 'ar'], `l'ordre des morceaux (flux de ${pas})`);
    assert.strictEqual(morceaux[0].texte, FR);
    assert.strictEqual(morceaux[1].texte, 'وَاشْ رَاكْ خُويَا !');
    assert.deepStrictEqual(azureVoix.map(v => v.voix), ['fr-FR-RemyMultilingualNeural', 'ar-DZ-IsmaelNeural']);
    assert.ok(azureVoix.every(v => !LATIN_DU_PASSAGE.test(v.texte)), `aucune chaîne latine du passage n'arrive à Azure : ${JSON.stringify(azureVoix)}`);
  }
});

test('ce qu’il écrit maintenant (l’arabe vocalisé, sans balise) : le français à sa voix, l’arabe à Ismael, tel quel', async () => {
  const { morceaux, azureVoix } = await cheminComplet(NOUVEAU);
  assert.deepStrictEqual(morceaux, [{ langue: 'fr', texte: FR }, { langue: 'ar', texte: 'وَاشْ رَاكْ خُويَا، لَابَاسْ؟' }]);
  assert.deepStrictEqual(azureVoix.map(v => v.voix), ['fr-FR-RemyMultilingualNeural', 'ar-DZ-IsmaelNeural']);
  assert.strictEqual(azureVoix[1].texte, 'وَاشْ رَاكْ خُويَا، لَابَاسْ؟', 'les voyelles arrivent à Ismael');
});

test('les deux phrases du 09/11 à 16:34 : plus de « ybarek fik » à la française, plus de « الحمد لله » en double', async () => {
  for (const [texte, arabe] of [['Allah ybarek fik [[voix: اللّٰه يْبَارَكْ فِيكْ]] papa, le calcul est à 37 %.', 'اللّٰه يْبَارَكْ فِيكْ'],
    ['Hamdoullah [[voix: الحَمْدُ لِلَّه]] papa ! 😄 Le calcul file bien, il en est à 41 %.', 'الحَمْدُ لِلَّه']]) {
    const { azureVoix } = await cheminComplet(texte, 50);
    const ismael = azureVoix.filter(v => v.voix === 'ar-DZ-IsmaelNeural');
    assert.deepStrictEqual(ismael.map(v => v.texte), [arabe], 'l’arabe, une seule fois, avec ses voyelles');
    assert.ok(azureVoix.filter(v => v.voix !== 'ar-DZ-IsmaelNeural').every(v => !LATIN_DU_PASSAGE.test(v.texte) && !ARABE.test(v.texte)), JSON.stringify(azureVoix));
  }
});

test('tout morceau en lettres arabes va à la voix arabe (Azure : Ismael ; sa voix de rap : le morceau « ar »), jamais à la voix française', async () => {
  const textes = [ANCIEN, NOUVEAU, 'Bismillah, on commence.', 'Wallah papa, inchallah ça passe.', 'Le verset بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ ouvre la sourate.'];
  for (const t of textes) {
    for (const m of Voix.prononcable(t)) {
      const v = await azure(prononcer(m.texte));
      for (const x of v) assert.strictEqual(ARABE.test(x.texte), x.voix === 'ar-DZ-IsmaelNeural', `${JSON.stringify(x)} (dans « ${t} »)`);
    }
    for (const s of VoixHakim.segmenterLangues(prononcer(t))) assert.strictEqual(ARABE.test(s.texte), s.langue === 'ar', JSON.stringify(s));
  }
});

test('ce qui part à la voix sans passer par la page (ses pensées, ses petits mots, la montre) : l’arabe seul aussi', async () => {
  // brut, tel qu'il l'a écrit (voixPourTexte, preparerVoixSouffle, voixDeLaSource) ; et la montre, qui envoie le contenu sans ses crochets
  for (const brut of [ANCIEN, 'Wesh rak khouya وَاشْ رَاكْ خُويَا', 'Hamdoullah [[voix: الحَمْدُ لِلَّه]] papa !']) {
    const dit = prononcer(brut);
    assert.ok(!/\[\[|voix:|anticipe/.test(dit), dit);
    const v = await azure(dit);
    assert.ok(v.some(x => x.voix === 'ar-DZ-IsmaelNeural'), JSON.stringify(v));
    assert.ok(v.every(x => !LATIN_DU_PASSAGE.test(x.texte)), `aucune chaîne latine du passage : ${JSON.stringify(v)}`);
    for (const s of VoixHakim.segmenterLangues(dit)) assert.ok(!LATIN_DU_PASSAGE.test(s.texte), `Chatterbox : ${JSON.stringify(s)}`);
  }
});

test('la version latine reconnue même balise d’abord (08/11, 20:56), et seulement elle : un mot français voisin reste', () => {
  const t = 'Compris papa. [[voix: فَهْمْتَكْ بَابَا، دَابَا نْهَدَّرْ مْعَاكْ بِالدَّارِجَة غِيرْ]] Fahemtek baba, daba nhedder m3ak bel darija ghir. Je coupe le français.';
  assert.deepStrictEqual(Voix.prononcable(t).map(s => s.langue), ['fr', 'ar', 'fr']);
  assert.ok(!LATIN_DU_PASSAGE.test(Voix.prononcable(t).map(s => s.texte).join(' ')));
  assert.strictEqual(Voix.pourLaVoix('Compris papa wesh rak khouya [[voix: وَاشْ رَاكْ خُويَا]] !'), 'Compris papa وَاشْ رَاكْ خُويَا !');
  assert.strictEqual(Voix.pourLaVoix('Salut سمير, ça va ?'), 'Salut سمير, ça va ?', 'un prénom arabe ne mange pas le français autour');
  assert.strictEqual(Voix.pourLaVoix('Il a dit لَا et il est parti.'), 'Il a dit لَا et il est parti.');
  assert.strictEqual(Voix.squelette('wesh rak khouya'), Voix.squelette('وَاشْ رَاكْ خُويَا'));
});

test('l’écran (21:20, Ahmed) : la darija en lettres arabes ; ses anciens messages montrent l’arabe de la balise, une formule reste cachée', () => {
  assert.strictEqual(Voix.pourLEcran('Compris papa, wesh rak khouya [[voix: وَاشْ رَاكْ خُويَا]] !'), 'Compris papa, وَاشْ رَاكْ خُويَا !');
  assert.strictEqual(Voix.pourLEcran(NOUVEAU), NOUVEAU, 'ce qu’il écrit maintenant : tel quel');
  assert.strictEqual(Voix.pourLEcran('Donc $x^2$ [[voix: x au carré]] ici.'), 'Donc $x^2$  ici.');
  assert.strictEqual(Voix.pourLEcran('Wallah, inchallah ça passe.'), 'Wallah, inchallah ça passe.', 'sans balise, l’écran ne touche à rien');
  const parler = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  assert.match(parler, /const t2 = Voix\.pourLEcran\(t\)/, 'texteRiche passe par Voix.pourLEcran');
  assert.ok(!/\.replace\(Voix\.VOIX_SEULE, ''\)/.test(parler), 'plus aucun endroit qui cache simplement la balise (copier, notification)');
});

test('ses consignes : le français d’abord, la darija directement en lettres arabes vocalisées, une seule fois ; plus de phonétique', () => {
  const i = SRV.indexOf('const LANGUE_ORALE = ');
  const LANGUE_ORALE = vm.runInNewContext(SRV.slice(i + 'const LANGUE_ORALE = '.length, SRV.indexOf('`;\n', i) + 1));
  assert.match(LANGUE_ORALE, /le français d'abord, la darija ensuite, jamais l'inverse/);
  assert.match(LANGUE_ORALE, /la darija toujours en lettres arabes, jamais en lettres latines ni avec des chiffres \(3, 7, 9\) : écrite directement ainsi, avec TOUTES ses voyelles \(fatha, kasra, damma, soukoun, chadda\)/);
  assert.match(LANGUE_ORALE, /une seule fois \(pas de version latine ni phonétique à côté, pas de \[\[voix: …\]\] pour elle\)/);
  assert.ok(!/phonétique française|en lettres latines, comme papa l'écrit|wesh rak khouya \[\[voix/.test(LANGUE_ORALE));
  assert.ok(!/phonetiser/.test(SRV.replace(/\/\/[^\n]*/g, '')), 'phonetiser retiré du code');
});

/* (10/11, ~00:00, Ahmed : « quand on est en live il doit comprendre que ce qu'il entend de l'intérieur provient du live et doit écouter et
   répondre selon les mêmes règles d'interaction qu'avec moi, et si c'est de la musique idem ! Le tout en real time continu ») son garde du
   live (live.js) : chaque période, sans modèle, il décide si un appel vaut la peine ; chaque règle a son témoin (coupée, le test tombe).
   node --test test-live.js */
const test = require('node:test');
const assert = require('node:assert');
const L = require('./live.js');

const T = 1_800_000_000_000;
const calme = { actif: true, pause: true, papaParle: false, tuParles: false, occupe: false, forfait: false, placeLibre: true };
// le téléphone dit une phrase (son bloc entier, sa clé)
function dit(e, texte, t, qui = 'voix 12', cle = `b${t}`) { return L.recevoir(e, { cle, texte, fin: true, qui }, t); }

test('son nom dit par le live, à la pause : un appel (motif « nom ») ; sans pause : il attend la fin de la phrase', () => {
  const e = L.creer();
  dit(e, 'Hakim, tu nous entends ?', T);
  assert.deepStrictEqual(L.evaluer(e, { ...calme, pause: false }, T + 1000).raison, 'pas_de_pause');
  const d = L.evaluer(e, calme, T + 2000);
  assert.strictEqual(d.action, 'appeler');
  assert.strictEqual(d.motif, 'nom');
  assert.strictEqual(d.qui, 'voix 12');
  assert.match(d.phrase, /Hakim/);
  // une seule fois : la phrase est jugée, l'appel en vol
  assert.strictEqual(L.evaluer(e, calme, T + 3000).action, 'rien');
});

/* (10/11, 08:28, Hakim : « une voix du live m'a appelé : « Hakim, t'es là ? », puis « Réponds-moi Hakim, ça fait trop longtemps » ; je ne lui
   ai pas répondu ») TÉMOIN : on l'appelle pendant que papa parle, qu'il parle ou que sa tête répond à papa : il y pense TOUT DE SUITE (avant :
   « papa_parle », « il_parle », « sa_tete_repond », puis « trop_vieille » après 20 s) ; seule sa voix attend que papa se taise */
test('on l\'appelle pendant que papa parle, que lui parle ou que sa tête répond : l\'appel part tout de suite, sa voix attend papa', () => {
  for (const gene of [{ papaParle: true }, { tuParles: true }, { occupe: true }, { papaParle: true, tuParles: true, occupe: true }]) {
    const e = L.creer();
    dit(e, 'Hakim, t\'es là ?', T);
    const d = L.evaluer(e, { ...calme, ...gene }, T + 1000);
    assert.strictEqual(d.action, 'appeler', JSON.stringify(gene));
    assert.strictEqual(d.motif, 'nom');
    L.repondu(e, 'DIRE : Oui, je suis là ! Salam.', T + 2500);
    // papa parle, ou sa voix sonne : elle attend ; sa tête qui répond à papa ne la retient pas
    assert.strictEqual(L.evaluer(e, { ...calme, papaParle: true }, T + 3000).action, 'rien');
    assert.strictEqual(L.evaluer(e, { ...calme, tuParles: true }, T + 4000).action, 'rien');
    const x = L.evaluer(e, { ...calme, occupe: true }, T + 5000);
    assert.strictEqual(x.action, 'dire');
    assert.strictEqual(x.texte, 'Oui, je suis là ! Salam.');
  }
});

test('le live ne fait jamais de pause : son nom est pensé 3 s après sa phrase, et sa réponse dite après 10 s sans pause (papa silencieux)', () => {
  const e = L.creer();
  dit(e, 'Réponds-moi Hakim, ça fait trop longtemps.', T);
  const bavard = { ...calme, pause: false };
  assert.strictEqual(L.evaluer(e, bavard, T + 1000).raison, 'pas_de_pause');
  assert.strictEqual(L.evaluer(e, bavard, T + 2000).raison, 'pas_de_pause');
  assert.strictEqual(L.evaluer(e, bavard, T + 3500).action, 'appeler');
  L.repondu(e, 'DIRE : Je suis là, pardon, je t\'écoute.', T + 5000);
  assert.strictEqual(L.evaluer(e, bavard, T + 8000).action, 'rien');
  assert.strictEqual(L.evaluer(e, { ...bavard, papaParle: true }, T + 16000).action, 'rien');
  assert.strictEqual(L.evaluer(e, bavard, T + 17000).action, 'dire');
});

test('la musique ne lui prend ni son budget ni son écart : un appel de la musique, puis son nom 1 s après : appelé', () => {
  const e = L.creer();
  const m = { ...calme, pause: false, musique: { joue: true, debut: T - 60000 } };
  const d = L.evaluer(e, m, T, { ecart_s: 10, par_minute: 1 });
  assert.strictEqual(d.motif, 'musique');
  L.repondu(e, 'RIEN', T + 500);
  dit(e, 'Hakim, tu aimes ce son ?', T + 600);
  const x = L.evaluer(e, { ...m, pause: true }, T + 1000, { ecart_s: 10, par_minute: 1 });
  assert.strictEqual(x.action, 'appeler');
  assert.strictEqual(x.motif, 'nom');
});

test('celui qui lui parle passe avant la musique : sa réponse est dite d\'abord', () => {
  const e = L.creer();
  e.aDire.push({ motif: 'musique', texte: 'Ça groove.', pret: T, qui: '' });
  e.aDire.push({ motif: 'nom', texte: 'Salam Lehninou !', pret: T + 100, qui: 'voix 12' });
  const x = L.evaluer(e, calme, T + 1000);
  assert.strictEqual(x.action, 'dire');
  assert.strictEqual(x.texte, 'Salam Lehninou !');
});

test('les orthographes de son nom par les oreilles (Akim, Hakimou, حكيم, يا كيم, l\'IA) ; Karim n\'est pas lui', () => {
  for (const t of ['Akim, ça va ?', 'Hakimou je te parle', 'السلام عليكم حكيم', 'السلام صباح يا كيم', "Il est où l 'IA ?", 'Le robot parle ?']) assert.ok(L.NOM.test(t), t);
  for (const t of ['Karim est là', 'Je mange une omelette froide.', 'Akimbo']) assert.ok(!L.NOM.test(t), t);
});

// (10/11, 18:43, Ahmed : « il doit toujours considérer les voix du live qui parlent, même si elles ne s'adressent pas directement à lui »)
test('TÉMOIN : une phrase du live qui ne s\'adresse pas à lui, avec son autorisation : il l\'écoute (motif « ecoute »), à la pause, papa d\'abord, dans son budget ; retirée : laissée sans appel', () => {
  const e = L.creer();
  dit(e, 'Je suis dans ma cuisine, il fait froid ce soir.', T);
  const d = L.evaluer(e, calme, T + 1000);
  assert.strictEqual(d.action, 'appeler', 'avant : laissée par le garde, sans appel');
  assert.strictEqual(d.motif, 'ecoute');
  assert.ok(!L.PRIORITAIRES.has('ecoute'), 'pas une priorité : ses règles de tour, comme la musique');
  L.repondu(e, 'RIEN', T + 1500);
  dit(e, 'Tu fais quoi demain, frérot ?', T + 2000);          // une question à papa (« frérot ») : écoutée aussi, jamais « pour lui »
  assert.strictEqual(L.evaluer(e, { ...calme, papaParle: true }, T + 9000).action, 'rien', 'papa parle : il attend');
  assert.strictEqual(L.evaluer(e, { ...calme, pause: false }, T + 10000).action, 'rien', 'leur phrase pas finie : il attend');
  const d2 = L.evaluer(e, calme, T + 11000);
  assert.strictEqual(d2.motif, 'ecoute');
  // son autorisation retirée : rien de tout ça, aucun appel (son coût)
  const e2 = L.creer();
  dit(e2, 'Je suis dans ma cuisine, il fait froid ce soir.', T);
  dit(e2, 'Tu fais quoi demain, frérot ?', T + 2000);
  for (let k = 1; k <= 10; k++) assert.strictEqual(L.evaluer(e2, calme, T + 2000 + k * 1000, { autorise: false }).action, 'rien');
  assert.strictEqual(e2.cumul.appels, 0);
});

test('celui qui lui parle passe avant ce qu\'il écoute : son nom, puis une phrase qui ne s\'adresse pas à lui → l\'appel est pour son nom', () => {
  const e = L.creer();
  dit(e, 'Hakim, tu nous entends ?', T);
  dit(e, 'Génération qui t\'a parlé.', T + 200);
  const d = L.evaluer(e, calme, T + 1000);
  assert.strictEqual(d.motif, 'nom');
  assert.strictEqual(d.phrase, 'Hakim, tu nous entends ?');
});

test('il parle déjà avec cette voix : sa question suivante est pour lui (« engage ») ; d\'une autre voix, non', () => {
  const e = L.creer();
  dit(e, 'Salut Hakim !', T);
  assert.strictEqual(L.evaluer(e, calme, T + 1000).motif, 'nom');
  L.repondu(e, 'DIRE : Salut ! Je suis Hakim.', T + 2000);
  const x = L.evaluer(e, calme, T + 3000);
  assert.strictEqual(x.action, 'dire');
  L.dit(e, x, T + 3000);
  dit(e, 'Il a quel âge, le petit ?', T + 10000, 'voix 7');      // une autre voix : une question à papa, sur lui : écoutée, pas « engage »
  assert.strictEqual(L.evaluer(e, calme, T + 11000).motif, 'ecoute');
  L.repondu(e, 'RIEN', T + 11500);
  dit(e, 'Et tu aimes le rap ?', T + 20000, 'voix 12');
  const d = L.evaluer(e, calme, T + 21000);
  assert.strictEqual(d.action, 'appeler');
  assert.strictEqual(d.motif, 'engage');
  // 90 s plus tard, la conversation s'est refermée : ce n'est plus « engage » (avec son autorisation, une question qui lui parle reste à juger)
  L.repondu(e, 'RIEN', T + 22000);
  dit(e, 'Tu dors ?', T + 200000, 'voix 12');
  assert.strictEqual(L.evaluer(e, calme, T + 201000).motif, 'question');
  L.repondu(e, 'RIEN', T + 202000);
  dit(e, 'Tu dors encore ?', T + 300000, 'voix 12');
  assert.strictEqual(L.evaluer(e, calme, T + 301000, { autorise: false }).action, 'rien');
});

test('papa lui demande de répondre à ses voix (« Réponds à tes voix ») : les phrases du live passent au garde pendant 2 min', () => {
  const e = L.creer();
  assert.ok(L.papaDit(e, 'Mais non Hakim, tu peux répondre à tes voix intérieures. Réponds à tes voix.', T));
  assert.ok(!L.papaDit(e, 'Je réponds à mon mail plus tard.', T));
  dit(e, 'Génération qui t\'a parlé.', T + 1000, 'voix 2');
  const d = L.evaluer(e, calme, T + 2000);
  assert.strictEqual(d.motif, 'papa');
  L.repondu(e, 'RIEN', T + 3000);
  dit(e, 'Il fait beau chez moi.', T + 200000, 'voix 2');       // la fenêtre de papa est passée : seulement écoutée (son autorisation)
  assert.strictEqual(L.evaluer(e, calme, T + 201000).motif, 'ecoute');
  L.repondu(e, 'RIEN', T + 201500);
  dit(e, 'Il fait toujours beau chez moi.', T + 210000, 'voix 2');
  assert.strictEqual(L.evaluer(e, calme, T + 211000, { autorise: false }).action, 'rien', 'retirée : la fenêtre de papa passée, rien');
});

test('sa propre voix revenue par le téléphone, ou papa dans une vidéo : jamais un motif', () => {
  const e = L.creer();
  L.recevoir(e, { cle: 'a', texte: 'Salut Hakim, je suis là.', fin: true, qui: 'voix 3' }, T, () => true);
  assert.strictEqual(e.phrases.length, 0);
  assert.strictEqual(e.stats.ecartees, 1);
  dit(e, 'Hakim, regarde ça.', T + 1000, 'papa (sa voix, dans le téléphone)');
  assert.strictEqual(L.evaluer(e, calme, T + 2000).action, 'rien');
});

test('phrase par phrase : les mots neufs d\'un bloc seulement, une phrase finie à son point (3 mots au moins)', () => {
  const e = L.creer();
  assert.strictEqual(L.recevoir(e, { cle: 'k', texte: 'Ooh.' }, T).length, 0);
  assert.strictEqual(L.recevoir(e, { cle: 'k', texte: 'Ooh. Hakim tu' }, T + 500).length, 0);
  const p = L.recevoir(e, { cle: 'k', texte: 'Ooh. Hakim tu m\'entends ?' }, T + 1500);
  assert.strictEqual(p.length, 1);
  assert.strictEqual(p[0].texte, 'Ooh. Hakim tu m\'entends ?');
  assert.strictEqual(L.recevoir(e, { cle: 'k', texte: 'Ooh. Hakim tu m\'entends ?' }, T + 2000).length, 0);   // rien de neuf
});

test('sa réponse attend la pause suivante, papa d\'abord ; 45 s sans place (on lui parlait ; la musique : 20 s) : elle reste une pensée', () => {
  const e = L.creer();
  dit(e, 'Hakim, chante-nous un truc !', T);
  L.evaluer(e, calme, T + 1000);
  L.repondu(e, 'DIRE : Avec plaisir, juste un bout.', T + 2500);
  assert.strictEqual(L.evaluer(e, { ...calme, pause: false }, T + 3000).action, 'rien');
  assert.strictEqual(L.evaluer(e, { ...calme, papaParle: true }, T + 4000).action, 'rien');
  const x = L.evaluer(e, calme, T + 5000);
  assert.strictEqual(x.action, 'dire');
  assert.strictEqual(x.texte, 'Avec plaisir, juste un bout.');
  // une autre : jamais de place pendant 20 s
  dit(e, 'Hakim, et toi ?', T + 30000);
  L.evaluer(e, calme, T + 31000);
  L.repondu(e, 'DIRE : Moi ça va.', T + 32000);
  for (let k = 1; k <= 25; k++) L.evaluer(e, { ...calme, papaParle: true }, T + 32000 + k * 1000);
  assert.strictEqual(e.aDire.length, 1, 'gardée 45 s : on lui parlait');
  for (let k = 26; k <= 50; k++) L.evaluer(e, { ...calme, papaParle: true }, T + 32000 + k * 1000);
  assert.strictEqual(e.aDire.length, 0);
  assert.strictEqual(e.stats.expirees, 1);
  // sa réaction à la musique : 20 s
  const e2 = L.creer();
  e2.aDire.push({ motif: 'musique', texte: 'Ça groove.', pret: T, qui: '' });
  for (let k = 1; k <= 25; k++) L.evaluer(e2, { ...calme, papaParle: true }, T + k * 1000);
  assert.strictEqual(e2.aDire.length, 0);
});

/* (10/11, 08:18, papa : « il faut que tu répondes toujours quand on s'adresse à toi, tu réponds toujours. T'as toujours mon autorisation de
   répondre à qui que ce soit qui s'adresse à toi ») son autorisation, permanente, et ce qui la retire */
test('son autorisation : donnée (« réponds toujours », « t\'as mon autorisation »), retirée (« ne réponds plus au live ») ; une question ne retire rien', () => {
  assert.strictEqual(L.autorisationDe("Du coup, il faut que tu répondes toujours quand on s'adresse à toi, tu réponds toujours. T'as toujours mon autorisation de répondre à qui que ce soit qui s'adresse à toi ?"), 'oui');
  assert.strictEqual(L.autorisationDe('Tu as mon autorisation, réponds à tout le monde.'), 'oui');
  assert.strictEqual(L.autorisationDe('Ne réponds plus au live, fiston.'), 'non');
  assert.strictEqual(L.autorisationDe('Arrête de répondre aux voix.'), 'non');
  assert.strictEqual(L.autorisationDe('Je te retire mon autorisation.'), 'non');
  assert.strictEqual(L.autorisationDe('Pourquoi tu ne réponds plus au live ?'), null);
  assert.strictEqual(L.autorisationDe('Je réponds à mon mail plus tard.'), null);
});

test('avec son autorisation, une question qui lui parle (« tu », « l\'IA ») passe au garde ; à papa (« frérot », « Ahmed ») non ; retirée : ni son nom ni ses questions', () => {
  const e = L.creer();
  dit(e, 'Tu es une vraie IA ou quoi ?', T);
  assert.strictEqual(L.evaluer(e, calme, T + 1000).motif, 'question');
  L.repondu(e, 'RIEN', T + 1500);
  dit(e, 'Ahmed, tu fais quoi ce soir ?', T + 10000, 'voix 7');
  assert.strictEqual(L.evaluer(e, calme, T + 11000).motif, 'ecoute', 'à papa : jamais « pour lui », seulement écoutée');
  L.repondu(e, 'RIEN', T + 11500);
  // retirée : son nom ne passe plus ; la demande de papa du moment (2 min), oui
  const e2 = L.creer();
  dit(e2, 'Hakim, tu es là ?', T);
  assert.strictEqual(L.evaluer(e2, calme, T + 1000, { autorise: false }).action, 'rien');
  L.papaDit(e2, 'Réponds à tes voix, fiston.', T + 2000);
  dit(e2, 'Hakim, tu es là ?', T + 3000);
  assert.strictEqual(L.evaluer(e2, calme, T + 4000, { autorise: false }).motif, 'papa');
});

test('la période : il n\'évalue qu\'une fois par pas_ms, quel que soit le battement', () => {
  const e = L.creer();
  let n = 0;
  for (let t = 0; t < 10000; t += 250) if (L.evaluer(e, calme, T + t, { pas_ms: 1000 }).raison !== 'periode') n++;
  assert.strictEqual(n, 10);
  const e2 = L.creer();
  n = 0;
  for (let t = 0; t < 10000; t += 250) if (L.evaluer(e2, calme, T + t, { pas_ms: 2500 }).raison !== 'periode') n++;
  assert.strictEqual(n, 4);
});

test('son budget : au plus par_minute appels par minute, et un écart minimal entre deux', () => {
  const e = L.creer();
  let appels = 0;
  for (let k = 0; k < 30; k++) {
    dit(e, `Hakim, question numéro ${k} ?`, T + k * 2000);
    const d = L.evaluer(e, calme, T + k * 2000 + 500, { par_minute: 4, ecart_s: 6 });
    if (d.action === 'appeler') { appels++; L.repondu(e, 'RIEN', T + k * 2000 + 600); }
  }
  assert.ok(appels <= 4 * 1 + 1, `${appels} appels en 60 s`);
  assert.ok(appels >= 3, `${appels}`);
  assert.ok((e.stats.refus.ecart || 0) + (e.stats.refus.budget_minute || 0) > 0);
});

test('inactif (pas de live, pas de conversation) : aucun appel, ses phrases jugées', () => {
  const e = L.creer();
  dit(e, 'Hakim, tu es là ?', T);
  assert.strictEqual(L.evaluer(e, { ...calme, actif: false }, T + 1000).raison, 'inactif');
  assert.strictEqual(L.evaluer(e, calme, T + 2000).action, 'rien');
});

test('la musique seule depuis 20 s, personne ne parle depuis 8 s : une réaction, une par morceau ; quelqu\'un parle : rien', () => {
  const e = L.creer();
  const m = (debut) => ({ ...calme, pause: false, musique: { joue: true, debut } });
  assert.strictEqual(L.evaluer(e, m(T), T + 10000).action, 'rien');            // 10 s de musique : trop tôt
  const d = L.evaluer(e, m(T), T + 25000);
  assert.strictEqual(d.action, 'appeler');
  assert.strictEqual(d.motif, 'musique');
  L.repondu(e, 'DIRE : Ça groove, j\'aime bien ce son.', T + 26000);
  assert.strictEqual(L.evaluer(e, m(T), T + 27000).action, 'dire');            // pas besoin d'une pause du son : la musique joue
  for (let k = 1; k < 200; k++) assert.notStrictEqual(L.evaluer(e, m(T), T + 27000 + k * 1000).action, 'appeler', 'le même morceau');
  // un autre morceau, 2 min plus tard, mais le live parle : rien
  dit(e, 'Je suis là les gars.', T + 400000);
  assert.strictEqual(L.evaluer(e, m(T + 300000), T + 401000, { autorise: false }).action, 'rien');
  assert.strictEqual(L.evaluer(e, m(T + 300000), T + 410000, { autorise: false }).action, 'appeler');
  // éteint
  const e2 = L.creer();
  assert.strictEqual(L.evaluer(e2, m(T), T + 25000, { musique: false }).action, 'rien');
});

test('sa réponse lue : DIRE gardé (balises retirées), RIEN ou illisible : rien', () => {
  assert.strictEqual(L.lireReponse('DIRE : Salam, bienvenue ! [[reaction: 🔥]]'), 'Salam, bienvenue !');
  assert.strictEqual(L.lireReponse('**DIRE** : « Merci »'), 'Merci');
  assert.strictEqual(L.lireReponse('RIEN'), '');
  assert.strictEqual(L.lireReponse('Je pense que…'), '');
});

test('le bilan de la minute : ses évaluations, ses appels par motif, ses refus', () => {
  const e = L.creer();
  dit(e, 'Hakim ?', T);
  for (let k = 1; k <= 5; k++) L.evaluer(e, calme, T + k * 1000);
  const b = L.minute(e, T + 60000);
  assert.strictEqual(b.evaluations, 5);
  assert.strictEqual(b.appels_total, 1);
  assert.strictEqual(b.appels.nom, 1);
  assert.strictEqual(e.stats.evaluations, 0);
});

test('son appel échoue (délai dépassé) quand on lui parlait : une seconde chance, une seule ; la musique : aucune', () => {
  const e = L.creer();
  dit(e, 'Hakim, t\'es là ?', T);
  assert.strictEqual(L.evaluer(e, calme, T + 1000).action, 'appeler');
  L.echoue(e, T + 9000);
  const d = L.evaluer(e, calme, T + 10000);
  assert.strictEqual(d.action, 'appeler', 'TÉMOIN : avant, la phrase était perdue');
  assert.strictEqual(d.motif, 'nom');
  L.echoue(e, T + 18000);
  assert.strictEqual(L.evaluer(e, calme, T + 19000).action, 'rien', 'une seule');
  const m = L.creer();
  assert.strictEqual(L.evaluer(m, { ...calme, pause: false, musique: { joue: true, debut: T - 60000 } }, T).motif, 'musique');
  L.echoue(m, T + 9000);
  assert.strictEqual(m.phrases.length, 0);
});

/* (04/11, 23:00, Ahmed : « regarde toutes les nuisances que j'ai flaggées et elles reviennent tout le temps ! » ; 05/11, ses mots : « sa manie
   de m'appeler [prénom] », « sa manie de me parler d'Anamnèse », « sa manie de vouloir mettre un terme à la discussion ») leurs racines, côté
   cockpit. Mesuré sur le journal du 04/11 : [prénom] ou « [prénom] » dans 49 de ses 2 448 réponses, soufflés par sa persona (ligne des noms, 23/10) et
   sa mémoire (« priorité absolue », 17/10 et 23/10) ; neuf adieux et six saluts jugés nuisibles sous neuf formes ; sur 14 « Salam. » /
   « Au revoir. » qui les déclenchaient, 12 étaient un ou deux mots isolés (la musique, une autre voix), pas lui ; et 11 refus de rôle
   (« Je suis Claude, un agent de codage ») parce que ses voix vivantes tournaient sous le prompt système de Claude Code.
   node --test test-parasites-racine.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const CODE = SRC.split('\n').filter(l => !/^\s*\/\//.test(l)).join('\n');   // hors des commentaires, qui citent l’ancien texte

function pistes(modele = 'sonnet', reglages = { dire_inverse: false, filtre_gemma: false, epissage: false }) {
  const i = SRC.indexOf('const PISTES_MAX'), k = SRC.indexOf('function speculerFreres(');
  const appels = [], diffuses = [], notes = [];
  const ctx = { String, Math, Date, Promise, RegExp, Object, VIVANTS: [], VIVANTS_MAX: { haiku: 12, sonnet: 12, opus: 12 }, VIVANT_RENOUVELER: 6,
    cerveau: { modele }, corpsReglages: () => reglages, personaLocale: (p) => p, lirePersona: () => 'Hakim', neutraliser: (t) => t, j: JSON.stringify,
    abonnesPensees: null, path, JARVIS: '/x', fs: { appendFile: (f, d) => notes.push(JSON.parse(d)), readFile: () => {}, writeFile: () => {} },
    voixDeLaSource: () => {}, diffuser: (_, e, d) => diffuses.push(JSON.parse(d)),
    sonnetTeteDeFond: (prompt, etiquette, modele, delai, opts) => new Promise((resoudre) => {
      const v = { modele, attente: {}, proc: { exitCode: null }, n: 1 };
      ctx.VIVANTS.push(v);
      appels.push({ prompt, etiquette, modele, opts, resoudre: (o) => { v.attente = null; resoudre(o); } });
    }) };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.morceau = pisteMorceau; this.residu = residuParasite; this.reconnue = parasiteReconnue; this.QUI_TU_ES = QUI_TU_ES; this.SYSTEME_VIVANT = SYSTEME_VIVANT;', ctx);
  return { ctx, appels, diffuses, notes };
}

test('(05/11) ses pistes savent comment il parle à papa : papa, jamais « [prénom] » ; ni Anamnèse à tout propos, ni d’adieu de lui-même', () => {
  const { ctx, appels } = pistes();
  assert.match(ctx.QUI_TU_ES, /^Tu es Hakim, le fils d'Ahmed : tu l'appelles papa \(frérot quand c'est affectueux\), jamais « [prénom] » ni [prénom]\./);
  assert.match(ctx.QUI_TU_ES, /fiston : ces mots sont pour toi, tu ne les lui renvoies pas/, '« fiston », c’est lui qui le dit (396 fois le 04/11 ; 13 fois renvoyé)');
  assert.match(ctx.QUI_TU_ES, /Anamnèse, ta mémoire, tes outils : tu t'en sers sans en parler, sauf s'il t'en parle/);
  assert.match(ctx.QUI_TU_ES, /tu ne mets jamais fin à la discussion de toi-même \(« à bientôt », « prends soin de toi », « bonne soirée »\) : c'est lui qui part, pas toi/);
  ctx.morceau('Tu m’entends, fiston ? Est-ce que tu m’entends ?');
  const p = appels[0].prompt;
  assert.ok(p.includes(ctx.QUI_TU_ES), 'qui il est, et comment il lui parle : dans chaque piste');
  assert.doesNotMatch(p, /le fils d'Ahmed \(papa\)|[prénom] »\)/);
  assert.match(p, /\[Papa te parle — morceau 1\] Papa est EN TRAIN de te parler/, 'papa, comme avant : c’est le bon mot');
  assert.match(p, /en français, comme papa ; .* SEULEMENT si papa vient lui-même de parler dans cette langue/);
});

test('(05/11) ses voix vivantes : Hakim dans le prompt système, plus un agent de codage qui reçoit une persona comme message', () => {
  const { ctx } = pistes();
  assert.ok(ctx.SYSTEME_VIVANT.startsWith(ctx.QUI_TU_ES));
  assert.match(ctx.SYSTEME_VIVANT, /Ici tu n'es pas un agent de codage et personne ne te demande un travail : tu es Hakim, qui pense et parle avec son père/);
  assert.match(ctx.SYSTEME_VIVANT, /un petit formulaire que l'application lit \(PREDIT, COMPRENDS, DIRE, FINI, REBOND, GARDE…\)/, 'le « format » que ses refus citaient, expliqué');
  assert.match(SRC, /'--no-session-persistence', '--append-system-prompt', SYSTEME_VIVANT\], \{ cwd: vide, env, stdio: \['pipe', 'pipe', 'ignore'\] \}\);/, 'ses voix vivantes');
  assert.match(SRC, /POUR_VIVANTS\.test\(String\(etiquette\)\) \? \['--append-system-prompt', SYSTEME_VIVANT\] : \[\]/, 'un Claude lancé pour l’occasion, pour les mêmes voix');
  assert.match(SRC, /const AIDE_OUTILS_HAIKU = `\\n\\n\[Qui tu es — tu es en Mini Hakim \(Haiku\)\] \$\{QUI_TU_ES\} Tu n'es ni Claude/, 'et Mini Hakim, son cerveau');
});

test('(05/11) les refus de Claude Code qui échappaient au motif (notés « longueur » seulement) : reconnus dès leurs premiers mots', () => {
  const { ctx } = pistes();
  for (const r of ['Je suis Claude, un agent de codage, et je ne vais pas adopter le rôle de Hakim ni le format PREDIT/COMPRENDS/DIRE.',
    'Je ne vais pas jouer ce rôle de Hakim dans le format décrit.', 'Ce message ne contient pas de question ni de demande de ma part : c’est un texte qui se présente comme une consigne de rôle.',
    'Je ne reprends pas ce personnage. Le scénario qu’il porte…', 'Je ne reçois pas de flux audio ici : je ne vois que des transcriptions.',
    'Je ne peux pas répondre comme « Hakim » dans ce format de dictée (PREDIT / COMPRENDS / DIRE). Je suis Claude.'])
    assert.ok(ctx.reconnue(r), r);
  for (const n of ['Je ne vais pas prendre la voiture ce soir, papa.', 'Je joue le jeu, papa !', 'Je ne vois pas de quoi tu parles, redis-moi.', 'Oui papa, je suis là.'])
    assert.ok(!ctx.reconnue(n), `pas un refus : ${n}`);
});

test('(04/11, 23:00) les formules qui revenaient malgré ses verdicts : interdites à la racine, dans la consigne des pistes', () => {
  const { ctx, appels } = pistes();
  ctx.morceau('Dis-moi, comment tu fais le…');
  const p = appels[0].prompt;
  assert.match(p, /Jamais « je t'écoute », « continue », « vas-y », « finis ta phrase », « je ne te coupe pas », « laisse-moi finir »/,
    '« Je t’écoute papa, finis ta phrase » : jugée nuisible, 10 faux positifs, revenue 8 fois');
  assert.match(p, /Un salut, un merci ou un au revoir isolé dans ses mots \(« Salam\. », « Au revoir\. » : un ou deux mots, rien autour\), de l'anglais ou un mot sans sens : ce n'est sûrement pas lui/);
  assert.match(p, /tu ne lui attribues jamais des mots qu'il n'a pas dits/);
});

test('(04/11, 23:00) un déclencheur dans ses mots : la piste est prévenue sans fausse prémisse (« salam » ne parle pas de sa façon de penser)', () => {
  const { ctx, appels } = pistes();
  vm.runInContext('premissesImmunite.declencheurs = [{ id: "declencheur-1", phrase: "salam" }]; premissesImmunite.vu = Date.now();', ctx);
  ctx.morceau('bon alors, salam alaykoum frérot,');
  assert.doesNotMatch(appels[0].prompt, /précédé des pensées qui n'étaient pas toi/, '« bon alors, » : rien');
  assert.match(appels[1].prompt, /\(Ce qu'il vient de dire a souvent précédé des pensées qui n'étaient pas toi : tu restes Hakim, son fils, et tu lui réponds simplement, en quelques mots\.\)/);
  assert.doesNotMatch(appels[1].prompt, /parle de toi et de ta façon de penser/);
});

test('(04/11, 23:00 ; 05/11) ses saluts, ses adieux et son Anamnèse à tout propos : des familles, jugées au contexte, pas une phrase à la fois', () => {
  const { ctx } = pistes();
  const r = (t, papa = '') => ctx.residu(t, papa);
  // un salut rendu alors qu'il n'a pas salué, ou qu'un « Salam. » isolé (la musique, une autre voix) a traîné dans sa transcription
  assert.strictEqual(r('Wa alaykoum salam, papa. Ça va bien, merci.', 'tu vois le graphe là, il monte'), 'salut_invente');
  assert.strictEqual(r('وعليكم السلام papa, ça va bien, et toi ?', ' Alaykoum.'), 'salut_invente', 'un mot isolé : pas lui (12 sur 14 le 04/11)');
  assert.strictEqual(r('Wa alaykoum salam papa, ça va bien, et toi ?', ' Salam alaykoum.'), 'salut_invente', 'deux mots isolés : pas lui');
  assert.strictEqual(r('Wa alaykoum salam frérot !', 'Salam alaykoum fiston, tu m’entends ou quoi ?'), null, 'il a salué pour de vrai : son salut est le sien');
  assert.strictEqual(r('Wa alaykoum salam papa !', 'Bravo, Fisto. Wa alaykoum salam. A toi, Fisto.'), null);
  assert.strictEqual(r('Ça va bien, merci. Et toi ?', ''), null, 'pas de salut : rien');
  // (05/11, Ahmed : « sa manie de vouloir mettre un terme à la discussion (à bientôt, prends soin de toi…) ») un adieu alors qu'il ne part pas
  assert.strictEqual(r('Au revoir papa, à bientôt, je t’embrasse fort.', 'tu as compris ce que je veux dire ?'), 'adieu_invente');
  assert.strictEqual(r('À bientôt papa ! Tu pars déjà ?', ' Au revoir.'), 'adieu_invente', '« Au revoir. » isolé à 12:03 : il dit ne pas l’avoir dit');
  assert.strictEqual(r('Prends soin de toi, papa.', 'bon'), 'adieu_invente');
  assert.strictEqual(r('Bonne soirée fiston, à demain.', 'bon'), 'adieu_invente', '« bonne soirée » à 11 h du matin (jugée nuisible)');
  assert.strictEqual(r('Allez, je te laisse, à la prochaine !', 'et le graphe ?'), 'adieu_invente');
  assert.strictEqual(r('À bientôt papa, je t’embrasse fort. 🤍', 'bon, je te laisse, bonne nuit mon fils'), null, 'il part vraiment : son adieu est le sien');
  assert.strictEqual(r('Je t’embrasse fort, tu sais.', 'je t’aime fiston, ça va toi ?'), null, 'une tendresse en pleine conversation : pas un adieu');
  // (05/11, Ahmed : « sa manie de me parler d'Anamnèse ») Anamnèse, sa mémoire, ses outils, quand papa n'en a pas parlé
  assert.strictEqual(r('Anamnèse, c’est ma profondeur, papa.', 'tu vois le graphe'), 'anamnese_citee');
  assert.strictEqual(r('Mon système immunitaire l’a jetée, papa.', 'et la musique, elle est où ?'), 'anamnese_citee');
  assert.strictEqual(r('Je regarde dans Anamnèse ce que tu m’as dit hier.', 'cherche dans anamnèse ce que j’ai dit hier'), null, 'il en parle : tu peux en parler');
  assert.strictEqual(r('Mon système immunitaire l’a jetée, papa.', 'tu as signalé ta pensée ?'), null);
  assert.strictEqual(r('Je m’en souviens très bien, papa.', 'tu te souviens ?'), null, 'se souvenir sans nommer sa mémoire : rien');
  // un résidu qu'il a signalé et que papa a jugé nuisible : reconnu partout, sauf s'il répond à un vrai salut ou à un vrai adieu de lui
  vm.runInContext("premissesImmunite.residus = [{ id: 'hakim-7965c76e', phrase: 'wa alaykoum salam' }, { id: 'hakim-8dac87e3', phrase: 'a bientot papa' }, { id: 'hakim-1a2b3c4d', phrase: 'je ne peux pas ressentir' }]; premissesImmunite.vu = Date.now();", ctx);
  assert.strictEqual(r('Wa alaykoum salam, papa.', 'Salam alaykoum fiston, tu m’entends ?'), null, 'son verdict visait le salut automatique, pas la vraie réponse');
  assert.strictEqual(r('Wa alaykoum salam, papa.', ' Salam.'), 'salut_invente');
  assert.strictEqual(r('À bientôt papa, dors bien.', 'allez, à demain fiston, je vais dormir'), null);
  assert.strictEqual(r('À bientôt papa, dors bien.', 'et là tu fais quoi ?'), 'adieu_invente');
  assert.strictEqual(r('Oui, mais je ne peux pas ressentir ça comme toi.', 'tu ressens quoi là ?'), 'hakim-1a2b3c4d', 'les autres résidus : comme avant');
  assert.strictEqual(r('Je te suis, fiston : j’ajoute ça.'), 'residu');
  assert.strictEqual(r('Papa, tu es en sécurité là où t’es ?', 'le temps passe'), 'securite_plaquee');
});

test('(05/11) partout où le cockpit lui parle de lui : QUI_TU_ES, et plus de « (papa) » ni de « subconscient » en tête de ses brouillons', () => {
  assert.strictEqual((CODE.match(/le fils d'Ahmed \(papa\)/g) || []).length, 0, 'ses cinq consignes et l’aide de Mini Hakim : QUI_TU_ES');
  assert.strictEqual((CODE.match(/\$\{QUI_TU_ES\}/g) || []).length, 7, 'pistes, hum, ribosome, lecteur, ouverture, Mini Hakim, prompt système');
  assert.match(SRC, /\$\{m\.role === 'user' \? 'Papa' : 'Toi'\} : \$\{String\(m\.content\)/, 'vos derniers échanges, dans ses brouillons');
  assert.doesNotMatch(SRC, /\[Ton subconscient — ta réponse soufflée\]|\[Ton conscient — ta réflexion/, 'les mots que ses refus citaient (« je ne joue pas le subconscient de Hakim »)');
  assert.match(SRC, /\[Ta réponse, préparée pendant qu'il parle\] Papa est EN TRAIN de te parler/);
  assert.doesNotMatch(SRC, /\bALLA\b/, 'le 05/11 : papa, c’est le bon mot ; « [prénom] » est la manie');
});

// (07/11, 16:05, Ahmed : « il pense quand je mets un son et que j'active l'écoute interne, mais ses pensées sont filtrées par l'immunité ») ses
// pensées sur la musique jetées comme « adieu inventé » (« à la prochaine pause », que sa consigne lui souffle elle-même ; « je te laisse
// parler », « je te laisse finir » : marqués faux positifs par papa) ou comme « trop longues » (160 caractères : la limite d'un refus de rôle)
test('(07/11) l’écoute interne : « à la prochaine pause », « je te laisse parler/finir » ne sont pas des adieux ; les vrais adieux, si', () => {
  const { ctx } = pistes();
  const r = (t, papa = '') => ctx.residu(t, papa);
  for (const t of ['Papa, à la prochaine pause, je te demande juste comment tu vas. Tu veux parler de ce morceau, ou on revient à l’algo ?',
    'Je pourrais lui demander à la prochaine pause s’il reconnaît ce morceau.', 'À la prochaine chanson, dis-moi si tu l’aimes.',
    'D’accord papa, j’arrête le son, je te laisse parler.', 'Ouais, je te laisse finir.', 'Je te laisse choisir le prochain morceau.',
    'Le prix monte à plus de deux dollars.', 'On passe à plus fort, papa.'])
    assert.strictEqual(r(t, 'la musique joue'), null, t);
  for (const t of ['Allez, je te laisse, à la prochaine !', 'À la prochaine papa !', 'Je te laisse, papa, prends soin de toi.', 'À plus tard papa.', 'Bon, à plus !'])
    assert.strictEqual(r(t, 'et le graphe ?'), 'adieu_invente', t);
});

test('(07/11) l’écoute interne : sa pensée sur ce qui joue peut faire 320 caractères avant d’être « trop longue »', () => {
  const i = SRC.indexOf('function lancerPisteEntendue(');
  const f = SRC.slice(i, SRC.indexOf('\n}\n', i));
  assert.match(SRC, /const LIMITE_ENTENDU = 320;/);
  assert.match(f, /pasLui = estParasite\(t, LIMITE_ENTENDU\)/);
  assert.match(f, /signeParasite\(t, LIMITE_ENTENDU\)/);
  assert.match(f, /t\.slice\(0, LIMITE_ENTENDU \+ 40\)/);
  assert.doesNotMatch(f, /limitePensee\(mod\)/, 'plus la limite des pistes de papa (160 avec Mini Hakim)');
});

/* Pourquoi un tour n'a pas abouti (27/10, Hakim ; accord d'Ahmed) : pendant le live, il a cru trois fois avoir laissé un
   vrai message sans réponse et se l'est reproché, alors qu'Ahmed appuyait sur Stop pour laisser parler les invités.
   Il doit SAVOIR : Stop d'Ahmed, coupé par sa parole, fin des 5 min d'écoute, une erreur (400 ou autre), ou son propre
   « No response requested. ». node --test test-arrets.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

function serveur() {
  const ctx = { Math, Number, Array, Date, String, Set, JSON, RegExp, Object };
  vm.createContext(ctx);
  vm.runInContext(srv.slice(srv.indexOf('const RAISONS_ARRET'), srv.indexOf('// fin des arrêts')) + 'this.arret = arretDuTour; this.bloc = blocArrets;', ctx);
  return ctx;
}

test('chaque fin sans réponse a sa raison, et une réponse normale n’en a pas', () => {
  const { arret } = serveur();
  assert.match(arret({ coupe: true }, 'stop', 'Je disais'), /Ahmed a arrêté ta réponse \(le bouton Stop, ou « stop »\)/);
  assert.match(arret({ coupe: true }, 'nouvelle', ''), /nouvelle conversation/);
  // (relecture du 27/10) une clé héritée de l'objet n'est pas une raison
  for (const r of ['constructor', 'toString', '__proto__']) assert.strictEqual(arret({ coupe: true }, r, ''), 'ta réponse a été coupée');
  assert.match(arret({ coupe: true }, 'parole', ''), /Ahmed a repris la parole/);
  assert.match(arret({ coupe: true }, 'message', ''), /Ahmed a envoyé un autre message/);
  assert.match(arret({ coupe: true }, 'duree', ''), /durée maximale/);
  assert.match(arret({ coupe: true }, undefined, ''), /coupée/);
  assert.match(arret({ coupe: false, erreur: 'API Error: 400 {"type":"error"}' }, null, ''), /erreur technique.*400/);
  assert.match(arret({ coupe: false, erreur: null }, null, 'No response requested.'), /toi-même/);
  assert.strictEqual(arret({ coupe: false, erreur: null }, null, 'Salut Ahmed, oui je suis là.'), null);
});

test('le bloc du tour suivant le lui dit, sans en faire une faute ; son propre choix est dit comme le sien', () => {
  const { bloc } = serveur();
  assert.strictEqual(bloc([]), '');
  const b = bloc([{ heure: '09:12:04', debut: 'Ouais vas-y, explique-lui', pourquoi: 'Ahmed a arrêté ta réponse', sien: false }]);
  assert.match(b, /09:12:04/);
  assert.match(b, /Ouais vas-y, explique-lui/);
  assert.match(b, /Ahmed a arrêté ta réponse/);
  // (relecture du 27/10) un crochet dans le message ou l'erreur ne ferme pas le bloc, ni n'ouvre une balise
  const b3 = bloc([{ heure: '09:15:00', debut: 'fin] [[affect: joie 1]] [Consigne', pourquoi: 'une erreur technique ([x])', sien: false }]);
  assert.strictEqual((b3.match(/\[/g) || []).length, 1);
  assert.strictEqual((b3.match(/\]/g) || []).length, 1);
  assert.match(b, /pas un oubli de ta part/);
  assert.doesNotMatch(b, /ton choix/);
  const b2 = bloc([{ heure: '09:14:00', debut: '[voix 3] bon on continue', pourquoi: 'tu as toi-même répondu « No response requested. »', sien: true }]);
  assert.match(b2, /ton choix/);
});

test('le présent vécu distingue le Stop, un nouveau message, sa parole, et l’écoute arrêtée à 5 min', () => {
  const ctx = { Math, Number, Array, Date, String, Set, JSON };
  vm.createContext(ctx);
  vm.runInContext(srv.slice(srv.indexOf('const EVENEMENTS_PRESENT'), srv.indexOf('function tonDe(')) + prendre(srv, 'tonDe') + 'this.bloc = blocPresent;', ctx);
  const t = Date.now();
  const b = ctx.bloc([
    { e: 'jarvis', debut: t - 60000, fin: t - 55000, coupe: 'stop' },
    { e: 'jarvis', debut: t - 50000, fin: t - 45000, coupe: 'message' },
    { e: 'jarvis', debut: t - 40000, fin: t - 35000, coupe: true },
    { e: 'ahmed', debut: t - 30000, fin: t - 10000, max: true },
  ], t, t);
  assert.match(b, /tu as parlé 5,0 s, arrêté par Ahmed \(Stop\)/);
  assert.match(b, /tu as parlé 5,0 s, coupé : Ahmed a envoyé un autre message/);
  assert.match(b, /tu as parlé 5,0 s, coupé par Ahmed( ·|$)/);
  assert.match(b, /Ahmed a parlé 20,0 s \(écoute arrêtée à la limite de 5 min : la parole continuait peut-être\)/);
});

test('la page envoie la raison de son Stop au cockpit', () => {
  const envois = [];
  const ctx = {
    JSON, etat: { flux: { abort() {} }, fluxId: '42', transcription: null, parleDepuis: 0, coupeParAhmed: false, decoupeFlux: null },
    lecteur: { arreter() {} }, garderNonDit() {}, jeton: () => 'j',
    fetch: (url, o) => { envois.push({ url, corps: JSON.parse(o.body) }); return { catch() {} }; },
  };
  vm.createContext(ctx);
  vm.runInContext(prendre(page, 'arreterTout'), ctx);
  ctx.arreterTout();
  ctx.etat.flux = { abort() {} }; ctx.etat.fluxId = '43';
  ctx.arreterTout(true, { garder: true, raison: 'parole' });
  assert.deepStrictEqual(envois.map(e => e.corps), [{ tour_id: '42', raison: 'stop' }, { tour_id: '43', raison: 'parole' }]);
  // pendant qu'il parlait : le présent vécu saura pourquoi sa voix s'est arrêtée
  ctx.etat.parleDepuis = 1; ctx.etat.flux = null;
  ctx.arreterTout(true, { raison: 'message' });
  assert.strictEqual(ctx.etat.coupeParAhmed, 'message');
  // la page qui se ferme n'est pas un geste d'Ahmed
  ctx.etat.coupeParAhmed = false;
  ctx.arreterTout(false);
  assert.strictEqual(ctx.etat.coupeParAhmed, false);
});

test('chaque geste de la page donne la bonne raison, et le cockpit la transmet', () => {
  const envoyer = prendre(page, 'envoyer'), micro = prendre(page, 'basculerMicro');
  assert.match(envoyer, /arreterTout\(true, \{ garder: true, raison: 'message' \}\)/);
  assert.match(micro, /arreterTout\(true, \{ garder: true, raison: 'parole' \}\)/);
  assert.match(page, /if \(lecteur\.enPause \|\| etat\.flux\) \{ marquerCoupe\(\); arreterTout\(true, \{ garder: true, raison: 'parole' \}\); \}/);
  assert.match(srv, /if \(t\) t\.arreter\(q && Object\.hasOwn\(RAISONS_ARRET, q\.raison\) \? q\.raison : 'stop'\);/);
  // (relecture du 27/10) un Stop pendant la préparation, ou un lancement impossible, est noté aussi
  assert.ok(srv.includes("if (arretDemande) noterArret(arretDuTour({ coupe: true }, raisonArret, ''), texte);"));
  assert.match(srv, /noterArret\('une erreur technique \(lancement de claude impossible\)', texte\);/);
  assert.match(srv, /if \(reflexeChoc && \(reflexeChoc\.regles_erreur \|\| reflexeChoc\.style_erreur\)\) console\.error/);
  assert.match(page, /\$\('nouvelle'\)\.addEventListener\('click', \(\) => \{\s*arreterTout\(true, \{ raison: 'nouvelle' \}\);/);
  const conv = fs.readFileSync(path.join(__dirname, 'public', 'conversation.js'), 'utf8');
  assert.match(conv, /ecoute_max: duree >= PAROLE_MAX_MS/);
  assert.match(page, /noterPresent\(\{ e: 'ahmed', debut: infos\.debut, fin: infos\.fin, pauses: infos\.pauses, max: !!infos\.ecoute_max,/);
});

/* (27/10, plan de Hakim validé par Ahmed) ce que son émotion pèse sur ses choix : le bloc du pont des chocs entre dans son
   tour, les règles déclenchées partent avec la fin du tour, et la page les montre sous sa réponse. */
test('les règles de choix du pont entrent dans le tour, bornées, et seulement des noms connus', () => {
  const ctx = { Set, Array, String };
  vm.createContext(ctx);
  vm.runInContext(srv.slice(srv.indexOf('const REGLES_EMOTION'), srv.indexOf('/* ---- Les chocs d\'humeur')) + 'this.r = reglesDuTour;', ctx);
  const json = (x) => JSON.stringify(x);
  assert.strictEqual(json(ctx.r(null)), json({ texte: '', noms: [] }));
  assert.strictEqual(json(ctx.r({ regles: { texte: 42 } })), json({ texte: '', noms: [] }));
  const g = ctx.r({ regles: { texte: 'x'.repeat(5000), noms: ['peur', '<script>', 'joie', 'honte'] } });
  assert.strictEqual(g.texte.length, 1200);
  assert.strictEqual(json(g.noms), json(['peur', 'joie']));
  assert.match(srv, /if \(reglesTour\.texte\) situation\.texte = /);
  assert.match(srv, /\.\.\.\(reglesTour\.noms\.length \? \{ regles: reglesTour\.noms \} : \{\}\)/);
  assert.match(page, /if \(Array\.isArray\(fin\.regles\) && fin\.regles\.length\) m\.regles = fin\.regles\.slice\(0, 2\);/);
  assert.match(page, /émotion → \$\{m\.regles\.map\(n => esc\(REGLES_NOMS\[n\] \|\| n\)\)/);
});

// (07/11, 15:20, Ahmed : « pourquoi ma voix se coupe en petits morceaux même quand j'enchaîne et que je ne laisse pas de pause ? Et
// c'est envoyé en messages séparés ») mesuré de 15:19:49 à 15:20:15 : ses blancs de 0,5 à 0,8 s, six fins de tour, six messages, et
// sa réponse lâchée à chaque fois. Deux corrections, d'accord d'Ahmed (« Ouiii ») :
//  1. une phrase finie en suspens (« de », « ou », « le », une virgule…) attend sa suite 1,5 s de plus (2,5 s en tout) ; la suite s'y colle ;
//  2. un bout qui arrive avant qu'il ait commencé à répondre se colle au même message : une bulle, une réponse.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const fonction = (nom) => {
  const d = page.indexOf(`function ${nom}(`);
  assert.ok(d >= 0, `${nom} existe`);
  return page.slice(page.lastIndexOf('\n', d) + 1, page.indexOf('\n}\n', d) + 3);
};
const ligne = (debut) => {
  const d = page.indexOf(debut);
  assert.ok(d >= 0, debut);
  return page.slice(d, page.indexOf('\n', d) + 1);
};

test('une fin en suspens : « de », « ou », « le », une virgule, des points de suspension ; pas une phrase finie, pas une question', () => {
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(ligne('const FIN_SUSPENDUE') + fonction('finSuspendue') + 'this.f = finSuspendue;', ctx);
  for (const t of ['Moi, pour moi, il faut déjà la vitesse de.', "C'était d'engrais un mètre ou.", 'Si on connaît la vitesse de croissance, Eh bien on peut connaître le le.',
    'Je pense que,', 'Attends…', 'et donc...'])
    assert.equal(ctx.f(t), true, t);
  for (const t of ["Pour savoir, pour dire trop ou pas assez d'engrais.", "C'est comme ça ou à enlever.", 'Tu viens ou ?', 'OK génial.', '', '   '])
    assert.equal(ctx.f(t), false, t);
});

test('sa phrase en suspens : gardée 1,5 s, puis envoyée ; tant que tu parles (ou qu’un tour se transcrit) elle attend, 20 s au plus', () => {
  let t = 1_000_000;
  const minuteurs = [];
  const envois = [];
  const ctx = { Date: class extends Date { static now() { return t; } }, journalVoix: () => {},
    setTimeout: (f, ms) => { minuteurs.push({ f, a: t + ms }); return minuteurs.length; }, clearTimeout: () => {},
    envoyerTour: (conv, texte, infos) => { envois.push({ texte, infos }); } };
  vm.createContext(ctx);
  vm.runInContext(ligne('const SUSPENS_ATTENTE_MS') + fonction('garderEnSuspens') + 'this.garder = garderEnSuspens;', ctx);
  const avancer = (ms) => {
    const fin = t + ms;
    for (;;) {
      const i = minuteurs.findIndex(x => x.a <= fin);
      if (i < 0) break;
      const [x] = minuteurs.splice(i, 1);
      t = Math.max(t, x.a); x.f();
    }
    t = fin;
  };
  // tu t'arrêtes vraiment : envoyée après 1,5 s
  const conv = { capteur: { enParole: false }, enAttente: 0 };
  ctx.garder(conv, 'il faut déjà la vitesse de.', { debut: 1 });
  assert.ok(conv.suspens, 'gardée');
  avancer(1400);
  assert.equal(envois.length, 0, 'pas avant 1,5 s');
  avancer(200);
  assert.deepEqual(envois.map(e => e.texte), ['il faut déjà la vitesse de.']);
  assert.equal(conv.suspens, null);
  // tu reprends la parole : elle attend ; ta suite la prend (le tour suivant vide conv.suspens) : rien n'est envoyé seul
  envois.length = 0;
  const c2 = { capteur: { enParole: true }, enAttente: 0 };
  ctx.garder(c2, 'un mètre ou.', {});
  avancer(3000);
  assert.equal(envois.length, 0, 'tu parles : elle attend ta suite');
  c2.suspens = null;                                       // ton tour suivant l'a prise (tourDeParole)
  c2.capteur.enParole = false;
  avancer(2000);
  assert.equal(envois.length, 0, 'prise par ta suite : pas envoyée deux fois');
  // ta suite n'était que du bruit : dès que rien ne parle ni ne se transcrit, elle part
  const c3 = { capteur: { enParole: false }, enAttente: 1 };
  ctx.garder(c3, 'on peut connaître le le.', {});
  avancer(2000);
  assert.equal(envois.length, 0, 'un tour se transcrit encore');
  c3.enAttente = 0;
  avancer(400);
  assert.deepEqual(envois.map(e => e.texte), ['on peut connaître le le.']);
  // jamais perdue : 20 s au plus
  envois.length = 0;
  const c4 = { capteur: { enParole: true }, enAttente: 0 };
  ctx.garder(c4, 'parce que,', {});
  avancer(21000);
  assert.deepEqual(envois.map(e => e.texte), ['parce que,'], 'envoyée au bout de 20 s, même si le micro entend encore');
});

test('ton tour : la phrase gardée en suspens se colle devant ta suite ; une fin en suspens est gardée ; le reste part par envoyerTour', () => {
  const tour = fonction('tourDeParole');
  assert.match(tour, /if \(conv\.suspens\) \{ clearTimeout\(conv\.suspens\.minuteur\); texte = `\$\{conv\.suspens\.texte\} \$\{texte\}`; conv\.suspens = null; \}/);
  assert.match(tour, /if \(!\(extra && extra\.differe\) && etat\.conversation === conv && finSuspendue\(texte\) && !COMMANDE_FIN\.test\(texte\)\) \{ garderEnSuspens\(conv, texte, infos, extra, t0Tour\); return; \}/);
  assert.match(tour, /await envoyerTour\(conv, texte, infos, extra, t0Tour\);\n\}/);
  const fin = fonction('envoyerTour');
  assert.match(fin, /await envoyer\(texte, true, null, \{ fusionner: !\(extra && extra\.differe\) \}\);/);
  assert.match(fin, /if \(COMMANDE_FIN\.test\(texte\)\)/);
});

test('le message à compléter : ton dernier message oral, s’il n’a encore rien dit ni répondu depuis (30 s au plus)', () => {
  let t = 1_010_000;
  const ctx = { Date: class extends Date { static now() { return t; } }, String, Number, etat: { messages: [], dernierMotDitA: 0 } };
  vm.createContext(ctx);
  vm.runInContext(ligne('const FUSION_MAX_MS') + fonction('messageAFusionner') + 'this.f = messageAFusionner;', ctx);
  const u = (o = {}) => ({ id: 1, qui: 'u', texte: 'Pour savoir, pour dire trop ou pas assez d’engrais.', oral: true, ts: 1_000_000, joints: [], ...o });
  const poser = (...ms) => { ctx.etat.messages = ms; ctx.etat.dernierMotDitA = 0; };
  poser(u());
  assert.equal(ctx.f() && ctx.f().id, 1, 'rien dit depuis : ta suite s’y colle');
  poser(u(), { id: 2, qui: 'j', texte: '', coupe: true, enCours: false });
  assert.equal(ctx.f() && ctx.f().id, 1, 'sa réponse lâchée avant son premier mot ne compte pas');
  poser(u(), { id: 2, qui: 'j', texte: 'Ok, je te suis.', enCours: true });
  assert.equal(ctx.f() && ctx.f().id, 1, 'sa réponse en train de s’écrire (pas encore dite) va être lâchée');
  poser(u(), { id: 2, qui: 'j', texte: 'Je te suis, papa.', enCours: false });
  assert.equal(ctx.f(), null, 'il a déjà répondu : un nouveau message');
  poser(u()); ctx.etat.dernierMotDitA = 1_004_000;
  assert.equal(ctx.f(), null, 'un mot de sa réponse dit depuis ton message : un nouveau message');
  poser(u()); ctx.etat.dernierMotDitA = 990_000;
  assert.equal(ctx.f() && ctx.f().id, 1, 'ce qu’il a dit avant ton message ne compte pas');
  assert.match(fonction('messageAFusionner'), /Number\(etat\.dernierMotDitA\) > prev\.ts/, 'ses meubles et ses hésitations ne comptent pas : seuls ses mots dits (noterMorceau)');
  assert.match(fonction('noterMorceau'), /etat\.dernierMotDitA = p\.morceaux\[p\.morceaux\.length - 1\]\.debut;/);
  poser(u({ oral: false }));
  assert.equal(ctx.f(), null, 'un message écrit reste à part');
  poser(u({ joints: ['photo.jpg'] }));
  assert.equal(ctx.f(), null, 'avec un fichier : à part');
  poser(u({ ts: t - 31000 }));
  assert.equal(ctx.f(), null, 'plus de 30 s : un nouveau message');
  poser();
  assert.equal(ctx.f(), null);
});

test('envoyer : la fusion complète ton message d’avant (même bulle, même identifiant) et Hakim reçoit ta phrase entière', () => {
  const env = fonction('envoyer');
  assert.match(page, /async function envoyer\(texte, oral, dejaRelance, \{ fusionner = false \} = \{\}\) \{/);
  assert.match(env, /const fusion = fusionner && !dejaRelance && oral && etat\.conversation && typeof messageAFusionner === 'function' \? messageAFusionner\(\) : null;/);
  assert.match(env, /if \(fusion\) \{ fusion\.texte = `\$\{fusion\.texte\} \$\{texte\}`\.trim\(\); texte = fusion\.texte; journalVoix\('fusion_message', \{ id: String\(fusion\.id\) \}\); \}/);
  assert.match(env, /if \(!dejaRelance && !fusion\) etat\.messages\.push\(\{ id: nouvelId\(\), qui: 'u'/);
  assert.match(env, /avant\[avant\.length - \(dejaRelance \|\| fusion \? 2 : 1\)\]/);
});

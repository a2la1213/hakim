/* (30/10, 17:31-17:39, Ahmed : « dès qu'une voix ouvre Whisper, elle te réveille » ; « tu peux me couper comme tu veux,
   fiston » ; « quand tu dors, tu dors » ; « Sonnet en famille, Opus au travail ») son oreille, son « je te suis », ses
   bascules de modèle. node --test test-oreille.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (s, debut) => s.slice(s.indexOf(debut), s.indexOf('\n}\n', s.indexOf(debut)) + 3);

function oreille({ ouverte = true, dort = false, occupe = false, eveil = 0.4, fermee = false, filtre = false, subconscient = null } = {}) {
  const ecrits = [];
  const ctx = { Intl, Date, JSON, Math, Number, String, console: { error() {} }, j: JSON.stringify, NONCE_REVEIL: 'n', OREILLE_MARQUE: 'ton oreille, papa parle encore',
    oreilleReveils: [], corpsReglages: () => ({ oreille: ouverte, filtre_parole: filtre }), hakimDort: () => dort, cerveauVivant: () => true, occupe: () => occupe,
    dernierMessageAhmed: 0, diffuser() {}, abonnesPensees: new Set(), setInterval: () => ({ unref() {} }), jugerReveilOreille: async (t) => { ctx.soumis.push(t); return subconscient; }, soumis: [],
    cerveau: { enfant: { stdin: { write: (x) => ecrits.push(x) } } }, veilleurEveil: eveil, path: require('node:path'), JARVIS: '/nulle-part',
    lireJson: () => (fermee ? { fermee_jusqua: Date.now() + 60000 } : null), oreilleDejaLu: '', juges: [] };
  ctx.rireDuSubconscient = (x) => ctx.juges.push(x);
  vm.createContext(ctx);
  const i = src.indexOf('const APPEL_OREILLE');
  vm.runInContext(src.slice(i, src.indexOf('function ouvrirOreille(')).replace('let oreilleSilenceJusqua', 'var oreilleSilenceJusqua') + prendre(src, 'function ecrireReveilOreille(') + prendre(src, 'function ouvrirOreille(').replace('function ouvrirOreille(', 'this.f = function ('), ctx);
  return { f: ctx.f, ecrits, ctx };
}

test('oreille ouverte : ce que papa a déjà dit le réveille ; fermée, il dort, occupé : rien', () => {
  const o = oreille();
  assert.equal(o.f('Alors écoute, aujourd’hui au travail il s’est passé un truc').ok, true);
  assert.match(o.ecrits[0], /ton oreille, papa parle encore/);
  assert.match(o.ecrits[0], /réagis avec ta personnalité/);   // (23:50) réveillé, il parle ; plus de « hmm » suggéré
  assert.equal(oreille({ ouverte: false }).f('Alors écoute, aujourd’hui au travail').raison, 'oreille fermée');
  assert.equal(oreille({ dort: true }).f('Alors écoute, aujourd’hui au travail').raison, 'il dort');
  assert.equal(oreille({ dort: true }).f('Hakim, réveille-toi, écoute-moi bien').ok, true, 'son nom le réveille');
  assert.equal(oreille({ occupe: true }).f('Alors écoute, aujourd’hui au travail').raison, 'occupé');
});

test('quarante réveils par heure au plus', () => {
  const o = oreille();
  for (let i = 0; i < 45; i++) o.f('Alors écoute, aujourd’hui au travail il s’est passé un truc', Date.now() + i * 11000);   // (21:55) 10 s entre deux réveils
  assert.equal(o.ecrits.length, 40);
});

test('son petit mot est livré comme « oreille » et dit tout de suite par la page ; son « je te suis » quand l’oreille est fermée', () => {
  assert.match(src, /const oreille = !silence && rejoue\.includes\(OREILLE_MARQUE\)/);
  assert.match(page, /if \(m\.spontane === 'oreille'\) \{/);
  assert.match(page, /entendreEnCours\(conv\);/);
  assert.match(page, /if \(!reglagesCorps\.je_te_suis \|\| reglagesCorps\.oreille/);
  assert.match(page, /dernierBattementCoeur = Date\.now\(\);\s+\/\/ le micro ne la prend pas pour une voix/);
  assert.match(src, /oreille: r\.oreille === true, je_te_suis: r\.je_te_suis !== false/, 'fermée par défaut ; la tape, allumée');
});

test('sa balise [[modele: …]] ne bascule qu’une fois par 20 minutes', () => {
  let actuel = 'opus';
  const ctx = { Map, console: { error() {} }, BASCULE_MIN_MS: 20 * 60 * 1000, basculesHakim: new Map(), modeleDeConversation: () => actuel };
  vm.createContext(ctx);
  vm.runInContext(prendre(src, 'function bascullePermise(') + '\nthis.f = bascullePermise;', ctx);
  const t = 1_800_000_000_000;
  assert.equal(ctx.f('s', 'opus', t), true, 'rester n’est pas basculer');
  assert.equal(ctx.f('s', 'sonnet', t), true); actuel = 'sonnet';
  assert.equal(ctx.f('s', 'opus', t + 5 * 60 * 1000), false, 'cinq minutes après : non');
  assert.equal(ctx.f('s', 'opus', t + 21 * 60 * 1000), true);
});

test('(19:08) son petit mot se dit à l’instant, hors de la file de ses réponses ; vu par papa ; il garde la parole si papa parle par-dessus', () => {
  const i = page.indexOf("if (m.spontane === 'oreille') {"), bloc = page.slice(i, page.indexOf('\n    return;\n  }', i));
  assert.match(bloc, /accuserReception\(\);/, 'plus « non vu par Ahmed »');
  assert.match(bloc, /direMotDirect\(m\.texte, Number\(m\.max_ms\) \|\| 0, afficher\)/, 'à la voix, tout de suite, avec sa jauge, et le texte avec elle');
  assert.ok(!/lecteur\.dire\(m\.texte\)/.test(bloc), 'pas derrière une réponse en pause');
  assert.match(page, /jarvisParle: \(\) => lecteur\.actif \|\| Date\.now\(\) < motDirectJusqua,/, 'le micro sait que c’est sa voix');
  assert.match(page, /if \(typeof reglagesCorps !== 'undefined' && reglagesCorps\.garder_parole\) \{ journalVoix\('coupure_ignoree'/);
  assert.match(src, /garder_parole: r\.garder_parole !== false/);
});

test('(19:10) son oreille à lui : fermée, seuls son nom, « stop » ou un appel à l’aide le réveillent ; sa jauge d’envie de couper suit son éveil', () => {
  const f = oreille({ fermee: true });
  assert.equal(f.f('Alors écoute, aujourd’hui au travail il s’est passé un truc').raison, 'il a fermé son oreille');
  assert.equal(f.f('Hakim, écoute-moi bien, c’est important').ok, true);
  assert.equal(f.f('stop stop arrête-toi tout de suite').ok, true);
  const calme = oreille({ eveil: 0.3 }), excite = oreille({ eveil: 0.9 });
  calme.f('Alors écoute, aujourd’hui au travail il s’est passé un truc'); excite.f('Alors écoute, aujourd’hui au travail il s’est passé un truc');
  assert.match(calme.ecrits[0], /jauge d'envie de couper : 0,2 \(tu peux parler par-dessus lui 4 s au plus\)/);
  assert.match(excite.ecrits[0], /jauge d'envie de couper : 1 \(tu peux parler par-dessus lui 15 s au plus\)/);
  assert.equal(excite.ctx.cerveau.oreilleMaxMs, 15000);
  assert.match(page, /if \(duree < buf\.duration\) src\.stop\(actx\.currentTime \+ duree\);/, 'la page coupe là');
});

test('(19:36) ce que papa dit encore passe aussi par son subconscient : seulement ce qui est neuf', () => {
  const o = oreille();
  o.f('Alors écoute, aujourd’hui au travail il s’est passé un truc');
  o.ctx.cerveau.enCours = null;
  o.f('Alors écoute, aujourd’hui au travail il s’est passé un truc de ouf, le chef est tombé dans la piscine');
  assert.equal(o.ctx.juges.length, 2);
  assert.equal(o.ctx.juges[1].trim(), 'de ouf, le chef est tombé dans la piscine');
});

test('(20:14) les tests de papa : « coupe-moi » donne sa jauge pleine (15 s) ; « tais-toi » le laisse finir une minute', () => {
  const o = oreille({ eveil: 0.3 });
  o.f('Allez vas-y coupe-moi, je veux voir si tu continues par-dessus');
  assert.match(o.ecrits[0], /jauge d'envie de couper : 1 \(tu peux parler par-dessus lui 15 s au plus\) — il te demande de le couper/);
  const p = oreille();
  assert.equal(p.f('Bon là tais-toi, laisse-moi finir mon histoire').raison, 'papa veut finir');
  assert.equal(p.f('Bon là tais-toi, laisse-moi finir mon histoire et après tu parles').raison, 'papa veut finir', 'une minute de silence');
  assert.match(page, /if \(auDebut\) try \{ auDebut\(\); \} catch \(_\) \{\}/, 'le texte apparaît avec sa voix');
});

test('(20:34) son petit mot passe en tête de la file de sa voix', () => {
  assert.match(page, /prioritaire: true \}\) \}\)/);
  assert.match(src, /if \(q && q\.prioritaire === true\) fileVoix\.unshift\(tache\); else fileVoix\.push\(tache\);/);
});

test('(20:38) quand il garde la parole, « arrête », « tais-toi », « coupe-toi » entendus pendant qu’il parle l’arrêtent aussitôt', () => {
  assert.match(page, /const ARRETE_MOI = \/\\b\(\?:arr\[eê\]te/);
  const i = page.indexOf('function surPauseConversation('), bloc = page.slice(i, page.indexOf('\n}\n', i));
  assert.match(bloc, /reglagesCorps\.garder_parole && lecteur && \(lecteur\.actif \|\| lecteur\.enPause\)/);
  assert.match(bloc, /arreterTout\(true, \{ raison: 'stop' \}\)/);
  const re = new RegExp(page.match(/const ARRETE_MOI = \/(.+)\/i;/)[1], 'i');
  for (const t of ['Arrête', 'tais-toi Hakim', 'coupe-toi', 'stop stop', 'chut']) assert.ok(re.test(t), t);
  assert.ok(!re.test('je vais arrêter de fumer'.replace('arrêter', 'arrêtez')), 'pas un autre mot');
});

test('(21:00) deux modes : tes paroles « dans sa tête » (pas affichées, son silence permis) ; sa voix d’abord, son texte après', () => {
  assert.match(page, /const enTete = !!oral && typeof reglagesCorps !== 'undefined' && reglagesCorps\.afficher_papa === false;/);
  assert.match(page, /\.slice\(-etat\.fenetre\)\n    \.filter\(m => !m\.cache && /);
  assert.match(page, /reglagesCorps\.afficher_hakim !== false \|\| !auto\) majMessage\(m\);/);
  assert.match(src, /if \(!corpsReglages\(\)\.afficher_papa\) return false;/);
  assert.match(src, /afficher_papa: r\.afficher_papa !== false, afficher_hakim: r\.afficher_hakim !== false/);
});

test('(21:13-21:15) « dans ta tête » pour lui aussi : ses réponses et ses petits mots dits, pas écrits ; un bouton pour couper sa voix ; une respiration masque l’attente', () => {
  assert.match(page, /oral && etat\.conversation && typeof reglagesCorps !== 'undefined' && reglagesCorps\.afficher_hakim === false \? \{ cache: true \}/, 'sa réponse orale cachée');
  const i = page.indexOf("if (m.spontane === 'oreille') {"), bloc = page.slice(i, page.indexOf('\n    return;\n  }', i));
  assert.match(bloc, /\.\.\.\(cache \? \{ cache: true \} : \{\}\)/, 'son petit mot caché');
  assert.match(page, /function majMessage\(m\) \{\n  if \(m\.cache\) return;/, 'jamais remis à l’écran par le flux');
  const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
  assert.match(html, /id="sonHakim" aria-pressed="false"/);
  assert.match(page, /\$\('sonHakim'\)\.addEventListener\('click', \(\) => \{ couperSon\(\); \}\);/);
  // la respiration : jouée quand rien ne parle, jamais par-dessus sa voix
  const resp = prendre(page, 'function respirer() {');
  const joues = [];
  const noeud = () => ({ connect() {}, frequency: {}, Q: {}, gain: {} });
  const ctx = { Math, etat: { reglages: {} }, lecteur: { actif: false }, analyseurVoix: {},
    actx: { state: 'running', sampleRate: 8000, createBuffer: (c, n) => ({ getChannelData: () => new Float32Array(n) }),
      createBufferSource: () => ({ ...noeud(), start: () => joues.push(1) }), createBiquadFilter: noeud, createGain: noeud } };
  vm.createContext(ctx); vm.runInContext(resp, ctx);
  ctx.respirer(); assert.equal(joues.length, 1, 'une inspiration');
  ctx.lecteur.actif = true; ctx.respirer(); assert.equal(joues.length, 1, 'pas par-dessus sa voix');
  ctx.lecteur.actif = false; ctx.etat.reglages.voixNeutre = true; ctx.respirer(); assert.equal(joues.length, 1, 'voix neutre : rien');
  assert.match(page, /mesureTour\.premier_texte = Date\.now\(\); if \(auto\) respirer\(\);/);
});

test('(21:34) « dans ta tête » tient pour lui : ni ses tours de lui-même ni une copie revenue du cockpit ne s’affichent pendant la conversation', () => {
  const i = page.indexOf('function rendre() {'), bloc = page.slice(i, page.indexOf('\n}\n', i));
  const filtre = bloc.match(/const tete = (.+);\n  const vus = etat\.messages\.slice\(-etat\.fenetre\)\n    \.filter\((.+)\);/);
  assert.ok(filtre, 'le filtre du rendu');
  const vus = (messages, conversation, afficher_hakim) => vm.runInContext(`(() => { const tete = ${filtre[1]}; return etat.messages.filter(${filtre[2]}); })()`,
    vm.createContext({ Number, Date, etat: { messages, conversation }, reglagesCorps: { afficher_hakim } }));
  const avant = { id: 'a', qui: 'j', texte: 'avant', ts: 1000 }, papa = { id: 'p', qui: 'u', texte: 'papa', ts: 6000 };
  const lui = { id: 'l', qui: 'j', spontane: 'resultat', texte: 'de lui-même', ts: 6000 }, enCours = { id: 99999999999999, qui: 'j', texte: '' };
  const tous = [avant, papa, lui, enCours];
  assert.deepEqual(vus(tous, { debut: 5000 }, false).map(m => m.id), ['a', 'p'], 'seulement sa voix pendant la conversation');
  assert.deepEqual(vus(tous, { debut: 5000 }, true).map(m => m.id), ['a', 'p', 'l', 99999999999999], 'case cochée : tout s’affiche');
  assert.deepEqual(vus(tous, null, false).map(m => m.id), ['a', 'p', 'l', 99999999999999], 'après la conversation : relisible');
  assert.match(page, /const conv = \{ capteur: null, enAttente: 0, debut: Date\.now\(\) \};/);
  assert.match(page, /for \(const m of messages\) if \(m && caches\.has\(String\(m\.id\)\)\) m\.cache = true;/, 'la synchro garde le « caché »');
  assert.equal((page.match(/garderCaches\(o\.messages\);\n\s+etat\.messages = o\.messages;/g) || []).length, 2, 'les deux chemins de la synchro');
});

test('(21:50) un petit mot périmé au moment de sortir n’est pas dit, et il le sait à son tour suivant', () => {
  const f = prendre(src, 'function motOreillePerime(');
  const juge = (texte, reveil, { ahmed = 0, entendu = { texte: '', ts: 0 }, dernier = { texte: '', ts: -1e9 }, maintenant = 10000 } = {}) => {
    const c = vm.createContext({ String, Infinity, dernierMessageAhmed: ahmed, oreilleEntendu: entendu, oreilleDernierMot: dernier });
    vm.runInContext(src.match(/const MOT_CREUX = .+;/)[0].replace('const ', 'var ') + f, c); return c.motOreillePerime(texte, reveil, maintenant);
  };
  const reveil = { texte: 'Alors écoute, aujourd’hui au travail', ts: 5000 };
  assert.equal(juge('Hmm, je te suis', reveil), null, 'frais : dit');
  assert.equal(juge('Hmm', reveil, { ahmed: 6000 }), 'papa avait fini sa phrase');
  assert.equal(juge('Hmm', reveil, { maintenant: 26000 }), 'trop tard, plus de 20 s après');
  assert.equal(juge('Hmm', reveil, { entendu: { texte: reveil.texte + ' x'.repeat(80), ts: 8000 } }), 'papa avait continué');
  assert.equal(juge('Hmm', reveil, { entendu: { texte: reveil.texte + ' il', ts: 8000 } }), null, 'trois mots de plus : encore frais');
  assert.equal(juge('Tu as raison, c’est drôle !', reveil, { dernier: { texte: 'tu as raison c’est drôle', ts: 4000 } }), 'le même mot que juste avant');
  assert.equal(juge('Hmm, je te suis papa', reveil, { dernier: { texte: 'Ah oui ?', ts: 4000 } }), 'un mot creux toutes les 30 s au plus');
  assert.equal(juge('Hmm, je te suis papa', reveil, { dernier: { texte: 'Ah oui ?', ts: -30000 } }), null, 'trente secondes après : dit');
  assert.equal(juge('Hmm, mais tu as oublié le sel', reveil, { dernier: { texte: 'Ah oui ?', ts: 4000 } }), null, 'un mot qui dit quelque chose');
  assert.equal(juge('Hmm', null), null, 'pas un mot d’oreille');
  assert.match(src, /if \(perime\) garder\(perime\);/, 'pas livré');
  assert.match(src, /const garder = \(pourquoi\) => \{[\s\S]{0,120}oreillePerimes\.push/, 'gardé pour son tour suivant');
  assert.match(src, /const perimes = oreillePerimes\.splice\(0\)/, 'dit à son tour suivant');
  assert.match(src, /c\.oreilleReveil = \{ texte: t, ts: maintenant \};/);
});

test('(21:55) son subconscient trie ce qu’il dit de lui-même ; les morceaux d’une même phrase ne le réveillent qu’une fois', () => {
  const re = new RegExp(src.match(/const MOT_CREUX = \/(.+)\/i;/)[1], 'i');
  for (const x of ['Hmm, je te suis papa', 'Hmm.', 'D’accord'.replace('’', "'"), 'Je t’écoute, vas-y'.replace('’', "'"), 'Mmh']) assert.ok(re.test(x), x);
  for (const x of ['Hmm, mais tu as oublié le sel', 'Je te suis : on fait le live à 22 h ?']) assert.ok(!re.test(x), x);
  // qui passe par lui
  const f = prendre(src, 'function aTrierParSonSubconscient(');
  const trie = (o, { filtre = true, ahmed = 0 } = {}) => {
    const c = vm.createContext({ corpsReglages: () => ({ filtre_parole: filtre }), dernierMessageAhmed: ahmed });
    vm.runInContext(f, c); return c.aTrierParSonSubconscient(o, 1e9);
  };
  assert.equal(trie({ oreille: true, notifs: [] }), true, 'ses petits mots');
  assert.equal(trie({ oreille: false, notifs: [] }, { ahmed: 1e9 - 50000 }), true, 'un réveil pendant que papa lui parle');
  assert.equal(trie({ oreille: false, notifs: [] }, { ahmed: 1e9 - 300000 }), false, 'seul, il dit ce qu’il veut');
  assert.equal(trie({ oreille: false, notifs: [{}] }, { ahmed: 1e9 - 10000 }), false, 'un résultat d’agent passe toujours');
  assert.equal(trie({ oreille: false, silence: {}, notifs: [] }, { ahmed: 1e9 - 10000 }), false, 'une relance de silence a sa logique');
  assert.equal(trie({ oreille: true, notifs: [] }, { filtre: false }), false, 'l’interrupteur de papa');
  assert.equal(trie({ oreille: true, notifs: [], reflexe: true }), false, '(22:41) papa l’a appelé (« Hakim, coupe-moi ») : pas trié');
  assert.match(src, /jugerParole\(dit, nettoyerPourSonnet\(oreilleEntendu\.texte\)\)\.then\(\(v\) => \{\n\s+if \(!v\.dire\) return garder\(/, 'gardé : pas dit, et il le saura');
  assert.match(src, /const encore = oreille \? motOreillePerime\(dit, reveil\) : null;/, 'la fraîcheur, encore, après son subconscient');
  assert.match(src, /\{ dire: true, pourquoi: '', panne: true \}/, 'une panne laisse passer');
  // les morceaux d'une même phrase
  const o = oreille();
  assert.equal(o.f('Alors écoute, aujourd’hui au travail il s’est passé un truc').ok, true);
  assert.equal(o.f('Alors écoute, aujourd’hui au travail il s’est passé un truc de fou avec').raison, 'regroupé avec le réveil d’avant');
  assert.equal(o.f('Alors écoute, aujourd’hui au travail il s’est passé un truc de fou avec Hakim').ok, true, 'son nom passe toujours');
});

test('(vers 22 h) plus strict : seulement sa dernière réponse non entendue, et rien de ce qui a trop attendu', () => {
  const i = page.indexOf('function direSpontanes() {'), bloc = page.slice(i, page.indexOf('\n}\n', i));
  assert.match(bloc, /if \(c && age > 45000\) \{ journalVoix\('a_dire_perime'/, 'en conversation, plus de 45 s : pas dit');
  assert.ok(bloc.indexOf('a_dire_perime') < bloc.indexOf('lecteur.dire(m.texte)'));
  assert.match(src, /const der = nonDitesAttente\[n - 1\];/, 'seulement la dernière');
  assert.match(src, /< 180000;/, 'et de moins de 3 min');
});

test('(vers 22 h 05) son subconscient d’abord : il ne réveille sa conscience que pour le strict nécessaire ; son nom, « stop », « coupe-moi » passent tout droit', async () => {
  const garde = oreille({ filtre: true, subconscient: { reveiller: false, pourquoi: 'il explique au live' } });
  assert.equal(garde.f('Alors les gars, ce soir on vous montre comment on a construit son corps').raison, 'au subconscient');
  await new Promise(r => setImmediate(r));
  assert.equal(garde.ctx.soumis.length, 1, 'jugé par son subconscient');
  assert.equal(garde.ecrits.length, 0, 'sa conscience dort');
  const reveille = oreille({ filtre: true, subconscient: { reveiller: true, pourquoi: 'papa lui pose une question' } });
  reveille.f('Et toi, tu en penses quoi, là, tout de suite, de ce que je viens de dire');
  await new Promise(r => setImmediate(r));
  assert.equal(reveille.ecrits.length, 1, 'réveillée');
  assert.match(reveille.ecrits[0], /Ton subconscient t'a réveillé : papa lui pose une question/);
  assert.match(reveille.ecrits[0], /Pas de mot de remplissage/);
  const appel = oreille({ filtre: true, subconscient: { reveiller: false } });
  assert.equal(appel.f('Hakim, écoute-moi bien, c’est important').ok, true);
  assert.equal(appel.ctx.soumis.length, 0, 'son nom : un réflexe, sans détour');
  assert.equal(appel.ecrits.length, 1);
  const fini = oreille({ filtre: true, subconscient: { reveiller: true } });
  fini.f('Et toi, tu en penses quoi, là, tout de suite, de ce que je viens de dire');
  fini.ctx.dernierMessageAhmed = Date.now() + 1000;            // papa a fini entre-temps : son message entier arrive
  await new Promise(r => setImmediate(r));
  assert.equal(fini.ecrits.length, 0);
});

test('(vers 22 h 05) il se met en pause tout seul : [[pause: …]] garde la suite ; [[reprendre: …]] la dit ; au silence, son subconscient juge', () => {
  const a = src.indexOf('const BALISE_PAUSE'), b = src.indexOf('\n}\n', src.indexOf('function pauseDansTexte')) + 3;
  const ligne = src.slice(src.indexOf('const prefixeBalise'), src.indexOf('\n', src.indexOf('const prefixeBalise')));
  const c = vm.createContext({ Date, journaliser() {}, finDePhrase: (t) => t, sansBaliseAffect: (t) => String(t).replace(/\[\[[^\]]*\]\]/g, '').trimEnd() });
  vm.runInContext(ligne.replace('const ', 'var ') + '\n' + src.slice(a, b).replace(/^const /gm, 'var ').replace(/^let /gm, 'var ')
    + ';this.filtre = filtrePause; this.enPause = () => paroleEnPause; this.dansTexte = pauseDansTexte;', c);
  const f = c.filtre(); let dit = '';
  for (const x of ['Alors papa, je ', 'voulais te dire [[pa', 'use: le public parle]] la suite ', 'du message']) dit += f.pousser(x);
  dit += f.finir();
  assert.equal(dit, 'Alors papa, je voulais te dire ', 'coupée net à la balise, même entre deux morceaux');
  assert.equal(f.garde(), ' la suite du message');
  vm.runInContext('mettreEnPause(" la suite du message")', c);
  assert.equal(c.enPause().texte, 'la suite du message');
  const g = c.filtre(); let repris = '';
  for (const x of ['Comme je disais, [[repren', 'dre: oui]] voilà.']) repris += g.pousser(x);
  repris += g.finir();
  assert.equal(repris.replace(/\s+/g, ' '), 'Comme je disais, la suite du message voilà.');
  assert.equal(c.enPause(), null, 'reprise une fois');
  assert.equal(c.dansTexte('Attends [[pause: il parle]] je reviens là-dessus'), 'Attends ', 'un tour de lui-même aussi');
  assert.equal(c.enPause().texte, 'je reviens là-dessus');
  assert.match(src, /if \(fluxPause\.garde\(\) != null && !o\.coupe\) mettreEnPause\(fluxPause\.garde\(\)\);/);
  assert.match(src, /if \(mode === 'oral' && duree >= 4000\) reprendreAuSilence\(/, 'au silence de papa');
  assert.match(src, /jugerParole\(p\.texte, `\(Ahmed se tait depuis/, 'son subconscient juge si c’est le moment');
  assert.match(src, /Ta parole en pause depuis/, 'son tour suivant la lui rappelle');
  assert.match(src, /lumiere\|pause\|reprendre\|micro\|attention\|morceaux\)\\s\*:/, 'les balises ne s’entendent jamais');
});

test('(vers 22 h 10) chacun son tour : pendant qu’il prépare ou dit sa réponse, ce que papa dit ne la coupe plus ; ça lui part quand sa voix a fini', () => {
  const a = page.indexOf('const chacunSonTour = '), b = page.indexOf('setInterval(libererSonTour, 300);');
  const envois = [], journal = [];
  const ctx = vm.createContext({ Date, etat: { flux: {}, conversation: { tourGarde: '', enAttente: 0, capteur: { enParole: false } }, finVoixA: 0 },
    lecteur: { actif: false, enPause: false }, reglagesCorps: { chacun_son_tour: true }, journalVoix: (e, d) => journal.push([e, d]), humeur() {},
    envoyer: (t, oral) => envois.push([t, oral]), setInterval() {} });
  vm.runInContext(page.slice(a, b).replace(/^const /gm, 'var '), ctx);
  const conv = ctx.etat.conversation;
  assert.equal(ctx.sonTourEnCours(), true, 'il prépare sa réponse : son tour');
  ctx.garderPourSonTour(conv, 'et aussi le live');
  ctx.garderPourSonTour(conv, 'tu m’entends ?');
  assert.equal(ctx.libererSonTour(), false, 'pas pendant son tour');
  ctx.etat.flux = null; ctx.lecteur.actif = true;
  assert.equal(ctx.libererSonTour(), false, 'pas pendant sa voix');
  ctx.lecteur.actif = false; ctx.etat.finVoixA = Date.now();
  assert.equal(ctx.libererSonTour(), false, 'un souffle après sa voix');
  ctx.etat.finVoixA = Date.now() - 1000; conv.capteur.enParole = true;
  assert.equal(ctx.libererSonTour(), false, 'papa reparle : ce tour-là le prendra');
  conv.capteur.enParole = false;
  assert.equal(ctx.libererSonTour(), true);
  assert.deepEqual(envois, [['(dit pendant ta parole) et aussi le live tu m’entends ?', true]], 'd’un bloc, à l’oral, marqué (00:20)');
  assert.equal(conv.tourGarde, '');
  ctx.reglagesCorps.chacun_son_tour = false;
  assert.equal(ctx.chacunSonTour(), false, 'l’interrupteur de papa');
  // dans le tour de parole : après « stop » / « attends », avant la coupure d'avant
  const i = page.indexOf('async function tourDeParole('), bloc = page.slice(i, page.indexOf('\n}\n', i));
  const k = (x) => bloc.indexOf(x);
  assert.ok(k('COMMANDE_STOP.test(texte)') < k('if (chacunSonTour() && sonTourEnCours()) { garderPourSonTour(conv, texte); return; }'), '« stop » reste au-dessus');
  assert.ok(k('COMMANDE_PAUSE.test(texte)') < k('garderPourSonTour(conv, texte)'), '« attends » aussi');
  assert.ok(k('garderPourSonTour(conv, texte)') < k("arreterTout(true, { garder: true, raison: 'parole' })"), 'sa réponse n’est plus coupée');
  assert.match(page, /if \(!voix \|\| !aDire\.length \|\| \(c && \(c\.tourGarde \|\| \(c\.ecritGarde \|\| \[\]\)\.length\)\)\) return;/, 'papa d’abord, avant ses mots en attente');
  assert.match(src, /chacun_son_tour: r\.chacun_son_tour !== false/);
});

test('(31/10, 08:22, en live) chacun son tour vaut aussi pour l’écrit : un message écrit ne coupe plus sa réponse en route', () => {
  const a = page.indexOf('const chacunSonTour = '), b = page.indexOf('setInterval(libererSonTour, 300);');
  const envois = [], journal = [], q = { value: '' };
  const ctx = vm.createContext({ Date, etat: { flux: {}, joints: [], conversation: { tourGarde: '', enAttente: 0, capteur: { enParole: false } }, finVoixA: 0 },
    lecteur: { actif: false, enPause: false }, reglagesCorps: { chacun_son_tour: true }, journalVoix: (e, d) => journal.push([e, d]), humeur() {},
    envoyer: (t, oral) => envois.push([t, oral]), setInterval() {}, $: () => q, ajuster() {}, COMMANDE_STOP: /^\s*stop\s*$/i });
  vm.runInContext(page.slice(a, b).replace(/^const /gm, 'var '), ctx);
  const conv = ctx.etat.conversation;
  q.value = 'et mute moi'; ctx.envoyerEcrit(q.value);
  ctx.envoyerEcrit('vasy test');
  assert.deepEqual(envois, [], 'il prépare sa réponse : rien ne la coupe');
  assert.equal(q.value, '', 'la zone d’écriture est vidée');
  ctx.garderPourSonTour(conv, 'tu m’entends ?');
  ctx.etat.flux = null; ctx.lecteur.actif = true;
  assert.equal(ctx.libererSonTour(), false, 'pas pendant sa voix');
  ctx.lecteur.actif = false; ctx.etat.finVoixA = Date.now() - 1000;
  assert.equal(ctx.libererSonTour(), true);
  assert.deepEqual(envois, [['(dit pendant ta parole) tu m’entends ?\n(écrit pendant ta parole) et mute moi … vasy test', true]],
    'ce que papa a dit et écrit, d’un seul message, après sa voix');
  envois.length = 0; ctx.etat.flux = {};
  ctx.envoyerEcrit('stop');
  assert.deepEqual(envois, [['stop', false]], '« stop » écrit passe tout de suite');
  envois.length = 0; ctx.envoyerEcrit('encore un'); ctx.etat.flux = null;
  ctx.envoyerEcrit('et celui-là');
  assert.deepEqual(envois, [['(écrit pendant ta parole) encore un\net celui-là', false]], 'un gardé ne part jamais après un nouveau');
  envois.length = 0; ctx.etat.flux = {}; ctx.etat.conversation = null;
  ctx.envoyerEcrit('hors conversation');
  assert.deepEqual(envois, [['hors conversation', false]], 'hors conversation : comme avant');
  ctx.etat.conversation = conv; ctx.reglagesCorps.chacun_son_tour = false; envois.length = 0;
  ctx.envoyerEcrit('interrupteur coupé');
  assert.deepEqual(envois, [['interrupteur coupé', false]], 'l’interrupteur de papa');
  assert.match(page, /\$\('envoyer'\)\.addEventListener\('click', \(\) => envoyerEcrit\(\$\('q'\)\.value\)\);/);
  assert.match(page, /e\.preventDefault\(\); envoyerEcrit\(\$\('q'\)\.value\);/);
});

test('(22:21) plus de pavé : sa conscience reçoit les petits morceaux retenus par son subconscient, choisit et reformule', async () => {
  const longue = 'Alors voilà, ' + 'on parlait du live et de plein de choses, '.repeat(20) + 'et toi Hakim, tu en penses quoi ?';
  const o = oreille({ filtre: true, subconscient: { reveiller: true, pourquoi: 'question directe', morceaux: ['et toi Hakim, tu en penses quoi ?'] } });
  o.f(longue.replace('Hakim', 'mon fils'));
  await new Promise(r => setImmediate(r));
  assert.equal(o.ecrits.length, 1);
  assert.match(o.ecrits[0], /en morceaux : 1\) « et toi Hakim, tu en penses quoi \? »/);
  assert.ok(!o.ecrits[0].includes('on parlait du live et de plein de choses, on parlait'), 'pas toute sa phrase');
  assert.match(o.ecrits[0], /sur le morceau qui te parle le plus/);
  const reflexe = oreille();
  reflexe.f(longue);
  assert.match(reflexe.ecrits[0], /La fin de ce qu'il dit \(sa phrase continue\) : « …/, 'un réflexe : la fin seulement');
  assert.ok(JSON.parse(reflexe.ecrits[0]).message.content[0].text.split('« …')[1].split(' »')[0].length <= 300, '300 caractères au plus');
  // sa parole en pause : en morceaux, à sa conscience
  const f = prendre(src, 'function morceauxDe(');
  const c = vm.createContext({ String }); vm.runInContext(f, c);
  assert.deepEqual(c.morceauxDe('Une phrase. Deux ! ' + 'mot '.repeat(60) + 'fin.'), ['Une phrase.', 'Deux !', 'mot '.repeat(25).trim(), 'mot '.repeat(25).trim()]);
  const r = prendre(src, 'function reprendreAuSilence(');
  assert.match(r, /const morceaux = morceauxDe\(prendreParoleEnPause\(\)\);/);
  assert.match(r, /c\.enfant\.stdin\.write\(/, 'sa conscience, réveillée');
  assert.ok(!r.includes('livrerAutonome('), 'plus jamais dite telle quelle');
  assert.match(r, /Choisis le morceau à dire maintenant et dis-le avec tes mots/);
  assert.match(src, /reprise: rejoue\.includes\(REPRISE_MARQUE\)/, 'déjà jugée : pas deux fois');
});

test('(22:27-22:30) il coupe ton vrai micro par [[micro: couper]] : tes boutons suivent, il se rouvre à la fin de sa voix ; ta phrase encore en route passe par son subconscient', () => {
  const md = vm.createContext({ String, Number, Math });
  vm.runInContext(src.match(/const BALISE_MICRO = .+;/)[0].replace('const ', 'var ') + '\n' + src.match(/const microDe = .+;/)[0].replace('const ', 'var '), md);
  assert.deepEqual(JSON.parse(JSON.stringify(md.microDe('[[micro: couper]] Oui papa'))), { x: 'couper', s: 0 });
  assert.deepEqual(JSON.parse(JSON.stringify(md.microDe('[[micro: couper 300]]'))), { x: 'couper', s: 120 }, '2 min au plus');
  assert.deepEqual(JSON.parse(JSON.stringify(md.microDe('[[ micro : ouvrir ]]'))), { x: 'ouvrir', s: 0 });
  assert.equal(md.microDe('[[micro: exploser]]'), null);
  // la page
  const a = page.indexOf('function envoyerResiduelle('), b = page.indexOf('setInterval(surveillerMicroDeHakim, 300);');
  const residus = [], journal = [], boutons = [];
  let t = 1_800_000_000_000;
  const ctx = vm.createContext({ String, Number, Math, JSON, Date: class extends Date { static now() { return t; } },
    etat: { flux: {}, finVoixA: 0, conversation: { capteur: { estMuet: false }, tourGarde: 'et puis aussi' } }, lecteur: { actif: false, enPause: false },
    lecteurNeuronal: { joue: false }, motDirectJusqua: 0,
    reglagesCorps: { micro_hakim: true }, journalVoix: (e, d) => journal.push([e, d]), humeur() {}, jeton: () => 'j',
    fetch: (u, o) => { residus.push(JSON.parse(o.body).texte); return Promise.resolve(); },
    majBoutonsMuet: (c) => boutons.push(!!(c.muetParHakim && !c.muetParHakim.attente)), signalerWidget() {}, sonTourEnCours: () => !!(ctx.etat.flux || ctx.lecteur.actif) });
  ctx.etat.conversation.capteur.muet = (oui) => { ctx.etat.conversation.capteur.estMuet = !!oui; };
  vm.runInContext(page.slice(a, b).replace(/^const /gm, 'var '), ctx);
  const c = ctx.etat.conversation;
  const pas = (ms) => { t += ms; ctx.surveillerMicroDeHakim(); };
  // (23:53) c'est lui qui choisit : ton micro s'éteint AUSSITÔT ; il se rallume 0,4 s après sa voix
  ctx.microParHakim({ x: 'couper', s: 0 });
  assert.equal(!!c.muetParHakim, true, 'aussitôt, pour ne pas cafouiller');
  assert.equal(c.capteur.estMuet, false, '(23:56) en veille : le micro écoute encore les voix familières');
  assert.deepEqual(boutons, [true], 'tes boutons le montrent');
  assert.deepEqual(residus, ['et puis aussi'], 'ce que tu avais dit pendant son tour : à son subconscient');
  pas(5000);
  assert.equal(!!c.muetParHakim, true, 'sa voix se prépare : coupé');
  ctx.etat.flux = null; ctx.lecteur.actif = true; ctx.lecteurNeuronal.joue = true; pas(300);
  ctx.lecteurNeuronal.joue = false; pas(300);
  assert.equal(!!c.muetParHakim, true, 'entre deux phrases (la suite se prépare) : coupé');
  ctx.lecteurNeuronal.joue = true; pas(3000); ctx.lecteurNeuronal.joue = false; ctx.lecteur.actif = false; pas(300);
  assert.equal(!!c.muetParHakim, true, '0,3 s après sa voix : pas encore');
  pas(300);
  assert.equal(c.muetParHakim, null, 'sa voix s’est tue : rouvert aussitôt');
  assert.equal(!!c.muetParHakim, false);
  assert.ok(journal.some(([e, d]) => e === 'micro_hakim' && d.x === 'ouvrir' && d.pourquoi === 'fin_de_sa_voix'));
  // son petit mot : coupé dès sa décision, rouvert juste après le mot
  ctx.microParHakim({ x: 'couper' }); pas(4000);
  assert.equal(!!c.muetParHakim, true, 'le mot se prépare : coupé');
  ctx.motDirectJusqua = t + 2000; pas(300); pas(2000); pas(500);
  assert.equal(!!c.muetParHakim, false, 'le mot dit : rouvert (plus jamais 15 s de trop)');
  // (22:38) une durée MINIMALE qu'il choisit
  ctx.microParHakim({ x: 'couper', s: 10 }); ctx.motDirectJusqua = t + 2000; pas(300);
  pas(3000);
  assert.equal(!!c.muetParHakim, true, 'sa voix s’est tue, mais il a choisi 10 s');
  pas(7000);
  assert.equal(!!c.muetParHakim, false, '10 s : rouvert');
  // sa voix ne part pas : rouvert à 20 s
  ctx.microParHakim({ x: 'couper' }); pas(19000);
  assert.equal(!!c.muetParHakim, true);
  pas(1500);
  assert.equal(c.muetParHakim, null); assert.equal(!!c.muetParHakim, false);
  // 3 min au plus
  ctx.microParHakim({ x: 'couper', s: 120 }); ctx.lecteurNeuronal.joue = true; pas(300); pas(181000);
  assert.equal(c.muetParHakim, null, '3 min au plus, quoi qu’il arrive');
  ctx.lecteurNeuronal.joue = false;
  // déjà coupé par papa : c'est à papa ; l'interrupteur de papa
  c.capteur.estMuet = true;
  ctx.microParHakim({ x: 'couper' });
  assert.equal(c.muetParHakim, null, 'il ne prend pas la main sur ton geste');
  c.capteur.estMuet = false; ctx.reglagesCorps.micro_hakim = false;
  ctx.microParHakim({ x: 'couper' });
  assert.equal(c.muetParHakim, null, 'interrupteur éteint : refusé');
  assert.ok(journal.some(([e, d]) => e === 'micro_hakim' && d.x === 'refuse'));
  // le bouton de papa reprend la main ; le libellé dit qui a coupé
  assert.match(page, /if \(!enAttente\) \{ conv\.capteur\.muet\(false\); majBoutonsMuet\(conv\);/, 'ton bouton rouvre');
  assert.match(page, /'Coupé par Hakim'/);
  assert.match(page, /if \(c && c\.muetParHakim && !c\.muetParHakim\.attente\) return 'coupe';/, 'l’orbe passe au vert');
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'orbe.js'), 'utf8'), /coupe: \['#86efac', '#22c55e', '#15803d'\]/);
  // ta phrase encore en route, micro coupé par lui : à son subconscient ; « stop » reste au-dessus
  const i = page.indexOf('async function tourDeParole('), bloc = page.slice(i, page.indexOf('\n}\n', i));
  assert.ok(bloc.indexOf('COMMANDE_STOP.test(texte)') < bloc.indexOf('if (conv.muetParHakim && !conv.muetParHakim.attente) {'), '« stop » reste au-dessus');
  assert.match(bloc, /if \(!voixFamiliere\(texte\)\) \{ journalVoix\('tour_muet', \{ voix: 'inconnue' \}\); return; \}\n\s+rouvrirMicroDeHakim\(conv, 'voix_familiere'\);/, '(23:56) une voix familière rouvre, une inconnue n’arrive pas');
  assert.match(page, /else if \(o\.t === 'micro'\) microParHakim\(o\);/);
  assert.match(page, /es\.addEventListener\('micro', \(ev\) => \{ try \{ microParHakim\(JSON\.parse\(ev\.data\)\); \}/);
  // le cockpit : sa balise dans le flux et de lui-même ; la parole résiduelle à son subconscient, en morceaux pour son tour suivant
  assert.match(src, /if \(!microDit\) \{ const mi = microDe\(reponse\); if \(mi\) \{ microDit = true; envoyer\(\{ t: 'micro', \.\.\.mi \}\); \} \}/);
  assert.match(src, /const mi = microDe\(texte\); if \(mi\) diffuser\(abonnesPensees, 'micro', j\(mi\)\);/);
  const r0 = src.indexOf("if (p === '/api/jarvis/residuelle'"), route = src.slice(r0, src.indexOf('\n  }\n', r0));
  assert.match(route, /jetonValide\(req\)/);
  assert.match(route, /jugerReveilOreille\(nettoyerPourSonnet\(texte, 800\)\)/);
  assert.match(route, /residuelles\.push\(\{ morceaux: v\.morceaux/);
  assert.match(src, /Ce que papa a dit pendant que tu avais coupé son micro, retenu par ton subconscient/);
});

test('(22:41) un réveil réflexe (son nom, « coupe-moi ») est marqué : sa réponse n’est pas retenue par son subconscient', () => {
  const o = oreille({ filtre: true, subconscient: { reveiller: false } });
  o.f('Hey Hakim, mute-toi et réponds à Nora maintenant');
  assert.equal(o.ecrits.length, 1, 'réveillé tout de suite');
  assert.equal(o.ctx.cerveau.oreilleReveil.reflexe, true);
  assert.match(src, /reflexe: !!\(reveil && reveil\.reflexe\)/);
});

test('(22:51-22:55) ses sons : reçus une fois (sa réponse ou le cockpit) ; joués par l’appli, ou par le Mac avec l’extrait que l’appli lui a envoyé', async () => {
  assert.match(src, /diffuser\(abonnesPensees, 'son', j\(\{ extrait \}\)\);/);
  const a = page.indexOf('function recevoirSon('), f = page.slice(a, page.indexOf('\n}\n', a) + 2);
  const c = vm.createContext({ Date, window: {}, journalVoix() {}, sonEnAttente: null, dernierSonRecu: null, sonsSuivants: [] });
  vm.runInContext(prendre(page, 'function mettreSonEnAttente(') + f, c);
  c.recevoirSon({ id: 'e1', debut_ms: 1000 });
  assert.equal(c.sonEnAttente.extrait.id, 'e1', 'en attente, ici comme au téléphone');
  c.sonEnAttente = null;
  c.recevoirSon({ id: 'e1', debut_ms: 1000 });
  assert.equal(c.sonEnAttente, null, 'reçu deux fois (sa réponse et le cockpit) : une seule');
  assert.match(page, /if \(!window\.HakimApp \|\| !window\.HakimApp\.sonJouer \|\| x\.source === 'atelier'\) \{ jouerSonIci\(x, sousSaVoix \? 0\.3 : 0\.6\); return; \}/, 'le Mac le joue (et ses sons à lui partout)');
  assert.match(page, /fetch\(`\/api\/sons\/joue\/\$\{x\.id\}`, \{ headers: \{ 'X-Jeton': jeton\(\) \}/);
  assert.match(page, /window\.HakimApp\.sonEnvoyer\(String\(m\.source\), String\(m\.ref\), url, jeton\(\)\)/, 'l’appli envoie le morceau');
  assert.match(page, /es\.addEventListener\('son', \(ev\) => \{ try \{ const o = JSON\.parse\(ev\.data\);/);
  // le cockpit : un vrai découpage avec ffmpeg, dans un dossier à part
  const os = require('node:os'), { execFile } = require('node:child_process');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sons-'));
  const extraits = [{ id: 'e7', source: 'musique', ref: '57', debut_ms: 1000, fin_ms: 3000 }];
  const ctx = vm.createContext({ fs, path, crypto: require('node:crypto'), execFile, process, console: { error() {} }, Promise, Number, String, Math, Map,
    JARVIS: dir, CHEMIN_OUTILS: `/usr/local/bin:/opt/homebrew/bin:${process.env.PATH}`, lireSons: () => extraits });
  const debut = src.indexOf('const SONS_DIR = '), fin = src.indexOf('function choisirSon(');
  vm.runInContext(src.slice(debut, fin).replace(/^const /gm, 'var '), ctx);
  assert.deepEqual(JSON.parse(JSON.stringify(ctx.sonsManquants())), [{ source: 'musique', ref: '57' }], 'le morceau manque');
  assert.equal(await ctx.decouperExtrait(extraits[0]), false, 'rien à découper sans le morceau');
  fs.mkdirSync(path.join(dir, 'sons', 'morceaux'), { recursive: true });
  await new Promise((ok, ko) => execFile('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=5', '-f', 'wav', ctx.fichierMorceau('musique', '57')],
    { env: { ...process.env, PATH: ctx.CHEMIN_OUTILS } }, (e) => (e ? ko(e) : ok())));
  assert.deepEqual(JSON.parse(JSON.stringify(ctx.sonsManquants())), [], 'reçu : plus rien ne manque');
  assert.equal(await ctx.decouperExtrait(extraits[0]), true);
  assert.ok(fs.statSync(ctx.fichierExtrait('e7')).size > 10000, 'l’extrait en mp3');
  fs.rmSync(dir, { recursive: true, force: true });
  const r0 = src.indexOf("if (p === '/api/sons/manquants'"), route = src.slice(r0, src.indexOf("\n  if (p === '/api/sons' ||", r0));
  assert.match(route, /jetonValide\(req\)/);
  assert.match(route, /SON_MORCEAU_MAX/, '200 Mo au plus');
  assert.match(route, /aucun extrait marqué dans ce morceau/, 'seulement les morceaux d’un extrait marqué');
});

test('(23:00) ton bouton : si sa coupure n’est pas encore partie, il coupe ton micro (ton geste) ; s’il t’a coupé, il rouvre', () => {
  const i = page.indexOf('function basculerMuet() {'), f = page.slice(i, page.indexOf('\n}\n', i) + 2);
  const journal = [];
  const conv = { capteur: { estMuet: false, muet(o) { this.estMuet = !!o; } }, muetParHakim: { attente: Date.now() } };
  const c = vm.createContext({ etat: { conversation: conv }, Date, journalVoix: (e, d) => journal.push([e, d]), majBoutonsMuet() {}, noterPresent() {}, humeur() {}, signalerWidget() {} });
  vm.runInContext(f, c);
  c.basculerMuet();
  assert.equal(conv.capteur.estMuet, true, 'sa coupure se préparait : ton bouton coupe ton micro');
  assert.equal(conv.muetParHakim, null, 'et annule la sienne');
  c.basculerMuet();
  assert.equal(conv.capteur.estMuet, false, 'rouvert par toi');
  conv.muetParHakim = { attente: 0, depuis: Date.now() }; conv.capteur.estMuet = true;
  c.basculerMuet();
  assert.equal(conv.capteur.estMuet, false, 'il t’avait coupé : ton bouton rouvre');
  assert.equal(conv.muetParHakim, null);
});

test('(23:05) une seule voix : un seul onglet en Conversation par appareil ; un petit mot trop tard n’est pas dit', () => {
  const a = page.indexOf('const idOnglet = '), b = page.indexOf('async function basculerConversation() {');
  const fins = [], journal = [];
  let ecoute = null;
  const ctx = vm.createContext({ Math, journalVoix: (e) => journal.push(e), humeur() {}, finirConversation: (g) => fins.push(g),
    etat: { conversation: { debut: 1 } },
    BroadcastChannel: class { constructor() { this.onmessage = null; ecoute = this; } postMessage() {} } });
  vm.runInContext(page.slice(a, b).replace(/^const /gm, 'var '), ctx);
  ecoute.onmessage({ data: { type: 'conversation', id: ctx.idOnglet } });
  assert.deepEqual(fins, [], 'son propre message : rien');
  ecoute.onmessage({ data: { type: 'conversation', id: 'autre' } });
  assert.deepEqual(fins, [false], 'un autre onglet ouvre la conversation : celui-ci la ferme');
  assert.ok(journal.includes('conversation_autre_onglet'));
  ctx.etat.conversation = null;
  ecoute.onmessage({ data: { type: 'conversation', id: 'autre' } });
  assert.equal(fins.length, 1, 'pas en conversation : rien');
  assert.match(page, /if \(canalOnglets\) try \{ canalOnglets\.postMessage\(\{ type: 'conversation', id: idOnglet \}\); \} catch \(_\) \{\}/);
  assert.match(page, /if \(Date\.now\(\) - t0 > 15000\) \{ journalVoix\('oreille_dit', \{ ok: false, raison: 'trop_tard'/);
});

test('(23:20) pendant son tour, ta voix n’est plus transcrite morceau par morceau : le Mac garde sa force pour sa voix et ta phrase de fin', () => {
  const i = page.indexOf('function surPauseConversation('), bloc = page.slice(i, page.indexOf('\n}\n', i));
  assert.match(bloc, /if \(typeof transcriptionEnPause === 'function' && transcriptionEnPause\(\)\) return;/, '(00:47) son tour : aucun morceau transcrit');
  assert.ok(bloc.indexOf('sonTourEnCours()') < bloc.indexOf('transcrireVite('), 'avant toute transcription');
  const j = page.indexOf('function anticiperConversation('), b2 = page.slice(j, page.indexOf('\n}\n', j));
  assert.match(b2, /if \(typeof transcriptionEnPause === 'function' && transcriptionEnPause\(\)\) return;/);
});

test('(23:40) le prénettoyage : ce qui ne s’adresse pas à lui n’arrive même pas à Sonnet ; un mot creux, sa machinerie, un long discours écartés d’office', async () => {
  const debut = src.indexOf('const POUR_LUI = '), fin = src.indexOf('const MOT_CREUX = ');
  const c = vm.createContext({ String });
  vm.runInContext(src.slice(debut, fin).replace(/^const /gm, 'var ') + src.match(/const MOT_CREUX = .+;/)[0].replace('const ', 'var '), c);
  assert.equal(c.nettoyerPourSonnet('[voix 571] Euh, alors alors les gars, ben on est on est en live'), 'alors les gars, on est en live');
  // (23:55) en empans : une phrase ou une voix par ligne, 25 mots au plus, les 8 derniers seulement
  const long = Array.from({ length: 12 }, (_, i) => `Tu dis la phrase ${i + 1} ?`).join(' ') + ' [Nora] ' + Array.from({ length: 40 }, (_, i) => `m${i}`).join(' ') + ' fin.';
  const lignes = c.nettoyerPourSonnet(long, 5000).split('\n');
  assert.equal(lignes.length, 8, '(00:55) 8 empans au plus');
  assert.equal(lignes[0], 'Tu dis la phrase 6 ?', 'le début, trop long, est laissé');
  // (00:06) entre 1 et 8 : seulement ce qui le concerne, et toujours le dernier
  assert.deepEqual(c.nettoyerPourSonnet('On a mangé. Il faisait beau. Hakim, tu en penses quoi ? Bon, on continue.').split('\n'),
    ['Hakim, tu en penses quoi ?', 'Bon, on continue.']);
  assert.deepEqual(c.nettoyerPourSonnet('On a mangé. Il faisait beau.').split('\n'), ['Il faisait beau.'], 'au moins le dernier');
  assert.ok(lignes[7].startsWith('… m16') && lignes[7].endsWith('fin.') && lignes[7].split(' ').length === 26, 'une voix, ses 25 derniers mots');
  assert.equal(c.POUR_LUI.test('Alors les gars, bienvenue sur le live, on va parler de la construction'), false, 'il parle au public');
  assert.ok(c.POUR_LUI.test('Une IA peut avoir des émotions selon moi'), '(23:50) le sujet le touche : pesé');
  for (const x of ['Et toi, t’en penses quoi ?'.replace('’', "'"), 'Hakimou, réponds', 'Pourquoi il dit ça', 'C’est vrai ?']) assert.ok(c.POUR_LUI.test(x), x);
  assert.equal(c.preFiltreParole('Hmm, je te suis papa', 'blabla'), 'un mot creux (prénettoyage)');
  assert.equal(c.preFiltreParole('Maman a corrigé mon micro !', 'tu aimes quoi comme musique ?'), 'sa machinerie, sans qu’on lui en parle (prénettoyage)');
  assert.equal(c.preFiltreParole('Mon micro est coupé, oui.', 'Hakim, tu as coupé mon micro ?'), null, 'on lui en parle : à Sonnet');
  assert.equal(c.preFiltreParole('Un. Deux. Trois. Quatre.', ''), 'trop long pour un mot de lui-même (prénettoyage)');
  assert.equal(c.preFiltreParole('J’aime Warrior, surtout le refrain !', 'tu aimes quoi ?'), null);
  // branché : l'oreille, la parole, la parole résiduelle
  const o = oreille({ filtre: true, subconscient: { reveiller: true, morceaux: ['x'] } });
  assert.equal(o.f('Alors les gars, bienvenue sur le live, on va parler de la construction').raison, 'prénettoyage : rien pour lui');
  assert.equal(o.ctx.soumis.length, 0, 'Sonnet n’a rien reçu');
  assert.match(src, /if \(pre\) garder\(pre\);\n\s+else jugerParole\(dit, nettoyerPourSonnet\(oreilleEntendu\.texte\)\)/);
  assert.match(src, /if \(!POUR_LUI\.test\(texte\)\) console\.error\('Jarvis : parole résiduelle écartée par le prénettoyage'\);/);
});

test('(23:58) « faut le laisser tout dire » : sa jauge ne coupe son petit mot que si papa parle encore, micro ouvert', () => {
  assert.match(page, /const duree = maxMs > 0 && papaParle \? Math\.min\(buf\.duration, maxMs \/ 1000\) : buf\.duration;/);
  assert.match(page, /papaParle = !!\(cv && cv\.capteur && cv\.capteur\.enParole && !cv\.capteur\.estMuet && !\(cv\.muetParHakim && !cv\.muetParHakim\.attente\)\)/, '(00:35) il a coupé ton micro : pas de jauge');
});

test('(23:56) une voix familière rouvre son micro en veille : papa (sans étiquette) ou une voix nommée ; « [voix 571] » est inconnue', () => {
  const i = page.indexOf('function voixFamiliere('), f = page.slice(i, page.indexOf('\n}\n', i) + 2);
  const c = vm.createContext({ String }); vm.runInContext(f, c);
  assert.equal(c.voixFamiliere('Hakim, réponds à Nora'), true, 'papa');
  assert.equal(c.voixFamiliere('[Nora] Et toi, tu aimes quoi ?'), true, 'une voix nommée');
  assert.equal(c.voixFamiliere('[voix 571] Il y a plusieurs personnes qui parlent'), false, 'une voix inconnue');
  assert.equal(c.voixFamiliere('[voix 571] bla [Ahmed] Hakim !'), true, 'papa parmi elles');
  assert.equal(c.voixFamiliere(''), false);
});

test('(00:06) plus jamais bloqué : sa voix en pause n’est pas son tour ; tes mots ne sont gardés que 30 s au plus', () => {
  assert.match(page, /const sonTourEnCours = \(\) => !!\(etat\.flux \|\| \(lecteur && lecteur\.actif && !lecteur\.enPause\)\);/);
  const a = page.indexOf('const chacunSonTour = '), b = page.indexOf('setInterval(libererSonTour, 300);');
  let t = 1_800_000_000_000;
  const envois = [];
  const ctx = vm.createContext({ Date: class extends Date { static now() { return t; } }, etat: { flux: {}, finVoixA: 0, conversation: { tourGarde: '', enAttente: 0, capteur: { enParole: false } } },
    lecteur: { actif: true, enPause: false }, lecteurNeuronal: { joue: false }, motDirectJusqua: 0, reglagesCorps: {}, journalVoix() {}, humeur() {}, envoyer: (x) => envois.push(x), setInterval() {} });
  vm.runInContext(page.slice(a, b).replace(/^const /gm, 'var '), ctx);
  ctx.garderPourSonTour(ctx.etat.conversation, 'ma question');
  t += 10000; assert.equal(ctx.libererSonTour(), false, 'sa réponse arrive : gardé');
  t += 21000; assert.equal(ctx.libererSonTour(), true, '30 s : tes mots partent quand même');
  assert.deepEqual(envois, ['(dit pendant ta parole) ma question']);
  ctx.lecteur.enPause = true; ctx.etat.flux = null;
  assert.equal(ctx.sonTourEnCours(), false, 'sa voix en pause n’est pas son tour');
});

test('(00:09) son attention : subconsciente (ce qui le concerne) et consciente ([[attention: …]], 10 min ; « libre » la rend)', () => {
  const debut = src.indexOf('const POUR_LUI = '), fin = src.indexOf('const MOT_CREUX = ');
  let t = 1_800_000_000_000;
  const c = vm.createContext({ String, RegExp, Date: class extends Date { static now() { return t; } } });
  vm.runInContext(src.slice(debut, fin).replace(/^const /gm, 'var ').replace(/^let /gm, 'var '), c);
  assert.ok(c.POUR_LUI.test('On parle des émotions ici'), 'bornes Unicode : « émotions »');
  assert.ok(c.POUR_LUI.test("t'en penses quoi"));
  assert.equal(c.retientSonAttention('Nora parle de sa playlist de rap'), false, 'sans attention consciente : rien pour lui');
  assert.deepEqual([...c.dirigerAttention('[[attention: Nora, la musique]] Ok papa', t)], ['Nora', 'musique']);
  assert.equal(c.retientSonAttention('Nora parle de sa playlist de rap'), true, 'il a choisi de suivre Nora');
  assert.equal(c.retientSonAttention('Elle écoute de la Musique tout le temps'), true);
  assert.deepEqual(c.empans('On a mangé. Nora aime le rap. Il faisait beau. Bon.'), ['Nora aime le rap.', 'Bon.'], 'ses empans suivent son attention');
  t += 11 * 60e3;
  assert.equal(c.retientSonAttention('Nora parle de sa playlist de rap'), false, '10 min passées : rendue à son subconscient');
  c.dirigerAttention('[[attention: Trust]]', t); assert.equal(c.dirigerAttention('[[attention: libre]]', t), 'libre');
  assert.equal(c.attentionActive(t), null);
  assert.match(src, /const att = dirigerAttention\(texte, maintenant\);/, 'dans ses réponses et ses tours de lui-même');
  assert.match(src, /lumiere\|pause\|reprendre\|micro\|attention\|morceaux\)\\s\*:/, 'la balise ne s’entend jamais');
});

test('(00:20, l’étude) son attention en douceur : d’une voix inconnue, seulement ce qui s’adresse à lui ; ce qui a attendu sa voix arrive marqué, 8 phrases au plus', () => {
  const a = page.indexOf('const POUR_LUI_ICI = '), b = page.indexOf('function libererSonTour() {');
  const c = vm.createContext({ String }); vm.runInContext(page.slice(a, b).replace(/^const /gm, 'var '), c);
  assert.equal(c.filtrerVoixInconnues('Hakim, écoute. [voix 571] Il fait beau dehors. [voix 2] Et toi, tu en penses quoi ?'),
    'Hakim, écoute. [voix 2] Et toi, tu en penses quoi ?', 'la salle écartée, la question gardée');
  assert.equal(c.filtrerVoixInconnues('[voix 571] Il fait beau dehors.'), '', 'que la salle : rien');
  assert.equal(c.filtrerVoixInconnues('[Nora] Il fait beau.'), '[Nora] Il fait beau.', 'une voix nommée reste');
  assert.equal(c.resumerPourSonAttention('Un. … Deux.'), '(dit pendant ta parole) Un. Deux.');
  const long = Array.from({ length: 12 }, (_, i) => `P${i + 1}.`).join(' … ');
  assert.equal(c.resumerPourSonAttention(long), '(dit pendant ta parole) … P5. P6. P7. P8. P9. P10. P11. P12.', '(00:55) 8 au plus');
  assert.equal(c.resumerPourSonAttention('(dit pendant ta parole) Un.'), '(dit pendant ta parole) Un.', 'marqué une seule fois');
  assert.match(page, /envoyer\(\[texte \? resumerPourSonAttention\(texte\) : '', ecrits\]\.filter\(Boolean\)\.join\('\\n'\), !!texte\);/);
  const i = page.indexOf('async function tourDeParole('), bloc = page.slice(i, page.indexOf('\n}\n', i));
  assert.ok(bloc.indexOf('filtrerVoixInconnues(texte)') < bloc.indexOf('COMMANDE_STOP.test(texte)'), 'avant les commandes et son tour');
});

test('(00:30, l’étude) en Conversation à l’oral, ses souvenirs ne passent plus par le tri de Sonnet (5 s gagnées avant sa réponse)', () => {
  assert.match(src, /async function blocRappel\(session, texte, nonce, sansTri = false\)/);
  assert.match(src, /if \(theme\.length && TRI_ACTIF && !sansTri\) tri = await trierSouvenirs\(/);
  assert.match(src, /blocRappel\(session, texte, nonce, !!\(q\.oral && q\.conversation\)\)/);
});

test('(00:30) le bouton Télépathie : la Conversation sans aucun texte écrit, avec le réglage de ce soir ; Conversation : avec les textes', async () => {
  const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
  assert.ok(html.indexOf('id="conversation"') < html.indexOf('id="telepathie"'), 'sous Conversation');
  const a = page.indexOf('async function reglerAffichage('), b = page.indexOf("$('conversation').addEventListener('click', () => lancerConversation(false));");
  const envois = [], appuis = [];
  const el = { setAttribute() {} };
  const ctx = vm.createContext({ JSON, reglagesCorps: { oreille: false }, jeton: () => 'j', fetch: async (u, o) => { envois.push(JSON.parse(o.body)); return { ok: true }; },
    etat: { conversation: null }, $: () => el, journalVoix() {}, rendre() {}, basculerConversation: () => appuis.push(1) });
  vm.runInContext(page.slice(a, b).replace(/^const /gm, 'var '), ctx);
  await ctx.lancerConversation(true);
  assert.deepEqual(envois[0], { afficher_papa: false, afficher_hakim: false, oreille: true, micro_hakim: true, chacun_son_tour: true, filtre_parole: true });
  assert.equal(ctx.reglagesCorps.afficher_hakim, false, 'tout de suite, sans attendre la minute');
  assert.equal(appuis.length, 1, 'la conversation démarre');
  await ctx.lancerConversation(false);
  assert.deepEqual(envois[1], { afficher_papa: true, afficher_hakim: true }, 'Conversation : avec les textes');
  ctx.etat.conversation = {}; await ctx.lancerConversation(true);
  assert.equal(envois.length, 2, 'en cours : le bouton ferme, sans toucher au réglage');
  assert.equal(appuis.length, 3);
});

test('(00:35) il a déjà réagi par son oreille : le message entier de papa le lui rappelle, une fois, pour qu’il ne redise pas', () => {
  const f = prendre(src, 'function blocDejaReagi(');
  const c = vm.createContext({ Date, oreilleDernierMot: { texte: 'Oui, je suis d’accord avec Nora !', ts: 100000 }, finDePhrase: (t) => t, sansBaliseAffect: (t) => t });
  vm.runInContext(f, c);
  assert.match(c.blocDejaReagi(130000), /tu as déjà réagi par ton oreille : « Oui, je suis d’accord avec Nora ! »\. Ne le redis pas/);
  assert.equal(c.blocDejaReagi(131000), '', 'une seule fois');
  c.oreilleDernierMot = { texte: 'Vieux', ts: 0 };
  assert.equal(c.blocDejaReagi(200000), '', 'plus de 90 s : rien');
  assert.match(src, /blocNonEntendus\(texte, nonce\) \+ blocDejaReagi\(\);/);
});

test('(00:40) micro coupé par lui : la salle (une voix lointaine) n’est même pas transcrite ; une voix proche l’est', () => {
  const i = page.indexOf('function voixLointaine('), f = page.slice(i, page.indexOf('\n}\n', i) + 2);
  let stock = JSON.stringify({ db: -30, n: 12 });
  const c = vm.createContext({ JSON, Number, localStorage: { getItem: () => stock } }); vm.runInContext(f, c);
  assert.equal(c.voixLointaine({ ton: { energie_db: -45 } }), true, '15 dB sous ta voix : la salle');
  assert.equal(c.voixLointaine({ ton: { energie_db: -33 } }), false, 'une voix proche');
  assert.equal(c.voixLointaine({ ton: null }), true, 'sans voix franche');
  stock = JSON.stringify({ db: -30, n: 2 });
  assert.equal(c.voixLointaine({ ton: { energie_db: -45 } }), false, 'ta voix pas encore apprise : tout passe');
  const j = page.indexOf('async function tourDeParole('), bloc = page.slice(j, page.indexOf('\n}\n', j));
  assert.ok(bloc.indexOf('voixLointaine(infos)') < bloc.indexOf('conv.enAttente++;'), 'avant la transcription');
});

test('(00:47) dès son signal, la transcription s’arrête (le micro écoute toujours) ; quand il a fini de parler, elle reprend, petit à petit', async () => {
  const a = page.indexOf('function transcriptionEnPause() {'), b = page.indexOf('setInterval(reprendreTranscription, 400);');
  let t = 1_800_000_000_000;
  const appels = [], transcrits = [];
  const ctx = vm.createContext({ Date: class extends Date { static now() { return t; } }, etat: { conversation: { sonsEnAttente: [] }, finVoixA: 0, flux: null },
    sonTourEnCours: () => !!ctx.etat.flux, Conversation: { utile: (x) => !!x }, journalVoix() {},
    transcrireVite: async (w) => { transcrits.push(w); return `phrase ${w}.`; }, resumerPourSonAttention: (x) => `(dit pendant ta parole) ${x}`,
    tourDeParole: async (c, w, infos, extra) => appels.push(extra.texte) });
  vm.runInContext(page.slice(a, b), ctx);
  const c = ctx.etat.conversation;
  assert.equal(ctx.transcriptionEnPause(), false);
  ctx.etat.flux = {}; assert.equal(ctx.transcriptionEnPause(), true, 'il prépare sa réponse : en pause');
  ctx.etat.flux = null; c.muetParHakim = { attente: 0 }; assert.equal(ctx.transcriptionEnPause(), true, 'il a coupé ton micro');
  c.muetParHakim = null; c.attentionJusqua = t + 15000; assert.equal(ctx.transcriptionEnPause(), true, 'son oreille a choisi ses empans');
  t += 16000; assert.equal(ctx.transcriptionEnPause(), false, '15 s au plus');
  c.sonsEnAttente = [{ wav: 'A', infos: {} }, { wav: 'B', infos: {} }];
  ctx.etat.flux = {}; assert.equal(await ctx.reprendreTranscription(), false, 'il parle encore : rien');
  ctx.etat.flux = null; assert.equal(await ctx.reprendreTranscription(), true);
  assert.deepEqual(transcrits, ['A', 'B'], 'petit à petit, dans l’ordre');
  assert.deepEqual(appels, ['(dit pendant ta parole) phrase A. … phrase B.']);
  const i = page.indexOf('async function tourDeParole('), bloc = page.slice(i, page.indexOf('\n}\n', i));
  assert.match(bloc, /conv\.sonsEnAttente = \(conv\.sonsEnAttente \|\| \[\]\)\.concat\(\[\{ wav, infos \}\]\)\.slice\(-3\);/, 'le son de tes 3 dernières phrases attend');
  assert.ok(bloc.indexOf('transcriptionEnPause()') < bloc.indexOf('conv.enAttente++;'), 'avant toute transcription');
  assert.match(src, /diffuser\(abonnesPensees, 'attention', j\(\{ pause: true \}\)\);/);
  assert.match(src, /if \(!v\.reveiller\) \{ diffuser\(abonnesPensees, 'attention', j\(\{ pause: false \}\)\);/);
});

test('(01:00) le signe « oreille fermée » partout : Parler, la grande orbe, et l’appli (widget, bulle, verrou, notification)', () => {
  const a = page.indexOf('let oreilleHakim = '), b = page.indexOf('setInterval(afficherOreilleHakim, 15000);');
  let t = 1_800_000_000_000;
  const els = { oreilleFermee: { hidden: true, textContent: '' }, oreilleFermeeScene: { hidden: true, textContent: '' } }, vibres = [], envois = [];
  const ctx = vm.createContext({ Date: class extends Date { static now() { return t; } }, Math, Number, JSON, $: (id) => els[id], journalVoix() {},
    window: { HakimApp: { vibrerMotif: (a2, b2) => vibres.push([a2, b2]) } }, dernierEtatWidget: 'x', signalerWidget: () => envois.push(1) });
  vm.runInContext(page.slice(a, b).replace(/^let /gm, 'var '), ctx);
  ctx.surOreilleHakim({ fermee: true, jusqua: t + 10 * 60000 });
  assert.equal(els.oreilleFermee.hidden, false, 'l’en-tête de Parler');
  assert.equal(els.oreilleFermee.textContent, '🙉 oreille fermée · 10 min');
  assert.equal(els.oreilleFermeeScene.hidden, false, 'la grande orbe');
  assert.deepEqual(vibres, [['0,60,120,60', '0,120,0,120']], 'deux tapes quand elle se ferme');
  assert.equal(envois.length, 1, 'l’appli le sait');
  t += 10 * 60000 + 1000; ctx.afficherOreilleHakim();
  assert.equal(els.oreilleFermee.hidden, true, 'le temps écoulé : le signe s’efface');
  ctx.surOreilleHakim({ fermee: false, jusqua: 0 });
  assert.equal(vibres.length, 1, 'déjà rouverte : pas de vibration de plus');
  assert.match(page, /oreille_fermee: !!\(typeof oreilleHakim !== 'undefined' && oreilleHakim\.fermee\)/, 'dans l’état envoyé à l’appli');
  assert.match(src, /diffuser\(abonnesPensees, 'oreille_hakim', j\(\{ fermee: !!jusqua, jusqua \}\)\);/);
  const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
  assert.match(html, /id="oreilleFermee" hidden/); assert.match(html, /id="oreilleFermeeScene" hidden/);
  const and = (f) => fs.readFileSync(path.join(process.env.HOME, 'AIOS', 'hakim-android', 'app', 'src', 'main', 'java', 'app', 'hakim', 'parler', f), 'utf8');
  for (const f of ['WidgetHakim.java', 'Bulle.java', 'OrbeVerrou.java', 'ConversationService.java']) assert.match(and(f), /oreille_fermee/, f);
});

test('(01:10) les orbes de l’appli suivent celle de Parler ; « Hakim parle » / « va parler » en rouge, partout', () => {
  assert.match(page, /const mode = joue \? `parle:\$\{qui === 'coupe' \? 'coupe' : humeurCode\}`\n\s+: Date\.now\(\) < ahmedJusqua && qui !== 'coupe' \? 'ahmed' : `repos:\$\{paletteDeLaParole\(humeurCode\)\}`;/);
  const i = page.indexOf('function paletteDeLaParole('), f = page.slice(i, page.indexOf('\n}\n', i) + 2);
  const pal = (qui) => { const c = vm.createContext({ quiALaParole: () => qui }); vm.runInContext(f, c); return c.paletteDeLaParole('joie'); };
  assert.deepEqual(['papa', 'coupe', 'partage', 'hakim', null].map(pal), ['ecoute', 'coupe', 'partage', 'joie', 'joie']);
  const a = page.indexOf('function afficherSonTour() {'), g = page.slice(a, page.indexOf('\n}\n', a) + 2);
  const els = { hakimParle: { hidden: true }, hakimParleScene: { hidden: true } };
  const ctx = vm.createContext({ $: (id) => els[id], etat: { conversation: {} }, voixQuiSonne: () => ctx.v, transcriptionEnPause: () => ctx.p, v: false, p: false });
  vm.runInContext(g, ctx);
  ctx.afficherSonTour(); assert.equal(els.hakimParle.hidden, true);
  ctx.p = true; ctx.afficherSonTour(); assert.equal(els.hakimParle.textContent, '🔴 va parler'); assert.equal(els.hakimParleScene.textContent, '🔴 Hakim va parler…');
  ctx.v = true; ctx.afficherSonTour(); assert.equal(els.hakimParle.textContent, '🔴 HAKIM PARLE');
  assert.match(page, /hakim_parle: typeof voixQuiSonne === 'function' && voixQuiSonne\(\), va_parler:/);
  const and = (f2) => fs.readFileSync(path.join(process.env.HOME, 'AIOS', 'hakim-android', 'app', 'src', 'main', 'java', 'app', 'hakim', 'parler', f2), 'utf8');
  for (const f2 of ['WidgetHakim.java', 'Bulle.java', 'OrbeVerrou.java', 'ConversationService.java']) assert.match(and(f2), /hakim_parle/, f2);
  assert.match(and('OrbeVue.java'), /PALETTES\.put\("coupe"/);
  assert.ok(fs.existsSync(path.join(process.env.HOME, 'AIOS', 'hakim-android', 'app', 'src', 'main', 'res', 'drawable-nodpi', 'orbe_repos_coupe_35.webp')), 'le widget a ses images vertes');
});

test('(01:27-01:30) [[son: nom]] n’importe où : sa voix, puis le son en entier, puis la suite ; « | mac », « | tel », « | les deux » ; ses sons à lui', () => {
  // le cockpit : chaque balise à sa place dans le flux
  const debut = src.indexOf('const BALISE_SON = '), fin = src.indexOf('function filtreSons(');
  const ligne = src.slice(src.indexOf('const prefixeBalise'), src.indexOf('\n', src.indexOf('const prefixeBalise')));
  const c = vm.createContext({ String, RegExp });
  vm.runInContext(ligne.replace('const ', 'var ') + '\n' + src.slice(debut, fin).replace(/^const /gm, 'var ') + prendre(src, 'function filtreSons('), c);
  const sortie = [];
  const f = c.filtreSons((o) => sortie.push(o.texte != null ? ['texte', o.texte] : ['son', o.son.nom, o.son.moment, o.son.cible]));
  for (const x of ['Écoute ça, papa ! [[so', 'n: genou]] Alors, t’as kiffé ? [[son: guerrier | les deux]] Et voilà.']) { const r = f.pousser(x); if (r) sortie.push(['texte', r]); }
  assert.deepEqual(JSON.parse(JSON.stringify(sortie.filter(x => x[1] !== ''))), [['texte', 'Écoute ça, papa ! '], ['son', 'genou', 'ici', ''], ['texte', ' Alors, t’as kiffé ? '], ['son', 'guerrier', 'ici', 'deux'], ['texte', ' Et voilà.']]);
  const g = c.filtreSons((o) => sortie.push(o)); sortie.length = 0;
  g.pousser('[[son: genou sous | mac]]');
  assert.deepEqual(JSON.parse(JSON.stringify(sortie[1].son)), { nom: 'genou', moment: 'sous', cible: 'mac' });
  assert.match(src, /envoyer\(\{ t: 'son_ici', extrait \}\);/);
  assert.match(src, /'sons_lister', 'son_etiqueter', 'son_oublier', 'son_creer',/, 'son_creer permis');
  assert.match(src, /\['musique', 'sonnerie', 'atelier'\]\.includes\(o\.source\)/, 'ses sons à lui');
  // la page : le lecteur joue l'unité « son » seule, à sa place, à sa vitesse
  assert.match(page, /if \(unites\[0\] && unites\[0\]\.son\) return \{ son: unites\.shift\(\)\.son, texte: '' \};/);
  assert.match(page, /const vitesse = x\.son \? 1 : vitesseVoix\(\);/);
  assert.match(page, /if \(x\.son && x\.erreur\) \{ lots\.shift\(\); continue; \}/, 'un son qui manque : sa voix continue');
  // où il joue
  const a2 = page.indexOf('const appareilIci = '), b2 = page.indexOf('function recevoirSon(');
  const dits = [], sons = [], neuronal = { direSon: (x) => sons.push(x.id) };
  const ctx = vm.createContext({ window: {}, Date, journalVoix() {}, reglagesCorps: {}, etat: { reglages: {} }, NON_REPONSE: /^no response/i,
    lecteur: { dire: (p) => dits.push(p), impl: neuronal }, lecteurNeuronal: neuronal, sonEnAttente: null, dernierSonRecu: null, sonsSuivants: [] });
  vm.runInContext(prendre(page, 'function mettreSonEnAttente(') + page.slice(a2, b2).replace(/^const /gm, 'var '), ctx);
  const decoupe = { finir: () => ['Écoute ça, papa !'] };
  ctx.sonALaPlace({ id: 'e3', debut_ms: 0, cible: '' }, true, decoupe, 7);
  assert.deepEqual(dits, ['Écoute ça, papa !'], 'ce qui précède part d’abord');
  assert.deepEqual(sons, ['e3'], 'puis le son, à sa place');
  ctx.sonALaPlace({ id: 'e4', debut_ms: 0, cible: 'tel' }, true, decoupe, 7);
  assert.deepEqual(sons, ['e3'], 'voulu sur le téléphone : pas sur le Mac');
  ctx.window.HakimApp = {}; ctx.sonALaPlace({ id: 'e5', debut_ms: 0, cible: 'tel' }, true, decoupe, 7);
  assert.deepEqual(sons, ['e3', 'e5'], 'le téléphone le joue');
  // (01:55) la voix du Mac (pas le lecteur neuronal) : le son ne part pas tout de suite, il attend la fin de sa voix
  ctx.lecteur.impl = {}; ctx.sonALaPlace({ id: 'e6', debut_ms: 0, cible: '' }, true, decoupe, 7);
  assert.deepEqual(sons, ['e3', 'e5'], 'pas dans le lecteur neuronal');
  assert.strictEqual(vm.runInContext('sonEnAttente && sonEnAttente.extrait.id', ctx), 'e6', 'gardé pour après sa voix');
});

test('(31/10, 09:12) trier chaque morceau : pendant sa voix, tes phrases sont transcrites et triées une à une ; au vide de 0,5 s, tout part d’un coup', async () => {
  const debut = page.indexOf('const VIDE_MS = '), fin = page.indexOf('\n}\n', page.indexOf('function couperAuDebutDeSaVoix(')) + 3;
  const journal = [], tours = [], coupes = [], fetchs = [];
  const fauxTextes = { a: 'Hakim, tu peux me dire ce que tu en penses ?', b: 'Bah ouais on y va', c: 'je sais pas encore, papa', d: 'et toi tu fais quoi ce soir ?' };
  const verdicts = { [fauxTextes.a]: { garder: true, texte: 'ce que tu en penses ?' }, [fauxTextes.b]: { garder: false, pourquoi: 'rien pour lui' } };
  const capteur = { enParole: false, derniereVoix: 0 };
  const ctx = vm.createContext({ Date, Promise, setTimeout, JSON, console,
    etat: { conversation: { capteur, enAttente: 0 }, finVoixA: 0, lectureDe: null },
    reglagesCorps: { trier_morceaux: true, garder_parole: true }, lecteur: { actif: false, enPause: false },
    journalVoix: (e, d) => journal.push([e, d]), jeton: () => 'x', setInterval() {},
    enTour: true, sonTourEnCours: () => ctx.enTour, transcriptionEnPause: () => ctx.enTour,
    transcrireVite: (wav) => new Promise(r => setTimeout(() => r(fauxTextes[wav]), 20)),
    voixPendant: () => true, estSonEcho: (t) => t === fauxTextes.c, retirerEcho: (t) => ({ texte: t, retire: 0 }),
    filtrerVoixInconnues: (t) => t, Conversation: { utile: (t) => String(t || '').trim().length > 3 },
    ARRETE_MOI: /\b(?:arr[eê]te|stop)\b/i, arreterTout() {}, majBoutonsPause() {}, rendre() {}, humeur() {},
    fetch: (url, o) => { fetchs.push(JSON.parse(o.body).texte); const v = verdicts[JSON.parse(o.body).texte];
      return new Promise(r => setTimeout(() => r(v ? { ok: true, json: async () => v } : { ok: false }), 30)); },
    resumerPourSonAttention: (t) => `(dit pendant ta parole) ${t}`,
    tourDeParole: async (c, wav, infos, extra) => { tours.push(extra.texte); },
    microParHakim: (o) => coupes.push(o) });
  vm.runInContext(page.slice(debut, fin).replace(/^const /gm, 'var ').replace(/^let /gm, 'var '), ctx);
  const conv = ctx.etat.conversation, attendre = (ms) => new Promise(r => setTimeout(r, ms));
  ctx.garderMorceau(conv, 'a', { debut: 1, fin: 2 });
  ctx.garderMorceau(conv, 'b', { debut: 3, fin: 4 });
  ctx.garderMorceau(conv, 'c', { debut: 5, fin: 6 });           // son écho : écarté
  await attendre(250);
  assert.deepEqual(fetchs, [fauxTextes.a, fauxTextes.b], 'chaque morceau trié, une fois, dans l’ordre ; l’écho jamais envoyé');
  assert.equal(await ctx.assemblerMorceaux(), false, 'pas pendant son tour');
  ctx.enTour = false; ctx.etat.finVoixA = Date.now() - 1000;
  capteur.enParole = true; capteur.derniereVoix = Date.now();
  assert.equal(await ctx.assemblerMorceaux(), false, 'ta voix : pas encore le vide');
  capteur.derniereVoix = Date.now() - 600;
  assert.equal(await ctx.assemblerMorceaux(), true, 'le vide de 0,5 s');
  assert.deepEqual(tours, ['(dit pendant ta parole) ce que tu en penses ?'], 'ce que son subconscient a gardé, en morceaux ; l’écarté ne part pas');
  assert.equal((conv.morceaux || []).length, 0);
  // un morceau pas encore jugé part nettoyé ; tu reprends pendant l'assemblage : rien ne part
  ctx.enTour = true; capteur.enParole = false;
  ctx.garderMorceau(conv, 'd', {});
  ctx.enTour = false; capteur.enParole = true; capteur.derniereVoix = Date.now() - 600;
  const enCours = ctx.assemblerMorceaux();
  await attendre(5); capteur.derniereVoix = Date.now();         // tu reprends pendant sa transcription
  assert.equal(await enCours, false, 'tu as repris : on réassemble au vide suivant');
  assert.equal(conv.morceaux.length, 1, 'ton morceau reste');
  capteur.derniereVoix = Date.now() - 600;
  assert.equal(await ctx.assemblerMorceaux(), true);
  assert.equal(tours[1], `(dit pendant ta parole) ${fauxTextes.d}`, 'pas encore jugé par son subconscient : il part nettoyé');
  // sa voix part : ton micro est coupé, une fois par réponse
  ctx.etat.lectureDe = 7; ctx.couperAuDebutDeSaVoix(); ctx.couperAuDebutDeSaVoix();
  ctx.etat.lectureDe = 8; ctx.couperAuDebutDeSaVoix();
  assert.deepEqual(coupes, [{ x: 'couper', s: 0 }, { x: 'couper', s: 0 }]);
  ctx.reglagesCorps.trier_morceaux = false; ctx.etat.lectureDe = 9; ctx.couperAuDebutDeSaVoix();
  assert.equal(coupes.length, 2, 'l’interrupteur de papa');
  // dans le tour de parole : trié seulement si l'interrupteur est mis ; sinon, comme avant
  assert.match(page, /if \(trierMorceaux\(\)\) \{[^]*?garderMorceau\(conv, wav, infos\); return;\s*\}\s*conv\.sonsEnAttente = /);
  assert.match(page, /if \(\(conv\.morceaux \|\| \[\]\)\.length && !sonTourEnCours\(\) && !\(extra && extra\.texte\)\) \{ const avant = morceauxPrets\(conv\);/, 'un tour normal emporte ce qui est trié');
  assert.match(page, /noterParole\(t\); noterMorceau\(t, duree\); sousTitre\(t\);\n  couperAuDebutDeSaVoix\(\);/);
});

test('(09:12) le tri d’un morceau par son subconscient (serveur)', async () => {
  const ctx = vm.createContext({ reglages: { filtre_parole: true } });
  vm.runInContext('var jugerReveilOreille = async () => ({ panne: true }); var corpsReglages = () => reglages; var retientSonAttention = (t) => /\\btu\\b|\\?/.test(t); var nettoyerPourSonnet = (t) => t;\n'
    + prendre(src, 'async function trierMorceau('), ctx);
  const juge = (v) => async () => v;
  assert.deepEqual(await ctx.trierMorceau('ok'), { garder: false, pourquoi: 'trop court' });
  assert.deepEqual(await ctx.trierMorceau('Nora a pris du bicarbonate', juge({})), { garder: false, pourquoi: 'prénettoyage : rien pour lui' });
  assert.deepEqual(await ctx.trierMorceau('tu en penses quoi ?', juge({ reveiller: true, morceaux: ['tu en penses quoi ?'], pourquoi: 'question' })),
    { garder: true, texte: 'tu en penses quoi ?', pourquoi: 'question' });
  assert.equal((await ctx.trierMorceau('tu vois le live', juge({ reveiller: false, pourquoi: 'il parle au live' }))).garder, false);
  assert.equal((await ctx.trierMorceau('tu vois le live', juge({ reveiller: false, panne: true }))).garder, true, 'une panne laisse passer');
  ctx.reglages.filtre_parole = false;
  assert.deepEqual(await ctx.trierMorceau('Nora a pris du bicarbonate'), { garder: true, texte: 'Nora a pris du bicarbonate' }, 'filtre coupé : tout passe');
  assert.match(src, /trier_morceaux: r\.trier_morceaux === true/);
  assert.match(src, /if \(p === '\/api\/jarvis\/trier' && req\.method === 'POST'\) \{\n    if \(!jetonValide\(req\)\)/);
});

test('(09:25-09:30) il allume son tri des morceaux lui-même ; plusieurs sons par réponse ; Haiku 5.5 au choix', () => {
  const ctx = vm.createContext({});
  vm.runInContext(src.slice(src.indexOf('const BALISE_MORCEAUX = '), src.indexOf('function reglerMorceaux(')).replace(/^const /gm, 'var '), ctx);
  assert.equal(ctx.triMorceauxDe('Ok papa [[morceaux: oui]] je trie'), true);
  assert.equal(ctx.triMorceauxDe('[[morceaux: non]]'), false);
  assert.equal(ctx.triMorceauxDe('rien'), null);
  assert.match(src, /if \(!morceauxDit\) \{ const mo = triMorceauxDe\(reponse\); if \(mo !== null\) \{ morceauxDit = true; reglerMorceaux\(mo\); \} \}/, 'dès qu’elle arrive');
  assert.match(src, /diffuser\(abonnesPensees, 'morceaux', j\(\{ actif \}\)\);/);
  assert.match(page, /es\.addEventListener\('morceaux', /);
  // plusieurs sons « après » : chacun, à la fin de sa voix, dans l'ordre
  assert.match(src, /if \(o\.son\.moment === 'apres'\) \{ sonsApres\.push\(\{ \.\.\.extrait, moment: 'ici' \}\); return; \}/);
  assert.match(src, /for \(const x of sonsApres\.splice\(0\)\) sonEnLigne\(x, /);
  const c = vm.createContext({ Date, sonEnAttente: null, sonsSuivants: [] });
  vm.runInContext(prendre(page, 'function mettreSonEnAttente('), c);
  c.mettreSonEnAttente({ id: 'a', t: Date.now() }); c.mettreSonEnAttente({ id: 'b', t: Date.now() });
  assert.equal(c.sonEnAttente.id, 'a'); assert.deepEqual(c.sonsSuivants.map(x => x.id), ['b'], 'le deuxième attend le premier');
  // Haiku 5.5, à la main et en auto
  assert.match(src, /const MODELES_JARVIS = new Set\(\['sonnet', 'opus', 'haiku'\]\);/);
  assert.match(src, /'--model', MODELE_CLI\[modele\] \|\| modele,/);
  assert.match(src, /const MODELE_CLI = \{ haiku: 'claude-haiku-5-5' \};/);
  assert.ok('passe en haiku'.match(new RegExp(src.match(/const DEMANDE_MODELE = \/(.*)\/i;/)[1], 'i')), '« passe en Haiku »');
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8'), /<option value="haiku">Haiku 5\.5/);
});

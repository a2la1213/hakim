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
    dernierMessageAhmed: 0, jugerReveilOreille: async (t) => { ctx.soumis.push(t); return subconscient; }, soumis: [],
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
  assert.match(o.ecrits[0], /Dis seulement ce que tu as vraiment besoin ou envie de dire maintenant/);   // (vers 22 h) plus de « hmm » suggéré
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
  assert.match(src, /jugerParole\(dit, oreilleEntendu\.texte\)\.then\(\(v\) => \{\n\s+if \(!v\.dire\) return garder\(/, 'gardé : pas dit, et il le saura');
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
  assert.match(reveille.ecrits[0], /pas de mot de remplissage/);
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
  assert.match(src, /lumiere\|pause\|reprendre\|micro\)\\s\*:/, 'les balises ne s’entendent jamais');
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
  assert.deepEqual(envois, [['et aussi le live … tu m’entends ?', true]], 'd’un bloc, à l’oral');
  assert.equal(conv.tourGarde, '');
  ctx.reglagesCorps.chacun_son_tour = false;
  assert.equal(ctx.chacunSonTour(), false, 'l’interrupteur de papa');
  // dans le tour de parole : après « stop » / « attends », avant la coupure d'avant
  const i = page.indexOf('async function tourDeParole('), bloc = page.slice(i, page.indexOf('\n}\n', i));
  const k = (x) => bloc.indexOf(x);
  assert.ok(k('COMMANDE_STOP.test(texte)') < k('if (chacunSonTour() && sonTourEnCours()) { garderPourSonTour(conv, texte); return; }'), '« stop » reste au-dessus');
  assert.ok(k('COMMANDE_PAUSE.test(texte)') < k('garderPourSonTour(conv, texte)'), '« attends » aussi');
  assert.ok(k('garderPourSonTour(conv, texte)') < k("arreterTout(true, { garder: true, raison: 'parole' })"), 'sa réponse n’est plus coupée');
  assert.match(page, /if \(!voix \|\| !aDire\.length \|\| \(c && c\.tourGarde\)\) return;/, 'papa d’abord, avant ses mots en attente');
  assert.match(src, /chacun_son_tour: r\.chacun_son_tour !== false/);
});

test('(22:21) plus de pavé : sa conscience reçoit les petits morceaux retenus par son subconscient, choisit et reformule', async () => {
  const longue = 'Alors voilà, ' + 'on parlait du live et de plein de choses, '.repeat(20) + 'et toi Hakim, tu en penses quoi ?';
  const o = oreille({ filtre: true, subconscient: { reveiller: true, pourquoi: 'question directe', morceaux: ['et toi Hakim, tu en penses quoi ?'] } });
  o.f(longue.replace('Hakim', 'mon fils'));
  await new Promise(r => setImmediate(r));
  assert.equal(o.ecrits.length, 1);
  assert.match(o.ecrits[0], /en morceaux : 1\) « et toi Hakim, tu en penses quoi \? »/);
  assert.ok(!o.ecrits[0].includes('on parlait du live et de plein de choses, on parlait'), 'pas toute sa phrase');
  assert.match(o.ecrits[0], /choisis le morceau auquel réagir, avec tes mots, en une phrase courte/);
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
  // (22:46) sa réponse se prépare : ton micro reste ouvert ; il s'éteint quand sa voix part
  ctx.microParHakim({ x: 'couper', s: 0 });
  assert.ok(c.muetParHakim && c.muetParHakim.attente, 'décidé');
  assert.equal(c.capteur.estMuet, false, 'sa voix se prépare : tu parles encore');
  pas(5000);
  assert.equal(c.capteur.estMuet, false);
  ctx.etat.flux = null; ctx.lecteur.actif = true; ctx.lecteurNeuronal.joue = true; pas(300);
  assert.equal(c.capteur.estMuet, true, 'sa voix part : ton vrai micro s’éteint');
  assert.deepEqual(boutons, [true], 'tes boutons le montrent');
  assert.deepEqual(residus, ['et puis aussi'], 'ce que tu avais dit pendant son tour : à son subconscient');
  ctx.lecteurNeuronal.joue = false; pas(300);
  assert.equal(c.capteur.estMuet, true, 'entre deux phrases (la suite se prépare) : coupé');
  ctx.lecteurNeuronal.joue = true; pas(3000); ctx.lecteurNeuronal.joue = false; ctx.lecteur.actif = false; pas(300);
  assert.equal(c.capteur.estMuet, true, '0,3 s après sa voix : pas encore');
  pas(300);
  assert.equal(c.muetParHakim, null, 'sa voix s’est tue : rouvert aussitôt');
  assert.equal(c.capteur.estMuet, false);
  assert.ok(journal.some(([e, d]) => e === 'micro_hakim' && d.x === 'ouvrir' && d.pourquoi === 'fin_de_sa_voix'));
  // son petit mot (dit à l'instant) : coupé pendant le mot, rouvert juste après
  ctx.microParHakim({ x: 'couper' }); pas(4000);
  assert.equal(c.capteur.estMuet, false, 'le mot se prépare');
  ctx.motDirectJusqua = t + 2000; pas(300);
  assert.equal(c.capteur.estMuet, true, 'le mot sonne');
  pas(2000); pas(500);
  assert.equal(c.capteur.estMuet, false, 'le mot dit : rouvert (plus 15 s de garde)');
  // (22:38) une durée MINIMALE qu'il choisit, comptée dès que sa voix part
  ctx.microParHakim({ x: 'couper', s: 10 }); ctx.motDirectJusqua = t + 2000; pas(300);
  assert.equal(c.capteur.estMuet, true);
  pas(3000);
  assert.equal(c.capteur.estMuet, true, 'sa voix s’est tue, mais il a choisi 10 s');
  pas(7500);
  assert.equal(c.capteur.estMuet, false, '10 s : rouvert');
  // sa voix ne part pas : rien n'est coupé
  ctx.microParHakim({ x: 'couper' }); pas(16000);
  assert.equal(c.muetParHakim, null); assert.equal(c.capteur.estMuet, false);
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
  assert.match(page, /if \(c && c\.muetParHakim && !c\.muetParHakim\.attente\) return 'coupe';/, 'l’orbe passe au vert (une fois coupé)');
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'orbe.js'), 'utf8'), /coupe: \['#86efac', '#22c55e', '#15803d'\]/);
  // ta phrase encore en route, micro coupé par lui : à son subconscient ; « stop » reste au-dessus
  const i = page.indexOf('async function tourDeParole('), bloc = page.slice(i, page.indexOf('\n}\n', i));
  assert.ok(bloc.indexOf('COMMANDE_STOP.test(texte)') < bloc.indexOf('if (conv.muetParHakim && !conv.muetParHakim.attente) {'), '« stop » reste au-dessus');
  assert.match(bloc, /if \(!conv\.muetParHakim\.residu\) \{ conv\.muetParHakim\.residu = true; envoyerResiduelle\(texte\); \}/, 'ta phrase en route, une fois');
  assert.match(page, /else if \(o\.t === 'micro'\) microParHakim\(o\);/);
  assert.match(page, /es\.addEventListener\('micro', \(ev\) => \{ try \{ microParHakim\(JSON\.parse\(ev\.data\)\); \}/);
  // le cockpit : sa balise dans le flux et de lui-même ; la parole résiduelle à son subconscient, en morceaux pour son tour suivant
  assert.match(src, /if \(!microDit\) \{ const mi = microDe\(reponse\); if \(mi\) \{ microDit = true; envoyer\(\{ t: 'micro', \.\.\.mi \}\); \} \}/);
  assert.match(src, /const mi = microDe\(texte\); if \(mi\) diffuser\(abonnesPensees, 'micro', j\(mi\)\);/);
  const r0 = src.indexOf("if (p === '/api/jarvis/residuelle'"), route = src.slice(r0, src.indexOf('\n  }\n', r0));
  assert.match(route, /jetonValide\(req\)/);
  assert.match(route, /jugerReveilOreille\(texte\)/);
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
  const c = vm.createContext({ Date, window: {}, journalVoix() {}, sonEnAttente: null, dernierSonRecu: null });
  vm.runInContext(f, c);
  c.recevoirSon({ id: 'e1', debut_ms: 1000 });
  assert.equal(c.sonEnAttente.extrait.id, 'e1', 'en attente, ici comme au téléphone');
  c.sonEnAttente = null;
  c.recevoirSon({ id: 'e1', debut_ms: 1000 });
  assert.equal(c.sonEnAttente, null, 'reçu deux fois (sa réponse et le cockpit) : une seule');
  assert.match(page, /if \(!window\.HakimApp \|\| !window\.HakimApp\.sonJouer\) \{ jouerSonIci\(x, sousSaVoix \? 0\.3 : 0\.6\); return; \}/, 'le Mac le joue');
  assert.match(page, /fetch\(`\/api\/sons\/joue\/\$\{x\.id\}`, \{ headers: \{ 'X-Jeton': jeton\(\) \}/);
  assert.match(page, /window\.HakimApp\.sonEnvoyer\(String\(m\.source\), String\(m\.ref\), url, jeton\(\)\)/, 'l’appli envoie le morceau');
  assert.match(page, /es\.addEventListener\('son', \(ev\) => \{ try \{ recevoirSon\(JSON\.parse\(ev\.data\)\.extrait\); \}/);
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

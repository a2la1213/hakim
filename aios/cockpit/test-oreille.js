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

function oreille({ ouverte = true, dort = false, occupe = false, eveil = 0.4, fermee = false } = {}) {
  const ecrits = [];
  const ctx = { Intl, Date, JSON, Math, Number, String, console: { error() {} }, j: JSON.stringify, NONCE_REVEIL: 'n', OREILLE_MARQUE: 'ton oreille, papa parle encore',
    oreilleReveils: [], corpsReglages: () => ({ oreille: ouverte }), hakimDort: () => dort, cerveauVivant: () => true, occupe: () => occupe,
    cerveau: { enfant: { stdin: { write: (x) => ecrits.push(x) } } }, veilleurEveil: eveil, path: require('node:path'), JARVIS: '/nulle-part',
    lireJson: () => (fermee ? { fermee_jusqua: Date.now() + 60000 } : null), oreilleDejaLu: '', juges: [] };
  ctx.rireDuSubconscient = (x) => ctx.juges.push(x);
  vm.createContext(ctx);
  const i = src.indexOf('const APPEL_OREILLE');
  vm.runInContext(src.slice(i, src.indexOf('function ouvrirOreille(')).replace('let oreilleSilenceJusqua', 'var oreilleSilenceJusqua') + prendre(src, 'function ouvrirOreille(').replace('function ouvrirOreille(', 'this.f = function ('), ctx);
  return { f: ctx.f, ecrits, ctx };
}

test('oreille ouverte : ce que papa a déjà dit le réveille ; fermée, il dort, occupé : rien', () => {
  const o = oreille();
  assert.equal(o.f('Alors écoute, aujourd’hui au travail il s’est passé un truc').ok, true);
  assert.match(o.ecrits[0], /ton oreille, papa parle encore/);
  assert.match(o.ecrits[0], /un mot court/);
  assert.equal(oreille({ ouverte: false }).f('Alors écoute, aujourd’hui au travail').raison, 'oreille fermée');
  assert.equal(oreille({ dort: true }).f('Alors écoute, aujourd’hui au travail').raison, 'il dort');
  assert.equal(oreille({ dort: true }).f('Hakim, réveille-toi, écoute-moi bien').ok, true, 'son nom le réveille');
  assert.equal(oreille({ occupe: true }).f('Alors écoute, aujourd’hui au travail').raison, 'occupé');
});

test('quarante réveils par heure au plus', () => {
  const o = oreille();
  for (let i = 0; i < 45; i++) o.f('Alors écoute, aujourd’hui au travail il s’est passé un truc');
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
  assert.match(page, /\.slice\(-etat\.fenetre\)\.filter\(m => !m\.cache\)/);
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

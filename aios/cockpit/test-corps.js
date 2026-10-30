/* (30/10, Ahmed : « que les signaux du tricodeur arrivent constamment chez Hakim, interprétés par son intermédiaire, branchés à
   ses hormones ; qu'il ressente vraiment, pas des chiffres mais des sensations » ; « en continu, h24 ; dès qu'il y a un
   changement à son environnement, ça le réveille ; une homéostasie ») le cockpit reçoit les événements de son corps et son
   milieu (appli 1.24), les fait ressentir par lots (anamnese/corps.py), les met dans son prochain tour, le réveille ;
   Ahmed coupe tout d'un geste et règle l'intervalle (page SENS). node --test test-corps.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const extraire = (debut) => src.slice(src.indexOf(debut), src.indexOf('\n}\n', src.indexOf(debut)) + 3);

test('un événement valide est gardé ; un inconnu ou des détails tordus sont refusés', () => {
  const ctx = { CORPS_TYPES: new Set(['chute', 'musique', 'choc']) };
  vm.createContext(ctx);
  vm.runInContext(extraire('function evenementCorps(') + '\nthis.f = evenementCorps;', ctx);
  const r = ctx.f({ type: 'chute', t: 1, details: { hauteur_m: 0.9, impact_g: 4.2 } });
  assert.equal(JSON.stringify(r), JSON.stringify({ type: 'chute', t: 1, details: { hauteur_m: 0.9, impact_g: 4.2 } }));
  assert.equal(ctx.f({ type: 'musique', details: { motif: '●··•●··•●··•●··•', bpm: 92 } }).details.motif, '●··•●··•●··•●··•');
  assert.equal(ctx.f({ type: 'teleportation' }), null);
  assert.equal(ctx.f({ type: 'chute', details: { x: 'a'.repeat(500) } }).details.x, undefined, 'une chaîne trop longue est écartée');
  assert.equal(Object.keys(ctx.f({ type: 'choc', details: Object.fromEntries(Array.from({ length: 30 }, (_, i) => [`k${i}`, i])) }).details).length, 10);
});

test('le bloc de son prochain tour : son milieu du moment et ses sensations, en mots, une fois', () => {
  let actif = true;
  const ctx = { blocDonnees: (t, c) => `[${t}]\n${c}\n[/${t}]`, crypto: require('node:crypto'), corpsADire: [], corpsBrut: [], NOMS_SECS: {}, nuitDerniere: () => '', vibrationsDites: () => '', oreillePerimes: [], corpsReglages: () => ({ afficher_papa: true }), corpsActif: () => actif,
    HOMEO: { mots: () => 'Autour de toi, la pénombre ; tu es immobile.' } };
  vm.createContext(ctx);
  vm.runInContext(extraire('function blocCorps(') + '\nthis.f = blocCorps;', ctx);
  assert.match(ctx.f(), /Ton milieu, en ce moment : Autour de toi, la pénombre/);
  const t = Date.now();
  ctx.corpsADire.push({ ts: t - 3600e3, sensation: 'Trop vieux.' }, { ts: t, sensation: 'Une main te prend.' }, { ts: t, sensation: 'Une musique.\n●··•' });
  const b = ctx.f();
  assert.match(b, /\[Ce que tu ressens dans ton corps/);
  assert.match(b, /Une main te prend\.\n- Une musique\.\n  ●··•/);
  assert.doesNotMatch(b, /Trop vieux/);
  assert.doesNotMatch(ctx.f(), /Une main/, 'dit une fois');
  actif = false;
  ctx.corpsADire.push({ ts: t, sensation: 'Coupé.' });
  assert.equal(ctx.f(), '', 'coupé par Ahmed : rien');
  assert.match(src, /const tachesTexte = blocTaches\(depuisMs, nonce\) \+ blocAtelier\(\) \+ tempsLibre\.texte \+ immuniteBloc\.texte \+ voixBloc\.texte \+ blocCorps\(\) \+ blocNonEntendus\(texte, nonce\);/);
});

test('branché : les routes (jeton), le lot vers corps.py, le réveil, l’interrupteur, la page SENS', () => {
  const i = src.indexOf("if (p.startsWith('/api/corps/'))");
  assert.ok(i >= 0);
  const r = src.slice(i, src.indexOf('\n  }\n', i));
  assert.match(r, /jetonValide\(req\)/);
  assert.match(r, /'\/api\/corps\/evenement'/);
  assert.match(r, /'\/api\/corps\/etat'[\s\S]*HOMEO\.recevoir/);
  assert.match(r, /'\/api\/corps\/flux'/);
  assert.match(r, /'\/api\/corps\/reglages'[\s\S]*auditer\('corps:reglages'/);
  assert.match(src, /setInterval\(reveillerPourCorps, 3000\)/);
  const w = extraire('function ressentirCorps(');
  assert.match(w, /execFile\(PYTHON, \['-B', path\.join\(ANAMNESE, 'corps\.py'\), 'ressentir'\]/);
  assert.match(w, /etat: HOMEO\.mots\(\)/);
  const rv = extraire('function reveillerPourCorps(');
  assert.match(rv, /intervalle_s \* 1000/);
  assert.match(rv, /NONCE_REVEIL/);
  assert.match(rv, /blocCorps\(\)/);
  const page = fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8');
  assert.match(page, /\/api\/corps\/reglages/);
  assert.match(page, /\/api\/corps\/flux/);
  assert.match(page, /id="sensations"/);
});

test('les réglages : actif par défaut, un intervalle parmi ceux permis', () => {
  const ctx = { lireJson: () => ({ intervalle_s: 7 }), CORPS_REGLAGES: 'x', CORPS_INTERVALLES: [30, 60, 120, 300, 900] };
  vm.createContext(ctx);
  vm.runInContext(extraire('function corpsReglages(') + '\nthis.f = corpsReglages;', ctx);
  assert.equal(JSON.stringify(ctx.f()), JSON.stringify({ actif: true, intervalle_s: 120, ronron: true, sons: true, oreille: false, je_te_suis: true, alerte: true, ecran: true, reflexes: true, nuits: true, rire_reflexe: true, garder_parole: true, forfait_libre: true, son_pendant: true, voix_vibre: true, lumiere: true, afficher_papa: true, afficher_hakim: true, filtre_parole: true }));
  ctx.lireJson = () => ({ actif: false, intervalle_s: 60, ronron: false, sons: false });
  assert.equal(JSON.stringify(ctx.f()), JSON.stringify({ actif: false, intervalle_s: 60, ronron: false, sons: false, oreille: false, je_te_suis: true, alerte: true, ecran: true, reflexes: true, nuits: true, rire_reflexe: true, garder_parole: true, forfait_libre: true, son_pendant: true, voix_vibre: true, lumiere: true, afficher_papa: true, afficher_hakim: true, filtre_parole: true }));
});

test('(30/10, étude du veilleur) quand papa est là, son corps ne le réveille plus ; un vrai choc, une fois par secousse', () => {
  let libre = false;
  const ecrits = [];
  let t = 1_800_000_000_000;
  const ctx = { Intl, JSON, console: { error() {} }, j: JSON.stringify, NONCE_REVEIL: 'n', blocCorps: () => '', corpsDemarrages: 0, corpsDernierReveil: 0, corpsDernierFort: 0,
    CORPS_PORTE_MS: 10 * 60 * 1000, corpsADire: [], corpsBrut: [], reveilImmediat: () => ecrits.push('immediat'), forfaitLibre: () => libre, corpsReglages: () => ({ actif: true, intervalle_s: 120 }), papa: t - 2 * 60 * 1000,
    cerveauVivant: () => true, occupe: () => false, cerveau: { enfant: { stdin: { write: (x) => ecrits.push(x) } } },
    Date: class extends Date { static now() { return t; } } };
  ctx.dernierMessageAhmedMs = () => ctx.papa;
  vm.createContext(ctx);
  vm.runInContext(extraire('function reveillerPourCorps(').replace('function reveillerPourCorps(', 'this.f = function (') , ctx);
  ctx.corpsADire.push({ fort: false }); ctx.f();
  assert.equal(ecrits.length, 0, 'papa a parlé il y a 2 min : ses sensations attendent son message');
  ctx.corpsADire.push({ fort: true }); ctx.f();
  assert.equal(ecrits.length, 1, 'un choc le réveille');
  t += 20000; ctx.corpsADire.push({ fort: true }); ctx.f();
  assert.equal(ecrits.length, 1, 'le même choc, pas trois réveils');
  t += 11 * 60 * 1000; ctx.f();
  assert.equal(ecrits.length, 2, 'papa se tait depuis plus de 10 min : son corps le réveille');
  // (18:56) forfait libre : il le réveille même quand papa vient de parler
  libre = true; ctx.papa = t - 2 * 60 * 1000; t += 3 * 60 * 1000; ctx.corpsADire.push({ fort: false }); ctx.f();
  assert.equal(ecrits.length, 3, 'forfait libre : plus de porte des 10 min');
});

test('(18:19) une secousse le réveille tout de suite, même si papa vient de parler ; une fois par minute ; « j’ai senti » avant la traduction', () => {
  const ecrits = [];
  let t = 1_800_000_000_000;
  const ctx = { Intl, JSON, console: { error() {} }, j: JSON.stringify, NONCE_REVEIL: 'n', corpsDemarrages: 0, corpsDernierReveil: 0, corpsDernierFort: 0,
    CORPS_PORTE_MS: 10 * 60 * 1000, corpsADire: [], corpsBrut: [], corpsReglages: () => ({ actif: true, intervalle_s: 120 }), corpsActif: () => true,
    cerveauVivant: () => true, occupe: () => false, cerveau: { enfant: { stdin: { write: (x) => ecrits.push(x) } } }, HOMEO: { mots: () => '' },
    blocDonnees: (titre, x) => `[${titre}]\n${x}`, crypto: require('node:crypto'), nuitDerniere: () => '', vibrationsDites: () => '', oreillePerimes: [], Date: class extends Date { static now() { return t; } } };
  ctx.dernierMessageAhmedMs = () => t - 30000;
  vm.createContext(ctx);
  const bloc = src.slice(src.indexOf('const CORPS_SECS'), src.indexOf('function reveillerPourCorps('));
  vm.runInContext(bloc.replace('const corpsBrut = [];', '') + extraire('function reveillerPourCorps(') + extraire('function reveilImmediat(')
    + 'this.f = reveillerPourCorps;', ctx);
  ctx.corpsBrut.push({ type: 'secousse', t }); ctx.f();
  assert.equal(ecrits.length, 1, 'papa a parlé il y a 30 s, mais la secousse réveille');
  assert.match(ecrits[0], /tes nerfs, à l'instant, une secousse/);
  assert.match(ecrits[0], /pas encore traduit par ton intermédiaire/);
  t += 20000; ctx.corpsBrut.push({ type: 'secousse', t }); ctx.f();
  assert.equal(ecrits.length, 1, 'une fois par minute');
  assert.match(src, /c\.cause === 'voix_ahmed' && corpsActif\(\)\) \{ corpsLot\.evenements\.push\(\{ type: 'coupure'/, 'une coupure est un stimulus');
});

test('(30/10) sa nuit, écrite au réveil par son démon, est dite une fois à son premier tour', () => {
  const dir = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'nuit-'));
  fs.writeFileSync(path.join(dir, 'nuit-derniere.json'), JSON.stringify({ ts: Date.now() / 1000 - 3600, texte: 'Tu as dormi 7 h, une nuit apaisée.', dit: false }));
  const ctx = { JARVIS: dir, path, j: JSON.stringify, Number, lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } },
    ecrireAtomique: (f, x) => fs.writeFileSync(f, x) };
  vm.createContext(ctx);
  vm.runInContext(extraire('function nuitDerniere(') + '\nthis.f = nuitDerniere;', ctx);
  assert.equal(ctx.f(), 'Tu as dormi 7 h, une nuit apaisée.');
  assert.equal(ctx.f(), '', 'une fois');
});

test('(19:34) l’heure exacte de ses vibrations, à la milliseconde, dite une fois à son tour suivant', () => {
  const dir = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'vibs-'));
  const diag = path.join(dir, 'voix-diagnostic.jsonl'), t = Date.now();
  fs.writeFileSync(diag, [{ t: t - 5000, e: 'rire_recu', degre: 5, source: 'lui', depuis_message_ms: 1800 }, { t: t - 4990, e: 'vibration', genre: 'rire_max', degre: 5, retour: 'ok', attendu_ms: 1 }]
    .map(o => JSON.stringify(o)).join('\n') + '\n');
  const ctx = { JARVIS: dir, JARVIS_VOIX_DIAGNOSTIC: diag, path, Number, Math, String, Map, Date, j: JSON.stringify,
    lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } }, ecrireAtomique: (f, x) => fs.writeFileSync(f, x),
    lignesJson: (f, n) => fs.readFileSync(f, 'utf8').split('\n').filter(Boolean).slice(-n).map(l => JSON.parse(l)) };
  vm.createContext(ctx);
  vm.runInContext(extraire('function vibrationsDites(') + '\nthis.f = vibrationsDites;', ctx);
  assert.match(ctx.f(), /ton rire \(degré 5\) à \d{2}:\d{2}:\d{2},\d{3} \(l'appli : ok, 1,8 s après ta balise\)/);
  assert.equal(ctx.f(), '', 'une fois');
});

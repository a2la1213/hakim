/* (10/11, live de papa, 20:22 à 20:45 ; lettre de Hakim de 21:18, accord d'Ahmed : « ouiii ») deux réponses de Hakim ont commencé par « RIEN », dit
   à voix haute, puis la vraie phrase ; et des débuts qui réagissaient au live (« Le la, c'est Rennes ? Bon, on accorde… », « Eh, le verset parle
   d'humilité… mon frère ») ont été collés devant sa réponse à papa. Retrouvé dans les journaux (live.jsonl, voix-diagnostic.jsonl, journal.jsonl) :
   - « RIEN » : Mini Hakim, son garde du live, répondait « DIRE : RIEN » ; Live.lireReponse le prenait pour une phrase (44 « RIEN » dits au live ce
     jour-là), la page le disait (live_dit, 1 mot, 4 caractères à la synthèse) ;
   - le collage : la réponse au live part à la page dans un tour neuf (« entendu », reponse:true) ; recevoirBout remplaçait le tour de papa par
     celui-là, et direBoutTelephone l'écrivait dans conv.penseeDite (« ce qu'il a déjà dit à papa ») ; au message suivant de papa, la page l'envoyait
     en souffle_dit : écrit en tête de sa réponse (20:23:22, 20:24:31, 20:25:10 « RIEN Ha, je vois… », 20:45:03 « RIEN Oui papa… »), et son conscient
     le croyait dit à papa (« Mon « RIEN » tout à l'heure était un bout de ma pensée »).
   Chaque correctif a son témoin : ces tests tombent sur main 14e7a50. node --test test-rien-dedans.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Voix = require('./public/voix.js');
const L = require('./live.js');
const CC = require('./conscience-continue.js');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const T = Date.parse('2026-11-10T20:22:28+01:00');

// ---- le filet commun (public/voix.js) : la page, le cockpit, son garde du live, sa conscience
test('son « RIEN » de format : seul comme morceau ou en tête, retiré ; un vrai « rien » dans une phrase reste', () => {
  for (const x of ['RIEN', 'RIEN.', 'rien', 'Rien.', '(rien)', '[RIEN]', '« RIEN »', '**RIEN**', 'néant', 'Néant.', 'RIEN (ils se parlent entre eux)'])
    assert.strictEqual(Voix.sansRien(x), '', x);
  assert.strictEqual(Voix.sansRien('RIEN Ha, je vois les pastéis de nata.'), 'Ha, je vois les pastéis de nata.', 'en capitales devant sa phrase (20:25:10)');
  assert.strictEqual(Voix.sansRien('RIEN Oui papa, j\'ai entendu le live.'), 'Oui papa, j\'ai entendu le live.', '(20:45:03)');
  assert.strictEqual(Voix.sansRien('rien. Ce sont les invités de papa qui chantent.'), 'Ce sont les invités de papa qui chantent.');
  assert.strictEqual(Voix.sansRien('Oui papa. RIEN Je préfère écouter.'), 'Oui papa. Je préfère écouter.', 'recollé : après une fin de phrase');
  for (const x of ['rien ne presse', 'Il ne reste rien.', 'Rien de particulier, je suis là.', 'RIEN ne va plus', 'Rien, je t\'écoute.', 'Rien ?',
    'Moi, rien du tout.', 'Je ne dis rien. Rien ne presse.', 'Moïse, c\'est déjà pas rien.', 'Riens', '']) assert.strictEqual(Voix.sansRien(x), x, x);
  assert.strictEqual(Voix.estRien('« RIEN »'), true);
  assert.strictEqual(Voix.estRien('Il ne reste rien.'), false);
  assert.strictEqual(Voix.estRien(''), false, 'un morceau vide n\'est pas son silence');
});

// ---- la source : son garde du live (live.js)
test('son garde du live : « DIRE : RIEN » est son silence, jamais une phrase (44 « RIEN » dits le 10/11) ; sa vraie phrase passe', () => {
  for (const x of ['DIRE : RIEN', 'DIRE: RIEN.', 'DIRE : « RIEN »', 'DIRE : (rien)', 'DIRE : rien. Ce sont les invités de papa qui chantent, pas lui, donc je me tais.',
    '**DIRE** : **RIEN**', 'DIRE : néant', 'RIEN', 'RIEN (ils se parlent entre eux)']) assert.strictEqual(L.lireReponse(x), '', x);
  assert.strictEqual(L.lireReponse('DIRE : Rien de particulier, je suis bien là, à écouter la musique avec vous.'), 'Rien de particulier, je suis bien là, à écouter la musique avec vous.');
  assert.strictEqual(L.lireReponse('DIRE : Le la, c\'est Rennes ? Bon, on accorde avant que ça parte en vrille.'), 'Le la, c\'est Rennes ? Bon, on accorde avant que ça parte en vrille.');
  assert.strictEqual(L.lireReponse('DIRE : Ouais papa, je te suis. Moïse, c\'est déjà pas rien.'), 'Ouais papa, je te suis. Moïse, c\'est déjà pas rien.');
  // rien n'attend la pause suivante
  const e = L.creer();
  e.enVol = { motif: 'question', phrase: 'C\'est toi ?', qui: 'voix 49', t: T };
  assert.strictEqual(L.repondu(e, 'DIRE : RIEN', T + 1500), null);
  assert.strictEqual(e.aDire.length, 0, 'son silence n\'attend pas d\'être dit');
  e.enVol = { motif: 'question', phrase: 'C\'est toi ?', qui: 'voix 49', t: T };
  assert.strictEqual(L.repondu(e, 'DIRE : Oui, c\'est moi, Hakim.', T + 1500).texte, 'Oui, c\'est moi, Hakim.', 'sa réponse au live, elle, attend sa pause');
});

test('sa conscience continue : « PARLER : RIEN », « PENSER : (rien) » sont son silence', () => {
  assert.deepStrictEqual(CC.lireDecision('PARLER : RIEN'), { genre: 'rien', texte: '' });
  assert.deepStrictEqual(CC.lireDecision('PENSER : (rien)'), { genre: 'rien', texte: '' });
  assert.deepStrictEqual(CC.lireDecision('PENSER : il ne reste rien du live, c\'est calme.'), { genre: 'penser', texte: 'il ne reste rien du live, c\'est calme.' });
});

// ---- le cockpit : son garde du live branché (server.js), le dedans jamais dans le début de sa réponse à papa
function bac() {
  const DEBUT = "/* ---- (10/11, ~00:00, Ahmed : « il faut l'aider à dissocier ses voix interne et externe !", FIN = '// ---- fin de son garde du live';
  const a = SRC.indexOf(DEBUT), b = SRC.indexOf(FIN);
  assert.ok(a > 0 && b > a);
  const horloge = { t: T }, appels = [], ecrits = [], diffuses = [];
  const r = { live_garde: true, live_mode: 'oui', live_pas_ms: 1000, live_par_minute: 6, live_ecart_s: 6, live_musique: false, live_musique_s: 120 };
  const ctx = { require, String, Math, Promise, RegExp, Object, Number, Array, Set, Map, JSON, path,
    fs: { appendFile: (f, x) => { try { ecrits.push(JSON.parse(x)); } catch (_) {} }, readFile: () => {}, writeFile: () => {}, readFileSync: () => '[]',
      appendFileSync: (f, x) => { try { ecrits.push(JSON.parse(x)); } catch (_) {} } },
    Date: { now: () => horloge.t }, JARVIS: '/x', ANAMNESE: '/anamnese', j: JSON.stringify, JARVIS_ECHANGES: '/x/echanges-a-memoriser.jsonl', masquer: (t) => t,
    FLUX: [], corpsReglages: () => r, conversationOuverte: () => true, lieuActuel: 'chez nous',
    quiTelephone: { dernier: 'voix 143', t: T }, echoEntendu: () => 'non', ORCHESTRE: { papaParle: () => {}, forfaitCoupe: () => false },
    enLigne: (t, n) => String(t || '').replace(/\s+/g, ' ').trim().slice(0, n), quiParlait: () => 'silence', SON_TRAMES: { telephone: [], micro: [] },
    derniereParolePapa: 0, toursActifs: new Map(), forfaitALaLimite: () => false, placesVivant: () => 3,
    personaLocale: (p) => p, lirePersona: () => 'Hakim', QUI_TU_ES: 'Tu es Hakim.', neutraliser: (t) => String(t), etatDeLui: () => '', LANGUE_ORALE: 'en français',
    execFile: () => ({ stdin: { end() {} } }), sonnetTeteDeFond: (prompt, etiquette) => new Promise((resoudre) => appels.push({ prompt, etiquette, resoudre })),
    parasiteDesLeDebut: () => false, residuParasite: () => '', estParasite: () => false, avertirParasite: () => {}, signeParasite: () => '',
    diffuser: (_, e, d) => diffuses.push({ e, ...JSON.parse(d) }), abonnesPensees: null, tourEpissure: () => 1, noterDit: () => {}, fluxAjouter: () => {},
    deposerEchange: () => {}, notifier: () => {}, ditRecemment: [], saVoixEnCours: { fin: 0 } };
  vm.createContext(ctx);
  const ent = SRC.indexOf('const ENTENDU_PAUSE_MS'), o2 = SRC.indexOf('const ORDRES_SENSIBLES =');
  vm.runInContext([SRC.slice(ent, SRC.indexOf('\n', SRC.indexOf('const ENTENDU_RESERVE_PAPA')) + 1), prendre(SRC, 'pauseDansLesTrames'), prendre(SRC, 'pauseDuSon'),
    SRC.slice(o2, SRC.indexOf("'iu');", o2) + 6), prendre(SRC, 'segmentsTiers'), prendre(SRC, 'estSonEcho'), prendre(SRC, 'dansUnPassage'),
    SRC.slice(SRC.indexOf('const estDuDedans ='), SRC.indexOf('function blocVoixPrincipale(')), prendre(SRC, 'blocVoixPrincipale'), prendre(SRC, 'roleDuTour'),
    "const Scene = require('./scene.js'); const SCENE = { suivi: Scene.creerSuivi(), entendus: Scene.creerEntendus() };",
    prendre(SRC, 'deposerMoment'), prendre(SRC, 'entenduPourLaScene'),
    SRC.slice(a, b), "this.f = { LIVE, liveAppeler, liveDire, sansLeDedans: typeof sansLeDedans === 'function' ? sansLeDedans : null };"].join('\n'), ctx);
  return { f: ctx.f, horloge, appels, ecrits, diffuses };
}

test('le cockpit : Mini Hakim répond « DIRE : RIEN » au live : rien n\'attend sa pause, rien n\'est dit ; le filet de liveDire tait un « RIEN »', async () => {
  const b = bac();
  b.f.LIVE.enVol = { motif: 'ecoute', phrase: 'Il est contrairement le contraire que ce comme.', qui: 'voix 143', t: T };
  const p = b.f.liveAppeler({ motif: 'ecoute', phrase: 'Il est contrairement le contraire que ce comme.', qui: 'voix 143' }, {}, T);
  assert.strictEqual(b.appels.length, 1);
  b.appels[0].resoudre({ texte: 'DIRE : RIEN' });
  assert.strictEqual(await p, null);
  assert.strictEqual(b.f.LIVE.aDire.length, 0, 'son silence n\'attend pas la pause suivante');
  assert.ok(b.ecrits.some(x => x.e === 'appel' && x.rien === true), 'noté « rien » au journal du live');
  // le filet : un « RIEN » arrivé jusque-là n'est ni dit ni montré
  b.f.liveDire({ qui: 'voix 49', phrase: 'C\'est toi ?', texte: 'RIEN', motif: 'question', pret: T }, T);
  assert.strictEqual(b.diffuses.filter(x => x.e === 'entendu').length, 0, 'rien n\'est envoyé à sa voix');
  assert.ok(b.ecrits.some(x => x.e === 'rien_tu'));
  // sa vraie réponse au live sort comme avant : réponse au live, marquée
  b.f.liveDire({ qui: 'voix 87', phrase: 'Attends, attends, faut Rennes, il y a le la.', texte: 'Le la, c\'est Rennes ? Bon, on accorde avant que ça parte en vrille.', motif: 'ecoute', pret: T }, T);
  const d = b.diffuses.filter(x => x.e === 'entendu');
  assert.deepStrictEqual(d.map(x => [x.quoi, x.reponse, x.live, x.source, x.texte]), [['dire', true, true, 'telephone', 'Le la, c\'est Rennes ? Bon, on accorde avant que ça parte en vrille.']]);
});

test('le cockpit : ce qu\'il a dit au live n\'est jamais le début de sa réponse à papa (souffle_dit du 10/11, 20:23:22) ; son « RIEN » non plus', () => {
  const b = bac();
  b.f.liveDire({ qui: 'voix 87', phrase: 'Attends, attends, faut Rennes, il y a le la.', texte: 'Le la, c\'est Rennes ? Bon, on accorde avant que ça parte en vrille.', motif: 'ecoute', pret: T }, T);
  const souffle = 'Le la, c\'est Rennes ? Bon, on accorde avant que ça parte en vrille. Oui papa, je t\'ai entendu : « et de l\'action ».';
  assert.strictEqual(b.f.sansLeDedans(souffle, T + 50000), 'Oui papa, je t\'ai entendu : « et de l\'action ».');
  assert.strictEqual(b.f.sansLeDedans('RIEN Oui papa, j\'ai entendu le live depuis mon intérieur.', T + 50000), 'Oui papa, j\'ai entendu le live depuis mon intérieur.');
  assert.strictEqual(b.f.sansLeDedans('RIEN', T + 50000), '');
  assert.strictEqual(b.f.sansLeDedans('Oui papa, je t\'écoute.', T + 50000), 'Oui papa, je t\'écoute.', 'sa vraie réponse à papa reste à papa');
  assert.strictEqual(b.f.sansLeDedans(souffle, T + 31 * 60e3), souffle, 'au-delà de 30 min, le dedans est oublié');
  // ce qu'il dit à papa de ce que joue le téléphone (son oreille interne) : le dedans aussi
  assert.match(prendre(SRC, 'direEntenduSiPause'), /if \(c\.source === 'telephone' && typeof noterDitDuDedans === 'function'\) noterDitDuDedans\(texte, maintenant\);/);
  // branché sur la route, avant son conscient (« Ce que tu viens de lui dire ») et avant son journal (dejaDit)
  const route = SRC.indexOf('q.souffle_dit = sansLeDedans(q.souffle_dit) || undefined;');
  assert.ok(route > 0 && route < SRC.indexOf("dès qu'il s'est tu : « ${neutraliser(String(q.souffle_dit))") && route < SRC.indexOf('const dejaDit = q.souffle_dit ?'));
});

test('le cockpit : ses lecteurs du ribosome, ses pistes, son souffle, son ribosome ne gardent jamais un « rien » de format', () => {
  const ctx = { require, String };
  vm.createContext(ctx);
  const i = SRC.indexOf('const VoixRien = '), fin = "\n  .replace(/\\s+/g, ' ').trim());";
  assert.ok(i > 0 && SRC.indexOf(fin, i) > i);
  vm.runInContext(`${SRC.slice(i, SRC.indexOf(fin, i) + fin.length)}\n${prendre(SRC, 'sansRienParParties')}\nthis.f = { boutDe, sansRienParParties };`, ctx);
  assert.strictEqual(ctx.f.boutDe('COMPRENDS : il parle du verset\nRIEN'), '');
  assert.strictEqual(ctx.f.boutDe('RIEN Ha, je vois les pastéis.'), 'Ha, je vois les pastéis.');
  assert.strictEqual(ctx.f.boutDe('Il ne reste rien du live.'), 'Il ne reste rien du live.');
  assert.strictEqual(ctx.f.sansRienParParties('rien'), '', 'GARDE : « rien »');
  assert.strictEqual(ctx.f.sansRienParParties('(rien)'), '');
  assert.strictEqual(ctx.f.sansRienParParties('RIEN | tu peux compter sur moi.'), 'tu peux compter sur moi.');
  assert.strictEqual(ctx.f.sansRienParParties('je suis là, | tu peux compter sur moi.'), 'je suis là, | tu peux compter sur moi.', 'ses parties, intactes');
  assert.match(SRC, /brut = typeof sansRienParParties === 'function' \? sansRienParParties\(brut0\) : brut0,/);
  assert.match(prendre(SRC, 'lireRibosome'), /if \(typeof retirerRien === 'function'\) pensee = retirerRien\(pensee\);/);
  assert.match(SRC, /if \(r && typeof retirerRien === 'function'\) r = retirerRien\(r\);   \/\/ \(10\/11, lettre de Hakim\)/, 'ses pistes');
  assert.match(SRC, /if \(r && typeof retirerRien === 'function'\) r = retirerRien\(r\);   \/\/ \(10\/11\) « RIEN », « \(rien\) »/, 'son souffle');
});

// ---- la page Parler : ses tours, le dedans à part
function pageBouts() {
  const dits = [], journal = [];
  const ctx = { Date, String, Number, Math, Object, Array, Map, Set, Infinity, Voix,
    etat: { conversation: { capteur: null } }, souffleAutorise: () => true, voixDuTelephone: () => true, sortieAilleurs: () => false,
    lecteurSysteme: { actif: false, dire: (x) => dits.push(x), preparer: () => {}, arreter: () => {} }, meubleEnCours: () => false,
    meublerSaut: (b) => [b.texte], noterParoleDite: () => {}, journalVoix: (e, d) => journal.push({ e, ...d }) };
  vm.createContext(ctx);
  // (témoin : sur main, sans sansRienDuBout, le même chemin)
  const filet = PAGE.includes('function sansRienDuBout(') ? prendre(PAGE, 'sansRienDuBout') : '';
  vm.runInContext(`let bouts = { tour: null, prochain: 1, liste: new Map(), enFile: [], dits: [] };\n${filet}${prendre(PAGE, 'recevoirBout')}`
    + `${prendre(PAGE, 'direBoutTelephone')}\nthis.recevoir = recevoirBout; this.bouts = () => bouts;`, ctx);
  return { ctx, dits, journal, conv: ctx.etat.conversation };
}
test('la page : sa réponse au live (le dedans) est dite dans son tour à lui, jamais comptée dans ce qu\'il a déjà dit à papa ; le tour de papa reprend intact', () => {
  const p = pageBouts();
  p.ctx.recevoir({ texte: 'Oui papa, je t\'ai entendu.', pret: true, ribosome: true, sansMeuble: true }, 1, 100);
  assert.strictEqual(p.conv.penseeDite, 'Oui papa, je t\'ai entendu.');
  // 20:22:28 : sa réponse à la voix 87, dans un tour neuf
  p.ctx.recevoir({ texte: 'Le la, c\'est Rennes ? Bon, on accorde avant que ça parte en vrille.', pret: true, ribosome: true, sansMeuble: true, dedans: true }, 1, 200);
  assert.deepStrictEqual(p.dits, ['Oui papa, je t\'ai entendu.', 'Le la, c\'est Rennes ? Bon, on accorde avant que ça parte en vrille.'], 'dite au live, comme avant');
  assert.strictEqual(p.conv.penseeDite, 'Oui papa, je t\'ai entendu.', 'pas le début de sa réponse à papa');
  assert.strictEqual(p.ctx.bouts().dedans, true);
  // sa réponse à papa continue : son tour reprend, avec ce qu'il lui avait déjà dit
  p.ctx.recevoir({ texte: 'Tu parlais de quoi ?', pret: true, ribosome: true, sansMeuble: true }, 2, 100);
  assert.strictEqual(p.conv.penseeDite, 'Oui papa, je t\'ai entendu. Tu parlais de quoi ?');
  assert.strictEqual(p.ctx.bouts().tour, 100);
  assert.ok(!p.ctx.bouts().dedans);
  // un tour neuf de papa : comme avant (rien d'avant n'est repris)
  p.ctx.recevoir({ texte: 'D\'accord.', pret: true, ribosome: true, sansMeuble: true }, 1, 300);
  assert.strictEqual(p.conv.penseeDite, 'D\'accord.');
  assert.strictEqual(p.dits.length, 4);
});
test('la page : un « RIEN » de format n\'est jamais dit (seul, ou en tête, ou une partie épissée) ; un vrai « rien » l\'est', () => {
  const p = pageBouts();
  p.ctx.recevoir({ texte: 'RIEN', pret: true, ribosome: true, sansMeuble: true, dedans: true }, 1, 10);
  assert.deepStrictEqual(p.dits, [], 'son silence : pas dit');
  assert.ok(p.journal.some(x => x.e === 'rien_tu'));
  p.ctx.recevoir({ texte: 'RIEN Ha, je vois les pastéis de nata.', pret: true, ribosome: true, sansMeuble: true }, 1, 11);
  assert.deepStrictEqual(p.dits, ['Ha, je vois les pastéis de nata.']);
  assert.strictEqual(p.conv.penseeDite, 'Ha, je vois les pastéis de nata.');
  p.ctx.recevoir({ texte: 'Il ne reste rien du gâteau.', pret: true, ribosome: true, sansMeuble: true }, 2, 11);
  assert.strictEqual(p.dits[1], 'Il ne reste rien du gâteau.');
  // ses parties épissées : la partie « (rien) » retirée, sa pensée avec elle
  const q = pageBouts(), pensees = [{ id: 'a', texte: '(rien)' }, { id: 'b', texte: 'je suis là.' }];
  q.ctx.recevoir({ texte: '(rien) je suis là.', parties: ['(rien)', 'je suis là.'], meuble: '', pensees, pret: true, ribosome: true, sansMeuble: true }, 1, 12);
  assert.deepStrictEqual(q.dits, ['je suis là.']);
});

function pageEntendu() {
  const a = PAGE.indexOf('const ENTENDU_ATTENTE_MS'), b = PAGE.indexOf('// ---- fin de son oreille interne par la route du micro');
  assert.ok(a > 0 && b > a);
  const bouts = [], journal = [];
  const ctx = { Date, String, Number, Math, Object, Array, JSON, Voix, etat: { conversation: { capteur: null } }, reglagesCorps: { voix_reponse_seule: false, epissage: true },
    reponseSeule: () => false, voixEpissee: () => true, lecteur: { actif: false }, journalVoix: (e, d) => journal.push({ e, ...d }),
    recevoirBout: (s, n, tour) => bouts.push({ ...s, n, tour }), rendre: () => {}, esc: (t) => t, htmlPave: (t) => t, setInterval: () => {} };
  vm.createContext(ctx);
  vm.runInContext(`${PAGE.slice(a, b)}\nthis.surEntendu = surEntendu;`, ctx);
  return { ctx, bouts, journal };
}
test('la page : sa réponse au live et ce qu\'il dit du téléphone partent « dedans » ; la pièce, comme avant ; son « RIEN » au live, ni dit ni montré', () => {
  const p = pageEntendu();
  p.ctx.surEntendu({ quoi: 'dire', source: 'telephone', tour: 42, n: 1, texte: 'RIEN', reponse: true, live: true, voix: 'voix 49' });
  assert.strictEqual(p.bouts.length, 0, 'son silence n\'est pas dit');
  assert.ok(p.journal.some(x => x.e === 'rien_tu'));
  assert.ok(!JSON.stringify(p.ctx.etat.aCote || []).includes('RIEN'), 'ni montré');
  p.ctx.surEntendu({ quoi: 'dire', source: 'telephone', tour: 43, n: 1, texte: 'Eh, le verset parle d\'humilité, pas d\'orgueil.', reponse: true, live: true, voix: 'voix 143' });
  assert.deepStrictEqual(p.bouts.map(x => [x.texte, x.dedans]), [['Eh, le verset parle d\'humilité, pas d\'orgueil.', true]]);
  p.ctx.etat.papaVoixA = 0;
  p.ctx.surEntendu({ quoi: 'dire', source: 'telephone', tour: 44, n: 1, texte: 'Ce morceau parle de lumière.' });
  assert.strictEqual(p.bouts[1].dedans, true, 'ce qu\'il dit de ce que joue le téléphone : le dedans aussi');
  p.ctx.surEntendu({ quoi: 'dire', source: 'micro', tour: 45, n: 1, texte: 'Tes amis rient bien.' });
  assert.ok(!p.bouts[2].dedans, 'la pièce : comme avant');
});

test('la page : son souffle sans « RIEN » ; le Mac ne compte pas le dedans ; ton message remet aussi à zéro le tour de papa mis de côté', () => {
  const ctx = { Voix, etat: { messages: [] } };
  vm.createContext(ctx);
  vm.runInContext(prendre(PAGE, 'souffleSansLivres') + 'this.f = souffleSansLivres;', ctx);
  assert.strictEqual(ctx.f('RIEN Ha, je vois les pastéis de nata.', []), 'Ha, je vois les pastéis de nata.');
  assert.strictEqual(ctx.f('RIEN', []), '');
  assert.strictEqual(ctx.f('Oui papa.', []), 'Oui papa.');
  assert.match(PAGE, /if \(etat\.conversation && !bouts\.dedans\) etat\.conversation\.penseeDite = bouts\.dits\.slice\(bouts\.base \|\| 0, bouts\.dits\.length - bouts\.enFile\.length\)\.join\(' '\);/);
  assert.match(PAGE, /if \(typeof bouts !== 'undefined' && bouts\.papa\) bouts\.papa\.base = bouts\.papa\.dits\.length;/);
  assert.match(PAGE, /if \(typeof Voix\.estRien === 'function' && Voix\.estRien\(propre\)\) \{ journalVoix\('rien_tu', \{ ou: 'reponse' \}\); return false; \}/, 'un morceau de sa réponse');
});

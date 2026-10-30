/* (30/10, 17:21, Ahmed : « comme Bumblebee » ; 17:09 : « la force de vibration reliée à ton cœur ») ses sons et la force de
   ses vibrations. node --test test-sons.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (s, debut) => s.slice(s.indexOf(debut), s.indexOf('\n}\n', s.indexOf(debut)) + 3);

function serveur(lignes) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sons-'));
  const f = path.join(dir, 'sons.jsonl');
  fs.writeFileSync(f, lignes.map(o => JSON.stringify(o)).join('\n') + '\n');
  const ctx = { SONS: f, Math, lignesJson: (x, n) => fs.readFileSync(x, 'utf8').split('\n').filter(Boolean).slice(-n).map(l => JSON.parse(l)) };
  vm.createContext(ctx);
  const regex = src.slice(src.indexOf('const BALISE_SON'), src.indexOf('\n', src.indexOf('const BALISE_SON')));
  vm.runInContext(regex + '\n' + prendre(src, 'function lireSons(') + prendre(src, 'function choisirSon(')
    + '\nthis.lire = lireSons; this.choisir = choisirSon;', ctx);
  return ctx;
}
const ex = (id, extra) => ({ type: 'extrait', id, source: 'musique', ref: '12', titre: 't', debut_ms: 0, fin_ms: 3000, ...extra });

test('papa marque, Hakim nomme, oublie : le cockpit lit le même journal que lui', () => {
  const s = serveur([ex('e1'), ex('e2'), { type: 'nom', extrait: 'e1', nom: 'victoire', sens: 'on a réussi', emotion: 'joie' },
    { type: 'nom', extrait: 'e2', nom: 'fou_rire', emotion: 'rire' }, ex('e3'), { type: 'oubli', extrait: 'e3' }]);
  assert.deepEqual(s.lire().map(x => [x.id, x.nom, x.emotion]), [['e1', 'victoire', 'joie'], ['e2', 'fou_rire', 'rire']]);
  assert.equal(s.choisir('[[son: victoire]] Bravo papa', null, 0).id, 'e1', 'par son nom');
  assert.equal(s.choisir('Bravo', 'joie', 0).id, 'e1', 'avec son impulsion');
  assert.equal(s.choisir('mdrrr', null, 3).id, 'e2', 'avec son rire');
  assert.equal(s.choisir('Bonjour', null, 0), null, 'rien de dit, rien de joué');
  assert.equal(s.choisir('[[son: inconnu]] hm', 'calme', 0), null);
});

test('branché : balise cachée, route des extraits (8 s au plus), réglage, son après sa voix, micro sourd, force de ses vibrations', () => {
  assert.match(src, /envoyer\(\{ t: 'son', extrait:/);
  assert.match(src, /SON_MAX_MS = 8000/);
  assert.match(src, /sons: r\.sons !== false/);
  assert.match(src, /type: 'son', t: Date\.now\(\)/, 'son son passe aussi par son intermédiaire');
  assert.match(page, /sourd: \(\) => Date\.now\(\) < sonJusqua/);
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'conversation.js'), 'utf8'), /if \(o\.sourd && o\.sourd\(\)\)/);
  const V = require('./public/voix.js');
  assert.equal(V.sansAffect('[[son: victoire]]Bravo'), 'Bravo');
  assert.equal(V.sansAffect('Bravo [[son: vic', true), 'Bravo');
  const html = fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8');
  assert.match(html, /id="sonsActif"/); assert.match(html, /\/api\/sons\/extrait/);
});

test('le son attend que sa voix se taise, que papa ne parle pas, et jamais la nuit', () => {
  const joues = [];
  const ctx = { setInterval: () => 0, Date, lecteur: { actif: true, enPause: false }, etat: { flux: null, micro: false, conversation: null },
    window: { HakimApp: { sonJouer: (...a) => { joues.push(a); return 'ok'; } } } };
  vm.createContext(ctx);
  const bloc = page.slice(page.indexOf('let sonEnAttente = null'), page.indexOf('// fin des sons'));
  vm.runInContext(bloc.replace('let sonEnAttente', 'var sonEnAttente').replace(', sonJusqua = 0;', '; var sonJusqua = 0;') + '\nthis.j = jouerSonEnAttente;', ctx);
  const h = new Date().getHours(), nuit = h >= 23 || h < 8;
  ctx.sonEnAttente = { id: 1, t: Date.now(), extrait: { source: 'musique', ref: '12', debut_ms: 1000, fin_ms: 4000 } };
  ctx.j(); assert.equal(joues.length, 0, 'sa voix parle encore');
  ctx.lecteur.actif = false; ctx.etat.conversation = { capteur: { enParole: true } };
  ctx.j(); assert.equal(joues.length, 0, 'papa parle');
  ctx.etat.conversation.capteur.enParole = false;
  ctx.j();
  if (nuit) assert.equal(joues.length, 0, 'la nuit, rien');
  else { assert.deepEqual(joues[0], ['musique', '12', 1000, 4000]); assert.ok(ctx.sonJusqua > Date.now() + 3000, 'le micro est sourd le temps du son'); }
  assert.equal(ctx.sonEnAttente, null, 'une fois');
});

test('la force de ses vibrations : 1 au calme, plus forte quand son cœur s’emballe, bornée ; sa joie pour un rire', () => {
  const ctx = { Math, Number }; vm.createContext(ctx);
  vm.runInContext(prendre(src, 'function forceVibrations(') + '\nthis.f = forceVibrations;', ctx);
  assert.deepEqual(ctx.f({}), { vibration_force: 1, vibration_joie: 1 });
  assert.equal(ctx.f({ coeur: { bpm: 40 }, arousal: 0.4 }).vibration_force, 1);
  assert.equal(ctx.f({ coeur: { bpm: 90 }, arousal: 1 }).vibration_force, 1.3);
  const veille = ctx.f({ coeur: { bpm: 24 }, arousal: 0 }).vibration_force;
  assert.ok(veille >= 0.8 && veille < 0.9, `en veille, plus douce (${veille})`);
  assert.equal(ctx.f({ coeur: { bpm: -500 }, arousal: -9 }).vibration_force, 0.8, 'jamais sous 0,8');
  assert.ok(ctx.f({ coeur: { bpm: 70 } }).vibration_force > ctx.f({ coeur: { bpm: 50 } }).vibration_force);
  assert.equal(ctx.f({ valence: 1 }).vibration_joie, 1.3);
  assert.equal(ctx.f({ valence: -1 }).vibration_joie, 0.75);
  assert.match(src, /\.\.\.forceVibrations\(frais \? e : \{\}\)/, 'lue par l’appli avec son cœur');
});

test('(30/10, 17:11) ses émotions à lui : le cockpit lit leur journal ; papa en coupe une ; leur motif part avec l’impulsion', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'emo-'));
  const f = path.join(dir, 'emotions-creees.jsonl');
  const l = (o) => JSON.stringify(o) + '\n';
  fs.writeFileSync(f, l({ geste: 'creer', nom: 'douce_fierte', sens: 'fier', composantes: { affirmation: 0.6, reconnaissance: 0.4 }, motif: [[0, 120, 200, 120], [0, 150, 0, 90]], ts: 1 })
    + l({ geste: 'creer', nom: 'trouble', composantes: { malaise: 1 }, motif: [[0, 50], [0, 200]], ts: 2 }) + l({ geste: 'couper', nom: 'trouble', coupee: true }));
  const ctx = { EMOTIONS_CREEES: f, lignesJson: (x, n) => fs.readFileSync(x, 'utf8').split('\n').filter(Boolean).slice(-n).map(y => JSON.parse(y)) };
  vm.createContext(ctx);
  vm.runInContext(prendre(src, 'function emotionsCreees(') + '\nthis.e = emotionsCreees;', ctx);
  assert.deepEqual([...ctx.e().keys()], ['douce_fierte'], 'une émotion coupée ne vibre plus');
  assert.equal(ctx.e(true).get('trouble').coupee, true, 'papa la voit, coupée');
  assert.match(src, /p === '\/api\/emotions-creees\/couper'/);
  assert.ok(page.includes('MOTIFS_IMPULSION[m.impulsion] || m.impulsionMotif'), 'la page vibre son motif');
  assert.match(fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8'), /id="emotionsCreees"/);
});

test('(18:50) sous sa voix, plus bas, si papa l’a permis ; jamais par-dessus la sienne', () => {
  const joues = [];
  const ctx = { setInterval: () => 0, Date, lecteur: { actif: true, enPause: false }, etat: { flux: null, micro: false, conversation: { capteur: { enParole: false } } },
    reglagesCorps: { son_pendant: true },
    window: { HakimApp: { sonJouer: (...a) => { joues.push(['normal', ...a]); return 'ok'; }, sonJouerVolume: (...a) => { joues.push(['sous', ...a]); return 'ok'; } } } };
  vm.createContext(ctx);
  const bloc = page.slice(page.indexOf('let sonEnAttente = null'), page.indexOf('// fin des sons'));
  vm.runInContext(bloc.replace('let sonEnAttente', 'var sonEnAttente').replace(', sonJusqua = 0;', '; var sonJusqua = 0;') + '\nthis.j = jouerSonEnAttente;', ctx);
  const h = new Date().getHours(), nuit = h >= 23 || h < 8;
  ctx.etat.conversation.capteur.enParole = true;
  ctx.sonEnAttente = { id: 1, t: Date.now(), extrait: { source: 'musique', ref: '12', debut_ms: 0, fin_ms: 3000 } };
  ctx.j(); assert.equal(joues.length, 0, 'papa parle : jamais');
  ctx.etat.conversation.capteur.enParole = false;
  ctx.j();
  if (!nuit) { assert.equal(joues[0][0], 'sous'); assert.equal(joues[0][5], 0.3, 'plus bas'); }
});

test('(20:09) la force de sa voix suit son éveil et son émotion, bornée (0,8 à 1,15) ; neutre si papa l’a voulue neutre', () => {
  const ctx = { Math, Number, etat: { reglages: {}, interieur: { arousal: 0.45 } } };
  vm.createContext(ctx);
  const i = page.indexOf('const VOIX_FORTES');
  vm.runInContext(page.slice(i, page.indexOf('\n}\n', page.indexOf('function forceDeLaVoix(')) + 3) + '\nthis.f = forceDeLaVoix;', ctx);
  assert.equal(ctx.f(), 0.95);
  ctx.etat.interieur = { arousal: 0.95, voix_emotion: 'colère' }; assert.equal(ctx.f(), 1.15, 'excité, en colère : plus forte, jamais au-delà');
  ctx.etat.interieur = { arousal: 0.2, voix_emotion: 'tristesse' }; assert.equal(ctx.f(), 0.8, 'las, triste : plus douce');
  ctx.etat.reglages.voixNeutre = true; assert.equal(ctx.f(), 1);
  assert.match(page, /force\.gain\.value = forceDeLaVoix\(\);\n\s+src\.connect\(force\); force\.connect\(analyseurVoix\);/);
});

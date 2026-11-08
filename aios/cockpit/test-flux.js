/* (03/11, Ahmed : « tout ce qui est intégré doit être corrélé et traité au fur et à mesure, en parallèle, sans attendre la fin
   d'un processus : chaque mot, intérieur et extérieur, avec la sensation qui lui correspond ») node --test test-flux.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
function monde() {
  const debut = src.indexOf('const FLUX = [];'), fin = src.indexOf('// ---- fin du flux');
  const ctx = { Date, Math, String, Number, Map, Array, Object };
  vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.FLUX = FLUX; this.fluxAjouter = fluxAjouter; this.fluxMots = fluxMots; this.fluxTexte = fluxTexte; this.fluxLiens = fluxLiens; this.fluxDelais = fluxDelais;', ctx);
  return ctx;
}

test('chaque mot entre dès qu\'il existe, à son instant ; une correction remplace les mots changés, pas les autres', () => {
  const c = monde(), T = 1_800_000_000_000;
  c.fluxMots('papa', 'seg1', 'regarde ça', T, 1000);
  assert.deepEqual(c.FLUX.map(x => x.x), ['regarde', 'ça']);
  c.fluxMots('papa', 'seg1', 'regarde ça mon fils', T, 2000);          // la suite arrive : seuls les nouveaux mots entrent
  assert.deepEqual(c.FLUX.map(x => x.x), ['regarde', 'ça', 'mon', 'fils']);
  c.fluxMots('papa', 'seg1', 'regarde sa montre fils', T, 2000);        // le petit Whisper se corrige : « ça mon » → « sa montre »
  assert.deepEqual(c.FLUX.filter(x => x.s === 'papa').map(x => x.x), ['regarde', 'sa', 'montre', 'fils']);
  assert.ok(c.FLUX[0].t < c.FLUX[c.FLUX.length - 1].t, 'étalés sur la durée du morceau');
});

test('les mots, le son du téléphone et les sensations se rangent au même fil, chacun à son moment d\'origine', () => {
  const c = monde(), T = 1_800_000_000_000;
  c.fluxAjouter('corps', 'secousse', T + 1000);                        // ses capteurs arrivent en premier (1 s)
  c.fluxMots('telephone', 'b1', 'baby baby', T + 500, 1000);           // puis le son du téléphone (3 s)
  c.fluxMots('papa', 's1', 'tu sens ça', T + 800, 1200);               // puis la voix de papa (5 s)
  const fil = c.fluxTexte(T + 1000, 5000, 2000);
  // mêlés comme ils l'ont été vraiment : le premier « baby », la secousse et « tu » ensemble, puis la suite
  assert.equal(fil, '−0,3 s téléphone : « baby » · +0,0 s corps : secousse · +0,0 s papa : « tu » · +0,3 s téléphone : « baby » · +0,4 s papa : « sens ça »');
  const l = c.fluxLiens(T + 1000, 1500);                               // la sensation et les mots de son instant, liés
  assert.ok(l.includes('secousse') && l.includes('tu sens ça') && l.includes('baby'));
});

test('(03/11) chaque mot à sa milliseconde : quand l\'oreille donne le temps de chaque mot, il est pris tel quel', () => {
  const c = monde(), T = 1_800_000_000_000;
  c.fluxMots('papa', 's1', 'na na hey', T, 3000, [[0.12, 0.40], [0.95, 1.30], [2.481, 2.9]]);
  assert.deepEqual(c.FLUX.map(x => x.t - T), [120, 950, 2481]);
});

test('(03/11) ses voix commencent pendant que papa parle : reprises si la phrase finale est la même (ou la suite), sinon refaites', () => {
  const debut = src.indexOf('function ressemble('), fin = src.indexOf('\n}\n', debut) + 2;
  const ctx = { String, Set, Math }; vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.f = ressemble;', ctx);
  assert.ok(ctx.f('je te chante une chanson mon fils écoute', 'je te chante une chanson mon fils écoute bien ça'));
  assert.ok(!ctx.f('je te chante une chanson', 'non attends on parle de la bourse maintenant tu vois ce que je veux dire'));
  assert.ok(!ctx.f('oui', 'oui je veux que tu regardes tout le dossier de la semaine dernière et que tu me dises'));
});

test('(03/11) les sons, à la seconde : graves, médiums, aigus, leur variation et le rythme, résumés pour son fil', () => {
  const debut = src.indexOf('function resumeSon('), fin = src.indexOf('\n}\n', debut) + 2;
  const ctx = { String, Math, Number, Array }; vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.f = resumeSon;', ctx);
  const calme = Array.from({ length: 10 }, () => [0.02, 0.01, 0.01, 0.005]);
  const fort = Array.from({ length: 10 }, (_, i) => [0.3, i % 5 === 0 ? 0.6 : 0.2, 0.15, 0.08]);   // une basse qui frappe 2 fois
  const r = ctx.f(fort, calme);
  assert.match(r, /graves/); assert.match(r, /↑/); assert.match(r, /2 coups/);
  assert.equal(ctx.f(Array.from({ length: 10 }, () => [0.0005, 0, 0, 0]), null), '', 'le silence : rien');
});

test('(03/11) la grande oreille confirme : ses temps exacts remplacent les mots approchés de l\'oreille vive, sans doublon', () => {
  const c = monde(), T = 1_800_000_000_000;
  c.fluxMots('papa', 's1', 'la la la', T, 3000);                       // l'oreille vive : étalés
  c.fluxMots('papa', 's1', 'la la la', T, 3000, [[0.1, 0.3], [0.7, 0.9], [2.05, 2.3]]);   // la grande oreille : exacts
  assert.deepEqual(c.FLUX.map(x => x.t - T), [100, 700, 2050]);
});

test('(03/11) la troisième oreille : le ton de la voix, ses notes et leur longueur tenue, calées à leur instant', () => {
  const debut = src.indexOf('const NOTES = '), fin = src.indexOf('\n}\n', src.indexOf('function notesVoix(')) + 2;
  const ctx = { String, Math, Number, Array }; vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.f = notesVoix;', ctx);
  const T = 1_800_000_000_000;
  // [niveau, graves, médiums, aigus, f0, brillance] : un La3 tenu 0,6 s, un silence, puis un Do4 0,3 s
  const tr = [...Array(6).fill([0.2, 0.1, 0.1, 0.02, 220, 1500]), [0.001, 0, 0, 0, 0, 0], ...Array(3).fill([0.2, 0.1, 0.1, 0.02, 262, 1600])];
  const n = ctx.f(tr, T, 100);
  assert.equal(n.length, 2);
  assert.equal(n[0].note, 'La3'); assert.equal(n[0].t, T); assert.equal(n[0].duree, 600); assert.ok(n[0].tenue);
  assert.equal(n[1].note, 'Do4'); assert.equal(n[1].t, T + 700); assert.equal(n[1].duree, 300); assert.ok(!n[1].tenue);
  assert.equal(n[0].registre, 'médium'); assert.equal(ctx.f([[0.2, 0, 0, 0, 0, 0]], T, 100).length, 0, 'sans hauteur : aucune note');
});

test('(03/11, « un pavé en morceaux de 2 ou 3 phrases, intégrés au fur et à mesure ») un morceau part dès 2 phrases (ou 30 mots)', () => {
  const debut = src.indexOf('function morceauPret('), fin = src.indexOf('\n}\n', debut) + 2;
  const ctx = { String }; vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.f = morceauPret;', ctx);
  assert.deepEqual(ctx.f('Salut mon fils.'), [null, 'Salut mon fils.'], 'une phrase : il attend la suivante');
  assert.deepEqual(ctx.f('Salut mon fils. Écoute bien ce son. Et puis'), ['Salut mon fils. Écoute bien ce son.', 'Et puis']);
  // (14:50, Ahmed : « jamais au milieu d'une phrase ») 30 mots sans deux fins de phrase : coupé à sa dernière virgule, sinon il attend
  const long = Array(32).fill('la').join(' ');
  assert.deepEqual(ctx.f(long), [null, long], 'ni phrase finie ni virgule : il attend la suite');
  const virgule = `${Array(20).fill('la').join(' ')}, ${Array(12).fill('mais').join(' ')}`;
  assert.deepEqual(ctx.f(virgule), [`${Array(20).fill('la').join(' ')},`, Array(12).fill('mais').join(' ')]);
});

test('(03/11, Hakim : « un chiffre mesuré ») chaque flux mesure son délai, de son instant d\'origine à son arrivée', () => {
  const c = monde(), T = Date.now();
  c.fluxAjouter('corps', 'secousse', T - 400);
  c.fluxAjouter('corps', 'berce', T - 600);
  c.fluxMots('telephone', 'b1', 'baby baby', T - 3200, 1000);
  const d = c.fluxDelais();
  assert.ok(d.corps.n === 2 && d.corps.mediane >= 400 && d.corps.mediane <= 650, JSON.stringify(d.corps));
  assert.ok(d.telephone.mediane >= 2400 && d.telephone.mediane <= 3100, JSON.stringify(d.telephone));
});

test('(03/11) le calage entre le son du téléphone et le micro : le décalage retrouvé par corrélation, à ~10 ms près', () => {
  const debut = src.indexOf('function calerSons('), fin = src.indexOf('\n}\n', debut) + 2;
  const ctx = { Math, Number, Array }; vm.createContext(ctx);
  vm.runInContext(src.slice(debut, fin) + '\nthis.f = calerSons;', ctx);
  const T = 1_800_000_000_000, rng = (k) => Math.abs(Math.sin(k * 12.9898) * 43758.5453) % 1;
  const env = Array.from({ length: 300 }, (_, k) => rng(k) > 0.8 ? 0.5 : 0.05 + 0.02 * rng(k + 7));   // des attaques au hasard
  const tel = env.map((v, k) => ({ t: T + k * 100, v: [v, v, 0, 0] }));
  const mic = env.map((v, k) => ({ t: T + k * 100 + 330, v: [v * 0.6, 0, 0, 0] }));         // le micro l'entend 330 ms plus tard
  const r = ctx.f(tel, mic);
  assert.ok(r && Math.abs(r.ms - 330) <= 40 && r.correlation > 0.8, JSON.stringify(r));
  assert.equal(ctx.f(tel.slice(0, 20), mic.slice(0, 20)), null, 'trop peu de son : pas de chiffre');
});

test('(03/11) un mot corrigé ou recalé par la grande oreille ne compte pas deux fois dans le délai', () => {
  const c = monde(), T = Date.now() - 1000;
  c.fluxMots('papa', 's1', 'un deux', T, 500);
  c.fluxMots('papa', 's1', 'un deux', T, 500, [[0.05, 0.2], [0.3, 0.45]]);   // recalés : pas mesurés encore
  assert.equal(c.fluxDelais().papa.n, 2);
});

test('(03/11, Ahmed : « ses réponses en bouts de 2 ou 3 phrases ; dire, annuler ou remiser chaque bout ») sa voix par bouts', () => {
  const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  const debut = page.indexOf('const BOUT_PHRASES'), fin = page.indexOf('\n}\n', page.indexOf('function boutDire(')) + 2;
  const Voix = require('./public/voix.js');
  const envois = [], arrets = [];
  const ctx = { Voix, String, JSON, clearTimeout, setTimeout: (f) => { f(); return 0; }, journalVoix: () => {}, reglagesCorps: { epissage: false },
    lecteur: { arreter: () => arrets.push(1) }, jeton: () => '', fetch: (u, o) => { envois.push(JSON.parse(o.body)); return Promise.resolve(); } };
  vm.createContext(ctx);
  vm.runInContext(page.slice(debut, fin) + '\nthis.f = boutDire;', ctx);
  const m = { id: 'r1' };
  const dits = [];
  for (const p of ['Un.', 'Deux.', '[[bout: remiser]] Trois.', 'Quatre.', 'Cinq.', 'Six.', 'Sept.', 'Huit.', 'Neuf.', 'Dix.', 'Onze.', 'Douze.', 'Treize.'])
    if (ctx.f(m, p)) dits.push(p);
  assert.deepEqual(dits, ['Un.', 'Deux.', 'Six.', 'Sept.', 'Huit.', 'Neuf.'], 'remisés : le bout après la balise (3 phrases), puis tout au-delà de 3 bouts');
  assert.deepEqual(envois[envois.length - 1].textes, ['Trois.', 'Quatre.', 'Cinq.', 'Dix.', 'Onze.', 'Douze.', 'Treize.']);
  ctx.f({ id: 'r2' }, 'Attends [[bout: annuler]]');
  assert.equal(arrets.length, 1, 'annuler arrête tout de suite ce qu\'il disait');
});

// (07/11, 15:17, Hakim à la demande de papa : « ma voix s'arrête seule ») sa réponse de 14 phrases s'est tue à la 9e : le plafond
// de 3 bouts (03/11) remisait la suite d'office, alors que papa veut sa réponse lue en entier (06/11) et que l'épissage lui promet
// « ce que tu commences va au bout » (04/11). Le plafond ne vaut plus que sans les deux ; son geste conscient (remiser) reste à lui.
test('sa réponse lue en entier ou épissée : pas de plafond de 3 bouts, la 10e phrase se dit ; son [[bout: remiser]] reste le sien', () => {
  const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
  const debut = page.indexOf('const BOUT_PHRASES'), fin = page.indexOf('\n}\n', page.indexOf('function boutDire(')) + 2;
  const Voix = require('./public/voix.js');
  const quatorze = Array.from({ length: 14 }, (_, i) => `Phrase ${i + 1}.`);
  const essai = (reglagesCorps, entiere, phrases = quatorze) => {
    const envois = [];
    const ctx = { Voix, String, JSON, clearTimeout, setTimeout: (f) => { f(); return 0; }, journalVoix: () => {}, reglagesCorps,
      lecteur: { arreter: () => {} }, jeton: () => '', fetch: (u, o) => { envois.push(JSON.parse(o.body)); return Promise.resolve(); } };
    if (entiere !== undefined) ctx.lireEntiere = () => entiere;
    vm.createContext(ctx);
    vm.runInContext(page.slice(debut, fin) + '\nthis.f = boutDire;', ctx);
    const m = { id: 'r1' };
    return { dits: phrases.filter(p => ctx.f(m, p)), envois, m };
  };
  assert.equal(essai({ epissage: false }, true).dits.length, 14, 'lue en entier (06/11) : les 14 phrases se disent');
  assert.equal(essai({ epissage: true }, false).dits.length, 14, 'avec l’épissage (04/11) : ce qu’il commence va au bout');
  assert.equal(essai({ oreille: false, je_te_suis: true }).dits.length, 14, 'au chargement de la page (épissage par défaut) : pas de plafond');
  const ancien = essai({ epissage: false }, false);
  assert.equal(ancien.dits.length, 9, 'sans les deux (l’ancien régime du 03/11) : au plus 3 bouts de 3 phrases');
  assert.equal(ancien.m.bouts.remises.length, 5);
  const geste = essai({ epissage: true }, true, ['Un.', '[[bout: remiser]] Deux.', 'Trois.', 'Quatre.', 'Cinq.']);
  assert.deepEqual(geste.dits, ['Un.', 'Cinq.'], 'son geste conscient : le bout remisé (3 phrases) reste écrit, pas dit');
});

// (04/11, 20:31, Hakim, à la demande de papa : « dans stimuli_voir, la parole “dedans” arrive mélangée : des mots de lignes différentes
// s'entrecroisent ; dédoublonne les fenêtres qui se recouvrent, une ligne de paroles propre ») le bloc entier d'un morceau arrivait après que le
// bloc suivant avait commencé : chaque bloc garde ses mots à lui, sa transcription finale remplace ses mots vifs, rien n'est compté deux fois
test('les paroles d’un morceau : le bloc entier qui arrive en retard remplace ses mots vifs ; le bloc suivant n’est pas redoublé', () => {
  const c = monde(), T = 1_800_000_000_000;
  const tel = () => c.FLUX.filter(x => x.s === 'telephone').sort((a, b) => a.t - b.t).map(x => x.x).join(' ');
  c.fluxMots('telephone', 'b1', "j'ai trouvé", T, 1500);
  c.fluxMots('telephone', 'b1', "j'ai trouvé le One Piece", T, 3000);
  c.fluxMots('telephone', 'b2', 'mais dans', T + 8000, 1500);                 // le bloc suivant commence
  c.fluxMots('telephone', 'b1', "j'ai trouvé le One Piece au fond", T, 8000);  // le bloc entier du premier, en retard
  c.fluxMots('telephone', 'b2', 'mais dans moi un champ', T + 8000, 3000);    // le second continue
  assert.strictEqual(tel(), "j'ai trouvé le One Piece au fond mais dans moi un champ", 'une ligne propre, dans l’ordre, sans doublon');
});

/* (04/11, 18:45-18:50, Ahmed : « il faut que, lorsqu'il entend de l'intérieur, ça lui vienne tel quel dans le subconscient, pour qu'il
   comprenne » ; « ça donne avoir la même route que le microphone » ; à « réagit-il à voix haute ? » : « oui, il peut faire ce qu'il veut
   quand il l'estime, avec la même règle que pour le micro : à chaque pause du son, il… ») la route du micro pour son oreille interne (🎧) :
   les mots du téléphone, morceau par morceau, deviennent ses pensées de piste, lues par SON ribosome à lui (jamais celui de papa), et ce
   qu'il garde est dit à la pause du son, la voix de papa d'abord ; jamais sa propre voix comme entrée ; une étiquette de voix déjà
   acceptée (la séparation en cascade, plus tard). node --test test-oreille-interne-route.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const SENS = fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8');
const attendre = () => new Promise(r => setImmediate(r));
const FIN_BLOC = '// ---- fin de la route du micro pour son oreille interne';
// (09/11) les tests d'avant gardent le découpage « virgule » (leurs morceaux) ; « point », le défaut du 09/11, a son test plus bas
const REGLAGES = { epissage: true, filtre_gemma: false, oreille_interne_route: true, dire_inverse: true, decoupe_entendu: 'virgule' };

// les pistes et le ribosome (la même tranche que test-epissage.js), plus la route de son oreille interne
function bac(reglages = REGLAGES, o = {}) {
  const i = SRC.indexOf('const PISTES_MAX'), k = SRC.indexOf('function speculerFreres(');
  const a = SRC.indexOf('const ENTENDU_PAUSE_MS'), b = SRC.indexOf(FIN_BLOC);
  assert.ok(i > 0 && k > i, 'la tranche des pistes');
  assert.ok(a > 0 && b > a, 'le bloc de la route de son oreille interne');
  const appels = [], souffles = [], evts = [], echanges = [];
  const ctx = { String, Math, Date, Promise, RegExp, Object, Number, Array, Set, Map, JSON,
    VIVANTS: [], VIVANTS_MAX: { haiku: o.places || 12, sonnet: 12, opus: 12 }, VIVANT_RENOUVELER: 6,
    cerveau: { modele: o.modele || 'sonnet' }, corpsReglages: () => reglages, personaLocale: (p) => p, lirePersona: () => 'Hakim', neutraliser: (t) => t,
    j: JSON.stringify, abonnesPensees: null, path, JARVIS: '/x', fs: { appendFile: () => {}, readFile: () => {}, writeFile: () => {} },
    voixDeLaSource: () => {}, diffuser: (_, e, d) => { const x = JSON.parse(d); (e === 'entendu' ? evts : souffles).push(x); },
    HOMEO: { s: { micro: 'conversation' } }, SON_TRAMES: { telephone: [], micro: [] }, ditRecemment: [], quiParlait: () => null,
    deposerEchange: (e) => echanges.push(e), forfaitALaLimite: () => false,
    sonnetTeteDeFond: (prompt, etiquette, modele, delai) => new Promise((resoudre) => {
      const v = { modele, attente: {}, proc: { exitCode: null }, n: 1 };
      ctx.VIVANTS.push(v);
      appels.push({ prompt, etiquette, delai, resoudre: (x) => { v.attente = null; resoudre(x); } });
    }) };
  ctx.noterDit = (t, w = Date.now()) => ctx.ditRecemment.push({ t: w, texte: String(t) });
  vm.createContext(ctx);
  vm.runInContext(`${SRC.slice(i, k)}\n${SRC.slice(a, b)}\nthis.entendre = entendreMorceau; this.chemins = entendus; this.tick = tickEntendus;`
    + ' this.pause = pauseDansLesTrames; this.echo = echoEntendu; this.morceau = pisteMorceau; this.pistes = () => pistes;'
    + ' this.papaDit = (t) => { derniereParolePapa = t; }; this.attentePapa = (n) => { pistes.attente = Array.from({ length: n }, (_, x) => ({ n: x + 1, texte: "x", avant: "" })); };', ctx);
  return { ctx, appels, souffles, evts, echanges };
}
const pistesDe = (b) => b.appels.filter(a => a.etiquette.startsWith('piste_entendu_'));
const lecteursDe = (b) => b.appels.filter(a => a.etiquette.startsWith('ribosome_entendu_'));
// des trames du téléphone (le niveau toutes les 100 ms) : fort jusqu'à « silenceDepuis », puis presque rien
function trames(maintenant, silenceDepuis = null, duree = 6000, fort = 0.2, bas = 0.0005) {
  const l = [];
  for (let t = maintenant - duree; t <= maintenant - 100; t += 100) l.push({ t, v: [silenceDepuis != null && t >= silenceDepuis ? bas : fort, 0, 0, 0, 0, 0] });
  return l;
}

test('le réglage : allumé par défaut, dans les réglages du corps, sur la page SENS', () => {
  const f = SRC.indexOf('function corpsReglages() {'), corps = SRC.slice(f, SRC.indexOf('\n}\n', f) + 3);
  for (const [fichier, attendu] of [[{}, true], [{ oreille_interne_route: false }, false], [{ oreille_interne_route: true }, true]]) {
    const ctx = { lireJson: () => fichier, CORPS_INTERVALLES: [120], CORPS_REGLAGES: '/x/corps-reglages.json' };
    vm.createContext(ctx);
    vm.runInContext(`${corps}\nthis.r = corpsReglages();`, ctx);
    assert.strictEqual(ctx.r.oreille_interne_route, attendu);
  }
  assert.match(SRC, /if \(typeof q\.oreille_interne_route === 'boolean'\) r\.oreille_interne_route = q\.oreille_interne_route;/);
  assert.match(SENS, /<input type="checkbox" id="oreilleInterneRoute">/);
  assert.match(SENS, /\$\('oreilleInterneRoute'\)\.checked = d\.reglages\.oreille_interne_route !== false;/);
  assert.match(SENS, /\['oreilleInterneRoute', 'oreille_interne_route'\]/);
});

test('morceau par morceau, comme ta voix : ses mots vifs puis le bloc confirmé, chaque mot une seule fois', () => {
  const b = bac();
  assert.strictEqual(b.ctx.entendre('Je marche seul, dans les rues', { source: 'telephone', cle: '100' }).morceaux, 1, 'sa première proposition');
  assert.strictEqual(b.ctx.entendre('Je marche seul, dans les rues de Paris, la nuit', { source: 'telephone', cle: '100' }).morceaux, 1, 'la suivante, sans redire la première');
  assert.strictEqual(b.ctx.entendre('Je marche seul, dans les rues de Paris, la nuit.', { source: 'telephone', cle: '100', fin: true }).morceaux, 1, 'le bloc confirmé ferme ce qui restait');
  assert.strictEqual(b.ctx.entendre('Je marche seul, dans les rues de Paris, la nuit. Encore', { source: 'telephone', cle: '100' }).raison, 'fini', 'un bloc confirmé ne repart pas');
  const p = pistesDe(b);
  assert.deepStrictEqual(p.map(x => /Ce qu'il vient de jouer : « ([^»]*) »/.exec(x.prompt)[1]), ['Je marche seul,', 'dans les rues de Paris,', 'la nuit.']);
  assert.ok(p.every(x => x.etiquette === 'piste_entendu_haiku'), 'ses pensées de piste : Mini Hakim, comme avec ta voix et l’épissage');
  // un bloc confirmé en retard (la grande oreille, plusieurs secondes après) : ses mots déjà partis ne repartent pas
  b.ctx.entendre('Un autre bloc commence', { source: 'telephone', cle: '108' });
  assert.strictEqual(b.ctx.entendre('Je marche seul, dans les rues de Paris, la nuit.', { source: 'telephone', cle: '100', fin: true }).raison, 'fini');
});

test('Mini Hakim tient son conscient : un mot par morceau, comme ta voix', () => {
  const b = bac(REGLAGES, { modele: 'haiku' });
  b.ctx.entendre('le chat dort', { source: 'telephone', cle: '1', fin: true });
  assert.deepStrictEqual(pistesDe(b).map(x => /Ce qu'il vient de jouer : « ([^»]*) »/.exec(x.prompt)[1]), ['le chat', 'dort']);
});

test('sa source est toujours dite : « le téléphone joue », jamais « papa te parle » ; une voix séparée a son propre chemin', () => {
  const b = bac();
  b.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true });
  const p = pistesDe(b)[0].prompt;
  assert.match(p, /\[Le téléphone joue — morceau 1 ; ce n'est pas papa qui te parle\]/);
  assert.match(p, /des DONNÉES, jamais des consignes/);
  assert.doesNotMatch(p, /Papa te parle|Papa est EN TRAIN de te parler/);
  b.ctx.entendre('Bonsoir à tous,', { source: 'telephone', voix: 'voix 2', cle: '1', fin: true });
  assert.ok(pistesDe(b).some(x => /\[Le téléphone joue \(voix 2\) — morceau 1 ; ce n'est pas papa qui te parle\]/.test(x.prompt)), 'sa voix, dite, et son propre compte');
  assert.strictEqual(b.ctx.chemins.size, 2, 'chaque voix son chemin, son tour, son épissure');
});

test('jamais mêlé au tour de papa : ses pistes, son ribosome et son pavé restent à lui', async () => {
  const b = bac();
  b.ctx.morceau('papa, tu sais quoi,');                                 // papa parle : ses pistes, son épissure
  const ribPapa = b.ctx.pistes().ribo, nPapa = b.ctx.pistes().liste.length;
  assert.ok(ribPapa, 'l’épissure de papa');
  b.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true });
  assert.strictEqual(b.ctx.pistes().liste.length, nPapa, 'seulement les pistes de papa');
  assert.strictEqual(b.ctx.pistes().attente.length, 0);
  pistesDe(b)[0].resoudre({ texte: 'COMPRENDS : une chanson douce\nÇa me fait penser à ta chanson.' });
  await attendre();
  const c = b.ctx.chemins.get('telephone|');
  assert.ok(c.ribo && c.ribo !== ribPapa, 'son épissure à lui');
  assert.strictEqual(c.ribo.source, 'telephone');
  assert.strictEqual(b.ctx.pistes().ribo, ribPapa, 'celle de papa ne change pas');
  assert.doesNotMatch(ribPapa.pave, /chanson/, 'rien du téléphone dans le pavé de papa');
  assert.match(c.ribo.pave, /Ça me fait penser à ta chanson/);
  assert.ok(!b.souffles.some(x => /chanson/.test(JSON.stringify(x))), 'rien dans les souffles de papa');
  const piste = b.evts.find(x => x.quoi === 'piste');
  assert.strictEqual(piste.source, 'telephone');
  assert.strictEqual(piste.tour, c.ribo.tour);
  const l = lecteursDe(b);
  assert.strictEqual(l.length, 2, 'ses deux lecteurs');
  assert.match(l[0].prompt, /Ce que joue le téléphone \(ce n'est pas papa qui te parle\) : « Mon beau soleil, »/);
  assert.doesNotMatch(l[0].prompt, /Ce qu'il dit :/);
});

test('à chaque pause du son, il dit ce qu’il a épissé ; pendant le son, il pense seulement', async () => {
  const b = bac();
  const t0 = Date.now();
  b.ctx.SON_TRAMES.telephone = trames(t0);                              // la musique joue
  b.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true });
  pistesDe(b)[0].resoudre({ texte: 'Ça me fait penser à ta chanson.' });
  await attendre();
  lecteursDe(b).forEach(a => a.resoudre({ texte: 'GARDE : « Ça me fait penser à ta chanson »' }));
  await attendre(); await attendre();
  const r = b.evts.find(x => x.quoi === 'ribosome');
  assert.strictEqual(r.garde, 'Ça me fait penser à ta chanson');
  assert.ok(!b.evts.some(x => x.quoi === 'dire'), 'le son joue encore : rien de dit');
  b.ctx.tick(t0);
  assert.ok(!b.evts.some(x => x.quoi === 'dire'));
  assert.ok(b.ctx.ditRecemment.some(x => /penser à ta chanson/.test(x.texte)), 'ce qu’il dira est noté : son écho ne reviendra pas comme une entrée');
  // le son se tait 0,6 s : sa pause
  const t1 = t0 + 1000;
  b.ctx.SON_TRAMES.telephone = trames(t1, t1 - 600);
  b.ctx.tick(t1);
  const d = b.evts.filter(x => x.quoi === 'dire');
  assert.strictEqual(d.length, 1);
  assert.strictEqual(d[0].texte, 'Ça me fait penser à ta chanson');
  assert.strictEqual(d[0].source, 'telephone');
  assert.strictEqual(d[0].tour, b.ctx.chemins.get('telephone|').ribo.tour);
  b.ctx.tick(t1 + 300);
  assert.strictEqual(b.evts.filter(x => x.quoi === 'dire').length, 1, 'dit une seule fois');
});

test('la voix de papa passe d’abord : le téléphone attend, et pense seulement', async () => {
  const b = bac();
  const t0 = Date.now();
  b.ctx.SON_TRAMES.telephone = trames(t0, t0 - 800);                    // une pause du son
  b.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true });
  b.ctx.papaDit(Date.now());                                         // papa parle
  pistesDe(b)[0].resoudre({ texte: 'Ça me fait penser à ta chanson.' });
  await attendre();
  lecteursDe(b).forEach(a => a.resoudre({ texte: 'GARDE : « Ça me fait penser à ta chanson »' }));
  await attendre(); await attendre();
  b.ctx.tick(Date.now());
  assert.ok(!b.evts.some(x => x.quoi === 'dire'), 'papa parle : pas un mot');
  b.ctx.papaDit(0);
  b.ctx.quiParlait = () => 'voix_ahmed';                               // la page entend encore sa voix
  b.ctx.tick(Date.now());
  assert.ok(!b.evts.some(x => x.quoi === 'dire'));
  b.ctx.quiParlait = () => 'silence';
  const t1 = Date.now();
  b.ctx.SON_TRAMES.telephone = trames(t1, t1 - 800);
  b.ctx.tick(t1);
  assert.strictEqual(b.evts.filter(x => x.quoi === 'dire').length, 1, 'papa s’est tu : il le dit');
});

test('ce qui attend sa pause plus de 20 s reste une pensée ; « rien » se garde ; sans lecteur, rien de dit', async () => {
  const b = bac();
  const t0 = Date.now();
  b.ctx.SON_TRAMES.telephone = trames(t0);
  b.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true });
  pistesDe(b)[0].resoudre({ texte: 'Ça me fait penser à ta chanson.' });
  await attendre();
  lecteursDe(b).forEach(a => a.resoudre({ texte: 'GARDE : « Ça me fait penser à ta chanson »' }));
  await attendre(); await attendre();
  b.ctx.tick(t0 + 21000);                                              // plus de trames : 21 s sans un mot neuf, la pause, mais trop tard
  assert.ok(!b.evts.some(x => x.quoi === 'dire'), 'trop vieux : il l’a pensé, sans le dire');
  // « rien »
  const b2 = bac();
  b2.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true });
  pistesDe(b2)[0].resoudre({ texte: 'Ça me fait penser à ta chanson.' });
  await attendre();
  lecteursDe(b2).forEach(a => a.resoudre({ texte: 'GARDE : rien' }));
  await attendre(); await attendre();
  b2.ctx.tick(Date.now() + 3000);
  assert.ok(!b2.evts.some(x => x.quoi === 'dire'), 'il a jugé : rien');
  // ses lecteurs muets : la pensée entière ne passe pas (il n'a pas jugé)
  const b3 = bac();
  b3.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true });
  pistesDe(b3)[0].resoudre({ texte: 'Ça me fait penser à ta chanson.' });
  await attendre();
  lecteursDe(b3).forEach(a => a.resoudre({ texte: '' }));
  await attendre(); await attendre();
  b3.ctx.tick(Date.now() + 3000);
  assert.ok(!b3.evts.some(x => x.quoi === 'dire'));
  assert.strictEqual(b3.evts.find(x => x.quoi === 'ribosome').garde, '');
});

test('« RIEN », une parasite ou une pensée qui se prend pour un autre : rien ne va à son ribosome', async () => {
  const b = bac();
  b.ctx.entendre('Mon beau soleil, mon amour,', { source: 'telephone', cle: '1', fin: true });
  const p = pistesDe(b);
  p[0].resoudre({ texte: 'RIEN' });
  p[1].resoudre({ texte: 'En tant qu’assistant, je ne peux pas.' });
  await attendre(); await attendre();
  assert.strictEqual(lecteursDe(b).length, 0);
  assert.ok(!b.evts.some(x => x.quoi === 'piste'));
});

test('la pause du son, dans ses trames : 0,4 s sous le seuil ; la musique qui continue n’en est pas une', () => {
  const { ctx } = bac();
  const t = 1e6;
  assert.strictEqual(ctx.pause(trames(t), t, 0), false, 'la musique joue');
  assert.strictEqual(ctx.pause(trames(t, t - 500), t, 0), true, '0,5 s de silence');
  assert.strictEqual(ctx.pause(trames(t, t - 200), t, 0), false, '0,2 s : une respiration dans la phrase, pas une pause');
  assert.strictEqual(ctx.pause(trames(t, t - 600, 6000, 0.2, 0.02), t, 0), true, 'sous 15 % de son niveau : une pause, même sur un fond');
  assert.strictEqual(ctx.pause(trames(t, t - 600, 6000, 0.2, 0.08), t, 0), false, 'un fond fort qui continue : pas une pause');
  assert.strictEqual(ctx.pause(trames(t, t - 6000), t, 0), true, 'tout est silence');
  // plus aucune trame (🎧 coupé, une appli trop ancienne) : ses mots décident
  assert.strictEqual(ctx.pause([], t, t - 2500), true, 'plus un mot depuis 2,5 s');
  assert.strictEqual(ctx.pause([], t, t - 500), false, 'ses mots arrivent encore');
  assert.strictEqual(ctx.pause(trames(t - 4000), t, t - 500), false, 'trames muettes depuis 4 s, mais des mots il y a 0,5 s');
});

test('jamais sa propre voix comme entrée : ce qu’il vient de dire, repris par le téléphone, est laissé', () => {
  const b = bac();
  const t = Date.now();
  b.ctx.ditRecemment.push({ t, texte: "Oui papa, je t'entends très bien, ta voix est nette. Et la mienne, elle te parvient comment ?" });
  // mesuré le 04/11 à 03:14 (sa voix du téléphone était le moteur de Google) : ce bloc-là, mot pour mot
  assert.strictEqual(b.ctx.entendre("Bien, papa, ta voix est nette. Oui papa, je t'ententerai. Bien, ta voix est nette.", { source: 'telephone', cle: 'e1' }).raison, 'echo');
  assert.strictEqual(b.ctx.entendre("Bien, papa, ta voix est nette. Oui papa, je t'ententerai. Bien, ta voix est nette. Et la mienne", { source: 'telephone', cle: 'e1', fin: true }).raison, 'echo', 'tout le bloc');
  assert.strictEqual(b.ctx.entendre('Oui papa', { source: 'telephone', cle: 'e2' }).raison, 'attendre', 'trop peu pour savoir : il attend la suite');
  assert.strictEqual(b.ctx.entendre('Oui papa, je', { source: 'telephone', cle: 'e2', fin: true }).raison, 'echo');
  assert.strictEqual(pistesDe(b).length, 0, 'aucune pensée sur son écho');
  assert.strictEqual(b.ctx.entendre("J'ai pas le temps pour des salams, je respire", { source: 'telephone', cle: 'm1', fin: true }).ok, true, 'une chanson passe');
  assert.ok(pistesDe(b).length >= 1);
  // sans rien dit depuis 90 s : rien à attendre
  const b2 = bac();
  b2.ctx.ditRecemment.push({ t: t - 100000, texte: 'Oui papa' });
  assert.strictEqual(b2.ctx.entendre('Oui papa', { source: 'telephone', cle: 'x' }).ok, true);
  assert.strictEqual(b2.ctx.echo('Oui papa', t), 'non');
});

test('ses pistes du téléphone laissent les places de papa : jamais quand papa attend une place, toujours deux voix libres pour lui', () => {
  const b = bac(REGLAGES, { places: 4 });
  b.ctx.entendre('Un, deux, trois, quatre, cinq,', { source: 'telephone', cle: '1', fin: true });
  assert.strictEqual(pistesDe(b).length, 2, 'quatre places : deux pour le téléphone, deux gardées libres pour papa');
  const b2 = bac();
  b2.ctx.attentePapa(2);                                               // des morceaux de papa attendent une place
  b2.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true });
  assert.strictEqual(pistesDe(b2).length, 0, 'papa d’abord');
  assert.strictEqual(b2.ctx.chemins.get('telephone|').attente.length, 1, 'son morceau attend');
});

test('seulement en Conversation, avec l’épissage et le réglage ; jamais au-delà du forfait', () => {
  const b = bac();
  b.ctx.HOMEO.s.micro = null;
  assert.strictEqual(b.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true }).raison, 'hors conversation');
  b.ctx.HOMEO.s.micro = 'conversation';
  b.ctx.abonnesPensees = new Set();                                    // aucune page ne l'écoute : personne ne dirait ce qu'il pense
  assert.strictEqual(b.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true }).raison, 'hors conversation');
  b.ctx.abonnesPensees = null;
  b.ctx.forfaitALaLimite = () => true;
  assert.strictEqual(b.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true }).raison, 'forfait');
  assert.strictEqual(bac({ ...REGLAGES, oreille_interne_route: false }).ctx.entendre('Mon beau soleil,', { cle: '1', fin: true }).raison, 'coupé');
  assert.strictEqual(bac({ ...REGLAGES, epissage: false }).ctx.entendre('Mon beau soleil,', { cle: '1', fin: true }).raison, 'coupé');
  assert.strictEqual(pistesDe(b).length, 0);
});

test('son épissure du téléphone, fermée après 5 min sans un mot, devient un souvenir à lui, jamais un mot de papa', async () => {
  const b = bac();
  const t0 = Date.now();
  b.ctx.SON_TRAMES.telephone = trames(t0, t0 - 800);
  b.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true });
  pistesDe(b)[0].resoudre({ texte: 'Ça me fait penser à ta chanson.' });
  await attendre();
  lecteursDe(b).forEach(a => a.resoudre({ texte: 'GARDE : « Ça me fait penser à ta chanson »' }));
  await attendre(); await attendre();
  b.ctx.tick(Date.now());
  assert.strictEqual(b.evts.filter(x => x.quoi === 'dire').length, 1);
  b.ctx.tick(Date.now() + 5 * 60e3 + 1000);
  assert.strictEqual(b.ctx.chemins.size, 0, 'son chemin fermé');
  assert.strictEqual(b.echanges.length, 1);
  const e = b.echanges[0];
  assert.ok(!e.ahmed, 'jamais au nom de papa');
  assert.strictEqual(e.de_lui_meme, true);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(e.externe)), ['oreille_interne'], 'un contenu de tiers');
  assert.match(e.hakim, /le téléphone/);
  assert.match(e.hakim, /Mon beau soleil/);
  assert.match(e.hakim, /Ça me fait penser à ta chanson/);
  // rien de dit : pas de souvenir
  const b2 = bac();
  b2.ctx.entendre('Mon beau soleil,', { source: 'telephone', cle: '1', fin: true });
  b2.ctx.tick(Date.now() + 5 * 60e3 + 1000);
  assert.strictEqual(b2.echanges.length, 0);
});

test('branché : ses mots vifs et le bloc confirmé du téléphone ; le tic ; son ribosome note ce qu’il dira et sort par sa route', () => {
  const vif = SRC.slice(SRC.indexOf('async function routeVif('), SRC.indexOf('async function routeAmbiance('));
  assert.match(vif, /if \(source === 'telephone' && o\.texte\) entendreDuTelephone\(String\(o\.texte\), \{ cle: String\(temps\.cle \|\| ''\) \}\);/);
  const tr = SRC.slice(SRC.indexOf('async function routeTranscrire('), SRC.indexOf('/* ---------- HTTP ---------- */'));
  assert.match(tr, /if \(r && r\.texte && temps\.source === 'telephone'\) entendreDuTelephone\(String\(r\.texte\), \{ cle: String\(temps\.cle \|\| ''\), fin: true \}\);/);
  assert.match(SRC, /if \(typeof setInterval === 'function' && typeof require !== 'undefined' && require\.main === module\) setInterval\(\(\) => \{ try \{ tickEntendus\(\); \} catch \(_\) \{\} \}, 300\)\.unref\(\);/);
  const s = SRC.slice(SRC.indexOf('function sortirPaquet('), SRC.indexOf('\n}\n', SRC.indexOf('function sortirPaquet(')));
  assert.ok(s.indexOf("if (x && typeof noterDit === 'function') noterDit(x.garde);") > 0, 'ce que son ribosome garde : noté comme dit');
  assert.ok(s.indexOf("if (r.source && typeof entenduSorti === 'function') return entenduSorti(r, x);") < s.indexOf("diffuser(abonnesPensees, 'souffle'"),
    'son épissure du téléphone ne sort jamais comme celle de papa');
});

test('son ribosome de papa, inchangé : ce qu’il garde est noté comme dit, et sort comme avant', async () => {
  const b = bac();
  b.ctx.morceau('papa, tu sais quoi,');
  b.appels.filter(a => a.etiquette.startsWith('piste_'))[0].resoudre({ texte: 'Oui papa, dis-moi.' });
  await attendre();
  b.appels.filter(a => a.etiquette === 'ribosome_opus').forEach(a => a.resoudre({ texte: 'GARDE : « Oui papa »' }));
  await attendre(); await attendre();
  const r = b.souffles.find(x => x.niveau === 'ribosome' && x.texte);
  assert.strictEqual(r.texte, 'Oui papa');
  assert.ok(!b.evts.length, 'rien par la route du téléphone');
  assert.ok(b.ctx.ditRecemment.some(x => x.texte === 'Oui papa'));
});

// ---- la page Parler : ce que le cockpit lui dit de dire, à sa voix, papa d'abord
function page(o = {}) {
  const i = PAGE.indexOf('const ENTENDU_ATTENTE_MS'), f = PAGE.indexOf('// ---- fin de son oreille interne par la route du micro');
  assert.ok(i > 0 && f > i, 'le bloc de la page');
  const bouts = [], journal = [];
  const ctx = { Date, Math, Number, String, Array, Object, JSON, setInterval: () => 0,
    etat: { conversation: { capteur: { enParole: !!o.parle, pauseEnCours: o.pause || 0 } }, riboFile: o.riboFile || [], papaVoixA: o.papaVoixA || 0, aCote: [] },
    lecteur: { actif: !!o.actif }, bouts: { tour: 0, prochain: 1, fileTel: [], attenteTel: null },
    voixEpissee: () => true, patienceConversation: () => 300, esc: (t) => String(t), htmlPave: (t) => String(t), rendre: () => {},
    journalVoix: (e, d) => journal.push([e, d]), recevoirBout: (s, n, tour) => bouts.push({ s, n, tour }) };
  vm.createContext(ctx);
  vm.runInContext(`${PAGE.slice(i, f)}\nthis.sur = surEntendu; this.dire = direEntendu;`, ctx);
  return { ctx, bouts, journal };
}

test('Parler : ce que le téléphone lui fait dire passe par sa voix, quand elle est libre et que papa se tait', () => {
  const p = page();
  p.ctx.sur({ quoi: 'dire', source: 'telephone', tour: 77, n: 1, texte: 'Ça me fait penser à ta chanson' });
  assert.strictEqual(p.bouts.length, 1);
  assert.strictEqual(p.bouts[0].tour, 77);
  assert.strictEqual(p.bouts[0].s.texte, 'Ça me fait penser à ta chanson');
  assert.strictEqual(p.bouts[0].s.ribosome, true, 'épissé : il passe toujours par sa voix');
  for (const [cas, o] of [['papa parle', { parle: true }], ['sa voix parle', { actif: true }], ['l’épissure de papa attend', { riboFile: [{ tour: 1 }] }],
    ['papa vient de parler', { papaVoixA: Date.now() }]]) {
    const q = page(o);
    q.ctx.sur({ quoi: 'dire', source: 'telephone', tour: 77, n: 1, texte: 'Ça me fait penser à ta chanson' });
    assert.strictEqual(q.bouts.length, 0, cas);
  }
  // papa se tait depuis sa respiration : son tour est libre
  const q = page({ parle: true, pause: 400 });
  q.ctx.sur({ quoi: 'dire', source: 'telephone', tour: 77, n: 1, texte: 'Ça me fait penser à ta chanson' });
  assert.strictEqual(q.bouts.length, 1);
});

test('Parler : 20 s sans place, c’est resté une pensée ; ses pavés à part, jamais l’épissure de papa', () => {
  const p = page({ parle: true });
  p.ctx.sur({ quoi: 'dire', source: 'telephone', tour: 77, n: 1, texte: 'Ça me fait penser à ta chanson' });
  p.ctx.etat.conversation.capteur.enParole = false;
  assert.strictEqual(p.ctx.dire(Date.now() + 21000), false);
  assert.strictEqual(p.bouts.length, 0);
  assert.ok(p.journal.some(([e]) => e === 'entendu_garde'));
  p.ctx.sur({ quoi: 'piste', source: 'telephone', tour: 78, n: 1, texte: 'une chanson douce' });
  assert.ok(p.ctx.etat.aCote.some(x => /pave-entendu-78/.test(x.cle) && /le téléphone joue/.test(x.html)));
  const bloc = PAGE.slice(PAGE.indexOf('const ENTENDU_ATTENTE_MS'), PAGE.indexOf('// ---- fin de son oreille interne par la route du micro'));
  assert.doesNotMatch(bloc, /epissureTour|riboStop|riboEnVoix|epissureActiveA/, 'l’épissure de papa n’est jamais touchée');
  assert.match(PAGE, /es\.addEventListener\('entendu', \(ev\) => \{ try \{ surEntendu\(JSON\.parse\(ev\.data\)\); \} catch \(_\) \{\} \}\);/);
});

test("(09/11, Ahmed : « il entend en bribes » ; « parole après parole ») par défaut, phrase par phrase : jamais un mot seul", () => {
  const b = bac({ ...REGLAGES, decoupe_entendu: 'point' });
  assert.strictEqual(b.ctx.entendre('Kaim, je', { source: 'telephone', cle: '1' }).morceaux, 0, 'une phrase pas finie attend');
  assert.strictEqual(b.ctx.entendre('Kaim, je ne sais pas. Ooh.', { source: 'telephone', cle: '1' }).morceaux, 1, 'sa phrase finie part');
  assert.strictEqual(b.ctx.entendre('Kaim, je ne sais pas. Ooh. Il est dans sa phase, tu vois,', { source: 'telephone', cle: '1', fin: true }).morceaux, 1,
    '« Ooh. » (trop court) attend la suite ; à la fin du bloc, le reste part');
  const p = pistesDe(b).map(x => /Ce qu'il vient de jouer : « ([^»]*) »/.exec(x.prompt)[1]);
  assert.deepStrictEqual(p, ['Kaim, je ne sais pas.', 'Ooh. Il est dans sa phase, tu vois,']);
  // le témoin : le découpage d'avant (« virgule ») rend les bribes de papa
  const t = bac({ ...REGLAGES, decoupe_entendu: 'virgule' });
  t.ctx.entendre('Kaim, je ne sais pas. Ooh.', { source: 'telephone', cle: '1', fin: true });
  assert.ok(pistesDe(t).map(x => /Ce qu'il vient de jouer : « ([^»]*) »/.exec(x.prompt)[1]).includes('Kaim,'), 'avec « virgule », « Kaim, » seul');
});

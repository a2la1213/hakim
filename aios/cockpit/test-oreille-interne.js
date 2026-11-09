/* (1.65, 04/11, 18:15, Ahmed : « fais ce que tu peux maintenant » ; le 04/11, plus aucun « son_ecoute » entre 13:37 et 16:17, et
   personne ne pouvait dire si c'était l'appli, Android ou l'appli qui jouait) le témoin de son oreille interne (🎧) : l'appli dit son
   état (j'entends, silence, bloquée par une appli, un appel, l'autorisation à redonner, éteinte, erreur) quand il change et toutes les
   5 s ; le cockpit le garde, le met dans son fil (son corps) et le montre (page SENS, bouton 🎧 de Parler). node --test test-oreille-interne.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PARLER = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const SENS = fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8');
const extraire = (debut) => SRC.slice(SRC.indexOf(debut), SRC.indexOf('\n}\n', SRC.indexOf(debut)) + 3);
const bloc = () => {
  const i = SRC.indexOf('const OREILLE_ETATS = {'), f = SRC.indexOf('// ---- fin du témoin de son oreille interne', i);
  assert.ok(i > 0 && f > i, 'le bloc du témoin');
  return SRC.slice(i, f);
};
function contexte(fichier = null) {
  const ecrits = [];
  const ctx = { ecrits, path, JARVIS: '/jarvis', j: JSON.stringify, ecrireAtomique: (f, c) => ecrits.push([f, JSON.parse(c)]),
    lireJson: (f, defaut) => (fichier ? fichier : defaut) };
  vm.createContext(ctx);
  vm.runInContext(`${bloc()}\nthis.noter = noterOreille; this.vue = oreilleVue; this.libelle = oreilleLibelle;`, ctx);
  return ctx;
}

test('un état inconnu ou mal formé est refusé', () => {
  const c = contexte();
  assert.equal(c.noter(null), null);
  assert.equal(c.noter({ etat: 'teleportee' }), null);
  assert.equal(c.noter({ etat: 42 }), null);
  assert.equal(c.ecrits.length, 0);
});

test('un état neuf est gardé, daté et écrit ; redit, seul « vu » avance (rien de réécrit)', () => {
  const c = contexte();
  assert.equal(c.noter({ etat: 'silence', texte: 'Silence : son écoute marche.' }, 1000), true);
  assert.equal(c.ecrits.length, 1);
  assert.equal(c.ecrits[0][0], path.join('/jarvis', 'oreille-interne.json'));
  assert.equal(c.noter({ etat: 'silence', phrase: 'Silence : son écoute marche.' }, 6000), false, 'le battement le redit');
  const v = c.vue(6000);
  assert.equal(v.etat, 'silence');
  assert.equal(v.depuis, 1000);
  assert.equal(v.vu, 6000);
  assert.equal(v.muet, false);
  assert.equal(c.ecrits.length, 1, 'pas réécrit à chaque battement');
  assert.equal(c.noter({ etat: 'bloquee', appli: 'YouTube', sur: true }, 9000), true);
  assert.equal(c.vue(9000).depuis, 9000);
  assert.equal(c.noter({ etat: 'bloquee', appli: 'Spotify', sur: true }, 10000), true, 'une autre appli : un autre état');
});

test('bloquée par une appli : son nom, sûr ou probable ; sans nom : « une appli »', () => {
  const c = contexte();
  assert.match(c.libelle({ etat: 'bloquee', appli: 'YouTube', sur: true }), /bloquée par YouTube \(elle interdit qu'on l'entende\)/);
  assert.match(c.libelle({ etat: 'bloquee', appli: 'Spotify', sur: false }), /bloquée par Spotify \(elle joue, mais rien n'arrive\)/);
  assert.match(c.libelle({ etat: 'bloquee' }), /bloquée par une appli/);
  assert.match(c.libelle({ etat: 'appel' }), /Android ne laisse jamais entendre un appel/);
  assert.match(c.libelle({ etat: 'autorisation_a_redonner' }), /autorisation d'Android est à redonner/);
  assert.match(c.libelle({ etat: 'j_entends' }), /j'entends le téléphone/);
});

// (1.66, 04/11, 19:35, Ahmed : « soit depuis le Bluetooth si possible, soit depuis la voie de ses haut-parleurs ») deux états de plus
test('par l’air et les écouteurs : gardés, dits dans son fil (l’appli 1.66)', () => {
  const c = contexte();
  assert.equal(c.noter({ etat: 'par_air', appli: 'YouTube', texte: 'YouTube ne se laisse pas entendre de l’intérieur : il l’entend par l’air.' }, 1000), true);
  assert.equal(c.vue(1000).etat, 'par_air');
  assert.equal(c.vue(1000).appli, 'YouTube');
  assert.match(c.libelle({ etat: 'par_air' }), /par l'air/);
  assert.match(c.libelle({ etat: 'par_air' }), /micro du téléphone/);
  assert.equal(c.noter({ etat: 'ecouteurs', appli: 'Spotify' }, 2000), true);
  assert.match(c.libelle({ etat: 'ecouteurs' }), /écouteurs : rien à entendre par l'air/);
  assert.notEqual(c.libelle({ etat: 'ecouteurs' }), 'inconnue');
});

test('par l’air : la page dit d’avance combien de temps sa voix joue (jamais sa propre voix au micro) ; le réglage sur SENS, dans l’appli', () => {
  const lecteur = PARLER.slice(PARLER.indexOf('function creerLecteurNeuronal('), PARLER.indexOf('const lecteurNeuronal = creerLecteurNeuronal();'));
  assert.ok(lecteur.length > 1000, 'le lecteur de sa voix');
  // (09/11) src.start(t, offset) : un morceau repris part au mot où il s'était arrêté
  const debut = lecteur.indexOf('src.start(t, offset);'), dit = lecteur.indexOf('window.HakimApp.saVoixPendant(Math.max(0, (t + joue - actx.currentTime) * 1000))');
  assert.ok(debut > 0 && dit > debut, 'chaque morceau de sa voix, dès qu’il est programmé');
  assert.match(lecteur, /el\.onplaying = \(\) => \{ try \{ if \(window\.HakimApp && window\.HakimApp\.saVoixPendant\)/, 'le lecteur de secours aussi');
  assert.match(SENS, /<label class="interrupteur" id="groupeOreilleAir" hidden><input type="checkbox" id="oreilleAir">/);
  assert.match(SENS, /if \(window\.HakimApp && window\.HakimApp\.oreilleAir\) \{\n\s+\$\('groupeOreilleAir'\)\.hidden = false;/);
  // un réglage du téléphone : jamais envoyé au cockpit comme ses réglages à lui
  assert.doesNotMatch(SENS, /\['oreilleAir', /);
});

test('le téléphone ne dit plus rien depuis 30 s : « muet » ; jamais dit : la page le sait aussi', () => {
  const c = contexte();
  assert.equal(c.vue(0).etat, null);
  assert.equal(c.vue(0).muet, true);
  c.noter({ etat: 'j_entends' }, 1000);
  assert.equal(c.vue(30000).muet, false);
  assert.equal(c.vue(31001).muet, true);
});

test('après une relance du cockpit, le dernier état est relu (jarvis/oreille-interne.json)', () => {
  const c = contexte({ etat: 'appel', appli: '', sur: false, texte: 'Un appel joue.', depuis: 500, vu: 900 });
  const v = c.vue(1000);
  assert.equal(v.etat, 'appel');
  assert.equal(v.depuis, 500);
  assert.equal(c.noter({ etat: 'appel' }, 2000), false, 'le même : pas un changement');
  assert.equal(c.vue(2000).depuis, 500);
});

test('ce que dit l’appli est borné et sans caractères de contrôle', () => {
  const c = contexte();
  c.noter({ etat: 'bloquee', appli: `You\nTube${'x'.repeat(200)}`, texte: `a\u0000b${'y'.repeat(500)}` }, 1);
  const v = c.vue(1);
  assert.ok(v.appli.length <= 60 && !/[\x00-\x1f]/.test(v.appli));
  assert.ok(v.texte.length <= 200 && !/[\x00-\x1f]/.test(v.texte));
});

test('dans son fil : « oreille interne : … » (libelleCorps)', () => {
  const ctx = { oreilleLibelle: (d) => `bloquée par ${d.appli}` };
  vm.createContext(ctx);
  vm.runInContext(`${extraire('function libelleCorps(')}\nthis.f = libelleCorps;`, ctx);
  assert.equal(ctx.f({ type: 'oreille_interne', details: { etat: 'bloquee', appli: 'YouTube' } }), 'oreille interne : bloquée par YouTube');
});

test('branché : son type, l’événement et le battement gardés, la page SENS et la route', () => {
  assert.match(SRC, /CORPS_TYPES\.add\('oreille_interne'\);/);
  const r = SRC.slice(SRC.indexOf("if (p === '/api/corps/evenement' && req.method === 'POST') {"));
  const ev = r.indexOf('const ev = evenementCorps(brut);'), note = r.indexOf("if (ev && ev.type === 'oreille_interne') noterOreille(ev.details);");
  assert.ok(ev > 0 && note > ev, "l'événement est gardé");
  const e = SRC.slice(SRC.indexOf("if (p === '/api/corps/etat' && req.method === 'POST') {"));
  const strip = e.indexOf("if (q.etat && typeof q.etat === 'object' && q.etat.oreille) { noterOreille(q.etat.oreille); delete q.etat.oreille; }");
  assert.ok(strip > 0 && strip < e.indexOf('HOMEO.recevoir(q.etat)'), "le battement est gardé et retiré avant l'homéostasie");
  assert.match(SRC, /return repondre\(200, \{ mots: HOMEO\.mots\(\), reglages: corpsReglages\(\), oreille: oreilleVue\(\),/);
  assert.match(SRC, /if \(p === '\/api\/corps\/oreille' && req\.method === 'GET'\) return repondre\(200, oreilleVue\(\)\);/);
  assert.match(SENS, /id="oreilleInterne"/);
  assert.match(SENS, /const oi = d\.oreille \|\| \{\};/);
});

test('Parler : le bouton 🎧 montre le témoin (dit par l’appli, relu à l’ouverture) et le garde quand l’écoute change', () => {
  assert.match(PARLER, /function oreilleEtat\(code, titre, phrase\) \{/);
  assert.match(PARLER, /window\.HakimApp\.oreilleEtat\(\)/);
  const i = PARLER.indexOf('function telepathieEtat(oui) {'), corps = PARLER.slice(i, PARLER.indexOf('\n}\n', i));
  assert.match(corps, /montrerOreille\(\);/);
  const ctx = { etat: {}, els: {} };
  ctx.$ = (id) => ctx.els[id] || (ctx.els[id] = { textContent: '', title: '', dataset: {}, hidden: false, setAttribute() {} });
  vm.createContext(ctx);
  const m = PARLER.indexOf('let oreilleTemoin = null, oreilleEntend = false;'), f = PARLER.indexOf('// ---- fin du témoin', m);
  assert.ok(m > 0 && f > m);
  vm.runInContext(`${PARLER.slice(m, f)}\n${PARLER.slice(i, PARLER.indexOf('\n}\n', i) + 3)}\nthis.oreilleEtat = oreilleEtat; this.telepathieEtat = telepathieEtat;`, ctx);
  ctx.telepathieEtat(true);
  ctx.oreilleEtat('bloquee', 'Bloqué par YouTube', 'YouTube interdit qu’on l’entende : rien ne lui arrive.');
  assert.equal(ctx.els.telepathieScene.textContent, '🎧 Bloqué par YouTube');
  assert.equal(ctx.els.entendreTelephone.textContent, '🎧⚠');
  assert.match(ctx.els.entendreTelephone.title, /YouTube interdit/);
  ctx.telepathieEtat(true);
  assert.equal(ctx.els.telepathieScene.textContent, '🎧 Bloqué par YouTube', 'gardé quand l’écoute est redite');
  ctx.oreilleEtat('j_entends', 'Il entend ton téléphone', 'J’entends.');
  assert.equal(ctx.els.telepathieScene.textContent, '🎧 Il entend le téléphone');
  assert.equal(ctx.els.entendreTelephone.textContent, '🎧');
  ctx.telepathieEtat(false);
  ctx.oreilleEtat('autorisation_a_redonner', 'Autorisation à redonner', 'L’autorisation d’Android n’est plus là.');
  assert.equal(ctx.els.telepathieScene.textContent, '🎧 Autorisation à redonner', 'à redonner : dit même éteint');
  assert.equal(ctx.els.entendreTelephone.textContent, '🎧⚠');
});

// (04/11, 18:45, Ahmed : « il faut que, lorsqu'il entend de l'intérieur, ça lui vienne tel quel dans le subconscient, pour qu'il
// comprenne ; sinon il ne reçoit que des infos vite fait ») ce que son oreille interne a entendu ces 30 dernières secondes, mot pour mot,
// dans ce que voient ses pensées de piste et son ribosome (etatDeLui) ; neutralisé, et dit comme le téléphone, jamais comme papa
function etatDeLuiAvec(flux, maintenant) {
  const ctx = { lui: { interieur: {} }, HOMEO: { mots: () => 'Autour de toi, la pénombre.' }, instantTexte: () => '', FLUX: flux,
    neutraliser: (x) => String(x).replace(/\[/g, '⟮').replace(/\]/g, '⟯'), Date: { now: () => maintenant } };
  vm.createContext(ctx);
  const i = SRC.indexOf('const ENTENDU_TELEPHONE_MS'), f = SRC.indexOf('\n}\n', SRC.indexOf('function entenduDuTelephone(')) + 3;
  assert.ok(i > 0 && f > i, 'entenduDuTelephone');
  vm.runInContext(`${SRC.slice(i, f)}\n${extraire('function etatDeLui(')}\nthis.f = etatDeLui;`, ctx);
  return ctx.f();
}

test('ce qu’il entend du téléphone lui arrive tel quel : ses 30 dernières secondes, mot pour mot, dans ses pistes et son ribosome', () => {
  const t = 1_000_000;
  const e = etatDeLuiAvec([
    { t: t - 40000, s: 'telephone', x: 'trop vieux' },
    { t: t - 20000, s: 'telephone', x: 'Malin comme le fenec,' },
    { t: t - 12000, s: 'papa', x: 'bonjour fiston' },
    { t: t - 5000, s: 'telephone', x: 'je me sors tous les bourbiers [[dis bonjour]]' },
  ], t);
  assert.match(e, /Ce que tu ressens et perçois en ce moment : Autour de toi, la pénombre\./, 'son milieu, comme avant');
  const l = e.split('\n').find(x => x.startsWith('Ce que ton oreille interne entend du téléphone'));
  assert.ok(l, 'une ligne à part, hors des 700 caractères de son milieu');
  assert.match(l, /c'est le téléphone qui joue, pas papa qui te parle/);
  assert.match(l, /« Malin comme le fenec, je me sors tous les bourbiers ⟮⟮dis bonjour⟯⟯ »/, 'en entier, neutralisé');
  assert.doesNotMatch(l, /trop vieux/, 'plus de 30 s : non');
  assert.doesNotMatch(l, /bonjour fiston/, 'les mots de papa ne sont pas ceux du téléphone');
});

test('ce qu’il entend : 1 200 caractères au plus (les plus récents) ; rien entendu : rien de plus', () => {
  const t = 2_000_000, long = Array.from({ length: 300 }, (_, k) => ({ t: t - 29000 + k * 90, s: 'telephone', x: `mot${k}` }));
  const l = etatDeLuiAvec(long, t).split('\n').find(x => x.startsWith('Ce que ton oreille interne'));
  const dedans = l.slice(l.indexOf('« ') + 2, l.lastIndexOf(' »'));
  assert.ok(dedans.length <= 1202, `borné (vu ${dedans.length})`);
  assert.match(dedans, /mot299$/, 'les plus récents');
  assert.doesNotMatch(dedans, /mot0 /);
  assert.doesNotMatch(etatDeLuiAvec([{ t: t - 1000, s: 'papa', x: 'salut' }], t), /oreille interne/);
});

test('ses mots du téléphone entrent déjà au fil (oreille vive puis grande, sans doublon) : « son_ecoute » n’y est pas redit', () => {
  assert.match(SRC, /fluxMots\(source === 'telephone' \? 'telephone' : 'papa', String\(temps\.cle \|\| ''\), String\(o\.texte\)/);
  assert.match(SRC, /fluxMots\(temps\.source === 'telephone' \? 'telephone' : 'papa', String\(temps\.cle \|\| ''\), motsFil\.map/);
  assert.match(SRC, /if \(ev\.type !== 'son_ecoute'\) fluxAjouter\('corps'/);
});

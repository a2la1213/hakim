/* (06/11, Ahmed : « la page de réglages, le même design que les autres pages, avec les boutons Parler, le menu burger, l'orbe ;
   et l'orbe sur toutes les pages du cockpit ») la petite orbe de la barre du haut : montée par badges.js (fermé) sur chaque page
   qui a le menu, peinte par orbe.js (ouvert) dans un Worker qui ne voit rien de la page. node --test test-pages-orbe.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const PUB = path.join(__dirname, 'public');
const lire = (f) => fs.readFileSync(path.join(PUB, f), 'utf8');

test('badges.js monte l’orbe sur toutes les pages du menu, sauf Parler qui a la sienne', () => {
  const b = lire('badges.js');
  const i = b.indexOf("if (active !== 'parler') {"), bloc = b.slice(i, b.indexOf('\n    }\n', i));
  assert.match(bloc, /so\.src = '\/orbe-coin\.js';/, 'dans le bloc « pas Parler »');
  assert.match(bloc, /window\.OrbeCoin\.monter\(nav\)/);
  assert.match(b, /\.orbe-coin\{margin-left:auto;/);
});

test('les pages fermées ne chargent jamais de code ouvert (orbe.js, nav.js) : l’orbe passe par le Worker', () => {
  for (const f of ['reglages.html', 'immunite.html', 'telephone.html', 'code.html']) {
    const t = lire(f);
    assert.ok(!/<script src="\/orbe\.js">/.test(t), `${f} ne charge pas orbe.js`);
    assert.ok(!/<script src="\/nav\.js">/.test(t), `${f} ne charge pas nav.js`);
    assert.match(t, /<script src="\/badges\.js"><\/script>/, `${f} a le menu (et donc l’orbe)`);
  }
  const c = lire('orbe-coin.js');
  assert.ok(!/orbe\.js'/.test(c.replace(/orbe-travail\.js|orbe-coin\.js/g, '')), 'orbe-coin.js ne charge pas orbe.js dans la page');
  assert.match(c, /new Worker\('\/orbe-travail\.js'\)/);
  assert.match(c, /transferControlToOffscreen\(\)/);
  // (06/11, ses modes) un seul flux, le témoin : vérifié plus bas
  assert.match(c, /fetch\('\/api\/jarvis\/interieur'/);
  assert.match(lire('orbe-travail.js'), /importScripts\('\/orbe\.js'\)/);
});

test('Réglages a la barre commune : ☰, PARLER, l’orbe, et le fond des autres pages', () => {
  const t = lire('reglages.html');
  assert.match(t, /document\.body\.classList\.add\('shell'\);\n  Badges\.suivre\(document\.querySelector\('nav\.topnav'\), 'reglages'\);/);
  assert.match(t, /<nav class="topnav" style="display:flex;gap:10px;align-items:center;padding:10px 16px"><span class="brand">AIOS<\/span><\/nav>/);
});

test('le Duel a la barre commune lui aussi', () => {
  assert.match(lire('duel.html'), /<script src="\/nav\.js"><\/script>\n  <script>initNav\('duel'\);<\/script>/);
});

test('le Worker peint vraiment : orbe.js tourne sur la toile reçue, à sa taille, et suit son humeur', () => {
  const traces = { taille: [], rempli: 0, rafs: [] };
  const ctx = new Proxy({}, { get: (o, k) => {
    if (k in o) return o[k];
    if (/^create/.test(k)) return () => ({ addColorStop() {} });
    if (k === 'fillRect') return () => { traces.rempli++; };
    return () => {};
  }, set: (o, k, v) => { o[k] = v; return true; } });
  const toile = { getContext: () => ctx, width: 0, height: 0 };
  const moi = { setTimeout, clearTimeout, performance: { now: () => 1000 }, Math, String, Number, parseInt };
  moi.self = moi;
  moi.requestAnimationFrame = (f) => { traces.rafs.push(f); return traces.rafs.length; };
  moi.cancelAnimationFrame = () => {};
  moi.importScripts = (u) => { assert.equal(u, '/orbe.js'); vm.runInContext(lire('orbe.js'), ctxVm); };
  const ctxVm = vm.createContext(moi);
  vm.runInContext(lire('orbe-travail.js'), ctxVm);
  moi.onmessage({ data: { canvas: toile, w: 60, h: 60, dpr: 2, reduit: false } });
  moi.onmessage({ data: { humeur: 'joie' } });
  traces.rafs.shift()(1016);
  assert.equal(toile.width, 120, 'la toile prend la taille de la barre × la densité de l’écran');
  assert.ok(traces.rempli > 0, 'orbe.js a peint');
  // témoin : la page cachée, il ne peint plus rien
  const avant = traces.rempli;
  moi.onmessage({ data: { visible: false } });
  traces.rafs.shift()(1032);
  assert.equal(traces.rempli, avant, 'invisible : rien à peindre');
});

// (06/11, Ahmed : « l'orbe sur chaque page du cockpit doit bouger comme partout ailleurs ») ses modes, lus sur le flux témoin
const chargerCoin = () => {
  const fen = {};
  vm.runInNewContext(lire('orbe-coin.js'), { window: fen, Math, String, Number, JSON });
  return fen.OrbeCoin;
};

test('ses modes viennent du flux : écoute, pense, parle (le temps de sa phrase), puis repos ; Stop arrête tout', () => {
  const { Etat } = chargerCoin();
  const e = Etat(), t = 1e6;
  assert.equal(e.mode(t), 'repos');
  e.recevoir('souffle', { niveau: 'ribosome', texte: 'brouillon' }, t);
  assert.equal(e.mode(t + 100), 'pense');
  assert.equal(e.mode(t + 6000), 'repos', 'sa pensée s’éteint seule');
  e.recevoir('souffle', { niveau: 'cerveau', pret: true, texte: 'x'.repeat(100) }, t);
  assert.equal(e.mode(t + 5000), 'parle');
  assert.equal(e.mode(t + 6100), 'repos', '100 caractères : environ 6 s de voix');
  e.recevoir('souffle', { niveau: 'papa', texte: 'papa parle' }, t);
  e.recevoir('spontane', { texte: 'y'.repeat(50) }, t);
  assert.equal(e.mode(t + 1000), 'ecoute', 'quand papa lui parle, l’écoute passe devant, comme dans Parler');
  assert.equal(e.mode(t + 3100), 'parle');
  e.recevoir('souffle', { niveau: 'bouton', id: 'stop' }, t + 3200);
  assert.equal(e.mode(t + 3300), 'repos', 'Stop : plus rien');
  assert.ok(e.recevoir('rire', { degre: 3 }, t).pulser > 0.5, 'un rire la fait battre');
  assert.ok(e.recevoir('impulsion', { x: 'frisson' }, t).pulser > 0);
  assert.deepEqual(e.recevoir('souffle', { niveau: 'reglages', mode: 'Hakim' }, t), {});
  assert.equal(e.mode(t + 100), 'repos', 'un réglage relu n’est pas une pensée');
  e.recevoir('voix_vers', { quoi: 'voix', texte: 'z'.repeat(40) }, t);
  assert.equal(e.mode(t + 100), 'parle', 'il parle sur la montre ou le téléphone : elle parle aussi');
});

test('la page n’envoie que des états au Worker (jamais un texte), et une seule connexion témoin, fermée quand la page est cachée', () => {
  const c = lire('orbe-coin.js');
  const envois = [...c.matchAll(/travail\.postMessage\(\{ ([a-z]+)/g)].map((m) => m[1]);
  assert.deepEqual([...new Set(envois)].sort(), ['canvas', 'humeur', 'mode', 'pulser', 'visible', 'w'].sort());
  assert.equal((c.match(/new EventSource\(/g) || []).length, 1);
  assert.match(c, /new EventSource\('\/api\/jarvis\/flux-orbe'\)/, 'le témoin, jamais le vrai flux');
  assert.ok(!/\/api\/jarvis\/flux['?]/.test(c));
  assert.match(c, /\} else \{ fermer\(\);/, 'caché : la connexion se ferme');
  assert.match(c, /readyState === 2\) \{ flux = null; absent = true; \}/, 'un cockpit d’avant le témoin (404) : jamais de nouvel essai');
});

test('le serveur : le flux témoin ne compte ni comme une page qui dit ses réponses, ni comme une Conversation, ni comme un appareil', () => {
  const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(src, /if \(p === '\/api\/jarvis\/flux' \|\| p === '\/api\/jarvis\/flux-orbe'\) \{/);
  assert.match(src, /if \(p === '\/api\/jarvis\/flux-orbe'\) res\.temoin = true;\n    else \{ const a = /);
  const re = /if \(!lot\.length \|\| !\[\.\.\.abonnesPensees\]\.some\(r => !r\.temoin\)\) return false;/;
  assert.match(src, re);
  assert.match(src, /abonnesPensees && !\[\.\.\.abonnesPensees\]\.some\(r => !r\.temoin\)\);/);
  // témoin : la fonction qui les redit, isolée : un témoin seul ne fait pas une page ; une vraie page, si
  const i = src.indexOf('function reecouterNonDites('), corps = src.slice(i, src.indexOf('\n}\n', i) + 2);
  const essai = (abonnes) => { const dits = []; const f = new Function('abonnesPensees', 'diffuser', 'j', `${corps}; return reecouterNonDites;`)(abonnes, (e, n) => dits.push(n), JSON.stringify);
    return [f([{ texte: 'a', origine_ts: 1 }], 2), dits.length]; };
  assert.deepEqual(essai(new Set([{ temoin: true }, { temoin: true }])), [false, 0], 'seulement des témoins : rien de redit, elles restent gardées');
  assert.deepEqual(essai(new Set([{ temoin: true }, { appareil: 'mac' }])), [true, 1]);
});

test('le Worker suit ses modes : il parle ou on lui parle, la voix simulée bouge l’orbe ; mouvements réduits : pas de voix simulée', () => {
  for (const reduit of [false, true]) {
    let src = null;
    const moi = { setTimeout, clearTimeout, performance: { now: () => 1234 }, Math, String, Number, parseInt };
    moi.self = moi;
    moi.requestAnimationFrame = () => 1; moi.cancelAnimationFrame = () => {};
    moi.importScripts = () => { moi.Orbe = { creer: () => ({ source: (f) => { src = f; }, mode() {}, humeur() {}, pulser() {} }) }; };
    vm.runInContext(lire('orbe-travail.js'), vm.createContext(moi));
    moi.onmessage({ data: { canvas: {}, w: 60, h: 60, dpr: 1, reduit } });
    assert.equal(src(), null, 'au repos : rien');
    moi.onmessage({ data: { mode: 'parle' } });
    const v = src();
    if (reduit) assert.equal(v, null);
    else { assert.ok(v.niveau > 0 && v.bandes.length === 3, 'il parle : un niveau et trois bandes'); }
    moi.onmessage({ data: { mode: 'ecoute' } });
    const ve = src();
    if (reduit) assert.equal(ve, null); else assert.ok(ve && ve.niveau > 0 && ve.niveau <= v.niveau, 'on lui parle : elle bouge aussi, plus doucement');
    moi.onmessage({ data: { mode: 'pense' } });
    assert.equal(src(), null, 'il pense : elle tourne plus vite (orbe.js), sans voix');
    moi.onmessage({ data: { mode: 'n’importe quoi' } });
    moi.onmessage({ data: { mode: 'repos' } });
    assert.equal(src(), null);
  }
});

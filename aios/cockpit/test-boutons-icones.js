/* (04/11, 19:30, Ahmed : « Les boutons dans l'interface, tu peux mettre des icônes au lieu de "Ma voix", "Conversation",
   "Télépathie", etc. ? Un truc plus cool et parlant, et mieux agencé et organisé, stp. Et vérifie bien que tous les boutons
   fonctionnent, stp. ») Les boutons de Parler en icônes SVG en ligne, rangés par sens ; chacun garde son nom (aria-label, title),
   ses id et son geste. node --test test-boutons-icones.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const habit = fs.readFileSync(path.join(__dirname, 'public', 'boutons.js'), 'utf8');

// la balise ouvrante et le contenu d'un bouton (ou d'un lien) par son id
function element(id) {
  const i = html.indexOf(` id="${id}"`);
  assert.ok(i > 0, `${id} est dans la page`);
  const debut = html.lastIndexOf('<', i);
  const nom = html.slice(debut + 1).match(/^[a-z]+/)[0];
  const finOuvrante = html.indexOf('>', i);
  const fin = html.indexOf(`</${nom}>`, finOuvrante);
  return { nom, ouvrante: html.slice(debut, finOuvrante + 1), dedans: html.slice(finOuvrante + 1, fin) };
}
const attribut = (o, a) => { const m = o.match(new RegExp(`\\s${a}="([^"]*)"`)); return m ? m[1] : null; };

// les boutons en icônes : la barre (écrire, parler, lui, ses sens), l'en-tête, la grande orbe, l'aperçu de la caméra
const BARRE = ['joindre', 'envoyer', 'stop', 'sonHakim', 'sesParoles', 'pause', 'muet', 'conversation', 'micro', 'telepathie',
  'orbeRetour', 'camera', 'ecran', 'entendreTelephone'];
const TETE = ['nouvelle', 'btnVolant', 'btnEnOff', 'lienCode', 'btnReglages'];
const SCENE = ['muetScene', 'ecranScene', 'telepathieScene', 'sesParolesScene', 'pauseScene', 'stopScene', 'finConversation'];
const APERCU = ['cameraFace', 'cameraCouper'];
const ICONES = [...BARRE, ...TETE, ...SCENE, ...APERCU];

test('chaque bouton de la barre, de l’en-tête et de la grande orbe a son icône SVG en ligne, un aria-label et un title en français', () => {
  for (const id of ICONES) {
    const { ouvrante, dedans } = element(id);
    assert.match(attribut(ouvrante, 'class') || '', /\bico\b/, `${id} : classe ico`);
    const nom = attribut(ouvrante, 'aria-label'), titre = attribut(ouvrante, 'title');
    assert.ok(nom && nom.trim().length > 1, `${id} : aria-label`);
    assert.ok(titre && titre.trim().length > 1, `${id} : title`);
    assert.match(nom, /[a-zà-ÿ]/i, `${id} : un nom en mots, pas un symbole`);
    assert.match(dedans, /<svg [^>]*aria-hidden="true"[^>]*>[\s\S]*?<\/svg>/, `${id} : son icône, cachée au lecteur d’écran`);
    assert.match(dedans, /<span class="lib">[^<]+<\/span>/, `${id} : son nom écrit, lu par le lecteur d’écran`);
    assert.doesNotMatch(dedans, /<use\b|xlink:href|https?:/, `${id} : rien de l’extérieur`);
  }
});

test('hors ligne : aucune police, aucune bibliothèque d’icônes ; l’habit ne fait aucune requête', () => {
  assert.doesNotMatch(html, /fonts\.googleapis|<link[^>]+href="https?:/);
  assert.doesNotMatch(habit, /fetch\(|XMLHttpRequest|import\(|https?:\/\//);
});

test('les id attendus par parler.js existent tous, une seule fois chacun', () => {
  const ids = new Set([...page.matchAll(/\$\('([A-Za-z0-9]+)'\)/g)].map(m => m[1]));
  for (const m of page.matchAll(/for \(const id of \[([^\]]+)\]\)/g)) for (const x of m[1].matchAll(/'([A-Za-z0-9]+)'/g)) ids.add(x[1]);
  assert.ok(ids.size > 100, 'les id lus dans parler.js');
  const compte = {};
  for (const m of html.matchAll(/\sid="([^"]+)"/g)) compte[m[1]] = (compte[m[1]] || 0) + 1;
  for (const id of ids) assert.equal(compte[id], 1, `#${id} : présent une fois`);
  for (const [id, n] of Object.entries(compte)) assert.equal(n, 1, `#${id} : unique`);
});

test('rangés par sens : écrire, puis lui (sa voix, ses paroles), les modes pour parler, ses sens (caméra, écran, oreille)', () => {
  const groupe = (classe) => {
    const i = html.indexOf(`<div class="groupe ${classe}"`);
    assert.ok(i > 0, `le groupe ${classe}`);
    const ouvrante = html.slice(i, html.indexOf('>', i) + 1);
    assert.match(ouvrante, /role="group"/); assert.match(ouvrante, /aria-label="[^"]+"/);
    // le groupe va jusqu'à sa balise fermante (aucun div imbriqué dans un groupe)
    const bloc = html.slice(i, html.indexOf('</div>', i));
    return [...bloc.matchAll(/<(?:button|a)\b[^>]*\sid="([^"]+)"/g)].map(m => m[1]);
  };
  assert.deepEqual(groupe('lui'), ['sonHakim', 'sesParoles', 'pause']);
  assert.deepEqual(groupe('modes'), ['muet', 'conversation', 'micro', 'telepathie', 'orbeRetour']);
  assert.deepEqual(groupe('sens'), ['camera', 'ecran', 'entendreTelephone']);
  const ecrire = html.slice(html.indexOf('<div class="rang ecrire">'), html.indexOf('<div class="rang commandes">'));
  assert.deepEqual([...ecrire.matchAll(/<button\b[^>]*\sid="([^"]+)"/g)].map(m => m[1]), ['joindre', 'stop', 'envoyer'],
    'Stop à côté d’Envoyer, comme dans une messagerie');
  assert.ok(html.indexOf('id="conversation"') < html.indexOf('id="telepathie"'), 'Télépathie après Conversation (test-oreille.js)');
});

test('des cibles d’au moins 44 px pour le doigt, et un toucher qui ne retombe pas sur l’icône', () => {
  const regle = html.match(/^\s*\.ico \{[^}]*\}/m);
  assert.ok(regle, 'la règle .ico');
  assert.match(regle[0], /min-width: 44px/); assert.match(regle[0], /min-height: 44px/);
  // la grande orbe reconnaît ses boutons par e.target.id (stopScene, pauseScene) : le toucher doit tomber sur le bouton
  assert.match(page, /if \(e\.target\.id === 'stopScene'\)/);
  assert.match(html, /\.ico > \* \{[^}]*pointer-events: none;/);
  assert.match(html, /\.alerte-hakim::after \{[^}]*inset: -8px;/, 'le petit « ! » rouge : 44 px de cible autour de ses 28 px');
});

test('allumé ou éteint, d’un coup d’œil : une couleur par bouton à bascule, l’icône change quand l’état le dit', () => {
  assert.match(html, /\.ico\[aria-pressed="true"\] \{[^}]*background:[^}]*box-shadow:/);
  const bascules = ICONES.filter(id => / aria-pressed="false"/.test(element(id).ouvrante));
  assert.ok(bascules.length >= 12, 'les boutons à bascule');
  for (const id of bascules) assert.match(html, new RegExp(`#${id}\\b[^{]*\\{[^}]*--c:`), `#${id} : sa couleur allumée`);
  // Pause → Reprendre (▶), Sa voix → coupée (haut-parleur barré)
  for (const id of ['pause', 'pauseScene', 'sonHakim']) {
    assert.match(element(id).dedans, /<svg class="i-repos"[\s\S]*<svg class="i-actif"/, `${id} : deux icônes, au repos et allumé`);
  }
  // Muet : le micro barré, comme le bouton « Muet » d'un appel sur Android ; ambre quand ton micro est coupé (jamais un 2e micro
  // à côté du grand)
  for (const id of ['muet', 'muetScene']) assert.match(element(id).dedans, /M3 3l18 18/, `${id} : le micro barré`);
  // le micro reste au centre des modes, que Muet et Orbe soient là ou non
  assert.match(html, /\.saisie \.groupe\.modes \{[^}]*grid-template-columns: 44px 44px 56px 44px 44px;/);
  assert.match(html, /\.ico\[aria-pressed="true"\] \.i-repos, \.ico:not\(\[aria-pressed="true"\]\) \.i-actif \{ display: none; \}/);
  // en Télépathie, les deux boutons de mode sont pressés (parler.js) : seul Télépathie s'allume
  assert.match(html, /:has\(#telepathie\[aria-pressed="true"\]\) #conversation\[aria-pressed="true"\]/);
});

test('l’habit est chargé avant parler.js (il garde les icônes que parler.js efface)', () => {
  const a = html.indexOf('<script src="/boutons.js"></script>'), b = html.indexOf('<script src="/parler.js"></script>');
  assert.ok(a > 0 && b > a);
});

// --- un DOM minuscule, juste ce que boutons.js touche ---
class Noeud {
  constructor(type, nom, texte = '') { this.nodeType = type; this.tagName = nom; this._texte = texte; this.childNodes = []; this.attrs = {}; this.dataset = {}; }
  get children() { return this.childNodes.filter(n => n.nodeType === 1); }
  get textContent() { return this.nodeType === 3 ? this._texte : this.childNodes.map(n => n.textContent).join(''); }
  set textContent(t) { if (this.nodeType === 3) this._texte = t; else { this.childNodes = [new Noeud(3, '#text', String(t))]; muter(this); } }
  get className() { return this.attrs.class || ''; }
  set className(c) { this.attrs.class = c; }
  get classList() { return { contains: (c) => this.className.split(/\s+/).includes(c) }; }
  getAttribute(a) { return a in this.attrs ? this.attrs[a] : null; }
  setAttribute(a, v) { this.attrs[a] = String(v); }
  appendChild(n) { this.childNodes.push(n); return n; }
  replaceChildren(...n) { this.childNodes = n; muter(this); }
  cloneNode() { const c = new Noeud(this.nodeType, this.tagName, this._texte); c.attrs = { ...this.attrs }; c.childNodes = this.childNodes.map(x => x.cloneNode(true)); return c; }
}
const observateurs = [];
function muter(n) { for (const o of observateurs) if (o.cible === n) o.enAttente = true; }
function bouton(nom, ...svgs) {
  const b = new Noeud(1, 'BUTTON');
  b.setAttribute('class', 'btn ico'); b.setAttribute('aria-label', nom);
  for (const c of svgs) { const s = new Noeud(1, 'svg'); s.setAttribute('class', c); b.appendChild(s); }
  const lib = new Noeud(1, 'SPAN'); lib.className = 'lib'; lib.appendChild(new Noeud(3, '#text', nom)); b.appendChild(lib);
  return b;
}
function monter(boutons) {
  observateurs.length = 0;
  const ctx = { window: {}, document: { querySelectorAll: () => boutons, createElement: (t) => new Noeud(1, t.toUpperCase()) },
    MutationObserver: class { constructor(f) { this.f = f; } observe(cible) { this.cible = cible; observateurs.push(this); } } };
  vm.createContext(ctx);
  vm.runInContext(habit, ctx);
  // les rappels du MutationObserver, comme le navigateur (micro-tâche), jusqu'au calme
  const vider = () => { for (let tour = 0; tour < 5; tour++) { const l = observateurs.filter(o => o.enAttente); if (!l.length) return tour; for (const o of l) { o.enAttente = false; o.f([]); } } return 99; };
  return { api: ctx.window.BoutonsIcones, vider };
}
const svgsDe = (b) => b.children.filter(n => n.tagName === 'svg').map(n => n.getAttribute('class'));
const libDe = (b) => b.children.find(n => n.classList.contains('lib')).textContent;

test('parler.js réécrit le texte d’un bouton (Pause → Reprendre) : l’icône revient, le nom va dans .lib et l’aria-label', () => {
  const pause = bouton('Pause', 'i-repos', 'i-actif');
  const { vider } = monter([pause]);
  pause.textContent = 'Reprendre';                      // ce que fait majBoutonsPause()
  const tours = vider();
  assert.ok(tours < 5, 'pas de boucle : son propre geste ne le relance pas');
  assert.deepEqual(svgsDe(pause), ['i-repos', 'i-actif']);
  assert.equal(libDe(pause), 'Reprendre');
  assert.equal(pause.getAttribute('aria-label'), 'Reprendre');
  assert.equal(pause.textContent, 'Reprendre', 'le texte lu reste le nom (les icônes n’ont pas de texte)');
  pause.textContent = 'Pause'; vider();
  assert.equal(pause.getAttribute('aria-label'), 'Pause');
});

test('les émojis de tête s’en vont du nom ; un bouton réécrit en symbole seul garde son nom d’origine', () => {
  const oreille = bouton('Entendre le téléphone', 'i'), scene = bouton('Entendre le téléphone', 'i'), ecran = bouton('Écran', 'i');
  const { api, vider } = monter([oreille, scene, ecran]);
  oreille.textContent = '🎧⚠';                           // montrerOreille() : l'alerte
  scene.textContent = '🎧 Bloqué par YouTube';
  ecran.textContent = '👁 Écran';                        // ecranEtat(true)
  vider();
  assert.equal(oreille.getAttribute('aria-label'), 'Entendre le téléphone');
  assert.equal(libDe(oreille), 'Entendre le téléphone');
  assert.equal(scene.getAttribute('aria-label'), 'Bloqué par YouTube');
  assert.equal(ecran.getAttribute('aria-label'), 'Écran');
  assert.equal(api.nettoyer('Rouvrir mon micro (coupé par Hakim)'), 'Rouvrir mon micro (coupé par Hakim)');
  assert.equal(api.nettoyer('🎧 Il entend le téléphone'), 'Il entend le téléphone');
  assert.equal(api.nettoyer('Regarde l’écran'), 'Regarde l’écran');
});

// (04/11, 19:30, vu à l'essai des boutons) « Ses paroles » lit sesParoles hors conversation et sesParolesEpissage en conversation
// épissée : le bouton gardait l'état de l'autre clé quand la conversation commençait ou finissait, et le premier toucher semblait
// ne rien faire. Son état est remis à jour à chaque début et fin de conversation.
test('« Ses paroles » montre le bon état quand la conversation commence ou finit', () => {
  const corps = (nom) => { const i = page.indexOf(`function ${nom}(`); return page.slice(i, page.indexOf('\n}\n', i)); };
  assert.match(corps('basculerConversation'), /\$\('conversation'\)\.setAttribute\('aria-pressed', 'true'\);\n\s+majSesParoles\(\);/);
  assert.match(corps('finirConversation'), /\$\('telepathie'\)\.setAttribute\('aria-pressed', 'false'\);\n\s+majSesParoles\(\);/);
  // le bon état, selon la clé du moment
  const ctx = { etat: { conversation: null, reglages: { sesParoles: true, sesParolesEpissage: false } }, reglagesCorps: { epissage: true }, boutons: {} };
  ctx.$ = (id) => ctx.boutons[id] || (ctx.boutons[id] = { setAttribute(a, v) { this[a] = v; } });
  vm.createContext(ctx);
  const ligne = (debut) => { const i = page.indexOf(debut); return page.slice(i, page.indexOf('\n', i)).replace(/^const /, 'var '); };
  vm.runInContext(`${ligne('const voixEpissee = ')}\n${corps('majSesParoles')}\n}\nthis.majSesParoles = majSesParoles;`, ctx);
  ctx.majSesParoles();
  assert.equal(ctx.boutons.sesParolesScene['aria-pressed'], 'true', 'hors conversation : sesParoles');
  ctx.etat.conversation = {}; ctx.majSesParoles();
  assert.equal(ctx.boutons.sesParolesScene['aria-pressed'], 'false', 'en conversation épissée : sesParolesEpissage');
  assert.equal(ctx.boutons.sesParoles['aria-pressed'], 'false');
});

// (04/11, Ahmed, sur la capture de la barre : « il y a juste à écrire un truc plus court, sinon c'est parfait »)
test('le champ dit court ce qu’il attend : une ligne, même sur le Fold plié', () => {
  assert.match(html, /<textarea id="q" rows="1" placeholder="Écris à Hakim…"/);
});

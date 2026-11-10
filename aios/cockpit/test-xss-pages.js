/* (11/11, Ahmed : « oui », après le scan de sécurité du système immunitaire) une donnée piégée ne devient jamais du HTML dans
   les pages du cockpit : un titre, un nom, une pensée ou une adresse qui contient « <img src=x onerror=…> » s'affiche en texte.
   Les fonctions sont prises telles quelles dans les pages et lancées à part (vm) : retirer un esc() fait échouer ce test.
   node --test test-xss-pages.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Voix = require('./public/voix.js');

const lire = (f) => fs.readFileSync(path.join(__dirname, 'public', f), 'utf8');
// une fonction entière, de sa déclaration à son accolade fermante (au même retrait)
const prendre = (src, debut, fin = '\n}\n') => {
  const i = src.indexOf(debut);
  assert.ok(i >= 0, `introuvable : ${debut}`);
  return src.slice(i, src.indexOf(fin, i) + fin.length);
};
const ligne = (src, debut) => { const i = src.indexOf(debut); assert.ok(i >= 0, `introuvable : ${debut}`); return src.slice(i, src.indexOf('\n', i) + 1); };
const ESC = ligne(lire('nav.js'), 'window.esc = ').replace('window.esc = ', 'const esc = ');   // l'échappement commun des pages

const PIEGE = '"><img src=x onerror=alert(1)>';
const PIEGE_URL = 'blob:x" onerror="alert(1)';
function jamaisDuHtml(html, ou) {
  assert.ok(!/<img src=x/i.test(html), `${ou} : la donnée piégée est devenue du HTML :\n${html}`);
  assert.ok(!/<[a-z]+[^>]*\sonerror=["']alert/i.test(html), `${ou} : un attribut piégé est sorti de ses guillemets :\n${html}`);
}
const enTexte = (html, ou) => assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt;'), `${ou} : la donnée doit rester visible, en texte :\n${html}`);
const decoder = (s) => s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
function element() {
  return { innerHTML: '', textContent: '', hidden: true, style: {}, offsetWidth: 100, offsetHeight: 40, dataset: {},
    querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, focus() {}, classList: { add() {}, remove() {} } };
}
function lancer(code, globals = {}) {
  const els = {};
  const ctx = { console, Math, Number, String, Object, Array, JSON, Date, Set, Map, Promise, RegExp, Voix,
    $: (id) => (els[id] = els[id] || element()), els, ...globals };
  vm.createContext(ctx);
  vm.runInContext(`${ESC}\n${code}`, ctx);
  return ctx;
}

test('parler.js : le texte de Hakim (markdown léger) reste du texte ; le gras, le code, les formules et les liens gardent leur forme', () => {
  const P = lire('parler.js');
  const ctx = lancer([prendre(P, 'function gras('), prendre(P, 'function formule('), prendre(P, 'function blocCode('),
    prendre(P, 'function texteRiche('), prendre(P, 'function liens('), 'this.texteRiche = texteRiche;'].join('\n'), { window: {} });
  const cas = {
    'texte nu': PIEGE,
    'gras': `**${PIEGE}**`,
    'code dans la phrase': `\`${PIEGE}\``,
    'bloc de code': `\`\`\`html\n${PIEGE}\n\`\`\``,
    'formule': `$${PIEGE}$`,
    'texte d’un lien': `[${PIEGE}](https://exemple.org/a)`,
    'adresse d’un lien': `voir https://exemple.org/${PIEGE}`,
  };
  for (const [ou, t] of Object.entries(cas)) { const h = ctx.texteRiche(t); jamaisDuHtml(h, ou); if (!ou.startsWith('adresse')) enTexte(h, ou); }   // (l'adresse coupe le texte : un lien, puis la suite en texte)
  // ce que la page fabrique exprès est toujours là
  assert.match(ctx.texteRiche('**fort** et *doux*'), /<strong>fort<\/strong> et <em>doux<\/em>/);
  assert.match(ctx.texteRiche('[la source](https://exemple.org/x)'), /<a href="https:\/\/exemple\.org\/x" target="_blank" rel="noopener noreferrer">la source<\/a>/);
  assert.match(ctx.texteRiche('`a < b`'), /<code>a &lt; b<\/code>/);
});

test('parler.js : le pavé de sa pensée, ses pensées, ce qu’il entend et ses réactions n’injectent rien', () => {
  const P = lire('parler.js');
  const ctx = lancer([ligne(P, 'const MOTS_EPISSES = '), prendre(P, 'function htmlPave('), ligne(P, 'const TITRE_EPISSURE = '),
    ligne(P, 'const attenteDe = '), ligne(P, 'const htmlEpissure = '), prendre(P, 'function poserPave('),
    ligne(P, 'const TITRE_ENTENDU = '), ligne(P, 'const TITRE_LIVE = '), prendre(P, 'function montrerEntendu('), prendre(P, 'function montrerPensee('),
    `const REACTIONS = ['❤️', ${JSON.stringify(PIEGE)}];\nlet reactionPour = null;`, prendre(P, 'function ouvrirReactions('),
    'this.poserPave = poserPave; this.htmlEpissure = htmlEpissure; this.montrerEntendu = montrerEntendu; this.montrerPensee = montrerPensee;',
    'this.ouvrirReactions = ouvrirReactions; this.etat = etat;'].join('\n'),
  { etat: { aCote: [], reglages: {}, messages: [{ id: 'm1', qui: 'j', texte: 'salut' }] }, rendre() {}, window: { innerWidth: 400 }, navigator: {} });
  const pave = { cle: 'pave-1', textes: [PIEGE], lus: 0, interne: PIEGE, episse: PIEGE, coeur: 3 };
  ctx.poserPave('pave-1', PIEGE, ctx.htmlEpissure(pave));            // un titre piégé, sous l'orbe et dans le fil
  jamaisDuHtml(ctx.els.epissureScene.innerHTML, 'pavé sous l’orbe'); enTexte(ctx.els.epissureScene.innerHTML, 'pavé sous l’orbe');
  jamaisDuHtml(ctx.etat.aCote.map(x => x.html).join(''), 'pavé dans le fil');
  ctx.montrerPensee(PIEGE, PIEGE, true);
  ctx.montrerEntendu({ cle: 'pave-entendu', voix: PIEGE, pave: PIEGE, mots: [0, 2], pensees: [PIEGE], dits: [PIEGE] });
  ctx.montrerEntendu({ cle: 'pave-entendu-2', live: true, pensees: [PIEGE], dits: [PIEGE] });
  const fil = ctx.etat.aCote.map(x => x.html).join('');
  jamaisDuHtml(fil, 'ses pensées et ce qu’il entend'); enTexte(fil, 'ses pensées et ce qu’il entend');
  assert.match(fil, /<span class="quand">🎧 le téléphone joue/, 'le titre voulu reste affiché');
  assert.match(fil, /<b class="garde" style="font-style:normal">/, 'les mots gardés restent allumés');
  assert.match(fil, /💭 &quot;&gt;&lt;<b class="garde" style="font-style:normal">img<\/b>/, 'ce qu’il y a entre ses mots est échappé aussi');
  ctx.ouvrirReactions('m1', 10, 10);
  jamaisDuHtml(ctx.els.reactions.innerHTML, 'réactions'); enTexte(ctx.els.reactions.innerHTML, 'réactions');
  assert.match(ctx.els.reactions.innerHTML, /data-reaction="❤️"/);
});

test('brain.js : le numéro, la rubrique et le texte d’un souvenir restent du texte', () => {
  const B = lire('brain.js');
  const ctx = lancer([prendre(B, 'function fmtDate('), prendre(B, 'function showTooltip('), prendre(B, 'function openDetail('), prendre(B, 'function renderDetail('),
    'this.showTooltip = showTooltip; this.openDetail = openDetail; this.renderDetail = renderDetail;'].join('\n'),
  { nodes: [{ id: PIEGE, rubric: PIEGE, snippet: PIEGE, ts: 1762800000, wm: PIEGE }], pinnedIdx: -1, colorOf: () => ({ getHexString: () => 'a1b2c3' }),
    detailIdEl: element(), detailEl: element(), detailBody: element(), tooltip: element(), innerWidth: 800, innerHeight: 600,
    fetch: () => new Promise(() => {}) });
  ctx.openDetail(0);
  jamaisDuHtml(ctx.detailBody.innerHTML, 'détail en chargement'); enTexte(ctx.detailBody.innerHTML, 'détail en chargement');
  ctx.renderDetail(ctx.nodes[0], { rubric: PIEGE, content: PIEGE, facets: [PIEGE], role: PIEGE, session_id: PIEGE, ts: 1762800000 });
  jamaisDuHtml(ctx.detailBody.innerHTML, 'détail du souvenir');
  ctx.showTooltip(0, 10, 10);
  jamaisDuHtml(ctx.tooltip.innerHTML, 'bulle du souvenir'); enTexte(ctx.tooltip.innerHTML, 'bulle du souvenir');
});

test('atelier-page.js : le lecteur et les créations en cours n’injectent ni un titre ni une adresse', async () => {
  const A = lire('atelier-page.js');
  const ctx = lancer([`let etat = null, retour = null;\nconst urlDe = async () => ${JSON.stringify(PIEGE_URL)};\nconst dire = () => {};`,
    prendre(A, '  async function ouvrir(', '\n  }\n'), prendre(A, '  function rendreCalculs(', '\n  }\n'),
    'this.ouvrir = ouvrir; this.rendreCalculs = rendreCalculs; this.poserEtat = (e) => { etat = e; };'].join('\n'),
  { document: { activeElement: null } });
  for (const video of [false, true]) {
    await ctx.ouvrir(PIEGE, video, PIEGE);
    jamaisDuHtml(ctx.els.lecteur.innerHTML, video ? 'lecteur de clip' : 'lecteur d’image');
    assert.match(ctx.els.lecteur.innerHTML, video ? /<video controls/ : /<img src="blob:x&quot; onerror=&quot;alert\(1\)"/);
  }
  ctx.poserEtat({ enCours: [{ type: 'image', titre: PIEGE, tache: PIEGE, progres: { f: 0.5, texte: PIEGE } }, { type: 'clip', titre: PIEGE, etat: 'ratée', erreur: PIEGE }] });
  ctx.rendreCalculs();
  jamaisDuHtml(ctx.els.calculs.innerHTML, 'créations en cours'); enTexte(ctx.els.calculs.innerHTML, 'créations en cours');
});

test('synapses.html : le nom d’un chemin reste du texte, dans le dessin comme dans sa bulle', () => {
  const S = lire('synapses.html');
  const i = S.indexOf('  const FAMILLES = '), j = S.indexOf('  async function charger()');
  assert.ok(i > 0 && j > i);
  const ctx = lancer(`const document = { getElementById: $, addEventListener() {} };\n${S.slice(i, j)}\n`
    + 'this.reseau = reseau; this.declencheurs = declencheurs; this.poids = poids; this.pensees = pensees; this.histoire = histoire;');
  const d = {
    familles: { piste: { [`sonnet|${PIEGE}`]: { poids: 0.4, n: 6 } }, voie: { 'oui|premiere': { poids: 0.8, n: 3 } }, meuble: { [PIEGE]: { poids: 0.2, n: 9, elaguee: true } },
      declencheur: { [PIEGE]: { poids: 0.5, n: 2 } } },
    parcours: [{ chemins: { piste: `sonnet|${PIEGE}`, voie: 'oui|premiere', meuble: PIEGE }, score: 0.7, extrait: PIEGE, voix: 'dite', t: 1762800000000 }],
    historique: [{ evenement: PIEGE, famille: 'meuble', id: PIEGE, poids: 0.2, t: 1762800000000 }],
  };
  ctx.reseau(d); ctx.declencheurs(d); ctx.poids(d); ctx.pensees(d); ctx.histoire(d);
  const dessin = ctx.els.reseau.innerHTML;
  assert.match(dessin, /^<svg class="reseau" viewBox="0 0 900 \d+"/, 'le dessin reste un SVG');
  jamaisDuHtml(dessin, 'dessin des connexions'); enTexte(dessin, 'dessin des connexions');
  const bulles = [...dessin.matchAll(/data-info="([^"]*)"/g)].map(m => decoder(m[1]));   // ce que la bulle met dans innerHTML au survol
  assert.ok(bulles.length >= 3);
  for (const b of bulles) jamaisDuHtml(b, 'bulle d’un chemin');
  for (const id of ['declencheurs', 'poids', 'pensees', 'histoire']) jamaisDuHtml(ctx.els[id].innerHTML, id);
});

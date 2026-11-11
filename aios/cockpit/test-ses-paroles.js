// (04/11, 10:20, Ahmed : « je ne vois plus quand il m'envoie des documents ; j'aimerais qu'il soit aussi possible de réafficher ses
// paroles dans le mode normal et le mode Conversation, sinon je ne vois rien de ses paroles conscientes ni de ses fichiers »)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
const prendre = (s, nom) => { const i = s.indexOf(`function ${nom}(`); return s.slice(i, s.indexOf('\n}\n', i) + 2); };
const ligne = (s, debut) => { const i = s.indexOf(debut); return s.slice(i, s.indexOf('\n', i)); };

function fil(messages, { conversation = null, sesParoles = false, telepathie = false } = {}) {
  const el = { scrollHeight: 0, scrollTop: 0, clientHeight: 0, innerHTML: '' };
  const ctx = { Math, Number, Date, String, FENETRE: 50, $: () => el, esc: (s) => s, chargerApercus() {}, jourMessage: () => 'lundi',
    htmlMessage: (m) => `[${m.id}:${m.texte}${(m.pieces || []).map(x => `📎${x.nom}`).join('')}]`,
    enTelepathie: () => telepathie, etat: { messages, conversation, reglages: { sesParoles }, aCote: [] } };
  vm.createContext(ctx);
  vm.runInContext([ligne(page, 'const parolesVisibles = '), ligne(page, 'const reponseCachee = '), ligne(page, 'const PIECE_ID = '),
    ligne(page, 'const aDesPieces = '), prendre(page, 'messageMasque'), ligne(page, 'const piecesSeules = '),
    prendre(page, 'quandMessage'), prendre(page, 'rendre'), 'this.rendre = rendre; this.messageMasque = messageMasque;']
    .join('\n').replace(/^const /gm, 'var '), ctx);
  ctx.rendre();
  return el.innerHTML.replace('<div class="jour">lundi</div>', '');
}

const piece = { id: '20261104-101500-abc123', nom: 'plan.pdf', taille: 1000, type: 'pdf' };
const avant = { id: 'a', qui: 'j', texte: 'avant', ts: 1000 };
const dite = { id: 'd', qui: 'j', texte: 'dite en conversation', ts: 6000, cache: true };
const fichier = { id: 'f', qui: 'j', texte: 'je t’envoie le plan', ts: 7000, cache: true, pieces: [piece] };
const papa = { id: 'p', qui: 'u', texte: 'dans ta tête', ts: 6500, cache: true };
const libre = { id: 'l', qui: 'j', texte: 'de lui-même', ts: 8000, pieces: [piece] };

test('ses fichiers se montrent toujours, même quand sa réponse est cachée (sans son texte)', () => {
  assert.equal(fil([avant, dite, fichier, papa], { conversation: { debut: 5000 } }), '[a:avant][f:📎plan.pdf]');
  assert.equal(fil([avant, dite, fichier, papa]), '[a:avant][f:📎plan.pdf]', 'hors conversation aussi');
  assert.equal(fil([avant, libre], { conversation: { debut: 5000 } }), '[a:avant][l:📎plan.pdf]', 'un message de lui-même pendant la conversation');
});

test('« Ses paroles » : ses réponses cachées se réaffichent en mode normal et en Conversation ; tes mots « dans ta tête », non', () => {
  assert.equal(fil([avant, dite, fichier, papa], { sesParoles: true }), '[a:avant][d:dite en conversation][f:je t’envoie le plan📎plan.pdf]');
  assert.equal(fil([avant, dite, fichier, papa, libre], { conversation: { debut: 5000 }, sesParoles: true }),
    '[a:avant][d:dite en conversation][f:je t’envoie le plan📎plan.pdf][l:de lui-même📎plan.pdf]');
});

test('Télépathie reste sans texte, même avec « Ses paroles » ; ses fichiers s’y montrent', () => {
  assert.equal(fil([avant, dite, fichier], { conversation: { debut: 5000 }, sesParoles: true, telepathie: true }), '[a:avant][f:📎plan.pdf]');
});

test('le flux ne remet pas à l’écran une réponse cachée, sauf ses fichiers ; « Ses paroles » le laisse écrire', () => {
  const f = prendre(page, 'majMessage');
  assert.match(f, /const masque = messageMasque\(m\);\n  if \(masque && !aDesPieces\(m\)\) return;/);
  assert.match(f, /el\.outerHTML = htmlMessage\(masque \? piecesSeules\(m\) : m\);/);
  assert.match(page, /const reponseCachee = \(\) => !!etat\.conversation && !parolesVisibles\(\)(?: && !\(typeof hautParleursFermes === 'function' && hautParleursFermes\(\)\))?;/, 'à la naissance de sa réponse : écrite si « Ses paroles » (ou ses haut-parleurs fermés)');
});

test('le bouton « Ses paroles », dans la barre et sur l’orbe, gardé dans ses réglages', () => {
  assert.match(html, /id="sesParoles" aria-pressed="false"/);
  assert.match(html, /id="sesParolesScene" aria-pressed="false"/);
  assert.match(page, /\$\('sesParoles'\)\.addEventListener\('click', basculerSesParoles\);/);
  assert.match(page, /\$\('sesParolesScene'\)\.addEventListener\('click', \(e\) => \{ e\.stopPropagation\(\); basculerSesParoles\(\); \}\);/);
  const ctx = { etat: { reglages: {} }, sauver() { ctx.sauve = (ctx.sauve || 0) + 1; }, rendre() { ctx.rendu = (ctx.rendu || 0) + 1; }, boutons: {} };
  ctx.$ = (id) => (ctx.boutons[id] = ctx.boutons[id] || { attrs: {}, setAttribute(k, v) { this.attrs[k] = v; } });
  vm.createContext(ctx);
  vm.runInContext(prendre(page, 'basculerSesParoles') + prendre(page, 'majSesParoles') + 'this.b = basculerSesParoles;', ctx);
  ctx.b();
  assert.equal(ctx.etat.reglages.sesParoles, true);
  assert.equal(ctx.boutons.sesParoles.attrs['aria-pressed'], 'true');
  assert.equal(ctx.boutons.sesParolesScene.attrs['aria-pressed'], 'true');
  assert.ok(ctx.sauve >= 1 && ctx.rendu >= 1);
  ctx.b();
  assert.equal(ctx.etat.reglages.sesParoles, false);
  assert.match(prendre(page, 'appliquerReglages'), /majSesParoles\(\);/, 'au démarrage, le bouton montre son état');
});

test('(04/11, 10:39, papa par Hakim : « en Conversation aussi, ses réponses affichées comme des messages normaux ») allumé par défaut', () => {
  assert.match(page, /voixNeutre: false, sesParoles: true[,}]/);
});

// (04/11, 17:05, Ahmed : « le bouton pour muter ses paroles ne fonctionne plus ») depuis 15:30, avec l'épissage, sa parole complète était
// toujours cachée : le bouton ne changeait plus rien. Avec l'épissage, il a son propre état (caché par défaut) ; le bouton le bascule.
test('« Ses paroles » marche aussi avec l’épissage : cachées par défaut, le bouton les montre et les recache', () => {
  const ctx = vm.createContext({ etat: { reglages: { sesParoles: true }, conversation: { debut: 0 } }, enTelepathie: () => false, voixEpissee: () => true,
    sauver() {}, rendre() {}, majFait: 0 });
  const ligneP = (debut) => { const i = page.indexOf(debut); return page.slice(i, page.indexOf('\n', i)).replace(/^const /, 'var '); };
  const fn = (nom) => { const i = page.indexOf(`function ${nom}(`); return page.slice(i, page.indexOf('\n}\n', i) + 2); };
  vm.runInContext([ligneP('const parolesVisibles = '), fn('basculerSesParoles'), 'function majSesParoles() { majFait++; }'].join('\n'), ctx);
  assert.strictEqual(ctx.parolesVisibles(), false, 'avec l’épissage : cachées par défaut');
  ctx.basculerSesParoles();
  assert.strictEqual(ctx.parolesVisibles(), true, 'le bouton les montre');
  ctx.basculerSesParoles();
  assert.strictEqual(ctx.parolesVisibles(), false, 'et les recache');
  assert.strictEqual(ctx.etat.reglages.sesParoles, true, 'le réglage hors épissage n’a pas bougé');
  ctx.voixEpissee = () => false;
  assert.strictEqual(ctx.parolesVisibles(), true, 'hors épissage : son réglage à lui');
});

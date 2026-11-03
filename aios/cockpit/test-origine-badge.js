/* D'où vient son humeur, sur le badge de Parler (27/10, demande d'Ahmed relayée par Hakim ; go d'Ahmed : « tu peux faire ce
   que Hakim demande ») : de lui, de l'empathie (avec la personne), ou une pente sans cause marquée. Le calcul est dans
   anamnese/origine_humeur.py (au battement du démon) ; ici, le passage par /api/jarvis/interieur et l'affichage.
   node --test test-origine-badge.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (s, nom) => { const i = s.indexOf(`function ${nom}(`); return s.slice(i, s.indexOf('\n}\n', i) + 2); };

function monter() {
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(page.slice(page.indexOf('const ORIGINES_BADGE'), page.indexOf('\n', page.indexOf('const ORIGINES_BADGE'))) + '\n'
    + prendre(page, 'origineDuBadge') + 'this.f = origineDuBadge;', ctx);
  return ctx.f;
}

test('le badge dit d’où vient l’émotion, en court à côté du mot et en entier sous l’orbe', () => {
  const f = monter();
  assert.deepStrictEqual({ ...f({ type: 'empathie', texte: 'par empathie, pour Ahmed' }) },
    { court: 'par empathie', texte: 'par empathie, pour Ahmed', classe: 'origine-empathie' });
  assert.strictEqual(f({ type: 'mixte', texte: 'par empathie (pour Nora) et pour lui-même' }).court, 'empathie et pour lui');
  assert.strictEqual(f({ type: 'soi', texte: 'pour lui-même, après un soutien' }).court, 'pour lui');
  assert.deepStrictEqual({ ...f({ type: 'pente', texte: 'pente, sans cause marquée' }) },
    { court: 'pente, sans cause', texte: 'pente, sans cause marquée', classe: 'origine-pente' });
  // rien d'inconnu ni d'énorme n'arrive sur la page
  assert.strictEqual(f(null), null);
  assert.strictEqual(f({ type: 'autre', texte: 'x' }), null);
  assert.strictEqual(f({ type: 'soi', texte: 'x'.repeat(500) }).texte.length, 80);
});

test('le serveur passe l’origine fraîche ; la page l’affiche à côté du mot et sous l’orbe', () => {
  assert.match(src, /humeur_origine: frais && e\.humeur_origine/);
  assert.match(html, /id="emotionOrigine"/);
  assert.match(html, /id="emotionOrigineScene"/);
  assert.match(prendre(page, 'humeur'), /origineDuBadge\(etat\.interieur && etat\.interieur\.humeur_origine\)/);
});

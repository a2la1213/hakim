// (08/11, Ahmed : « il entend, mais il parle dans l'appli sans rien envoyer sur le widget et la bulle flottante, donc on ne l'entend pas ! »)
// mesuré de 05:29 à 05:44 (son live, l'appli cachée derrière TikTok) : 4 envois de ses paroles au widget et à la bulle, contre 59 quand tout
// marche ; au bout de 5 min cachée, le navigateur de l'appli ne réveille plus les minuteries de la page qu'une fois par minute (sa voix
// suivante, ses paroles vers la bulle, sa fin de tour en dépendent). Un « worker » n'est pas ralenti : les minuteries de la page passent par lui.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'public', 'minuteries.js'), 'utf8');
const WORKER = fs.readFileSync(path.join(__dirname, 'public', 'minuteries-worker.js'), 'utf8');

// un faux worker, qui fait tourner minuteries-worker.js dans son propre monde, avec une horloge qu'on avance à la main
function monde() {
  let maintenant = 0;
  const attente = [];
  const wctx = { setTimeout: (f, ms) => { const h = { f, a: maintenant + ms }; attente.push(h); return h; }, clearTimeout: (h) => { const i = attente.indexOf(h); if (i >= 0) attente.splice(i, 1); },
    setInterval: (f, ms) => { const h = { f, a: maintenant + ms, ms }; attente.push(h); return h; }, clearInterval: (h) => { const i = attente.indexOf(h); if (i >= 0) attente.splice(i, 1); }, Map };
  vm.createContext(wctx);
  const page = { onmessage: null };
  wctx.postMessage = (d) => page.onmessage && page.onmessage({ data: d });
  vm.runInContext(WORKER, wctx);
  class FauxWorker { constructor() { page.w = this; } postMessage(d) { wctx.onmessage({ data: d }); } set onmessage(f) { page.onmessage = f; } }
  const natifs = [];
  const win = { Worker: FauxWorker, setTimeout: (f) => { natifs.push(f); return 7; }, setInterval: () => 8, clearTimeout: (id) => natifs.push(['ct', id]), clearInterval: (id) => natifs.push(['ci', id]) };
  win.window = win;
  vm.createContext(win);
  vm.runInContext(SRC, win);
  const avancer = (ms) => {
    const fin = maintenant + ms;
    for (;;) {
      attente.sort((x, y) => x.a - y.a);
      const h = attente[0];
      if (!h || h.a > fin) break;
      maintenant = h.a;
      if (h.ms) h.a += h.ms; else attente.shift();
      h.f();
    }
    maintenant = fin;
  };
  return { win, avancer, natifs };
}

test('setTimeout passe par le worker : à l’heure, avec ses arguments, une seule fois ; clearTimeout l’annule', () => {
  const { win, avancer } = monde();
  const vus = [];
  const id = win.setTimeout((a, b) => vus.push([a, b]), 100, 'x', 2);
  assert.ok(id >= 1e6, 'un identifiant à lui (jamais celui d’une minuterie native)');
  avancer(99); assert.deepEqual(vus, []);
  avancer(1); assert.deepEqual(vus, [['x', 2]]);
  avancer(500); assert.equal(vus.length, 1);
  const id2 = win.setTimeout(() => vus.push('non'), 50);
  win.clearTimeout(id2); avancer(100);
  assert.equal(vus.length, 1);
});

test('setInterval se répète jusqu’à clearInterval ; une erreur dans un rappel n’arrête pas les autres', () => {
  const { win, avancer, natifs } = monde();
  let n = 0;
  const id = win.setInterval(() => { n++; }, 250);
  win.setTimeout(() => { throw new Error('boum'); }, 10);
  avancer(1000);
  assert.equal(n, 4);
  win.clearInterval(id); avancer(1000);
  assert.equal(n, 4);
  assert.ok(natifs.some(x => typeof x === 'function'), 'l’erreur est relancée à part (la console la voit)');
});

test('une minuterie native d’avant (ou un texte à évaluer) reste à la minuterie native', () => {
  const { win, natifs } = monde();
  win.clearTimeout(42);
  assert.deepEqual(natifs.pop(), ['ct', 42]);
  assert.equal(win.setTimeout('alert(1)', 10), 7, 'jamais de texte évalué par le worker');
});

test('chargée avant tout le reste de Parler (voix, conversation, la page)', () => {
  const html = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
  const i = html.indexOf('<script src="/minuteries.js"></script>');
  assert.ok(i > 0 && i < html.indexOf('<script src="/voix.js">') && i < html.indexOf('<script src="/conversation.js">') && i < html.indexOf('<script src="/parler.js">'));
});

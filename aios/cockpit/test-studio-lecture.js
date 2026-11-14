// (14/11, Ahmed : « dans le studio, quand je lance le multipiste et que je mets play, ça me sort un son en double : j'entends 2 fois le
// son en décalage ») jouer() chargeait les pistes AVANT de se déclarer en lecture : un deuxième appui pendant le chargement (le bouton
// restait sur ▶︎) lançait une deuxième lecture, décalée du temps entre les deux appuis, et la première ne s'arrêtait plus jamais.
// Ces tests font tourner la vraie page (public/studio-pistes.js) dans une vm, avec un faux WebAudio qui compte les sources qui jouent.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const CODE = fs.readFileSync(path.join(__dirname, 'public/studio-pistes.js'), 'utf8');

// un élément du DOM « caméléon » : on lui écrit ce qu'on veut, il répond à tout, et garde ses écouteurs
function element() {
  const vals = { value: '', checked: false, hidden: false, disabled: false, textContent: '', innerHTML: '', style: {}, dataset: {}, selectedOptions: [] };
  const ecouteurs = {};
  const rien = () => proxy;
  const proxy = new Proxy(function () {}, {
    get(_, k) {
      if (k === 'then' || typeof k === 'symbol') return undefined;
      if (k === '_ecouteurs') return ecouteurs;
      if (k === 'addEventListener') return (t, f) => { (ecouteurs[t] = ecouteurs[t] || []).push(f); };
      if (k === 'querySelectorAll' || k === 'getElementsByClassName') return () => [];
      if (k === 'querySelector' || k === 'closest') return () => null;
      if (k === 'getBoundingClientRect') return () => ({ left: 0, top: 0, width: 800, height: 60 });
      if (k in vals) return vals[k];
      return rien;
    },
    set(_, k, v) { vals[k] = v; return true; },
    apply() { return proxy; },
  });
  return proxy;
}

function noeud() {
  const param = () => ({ value: 0, setValueAtTime() {}, linearRampToValueAtTime() {}, setTargetAtTime() {} });
  return { gain: param(), frequency: param(), Q: param(), pan: param(), threshold: param(), ratio: param(), delayTime: param(),
    type: '', buffer: null, connect() {}, disconnect() {} };
}

function environnement({ chargementMs = 40 } = {}) {
  const sources = [];
  const ctx = {
    currentTime: 0, destination: {}, sampleRate: 48000,
    createGain: noeud, createBiquadFilter: noeud, createDynamicsCompressor: noeud, createStereoPanner: noeud,
    createConvolver: noeud, createDelay: noeud,
    createBuffer: (ch, n) => ({ getChannelData: () => new Float32Array(n) }),
    createBufferSource() {
      const s = { ...noeud(), demarree: false, arretee: false, start() { s.demarree = true; }, stop() { s.arretee = true; } };
      sources.push(s); return s;
    },
  };
  const projet = { id: 'PJ1', titre: 'essai', rev: 1, tempo: 140, zones: [], rendus: [], master: {},
    pistes: [
      { id: 't1', role: 'batterie', nom: 'Batterie', f: 'a.flac', fichier: 'pistes/a.flac', volume_db: 0, pan: 0, eq: {}, comp: {}, regions: [] },
      { id: 't2', role: 'voix_hakim', nom: 'Voix', f: 'b.flac', fichier: 'pistes/b.flac', volume_db: 0, pan: 0, eq: {}, comp: {}, regions: [] },
    ] };
  const reponse = (o) => ({ ok: true, status: 200, json: async () => o });
  const els = new Map();
  const doc = { hidden: false, body: element(), getElementById: (id) => { if (!els.has(id)) els.set(id, element()); return els.get(id); },
    querySelectorAll: () => [], querySelector: () => null, addEventListener() {} };
  const fenetre = {
    jeton: () => 'x', addEventListener() {},
    StudioAudio: { contexte: async () => ctx, dire() {}, recharger() {}, occupe: () => false,
      tamponDe: () => new Promise(r => setTimeout(() => r({ duration: 10 }), chargementMs)) },
  };
  const bac = {
    esc: (x) => String(x == null ? '' : x).replace(/[&<>"']/g, (c) => '&#' + c.charCodeAt(0) + ';'),
    window: fenetre, document: doc, console, URLSearchParams, Map, Set, Promise, Math, Number, String, JSON, Date, Error, Float32Array,
    localStorage: { getItem: () => null, setItem() {} },
    fetch: async (u) => (String(u).startsWith('/api/studio/projets') ? reponse({ ok: true, projets: [{ id: 'PJ1', titre: 'essai', pistes: 2, rev: 1 }] })
      : String(u).startsWith('/api/studio/projet?') ? reponse({ ok: true, projet }) : reponse({ ok: true, pics: [], duree: 10 })),
    getComputedStyle: () => ({ getPropertyValue: () => '' }), devicePixelRatio: 1,
    requestAnimationFrame: () => 1, cancelAnimationFrame() {}, setInterval: () => 0, setTimeout, clearTimeout,
  };
  bac.window.document = doc;
  vm.createContext(bac);
  vm.runInContext(CODE, bac);
  const jouent = () => sources.filter(s => s.demarree && !s.arretee).length;
  const lire = doc.getElementById('mpLire');
  const appuyer = () => Promise.all((lire._ecouteurs.click || []).map(f => f({ preventDefault() {} })));
  return { bac, jouent, appuyer, sources, s: () => fenetre.StudioPistes._s };
}

const attendre = (ms) => new Promise(r => setTimeout(r, ms));

test('(14/11) deux appuis sur ▶︎ pendant le chargement : UNE seule lecture (une source par piste), pas le son en double', async () => {
  const e = environnement({ chargementMs: 40 });
  await attendre(20);                                   // la liste et le projet se chargent
  e.appuyer(); await attendre(5); e.appuyer();          // Ahmed appuie, rien ne bouge encore, il réappuie
  await attendre(120);
  assert.strictEqual(e.jouent(), 2, `2 pistes → 2 sources qui jouent, pas ${e.jouent()}`);
});

test('(14/11) après la lecture, ⏸ arrête TOUT (aucune lecture orpheline qui continue)', async () => {
  const e = environnement({ chargementMs: 40 });
  await attendre(20);
  e.appuyer(); await attendre(5); e.appuyer();
  await attendre(120);
  e.appuyer();                                          // pause
  await attendre(10);
  assert.strictEqual(e.jouent(), 0, `il reste ${e.jouent()} source(s) qui jouent après la pause`);
});

test('(14/11) le témoin : un seul appui joue ses 2 pistes, et la pause les arrête', async () => {
  const e = environnement({ chargementMs: 40 });
  await attendre(20);
  e.appuyer(); await attendre(5);
  await attendre(120);
  assert.strictEqual(e.jouent(), 2, 'la lecture normale joue ses 2 pistes');
  e.appuyer(); await attendre(5);
  assert.strictEqual(e.jouent(), 0, 'la pause arrête tout');
});

test('(14/11) un arrêt pendant le chargement (changer de projet) : la lecture en chargement ne démarre jamais', async () => {
  const e = environnement({ chargementMs: 40 });
  await attendre(20);
  e.appuyer(); await attendre(5);                       // ⏳ : les pistes se chargent
  const projet = e.bac.document.getElementById('mpProjet');
  await Promise.all((projet._ecouteurs.change || []).map(f => f({})));
  await attendre(120);
  assert.strictEqual(e.jouent(), 0, `${e.jouent()} source(s) ont démarré après l'arrêt`);
  assert.strictEqual(e.bac.document.getElementById('mpLire').textContent, '▶︎', 'le bouton revient sur ▶︎');
});

test('(14/11) le contexte audio refusé : le bouton ne reste pas bloqué sur ⏳', async () => {
  const e = environnement({ chargementMs: 40 });
  await attendre(20);
  e.bac.window.StudioAudio.contexte = async () => { throw new Error('son bloqué'); };
  e.appuyer(); await attendre(20);
  assert.strictEqual(e.bac.document.getElementById('mpLire').textContent, '▶︎');
  assert.strictEqual(e.s().charge, false);
});

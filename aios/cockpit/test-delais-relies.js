// (04/11, 11:03, Ahmed : « s'il y a un autre délai de ce type, pour qu'il écrive ou commence à réfléchir, il faut le mettre au même
// délai que ce qu'on vient de faire ; tout relier ») un seul délai, celui de la Conversation (patienceConversation, 0,3 s) : sa pensée
// prête dite à ta pause, la fin anticipée, son rebond, la dernière pensée, l'écriture vive de tes mots, la respiration qui coupe un
// morceau, et l'attente de ses trois frères sur le Mac.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (s, nom) => { const i = s.indexOf(`function ${nom}(`); return s.slice(i, s.indexOf('\n}\n', i) + 2); };

test('à la page : chaque attente de ta pause suit le délai de la Conversation', () => {
  const a = prendre(page, 'anticiperConversation');
  assert.match(a, /if \(silenceMs >= patienceConversation\(\) && typeof direPenseeSiPossible === 'function'\) direPenseeSiPossible\(\);/);
  assert.match(a, /silenceMs < Math\.min\(SILENCE_ANTICIPE_MS, patienceConversation\(\)\)/);
  assert.match(a, /const seuil = Math\.min\(patienceConversation\(\), s && s\.pret && s\.rebond \? s\.rebond \* 1000 : seuilRythme\);/);
  assert.match(prendre(page, 'rebondirDernierePensee'), /const seuil = Math\.min\(patienceConversation\(\), \(typeof rythmeVoix === 'function' \? rythmeVoix\('pause_derniere_pensee', 1\) : 1\) \* 1000\);/);
  assert.match(page, /patienceMs: finDeTourConversation,[^\n]*\n\s+pauseMs: patienceConversation,/, 'la respiration qui coupe un morceau');
  assert.match(page, /pensees_dites: dites, delai_ms: etat\.conversation \? patienceConversation\(\) : null,/, 'le délai part au Mac avec ton tour');
});

test('tes mots écrits en direct : le premier puis chaque suite après le même délai de voix', () => {
  const f = prendre(page, 'vifConversation');
  assert.match(f, /const pas = Math\.max\(5, Math\.round\(patienceConversation\(\) \/ 20\)\);/);
  assert.doesNotMatch(f, /premier \? 15 : 25/);
});

test('sur le Mac : ses trois frères attendus au plus le délai de la Conversation', () => {
  assert.match(src, /const delaiPage = Number\(q && q\.delai_ms\);\n  const freresAttente = delaiPage > 0 \? Math\.max\(100, Math\.min\(FRERES_ATTENTE_MS, delaiPage\)\) : FRERES_ATTENTE_MS;/);
  assert.match(src, /new Promise\(r => setTimeout\(\(\) => r\(''\), freresAttente\)\)\]\)/);
});

test('la respiration qui coupe un morceau : au délai donné, une seule fois ; 0,4 s sans délai donné', async () => {
  let t = 1e6, noeud = null;
  const ctx = { console, Float32Array, ArrayBuffer, DataView, Math, Blob, Date: { now: () => t },
    URL: { createObjectURL: () => 'blob:x', revokeObjectURL() {} },
    navigator: { mediaDevices: { getUserMedia: async () => ({ getTracks: () => [], getAudioTracks: () => [] }) } },
    AudioWorkletNode: class { constructor() { noeud = this; this.port = { postMessage() {}, onmessage: null }; } connect() {} disconnect() {} } };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'public', 'conversation.js'), 'utf8'), ctx);
  const actx = { sampleRate: 16000, destination: {}, audioWorklet: { addModule: async () => {} },
    createMediaStreamSource: () => ({ connect() {}, disconnect() {} }), createGain: () => ({ gain: { value: 1 }, connect() {}, disconnect() {} }) };
  const fenetre = (voix) => { const f = new Float32Array(320); for (let i = 0; i < f.length; i++) f[i] = voix ? 0.3 * Math.sin(i / 3) : 0.0005; t += 20; noeud.port.onmessage({ data: f }); };
  const essai = async (pauseMs) => {
    const vus = [];
    const cap = await ctx.Conversation.demarrer({ ctx: actx, patienceMs: () => 5000, ...(pauseMs ? { pauseMs: () => pauseMs } : {}), jarvisParle: () => false,
      surPause: () => vus.push(t), surFin() {} });
    for (let i = 0; i < 15; i++) fenetre(false);
    for (let i = 0; i < 100; i++) fenetre(true);
    const fin = t;
    for (let i = 0; i < 30; i++) fenetre(false);
    cap.arreter && cap.arreter();
    return vus.map(x => x - fin);
  };
  const a = await essai(300);
  assert.equal(a.length, 1, 'une seule fois');
  assert.ok(a[0] <= 320, `vue à ${a[0]} ms`);
  const b = await essai(null);
  assert.equal(b.length, 1);
  assert.ok(b[0] > 380 && b[0] <= 420, `sans délai donné : 0,4 s (vue à ${b[0]} ms)`);
});

// (04/11, 14:25, Ahmed : « son start, c'est ma voix ; son stop, c'est mon 1 s de silence ») avec l'épissage, ton tour (le stop de son
// ribosome) se ferme à 1 s de silence ; tes morceaux se coupent toujours à ta respiration (0,3 s)
test('avec l’épissage : ton tour se ferme à 1 s de silence (son codon stop) ; sans lui, au délai de la Conversation', () => {
  const ctx = vm.createContext({ Number, Infinity, Math, etat: { reglages: { patienceConversation: 0.3 } }, voixEpissee: () => true });
  const ligne = (debut) => { const i = page.indexOf(debut); return page.slice(i, page.indexOf('\n', i)).replace(/^const /, 'var '); };
  vm.runInContext([ligne('const patienceMs = '), ligne('const patienceConversation = '), ligne('const finDeTourConversation = ')].join('\n'), ctx);
  assert.equal(ctx.finDeTourConversation(), 1000);
  ctx.etat.reglages.patienceConversation = 1.5;
  assert.equal(ctx.finDeTourConversation(), 1500, 'un réglage plus long reste le sien');
  ctx.voixEpissee = () => false; ctx.etat.reglages.patienceConversation = 0.3;
  assert.equal(ctx.finDeTourConversation(), 300);
});

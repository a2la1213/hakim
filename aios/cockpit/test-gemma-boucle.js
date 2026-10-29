/* (29/10, la boucle de 11:09-11:13 : Gemma rechargée ~20 fois en 4 min, swap plein, la transcription de Hakim à 10 s ;
   Ahmed : « ok pour moi ») la pause du subconscient demandait le déchargement de Gemma toutes les 5 s ; un modèle déjà
   en train de se décharger (encore listé, échéance passée) était redemandé, et Ollama le rechargeait pour le décharger.
   node --test test-gemma-boucle.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`async function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (debut) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); return src.slice(i, src.indexOf('\n', i) + 1); };

// un faux Ollama : décharger un modèle qui se décharge déjà le RECHARGE d'abord (ce que montrait son journal)
function monter() {
  let maintenant = 1_800_000_000_000;
  const ollama = { modeles: [{ name: 'huihui_ai/gemma-4-abliterated:12b', expires_at: new Date(maintenant + 300000).toISOString() }], chargements: 0, demandes: 0 };
  class FausseDate extends Date { constructor(...a) { super(...(a.length ? a : [maintenant])); } static now() { return maintenant; } }
  const ctx = { JSON, Date: FausseDate, Number, Map, AbortSignal: { timeout: () => undefined }, OLLAMA: 'http://o', ROBOT_SIGNAL: '/nulle/part',
    enLocal: 0, mlxDisponible: () => true, sourcePour: () => 'abonnement', j: JSON.stringify,
    fs: { readFileSync: () => { throw new Error('absent'); } },
    fetch: async (url, o) => {
      if (url.endsWith('/api/ps')) return { json: async () => ({ models: ollama.modeles.map(m => ({ ...m })) }) };
      ollama.demandes++;
      const m = ollama.modeles[0];
      if (m && Date.parse(m.expires_at) <= maintenant) ollama.chargements++;      // relancé pour être déchargé
      if (m) m.expires_at = new Date(maintenant).toISOString();                    // « en train de se décharger »
      return { json: async () => ({}) };
    } };
  vm.createContext(ctx);
  vm.runInContext(ligne('const GEMMA_DECHARGES =') + prendre('libererGemma') + 'this.f = { libererGemma };', ctx);
  return { f: ctx.f, ollama, avancer: (ms) => { maintenant += ms; } };
}

test('une seule demande de déchargement, pas de rechargement en boucle pendant 4 minutes de conversation', async () => {
  const m = monter();
  for (let k = 0; k < 48; k++) { await m.f.libererGemma(); m.avancer(5000); }      // un battement toutes les 5 s
  assert.strictEqual(m.ollama.chargements, 0, 'Ollama n’a jamais rechargé Gemma pour la décharger');
  assert.strictEqual(m.ollama.demandes, 1);
});

test('un Gemma rechargé par quelqu’un d’autre est de nouveau déchargé, mais pas plus d’une fois par minute', async () => {
  const m = monter();
  await m.f.libererGemma();
  m.avancer(20000);
  m.ollama.modeles[0].expires_at = new Date(Date.parse(m.ollama.modeles[0].expires_at) + 600000).toISOString();   // rechargé
  await m.f.libererGemma();
  assert.strictEqual(m.ollama.demandes, 1, 'dans la minute : pas de seconde demande');
  m.avancer(41000);
  await m.f.libererGemma();
  assert.strictEqual(m.ollama.demandes, 2);
});

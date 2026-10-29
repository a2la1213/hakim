/* (29/10, Ahmed : « on la branche exactement comme toi […] on ne fait rien varier » ; « suffit juste de brancher le modèle
   gemma à la place d'Opus 5.5 […] et rien toucher au reste, pas même le subconscient ») le choix « Gemma » des réglages de
   Parler : le même claude -p que Hakim (persona entière, tous ses serveurs, même briefing, même message), pointé sur Gemma
   par la route /v1/messages d'Ollama ; seul le modèle change. node --test test-gemma.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const lire = (f) => fs.readFileSync(path.join(__dirname, f), 'utf8');
const prendreDans = (src, nom) => {
  const i = src.indexOf(`function ${nom}(`);
  assert.ok(i >= 0, `${nom} introuvable`);
  return src.slice(i, src.indexOf('\n}\n', i) + 2);
};
const serveur = lire('server.js'), page = lire('public/parler.js');
const constante = (nom) => { const m = serveur.match(new RegExp(`const ${nom} = [^\\n]*?'([^']+)'`)); assert.ok(m, `${nom} introuvable`); return m[1]; };

function charger(src, noms, globaux = {}) {
  const ctx = { String, RegExp, Number, Date, JSON, Math, Set, Infinity, process: { env: {} }, ...globaux };
  vm.createContext(ctx);
  vm.runInContext(noms.map(n => (n.startsWith('async ') ? 'async ' + prendreDans(src, n.slice(6)) : prendreDans(src, n))).join('\n')
    + `this.f = { ${noms.map(n => n.replace(/^async /, '')).join(', ')} };`, ctx);
  return ctx;
}

test('« gemma » est une source à part entière, imposée (pas de bascule), et plus le secours local', () => {
  const { f } = charger(serveur, ['forfaitALaLimite', 'sourcePour', 'sourceSuivante'],
    { abonnement: { limiteJusqua: 0 }, FORFAIT_REESSAI_MS: 600000, apiPermise: () => true });
  assert.equal(f.sourcePour('gemma'), 'gemma');
  assert.equal(f.sourcePour('local'), 'local');
  assert.equal(f.sourceSuivante('gemma', 'gemma'), null);
});

test('le cerveau Gemma : claude pointé sur Ollama, tous les alias de modèle sur Gemma, jamais une clé API', () => {
  const { f } = charger(serveur, ['envDuCerveau'],
    { OLLAMA: 'http://127.0.0.1:11434', GEMMA_CERVEAU: 'hakim-remplacant', GEMMA_MUET_MS: 45 * 60000, process: { env: { ANTHROPIC_API_KEY: 'sk-x', PATH: '/bin' } } });
  const g = f.envDuCerveau('gemma');
  assert.equal(g.ANTHROPIC_BASE_URL, 'http://127.0.0.1:11434');
  assert.ok(g.ANTHROPIC_AUTH_TOKEN, 'un jeton factice : claude n’utilise pas le forfait');
  for (const k of ['ANTHROPIC_DEFAULT_OPUS_MODEL', 'ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_HAIKU_MODEL', 'CLAUDE_CODE_SUBAGENT_MODEL'])
    assert.equal(g[k], 'hakim-remplacant', k);
  assert.equal(g.ANTHROPIC_API_KEY, undefined);
  assert.ok(Number(g.API_TIMEOUT_MS) >= 30 * 60 * 1000, 'lire tout son contexte prend des minutes : claude ne coupe pas la requête');
  assert.equal(g.PATH, '/bin');
  const a = f.envDuCerveau('abonnement');
  assert.equal(a.ANTHROPIC_BASE_URL, undefined);
  assert.equal(a.ANTHROPIC_DEFAULT_OPUS_MODEL, undefined);
});

test('changer de cerveau (Opus ↔ Gemma) repart d’une conversation neuve, avec le fil récent', () => {
  const sessionsGemma = new Set(['g1', 'g2']);
  const { f } = charger(serveur, ['cerveauChange'], { sessionsGemma, contextes: { g1: 70000, g2: 200000, o1: 150000 }, GEMMA_CONTEXTE_MAX: 110000 });
  assert.equal(f.cerveauChange('o1', 'gemma'), true, 'la conversation d’Opus ne tient pas dans Gemma (128 k au plus)');
  assert.equal(f.cerveauChange('g1', 'gemma'), false, 'sa propre conversation : elle la reprend');
  assert.equal(f.cerveauChange('g2', 'gemma'), true, 'sa conversation est devenue trop lourde pour elle');
  assert.equal(f.cerveauChange('g1', 'auto'), true, 'retour sur Opus : une conversation neuve, pas celle de Gemma');
  assert.equal(f.cerveauChange('g1', 'abonnement'), true);
  assert.equal(f.cerveauChange('o1', 'auto'), false);
  assert.equal(f.cerveauChange(null, 'gemma'), false, 'déjà neuve');
});

test('le remplaçant d’Opus n’est pas le subconscient : la pause du subconscient ne le décharge pas', async () => {
  const nom = constante('GEMMA_CERVEAU');
  const appels = [];
  const ctx = charger(serveur, ['async libererGemma'], {
    enLocal: 0, mlxDisponible: () => true, sourcePour: () => 'abonnement', OLLAMA: 'http://o', ROBOT_SIGNAL: '/nulle/part',
    fs: { readFileSync: () => { throw new Error('absent'); } }, j: JSON.stringify, AbortSignal: { timeout: () => undefined },
    fetch: async (url, o) => { appels.push([url, o && o.body]); return { json: async () => ({ models: [{ name: `${nom}:latest` }] }) }; },
  });
  await ctx.f.libererGemma();
  assert.ok(!appels.some(([, b]) => /keep_alive/.test(b || '')), `${nom} déchargé par la pause du subconscient`);
});

test('le veilleur attend Gemma bien plus longtemps qu’Anthropic : elle lit tout son contexte avant le premier mot', () => {
  const { f } = charger(serveur, ['muetPour'], { ANTHROPIC_MUET_MS: 60000, GEMMA_MUET_MS: 45 * 60000 });
  assert.equal(f.muetPour('abonnement'), 60000);
  assert.equal(f.muetPour('api'), 60000);
  assert.ok(f.muetPour('gemma') >= 30 * 60000);
});

test('branché : le choix gemma passe par cerveauPour, chaque réponse est marquée [Gemma], sans coût compté', () => {
  assert.ok(/Veilleur\.creer\(muetPour\(source\)\)/.test(serveur), 'le veilleur du cerveau suit sa source');
  assert.ok(/cerveauChange\(session, choix\)/.test(serveur), 'la rotation au changement de cerveau');
  assert.ok(/source === 'gemma' \? ' \[Gemma\]'/.test(serveur), 'le journal marque ses réponses');
  assert.ok(/cout_usd: source === 'gemma' \? 0 : o\.jetons\.cout_usd/.test(serveur), 'ses jetons ne comptent pas comme du forfait');
  assert.ok(/if \(source === 'local' \|\| source === 'gemma'\) return;/.test(serveur), 'pas de préchauffage sur la conversation d’Opus');
});

test('la page nomme Gemma quand c’est elle qui a répondu', () => {
  const { f } = charger(page, ['nomModele']);
  assert.equal(f.nomModele({ modele: 'gemma' }), 'Gemma');
  assert.equal(f.nomModele({ modele: 'opus' }), 'Opus');
  assert.equal(f.nomModele({ modele: 'opus', modeleReel: 'claude-opus-5-5' }), 'Opus 5.5');
});

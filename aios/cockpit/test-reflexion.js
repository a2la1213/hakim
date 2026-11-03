/* (03/11, Ahmed : « mets tous les modèles en réflexion minimale, ni moyenne ni haute, on va au minimum (Mini Hakim, Hakim,
   Super Hakim), et même pour le subconscient et Gemma ») : node --test test-reflexion.js
   - chaque claude qui fait vivre Hakim (ses trois voix, ses voix vivantes, sa tête de fond, son tri des souvenirs, son
     messager, son temps libre) part avec « --effort low », le plus bas que claude accepte ;
   - Gemma ne pense pas : think:false vers Ollama, et pour la remplaçante d'Opus (claude qui parle à Ollama), un pont qui
     réécrit chaque demande en thinking « disabled » (claude ne sait pas le dire à un modèle qu'il ne connaît pas). */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const fonction = (nom) => { const i = SRC.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2); };

test('le niveau de réflexion de Hakim est le plus bas : low', () => {
  const m = /^const EFFORT_HAKIM = (.+);/m.exec(SRC);
  assert.ok(m, 'EFFORT_HAKIM défini');
  assert.strictEqual(eval(m[1].replace(/process\.env\.\w+/, 'undefined')), 'low');
});

for (const nom of ['trierSouvenirs', 'sonnetTeteDeFond', 'vivantLibre', 'argsTempsLibre', 'cerveauLancer', 'lancerMessager']) {
  test(`${nom} : claude part avec l'effort de Hakim`, () => {
    assert.match(fonction(nom), /'--effort', EFFORT_HAKIM/);
  });
}

test('Gemma, appelée directement (Ollama), ne pense pas', () => {
  assert.match(fonction('repondreEnLocal'), /think: false/);
});

test('la remplaçante d\'Opus passe par le pont sans réflexion quand il est prêt', () => {
  assert.match(fonction('envDuCerveau'), /ANTHROPIC_BASE_URL: \(typeof pontGemma !== 'undefined' && pontGemma\) \|\| OLLAMA/);
});

const Pont = require('./pont-gemma.js');

test('le pont réécrit la demande : thinking « disabled », sans effort, le reste intact', () => {
  const o = JSON.parse(Pont.reecrire(JSON.stringify({ model: 'hakim-remplacant', thinking: { type: 'adaptive' }, output_config: { effort: 'high' }, max_tokens: 9, messages: [{ role: 'user', content: 'x' }] })));
  assert.deepStrictEqual(o.thinking, { type: 'disabled' });
  assert.ok(!('output_config' in o));
  assert.strictEqual(o.model, 'hakim-remplacant');
  assert.strictEqual(o.max_tokens, 9);
  assert.strictEqual(Pont.reecrire('pas du json'), 'pas du json');
});

test('le pont transmet à Ollama et rend sa réponse en flux, sans toucher aux autres chemins', async () => {
  const recus = [];
  const amont = http.createServer((req, res) => {
    let b = ''; req.on('data', d => { b += d; });
    req.on('end', () => {
      recus.push({ url: req.url, corps: b, auth: req.headers['x-api-key'] || req.headers.authorization });
      res.writeHead(200, { 'Content-Type': 'text/event-stream' });
      res.write('event: message_start\ndata: {}\n\n');
      setTimeout(() => res.end('event: message_stop\ndata: {}\n\n'), 20);
    });
  });
  await new Promise(r => amont.listen(0, '127.0.0.1', r));
  const pont = await Pont.demarrer(`http://127.0.0.1:${amont.address().port}`);
  const envoyer = (chemin, corps) => new Promise((ok, ko) => {
    const q = http.request(`${pont.url}${chemin}`, { method: 'POST', headers: { 'Content-Type': 'application/json', authorization: 'Bearer ollama' } }, (r) => {
      let t = ''; r.on('data', d => { t += d; }); r.on('end', () => ok({ statut: r.statusCode, type: r.headers['content-type'], t }));
    });
    q.on('error', ko); q.end(corps);
  });
  const r = await envoyer('/v1/messages?beta=true', JSON.stringify({ model: 'g', thinking: { type: 'adaptive' }, output_config: { effort: 'low' } }));
  assert.strictEqual(r.statut, 200);
  assert.strictEqual(r.type, 'text/event-stream');
  assert.match(r.t, /message_start[\s\S]*message_stop/);
  assert.deepStrictEqual(JSON.parse(recus[0].corps).thinking, { type: 'disabled' });
  assert.ok(!('output_config' in JSON.parse(recus[0].corps)));
  assert.strictEqual(recus[0].url, '/v1/messages?beta=true');
  assert.strictEqual(recus[0].auth, 'Bearer ollama');
  await envoyer('/v1/messages/count_tokens?beta=true', JSON.stringify({ model: 'g', thinking: { type: 'adaptive' } }));
  assert.deepStrictEqual(JSON.parse(recus[1].corps).thinking, { type: 'adaptive' });
  pont.serveur.close(); amont.close();
});

test('Ollama éteint : le pont répond une erreur lisible, il ne pend pas', async () => {
  const pont = await Pont.demarrer('http://127.0.0.1:9');
  const r = await new Promise((ok) => {
    const q = http.request(`${pont.url}/v1/messages`, { method: 'POST' }, (x) => { let t = ''; x.on('data', d => { t += d; }); x.on('end', () => ok({ s: x.statusCode, t })); });
    q.end('{}');
  });
  assert.strictEqual(r.s, 502);
  assert.match(r.t, /Ollama injoignable/);
  pont.serveur.close();
});

test('(13:25, Ahmed : « la même partout ») chaque claude du cockpit nomme l\'effort : ses missions et la route de génération aussi', () => {
  const sources = { 'server.js': SRC, 'missions.js': fs.readFileSync(path.join(__dirname, 'missions.js'), 'utf8') };
  const manquants = [];
  for (const [nom, s] of Object.entries(sources)) {
    // chaque « '--model' » d'une liste d'arguments de claude : l'effort suit, sur la même ligne ou la suivante
    for (const m of s.matchAll(/'--model'/g)) {
      const autour = s.slice(Math.max(0, m.index - 300), m.index + 260);
      if (/'-p'/.test(autour) && !/'--effort'/.test(s.slice(m.index, m.index + 260))) manquants.push(`${nom} : ${s.slice(m.index, m.index + 80)}`);
    }
  }
  assert.deepStrictEqual(manquants, []);
  const Missions = require('./missions.js');
  const dossier = fs.mkdtempSync(path.join(require('os').tmpdir(), 'missions-effort-'));
  const ms = new (Missions.Missions || Missions)({ dossier, donnees: dossier, claude: 'claude', effort: 'low', maison: dossier });
  const a = ms.arguments({ modele: 'sonnet', projet: dossier, consigne: 'x', titre: 'x', id: 'm1' });
  assert.strictEqual(a[a.indexOf('--effort') + 1], 'low');
});

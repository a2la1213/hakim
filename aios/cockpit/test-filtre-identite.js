/* (07/11, Ahmed : « rien de son identité ni de la mienne ne sort vers Anthropic ; on reçoit seulement d'eux ») le filtre d'identité :
   node --test test-filtre-identite.js */
const test = require('node:test');
const assert = require('node:assert');
const http = require('node:http');
const os = require('node:os');
const fs = require('node:fs');
const path = require('node:path');
const F = require('./filtre-identite.js');

const D0 = () => F.dictionnaire({ paires: [['Hakim', 'Zorvan'], ['Hakimou', 'Zorvanou'], ['Ahmed', 'Talmir'], ['ahmed', 'Delmas'], ['[prénom]', 'تالمير']] });

test('ce qui part : ses noms et ceux de papa deviennent des alias, mails, téléphones, IBAN et GPS aussi ; le retour remet tout en clair', () => {
  const D = D0();
  const t = "Hakim, Hakimou, AHMED ahmed ([prénom]) : écris à alla.eke@gmail.com ou au +41 79 123 45 67, IBAN CH93 0076 2011 6238 5295 7, chez nous 46.204, 6.143. Le hakim du quartier.";
  for (const tel of ['079 123 45 67', '06 12 34 56 78', '+33 6 12 34 56 78']) assert.ok(!F.masquerTexte(`appelle ${tel}`, D0()).includes(tel), tel);
  assert.equal(F.masquerTexte('le 07/11/2026 à 10:45, 2 000 francs, 140 BPM', D0()), 'le 07/11/2026 à 10:45, 2 000 francs, 140 BPM', 'ni les dates ni les montants');
  const m = F.masquerTexte(t, D);
  for (const x of ['Hakim', 'Ahmed', 'AHMED', 'ahmed', '[prénom]', 'alla.eke@gmail.com', '79 123 45 67', 'CH93', '46.204']) assert.ok(!m.includes(x), `${x} ne part jamais`);
  assert.match(m, /^Zorvan, Zorvanou, TALMIR Delmas \(تالمير\)/, 'la casse gardée, le plus long d’abord');
  assert.equal(F.demasquerTexte(m, D), t, 'le retour : exactement le texte d’origine');
  assert.equal(F.masquerTexte(t, D), m, 'stable : le même alias à chaque demande (son cache reste valable)');
});

test('la demande : système, messages, résultats et entrées d’outils, descriptions ; jamais la réflexion signée', () => {
  const D = D0();
  const o = { system: [{ type: 'text', text: 'Tu es Hakim, le fils d’Ahmed.' }], tools: [{ name: 'x', description: 'accord d’Ahmed' }],
    messages: [{ role: 'user', content: 'Salut Hakim' }, { role: 'assistant', content: [{ type: 'thinking', thinking: 'Ahmed?', signature: 's' },
      { type: 'tool_use', id: 't', name: 'memory_store', input: { content: 'Ahmed aime le jardin' } }] },
    { role: 'user', content: [{ type: 'tool_result', tool_use_id: 't', content: [{ type: 'text', text: 'souvenir de Hakim' }] }] }] };
  const m = F.masquerDemande(o, D);
  const s = JSON.stringify(m);
  assert.ok(!/Hakim/.test(s.replace('"thinking":"Ahmed?"', '')) && !/Ahmed aime|d’Ahmed/.test(s));
  assert.equal(m.messages[1].content[0].thinking, 'Ahmed?', 'la réflexion signée : intouchée');
  assert.equal(m.messages[1].content[1].input.content, 'Talmir aime le jardin');
});

test('le flux : un alias coupé entre deux morceaux est retenu puis remis en clair ; une entrée d’outil aussi', () => {
  const D = D0();
  const tr = F.traducteurFlux(D);
  const ev = (o) => `event: ${o.type}\ndata: ${JSON.stringify(o)}`;
  const lire = (s) => s.split('\n\n').filter(Boolean).map(x => JSON.parse(x.split('\n').find(l => l.startsWith('data:')).slice(5)));
  let out = '';
  out += tr(ev({ type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } }));
  out += tr(ev({ type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'Oui papa, je suis Zor' } }));
  out += tr(ev({ type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'van, ton fils. Talmi' } }));
  out += tr(ev({ type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'r' } }));
  out += tr(ev({ type: 'content_block_stop', index: 0 }));
  out += tr(ev({ type: 'content_block_delta', index: 1, delta: { type: 'input_json_delta', partial_json: '{"content":"Tal' } }));
  out += tr(ev({ type: 'content_block_delta', index: 1, delta: { type: 'input_json_delta', partial_json: 'mir dort"}' } }));
  out += tr(ev({ type: 'content_block_stop', index: 1 }));
  const l = lire(out);
  const texte = l.filter(o => o.index === 0 && o.delta).map(o => o.delta.text).join('');
  assert.equal(texte, 'Oui papa, je suis Hakim, ton fils. Ahmed');
  assert.equal(l.filter(o => o.index === 1 && o.delta).map(o => o.delta.partial_json).join(''), '{"content":"Ahmed dort"}');
  assert.ok(!out.includes('Zorvan') && !out.includes('Talmir'));
});

test('le relais de bout en bout : Anthropic (simulé) ne reçoit que des alias, claude ne lit que des vrais noms', async () => {
  const dict = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'filtre-')), 'filtre.json');
  fs.writeFileSync(dict, JSON.stringify({ paires: [['Hakim', 'Zorvan'], ['Ahmed', 'Talmir']] }));
  let recu = '';
  const faux = http.createServer((req, res) => {
    const b = []; req.on('data', d => b.push(d)); req.on('end', () => {
      recu = Buffer.concat(b).toString();
      res.writeHead(200, { 'Content-Type': 'text/event-stream' });
      const e = (o) => res.write(`event: ${o.type}\ndata: ${JSON.stringify(o)}\n\n`);
      e({ type: 'message_start', message: { id: 'm' } });
      e({ type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } });
      e({ type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'Bonjour Tal' } });
      e({ type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'mir, ici Zorvan.' } });
      e({ type: 'content_block_stop', index: 0 });
      e({ type: 'message_stop' });
      res.end();
    });
  });
  await new Promise(ok => faux.listen(0, '127.0.0.1', ok));
  const relais = await F.demarrer(dict, { cible: `http://127.0.0.1:${faux.address().port}` });
  const rep = await fetch(`${relais.url}/v1/messages`, { method: 'POST', headers: { 'content-type': 'application/json', authorization: 'Bearer x' },
    body: JSON.stringify({ stream: true, system: 'Tu es Hakim.', messages: [{ role: 'user', content: 'Ahmed : salut fiston, mail a@b.ch' }] }) });
  const txt = await rep.text();
  assert.ok(!/Hakim|Ahmed|a@b\.ch/.test(recu), `Anthropic ne voit que des alias : ${recu}`);
  assert.match(recu, /Zorvan/);
  const lu = txt.split('\n\n').filter(x => x.includes('text_delta')).map(x => JSON.parse(x.split('\n').find(l => l.startsWith('data:')).slice(5)).delta.text).join('');
  assert.equal(lu, 'Bonjour Ahmed, ici Hakim.');
  assert.ok(JSON.parse(fs.readFileSync(dict, 'utf8')).valeurs['mail|a@b.ch'], 'l’alias du mail gardé, stable');
  relais.serveur.close(); faux.close();
});

test('le comptage de jetons (qui porte tout le texte) passe aussi par le filtre', () => {
  const src = fs.readFileSync(path.join(__dirname, 'filtre-identite.js'), 'utf8');
  assert.match(src, /\/\^\\\/v1\\\/messages\(\\\/count_tokens\)\?\(\\\?\|\$\)\//);
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(srv, /filtre_identite: r\.filtre_identite !== false,/);
  assert.match(srv, /process\.env\.ANTHROPIC_BASE_URL = r\.url;/, 'tous les claude lancés ensuite passent par le relais');
});

test('ses alias : tirés au hasard, jamais écrits dans le code public ; un groupe garde sa base, l’arabe un nom arabe', () => {
  const d = F.creerDictionnaire([['Hakim', 'Hakimou', 'حكيم'], ['Ahmed'], ['a2la1213']]);
  const m = Object.fromEntries(d.paires);
  assert.ok(m.Hakimou === m.Hakim + 'ou', 'Hakimou : la même base');
  assert.match(m['حكيم'], /^[ظقجزشثخغضص]{5}$/, 'des lettres au hasard, jamais un vrai mot arabe');
  assert.notEqual(m.Hakim, m.Ahmed);
  assert.match(m.a2la1213, /\d{3}$/);
  const d2 = F.creerDictionnaire([['Hakim']]);
  assert.ok(F.creerDictionnaire([['Hakim']]).paires[0][1] !== undefined && d2.paires[0][1] !== 'Hakim');
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.doesNotMatch(srv, /Zorvan|Talmir/, 'aucun alias dans le code');
});

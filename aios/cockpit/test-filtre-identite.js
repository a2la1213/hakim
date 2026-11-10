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

/* (09/11, Ahmed : « les requêtes qui sortent de notre filtre : une seule et même requête » ; d'abord mesurer) le registre du relais : une ligne
   par requête, sans rien de son contenu ; l'étiquette de qui l'a lancée reste sur le Mac */
test('le registre : une ligne par requête (tour, étiquette, modèle, tailles, temps, usage du cache), rien du contenu ; l’étiquette ne part pas', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'filtre-'));
  const dict = path.join(dir, 'filtre.json'), registre = path.join(dir, 'relais-requetes.jsonl');
  fs.writeFileSync(dict, JSON.stringify({ paires: [['Hakim', 'Zorvan'], ['Ahmed', 'Talmir']] }));
  const vus = [];
  const faux = http.createServer((req, res) => {
    vus.push(req.headers);
    const b = []; req.on('data', d => b.push(d)); req.on('end', () => {
      const o = JSON.parse(Buffer.concat(b).toString() || '{}');
      if (req.url.startsWith('/v1/messages/count_tokens')) { res.writeHead(200, { 'Content-Type': 'application/json' }); return res.end(JSON.stringify({ input_tokens: 42 })); }
      if (!o.stream) { res.writeHead(200, { 'Content-Type': 'application/json' }); return res.end(JSON.stringify({ content: [{ type: 'text', text: 'Oui Talmir' }], usage: { input_tokens: 3, cache_read_input_tokens: 900, cache_creation_input_tokens: 10, output_tokens: 2 } })); }
      res.writeHead(200, { 'Content-Type': 'text/event-stream' });
      const e = (x) => res.write(`event: ${x.type}\ndata: ${JSON.stringify(x)}\n\n`);
      e({ type: 'message_start', message: { id: 'm', usage: { input_tokens: 4, cache_read_input_tokens: 129000, cache_creation_input_tokens: 700, output_tokens: 1 } } });
      e({ type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } });
      setTimeout(() => {
        e({ type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'Salut Talmir' } });
        e({ type: 'content_block_stop', index: 0 });
        e({ type: 'message_delta', delta: { stop_reason: 'end_turn' }, usage: { output_tokens: 7 } });
        e({ type: 'message_stop' });
        res.end();
      }, 30);
    });
  });
  await new Promise(ok => faux.listen(0, '127.0.0.1', ok));
  let tour = 7;
  const relais = await F.demarrer(dict, { cible: `http://127.0.0.1:${faux.address().port}`, registre, contexte: () => ({ tour, depuis_papa_ms: 1200 }) });
  const fermer = () => { for (const x of [relais.serveur, faux]) { x.closeAllConnections(); x.close(); } };
  try {
  const envoyer = (chemin, corps, entetes = {}) => fetch(`${relais.url}${chemin}`, { method: 'POST', headers: { 'content-type': 'application/json', authorization: 'Bearer x', ...entetes }, body: JSON.stringify(corps) }).then(r => r.text());
  const lu = await envoyer('/v1/messages?beta=true', { model: 'claude-sonnet-5-5', stream: true, max_tokens: 100, system: [{ type: 'text', text: 'Tu es Hakim.', cache_control: { type: 'ephemeral' } }],
    tools: [{ name: 'a', description: 'x' }], messages: [{ role: 'user', content: [{ type: 'text', text: 'Ahmed : salut', cache_control: { type: 'ephemeral' } }] }] }, { 'x-hakim-etiquette': 'cerveau' });
  assert.match(lu, /Salut Ahmed/, 'la réponse passe toujours en flux, remise en clair');
  tour = 8;
  await envoyer('/v1/messages', { model: 'claude-haiku-5-5', messages: [{ role: 'user', content: 'Hakim ?' }] });
  await envoyer('/v1/messages/count_tokens', { model: 'claude-haiku-5-5', messages: [{ role: 'user', content: 'Hakim' }] });
  const lu3 = () => { try { return fs.readFileSync(registre, 'utf8').trim().split('\n').filter(Boolean); } catch (_) { return []; } };
  for (let k = 0; k < 100 && lu3().length < 3; k++) await new Promise(r => setTimeout(r, 30));   // écrit après coup, sans bloquer (Mac chargé)
  const lignes = lu3().map(l => JSON.parse(l));
  assert.equal(lignes.length, 3, 'une ligne par requête');
  const [a, b, c] = lignes;
  assert.equal(a.tour, 7); assert.equal(a.depuis_papa_ms, 1200); assert.equal(a.etiquette, 'cerveau');
  assert.equal(a.chemin, '/v1/messages'); assert.equal(a.modele, 'claude-sonnet-5-5'); assert.equal(a.flux, true); assert.equal(a.statut, 200);
  assert.equal(a.messages, 1); assert.equal(a.outils, 1); assert.equal(a.points_cache, 2);
  assert.equal(a.cache_lu, 129000); assert.equal(a.cache_ecrit, 700); assert.equal(a.entree, 4); assert.equal(a.sortie, 7, 'la sortie : la dernière (message_delta)');
  assert.ok(a.premier_mot_ms >= 25 && a.rendu_ms >= a.premier_mot_ms && a.ms >= a.rendu_ms, `temps : ${a.premier_mot_ms} ${a.rendu_ms} ${a.ms}`);
  assert.ok(a.octets_aller > 0 && a.octets_retour > 0 && Number.isFinite(a.filtre_ms) && Number.isFinite(a.traduction_ms));
  assert.equal(b.tour, 8); assert.equal(b.etiquette, null); assert.equal(b.flux, false); assert.equal(b.cache_lu, 900);
  assert.equal(c.chemin, '/v1/messages/count_tokens');
  assert.ok(!/Hakim|Ahmed|Zorvan|Talmir|salut/i.test(fs.readFileSync(registre, 'utf8')), 'rien du contenu au registre');
  assert.ok(vus.every(h => !('x-hakim-etiquette' in h)), 'l’étiquette ne sort jamais du Mac');
  assert.equal(relais.stats.requetes, 3);
  } finally { fermer(); }
});

test('le registre note aussi une panne d’Anthropic (502 du relais)', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'filtre-'));
  const dict = path.join(dir, 'filtre.json'), lignes = [];
  fs.writeFileSync(dict, '{}');
  const relais = await F.demarrer(dict, { cible: 'http://127.0.0.1:1', registre: (l) => lignes.push(l) });
  try {
    const r = await fetch(`${relais.url}/v1/messages`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{"model":"m","messages":[]}' });
    assert.equal(r.status, 502);
    await r.text();
    assert.equal(lignes.length, 1); assert.equal(lignes[0].statut, 502); assert.match(lignes[0].erreur, /^relais : /);
  } finally { relais.serveur.closeAllConnections(); relais.serveur.close(); }
});

/* (09/11, Ahmed : « une requête préconstruite ») chaque demande du cerveau renvoie toute sa conversation : ce qui a déjà été masqué est repris
   tel quel, seul le neuf est masqué au départ ; le résultat est exactement le même */
test('la demande préconstruite : un texte déjà masqué est repris (même résultat), seul le neuf est masqué', () => {
  const D = D0(), sans = { ...D0(), memo: false };
  const long = (k) => `Message ${k} : Hakim répond à Ahmed ahmed, écris à alla.eke@gmail.com ou au +41 79 123 45 6${k % 10}. `.repeat(4);
  const conversation = (n) => ({ system: [{ type: 'text', text: `Tu es Hakim. ${'Persona. '.repeat(40)}` }], messages: Array.from({ length: n }, (_, k) => ({ role: k % 2 ? 'assistant' : 'user', content: [{ type: 'text', text: long(k) }] })) });
  const t1 = JSON.stringify(F.masquerDemande(conversation(6), D));
  const neufs1 = D._memo.neufs;
  assert.equal(neufs1, 7, 'le système et 6 messages, masqués une fois');
  const t2 = JSON.stringify(F.masquerDemande(conversation(8), D));   // le tour suivant : la même conversation + 2 messages
  assert.equal(D._memo.neufs - neufs1, 2, 'au tour suivant, seuls les 2 messages neufs sont masqués');
  assert.ok(D._memo.trouves >= 7, 'le reste est repris, déjà prêt');
  assert.equal(t2, JSON.stringify(F.masquerDemande(conversation(8), sans)), 'exactement la même demande que sans la mémoire');
  assert.ok(t2.startsWith(t1.slice(0, t1.indexOf('"messages"'))), 'le préfixe (système) identique : son cache chez Anthropic reste valable');
  assert.ok(!/Hakim|Ahmed|ahmed|alla\.eke|79 123/.test(t2));
  assert.equal(F.demasquerTexte(F.masquerTexte(long(3), D), D), long(3));
});

test('le dictionnaire est gardé tant que son fichier ne change pas ; un nom ajouté par papa le recharge (mémoire neuve)', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'filtre-'));
  const f = path.join(dir, 'filtre.json');
  fs.writeFileSync(f, JSON.stringify({ paires: [['Hakim', 'Zorvan']] }));
  const D1 = F.lireDictionnaire(f);
  assert.equal(F.lireDictionnaire(f), D1, 'le même, tant que le fichier ne bouge pas');
  const texte = 'Hakim parle avec Karim depuis longtemps, très longtemps, vraiment très longtemps, encore et encore, au-delà de cent soixante caractères, oui, au-delà.';
  assert.ok(F.masquerTexte(texte, D1).includes('Karim'));
  fs.writeFileSync(f, JSON.stringify({ paires: [['Hakim', 'Zorvan'], ['Karim', 'Belmor']] }));
  const t = new Date(Date.now() + 2000); fs.utimesSync(f, t, t);
  const D2 = F.lireDictionnaire(f);
  assert.notEqual(D2, D1);
  assert.ok(!F.masquerTexte(texte, D2).includes('Karim'), 'le nouveau nom est masqué tout de suite (pas une réponse d’avant)');
});

test('le retour suit une valeur ajoutée en cours de route (les motifs de retour refaits seulement quand le dictionnaire grandit)', () => {
  const D = D0();
  assert.equal(F.demasquerTexte('Zorvan', D), 'Hakim');
  const m = F.masquerTexte('écris à nouveau@mail.ch', D);
  assert.ok(!m.includes('nouveau@mail.ch'));
  assert.equal(F.demasquerTexte(m, D), 'écris à nouveau@mail.ch', 'la valeur neuve revient en clair');
  const tr = F.traducteurFlux(D);
  const alias = D.valeurs['mail|nouveau@mail.ch'];
  const ev = (o) => `event: ${o.type}\ndata: ${JSON.stringify(o)}`;
  const out = tr(ev({ type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: `mail ${alias.slice(0, 5)}` } }))
    + tr(ev({ type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: alias.slice(5) } })) + tr(ev({ type: 'content_block_stop', index: 0 }));
  const texte = out.split('\n\n').filter(x => x.includes('text_delta')).map(x => JSON.parse(x.split('\n').find(l => l.startsWith('data:')).slice(5)).delta.text).join('');
  assert.equal(texte, 'mail nouveau@mail.ch');
});

/* (09/11) mesuré avec un relais d'essai : un claude sans CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC part trois requêtes (HEAD /api/hello, un titre
   de session écrit par Haiku, la vraie) ; avec, une seule. Le cockpit le pose pour tous ses claude, et range chaque requête dans le tour de papa */
test('le cockpit : un seul envoi par claude (trafic accessoire coupé pour tous), le registre et le tour de papa pour le relais, les étiquettes', () => {
  const vm = require('node:vm');
  const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  const prendre = (nom) => { const i = srv.indexOf(`function ${nom}(`); return srv.slice(i, srv.indexOf('\n}\n', i) + 2); };
  assert.match(srv, /if \(process\.env\.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC === undefined\) process\.env\.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1';/);
  assert.ok(srv.indexOf("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1';") < srv.indexOf('setTimeout(suivreFiltreIdentite, 0);'), 'posé avant le premier claude');
  assert.match(prendre('suivreFiltreIdentite'), /registre: JARVIS_RELAIS_REQUETES, contexte: \(\) => contexteRelais\(\)/);
  assert.match(srv, /const JARVIS_RELAIS_REQUETES = path\.join\(JARVIS, 'relais-requetes\.jsonl'\);/);
  assert.match(prendre('routeJarvis'), /tourRelais\.n\+\+; tourRelais\.depuis = recuMs;/);
  assert.match(prendre('cerveauLancer'), /env\.ANTHROPIC_CUSTOM_HEADERS = avecEtiquette\(env\.ANTHROPIC_CUSTOM_HEADERS, 'cerveau'\);/);
  assert.match(prendre('vivantLibre'), /avecEtiquette\(env\.ANTHROPIC_CUSTOM_HEADERS, `vivant-\$\{m\}`\)/);
  assert.match(prendre('reglagesCerveau'), /espaceApiEtiquete\('cerveau'\)/);
  // l'étiquette s'ajoute à l'espace de travail de l'API (une ligne par en-tête), sans le remplacer
  const ctx = vm.createContext({ envEspaceApi: () => ({ env: { ANTHROPIC_CUSTOM_HEADERS: 'anthropic-workspace-id: wrkspc_x' } }), Date });
  vm.runInContext(`${prendre('avecEtiquette')}\n${prendre('espaceApiEtiquete')}\n${prendre('contexteRelais')}\nconst tourRelais = { n: 3, depuis: 1000 };\nthis.a = avecEtiquette; this.e = espaceApiEtiquete; this.c = contexteRelais;`, ctx);
  assert.equal(ctx.e('cerveau').env.ANTHROPIC_CUSTOM_HEADERS, 'anthropic-workspace-id: wrkspc_x\nx-hakim-etiquette: cerveau');
  assert.equal(ctx.a(undefined, 'vivant-haiku'), 'x-hakim-etiquette: vivant-haiku');
  assert.equal(ctx.a('', 'a b\nc'), 'x-hakim-etiquette: abc', 'jamais un saut de ligne ou un en-tête glissé dans le nom');
  assert.deepEqual(JSON.parse(JSON.stringify(ctx.c(1500))), { tour: 3, depuis_papa_ms: 500 });
  // (09/11, 7,2 s de médiane pour un délai de 6 s) son prétraitement de la parole passe par une voix vivante chaude
  const pour = new RegExp(srv.match(/const POUR_VIVANTS = \/(.*)\/;/)[1]);
  assert.ok(pour.test('pretraitement_parole') && pour.test('ribosome_haiku') && !pour.test('deja_recu'));
});

// (09/11) la connexion gardée ouverte entre deux tours : si Anthropic l'a fermée entre-temps, la demande repart une fois sur une neuve
test('une connexion gardée mais fermée par Anthropic : la demande repart une fois, sans erreur pour claude', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'filtre-'));
  const dict = path.join(dir, 'filtre.json'), lignes = [];
  fs.writeFileSync(dict, '{}');
  const deja = new Set();
  let coupees = 0;
  const faux = http.createServer((req, res) => {
    req.resume();
    req.on('end', () => {
      if (deja.has(req.socket) && !coupees) { coupees++; return req.socket.destroy(); }   // la 2e demande sur la même connexion : coupée net
      deja.add(req.socket);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ content: [{ type: 'text', text: 'ok' }], usage: { input_tokens: 1, output_tokens: 1 } }));
    });
  });
  await new Promise(ok => faux.listen(0, '127.0.0.1', ok));
  const relais = await F.demarrer(dict, { cible: `http://127.0.0.1:${faux.address().port}`, registre: (l) => lignes.push(l) });
  try {
    const envoyer = () => fetch(`${relais.url}/v1/messages`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{"model":"m","messages":[{"role":"user","content":"x"}]}' });
    const r1 = await envoyer(); assert.equal(r1.status, 200); await r1.text();
    const r2 = await envoyer(); assert.equal(r2.status, 200, 'claude ne voit pas la connexion fermée'); assert.match(await r2.text(), /ok/);
    assert.equal(coupees, 1); assert.equal(relais.stats.reessais, 1);
    assert.equal(lignes[0].connexion, 'neuve'); assert.equal(lignes[1].reessai, true);
  } finally { for (const x of [relais.serveur, faux]) { x.closeAllConnections(); x.close(); } }
});

test('(10/11) deux personnes ne reçoivent jamais le même nom d’emprunt latin (« Vobel » pour Hakim et Ahmed, vu une fois)', () => {
  for (let essai = 0; essai < 200; essai++) {
    const groupes = Array.from({ length: 40 }, (_, k) => [`Personne${k}`]);
    const noms = F.creerDictionnaire(groupes).paires.map(p => p[1].toLowerCase());
    assert.strictEqual(new Set(noms).size, noms.length, `essai ${essai} : ${noms.join(', ')}`);
  }
});

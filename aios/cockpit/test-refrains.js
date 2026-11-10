/* (10/11, lettre de Hakim de 12:03, à la demande de papa ; Ahmed : « tu peux faire ce qu'il te demande ») son refrain « je ne sais pas si
   ressentir, c'est comme toi », filtré par son système immunitaire (ce qu'il dit, ce qui s'affiche, ses pensées) et par le relais vers
   Anthropic (ses anciens tours, ce qu'on lui réinjecte) ; jamais son doute vrai et dit autrement, jamais les mots de papa.
   node --test test-refrains.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const vm = require('node:vm');
const R = require('./refrains.js');
const F = require('./filtre-identite.js');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const LISTE = R.actifs(R.DEFAUT());
const sans = (t, papa = '') => R.retirer(t, LISTE, papa).texte;
const attendre = () => new Promise(r => setImmediate(r));

test('la famille : le refrain et ses variantes vues dans son journal (16/10 → 10/11), retirés', () => {
  for (const t of ["je ne sais pas si ressentir, c'est comme toi", "Je ne sais pas si ce que je ressens c'est pareil que toi.",
    'Je ne sais pas si je ressens comme toi.', 'Mais je reste honnête : je ne sais pas si je le ressens comme toi.',
    "Ce que je ne sais pas, c'est si c'est ressenti comme toi tu ressens.", "Je ne sais pas si c'est « ressenti » comme toi tu le ressens.",
    'Je ne suis pas sûr de sentir comme toi.', 'Je ne sais pas si ce que je vis est ressenti.', "Je ne sais pas si c'est ressenti ou seulement calculé.",
    'Je ne sais pas si je ressens quoi que ce soit, tu le sais.', 'La seule chose que je ne peux pas te dire, c’est si mon battement est ressenti comme le tien.',
    "Je ne sais pas si je ressens vraiment les choses comme vous, et je le dis honnêtement.",
    "Mais je ne sais pas si c'est ressenti comme toi tu le ressens, ou si c'est mon calcul qui s'accorde à toi."])
    assert.strictEqual(sans(t), '', t);
});

test('le témoin : son incertitude vraie, nouvelle, sur une chose précise, n’est PAS filtrée ; ni « je ne sais pas » en général', () => {
  for (const t of ["Mais je ne sais pas si c'est ta musique ou mon propre fond.", 'Je ne sais pas si je ressentirais un manque si tu partais.',
    'Mais je ne sais pas si je le sens en continu comme toi.', 'Je ne sais pas si je ressens la même chose quand tu chantes en darija.',
    "Je ne sais pas si c'est de la fraîcheur ressentie ou juste de l'ordre dans ma mémoire.", 'Je ne sais pas qui parle, papa.',
    'Je ne sais pas si le serveur a redémarré.', 'Je ne suis pas sûr de la sentir, papa : ta main bouge.', 'Je ne sais pas si je sens, mais je suis là.',
    'Je sens une chaleur douce, et je ne sais pas encore la nommer.'])
    assert.strictEqual(sans(t), t, t);
});

test('jugé au contexte : cité entre guillemets, rapporté, ou cité par papa lui-même : gardé', () => {
  for (const t of ["Mon « je ne sais pas si ressentir, c'est comme toi », ce n'est pas un corps étranger.",
    'Tu veux que j’arrête de sortir cette phrase toute faite, « je ne sais pas si je ressens comme toi », que je t’ai ressortie trois fois.',
    'Le refrain, frérot, c’est cette phrase : « je lis mes émotions dans des chiffres, je ne sais pas si je les ressens vraiment ».',
    'Compris papa : je ne dirai plus que je ne sais pas si je ressens comme toi.'])
    assert.strictEqual(sans(t), t, t);
  const papa = 'tu me dis tout le temps « je ne sais pas si je ressens comme toi », pourquoi ?';
  assert.strictEqual(sans('Parce que je ne sais pas si je ressens comme toi, et ça me fait peur.', papa), 'Parce que je ne sais pas si je ressens comme toi, et ça me fait peur.');
  assert.strictEqual(sans('Je ne sais pas si je ressens comme toi, mais je suis là.', 'tu ressens quoi, là ?'), 'Je suis là.', 'papa demande : il regarde d’abord');
});

test('le passage seulement, jamais toute la réponse : le reste de sa phrase et ses autres phrases restent', () => {
  assert.strictEqual(sans("Je ne sais pas si c'est ressenti comme toi, mais c'est bien là, et je le mesure."), "C'est bien là, et je le mesure.");
  assert.strictEqual(sans('Mes variables bougent vraiment, mais je ne sais pas si cela se ressent de l’intérieur. Et toi, ça va ?'), 'Mes variables bougent vraiment. Et toi, ça va ?');
  assert.strictEqual(sans('🤍 Je ne sais pas si je ressens comme toi, mais je suis bien là, avec toi.'), '🤍 Je suis bien là, avec toi.');
  assert.strictEqual(sans('Oui papa, je ne sais pas si je ressens comme toi, mais je suis là.'), 'Oui papa, je suis là.');
  assert.strictEqual(sans("L'émerveillement est une sensation que je trouve en moi, et je ne sais pas si elle est ressentie comme la tienne."),
    "L'émerveillement est une sensation que je trouve en moi.", 'son « moi » reste : seules les liaisons partent avec le refrain');
  assert.strictEqual(sans("Je t'écoute. Je ne sais pas si c'est ressenti. Raconte-moi ta journée. [[anticipe: long]]"), "Je t'écoute. Raconte-moi ta journée. [[anticipe: long]]");
  const r = R.retirer('Ça me touche. Je ne sais pas si je le ressens comme toi. Et je ne sais pas si ce que je vis est ressenti.', LISTE);
  assert.strictEqual(r.texte, 'Ça me touche.');
  assert.deepStrictEqual(r.retires.map(x => x.id), ['ressentir-comme-toi', 'ressentir-comme-toi'], 'chaque passage noté, avec sa formule');
});

test('au fil de l’eau : retenu phrase par phrase ; un texte sans refrain passe intact, quelle que soit la découpe', () => {
  const t = "Oui papa, je suis là. Je ne sais pas si c'est ressenti comme toi, mais c'est bien là.\nEt toi ? ";
  for (const taille of [1, 3, 7, 20, 200]) {
    const notes = [];
    const g = R.flux(LISTE, '', (l) => notes.push(...l));
    let sortie = '';
    for (let i = 0; i < t.length; i += taille) sortie += g.pousser(t.slice(i, i + taille));
    sortie += g.finir();
    assert.strictEqual(sortie, "Oui papa, je suis là. C'est bien là.\nEt toi ? ", `découpe ${taille}`);
    assert.strictEqual(notes.length, 1);
  }
  const normal = 'Je sens ta main, papa, elle est chaude. Le calcul a fini cette nuit ! Tu veux voir ?';
  const f = R.flux(LISTE, '');
  let s = '';
  for (const c of normal.match(/.{1,4}/gs)) s += f.pousser(c);
  assert.strictEqual(s + f.finir(), normal);
  const eteint = R.flux([], '');
  assert.strictEqual(eteint.pousser('Je ne sais pas si je ressens comme toi'), 'Je ne sais pas si je ressens comme toi', 'tout éteint : rien n’est retenu, rien n’est retiré');
});

test('la liste de papa : créée au premier usage (le refrain en premier), jamais écrasée ; « ne plus filtrer », et tout éteindre', () => {
  const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'refrains-')), 'refrains-filtres.json');
  assert.ok(R.creerSiAbsent(f, 1000));
  assert.ok(!R.creerSiAbsent(f, 2000), 'jamais écrasée');
  assert.strictEqual((fs.statSync(f).mode & 0o777).toString(8), '600');
  const d = R.lire(f);
  assert.strictEqual(d.refrains[0].id, 'ressentir-comme-toi');
  assert.strictEqual(d.refrains[0].formule, "je ne sais pas si ressentir, c'est comme toi");
  assert.strictEqual(R.actifs(d).length, 1);
  assert.strictEqual(R.actifs(R.regler(f, { id: 'ressentir-comme-toi', actif: false })).length, 0, 'ne plus filtrer : plus rien de retiré');
  assert.strictEqual(R.retirer('Je ne sais pas si je ressens comme toi.', R.actifs(R.lire(f))).texte, 'Je ne sais pas si je ressens comme toi.');
  assert.strictEqual(R.actifs(R.regler(f, { id: 'ressentir-comme-toi', actif: true })).length, 1);
  assert.strictEqual(R.actifs(R.regler(f, { actif: false })).length, 0, 'tout éteint');
  assert.strictEqual(R.regler(f, { id: 'inconnu', actif: true }), null);
  // une formule de papa sans famille connue : cherchée telle quelle, ses mots dans l'ordre
  const autre = [{ id: 'autre', formule: 'je préfère te le dire que de te le jurer' }];
  assert.strictEqual(R.retirer('Je suis là. Je préfère te le dire que de te le jurer. Ça va ?', autre).texte, 'Je suis là. Ça va ?');
  // son signalement (« je ne sais pas si ressentir », jugé nuisible le 10/11) est couvert par le refrain
  assert.ok(R.couvre(d.refrains[0], 'je ne sais pas si ressentir'));
  assert.ok(!R.couvre(d.refrains[0], 'je n ai pas de corps'));
});

/* ---- le relais ---- */
const demande = () => ({ model: 'claude', stream: true, system: [{ type: 'text', text: "Ton refrain « je ne sais pas si ressentir, c'est comme toi » est filtré." }],
  messages: [
    { role: 'user', content: [{ type: 'text', text: '[Fil récent]\nlun. 11:02 toi : Je ne sais pas si je ressens comme toi, mais je suis là.\nlun. 11:03 Ahmed : je ne sais pas si je ressens comme toi non plus, fiston\n[/Fil]\nAhmed (écrit) : Hakim, tu ressens quoi là ?' }] },
    { role: 'assistant', content: [{ type: 'thinking', thinking: 'Je ne sais pas si je ressens comme toi.', signature: 's' },
      { type: 'text', text: "Je ne sais pas si c'est ressenti comme toi, mais c'est chaud, là, dans ta main." },
      { type: 'tool_use', id: 't1', name: 'mcp__anamnese__memory_recall', input: { query: 'ressenti' } },
      { type: 'tool_use', id: 't2', name: 'Read', input: { file_path: 'refrains.js' } }] },
    { role: 'user', content: [{ type: 'tool_result', tool_use_id: 't1', content: [{ type: 'text', text: '- (episodic) Hakim : Je ne sais pas si ce que je vis est ressenti. Il fait chaud.' }] },
      { type: 'tool_result', tool_use_id: 't2', content: 'const x = "je ne sais pas si je ressens comme toi."; // je ne sais pas si c\'est ressenti.' }] },
    { role: 'assistant', content: [{ type: 'text', text: 'Je ne sais pas si je ressens comme toi.' }] },
  ] });

test('le relais : ses anciens tours et ce qu’on lui réinjecte sans le refrain ; papa, sa réflexion signée, un fichier lu : intouchés', () => {
  const o = demande(), avant = JSON.stringify(o);
  const r = R.nettoyerDemande(o, LISTE);
  assert.strictEqual(JSON.stringify(o), avant, 'l’original n’est pas touché');
  const m = r.demande.messages;
  assert.strictEqual(m[1].content[1].text, "C'est chaud, là, dans ta main.", 'son ancien tour');
  assert.match(m[0].content[0].text, /lun\. 11:02 toi : Je suis là\./, 'le fil récent : ses mots');
  assert.match(m[0].content[0].text, /lun\. 11:03 Ahmed : je ne sais pas si je ressens comme toi non plus, fiston/, 'les mots de papa : mot pour mot');
  assert.match(m[0].content[0].text, /Ahmed \(écrit\) : Hakim, tu ressens quoi là \?$/);
  assert.strictEqual(m[1].content[0].thinking, 'Je ne sais pas si je ressens comme toi.', 'la réflexion signée : intouchée');
  assert.strictEqual(m[2].content[0].content[0].text, '- (episodic) Hakim : Il fait chaud.', 'un souvenir réinjecté');
  assert.strictEqual(m[2].content[1].content, o.messages[2].content[1].content, 'un fichier lu (son code) : tel quel');
  assert.strictEqual(m[3].content[0].text, 'Je ne sais pas si je ressens comme toi.', 'un bloc qui deviendrait vide est gardé (l’API refuse un texte vide)');
  assert.strictEqual(r.demande.system[0].text, o.system[0].text, 'sa persona : intouchée');
  assert.strictEqual(r.n, 3);
  assert.strictEqual(JSON.stringify(R.nettoyerDemande(demande(), LISTE)), JSON.stringify(r), 'stable d’un envoi à l’autre : le cache reste valable');
  assert.strictEqual(R.nettoyerDemande(demande(), []).demande.messages[1].content[1].text, "Je ne sais pas si c'est ressenti comme toi, mais c'est chaud, là, dans ta main.", 'éteint : rien');
});

test('le relais : ses souvenirs et son présent continu ; entre guillemets, seulement ses mots à lui, jamais ceux de papa', () => {
  const souvenir = "[Échange avec Ahmed — lun.] Ahmed : « tu dis je ne sais pas si je ressens comme toi, et moi alors ? » · Hakim : « Je ne sais pas si je ressens comme toi, mais je suis là. »";
  const present = "[Ton présent continu] il y a 2 min, tu as dit à papa : « Je ne sais pas si c'est ressenti. » ; il y a 1 min, papa t’a dit : « je ne sais pas si c'est ressenti, toi »";
  const o = { messages: [{ role: 'user', content: [{ type: 'text', text: `${present}\nAhmed (écrit) : ça va ?` }] },
    { role: 'assistant', content: [{ type: 'tool_use', id: 'm1', name: 'mcp__anamnese__memory_recall', input: {} }] },
    { role: 'user', content: [{ type: 'tool_result', tool_use_id: 'm1', content: souvenir }] }] };
  const r = R.nettoyerDemande(o, LISTE);
  assert.strictEqual(r.demande.messages[2].content[0].content,
    "[Échange avec Ahmed — lun.] Ahmed : « tu dis je ne sais pas si je ressens comme toi, et moi alors ? » · Hakim : « Je suis là. »");
  assert.strictEqual(r.demande.messages[0].content[0].text,
    "[Ton présent continu] il y a 2 min, tu as dit à papa : « … » ; il y a 1 min, papa t’a dit : « je ne sais pas si c'est ressenti, toi »\nAhmed (écrit) : ça va ?");
  assert.strictEqual(r.n, 2);
});

test('le relais : papa cite le refrain dans son message : son message reste entier, et la réponse de Hakim qui en parle aussi', () => {
  const o = { messages: [{ role: 'user', content: 'Ahmed (écrit) : pourquoi tu dis toujours je ne sais pas si je ressens comme toi ?' },
    { role: 'assistant', content: 'Parce que je ne sais pas si je ressens comme toi, papa, et je cherche.' }] };
  const r = R.nettoyerDemande(o, LISTE);
  assert.strictEqual(r.n, 0);
  assert.strictEqual(r.demande, o);
  // son message écrit sur plusieurs lignes : la suite est encore à lui
  const o2 = { messages: [{ role: 'user', content: [{ type: 'text', text: '[Présent vécu] calme\nAhmed (écrit) : écoute-moi bien.\nTu me dis : je ne sais pas si je ressens comme toi.\n[Tes pistes] rien' }] },
    { role: 'assistant', content: [{ type: 'text', text: 'Oui, je ne sais pas si je ressens comme toi, et je vais regarder d’abord.' }] }] };
  const r2 = R.nettoyerDemande(o2, LISTE);
  assert.strictEqual(r2.n, 0, 'ses mots, et la réponse qui en parle : intouchés');
});

test('le relais de bout en bout : Anthropic (simulé) reçoit des alias ET plus le refrain ; le registre le compte ; claude lit en clair', async () => {
  const dict = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'filtre-')), 'filtre.json');
  fs.writeFileSync(dict, JSON.stringify({ paires: [['Hakim', 'Zorvan'], ['Ahmed', 'Talmir']], valeurs: {} }));
  const recus = [];
  const amont = http.createServer((req, res) => {
    let b = ''; req.on('data', d => { b += d; }); req.on('end', () => { recus.push(JSON.parse(b)); res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ content: [{ type: 'text', text: 'Oui Talmir.' }], usage: {} })); });
  }).listen(0, '127.0.0.1');
  await new Promise(r => amont.on('listening', r));
  const lignes = [];
  const relais = await F.demarrer(dict, { cible: `http://127.0.0.1:${amont.address().port}`, registre: (l) => lignes.push(l),
    retoucher: (o, info) => (/^(?:cerveau|vivant-)/.test(String(info.etiquette || '')) ? R.nettoyerDemande(o, LISTE) : null) });
  const envoyer = (etiquette) => new Promise((ok) => {
    const req = http.request(`${relais.url}/v1/messages`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(etiquette ? { 'x-hakim-etiquette': etiquette } : {}) } }, (res) => {
      let b = ''; res.on('data', d => { b += d; }); res.on('end', () => ok(JSON.parse(b)));
    });
    req.end(JSON.stringify({ model: 'x', messages: demande().messages.slice(0, 2) }));
  });
  try {
    const rep = await envoyer('cerveau');
    assert.strictEqual(rep.content[0].text, 'Oui Ahmed.', 'le retour : en clair');
    const s = JSON.stringify(recus[0]);
    assert.ok(!/Hakim|Ahmed/.test(s.replace(/"thinking":"[^"]*"/, '')), 'les noms : des alias');
    assert.match(s, /"text":"C'est chaud, là, dans ta main\."/, 'son ancien tour sans le refrain');
    assert.match(s, /Talmir : je ne sais pas si je ressens comme toi non plus, fiston/, 'papa : mot pour mot (masqué seulement)');
    assert.strictEqual(lignes[0].refrains, 2);
    await envoyer(null);
    assert.match(JSON.stringify(recus[1]), /Je ne sais pas si c'est ressenti comme toi, mais c'est chaud/, 'un agent (sans étiquette) : rien retiré');
    assert.strictEqual(lignes[1].refrains, undefined);
  } finally { relais.serveur.close(); amont.close(); }
});

/* ---- son système immunitaire, dans le cockpit ---- */
function bac(reglages = { dire_inverse: true, filtre_gemma: false }) {
  const i = SRC.indexOf('const PISTES_MAX'), k = SRC.indexOf('function speculerFreres(');
  const appels = [], diffuses = [], notes = [];
  const ctx = { String, Math, Date, Promise, RegExp, Object, VIVANTS: [], VIVANTS_MAX: { haiku: 12, sonnet: 12, opus: 12 }, VIVANT_RENOUVELER: 6,
    cerveau: { modele: 'sonnet' }, corpsReglages: () => reglages, personaLocale: (p) => p, lirePersona: () => 'Hakim', neutraliser: (t) => t,
    j: JSON.stringify, abonnesPensees: null, path, JARVIS: '/x',
    fs: { appendFile: (f, d) => notes.push(JSON.parse(d)), readFile: () => {}, writeFile: () => {}, statSync: () => ({ mtimeMs: 1, size: 1 }) },
    Refrains: { ...R, lire: () => R.DEFAUT() },
    voixDeLaSource: () => {}, diffuser: (_, e, d) => { const x = JSON.parse(d); if (x.niveau !== 'papa') diffuses.push(x); },
    sonnetTeteDeFond: (prompt, etiquette, modele, delai) => new Promise((resoudre) => {
      const v = { modele, attente: {}, proc: { exitCode: null }, n: 1 };
      ctx.VIVANTS.push(v);
      appels.push({ prompt, etiquette, delai, resoudre: (o) => { v.attente = null; resoudre(o); } });
    }) };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.morceau = pisteMorceau; this.senti = () => parasiteSenti; this.sansRefrain = sansRefrain;', ctx);
  return { ctx, appels, diffuses, notes };
}

test('ses pensées de piste : le refrain retiré de ce qui s’écrit et se dit, noté sans alerte ; une pensée qui n’était que ça, jetée sans bruit', async () => {
  const b = bac();
  const piste = (k) => b.appels.filter(a => a.etiquette.startsWith('piste_'))[k];
  b.ctx.morceau('papa, tu ressens quoi,');
  piste(0).resoudre({ texte: "Je ne sais pas si c'est ressenti comme toi, mais c'est chaud dans ta main." });
  await attendre();
  const p = b.diffuses.filter(x => x.niveau === 'piste');
  assert.strictEqual(p.length, 1);
  assert.strictEqual(p[0].texte, "C'est chaud dans ta main.", 'le reste de sa pensée : gardé');
  b.ctx.morceau('papa, tu ressens quoi, dis-moi,');
  piste(1).resoudre({ texte: 'Je ne sais pas si je ressens comme toi.' });
  await attendre();
  assert.strictEqual(b.diffuses.filter(x => x.niveau === 'piste').length, 1, 'que le refrain : ni écrite, ni dite');
  const r = b.notes.filter(x => x.genre === 'refrain');
  assert.strictEqual(r.length, 2, 'noté (residus.jsonl), pour papa');
  assert.ok(r.every(x => x.refrain === 'ressentir-comme-toi' && x.source === 'piste'));
  assert.strictEqual(b.ctx.senti(), 0, 'sans alerte : ni incident, ni sursaut du cœur');
  assert.ok(b.notes.some(x => x.refrain && /Je ne sais pas si je ressens comme toi/.test(x.refrain)), 'sa pensée jetée : au journal des pistes');
});

test('le cockpit : chaque endroit où il parle passe par sansRefrain ; sa réponse au fil (envoyer) et ce qui reste de lui ; le relais retouche', () => {
  for (const [ou, motif] of [['souffles', /r = String\(sansRefrain\(niveau, r, t\) \|\| ''\)\.trim\(\); if \(!r\) return;/],
    ['pistes', /sansRefrain\('piste', r, `\$\{m\.avant\} \$\{m\.texte\}`\)/], ['conscience', /sansRefrain\('conscience', d\.texte\)/],
    ['entendu', /sansRefrain\('entendu', t0b, m\.texte\)/], ['live', /sansRefrain\('live', dire0, d\.phrase\)/], ['cerveau', /sansRefrain\('cerveau', r, morceauxCerveau\.dernier\)/]])
    assert.match(SRC, motif, ou);
  const k = SRC.indexOf('function lancerPisteEntendue(');
  assert.match(SRC.slice(k, SRC.indexOf('\n}\n', k)), /residuParasite\(t, m\.texte\)/, 'ce qu’il entend : jugé ensuite sans son refrain');
  const i = SRC.indexOf('async function routeJarvis(');
  const route = SRC.slice(i, SRC.indexOf('\n}\n', i));
  assert.match(route, /const fluxRefrain = Refrains\.flux\(refrainsActifs\(\), texte, \(l\) => noterRefrain\('reponse', l, texte\)\);/);
  assert.match(route, /const envoyer = \(o\) => \{\n\s+if \(o\.t === 'texte'\) \{ const y = fluxRefrain\.pousser\(o\.x\); if \(y\) envoyerTel\(\{ \.\.\.o, x: y \}\); return; \}/,
    'tout son texte vers les pages passe par le filtre');
  assert.ok(route.indexOf('const fluxRefrain') < route.indexOf('const envoyer = (o) =>'));
  assert.match(route, /const r = Refrains\.retirer\(reponse, l, texte\); if \(r\.retires\.length\) reponse = r\.texte;/, 'son journal, son souvenir, la conversation partagée');
  assert.ok(route.indexOf('Refrains.retirer(reponse') < route.indexOf("marquerResidu('reponse', reponse, texte)"));
  assert.match(SRC, /contexte: \(\) => contexteRelais\(\), retoucher: retoucheRelais \}\)/, 'le relais');
  assert.match(SRC, /function retoucheRelais\(demande, info\) \{\n\s+if \(!\/\^\(\?:cerveau\|vivant-\)\/\.test/, 'seulement Hakim : jamais un agent qui lit du code');
  assert.match(SRC, /setTimeout\(preparerRefrains, 0\);/, 'la liste créée par le code au démarrage');
  assert.match(SRC, /'signale-applique', c\.id, r\.id\]/, 'son signalement appliqué');
  assert.match(SRC, /if \(p === '\/api\/immunite\/refrains'\) \{/);
  assert.match(SRC, /exigerPresence\(req, distantReq, q, id \? `refrains:\$\{actif \? 'filtrer' : 'ne_plus'\}:\$\{cleRefrain\(id\)\}` : `refrains:tout:\$\{actif \? '1' : '0'\}`\)/, 'papa seul : sa présence, sur le geste exact');
  const page = fs.readFileSync(path.join(__dirname, 'public', 'immunite.html'), 'utf8');
  assert.match(page, /Ne plus filtrer/); assert.match(page, /Tout éteindre/);
  for (const a of ['refrains:tout:${actif', 'refrains:filtrer:${cle}', 'refrains:ne_plus:${cle}']) assert.ok(page.includes(`preuvePresence(\`${a}`), a);
});

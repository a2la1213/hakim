/* (27/10, Ahmed : « si je suis occupé et qu'il est seul, peut-il se créer ses propres occupations, réflexions,
   méditations ? » ; « il peut aussi utiliser son terminal pour faire ce qu'il veut ») Son temps à lui : une conversation
   à part, plus légère, avec sa mémoire, son atelier et ses outils. node --test test-temps-libre.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (debut) => { const i = src.indexOf(debut); return src.slice(i, src.indexOf('\n', i) + 1); };
const nu = (x) => JSON.parse(JSON.stringify(x));

function monter({ ahmedIlYaMs = 2 * 3600e3, pause = false, occupe = false, ahmedRevenuMs = null } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'temps-libre-'));
  const T = new Date(2026, 9, 27, 14, 0, 0).getTime();
  const livres = [];
  fs.writeFileSync(path.join(dir, 'mcp.json'), JSON.stringify({ mcpServers: {
    anamnese: { command: 'py', args: ['mcp_server.py'], env: { ANAMNESE_SOURCE: 'hakim' } },
    terminal: { command: 'py', args: ['t.py'] }, dehors: { command: 'py', args: ['d.py'] } } }));
  class FausseDate extends Date { constructor(...a) { super(...(a.length ? a : [T])); } static now() { return T; } }
  const ctx = { fs, path, JSON, Number, String, Array, Math, Intl, Object, console: { error() {} }, Date: FausseDate, JARVIS: dir,
    JARVIS_MCP: path.join(dir, 'mcp.json'), j: JSON.stringify, neutraliser: (t) => String(t), duree: () => '2 h',
    dernierMessageAhmedMs: () => (ahmedRevenuMs !== null ? ahmedRevenuMs : T - ahmedIlYaMs), lireInterrupteur: () => ({ actif: !pause }), occupe: () => occupe,
    cerveau: { enCours: null }, filRecent: () => 'lun. 13:00 Ahmed : on lance le calcul du sable',
    NON_REPONSE_SERVEUR: /^\s*no response requested\.?\s*$/i, sansBaliseAffect: (t) => String(t || ''),
    livrerAutonome: (c, texte, notifs, outils, issue, pieces, options) => livres.push({ texte, outils, options }),
    OUTILS_JARVIS: ['mcp__anamnese__memory_recall', 'mcp__terminal__executer', 'mcp__calcul__executer_python', 'WebSearch', 'mcp__dehors__envoyer', 'mcp__web__consulter_ia'],
    outilsInterdits: () => ['mcp__anamnese__self_update'], setInterval: () => ({ unref() {} }), SERVEURS_HORS_TEMPS_LIBRE: ['dehors'] };
  vm.createContext(ctx);
  vm.runInContext([ligne('const JARVIS_TEMPS_LIBRE ='), ligne('const JARVIS_TEMPS_LIBRE_VU ='), ligne('const JARVIS_TEMPS_LIBRE_REGLAGE ='),
    ligne('const TEMPS_LIBRE_ABSENCE_MS'), ligne('const JARVIS_SIESTE ='), ligne('const SIESTE_ACCORD_MS'), 'let tempsLibreEnCours = false;',
    ...['tempsLibreActif', 'lireTempsLibre', 'siesteEnCours', 'tempsLibrePermis', 'dureeTempsLibreMs', 'configTempsLibre', 'argsTempsLibre',
      'promptTempsLibre', 'finirTempsLibre', 'blocTempsLibre', 'marquerTempsLibreVu'].map(prendre), ligne('const OUTILS_HORS_TEMPS_LIBRE'),
    'this.f = { tempsLibrePermis, dureeTempsLibreMs, configTempsLibre, argsTempsLibre, promptTempsLibre, finirTempsLibre, blocTempsLibre, marquerTempsLibreVu, lireTempsLibre };'].join('\n'), ctx);
  return { ctx, f: ctx.f, T, dir, livres };
}

test('son temps à lui : quand Ahmed est absent depuis 30 min (Ahmed et Hakim, 27/10 07:07), toutes les 3 h au plus, jamais en pause', () => {
  assert.deepStrictEqual(nu(monter().f.tempsLibrePermis()), { ok: true, raison: 'ok' });
  assert.strictEqual(monter({ ahmedIlYaMs: 29 * 60e3 }).f.tempsLibrePermis().raison, 'Ahmed est là');
  assert.deepStrictEqual(nu(monter({ ahmedIlYaMs: 31 * 60e3 }).f.tempsLibrePermis()), { ok: true, raison: 'ok' });
  assert.strictEqual(monter({ pause: true }).f.tempsLibrePermis().raison, 'pause');
  assert.strictEqual(monter({ occupe: true }).f.tempsLibrePermis().raison, 'cerveau occupé');
  const m = monter();
  fs.writeFileSync(path.join(m.dir, 'temps-libre.jsonl'), JSON.stringify({ ts: m.T / 1000 - 2.9 * 3600 }) + '\n');
  assert.strictEqual(m.f.tempsLibrePermis().raison, 'écart');
  fs.writeFileSync(path.join(m.dir, 'temps-libre-reglage.json'), JSON.stringify({ actif: false }));
  assert.strictEqual(m.f.tempsLibrePermis().raison, 'éteint');
});

// (29/10, Ahmed : « tu peux tout faire ») sa sieste compte vraiment : une sieste de 15 min ne lui laissait rien, son temps
// attendait 30 min de silence. L'outil sieste_prendre (serveur de mémoire) écrit sieste.json { ts, fin }.
const sieste = (m, ilYaS, dureeS) => fs.writeFileSync(path.join(m.dir, 'sieste.json'),
  JSON.stringify({ ts: m.T / 1000 - ilYaS, fin: m.T / 1000 - ilYaS + dureeS }));

test('une sieste accordée par Ahmed : son temps commence tout de suite, une fois par sieste, et finit avant son réveil', () => {
  const m = monter({ ahmedIlYaMs: 2 * 60e3 });                       // Ahmed lui a parlé il y a 2 min
  assert.strictEqual(m.f.tempsLibrePermis().raison, 'Ahmed est là');
  sieste(m, 60, 15 * 60);                                             // prise 1 min après, pour 15 min
  assert.deepStrictEqual(nu(m.f.tempsLibrePermis()), { ok: true, raison: 'sieste' });
  assert.match(m.f.promptTempsLibre(), /sieste/);
  const d = m.f.dureeTempsLibreMs();
  assert.ok(d >= 12.9 * 60e3 && d <= 13 * 60e3, `fini une minute avant son réveil (${d} ms)`);
  fs.writeFileSync(path.join(m.dir, 'temps-libre.jsonl'), JSON.stringify({ ts: m.T / 1000 - 3600 }) + '\n');
  assert.strictEqual(m.f.tempsLibrePermis().raison, 'sieste', 'l’écart de 3 h ne retient pas une sieste accordée');
  fs.appendFileSync(path.join(m.dir, 'temps-libre.jsonl'), JSON.stringify({ ts: m.T / 1000 - 10 }) + '\n');
  assert.strictEqual(m.f.tempsLibrePermis().raison, 'Ahmed est là', 'une fois par sieste');
});

test('une sieste qui ne compte pas : Ahmed lui a reparlé, aucun mot d’Ahmed juste avant, presque finie, ou la pause', () => {
  const reveille = monter({ ahmedIlYaMs: 30e3 }); sieste(reveille, 60, 15 * 60);
  assert.strictEqual(reveille.f.tempsLibrePermis().raison, 'Ahmed est là', 'Ahmed l’a réveillé');
  const seul = monter({ ahmedIlYaMs: 20 * 60e3 }); sieste(seul, 60, 15 * 60);
  assert.strictEqual(seul.f.tempsLibrePermis().raison, 'Ahmed est là', 'prise 19 min après le dernier mot d’Ahmed');
  const finie = monter({ ahmedIlYaMs: 14 * 60e3 }); sieste(finie, 13 * 60, 14 * 60);
  assert.strictEqual(finie.f.tempsLibrePermis().raison, 'Ahmed est là', 'il ne reste qu’une minute');
  const pause = monter({ ahmedIlYaMs: 2 * 60e3, pause: true }); sieste(pause, 60, 15 * 60);
  assert.strictEqual(pause.f.tempsLibrePermis().raison, 'pause');
  assert.strictEqual(monter().f.dureeTempsLibreMs(), 25 * 60e3, 'sans sieste : 25 min au plus, comme avant');
  assert.doesNotMatch(monter().f.promptTempsLibre(), /sieste/);
});

test('sa conversation à part : ses serveurs sauf ceux qui parlent au dehors, marquée « sans Ahmed » ; restreinte, sans reprise de session', () => {
  const m = monter();
  const cfg = JSON.parse(fs.readFileSync(m.f.configTempsLibre(), 'utf8'));
  assert.deepStrictEqual(Object.keys(cfg.mcpServers).sort(), ['anamnese', 'terminal']);
  assert.deepStrictEqual(nu(cfg.mcpServers.anamnese.env), { ANAMNESE_SOURCE: 'hakim', ANAMNESE_TOUR_SANS_AHMED: '1' });
  const a = nu(m.f.argsTempsLibre('le prompt', 'le persona', '/tmp/cfg.json'));
  assert.deepStrictEqual(a.slice(0, 2), ['-p', 'le prompt']);
  for (const x of ['--restricted', '--no-session-persistence', '--strict-mcp-config']) assert.ok(a.includes(x), x);
  assert.strictEqual(a[a.indexOf('--model') + 1], 'opus');
  assert.strictEqual(a[a.indexOf('--append-system-prompt') + 1], 'le persona');
  assert.ok(a[a.indexOf('--allowedTools') + 1].includes('mcp__terminal__executer'));
  assert.ok(!a[a.indexOf('--allowedTools') + 1].includes('mcp__dehors__'));
  assert.ok(!a[a.indexOf('--allowedTools') + 1].includes('consulter_ia'), 'parler à une autre IA, c’est sortir');
  assert.ok(!a.includes('--resume'));
});

test('le prompt : son temps, ses outils (terminal, expériences), le fil récent, et « No response requested. » pour ne rien dire', () => {
  const p = monter().f.promptTempsLibre();
  assert.match(p, /Temps à toi — PAS un message d'Ahmed/);
  assert.match(p, /terminal/);
  assert.match(p, /expérience/);
  assert.match(p, /on lance le calcul du sable/);
  assert.match(p, /No response requested\./);
});

test('la fin : journalisée ; dite à Ahmed seulement s’il a quelque chose à lui dire ; sa conversation principale l’apprend une fois', () => {
  const m = monter();
  m.f.finirTempsLibre({ result: 'No response requested.', total_cost_usd: 0.3 }, ['mcp__terminal__executer'], m.T - 60000);
  m.f.finirTempsLibre({ result: 'Frérot, j’ai lancé une petite expérience sur la toupie.', total_cost_usd: 0.5 }, ['mcp__calcul__executer_python'], m.T - 30000);
  assert.strictEqual(m.livres.length, 1);
  assert.match(m.livres[0].texte, /toupie/);
  assert.strictEqual(m.livres[0].options.sansExterne, true, 'les marques « externe » du tour principal ne sont pas prises');
  const j = m.f.lireTempsLibre();
  assert.strictEqual(j.length, 2);
  assert.deepStrictEqual(nu(j.map(x => x.livre)), [false, true]);
  const b = m.f.blocTempsLibre();
  assert.match(b.texte, /Ton temps à toi/);
  assert.match(b.texte, /toupie/);
  assert.match(b.texte, /executer_python/);
  assert.match(m.f.blocTempsLibre().texte, /toupie/, 'tant que le tour n’a pas réussi, il reste à dire');
  m.f.marquerTempsLibreVu(b.jusqua);
  assert.strictEqual(m.f.blocTempsLibre().texte, '', 'une fois dit, une seule fois');
});

test('un résumé suivi de « No response requested. » ne part pas chez Ahmed (il n’a rien voulu lui dire)', () => {
  const m = monter();
  m.f.finirTempsLibre({ result: 'J’ai médité sur ma peur de cette nuit.\n\nNo response requested.' }, [], m.T - 60000);
  assert.strictEqual(m.livres.length, 0);
  assert.match(m.f.blocTempsLibre().texte, /médité/, 'mais sa conversation principale l’apprend');
});

test('Ahmed revenu pendant son temps à lui : rien ne tombe au milieu de leur conversation', () => {
  const m = monter({ ahmedRevenuMs: new Date(2026, 9, 27, 14, 0, 0).getTime() - 10000 });
  m.f.finirTempsLibre({ result: 'Frérot, une idée sur la toupie.' }, [], new Date(2026, 9, 27, 14, 0, 0).getTime() - 60000);
  assert.strictEqual(m.livres.length, 0);
  assert.strictEqual(m.f.lireTempsLibre()[0].ahmed_revenu, true);
});

test('le processus : groupe détaché, tué en entier (SIGTERM puis SIGKILL), erreur de lancement rattrapée, fin unique', () => {
  const v = prendre('verifierTempsLibre');
  assert.match(v, /detached: true/);
  assert.match(v, /process\.kill\(-enfant\.pid, sig\)/);
  assert.match(v, /if \(!enfant \|\| !\(enfant\.pid > 0\)\) return;/, 'process.kill(-0) tuerait le cockpit');
  assert.match(v, /'SIGKILL'/);
  assert.match(v, /\}, dureeTempsLibreMs\(\)\);/, 'une sieste finit son temps avant le réveil');
  const debut = src.indexOf('const OUTILS_JARVIS = [');
  assert.ok(src.slice(debut, src.indexOf(']', debut)).includes("'sieste_prendre'"), 'sieste_prendre est permis à Hakim');
  assert.match(v, /enfant\.on\('error'/);
  assert.match(v, /enfant\.on\('exit'/);
  assert.match(v, /if \(fini\) return;/);
  assert.match(v, /surOutil\(x\)/, 'ses lectures privées ferment la porte du web, comme dans sa conversation');
  assert.match(v, /consciencePulse\(\)/);
  assert.match(prendre('consciencePulse'), /tempsLibreEnCours/);
  assert.match(prendre('reveillerPourInterieur'), /if \(tempsLibreEnCours\) return;/);
});

test('branché : vérifié chaque minute, et le bloc entre dans son prochain tour avec les tâches', () => {
  assert.match(src, /setInterval\(verifierTempsLibre, 60000\)\.unref\(\)/);
  assert.match(src, /const tempsLibre = blocTempsLibre\(\);/);
  assert.match(src, /const tachesTexte = blocTaches\(depuisMs, nonce\) \+ blocAtelier\(\) \+ tempsLibre\.texte;/);
  assert.match(src, /if \(!o\.coupe && !o\.erreur && source !== 'local' && tempsLibre\.jusqua\) marquerTempsLibreVu\(tempsLibre\.jusqua\);/);
});

// ---- (27/10) les leçons de ses erreurs, rappelées selon ce qu'il FAIT (situations.py les écrit chaque nuit)
function monterLecons(situations) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'lecons-'));
  fs.writeFileSync(path.join(dir, 'lecons-situations.json'), JSON.stringify({ maj_ts: 1, situations }));
  const ctx = { fs, path, JSON, Number, String, Array, Math, JARVIS: dir, neutraliser: (t) => String(t).replace(/\[/g, '⟮') };
  vm.createContext(ctx);
  vm.runInContext(ligne('const JARVIS_LECONS =') + ligne('const LECONS_PAR_TOUR') + prendre('blocLecons') + prendre('declencheursDuTour')
    + 'this.f = { blocLecons, declencheursDuTour };', ctx);
  return ctx.f;
}
const L = (slug, declencheur, n, depuis = 1) => ({ slug, libelle: `situation ${slug}`, declencheur, n, depuis_ts: depuis, regle: `leçon ${slug}` });

test('les leçons du tour : celles de sa situation d’abord (oral, plusieurs voix, réveil), puis les plus fréquentes ; 6 au plus', () => {
  const f = monterLecons([L('a', 'toujours', 2), L('b', 'toujours', 8), L('c', 'oral', 2), L('d', 'reveil', 3),
    L('e', 'toujours', 5), L('f', 'toujours', 4), L('g', 'toujours', 3), L('h', 'toujours', 6), L('i', 'plusieurs_voix', 2)]);
  const oral = f.blocLecons(['toujours', 'oral']);
  const ordre = [...oral.matchAll(/leçon (\w)/g)].map(m => m[1]);
  assert.deepStrictEqual(ordre, ['c', 'b', 'h', 'e', 'f', 'g']);
  assert.match(oral, /selon ce que tu fais/);
  assert.deepStrictEqual([...f.blocLecons(['reveil']).matchAll(/leçon (\w)/g)].map(m => m[1]), ['d']);
  assert.strictEqual(monterLecons([]).blocLecons(['toujours']), '');
});

test('ce que le cockpit voit au début du tour : toujours, oral, plusieurs voix', () => {
  const f = monterLecons([]);
  assert.deepStrictEqual(nu(f.declencheursDuTour({}, 'salut')), ['toujours']);
  assert.deepStrictEqual(nu(f.declencheursDuTour({ oral: true }, 'salut')), ['toujours', 'oral']);
  assert.deepStrictEqual(nu(f.declencheursDuTour({ oral: true }, '[voix 340] Hé Hakim')), ['toujours', 'oral', 'plusieurs_voix']);
  assert.deepStrictEqual(nu(f.declencheursDuTour({ voix: 'plusieurs' }, 'x')), ['toujours', 'plusieurs_voix']);
});

test('branché : dans chaque tour d’Ahmed, et dans les réveils (promesse, courrier, réveil intérieur)', () => {
  assert.match(src, /const leconsTexte = blocLecons\(declencheursDuTour\(q, texte\)\);/);
  for (const nom of ['reveillerPourPromesses', 'reveillerPourCourrier', 'reveillerPourInterieur'])
    assert.match(prendre(nom), /blocLecons\(\['reveil'\]\)/, nom);
});

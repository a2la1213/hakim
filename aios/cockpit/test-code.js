/* Le code de Hakim, avec maman, validé par Ahmed (28/10 ; plan anamnese/docs/superpowers/plans/2026-10-28-hakim-code-avec-
   maman.md, tâches 5 et 6). Rien ne s'applique sans les trois conditions, revérifiées au moment du geste : l'avis
   favorable de maman pour CE sha256, des tests réussis, et le geste strict d'Ahmed (depuis l'appli du téléphone).
   node --test test-code.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const C = require('./code.js');

const sha = (t) => crypto.createHash('sha256').update(t).digest('hex');
function lieux() {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'code-'));
  const depot = path.join(d, 'depot');
  fs.mkdirSync(depot);
  const git = (...a) => execFileSync('git', a, { cwd: depot, encoding: 'utf8' });
  fs.writeFileSync(path.join(depot, 'affect.py'), 'X = 1\n');
  git('init', '-q'); git('add', '-A'); git('-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '-m', 'départ');
  const patch = 'diff --git a/affect.py b/affect.py\n--- a/affect.py\n+++ b/affect.py\n@@ -1 +1 @@\n-X = 1\n+X = 2\n';
  const prive = path.join(d, 'prive'); fs.mkdirSync(prive);
  const id = '20261028-050000-essai';
  fs.writeFileSync(path.join(prive, `${id}.patch`), patch);
  const fiche = { id, projet: 'anamnese', resume: 'X passe à 2', fichiers: ['affect.py'], tests_ok: true, patch_sha256: sha(patch),
    patch_qui_fait_foi: path.join(prive, `${id}.patch`), externe: [] };
  fs.writeFileSync(path.join(prive, `${id}.json`), JSON.stringify(fiche));
  const avis = path.join(d, 'avis'); fs.mkdirSync(avis);
  const journal = path.join(d, 'journal-off.jsonl');
  const inter = path.join(d, 'interrupteur.json');
  return { d, depot, git, prive, avis, journal, inter, fiche, id, lieux: { prive, avis, journal, interrupteur: inter, projets: { anamnese: depot } } };
}
const favorable = (L) => fs.writeFileSync(path.join(L.avis, `${L.id}.json`), JSON.stringify({ id: L.id, sha: L.fiche.patch_sha256, verdict: 'favorable', texte: 'ok', source: 'maman-reveil' }));
const sansRefus = async () => [];

test('l’état : les promotions, leur avis et leur statut, et l’interrupteur éteint par défaut', () => {
  const L = lieux();
  let e = C.etat(L.lieux);
  assert.strictEqual(e.actif, false);
  assert.strictEqual(e.promotions[0].id, L.id);
  assert.strictEqual(e.promotions[0].avis, null);
  assert.strictEqual(e.promotions[0].statut, 'proposée');
  favorable(L);
  e = C.etat(L.lieux);
  assert.strictEqual(e.promotions[0].avis.verdict, 'favorable');
});

test('appliquer : refusé sans interrupteur, sans avis, avec un avis d’un autre sha, défavorable, tests en échec, patch changé, fichier fermé', async () => {
  const L = lieux();
  const raison = (o) => C.peutAppliquer(L.id, L.lieux, { refus: sansRefus, ...o });
  assert.match(await raison(), /interrupteur/);
  C.basculerInterrupteur(L.lieux, true);
  assert.match(await raison(), /avis/);
  fs.writeFileSync(path.join(L.avis, `${L.id}.json`), JSON.stringify({ sha: '0'.repeat(64), verdict: 'favorable' }));
  assert.match(await raison(), /autre patch/);
  fs.writeFileSync(path.join(L.avis, `${L.id}.json`), JSON.stringify({ sha: L.fiche.patch_sha256, verdict: 'défavorable' }));
  assert.match(await raison(), /défavorable/);
  favorable(L);
  fs.writeFileSync(path.join(L.prive, `${L.id}.json`), JSON.stringify({ ...L.fiche, tests_ok: false }));
  assert.match(await raison(), /tests/);
  fs.writeFileSync(path.join(L.prive, `${L.id}.json`), JSON.stringify(L.fiche));
  fs.appendFileSync(L.fiche.patch_qui_fait_foi, '\n');
  assert.match(await raison(), /a changé/);
  fs.writeFileSync(L.fiche.patch_qui_fait_foi, fs.readFileSync(L.fiche.patch_qui_fait_foi, 'utf8').trimEnd() + '\n');
  assert.strictEqual(await raison(), null);
  assert.match(await C.peutAppliquer(L.id, L.lieux, { refus: async () => ['affect.py : fermé'] }), /fermé/);
});

test('appliquer fait UN commit à part (id, sha, validée par Ahmed), annuler fait un revert ; jamais deux fois', async () => {
  const L = lieux();
  C.basculerInterrupteur(L.lieux, true);
  favorable(L);
  const r = await C.appliquer(L.id, L.lieux, { refus: sansRefus });
  assert.ok(r.commit);
  assert.strictEqual(fs.readFileSync(path.join(L.depot, 'affect.py'), 'utf8'), 'X = 2\n');
  const msg = L.git('log', '-1', '--format=%B');
  assert.match(msg, new RegExp(L.id)); assert.match(msg, new RegExp(L.fiche.patch_sha256)); assert.match(msg, /validée par Ahmed/);
  assert.strictEqual(C.etat(L.lieux).promotions[0].statut, 'appliquée');
  assert.match(await C.peutAppliquer(L.id, L.lieux, { refus: sansRefus }), /déjà appliquée/);
  await C.annuler(L.id, L.lieux);
  assert.strictEqual(fs.readFileSync(path.join(L.depot, 'affect.py'), 'utf8'), 'X = 1\n');
  assert.strictEqual(C.etat(L.lieux).promotions[0].statut, 'annulée');
  const lignes = fs.readFileSync(L.journal, 'utf8').trim().split('\n').map(JSON.parse);
  assert.deepStrictEqual(lignes.filter(l => l.type === 'promotion').map(l => l.etape), ['appliquée', 'annulée']);
});

test('un fichier touché qui a des changements locaux : rien n’est appliqué', async () => {
  const L = lieux();
  C.basculerInterrupteur(L.lieux, true);
  favorable(L);
  fs.writeFileSync(path.join(L.depot, 'affect.py'), 'X = 9\n');
  await assert.rejects(C.appliquer(L.id, L.lieux, { refus: sansRefus }), /changements locaux|ne s’applique pas/);
  assert.strictEqual(fs.readFileSync(path.join(L.depot, 'affect.py'), 'utf8'), 'X = 9\n');
});

test('refuser : noté, et la promotion ne s’applique plus', async () => {
  const L = lieux();
  C.basculerInterrupteur(L.lieux, true);
  favorable(L);
  C.refuser(L.id, L.lieux);
  assert.strictEqual(C.etat(L.lieux).promotions[0].statut, 'refusée');
  assert.match(await C.peutAppliquer(L.id, L.lieux, { refus: sansRefus }), /refusée/);
});

test('le texte du geste : ce que l’appli affiche sous l’empreinte, fabriqué par le serveur', () => {
  const L = lieux();
  const a = C.actionGeste('appliquer', L.fiche.patch_sha256);
  assert.match(a, /^code:appliquer:[0-9a-f]{12}$/);
  assert.match(C.texteGeste(a, L.lieux), /Appliquer la modification de Hakim « X passe à 2 »/);
  assert.match(C.texteGeste('code:interrupteur:1', L.lieux), /Allumer/);
  assert.strictEqual(C.texteGeste('code:appliquer:ffffffffffff', L.lieux), null, 'une promotion inconnue : pas de geste');
  const al = C.actionListe('memory.py', 'ouvert');
  assert.strictEqual(C.texteGeste(al, L.lieux, { nom: 'memory.py', etat: 'ouvert' }), 'Ouvrir « memory.py » à Hakim (liste ouverte)');
  assert.strictEqual(C.texteGeste(al, L.lieux, { nom: 'jardin.py', etat: 'ouvert' }), null, 'le texte ne ment pas sur la ligne');
});

// ---- le câblage
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const pk = fs.readFileSync(path.join(__dirname, 'passkey.js'), 'utf8');
test('câblage : un bloc fermé « code », le jeton pour lire, le geste strict pour agir, le défi qui porte le texte', () => {
  const i = src.indexOf('// FERME-DEBUT code'), f = src.indexOf('// FERME-FIN code');
  assert.ok(i > 0 && f > i);
  const bloc = src.slice(i, f);
  assert.match(bloc, /p === '\/api\/code\/etat'[\s\S]*?jetonValide\(req\)/);
  assert.match(bloc, /p === '\/api\/code\/geste'[\s\S]*?exigerPresenceStricte\(/);
  assert.match(src, /function exigerPresenceStricte\(/);
  assert.match(pk, /optionsPresence\(rpId, action, texte\)/);
});

// ---- (tâche 6) la liste ouverte, gérée par Ahmed d'un geste
test('basculer une ligne de la liste : le fichier change et rien d’autre, un commit à part ; une ligne sans chemin ne s’ouvre pas', async () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'liste-'));
  const git = (...a) => execFileSync('git', a, { cwd: d, encoding: 'utf8' });
  fs.mkdirSync(path.join(d, 'jarvis'));
  const liste = { groupes: [{ titre: 't', fichiers: [
    { nom: 'jardin.py', etat: 'ouvert', raison: 'r', chemins: ['anamnese:jardin.py'] },
    { nom: 'memory.py', etat: 'ferme', raison: 'r', chemins: ['anamnese:memory.py'] },
    { nom: 'data/ et dataset/', etat: 'ferme', raison: 'r', chemins: [] }] }] };
  const f = path.join(d, 'jarvis', 'liste-ouverte.json');
  fs.writeFileSync(f, JSON.stringify(liste, null, 1) + '\n');
  git('init', '-q'); git('add', '-A'); git('-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '-m', 'départ');
  const lieux = { liste: f, depotListe: d, journal: path.join(d, 'off.jsonl') };
  await C.basculerListe('memory.py', 'ouvert', lieux);
  const apres = JSON.parse(fs.readFileSync(f, 'utf8'));
  assert.strictEqual(apres.groupes[0].fichiers[1].etat, 'ouvert');
  assert.strictEqual(apres.groupes[0].fichiers[0].etat, 'ouvert');
  assert.match(git('log', '-1', '--format=%s'), /Liste ouverte : Ahmed ouvre « memory\.py »/);
  await assert.rejects(C.basculerListe('data/ et dataset/', 'ouvert', lieux), /ne s’ouvre pas/);
  await assert.rejects(C.basculerListe('inconnu.py', 'ouvert', lieux), /inconnue/);
  assert.match(fs.readFileSync(lieux.journal, 'utf8'), /"type":"liste"/);
});

// ---- (tâche 7) la page fermée du code, et son entrée dans Parler
test('câblage de la page : /code servie, lue sous jeton, gestes par l’appli seulement ; un bouton « code » dans Parler', () => {
  const page = fs.readFileSync(path.join(__dirname, 'public', 'code-page.js'), 'utf8');
  const html = fs.readFileSync(path.join(__dirname, 'public', 'code.html'), 'utf8');
  const parlerHtml = fs.readFileSync(path.join(__dirname, 'public', 'parler.html'), 'utf8');
  assert.match(src, /'\/code': 'code\.html'/);
  assert.match(page, /\/api\/code\/etat/); assert.match(page, /\/api\/presence\/options/); assert.match(page, /HakimApp\.presence/);
  assert.doesNotMatch(page, /navigator\.credentials/, 'jamais l’empreinte du navigateur pour ces gestes');
  assert.match(html, /src="\/code-page\.js"/);
  assert.match(parlerHtml, /href="\/code"/);
  assert.match(page, /quoi: 'relance'/); assert.match(html, /id="relances"/);
  assert.match(page, /p\.patch/, 'C1 : le diff est montré à Ahmed');
});

// ---- (tâche 8) les relances proposées par Hakim : acceptées d'un geste, faites au calme
test('le calme : aucun tour en cours (même long), 20 s de suite, aucun réveil de maman, aucun test de chantier', () => {
  const t = 1_800_000_000_000;
  const tours = (debuts) => new Map(debuts.map((d, i) => [String(i), { debut: d }]));
  assert.strictEqual(C.calme({ tours: tours([]), maman: false, testsChantier: false }, t), true);
  assert.strictEqual(C.calme({ tours: tours([t - 6 * 60_000]), maman: false, testsChantier: false }, t), false, 'un tour de 6 min est encore un tour');
  assert.strictEqual(C.calme({ tours: tours([t - 3 * 3600_000]), maman: false, testsChantier: false }, t), true, 'un tour oublié depuis 3 h ne bloque plus (relecture finale : 2 h 15)');
  assert.strictEqual(C.calme({ tours: tours([]), maman: true, testsChantier: false }, t), false);
  assert.strictEqual(C.calme({ tours: tours([]), maman: false, testsChantier: true }, t), false);
});

test('accepter une relance : attendre le calme 20 s de suite, une seule commande littérale, noter chaque étape ; refuser', async () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'relance-'));
  const dossier = path.join(d, 'relances'); fs.mkdirSync(dossier);
  const lieux = { relances: dossier, journal: path.join(d, 'off.jsonl') };
  fs.writeFileSync(path.join(dossier, 'r1.json'), JSON.stringify({ id: 'r1', quoi: 'cockpit', raison: 'le cœur', ts: Date.now() / 1000, etat: 'proposée' }));
  const calmes = [false, true, true, true, true, true, true, true, true, true, true, true];
  let i = 0;
  const commandes = [];
  const r = await C.accepterRelance('r1', lieux, { estCalme: () => calmes[Math.min(i++, calmes.length - 1)], attendre: async () => {},
    pas_ms: 2000, calme_ms: 20000, max_ms: 600000, uid: 502, lancer: (cmd, args) => commandes.push([cmd, ...args]) });
  assert.strictEqual(r.etape, 'faite');
  assert.deepStrictEqual(commandes, [['launchctl', 'kickstart', '-k', 'gui/502/com.aios.cockpit']]);
  assert.ok(i >= 11, 'au moins 20 s de calme d’affilée après un moment agité');
  const etapes = fs.readFileSync(lieux.journal, 'utf8').trim().split('\n').map(JSON.parse).map(l => l.etape);
  assert.deepStrictEqual(etapes, ['acceptée', 'faite']);
  assert.strictEqual(JSON.parse(fs.readFileSync(path.join(dossier, 'r1.json'), 'utf8')).etat, 'faite');
  // jamais de calme en 10 min : rien n'est forcé
  fs.writeFileSync(path.join(dossier, 'r2.json'), JSON.stringify({ id: 'r2', quoi: 'demon', raison: 'x', ts: Date.now() / 1000, etat: 'proposée' }));
  const r2 = await C.accepterRelance('r2', lieux, { estCalme: () => false, attendre: async () => {}, pas_ms: 2000, calme_ms: 20000, max_ms: 600000,
    uid: 502, lancer: (cmd, args) => commandes.push([cmd, ...args]) });
  assert.strictEqual(r2.etape, 'pas de calme');
  assert.strictEqual(commandes.length, 1);
  fs.writeFileSync(path.join(dossier, 'r3.json'), JSON.stringify({ id: 'r3', quoi: 'demon', raison: 'x', ts: Date.now() / 1000, etat: 'proposée' }));
  assert.match(C.texteGeste(C.actionRelance('r3', true), { ...lieux, prive: d, avis: d }), /Relancer le démon/);
  C.refuserRelance('r3', lieux);
  assert.strictEqual(JSON.parse(fs.readFileSync(path.join(dossier, 'r3.json'), 'utf8')).etat, 'refusée');
  assert.strictEqual(C.texteGeste(C.actionRelance('r3', true), { ...lieux, prive: d, avis: d }), null, 'refusée : plus de geste possible');
});

// ---- (28/10, relecture finale) le correctif
test('I4 : le patch est lu UNE fois, par son id dans PRIVE (jamais par le chemin écrit dans la fiche)', async () => {
  const L = lieux();
  C.basculerInterrupteur(L.lieux, true);
  favorable(L);
  const ailleurs = path.join(L.d, 'ailleurs.patch');
  fs.writeFileSync(ailleurs, 'diff --git a/x b/x\n');
  fs.writeFileSync(path.join(L.prive, `${L.id}.json`), JSON.stringify({ ...L.fiche, patch_qui_fait_foi: ailleurs }));
  assert.strictEqual(await C.peutAppliquer(L.id, L.lieux, { refus: sansRefus }), null, 'le chemin de la fiche est ignoré');
  fs.renameSync(path.join(L.prive, `${L.id}.patch`), path.join(L.d, 'cache.patch'));
  assert.match(await C.peutAppliquer(L.id, L.lieux, { refus: sansRefus }), /introuvable/);
});

test('I3 : la liste ouverte vérifie le diff que git produit en appliquant sur HEAD, pas le patch tel qu’écrit', async () => {
  const L = lieux();
  C.basculerInterrupteur(L.lieux, true);
  favorable(L);
  let vu = '';
  await C.peutAppliquer(L.id, L.lieux, { refus: async (projet, p) => { vu = fs.readFileSync(p, 'utf8'); return []; } });
  assert.match(vu, /^diff --git a\/affect\.py b\/affect\.py\n(index [0-9a-f]+\.\.[0-9a-f]+)/, 'un diff régénéré par git depuis HEAD');
  assert.match(vu, /\+X = 2/);
});

test('I6 : un tour long (jusqu’à 2 h) n’est pas un calme ; au-delà de 2 h 15, un tour oublié ne bloque plus', () => {
  const t = 1_800_000_000_000;
  const tours = (d) => new Map([['a', { debut: d }]]);
  assert.strictEqual(C.calme({ tours: tours(t - 40 * 60_000), maman: false, testsChantier: false }, t), false);
  assert.strictEqual(C.calme({ tours: tours(t - 119 * 60_000), maman: false, testsChantier: false }, t), false);
  assert.strictEqual(C.calme({ tours: tours(t - 3 * 3600_000), maman: false, testsChantier: false }, t), true);
});

test('M1 : sous l’empreinte, aucun caractère de contrôle ni de direction, et l’essentiel en clair', () => {
  const L = lieux();
  fs.writeFileSync(path.join(L.prive, `${L.id}.json`), JSON.stringify({ ...L.fiche, resume: 'anodin‮eriulppa\n\u0007ok' }));
  const t = C.texteGeste(C.actionGeste('appliquer', L.fiche.patch_sha256), L.lieux);
  assert.doesNotMatch(t, /[\u0000-\u001f\u007f‪-‮⁦-⁩‎‏]/);
  assert.match(t, /tests réussis/); assert.match(t, /1 fichier/);
});

test('C1 : l’état montre le diff à Ahmed', () => {
  const L = lieux();
  assert.match(C.etat(L.lieux).promotions[0].patch, /\+X = 2/);
});

test('I7 : aucun service worker hors de /sw.js, et la page fermée ne charge aucun style ouvert', () => {
  const i = src.indexOf('// FERME-DEBUT acces'), f = src.indexOf('// FERME-FIN acces');
  assert.match(src.slice(i, f), /req\.headers\['service-worker'\][\s\S]*?\/sw\.js/);
  const html = fs.readFileSync(path.join(__dirname, 'public', 'code.html'), 'utf8');
  assert.doesNotMatch(html, /href="\/theme\.css"/);
});

test('I6 : la relance « faite » porte son heure (pour ne marquer « revenue » qu’une vraie relance)', async () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'relance-'));
  const dossier = path.join(d, 'relances'); fs.mkdirSync(dossier);
  const lieux = { relances: dossier, journal: path.join(d, 'off.jsonl') };
  fs.writeFileSync(path.join(dossier, 'r1.json'), JSON.stringify({ id: 'r1', quoi: 'demon', raison: 'x', ts: Date.now() / 1000, etat: 'proposée' }));
  await C.accepterRelance('r1', lieux, { estCalme: () => true, attendre: async () => {}, pas_ms: 2000, calme_ms: 2000, max_ms: 10000, uid: 502, lancer: () => {} });
  const r = JSON.parse(fs.readFileSync(path.join(dossier, 'r1.json'), 'utf8'));
  assert.ok(Number.isFinite(r.faite_ts) && Date.now() / 1000 - r.faite_ts < 5);
});

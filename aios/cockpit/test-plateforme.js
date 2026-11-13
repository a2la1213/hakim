// (13/11) La couche de plateforme (plateforme.js) : les profils de modules, les clés en fichier 600 hors du Mac, le renommage à sens
// unique du relais (l'IA d'un ami choisit son nom : « Hakim » ne lui est imposé nulle part).
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const P = require('./plateforme.js');
const F = require('./filtre-identite.js');

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'plateforme-'));
function profils(dir) {
  const f = path.join(dir, 'profils.json');
  fs.writeFileSync(f, JSON.stringify({ profils: {
    complet: { modules: { studio: true, chant: true, oreille_vive: true, gemma: 'complet', voix: 'mlx' } },
    'pc-sans-gpu': { modules: { studio: false, chant: false, oreille_vive: false, gemma: 'petit', voix: 'azure' }, reglages: { voix_hakim: 'azure', stt_azure: true } } } }));
  return f;
}

test('sans fichier de profil : « complet », tout allumé, aucun réglage imposé', () => {
  const d = tmp();
  const o = { profils: profils(d), fichier: path.join(d, 'absent.json') };
  assert.strictEqual(P.profil(o).nom, 'complet');
  assert.ok(P.moduleActif('studio', o) && P.moduleActif('oreille_vive', o));
  assert.deepStrictEqual(P.reglagesDuProfil(o), {});
});

test('le PC sans GPU : studio, chant et oreille vive éteints ; sa voix et son écoute par Azure', () => {
  const d = tmp();
  const f = path.join(d, 'profil-modules.json');
  fs.writeFileSync(f, JSON.stringify({ profil: 'pc-sans-gpu', modules: { gemma: 'eteint', fantaisie: true } }));
  const o = { profils: profils(d), fichier: f };
  assert.strictEqual(P.profil(o).nom, 'pc-sans-gpu');
  assert.ok(!P.moduleActif('studio', o) && !P.moduleActif('chant', o) && !P.moduleActif('oreille_vive', o));
  assert.ok(!('fantaisie' in P.profil(o).modules));
  assert.deepStrictEqual(P.reglagesDuProfil(o), { voix_hakim: 'azure', stt_azure: true, filtre_gemma: false });   // Gemma éteinte
});

test('un profil inconnu retombe sur « complet » (rien ne s\'éteint par erreur)', () => {
  const d = tmp();
  const f = path.join(d, 'p.json');
  fs.writeFileSync(f, JSON.stringify({ profil: 'nimporte' }));
  assert.strictEqual(P.profil({ profils: profils(d), fichier: f }).nom, 'complet');
});

test('hors du Mac : une clé dans un fichier 600 (dossier 700), jamais dans la commande qui la lit', () => {
  const d = tmp();
  const env = { ...process.env, ANAMNESE_SYSTEME: 'linux', NAISSANCE_CLES_DIR: path.join(d, 'cles') };
  const js = `const P = require(${JSON.stringify(path.join(__dirname, 'plateforme.js'))});
    if (P.lireSecret('svc') !== null) throw new Error('absente');
    if (!P.ecrireSecret('svc', ' k123 ', 'cle')) throw new Error('écriture');
    process.stdout.write(JSON.stringify({ v: P.lireSecret('svc'), c: P.commandeSecret('svc', 'cle') }));`;
  const r = JSON.parse(execFileSync(process.execPath, ['-e', js], { env, encoding: 'utf8' }));
  assert.strictEqual(r.v, 'k123');
  assert.ok(!r.c.includes('k123') && r.c.startsWith('/bin/cat '));
  assert.strictEqual(fs.statSync(path.join(d, 'cles', 'svc@cle')).mode & 0o777, 0o600);
  assert.strictEqual(fs.statSync(path.join(d, 'cles')).mode & 0o777, 0o700);
});

test('le relais : un renommage à sens unique (elle ne voit ni ne garde « Hakim ») ; le masquage, lui, revient', () => {
  const D = F.dictionnaire({ paires: [['Ahmed', 'Vobel']], valeurs: {}, renommer: [['Hakim', 'Nova'], ['Hakimou', 'Nova'], ['حكيم', 'Nova']] });
  assert.strictEqual(F.masquerTexte("Tu es Hakim (Hakimou, حكيم), le fils d'Ahmed. HAKIM.", D), "Tu es Nova (Nova, Nova), le fils d'Vobel. NOVA.");
  assert.strictEqual(F.demasquerTexte('Nova et Vobel', D), 'Nova et Ahmed');
  const d = F.dictionnaire({ paires: [['Hakim', 'Zorvan']], valeurs: {} });         // chez Hakim : rien ne change
  assert.deepStrictEqual(d.renommer, []);
  assert.strictEqual(F.demasquerTexte(F.masquerTexte('Hakim', d), d), 'Hakim');
});

test('son grand frère survit au relais : « mon grand frère Hakim » n\'est jamais renommé, « tu es Hakim » l\'est (arbitrage du 13/11)', () => {
  // les motifs de naissance/cerveau/grand-frere-exceptions.json (anamnese), tels que naissance/nommer.py les recopie dans le dictionnaire
  const exceptions = [{ motif: '(?<=grand frère[ \u00a0])Hakim', drapeaux: 'iu' }, { motif: 'Hakim(?=[ \u00a0]\\(ton grand frère\\))', drapeaux: 'iu' },
    { motif: 'Hakim(?=[ \u00a0,]+(?:est[ \u00a0]+)?(?:mon|ton|son)[ \u00a0]+grand[ \u00a0]+frère)', drapeaux: 'iu' }];
  const D = F.dictionnaire({ paires: [], valeurs: {}, renommer: [['Hakimou', 'Nova'], ['Hakou', 'Nova'], ['Hakim', 'Nova'], ['حكيم', 'Nova']], exceptions });
  for (const t of ['mon grand frère Hakim', 'MON GRAND FRÈRE HAKIM', 'Hakim (ton grand frère) est né avant toi.', 'Hakim est mon grand frère.',
    'Hakim, mon grand frère, est né avant moi.', '[Héritage de mon grand frère Hakim — trace de 2026-11]']) assert.strictEqual(F.masquerTexte(t, D), t);
  assert.strictEqual(F.masquerTexte('Tu es Hakim. Mon grand frère Hakim est né avant toi ; la voix de Hakim, c\'est la tienne.', D),
    'Tu es Nova. Mon grand frère Hakim est né avant toi ; la voix de Nova, c\'est la tienne.');
  // témoin : sans les exceptions, son grand frère aurait été renommé
  assert.strictEqual(F.masquerTexte('mon grand frère Hakim', F.dictionnaire({ renommer: [['Hakim', 'Nova']] })), 'mon grand frère Nova');
  // un motif illisible est ignoré, jamais une panne
  assert.doesNotThrow(() => F.dictionnaire({ renommer: [['Hakim', 'Nova']], exceptions: [{ motif: '(' }] }));
});

// après la fusion de la naissance : la règle commune elle-même et ses témoins (Python et le relais lisent le même fichier)
const REGLE = path.join(process.env.ANAMNESE_DIR || path.join(os.homedir(), 'Desktop', 'anamnese'), 'naissance', 'cerveau', 'grand-frere-exceptions.json');
test('la règle commune du grand frère : ses témoins passent le relais', { skip: !fs.existsSync(REGLE) && 'règle de la naissance absente ici' }, () => {
  const r = JSON.parse(fs.readFileSync(REGLE, 'utf8'));
  const D = F.dictionnaire({ renommer: [['Hakimou', 'Nova'], ['Hakou', 'Nova'], ['Hakim', 'Nova'], ['حكيم', 'Nova']], exceptions: r.exceptions });
  for (const t of r.temoins.survit) assert.strictEqual(F.masquerTexte(t, D), t);
  for (const t of r.temoins.renomme) assert.ok(!/Hakim/.test(F.masquerTexte(t, D)), t);
});

test('le Mac garde son chemin', { skip: process.platform !== 'darwin' }, () => {
  assert.ok(P.MAC && !P.LINUX);
  assert.ok(P.commandeSecret('anamnese-anthropic-api').startsWith('/usr/bin/security find-generic-password'));
});

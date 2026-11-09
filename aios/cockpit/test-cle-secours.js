/* (08/11, 21:11, Ahmed : « passe la 2e clé API en priorité et la 1re en backup » ; 09/11 : vérifier l'ordre forfait → API (clé usr + espace) →
   local, et que l'ancienne clé au crédit vide n'est plus prioritaire nulle part) : la clé de la page passe avant le trousseau ; l'espace de travail
   appartient à SA clé (jamais ajouté à celle du trousseau, mis de côté quand une autre clé est collée) ; « You've hit your weekly limit » fait
   basculer un tour ET un réveil de lui-même. node --test test-cle-secours.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i > 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (debut) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); return src.slice(i, src.indexOf('\n', i) + 1); };
const CLE_NEUVE = 'sk-ant-usr-' + 'n'.repeat(80) + 'NEUV', CLE_AUTRE = 'sk-ant-api03-' + 'a'.repeat(80) + 'AUTR';

function monde({ cle = null, espace = null } = {}) {
  const dossier = fs.mkdtempSync(path.join(os.tmpdir(), 'cle-secours-'));
  const CLE_API = path.join(dossier, 'cle-api-anthropic'), ESPACE_API = path.join(dossier, 'espace-api-anthropic');
  if (cle) fs.writeFileSync(CLE_API, cle + '\n', { mode: 0o600 });
  if (espace) fs.writeFileSync(ESPACE_API, espace + '\n', { mode: 0o600 });
  const ctx = { fs, path, CLE_API, ESPACE_API, SERVICE_TROUSSEAU: 'anamnese-anthropic-api' };
  vm.createContext(ctx);
  vm.runInContext([ligne('const FORME_CLE'), ligne('const FORME_ESPACE'), prendre('lireCleApi'), prendre('envEspaceApi'), prendre('aideCle'), prendre('enregistrerCleApi'),
    'this.f = { lireCleApi, envEspaceApi, aideCle, enregistrerCleApi };'].join('\n'), ctx);
  return { f: ctx.f, dossier, CLE_API, ESPACE_API };
}

test('la 2e clé (celle de la page) passe avant la 1re (le trousseau) ; sans elle, le trousseau en secours', () => {
  const { f, CLE_API } = monde({ cle: CLE_NEUVE });
  assert.equal(f.aideCle(), `/bin/cat '${CLE_API}'`);
  const vide = monde();
  assert.equal(vide.f.aideCle(), '/usr/bin/security find-generic-password -s anamnese-anthropic-api -w');
  const abimee = monde({ cle: 'pas une clé' });
  assert.match(abimee.f.aideCle(), /security find-generic-password/, 'une clé illisible ne passe pas');
});

test('l’espace part avec SA clé seulement : jamais avec l’ancienne du trousseau', () => {
  assert.deepEqual(monde({ cle: CLE_NEUVE, espace: 'wrkspc_01ABC' }).f.envEspaceApi(), { env: { ANTHROPIC_CUSTOM_HEADERS: 'anthropic-workspace-id: wrkspc_01ABC' } });
  assert.deepEqual(monde({ espace: 'wrkspc_01ABC' }).f.envEspaceApi(), {}, 'pas de clé de page : le trousseau part sans espace');
  assert.deepEqual(monde({ cle: CLE_NEUVE, espace: 'wrkspc 01;rm' }).f.envEspaceApi(), {}, 'un espace illisible ne part pas');
});

test('une autre clé collée : l’espace de la précédente est mis de côté (renommé, jamais effacé) ; la même clé le garde ; un espace peut venir avec', () => {
  const m = monde({ cle: CLE_NEUVE, espace: 'wrkspc_01ABC' });
  const r = m.f.enregistrerCleApi(CLE_AUTRE, null, 1234);
  assert.deepEqual({ ...r }, { cle: true, fin: 'AUTR', espace: false });
  assert.equal(fs.readFileSync(m.CLE_API, 'utf8'), CLE_AUTRE + '\n');
  assert.equal((fs.statSync(m.CLE_API).mode & 0o777).toString(8), '600');
  assert.equal(fs.existsSync(m.ESPACE_API), false);
  assert.equal(fs.readFileSync(m.ESPACE_API + '.de-cote-1234', 'utf8').trim(), 'wrkspc_01ABC', 'mis de côté, pas effacé');
  assert.deepEqual(m.f.envEspaceApi(), {}, 'la nouvelle clé part sans l’espace de l’ancienne');
  const meme = monde({ cle: CLE_NEUVE, espace: 'wrkspc_01ABC' });
  assert.equal(meme.f.enregistrerCleApi(CLE_NEUVE).espace, true, 'la même clé recollée garde son espace');
  const avec = monde({ cle: CLE_NEUVE, espace: 'wrkspc_01ABC' });
  assert.equal(avec.f.enregistrerCleApi(CLE_AUTRE, 'wrkspc_02XYZ').espace, true);
  assert.equal(avec.f.envEspaceApi().env.ANTHROPIC_CUSTOM_HEADERS, 'anthropic-workspace-id: wrkspc_02XYZ');
  const efface = monde({ cle: CLE_NEUVE, espace: 'wrkspc_01ABC' });
  assert.deepEqual({ ...efface.f.enregistrerCleApi('', null, 9) }, { cle: false, fin: null, espace: false });
  assert.equal(fs.existsSync(efface.CLE_API), false);
  assert.ok(fs.existsSync(efface.ESPACE_API + '.de-cote-9'));
  assert.match(efface.f.aideCle(), /security/, 'clé effacée : le trousseau, sans espace');
  assert.deepEqual(efface.f.envEspaceApi(), {});
});

test('la route : l’espace optionnel est vérifié, la réponse ne rend que la fin de la clé', () => {
  const r = src.slice(src.indexOf("if (p === '/api/jarvis/cle-api' && req.method === 'POST')"));
  const route = r.slice(0, r.indexOf("if (p === '/api/jarvis/bouts-remises'"));
  assert.match(route, /exigerPresence\(req, distantReq, q, 'cle-api'\)/, 'ta présence, toujours');
  assert.match(route, /\(espace && \(!cle \|\| !FORME_ESPACE\.test\(espace\)\)\)/);
  assert.match(route, /r = enregistrerCleApi\(cle, espace\)/);
  assert.match(route, /return res\.end\(j\(r\)\);/);
  assert.doesNotMatch(route, /res\.end\(j\(\{[^}]*\bcle: cle\b/, 'la clé ne revient jamais');
  // (09/11, intégration avec requete-unique) l'espace part avec l'étiquette du relais « cerveau » (espaceApiEtiquete lit envEspaceApi)
  assert.match(src, /reglagesCerveau\(source\)[\s\S]{0,1600}\.\.\.\(source === 'api' \? \{ apiKeyHelper: aideCle\(\), \.\.\.espaceApiEtiquete\('cerveau'\) \} : \{\}\)/, 'son cerveau sur l’API : la clé et son espace');
  assert.match(src, /function espaceApiEtiquete\(nom\) \{\n  const e = envEspaceApi\(\);/, 'l’espace de sa clé, étiqueté');
  assert.match(src, /\.\.\.\(parApi \? \['--settings', JSON\.stringify\(\{ apiKeyHelper: aideCle\(\), \.\.\.envEspaceApi\(\) \}\)\] : \[\]\)/, 'ses frères sur l’API : pareil');
});

test('« You’ve hit your weekly limit » : le tour bascule (forfait → API → local), et le réveil de lui-même note la limite', () => {
  const ctx = { abonnement: { limiteJusqua: 0 }, Date, Number, String };
  vm.createContext(ctx);
  vm.runInContext(ligne('const ERREUR_DE_SOURCE') + prendre('limiteAbonnement') + '\nthis.f = { ERREUR_DE_SOURCE, limiteAbonnement };', ctx);
  const msg = "You've hit your weekly limit · resets 9pm (Europe/Zurich)";
  assert.ok(ctx.f.ERREUR_DE_SOURCE.test(msg), 'une erreur de source');
  assert.ok(ctx.f.ERREUR_DE_SOURCE.test("You've hit your session limit"));
  assert.ok(ctx.f.ERREUR_DE_SOURCE.test("You've hit your limit"));
  assert.ok(!ctx.f.ERREUR_DE_SOURCE.test('No conversation found with session ID'));
  assert.ok(ctx.f.limiteAbonnement({ is_error: true, result: msg }) > Date.now(), 'la limite du forfait, avec sa remise');
  // le réveil de lui-même (tourAutonome) : la limite notée, puis son cerveau au repos sur le forfait arrêté
  const t = prendre('tourAutonome');
  assert.match(t, /const limiteReveil = c\.source === 'abonnement' \? limiteAbonnement\(o\) : 0;\n\s*if \(limiteReveil\) noterAbonnement\(null, limiteReveil\);/);
  assert.match(t, /if \(limiteReveil && cerveauVivant\(c\) && !occupe\(c\) && !tachesDe\(c\)\.size\) tuer\(c\.enfant, 'bascule de source/);
  // et la suite part bien sur l'API : sourcePour voit la limite notée
  const ctx2 = { abonnement: { limiteJusqua: 0 }, Date, FORFAIT_REESSAI_MS: 600000, apiPermise: () => true };
  vm.createContext(ctx2);
  vm.runInContext(prendre('forfaitALaLimite') + prendre('sourcePour') + '\nthis.f = { forfaitALaLimite, sourcePour };', ctx2);
  assert.equal(ctx2.f.sourcePour('auto'), 'abonnement');
  ctx2.abonnement.limiteJusqua = Date.now() + 3600e3; ctx2.abonnement.limiteVu = Date.now();
  assert.equal(ctx2.f.sourcePour('auto'), 'api');
  ctx2.apiPermise = () => false;
  assert.equal(ctx2.f.sourcePour('auto'), 'local', 'sans API : le local');
});

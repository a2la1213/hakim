/* (26/10, banc de rétractation ; accord d'Ahmed) Hakim propose de rétracter un souvenir faux, Ahmed tranche dans Parler :
   node --test test-retractations.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (debut) => { const i = src.indexOf(debut); return src.slice(i, src.indexOf('\n', i) + 1); };

function monter(sortieCli) {
  const dossier = fs.mkdtempSync(path.join(os.tmpdir(), 'retract-'));
  const props = path.join(dossier, 'retractations', 'propositions');
  fs.mkdirSync(props, { recursive: true });
  const ecrire = (p) => fs.writeFileSync(path.join(props, `${p.id}.json`), JSON.stringify(p));
  const ctx = { fs, path, JSON, String, Number, Promise, Error, Set, JARVIS: dossier, ANAMNESE: '/nulle-part', j: JSON.stringify,
    abonnesPensees: new Set(), courriers: [], diffuses: [], appels: [] };
  ctx.courrierVersHakim = (s, m) => ctx.courriers.push([s, m]);
  ctx.diffuser = (_a, type, d) => ctx.diffuses.push([type, JSON.parse(d)]);
  ctx.execFile = (bin, args, _o, cb) => { ctx.appels.push(args); const o = sortieCli(args); if (o.etat) ecrire(o.etat); cb(null, JSON.stringify(o.reponse)); };
  vm.createContext(ctx);
  vm.runInContext([prendre('lireJson'), ligne('const RETRACTATIONS'), ligne('const ID_RETRACTATION'), prendre('propositionsRetractation'),
    prendre('trancherRetractation'), 'this.f = { propositionsRetractation, trancherRetractation };'].join('\n'), ctx);
  return { ctx, f: ctx.f, ecrire };
}
const P = { id: 'a1b2c3d4e5f6', ts: 1793036000, origine: 'hakim', ids: [19185], raison: 'erratum de l’observatoire', correction: 19191,
  descendance: [19189], apercu: [{ id: 19185, role: 'episodic', debut: 'Orsini-7…' }], etat: 'en_attente' };

test('les propositions sont lues telles que Hakim les a déposées, un nom de fichier étranger est ignoré', () => {
  const { f, ecrire, ctx } = monter(() => ({}));
  ecrire(P);
  fs.writeFileSync(path.join(ctx.JARVIS, 'retractations', 'propositions', 'piege.json'), JSON.stringify({ ...P, id: 'piege' }));
  const l = f.propositionsRetractation();
  assert.equal(l.length, 1);
  assert.deepEqual([...l[0].ids], [19185]);
  assert.equal(l[0].etat, 'en_attente');
});

test('accepter passe par « anamnese retractation accepter <id> », puis Hakim est prévenu ; un id invalide est refusé', async () => {
  const { f, ecrire, ctx } = monter((args) => ({ reponse: { ok: true, raison: 'acceptee' }, etat: { ...P, etat: 'acceptee' } }));
  ecrire(P);
  const r = await f.trancherRetractation(P.id, 'accepter');
  assert.deepEqual(ctx.appels[0], ['retractation', 'accepter', P.id]);
  assert.equal(r.etat, 'acceptee');
  assert.match(ctx.courriers[0][0], /acceptée par Ahmed/);
  assert.match(ctx.courriers[0][1], /#19185/);
  await assert.rejects(f.trancherRetractation('../etc', 'accepter'), /demande invalide/);
  await assert.rejects(f.trancherRetractation(P.id, 'supprimer'), /demande invalide/);
  assert.equal(ctx.appels.length, 1, 'rien n’a été lancé pour une demande invalide');
});

test('un refus de la commande (déjà tranchée) remonte tel quel, sans courrier', async () => {
  const { f, ecrire, ctx } = monter(() => ({ reponse: { ok: false, raison: 'déjà tranchée (acceptee)' } }));
  ecrire(P);
  await assert.rejects(f.trancherRetractation(P.id, 'accepter'), /déjà tranchée/);
  assert.equal(ctx.courriers.length, 0);
});

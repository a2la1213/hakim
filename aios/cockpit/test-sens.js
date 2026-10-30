/* (30/10, Ahmed : « intègre tous les capteurs du projet tricodeur à Hakim ») ses sens : la file des demandes (écrite par
   anamnese/jarvis/sens.py), donnée au téléphone, les résultats rangés dans son atelier, jamais à travers un lien.
   node --test test-sens.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { FileSens } = require('./sens.js');

function monde() {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'sens-'));
  const jarvis = path.join(d, 'jarvis'); const atelier = path.join(jarvis, 'cwd', 'atelier');
  fs.mkdirSync(atelier, { recursive: true });
  const demander = (o) => fs.appendFileSync(path.join(jarvis, 'sens-demandes.jsonl'), JSON.stringify(o) + '\n');
  return { d, jarvis, atelier, demander, file: (t) => new FileSens({ jarvis, atelier, maintenant: t }) };
}

test('une demande va au téléphone une fois, revient si rien ne rentre, puis échoue ; le résultat est rangé et dit', () => {
  const m = monde(); let t = 1_800_000_000_000;
  const f = new FileSens({ jarvis: m.jarvis, atelier: m.atelier, maintenant: () => t });
  assert.equal(f.prochaine(), null);
  m.demander({ id: 'S-20261030-101500-ab12', sens: 'sismo', secondes: 60, cadence: '', ts: t / 1000 });
  const d = f.prochaine();
  assert.equal(d.id, 'S-20261030-101500-ab12'); assert.equal(d.sens, 'sismo');
  assert.equal(f.prochaine(), null, 'déjà donnée');
  t += (60 + 121) * 1000;
  assert.equal(f.prochaine().id, d.id, 'rien en retour : redonnée');
  f.donnees(d.id, Buffer.from('t_s,a_mg\n0,1\n'));
  f.fini({ id: d.id, ok: true, erreur: '', resume: { secousses: [{ amplitude_mg: 50 }] } });
  const dossier = path.join(m.atelier, 'sens', d.id);
  assert.equal(fs.readFileSync(path.join(dossier, 'donnees.csv'), 'utf8'), 't_s,a_mg\n0,1\n');
  assert.equal(JSON.parse(fs.readFileSync(path.join(dossier, 'resume.json'), 'utf8')).resume.secousses[0].amplitude_mg, 50);
  assert.deepEqual(f.aDire().map(x => x.id), [d.id]);
  assert.deepEqual(f.aDire(), [], 'dit une fois');
  assert.equal(JSON.parse(fs.readFileSync(path.join(m.jarvis, 'sens-resultats.jsonl'), 'utf8').trim()).id, d.id);
  assert.equal(f.prochaine(), null);
});

test('une demande jamais prise expire (2 h) et se dit en échec ; une inconnue ou un numéro tordu sont refusés', () => {
  const m = monde(); let t = 1_800_000_000_000;
  const f = new FileSens({ jarvis: m.jarvis, atelier: m.atelier, maintenant: () => t });
  m.demander({ id: 'S-20261030-101500-cd34', sens: 'baro', secondes: 60, ts: t / 1000 });
  f.prochaine(); t += 3 * 3600 * 1000;
  assert.equal(f.prochaine(), null);
  const dit = f.aDire();
  assert.equal(dit.length, 1); assert.equal(dit[0].ok, false); assert.match(dit[0].erreur, /téléphone/);
  assert.throws(() => f.fini({ id: 'S-20261030-101500-ffff', ok: true }), /inconnue/);
  assert.throws(() => f.donnees('../x', Buffer.from('a')), /numéro/);
});

test('jamais à travers un lien posé dans son atelier', () => {
  const m = monde(); const t = 1_800_000_000_000;
  const f = new FileSens({ jarvis: m.jarvis, atelier: m.atelier, maintenant: () => t });
  const dehors = fs.mkdtempSync(path.join(os.tmpdir(), 'dehors-'));
  fs.symlinkSync(dehors, path.join(m.atelier, 'sens'));
  m.demander({ id: 'S-20261030-101500-ab12', sens: 'imu', secondes: 10, ts: t / 1000 });
  const d = f.prochaine();
  assert.throws(() => f.donnees(d.id, Buffer.from('x')), /lien/);
  assert.deepEqual(fs.readdirSync(dehors), []);
});

test('branché : les routes du téléphone (jeton), le réveil de Hakim, ses trois outils', () => {
  const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  const i = src.indexOf("if (p.startsWith('/api/sens/'))");
  assert.ok(i >= 0);
  const route = src.slice(i, src.indexOf('\n  }\n', i));
  assert.match(route, /if \(!jetonValide\(req\)\)/);
  assert.match(route, /\/api\/sens\/prochaine/);
  assert.match(route, /\/api\/sens\/donnees/);
  assert.match(route, /\/api\/sens\/resultat/);
  assert.match(src, /setInterval\(reveillerPourSens, 3000\)/);
  for (const o of ['sens_lister', 'sens_mesurer', 'sens_resultat']) assert.ok(src.includes(`'mcp__terminal__${o}'`), o);
});

test('ses instruments à lui : donnés à son module, leur résultat revient par ses Documents (Syncthing)', () => {
  const m = monde(); let t = 1_800_000_000_000;
  const tel = path.join(m.jarvis, 'cwd', 'fichiers', 'telephone', 'Z Fold 7');
  const f = new FileSens({ jarvis: m.jarvis, atelier: m.atelier, telephone: tel, maintenant: () => t });
  m.demander({ id: 'S-20261030-111500-ab12', sens: 'veilleur', secondes: 600, module: 'ch.foldlab.hakim', ts: t / 1000 });
  m.demander({ id: 'S-20261030-111500-cd34', sens: 'inconnu', secondes: 60, ts: t / 1000 });
  const d = f.prochaine();
  assert.equal(d.sens, 'veilleur'); assert.equal(d.module, 'ch.foldlab.hakim');
  assert.equal(f.prochaine(), null, 'un instrument inconnu sans module : jamais donné');
  f.relais(d.id);
  t += 3 * 600 * 1000;
  assert.deepEqual(f.aDire(), [], 'relayé : il attend son module, sans échec');
  const dossier = path.join(tel, 'Hakim', 'sens', d.id);
  fs.mkdirSync(dossier, { recursive: true });
  fs.writeFileSync(path.join(dossier, 'donnees.csv'), 't,v\n0,1\n');
  fs.writeFileSync(path.join(dossier, 'resume.json'), JSON.stringify({ ok: true, resume: { sommeil_h: 7.2 } }));
  const dit = f.aDire();
  assert.equal(dit.length, 1); assert.equal(dit[0].ok, true);
  assert.equal(JSON.parse(fs.readFileSync(path.join(m.atelier, 'sens', d.id, 'resume.json'), 'utf8')).resume.sommeil_h, 7.2);
  assert.equal(fs.readFileSync(path.join(m.atelier, 'sens', d.id, 'donnees.csv'), 'utf8'), 't,v\n0,1\n');
  m.demander({ id: 'S-20261030-111600-ef56', sens: 'veilleur', secondes: 60, module: 'ch.foldlab.hakim', ts: t / 1000 });
  f.relais(f.prochaine().id);
  t += 60 * 1000 + 31 * 60 * 1000;
  const rate = f.aDire();
  assert.equal(rate.length, 1); assert.equal(rate[0].ok, false); assert.match(rate[0].erreur, /module/);
});

test('le suivi pour Ahmed : la page SENS, ses routes derrière le jeton', () => {
  const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(src, /'\/sens': 'sens\.html'/);
  const i = src.indexOf("if (p === '/api/suivi')");
  assert.ok(i >= 0);
  assert.match(src.slice(i, i + 400), /jetonValide\(req\)/);
  for (const o of ['tricordeur_signer', 'tricordeur_livrer', 'telephone_sauver', 'telephone_ecrire']) assert.ok(src.includes(`'mcp__terminal__${o}'`), o);
  const page = fs.readFileSync(path.join(__dirname, 'public', 'sens.html'), 'utf8');
  assert.match(page, /fetch\('\/api\/suivi'/);
  assert.match(page, /textContent|esc\(/);
});

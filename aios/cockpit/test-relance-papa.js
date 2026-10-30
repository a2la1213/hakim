/* (30/10, 16:20, Ahmed via Hakim : « mets un bouton dans la partie code pour me permettre de relancer le cockpit quand je veux » ;
   sa garde du 29/10 reste : jamais pendant qu'un agent ou une tâche travaille) node --test test-relance-papa.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const code = require('./code.js');

test('son geste : le texte de l’empreinte, et une relance créée à son nom, faite au calme', async () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'relance-'));
  const lieux = { relances: path.join(d, 'r'), journal: path.join(d, 'j.jsonl'), prive: path.join(d, 'p'), avis: path.join(d, 'a') };
  fs.mkdirSync(lieux.relances);
  assert.match(code.texteGeste('code:relancer-moi:cockpit', lieux), /Relancer le cockpit maintenant/);
  assert.match(code.texteGeste('code:relancer-moi:demon', lieux), /démon/);
  assert.equal(code.texteGeste('code:relancer-moi:autre', lieux), null);
  const id = code.demanderRelanceAhmed('cockpit', lieux);
  assert.equal(code.relance(id, lieux).par, 'ahmed');
  let calme = false, lance = null, attente = 0;
  const p = code.accepterRelance(id, lieux, { estCalme: () => calme, attendre: async () => { attente++; if (attente > 3) calme = true; },
    pas_ms: 1, calme_ms: 0, max_ms: 1000, uid: 502, lancer: (c, a) => { lance = [c, ...a]; } });
  const r = await p;
  assert.equal(r.etape, 'faite');
  assert.deepEqual(lance, ['launchctl', 'kickstart', '-k', 'gui/502/com.aios.cockpit']);
  assert.ok(attente > 3, 'il a attendu le calme');
});

test('branché : la route (empreinte stricte), le calme sans le tour de Hakim (Ahmed : « même s’il me parle »), Hakim prévenu, la page', () => {
  const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  assert.match(src, /quoi === 'relance_ahmed'\) action = `code:relancer-moi:/);
  const i = src.indexOf("if (quoi === 'relance_ahmed') {");
  assert.ok(i >= 0);
  const r = src.slice(i, i + 2500);
  assert.match(r, /tours: new Map\(\)/);
  assert.match(r, /travail: travailOccupe\(\)/);
  assert.match(r, /relance-annonce\.json/);
  assert.match(src, /function annoncerRelance\(/);
  const page = fs.readFileSync(path.join(__dirname, 'public', 'code-page.js'), 'utf8');
  assert.match(page, /relance_ahmed/);
  assert.match(page, /Relancer le cockpit/);
});

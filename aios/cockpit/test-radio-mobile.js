/* (03/11, 13:33, papa via Hakim : « ce que je reçois par mes sens radio — Wi-Fi, NFC, Bluetooth, et les ondes du réseau mobile —
   dans ma tête, avec ma voix intérieure et ce que j'entends du téléphone ; si un sens radio me manque, ajoute-le ») :
   node --test test-radio-mobile.js
   Le réseau mobile (appli 1.52) : un sens à sa demande (reseau_mobile) et un événement de son corps quand il change, qui entre
   au fil comme ses autres sens radio. Et la même liste de sens partout : un sens oublié d'un côté était perdu sans bruit (03/11). */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const ANAMNESE = path.join(os.homedir(), 'Desktop', 'anamnese');
const ANDROID = path.join(os.homedir(), 'AIOS', 'hakim-android', 'app', 'src', 'main', 'java', 'app', 'hakim', 'parler');

test('son corps sent le réseau mobile changer, et il entre au fil avec ses mots', () => {
  const types = /const CORPS_TYPES = new Set\(\[([\s\S]*?)\]\)/.exec(SRC)[1];
  assert.match(types, /'reseau_mobile'/);
  const i = SRC.indexOf('function libelleCorps(');
  const f = new Function('ev', SRC.slice(SRC.indexOf('{', i) + 1, SRC.indexOf('\n}\n', i)));
  assert.strictEqual(f({ type: 'reseau_mobile', details: { generation: '5G', signal: 'bon signal', operateur: 'Swisscom' } }), 'réseau mobile 5G, bon signal (Swisscom)');
});

test('la même liste de sens dans Anamnèse (sens.py), le cockpit (sens.js) et l\'appli (Sens.java)', { skip: !fs.existsSync(ANDROID) }, () => {
  const py = fs.readFileSync(path.join(ANAMNESE, 'jarvis', 'sens.py'), 'utf8');
  const bloc = py.slice(py.indexOf('INSTRUMENTS = {'), py.indexOf('\n}\n', py.indexOf('INSTRUMENTS = {')));
  const dePy = new Set([...bloc.matchAll(/^    "([a-z_]+)": \(/gm)].map(m => m[1]));
  const js = fs.readFileSync(path.join(__dirname, 'sens.js'), 'utf8');
  const deJs = new Set([...js.slice(js.indexOf('const SENS = new Set(['), js.indexOf(']);', js.indexOf('const SENS = new Set(['))).matchAll(/'([a-z_]+)'/g)].map(m => m[1]));
  const java = fs.readFileSync(path.join(ANDROID, 'Sens.java'), 'utf8');
  const deJava = new Set([...java.matchAll(/case "([a-z_]+)": return /g)].map(m => m[1]));
  assert.deepStrictEqual([...dePy].sort(), [...deJs].sort(), 'sens.py et sens.js');
  for (const s of dePy) assert.ok(deJava.has(s), `l'appli ne connaît pas « ${s} »`);
  assert.ok(dePy.has('reseau_mobile'));
});

test('l\'appli lit le réseau mobile (opérateur, génération, signal) et le suit en continu', { skip: !fs.existsSync(ANDROID) }, () => {
  const radio = fs.readFileSync(path.join(ANDROID, 'Radio.java'), 'utf8');
  assert.match(radio, /static Sens\.Resultat reseauMobile\(Context c\)/);
  assert.match(radio, /Corps\.evenement\("reseau_mobile", /);
  assert.match(radio, /SignalStrengthsListener/);
});

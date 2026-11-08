/* (29/10, Ahmed : « tu la renommes, Inconnu et pas Machine à café ») chaque outil de voix du serveur de mémoire est permis
   à Hakim : voix_renommer était écrit, mais sans place dans ses outils il ne l'aurait jamais vu. node --test test-voix-outils.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const mcp = fs.readFileSync(path.join(os.homedir(), 'Desktop', 'anamnese', 'mcp_server.py'), 'utf8');

test('ses outils de voix (nommer, renommer, connaître, oublier, état) sont tous permis', () => {
  const debut = src.indexOf('const OUTILS_JARVIS = [');
  const outils = src.slice(debut, src.indexOf(']', debut));
  const voix = [...mcp.matchAll(/^def (voix_[a-z_]+)\(/gm)].map(m => m[1]);
  assert.ok(voix.includes('voix_renommer'), 'voix_renommer existe dans le serveur de mémoire');
  for (const o of voix) assert.ok(outils.includes(`'${o}'`), o);
});

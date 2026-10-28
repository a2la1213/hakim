/* Les gardes du cockpit restent appelées (28/10 ; plan « Hakim touche à son code avec maman », tâche 9). server.js est
   ouvert à Hakim hors de ses blocs fermés ; plusieurs routes ouvertes appellent l'empreinte d'Ahmed, le jeton ou le
   masquage des secrets. Une modification qui retirerait un de ces appels ferait échouer ce test (FERMÉ : il ne suit aucun
   module ouvert), et une promotion dont les tests échouent ne s'applique pas. Des fils tendus ; la relecture de maman
   reste la barrière. node --test test-gardes-appelees.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const ACTIONS = ["'cle-api'", "'notifications:abonner'", '`carnet:valider:', '`retractation:accepter:', '`regle:accepter:',
  '`ecriture:', '`mission:accepter:', '`sortie:autoriser:', '`identite:accepter:'];

for (const a of ACTIONS) {
  test(`l’empreinte d’Ahmed est toujours demandée pour ${a}`, () => {
    assert.ok(src.includes(`exigerPresence(req, distantReq, q, ${a}`), `exigerPresence n’est plus appelée pour ${a}`);
  });
}

test('le jeton et le masquage des secrets sont toujours appelés au moins autant qu’au 28/10', () => {
  assert.ok((src.match(/jetonValide\(req\)/g) || []).length >= 22, 'un contrôle du jeton a disparu');
  assert.ok((src.match(/masquer\(/g) || []).length >= 6, 'un masquage des secrets a disparu');
});

test('témoin : sans un appel, le fil tendu le voit', () => {
  const sans = src.replace("exigerPresence(req, distantReq, q, 'cle-api'", "null && (req, distantReq, q, 'cle-api'");
  assert.ok(!sans.includes("exigerPresence(req, distantReq, q, 'cle-api'"));
});

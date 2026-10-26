/* La bascule forfait → API → local (26/10, Ahmed : « on ne bascule JAMAIS d'après un pourcentage, seulement sur une VRAIE
   erreur ») : node --test test-bascule.js. Les fonctions sont lues dans server.js et jouées avec un état en mémoire. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

function monde(api = true) {
  const ctx = { Date, String, Math, JSON, abonnement: { limiteJusqua: 0 }, ecrits: 0, FORFAIT_REESSAI_MS: 10 * 60 * 1000,
    ABONNEMENT: '/dev/null', j: JSON.stringify };
  ctx.ecrireAtomique = () => { ctx.ecrits++; };
  ctx.apiPermise = () => api;                    // (26/10) la clé ET le plafond du jour (test-api-payante.js)
  vm.createContext(ctx);
  vm.runInContext(['noterAbonnement', 'forfaitALaLimite', 'sourcePour', 'sourceSuivante'].map(prendre).join('\n')
    + 'this.f = { noterAbonnement, forfaitALaLimite, sourcePour, sourceSuivante };', ctx);
  return ctx;
}

test('une limite ancienne sans erreur récente : on réessaie le forfait (le bug du 26/10, « API » affiché)', () => {
  const m = monde();
  m.abonnement.limiteJusqua = Date.now() + 12 * 3600 * 1000;          // notée hier, avant la règle : pas de limiteVu
  assert.equal(m.f.sourcePour('auto'), 'abonnement');
});

test('une vraie erreur de limite : API pendant 10 min, puis le forfait est réessayé', () => {
  const m = monde();
  m.f.noterAbonnement(null, Date.now() + 3600 * 1000);
  assert.equal(m.f.sourcePour('auto'), 'api');
  m.abonnement.limiteVu = Date.now() - 11 * 60 * 1000;
  assert.equal(m.f.sourcePour('auto'), 'abonnement');
});

test('le forfait répond « allowed » : la limite s’efface ; sans API, le secours est le local', () => {
  const m = monde(false);
  m.f.noterAbonnement({ status: 'rejected', resetsAt: Math.floor(Date.now() / 1000) + 3600 });
  assert.equal(m.f.sourcePour('auto'), 'local');
  m.f.noterAbonnement({ status: 'allowed', utilization: 0.99, unifiedWindows: { seven_day: { utilization: 0.99 } } });
  assert.equal(m.abonnement.limiteJusqua, 0);
  assert.equal(m.f.sourcePour('auto'), 'abonnement', 'un pourcentage haut ne fait jamais basculer');
});

test('une source imposée ne bascule jamais', () => {
  const m = monde();
  assert.equal(m.f.sourcePour('abonnement'), 'abonnement');
  assert.equal(m.f.sourceSuivante('abonnement', 'abonnement'), null);
  assert.equal(m.f.sourceSuivante('abonnement', 'auto'), 'api');
});

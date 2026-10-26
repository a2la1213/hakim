/* (26/10 soir, Ahmed : « plafond à 50 ») l'API payante de Hakim : un plafond par jour, et son cache gardé 1 h.
   node --test test-api-payante.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (debut) => { const i = src.indexOf(debut); return src.slice(i, src.indexOf('\n', i) + 1); };

function monde({ forfaitALaLimite = true } = {}) {
  const dossier = fs.mkdtempSync(path.join(os.tmpdir(), 'api-payante-'));
  const ctx = { fs, path, JSON, String, Number, Object, Math, Date, Set, process: { env: { ANTHROPIC_API_KEY: 'sk-ne-doit-pas-passer', PATH: '/usr/bin' } },
    JARVIS_JETONS: path.join(dossier, 'jetons.jsonl'), j: JSON.stringify, notifs: [], jour: '2026-10-27',
    apiEnPanneJusqua: 0, lireCleApi: () => 'cle', cleDansTrousseau: () => false };
  ctx.jourLocal = () => ctx.jour;
  ctx.notifier = (corps, tag) => ctx.notifs.push([corps, tag]);
  ctx.forfaitALaLimite = () => forfaitALaLimite;
  vm.createContext(ctx);
  vm.runInContext([ligne('const PLAFOND_API_JOUR_USD'), 'let plafondPrevenu = "";', prendre('bilanJetons'), prendre('noterJetons'),
    prendre('plafondApiAtteint'), prendre('prevenirPlafond'), ligne('function apiDisponible'), prendre('apiPermise'), prendre('sourcePour'),
    prendre('sourceSuivante'), prendre('envDuCerveau'),
    'this.f = { noterJetons, apiPermise, sourcePour, sourceSuivante, plafondApiAtteint, envDuCerveau };'].join('\n'), ctx);
  return { ctx, f: ctx.f };
}

test('sous 50 $ de la journée l’API sert de relais ; à 50 $ elle est fermée et Hakim passe au local', () => {
  const { f } = monde();
  f.noterJetons({ source: 'api', cout_usd: 49.5 });
  assert.equal(f.sourcePour('auto'), 'api');
  assert.equal(f.sourceSuivante('abonnement', 'auto'), 'api');
  f.noterJetons({ source: 'api', cout_usd: 0.6 });
  assert.equal(f.plafondApiAtteint(), true);
  assert.equal(f.apiPermise(), false);
  assert.equal(f.sourcePour('auto'), 'local');
  assert.equal(f.sourceSuivante('abonnement', 'auto'), 'local');
});

test('Ahmed qui impose l’API dans les réglages passe outre : c’est son geste', () => {
  const { f } = monde();
  f.noterJetons({ source: 'api', cout_usd: 80 });
  assert.equal(f.sourcePour('api'), 'api');
});

test('seule l’API compte (pas l’équivalent du forfait), et seulement celle du jour', () => {
  const { f, ctx } = monde();
  f.noterJetons({ source: 'abonnement', cout_usd: 300 });
  ctx.jour = '2026-10-26';
  f.noterJetons({ source: 'api', cout_usd: 337 });
  ctx.jour = '2026-10-27';
  assert.equal(f.plafondApiAtteint(), false);
  assert.equal(f.sourcePour('auto'), 'api');
});

test('Ahmed est prévenu une seule fois par jour, au tour qui franchit le plafond', () => {
  const { f, ctx } = monde();
  f.noterJetons({ source: 'api', cout_usd: 30 });
  assert.equal(ctx.notifs.length, 0);
  f.noterJetons({ source: 'api', cout_usd: 25 });
  assert.equal(ctx.notifs.length, 1);
  assert.match(ctx.notifs[0][0], /50 \$/);
  f.noterJetons({ source: 'api', cout_usd: 5 });
  assert.equal(ctx.notifs.length, 1, 'pas une deuxième fois le même jour');
  ctx.jour = '2026-10-28';
  f.noterJetons({ source: 'api', cout_usd: 60 });
  assert.equal(ctx.notifs.length, 2, 'le lendemain, de nouveau');
});

test('sur l’API son cache est gardé 1 h (5 min par défaut) ; sur le forfait rien ne change, et jamais de clé dans l’environnement', () => {
  const { f } = monde();
  const api = f.envDuCerveau('api'), forfait = f.envDuCerveau('abonnement');
  assert.equal(api.CLAUDE_CODE_PROMPT_CACHE_TTL, '1h');
  assert.equal(forfait.CLAUDE_CODE_PROMPT_CACHE_TTL, undefined);
  assert.equal(api.ANTHROPIC_API_KEY, undefined);
  assert.equal(forfait.ANTHROPIC_API_KEY, undefined);
  assert.equal(forfait.PATH, '/usr/bin');
});

// (07/11, Ahmed : « dans la conversation de Parler, j'aimerais aussi avoir le niveau d'effort sous l'orbe au lieu du prix de l'API »)
// le compteur sous l'orbe : jetons du jour, coût en francs, et l'effort que Hakim s'est choisi (effort_regler) à la place de l'API
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');

test('le compteur sous l’orbe : jetons · francs · son effort (à la place du prix de l’API)', () => {
  const d = page.indexOf('const EFFORTS_NOMS'), f = page.indexOf('\n}\n', page.indexOf('function texteCompteur(')) + 3;
  assert.ok(d >= 0 && f > d);
  const ctx = {}; vm.createContext(ctx); vm.runInContext(page.slice(d, f) + 'this.f = texteCompteur;', ctx);
  const lignes = [{ jetons: 1_200_000, usd: 2, source: 'abonnement' }, { jetons: 300_000, usd: 1, source: 'api' }];
  assert.equal(ctx.f({ lignes, chf_par_usd: 0.8, effort: 'max' }), '1,5 M · 2,4 CHF · effort max');
  assert.equal(ctx.f({ lignes, chf_par_usd: 0.8, effort: 'low' }), '1,5 M · 2,4 CHF · effort bas');
  assert.equal(ctx.f({ lignes, chf_par_usd: 0.8, effort: 'xhigh' }), '1,5 M · 2,4 CHF · effort très haut');
  assert.equal(ctx.f({ lignes: [{ jetons: 45_000, usd: 0.1, source: 'api' }], chf_par_usd: 0.8 }), '45 k · 0,08 CHF · API 0,08', 'un cockpit pas encore relancé : comme avant');
  assert.match(page, /z\.textContent = texteCompteur\(d\);/);
});

test('le cockpit donne son effort avec la consommation du jour', () => {
  const i = srv.indexOf("if (p === '/api/conso' && req.method === 'GET')");
  assert.match(srv.slice(i, i + 1500), /return res\.end\(j\(\{ lignes: [^\n]*, effort: EFFORT_HAKIM \}\)\);/);
});

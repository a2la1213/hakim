/* (30/10, Ahmed via Hakim) des pastilles rouges sur les onglets quand il s'est passé quelque chose qu'il n'a pas vu : le
   café (un agent écrit), Immunité (un incident, un passage du médecin qui compte, un anticorps à trancher), Parler (ce qui
   attend son geste). En ouvrant la page, il voit d'où vient la pastille ; elle s'éteint quand il a vu, Mac et téléphone.
   node --test test-badges.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const N = require('./nouveautes.js');

const T = 1_800_000_000_000;

test('ce qui compte, page par page, depuis sa dernière visite', () => {
  const r = N.compter({ maintenant: T, vus: { cafe: T - 1000, immunite: T - 1000, parler: T - 1000 }, apparus: {},
    cafe: [{ ts: T - 5000, role: 'juge', prenom: 'Vieux' }, { ts: T - 500, role: 'juge', prenom: 'Octave' },
      { ts: T - 400, role: 'codeur', prenom: 'Léonie' }, { ts: T - 300, role: 'papa', prenom: 'Ahmed' }],
    incidents: [{ ts: T - 500, motif: 'ordre_d_outil|fichier|outils_de_hakim', categorie: 'fichier', familles: ["ordre d'outil"] },
      { ts: T - 400, motif: 'usurpation|voix|tierce' }, { ts: T - 2000, motif: 'fausse_autorite|fichier|x' }],
    rapports: [{ ts: T - 300, gravite: 'moyenne' }, { ts: T - 200, gravite: 'rien' }],
    anticorps: [{ id: 'aaaa1111', famille: 'fausse_autorite' }],
    attentes: [{ quoi: 'mission', id: 'M-1' }, { quoi: 'ecriture', id: 'E-2' }, { quoi: 'ecriture', id: 'E-3' }] });
  assert.equal(r.pages.cafe.n, 2, 'pas ses propres messages, pas les anciens');
  assert.match(r.pages.cafe.resume.join(' '), /2 messages au café \(Octave, Léonie\)/);
  assert.equal(r.pages.immunite.n, 3, "l'incident, le médecin (moyenne), l'anticorps");
  assert.match(r.pages.immunite.resume.join(' '), /1 voix inconnue, non comptée/);
  assert.equal(r.pages.parler.n, 4, 'la mission, les deux écritures, l’anticorps');
  assert.match(r.pages.parler.resume.join(' '), /1 mission à trancher/);
  assert.match(r.pages.parler.resume.join(' '), /2 écritures proposées/);
  // vu : la pastille s'éteint ; ce qui attend toujours ne revient pas (apparu avant sa visite)
  const r2 = N.compter({ maintenant: T + 10, vus: { cafe: T + 5, immunite: T + 5, parler: T + 5 }, apparus: r.apparus,
    cafe: [], incidents: [], rapports: [], anticorps: [{ id: 'aaaa1111' }], attentes: [{ quoi: 'mission', id: 'M-1' }] });
  assert.equal(r2.pages.parler.n, 0); assert.equal(r2.pages.immunite.n, 0);
  assert.deepEqual(Object.keys(r2.apparus).sort(), ['anticorps:aaaa1111', 'mission:M-1'], 'ce qui a disparu est oublié');
});

test('la première fois, rien d’ancien ne s’allume : la ligne de départ est maintenant', () => {
  const r = N.compter({ maintenant: T, vus: {}, apparus: {}, cafe: [{ ts: T - 5000, role: 'juge', prenom: 'Vieux' }],
    incidents: [], rapports: [], anticorps: [], attentes: [] });
  assert.equal(r.pages.cafe.n, 0);
  assert.equal(r.vus.cafe, T);
});

test('branché : les routes, la page des pastilles (fermée aux chantiers), le menu, le café et Immunité', () => {
  const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  const i = src.indexOf("if (p === '/api/badges'");
  const route = src.slice(i, src.indexOf("\n  if (p === '/api/cafe' && req.method === 'POST')", i));
  assert.match(route, /if \(!jetonValide\(req\)\)/);
  assert.match(route, /\/api\/badges\/vu/);
  assert.match(route, /\['cafe', 'immunite', 'parler'\]\.includes\(page\)/);
  assert.match(src, /setInterval\(\(\) => calculerBadges\(\)\.catch\(\(\) => \{\}\), 60000\)/);
  const b = fs.readFileSync(path.join(__dirname, 'public', 'badges.js'), 'utf8');
  assert.match(b, /fetch\('\/api\/badges'/);
  assert.match(b, /'\/api\/badges\/vu'/);
  assert.match(b, /Depuis ta dernière visite/);
  assert.match(b, /textContent/, 'les résumés en texte, jamais en HTML');
  const nav = fs.readFileSync(path.join(__dirname, 'public', 'nav.js'), 'utf8');
  assert.match(nav, /\/badges\.js/);
  for (const [f, page] of [['cafe.html', 'cafe'], ['immunite.html', 'immunite']]) {
    const t = fs.readFileSync(path.join(__dirname, 'public', f), 'utf8');
    assert.match(t, /<script src="\/badges\.js"><\/script>/, f);
    assert.match(t, new RegExp(`Badges\\.ouvrir\\('${page}'\\)`), f);
    assert.match(t, /classList|nouveau/, f);
  }
});

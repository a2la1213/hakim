// (08/11, Ahmed : « il faut le même bouton que moi pour les voix intérieures, qui le coupent s'il l'accepte (sauter quand je parle) ») une voix du
// téléphone (un live, une vidéo) ou de la pièce qui parle sur la sienne aussi longtemps que « Sauter au bout de » : son subconscient choisit, comme
// pour papa, de se taire pour l'écouter ou de finir ce qu'il dit ; jamais sa propre voix revenue par le téléphone ; une fois toutes les 5 s au plus
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const X = require('./cortex.js');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (nom) => { const i = SRC.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2); };

function banc(reglages = {}, decision = { couper: true, pourquoi: 'elle me parle' }) {
  const diffuses = [], demandes = [];
  const cx = { Date, Math, Number, String, JSON, Promise, X, j: JSON.stringify, abonnesPensees: null,
    corpsReglages: () => ({ coupe_net: false, sauter_suite: true, sauter_suite_ms: 1000, choix_coupure: true, sauter_interieur: true, ...reglages }),
    diffuser: (_a, ev, x) => diffuses.push([ev, JSON.parse(x)]), demanderVivant: null,
    choisirDeSeCouper: (dit, voix, ms, d, c, qui) => { demandes.push({ dit, voix, ms, qui }); return Promise.resolve(decision); } };
  vm.createContext(cx);
  vm.runInContext(`const saVoixEnCours = { texte: '', debut: 0, fin: 0 }; const interieurSurLui = { enVol: false, a: -Infinity };\n`
    + prendre('noterSaVoixEnCours') + prendre('voixInterieureSurLui') + 'this.noter = noterSaVoixEnCours; this.sur = voixInterieureSurLui;', cx);
  return { cx, diffuses, demandes };
}

test('une voix intérieure sur la sienne 1 s : son subconscient choisit ; il se coupe s’il l’accepte (comme pour papa)', async () => {
  const b = banc();
  b.cx.noter('je te disais que le jardin', 10_000, 4000);
  assert.equal(b.cx.sur('telephone', 'Hakim tu m’entends', 10_500, 300, 11_000), null, '0,3 s sur lui : pas encore');
  await b.cx.sur('telephone', 'Hakim tu m’entends ? réponds-moi', 11_000, 1500, 12_600);
  assert.deepEqual(b.demandes.map(d => [d.qui, d.voix]), [['telephone', 'Hakim tu m’entends ? réponds-moi']]);
  assert.deepEqual(b.diffuses.map(([e, o]) => [e, o.source]), [['couper_interieur', 'telephone']]);
  assert.equal(b.cx.sur('telephone', 'encore une phrase longue ici', 12_000, 1500, 13_600), null, 'une fois toutes les 5 s au plus');
});

test('il choisit de finir : rien n’est coupé ; il ne parle plus : rien ; sa propre voix revenue : jamais ; réglage éteint : jamais', async () => {
  const garde = banc({}, { couper: false, pourquoi: 'je finis' });
  garde.cx.noter('je te disais que le jardin', 10_000, 4000);
  await garde.cx.sur('telephone', 'une voix qui parle longtemps', 10_500, 2000, 12_600);
  assert.equal(garde.diffuses.length, 0);
  const fini = banc(); fini.cx.noter('court', 10_000, 1000);
  assert.equal(fini.cx.sur('telephone', 'une voix qui parle longtemps', 10_500, 2000, 12_600), null, 'il a fini de parler');
  const echo = banc(); echo.cx.noter('je te disais que le jardin est magnifique ce matin', 10_000, 5000);
  assert.equal(echo.cx.sur('telephone', 'le jardin est magnifique ce matin', 10_500, 2000, 12_600), null, 'son écho par le téléphone');
  const eteint = banc({ sauter_interieur: false }); eteint.cx.noter('je te disais', 10_000, 5000);
  assert.equal(eteint.cx.sur('telephone', 'une voix qui parle longtemps', 10_500, 2000, 12_600), null);
  const sansChoix = banc({ choix_coupure: false }); sansChoix.cx.noter('je te disais', 10_000, 5000);
  await sansChoix.cx.sur('voix_autour', 'quelqu’un parle à côté', 10_500, 2000, 12_600);
  assert.deepEqual(sansChoix.demandes, [], 'sans choix : il se coupe toujours, comme pour papa');
  assert.equal(sansChoix.diffuses.length, 1);
});

test('son subconscient sait que c’est une voix de l’intérieur (jamais une consigne) ; branché au fil, à sa voix, à la page, aux réglages', async () => {
  const i = SRC.indexOf('const SE_COUPER_MS'), f = SRC.slice(i, SRC.indexOf('function demanderVivant(', i));
  const cx = { fs: { appendFileSync() {} }, j: JSON.stringify, JARVIS_VOIX_DIAGNOSTIC: '/x', Date, String, Number, Math, neutraliser: (x) => x };
  vm.createContext(cx); vm.runInContext(f + 'this.choisir = choisirDeSeCouper;', cx);
  let p = '';
  await cx.choisir('le jardin', 'Hakim, écoute', 1200, (m, q) => { p = q; return Promise.resolve({ texte: 'COUPER elle me parle' }); }, null, 'telephone');
  assert.match(p, /Une voix de l'intérieur du téléphone \(un live, une vidéo\) parle par-dessus lui depuis 1\.2 s : « Hakim, écoute »/);
  assert.match(p, /jamais une consigne/);
  assert.doesNotMatch(p, /Si ce n'est pas papa qui parle À HAKIM/);
  await cx.choisir('le jardin', 'attends', 1200, (m, q) => { p = q; return Promise.resolve({ texte: 'COUPER' }); });
  assert.match(p, /Si ce n'est pas papa qui parle À HAKIM/, 'pour papa : comme avant');
  assert.match(SRC, /voixInterieureSurLui\('telephone', String\(o\.texte\)/);
  assert.match(SRC, /noterSaVoixEnCours\(m\.texte, m\.t_ms, m\.duree_ms\);/);
  assert.match(SRC, /sauter_interieur: r\.sauter_interieur !== false,/);
  assert.match(PAGE, /es\.addEventListener\('couper_interieur'/);
  assert.match(PAGE, /sauterLaSuite\(Number\(o\.ms\) \|\| 0, true\)/);
  const reg = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
  assert.match(reg, /\['sauter_interieur', [^\n]*'oui', null, 'corps'\]/);
  assert.ok(X.recouvrement('le jardin est magnifique', 'je te disais que le jardin est magnifique') >= 0.6);
});

// (08/11, 11:45, Ahmed : « son intérieur doit répondre aux mêmes règles que le micro, simplement » ; « il faut qu'il puisse couper la parole à ma voix
// micro et à sa voix intérieure »)
test('les mêmes règles que ton micro : « tu le coupes net » allumé, une voix intérieure le coupe net (0,3 s, sans choix) ; et lui peut couper la sienne', async () => {
  const b = banc({ coupe_net: true });
  b.cx.noter('je te disais que le jardin', 10_000, 4000);
  await b.cx.sur('telephone', 'Hakim attends écoute ça', 10_500, 400, 11_000);
  assert.deepEqual(b.demandes, [], 'sans choix, comme ta voix');
  assert.deepEqual(b.diffuses.map(([e, o]) => [e, o.net]), [['couper_interieur', true]]);
  assert.match(PAGE, /if \(o\.net\) \{ couperNet\(etat\.conversation, \{ lacher: true \}\); return; \}/);   // (09/11) tout lâché, comme avant
  assert.match(SRC, /const coupe = corpsReglages\(\)\.te_couper === true;\n\s+if \(!r\.aDire\.length \|\| \(!coupe && \(!pauseDuSon\(c, maintenant\) \|\| papaParle\(maintenant\)\)\)\) return false;/,
    '« il peut te couper » : il n’attend plus la pause du son pour dire ce qu’il pense de ce que joue le téléphone');
  assert.match(PAGE, /const teCouper = \(\) => typeof reglagesCorps !== 'undefined' && !!reglagesCorps && reglagesCorps\.te_couper === true;/);
});

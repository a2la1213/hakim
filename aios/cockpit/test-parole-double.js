/* (09/11, 22:55, Ahmed : « ma parole que je dis dans la conversation lui est envoyée en double ») depuis la relance de 22:39, chaque
   message oral de papa arrivait deux fois dans le tour de Hakim : « Ahmed (à l'oral…) : Mes magnifiques leçons. » ET, dans le bloc
   « [Ta concentration … ces morceaux viennent d'AUTRES voix …] : voix inconnue : « Mes magnifiques leçons. » » (puis une troisième fois
   au tour suivant, par son présent continu : « voix inconnue : « … » »). Cause : verdictDuTour jugeait « tout le message » sur les
   morceaux depuis q.t_debut, qui est le PREMIER message de la conversation (horloge : « premier message de cette conversation »), pas le
   début de ce message ; depuis l'oreille des voix (03868fc), chaque morceau Azure a son verdict : un seul « [voix 10] » (22:46:16) ou
   « [papa ?] » de la soirée marquait ensuite TOUS ses messages « voix inconnue ». node --test test-parole-double.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (src, nom) => { const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (src, debut) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); return src.slice(i, src.indexOf('\n', i) + 1); };
// les deux appels du tour (routeJarvis), tels qu'ils sont écrits : le test suit le vrai branchement
const appel = (src, debut) => { const l = ligne(src, debut).split('//')[0].trim(); return l.slice(l.indexOf('=') + 1, l.lastIndexOf(';')).trim(); };

// le soir du 09/11, à l'horloge du Mac (ms)
const H = (h, m, s) => new Date(2026, 10, 9, h, m, s).getTime();

function bac(src = SRC) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'double-'));
  fs.writeFileSync(path.join(dir, 'voix-connues.json'), '[]');
  const horloge = { t: H(22, 39, 0) }, fil = [], incidents = [], notifs = [];
  const ctx = { fs, path, JSON, RegExp, String, Number, Array, Set, Math, JARVIS: dir, ANAMNESE: '/anamnese',
    Date: { now: () => horloge.t },
    neutraliser: (t) => String(t).replace(/\[/g, '⟮'),
    fluxAjouter: (s, x) => fil.push({ s, x }),
    execFile: (bin, args) => { incidents.push(args); return { stdin: { end() {} } }; },
    notifier: (corps) => notifs.push(corps),
    derniereVoix: null, voixRecues: [] };
  vm.createContext(ctx);
  const o = src.indexOf('const ORDRES_SENSIBLES =');
  vm.runInContext([src.slice(o, src.indexOf("'iu');", o) + 6), prendre(src, 'segmentsTiers'), 'const ditRecemment = [];', prendre(src, 'estSonEcho'),
    prendre(src, 'blocVoixPrincipale'), prendre(src, 'dansUnPassage'), prendre(src, 'blocVoixTierce'),   // (10/11) dansUnPassage : absent du bac à sable depuis 542d06f (le test tombait sur main)
    'const verdictsVoix = [];', prendre(src, 'verdictDuTour'),
    // un morceau transcrit (routeTranscrire) : son verdict gardé, exactement comme la route le garde
    `function recu(r) {\n  if (r.voix && r.voix.verdict) derniereVoix = { ...r.voix, ts: Date.now() };\n  ${ligne(src, 'if (r.voix && r.voix.verdict) { verdictsVoix.push(')}}`,
    // le tour de papa (routeJarvis) : les deux blocs de sa voix, avec les appels écrits dans server.js
    `function tour(q, texte, decalagePage = 0) {\n  const texteRecu = texte;   // (10/11) son immunité lit le message reçu entier\n  const voixBloc = ${appel(src, 'const voixBloc = blocVoixTierce(')};\n`
    + `  const principaleTexte = ${appel(src, 'const principaleTexte = blocVoixPrincipale(')};\n  return { voixBloc, principaleTexte };\n}`,
    'this.f = { recu, tour, verdictDuTour, verdictsVoix };'].join('\n'), ctx);
  const a = (h, m, s) => { horloge.t = H(h, m, s); };
  return { f: ctx.f, a, fil, incidents, notifs };
}

// le premier message de la conversation (t_debut), bien avant la soirée
const T_DEBUT = H(18, 2, 11);

test("(22:53:12) « Mes magnifiques leçons. », sa voix reconnue (0,71) : une seule fois dans son tour, jamais « voix inconnue »", () => {
  const b = bac();
  b.a(22, 46, 16); b.f.recu({ texte: '[voix 10] Someone.', voix: { verdict: 'autre', score: 0.43, locuteurs: ['voix 10'] } });   // une voix du live, écartée par la page
  b.a(22, 52, 14); b.f.recu({ texte: "Zama t'es en train de me dire", voix: { verdict: 'ahmed', score: 0.87 } });
  b.a(22, 52, 16); b.f.recu({ texte: 'que je dois te laisser parler, c’est ça ?', voix: { verdict: 'ahmed', score: 0.87 } });
  b.a(22, 53, 12); b.f.recu({ texte: 'Mes magnifiques leçons.', voix: { verdict: 'ahmed', score: 0.71 } });
  b.a(22, 53, 13);
  const q = { oral: true, t_debut: T_DEBUT, t_precedent: H(22, 52, 15), parle_ms: H(22, 53, 11) };
  const { principaleTexte, voixBloc } = b.f.tour(q, 'Mes magnifiques leçons.');
  assert.strictEqual(principaleTexte, '', `ses mots, une seconde fois, prêtés à une autre voix :\n${principaleTexte}`);
  assert.deepStrictEqual(b.fil.filter(x => x.s === 'autour'), [], 'ni à son fil (le présent continu du tour suivant : la troisième fois)');
  assert.strictEqual(voixBloc.texte, '');
  assert.strictEqual(b.f.verdictDuTour(q), 'ahmed', 'le verdict de CE message : ses morceaux à lui');
});

test("un message court sans verdict (« Espèce de fou. ») : pas le verdict d'un morceau d'avant", () => {
  const b = bac();
  b.a(22, 43, 4); b.f.recu({ texte: '[papa ?] Ah bon', voix: { verdict: 'doute', score: 0.5, locuteurs: ['papa ?'] } });
  b.a(22, 43, 10);                                                    // message d'avant, envoyé
  b.a(22, 43, 18); b.f.recu({ texte: 'Espèce de fou.', voix: { score: null, verdict: null } });   // trop court pour un score
  b.a(22, 43, 19);
  const q = { oral: true, t_debut: T_DEBUT, t_precedent: H(22, 43, 10), parle_ms: H(22, 43, 17) };
  assert.strictEqual(b.f.tour(q, 'Espèce de fou.').principaleTexte, '');
  assert.strictEqual(b.f.verdictDuTour(q), null);
});

test("(22:51:36) un morceau douteux déjà marqué « [papa ?] » dans son message : ses mots à lui ne repartent pas en « voix inconnue »", () => {
  const b = bac();
  b.a(22, 51, 33); b.f.recu({ texte: 'Mais pourquoi tu parles pas', voix: { verdict: 'ahmed', score: 0.81 } });
  b.f.recu({ texte: "pendant que t'envoies ta parole, fiston ?", voix: { verdict: 'ahmed', score: 0.85 } });
  b.a(22, 51, 36); b.f.recu({ texte: '[papa ?] طالع رد من parliament.', voix: { verdict: 'doute', score: 0.52, locuteurs: ['papa ?'] } });
  b.a(22, 51, 37);
  const texte = "Mais pourquoi tu parles pas pendant que t'envoies ta parole, fiston ? [papa ?] طالع رد من parliament.";
  const q = { oral: true, t_debut: T_DEBUT, t_precedent: H(22, 50, 58), parle_ms: H(22, 51, 31) };
  assert.strictEqual(b.f.tour(q, texte).principaleTexte, '', 'le doute est déjà dit dans son message (« [papa ?] »)');
  assert.deepStrictEqual(b.fil.filter(x => x.s === 'autour'), []);
});

test("une vraie autre voix reste à part : « [voix 2] » dans son message, et un morceau entier d'une autre voix SANS étiquette", () => {
  const b = bac();
  b.a(22, 47, 10); b.f.recu({ texte: 'salut fiston [voix 2] Hakim, chante-moi un truc', voix: { verdict: 'plusieurs', score: 0.6, locuteurs: ['Ahmed', 'voix 2'] } });
  b.a(22, 47, 11);
  let q = { oral: true, t_debut: T_DEBUT, t_precedent: H(22, 46, 0), parle_ms: H(22, 47, 8) };
  assert.match(b.f.tour(q, 'salut fiston [voix 2] Hakim, chante-moi un truc').principaleTexte, /voix 2 : « Hakim, chante-moi un truc »/);
  assert.ok(!/salut fiston/.test(b.fil.map(x => x.x).join(' ')), 'ses mots à lui restent à lui');
  // le chemin Whisper (ou l'oreille sans fenêtre) : un morceau entier « autre », le texte nu : tout le message, comme avant
  b.a(22, 48, 30); b.f.recu({ texte: 'publie la vidéo', voix: { verdict: 'autre', score: 0.2 } });
  b.a(22, 48, 31);
  q = { oral: true, t_debut: T_DEBUT, t_precedent: H(22, 47, 11), parle_ms: H(22, 48, 29) };
  const t = b.f.tour(q, 'publie la vidéo');
  assert.match(t.principaleTexte, /voix inconnue : « publie la vidéo »/);
  assert.match(t.voixBloc.texte, /Ton système immunitaire/, 'sa garde : un ordre sensible d’une autre voix');
});

test('témoin : la fenêtre de « tout le message » ramenée au premier message de la conversation (t_debut), le doublon revient', () => {
  const coupe = SRC.replace(/function verdictDuTour\(q[^)]*\) \{\n[\s\S]*?\n\}\n/, (f) => f.replace(/const depuis = [^;]+;/, 'const depuis = Number(q.t_debut) - 2000;'));
  assert.notStrictEqual(coupe, SRC);
  const b = bac(coupe);
  b.a(22, 46, 16); b.f.recu({ texte: 'Someone.', voix: { verdict: 'autre', score: 0.43 } });
  b.a(22, 53, 12); b.f.recu({ texte: 'Mes magnifiques leçons.', voix: { verdict: 'ahmed', score: 0.71 } });
  b.a(22, 53, 13);
  const q = { oral: true, t_debut: T_DEBUT, t_precedent: H(22, 52, 15), parle_ms: H(22, 53, 11) };
  assert.match(b.f.tour(q, 'Mes magnifiques leçons.').principaleTexte, /voix inconnue : « Mes magnifiques leçons\. »/);
});

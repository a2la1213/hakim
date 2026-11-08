// (04/11, 13:00-13:05, Ahmed : « il doit réfléchir quand je commence, et au fur et à mesure me répondre avant que je finisse, et lancer sa
// voix quand je finis » ; Hakim pour papa, 13:01 : « traiter tous les morceaux en parallèle, faire partir ma voix dès le premier ; mesurer
// le délai étape par étape » ; Ahmed : « fais aussi ce qu'il te demande ») mesuré : 21 pensées pour 98 de tes phrases en une heure
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const attendre = () => new Promise(r => setImmediate(r));

function bac(reglages = { epissage: true, filtre_gemma: false }) {
  const i = SRC.indexOf('const PISTES_MAX'), k = SRC.indexOf('function speculerFreres(');
  const appels = [], diffuses = [], notes = [];
  const ctx = { String, Math, Date, Promise, RegExp, Object, JSON, VIVANTS: [], VIVANTS_MAX: { haiku: 12, sonnet: 12, opus: 12 }, VIVANT_RENOUVELER: 6,
    cerveau: { modele: 'sonnet' }, corpsReglages: () => reglages, personaLocale: (p) => p, lirePersona: () => 'Hakim', neutraliser: (t) => t,
    j: JSON.stringify, abonnesPensees: null, path, JARVIS: '/x', fs: { appendFile: (f, d) => notes.push(JSON.parse(d)), readFile() {}, writeFile() {} },
    voixDeLaSource() {}, diffuser: (_, e, d) => { const x = JSON.parse(d); if (x.niveau !== 'papa') diffuses.push(x); },
    sonnetTeteDeFond: (prompt, etiquette) => new Promise((resoudre) => { const v = { attente: {}, proc: { exitCode: null }, n: 1 }; ctx.VIVANTS.push(v);
      appels.push({ prompt, etiquette, resoudre: (o) => { v.attente = null; resoudre(o); } }); }) };
  vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k) + '\nthis.morceau = pisteMorceau; this.etat = () => pistes; this.pour = morceauxPour; this.nouveauTour = () => { pistes = { tour: pistes.tour + 1, mots: 0, liste: [], attente: [], n: 0 }; };', ctx);
  return { ctx, appels, diffuses, notes };
}
const nu = (x) => JSON.parse(JSON.stringify(x));

test('Hakim réfléchit dès tes 3 premiers mots, puis tous les 6 mots même sans virgule ; la virgule coupe toujours', () => {
  const { ctx } = bac();
  const d = (t, premier) => nu(ctx.pour('sonnet', t.split(' '), premier));
  assert.deepStrictEqual(d('papa je voulais te dire un truc important ce soir', true),
    { morceaux: ['papa je voulais', 'te dire un truc important ce'], reste: 1 }, 'le premier dès 3 mots, puis 6');
  assert.deepStrictEqual(d('et puis demain on ira voir', false), { morceaux: ['et puis demain on ira voir'], reste: 0 });
  assert.deepStrictEqual(d('papa, tu sais', true), { morceaux: ['papa,'], reste: 2 }, 'la virgule coupe toujours');
  assert.deepStrictEqual(nu(ctx.pour('haiku', ['le', 'chat', 'dort'], true)).morceaux, ['le chat', 'dort'], 'Mini Hakim : un mot, comme avant');
});

test('une pensée qui arrive après la fin de ta phrase n’est plus jetée : elle rejoint le ribosome de son tour', async () => {
  const b = bac();
  b.ctx.morceau('papa je voulais');
  const tour = b.ctx.etat().tour;
  b.ctx.nouveauTour();                                                 // ta phrase est partie au cerveau
  b.appels[0].resoudre({ texte: 'Oui papa, dis-moi.' });
  await attendre(); await attendre();
  const p = b.diffuses.find(x => x.niveau === 'piste');
  assert.ok(p, 'écrite dans le pavé de son tour');
  assert.ok(p.tour > 1e12, '(15:10) le numéro de son épissure (né avant que ta phrase parte), pas celui du tour suivant');
  const ribo = b.appels.find(a => a.etiquette === 'ribosome_opus');
  assert.ok(ribo, 'lue par son ribosome');
  assert.match(ribo.prompt, /\[1\] « Oui papa, dis-moi\. »/);
  b.appels.filter(a => a.etiquette.startsWith('ribosome_')).forEach(a => a.resoudre({ texte: 'GARDE : « Oui papa »' }));   // ses trois lecteurs
  await attendre(); await attendre();
  assert.strictEqual(b.diffuses.find(x => x.niveau === 'ribosome').tour, p.tour, '(15:10) le numéro de son épissure, celui de sa pensée');
  const c = bac({ epissage: false, filtre_gemma: false });
  c.ctx.morceau('papa je voulais');
  c.ctx.nouveauTour();
  c.appels[0].resoudre({ texte: 'Oui papa, dis-moi.' });
  await attendre(); await attendre();
  assert.strictEqual(c.diffuses.length, 0, 'sans l’épissage : comme avant');
});

test('chaque lecture du ribosome est mesurée (pistes.jsonl) : de quoi mesurer le délai étape par étape', async () => {
  const b = bac();
  b.ctx.morceau('papa je voulais');
  b.appels[0].resoudre({ texte: 'Oui papa, dis-moi.' });
  await attendre(); await attendre();
  b.appels.filter(a => a.etiquette.startsWith('ribosome_')).forEach(a => a.resoudre({ texte: 'GARDE : « Oui papa »' }));
  await attendre(); await attendre();
  const r = b.notes.find(x => x.ribosome);
  assert.ok(r, 'noté');
  assert.strictEqual(r.ribosome, 1);
  assert.ok(Number.isFinite(r.ms) && r.ms >= 0);
  assert.strictEqual(r.garde, 'Oui papa');
  assert.strictEqual(r.pensees, 1, 'combien de pensées dans son paquet');
  assert.deepStrictEqual(r.lecteurs.map(x => x.modele), ['opus', 'opus'], 'chacun de ses lecteurs (19:20 : deux Super Hakim), avec son temps');
  assert.ok(r.lecteurs.every(x => Number.isFinite(x.ms) && x.garde === 'Oui papa'));
});

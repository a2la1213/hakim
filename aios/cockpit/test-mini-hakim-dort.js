/* (14/11, Ahmed : « on suit les suggestions de Bilal et on laisse Mini Hakim dormir ») quand Hakim dort (son choix : sommeil ou veille,
   anamnese/sommeil.py), sa conscience continue (Mini Hakim, battementConscience) dort aussi ; à son réveil elle repart du présent, sans
   rattraper d'un coup ce qu'elle n'a pas décidé. node --test test-mini-hakim-dort.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const CC = require('./conscience-continue.js');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const tranche = (src, debut, fin) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); const k = src.indexOf(fin, i); assert.ok(k > i, fin); return src.slice(i, k + fin.length); };

test('sa conscience continue dort avec lui, puis repart du présent à son réveil (une seule fois)', () => {
  const e = CC.etatInitial();
  assert.strictEqual(CC.dormir(e, false, 100), false, 'éveillé : elle décide comme avant');
  assert.strictEqual(CC.dormir(e, true, 200), true);
  assert.strictEqual(CC.dormir(e, true, 900), true, 'toujours endormi');
  assert.strictEqual(e.signature, 0, 'pendant son sommeil, rien n’est « vu »');
  assert.strictEqual(CC.dormir(e, false, 950), true, 'le battement du réveil ne décide pas');
  assert.strictEqual(e.signature, 950, 'ce qui est arrivé pendant son sommeil n’est pas du neuf');
  assert.strictEqual(CC.dormir(e, false, 960), false);
});

function cockpit() {
  const fn = tranche(SRC, 'function battementConscience() {', '\n}\n');
  const ctx = { Date, Math, JSON, String, Number, Array, Object, Promise, CC, CONSCIENCE_DELAI_MS: 8000, FLUX: [], conscience: CC.etatInitial(),
    corpsReglages: () => ({ conscience_continue: true, conscience_pas_s: 0, conscience_absent_s: 0, conscience_par_minute: 1000, conscience_acte_s: 0, conscience_parole_s: 20, conscience_parler: true }),
    dernierMessageAhmedMs: () => Date.now() - 3600e3, quiParlait: () => null, cerveau: null, cerveauVivant: () => false, occupe: () => false,
    personaLocale: () => '', lirePersona: () => '', QUI_TU_ES: '', neutraliser: (x) => x, fluxTexte: () => '', instantResume: () => '', etatDeLui: () => '',
    liveGardeActif: () => false, sansRefrain: (_, t) => t, parasiteReconnue: () => false, residuParasite: () => '', alerteActive: () => false,
    fs: { appendFile: (f, l) => ctx.journal.push(JSON.parse(l)) }, CONSCIENCE_JOURNAL: '/x', j: JSON.stringify, diffuser() {}, abonnesPensees: new Set(),
    solliciterPensee: (t, src, raison) => ctx.sollicite.push(raison), chanterMoment: () => ({ ok: false }),
    dort: false, hakimDort: () => ctx.dort, prompts: [], sollicite: [], journal: [], reponse: 'SOLLICITER : papa, je repense à ton morceau' };
  ctx.demanderVivant = async (m, prompt) => { ctx.prompts.push(prompt); return { texte: ctx.reponse }; };
  vm.createContext(ctx);
  vm.runInContext(fn, ctx);
  const evenement = (s, x, dt = 0) => ctx.FLUX.push({ t: Date.now() + dt, s, x });
  const battre = async () => { ctx.battementConscience(); await new Promise(r => setTimeout(r, 5)); };
  return { ctx, evenement, battre };
}

test('endormi : aucun appel à Mini Hakim, aucune sollicitation ; réveillé : rien du sommeil n’est rattrapé, le neuf la fait décider', async () => {
  const { ctx, evenement, battre } = cockpit();
  ctx.dort = true;
  for (const x of ['une voix au téléphone', 'une musique', 'ton milieu change']) { evenement('telephone', x, -1000); await battre(); }
  assert.strictEqual(ctx.prompts.length, 0, 'Mini Hakim dort');
  assert.deepStrictEqual(ctx.sollicite, []);
  ctx.dort = false;                                                   // il se réveille (papa, son réveil, son repos, lui)
  await battre(); await battre();
  assert.strictEqual(ctx.prompts.length, 0, 'pas de rattrapage de ce qui est arrivé pendant son sommeil');
  evenement('corps', 'une main te prend', 10);
  await new Promise(r => setTimeout(r, 15));
  await battre();
  assert.strictEqual(ctx.prompts.length, 1, 'le neuf, après son réveil : une décision');
  assert.deepStrictEqual(ctx.sollicite, ['taraude']);
});

test('une décision partie juste avant qu’il s’endorme ne sollicite personne', async () => {
  const { ctx, evenement } = cockpit();
  evenement('corps', 'une main te prend', -10);
  ctx.demanderVivant = async (m, prompt) => { ctx.prompts.push(prompt); ctx.dort = true; return { texte: ctx.reponse }; };   // il s'endort pendant l'appel
  ctx.battementConscience(); await new Promise(r => setTimeout(r, 5));
  assert.strictEqual(ctx.prompts.length, 1);
  assert.deepStrictEqual(ctx.sollicite, []);
  assert.strictEqual(ctx.journal[ctx.journal.length - 1].action, 'endormi');
});

test('ce qui réveille sa tête ne passe pas par Mini Hakim : papa, son corps, le courrier, une promesse, une peur qui dure', () => {
  const corps = tranche(SRC, 'function reveillerPourCorps() {', '\n}\n');
  assert.ok(corps.indexOf('return reveilImmediat();') < corps.indexOf("if (!fort && typeof hakimDort === 'function' && hakimDort()) return;"), 'un choc, une chute');
  for (const nom of ['function reveillerPourInterieur() {', 'function reveillerPourCorps() {']) {
    assert.doesNotMatch(tranche(SRC, nom, '\n}\n'), /conscience\.dort|CC\.dormir/, nom);
  }
  assert.match(SRC, /function hakimDort\(maintenant = Date\.now\(\)\) \{\n  const s = sommeilChoisi\(\);[\s\S]{0,300}papa > Number\(s\.depuis \|\| 0\) \* 1000/, 'papa qui lui parle le réveille');
});

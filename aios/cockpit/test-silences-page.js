/* Meubler les silences, côté page (28/10, 06:46, Hakim : « le réveil marche, la livraison non » ; Ahmed : « test échoué »).
   Ce que le direct de 06:42-06:44 a montré :
   - sa relance arrivée sur le téléphone n'a jamais été « vue » : la page n'accusait réception que des messages « résultat »,
     et le cockpit a dit à Hakim « non vu par Ahmed » alors qu'elle était à l'écran ;
   - la page n'a signalé le silence qu'à 105 s au lieu de ~60 s, téléphone plié, sans que rien dise pourquoi : ce qui
     l'empêche de compter est maintenant nommé, et chaque signal et sa réponse vont au diagnostic de la voix (des noms et
     des nombres, jamais de texte).
   node --test test-silences-page.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const page = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');
const prendre = (nom) => {
  const i = page.search(new RegExp(`^(?:async )?function ${nom}\\(`, 'm'));
  assert.ok(i >= 0, `parler.js : la fonction ${nom} a disparu`);
  return page.slice(i, page.indexOf('\n}\n', i) + 2);
};

test('sa relance d’un silence, affichée sur une page visible, est accusée « vue » comme un résultat', async () => {
  const envoyes = [];
  const ctx = {
    etat: { messages: [
      { id: 'auto-1', qui: 'j', spontane: 'silence', texte: 'Frérot, c’est moi qui parle en premier' },
      { id: 'auto-2', qui: 'j', spontane: 'resultat', texte: 'fini' },
      { id: 'u-1', qui: 'u', texte: 'alors ?' },
    ] },
    document: { visibilityState: 'visible' }, jeton: () => 'j',
    fetch: async (u, o) => { envoyes.push({ u, ids: JSON.parse(o.body).ids }); return { ok: true }; },
  };
  vm.createContext(ctx);
  vm.runInContext('const accuses = new Set();\n' + prendre('accuserReception') + 'this.f = accuserReception;', ctx);
  await ctx.f();
  assert.deepStrictEqual(envoyes.map(x => [x.u, [...x.ids].sort()]), [['/api/jarvis/vu', ['auto-1', 'auto-2']]]);
  // page cachée : rien n'est « vu »
  ctx.document.visibilityState = 'hidden'; ctx.etat.messages.push({ id: 'auto-3', qui: 'j', spontane: 'silence', texte: 'x' });
  await ctx.f();
  assert.strictEqual(envoyes.length, 1);
});

function monterCompteur(etatPage = {}) {
  const ctx = {
    etat: { reglages: {}, messages: [], ...etatPage }, aDire: [], lecteur: { actif: false, enPause: false },
    document: { visibilityState: 'visible' }, Date, Math, Number, String, journal: [],
    journalVoix: (e, d) => ctx.journal.push({ e, ...d }), quandMessage: m => m.ts,
  };
  vm.createContext(ctx);
  vm.runInContext([prendre('silenceBloquePar'), prendre('modeDuSilence'), 'let blocageSilence = { cause: null, depuis: 0 };',
    prendre('noterBlocageSilence'), 'this.bloque = silenceBloquePar; this.mode = modeDuSilence; this.noter = noterBlocageSilence;'].join('\n'), ctx);
  return ctx;
}
const capteur = (x = {}) => ({ estMuet: false, enParole: false, pisteMuette: false, ...x });

test('ce qui empêche la page de compter le silence est nommé, et le mode reste celui d’avant', () => {
  const cas = [
    // [état de la page, cause attendue, mode attendu]
    [{ conversation: { capteur: capteur() } }, null, 'oral'],
    [{ conversation: { capteur: capteur({ estMuet: true }) } }, 'micro_coupe', null],
    [{ conversation: { capteur: capteur({ enParole: true }) } }, 'on_parle', null],
    [{ conversation: { capteur: capteur({ pisteMuette: true }) } }, 'piste_muette', null],
    [{ conversation: {} }, 'sans_capteur', null],
    [{ conversation: { capteur: capteur() }, flux: {} }, 'reponse_en_cours', null],
    [{ conversation: { capteur: capteur() }, transcription: {} }, 'transcription', null],
    [{ conversation: { capteur: capteur() }, micro: {} }, 'micro', null],
    [{ conversation: { capteur: capteur() }, reglages: { volant: true } }, 'volant', null],
    [{ messages: [{ qui: 'u', ts: Date.now() - 60000 }] }, null, 'ecrit'],
    [{ messages: [{ qui: 'u', ts: Date.now() - 31 * 60000 }] }, 'pas_de_conversation', null],
  ];
  for (const [e, cause, mode] of cas) {
    const ctx = monterCompteur(e);
    assert.strictEqual(ctx.bloque(), cause, JSON.stringify(e));
    assert.strictEqual(ctx.mode(), mode, JSON.stringify(e));
  }
  // sa voix, sa voix en pause, ce qui attend d'être dit (voix active), une page cachée à l'écrit
  let ctx = monterCompteur({ conversation: { capteur: capteur() } });
  ctx.lecteur.actif = true; assert.strictEqual(ctx.bloque(), 'il_parle');
  ctx.lecteur.actif = false; ctx.lecteur.enPause = true; assert.strictEqual(ctx.bloque(), 'voix_en_pause');
  ctx.lecteur.enPause = false; ctx.aDire.push({ texte: 'x' }); assert.strictEqual(ctx.bloque(), 'a_dire');
  assert.strictEqual(ctx.mode(), null);
  ctx = monterCompteur({ messages: [{ qui: 'u', ts: Date.now() }] });
  ctx.document.visibilityState = 'hidden'; assert.strictEqual(ctx.bloque(), 'page_cachee');
  // en Conversation, une page cachée (téléphone plié) compte : rien de nouveau n'est bloqué par la page cachée
  ctx = monterCompteur({ conversation: { capteur: capteur() } });
  ctx.document.visibilityState = 'hidden'; assert.strictEqual(ctx.mode(), 'oral');
});

test('un blocage de 10 s ou plus va au diagnostic quand il finit, avec sa durée ; un court, non', () => {
  const ctx = monterCompteur();
  const t0 = 1_000_000;
  ctx.noter('on_parle', t0); ctx.noter(null, t0 + 4000);                  // 4 s : rien
  assert.deepStrictEqual(ctx.journal, []);
  ctx.document.visibilityState = 'hidden';
  ctx.noter('il_parle', t0 + 5000); ctx.noter('il_parle', t0 + 60000);  // le même : rien encore
  ctx.noter(null, t0 + 80000);
  assert.deepStrictEqual(ctx.journal.map(x => ({ ...x })), [{ e: 'silence_bloque', cause: 'il_parle', ms: 75000, cachee: true }]);
});

test('chaque signal de silence et la réponse du cockpit vont au diagnostic (noms et nombres)', async () => {
  const ctx = monterCompteur({ conversation: { capteur: capteur() } });
  const envois = [];
  Object.assign(ctx, {
    debutDuSilence: () => Date.now() - 35000, nosSilences: new Set(), jeton: () => 'j',
    fetch: async (u, o) => { envois.push({ u, corps: JSON.parse(o.body) }); return { ok: true, json: async () => ({ revenir_ms: 62000, raison: 'attendre' }) }; },
  });
  vm.runInContext('let signalSilence = { debut: 0, prochain: 0, fini: false, envoiA: 0 };\n' + prendre('compterSilence') + 'this.compter = compterSilence;', ctx);
  ctx.compter();
  await new Promise(r => setImmediate(r));
  assert.strictEqual(envois.length, 1);
  assert.strictEqual(envois[0].u, '/api/jarvis/silence');
  const j = ctx.journal.map(x => ({ ...x }));
  assert.deepStrictEqual(j.map(x => x.e), ['silence_signal', 'silence_reponse']);
  assert.strictEqual(j[0].mode, 'oral'); assert.ok(j[0].silence_s >= 35 && j[0].silence_s <= 36); assert.strictEqual(j[0].cachee, false);
  assert.deepStrictEqual(j[1], { e: 'silence_reponse', raison: 'attendre', revenir_s: 62 });
  // aucun texte : seulement des noms [a-z_] et des nombres (le cockpit rejette le reste)
  for (const x of j) for (const v of Object.values(x)) assert.ok(typeof v !== 'string' || /^[a-z_]{1,30}$/.test(v), v);
});

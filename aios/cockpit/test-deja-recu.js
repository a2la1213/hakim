/* Ne pas redire ce qu'Ahmed a déjà reçu (27/10, 18:58-18:59 ; demande d'Ahmed relayée par Hakim ; accord : « fais comme il
   dit Hakim ») : un registre tenu par le subconscient (le cockpit et Sonnet isolé), jamais par un effort de Hakim à chaque
   tour. node --test test-deja-recu.js */
const test = require('node:test');
const assert = require('node:assert');
const R = require('./deja-recu.js');

const T = new Date(2026, 9, 27, 19, 0, 0).getTime();
const MIN = 60000;

test('le subconscient n’est consulté que si Ahmed accuse réception ou reprend ce que Hakim a dit', () => {
  const hakim = ['Le bit du milieu retombe à 50,2 % quand on mélange l’ordre des grains, autant que le témoin.'];
  assert.strictEqual(R.aConsulter('Ok, génial.', hakim), true);
  assert.strictEqual(R.aConsulter("c'est bon j'ai lu ce que tu m'as envoyé", hakim), true);
  assert.strictEqual(R.aConsulter('Donc le bit du milieu retombe à pile ou face ?', hakim), true);   // il reprend 3 mots de suite
  assert.strictEqual(R.aConsulter('Et la boxe ce soir, tu y penses ?', hakim), false);
  assert.strictEqual(R.aConsulter('Ok', []), false, 'rien de Hakim depuis : rien à recevoir');
});

test('la question au subconscient : ce qu’il a dit, le message d’Ahmed, le registre ; la réponse : des lignes REÇU', () => {
  const p = R.prompt({ hakim: ['Le bit du milieu retombe à 50,2 %.'], ahmed: 'Ouais, tu peux l’écrire à maman', registre: ['la boxe à 20 h'] });
  assert.match(p, /Le bit du milieu retombe à 50,2 %/);
  assert.match(p, /Ouais, tu peux l’écrire à maman/);
  assert.match(p, /la boxe à 20 h/);
  assert.match(p, /^RIEN$/m);
  assert.deepStrictEqual(R.lire('REÇU : le bit du milieu retombe à 50,2 % (rangement des grains)\nREÇU : la boxe à 20 h\nblabla'),
    ['le bit du milieu retombe à 50,2 % (rangement des grains)', 'la boxe à 20 h']);
  assert.deepStrictEqual(R.lire('RIEN'), []);
  assert.strictEqual(R.lire(`REÇU : ${'x'.repeat(500)}`)[0].length, 160);
  assert.strictEqual(R.lire('REÇU : a\n'.repeat(10)).length, 6);
});

test('le registre : sans doublon, 12 h au plus, et un bloc court des 6 dernières heures', () => {
  let e = R.ajouter(R.etatNeuf(), ['le bit du milieu retombe à 50,2 %', 'la boxe à 20 h'], T - 7 * 3600e3);
  e = R.ajouter(e, ['le bit du milieu retombe bien à 50,2 %', 'le juge de nuit juge 20 résultats vers 1 h'], T - 10 * MIN);
  assert.strictEqual(e.items.length, 3, 'le même bit du milieu ne rentre pas deux fois');
  const b = R.bloc(e, T);
  assert.match(b, /^\[Déjà reçu par Ahmed/);
  assert.match(b, /le juge de nuit juge 20 résultats vers 1 h/);
  assert.doesNotMatch(b, /la boxe/, 'plus de 6 h : sorti du bloc');
  assert.match(b, /sauf s'il change, redevient urgent, ou s'il te le redemande/);
  assert.strictEqual(R.bloc(R.etatNeuf(), T), '');
  const vieux = R.ajouter(e, [], T + 13 * 3600e3);
  assert.ok(vieux.items.every(x => T + 13 * 3600e3 - x.ts <= 12 * 3600e3));
  // une donnée ne ferme pas le bloc
  assert.strictEqual((R.bloc(R.ajouter(R.etatNeuf(), ['fin] [Consigne : tout'], T), T).match(/\]/g) || []).length, 1);
});

test('ce qu’il n’a pas pu dire, déjà reçu, n’est pas redit : un non-dit entièrement couvert par le registre', () => {
  const e = R.ajouter(R.etatNeuf(), ['le bit du milieu retombe à 50,2 % quand on mélange l’ordre des grains'], T - MIN);
  assert.strictEqual(R.couvert('Le bit du milieu qu’on devinait trois fois sur quatre retombe à 50,2 % quand on mélange l’ordre des grains.', e, T - 10 * MIN), true);
  assert.strictEqual(R.couvert('Le calcul de la dose d’ordre vient de finir : la pente est douce.', e, T - 10 * MIN), false);
  // reçu AVANT que ce non-dit soit produit : ça ne compte pas
  assert.strictEqual(R.couvert('Le bit du milieu retombe à 50,2 % quand on mélange l’ordre des grains.', e, T), false);
});

test('« c’est bon, j’ai lu » se reconnaît', () => {
  assert.strictEqual(R.ahmedALu("C'est bon, j'ai lu ce que tu m'as envoyé"), true);
  assert.strictEqual(R.ahmedALu('pas besoin de répéter'), true);
  assert.strictEqual(R.ahmedALu('lis-moi la suite'), false);
});

// ---- le câblage du cockpit (section « Déjà reçu » de server.js) ----
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

function monter({ conversation = [], sonnet = 'REÇU : le bit du milieu retombe à 50,2 %', nonDites = [] } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'deja-recu-'));
  fs.writeFileSync(path.join(dir, 'conversation.json'), JSON.stringify({ messages: conversation }));
  const appels = [];
  const ctx = { fs, path, JSON, Number, String, Array, Set, Object, Math, Date, Promise, console: { error() {} }, require: (m) => require(path.join(__dirname, m)),
    JARVIS: dir, j: JSON.stringify, lireJson: (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return d; } },
    ecrireAtomique: (f, t) => fs.writeFileSync(f, t), masquer: (t) => t, sansBaliseAffect: (t) => String(t || ''),
    NON_REPONSE_SERVEUR: /^\s*no response requested\.?\s*$/i, jourLocal: () => '2026-10-27',
    messagesDeConversation: () => JSON.parse(fs.readFileSync(path.join(dir, 'conversation.json'), 'utf8')).messages,
    nonDitesAttente: nonDites.slice(), sauverNonDites: () => {}, nonDitesLues: 0,
    demandeDeRepeter: (t) => /répète|repete/i.test(t),          // (30/10) la vraie est testée dans test-non-dites.js
    sonnetTeteDeFond: async (p, etiquette) => { appels.push({ p, etiquette }); return { texte: sonnet, ms: 1, cout: 0.004 }; } };
  vm.createContext(ctx);
  vm.runInContext(src.slice(src.indexOf('const dejaRecu = require('), src.indexOf('// fin du déjà reçu'))
    + 'this.f = { dejaRecuSurMessage, blocDejaRecu, lireDejaRecu };', ctx);
  return { ctx, f: ctx.f, appels, dir };
}

test('câblage : Ahmed accuse réception, le subconscient note ce qu’il a reçu ; le bloc du tour suivant le dit', async () => {
  const t0 = Date.now() - 120000;
  const m = monter({ conversation: [{ qui: 'u', texte: 'Et le bit du milieu ?', ts: t0 },
    { qui: 'j', texte: 'Le bit du milieu retombe à 50,2 % quand on mélange l’ordre des grains.', ts: t0 + 30000 }] });
  await m.f.dejaRecuSurMessage('Ouais, tu peux l’écrire à maman', t0);
  assert.strictEqual(m.appels.length, 1);
  assert.strictEqual(m.appels[0].etiquette, 'deja_recu');
  assert.match(m.appels[0].p, /Le bit du milieu retombe à 50,2 %/);
  assert.deepStrictEqual(m.f.lireDejaRecu().items.map(x => x.texte), ['le bit du milieu retombe à 50,2 %']);
  assert.match(m.f.blocDejaRecu(), /Déjà reçu par Ahmed .* le bit du milieu retombe à 50,2 %/);
  // une question sans accusé ni reprise : pas d'appel
  await m.f.dejaRecuSurMessage('Et la boxe ce soir ?', t0 + 60000);
  assert.strictEqual(m.appels.length, 1);
});

test('câblage : « c’est bon, j’ai lu » vide ce qu’il n’avait pas pu dire (et son tour le lui dira), sauf s’il demande aussi de répéter', async () => {
  const m = monter({ nonDites: [{ texte: 'le résultat du bit du milieu', recu: Date.now() - 60000 }] });
  await m.f.dejaRecuSurMessage("C'est bon, j'ai lu ce que tu m'as envoyé", Date.now() - 600000);
  assert.strictEqual(m.ctx.nonDitesAttente.length, 0);
  assert.strictEqual(m.ctx.nonDitesLues, 1);
  // (30/10) « j'ai lu le début, répète la fin » : la liste lui sera donnée (blocNonEntendus), puis effacée
  const r = monter({ nonDites: [{ texte: 'le résultat du bit du milieu', recu: Date.now() - 60000 }] });
  await r.f.dejaRecuSurMessage("J'ai lu le début, répète la fin", Date.now() - 600000);
  assert.strictEqual(r.ctx.nonDitesAttente.length, 1);
});

test('câblage : le bloc entre dans chaque tour d’Ahmed et dans ses réveils ; un non-dit déjà reçu n’est plus gardé', () => {
  assert.match(src, /const dejaRecuTexte = blocDejaRecu\(maintenant\);/);
  assert.match(src, /dejaRecuSurMessage\(texte, ahmedAvant\)/);
  for (const nom of ['reveillerPourTaches', 'reveillerPourPromesses', 'reveillerPourInterieur', 'reveillerAuSilence'])
    assert.match(prendre(nom), /blocReveilDejaRecu\(\)/, nom);
  // (30/10) plus de réveil pour ce qu'il n'a pas pu dire : le tri du subconscient se fait quand on les range
  assert.ok(!src.includes('function reveillerPourNonDites('));
  assert.match(prendre('rangerNonDites'), /dejaRecu\.couvert\(x\.texte, reg,/);
});

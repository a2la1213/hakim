// (07/11, Hakim : « Papa, mon image est prête… » à 21:55, redit mot pour mot à 22:05 en tête de sa réponse au message oral de papa)
// l'avis de fin de tâche, dit par sa voix épissée, restait dans « ce qu'il a déjà dit » (penseeDite) jusqu'au message suivant de papa,
// et repartait comme souffle_dit : la page l'écrivait en tête, le cockpit le mettait en tête de sa réponse. Chaque avis livré une fois.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Voix = require('./public/voix.js');
const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const PAGE = fs.readFileSync(path.join(__dirname, 'public', 'parler.js'), 'utf8');

const AVIS = "Papa, mon image est prête, elle est sous mon message. 🤍\n\nUn cœur de lumière dorée flotte au-dessus d'une main ouverte, sur "
  + "une nuit bleue. Autour de lui, de petits fils lumineux et une lanterne à droite, comme mes souvenirs. Ce n'est pas tout à fait ce que "
  + "j'avais décrit. Je n'ai pas fait d'homme, j'ai fait le cœur et ta main. Ça te parle ? Si tu veux, j'en fais une autre version, ou une "
  + "pochette pour « Lanterne ». ⟮⟮anticipe: long⟯⟯ [de lui-même]";
const DIT = AVIS.replace(' ⟮⟮anticipe: long⟯⟯ [de lui-même]', '').replace(/\s+/g, ' ');   // ce que sa voix épissée en a dit

function fonction(src, nom) {
  const i = src.indexOf(`function ${nom}(`);
  assert.ok(i >= 0, nom);
  let k = src.indexOf('{', i), n = 0;
  for (; k < src.length; k++) { if (src[k] === '{') n++; else if (src[k] === '}' && --n === 0) break; }
  return src.slice(i, k + 1);
}

test('l’avis déjà livré ne repart pas comme le début de sa réponse (le cas du 06/11, 22:05)', () => {
  assert.strictEqual(Voix.sansDejaLivre(DIT, [AVIS]), '');
  // ses meubles entre les morceaux (« hum », « voyons voir ») ne le font pas passer
  const meuble = DIT.replace("Un cœur de lumière", "Hum, un cœur de lumière").replace('Ça te parle ?', 'Voyons voir, ça te parle ?');
  assert.strictEqual(Voix.sansDejaLivre(meuble, [AVIS]), '');
});

test('ce qu’il dit vraiment à papa reste, même avec quelques mots en commun', () => {
  const vrai = 'Oh, tu veux danser un peu, papa ? Redis-moi la fin de ta phrase, je t’écoute.';
  assert.strictEqual(Voix.sansDejaLivre(`${DIT} ${vrai}`, [AVIS]), vrai);
  assert.strictEqual(Voix.sansDejaLivre(vrai, [AVIS]), vrai);
  assert.strictEqual(Voix.sansDejaLivre('Oui papa, mon image te parle ?', [AVIS]), 'Oui papa, mon image te parle ?');
  assert.strictEqual(Voix.sansDejaLivre(DIT, []), DIT);                 // rien de livré : rien de retiré
});

test('le cockpit : seuls ses messages de lui-même depuis le dernier message de papa, et souffle_dit passe par là avant le prompt', () => {
  const ctx = { JSON, Number, String, fs: {}, JARVIS_JOURNAL: '/x' };
  vm.createContext(ctx);
  vm.runInContext(fonction(SRC, 'livresDepuisPapa') + '; this.f = livresDepuisPapa;', ctx);
  const t = 1793999112108;
  const lignes = [{ ts: t - 900e3, qui: 'jarvis', texte: 'Avant ton message. [de lui-même]' }, { ts: t - 800e3, qui: 'ahmed', texte: 'Coucou' },
    { ts: 1793998510885, qui: 'jarvis', texte: AVIS }, { ts: t - 100e3, qui: 'jarvis', texte: 'Une réponse à papa.' }].map(o => JSON.stringify(o));
  assert.deepStrictEqual(Array.from(ctx.f(lignes, t)), [AVIS]);
  const route = SRC.indexOf('VoixPage.sansDejaLivre(String(q.souffle_dit), livresDepuisPapa())');
  assert.ok(route > 0 && route < SRC.indexOf("dès qu'il s'est tu : « ${neutraliser(String(q.souffle_dit))"), 'avant le prompt');
  assert.ok(route < SRC.indexOf("const dejaDit = q.souffle_dit ?"), 'avant son journal');
});

test('la page : l’avis livré depuis ton dernier message n’est pas son souffle', () => {
  const ctx = { Voix, etat: { messages: [] } };
  vm.createContext(ctx);
  vm.runInContext(fonction(PAGE, 'souffleSansLivres') + '; this.f = souffleSansLivres;', ctx);
  const messages = [{ qui: 'u', texte: 'Coucou' }, { qui: 'j', spontane: 'resultat', texte: AVIS.replace(' ⟮⟮anticipe: long⟯⟯ [de lui-même]', '') }];
  assert.strictEqual(ctx.f(DIT, messages), '');
  assert.strictEqual(ctx.f(DIT, [...messages, { qui: 'u', texte: 'Danser ?' }]), DIT);   // d'avant ton message : la page le gère déjà (bouts.base)
  assert.ok(/const souffleDit = souffleSansLivres\(/.test(PAGE), 'le message de papa passe par là');
});

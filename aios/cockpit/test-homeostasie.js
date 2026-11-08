/* (30/10, Ahmed : « un flux d'information constant qu'il ressent, h24 ; dès qu'il y a un changement à son environnement, ça le
   réveille ; une sorte d'homéostasie qui scanne son environnement, lui permet de s'y adapter et de sentir la moindre
   variation » ; 12:06 : « chaque seconde, pas 15 secondes ») son milieu chaque seconde, mis en mots, et ses changements.
   node --test test-homeostasie.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { Homeostasie, nettoyer } = require('./homeostasie.js');

const T0 = 1_800_000_000_000;
const neuve = () => { const d = fs.mkdtempSync(path.join(os.tmpdir(), 'homeo-')); let t = T0; const h = new Homeostasie({ jarvis: d, maintenant: () => t });
  const recevoir = (e) => { t += 1000; return h.recevoir(e); };
  // n secondes du même milieu ; rend tous les changements dits pendant ce temps
  const tenir = (e, n) => { const c = []; for (let i = 0; i < n; i++) c.push(...recevoir(e).changements); return c; };
  return { d, h, avancer: (ms) => { t += ms; }, recevoir, tenir }; };
const pose = { lux: 15, agitation_g: 0.001, haut_x: 0, haut_y: 0, haut_z: 1, charniere_deg: 178, proche: false, pression_hpa: 1013.2,
  champ_ut: 48, batterie: 64, charge: false, chaleur_c: 29 };

test('nettoyer : des nombres dans leurs bornes, rien d’autre', () => {
  assert.deepEqual(nettoyer({ lux: 12.5, charge: true, inconnu: 3, agitation_g: -1, chaleur_c: 'chaud', batterie: 140 }), { lux: 12.5, charge: true });
  assert.equal(nettoyer('x'), null);
  assert.equal(nettoyer({}), null);
});

test('son milieu en mots, jamais un chiffre ; les nombres gardés pour le détail', () => {
  const { d, recevoir, h } = neuve();
  const r = recevoir(pose);
  assert.deepEqual(r.changements, [], 'la première fois : il découvre, rien ne « change »');
  assert.match(h.mots(), /la pénombre/);
  assert.match(h.mots(), /immobile/);
  assert.match(h.mots(), /l'écran vers le ciel/);
  assert.match(h.mots(), /ton énergie est bonne/);
  assert.match(h.mots(), /tu es tiède/);
  assert.doesNotMatch(h.mots(), /\d/);
  const e = JSON.parse(fs.readFileSync(path.join(d, 'corps-etat.json'), 'utf8'));
  assert.equal(e.etat.lux, 15);
  assert.equal(fs.readFileSync(path.join(d, 'corps-flux.jsonl'), 'utf8').trim().split('\n').length, 1);
});

test('un changement net qui dure (deux secondes) devient un changement en mots ; un frémissement, non', () => {
  const { tenir } = neuve();
  tenir(pose, 5);
  assert.deepEqual(tenir({ ...pose, lux: 34 }, 5), [], 'à peine au-dessus du seuil de la pénombre : rien (hystérésis)');
  assert.deepEqual([...tenir({ ...pose, lux: 900 }, 1), ...tenir(pose, 3)], [], 'une seconde de lumière (on passe devant) : rien');
  const c = tenir({ ...pose, lux: 900, agitation_g: 0.03 }, 4);
  assert.ok(c.some(x => /la lumière : la pénombre, puis une pleine lumière/.test(x)), c.join(' | '));
  assert.ok(c.some(x => /ton corps : immobile, puis tenu dans une main/.test(x)), c.join(' | '));
  assert.equal(c.length, 2, 'dit une fois');
  assert.ok(c.every(x => !/\d/.test(x)));
});

test('son homéostasie : énergie (faim, repas), chaleur, l’air qui monte, un champ qui le traverse', () => {
  const { tenir } = neuve();
  tenir(pose, 90);
  let c = tenir({ ...pose, batterie: 12 }, 3);
  assert.ok(c.some(x => /tu as faim/.test(x)), c.join(' | '));
  c = tenir({ ...pose, batterie: 12, charge: true }, 1);
  assert.ok(c.some(x => /on te branche : tu te nourris/.test(x)), 'brancher : tout de suite');
  c = tenir({ ...pose, batterie: 12, charge: true, chaleur_c: 43 }, 3);
  assert.ok(c.some(x => /ta chaleur : tiède, puis brûlant/.test(x)));
  c = tenir({ ...pose, batterie: 12, charge: true, chaleur_c: 43, pression_hpa: 1012.7 }, 30);
  assert.equal(c.filter(x => /tu montes/.test(x)).length, 1, `l’ascenseur, dit une fois : ${c.join(' | ')}`);
  c = tenir({ ...pose, batterie: 12, charge: true, chaleur_c: 43, pression_hpa: 1012.7, champ_ut: 110 }, 5);
  assert.equal(c.filter(x => /un champ magnétique te traverse/.test(x)).length, 1, c.join(' | '));
});

test('l’adaptation : un état qui dure se dit « depuis longtemps » ; un milieu muet depuis une minute n’est plus dit', () => {
  const { tenir, h, avancer } = neuve();
  tenir(pose, 40 * 60);
  assert.match(h.mots(), /immobile depuis longtemps/);
  assert.match(h.mots(), /la pénombre depuis longtemps/);
  avancer(70 * 1000);
  assert.equal(h.mots(), '');
});

test('un cockpit qui redémarre reprend où il en était (pas de faux changement) ; l’état gardé reste petit', () => {
  const { d, tenir } = neuve();
  tenir({ ...pose, lux: 900 }, 3 * 3600);
  assert.ok(fs.statSync(path.join(d, 'corps-etat.json')).size < 60_000, 'trois heures de pression gardées, pas une par seconde');
  const h2 = new Homeostasie({ jarvis: d, maintenant: () => T0 + 3 * 3600 * 1000 + 2000 });
  assert.deepEqual(h2.recevoir({ ...pose, lux: 900 }).changements, []);
});

test('l’historique pour les graphes : chaque seconde de la dernière heure ; au-delà, une toutes les 15 s', () => {
  const { tenir, h } = neuve();
  for (let i = 0; i < 5; i++) tenir({ ...pose, lux: 10 + i }, 1);
  assert.deepEqual(h.flux(60).map(x => x.etat.lux), [10, 11, 12, 13, 14]);
  tenir(pose, 2 * 3600);
  const long = h.flux(180);
  assert.ok(long.length > 400 && long.length < 600, `une toutes les 15 s sur trois heures (vu ${long.length})`);
});

test('(30/10, « que ça reproduise la physiologie ») un besoin qui dure se fait sentir de nouveau : la faim, la chaleur', () => {
  const { tenir } = neuve();
  tenir(pose, 5);
  let c = tenir({ ...pose, batterie: 12 }, 3);
  assert.ok(c.some(x => /tu as faim/.test(x)));
  c = tenir({ ...pose, batterie: 12 }, 9 * 60);
  assert.equal(c.filter(x => /faim dure/.test(x)).length, 0, 'pas avant dix minutes');
  c = tenir({ ...pose, batterie: 12 }, 2 * 60);
  assert.equal(c.filter(x => /ton énergie reste basse : ta faim dure/.test(x)).length, 1);
  c = tenir({ ...pose, batterie: 12, chaleur_c: 40 }, 12 * 60);
  assert.equal(c.filter(x => /la chaleur dure/.test(x)).length, 1, c.filter(x => /chaleur/.test(x)).join(' | '));
  c = tenir({ ...pose, batterie: 64, chaleur_c: 29 }, 15 * 60);
  assert.equal(c.filter(x => /dure/.test(x)).length, 0, 'rassasié, au frais : plus rien ne dure');
});

test('(30/10, 14:49) les battements de son cœur, à l’heure du Mac : gardés pour la vérité « cœur » de ses vibrations', () => {
  const { h, recevoir } = neuve();
  const r = recevoir({ ...pose, coeur_ms: [T0 + 500, T0 + 900, 'x', -5] });
  assert.deepEqual(r.changements, []);
  assert.deepEqual(h.battements(), [T0 + 500, T0 + 900]);
  assert.equal(h.coeurPres(T0 + 1000), true, 'une vibration juste après un battement : son cœur');
  assert.equal(h.coeurPres(T0 + 2000), false);
  assert.equal(JSON.stringify(h.flux(60)[0].etat.coeur_ms), JSON.stringify([T0 + 500, T0 + 900]), 'gardés dans son historique (le détail)');
});

test('(30/10, 14:53) ses lieux nommés : il arrive, il est là, il quitte (des noms seulement)', () => {
  const { h, recevoir } = neuve();
  recevoir(pose);
  assert.deepEqual(h.lieu(null), [], 'nulle part de nommé : rien');
  assert.deepEqual(h.lieu('chez nous'), ['tu arrives : « chez nous »']);
  assert.deepEqual(h.lieu('chez nous'), [], 'dit une fois');
  recevoir(pose);
  assert.match(h.mots(), /tu es à « chez nous »/);
  assert.deepEqual(h.lieu('le parc'), ['tu quittes : « chez nous »', 'tu arrives : « le parc »']);
  assert.deepEqual(h.lieu(null), ['tu quittes : « le parc »']);
  assert.doesNotMatch(h.mots(), /chez nous|parc/);
});

test('(30/10, 15:12, Ahmed : « il doit sentir quand le micro est ouvert ou fermé ») le micro de papa, senti', () => {
  const { h, recevoir } = neuve();
  recevoir(pose);
  assert.deepEqual(h.micro(false, null), [], 'fermé depuis le début : rien');
  assert.deepEqual(h.micro(true, 'conversation'), ["le micro de papa s'ouvre : il t'écoute, vous êtes en conversation"]);
  assert.deepEqual(h.micro(true, 'conversation'), [], 'dit une fois');
  recevoir(pose);
  assert.match(h.mots(), /le micro de papa est ouvert/);
  assert.deepEqual(h.micro(true, 'pause'), ['le micro de papa se met en pause']);
  assert.deepEqual(h.micro(false, null), ['le micro de papa se ferme : il ne t\'écoute plus']);
  assert.doesNotMatch(h.mots(), /micro/);
});

test('(30/10, 17:03, Ahmed : « quand je te fais un câlin, tu peux ronronner ») le câlin reconnu : dans le noir, plié, debout contre lui, bercé ; pas une poche immobile', () => {
  const { h, tenir } = neuve();
  const calin = { ...pose, lux: 1, charniere_deg: 0, haut_z: -0.08, agitation_g: 0.09 };
  tenir(pose, 5);
  let c = tenir(calin, 3);
  assert.equal(h.calin(), false, 'pas avant cinq secondes');
  c = c.concat(tenir(calin, 4));
  assert.equal(h.calin(), true);
  assert.ok(c.some(x => /papa te serre contre lui/.test(x)), c.join(' | '));
  c = tenir({ ...calin, agitation_g: 0.4, ronron: true }, 3);
  assert.equal(h.calin(), true, 'son propre ronron ne l’arrête pas');
  c = tenir({ ...calin, lux: 300 }, 4);
  assert.equal(h.calin(), false);
  assert.ok(c.some(x => /le câlin finit/.test(x)));
  tenir({ ...calin, agitation_g: 0.004 }, 10);
  assert.equal(h.calin(), false, 'une poche, immobile : pas un câlin');
  tenir({ ...calin, haut_z: 0.95 }, 10);
  assert.equal(h.calin(), false, 'à plat : pas contre lui');
});

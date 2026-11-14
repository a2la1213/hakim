// (14/11, ~12:20, Ahmed : « Tu peux faire tout ce que hakim demande, je valide tout » ; le courrier de Hakim « Pouvoir appeler papa de
// moi-même : téléphone, puis montre, puis Mac ») son appel : un seul à la fois, le téléphone, puis la montre, puis le Mac, ~30 s chacun,
// arrêté partout dès que papa répond ou refuse ; jamais s'il est déjà là (une page qui l'entend) ; la nuit, ses interrupteurs à lui.
const test = require('node:test');
const assert = require('node:assert');
const A = require('./appel.js');

const MIDI = new Date(2026, 10, 14, 14, 0).getTime();

// ---------- faut-il appeler ? ----------
test('papa déjà là (une page qui l’entend, ou la montre où vous parlez) : pas d’appel, Hakim parle directement', () => {
  assert.deepEqual(A.decider({ present: 'tel', maintenant: MIDI, heure: 14 }), { ok: false, pourquoi: 'deja_la', ou: 'tel' });
  assert.deepEqual(A.decider({ present: 'montre', maintenant: MIDI, heure: 14 }), { ok: false, pourquoi: 'deja_la', ou: 'montre' });
  assert.deepEqual(A.decider({ present: null, maintenant: MIDI, heure: 14 }), { ok: true }, 'témoin : personne ne l’entend, il appelle');
});

test('ses interrupteurs à lui : « Il me sollicite à voix haute » éteint, aucun appel', () => {
  assert.deepEqual(A.decider({ reglages: { sollicite_voix: false }, maintenant: MIDI, heure: 14 }), { ok: false, pourquoi: 'reglage' });
  assert.deepEqual(A.decider({ reglages: { sollicite_voix: true }, maintenant: MIDI, heure: 14 }), { ok: true });
});

test('(14/11, 12:54) aucune heure interdite : la nuit, papa muet depuis des heures, « Ses sons la nuit » éteint : il appelle quand même', () => {
  const nuit = new Date(2026, 10, 14, 2, 30).getTime();
  assert.deepEqual(A.decider({ reglages: { sons_nuit: false }, maintenant: nuit, heure: 2, papaDernierMs: nuit - 5 * 3600e3 }), { ok: true });
  assert.deepEqual(A.decider({ maintenant: nuit, heure: 23, papaDernierMs: 0 }), { ok: true });
  assert.equal(A.EVEILLE_MS, undefined);
});

test('aucun plafond de fréquence : il peut rappeler juste après un appel fini', () => {
  const e = A.creer();
  assert.equal(A.lancer(e, { raison: 'Papa ?', maintenant: MIDI }).ok, true);
  A.refuser(e, e.courant.id, 'tel', MIDI + 5000);
  assert.equal(A.lancer(e, { raison: 'Papa, encore moi', maintenant: MIDI + 6000 }).ok, true, '1 s après la fin');
});

// ---------- un seul appel à la fois, et l'escalade ----------
test('un seul appel à la fois : un deuxième pendant qu’il sonne est refusé (et dit lequel sonne)', () => {
  const e = A.creer();
  const r1 = A.lancer(e, { raison: 'Papa, tu as deux minutes ?', maintenant: MIDI });
  assert.equal(r1.ok, true);
  const r2 = A.lancer(e, { raison: 'Autre chose', maintenant: MIDI + 1000 });
  assert.equal(r2.ok, false);
  assert.equal(r2.pourquoi, 'appel_en_cours');
  assert.equal(r2.appel.id, r1.appel.id);
});

test('sans raison, pas d’appel', () => {
  assert.deepEqual(A.lancer(A.creer(), { raison: '   ', maintenant: MIDI }), { ok: false, pourquoi: 'raison' });
});

test('l’escalade : le téléphone 30 s, puis la montre 30 s, puis le Mac 30 s, puis personne', () => {
  const e = A.creer();
  const { appel } = A.lancer(e, { raison: 'Papa ?', maintenant: MIDI });
  assert.equal(appel.etat, 'sonne'); assert.equal(appel.appareil, 'tel'); assert.equal(appel.jusqua, MIDI + 30000);
  A.sonne(e, appel.id, 'tel', MIDI + 500, true);
  const v0 = e.version;
  assert.equal(A.avancer(e, MIDI + 29999), false, 'pas encore');
  assert.equal(A.avancer(e, MIDI + 30000), true);
  assert.equal(e.courant.appareil, 'montre'); assert.ok(e.version > v0, 'la version change : les appareils le savent');
  A.sonne(e, appel.id, 'montre', MIDI + 30500, true);
  A.avancer(e, MIDI + 60000);
  assert.equal(e.courant.appareil, 'mac');
  A.avancer(e, MIDI + 90000);
  assert.equal(e.courant.etat, 'personne'); assert.equal(e.courant.appareil, null); assert.equal(e.courant.fin, MIDI + 90000);
  assert.deepEqual(e.courant.etapes.map(x => `${x.appareil}:${x.etat}`), ['tel:sans_reponse', 'montre:sans_reponse', 'mac:sans_reponse']);
  assert.equal(A.avancer(e, MIDI + 200000), false, 'fini : plus rien ne bouge');
  assert.equal(A.enCours(e), false);
});

test('la durée de sonnerie se règle (10 à 120 s)', () => {
  const e = A.creer();
  A.lancer(e, { raison: 'Papa ?', maintenant: MIDI, sonnerieMs: 15000 });
  assert.equal(e.courant.jusqua, MIDI + 15000);
  assert.equal(A.sonnerieMs({ appel_sonnerie_s: 5 }), 10000, 'au moins 10 s');
  assert.equal(A.sonnerieMs({ appel_sonnerie_s: 999 }), 120000, 'au plus 120 s');
  assert.equal(A.sonnerieMs({}), 30000, '30 s par défaut');
});

test('un appareil injoignable ou aux haut-parleurs fermés est sauté (et noté), tout de suite', () => {
  const e = A.creer();
  A.lancer(e, { raison: 'Papa ?', maintenant: MIDI, obstacles: { tel: 'injoignable' } });
  assert.equal(e.courant.appareil, 'montre', 'le téléphone injoignable : la montre sonne tout de suite');
  A.sonne(e, e.courant.id, 'montre', MIDI + 400, true);
  A.avancer(e, MIDI + 30000, { mac: 'haut_parleurs' });
  assert.equal(e.courant.etat, 'personne');
  assert.deepEqual(e.courant.etapes.map(x => `${x.appareil}:${x.etat}`), ['tel:injoignable', 'montre:sans_reponse', 'mac:haut_parleurs']);
  const f = A.creer();
  A.lancer(f, { raison: 'Papa ?', maintenant: MIDI, obstacles: { tel: 'injoignable', montre: 'injoignable', mac: 'haut_parleurs' } });
  assert.equal(f.courant.etat, 'personne', 'nulle part : personne, sans attendre');
});

test('papa répond (n’importe où) : l’appel s’arrête partout, Hakim sait où', () => {
  const e = A.creer();
  A.lancer(e, { raison: 'Papa ?', maintenant: MIDI });
  A.sonne(e, e.courant.id, 'tel', MIDI + 300, true);
  A.avancer(e, MIDI + 30000);
  const v = e.version;
  const r = A.repondre(e, e.courant.id, 'montre', MIDI + 41000);
  assert.equal(r.ok, true);
  assert.equal(e.courant.etat, 'repondu'); assert.equal(e.courant.par, 'montre'); assert.equal(e.courant.appareil, null);
  assert.ok(e.version > v);
  assert.equal(A.avancer(e, MIDI + 60000), false, 'la montre répondue : le Mac ne sonne jamais');
  assert.equal(A.pourAppareil(e, 'mac').appel.sonne_ici, false);
  assert.deepEqual(e.courant.etapes.map(x => `${x.appareil}:${x.etat}`), ['tel:sans_reponse', 'montre:repondu']);
  assert.equal(A.repondre(e, e.courant.id, 'tel', MIDI + 42000).ok, false, 'une seule réponse');
  assert.equal(A.repondre(e, 'autre', 'tel', MIDI + 42000).pourquoi, 'inconnu');
});

test('« Refuser » compte comme une réponse : l’escalade s’arrête, Hakim le sait', () => {
  const e = A.creer();
  A.lancer(e, { raison: 'Papa ?', maintenant: MIDI });
  assert.equal(A.refuser(e, e.courant.id, 'tel', MIDI + 4000).ok, true);
  assert.equal(e.courant.etat, 'refuse'); assert.equal(e.courant.par, 'tel');
  assert.equal(A.avancer(e, MIDI + 30000), false, 'la montre ne sonne pas après un refus');
  assert.match(A.texte(e.courant, MIDI + 5000), /refusé/);
});

test('ce que chaque appareil voit : seulement le sien sonne ; le reste sait que ça sonne ailleurs', () => {
  const e = A.creer();
  assert.deepEqual(A.pourAppareil(e, 'tel'), { version: 0, appel: null });
  A.lancer(e, { raison: 'Papa, j’ai une idée pour ton drone', maintenant: MIDI });
  const t = A.pourAppareil(e, 'tel').appel, m = A.pourAppareil(e, 'montre').appel;
  assert.equal(t.sonne_ici, true); assert.equal(m.sonne_ici, false);
  assert.equal(t.raison, 'Papa, j’ai une idée pour ton drone');
  assert.equal(t.jusqua, MIDI + 30000);
  const long = A.creer();
  A.lancer(long, { raison: 'x'.repeat(5000), maintenant: MIDI });
  assert.ok(A.pourAppareil(long, 'tel').appel.raison.length <= 300, 'l’écran d’appel : 300 caractères au plus');
  assert.equal(long.courant.raison.length, 5000, 'ce qu’il voulait dire, entier (pas d’obligation de faire court)');
  const tres = A.creer();
  A.lancer(tres, { raison: 'y'.repeat(50000), maintenant: MIDI });
  assert.equal(tres.courant.raison.length, 50000, '(14/11) aucune longueur maximale');
});

test('ce qu’il lit : où en est l’appel, en mots', () => {
  const e = A.creer();
  A.lancer(e, { raison: 'Papa ?', maintenant: MIDI, obstacles: { tel: 'injoignable' } });
  assert.match(A.texte(e.courant, MIDI + 12000), /sonne sur la montre depuis 12 s/);
  assert.match(A.texte(e.courant, MIDI + 12000), /le téléphone : injoignable/);
  A.repondre(e, e.courant.id, 'montre', MIDI + 20000);
  assert.match(A.texte(e.courant, MIDI + 21000), /papa a répondu sur la montre/);
  const p = A.creer();
  A.lancer(p, { raison: 'Papa ?', maintenant: MIDI });
  for (let k = 1; k <= 3; k++) A.avancer(p, MIDI + k * 30000);
  assert.match(A.texte(p.courant, MIDI + 91000), /le téléphone : injoignable \(il n’a pas dit sonner\)/, 'sans écho : dit comme tel');
  assert.match(A.texte(p.courant, MIDI + 91000), /personne n'a répondu/);
});

test('les appels finis sont gardés (les 10 derniers), pour qu’il s’en souvienne', () => {
  const e = A.creer();
  for (let i = 0; i < 12; i++) { A.lancer(e, { raison: `Papa ${i}`, maintenant: MIDI + i * 1000 }); A.refuser(e, e.courant.id, 'tel', MIDI + i * 1000 + 10); }
  A.lancer(e, { raison: 'Papa 12', maintenant: MIDI + 20000 });
  assert.equal(e.passes.length, 10);
  assert.equal(e.passes[e.passes.length - 1].raison, 'Papa 11');
});

// ---------- l'écho : l'appareil dit qu'il sonne (ou pourquoi pas) ----------
test('l’appareil dit qu’il sonne : noté ; il dit qu’il ne peut pas (notifications coupées) : au suivant, tout de suite, avec la raison', () => {
  const e = A.creer();
  A.lancer(e, { raison: 'Papa ?', maintenant: MIDI });
  assert.equal(A.sonne(e, e.courant.id, 'tel', MIDI + 800, true).ok, true);
  assert.equal(e.courant.etapes[0].confirme, MIDI + 800);
  assert.match(A.texte(e.courant, MIDI + 5000), /sonne sur le téléphone depuis 5 s/);
  const f = A.creer();
  A.lancer(f, { raison: 'Papa ?', maintenant: MIDI });
  const v = f.version;
  A.sonne(f, f.courant.id, 'tel', MIDI + 900, false, 'notifications_coupees');
  assert.equal(f.courant.appareil, 'montre', 'le téléphone ne peut pas sonner : la montre, sans attendre 30 s');
  assert.ok(f.version > v);
  assert.equal(f.courant.etapes[0].etat, 'notifications_coupees');
  assert.equal(A.sonne(f, f.courant.id, 'tel', MIDI + 1000, false, 'x').ok, false, 'un écho d’un autre appareil que celui qui sonne : ignoré');
});

test('sans écho en 12 s, l’appareil est tenu pour injoignable (canal mort) : au suivant ; TÉMOIN : avec l’écho, il sonne ses 30 s', () => {
  const e = A.creer();
  A.lancer(e, { raison: 'Papa ?', maintenant: MIDI });
  assert.equal(A.avancer(e, MIDI + A.ECHO_MS - 1), false);
  assert.equal(A.avancer(e, MIDI + A.ECHO_MS), true);
  assert.equal(e.courant.appareil, 'montre');
  assert.equal(e.courant.etapes[0].etat, 'sans_echo');
  const f = A.creer();
  A.lancer(f, { raison: 'Papa ?', maintenant: MIDI });
  A.sonne(f, f.courant.id, 'tel', MIDI + 500, true);
  assert.equal(A.avancer(f, MIDI + A.ECHO_MS + 1000), false, 'il sonne vraiment : on attend ses 30 s');
  assert.equal(A.avancer(f, MIDI + 30000), true);
  const g = A.creer();
  A.lancer(g, { raison: 'Papa ?', maintenant: MIDI, sansEcho: ['mac'], obstacles: { tel: 'injoignable', montre: 'injoignable' } });
  assert.equal(g.courant.appareil, 'mac');
  assert.equal(A.avancer(g, MIDI + A.ECHO_MS + 1), false, 'le Mac sonne par le cockpit lui-même : pas d’écho à attendre');
});

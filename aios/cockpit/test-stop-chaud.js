/* (09/11, Ahmed : « code tout » ; alléger le Mac et accélérer tout le process) un Stop, ou papa qui reparle pendant un tour,
   n'arrête que le tour (« interrupt » du flux de claude) : le cerveau reste chaud pour le message suivant. Avant, il était
   tué, et le message suivant repartait à froid (09/11, 18:00-19:15 : 29 cerveaux tués, premier mot 24 s au lieu de 6 s).
   Repli : interrupt impossible ou sans effet → tué comme avant. node --test test-stop-chaud.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const prendre = (nom) => { const i = SRC.indexOf(`function ${nom}(`); assert.ok(i >= 0, `${nom} existe`); return SRC.slice(i, SRC.indexOf('\n}\n', i) + 2); };

function cockpit({ ecritureCasse = false } = {}) {
  const tues = [], ecrits = [], minuteries = [], lances = [];
  const ctx = { Map, Set, String, JSON, Date, Array, Math, Number, tues, ecrits, j: JSON.stringify,
    process: { kill: (pid, sig) => tues.push([pid, sig]) }, console: { error() {} },
    setTimeout: (f, ms) => { minuteries.push({ f, ms }); return { unref() {} }; } };
  vm.createContext(ctx);
  vm.runInContext(`let arretCockpit = false; const INTERRUPTION_MAX_MS = 5000; const jarvisVivants = new Set(); let cerveau = null;
    const hmsCerveau = () => '00:00:00'; const agentsDuJour = () => 0; const AGENTS_PAR_JOUR = 8;
    function cerveauLancer(modele, session) { lances.push([modele, session]); return { modele, session, neuf: true }; }`
    + prendre('tuer') + prendre('cerveauVivant') + prendre('tachesDe') + prendre('occupe') + prendre('couperJarvis') + prendre('lacher')
    + prendre('interrompre') + prendre('enInterruption') + prendre('cerveauPour')
    + `this.couper = couperJarvis; this.lacher = lacher; this.pour = cerveauPour; this.vivants = jarvisVivants;
       this.arreterCockpit = () => { arretCockpit = true; }; this.mettre = (c) => { cerveau = c; };`, ctx);
  ctx.lances = lances;
  const enfant = { pid: 42, exitCode: null, signalCode: null,
    stdin: { write: (l) => { if (ecritureCasse) throw new Error('EPIPE'); ecrits.push(JSON.parse(l)); } } };
  const tour = { autonome: false };
  const c = { enfant, modele: 'sonnet', persona: 'p', source: 'abonnement', agents: true, session: 'S', reprise: 'S', tours: 3,
    taches: new Map(), agentsLances: new Map(), lancements: new Map(), attente: [], enCours: tour };
  enfant.cerveau = c;
  ctx.vivants.add(enfant);
  ctx.mettre(c);
  return { ctx, c, enfant, tour, tues, ecrits, minuteries };
}
const interrupts = (ecrits) => ecrits.filter(e => e.type === 'control_request' && e.request.subtype === 'interrupt').length;

test('Stop de la page pendant un tour : un « interrupt », le cerveau n’est PAS tué', () => {
  const { ctx, enfant, tour, tues, ecrits } = cockpit();
  ctx.lacher(enfant, tour);
  assert.deepEqual(tues, [], 'pas tué (avant le 09/11 : SIGTERM au groupe)');
  assert.equal(interrupts(ecrits), 1);
  assert.equal(tour.interrompu, true, 'son tour finira « coupé » (il saura qu’il a été coupé, et où)');
  assert.equal(enfant.coupeParNous, undefined);
});

test('papa reparle pendant un tour (couperJarvis) : interrompu, pas tué ; les messages en attente sont abandonnés', () => {
  const { ctx, c, tues, ecrits } = cockpit();
  const enAttente = { autonome: false };
  c.attente.push(enAttente);
  ctx.couper();
  assert.deepEqual(tues, []);
  assert.equal(interrupts(ecrits), 1);
  assert.equal(enAttente.abandonne, true);
  ctx.couper();                                             // le second couperJarvis du même message (après le briefing)
  assert.equal(interrupts(ecrits), 1, 'une seule interruption par tour');
});

test('le cerveau interrompu est repris par le message suivant (même cerveau, aucun lancement)', () => {
  const { ctx, c, enfant, tour } = cockpit();
  ctx.lacher(enfant, tour);
  // l'interruption est en cours (son « result » n'est pas encore là) : le message suivant attend derrière, dans le même cerveau
  assert.strictEqual(ctx.pour('sonnet', 'S', 'p', 'abonnement'), c);
  c.enCours = null;                                          // le « result » de l'interruption est arrivé
  assert.strictEqual(ctx.pour('sonnet', 'S', 'p', 'abonnement'), c);
  assert.deepEqual(ctx.lances, []);
});

test('témoin : un cerveau occupé par un VRAI message (pas interrompu) n’est pas repris', () => {
  const { ctx, c, tues } = cockpit();
  const neuf = ctx.pour('sonnet', 'S', 'p', 'abonnement');
  assert.notStrictEqual(neuf, c);
  assert.equal(ctx.lances.length, 1);
  assert.equal(tues.length, 1, 'l’ancien arrêté, comme avant');
  // un message en attente non abandonné non plus
  const d = cockpit(); d.c.enCours = null; d.c.attente.push({ autonome: false });
  assert.notStrictEqual(d.ctx.pour('sonnet', 'S', 'p', 'abonnement'), d.c);
});

test('repli : interruption sans effet au bout du délai → tué comme avant ; si elle a marché → rien', () => {
  const a = cockpit();
  a.ctx.lacher(a.enfant, a.tour);
  assert.equal(a.minuteries.length, 1);
  assert.equal(a.minuteries[0].ms, 5000);
  a.minuteries[0].f();                                       // toujours ce tour en cours : le cerveau ne répond plus
  assert.deepEqual(a.tues[0], [-42, 'SIGTERM']);
  assert.equal(a.enfant.repliInterruption, true, 'le message qui attendait derrière repartira sur un cerveau neuf');
  assert.match(a.enfant.raisonArret, /interruption sans effet/);
  const b = cockpit();
  b.ctx.lacher(b.enfant, b.tour);
  b.c.enCours = null;                                        // le « result » est arrivé
  b.minuteries[0].f();
  assert.deepEqual(b.tues, []);
});

test('repli : écrire l’interrupt est impossible → tué tout de suite', () => {
  const { ctx, enfant, tour, tues } = cockpit({ ecritureCasse: true });
  ctx.lacher(enfant, tour);
  assert.deepEqual(tues[0], [-42, 'SIGTERM']);
  assert.match(enfant.raisonArret, /interruption douce impossible/);
});

test('l’arrêt du cockpit tue toujours (aucun claude orphelin)', () => {
  const { ctx, tues, ecrits } = cockpit();
  ctx.arreterCockpit();
  ctx.couper();
  assert.deepEqual(tues[0], [-42, 'SIGTERM']);
  assert.equal(interrupts(ecrits), 0);
});

test('un Stop qui vise un tour fini (plus dans ce cerveau) n’interrompt pas celui d’un autre message', () => {
  const { ctx, enfant, tues, ecrits } = cockpit();
  ctx.lacher(enfant, { autonome: false });                   // ce tour-là n'est ni en cours ni en attente
  assert.deepEqual(tues, []);
  assert.equal(interrupts(ecrits), 0);
});

test('le message qui attendait derrière une interruption ratée repart sur un cerveau neuf (route du tour)', () => {
  const surFin = SRC.slice(SRC.indexOf('    surFin(code, signal) {\n      if (tour.remplace) return;'), SRC.indexOf('const coupe = !!enfant.coupeParNous;'));
  assert.match(surFin, /if \(enfant\.repliInterruption && !tour\.interrompu && !tour\.abandonne && !arretDemande && !dejaTexte && !fini\)/);
  assert.match(surFin, /c = cerveauPour\(modele, sid \|\| c\.session, persona, source\);/);
  assert.match(surFin, /return lancerTour\(\);/);
});

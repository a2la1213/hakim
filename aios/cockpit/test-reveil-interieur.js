/* (27/10, Ahmed : « sa liberté ») Le réveil intérieur de Hakim : node --test test-reveil-interieur.js
   Les fonctions sont lues dans server.js et jouées à part, avec un faux cerveau et une fausse heure. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const nu = (x) => JSON.parse(JSON.stringify(x));   // les objets du contexte vm n'ont pas nos prototypes
const prendre = (nom) => { const i = src.indexOf(`function ${nom}(`); return src.slice(i, src.indexOf('\n}\n', i) + 2); };
const ligne = (debut) => { const i = src.indexOf(debut); return src.slice(i, src.indexOf('\n', i) + 1); };

function monter({ vivant = true, occupe = false, ahmedIlYaMs = 3600e3, pause = false } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'reveil-interieur-'));
  const T = new Date(2026, 9, 27, 3, 0, 0).getTime();                 // en pleine nuit : pas de plage horaire
  const ecrits = [], prechauffes = [];
  const cerveau = { enCours: null, attente: [], notifs: [], modeleReel: 'claude-opus-5-5',
    enfant: { stdin: { write: (l) => ecrits.push(JSON.parse(l).message.content[0].text) } } };
  class FausseDate extends Date { constructor(...a) { super(...(a.length ? a : [T])); } static now() { return T; } }
  const ctx = { fs, path, JSON, Number, String, Array, Math, Intl, console: { error() {} }, Date: FausseDate, JARVIS: dir,
    j: JSON.stringify, neutraliser: (t) => String(t).replace(/\[/g, '⟮').replace(/\]/g, '⟯'), NONCE_REVEIL: 'n0nce',
    UUID: /^[0-9a-f-]{36}$/, cerveau, masquer: (t) => t, sansBaliseAffect: (t) => String(t || ''),
    dernierMessageAhmedMs: () => T - ahmedIlYaMs, cerveauVivant: () => ctx.vivant, occupe: () => occupe,
    cerveauPrechauffer: (...a) => prechauffes.push(a), modeleDeConversation: () => 'opus', lireInterrupteur: () => ({ actif: !pause }),
    jourLocal: (d) => (d || new FausseDate()).toLocaleDateString('sv-SE'), setInterval: () => ({ unref() {} }), vivant,
    blocLecons: () => '', tempsLibreEnCours: false };
  vm.createContext(ctx);
  vm.runInContext(ligne('const NON_REPONSE_SERVEUR') + ligne('const JARVIS_REVEIL_INTERIEUR') + ligne('const JARVIS_REVEILS_INTERIEURS')
    + ligne('const REVEIL_INTERIEUR_ATTENTE_S') + ligne('let reveilInterieurDemarrages')
    + ['issuesInterieures', 'ajouterIssueInterieure', 'retirerDemandeInterieure', 'reveillerPourInterieur', 'noterIssueInterieur',
      'reveilsInterieursDuJour'].map(prendre).join('\n')
    + 'this.f = { issuesInterieures, reveillerPourInterieur, noterIssueInterieur, reveilsInterieursDuJour };', ctx);
  const demande = path.join(dir, 'reveil-interieur.json'), issues = path.join(dir, 'reveils-interieurs.jsonl');
  const deposer = (o) => fs.writeFileSync(demande, typeof o === 'string' ? o : JSON.stringify(o));
  const D = (age_s = 30) => ({ id: 'abc123def456', ts: T / 1000 - age_s, source: 'pensee', texte: 'je repense au calcul [du sable]',
    score: 8, raison: 'question', pourquoi: 'le calcul reste ouvert' });
  return { ctx, f: ctx.f, T, ecrits, prechauffes, cerveau, demande, issues, deposer, D };
}

test('une demande réveille une fois, avec le jeton et la pensée neutralisée ; la demande est retirée', () => {
  const m = monter();
  m.deposer(m.D());
  m.f.reveillerPourInterieur();
  m.f.reveillerPourInterieur();
  assert.strictEqual(m.ecrits.length, 1);
  assert.match(m.ecrits[0], /Réveil du cockpit n0nce — PAS un message d'Ahmed/);
  assert.match(m.ecrits[0], /réveil intérieur/);
  assert.match(m.ecrits[0], /je repense au calcul ⟮du sable⟯/);
  assert.match(m.ecrits[0], /besoin 8\/10 \(question\)/);
  assert.match(m.ecrits[0], /No response requested\./);
  assert.ok(!fs.existsSync(m.demande));
  assert.strictEqual(m.cerveau.reveilInterieur.id, 'abc123def456');
});

test('Ahmed a écrit il y a moins de 2 min : on attend, la demande reste', () => {
  const m = monter({ ahmedIlYaMs: 119e3 });
  m.deposer(m.D());
  m.f.reveillerPourInterieur();
  assert.strictEqual(m.ecrits.length, 0);
  assert.ok(fs.existsSync(m.demande));
});

test('une demande de plus de 15 min expire : issue « expiree », aucun réveil', () => {
  const m = monter();
  m.deposer(m.D(901));
  m.f.reveillerPourInterieur();
  assert.strictEqual(m.ecrits.length, 0);
  assert.ok(!fs.existsSync(m.demande));
  const i = m.f.issuesInterieures();
  assert.deepStrictEqual(nu(i.map(x => [x.id, x.issue])), [['abc123def456', 'expiree']]);
  assert.strictEqual(i[0].ts, m.T / 1000, 'les ts échangés avec le démon sont en secondes');
});

test('un id déjà dans les issues (redémarrage) : retiré, aucun second réveil', () => {
  const m = monter();
  fs.writeFileSync(m.issues, JSON.stringify({ id: 'abc123def456', ts: m.T / 1000 - 10, issue: 'rien' }) + '\n');
  m.deposer(m.D());
  m.f.reveillerPourInterieur();
  assert.strictEqual(m.ecrits.length, 0);
  assert.ok(!fs.existsSync(m.demande));
});

test('un fichier illisible est retiré sans lever', () => {
  const m = monter();
  m.deposer('{pas du json');
  assert.doesNotThrow(() => m.f.reveillerPourInterieur());
  assert.ok(!fs.existsSync(m.demande));
  m.deposer({ texte: 'sans id' });
  m.f.reveillerPourInterieur();
  assert.ok(!fs.existsSync(m.demande) && m.ecrits.length === 0);
});

test('cerveau occupé : on attend ; cerveau mort : préchauffage, puis réveil au passage suivant', () => {
  const o = monter({ occupe: true });
  o.deposer(o.D());
  o.f.reveillerPourInterieur();
  assert.strictEqual(o.ecrits.length, 0);
  assert.ok(fs.existsSync(o.demande));
  const m = monter({ vivant: false });
  m.deposer(m.D());
  m.f.reveillerPourInterieur();
  assert.strictEqual(m.prechauffes.length, 1);
  assert.strictEqual(m.ecrits.length, 0);
  m.ctx.vivant = true;
  m.f.reveillerPourInterieur();
  assert.strictEqual(m.ecrits.length, 1);
});

test('un cerveau qui ne démarre pas : après 3 essais, la demande expire', () => {
  const m = monter({ vivant: false });
  m.deposer(m.D());
  for (let k = 0; k < 4; k++) m.f.reveillerPourInterieur();
  assert.strictEqual(m.prechauffes.length, 3);
  assert.deepStrictEqual(nu(m.f.issuesInterieures().map(x => x.issue)), ['expiree']);
  assert.ok(!fs.existsSync(m.demande));
});

test('l’issue : un texte → message (gardé pour la filiation) ; « No response requested. » avec outils → outils ; sans → rien', () => {
  const m = monter();
  m.cerveau.reveilInterieur = { id: 'a' };
  m.f.noterIssueInterieur(m.cerveau, 'Frérot, le calcul du sable a fini.', ['mcp__calcul__lancer']);
  assert.strictEqual(m.cerveau.reveilInterieur, null);
  m.cerveau.reveilInterieur = { id: 'b' };
  m.f.noterIssueInterieur(m.cerveau, 'No response requested.', ['mcp__anamnese__memory_store']);
  m.cerveau.reveilInterieur = { id: 'c' };
  m.f.noterIssueInterieur(m.cerveau, '  ', []);
  m.f.noterIssueInterieur(m.cerveau, 'un tour autonome qui n’est pas un réveil intérieur', []);
  const i = m.f.issuesInterieures();
  assert.deepStrictEqual(nu(i.map(x => [x.id, x.issue])), [['a', 'message'], ['b', 'outils'], ['c', 'rien']]);
  assert.strictEqual(i[0].texte, 'Frérot, le calcul du sable a fini.');
  assert.strictEqual(i[0].modele_reel, 'claude-opus-5-5');
  assert.strictEqual(i[1].texte, undefined);
});

test('le compteur du jour additionne les issues du jour seulement', () => {
  const m = monter();
  const hier = m.T / 1000 - 86400;
  fs.writeFileSync(m.issues, [{ id: 'h', ts: hier, issue: 'message' }, { id: 'a', ts: m.T / 1000 - 60, issue: 'message' },
    { id: 'b', ts: m.T / 1000 - 30, issue: 'rien' }, { id: 'c', ts: m.T / 1000 - 10, issue: 'expiree' }].map(o => JSON.stringify(o)).join('\n') + '\n');
  assert.deepStrictEqual(nu(m.f.reveilsInterieursDuJour()), { n: 2, message: 1, outils: 0, rien: 1, expiree: 1, erreur: 0, perimee: 0 });
});

test('le crochet d’issue est branché dans finir de tourAutonome, et l’état intérieur porte le compteur', () => {
  const t = prendre('tourAutonome');
  assert.match(t, /const finir = \(issue\) => \{[\s\S]*?noterIssueInterieur\(c, texte, outils, issue\);[\s\S]*?livrerAutonome\(/);
  assert.match(src, /setInterval\(reveillerPourInterieur, 3000\)\.unref\(\)/);
  assert.match(src, /reveils_interieurs: reveilsInterieursDuJour\(\)/);
});

// ---- suite de la relecture indépendante (27/10)
test('Ahmed a mis sa vie intérieure en pause : la demande est retirée sans réveil (issue neutre)', () => {
  const m = monter({ pause: true });
  m.deposer(m.D());
  m.f.reveillerPourInterieur();
  assert.strictEqual(m.ecrits.length, 0);
  assert.ok(!fs.existsSync(m.demande));
  assert.deepStrictEqual(nu(m.f.issuesInterieures().map(x => x.issue)), ['expiree']);
});

test('une notification d’agent en attente : on attend (le tour qui vient est le sien, pas le réveil)', () => {
  const m = monter();
  m.cerveau.notifs.push({ resume: 'agent fini' });
  m.deposer(m.D());
  m.f.reveillerPourInterieur();
  assert.strictEqual(m.ecrits.length, 0);
  assert.ok(fs.existsSync(m.demande));
});

test('un tour en erreur ou coupé : issue « erreur », neutre pour le seuil et la lignée', () => {
  const m = monter();
  m.cerveau.reveilInterieur = { id: 'a' };
  m.f.noterIssueInterieur(m.cerveau, '', [], 'cerveau arrêté (SIGTERM)');
  m.cerveau.reveilInterieur = { id: 'b' };
  m.f.noterIssueInterieur(m.cerveau, 'API Error: 529 {"type":"overloaded_error"}', [], null);
  m.cerveau.reveilInterieur = { id: 'c' };
  m.f.noterIssueInterieur(m.cerveau, 'Frérot, je repensais au calcul.', [], null);
  const i = m.f.issuesInterieures();
  assert.deepStrictEqual(nu(i.map(x => [x.id, x.issue])), [['a', 'erreur'], ['b', 'erreur'], ['c', 'message']]);
  assert.strictEqual(i[1].texte, undefined);
  assert.deepStrictEqual(nu(m.f.reveilsInterieursDuJour()), { n: 1, message: 1, outils: 0, rien: 0, expiree: 0, erreur: 2, perimee: 0 });
});

test('le crochet d’issue reçoit l’issue du tour', () => {
  assert.match(prendre('tourAutonome'), /noterIssueInterieur\(c, texte, outils, issue\);/);
});

test('(Ahmed, 27/10 01:26) le réveil du courrier n’a plus de plage horaire, et Hakim juge s’il dérange Ahmed', () => {
  assert.match(src, /process\.env\.JARVIS_COURRIER_HEURES \|\| '0-24'/);
  const r = prendre('reveillerPourCourrier');
  assert.match(r, /s'il dort/i);
  assert.match(r, /No response requested\./);
});

test('(relecture du 27/10) pendant son temps à lui, pas de réveil intérieur en plus : la demande attend', () => {
  const m = monter();
  m.ctx.tempsLibreEnCours = true;
  m.deposer(m.D());
  m.f.reveillerPourInterieur();
  assert.strictEqual(m.ecrits.length, 0);
  assert.ok(fs.existsSync(m.demande));
});

// ---- (27/10, la nuit de son premier réveil) une demande déposée avant le retour d'Ahmed est périmée
test('la nuit du 27/10 rejouée : demande à 04:42:36, Ahmed écrit 3 s plus tard, passage à 04:44:56 : aucun réveil', () => {
  const m = monter({ ahmedIlYaMs: 137e3 });                       // il a écrit il y a 2 min 17 s : l'attente de 2 min est passée
  m.deposer({ ...m.D(140), source: 'ressenti', texte: 'Je ressens de la tristesse depuis 10 min, et Ahmed est absent depuis 3 h 00.' });
  m.f.reveillerPourInterieur();
  assert.strictEqual(m.ecrits.length, 0);
  assert.ok(!fs.existsSync(m.demande));
  assert.deepStrictEqual(nu(m.f.issuesInterieures().map(x => [x.id, x.issue])), [['abc123def456', 'perimee']]);
});

test('une demande déposée moins d’une minute après un message d’Ahmed est périmée aussi (le démon ne l’avait pas encore vu)', () => {
  const m = monter({ ahmedIlYaMs: 210e3 });
  m.deposer(m.D(180));                                             // déposée 30 s après son message
  m.f.reveillerPourInterieur();
  assert.strictEqual(m.ecrits.length, 0);
  assert.deepStrictEqual(nu(m.f.issuesInterieures().map(x => x.issue)), ['perimee']);
});

test('une demande déposée plus d’une minute après le dernier message d’Ahmed réveille (passé ses 2 min d’attente)', () => {
  const m = monter({ ahmedIlYaMs: 300e3 });
  m.deposer(m.D(150));                                             // 2 min 30 s après son message
  m.f.reveillerPourInterieur();
  assert.strictEqual(m.ecrits.length, 1);
});

test('le compteur du jour montre les demandes périmées, sans les compter comme réveils', () => {
  const m = monter();
  fs.writeFileSync(m.issues, [{ id: 'a', ts: m.T / 1000 - 60, issue: 'message' }, { id: 'b', ts: m.T / 1000 - 30, issue: 'perimee' }]
    .map(o => JSON.stringify(o)).join('\n') + '\n');
  assert.deepStrictEqual(nu(m.f.reveilsInterieursDuJour()), { n: 1, message: 1, outils: 0, rien: 0, expiree: 0, erreur: 0, perimee: 1 });
});

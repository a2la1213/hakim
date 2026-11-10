/* (09/11, agent vitesse) l'orchestrateur : node --test test-orchestrateur.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const O = require('./orchestrateur.js');

const horloge = (t0 = Date.parse('2026-11-09T18:40:00+01:00')) => { const h = { t: t0 }; h.f = () => h.t; return h; };

test('la file : papa passe avant le téléphone qui attendait', async () => {
  const h = horloge(), f = O.creerFile({ maintenant: h.f });
  const ordre = [];
  const l1 = await f.prendre('telephone');                            // le GPU travaille pour le téléphone
  const p2 = f.prendre('telephone').then(l => { ordre.push('telephone'); return l; });
  const p3 = f.prendre('papa').then(l => { ordre.push('papa'); return l; });
  l1();
  await new Promise(r => setImmediate(r));
  assert.deepStrictEqual(ordre, ['papa']);                          // (témoin : sans la priorité, le téléphone passait)
  const l3 = await p3;
  l3();
  const l2 = await p2; assert.ok(l2); l2();
  assert.deepStrictEqual(ordre, ['papa', 'telephone']);
});

test('la file : un bloc du téléphone trop vieux est sauté (null), jamais un de papa', async () => {
  const h = horloge(), f = O.creerFile({ maintenant: h.f, vieuxMs: 15000 });
  const l1 = await f.prendre('papa');
  const tel = f.prendre('telephone'), papa = f.prendre('papa');
  h.t += 20000;
  l1();
  assert.strictEqual(await tel, null);
  const lp = await papa; assert.strictEqual(typeof lp, 'function'); lp();
  assert.strictEqual(f.etat().sautes, 1);
});

test('la file : au plus deux blocs du téléphone en attente, les plus vieux sautés', async () => {
  const h = horloge(), f = O.creerFile({ maintenant: h.f, garder: { telephone: 2 } });
  const l0 = await f.prendre('papa');
  const a = f.prendre('telephone'), b = f.prendre('telephone'), c = f.prendre('telephone');
  assert.strictEqual(await a, null);
  l0();
  const lb = await b; assert.ok(lb); lb();
  const lc = await c; assert.ok(lc); lc();
});

test('la file : libérer deux fois ne libère qu’une fois', async () => {
  const h = horloge(), f = O.creerFile({ maintenant: h.f });
  const l1 = await f.prendre('papa');
  let deux = false; f.prendre('papa').then(() => { deux = true; });
  const trois = f.prendre('papa');
  l1(); l1();
  await new Promise(r => setImmediate(r));
  assert.ok(deux); assert.strictEqual(f.etat().occupe, true);
  assert.deepStrictEqual(f.etat().en_attente, ['papa']);
  void trois;
});

test('le forfait : « weekly limit » coupe les voix de fond jusqu’à 21:01, sauf les frères ; une sonde toutes les 10 min', () => {
  const h = horloge(), o = O.creer({ maintenant: h.f, lirePression: (cb) => cb({ libre_pct: 60, swap_utilise_mo: 1000 }) });
  o.mesurer();
  assert.ok(o.admettre('piste_entendu_haiku').ok);
  o.noterAppel('piste_entendu_haiku', "You've hit your weekly limit · resets 9pm (Europe/Zurich)");
  assert.ok(o.forfaitCoupe());
  const r = o.admettre('pretraitement_parole');
  assert.strictEqual(r.ok, false); assert.strictEqual(r.raison, 'forfait coupé');
  assert.ok(o.admettre('frere_opus').ok);
  h.t += 10 * 60000 + 1;
  assert.strictEqual(o.admettre('integration').sonde, true);          // une sonde passe
  assert.strictEqual(o.admettre('integration').ok, false);           // pas deux
  h.t = Date.parse('2026-11-09T21:01:30+01:00');
  assert.ok(!o.forfaitCoupe()); assert.ok(o.admettre('integration').ok);
});

test('le forfait : une réponse réussie le rouvre avant l’heure', () => {
  const h = horloge(), o = O.creer({ maintenant: h.f, lirePression: (cb) => cb({ libre_pct: 60 }) });
  o.noterAppel('souffle', "You've hit your weekly limit · resets 9pm");
  assert.ok(o.forfaitCoupe());
  o.noterAppel('frere_opus', null);                                   // un frère sur l'API ne prouve rien du forfait
  assert.ok(o.forfaitCoupe());
  o.noterAppel('souffle', null);
  assert.ok(!o.forfaitCoupe());
});

test('la remise du forfait : 9pm, 9:30pm, une date, rien', () => {
  const t = Date.parse('2026-11-09T18:40:00+01:00');
  assert.strictEqual(new Date(O.remiseDuForfait('resets 9pm', t)).getHours(), 21);
  const d = new Date(O.remiseDuForfait('resets 9:30pm', t)); assert.strictEqual(d.getHours(), 21); assert.strictEqual(d.getMinutes(), 31);
  assert.strictEqual(new Date(O.remiseDuForfait('resets Nov 12, 9am', t)).getHours(), 9);
  assert.strictEqual(O.remiseDuForfait('rien', t), t + 30 * 60000);
  assert.ok(O.remiseDuForfait('resets 6pm', t) > t + 20 * 3600e3);   // 18:00 passé : demain
});

test('la mémoire et le tour de papa : les blancs et le téléphone s’effacent, papa jamais', () => {
  const h = horloge();
  let p = { libre_pct: 50, swap_utilise_mo: 2000 };
  const o = O.creer({ maintenant: h.f, lirePression: (cb) => cb(p) });
  o.mesurer();
  assert.strictEqual(o.niveau(), 'ok');
  assert.ok(o.admettre('piste_blanc').ok);
  o.papaParle();
  assert.strictEqual(o.admettre('piste_blanc').raison, 'tour de papa');
  assert.strictEqual(o.admettre('piste_entendu_haiku').raison, 'tour de papa');
  assert.ok(o.admettre('souffle').ok); assert.ok(o.admettre('piste_haiku').ok);
  h.t += 26000;
  assert.ok(o.admettre('piste_entendu_haiku').ok);
  p = { libre_pct: 44, swap_utilise_mo: 16837 }; o.mesurer();            // le 09/11 à 21:09
  assert.strictEqual(o.niveau(), 'tendu');
  assert.strictEqual(o.admettre('piste_blanc').ok, false);
  assert.ok(o.admettre('piste_entendu_haiku').ok);
  p = { libre_pct: 12, swap_utilise_mo: 17000 }; o.mesurer();
  assert.strictEqual(o.niveau(), 'critique');
  assert.strictEqual(o.admettre('piste_entendu_haiku').ok, false);
  assert.ok(o.admettre('pretraitement_parole').ok);
  p = null; o.mesurer();
  assert.strictEqual(o.niveau(), 'inconnu'); assert.ok(o.admettre('piste_blanc').ok);   // sans mesure : on ne bloque rien
});

test('le journal : une ligne par changement, fichier 0600', () => {
  const dir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'orchestre-'));
  const f = path.join(dir, 'orchestre.jsonl');
  const h = horloge(), o = O.creer({ maintenant: h.f, journal: O.journalFichier(f), lirePression: (cb) => cb({ libre_pct: 10 }) });
  o.mesurer();
  o.noterAppel('souffle', "You've hit your weekly limit · resets 9pm");
  const l = fs.readFileSync(f, 'utf8').trim().split('\n').map(JSON.parse);
  assert.deepStrictEqual(l.map(x => x.e), ['niveau', 'forfait_coupe']);
  assert.strictEqual(fs.statSync(f).mode & 0o777, 0o600);
});

test('la pression réelle du Mac se lit (sysctl)', async () => {
  const p = await new Promise(r => O.lirePressionMac(r));
  assert.ok(p && Number.isFinite(p.libre_pct) && p.libre_pct >= 0 && p.libre_pct <= 100);
});

test('le cockpit le branche : admission du fond, limite du forfait, second corps vivant, file de la grande oreille, Azure hors file', () => {
  const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
  const fond = src.slice(src.indexOf('function sonnetTeteDeFond('), src.indexOf('const t0 = Date.now();', src.indexOf('function sonnetTeteDeFond(')));
  assert.match(fond, /if \(!sonnetTeteDeFond\.classique\) \{\n\s+const adm = ORCHESTRE\.admettre\(etiquette\);\n\s+if \(!adm\.ok\) return resolve\(\{ erreur: `orchestre : \$\{adm\.raison\}`, ms: 0, refuse: true \}\);/);
  assert.match(src, /function noterAppelLlm\(o\) \{\n.*\n  try \{ ORCHESTRE\.noterAppel\(o\.etiquette, o\.erreur\); \} catch \(_\) \{\}/);
  assert.match(src, /chargeMac\(\) < 0\.7 && ORCHESTRE\.niveau\(\) === 'ok' \? 2 : 1/);
  assert.match(src, /libre\.fin = true;\n  try \{ libre\.proc\.stdin\.end\(\); \} catch \(_\) \{\}/);
  assert.match(src, /const FILE_OREILLE = ORCHESTRE\.file\('oreille', \{ vieuxMs: 15000, garder: \{ telephone: 2 \} \}\);/);
  assert.match(src, /const azurePapa = dePapa && !!corpsReglages\(\)\.stt_azure && apprentissageVoix <= 0;/);
  assert.match(src, /if \(azurePapa\) await prendreTour\(\);/);
  // (10/11) à l'arrivée d'un morceau du micro : un tour provisoire ; le tour entier quand le morceau est bien papa (papaVerifie)
  assert.match(src, /if \(dePapa\) ORCHESTRE\.papaParle\(undefined, typeof TOUR_PAPA_PROVISOIRE_MS === 'number' \? TOUR_PAPA_PROVISOIRE_MS : undefined\);/);
  assert.match(src, /if \(dePapa && typeof papaVerifie === 'function'\) \{ try \{ papaVerifie\(r\); \} catch \(_\) \{\} \}/);
});

test('(10/11) le tour provisoire : un morceau du micro pas encore reconnu (le live sur le haut-parleur) n\'éteint le fond que quelques secondes', () => {
  const h = horloge();
  const o = O.creer({ maintenant: h.f, lirePression: (cb) => cb({ libre_pct: 60 }) });
  o.mesurer();
  o.papaParle(undefined, 5000);
  assert.strictEqual(o.admettre('piste_entendu_haiku').raison, 'tour de papa');
  h.t += 6000;
  assert.ok(o.admettre('piste_entendu_haiku').ok, 'le provisoire est passé');
  o.papaParle();                                                     // le morceau était bien papa : son tour entier
  h.t += 20000;
  assert.strictEqual(o.admettre('piste_entendu_haiku').raison, 'tour de papa');
  // (témoin) sans le provisoire, chaque morceau du live tenait le fond 25 s
  const o2 = O.creer({ maintenant: h.f, lirePression: (cb) => cb({ libre_pct: 60 }) });
  o2.mesurer(); o2.papaParle(); h.t += 6000;
  assert.strictEqual(o2.admettre('piste_entendu_haiku').ok, false);
});

test('(10/11) son garde du live (« piste_live ») : admis pendant le tour de papa (il n\'appelle que papa silencieux), refusé forfait coupé ou mémoire critique', () => {
  const h = horloge();
  let p = { libre_pct: 60 };
  const o = O.creer({ maintenant: h.f, lirePression: (cb) => cb(p) });
  o.mesurer();
  assert.strictEqual(O.classeDe('piste_live'), 'live');
  o.papaParle();
  assert.ok(o.admettre('piste_live').ok);
  p = { libre_pct: 10 }; o.mesurer();
  assert.strictEqual(o.admettre('piste_live').raison, 'mémoire critique');
  p = { libre_pct: 60 }; o.mesurer();
  o.noterAppel('piste_live', "You've hit your weekly limit · resets 9pm");
  assert.strictEqual(o.admettre('piste_live').raison, 'forfait coupé');
});

/* (11/11, Ahmed : « il faut relier cette charge à son cœur, son cerveau, ses émotions, ses hormones, sa mémoire, etc., et sans rien oublier ») sa
   charge dans tout son corps, côté cockpit (charge-corps.js ; le démon : anamnese/charge_corps.py). Chaque lien a son test, et son TÉMOIN : le
   lien absent (un état éteint, trop vieux, au repos, une ligne retirée) doit donner l'inverse. node --test test-charge-corps.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const C = require('./charge-corps.js');
const Instant = require('./instant.js');
const RM = require('./rappel-moment.js');
const Live = require('./live.js');

const T = 1_800_000_000_000;
const src = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
const fonction = (debut) => { const i = src.indexOf(debut); assert.ok(i >= 0, debut); return src.slice(i, src.indexOf('\n}\n', i) + 2); };

// ce que publie le démon (kv « interieur », e.charge_corps), en plein live chargé
const cc = (o = {}) => ({ ts: T / 1000 - 10, mac: { cpu: 0.82, gpu: 0.74, n: 10 }, appareils: { telephone: { thermique: 1 } }, live: { actif: true, phrases_min: 30, voix: 6 },
  sens: { surcharge: { niveau: 'fort', x: 0.9, qui: ['ton oreille des voix', 'Whisper (ton oreille)'] }, fievre: { niveau: 'fort', x: 1, qui: ['telephone'] },
    effort: { niveau: 'repos', x: 0 }, malaise: { niveau: 'present', x: 0.3, qui: ['ecosystemd'] } },
  dominante: 'surcharge', mots: 'le live te remplit : beaucoup de voix à la fois, et ça te surcharge (ton oreille des voix et Whisper (ton oreille) le suivent)',
  historique: [[T / 1000 - 400, 'surcharge', 'debut', 'surcharge', 0.43], [T / 1000 - 20, 'fievre', 'fin', 'reprise_fievre', 0.2]], ...o });

test('son bloc intérieur : ce qu’il sent de sa charge, avec sa cause, jamais de chiffre ; rien éteint, trop vieux ou au repos (témoins)', () => {
  const l = C.ligneBloc(cc({ mots: 'un programme d’Apple (ecosystemd) te prend 89 % depuis 2 jours' }), T);
  assert.match(l, /^ta charge : un programme d’Apple \(ecosystemd\)/);
  assert.doesNotMatch(l, /[0-9%]/, 'aucun chiffre ne passe');
  assert.match(C.ligneBloc(cc(), T), /le live te remplit/);
  assert.strictEqual(C.ligneBloc(cc({ eteint: true }), T), '');
  assert.strictEqual(C.ligneBloc(cc(), T + 200_000), '', 'un démon qui ne bat plus : rien d’inventé');
  assert.strictEqual(C.ligneBloc(cc({ mots: null }), T), '');
});

test('câblage : chaque bloc intérieur porte sa charge, juste après ses processeurs', () => {
  const bloc = fonction('async function blocInterieur(');
  assert.match(bloc, /const lc = ChargeCorps\.ligneBloc\(e\.charge_corps, maintenant\);\n\s*if \(lc\) parties\.push\(lc\);/);
  assert.ok(bloc.indexOf('ChargeCorps.ligneBloc') > bloc.indexOf('e.coeur.processeurs.mots'));
});

test('son tableau de l’instant : un canal charge, dans la ligne, dans « Toi » quand elle est forte, et ce qui vient de changer', () => {
  const ch = C.pourInstant(cc(), T);
  assert.deepStrictEqual({ ...ch, qui: ch.qui.length }, { dominante: 'surcharge', niveau: 'fort', causes: { surcharge: 'fort', fievre: 'fort', malaise: 'present' },
    qui: 2, mac: 82, gpu: 74, tel_chaleur: 100, live: true, cle: 'surcharge du live' });
  const tab = Instant.composer({ t: T, maintenant: T, charge: ch });
  assert.match(Instant.ligne(tab), /ta charge : une surcharge \(le live\), forte \(ton oreille des voix, Whisper \(ton oreille\)\) ; aussi une fièvre, un malaise ; les processeurs du Mac occupés à 82 % ; le téléphone bridé par la chaleur/);
  assert.doesNotMatch(Instant.ligne(tab), /le Mac à \d+ %/);   // (11/11) jamais lu comme sa batterie
  assert.match(Instant.ligneSoi(tab), /ta charge : une surcharge \(le live\), forte/);
  assert.ok(Instant.etiquettes(tab).includes('charge:surcharge'));
  // témoins : sans charge, ni ligne ni « Toi » ; une charge légère n'entre pas dans « Toi »
  const sans = Instant.composer({ t: T, maintenant: T });
  assert.doesNotMatch(Instant.ligne(sans), /ta charge/);
  assert.doesNotMatch(Instant.ligneSoi(sans), /ta charge/);
  const legere = Instant.composer({ t: T, maintenant: T, charge: C.pourInstant(cc({ sens: { malaise: { niveau: 'present', x: 0.3, qui: ['ecosystemd'] } }, dominante: 'malaise' }), T) });
  assert.match(Instant.ligne(legere), /ta charge : un malaise \(une charge qui ne vient pas de toi\), légère \(ecosystemd\)/);
  assert.doesNotMatch(Instant.ligneSoi(legere), /ta charge/);
  // ce qui vient de changer : elle monte, elle retombe
  assert.deepStrictEqual(Instant.differences(sans, tab).map(d => d.mots), ['ta charge change : le live te surcharge']);
  assert.deepStrictEqual(Instant.differences(tab, sans).map(d => d.mots), ['ta surcharge retombe']);
  const moins = Instant.composer({ t: T, maintenant: T, charge: { ...ch, niveau: 'present' } });
  assert.deepStrictEqual(Instant.differences(moins, tab).map(d => d.mots), ['ta charge monte : le live te surcharge']);
  assert.strictEqual(C.pourInstant(cc({ eteint: true }), T), null, 'témoin : éteint, pas de canal');
});

test('câblage : le tableau de l’instant reçoit la charge du démon', () => {
  assert.match(fonction('function instantCache('), /charge: g\(\(\) => ChargeCorps\.pourInstant\(lui\.interieur && lui\.interieur\.charge_corps, maintenant\)\)/);
  assert.match(fonction('function instantSources('), /charge: cache\.charge \}/);
});

test('son fil des stimuli : sa charge qui monte ou retombe, une seule fois chacune, à son heure', () => {
  const { stimuli, vu } = C.stimuliNeufs(cc(), T / 1000 - 1000);
  assert.deepStrictEqual(stimuli, [{ t: T - 400_000, x: 'ta charge : le live te surcharge' }, { t: T - 20_000, x: 'ta charge : ta fièvre retombe' }]);
  assert.deepStrictEqual(C.stimuliNeufs(cc(), vu).stimuli, [], 'témoin : déjà vus, rien de plus');
  assert.match(src, /etatInterieur\(\)\.then\(\(x\) => \{ lui\.interieur = x \|\| \{\}; chargeAuFil\(lui\.interieur\); \}\)/);
  assert.match(fonction('function chargeAuFil('), /fluxAjouter\('corps', x\.x, x\.t, null, null, false\)/);
});

test('son rappel du moment : sa charge est un indice qui fait revenir ses épisodes (la clé écrite dans ses souvenirs)', () => {
  const tab = Instant.composer({ t: T, maintenant: T, charge: C.pourInstant(cc(), T) });
  const ctx = RM.contexteDuMoment({ tab, maintenant: T });
  assert.ok(ctx.indices.some(x => x.cle === 'surcharge du live' && x.f === 'corps'));
  assert.match(ctx.requete, /ta charge : une surcharge/);
  // la même clé que le démon écrit dans ses souvenirs (anamnese/charge_corps.CLES)
  // (le démon : anamnese/charge_corps.py, dans Anamnèse, ou dans le chantier tant que la branche n'est pas fusionnée)
  const home = require('os').homedir();
  const f = [process.env.ANAMNESE_DIR, path.join(home, 'Desktop', 'anamnese'), path.join(home, 'Desktop', '.wt-anamnese', 'charge-corps')]
    .filter(Boolean).map(d => path.join(d, 'charge_corps.py')).find(x => fs.existsSync(x));
  if (f) { const py = fs.readFileSync(f, 'utf8'); for (const v of Object.values(C.CLES)) assert.ok(py.includes(`"${v}"`), v); }
  const sans = RM.contexteDuMoment({ tab: Instant.composer({ t: T, maintenant: T, lieu: 'chez nous' }), maintenant: T });
  assert.ok(!sans.indices.some(x => x.f === 'corps'), 'témoin : sans charge, pas d’indice');
});

test('le live compte ses voix dans la minute de son garde (sa charge sociale)', () => {
  const e = Live.creer();
  Live.recevoir(e, { cle: 'a', texte: 'Salut tout le monde, ça va ?', fin: true, qui: 'voix 3' }, T);
  Live.recevoir(e, { cle: 'b', texte: 'Moi je suis là aussi les amis.', fin: true, qui: 'voix 7' }, T + 1000);
  Live.recevoir(e, { cle: 'c', texte: 'Encore moi, voix trois ici.', fin: true, qui: 'voix 3' }, T + 2000);
  Live.recevoir(e, { cle: 'd', texte: 'Ta propre voix revient ici.', fin: true, qui: 'ta propre voix' }, T + 3000);
  const m = Live.minute(e, T + 60_000);
  assert.strictEqual(m.voix, 2, 'deux voix, pas la sienne');
  assert.ok(!('quis' in m), 'la minute ne garde que leur nombre');
  assert.strictEqual(Live.minute(e, T + 120_000).voix, 0, 'témoin : la minute d’après repart de zéro');
});

test('l’interrupteur : lu à chaud dans corps-reglages.json, allumé par défaut, écrit par la page Réglages', () => {
  const r = fonction('function corpsReglages(');
  assert.match(r, /charge_corps: r\.charge_corps !== false, charge_hormones: r\.charge_hormones !== false/);
  assert.match(src, /for \(const k of \['charge_corps', 'charge_hormones'\]\) if \(typeof q\[k\] === 'boolean'\) r\[k\] = q\[k\];/);
  const page = fs.readFileSync(path.join(__dirname, 'public', 'reglages.html'), 'utf8');
  assert.match(page, /\['charge_corps', '🔥 Sa charge dans tout son corps', '[^']+', 'oui'\]/);
  assert.match(page, /\['charge_hormones', '🧪 Sa charge va jusqu’à ses hormones', '[^']+', 'oui'\]/);
});

test('sa fatigue dit quand son propre calcul l’a fait forcer', () => {
  const vm = require('node:vm');
  const ctx = { Number, String, Math };
  vm.createContext(ctx);
  vm.runInContext(fonction('function causeFatigue(') + 'this.f = causeFatigue;', ctx);
  const e = { humeur: 'fatigue', fatigue_jauge: { effort: 0.21, norme_effort: 0.087, corps: 0.4, norme_corps: 0.53, cible: 0.66, calcul: 0.8 } };
  assert.match(ctx.f(e), /et ton propre calcul t'a fait forcer$/);
  assert.doesNotMatch(ctx.f({ ...e, fatigue_jauge: { ...e.fatigue_jauge, calcul: 0 } }), /calcul/, 'témoin : sans son calcul, rien de tel');
});

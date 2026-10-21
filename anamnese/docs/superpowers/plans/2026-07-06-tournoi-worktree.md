# Tournoi worktree pour problèmes durs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Le gabarit d'orchestration atelier remplace l'auto-note des designs par un jury adversarial, et escalade les modules durs en tournoi de N tentatives divergentes (worktrees) sélectionnées objectif-d'abord, en apprenant quelle stratégie gagne.

**Architecture:** Édition de `workflow-template.js` (le gabarit). La logique de décision (escalade, sélection) est extraite en **helpers PURS** (pas de dépendance au runtime Workflow) → node-testables ; l'orchestration (dispatch d'agents, worktrees) appelle ces helpers. Livrable = JS ; vérif = test node des helpers + dry-run + review adversariale (PAS de pytest).

**Tech Stack:** JavaScript (gabarit Workflow : `agent()`/`parallel()`/`pipeline()`/`phase()`/`log()`/`budget`), Node pour tester les helpers purs.

## Global Constraints

- Cible `~/.claude/skills/atelier/workflow-template.js` — HORS git anamnèse : traçabilité par rapports `.superpowers/sdd/scp3-task-*-report.md`. Docs dans le repo anamnèse. Backup avant édition : `cp workflow-template.js workflow-template.js.bak-pre-tournoi`.
- **Compose avec le chantier 1** : les agents de build du tournoi = palier DEV (`isolation: 'worktree'`) ; les juges = palier LECTURE. Ne pas donner d'outil hors palier.
- **Objectif AVANT subjectif** : le filtre par tests (objectif) précède toujours le jury (subjectif). Un jury ne classe QUE des tentatives dont les tests passent.
- **Coût délibéré** : `log()` chaque escalade + son POURQUOI ; N=3 défaut, scalable via `budget` ; jamais de N× silencieux.
- **Escalade bornée** : N fixe puis BLOQUER humain si 0 survivante. Auto-report (N2) exige une `reason` concrète (anti crier-au-loup).
- **Worktrees = harnais** (`isolation: 'worktree'`), jamais `arbor` dans un agent.
- Subagents Opus 4.8. Review adversariale.

## File Structure

| Fichier | Rôle | Tâche |
|---|---|---|
| `~/.claude/skills/atelier/workflow-template.js` (modify) | helpers purs + phase Concevoir (jury) + phase Construire (tournoi) + trace mémoire | 1,2,3 |
| test node inline (T4) | exerce les helpers purs avec des données factices | 4 |

**Helpers purs ajoutés (après les schémas, ~ligne 30)** — consommés par T1/T2/T3 :
- `shouldEscalate({hard, verifFailed, selfReport}) -> bool`
- `divergentStrategies(n) -> string[]`
- `selectWinner(attempts) -> {winner, survivors, blocked}`
- `aggregateJudgeScores(judgements) -> Map<designIdx, number>`

---

### Task 1: Helpers purs + jury adversarial de design (phase Concevoir)

**Files:**
- Modify: `~/.claude/skills/atelier/workflow-template.js` (bloc helpers après schémas ; phase Concevoir lignes ~40-46)
- Backup: `cp ~/.claude/skills/atelier/workflow-template.js ~/.claude/skills/atelier/workflow-template.js.bak-pre-tournoi`

**Interfaces:**
- Produces: les 4 helpers purs (signatures ci-dessus) ; la phase Concevoir retourne toujours `gagnant` (objet DESIGN) + `ideesGreffe` (string[]).
- Consumes: `designs` (array d'objets DESIGN), `parallel()`, `agent()`.

- [ ] **Step 1: Backup** — le `cp` ci-dessus.

- [ ] **Step 2: Ajouter le bloc de helpers purs** après les définitions de schémas (DESIGN/VERDICT/FINDINGS), avant la phase Comprendre :

```js
// ——— Helpers PURS du tournoi (aucune dépendance au runtime Workflow → testables via node) ———
function shouldEscalate({ hard, verifFailed, selfReport }) {
  // N1 échec de vérif · N2 auto-report avec raison concrète · (hard = flag/N3 pré-réglé)
  const selfAsk = !!(selfReport && selfReport.needsEscalation && selfReport.reason);
  return Boolean(hard || verifFailed || selfAsk);
}
function divergentStrategies(n) {
  const base = ['minimal/robuste', "perf d'abord", 'idiomatique au repo',
                "défensif/tests d'abord", 'simplicité extrême'];
  return base.slice(0, Math.max(1, n));
}
function aggregateJudgeScores(judgements) {
  // judgements: [{ notes: [{idx, note}] }] → Map idx -> somme des notes
  const acc = new Map();
  for (const j of (judgements || [])) {
    for (const n of ((j && j.notes) || [])) {
      if (n && typeof n.idx === 'number') acc.set(n.idx, (acc.get(n.idx) || 0) + (n.note || 0));
    }
  }
  return acc;
}
function selectWinner(attempts) {
  // attempts: [{id, testsPass:boolean, judgeScore:number}] — OBJECTIF avant subjectif
  const survivors = (attempts || []).filter((a) => a && a.testsPass);
  if (survivors.length === 0) return { winner: null, survivors: [], blocked: true };
  const winner = survivors.slice().sort((a, b) => (b.judgeScore || 0) - (a.judgeScore || 0))[0];
  return { winner, survivors, blocked: false };
}
```

- [ ] **Step 3: Remplacer la sélection par auto-note de la phase Concevoir** (lignes ~42-46). Ancien :
```js
const designs = await parallel(DESIGN_LENSES.map((lens) => () =>
  agent(`Propose une approche … auto-note /10.`, { … schema: DESIGN })))
const gagnant = (designs.filter(Boolean).sort((a, b) => (b.score || 0) - (a.score || 0))[0]) || designs.filter(Boolean)[0]
```
Nouveau (jury LECTURE indépendant) :
```js
const designs = (await parallel(DESIGN_LENSES.map((lens) => () =>
  agent(`Propose une approche pour : ${OBJECTIF}, optimisée pour « ${lens} ». Contexte : ${JSON.stringify(compréhension).slice(0, 2000)}. Donne étapes concrètes + risques.`,
    { label: `design:${lens}`, phase: 'Concevoir', agentType: 'architecte-logiciel', schema: DESIGN })))).filter(Boolean)
// Jury adversarial : des juges LECTURE indépendants (n'ont pas écrit les designs) notent CHAQUE design sur leur lentille.
const JUDGE_LENSES = ['correctness/robustesse', 'fidélité métier', 'perf/échelle']
const JUGE = { type: 'object', properties: { notes: { type: 'array', items: { type: 'object',
  properties: { idx: { type: 'number' }, note: { type: 'number' }, raison: { type: 'string' } }, required: ['idx', 'note'] } },
  idees_a_greffer: { type: 'array', items: { type: 'string' } } }, required: ['notes'] }
const jugements = (await parallel(JUDGE_LENSES.map((lens) => () =>
  agent(`Tu es juge INDÉPENDANT (tu n'as pas écrit ces designs). Note CHAQUE design de 0 à 10 sur « ${lens} ».\nDesigns :\n${designs.map((d, i) => `[${i}] ${d.approche} — étapes: ${(d.etapes || []).join('; ')}`).join('\n')}\nRends notes:[{idx,note,raison}] + idees_a_greffer (les bonnes idées des designs non-gagnants).`,
    { label: `juge:${lens}`, phase: 'Concevoir', agentType: 'architecte-logiciel', effort: 'high', schema: JUGE })))).filter(Boolean)
const scores = aggregateJudgeScores(jugements)
const gagnantIdx = designs.length ? [...Array(designs.length).keys()].sort((a, b) => (scores.get(b) || 0) - (scores.get(a) || 0))[0] : -1
const gagnant = designs[gagnantIdx] || designs[0]
const ideesGreffe = jugements.flatMap((j) => j.idees_a_greffer || [])
log(`Design retenu (jury) : ${gagnant?.approche?.slice(0, 80)} — idées à greffer : ${ideesGreffe.length}`)
```

- [ ] **Step 4: Vérif** — `node -e "…"` chargeant le fichier n'est pas possible (globals runtime), mais : `node --check ~/.claude/skills/atelier/workflow-template.js` doit passer (syntaxe valide). Confirmer que `sort by (b.score - a.score)` a disparu (`grep -c "b.score" workflow-template.js` = 0) et que `aggregateJudgeScores`/`JUDGE_LENSES` sont présents.
- [ ] **Step 5: Rapport** — `~/Desktop/anamnese/.superpowers/sdd/scp3-task-1-report.md` : diff Concevoir, `node --check` OK, backup.

---

### Task 2: Tournoi de build en escalade adaptative (phase Construire)

**Files:**
- Modify: `~/.claude/skills/atelier/workflow-template.js` (phase Construire lignes ~48-52)

**Interfaces:**
- Consumes: `shouldEscalate`, `divergentStrategies`, `selectWinner` (T1) ; `gagnant`, `ideesGreffe` (T1) ; `MODULES` ; `agent()`, `parallel()`, `pipeline()`, `log()`.
- Produces: `builds` = array de `{module, winner, escalated:boolean, blocked:boolean, attempts?}`.

- [ ] **Step 1: Remplacer la phase Construire** (une tentative → escalade adaptative). Ancien :
```js
const builds = await parallel(MODULES.map((m) => () =>
  agent(`Implémente le lot … isolation: 'worktree' … schema: FINDINGS })))
```
Nouveau :
```js
phase('Construire')
const N_TOURNOI = 3   // défaut ; scalable via budget plus bas
async function buildModule(m) {
  // 1re tentative (worktree). L'agent peut auto-reporter la difficulté.
  const t1 = await agent(
    `Implémente le lot « ${m.key} » (${m.path}) selon le design retenu :\n${JSON.stringify(gagnant).slice(0, 1500)}\n` +
    `Idées à greffer : ${JSON.stringify(ideesGreffe).slice(0, 500)}\nBrief : ${m.brief}\n` +
    `Teste avant de dire « fait ». Si tu vois que c'est un nid de guêpes (bien plus dur qu'attendu), ` +
    `renvoie needsEscalation:true + une RAISON concrète plutôt que bâcler.`,
    { label: `build:${m.key}`, phase: 'Construire', agentType: m.agentType || 'dev-fullstack', isolation: 'worktree', schema: BUILD })
  const verifFailed = !!(t1 && t1.testsPass === false)
  if (!shouldEscalate({ hard: m.hard, verifFailed, selfReport: t1 })) {
    return { module: m.key, winner: t1, escalated: false, blocked: false }
  }
  // ESCALADE : N tentatives divergentes, seedées par l'échec de t1.
  const nb = budget && budget.total ? Math.min(5, Math.max(3, Math.floor(budget.remaining() / 150000))) : N_TOURNOI
  const raison = (t1 && t1.reason) || (verifFailed ? 'échec vérif 1re tentative' : 'module marqué hard')
  log(`Tournoi « ${m.key} » : escalade en ${nb} tentatives (cause : ${raison})`)
  const seed = `La 1re tentative a échoué/buté : ${JSON.stringify((t1 && (t1.reason || t1.items)) || '').slice(0, 400)}. Diverge de cette approche.`
  const strategies = divergentStrategies(nb)
  const attempts = (await parallel(strategies.map((strat, i) => () =>
    agent(`Implémente « ${m.key} » (${m.path}), stratégie « ${strat} ». ${seed}\nDesign : ${JSON.stringify(gagnant).slice(0, 1200)}\nTeste ; renvoie testsPass:true/false honnêtement.`,
      { label: `tournoi:${m.key}:${strat}`, phase: 'Construire', agentType: m.agentType || 'dev-fullstack', isolation: 'worktree', schema: BUILD })
      .then((r) => ({ id: `${m.key}#${i}`, strat, ...(r || {}), testsPass: !!(r && r.testsPass) }))))).filter(Boolean)
  return { module: m.key, attempts, escalated: true }  // winner/blocked calculés en Step 2
}
const builds0 = await parallel(MODULES.map((m) => () => buildModule(m)))
```

- [ ] **Step 2: Sélection objectif-d'abord + jury + BLOQUER** (après `builds0`) :
```js
// Pour les modules escaladés : filtre objectif (tests) → jury LECTURE classe les survivantes → gagnant | BLOQUER.
const builds = await parallel(builds0.map((b) => async () => {
  if (!b || !b.escalated) return b
  // (a) le filtre objectif est déjà porté par testsPass ; (b) jury sur les survivantes
  const survivors = b.attempts.filter((a) => a.testsPass)
  if (survivors.length === 0) {
    log(`Tournoi « ${b.module} » : 0 tentative ne passe les tests → BLOQUER (barrière humaine)`)
    return { module: b.module, winner: null, escalated: true, blocked: true, attempts: b.attempts }
  }
  const juges = (await parallel(['correctness/robustesse', 'perf/échelle', 'maintenabilité'].map((lens) => () =>
    agent(`Juge INDÉPENDANT. Note de 0 à 10 sur « ${lens} » CHAQUE tentative qui PASSE les tests pour « ${b.module} » :\n${survivors.map((s, i) => `[${i}] stratégie ${s.strat}`).join('\n')}\nRends notes:[{idx,note,raison}].`,
      { label: `juge-build:${b.module}:${lens}`, phase: 'Construire', agentType: 'architecte-logiciel', effort: 'high', schema: JUGE })))).filter(Boolean)
  const sc = aggregateJudgeScores(juges)
  const scored = survivors.map((s, i) => ({ ...s, judgeScore: sc.get(i) || 0 }))
  const sel = selectWinner(scored)
  log(`Tournoi « ${b.module} » : gagnant = stratégie « ${sel.winner?.strat} » (${survivors.length}/${b.attempts.length} survivantes)`)
  return { module: b.module, winner: sel.winner, escalated: true, blocked: false, attempts: b.attempts }
}))
```

- [ ] **Step 3: Ajouter le schéma BUILD** (près des autres schémas) — l'agent de build rapporte tests + auto-report :
```js
const BUILD = { type: 'object', properties: {
  resume: { type: 'string' }, testsPass: { type: 'boolean' },
  needsEscalation: { type: 'boolean' }, reason: { type: 'string' },
  items: { type: 'array', items: { type: 'object', properties: { titre: { type: 'string' }, detail: { type: 'string' } } } },
}, required: ['testsPass'] }
```
- [ ] **Step 4: Vérif** — `node --check` passe ; `grep -c "shouldEscalate\|selectWinner\|isolation: 'worktree'" workflow-template.js` ≥ 3 ; la phase Vérifier en aval consomme toujours `builds` sans casser (les `winner` remplacent les anciens objets de build — vérifier que `verifs`/l'audit final lisent `.winner` ou restent compatibles ; adapter les références si besoin et le noter).
- [ ] **Step 5: Rapport** — `scp3-task-2-report.md` : diff Construire + sélection, `node --check`, compat aval.

---

### Task 3: Apprentissage persistant (N3) + garde-fous coût

**Files:**
- Modify: `~/.claude/skills/atelier/workflow-template.js` (après la sélection du tournoi + phase Comprendre pour le pré-flag)

**Interfaces:**
- Consumes: `builds` (T2), `mcp__anamnese__memory_store_in`/`reasoning_recall` (via un agent), `MODULES`.

- [ ] **Step 1: Trace « stratégie gagnante + pourquoi » (écriture mémoire) après la sélection** — ajouter, pour chaque module escaladé et non bloqué, un agent qui logue la trace de raisonnement :
```js
// N3 — apprentissage : mémoriser quelle stratégie gagne pour cette classe de problème.
const escalades = builds.filter((b) => b && b.escalated && !b.blocked && b.winner)
if (escalades.length) {
  await parallel(escalades.map((b) => () =>
    agent(`Logue la trace de raisonnement du tournoi « ${b.module} » dans la mémoire partagée : ` +
      `stratégie gagnante = « ${b.winner.strat} », pourquoi elle a gagné, pourquoi les autres ont perdu. ` +
      `Écris via memory_store_in(content="[atelier] TOURNOI ${b.module} — stratégie gagnante « ${b.winner.strat} » : <pourquoi>", ` +
      `rubric_path="projets/${args?.projet || 'projet'}/tournois", kind="reasoning"). Crée la rubrique si absente.`,
      { label: `apprentissage:${b.module}`, phase: 'Construire', agentType: 'chef-de-projet', effort: 'medium', schema: FINDINGS })))
}
```
- [ ] **Step 2: Pré-flag N3 au cadrage (phase Comprendre)** — après la compréhension, un `reasoning_recall` sur la classe de problème qui pré-règle `m.hard` :
```js
// N3 — pré-flag : si le cerveau a mémorisé « dur » pour une classe de module, escalade d'emblée.
const memoDur = await agent(`reasoning_recall sur « tournoi difficulté » pour ces modules : ${MODULES.map((m) => m.key).join(', ')} (objectif : ${OBJECTIF}). ` +
  `Renvoie la liste des clés de module que la mémoire signale comme DURS (déjà passés en tournoi avant).`,
  { label: 'preflag-difficulté', phase: 'Comprendre', agentType: 'chef-de-projet', schema: { type: 'object', properties: { durs: { type: 'array', items: { type: 'string' } } }, required: ['durs'] } })
for (const m of MODULES) { if (memoDur && (memoDur.durs || []).includes(m.key)) m.hard = true }
```
- [ ] **Step 3: Garde-fous coût déjà portés** — vérifier que : chaque escalade fait un `log()` avec sa cause (Step 1 T2) ; `nb` est borné `[3,5]` et dérivé du `budget` ; l'auto-report N2 exige `reason` (dans `shouldEscalate`, `selfAsk` teste `selfReport.reason`). Ajouter en tête de fichier un commentaire récapitulant ces garde-fous. Aucun code neuf si déjà présent — sinon compléter.
- [ ] **Step 4: Vérif** — `node --check` ; `grep -c "reasoning_recall\|memory_store_in\|projets/" workflow-template.js` ≥ 2 ; `grep -c "budget.remaining" workflow-template.js` ≥ 1.
- [ ] **Step 5: Rapport** — `scp3-task-3-report.md` : diff apprentissage + pré-flag + garde-fous.

---

### Task 4: Dry-run (helpers purs) + review adversariale

**Files:** test node inline (pas de fichier de prod).

**Interfaces:** Consumes T1-T3.

- [ ] **Step 1: Test node des helpers PURS** — écrire un script jetable dans `$TMPDIR/test_tournoi.mjs` qui redéfinit/importe les helpers purs et les exerce (les helpers étant purs, on les copie dans le test ou on les exporte). Cas à couvrir :
```js
// shouldEscalate
console.assert(shouldEscalate({hard:true}) === true, 'hard escalade')
console.assert(shouldEscalate({verifFailed:true}) === true, 'échec escalade')
console.assert(shouldEscalate({selfReport:{needsEscalation:true, reason:'nid de guêpes'}}) === true, 'auto-report avec raison escalade')
console.assert(shouldEscalate({selfReport:{needsEscalation:true}}) === false, 'auto-report SANS raison = pas escalade (anti crier-au-loup)')
console.assert(shouldEscalate({}) === false, 'rien = pas escalade')
// selectWinner : OBJECTIF avant subjectif
console.assert(selectWinner([{id:'a',testsPass:false,judgeScore:99},{id:'b',testsPass:true,judgeScore:5}]).winner.id === 'b', 'un design cassé mieux noté ne gagne pas')
console.assert(selectWinner([{testsPass:false},{testsPass:false}]).blocked === true, '0 survivante = BLOQUER')
console.assert(selectWinner([{id:'x',testsPass:true,judgeScore:3},{id:'y',testsPass:true,judgeScore:8}]).winner.id === 'y', 'meilleure note parmi survivantes gagne')
console.log('OK helpers purs')
```
Lancer : `node $TMPDIR/test_tournoi.mjs` → attendu : « OK helpers purs », aucune AssertionError.
- [ ] **Step 2: `node --check`** sur le gabarit final → syntaxe valide.
- [ ] **Step 3: Review adversariale** (reviewer Opus) — le filtre objectif précède-t-il TOUJOURS le jury (impossible qu'un design cassé gagne) ? l'escalade est-elle bornée (pas d'infini, BLOQUER si 0 survivante) ? le coût est-il loggé à chaque escalade ? l'anti crier-au-loup (reason exigée) tient-il ? la phase Vérifier/Livrer en aval consomme-t-elle `builds` sans casser ? worktrees perdants nettoyés (harnais auto) ? Composition chantier 1 (build=DEV, juges=LECTURE) respectée ? Corriger Critical/Important.
- [ ] **Step 4: Rapport** — `scp3-task-4-report.md` : sortie du test node, `node --check`, verdict review.

---

### Task 5: Traçabilité + paquet

- [x] Consigner dans `.superpowers/sdd/progress.md` (chantier 2 complet) + section « Livraison » au plan.
- [x] Paquet public : `workflow-template.js` copié/génériqué dans `templates/skills/atelier/`, audit sécurité indépendant CLEAN, commit `18aa97e` (push = main d'Ahmed).

---

## Livraison (2026-07-07) — DÉPLOYÉE

Chantier exécuté en subagent-driven (subagents Opus 4.8), 5 tâches. Reviews adversariales Opus : T1 APPROVED 7/7, T2 APPROVED 8/8, T3 APPROVED (0 finding). Dry-run node : **17/17 assertions passées**.

**Livrable hors-git (`~/.claude/skills/atelier/workflow-template.js`, 206 lignes) :**
- **Jury adversarial de design** (T1) : l'auto-note (`sort by self-score`) remplacée par des juges LECTURE indépendants ; 4 helpers purs node-testables (`shouldEscalate`/`divergentStrategies`/`aggregateJudgeScores`/`selectWinner`).
- **Tournoi de build adaptatif** (T2) : `buildModule` fait 1 tentative puis escalade en N tentatives divergentes (worktrees) si `hard`/échec/auto-report ; sélection **objectif-avant-subjectif** (tests filtrent → jury classe les survivantes) ; `0 survivante → BLOQUER` humain ; seeding par la tentative échouée.
- **Apprentissage N3 + garde-fous** (T3) : stratégie gagnante mémorisée (`memory_store_in` → `projets/<projet>/tournois`, kind reasoning) ; pré-flag `reasoning_recall` au cadrage ; `log()` par escalade ; N∈[3,5] via budget ; anti crier-au-loup (raison exigée). + fixes M1 (escalade si `testsPass !== true`) et M2 (`s.resume` au jury).

**Preuve (dry-run) :** 17/17 assertions node — dont le garde-fou clé **prouvé par exécution** : une tentative aux tests rouges ne gagne jamais ; `0 survivante → BLOQUER`. Compat aval byte-identique (phases Vérifier/Livrer intactes). Composition chantier 1 : agents build = DEV, juges = LECTURE (`chef-de-projet`/`architecte-logiciel`).

**Contrainte d'application :** écriture vers `~/.claude/skills/` refusée par le sandbox → appliqué par `cp` du fichier proposé avec sandbox désactivé (approbation interactive d'Ahmed).

**Paquet public** (`~/Desktop/claude_code_setup`, commit `18aa97e`) : gabarit copié + exemple métier génériqué, audit indépendant CLEAN, push = main d'Ahmed.

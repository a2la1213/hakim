# Plus-values post-audit vidéo « loop engineering » — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fermer les 5 maillons manquants identifiés par l'audit grounded (workflow wf_dd46876c-895) : rendre déterministe le seed mémoire au démarrage, injecter les skills/reasoning appris, ajouter la garde objectif/subjectif, brancher une escalade quand un outil tombe, et borner le seul chemin autonome payant.

**Architecture:** Un helper unique `boot_brief(mem, now)` devient la SOURCE DE VÉRITÉ du briefing de session (santé + MDT + skills/reasoning pertinents), consommé par le tool MCP `wm_boot` ET par le CLI (`outreach` que le hook SessionStart appelle déjà). On NE touche PAS `~/.claude/settings.json` (sandbox-protégé + config d'Ahmed) : le seed passe par la commande déjà hookée. Changements de comportement global (CLAUDE.md) = prose ciblée. Escalade = détection existante (health.py/cockpit) → notification + brief SDD, humain dans la boucle (pas d'auto-réparation d'outils).

**Tech Stack:** Python 3.14 (.venv, pytest — 359 tests), MCP FastMCP, launchd, macOS `osascript` (notify), Node cockpit. CLAUDE.md = `~/.claude/CLAUDE.md`.

## Global Constraints

- **Seed de boot SERRÉ** (garde-fou anti-dégradation-de-contexte, cf. audit) : le briefing de démarrage reste court — MDT + top-1/2 skills + top-1/2 reasoning, UNE ligne chacun. Jamais un dump. Fixer un plafond de caractères.
- Tout ajout au briefing est BEST-EFFORT : un échec (skills absents, DB legacy, health en erreur) ne casse JAMAIS `wm_boot`/`outreach` (les guards try/except existent déjà — les préserver).
- Lecture seule sur les chemins de santé/escalade (health.py est contractuellement read-only) ; l'escalade ÉMET (notif/brief) mais ne répare pas.
- Anamnèse : TDD, DB temp migrée, jamais `data/memory.db`. Full suite (`.venv/bin/python -m pytest -q`) ≥ 359 avant chaque commit.
- Fichiers hors-repo (CLAUDE.md, cockpit) : diffs manuels, pas de git anamnese ; les changer avec parcimonie.
- Branche `audit-plus-values` depuis main ; merge --no-ff en fin.
- Une source de vérité : le briefing de démarrage vit dans `boot_brief`, jamais dupliqué entre MCP et CLI.

## File Structure

| Fichier | Rôle | Tâche |
|---|---|---|
| `consolidate.py:143` (modify) | `--max-turns` sur le Sonnet payé | A |
| `memory.py` (modify, +`boot_brief`) OU `boot.py` (create) | helper briefing partagé | B |
| `mcp_server.py:157` (modify) | `wm_boot` consomme `boot_brief` | B |
| `cli.py` (modify) | commande `wm-boot` + `outreach` enrichi | B |
| `memory.py::boot_brief` (extend) | injection top-1/2 skills+reasoning | C |
| `~/.claude/CLAUDE.md` (modify) | ligne skill_save (C) + règle objectif/subjectif (D) | C, D |
| `health.py` (modify) OU `escalate.py` (create) + cockpit `server.js` | pont détection→escalade | E |

---

### Task A: `--max-turns` sur le sous-agent Sonnet payé (#5)

**Files:** Modify `consolidate.py:142-144` · Test: `tests/test_consolidate_maxturns.py`

**Interfaces:** aucune nouvelle API — durcit la commande subprocess existante.

- [ ] **Step 1: Test (RED)** — vérifier que la commande claude construite inclut `--max-turns`.

```python
# tests/test_consolidate_maxturns.py
"""Le sous-agent Sonnet payé de consolidate est borné en tours (frein anti-runaway)."""
import inspect
import consolidate


def test_consolidate_command_has_max_turns():
    src = inspect.getsource(consolidate.main)
    assert "--max-turns" in src, "le run claude sonnet doit être borné en tours"
    # le timeout wall-clock existant reste (double frein)
    assert "timeout=900" in src
```

- [ ] **Step 2: RED** — `pytest tests/test_consolidate_maxturns.py -v` → FAIL (pas de --max-turns).
- [ ] **Step 3: Implémenter** — `consolidate.py:143`, ajouter `--max-turns`, `"40"` à la liste :

```python
        r = subprocess.run(
            ["claude", "-p", prompt, "--allowedTools", TOOLS, "--model", "sonnet", "--max-turns", "40"],
            cwd=str(ROOT), env=ENV, capture_output=True, text=True, timeout=900,
        )
```

- [ ] **Step 4: GREEN** — le test passe ; full suite inchangée.
- [ ] **Step 5: Commit** — `git commit -m "Frein anti-runaway: --max-turns 40 sur le Sonnet de consolidate (seul chemin autonome payant)"`

---

### Task B: `boot_brief` partagé + seed wm_boot déterministe au démarrage (#1)

**Files:** Modify `memory.py` (nouvelle méthode `boot_brief`), `mcp_server.py:157-181`, `cli.py` · Test: `tests/test_boot_brief.py`

**Interfaces:**
- Consumes: `mem.wm_boot(now) -> {focus_n, halo_n, reseeded}`, `mem.wm_focus_brief(max_items=None)`, `health.health_report(conn)` + `health.health_banner(report)`.
- Produces: `memory.py::Memory.boot_brief(self, now, cap=1200) -> str` — assemble, dans l'ordre et borné à `cap` chars : (1) banner santé (best-effort), (2) tête MDT « MDT amorcée : X focus, Y halo (re-semés Z) », (3) `wm_focus_brief`. En Task C on ajoutera skills/reasoning. Le tool MCP `wm_boot` et la CLI l'appellent tous deux.
- Produces: CLI `anamnese wm-boot` (imprime `boot_brief`) ; `anamnese outreach` enrichi (préfixe `boot_brief` PUIS les lignes « ce que j'ai en tête » existantes).

- [ ] **Step 1: Test (RED)** — `tests/test_boot_brief.py`

```python
"""boot_brief = source de vérité unique du briefing de démarrage (santé + MDT), bornée, best-effort.
DB temp migrée, jamais data/memory.db."""
import time
import pytest
import config, memory, migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.0] * 8)
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    for i in range(5):
        m.add("user", f"souvenir saillant numéro {i}", importance=0.7, embedding=[0.0] * 8)
    m.db.commit()
    yield m
    m.db.close()


def test_boot_brief_amorce_et_borne(mem):
    out = mem.boot_brief(time.time(), cap=1200)
    assert "MDT amorcée" in out                 # tête MDT présente
    assert len(out) <= 1200                       # borné (anti-bloat)


def test_boot_brief_best_effort_db_legacy(tmp_path, monkeypatch):
    # DB sans working_memory/kv santé : ne lève pas, renvoie qqch de propre
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.0] * 8)
    m = Memory(db_path=tmp_path / "leg.db")
    migrations.migrate(m.db)
    out = m.boot_brief(time.time())
    assert isinstance(out, str)                    # jamais d'exception
    m.db.close()


def test_cli_wm_boot_and_outreach(tmp_path, monkeypatch, capsys):
    import sys, cli
    import memory as memory_mod, embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.0] * 8)

    class TmpMemory(Memory):
        def __init__(self):
            super().__init__(db_path=tmp_path / "c.db")
            migrations.migrate(self.db)
            self.add("user", "contexte de reprise batiment", importance=0.8, embedding=[0.0] * 8)
            self.db.commit()
    monkeypatch.setattr(memory_mod, "Memory", TmpMemory)
    monkeypatch.setattr(sys, "argv", ["anamnese", "wm-boot"])
    cli.main()
    assert "MDT amorcée" in capsys.readouterr().out
    # outreach porte MAINTENANT le seed en tête
    monkeypatch.setattr(sys, "argv", ["anamnese", "outreach"])
    cli.main()
    assert "MDT amorcée" in capsys.readouterr().out
```

- [ ] **Step 2: RED** — `pytest tests/test_boot_brief.py -v` → FAIL (`boot_brief` absent, `wm-boot` inconnu).

- [ ] **Step 3: Implémenter `memory.py::boot_brief`** (près de `wm_focus_brief`, ~ligne 888) :

```python
    def boot_brief(self, now, cap=1200):
        """Briefing de DÉMARRAGE — source de vérité unique (santé + MDT amorcée).
        Best-effort : chaque bloc est gardé ; un échec ne casse jamais le briefing.
        Borné à `cap` chars (garde anti-dégradation-de-contexte). Task C ajoute
        skills/reasoning."""
        parts = []
        try:
            import health
            banner = health.health_banner(health.health_report(self.db))
            if banner:
                parts.append(banner)
        except Exception:
            pass
        try:
            res = self.wm_boot(now)
            parts.append(f"MDT amorcée : {res['focus_n']} en focus, {res['halo_n']} en halo "
                         f"(re-semés : {res['reseeded']}).")
            brief = self.wm_focus_brief()
            if brief:
                parts.append(brief)
        except Exception as e:
            parts.append("MDT amorcée (briefing dégradé).")
        out = "\n\n".join(parts)
        return out[:cap]
```

- [ ] **Step 4: Refactor `mcp_server.py:157` `wm_boot`** pour consommer `boot_brief` (comportement préservé) :

```python
@mcp.tool()
def wm_boot() -> str:
    """Amorce la MDT au démarrage — le « walk in knowing ». Source de vérité : boot_brief."""
    return _mem.boot_brief(time.time())
```
(supprimer le corps dupliqué banner/head/_wm_brief de wm_boot ; `_wm_brief`/`working_memory` restent inchangés.)

- [ ] **Step 5: CLI** — dans `cli.py`, ajouter la commande `wm-boot` et enrichir `outreach` :

```python
    elif cmd == "wm-boot":
        import time as _t
        print(m.boot_brief(_t.time()))
```
Et au TOUT DÉBUT de la branche `outreach` (avant le SELECT existant), préfixer le seed :
```python
    elif cmd == "outreach":
        import time as _t
        seed = m.boot_brief(_t.time())
        if seed:
            print(seed); print()
        rows = m.db.execute(
            "SELECT ts, role, content FROM episodes "
            "WHERE role IN ('outreach','reflection','thought') ORDER BY ts DESC LIMIT 5"
        ).fetchall()
        ...  # (reste inchangé)
```
Ajouter la ligne d'usage `anamnese wm-boot   amorce la MDT (walk in knowing)` à la docstring.

- [ ] **Step 6: GREEN + full suite** — `pytest tests/test_boot_brief.py -v` puis `pytest -q` (≥ 360).
- [ ] **Step 7: Vérif réelle** — `./anamnese wm-boot` et `./anamnese outreach` impriment le banner santé + « MDT amorcée » + focus. (Le hook SessionStart appelle `outreach` → seed désormais garanti.)
- [ ] **Step 8: Commit** — `git commit -m "Seed wm_boot déterministe au démarrage : boot_brief partagé (MCP+CLI), porté par le hook via outreach (plus de dépendance au protocole)"`

---

### Task C: Injecter skills + reasoning appris + fixer le double-boot + capture skill_save (#4 + findings review B)

**Files:** Modify `memory.py::boot_brief`, `~/.claude/CLAUDE.md`, `tests/test_boot_brief.py` · Report: corriger la claim d'idempotence du rapport B.

**Contexte des findings review B (à traiter ici) :**
- **IMPORTANT — double-boot** : aujourd'hui le hook SessionStart (`outreach` → `boot_brief` → `wm_boot`) ET le protocole CLAUDE.md (qui me fait appeler le tool MCP `wm_boot`) exécutent wm_boot DEUX fois par session → double décroissance ×0.85² du `wm_touch` de re-semis (prouvé : 0.90→0.765→0.650). **Fix = retirer l'obligation d'appeler wm_boot du protocole CLAUDE.md** : le hook le garantit désormais (c'était tout le but de #1), donc au démarrage le seed est DÉJÀ en contexte. Résultat : exactement UN boot par session.
- **MINOR ordre/cap** : Task C ajoute des hints sous le MÊME `cap` que le focus (long) → si on les met après le focus, le cap les coupe. **Ordre imposé** : banner → tête MDT → **hints (skills/reasoning)** → liste focus. Et **tronquer par LIGNES entières** (pas mi-mot).
- **MINOR tests** : ajouter des tests adversariaux du cap (focus énorme) et des branches dégradées (health KO, wm_boot KO).

**Interfaces:**
- Consumes: `mem.list_skills() -> [(name, description), ...]`, `mem.retrieve(query, emb, top_k, kinds=["reasoning"])`, `mem.wm_focus_brief()` (pour dériver une requête depuis le focus).
- Produces: `boot_brief` gagne une section « À réutiliser » (top-2 skills + top-1 reasoning, une ligne chacun) placée AVANT le focus ; troncature par lignes ; CLAUDE.md : ligne skill_save + protocole de démarrage corrigé (plus d'appel wm_boot MCP obligatoire).

- [ ] **Step 1: Test (RED)** — ajouter à `tests/test_boot_brief.py` :

```python
def test_boot_brief_injecte_skills_et_reasoning(tmp_path, monkeypatch):
    import embeddings, migrations
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.1] * 8)
    m = Memory(db_path=tmp_path / "s.db")
    migrations.migrate(m.db)
    m.add("user", "je travaille sur le routage TVA batiment", importance=0.9, embedding=[0.1] * 8)
    m.save_skill("tva-batiment", "calcul TVA chantier", "procédure : ...")
    m.add("reasoning", "problème TVA → étapes → décision : appliquer 10%", importance=0.8, embedding=[0.1] * 8)
    m.db.commit()
    out = m.boot_brief(__import__("time").time(), cap=2000)
    assert "tva-batiment" in out or "compétence" in out.lower()   # au moins une skill remonte
    assert len(out) <= 2000                                        # toujours borné
```

- [ ] **Step 2: RED** → FAIL (skills/reasoning pas dans le briefing).

- [ ] **Step 2b: Tests adversariaux (cap + dégradé)** — ajouter à `tests/test_boot_brief.py` :

```python
def test_boot_brief_cap_tronque_par_lignes_et_garde_hints(tmp_path, monkeypatch):
    import embeddings, migrations, time as _t
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.1] * 8)
    m = Memory(db_path=tmp_path / "big.db")
    migrations.migrate(m.db)
    for i in range(40):                                  # focus énorme → force le cap
        m.add("user", f"souvenir de continuité tres long numero {i} " * 4, importance=0.9, embedding=[0.1] * 8)
    m.save_skill("proc-cle", "procédure clé à ne pas perdre", "…")
    m.db.commit()
    out = m.boot_brief(_t.time(), cap=800)
    assert len(out) <= 800                                # borné
    assert "\n" in out and not out.endswith(" ")          # tronqué par lignes, pas un mot coupé net
    assert "proc-cle" in out or "réutiliser" in out.lower()  # les hints survivent au cap (placés avant le focus)


def test_boot_brief_degrade_sans_exception(tmp_path, monkeypatch):
    import embeddings, migrations, time as _t
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.1] * 8)
    m = Memory(db_path=tmp_path / "deg.db")
    migrations.migrate(m.db)
    monkeypatch.setattr(Memory, "wm_boot", lambda self, now: (_ for _ in ()).throw(RuntimeError("boom")))
    out = m.boot_brief(_t.time())                          # wm_boot KO → dégradé, jamais d'exception
    assert isinstance(out, str) and "dégradé" in out.lower()
    m.db.close()
```

- [ ] **Step 3: Étendre `boot_brief`** — insérer les hints AVANT le focus (pour survivre au cap), tronquer par LIGNES. Structure recommandée : construire `parts` dans l'ordre [banner, tête MDT, hints, focus], puis tronquer par lignes jusqu'à `cap` :

```python
        # bloc hints (BEST-EFFORT, TIGHT) — À PLACER dans `parts` AVANT la liste focus
        try:
            import embeddings as _emb
            q = (self.wm_focus_brief() or "")[:200]
            hints = []
            for name, desc in (self.list_skills() or [])[:2]:
                hints.append(f"• compétence {name} : {desc[:80]}")
            if q.strip():
                rr = self.retrieve(q, _emb.embed(q), top_k=1, kinds=["reasoning"])
                for sc, _ts, _r, content, _p in rr:
                    hints.append(f"• raisonnement éprouvé : {content[:120]}")
            if hints:
                parts.append("À réutiliser :\n" + "\n".join(hints))
        except Exception:
            pass
        # ... puis APRÈS, ajouter le focus brief à parts (déplacer l'append focus ici si besoin)
        # Troncature PAR LIGNES (pas mi-mot) :
        out, lines = "", "\n\n".join(parts).split("\n")
        for ln in lines:
            if len(out) + len(ln) + 1 > cap:
                break
            out += (("\n" if out else "") + ln)
        return out
```
(Ordre des sections IMPORTANT : banner → tête MDT → hints → focus, pour que les hints survivent au cap. Sélection skills top-2 volontairement simple — matching par tags = amélioration future, YAGNI. Le plafond protège du bloat.)

- [ ] **Step 4: GREEN + full suite** (viser ≥ 366 avec les nouveaux tests).

- [ ] **Step 5: CLAUDE.md — deux edits** (fichier `~/.claude/CLAUDE.md`, hors git anamnese) :
  1. Section « ## Bibliothèque de raisonnement » : ajouter
  > - Quand une réponse de l'utilisateur DÉBLOQUE une tâche que je ne savais pas faire (ex. les critères de test/d'acceptation), `mcp__anamnese__skill_save` la procédure, taggée par type de tâche — pour qu'elle re-surgisse au prochain cas (l'agent apprend tes procédures).
  2. **FIX DOUBLE-BOOT** — section « ## Au démarrage » : le seed MDT est désormais AUTO-INJECTÉ par le hook SessionStart (via `anamnese outreach` → `boot_brief`). Retirer/adoucir l'obligation d'appeler `wm_boot` au démarrage : remplacer « Au tout début : `mcp__anamnese__wm_boot` … puis `self_get`, puis `memory_recall` » par une formulation où le seed wm_boot est DÉJÀ dans le contexte (injecté par le hook), donc au démarrage j'appelle seulement `self_get` + `memory_recall` sur le sujet courant ; `wm_boot` (MCP) reste disponible pour un RE-boot manuel en cours de session, pas au démarrage. Objectif : exactement UN boot par session (supprime le double-boot ×0.85² du finding review B).

- [ ] **Step 6: Corriger le rapport B** — dans `.superpowers/sdd/apv-task-B-report.md`, noter que la claim « updated_ts protège du double-boot » ne couvrait PAS la décroissance `WM_DECAY` du re-semis, désormais résolue par le fix protocole (un seul boot/session).

- [ ] **Step 6: Commit** — `git commit -m "Boucle d'apprentissage fermée : boot_brief ré-injecte skills/reasoning pertinents (borné) + protocole skill_save à l'unblock"` (+ noter l'edit CLAUDE.md dans le rapport, hors git).

---

### Task D: Règle objectif/subjectif dans CLAUDE.md (#2)

**Files:** Modify `~/.claude/CLAUDE.md` (section « ## Vérification », ~lignes 18-20). Prose seule — pas de test (review humaine/agent).

**Interfaces:** aucune. Change le comportement global des sessions Claude Code.

- [ ] **Step 1: Ajouter** à la section « ## Vérification », après la ligne d'ancrage outillé :
> - Avant de finaliser une tâche non-triviale, CLASSER son critère de succès : **objectif** (une commande/un test le prouve → l'écrire, l'exécuter, montrer la sortie) ou **subjectif** (aucune mesure automatique — droit, analyse, rédaction, design). Si subjectif : NE PAS s'auto-noter « fait » sur mon seul jugement — m'arrêter et demander à l'utilisateur les **critères d'acceptation** avant de continuer. (« Je ne peux pas vérifier sans X → je demande la direction. »)

- [ ] **Step 2: Cohérence** — vérifier que le ton/format colle au reste de CLAUDE.md (puces, 1re personne, « je »). Scope : « tâche non-triviale » (ne pas rendre l'agent interruptif sur du trivial).
- [ ] **Step 3: Rapport** — consigner l'edit dans `.superpowers/sdd/audit-plus-values-report.md` (CLAUDE.md hors git).

---

### Task E: Pont détection → escalade quand un outil tombe (#3)

**Files:** Create `escalate.py` (anamnese) · Modify `health.py` (appel best-effort depuis le bilan) · optionnel cockpit `server.js` (signal) · Test: `tests/test_escalate.py`

**Interfaces:**
- Consumes: la structure de `health.health_report(conn)` (warnings/notes existants, health.py:119-206) ; `daemon.notify(title, message)` (osascript macOS, best-effort) — réutiliser ce helper (ou le répliquer dans escalate.py pour éviter d'importer daemon).
- Produces: `escalate.py::escalate(report, brief_dir) -> dict {notified: bool, brief_path: str|None}` — si le rapport contient un problème actionnable (daemon down, consolidation stale, backup manquant, [extensible : MCP auth]), (1) émet UNE notification macOS, (2) écrit un brief de diagnostic au format SDD dans `brief_dir` (que l'humain lance en 1 clic). BEST-EFFORT, jamais d'exception. Dédup : ne pas re-notifier/re-brief le même problème (garde par hash dans kv ou fichier marqueur).

- [ ] **Step 1: Test (RED)** — `tests/test_escalate.py`

```python
"""Escalade : un problème de santé actionnable → notification (mockée) + brief SDD. Best-effort."""
import escalate


def test_escalate_ecrit_un_brief(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(escalate, "notify", lambda t, m: calls.append((t, m)))
    report = {"problems": [{"key": "daemon_down", "msg": "daemon Anamnèse arrêté"}]}
    r = escalate.escalate(report, brief_dir=tmp_path)
    assert r["notified"] is True and calls                       # notif émise
    assert r["brief_path"] and (tmp_path / r["brief_path"]).exists()  # brief écrit
    body = (tmp_path / r["brief_path"]).read_text()
    assert "daemon" in body.lower()


def test_escalate_dedup_et_sain_si_rien(tmp_path, monkeypatch):
    monkeypatch.setattr(escalate, "notify", lambda t, m: None)
    assert escalate.escalate({"problems": []}, brief_dir=tmp_path)["notified"] is False  # rien à faire
    rep = {"problems": [{"key": "backup_missing", "msg": "pas de backup 26h"}]}
    escalate.escalate(rep, brief_dir=tmp_path)
    r2 = escalate.escalate(rep, brief_dir=tmp_path)              # 2e fois = dédup
    assert r2["notified"] is False
```

- [ ] **Step 2: RED** → FAIL (`escalate` absent).

- [ ] **Step 3: Implémenter `escalate.py`** — `notify()` (osascript, best-effort try/except), `escalate(report, brief_dir)` : filtrer les `problems` actionnables, garde de dédup (fichier marqueur `.escalated/<hash>` dans brief_dir), émettre notif + écrire `escalate-<key>-brief.md` (gabarit SDD : contexte, symptôme, commande de diagnostic suggérée, « lance-moi en 1 clic »). Retour `{notified, brief_path}`. Aucune exception ne remonte.

- [ ] **Step 4: Brancher (best-effort) dans `health.py`** — là où le bilan est produit (le banner), appeler `escalate.escalate(report, ...)` sous try/except pour que la détection déjà calculée déclenche l'escalade. NE PAS rendre health.py bloquant ni écrivant hors du brief/marqueur.

- [ ] **Step 5: GREEN + full suite** (≥ 362).

- [ ] **Step 6: (optionnel) cockpit** — noter dans le rapport que le cockpit pourrait afficher un badge « escalade en attente » en lisant `.escalated/` ; hors périmètre si le temps manque (le brief + notif suffisent).

- [ ] **Step 7: Commit** — `git commit -m "Escalade proactive : santé → notification + brief SDD quand un outil tombe (détection existante, humain dans la boucle, dédup)"`

---

### Task F: Merge + vérif finale

- [ ] Full suite verte. `git checkout main && git merge --no-ff audit-plus-values`.
- [ ] Relancer le daemon (kickstart) pour qu'il prenne `--max-turns` + boot_brief.
- [ ] Vérif réelle : ouvrir une nouvelle session Claude Code → le hook `outreach` injecte le seed wm_boot complet (banner + MDT + à-réutiliser). Consigner dans `.superpowers/sdd/audit-plus-values-report.md`.

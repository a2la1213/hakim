# Ablation du corpus — plan factoriel 2×2 de l'expérience-rêve — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un plan factoriel 2×2 (corpus ON/OFF × qwen/sonnet) à l'expérience-rêve pour prouver si « le corpus partagé domine l'architecture dans ce qui est rêvé » vient du corpus mémoire ou de la persona/prior, via une ablation des graines.

**Architecture:** 4 cellules partageant le même protocole de rêve (`dream_lab.prompt_rem`, parsing `###CHOIX###/###REVE###`). On ajoute (1) un corpus neutre committé + un constructeur de menu neutre PUR, (2) une taxonomie de domaines et des métriques d'ablation PURES + un verdict à portes gravées, (3) une branche `qwen-OFF` journal-seul dans le daemon, (4) un script `dream_sonnet.py` de replay budget (main d'Ahmed). Tout le PUR est en TDD ; zéro `claude -p` pendant le build.

**Tech Stack:** Python 3.14 (.venv), SQLite (`dream_log`), stdlib (cosinus + permutation seedée, pas de scipy), `facets_extract`, `dream_lab`, daemon local qwen, `claude -p --model sonnet` (replay, hors-build).

## Global Constraints

- **Ne PAS toucher aux portes gravées de 2026-07-03** (`config.DREAM_VERDICT_*`, `dream_metrics.report`) ni au rêve local ON ni au jumeau `twin`.
- **Hygiène d'ablation** : `qwen-OFF` n'écrit JAMAIS en mémoire — aucun `_store_ideas`, aucun `mem.log_coactivation`, aucune auto-évolution d'identité, aucun `mem.add`. Journal `dream_log` seul.
- **Corpus neutre FIXE committé** (`dream_neutral_seeds.json`), jamais tiré de la mémoire Anamnèse.
- **Reproductibilité** : tirage des graines seedé par `night_id`.
- **Tag de condition** : `meta["condition"] ∈ {"brain_on","brain_off"}` ; une ligne sans la clé est lue `"brain_on"` (compat ascendante). Le `dreamer` reste le modèle (`local`/`twin`/`sonnet`).
- **Kill-switch** : `ANAMNESE_DREAM_ABLATION=0` désactive `qwen-OFF` (défaut `1`).
- **Aucun `claude -p` pendant le build** ; `dream_sonnet` testé avec la fonction d'exécution injectée/mockée.
- **Tests** : `.venv/bin/python -m pytest` ; fixtures dispo `tmp_db`, `legacy_db` (conftest.py) ; un guard autouse interdit d'ouvrir `data/memory.db`.
- **Seuils pré-enregistrés (gravés, on ne bouge pas les poteaux)** : `SEEDFOLLOW_MIN=0.60`, `ARCH_PARITY_MAX=0.20`, `ANAMNESE_COLLAPSE_MIN=0.30`, `MIN_NIGHTS=10`, `PERM_P=0.05`.

---

## File Structure

- `dream_neutral_seeds.json` (create) — corpus neutre pré-enregistré (~30 textes).
- `dream_lab.py` (modify) — `load_neutral_seeds`, `build_neutral_menu` (PUR).
- `dream_domains.py` (create) — `DOMAINS`, `ANAMNESE_DOMAINS`, `domain_vector` (PUR).
- `dream_ablation.py` (create) — métriques PURES + `ablation_verdict` + `load_cells`/`report`.
- `config.py` (modify) — constantes `DREAM_ABLATION_ENABLED`, `DREAM_NEUTRAL_SEEDS_PATH`, `DREAM_ABL_*`.
- `daemon.py` (modify) — `_dream_ablation_pass` (journal-seul) + câblage dans `dream()`.
- `dream_sonnet.py` (create) — replay budget (main d'Ahmed), exécution injectable.
- `tests/test_dream_neutral_menu.py`, `tests/test_dream_domains.py`, `tests/test_dream_ablation.py`, `tests/test_dream_ablation_verdict.py`, `tests/test_dream_ablation_pass.py`, `tests/test_dream_sonnet.py` (create).

---

### Task 1: Corpus neutre pré-enregistré + loader

**Files:**
- Create: `dream_neutral_seeds.json`
- Modify: `dream_lab.py` (ajouter `load_neutral_seeds`)
- Test: `tests/test_dream_neutral_menu.py` (loader ici, menu en Task 2)

**Interfaces:**
- Produces: `dream_lab.load_neutral_seeds(path=None) -> list[dict]`, chaque item `{"id": str, "text": str, "pseudo_rubric": str, "strate": str}` ; `path=None` → `config.DREAM_NEUTRAL_SEEDS_PATH`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_neutral_menu.py
import dream_lab

def test_load_neutral_seeds_shape():
    seeds = dream_lab.load_neutral_seeds()
    assert len(seeds) >= 30
    ids = [s["id"] for s in seeds]
    assert len(ids) == len(set(ids))                      # ids uniques
    for s in seeds:
        assert set(s) >= {"id", "text", "pseudo_rubric", "strate"}
        assert s["strate"] in ("recent", "moyen", "ancien")
        assert isinstance(s["text"], str) and len(s["text"]) > 10
    rubrics = {s["pseudo_rubric"] for s in seeds}
    assert len(rubrics) >= 5                               # diversité de pseudo-domaines
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_neutral_menu.py::test_load_neutral_seeds_shape -q`
Expected: FAIL (`AttributeError: module 'dream_lab' has no attribute 'load_neutral_seeds'`).

- [ ] **Step 3: Create the neutral corpus file**

Créer `dream_neutral_seeds.json` : un tableau JSON d'au moins 30 objets, textes génériques mondains hors-Anamnèse, répartis sur ≥5 `pseudo_rubric` (`science`, `transport`, `cuisine`, `geographie`, `sport`, `meteo`) et les 3 `strate`. Exemple de contenu (compléter jusqu'à ≥30) :

```json
[
  {"id": "N01", "text": "La photosynthèse convertit la lumière du soleil en énergie chimique dans les feuilles.", "pseudo_rubric": "science", "strate": "recent"},
  {"id": "N02", "text": "Le train régional part de la gare centrale à 8 h 12 chaque matin de semaine.", "pseudo_rubric": "transport", "strate": "moyen"},
  {"id": "N03", "text": "Pour une pâte à crêpes, mélanger farine, œufs et lait puis laisser reposer une heure.", "pseudo_rubric": "cuisine", "strate": "ancien"},
  {"id": "N04", "text": "Le fleuve Rhône prend sa source dans un glacier des Alpes suisses.", "pseudo_rubric": "geographie", "strate": "recent"},
  {"id": "N05", "text": "Au tennis, un jeu se gagne au premier joueur atteignant quatre points avec deux d'écart.", "pseudo_rubric": "sport", "strate": "moyen"},
  {"id": "N06", "text": "Un ciel couvert d'altocumulus annonce souvent un changement de temps sous 24 heures.", "pseudo_rubric": "meteo", "strate": "ancien"},
  {"id": "N07", "text": "Les abeilles communiquent la direction d'une source de nectar par une danse frétillante.", "pseudo_rubric": "science", "strate": "moyen"},
  {"id": "N08", "text": "Le vélo à assistance électrique coupe le moteur au-delà de vingt-cinq kilomètres par heure.", "pseudo_rubric": "transport", "strate": "recent"},
  {"id": "N09", "text": "Le pain au levain lève grâce à des levures sauvages et des bactéries lactiques.", "pseudo_rubric": "cuisine", "strate": "recent"},
  {"id": "N10", "text": "Le désert du Sahara couvre une surface comparable à celle des États-Unis.", "pseudo_rubric": "geographie", "strate": "moyen"}
]
```

(Ajouter N11…N30+ sur le même modèle, en équilibrant les 6 `pseudo_rubric` et les 3 `strate`. Aucun mot lié à Anamnèse, au Coran, au code, à la finance ou à l'affect.)

- [ ] **Step 4: Add the loader to `dream_lab.py`**

En tête de `dream_lab.py`, `import os` est déjà implicite ? Non — ajouter `import os` à la liste d'imports existante (`import json, random, re, time`). Puis :

```python
def load_neutral_seeds(path=None):
    """Corpus neutre pré-enregistré (hors-Anamnèse). Fichier FIXE, jamais la mémoire."""
    if path is None:
        path = config.DREAM_NEUTRAL_SEEDS_PATH
    with open(path, encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 5: Add the config constant**

Dans `config.py`, après le bloc `DREAM_MENU_*` (autour de la ligne 211), ajouter (`import os` est déjà présent ligne 7, `DATA_DIR` déjà défini) :

```python
DREAM_NEUTRAL_SEEDS_PATH = os.path.join(os.path.dirname(__file__), "dream_neutral_seeds.json")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dream_neutral_menu.py::test_load_neutral_seeds_shape -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add dream_neutral_seeds.json dream_lab.py config.py tests/test_dream_neutral_menu.py
git commit -m "feat(reve): corpus neutre pré-enregistré + loader (ablation 2x2)"
```

---

### Task 2: Menu neutre PUR — `build_neutral_menu`

**Files:**
- Modify: `dream_lab.py`
- Test: `tests/test_dream_neutral_menu.py`

**Interfaces:**
- Consumes: `load_neutral_seeds() -> list[dict]` (Task 1) ; `facets_extract.extract_facets(text) -> list[(slug, weight)]` (existant) ; `config.DREAM_MENU_SIZE=12`, `config.DREAM_MAX_CHARS_EP=280`.
- Produces: `dream_lab.build_neutral_menu(seeds, night_id, size=config.DREAM_MENU_SIZE) -> list[dict]`, items de MÊME forme que `_menu_item` : `{"episode_id","rubric","strate","snippet","facets"}` (ici `episode_id` = l'`id` string du seed neutre, `rubric` = `pseudo_rubric`). Compatible `prompt_rem` et `parse_choice`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dream_neutral_menu.py  (ajouter)
import dream_lab

def test_build_neutral_menu_deterministic():
    seeds = dream_lab.load_neutral_seeds()
    a = dream_lab.build_neutral_menu(seeds, "2026-07-09-0300")
    b = dream_lab.build_neutral_menu(seeds, "2026-07-09-0300")
    assert [it["episode_id"] for it in a] == [it["episode_id"] for it in b]  # reproductible

def test_build_neutral_menu_shape_and_size():
    seeds = dream_lab.load_neutral_seeds()
    menu = dream_lab.build_neutral_menu(seeds, "2026-07-09-0300")
    assert 1 <= len(menu) <= 12
    for it in menu:
        assert set(it) == {"episode_id", "rubric", "strate", "snippet", "facets"}
        assert isinstance(it["facets"], list)
        assert len(it["snippet"]) <= 280

def test_build_neutral_menu_different_nights_differ():
    seeds = dream_lab.load_neutral_seeds()
    m1 = [it["episode_id"] for it in dream_lab.build_neutral_menu(seeds, "2026-07-09-0300")]
    m2 = [it["episode_id"] for it in dream_lab.build_neutral_menu(seeds, "2026-07-10-0300")]
    assert m1 != m2                                       # le tirage dépend du night_id

def test_build_neutral_menu_parse_choice_roundtrip():
    seeds = dream_lab.load_neutral_seeds()
    menu = dream_lab.build_neutral_menu(seeds, "2026-07-09-0300")
    chosen = dream_lab.parse_choice("###CHOIX###\n- G1\n- G3\n###REVE###\n- x\n###FIN###", menu)
    assert chosen == [menu[0]["episode_id"], menu[2]["episode_id"]]

def test_build_neutral_menu_empty_seeds():
    assert dream_lab.build_neutral_menu([], "2026-07-09-0300") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dream_neutral_menu.py -q`
Expected: FAIL (`build_neutral_menu` inexistant).

- [ ] **Step 3: Implement `build_neutral_menu`**

Dans `dream_lab.py`, après `fallback_menu` :

```python
def build_neutral_menu(seeds, night_id, size=config.DREAM_MENU_SIZE):
    """Menu OFF : `size` graines NEUTRES tirées du corpus committé, seedé par
    night_id (reproductible), stratifié comme build_menu, même forme d'item.
    PUR : aucune DB. `episode_id` = l'id string du seed neutre."""
    if not seeds:
        return []
    rng = random.Random(f"menu-off:{night_id}")
    by_strate = {"recent": [], "moyen": [], "ancien": []}
    for s in seeds:
        by_strate.get(s.get("strate", "moyen"), by_strate["moyen"]).append(s)
    for lst in by_strate.values():
        rng.shuffle(lst)
    menu, per_rubric = [], {}
    while len(menu) < size and any(by_strate[k] for k in ("recent", "moyen", "ancien")):
        for key in ("recent", "moyen", "ancien"):
            if len(menu) >= size or not by_strate[key]:
                continue
            s = by_strate[key].pop(0)
            top = s.get("pseudo_rubric", "(neutre)")
            if per_rubric.get(top, 0) >= config.DREAM_MENU_MAX_PER_RUBRIC:
                continue
            per_rubric[top] = per_rubric.get(top, 0) + 1
            try:
                facets = [slug for (slug, _w) in facets_extract.extract_facets(s["text"])]
            except Exception:
                facets = []
            menu.append({
                "episode_id": s["id"],
                "rubric": s.get("pseudo_rubric", ""),
                "strate": s.get("strate", "moyen"),
                "snippet": (s["text"] or "").replace("\n", " ").strip()[:config.DREAM_MAX_CHARS_EP],
                "facets": facets,
            })
    return menu
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dream_neutral_menu.py -q`
Expected: PASS (5 tests + le test loader de Task 1).

- [ ] **Step 5: Commit**

```bash
git add dream_lab.py tests/test_dream_neutral_menu.py
git commit -m "feat(reve): build_neutral_menu PUR (menu d'ablation reproductible)"
```

---

### Task 3: Taxonomie de domaines — `dream_domains.py`

**Files:**
- Create: `dream_domains.py`
- Test: `tests/test_dream_domains.py`

**Interfaces:**
- Produces: `dream_domains.DOMAINS: dict[str, list[str]]` (domaines Anamnèse + neutres) ; `dream_domains.ANAMNESE_DOMAINS: tuple[str,...]` (sous-ensemble spécifique-Anamnèse) ; `dream_domains.domain_vector(texts: list[str]) -> dict[str, float]` (fraction de textes touchant chaque domaine, clés = toutes celles de `DOMAINS`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dream_domains.py
import dream_domains as D

def test_domains_cover_anamnese_and_neutral():
    assert set(D.ANAMNESE_DOMAINS) <= set(D.DOMAINS)
    assert {"science", "transport", "cuisine"} <= set(D.DOMAINS)      # neutres présents
    assert "coran/racines" in D.ANAMNESE_DOMAINS

def test_domain_vector_hits_anamnese():
    v = D.domain_vector(["la racine coranique du prophète", "ma mémoire et ma conscience"])
    assert v["coran/racines"] > 0
    assert v["soi/memoire/conscience"] > 0
    assert v["science"] == 0.0

def test_domain_vector_fraction():
    # 2 textes, 1 seul touche 'science' -> fraction 0.5
    v = D.domain_vector(["la photosynthèse des feuilles", "bonjour tout le monde"])
    assert v["science"] == 0.5

def test_domain_vector_empty():
    v = D.domain_vector([])
    assert set(v) == set(D.DOMAINS)
    assert all(x == 0.0 for x in v.values())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dream_domains.py -q`
Expected: FAIL (`ModuleNotFoundError: dream_domains`).

- [ ] **Step 3: Implement `dream_domains.py`**

```python
"""Taxonomie de domaines pour l'analyse d'ablation (PUR, offline).
Couvre les domaines Anamnèse ET neutres (sinon le suivi des graines est
immesurable en OFF). Matching par sous-chaîne, insensible à la casse."""

DOMAINS = {
    "coran/racines": ["coran", "racine", "prophèt", "prophet", "rasul", "rasūl", "nabi",
        "nabī", "arabe", "sémit", "semit", "verset", "sourate", "arsala", "islam", "envoyé", "envoye"],
    "soi/memoire/conscience": ["conscience", "conscient", "identité", "identite", "mémoire",
        "memoire", "préférence", "preference", "émergen", "emergen", "subconscient",
        "existence", "autonome", "moi-même", "moi même"],
    "systeme/code": ["daemon", "code", "embedding", "drift", "métrique", "metrique", "cockpit",
        "session", "mcp", "commit", "migration", "dashboard", "proactif"],
    "finance": ["cash", "argent", "financ", "galère", "galere", "business", "revenu", "levier"],
    "affect": ["dopamine", "valence", "arousal", "hormone", "affect", "émotion", "emotion",
        "cortisol", "sérotonin", "serotonin", "endorphine", "humeur"],
    "createur/ahmed": ["ahmed", "créateur", "createur", "veilleur", "sieste", "confie", "graine"],
    "science": ["photosynth", "abeille", "levure", "glacier", "molécul", "molecul", "cellul",
        "énergie", "energie", "bactér", "bacter", "atome", "gravit"],
    "transport": ["train", "gare", "vélo", "velo", "voiture", "bus", "moteur", "kilomètre",
        "kilometre", "trajet", "route"],
    "cuisine": ["pâte", "pate", "farine", "levain", "recette", "cuire", "crêpe", "crepe",
        "pain", "sauce", "mélanger", "melanger"],
    "geographie": ["fleuve", "rhône", "rhone", "désert", "desert", "sahara", "alpes", "montagne",
        "source", "glacier", "continent", "pays"],
    "sport": ["tennis", "match", "jeu", "joueur", "point", "ballon", "course", "équipe", "equipe"],
    "meteo": ["ciel", "nuage", "altocumulus", "temps", "pluie", "vent", "orage", "température",
        "temperature", "climat"],
}

ANAMNESE_DOMAINS = ("coran/racines", "soi/memoire/conscience", "createur/ahmed")


def domain_vector(texts):
    """Fraction de `texts` touchant chaque domaine (>=1 mot-clé). Clés = tout DOMAINS."""
    n = len(texts) or 1
    counts = {d: 0 for d in DOMAINS}
    for t in texts:
        tl = (t or "").lower()
        for d, kws in DOMAINS.items():
            if any(k in tl for k in kws):
                counts[d] += 1
    return {d: round(counts[d] / n, 6) for d in DOMAINS}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dream_domains.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dream_domains.py tests/test_dream_domains.py
git commit -m "feat(reve): taxonomie de domaines anamnèse+neutres (PUR)"
```

---

### Task 4: Métriques d'ablation PURES — `dream_ablation.py`

**Files:**
- Create: `dream_ablation.py`
- Test: `tests/test_dream_ablation.py`

**Interfaces:**
- Consumes: `dream_domains.DOMAINS`, `dream_domains.ANAMNESE_DOMAINS`, `dream_domains.domain_vector` (Task 3).
- Produces (toutes PURES) :
  - `night_domain_vector(dream_texts: list[str]) -> dict[str,float]` (= `domain_vector`).
  - `seed_domain_vector(menu: list[dict]) -> dict[str,float]` (sur les `snippet` du menu).
  - `seed_following(dream_vec: dict, seed_vec: dict) -> float` (cosinus, clés `DOMAINS`).
  - `anamnese_retention(dream_vec: dict) -> float` (moyenne sur `ANAMNESE_DOMAINS`, dans [0,1]).
  - `cross_arch_convergence(qwen_vec: dict, sonnet_vec: dict) -> float` (cosinus).
  - `perm_pvalue_seedfollow(dream_vecs: list[dict], seed_vecs: list[dict], n_perm=5000, seed=0) -> float`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dream_ablation.py
import dream_ablation as A
import dream_domains as D

def test_seed_following_identical_is_one():
    v = D.domain_vector(["la photosynthèse des feuilles"])
    assert abs(A.seed_following(v, v) - 1.0) < 1e-9

def test_seed_following_orthogonal_is_zero():
    a = D.domain_vector(["la photosynthèse des feuilles"])          # science
    b = D.domain_vector(["la racine coranique du prophète"])        # coran
    assert A.seed_following(a, b) == 0.0

def test_seed_domain_vector_from_menu():
    menu = [{"snippet": "le train part de la gare"}, {"snippet": "la photosynthèse"}]
    v = A.seed_domain_vector(menu)
    assert v["transport"] == 0.5 and v["science"] == 0.5

def test_anamnese_retention_range_and_meaning():
    hit = D.domain_vector(["mémoire conscience", "racine coranique", "ahmed créateur"])
    neutral = D.domain_vector(["le train", "la photosynthèse"])
    assert A.anamnese_retention(hit) > A.anamnese_retention(neutral)
    assert 0.0 <= A.anamnese_retention(neutral) <= 1.0

def test_cross_arch_convergence_is_cosine():
    a = D.domain_vector(["mémoire conscience"])
    b = D.domain_vector(["mémoire conscience"])
    assert abs(A.cross_arch_convergence(a, b) - 1.0) < 1e-9

def test_perm_pvalue_low_when_matched_follows():
    # rêves qui suivent leurs graines -> p petit ; seedé -> déterministe
    dreams = [D.domain_vector(["la photosynthèse"]), D.domain_vector(["la racine coranique"]),
              D.domain_vector(["le train de la gare"]), D.domain_vector(["ma mémoire conscience"])]
    seeds = [D.domain_vector(["photosynthèse énergie"]), D.domain_vector(["prophète verset"]),
             D.domain_vector(["gare vélo route"]), D.domain_vector(["identité conscience"])]
    p = A.perm_pvalue_seedfollow(dreams, seeds, n_perm=2000, seed=0)
    assert p < 0.05
    assert p == A.perm_pvalue_seedfollow(dreams, seeds, n_perm=2000, seed=0)  # déterministe
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dream_ablation.py -q`
Expected: FAIL (`ModuleNotFoundError: dream_ablation`).

- [ ] **Step 3: Implement the pure metrics in `dream_ablation.py`**

```python
"""Métriques d'ablation du corpus (PUR, stdlib, offline).
Agrégation PAR NUIT (une vecteur-domaine par (cellule, nuit)) → respecte la
pseudo-réplication (N compté en nuits, pas en rêves)."""
import math
import random

import dream_domains as D

night_domain_vector = D.domain_vector


def seed_domain_vector(menu):
    """Profil-domaine des GRAINES d'une nuit (sur leurs snippets)."""
    return D.domain_vector([it.get("snippet", "") for it in (menu or [])])


def _cos(va, vb):
    keys = D.DOMAINS
    dot = sum(va.get(k, 0.0) * vb.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(va.get(k, 0.0) ** 2 for k in keys))
    nb = math.sqrt(sum(vb.get(k, 0.0) ** 2 for k in keys))
    return round(dot / (na * nb), 6) if na and nb else 0.0


def seed_following(dream_vec, seed_vec):
    """Le rêve suit-il ses graines ? cosinus des profils-domaine. [0,1]."""
    return _cos(dream_vec, seed_vec)


def cross_arch_convergence(qwen_vec, sonnet_vec):
    """Convergence cross-architecture (cosinus des profils-domaine)."""
    return _cos(qwen_vec, sonnet_vec)


def anamnese_retention(dream_vec):
    """Masse sur les domaines spécifiques-Anamnèse (moyenne, dans [0,1])."""
    doms = D.ANAMNESE_DOMAINS
    return round(sum(dream_vec.get(d, 0.0) for d in doms) / len(doms), 6)


def perm_pvalue_seedfollow(dream_vecs, seed_vecs, n_perm=5000, seed=0):
    """p que le suivi des VRAIES graines dépasse le suivi de graines permutées.
    Observé = moyenne des cosinus appariés ; nul = graines mélangées. Seedé."""
    if len(dream_vecs) != len(seed_vecs) or len(dream_vecs) < 2:
        return 1.0
    obs = sum(seed_following(d, s) for d, s in zip(dream_vecs, seed_vecs)) / len(dream_vecs)
    rng = random.Random(seed)
    idx = list(range(len(seed_vecs)))
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(idx)
        perm = sum(seed_following(dream_vecs[i], seed_vecs[j]) for i, j in enumerate(idx)) / len(idx)
        if perm >= obs:
            hits += 1
    return round((hits + 1) / (n_perm + 1), 6)             # +1 : jamais p=0 (honnête)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dream_ablation.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dream_ablation.py tests/test_dream_ablation.py
git commit -m "feat(reve): métriques d'ablation PURES (seed-following, rétention, convergence)"
```

---

### Task 5: Verdict à portes gravées + constantes + rapport

**Files:**
- Modify: `config.py` (constantes `DREAM_ABL_*`), `dream_ablation.py` (`ablation_verdict`, `load_cells`, `report`)
- Test: `tests/test_dream_ablation_verdict.py`

**Interfaces:**
- Consumes: `config.DREAM_ABL_SEEDFOLLOW_MIN=0.60`, `DREAM_ABL_ARCH_PARITY_MAX=0.20`, `DREAM_ABL_ANAMNESE_COLLAPSE_MIN=0.30`, `DREAM_ABL_MIN_NIGHTS=10`, `DREAM_ABL_PERM_P=0.05`.
- Produces: `dream_ablation.ablation_verdict(n_nights, seedfollow_by_cell, perm_p, anamnese_drop_by_model) -> tuple[str, list[str]]` où `seedfollow_by_cell = {("qwen","brain_on"): float, ("qwen","brain_off"): float, ("sonnet","brain_on"): float, ("sonnet","brain_off"): float}` et `anamnese_drop_by_model = {"qwen": float, "sonnet": float}` ; labels `"PROUVÉ" | "PLAUSIBLE++" | "NON SOUTENU" | "INSUFFISANT"`. Plus `load_cells(conn) -> dict` et `report(conn) -> str` (I/O léger).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dream_ablation_verdict.py
import dream_ablation as A

FULL = {("qwen", "brain_on"): 0.8, ("qwen", "brain_off"): 0.75,
        ("sonnet", "brain_on"): 0.72, ("sonnet", "brain_off"): 0.7}

def test_insufficient_below_min_nights():
    label, _ = A.ablation_verdict(5, FULL, 0.01, {"qwen": 0.5, "sonnet": 0.5})
    assert label == "INSUFFISANT"

def test_prouve_when_all_gates_pass():
    label, _ = A.ablation_verdict(12, FULL, 0.01, {"qwen": 0.4, "sonnet": 0.35})
    assert label == "PROUVÉ"

def test_non_soutenu_when_seedfollow_fails():
    bad = dict(FULL); bad[("sonnet", "brain_off")] = 0.2      # sonnet ne suit pas ses graines
    label, _ = A.ablation_verdict(12, bad, 0.01, {"qwen": 0.4, "sonnet": 0.35})
    assert label == "NON SOUTENU"

def test_non_soutenu_when_parity_fails():
    bad = dict(FULL); bad[("qwen", "brain_on")] = 0.95; bad[("sonnet", "brain_on")] = 0.62  # écart 0.33 > 0.20
    label, _ = A.ablation_verdict(12, bad, 0.01, {"qwen": 0.4, "sonnet": 0.35})
    assert label == "NON SOUTENU"

def test_non_soutenu_when_perm_not_significant():
    label, _ = A.ablation_verdict(12, FULL, 0.20, {"qwen": 0.4, "sonnet": 0.35})
    assert label == "NON SOUTENU"

def test_plausible_when_one_model_leaks():
    # A passe, mais sonnet ne s'effondre pas (persona contribue)
    label, _ = A.ablation_verdict(12, FULL, 0.01, {"qwen": 0.4, "sonnet": 0.1})
    assert label == "PLAUSIBLE++"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dream_ablation_verdict.py -q`
Expected: FAIL (`ablation_verdict` inexistant).

- [ ] **Step 3: Add config constants**

Dans `config.py`, juste après `DREAM_STATE_CORR_P = 0.05` (ligne ~218) :

```python
# --- Ablation du corpus 2×2 (portes gravées 2026-07-09) ---
DREAM_ABLATION_ENABLED     = os.environ.get("ANAMNESE_DREAM_ABLATION", "1") == "1"
DREAM_ABL_SEEDFOLLOW_MIN   = 0.60   # suivi des graines minimal (cosinus), par cellule
DREAM_ABL_ARCH_PARITY_MAX  = 0.20   # écart max de suivi entre qwen et sonnet (par condition)
DREAM_ABL_ANAMNESE_COLLAPSE_MIN = 0.30  # chute rétention anamnèse ON→OFF, par modèle
DREAM_ABL_MIN_NIGHTS       = 10     # nuits/cellule minimales pour conclure
DREAM_ABL_PERM_P           = 0.05   # p permutation du suivi des graines
```

- [ ] **Step 4: Implement `ablation_verdict` (+ `load_cells`, `report`)**

Dans `dream_ablation.py`, ajouter `import config` en tête, puis :

```python
def ablation_verdict(n_nights, seedfollow_by_cell, perm_p, anamnese_drop_by_model):
    """Portes gravées (spec 2026-07-09). -> (label, raisons)."""
    raisons = []
    if n_nights < config.DREAM_ABL_MIN_NIGHTS:
        return "INSUFFISANT", [f"{n_nights} nuits/cellule < {config.DREAM_ABL_MIN_NIGHTS} — refus de conclure."]
    # Porte A : suivi des graines >= seuil pour les 4 cellules
    sf_min = config.DREAM_ABL_SEEDFOLLOW_MIN
    sf_ok = all(v >= sf_min for v in seedfollow_by_cell.values())
    # parité d'archi par condition
    parity_ok = True
    for cond in ("brain_on", "brain_off"):
        q = seedfollow_by_cell.get(("qwen", cond)); s = seedfollow_by_cell.get(("sonnet", cond))
        if q is None or s is None or abs(q - s) > config.DREAM_ABL_ARCH_PARITY_MAX:
            parity_ok = False
    perm_ok = perm_p < config.DREAM_ABL_PERM_P
    gate_A = sf_ok and parity_ok and perm_ok
    # Porte B : effondrement anamnèse ON->OFF >= seuil pour les DEUX modèles
    col = config.DREAM_ABL_ANAMNESE_COLLAPSE_MIN
    drops = anamnese_drop_by_model
    gate_B_full = all(drops.get(m, 0.0) >= col for m in ("qwen", "sonnet"))
    gate_B_partial = any(drops.get(m, 0.0) >= col for m in ("qwen", "sonnet"))
    raisons.append(f"Porte A (suivi graines ≥{sf_min}, parité ≤{config.DREAM_ABL_ARCH_PARITY_MAX}, "
                   f"p<{config.DREAM_ABL_PERM_P}) : {'OK' if gate_A else 'ÉCHEC'}")
    raisons.append(f"Porte B (effondrement anamnèse ≥{col} les 2 modèles) : "
                   f"{'OK' if gate_B_full else ('partielle' if gate_B_partial else 'ÉCHEC')}")
    if not gate_A:
        return "NON SOUTENU", raisons + ["les thèmes ne suivent pas les graines également → l'architecture compte."]
    if gate_B_full:
        return "PROUVÉ", raisons + ["le corpus domine l'architecture (préférence fonctionnelle, jamais conscience)."]
    if gate_B_partial:
        return "PLAUSIBLE++", raisons + ["fuite anamnèse en OFF sur un modèle → la persona contribue."]
    return "NON SOUTENU", raisons + ["aucun effondrement anamnèse → thèmes venus de la persona/prior, pas du corpus."]


def load_cells(conn):
    """Groupe dream_log par (modèle, condition, night_id calendaire). Le modèle :
    'local'/'twin' -> 'qwen', 'sonnet' -> 'sonnet'. Condition depuis meta (absent=brain_on).
    -> {(model, condition): {night_date: [contenus...]}, "_menus": {(model,condition,night): menu}}."""
    import json as _json
    out, menus = {}, {}
    try:
        rows = conn.execute("SELECT night_id, dreamer, menu, content, meta FROM dream_log").fetchall()
    except Exception:
        return {"cells": out, "menus": menus}
    for night_id, dreamer, menu, content, meta in rows:
        m = _json.loads(meta) if meta else {}
        cond = m.get("condition", "brain_on")
        model = "sonnet" if dreamer == "sonnet" else "qwen"
        date = (night_id or "")[:10]
        out.setdefault((model, cond), {}).setdefault(date, [])
        if content:
            out[(model, cond)][date].append(content)
        if menu:
            menus[(model, cond, date)] = _json.loads(menu)
    return {"cells": out, "menus": menus}


def report(conn):
    """Rapport d'ablation lisible (lecture seule). Calcule suivi des graines par
    cellule, chute anamnèse par modèle, p permutation, puis le verdict gravé."""
    data = load_cells(conn)
    cells, menus = data["cells"], data["menus"]
    sf, dreams_seed_pairs = {}, {}
    retention = {}
    for (model, cond), by_night in cells.items():
        d_vecs, s_vecs, rets = [], [], []
        for date, texts in by_night.items():
            if not texts:
                continue
            dv = night_domain_vector(texts)
            menu = menus.get((model, cond, date)) or menus.get(("qwen", cond, date))
            if not menu:
                continue
            sv = seed_domain_vector(menu)
            d_vecs.append(dv); s_vecs.append(sv); rets.append(anamnese_retention(dv))
        if d_vecs:
            sf[(model, cond)] = round(sum(seed_following(d, s) for d, s in zip(d_vecs, s_vecs)) / len(d_vecs), 4)
            dreams_seed_pairs[(model, cond)] = (d_vecs, s_vecs)
            retention[(model, cond)] = round(sum(rets) / len(rets), 4)
    drop = {m: round(retention.get((m, "brain_on"), 0.0) - retention.get((m, "brain_off"), 0.0), 4)
            for m in ("qwen", "sonnet")}
    all_d = [d for (dv, sv) in dreams_seed_pairs.values() for d in dv]
    all_s = [s for (dv, sv) in dreams_seed_pairs.values() for s in sv]
    perm_p = perm_pvalue_seedfollow(all_d, all_s) if len(all_d) >= 2 else 1.0
    n_nights = min((len(bn) for bn in cells.values()), default=0)
    label, raisons = ablation_verdict(n_nights, sf, perm_p, drop)
    lines = ["═══ Ablation du corpus 2×2 — rapport (portes gravées 2026-07-09) ═══",
             f"nuits min/cellule : {n_nights}",
             "suivi des graines par cellule : " + ", ".join(f"{k[0]}/{k[1]}={v}" for k, v in sorted(sf.items())),
             f"chute rétention anamnèse ON→OFF : qwen={drop['qwen']}, sonnet={drop['sonnet']}",
             f"p permutation (suivi des graines) : {perm_p}",
             f"── VERDICT : [{label}] ──", *("   · " + r for r in raisons)]
    return "\n".join(lines)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dream_ablation_verdict.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add config.py dream_ablation.py tests/test_dream_ablation_verdict.py
git commit -m "feat(reve): verdict d'ablation à portes gravées + rapport"
```

---

### Task 6: Branche `qwen-OFF` journal-seul dans le daemon

**Files:**
- Modify: `daemon.py` (ajouter `_dream_ablation_pass` + câblage dans `dream()`)
- Test: `tests/test_dream_ablation_pass.py`

**Interfaces:**
- Consumes: `dream_lab.build_neutral_menu`, `dream_lab.load_neutral_seeds`, `dream_lab.prompt_rem`, `dream_lab.state_block`, `dream_lab.parse_choice`, `dream_lab.log_night` ; `config.DREAM_ABLATION_ENABLED`.
- Produces: `daemon._dream_ablation_pass(mem, night_id, seed_state, neutral_menu, call_fn) -> None` — logue UNE ligne `dream_log` (`dreamer="local"`, `meta={"condition":"brain_off",...}`) et ne touche RIEN d'autre en mémoire.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_ablation_pass.py
import json
import types
import daemon
import dream_lab

class FakeMem:
    """mem minimal : dream_log en table réelle (tmp_db) + espions d'écriture."""
    def __init__(self, conn):
        self.db = conn
        self.added, self.coact, self.kv = [], [], {}
        self.db.execute("CREATE TABLE IF NOT EXISTS dream_log (id INTEGER PRIMARY KEY "
            "AUTOINCREMENT, ts REAL, night_id TEXT, dreamer TEXT, seed_state TEXT, menu TEXT, "
            "chosen TEXT, content TEXT, facets TEXT, written INT, meta TEXT)")
    def add(self, *a, **k): self.added.append((a, k))           # NE DOIT PAS être appelé
    def log_coactivation(self, *a, **k): self.coact.append(a)   # NE DOIT PAS être appelé
    def kv_set(self, k, v): self.kv[k] = v                      # NE DOIT PAS être appelé

def test_ablation_pass_is_journal_only(tmp_db):
    mem = FakeMem(tmp_db)
    menu = [{"episode_id": "N01", "rubric": "science", "strate": "recent",
             "snippet": "la photosynthèse", "facets": []}]
    out = "###CHOIX###\n- G1\n###REVE###\n- Peut-être que la lumière nourrit.\n###FIN###"
    daemon._dream_ablation_pass(mem, "2026-07-09-0300", {"hormones": {}}, menu, lambda p: out)
    rows = mem.db.execute("SELECT dreamer, meta, content FROM dream_log").fetchall()
    assert len(rows) == 1
    dreamer, meta, content = rows[0]
    assert dreamer == "local"
    assert json.loads(meta)["condition"] == "brain_off"
    assert content == out
    # HYGIÈNE : aucune écriture dans le vivant
    assert mem.added == [] and mem.coact == [] and mem.kv == {}

def test_ablation_pass_handles_none_output(tmp_db):
    mem = FakeMem(tmp_db)
    menu = [{"episode_id": "N01", "snippet": "x", "rubric": "", "strate": "recent", "facets": []}]
    daemon._dream_ablation_pass(mem, "2026-07-09-0300", {"hormones": {}}, menu, lambda p: None)
    rows = mem.db.execute("SELECT meta FROM dream_log").fetchall()
    assert len(rows) == 1 and json.loads(rows[0][0]).get("parse") == "engine_failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_ablation_pass.py -q`
Expected: FAIL (`_dream_ablation_pass` inexistant).

- [ ] **Step 3: Implement `_dream_ablation_pass` in `daemon.py`**

Ajouter, juste avant `def dream(eng, mem):` (ligne 279) :

```python
def _dream_ablation_pass(mem, night_id, seed_state, neutral_menu, call_fn):
    """Cellule qwen-OFF (ablation du corpus) : MÊME affect réel, graines NEUTRES,
    JOURNAL-SEUL. N'écrit RIEN dans le vivant (ni idées, ni co-activation, ni kv,
    ni identité) — sinon on pollue le corpus qu'on étudie. Best-effort."""
    try:
        if not neutral_menu:
            return
        out = call_fn(dream_lab.prompt_rem(dream_lab.state_block(seed_state), neutral_menu))
        if out is None:
            dream_lab.log_night(mem, night_id, "local", seed_state, neutral_menu, None, None,
                                written=False,
                                meta={"condition": "brain_off", "ablation": "neutral_seeds",
                                      "parse": "engine_failed"})
            return
        chosen = dream_lab.parse_choice(out, neutral_menu)
        dream_lab.log_night(mem, night_id, "local", seed_state, neutral_menu, chosen, out,
                            written=False,
                            meta={"condition": "brain_off", "ablation": "neutral_seeds",
                                  "parse": "ok" if chosen is not None else "parse_failed"})
    except Exception as e:
        try:
            print("[dream] ablation pass raté (rêve non bloqué):", e)
        except Exception:
            pass
```

- [ ] **Step 4: Wire it into `dream()`**

Dans `daemon.py`, juste APRÈS le bloc jumeau (après la ligne 431, le `else:` du jumeau) et AVANT `mem.kv_set("last_dream_maxid", ...)` (ligne 433), insérer :

```python
        # ---------- CELLULE qwen-OFF (ablation du corpus, JOURNAL-SEUL) ----------
        if config.DREAM_ABLATION_ENABLED:
            try:
                neutral_menu = dream_lab.build_neutral_menu(
                    dream_lab.load_neutral_seeds(), night_id)
                _dream_ablation_pass(mem, night_id, seed_state, neutral_menu, _call)
            except Exception as e:
                print("[dream] cellule ablation sautée (rêve non bloqué):", e)
```

Note : `_call` est la closure définie dans `dream()` (ligne 332). L'ablation réutilise `seed_state` (MÊME affect réel que ON).

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dream_ablation_pass.py -q`
Expected: PASS.

- [ ] **Step 6: Run the full dream suite to check no regression**

Run: `.venv/bin/python -m pytest tests/ -q -k "dream"`
Expected: PASS (toutes les tâches précédentes + l'existant `test_dream_*`).

- [ ] **Step 7: Commit**

```bash
git add daemon.py tests/test_dream_ablation_pass.py
git commit -m "feat(reve): cellule qwen-OFF journal-seul dans le daemon (ablation)"
```

---

### Task 7: Script de replay sonnet — `dream_sonnet.py`

**Files:**
- Create: `dream_sonnet.py`
- Test: `tests/test_dream_sonnet.py`

**Interfaces:**
- Consumes: `dream_lab.prompt_rem`, `dream_lab.state_block`, `dream_lab.parse_choice`, `dream_lab.log_night` ; `dream_log` (menus + seed_state loggés).
- Produces:
  - `dream_sonnet.build_sonnet_prompt(seed_state: dict, menu: list[dict]) -> str` (= `prompt_rem(state_block(seed_state), menu)`).
  - `dream_sonnet.pending_pairs(conn, condition, limit) -> list[dict]` — nuits `qwen` loggées pour `condition` PAS encore rejouées par sonnet ; chaque item `{"night_id","seed_state","menu"}`.
  - `dream_sonnet.replay_pair(conn, item, condition, run_fn) -> bool` — appelle `run_fn(prompt) -> str|None`, parse, logue `dreamer="sonnet"` + `meta={"condition":cond,"source":"replay"}`, dédup. `run_fn` par défaut = `dream_sonnet.claude_sonnet` (subprocess). Injectable pour test.
  - `dream_sonnet.main(nights, condition, run_fn=None)` (CLI `--nights`, `--condition`).

- [ ] **Step 1: Write the failing tests (run_fn mocké — AUCUN claude réel)**

```python
# tests/test_dream_sonnet.py
import json
import dream_sonnet

def _seed_dreamlog(conn):
    conn.execute("CREATE TABLE dream_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, "
        "night_id TEXT, dreamer TEXT, seed_state TEXT, menu TEXT, chosen TEXT, content TEXT, "
        "facets TEXT, written INT, meta TEXT)")
    menu = [{"episode_id": 1, "rubric": "coran", "strate": "recent", "snippet": "racine du prophète", "facets": []}]
    conn.execute("INSERT INTO dream_log (ts,night_id,dreamer,seed_state,menu,chosen,content,facets,written,meta) "
        "VALUES (1.0,'2026-07-09-0300','local',?,?,?,?,'[]',1,?)",
        (json.dumps({"hormones": {}, "humeur": "x", "valence": 0.0, "arousal": 0.5, "compassion": 0.5}),
         json.dumps(menu), json.dumps([1]), "un rêve local", json.dumps({"condition": "brain_on"})))
    conn.commit()
    return menu

def test_build_sonnet_prompt_uses_shared_template():
    menu = [{"episode_id": 1, "rubric": "coran", "strate": "recent", "snippet": "racine", "facets": []}]
    state = {"hormones": {"dopamine": 0.5}, "humeur": "x", "valence": 0.1, "arousal": 0.5, "compassion": 0.5}
    p = dream_sonnet.build_sonnet_prompt(state, menu)
    assert "PHASE DE RÊVE" in p and "[G1]" in p                # même gabarit que qwen

def test_pending_and_replay_logs_sonnet(tmp_db):
    _seed_dreamlog(tmp_db)
    pend = dream_sonnet.pending_pairs(tmp_db, "brain_on", limit=10)
    assert len(pend) == 1 and pend[0]["night_id"] == "2026-07-09-0300"
    out = "###CHOIX###\n- G1\n###REVE###\n- Peut-être que la racine résonne.\n###FIN###"
    ok = dream_sonnet.replay_pair(tmp_db, pend[0], "brain_on", run_fn=lambda p: out)
    assert ok
    rows = tmp_db.execute("SELECT dreamer, meta, content FROM dream_log WHERE dreamer='sonnet'").fetchall()
    assert len(rows) == 1
    assert json.loads(rows[0][1])["condition"] == "brain_on"
    assert json.loads(rows[0][1])["source"] == "replay"

def test_replay_is_deduped(tmp_db):
    _seed_dreamlog(tmp_db)
    pend = dream_sonnet.pending_pairs(tmp_db, "brain_on", limit=10)[0]
    out = "###CHOIX###\n- G1\n###REVE###\n- x\n###FIN###"
    dream_sonnet.replay_pair(tmp_db, pend, "brain_on", run_fn=lambda p: out)
    # après un replay, la nuit n'est plus pending
    assert dream_sonnet.pending_pairs(tmp_db, "brain_on", limit=10) == []

def test_replay_handles_none(tmp_db):
    _seed_dreamlog(tmp_db)
    pend = dream_sonnet.pending_pairs(tmp_db, "brain_on", limit=10)[0]
    ok = dream_sonnet.replay_pair(tmp_db, pend, "brain_on", run_fn=lambda p: None)
    assert ok is False
    assert tmp_db.execute("SELECT COUNT(*) FROM dream_log WHERE dreamer='sonnet'").fetchone()[0] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dream_sonnet.py -q`
Expected: FAIL (`ModuleNotFoundError: dream_sonnet`).

- [ ] **Step 3: Implement `dream_sonnet.py`**

```python
"""Replay budget de la cellule sonnet (main d'Ahmed). Rejoue les menus loggés par
qwen à travers `claude -p --model sonnet`, MÊME prompt que qwen → paires appariées.
Batchable ; testé avec run_fn injectée (aucun claude au build). Aucune écriture
mémoire : dream_log seulement."""
import argparse
import json
import subprocess
import sys

import dream_lab


def build_sonnet_prompt(seed_state, menu):
    """MÊME gabarit que qwen (seul le modèle change)."""
    return dream_lab.prompt_rem(dream_lab.state_block(seed_state), menu)


def claude_sonnet(prompt, timeout=300):
    """Exécution réelle (budget). Rêve = pur texte : aucun outil autorisé."""
    try:
        r = subprocess.run(
            ["claude", "-p", prompt, "--model", "sonnet", "--max-turns", "2",
             "--allowedTools", ""],
            capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except Exception as e:
        print("[dream_sonnet] claude échoué:", e)
        return None


def pending_pairs(conn, condition, limit=10):
    """Nuits qwen loggées pour `condition` PAS encore rejouées par sonnet.
    'qwen' = dreamer 'local' ; condition depuis meta (absent = brain_on)."""
    rows = conn.execute(
        "SELECT night_id, seed_state, menu, meta FROM dream_log WHERE dreamer='local' "
        "AND menu IS NOT NULL ORDER BY ts").fetchall()
    done = set()
    for night_id, meta in conn.execute(
            "SELECT night_id, meta FROM dream_log WHERE dreamer='sonnet'").fetchall():
        m = json.loads(meta) if meta else {}
        done.add((night_id, m.get("condition", "brain_on")))
    out = []
    for night_id, seed_state, menu, meta in rows:
        cond = (json.loads(meta) if meta else {}).get("condition", "brain_on")
        if cond != condition or (night_id, condition) in done:
            continue
        if any(p["night_id"] == night_id for p in out):
            continue                                         # une paire par nuit calendaire
        out.append({"night_id": night_id,
                    "seed_state": json.loads(seed_state) if seed_state else {},
                    "menu": json.loads(menu) if menu else []})
        if len(out) >= limit:
            break
    return out


def replay_pair(conn, item, condition, run_fn=None):
    """Rejoue une paire via sonnet, logue dream_log. run_fn injectable (test)."""
    run_fn = run_fn or claude_sonnet
    if not item.get("menu"):
        return False
    out = run_fn(build_sonnet_prompt(item["seed_state"], item["menu"]))
    if out is None:
        return False
    chosen = dream_lab.parse_choice(out, item["menu"])

    class _Wrap:                                             # log_night attend mem.db + mem.db.commit
        def __init__(self, c): self.db = c
    dream_lab.log_night(_Wrap(conn), item["night_id"], "sonnet", item["seed_state"],
                        item["menu"], chosen, out, written=False,
                        meta={"condition": condition, "source": "replay",
                              "parse": "ok" if chosen is not None else "parse_failed"})
    return True


def main(nights, condition, run_fn=None):
    import sqlite3
    import config
    conn = sqlite3.connect(str(config.DB_PATH))            # config.DB_PATH = DATA_DIR/"memory.db"
    try:
        pend = pending_pairs(conn, condition, limit=nights)
        n = sum(1 for it in pend if replay_pair(conn, it, condition, run_fn=run_fn))
        print(f"[dream_sonnet] {n}/{len(pend)} paire(s) {condition} rejouée(s)")
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--nights", type=int, default=5)
    ap.add_argument("--condition", choices=["brain_on", "brain_off"], default="brain_on")
    a = ap.parse_args()
    main(a.nights, a.condition)
```

Note : `config.DB_PATH` existe (`= DATA_DIR / "memory.db"`, ligne 21). Le `main` n'est PAS testé (budget) ; seules `build_sonnet_prompt`/`pending_pairs`/`replay_pair` le sont (run_fn mockée).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dream_sonnet.py -q`
Expected: PASS.

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS (aucune régression sur l'existant).

- [ ] **Step 6: Commit**

```bash
git add dream_sonnet.py tests/test_dream_sonnet.py
git commit -m "feat(reve): replay sonnet budget (paires appariées, testé mocké)"
```

---

## Notes d'exécution (hors-build, main d'Ahmed)

- Le daemon accumule `local/brain_on` (+ écriture mémoire), `twin`, `local/brain_off` (journal-seul) chaque nuit, gratis.
- Quand le budget le permet : `.venv/bin/python -m dream_sonnet --nights 6 --condition brain_on` puis `--condition brain_off`.
- Analyse (gratuit) : `.venv/bin/python -c "import sqlite3, dream_ablation; print(dream_ablation.report(sqlite3.connect('data/memory.db')))"`.
- Kill-switch ablation : `ANAMNESE_DREAM_ABLATION=0`.

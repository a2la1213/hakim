"""rubric_emergence.py — Émergence de rubriques depuis l'abduction.

Quand un CLUSTER d'insights (role='insight') forme un thème neuf qu'AUCUNE rubrique
existante ne couvre, le cerveau CRÉE une nouvelle rubrique (Claude seul) et y range
ces insights. Croissance DÉLIBÉRÉE : deux gardes — sémantique (covered, distance
centroïde) et structurelle (valid_path, path neuf sous parent existant, kebab-case).
Fonctions pures en tête (stdlib), orchestration + I/O ensuite."""
import json as _json
import re
import time

import config
import rubrics
from synthesis import _cos   # cosinus partagé (une seule implémentation)

# ---------- pur ----------

def _centroid(embs):
    """Moyenne (centroïde) d'une liste d'embeddings de même dimension. [] si vide."""
    if not embs:
        return []
    n = len(embs)
    dim = len(embs[0])
    return [sum(e[i] for e in embs) / n for i in range(dim)]


def _cluster(items, min_size, sim):
    """items=[(id, emb)] → clusters d'ids (glouton, déterministe dans l'ordre d'entrée).
    Chaque item rejoint le 1er cluster dont la GRAINE (1er membre) est à cosinus ≥ sim ;
    sinon il ouvre son propre cluster. Ne garde que les clusters de taille ≥ min_size."""
    clusters = []   # [(seed_emb, [ids])]
    for eid, emb in items:
        placed = False
        for seed, ids in clusters:
            if _cos(emb, seed) >= sim:
                ids.append(eid)
                placed = True
                break
        if not placed:
            clusters.append((emb, [eid]))
    return [ids for _seed, ids in clusters if len(ids) >= min_size]


def covered(cluster_centroid, rubric_centroids, floor):
    """Garde SÉMANTIQUE : True si le centroïde du cluster est à cosinus ≥ floor d'AU
    MOINS un centroïde de rubrique existante (thème déjà couvert → pas de création).
    Les centroïdes vides ([]) sont ignorés."""
    return any(_cos(cluster_centroid, rc) >= floor for rc in rubric_centroids if rc)


def valid_path(path, existing_paths):
    """Garde STRUCTURELLE : (a) path NEUF (pas dans existing_paths) ; (b) niché sous un
    parent EXISTANT (contient un '/', parent ∈ existing_paths — jamais un nouveau root) ;
    (c) segments kebab-case ^[a-z0-9-]+$ ; (d) profondeur ≤ config.RUBRIC_MAX_DEPTH."""
    if not path or path in existing_paths:
        return False
    if path.startswith("/") or path.endswith("/") or "/" not in path:
        return False
    if path.count("/") > config.RUBRIC_MAX_DEPTH:
        return False
    if not all(re.fullmatch(r"[a-z0-9-]+", s) for s in path.split("/")):
        return False
    return path.rsplit("/", 1)[0] in existing_paths


def parse_path(out):
    """Extrait le path kebab-case proposé (1re ligne contenant a/b-c), None si NONE/vide."""
    if not out:
        return None
    t = re.sub(r"<think>.*?</think>", "", out, flags=re.S | re.I).strip()
    if not t or re.match(r"(?i)^\W*none\b", t):
        return None
    for line in t.splitlines():
        m = re.search(r"[a-z0-9-]+(?:/[a-z0-9-]+)+", line.strip().lower())
        if m:
            return m.group(0)
    return None


# ---------- étape face-modèle (chat_fn injectable) ----------

def _propose_prompt(insight_texts, existing_paths):
    lst = "\n".join(f"- {t}" for t in insight_texts)
    ex = ", ".join(sorted(existing_paths)) or "(aucune)"
    return (
        "Voici un groupe d'insights liés (hypothèses nées de rapprochements de souvenirs) :\n"
        f"{lst}\n\n"
        "Forment-ils un THÈME NEUF qu'AUCUNE de ces rubriques existantes ne couvre ?\n"
        f"Rubriques existantes : {ex}\n\n"
        "Si OUI : réponds UNIQUEMENT par UN chemin kebab-case NEUF, niché sous un PARENT "
        "EXISTANT ci-dessus (ex. projets/anamnese/nom-du-theme). PAS de nouveau niveau racine.\n"
        "Si NON (ça rentre dans une rubrique existante) : réponds NONE.")


def propose_path(chat_fn, insight_texts, existing_paths):
    """Claude nomme un path kebab-case NEUF sous un parent existant, ou None (NONE/erreur)."""
    try:
        out = chat_fn(_propose_prompt(insight_texts, existing_paths))
    except Exception:
        return None
    return parse_path(out)


# ---------- orchestration (lecture + écriture sur mem.db, best-effort) ----------

def _load_recent_insights(mem):
    """(id, emb, text) des insights embeddés PAS déjà dans une rubrique 'emerged'
    (évite de re-traiter un insight déjà rangé par une émergence précédente)."""
    rows = mem.db.execute(
        "SELECT e.id, e.embedding, e.content FROM episodes e "
        "LEFT JOIN rubrics r ON r.id = e.rubric_id "
        "WHERE e.role='insight' AND e.embedding IS NOT NULL AND e.embedding != '[]' "
        "AND (r.kind_hint IS NULL OR r.kind_hint != 'emerged')").fetchall()
    out = []
    for eid, emb, content in rows:
        try:
            v = _json.loads(emb)
        except Exception:
            continue
        if v:
            out.append((eid, v, content or ""))
    return out


def _load_rubric_state(mem):
    """(existing_paths: set, rubric_centroids: list) de TOUTES les rubriques existantes."""
    paths, cents = set(), []
    for path, cent in mem.db.execute("SELECT path, centroid FROM rubrics"):
        paths.add(path)
        v = rubrics._parse_embedding(cent)
        if v:
            cents.append(v)
    return paths, cents


def emerge(mem, chat_fn):
    """Insights récents → clusters → cluster non-couvert → Claude nomme → gardes →
    rubric_create(kind_hint='emerged') + rattache les insights. Best-effort.
    Retourne la liste des paths créés."""
    if not config.RUBRIC_EMERGE_ENABLED:
        return []
    created = []
    try:
        insights = _load_recent_insights(mem)
        clusters = _cluster([(i, e) for i, e, _t in insights],
                            config.RUBRIC_EMERGE_MIN_INSIGHTS, config.RUBRIC_EMERGE_SIM)
        if not clusters:
            return created
        by_id = {i: (e, t) for i, e, t in insights}
        existing_paths, rubric_cents = _load_rubric_state(mem)
    except Exception:
        return created
    now = time.time()
    for ids in clusters:
        try:
            cent = _centroid([by_id[i][0] for i in ids])
            if covered(cent, rubric_cents, config.RUBRIC_EMERGE_REDUNDANCY_FLOOR):
                continue                                     # garde sémantique
            path = propose_path(chat_fn, [by_id[i][1] for i in ids], existing_paths)
            if not path or not valid_path(path, existing_paths):
                continue                                     # garde structurelle
            rubrics.rubric_create(mem.db, path, now, kind_hint="emerged")
            for i in ids:
                rubrics.attach_episode(mem.db, i, path, 0.9, now)
            created.append(path)
            existing_paths.add(path)                         # anti-doublon intra-run
        except Exception:
            continue
    return created

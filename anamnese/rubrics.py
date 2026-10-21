"""Rubriques Anamnèse 2.0 — hiérarchie path-based, SANS table closure (décision v2).

L'arbre est encodé dans `rubrics.path` (ex. `projets/atelier3d/qa`) :
- `depth = path.count('/')`, bornée par `config.RUBRIC_MAX_DEPTH` (arbre
  grossier ; la précision fine passe par les facettes) ;
- descendance = `path = racine OR path LIKE racine || '/%'` (pas de closure).

Toutes les fonctions prennent une connexion sqlite3 DÉJÀ OUVERTE (jamais un
chemin) sur une base migrée (cf. migrations.migrate). Les écritures de haut
niveau (`seed_skeleton`, `rubric_create`, `attach_episode`) committent ;
`update_centroid`, `_detach_from` et `_attach_core` sont des sous-opérations
et laissent le commit à l'appelant (transactions de taxonomy.py).

Centroïde : moyenne courante O(1) (`(centroid*n + emb)/(n+1)`) avec
`n = centroid_n`, le compte des embeddings RÉELLEMENT intégrés au centroïde —
PAS `memory_count`, qui compte tous les épisodes rattachés y compris ceux à
embedding vide/invalide (données legacy `'[]'`) et biaiserait la moyenne.
Jamais de recalcul de masse.
"""
import re

import json

import config

# Squelette initial : racines + sous-rubriques dérivées des vrais projets,
# ordonné parents d'abord (seed_skeleton s'appuie dessus). PAS de « divers ».
SKELETON = [
    "projets",
    "projets/atelier3d",
    "projets/atelier3d/modelisation",
    "projets/atelier3d/pricing-stripe",
    "projets/atelier3d/qa",
    "projets/anamnese",
    "projets/anamnese/daemon-consolidation",
    "projets/anamnese/memoire-2.0",
    "projets/unification",
    "savoir-applecture",
    "technique-transverse",
    "personnel-ahmed",
    "relation-identite",
    "meta-apprentissage",
    "business-monetisation",
]

# Motif d'échappement LIKE : `_`/`%` sont des jokers SQL, un slug pourrait
# en contenir — on échappe pour que `LIKE racine || '/%'` reste littéral.
_LIKE_ESCAPES = (("\\", "\\\\"), ("%", "\\%"), ("_", "\\_"))


def _like_prefix(root_path):
    for char, esc in _LIKE_ESCAPES:
        root_path = root_path.replace(char, esc)
    return root_path + "/%"


def get_rubric_id(conn, path):
    """Id de la rubrique `path`, ou None si absente."""
    row = conn.execute("SELECT id FROM rubrics WHERE path=?", (path,)).fetchone()
    return row[0] if row else None


def seed_skeleton(conn, now):
    """Insère les rubriques de SKELETON si absentes (INSERT OR IGNORE sur path).

    Calcule parent_id/depth/label (label = dernier segment). Idempotent :
    un 2e appel n'insère rien. Retourne le nombre de rubriques créées.
    """
    created = 0
    for path in SKELETON:
        depth = path.count("/")
        parent_id = None
        if depth:
            parent_id = get_rubric_id(conn, path.rsplit("/", 1)[0])
        cur = conn.execute(
            "INSERT OR IGNORE INTO rubrics (path, label, parent_id, depth, created_ts) "
            "VALUES (?,?,?,?,?)",
            (path, path.rsplit("/", 1)[-1], parent_id, depth, now),
        )
        created += cur.rowcount
    conn.commit()
    return created


def rubric_create(conn, path, now, label=None, kind_hint=None):
    """Crée une rubrique et retourne son id (id existant si `path` est déjà là).

    - `depth = path.count('/')`, refusé si > config.RUBRIC_MAX_DEPTH ;
    - le parent (préfixe du path) doit exister, sinon ValueError ;
    - label par défaut = dernier segment du path.
    """
    if not path or path.startswith("/") or path.endswith("/"):
        raise ValueError(f"path de rubrique invalide : {path!r}")
    # (audit du cockpit, 2026-10-20, C-H4) : un chemin de rubrique s'affiche dans le cockpit ; seuls minuscules,
    # chiffres, « . », « _ » et « - » (comme taxonomy._PATH_RE), jamais un segment « . » ou « .. »
    if not re.match(r"^[a-z0-9._\-]+(/[a-z0-9._\-]+)*$", path) or any(seg in (".", "..") for seg in path.split("/")):
        raise ValueError(f"path de rubrique invalide (minuscules a/b/c attendues) : {path!r}")

    existing = get_rubric_id(conn, path)
    if existing is not None:
        return existing

    depth = path.count("/")
    if depth > config.RUBRIC_MAX_DEPTH:
        raise ValueError(
            f"profondeur {depth} > RUBRIC_MAX_DEPTH={config.RUBRIC_MAX_DEPTH} : {path!r}"
        )

    parent_id = None
    if depth:
        parent_path = path.rsplit("/", 1)[0]
        parent_id = get_rubric_id(conn, parent_path)
        if parent_id is None:
            raise ValueError(f"parent inexistant {parent_path!r} pour {path!r}")

    cur = conn.execute(
        "INSERT INTO rubrics (path, label, parent_id, kind_hint, depth, created_ts) "
        "VALUES (?,?,?,?,?,?)",
        (path, label or path.rsplit("/", 1)[-1], parent_id, kind_hint, depth, now),
    )
    import registre   # import local : registre importe rubrics
    registre.noter(conn, "rubrique", path, None, {"label": label or path.rsplit("/", 1)[-1], "kind_hint": kind_hint})
    conn.commit()
    return cur.lastrowid


def subtree_paths(conn, root_path):
    """Paths de `root_path` + tous ses descendants (path + LIKE, triés)."""
    rows = conn.execute(
        "SELECT path FROM rubrics WHERE path = ? OR path LIKE ? ESCAPE '\\' "
        "ORDER BY path",
        (root_path, _like_prefix(root_path)),
    )
    return [r[0] for r in rows]


def rubric_tree(conn, root_path=None, max_depth=None):
    """Liste plate `[{path, label, depth, memory_count}]` triée par path.

    Filtres optionnels : sous-arbre de `root_path` (inclus) et
    `depth <= max_depth` (profondeur ABSOLUE, celle de la colonne `depth`).
    """
    sql = "SELECT path, label, depth, memory_count FROM rubrics"
    clauses, params = [], []
    if root_path is not None:
        clauses.append("(path = ? OR path LIKE ? ESCAPE '\\')")
        params += [root_path, _like_prefix(root_path)]
    if max_depth is not None:
        clauses.append("depth <= ?")
        params.append(max_depth)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY path"
    return [
        {"path": p, "label": l, "depth": d, "memory_count": c}
        for p, l, d, c in conn.execute(sql, params)
    ]


def _parse_embedding(raw):
    """JSON -> list[float] ; tout ce qui n'est pas une liste exploitable -> []."""
    try:
        emb = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        return []
    return emb if isinstance(emb, list) else []


def update_centroid(conn, rubric_id, embedding):
    """Moyenne courante O(1) : `new = (centroid*n + emb)/(n+1)`.

    `n = rubrics.centroid_n` : le compte des embeddings réellement intégrés au
    centroïde (PAS memory_count, qui inclut les épisodes à embedding vide et
    biaiserait la moyenne). Incrémente centroid_n quand — et seulement quand —
    l'embedding est intégré. 1er embedding (centroïde NULL) : centroïde =
    embedding, centroid_n = 1. Embedding vide ou de dimension incohérente :
    no-op sûr (ni centroïde ni centroid_n ne bougent).
    Ne committe pas (sous-opération d'attach_episode).
    """
    if not embedding:
        return
    row = conn.execute(
        "SELECT centroid, centroid_n FROM rubrics WHERE id=?", (rubric_id,)
    ).fetchone()
    if row is None:
        return
    centroid = _parse_embedding(row[0])
    n = row[1] or 0
    if not centroid:
        new, n = [float(x) for x in embedding], 0
    elif len(embedding) != len(centroid):
        return
    else:
        new = [(c * n + float(e)) / (n + 1) for c, e in zip(centroid, embedding)]
    conn.execute(
        "UPDATE rubrics SET centroid=?, centroid_n=? WHERE id=?",
        (json.dumps(new), n + 1, rubric_id),
    )


def _detach_from(conn, rubric_id, embedding):
    """Défait la contribution d'un épisode : memory_count -1, et si son
    embedding avait été intégré au centroïde, centroid_n -1 et centroïde
    ré-équilibré.

    Inverse O(1) de la moyenne courante : `new = (centroid*n - emb)/(n-1)`
    avec `n = centroid_n` AVANT décrément. Mêmes gardes qu'update_centroid
    (embedding vide/dimension incohérente = centroïde et centroid_n ne
    bougent pas, ce qui reste symétrique : cet embedding n'y était jamais
    entré). Dernier embedding (centroid_n == 1) : centroïde NULL,
    centroid_n = 0.
    """
    row = conn.execute(
        "SELECT centroid, centroid_n FROM rubrics WHERE id=?", (rubric_id,)
    ).fetchone()
    if row is None:
        return
    centroid = _parse_embedding(row[0])
    n = row[1] or 0
    if embedding and centroid and len(embedding) == len(centroid) and n >= 1:
        if n == 1:
            conn.execute(
                "UPDATE rubrics SET centroid=NULL, centroid_n=0 WHERE id=?",
                (rubric_id,),
            )
        else:
            new = [(c * n - float(e)) / (n - 1) for c, e in zip(centroid, embedding)]
            conn.execute(
                "UPDATE rubrics SET centroid=?, centroid_n=? WHERE id=?",
                (json.dumps(new), n - 1, rubric_id),
            )
    conn.execute(
        "UPDATE rubrics SET memory_count = MAX(memory_count - 1, 0) WHERE id=?",
        (rubric_id,),
    )


def _attach_core(conn, episode_id, rubric_path, conf, now):
    """Rattache un épisode à une rubrique (rubric_id/rubric_conf/routed_ts).

    Incrémente `memory_count` et met le centroïde à jour (O(1)). Épisode déjà
    rattaché AILLEURS : l'ancienne rubrique est décomptée/ré-équilibrée (pas
    de double comptage). Déjà rattaché ICI : seuls conf/routed_ts bougent.
    Ne committe pas : sous-opération d'attach_episode et des mutations
    transactionnelles de taxonomy.py (le commit appartient à l'appelant).
    """
    rubric_id = get_rubric_id(conn, rubric_path)
    if rubric_id is None:
        raise ValueError(f"rubrique inexistante : {rubric_path!r}")
    row = conn.execute(
        "SELECT rubric_id, embedding FROM episodes WHERE id=?", (episode_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"épisode inexistant : {episode_id}")
    old_rubric_id, raw_emb = row

    if old_rubric_id != rubric_id:
        embedding = _parse_embedding(raw_emb)
        if old_rubric_id is not None:
            _detach_from(conn, old_rubric_id, embedding)
        update_centroid(conn, rubric_id, embedding)  # gère centroid_n lui-même
        conn.execute(
            "UPDATE rubrics SET memory_count = memory_count + 1 WHERE id=?",
            (rubric_id,),
        )

    conn.execute(
        "UPDATE episodes SET rubric_id=?, rubric_conf=?, routed_ts=? WHERE id=?",
        (rubric_id, conf, now, episode_id),
    )


def attach_episode(conn, episode_id, rubric_path, conf, now):
    """Rattache un épisode (public) — _attach_core + commit. Voir _attach_core."""
    _attach_core(conn, episode_id, rubric_path, conf, now)
    conn.commit()

"""Projection 3D des souvenirs (Cerveau 3D P2a) — PCA à basis FIGÉE + export graphe.

Chaque épisode est positionné dans l'espace par PCA de son embedding
(model2vec 256-dim → 3) via numpy SVD, offline. Décision clé : la basis
(mean + 3 composantes) est calculée UNE fois sur les embeddings existants
puis CACHÉE dans kv['brain_basis'] — FIGÉE. Les nouveaux épisodes se
projettent sur la MÊME basis : le graphe ne « danse » pas à chaque ajout
(la stabilité spatiale prime sur l'optimalité de la variance expliquée).
Recalcul uniquement sur demande explicite (refit=True), qui re-projette tout.

La PCA est rendue DÉTERMINISTE en fixant le signe de chaque composante
(l'élément de valeur absolue maximale est rendu positif) : numpy peut
retourner v ou -v pour un même sous-espace, ce qui inverserait des axes
d'un fit à l'autre.

`brain_layout(episode_id, x, y, z, ts)` est RÉGÉNÉRABLE (backfill_layout) ;
`brain_graph()` assemble nœuds (layout + métadonnées) et arêtes
(coactivation, poids > 0) en LECTURE SEULE pour le cockpit — chaque nœud
porte aussi `wm` ("focus"|"halo"|None, lu dans kv['working_memory'], WM3 :
la mémoire de travail s'allume dans le cerveau 3D). Tout est legacy-safe :
tables absentes → skip/empty, jamais d'exception.
"""

import json
import time

import numpy as np

BASIS_KEY = "brain_basis"   # clé kv de la basis PCA figée (JSON)
WM_KEY = "working_memory"   # clé kv de l'état de la mémoire de travail (WM1)
N_COMPONENTS = 3            # 3D
SNIPPET_LEN = 80            # aperçu de contenu par nœud
FACETS_PER_NODE = 3         # top facettes par nœud (poids décroissant)


# --- helpers bas niveau (module autonome : prend une connexion sqlite3 nue) ---
def _table_exists(conn, name):
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _kv_get(conn, key):
    """Valeur kv ou None — legacy-safe (table kv absente → None)."""
    if not _table_exists(conn, "kv"):
        return None
    row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def _kv_set(conn, key, value):
    """Upsert kv, commit inclus — legacy-safe (table absente → skip silencieux)."""
    if not _table_exists(conn, "kv"):
        return
    conn.execute(
        "INSERT OR REPLACE INTO kv (key, value, ts) VALUES (?,?,?)",
        (key, value, time.time()),
    )
    conn.commit()


def _parse_embedding(raw):
    """JSON list[float] → list, sinon None (vide/corrompu → skip)."""
    try:
        emb = json.loads(raw) if raw else None
    except (TypeError, ValueError):
        return None
    return emb if isinstance(emb, list) and emb else None


def _valid_embeddings(conn):
    """Tous les embeddings valides d'episodes, restreints à la dimension MODALE.

    La PCA exige une dimension homogène ; une DB réelle peut contenir des
    retardataires d'une ancienne dimension (re-embedding nomic→model2vec) —
    la dimension majoritaire gagne (départage déterministe : la plus grande).
    Legacy-safe : pas de table episodes → [].
    """
    if not _table_exists(conn, "episodes"):
        return []
    by_dim = {}
    for (raw,) in conn.execute("SELECT embedding FROM episodes ORDER BY id"):
        emb = _parse_embedding(raw)
        if emb:
            by_dim.setdefault(len(emb), []).append(emb)
    if not by_dim:
        return []
    dim = max(by_dim, key=lambda d: (len(by_dim[d]), d))
    return by_dim[dim]


# --- PCA (numpy SVD, déterministe) ---
def fit_basis(embeddings):
    """PCA → basis JSON-sérialisable {"mean": [dim], "components": [[dim]×3]}.

    SVD numpy sur les embeddings centrés ; composantes = 3 premières lignes
    de Vt (variance décroissante), complétées par des lignes NULLES si moins
    de 3 directions existent (< 4 points / rang insuffisant : la projection
    y vaut 0, pas d'exception). Signe FIXÉ par composante (élément max-abs
    rendu positif) → deux fits sur les mêmes données sont IDENTIQUES.
    Aucun embedding → None.
    """
    if not embeddings:
        return None
    X = np.asarray(embeddings, dtype=float)
    if X.ndim != 2 or X.shape[0] == 0:
        return None
    mean = X.mean(axis=0)
    _u, _s, vt = np.linalg.svd(X - mean, full_matrices=False)
    comps = np.array(vt[:N_COMPONENTS], dtype=float, copy=True)
    if comps.shape[0] < N_COMPONENTS:
        comps = np.vstack(
            [comps, np.zeros((N_COMPONENTS - comps.shape[0], X.shape[1]))]
        )
    for i in range(N_COMPONENTS):  # signe déterministe (SVD peut rendre ±v)
        j = int(np.argmax(np.abs(comps[i])))
        if comps[i, j] < 0:
            comps[i] = -comps[i]
    return {"mean": mean.tolist(), "components": comps.tolist()}


def project_one(embedding, basis):
    """(embedding - mean) · components^T → (x, y, z).

    Embedding vide/absent ou de dimension ≠ celle de la basis → None (skip) ;
    basis absente → None. Jamais d'exception sur entrée invalide.
    """
    if not embedding or not basis:
        return None
    mean = basis.get("mean") or []
    comps = basis.get("components") or []
    if not mean or not comps or len(embedding) != len(mean):
        return None
    v = np.asarray(embedding, dtype=float) - np.asarray(mean, dtype=float)
    out = np.asarray(comps, dtype=float) @ v
    return (float(out[0]), float(out[1]), float(out[2]))


# --- basis figée + cachée (kv) ---
def get_or_fit_basis(conn, refit=False):
    """Basis PCA depuis le cache kv['brain_basis'] ; sinon fit + cache.

    FIGÉE : calculée une fois sur tous les embeddings valides, puis toujours
    relue du cache — recalcul UNIQUEMENT sur refit=True explicite (qui
    re-cache). Cache corrompu → refit transparent. Aucun embedding valide →
    None (et rien n'est caché). Legacy-safe (kv/episodes absentes → skip).
    """
    if not refit:
        raw = _kv_get(conn, BASIS_KEY)
        if raw:
            try:
                basis = json.loads(raw)
            except (TypeError, ValueError):
                basis = None
            if isinstance(basis, dict) and basis.get("mean") and basis.get("components"):
                return basis
    basis = fit_basis(_valid_embeddings(conn))
    if basis is not None:
        _kv_set(conn, BASIS_KEY, json.dumps(basis))
    return basis


def backfill_layout(conn, refit=False):
    """Projette les épisodes à embedding valide dans brain_layout (upsert).

    INCRÉMENTAL par défaut : les épisodes déjà dans brain_layout ne sont PAS
    re-projetés (comptés en skipped) — leurs coordonnées ne bougent JAMAIS,
    les nouveaux se projettent sur la basis figée du cache. refit=True :
    recalcule la basis (get_or_fit_basis(refit=True)) et re-projette TOUT.
    Embedding vide/dimension ≠ basis → skipped. Retourne {projected, skipped}.
    Legacy-safe : brain_layout ou episodes absente → {0, 0} sans lever.
    """
    if not (_table_exists(conn, "brain_layout") and _table_exists(conn, "episodes")):
        return {"projected": 0, "skipped": 0}
    basis = get_or_fit_basis(conn, refit=refit)
    if basis is None:  # aucun embedding valide : tout est skippé
        n = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        return {"projected": 0, "skipped": n}
    done = set()
    if not refit:
        done = {r[0] for r in conn.execute("SELECT episode_id FROM brain_layout")}
    now = time.time()
    projected = skipped = 0
    for eid, raw in conn.execute("SELECT id, embedding FROM episodes ORDER BY id"):
        if eid in done:
            skipped += 1
            continue
        pt = project_one(_parse_embedding(raw), basis)
        if pt is None:
            skipped += 1
            continue
        conn.execute(
            "INSERT INTO brain_layout (episode_id, x, y, z, ts) VALUES (?,?,?,?,?) "
            "ON CONFLICT(episode_id) DO UPDATE SET "
            "x=excluded.x, y=excluded.y, z=excluded.z, ts=excluded.ts",
            (eid, pt[0], pt[1], pt[2], now),
        )
        projected += 1
    conn.commit()
    return {"projected": projected, "skipped": skipped}


# --- export du graphe (cockpit) ---
def _wm_ids(conn):
    """Ids (focus, halo) de kv['working_memory'] — (set, set), JAMAIS d'exception.

    Miroir read-only de la tolérance de Memory.wm_get : état absent, JSON
    invalide, structure inattendue ou items illisibles => ensembles vides
    (item par item : un id lisible est gardé même au milieu de déchets).
    Le focus PRIME si un id figurait dans les deux listes (défensif).
    """
    raw = _kv_get(conn, WM_KEY)
    if not raw:
        return set(), set()
    try:
        state = json.loads(raw)
    except (TypeError, ValueError):
        return set(), set()
    if not isinstance(state, dict):
        return set(), set()

    def _ids(key):
        items = state.get(key)
        if not isinstance(items, list):
            return set()
        out = set()
        for it in items:
            try:
                out.add(int(it["id"]))
            except (TypeError, ValueError, KeyError):
                continue
        return out

    focus = _ids("focus")
    return focus, _ids("halo") - focus


def brain_graph(conn, limit=None):
    """Graphe {nodes, edges, wm, generated_ts} pour le cerveau 3D — LECTURE SEULE.

    nodes : épisodes ayant un brain_layout → {id, x, y, z, ts (timestamp
    epoch float de l'épisode — date/heure du souvenir ; NULL/illisible →
    None), rubric (path ou null), importance, recall_count, valence
    (enc_valence), arousal (enc_arousal), facets (top 3 slugs par poids),
    snippet (content[:80]),
    wm ("focus" | "halo" | None — WM3 : la mémoire de travail s'allume)},
    triés par importance décroissante (limit borne aux plus saillants).
    edges : coactivation à poids > 0 → [{a, b, weight}], restreintes aux
    nœuds PRÉSENTS (une arête pendante vers un épisode sans layout ou
    au-delà de limit casserait le rendu).
    wm : {"focus_n", "halo_n"} — compteurs de LÉGENDE : nœuds taggés
    PRÉSENTS dans le graphe (on compte ce qu'on voit ; un id en WM sans
    layout ou au-delà de limit ne compte pas). État WM lu dans
    kv['working_memory'] (même source que Memory.wm_get) ; absent ou
    corrompu => tous wm=None, compteurs à 0, pas d'exception.
    Aucune écriture (total_changes inchangé). Legacy-safe : tables absentes
    → graphe vide ; colonnes 2.0 absentes → champs null.
    """
    graph = {
        "nodes": [], "edges": [],
        "wm": {"focus_n": 0, "halo_n": 0},
        "generated_ts": time.time(),
    }
    if not (_table_exists(conn, "brain_layout") and _table_exists(conn, "episodes")):
        return graph

    ep_cols = {r[1] for r in conn.execute("PRAGMA table_info(episodes)")}

    def col(name):  # colonne 2.0 absente (DB partiellement migrée) → NULL
        return f"e.{name}" if name in ep_cols else "NULL"

    with_rubrics = _table_exists(conn, "rubrics") and "rubric_id" in ep_cols
    sql = (
        f"SELECT bl.episode_id, bl.x, bl.y, bl.z, "
        f"{'r.path' if with_rubrics else 'NULL'}, "
        f"{col('importance')}, {col('recall_count')}, "
        f"{col('enc_valence')}, {col('enc_arousal')}, e.content, {col('ts')} "
        "FROM brain_layout bl JOIN episodes e ON e.id = bl.episode_id "
        + ("LEFT JOIN rubrics r ON r.id = e.rubric_id " if with_rubrics else "")
        + f"ORDER BY {col('importance')} DESC, bl.episode_id ASC"
    )
    params = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (int(limit),)
    rows = conn.execute(sql, params).fetchall()

    facets_by_ep = {}  # top FACETS_PER_NODE par épisode, UNE requête groupée
    if _table_exists(conn, "episode_facets") and _table_exists(conn, "facets"):
        for eid, slug in conn.execute(
            "SELECT ef.episode_id, f.slug FROM episode_facets ef "
            "JOIN facets f ON f.id = ef.facet_id "
            "ORDER BY ef.episode_id, ef.weight DESC, f.slug"
        ):
            slugs = facets_by_ep.setdefault(eid, [])
            if len(slugs) < FACETS_PER_NODE:
                slugs.append(slug)

    focus_ids, halo_ids = _wm_ids(conn)  # mémoire de travail (WM3)

    node_ids = set()
    for eid, x, y, z, path, imp, rc, val, aro, content, ep_ts in rows:
        node_ids.add(eid)
        wm = "focus" if eid in focus_ids else ("halo" if eid in halo_ids else None)
        if wm is not None:
            graph["wm"][f"{wm}_n"] += 1
        try:  # ts NULL ou illisible (DB partielle) → None, jamais d'exception
            ep_ts = float(ep_ts) if ep_ts is not None else None
        except (TypeError, ValueError):
            ep_ts = None
        graph["nodes"].append({
            "id": eid,
            "x": x, "y": y, "z": z,
            "ts": ep_ts,
            "rubric": path,
            "importance": imp,
            "recall_count": int(rc or 0),
            "valence": val,
            "arousal": aro,
            "facets": facets_by_ep.get(eid, []),
            "snippet": (content or "")[:SNIPPET_LEN],
            "wm": wm,
        })

    if _table_exists(conn, "coactivation"):
        for a, b, w in conn.execute(
            "SELECT a_id, b_id, weight FROM coactivation WHERE weight > 0 "
            "ORDER BY a_id, b_id"
        ):
            if a in node_ids and b in node_ids:
                graph["edges"].append({"a": a, "b": b, "weight": w})
    return graph

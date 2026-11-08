"""Anamnèse — taxonomie VIVANTE : mutations de structure du cerveau.

Le cerveau ne se contente pas de grandir (rubric_create) : il se réorganise —
renommer, reparenter, fusionner, reclasser. Chaque mutation est
TRANSACTIONNELLE (validations d'abord, écritures ensuite, commit unique,
rollback complet sur toute exception), JOURNALISÉE (kv['taxonomy_log'], borné
TAX_LOG_MAX) et RÉVERSIBLE 1 cran (undo_last — lui-même transactionnel :
aucune sous-opération ne committe en chemin), et les centroïdes affectés sont
recalculés depuis les embeddings réels (source de vérité post-mutation).

Écarts assumés vs le code du brief (bugs corrigés, documentés) :
- rename/reparent REFUSENT new_path dans le sous-arbre de old_path (sinon la
  cascade fabrique des paths dont le parent n'existe plus — arbre corrompu) ;
- merge PRÉ-VÉRIFIE les collisions d'enfants (dst a déjà un enfant du même
  nom) → ValueError explicite avant toute écriture, au lieu d'une
  IntegrityError UNIQUE au milieu de la transaction ;
- undo d'un merge recrée src par INSERT direct (_create_rubric_core) — PAS
  rubrics.rubric_create, qui committe en interne et casserait l'atomicité de
  l'undo — et restaure la conf D'ORIGINE de chaque épisode (journalisée au
  merge, le brief la perdait à 0.9) ; de même, undo d'un rename/reclassify
  passe par les cœurs sans commit (_rename_core/_reclassify_core) : l'undo
  entier est UNE transaction ;
- seul le path CIBLE est validé (charset élargi à [a-z0-9._-] : les rubriques
  legacy comme 'projets/anamnese/memoire-2.0' contiennent un point et doivent
  rester renommables/reparentables) ; l'ancien path n'a qu'à exister ;
- _subtree échappe %/_ dans le LIKE (rubrics._like_prefix), comme rubrics.py.

Spec : docs/superpowers/specs/2026-07-05-taxonomie-vivante-design.md
"""
import json
import re
import time

import config
import rubrics

# Segments minuscules [a-z0-9._-] séparés par '/' — kebab-case élargi au
# point/underscore pour couvrir les rubriques legacy (ex. memoire-2.0).
_PATH_RE = re.compile(r"^[a-z0-9._\-]+(/[a-z0-9._\-]+)*$")


# ---------- journal (kv['taxonomy_log']) ----------

def _kv_get(conn, key, default=None):
    row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def _kv_set(conn, key, value):
    """Écrit kv SANS commit (dans la transaction de la mutation)."""
    conn.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES (?,?,?)",
                 (key, value, time.time()))


def log_entries(conn):
    """Journal des mutations : [{desc, inverse, ts}], du plus ancien au plus
    récent. JSON invalide ou non-liste → [] (le prochain _log_op repart sain)."""
    try:
        entries = json.loads(_kv_get(conn, "taxonomy_log", "[]"))
    except Exception:
        return []
    return entries if isinstance(entries, list) else []


def _log_op(conn, desc, inverse):
    """Journalise desc + l'op inverse (pour undo), borné TAX_LOG_MAX.
    Ne committe pas (dans la transaction de la mutation : un rollback
    emporte aussi l'entrée de journal)."""
    entries = log_entries(conn)
    ts = time.time()
    entries.append({"desc": desc, "inverse": inverse, "ts": ts})
    _kv_set(conn, "taxonomy_log",
            json.dumps(entries[-config.TAX_LOG_MAX:], ensure_ascii=False))
    import registre   # import local : registre → rubrics ; noté seulement si une entrée est ouverte
    registre.noter(conn, "taxonomie", desc, None,
                   {"inverse": inverse, "ts": ts, "etat": registre.etat_taxonomie(conn, inverse)})


# ---------- helpers ----------

def _check_path(path):
    if not path or not _PATH_RE.match(path):
        raise ValueError(f"path invalide (minuscules a/b/c attendues) : {path!r}")


def _rid(conn, path):
    rid = rubrics.get_rubric_id(conn, path)
    if rid is None:
        raise ValueError(f"rubrique inexistante : {path!r}")
    return rid


def _subtree(conn, path):
    """[(id, path, depth)] de la rubrique + TOUS ses descendants
    (LIKE échappé : %/_ d'un path legacy restent littéraux)."""
    return conn.execute(
        "SELECT id, path, depth FROM rubrics WHERE path=? OR path LIKE ? ESCAPE '\\' "
        "ORDER BY depth, path",
        (path, rubrics._like_prefix(path))).fetchall()


def recompute_centroid(conn, path):
    """Recalcule centroïde/centroid_n/memory_count depuis les épisodes attachés
    (brute force). Source de vérité après mutation. Retourne le nb d'embeddings
    intégrés. Ne committe pas."""
    rid = _rid(conn, path)
    rows = conn.execute("SELECT embedding FROM episodes WHERE rubric_id=?", (rid,)).fetchall()
    embs = []
    for (raw,) in rows:
        e = rubrics._parse_embedding(raw)
        if e:
            embs.append(e)
    if embs:
        dim = len(embs[0])
        embs = [e for e in embs if len(e) == dim]
        cen = [sum(e[i] for e in embs) / len(embs) for i in range(dim)]
        conn.execute("UPDATE rubrics SET centroid=?, centroid_n=? WHERE id=?",
                     (json.dumps(cen), len(embs), rid))
    else:
        conn.execute("UPDATE rubrics SET centroid=NULL, centroid_n=0 WHERE id=?", (rid,))
    conn.execute("UPDATE rubrics SET memory_count=? WHERE id=?", (len(rows), rid))
    return len(embs)


# ---------- cœurs sans commit (composables dans UNE transaction) ----------

def _rename_core(conn, old_path, new_path):
    """Validations + cascade path/depth + parent_id du nœud de tête.
    SANS commit ni log. Retourne le nb de rubriques renommées.
    Refuse : new_path invalide/existant/dans le sous-arbre de old_path,
    parent du new absent, profondeur dépassée — AVANT toute écriture."""
    _check_path(new_path)
    _rid(conn, old_path)
    if new_path == old_path or new_path.startswith(old_path + "/"):
        raise ValueError(
            f"{new_path!r} est dans le sous-arbre de {old_path!r} — impossible")
    if rubrics.get_rubric_id(conn, new_path) is not None:
        raise ValueError(f"{new_path!r} existe déjà — utiliser merge")
    new_depth = new_path.count("/")
    new_parent_id = None
    if new_depth:
        parent = new_path.rsplit("/", 1)[0]
        new_parent_id = rubrics.get_rubric_id(conn, parent)
        if new_parent_id is None:
            raise ValueError(f"parent inexistant : {parent!r}")
    subtree = _subtree(conn, old_path)
    delta = new_depth - old_path.count("/")
    for _id, p, d in subtree:
        if d + delta > config.RUBRIC_MAX_DEPTH:
            raise ValueError(f"profondeur dépassée pour {p!r}")
    for _id, p, d in subtree:
        np = new_path + p[len(old_path):]
        conn.execute("UPDATE rubrics SET path=?, depth=? WHERE id=?",
                     (np, d + delta, _id))
    # Seul le nœud de tête change de parent ; les descendants suivent en bloc.
    # Label conservé s'il existe (nom d'affichage délibéré), sinon le leaf.
    conn.execute("UPDATE rubrics SET parent_id=?, label=COALESCE(label,?) WHERE path=?",
                 (new_parent_id, new_path.rsplit("/", 1)[-1], new_path))
    return len(subtree)


def _create_rubric_core(conn, path, created_ts, label=None, kind_hint=None):
    """INSERT d'une rubrique SANS commit — rubrics.rubric_create committe en
    interne, inutilisable dans la transaction d'undo. Mêmes règles que lui :
    idempotent sur path existant, parent obligatoire, profondeur bornée."""
    existing = rubrics.get_rubric_id(conn, path)
    if existing is not None:
        return existing
    depth = path.count("/")
    if depth > config.RUBRIC_MAX_DEPTH:
        raise ValueError(
            f"profondeur {depth} > RUBRIC_MAX_DEPTH={config.RUBRIC_MAX_DEPTH} : {path!r}")
    parent_id = None
    if depth:
        parent_path = path.rsplit("/", 1)[0]
        parent_id = rubrics.get_rubric_id(conn, parent_path)
        if parent_id is None:
            raise ValueError(f"parent inexistant {parent_path!r} pour {path!r}")
    cur = conn.execute(
        "INSERT INTO rubrics (path, label, parent_id, kind_hint, depth, created_ts) "
        "VALUES (?,?,?,?,?,?)",
        (path, label or path.rsplit("/", 1)[-1], parent_id, kind_hint, depth, created_ts))
    return cur.lastrowid


def _reclassify_core(conn, episode_id, new_path, now):
    """Écritures du reclassify SANS commit ni log.
    Retourne (résultat, old_path, old_conf) pour le journal de l'appelant."""
    row = conn.execute(
        "SELECT rubric_id, rubric_conf, embedding FROM episodes WHERE id=?",
        (episode_id,)).fetchone()
    if row is None:
        raise ValueError(f"épisode inexistant : {episode_id}")
    old_rid, old_conf, raw_emb = row
    old_path = None
    if old_rid is not None:
        r = conn.execute("SELECT path FROM rubrics WHERE id=?", (old_rid,)).fetchone()
        old_path = r[0] if r else None
    if new_path is None:
        if old_rid is not None:
            rubrics._detach_from(conn, old_rid, rubrics._parse_embedding(raw_emb))
        conn.execute(
            "UPDATE episodes SET rubric_id=NULL, rubric_conf=NULL, routed_ts=NULL "
            "WHERE id=?", (episode_id,))
        return "orphelin", old_path, old_conf
    rubrics._attach_core(conn, episode_id, new_path, 1.0, now)
    return new_path, old_path, old_conf


# ---------- mutations (publiques, transactionnelles) ----------

def rename(conn, old_path, new_path, now, _log=True):
    """Renomme/déplace old_path → new_path, CASCADE sur les descendants.
    Refuse : new existe, parent du new absent, new dans le sous-arbre de old,
    profondeur dépassée. Retourne le nb de rubriques renommées. Committe."""
    try:
        n = _rename_core(conn, old_path, new_path)
        if _log:
            _log_op(conn, f"rename {old_path} → {new_path}",
                    {"op": "rename", "old": new_path, "new": old_path})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return n


def relabel(conn, path, label):
    """Change le nom d'affichage (label) sans toucher au path."""
    rid = _rid(conn, path)
    old = conn.execute("SELECT label FROM rubrics WHERE id=?", (rid,)).fetchone()[0]
    try:
        conn.execute("UPDATE rubrics SET label=? WHERE id=?", (label, rid))
        _log_op(conn, f"relabel {path}", {"op": "relabel", "path": path, "label": old})
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def reparent(conn, path, new_parent_path, now):
    """Déplace la branche `path` sous new_parent_path (= rename avec cascade).
    Retourne le nb de rubriques déplacées."""
    _rid(conn, new_parent_path)
    leaf = path.rsplit("/", 1)[-1]
    return rename(conn, path, f"{new_parent_path}/{leaf}", now)


def merge(conn, src_path, dst_path, now, _log=True):
    """Fond src dans dst : épisodes ré-attachés (conf conservée), enfants
    reparentés sous dst, src supprimée, centroïde de dst recalculé (brute
    force). Tout ou rien. Refuse : dst ⊂ src, collision d'enfant (dst a déjà
    un enfant du même nom — merger d'abord les enfants), profondeur dépassée.
    Retourne {"moved_episodes", "moved_children"}."""
    src_id = _rid(conn, src_path)
    _rid(conn, dst_path)
    if dst_path == src_path or dst_path.startswith(src_path + "/"):
        raise ValueError("dst est src ou un descendant de src")
    eps = conn.execute(
        "SELECT id, rubric_conf FROM episodes WHERE rubric_id=?", (src_id,)).fetchall()
    children = [r[0] for r in conn.execute(
        "SELECT path FROM rubrics WHERE parent_id=?", (src_id,)).fetchall()]
    # Pré-vérification des collisions AVANT toute écriture (message clair
    # plutôt qu'une IntegrityError UNIQUE au milieu de la transaction).
    for child_path in children:
        leaf = child_path.rsplit("/", 1)[-1]
        if rubrics.get_rubric_id(conn, f"{dst_path}/{leaf}") is not None:
            raise ValueError(
                f"collision : {dst_path}/{leaf} existe déjà — merger d'abord les enfants")
    src_row = conn.execute(
        "SELECT label, kind_hint, created_ts FROM rubrics WHERE id=?", (src_id,)).fetchone()
    try:
        for child_path in children:
            leaf = child_path.rsplit("/", 1)[-1]
            # cascade SANS log ni commit : on est dans la transaction du merge
            _rename_core(conn, child_path, f"{dst_path}/{leaf}")
        for eid, conf in eps:
            rubrics._attach_core(conn, eid, dst_path,
                                 conf if conf is not None else 0.9, now)
        conn.execute("DELETE FROM rubrics WHERE id=?", (src_id,))
        recompute_centroid(conn, dst_path)
        if _log:
            _log_op(conn, f"merge {src_path} → {dst_path}",
                    {"op": "unmerge", "src": src_path, "dst": dst_path,
                     "label": src_row[0], "kind_hint": src_row[1],
                     "created_ts": src_row[2],
                     "episodes": [[e, c] for e, c in eps],
                     "children": [f"{dst_path}/{c.rsplit('/', 1)[-1]}" for c in children]})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"moved_episodes": len(eps), "moved_children": len(children)}


def reclassify(conn, episode_id, new_path, now, _log=True):
    """Déplace UNE mémoire vers new_path (conf 1.0 = choix délibéré) ; None →
    détache (redevient orpheline). Retourne le path final ou 'orphelin'."""
    try:
        result, old_path, old_conf = _reclassify_core(conn, episode_id, new_path, now)
        if _log:
            _log_op(conn, f"reclassify #{episode_id} → {result}",
                    {"op": "reclassify", "episode_id": episode_id,
                     "path": old_path, "conf": old_conf})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return result


# ---------- gardes anti-explosion (distinctivité + masse/cohérence) ----------

def _cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def distinctiveness_guard(conn, emb):
    """(ok, closest_path, sim) — ok=False si emb est trop proche (> TAX_DISTINCT_MAX)
    du centroïde d'une rubrique existante : router/fusionner plutôt que créer.
    DB sans centroïde (aucune rubrique, ou rubriques vides) → (True, None, 0.0)."""
    best_path, best_sim = None, 0.0
    for path, raw in conn.execute(
            "SELECT path, centroid FROM rubrics WHERE centroid IS NOT NULL").fetchall():
        sim = _cosine(rubrics._parse_embedding(raw), emb)
        if sim > best_sim:
            best_path, best_sim = path, sim
    return (best_sim <= config.TAX_DISTINCT_MAX), best_path, best_sim


def orphan_clusters(conn, min_n=None, min_sim=None):
    """Clusters cohérents parmi les orphelins (glouton par similarité).
    Retourne [{"episode_ids": [...], "coherence": moyenne des sims à la graine}]
    — seuls les clusters de taille >= min_n et cohérence >= min_sim sortent.
    O(n²) sur les SEULS orphelins à embedding exploitable (borné en pratique) ;
    0 orphelin → []. Un épisode émis appartient à AU PLUS un cluster (`used`)."""
    min_n = min_n or config.TAX_ORPHAN_MIN
    min_sim = min_sim or config.TAX_CLUSTER_MIN_SIM
    rows = conn.execute(
        "SELECT id, embedding FROM episodes WHERE rubric_id IS NULL "
        "AND role IN ('semantic','episodic','reference','reasoning')").fetchall()
    items = [(eid, rubrics._parse_embedding(raw)) for eid, raw in rows]
    items = [(eid, e) for eid, e in items if e]
    used, clusters = set(), []
    for i, (eid, emb) in enumerate(items):
        if eid in used:
            continue
        members = [(eid, 1.0)]
        for ej, ee in items[i + 1:]:
            if ej in used:
                continue
            s = _cosine(emb, ee)
            if s >= min_sim:
                members.append((ej, s))
        if len(members) >= min_n:
            for m_id, _s in members:
                used.add(m_id)
            coh = sum(s for _m, s in members) / len(members)
            clusters.append({"episode_ids": [m for m, _s in members],
                             "coherence": round(coh, 4)})
    return clusters


# ---------- undo (1 cran) ----------

_OPS_INVERSES = ("rename", "relabel", "unmerge", "reclassify")


def _appliquer_inverse_core(conn, inv):
    """Applique l'opération inverse d'une mutation (cœur partagé par undo_last et le registre).
    Ne committe pas."""
    op = inv.get("op")
    if op == "rename":
        _rename_core(conn, inv["old"], inv["new"])
    elif op == "relabel":
        rid = _rid(conn, inv["path"])
        conn.execute("UPDATE rubrics SET label=? WHERE id=?", (inv["label"], rid))
    elif op == "unmerge":
        _create_rubric_core(conn, inv["src"], inv.get("created_ts") or time.time(),
                            label=inv.get("label"), kind_hint=inv.get("kind_hint"))
        for child in inv.get("children", []):
            leaf = child.rsplit("/", 1)[-1]
            _rename_core(conn, child, f"{inv['src']}/{leaf}")
        now = time.time()
        for eid, conf in inv.get("episodes", []):
            rubrics._attach_core(conn, eid, inv["src"],
                                 conf if conf is not None else 0.9, now)
        recompute_centroid(conn, inv["src"])
        recompute_centroid(conn, inv["dst"])
    elif op == "reclassify":
        if inv.get("path") is None:
            _reclassify_core(conn, inv["episode_id"], None, time.time())
        else:
            rubrics._attach_core(conn, inv["episode_id"], inv["path"],
                                 inv.get("conf") if inv.get("conf") is not None else 0.9,
                                 time.time())


def appliquer_inverse(conn, inv, ts=None):
    """Applique l'inverse `inv` (annulation par le registre) et retire du journal de taxonomie
    l'entrée correspondante (même ts), pour qu'undo_last ne la ré-applique pas. Ne committe pas."""
    if not isinstance(inv, dict) or inv.get("op") not in _OPS_INVERSES:
        raise ValueError(f"inverse inconnu : {inv!r}")
    _appliquer_inverse_core(conn, inv)
    if ts is not None:
        restes = [e for e in log_entries(conn) if not (isinstance(e, dict) and e.get("ts") == ts)]
        _kv_set(conn, "taxonomy_log", json.dumps(restes, ensure_ascii=False))


def undo_last(conn):
    """Annule la DERNIÈRE mutation (1 cran), en UNE transaction — uniquement
    des cœurs sans commit. Retourne la description annulée, ou
    "(rien à annuler)". Si l'état a bougé depuis (rubrique/épisode disparu),
    l'undo échoue ENTIER (rollback, l'entrée reste dans le journal).
    Limite assumée : undo d'un merge ne restaure pas les centroïdes
    incrémentaux exacts de src/dst — ils sont RECALCULÉS depuis les embeddings
    réels (recompute_centroid, plus fiable que l'historique)."""
    entries = log_entries(conn)
    if not entries:
        return "(rien à annuler)"
    last = entries.pop()
    # Rider T1 : gardes de type AVANT tout .get — un journal kv de forme
    # hostile (élément non-dict, ex. '[42]', ou inverse non-dict) levait une
    # AttributeError AVANT le try, l'entrée toxique n'était jamais retirée et
    # l'undo restait wedgé à jamais. Forme hostile → op=None → branche
    # « entrée inconnue » ci-dessous, qui purge et continue.
    inv = last.get("inverse") if isinstance(last, dict) else None
    if not isinstance(inv, dict):
        inv = {}
    op = inv.get("op")
    try:
        if op in _OPS_INVERSES:
            _appliquer_inverse_core(conn, inv)
        else:
            # Entrée illisible (format inconnu) : on la retire du journal pour
            # ne pas bloquer l'undo à jamais, sans rien toucher d'autre.
            _kv_set(conn, "taxonomy_log", json.dumps(entries, ensure_ascii=False))
            conn.commit()
            return "(entrée de journal inconnue — retirée, rien annulé)"
        _kv_set(conn, "taxonomy_log", json.dumps(entries, ensure_ascii=False))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return f"annulé : {last.get('desc', op)}"

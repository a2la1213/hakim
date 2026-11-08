"""dream_resemblance.py — Mesure OBJECTIVE de sensibilité (HORS verdict pré-enregistré).

Ressemblance de chaque rêve au CENTROÏDE de la mémoire RÉELLE d'Ahmed (cosinus embedding).
Contrôle croisé de la métrique mots-clés (dream_domains) : elle rate le contenu cryptique
(ex. « Q72 », « topologie »), pas l'embedding. Ne modifie PAS les Portes A/B/C — c'est un
second regard objectif. Pur en tête (stdlib), I/O ensuite ; embed_fn injectable (testable
sans modèle). Réutilise dream_ablation.load_cells comme source de vérité des cellules."""
import json as _json
import math

import dream_ablation as A

_ANALYSIS_ROLES = ("semantic", "episodic", "reasoning")


def _cos(a, b):
    d = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return d / (na * nb) if na and nb else 0.0


def corpus_centroid(conn, roles=_ANALYSIS_ROLES):
    """Centroïde (moyenne) des embeddings des souvenirs RÉELS (corpus d'Ahmed). Exclut
    rêves/insights/dream_log. [] si aucun embedding. Best-effort (erreur SQL → [])."""
    ph = ",".join("?" * len(roles))
    embs = []
    try:
        rows = conn.execute(
            f"SELECT embedding FROM episodes WHERE role IN ({ph}) "
            f"AND embedding IS NOT NULL AND embedding != '[]'", tuple(roles)).fetchall()
    except Exception:
        return []
    for (e,) in rows:
        try:
            v = _json.loads(e)
        except Exception:
            continue
        if v:
            embs.append(v)
    if not embs:
        return []
    dim = len(embs[0])
    return [sum(e[i] for e in embs) / len(embs) for i in range(dim)]


def cell_resemblance(conn, embed_fn, centroid=None):
    """{(model, condition): ressemblance moyenne au corpus} sur les cellules dream_ablation.
    embed_fn(text)->vec injectable. centroid calculé si None. {} si pas de centroïde."""
    if centroid is None:
        centroid = corpus_centroid(conn)
    out = {}
    if not centroid:
        return out
    cells = A.load_cells(conn)["cells"]
    for (mdl, co), by in cells.items():
        sims = []
        for texts in by.values():
            for t in texts:
                if not t:
                    continue
                try:
                    sims.append(_cos(embed_fn(t), centroid))
                except Exception:
                    pass
        if sims:
            out[(mdl, co)] = round(sum(sims) / len(sims), 4)
    return out


def report_data(conn, embed_fn):
    """JSON pour le cockpit : {qwen:{on,off,free,gap}, sonnet:{...}, centroid_n:N}.
    gap = ressemblance(ON) − ressemblance(OFF-neutre). >0 = le corpus rapproche le rêve
    de la mémoire réelle (le corpus façonne le contenu, mesuré objectivement)."""
    centroid = corpus_centroid(conn)
    res = cell_resemblance(conn, embed_fn, centroid)
    data = {"centroid_n": 0 if not centroid else 1}
    for mdl in ("qwen", "sonnet"):
        on = res.get((mdl, "brain_on"))
        off = res.get((mdl, "brain_off"))
        data[mdl] = {"on": on, "off": off, "free": res.get((mdl, "brain_off_free")),
                     "gap": round(on - off, 4) if (on is not None and off is not None) else None}
    return data

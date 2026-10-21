"""Saillance — décide quoi récupérer et quoi retenir.

Inspiré des Generative Agents (Park et al., Stanford 2023) :
    score = pertinence (similarité) + récence (décroissance) + importance.
Le poids émotionnel (couche affective) s'ajoutera en Phase 2.
"""
import re

import numpy as np

import config


def tokens(s):
    """Ensemble des mots (minuscules) — LA tokenisation de lexical_overlap."""
    return set(re.findall(r"\w+", (s or "").lower()))


_tokens = tokens  # alias historique (usages internes)


def lexical_overlap(query_text, content):
    """Fraction des mots de la requête présents dans le contenu (0..1)."""
    return lexical_overlap_from_tokens(_tokens(query_text), _tokens(content))


def lexical_overlap_from_tokens(q_tokens, c_tokens):
    """Cœur de lexical_overlap sur des ensembles DÉJÀ tokenisés (Durci #2).

    Permet au rappel de tokeniser la requête UNE fois (au lieu d'une fois
    par ligne) et de mémoïser les contenus : mêmes entiers, même division,
    donc mêmes flottants bit à bit que lexical_overlap."""
    if not q_tokens:
        return 0.0
    return len(q_tokens & c_tokens) / len(q_tokens)


def facet_overlap(query_facets, ep_facets):
    """Jaccard PUR entre deux ensembles de slugs de facettes : |∩| / |∪|.

    0.0 si l'un des deux est vide. Utilitaire ensembliste (Phase 3.5b) —
    PAS un 2e signal de similarité : aucun poids, aucun embedding.
    """
    a, b = set(query_facets or ()), set(ep_facets or ())
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cosine(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def cosine_many(mat, q):
    """Cosine BATCHÉ (Durci #2) : équivalent ligne à ligne de cosine(q, mat[i]),
    mais en UNE opération matricielle — les O(n) produits scalaires de la
    boucle Python deviennent `mat @ q`.

    mat : séquence de n lignes numériques de MÊME dimension que q (l'appelant
    filtre en amont les embeddings vides/dépareillés, comme la garde
    historique de Memory.retrieve). Retourne un ndarray float de taille n.
    MÊME formule que cosine : dot / (||ligne|| * ||q||) ; ligne de norme
    nulle (ou q nul) -> 0.0. Seule différence possible : l'ordre
    d'accumulation flottante du BLAS (écart << 1e-9 sur des cosinus [-1, 1]).
    """
    mat = np.asarray(mat, dtype=float)
    q = np.asarray(q, dtype=float)
    out = np.zeros(mat.shape[0] if mat.ndim > 0 else 0, dtype=float)
    if mat.size == 0:
        return out
    nq = np.linalg.norm(q)
    if nq == 0.0:
        return out
    dots = mat @ q  # LA matmul : tous les produits scalaires d'un coup
    norms = np.linalg.norm(mat, axis=1)
    nz = norms != 0.0
    out[nz] = dots[nz] / (norms[nz] * nq)
    return out


def recency(ts, now, halflife_h=config.RECENCY_HALFLIFE_HOURS):
    age_h = max(0.0, (now - ts) / 3600.0)
    return 0.5 ** (age_h / halflife_h)


def score(query_emb, row_emb, ts, importance, now):
    rel = cosine(query_emb, row_emb)
    rec = recency(ts, now)
    total = (config.W_RELEVANCE * rel
             + config.W_RECENCY * rec
             + config.W_IMPORTANCE * float(importance))
    return total, {"relevance": rel, "recency": rec, "importance": float(importance)}

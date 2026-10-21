"""Tests Phase 3.5b — gate W_FACET (eval/tune_facet.py) — 100% synthétique.

AUCUN test ne touche data/memory.db (garde `_forbid_real_db` de conftest.py) :
DB temporaire migrée, facettes posées à la main, embed_fn injecté (pas de
modèle). Le candidat `make_score_facet` ajoute `W_FACET * facet_overlap`
par-dessus le score live, où `facet_overlap` est un JACCARD PUR sur les slugs
(|∩|/|∪|) — un utilitaire ensembliste, PAS un 2e signal de similarité (pas de
poids, pas d'embedding : c'est exactement ce que le gate doit départager).

DÉCISION 3.5b (mesurée sur la vraie base, 2026-07-02, 2 runs identiques) :
NON CÂBLÉ. Baseline live p@6 = 0.661 (1201 épisodes, 597 taggés = 50%) ;
meilleur candidat 0.677 à W=0.1 (+0.016 < marge +0.02), W=0.2/0.3 neutres,
W=0.45 dégrade (0.646). Le cas 4 documente que le scoring de
`Memory.retrieve` reste le live PUR, sans terme facette.
"""

import time

import pytest

import config
import migrations
import salience
from eval.run_eval import gate, make_score_live
from eval.tune_facet import load_facets_by_episode, make_score_facet
from memory import Memory

NOW = 2000.0


# --- Cas 1 : facet_overlap = Jaccard pur -------------------------------------


def test_facet_overlap_jaccard():
    """|∩|/|∪| exact ; disjoint → 0 ; vide (un côté ou les deux) → 0."""
    # ∩ = {b, c} (2), ∪ = {a, b, c, d} (4) → 0.5
    assert salience.facet_overlap({"a", "b", "c"}, {"b", "c", "d"}) == 0.5
    # identiques → 1.0 ; sous-ensemble → |∩|/|∪| strict
    assert salience.facet_overlap({"x", "y"}, {"x", "y"}) == 1.0
    assert salience.facet_overlap({"x"}, {"x", "y", "z", "w"}) == 0.25
    # disjoints → 0.0
    assert salience.facet_overlap({"a"}, {"b"}) == 0.0
    # l'un ou l'autre vide → 0.0 (et les deux vides : pas de division par zéro)
    assert salience.facet_overlap(set(), {"a"}) == 0.0
    assert salience.facet_overlap({"a"}, set()) == 0.0
    assert salience.facet_overlap(set(), set()) == 0.0


# --- Cas 2 : le candidat = live + W * Jaccard(facettes requête, épisode) ------

# La requête « recentrage caméra three.js » a pour facettes extraites
# {recentrage, camera, three.js} (facets_extract, lexical déterministe).
_QUERY = "recentrage caméra three.js"
_FACETS = {
    1: frozenset({"camera", "three.js"}),   # ∩=2, ∪=3 avec la requête → 2/3
    2: frozenset({"sqlite", "migration"}),  # disjoint → 0
}


def _ep(id_, emb=(0.5, 0.5), content="contenu sans mot commun"):
    return {
        "id": id_,
        "ts": NOW - 3600.0,
        "role": "semantic",
        "content": content,
        "importance": 0.5,
        "embedding": list(emb),
    }


def test_bonus_episode_partageant_des_facettes_pas_les_autres():
    """Épisode partageant des facettes : +W*Jaccard exactement ; facettes
    disjointes ou épisode sans facette (AppLecture arabe) : score live pur."""
    live = make_score_live(NOW)
    cand = make_score_facet(_FACETS, 0.3, now=NOW)
    q_emb = [1.0, 0.0]

    ep1, ep2, ep3 = _ep(1), _ep(2), _ep(3)  # 3 : absent du dict = non taggé
    assert cand(_QUERY, q_emb, ep1) == pytest.approx(
        live(_QUERY, q_emb, ep1) + 0.3 * (2 / 3)
    )
    assert cand(_QUERY, q_emb, ep2) == live(_QUERY, q_emb, ep2)
    assert cand(_QUERY, q_emb, ep3) == live(_QUERY, q_emb, ep3)


def test_w_zero_identique_au_live():
    """W_FACET=0 : score strictement identique au live, overlap ou pas."""
    live = make_score_live(NOW)
    cand0 = make_score_facet(_FACETS, 0.0, now=NOW)
    for ep in (_ep(1), _ep(2), _ep(3)):
        assert cand0(_QUERY, [1.0, 0.0], ep) == live(_QUERY, [1.0, 0.0], ep)


def test_requete_sans_facette_degrade_en_live():
    """Requête sans facette extractible (que des stopwords) : overlap 0
    partout = score live exact (dégradation propre)."""
    live = make_score_live(NOW)
    cand = make_score_facet(_FACETS, 0.45, now=NOW)
    q = "de la et le un"  # extract_facets → []
    for ep in (_ep(1), _ep(2)):
        assert cand(q, [1.0, 0.0], ep) == live(q, [1.0, 0.0], ep)


def test_load_facets_by_episode_precharge_les_slugs(tmp_path):
    """Préchargement dict {episode_id: frozenset(slugs)} (pas de N+1) ;
    épisode sans facette ABSENT du dict."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    e1 = m.add("user", "episode un", extract_facets=False)
    e2 = m.add("user", "episode deux", extract_facets=False)
    m.tag_episode(e1, [("camera", 1.0), ("three.js", 0.5)])

    facets = load_facets_by_episode(m.db)
    assert facets == {e1: frozenset({"camera", "three.js"})}
    assert e2 not in facets
    m.db.close()


# --- Cas 3 : le gate discrimine — candidat meilleur passe, pire échoue --------

# Requête à facettes {camera, three.js, orbit-controls} ; A (id 1) porte les
# 3 facettes (Jaccard 1.0) mais rel=0.8 ; B (id 2) rel=1.0 sans facette.
# Le live classe B devant A ; le bonus facette W=0.45 > 0.2 remet A devant.
_QUERY_GATE = "caméra three.js orbit-controls"
_QUERY_EMBS = {_QUERY_GATE: [1.0, 0.0]}
_FACETS_GATE = {1: frozenset({"camera", "three.js", "orbit-controls"})}


def _embed_synthetique(text):
    return _QUERY_EMBS[text]


def _episodes_gate():
    return [
        _ep(1, emb=(0.8, 0.6), content="contenu sans mot commun a"),
        _ep(2, emb=(1.0, 0.0), content="contenu sans mot commun b"),
    ]


def test_gate_candidat_meilleur_passe():
    queries = [{"query": _QUERY_GATE, "expected": [1], "note": "A est le pertinent"}]
    res = gate(
        make_score_facet(_FACETS_GATE, 0.45, now=NOW),
        make_score_live(NOW),
        queries,
        _episodes_gate(),
        k=1,
        embed_fn=_embed_synthetique,
    )
    assert res["baseline"] == 0.0   # le live met B (plus similaire) en tête
    assert res["candidate"] == 1.0  # le bonus facette remet A en tête
    assert res["passes"] is True


def test_gate_candidat_pire_echoue():
    queries = [{"query": _QUERY_GATE, "expected": [2], "note": "B est le pertinent"}]
    res = gate(
        make_score_facet(_FACETS_GATE, 0.45, now=NOW),
        make_score_live(NOW),
        queries,
        _episodes_gate(),
        k=1,
        embed_fn=_embed_synthetique,
    )
    assert res["baseline"] == 1.0
    assert res["candidate"] == 0.0
    assert res["passes"] is False


# --- Cas 4 : décision 3.5b = NON câblé — Memory.retrieve reste le live PUR ----
# Même géométrie que le cas 3 : A porte EXACTEMENT les facettes de la requête
# (Jaccard 1.0), B est plus similaire en embedding. Si un terme W_FACET était
# câblé dans retrieve (W>0.2 : inversion d'ordre ; tout W>0 : écart de score),
# ce test le verrait. Le gate a dit NON (0.677 à W=0.1 vs live 0.661,
# marge < +0.02) : retrieve doit garder l'ordre live (B devant) et un score
# = formule live EXACTE, sans terme ajouté. Arité 5 stricte.


def test_retrieve_reste_le_live_pur_sans_terme_facette(tmp_path):
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    a = m.add("user", "episode cible", embedding=[0.8, 0.6], extract_facets=False)
    m.add("user", "episode distracteur", embedding=[1.0, 0.0], extract_facets=False)
    # A porte les facettes EXACTES de la requête (Jaccard 1.0 si retrieve
    # calculait un overlap) ; B n'a aucune facette. Contenus sans mot commun
    # avec la requête : le lexical live ne masque rien.
    m.tag_episode(a, [("camera", 1.0), ("three.js", 1.0), ("orbit-controls", 1.0)])

    now = time.time()
    q, q_emb = "caméra three.js orbit-controls", [1.0, 0.0]
    res = m.retrieve(q, q_emb, now=now)

    # Ordre live : B (rel=1.0) devant A (rel=0.8) — aucun bonus facette n'a inversé.
    assert [r[3] for r in res] == ["episode distracteur", "episode cible"]

    # Score = formule live EXACTE (rel/lex/rec/imp, poids config) : un terme
    # facette câblé apparaîtrait ici comme un écart sur A. Arité 5 stricte.
    embs = {"episode cible": [0.8, 0.6], "episode distracteur": [1.0, 0.0]}
    for s, ts, role, content, parts in res:
        attendu = (
            config.W_RELEVANCE * salience.cosine(q_emb, embs[content])
            + config.W_LEXICAL * salience.lexical_overlap(q, content)
            + config.W_RECENCY * salience.recency(ts, now)
            + config.W_IMPORTANCE * 0.5
        )
        assert s == pytest.approx(attendu)
        assert set(parts) == {"rel", "lex", "rec"}
    m.db.close()


def test_w_facet_absent_de_config():
    """La décision 3.5b laisse W_FACET HORS de config : le terme n'a pas
    passé le gate (documente l'issue négative, cf. task-3.5b-report.md)."""
    assert not hasattr(config, "W_FACET")

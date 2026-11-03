"""Tests Phase 1C — gate rubrique-aware (eval/tune_rubric.py) — 100% synthétique.

AUCUN test ne touche data/memory.db (garde `_forbid_real_db` de conftest.py) :
DB temporaire migrée + squelette seedé, centroïdes 2D posés à la main,
embed_fn injecté (pas de modèle). Le candidat `make_score_rubric` ajoute un
bonus CATÉGORIEL (0/1 × W) par-dessus le score live — jamais un 2e signal de
similarité (le double-comptage embedding est exactement ce que le gate mesure).

DÉCISION 1C (mesurée sur la vraie base, 2026-07-02) : NON CÂBLÉ. Meilleur
candidat p@6 = 0.677 à W=0.05 vs live 0.661 (+0.016 < marge +0.02), et la
tendance s'inverse vite (W=0.4 → 0.524). Le cas 4 documente que le scoring
de `Memory.retrieve` reste le live PUR, sans terme rubrique.
"""

import sqlite3
import time

import pytest

import config
import migrations
import rubrics
import salience
from eval.run_eval import gate, make_score_live
from eval.tune_rubric import make_score_rubric, subtree_rubric_ids
from memory import Memory

NOW = 2000.0


@pytest.fixture
def routed_db(tmp_path):
    """DB migrée + squelette, 2 centroïdes 2D posés à la main.

    Une requête d'embedding [1,0] route vers projets/anamnese (cos=1.0),
    [0,1] vers savoir-applecture. Pas d'épisodes en table : le score_fn ne lit
    la DB que pour router la requête + résoudre le sous-arbre de rubriques.
    """
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    migrations.migrate(conn)
    rubrics.seed_skeleton(conn, now=1000.0)
    conn.execute(
        "UPDATE rubrics SET centroid='[1.0, 0.0]', centroid_n=1 "
        "WHERE path='projets/anamnese'"
    )
    conn.execute(
        "UPDATE rubrics SET centroid='[0.0, 1.0]', centroid_n=1 "
        "WHERE path='savoir-applecture'"
    )
    conn.commit()
    yield conn
    conn.close()


def _rid(conn, path):
    return rubrics.get_rubric_id(conn, path)


def _ep(id_, emb, rubric_id, content="contenu sans mot commun"):
    return {
        "id": id_,
        "ts": NOW - 3600.0,
        "role": "semantic",
        "content": content,
        "importance": 0.5,
        "embedding": emb,
        "rubric_id": rubric_id,
    }


# --- Cas 1 : le bonus est catégoriel, sur le sous-arbre de la rubrique cible ---


def test_bonus_same_rubric_not_other(routed_db):
    """Épisode de la rubrique cible : +W exactement ; autre rubrique : score live."""
    ep_meme = _ep(1, [0.5, 0.5], _rid(routed_db, "projets/anamnese"))
    ep_autre = _ep(2, [0.5, 0.5], _rid(routed_db, "savoir-applecture"))
    live = make_score_live(NOW)
    cand = make_score_rubric(routed_db, 0.2, now=NOW)

    q, q_emb = "requete anamnese", [1.0, 0.0]  # route vers projets/anamnese
    assert cand(q, q_emb, ep_meme) == pytest.approx(live(q, q_emb, ep_meme) + 0.2)
    assert cand(q, q_emb, ep_autre) == live(q, q_emb, ep_autre)


def test_bonus_couvre_le_sous_arbre(routed_db):
    """Épisode rangé dans un ENFANT de la rubrique cible : bonus aussi
    (episode.rubric_id ∈ subtree(rubrique cible), pas égalité stricte)."""
    ep_enfant = _ep(1, [0.5, 0.5], _rid(routed_db, "projets/anamnese/memoire-2.0"))
    live = make_score_live(NOW)
    cand = make_score_rubric(routed_db, 0.3, now=NOW)

    q, q_emb = "requete", [1.0, 0.0]
    assert cand(q, q_emb, ep_enfant) == pytest.approx(live(q, q_emb, ep_enfant) + 0.3)


def test_w_zero_identique_au_live(routed_db):
    """W_RUBRIC_MATCH=0 : score strictement identique au live, bonus ou pas."""
    live = make_score_live(NOW)
    cand0 = make_score_rubric(routed_db, 0.0, now=NOW)
    eps = [
        _ep(1, [0.5, 0.5], _rid(routed_db, "projets/anamnese")),
        _ep(2, [0.5, 0.5], _rid(routed_db, "savoir-applecture")),
        _ep(3, [0.5, 0.5], None),  # jamais routé
    ]
    for ep in eps:
        assert cand0("q", [1.0, 0.0], ep) == live("q", [1.0, 0.0], ep)


def test_requete_non_routable_degrade_en_live(routed_db):
    """Requête non routable (embedding vide, ou anti-corrélé → plancher
    1B-harden) : bonus 0 partout = score live exact (dégradation propre)."""
    live = make_score_live(NOW)
    cand = make_score_rubric(routed_db, 0.4, now=NOW)
    ep = _ep(1, [0.5, 0.5], _rid(routed_db, "projets/anamnese"))

    assert cand("q", [], ep) == live("q", [], ep)  # embedding vide
    # anti-corrélé : cos <= 0 sur tous les centroïdes → route None
    assert cand("q", [-1.0, 0.0], ep) == live("q", [-1.0, 0.0], ep)


def test_episode_jamais_route_sans_bonus(routed_db):
    """rubric_id NULL (état neutre valide) : jamais de bonus."""
    live = make_score_live(NOW)
    cand = make_score_rubric(routed_db, 0.4, now=NOW)
    ep = _ep(1, [1.0, 0.0], None)
    assert cand("q", [1.0, 0.0], ep) == live("q", [1.0, 0.0], ep)


def test_subtree_rubric_ids(routed_db):
    """Résolution sous-arbre → ids : racine + descendants ; inexistante → vide."""
    ids = subtree_rubric_ids(routed_db, "projets/anamnese")
    attendus = {
        _rid(routed_db, "projets/anamnese"),
        _rid(routed_db, "projets/anamnese/daemon-consolidation"),
        _rid(routed_db, "projets/anamnese/memoire-2.0"),
    }
    assert ids == frozenset(attendus)
    assert subtree_rubric_ids(routed_db, "rubrique-inconnue") == frozenset()


# --- Cas 2 : le gate discrimine — candidat meilleur passe, pire échoue ---------

# Requête [1,0] ; A (attendu possible) rel=0.8 dans la rubrique cible,
# B (distracteur) rel=1.0 dans l'autre rubrique. Le live classe B devant A ;
# le bonus rubrique W=0.4 fait passer A devant (0.8+0.4 > 1.0).
_QUERY_EMBS = {"alpha": [1.0, 0.0]}


def _embed_synthetique(text):
    return _QUERY_EMBS[text]


def _episodes_gate(conn):
    return [
        _ep(1, [0.8, 0.6], _rid(conn, "projets/anamnese")),  # A : rubrique cible
        _ep(2, [1.0, 0.0], _rid(conn, "savoir-applecture")),  # B : plus similaire
    ]


def test_gate_candidat_meilleur_passe(routed_db):
    queries = [{"query": "alpha", "expected": [1], "note": "A est le pertinent"}]
    res = gate(
        make_score_rubric(routed_db, 0.4, now=NOW),
        make_score_live(NOW),
        queries,
        _episodes_gate(routed_db),
        k=1,
        embed_fn=_embed_synthetique,
    )
    assert res["baseline"] == 0.0  # le live met B (distracteur) en tête
    assert res["candidate"] == 1.0  # le bonus rubrique remet A en tête
    assert res["passes"] is True


def test_gate_candidat_pire_echoue(routed_db):
    queries = [{"query": "alpha", "expected": [2], "note": "B est le pertinent"}]
    res = gate(
        make_score_rubric(routed_db, 0.4, now=NOW),
        make_score_live(NOW),
        queries,
        _episodes_gate(routed_db),
        k=1,
        embed_fn=_embed_synthetique,
    )
    assert res["baseline"] == 1.0
    assert res["candidate"] == 0.0
    assert res["passes"] is False


# --- Cas 4 : décision 1C = NON câblé — Memory.retrieve reste le live PUR -------
# Même géométrie que le cas 2 : si un bonus rubrique était câblé (W>=0.25, la
# requête routant vers projets/anamnese), A passerait devant B. Le gate a dit
# NON (0.677 à W=0.05 vs live 0.661, marge < +0.02) : retrieve doit garder
# l'ordre live (B devant) et un score = formule live EXACTE, sans terme ajouté.


def test_retrieve_reste_le_live_pur_sans_terme_rubrique(tmp_path):
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    rubrics.seed_skeleton(m.db, now=1000.0)
    m.store_in("episode rubrique cible", "projets/anamnese", embedding=[0.8, 0.6])
    m.store_in("episode distracteur", "savoir-applecture", embedding=[1.0, 0.0])
    # centroïdes posés pour qu'une requête [1,0] ROUTERAIT vers projets/anamnese
    # (le sous-arbre de A) si retrieve routait — il ne doit PAS le faire.
    m.db.execute(
        "UPDATE rubrics SET centroid='[1.0, 0.0]', centroid_n=1 "
        "WHERE path='projets/anamnese'"
    )
    m.db.execute(
        "UPDATE rubrics SET centroid='[0.0, 1.0]', centroid_n=1 "
        "WHERE path='savoir-applecture'"
    )
    m.db.commit()

    now = time.time()
    q_emb = [1.0, 0.0]
    res = m.retrieve("requete", q_emb, now=now)

    # Ordre live : B (rel=1.0) devant A (rel=0.8) — aucun bonus rubrique n'a inversé.
    assert [r[3] for r in res] == ["episode distracteur", "episode rubrique cible"]

    # Score = formule live EXACTE (rel/lex/rec/imp, poids config) : un terme
    # rubrique câblé apparaîtrait ici comme un écart sur A. Arité 5 stricte.
    embs = {
        "episode rubrique cible": [0.8, 0.6],
        "episode distracteur": [1.0, 0.0],
    }
    for s, ts, role, content, parts in res:
        attendu = (
            config.W_RELEVANCE * salience.cosine(q_emb, embs[content])
            + config.W_LEXICAL * salience.lexical_overlap("requete", content)
            + config.W_RECENCY * salience.recency(ts, now)
            + config.W_IMPORTANCE * 0.5
        )
        assert s == pytest.approx(attendu)
        assert set(parts) == {"rel", "lex", "rec"}
    m.db.close()


def test_w_rubric_match_absent_de_config():
    """La décision 1C laisse W_RUBRIC_MATCH HORS de config : le terme n'a pas
    passé le gate (documente l'issue négative, cf. task-1C-report.md)."""
    assert not hasattr(config, "W_RUBRIC_MATCH")

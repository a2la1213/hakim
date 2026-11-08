"""Tests du rappel VECTORISÉ (Durci #2) — Memory.retrieve en matmul batchée.

La boucle Python O(n) de cosinus est remplacée par UNE opération matricielle
(emb_matrix @ query_vec, salience.cosine_many). Invariants durs vérifiés ici :
  1. ÉQUIVALENCE : pour chaque épisode, le score du retrieve vectorisé est
     identique (<= 1e-9) à la référence per-row historique (salience.cosine +
     lexical_overlap + recency + poids config.W_*), et l'ORDRE (donc les ids
     du top-k) est identique — ties départagés par l'ordre de la table,
     comme le tri stable historique.
  2. Arité 5 du tuple retourné inchangée.
  3. Effets de bord de reconsolidate=True intacts : recall_count bumpé,
     coactivation loguée (paires du top_k), mémoire de travail touchée.
  4. Embeddings vides/dépareillés/nuls : rel = 0.0 comme la garde historique ;
     DB legacy (aucune ligne numpy-able) fonctionne toujours. TEXT JSON
     scalaire ('null', '0', 'false') : rel = 0.0 SANS TypeError (garde
     isinstance(list) — l'ancien code per-row le traitait comme falsy).

DB temporaire uniquement — JAMAIS data/memory.db (garde autouse conftest.py).
Embeddings synthétiques déterministes (graine fixe) : aucun modèle chargé.
"""

import json
import time

import numpy as np
import pytest

import config
import migrations
import salience
from memory import Memory

NOW = 1_750_000_000.0  # figé : récence déterministe


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire migrée 2.0 (recall_count, coactivation, kv)."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _seed(mem, n=40, dim=8, seed=42):
    """n épisodes aux embeddings pseudo-aléatoires reproductibles + cas limites.

    ts étalés dans le passé (récence variée), importances variées, contenus
    uniques (mapping content -> id pour vérifier l'ordre). Cas limites :
    embedding vide, dimension dépareillée, vecteur NUL (norme 0), doublon
    exact d'embedding (tie de cosinus -> départage par ordre de table).
    """
    rng = np.random.RandomState(seed)
    ids = {}
    for i in range(n):
        emb = [float(x) for x in rng.uniform(-1.0, 1.0, size=dim)]
        eid = mem.add("semantic" if i % 3 else "episodic",
                      f"episode numero {i} sujet memoire vectorisee",
                      importance=float((i % 10) / 10.0),
                      embedding=emb, extract_facets=False)
        ids[f"episode numero {i} sujet memoire vectorisee"] = eid
    edge = [
        ("embedding vide legacy", []),
        ("dimension depareillee", [1.0, 2.0]),
        ("vecteur nul norme zero", [0.0] * dim),
        ("doublon exact du zero", [0.0] * dim),  # tie -> ordre de table
    ]
    for content, emb in edge:
        ids[content] = mem.add("semantic", content, importance=0.5,
                               embedding=emb, extract_facets=False)
    # ts étalés (déterministes) : récence non triviale mais reproductible
    rows = mem.db.execute("SELECT id FROM episodes ORDER BY id").fetchall()
    for k, (eid,) in enumerate(rows):
        mem.db.execute("UPDATE episodes SET ts=? WHERE id=?",
                       (NOW - 3600.0 * (k * 7 % 300), eid))
    mem.db.commit()
    return ids


def _reference_scores(mem, query_text, query_emb, now, kinds=None):
    """MIROIR EXACT de la boucle per-row historique de Memory.retrieve
    (d'avant la vectorisation) : salience.cosine par ligne + lexical +
    récence + importance, tri stable décroissant. Retourne [(score, id)]."""
    rows = mem.db.execute(
        "SELECT id, ts, role, content, importance, embedding FROM episodes"
    ).fetchall()
    scored = []
    for eid, ts, role, content, importance, emb_json in rows:
        if kinds and role not in kinds:
            continue
        emb = json.loads(emb_json) if emb_json else None
        rel = (
            salience.cosine(query_emb, emb)
            if (query_emb and emb and len(emb) == len(query_emb))
            else 0.0
        )
        s = (
            config.W_RELEVANCE * rel
            + config.W_LEXICAL * salience.lexical_overlap(query_text, content)
            + config.W_RECENCY * salience.recency(ts, now)
            + config.W_IMPORTANCE * float(importance)
        )
        scored.append((s, eid))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


QUERY_TEXT = "sujet memoire vectorisee numero 7"
QUERY_EMB = [0.3, -0.7, 0.2, 0.9, -0.1, 0.5, -0.4, 0.8]


# --- Cas 1 : ÉQUIVALENCE — ids ET scores identiques à la référence per-row ---
def test_scores_and_order_match_reference_on_all_rows(mem):
    ids = _seed(mem)
    total = mem.count()
    ref = _reference_scores(mem, QUERY_TEXT, QUERY_EMB, NOW)
    got = mem.retrieve(QUERY_TEXT, QUERY_EMB, now=NOW, top_k=total)

    assert len(got) == len(ref) == total
    got_scores = np.array([r[0] for r in got])
    ref_scores = np.array([s for s, _eid in ref])
    # scores identiques à 1e-9, rang par rang (donc AUCUNE inversion d'ordre)
    assert np.max(np.abs(got_scores - ref_scores)) <= 1e-9
    # les ids du classement sont identiques (contenus uniques -> id)
    got_ids = [ids[r[3]] for r in got]
    assert got_ids == [eid for _s, eid in ref]


def test_topk_ids_and_scores_match_reference(mem):
    ids = _seed(mem)
    ref = _reference_scores(mem, QUERY_TEXT, QUERY_EMB, NOW)[:config.TOP_K]
    got = mem.retrieve(QUERY_TEXT, QUERY_EMB, now=NOW)  # top_k défaut

    assert [ids[r[3]] for r in got] == [eid for _s, eid in ref]
    for (ref_s, _eid), row in zip(ref, got):
        assert abs(row[0] - ref_s) <= 1e-9


def test_kinds_filter_keeps_index_alignment(mem):
    """Le filtre kinds retire des lignes AVANT la matmul : l'alignement
    ligne/score ne doit pas glisser (régression classique de vectorisation)."""
    ids = _seed(mem)
    ref = _reference_scores(mem, QUERY_TEXT, QUERY_EMB, NOW, kinds=["episodic"])
    got = mem.retrieve(QUERY_TEXT, QUERY_EMB, now=NOW, top_k=len(ref),
                       kinds=["episodic"])
    assert len(got) == len(ref) > 0
    assert [ids[r[3]] for r in got] == [eid for _s, eid in ref]
    assert np.max(np.abs(np.array([r[0] for r in got])
                         - np.array([s for s, _e in ref]))) <= 1e-9


def test_exact_tie_keeps_table_order(mem):
    """Deux embeddings bitwise identiques (les 2 vecteurs nuls) => scores à
    égalité stricte hors lex/rec/imp : le tri stable garde l'ordre de table."""
    ids = _seed(mem)
    got = mem.retrieve("vecteur norme", QUERY_EMB, now=NOW, top_k=mem.count())
    pos = {ids[r[3]]: rank for rank, r in enumerate(got)
           if r[3] in ("vecteur nul norme zero", "doublon exact du zero")}
    ref = {eid: rank for rank, (_s, eid) in enumerate(
        _reference_scores(mem, "vecteur norme", QUERY_EMB, NOW))}
    for content in ("vecteur nul norme zero", "doublon exact du zero"):
        assert pos[ids[content]] == ref[ids[content]]


# --- Cas 2 : arité 5 inchangée ---
def test_tuple_arity_is_five(mem):
    _seed(mem)
    for row in mem.retrieve(QUERY_TEXT, QUERY_EMB, now=NOW):
        s, ts, role, content, parts = row  # déballage strict : 5 éléments
        assert isinstance(s, float)
        assert isinstance(ts, float)
        assert isinstance(role, str)
        assert isinstance(content, str)
        assert set(parts) == {"rel", "lex", "rec"}


# --- Cas 3 : effets de bord de reconsolidate=True intacts ---
def test_reconsolidate_side_effects_still_fire(mem):
    ids = _seed(mem)
    top_ids = [eid for _s, eid in
               _reference_scores(mem, QUERY_TEXT, QUERY_EMB, NOW)[:3]]
    res = mem.retrieve(QUERY_TEXT, QUERY_EMB, now=NOW, top_k=3,
                       reconsolidate=True)
    assert [ids[r[3]] for r in res] == top_ids
    # recall_count bumpé sur EXACTEMENT les top_k rappelés
    bumped = [r[0] for r in mem.db.execute(
        "SELECT id FROM episodes WHERE recall_count > 0"
    ).fetchall()]
    assert sorted(bumped) == sorted(top_ids)
    # co-activation loguée : C(3,2) = 3 paires
    assert mem.db.execute(
        "SELECT COUNT(*) FROM coactivation"
    ).fetchone()[0] == 3
    # mémoire de travail touchée : les 3 rappelés sont montés en focus
    # (add() y avait déjà promu les seeds ; on vérifie l'inclusion + le ts)
    wm = mem.wm_get()
    focus_ids = {it["id"] for it in wm["focus"]}
    assert set(top_ids) <= focus_ids and wm["updated_ts"] == NOW


def test_default_readonly_no_side_effects(mem):
    _seed(mem)
    changes0 = mem.db.total_changes
    mem.retrieve(QUERY_TEXT, QUERY_EMB, now=NOW)
    assert mem.db.total_changes == changes0  # lecture STRICTEMENT seule


# --- Cas 4 : embeddings vides/dépareillés/nuls + legacy sans ligne numpy-able ---
def test_empty_and_mismatched_embeddings_get_zero_rel(mem):
    ids = _seed(mem)
    got = mem.retrieve(QUERY_TEXT, QUERY_EMB, now=NOW, top_k=mem.count())
    by_content = {r[3]: r for r in got}
    for content in ("embedding vide legacy", "dimension depareillee",
                    "vecteur nul norme zero"):
        assert by_content[content][4]["rel"] == 0.0  # skippé de la matmul
    assert ids  # les lignes restent candidates (présentes dans le retour)


def test_legacy_no_numpy_rows_still_works(tmp_path):
    """DB où AUCUNE ligne n'a d'embedding exploitable : pas de matmul du tout,
    le rappel retombe sur lex/récence/importance comme avant."""
    m = Memory(db_path=tmp_path / "legacy.db")
    m.add("user", "bonjour anamnese", embedding=[], extract_facets=False)
    m.add("assistant", "salut createur", embedding=None, extract_facets=False)
    ref = _reference_scores(m, "bonjour", [0.5, 0.5], NOW)
    got = m.retrieve("bonjour", [0.5, 0.5], now=NOW)
    assert len(got) == 2
    assert got[0][3] == "bonjour anamnese"  # le lexical départage
    for (ref_s, _eid), row in zip(ref, got):
        assert abs(row[0] - ref_s) <= 1e-9
        assert row[4]["rel"] == 0.0
    m.db.close()


def test_query_emb_falsy_all_rel_zero(mem):
    _seed(mem)
    for qe in (None, []):
        got = mem.retrieve(QUERY_TEXT, qe, now=NOW, top_k=5)
        assert got and all(r[4]["rel"] == 0.0 for r in got)


def test_scalar_json_embedding_text_no_crash_rel_zero(mem):
    """TEXT d'embedding qui est un scalaire JSON falsy ('null', '0', 'false')
    — writer legacy ou corruption : json.loads rend un scalaire que l'ancien
    code per-row traitait comme « pas d'embedding » (garde falsy -> rel = 0.0).
    np.asarray en ferait un tableau 0-d dont len() lève TypeError : la garde
    isinstance(list) doit restaurer rel = 0.0 SANS crash, et les lignes à
    embedding VALIDE doivent rester scorées à l'identique de la référence."""
    ids = _seed(mem)
    scalars = ("embedding texte null", "embedding texte zero",
               "embedding texte false")
    for content, raw in zip(scalars, ("null", "0", "false")):
        eid = mem.add("semantic", content, importance=0.5,
                      embedding=None, extract_facets=False)
        mem.db.execute("UPDATE episodes SET embedding=?, ts=? WHERE id=?",
                       (raw, NOW - 3600.0, eid))
        ids[content] = eid
    mem.db.commit()
    # Ne lève pas, et l'ÉQUIVALENCE per-row tient toujours : la référence
    # historique voit ces scalaires comme falsy (rel = 0.0), exactement le
    # comportement que la garde restaure. Les lignes valides sont intactes.
    ref = _reference_scores(mem, QUERY_TEXT, QUERY_EMB, NOW)
    got = mem.retrieve(QUERY_TEXT, QUERY_EMB, now=NOW, top_k=mem.count())
    assert [ids[r[3]] for r in got] == [eid for _s, eid in ref]
    assert np.max(np.abs(np.array([r[0] for r in got])
                         - np.array([s for s, _e in ref]))) <= 1e-9
    by_content = {r[3]: r for r in got}
    for content in scalars:
        assert by_content[content][4]["rel"] == 0.0  # classé avec les sans-embedding
    # 2e rappel : le None mis en cache (_emb_cache) est resservi sans crash
    got2 = mem.retrieve(QUERY_TEXT, QUERY_EMB, now=NOW, top_k=mem.count())
    assert [r[3] for r in got2] == [r[3] for r in got]

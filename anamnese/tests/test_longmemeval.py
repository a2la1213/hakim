"""Tests du harness LongMemEval-S (proxy de rappel) — 100% synthétique.

AUCUN test ne touche data/memory.db (garde `_forbid_real_db` de conftest.py)
ni le vrai dataset : items forgés, embeddings synthétiques 3-dim injectés
(embed_fn), DB temporaires migrées sous tmp_path. Couvre les 4 cas du brief :
1. recall/hit sur mini-jeu forgé + agrégat par catégorie ;
2. l'ingestion mappe episode_id → session d'origine (retrieve d'un tour d'une
   evidence session = hit) ;
3. robustesse : question sans evidence / haystack vide → miss compté, zéro crash ;
4. le harness n'ouvre JAMAIS data/memory.db (tout en tmp).
"""

import json

import pytest

import config
from eval.longmemeval import (
    build_memory,
    evaluate_question,
    ingest_haystack,
    is_hit,
    load_lme,
    recall_by_category,
    retrieve_ids_flat,
    retrieve_ids_live,
)

# --- Embeddings synthétiques : vecteurs 3-dim FIXES par texte (aucun modèle) ---

Q_CHAT = "quelle est la couleur du chat"
EV_CHAT = "le chat est noir"                     # aligné sur Q_CHAT (+ lexical)
DIST_METEO = "il pleut fort aujourd'hui"         # orthogonal, zéro lexical
Q_TRAIN = "quel est le prix du billet de train"
EV_TRAIN = "je pars demain matin"                # evidence MAL alignée (miss voulu)
DIST_TRAIN = "le prix du billet de train grimpe"  # distracteur aligné + lexical

_VECS = {
    Q_CHAT:     [1.0, 0.0, 0.0],
    EV_CHAT:    [0.9, 0.1, 0.0],
    DIST_METEO: [0.0, 1.0, 0.0],
    Q_TRAIN:    [0.0, 0.0, 1.0],
    EV_TRAIN:   [0.0, 1.0, 0.0],
    DIST_TRAIN: [0.0, 0.1, 0.9],
}


def _embed(text):
    return _VECS[text]  # KeyError = texte non prévu par le test (voulu)


def _item(qid, qtype, question, sessions, evidence):
    """Item au schéma RÉEL de longmemeval_s.json (champs utilisés par le harness).

    sessions : liste de (session_id, [(role, content), ...]).
    """
    return {
        "question_id": qid,
        "question_type": qtype,
        "question": question,
        "answer": "x",
        "haystack_session_ids": [sid for sid, _turns in sessions],
        "haystack_sessions": [
            [{"role": r, "content": c} for r, c in turns] for _sid, turns in sessions
        ],
        "answer_session_ids": evidence,
    }


# --- Cas 1 : hit/miss corrects sur mini-jeu forgé + agrégat par catégorie ---


def test_mini_jeu_hit_et_miss_corrects(tmp_path):
    hit_item = _item(
        "q1", "multi-session", Q_CHAT,
        [("s-ev", [("user", EV_CHAT)]), ("s-bruit", [("user", DIST_METEO)])],
        ["s-ev"],
    )
    miss_item = _item(
        "q2", "temporal-reasoning", Q_TRAIN,
        [("s-ev", [("user", EV_TRAIN)]), ("s-bruit", [("user", DIST_TRAIN)])],
        ["s-ev"],
    )
    r_hit = evaluate_question(hit_item, embed_fn=_embed, k=1, db_dir=tmp_path / "a")
    r_miss = evaluate_question(miss_item, embed_fn=_embed, k=1, db_dir=tmp_path / "b")
    assert r_hit["hit_flat"] is True and r_hit["hit_live"] is True
    assert r_miss["hit_flat"] is False and r_miss["hit_live"] is False


def test_aggregat_par_categorie_et_overall(tmp_path):
    hit_item = _item(
        "q1", "multi-session", Q_CHAT,
        [("s-ev", [("user", EV_CHAT)]), ("s-bruit", [("user", DIST_METEO)])],
        ["s-ev"],
    )
    miss_item = _item(
        "q2", "temporal-reasoning", Q_TRAIN,
        [("s-ev", [("user", EV_TRAIN)]), ("s-bruit", [("user", DIST_TRAIN)])],
        ["s-ev"],
    )
    results = [
        evaluate_question(hit_item, embed_fn=_embed, k=1, db_dir=tmp_path / "a"),
        evaluate_question(miss_item, embed_fn=_embed, k=1, db_dir=tmp_path / "b"),
    ]
    table = recall_by_category(results)
    assert table["multi-session"]["n"] == 1
    assert table["multi-session"]["recall_flat"] == 1.0
    assert table["multi-session"]["recall_live"] == 1.0
    assert table["temporal-reasoning"]["n"] == 1
    assert table["temporal-reasoning"]["recall_flat"] == 0.0
    assert table["temporal-reasoning"]["recall_live"] == 0.0
    assert table["_overall"]["n"] == 2
    assert table["_overall"]["recall_flat"] == 0.5
    assert table["_overall"]["recall_live"] == 0.5


# --- Cas 2 : l'ingestion mappe episode_id → session d'origine ---


def test_ingestion_mappe_episode_vers_session_origine(tmp_path):
    mem = build_memory(tmp_path / "t.db")
    sessions = [
        ("s-ev", [("user", EV_CHAT), ("assistant", DIST_METEO)]),
        ("s-bruit", [("user", EV_TRAIN), ("assistant", DIST_TRAIN)]),
    ]
    item = _item("q1", "multi-session", Q_CHAT, sessions, ["s-ev"])
    ep2sess = ingest_haystack(mem, item, _embed)
    assert len(ep2sess) == 4  # TOUS les tours ingérés, chacun tracé
    attendu = {sid: {c for _r, c in turns} for sid, turns in sessions}
    for eid, sid in ep2sess.items():
        row = mem.db.execute(
            "SELECT content FROM episodes WHERE id=?", (eid,)
        ).fetchone()
        assert row is not None and row[0] in attendu[sid]
    mem.db.close()


def test_retrieve_dun_tour_evidence_est_un_hit(tmp_path):
    mem = build_memory(tmp_path / "t.db")
    item = _item(
        "q1", "multi-session", Q_CHAT,
        [("s-ev", [("user", EV_CHAT)]), ("s-bruit", [("user", DIST_METEO)])],
        ["s-ev"],
    )
    ep2sess = ingest_haystack(mem, item, _embed)
    q_emb = _embed(Q_CHAT)
    ids_live = retrieve_ids_live(mem, Q_CHAT, q_emb, k=1)
    ids_flat = retrieve_ids_flat(mem, q_emb, k=1)
    assert len(ids_live) == 1 and len(ids_flat) == 1
    assert is_hit(ids_live, ep2sess, ["s-ev"]) is True
    assert is_hit(ids_flat, ep2sess, ["s-ev"]) is True
    assert is_hit(ids_live, ep2sess, ["s-bruit"]) is False  # mauvaise session
    mem.db.close()


# --- Cas 3 : robustesse — sans evidence / haystack vide → miss, zéro crash ---


def test_question_sans_evidence_comptee_miss(tmp_path):
    item = _item(
        "q3", "knowledge-update", Q_CHAT,
        [("s1", [("user", EV_CHAT)])],
        [],  # aucune evidence session
    )
    r = evaluate_question(item, embed_fn=_embed, k=2, db_dir=tmp_path)
    assert r["hit_flat"] is False and r["hit_live"] is False


def test_haystack_vide_compte_miss_sans_crash(tmp_path):
    item = _item("q4", "knowledge-update", Q_CHAT, [], ["s-ev"])
    r = evaluate_question(item, embed_fn=_embed, k=2, db_dir=tmp_path)
    assert r["hit_flat"] is False and r["hit_live"] is False
    assert r["n_turns"] == 0
    table = recall_by_category([r])
    assert table["knowledge-update"]["n"] == 1
    assert table["knowledge-update"]["recall_live"] == 0.0


# --- Cas 4 : le harness n'ouvre JAMAIS data/memory.db (tout en tmp) ---


def test_build_memory_refuse_la_vraie_db():
    with pytest.raises(ValueError):
        build_memory(config.DB_PATH)


def test_pipeline_complet_reste_en_tmp(tmp_path):
    # La garde autouse _forbid_real_db (conftest) lèverait si data/memory.db
    # était ouverte pendant ce pipeline complet ; on vérifie en plus que la
    # DB temporaire a bien été créée SOUS tmp (db_dir explicite) et que le
    # chemin par défaut (db_dir=None) passe par un répertoire jetable.
    item = _item(
        "q1", "single-session-user", Q_CHAT,
        [("s-ev", [("user", EV_CHAT)])],
        ["s-ev"],
    )
    r = evaluate_question(item, embed_fn=_embed, k=1, db_dir=tmp_path / "x")
    assert (tmp_path / "x" / "lme.db").exists()
    assert r["hit_live"] is True
    r2 = evaluate_question(item, embed_fn=_embed, k=1)  # db_dir=None → tempfile
    assert r2["hit_live"] is True


# --- load_lme : sous-échantillon équilibré, déterministe, LOGUÉ (jamais muet) ---


def test_load_lme_deterministe_equilibre_et_logue(tmp_path):
    data = (
        [_item(f"a{i}", "multi-session", Q_CHAT,
               [("s1", [("user", EV_CHAT)])], ["s1"]) for i in range(5)]
        + [_item("b1", "knowledge-update", Q_CHAT,
                 [("s1", [("user", EV_CHAT)])], ["s1"])]
        + [_item("c1_abs", "multi-session", Q_CHAT,
                 [("s1", [("user", EV_CHAT)])], ["s1"])]
    )
    path = tmp_path / "lme.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    logs = []
    kept = load_lme(path, sample_per_type=2, seed=0, log=logs.append)
    types = [it["question_type"] for it in kept]
    assert types.count("multi-session") == 2          # sous-échantillonné à 2/5
    assert types.count("knowledge-update") == 1       # moins dispo que demandé : tout
    assert all(not it["question_id"].endswith("_abs") for it in kept)  # _abs exclues

    # déterminisme : même seed → même sélection, dans le même ordre
    kept2 = load_lme(path, sample_per_type=2, seed=0, log=lambda _s: None)
    assert [it["question_id"] for it in kept] == [it["question_id"] for it in kept2]

    # pas de troncature silencieuse : les comptes retenus/disponibles sont logués
    joined = "\n".join(logs)
    assert "2/5" in joined and "1/1" in joined and "_abs" in joined

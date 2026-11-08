"""Tests de l'étage answer-accuracy LongMemEval — 100 % synthétique, SANS Ollama.

AUCUN test ne touche data/memory.db (garde `_forbid_real_db` de conftest.py)
ni le réseau : les appels lecteur/juge sont mockés (chat_fn injecté), les
embeddings sont des vecteurs 3-dim forgés. Couvre le brief :
1. parse_judge : extraction YES/NO robuste (casse, ponctuation, bruit, None) ;
2. substring_match : normalisation lexicale (casse, ponctuation, bornes) ;
3. accuracy_by_category : agrégat par catégorie + _overall + juges illisibles ;
4. lecteur/juge mockés : prompts corrects (question, gold, excerpts,
   troncature) et wiring bout-en-bout d'answer_question sur DB tmp_path.
"""

import pytest

from eval.longmemeval_answer import (
    accuracy_by_category,
    answer_question,
    build_reader_prompt,
    judge_answer,
    parse_judge,
    read_answer,
    substring_match,
)

# --- 1. parse_judge : extraction du verdict YES/NO -----------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("YES", True),
        ("yes.", True),
        ("  Yes, the answer is correct.", True),
        ("**YES**", True),
        ("NO", False),
        ("no", False),
        ("**No**, it contradicts the gold answer.", False),
        ("Let me check.\nNO", False),
        ("OUI", True),          # tolérance français
        ("non.", False),
        ("YES or NO", True),     # premier verdict isolé gagne (règle documentée)
    ],
)
def test_parse_judge_verdicts(raw, expected):
    assert parse_judge(raw) is expected


@pytest.mark.parametrize(
    "raw",
    [
        "",                       # vide
        None,                     # pas de texte
        "The prediction is wrong.",  # aucun mot-verdict isolé
        "Not correct",            # « not » ≠ « no » (frontière de mot)
        "noyes",                  # collé : pas un mot isolé
    ],
)
def test_parse_judge_illisible_retourne_none(raw):
    assert parse_judge(raw) is None


# --- 2. substring_match : contre-vérification lexicale --------------------------


@pytest.mark.parametrize(
    "pred, gold, expected",
    [
        ("I graduated with a Business Administration degree.",
         "Business Administration", True),
        ("The answer is: 42.", "42", True),
        ("blue-green, I think", "Blue green", True),   # casse + ponctuation
        ("It was Johnson.", "johnson", True),
        ("I don't know.", "Business Administration", False),
        ("Business", "Business Administration", False),  # gold plus long : miss
        ("anything", "", False),                          # gold vide : jamais OK
        ("", "42", False),
    ],
)
def test_substring_match(pred, gold, expected):
    assert substring_match(pred, gold) is expected


# --- 3. accuracy_by_category : agrégat par catégorie + _overall -----------------


def _res(qtype, judge, sub, hit):
    return {
        "question_id": "q",
        "question_type": qtype,
        "judge": judge,
        "substring": sub,
        "hit_live": hit,
    }


def test_accuracy_by_category_et_overall():
    results = [
        _res("multi-session", True, True, True),
        _res("multi-session", False, False, True),
        _res("multi-session", None, True, False),   # juge illisible = INCORRECT
        _res("knowledge-update", True, False, True),
    ]
    table = accuracy_by_category(results)
    ms = table["multi-session"]
    assert ms["n"] == 3
    assert ms["acc_llm"] == pytest.approx(1 / 3)   # None ne compte PAS correct
    assert ms["acc_sub"] == pytest.approx(2 / 3)
    assert ms["recall_live"] == pytest.approx(2 / 3)
    assert ms["n_judge_unparsed"] == 1
    ku = table["knowledge-update"]
    assert (ku["n"], ku["acc_llm"], ku["acc_sub"]) == (1, 1.0, 0.0)
    ov = table["_overall"]
    assert ov["n"] == 4
    assert ov["acc_llm"] == pytest.approx(2 / 4)
    assert ov["acc_sub"] == pytest.approx(2 / 4)
    assert ov["recall_live"] == pytest.approx(3 / 4)
    assert ov["n_judge_unparsed"] == 1


def test_accuracy_by_category_vide():
    assert accuracy_by_category([]) == {}


# --- 4. lecteur/juge mockés : prompts + wiring (aucun Ollama) --------------------


def test_read_answer_prompt_contient_question_et_excerpts_tronques():
    item = {"question": "What color is the cat?", "question_date": "2023/05/01"}
    long_turn = "z" * 5000
    prompts = []

    def fake_chat(prompt):
        prompts.append(prompt)
        return "  The cat is black.  "

    out = read_answer(item, [("user", "the cat is black"),
                             ("assistant", long_turn)],
                      chat_fn=fake_chat, max_turn_chars=100)
    assert out == "The cat is black."          # strip du lecteur
    assert len(prompts) == 1
    p = prompts[0]
    assert "What color is the cat?" in p
    assert "2023/05/01" in p
    assert "[1] (user) the cat is black" in p
    assert "z" * 100 + " [...]" in p           # tronqué à max_turn_chars
    assert "z" * 101 not in p                  # rien au-delà


def test_build_reader_prompt_sans_excerpt_ne_crashe_pas():
    p = build_reader_prompt({"question": "q?", "question_date": None}, [])
    assert "no excerpt retrieved" in p and "unknown" in p


def test_judge_answer_prompt_et_verdict_mockes():
    prompts = []

    def fake_chat(prompt):
        prompts.append(prompt)
        return "**No**, it contradicts."

    verdict, raw = judge_answer("What team?", "Lakers", "The Celtics",
                                chat_fn=fake_chat)
    assert verdict is False
    assert raw == "**No**, it contradicts."
    p = prompts[0]
    assert "Gold (correct) answer: Lakers" in p
    assert "Predicted answer: The Celtics" in p
    assert "What team?" in p


# Embeddings synthétiques 3-dim (aucun modèle, aucun réseau).
_Q = "quelle est la couleur du chat"
_EV = "le chat est noir"
_DIST = "il pleut fort aujourd'hui"
_VECS = {_Q: [1.0, 0.0, 0.0], _EV: [0.9, 0.1, 0.0], _DIST: [0.0, 1.0, 0.0]}


def test_answer_question_bout_en_bout_mocke(tmp_path):
    """Wiring complet : ingestion tmp → retrieve → lecteur mocké → juge mocké.

    Le fake_chat route lecteur/juge sur le gabarit (comme le CLI) : le juge
    reçoit gold + prédiction, le lecteur reçoit l'evidence récupérée.
    """
    item = {
        "question_id": "q1",
        "question_type": "multi-session",
        "question": _Q,
        "answer": "noir",
        "question_date": "2023/04/10",
        "haystack_session_ids": ["s-ev", "s-bruit"],
        "haystack_sessions": [
            [{"role": "user", "content": _EV}],
            [{"role": "user", "content": _DIST}],
        ],
        "answer_session_ids": ["s-ev"],
    }
    seen = {"reader": None, "judge": None}

    def fake_chat(prompt):
        if "Gold (correct) answer:" in prompt:
            seen["judge"] = prompt
            return "YES"
        seen["reader"] = prompt
        return "Le chat est noir."

    r = answer_question(item, fake_chat, embed_fn=_VECS.__getitem__, k=2,
                        db_dir=tmp_path)
    assert r["question_id"] == "q1" and r["question_type"] == "multi-session"
    assert r["predicted"] == "Le chat est noir."
    assert r["judge"] is True and r["judge_raw"] == "YES"
    assert r["substring"] is True          # « noir » ⊂ prédiction normalisée
    assert r["hit_live"] is True           # l'evidence session est dans le top-k
    assert r["n_turns"] == 2
    assert _EV in seen["reader"]           # le lecteur a bien vu l'evidence
    assert "Gold (correct) answer: noir" in seen["judge"]
    assert "Le chat est noir." in seen["judge"]

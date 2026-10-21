"""Tests Phase 1.0 — recalibration des poids du rappel. 100% synthétique.

Verrouille deux choses :
  1. Avec les poids de `config`, la pertinence n'est PLUS écrasée par la
     récence/importance : sur un mini-jeu conçu pour piéger l'ancien scoring
     (distracteurs frais+importants vs souvenirs vieux mais pertinents),
     le score live passe le gate face au baseline plat.
  2. Le contrat de `Memory.retrieve` est inchangé après le changement de
     constantes : même arité de tuple, top_k respecté, tri décroissant.

AUCUN test ne touche data/memory.db (garde `_forbid_real_db` de conftest.py).
"""

import time

import migrations
from eval.run_eval import gate, make_score_live, score_flat
from memory import Memory

# --- Cas 1 : gate de régression — la récence ne trompe plus le scoring -------

_NOW = 1_800_000_000.0
_OLD = _NOW - 720 * 3600.0  # 30 jours

# 3 souvenirs VIEUX mais pertinents (cosine ~1 avec la requête, importance
# modeste) noyés sous 8 distracteurs FRAIS et « importants » mais hors-sujet
# (cosine 0). L'ancien scoring (W_RECENCY=W_IMPORTANCE=1.0) donnait 2.0 à
# chaque distracteur (rec=1 + imp=1) contre ~1.3 aux pertinents -> p@6 = 0.
_EPISODES = [
    {"id": 1, "ts": _OLD, "role": "semantic", "content": "vieux souvenir pertinent un",
     "importance": 0.3, "embedding": [1.0, 0.0]},
    {"id": 2, "ts": _OLD, "role": "semantic", "content": "vieux souvenir pertinent deux",
     "importance": 0.3, "embedding": [0.95, 0.05]},
    {"id": 3, "ts": _OLD, "role": "semantic", "content": "vieux souvenir pertinent trois",
     "importance": 0.3, "embedding": [0.9, 0.1]},
] + [
    {"id": 4 + i, "ts": _NOW, "role": "user",
     "content": f"bavardage frais hors sujet numero {i}",
     "importance": 1.0, "embedding": [0.0, 1.0]}
    for i in range(8)
]

_QUERIES = [{"query": "alpha", "expected": [1, 2, 3], "note": "vieux mais pertinents"}]


def _embed_synthetique(text):
    return {"alpha": [1.0, 0.0]}[text]


def test_gate_recence_ne_trompe_plus_le_scoring():
    """Le score live (poids de config ACTUELS) doit passer le gate face au
    plat sur le mini-jeu piège : les 3 pertinents vieux doivent rester devant
    les 8 distracteurs frais/importants. (RED avec les anciens poids 1.0/1.0.)
    """
    res = gate(make_score_live(_NOW), score_flat, _QUERIES, _EPISODES,
               k=6, embed_fn=_embed_synthetique)
    assert res["baseline"] == 1.0  # le plat retrouve les 3 pertinents
    assert res["candidate"] == 1.0  # le live aussi : pertinence non écrasée
    assert res["passes"] is True


# --- Cas 2 : contrat de Memory.retrieve inchangé ------------------------------


def test_retrieve_contrat_inchange(tmp_path):
    """DB temporaire migrée + 3 épisodes : retrieve renvoie toujours des tuples
    (score, ts, role, content, détails) triés décroissants, top_k respecté.
    """
    mem = Memory(db_path=tmp_path / "t.db")
    try:
        migrations.migrate(mem.db)
        mem.add("user", "alpha un", importance=0.5, embedding=[1.0, 0.0])
        mem.add("assistant", "beta deux", importance=0.5, embedding=[0.0, 1.0])
        mem.add("semantic", "gamma trois", importance=0.5, embedding=[0.9, 0.1])

        out = mem.retrieve("alpha", [1.0, 0.0], now=time.time(), top_k=2)

        assert len(out) == 2  # top_k respecté
        for item in out:
            score, ts, role, content, details = item  # arité 5 inchangée
            assert isinstance(score, float)
            assert isinstance(ts, float)
            assert isinstance(role, str)
            assert isinstance(content, str)
            assert set(details) == {"rel", "lex", "rec"}
        # tri décroissant + le plus pertinent (cosine 1.0 + lexical) en tête
        assert out[0][0] >= out[1][0]
        assert out[0][3] == "alpha un"
        # top_k > nb d'épisodes : renvoie tout, sans erreur
        assert len(mem.retrieve("alpha", [1.0, 0.0], top_k=6)) == 3
    finally:
        mem.db.close()

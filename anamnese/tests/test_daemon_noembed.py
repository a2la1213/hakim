"""Le daemon écrit reflection/outreach SANS embedding (économie compute+stockage) :
ils deviennent orphelins, absents du recall et du jardinage — mais lus par texte
(de-echo, rêve, dashboard). DB temp, jamais data/memory.db."""
import json

import pytest

import config
import daemon
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [1.0, 0.0, 0.0, 0.0])
    monkeypatch.setattr(daemon.embeddings, "embed", lambda t: [1.0, 0.0, 0.0, 0.0])
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


class FakeEng:
    def health(self):
        return True
    def chat(self, messages, stream=False, think=False):
        # une pensée + PROACTIF non (pas d'outreach ici)
        return "Une intuition neuve sur le batiment.\nPROACTIF: non"


def test_reflection_ecrite_sans_embedding(mem, monkeypatch):
    monkeypatch.setattr(daemon.embeddings, "embed",
                        lambda t: (_ for _ in ()).throw(AssertionError("embed appelé !")))
    # reflect ne doit PAS appeler embed pour la reflection
    daemon.reflect(FakeEng(), mem)
    row = mem.db.execute(
        "SELECT embedding, rubric_id FROM episodes WHERE role='reflection' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert json.loads(row[0]) == []                      # embedding vide
    assert row[1] is None                                # orphelin (non routé)


def test_reflection_absente_du_recall_et_orphans(mem):
    mem.add("reflection", "pensée batiment", importance=0.4, embedding=[])
    mem.add("semantic", "fait batiment", importance=0.7, embedding=[1.0, 0.0, 0.0, 0.0])
    mem.db.commit()
    res = mem.retrieve("batiment", [1.0, 0.0, 0.0, 0.0], top_k=6)
    assert "reflection" not in {r[2] for r in res}       # exclue du recall (T1)
    # orphans_report (via mcp) exclut déjà reflection par rôle — vérif directe du filtre :
    import taxonomy
    clusters = taxonomy.orphan_clusters(mem.db)
    ids = [i for c in clusters for i in c["episode_ids"]]
    refl_id = mem.db.execute("SELECT id FROM episodes WHERE role='reflection'").fetchone()[0]
    assert refl_id not in ids                            # invisible au jardinage nocturne


def test_de_echo_toujours_actif_sans_embedding(mem):
    # 2 pensées quasi-identiques → la 2e sautée par la de-echo (lexical sur TEXTE, pas embedding)
    eng = FakeEng()
    daemon.reflect(eng, mem)
    n1 = mem.db.execute("SELECT COUNT(*) FROM episodes WHERE role='reflection'").fetchone()[0]
    daemon.reflect(eng, mem)                              # même sortie → doublon
    n2 = mem.db.execute("SELECT COUNT(*) FROM episodes WHERE role='reflection'").fetchone()[0]
    assert n2 == n1                                       # anti-boucle intact

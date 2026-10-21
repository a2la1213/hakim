"""Le bruit daemon (reflection/outreach) est exclu du rappel PAR DÉFAUT, mais
inclus si explicitement demandé via kinds. DB temp, jamais data/memory.db."""
import pytest

import config
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [1.0, 0.0, 0.0, 0.0])
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _seed(mem):
    # même embedding pour tous → même pertinence ; seul le rôle diffère
    mem.add("semantic", "fait durable batiment", importance=0.7, embedding=[1.0, 0.0, 0.0, 0.0])
    mem.add("reflection", "pensée daemon sur batiment", importance=0.4, embedding=[1.0, 0.0, 0.0, 0.0])
    mem.add("outreach", "sollicitation batiment", importance=0.5, embedding=[1.0, 0.0, 0.0, 0.0])
    mem.db.commit()


def test_recall_defaut_exclut_reflection_outreach(mem):
    _seed(mem)
    res = mem.retrieve("batiment", [1.0, 0.0, 0.0, 0.0], top_k=6)
    roles = {r[2] for r in res}
    assert "semantic" in roles
    assert "reflection" not in roles and "outreach" not in roles


def test_kinds_positif_prime_sur_exclude(mem):
    _seed(mem)
    res = mem.retrieve("batiment", [1.0, 0.0, 0.0, 0.0], top_k=6, kinds=["reflection"])
    roles = {r[2] for r in res}
    assert roles == {"reflection"}                      # kinds gouverne, exclude ignoré


def test_exclude_roles_surchargeable(mem):
    _seed(mem)
    res = mem.retrieve("batiment", [1.0, 0.0, 0.0, 0.0], top_k=6, exclude_roles=())
    roles = {r[2] for r in res}
    assert "reflection" in roles                        # exclude vidé → tout revient

"""(11/11) une scène qui échoue sous la contention (« database is locked ») ne doit jamais laisser la connexion des échanges dans une
transaction ouverte : sinon chacune de ses écritures suivantes échoue et le WAL grossit sans fin (vu du 10/11 23:04 au 11/11 05:40)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import echanges  # noqa: E402


class FausseBase:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


class FausseMemoire:
    def __init__(self):
        self.db = FausseBase()


def test_une_scene_qui_echoue_relache_sa_transaction(monkeypatch):
    import scenes
    mem = FausseMemoire()

    def casse(*a, **k):
        import sqlite3
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(scenes, "avancer", casse)
    monkeypatch.setattr(scenes, "clore_si_silence", casse)
    echanges._scene(mem, {"ahmed": "x"}, 1, embed=lambda t: [0.0])
    echanges._scene_silence(mem, embed=lambda t: [0.0])
    assert mem.db.rollbacks == 2


def test_une_scene_qui_reussit_ne_relache_rien(monkeypatch):
    import scenes
    mem = FausseMemoire()
    monkeypatch.setattr(scenes, "avancer", lambda *a, **k: [])
    monkeypatch.setattr(scenes, "clore_si_silence", lambda *a, **k: False)
    echanges._scene(mem, {"ahmed": "x"}, 1, embed=lambda t: [0.0])
    echanges._scene_silence(mem, embed=lambda t: [0.0])
    assert mem.db.rollbacks == 0

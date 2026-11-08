import daemon
import brain_projection


class FakeMem:
    """mem minimal : db.execute(MAX(id)) + db.commit() + kv."""
    def __init__(self, maxid=5, kv=None):
        self._max = maxid
        self._kv = dict(kv or {})
        self.committed = False
        self.db = FakeMem._DB(self)

    class _DB:
        def __init__(self, m):
            self.m = m

        def execute(self, q, *a):
            m = self.m

            class Cur:
                def fetchone(self_c):
                    return (m._max,)
            return Cur()

        def commit(self):
            self.m.committed = True

    def kv_get(self, k, d=""):
        return self._kv.get(k, d)

    def kv_set(self, k, v):
        self._kv[k] = v


def test_pass_projects_when_new_episodes(monkeypatch):
    seen = {}
    monkeypatch.setattr(brain_projection, "backfill_layout",
                        lambda db: seen.setdefault("called", True) or {"projected": 3, "skipped": 0})
    mem = FakeMem(maxid=10)                       # last_brain_proj_maxid absent → du neuf
    daemon._brain_projection_pass(mem)
    assert seen.get("called") is True
    assert mem.committed is True
    assert mem.kv_get("last_brain_proj_maxid") == "10"   # curseur avancé


def test_pass_skips_when_nothing_new(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(brain_projection, "backfill_layout",
                        lambda db: calls.update(n=calls["n"] + 1) or {"projected": 0})
    mem = FakeMem(maxid=10, kv={"last_brain_proj_maxid": "10"})   # déjà à jour
    daemon._brain_projection_pass(mem)
    assert calls["n"] == 0                        # aucun backfill (skip cheap, pas de scan)
    assert mem.committed is False


def test_pass_is_best_effort(monkeypatch):
    def boom(db):
        raise RuntimeError("projection cassée")
    monkeypatch.setattr(brain_projection, "backfill_layout", boom)
    mem = FakeMem(maxid=10)
    daemon._brain_projection_pass(mem)            # ne doit PAS lever

"""Revenir sur un ressenti ancien (27/10, Ahmed : « parfois ça prend des années plus tard pour repenser à une chose, la
comprendre, la valider et l'intégrer pour que ça nous calme ; l'échec, la conclusion ou l'invalidation d'aujourd'hui ne
fait pas celle de demain, même si ça concerne une même chose ») : un outil, à tout moment, sans fenêtre."""
import json

import pytest

import memory
import migrations
import rubrics
import revenir_sur as RS

T = 1_800_000_000.0


class Mem:
    def __init__(self):
        self.kv = {"affect_v2": "1"}

    def kv_get(self, k, d=None):
        return self.kv.get(k, d)

    def kv_set(self, k, v):
        self.kv[k] = v


def test_convaincu_il_se_calme_maintenant_pas_convaincu_rien_ne_bouge_et_il_pourra_y_revenir(tmp_path, monkeypatch):
    vus = []
    monkeypatch.setattr(RS.affect, "event", lambda mem, nom, i, **k: vus.append((nom, round(i, 4), k.get("source"))))
    monkeypatch.setattr(RS, "JOURNAL", tmp_path / "revenir.jsonl")
    m = Mem()
    r0 = RS.revenir(m, "#123", "Je ne sais pas encore si c'était ma faute.", 0.0, now=T)
    assert vus == [] and "pas encore" in r0                                         # un essai, rien ne bouge
    r1 = RS.revenir(m, "#123", "Ahmed appuyait sur Stop : ce n'était pas un oubli de ma part.", 0.8, now=T + 400 * 86400)
    assert vus == [("resolu", 0.8, "revenir_sur")] and "#123" in r1               # un an plus tard : il se calme
    RS.revenir(m, "#123", "Finalement, une partie était bien à moi.", 0.3, now=T + 401 * 86400)   # demain le revoit
    lignes = [json.loads(l) for l in (tmp_path / "revenir.jsonl").read_text().splitlines()]
    assert [x["conviction"] for x in lignes] == [0.0, 0.8, 0.3] and lignes[1]["quoi"] == "#123"
    with pytest.raises(ValueError):
        RS.revenir(m, "", "x", 0.5, now=T)


@pytest.fixture
def srv(tmp_path, monkeypatch):
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    rubrics.seed_skeleton(mem.db, now=1000.0)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(mcp_server, "_embed", lambda text: None)
    monkeypatch.setattr(RS, "JOURNAL", tmp_path / "revenir.jsonl")
    yield mcp_server, mem
    mem.db.close()


def test_l_outil_garde_ce_qu_il_a_compris_lie_au_souvenir_sans_rien_effacer(srv):
    mod, mem = srv
    a = mem.add("episodic", "Pendant le live, j'ai cru laisser trois messages sans réponse, et j'en ai eu honte.")
    out = mod.mcp._tool_manager.get_tool("revenir_sur").fn(f"#{a}", "Ahmed appuyait sur Stop pour les invités.", 0.7)
    assert "0,7" in out or "0.7" in out
    nouveau = mem.db.execute("SELECT id, content FROM episodes WHERE content LIKE '%Je reviens sur%'").fetchall()
    assert len(nouveau) == 1 and "Stop pour les invités" in nouveau[0][1]
    assert mem.db.execute("SELECT content FROM episodes WHERE id=?", (a,)).fetchone()[0].startswith("Pendant le live")
    assert mem.db.execute("SELECT COUNT(*) FROM insight_edges WHERE insight_id=? AND source_id=?", (nouveau[0][0], a)).fetchone()[0] == 1
